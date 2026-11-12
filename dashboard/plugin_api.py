from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


_PLUGIN_PACKAGE = "hermes_dashboard_plugin_hermes_reading"
_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if _PLUGIN_PACKAGE not in sys.modules:
    package = types.ModuleType(_PLUGIN_PACKAGE)
    package.__path__ = [str(_PLUGIN_ROOT)]
    package.__package__ = _PLUGIN_PACKAGE
    sys.modules[_PLUGIN_PACKAGE] = package
reading_core = importlib.import_module(f"{_PLUGIN_PACKAGE}.reading_core")

router = APIRouter()


class ReadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class SaveRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(default="", max_length=400)
    note: str = Field(default="", max_length=1000)


class SourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=2048)


@router.get("/feed")
def feed(q: str = "", saved: bool = False):
    try:
        return {"items": reading_core.search(q, saved_only=saved), "sources": reading_core.sources()}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/projects")
def projects(q: str, language: str = ""):
    try:
        return {"items": reading_core.github_projects(q, language)}
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/readings")
def readings():
    try:
        return {"items": reading_core.list_readings()}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/readings/{item_id}")
def reading(item_id: str):
    item = reading_core.get_reading(item_id)
    if not item:
        raise HTTPException(404, "Reading not found.")
    return item


@router.post("/readings/{item_id}/note")
def reading_note(item_id: str):
    try:
        return reading_core.save_reading_note(item_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.delete("/readings/{item_id}")
def delete_reading(item_id: str):
    if not reading_core.delete_reading(item_id):
        raise HTTPException(404, "Reading not found.")
    return {"deleted": True}


@router.post("/refresh")
def refresh():
    try:
        return reading_core.refresh()
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/read")
def read(body: ReadRequest):
    try:
        return reading_core.read_url(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/save")
def save(body: SaveRequest):
    try:
        return reading_core.save_item(body.url, body.title, body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post("/sources")
def add_source(body: SourceRequest):
    try:
        url = reading_core.public_https(body.url)
        # Validate the feed before persisting it, so a typo does not create a dead source.
        content, _content_type, _final = reading_core.fetch(url)
        import feedparser
        parsed = feedparser.parse(content)
        if parsed.bozo and not parsed.entries:
            raise ValueError("This address did not return a readable RSS or Atom feed.")
        import uuid, time
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))[:12]
        db = reading_core.connect()
        db.execute("INSERT INTO sources(id,name,url,enabled,added_at) VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET name=excluded.name,enabled=1", (source_id, body.name.strip(), url, 1, int(time.time())))
        db.commit(); db.close()
        return {"sources": reading_core.sources()}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.delete("/sources/{source_id}")
def remove_source(source_id: str):
    db = reading_core.connect()
    db.execute("DELETE FROM sources WHERE id=?", (source_id,))
    db.commit(); db.close()
    return {"sources": reading_core.sources()}
