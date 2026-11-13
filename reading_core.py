"""Shared data and extraction functions for Hermes Reading."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import sqlite3
import subprocess
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
import trafilatura
import fitz
from plugins.plugin_storage import plugin_data_dir


PLUGIN_ID = "hermes-reading"
DEFAULT_SOURCES = [
    {"id": "hacker-news", "name": "Hacker News", "url": "https://hnrss.org/frontpage"},
    {"id": "lobsters", "name": "Lobsters", "url": "https://lobste.rs/rss"},
    {"id": "arxiv-ai", "name": "arXiv · AI", "url": "https://rss.arxiv.org/rss/cs.AI"},
    {"id": "simon-willison", "name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
    {"id": "openai", "name": "OpenAI News", "url": "https://openai.com/news/rss.xml"},
]
MAX_BYTES = 12 * 1024 * 1024
MAX_TEXT = 120_000
_DATABASE_INITIALIZED = False
SUMMARY_LANGUAGES = ("English", "Polish", "Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese")


def db_path() -> Path:
    root = Path(plugin_data_dir(PLUGIN_ID))
    root.mkdir(parents=True, exist_ok=True)
    return root / "reading.sqlite3"


def connect() -> sqlite3.Connection:
    global _DATABASE_INITIALIZED
    db = sqlite3.connect(db_path())
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1, added_at INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '', saved INTEGER NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '', published_at INTEGER NOT NULL DEFAULT 0,
        fetched_at INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT 'article',
        status TEXT NOT NULL DEFAULT 'done', step TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', qa_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}', transcript_method TEXT NOT NULL DEFAULT ''
    )""")
    db.execute("CREATE TABLE IF NOT EXISTS plugin_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    existing = {row[1] for row in db.execute("PRAGMA table_info(items)")}
    for column, declaration in (
        ("kind", "TEXT NOT NULL DEFAULT 'article'"), ("status", "TEXT NOT NULL DEFAULT 'done'"),
        ("step", "TEXT NOT NULL DEFAULT ''"), ("error", "TEXT NOT NULL DEFAULT ''"),
        ("qa_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"), ("transcript_method", "TEXT NOT NULL DEFAULT ''"),
    ):
        if column not in existing:
            db.execute(f"ALTER TABLE items ADD COLUMN {column} {declaration}")
    seeded = db.execute("SELECT value FROM plugin_meta WHERE key='default_sources_seeded'").fetchone()
    if not seeded:
        for source in DEFAULT_SOURCES:
            db.execute("INSERT OR IGNORE INTO sources(id,name,url,enabled,added_at) VALUES(?,?,?,?,?)",
                       (source["id"], source["name"], source["url"], 1, int(time.time())))
        db.execute("INSERT INTO plugin_meta(key,value) VALUES('default_sources_seeded','1')")
    if not _DATABASE_INITIALIZED:
        db.execute("UPDATE items SET status='error',step='',error='Reading was interrupted by a Hermes restart.' WHERE status='working'")
        _DATABASE_INITIALIZED = True
    db.commit()
    return db


def summary_language() -> str:
    db = connect()
    row = db.execute("SELECT value FROM plugin_meta WHERE key='summary_language'").fetchone()
    db.close()
    return normalize_summary_language(row[0] if row else "English")


def normalize_summary_language(language: object) -> str:
    value = str(language or "English").strip()
    return value if value in SUMMARY_LANGUAGES else "English"


def set_summary_language(language: str) -> str:
    value = normalize_summary_language(language)
    db = connect()
    db.execute("INSERT INTO plugin_meta(key,value) VALUES('summary_language',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (value,))
    db.commit()
    db.close()
    return value


def public_https(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use a public HTTPS address.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise ValueError("Local and private addresses are not allowed.")
    try:
        resolved = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("The host could not be resolved.") from exc
    if not resolved:
        raise ValueError("The host could not be resolved.")
    for row in resolved:
        address = ipaddress.ip_address(row[4][0].split("%", 1)[0])
        if not address.is_global:
            raise ValueError("Local and private addresses are not allowed.")
    return url


def fetch(url: str, accept: str = "text/html,application/pdf,application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.5") -> tuple[bytes, str, str]:
    current = public_https(url)
    headers = {"User-Agent": "HermesReading/0.1 (+public feed and article reader)", "Accept": accept}
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        for _ in range(5):
            public_https(current)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    target = response.headers.get("location")
                    if not target:
                        raise ValueError("The source returned an invalid redirect.")
                    current = public_https(urljoin(current, target))
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("The source is larger than 12 MB.")
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", "").lower(), str(response.url)
    raise ValueError("Too many redirects.")


def refresh() -> dict:
    db = connect()
    updated = 0
    failed = []
    for source in db.execute("SELECT id,name,url FROM sources WHERE enabled=1").fetchall():
        try:
            body, _content_type, _final_url = fetch(source["url"], "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5")
            parsed = feedparser.parse(body)
            if parsed.bozo and not parsed.entries:
                raise ValueError("Feed could not be parsed.")
            for entry in parsed.entries[:80]:
                link = str(entry.get("link", "")).strip()
                if not link:
                    continue
                title = str(entry.get("title", "Untitled")).strip()[:400]
                summary = trafilatura.extract(str(entry.get("summary", "")), output_format="txt") or ""
                published = 0
                if entry.get("published_parsed"):
                    try:
                        published = int(time.mktime(entry.published_parsed))
                    except (TypeError, ValueError, OverflowError):
                        pass
                item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, link))
                db.execute("""INSERT INTO items(id,url,title,source,summary,published_at,fetched_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title, source=excluded.source, summary=excluded.summary,
                    published_at=excluded.published_at, fetched_at=excluded.fetched_at""",
                    (item_id, link, title, source["name"], summary[:2000], published, int(time.time())))
                updated += 1
            db.commit()
        except Exception as exc:
            failed.append({"source": source["name"], "error": str(exc)[:180]})
    db.close()
    return {"updated": updated, "failed": failed, "refreshed_at": int(time.time())}


def search(query: str = "", saved_only: bool = False, limit: int = 50) -> list[dict]:
    db = connect()
    clauses, args = [], []
    if query.strip():
        term = f"%{query.strip()}%"
        clauses.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
        args.extend((term, term, term))
    if saved_only:
        clauses.append("saved=1")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(f"SELECT id,url,title,source,summary,saved,note,published_at,fetched_at FROM items{where} ORDER BY published_at DESC, fetched_at DESC LIMIT ?", (*args, max(1, min(limit, 100)))).fetchall()
    db.close()
    return [dict(row) for row in rows]


def read_url(url: str) -> dict:
    url = public_https(url)
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.lower() in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        result = read_youtube(url)
        metadata = {k: result.get(k) for k in ("author", "published", "site")}
        db = connect()
        db.execute("""INSERT INTO items(id,url,title,source,summary,content,fetched_at,kind,status,metadata_json,transcript_method)
            VALUES(?,?,?,?,?,?,?,?, 'done',?,?) ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,content=excluded.content,fetched_at=excluded.fetched_at,kind=excluded.kind,status='done',metadata_json=excluded.metadata_json,transcript_method=excluded.transcript_method""",
            (result["id"], result["url"], result["title"], "YouTube", "", result["text"], int(time.time()), "video", json.dumps(metadata), result["transcript_method"]))
        db.commit(); db.close()
        db = connect()
        row = db.execute("SELECT id,saved,note FROM items WHERE url=?", (result["url"],)).fetchone()
        db.close()
        result["id"] = row["id"]
        result["saved"] = bool(row["saved"])
        result["note"] = row["note"]
        return result
    if parsed.hostname and parsed.hostname.lower() in {"arxiv.org", "www.arxiv.org"}:
        import re
        match = re.search(r"/(?:abs|html|pdf)/([^/?#]+)", parsed.path)
        if match and "/pdf/" not in parsed.path:
            url = f"https://arxiv.org/pdf/{match.group(1).removesuffix('.pdf')}"
    body, content_type, final_url = fetch(url)
    metadata = {}
    if "pdf" in content_type or body[:5] == b"%PDF-":
        document = fitz.open(stream=body, filetype="pdf")
        title = (document.metadata or {}).get("title") or Path(urlparse(final_url).path).name or "PDF document"
        text = "\n\n".join(page.get_text("text") for page in document)
        document.close()
    else:
        title, text, metadata = extract_html(body, final_url)
        if not text:
            text = trafilatura.extract(body, url=final_url, include_comments=False, include_tables=True, output_format="txt") or ""
            meta = trafilatura.extract_metadata(body, default_url=final_url) if text else None
            title = title or (meta.title if meta else "")
            metadata = metadata or {"author": getattr(meta, "author", None), "published": getattr(meta, "date", None), "site": getattr(meta, "sitename", None)}
        title = title or Path(urlparse(final_url).path).name or urlparse(final_url).hostname or "Article"
    text = text.strip()[:MAX_TEXT]
    if len(text) < 200:
        raise ValueError("No readable article text was found. It may need a sign-in or rely on scripts.")
    db = connect()
    existing = db.execute("SELECT id,saved,note FROM items WHERE url=?", (final_url,)).fetchone()
    item_id = existing["id"] if existing else str(uuid.uuid5(uuid.NAMESPACE_URL, final_url))
    kind = "paper" if "arxiv.org" in (urlparse(final_url).hostname or "") else ("pdf" if "pdf" in content_type or body[:5] == b"%PDF-" else "article")
    db.execute("""INSERT INTO items(id,url,title,source,content,fetched_at,status,kind,metadata_json) VALUES(?,?,?,?,?,?,'done',?,?)
        ON CONFLICT(url) DO UPDATE SET title=excluded.title, content=excluded.content, fetched_at=excluded.fetched_at,metadata_json=excluded.metadata_json""",
        (item_id, final_url, title[:400], urlparse(final_url).hostname or "Web", text, int(time.time()), kind, json.dumps(metadata)))
    db.commit()
    row = db.execute("SELECT saved,note FROM items WHERE id=?", (item_id,)).fetchone()
    db.close()
    return {"id": item_id, "url": final_url, "title": title[:400], "text": text, "saved": bool(row["saved"]), "note": row["note"], "kind": kind, **metadata}


def extract_html(body: bytes, url: str) -> tuple[str, str, dict]:
    """Run the same Defuddle + linkedom extraction used by Lectio; retain a Python fallback."""
    bridge = Path(__file__).with_name("defuddle-extract.bundle.mjs")
    node = shutil.which("node")
    if bridge.exists() and node:
        try:
            env = {key: value for key, value in {
                "PATH": str(Path(node).parent), "HOME": str(Path.home()),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
            }.items() if value}
            result = subprocess.run([node, str(bridge), url], input=body, capture_output=True, timeout=45, check=False, env=env)
            if result.returncode == 0:
                parsed = json.loads(result.stdout)
                return str(parsed.get("title") or ""), str(parsed.get("text") or ""), {k: parsed.get(k) for k in ("author", "published", "site")}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    return "", "", {}


def read_youtube(url: str) -> dict:
    """Read captions first; local audio transcription is an optional install extra."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise ValueError("YouTube reading needs the optional yt-dlp dependency.") from exc
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        from urllib.parse import parse_qs
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if not video_id:
            match = re.match(r"^/(?:shorts|embed|live)/([\w-]{11})", parsed.path)
            video_id = match.group(1) if match else ""
    if not video_id or not re.fullmatch(r"[\w-]{11}", video_id):
        raise ValueError("This does not look like a supported YouTube video link.")
    base = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory(prefix="hermes-reading-video-") as tmp:
        options = {"quiet": True, "no_warnings": True, "skip_download": True,
                   "writesubtitles": True, "writeautomaticsub": True,
                   "subtitleslangs": ["pl.*", "en.*"], "subtitlesformat": "vtt",
                   "outtmpl": str(Path(tmp) / "%(id)s.%(ext)s"), "socket_timeout": 20,
                   "max_filesize": MAX_BYTES, "noplaylist": True}
        try:   # metadata first, so a refused subtitle download (YouTube answers 429) does not end the read: the audio fallback below still runs
            with yt_dlp.YoutubeDL({**options, "writesubtitles": False, "writeautomaticsub": False}) as ydl:
                info = ydl.extract_info(base, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError("YouTube refused the request right now. Try again in a few minutes.") from exc
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([base])
        except yt_dlp.utils.DownloadError:
            pass
        duration = int(info.get("duration") or 0)
        if duration > 3 * 60 * 60:
            raise ValueError("Videos longer than three hours are not supported.")
        caption_files = list(Path(tmp).glob("*.vtt"))
        caption_files.sort(key=lambda p: ("pl" not in p.name.lower(), "en" not in p.name.lower(), p.name))
        text = parse_vtt(caption_files[0].read_text(errors="replace")) if caption_files else ""
        transcript_method = "captions"
        if len(text) < 400:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ValueError("No usable captions were available. Local transcription is optional; faster-whisper must be available in the Hermes plugin runtime.") from exc
            if duration > 75 * 60:
                raise ValueError("Without captions, local transcription is limited to videos up to 75 minutes.")
            audio_options = {**options, "skip_download": False, "writesubtitles": False,
                             "writeautomaticsub": False, "format": "bestaudio/best",
                             "max_filesize": 100 * 1024 * 1024,
                             "outtmpl": str(Path(tmp) / "audio.%(ext)s")}
            with yt_dlp.YoutubeDL(audio_options) as ydl:
                ydl.download([base])
            audio = next((p for p in Path(tmp).glob("audio.*") if p.suffix.lower() not in {".vtt", ".json", ".part"}), None)
            if not audio:
                raise ValueError("Could not download the audio for local transcription.")
            model = WhisperModel("small", device="cpu", compute_type="int8")
            segments, _info = model.transcribe(str(audio), vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            transcript_method = "local Whisper transcription"
    if len(text) < 200:
        raise ValueError("No usable captions or transcript were found.")
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, base)), "url": base,
            "title": str(info.get("title") or "YouTube video")[:400],
            "text": text[:MAX_TEXT], "saved": False, "note": "", "kind": "video",
            "author": info.get("uploader"), "published": info.get("upload_date"),
            "site": "YouTube", "transcript_method": transcript_method}


def parse_vtt(vtt: str) -> str:
    lines, previous = [], ""
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&amp;", "&", line)
        line = re.sub(r"&lt;", "<", line)
        line = re.sub(r"&gt;", ">", line).strip()
        if not line or line == previous:
            continue
        if previous and line.startswith(previous):
            lines.pop()
        lines.append(line)
        previous = line
    return " ".join(lines)


def save_item(url: str, title: str, note: str = "") -> dict:
    url = public_https(url)
    db = connect()
    item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    db.execute("""INSERT INTO items(id,url,title,source,saved,note,fetched_at) VALUES(?,?,?,?,1,?,?)
        ON CONFLICT(url) DO UPDATE SET saved=1, note=excluded.note, title=CASE WHEN excluded.title!='' THEN excluded.title ELSE items.title END""",
        (item_id, url, title.strip()[:400] or url, urlparse(url).hostname or "Web", note.strip()[:1000], int(time.time())))
    db.commit()
    db.close()
    return {"id": item_id, "url": url, "saved": True}


def sources() -> list[dict]:
    db = connect()
    result = [dict(row) for row in db.execute("SELECT id,name,url,enabled FROM sources ORDER BY name")]
    db.close()
    return result


def list_readings(limit: int = 100) -> list[dict]:
    db = connect()
    rows = db.execute("SELECT id,url,title,source,summary,saved,note,published_at,fetched_at,kind,status,step,error,qa_json,metadata_json,transcript_method FROM items WHERE content!='' OR status IN ('working','error') OR saved=1 ORDER BY fetched_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    db.close()
    result = []
    for row in rows:
        item = dict(row)
        item["qa"] = json.loads(item.pop("qa_json") or "[]")
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        result.append(item)
    return result


def get_reading(item_id: str) -> dict | None:
    db = connect()
    row = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    db.close()
    if not row:
        return None
    result = dict(row)
    result["qa"] = json.loads(result.pop("qa_json") or "[]")
    result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    return result


def create_reading(url: str) -> dict:
    safe_url = public_https(url)
    item_id = str(uuid.uuid4())
    now = int(time.time())
    db = connect()
    existing = db.execute("SELECT id,status FROM items WHERE url=?", (safe_url,)).fetchone()
    if existing:
        if existing["status"] == "working":
            db.close()
            raise ValueError("This source is already being read.")
        item_id = existing["id"]
        db.execute("UPDATE items SET status='working',step='fetching',error='',fetched_at=? WHERE id=?", (now, item_id))
    else:
        db.execute("INSERT INTO items(id,url,title,source,status,step,fetched_at,kind) VALUES(?,?,?,?,'working','fetching',?,'article')",
                   (item_id, safe_url, safe_url, urlparse(safe_url).hostname or "Web", now))
    db.commit(); db.close()
    return {"id": item_id, "url": safe_url}


def update_reading(item_id: str, **fields) -> None:
    allowed = {"title", "summary", "content", "status", "step", "error", "kind", "note", "saved", "qa_json", "metadata_json", "transcript_method", "fetched_at"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    db = connect()
    db.execute(f"UPDATE items SET {','.join(f'{key}=?' for key in updates)} WHERE id=?", (*updates.values(), item_id))
    db.commit(); db.close()


def save_reading_note(item_id: str) -> dict:
    item = get_reading(item_id)
    if not item or not item.get("summary"):
        raise ValueError("Summarize this source before saving a note.")
    notes_dir = Path(plugin_data_dir(PLUGIN_ID)) / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")[:60] or "reading"
    date = time.strftime("%Y-%m-%d", time.localtime(item.get("fetched_at") or time.time()))
    target = notes_dir / f"{date}-{slug}.md"
    suffix = 2
    while target.exists():
        target = notes_dir / f"{date}-{slug}-{suffix}.md"; suffix += 1
    qa = "\n\n".join(f"**{entry['q']}**\n\n{entry['a']}" for entry in item.get("qa", []))
    body = f"# {item['title']}\n\nSource: {item['url']}\nType: {item.get('kind', 'article')}\nSaved: {date}\n\n{item['summary']}\n"
    if qa:
        body += f"\n## Questions and answers\n\n{qa}\n"
    target.write_text(body, encoding="utf-8")
    update_reading(item_id, saved=1, note=str(target))
    return {"path": str(target), "saved": True}


def delete_reading(item_id: str) -> bool:
    db = connect()
    cursor = db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit(); db.close()
    return cursor.rowcount > 0


def github_projects(query: str, language: str = "", limit: int = 20) -> list[dict]:
    """Search public GitHub repositories without requiring an API token."""
    query = query.strip()
    if not query:
        return []
    search_query = query[:120]
    if language.strip():
        search_query += f" language:{language.strip()[:40]}"
    response = httpx.get(
        "https://api.github.com/search/repositories",
        params={"q": search_query, "sort": "stars", "order": "desc", "per_page": max(1, min(limit, 30))},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "HermesReading/0.1"},
        timeout=15,
    )
    response.raise_for_status()
    return [{
        "name": repo.get("full_name", ""),
        "description": repo.get("description") or "",
        "url": repo.get("html_url", ""),
        "language": repo.get("language") or "",
        "stars": repo.get("stargazers_count", 0),
        "updated_at": repo.get("updated_at", ""),
    } for repo in response.json().get("items", [])]
