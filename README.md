# Hermes Reading

One Hermes Desktop workspace for discovering public technology feeds and GitHub projects, reading articles and papers, and keeping a personal reading list.

## What is included

- **Discover:** recent stories from editable RSS/Atom sources.
- **Projects:** public GitHub repository search with language filters.
- **Reader:** use the same Defuddle + linkedom extraction approach as Lectio for public HTTPS articles, parse PDFs including arXiv papers, and read YouTube captions.
- **Summaries and questions:** generate Polish summaries and source-grounded answers with the model configured in Hermes. Longer sources are summarized in chunks.
- **Reading history:** revisit extracted text, summaries and question history.
- **Notes:** save a Markdown copy to the plugin's private data directory.
- **Optional transcription:** if captions are unavailable and faster-whisper is present in the Hermes plugin runtime, transcribe local audio for videos up to 75 minutes. The Whisper model downloads on first use.
- **Hermes handoff:** add the selected source to the focused chat as an unsent draft. The user reviews and sends it.
- **Agent tools:** `reading_search`, `reading_open`, `reading_summarize`, `reading_ask`, `reading_save`, `reading_note`, `reading_delete`, `reading_list`, `reading_sources`, and `reading_projects`.

The desktop UI keeps discovery and the full reader in one page. Agent tools and UI share the same plugin data. Feed and article content is treated as untrusted source material; the plugin does not execute page scripts or auto-send prompts. The provider and credentials remain owned by Hermes through its plugin LLM API.

## Privacy and network disclosure

Hermes Reading requests public RSS/Atom sources, public article and PDF URLs entered by the user, YouTube for captions/audio when requested, and GitHub's public repository search API. Source text is sent to the user's currently configured Hermes model only when the user requests a summary or asks a question. The plugin stores extracted text, summaries, questions, notes and feeds under its own Hermes plugin data directory; it does not read the user's other files or store provider credentials. The HTML extractor invokes the fixed, bundled Defuddle script with Node; YouTube support uses the `yt-dlp` Python library. Optional local Whisper downloads its model through faster-whisper on first use.

## Install for development

Install the folder as one regular Hermes agent plugin from a Git repository or copy it to the active Hermes plugins directory. The combined package contains `plugin.yaml`, `__init__.py`, `dashboard/` and `desktop/`. The bundled Defuddle extractor requires a Node runtime on the Hermes gateway; Trafilatura is the fallback if it is absent. Install Python dependencies through the Hermes plugin workflow. Enable the agent plugin in Capabilities → Plugins; the desktop UI is separately enabled in Desktop plugin controls. The gateway must load the plugin for its REST routes and RPC methods to work.

This package has not yet been checked against a live Hermes Desktop installation. Compatibility should be verified against the target Hermes version before marketplace submission.

The package declares Hermes `>=0.23.1`, the first supported release for its plugin RPC, model-task and Desktop event APIs.

## Data and network

Reading items, source text, summaries, Q&A history, saved notes and configured feeds are stored in Hermes' plugin data directory. The app fetches public HTTPS feeds, article pages, PDFs, YouTube captions and GitHub's public repository search API. Downloads are capped at 12 MB. Redirect targets are checked and local/private addresses are rejected. Model calls use the active Hermes provider and its registered `Hermes Reading` auxiliary task; no provider is hard-coded.

## Credits

HTML extraction uses bundled [Defuddle](https://github.com/kepano/defuddle) by **Steph Ango (@kepano)** (MIT) and [LinkeDOM](https://github.com/WebReflection/linkedom) by Andrea Giammarchi (ISC), matching the extraction path used by Lectio. The bundled extractor includes their runtime dependencies; their license texts are in `third_party_licenses/`. Trafilatura remains the fallback; PDF extraction uses PyMuPDF.

Other runtime components retain their respective licenses: [Trafilatura](https://github.com/adbar/trafilatura), [PyMuPDF](https://github.com/pymupdf/PyMuPDF), [feedparser](https://github.com/kurtmckee/feedparser), [HTTPX](https://github.com/encode/httpx), and [yt-dlp](https://github.com/yt-dlp/yt-dlp). Review and include their notices as required before redistribution.

## Before marketplace submission

Review third-party notices, validate the package with the target Hermes CLI, and exercise the desktop page against a live gateway before release. The plugin itself is MIT licensed; bundled third-party components retain their own notices.
