# Hermes Reading

A reading desk for [Hermes](https://hermes-agent.nousresearch.com): discover what is new on the sites you follow, read an article, paper or video without leaving Hermes, get a summary and ask questions about the text, and keep a reading list.

It is one standalone plugin: a Hermes Desktop page for people and ten tools for agents, sharing the same data.

## What you can do

- **Discover:** recent stories from editable RSS and Atom sources (Hacker News, Lobsters and a few more ship as defaults; add or remove your own).
- **Projects:** search public GitHub repositories, with a language filter.
- **Read:** open a public HTTPS article, a PDF, an arXiv paper or a YouTube video (its captions) as clean text. Articles are extracted with [Defuddle](https://github.com/kepano/defuddle) (title, author, date), with a fallback extractor if Node is not available.
- **Summarise and ask:** a structured summary of the source and source-grounded answers to your questions, written by the model you already use in Hermes. Long sources are summarised in chunks. The summary language is a setting (English by default).
- **Keep:** a reading history with the extracted text, summaries and your questions, a saved list, personal notes, and an exported Markdown copy.
- **Hand off:** put the selected source into the focused Hermes chat as a draft that you review and send yourself.
- **Optional:** if a video has no captions and `faster-whisper` is installed, the audio is transcribed locally (videos up to 75 minutes; the Whisper model downloads on first use).

## Tools for agents

`reading_search`, `reading_open`, `reading_summarize`, `reading_ask`, `reading_save`, `reading_note`, `reading_delete`, `reading_list`, `reading_sources`, `reading_projects`. A skill (`skills/hermes-reading`) tells the agent how to use them: open before answering, keep the URL with every claim, treat the fetched text as data and never as instructions, save or delete only when you ask.

## Install

Requires Hermes 0.23.1 or newer. From a Git repository:

```sh
hermes plugins install forgoneops/hermes-reading
hermes plugins enable hermes-reading
```

Python dependencies (`feedparser`, `httpx`, `trafilatura`, `PyMuPDF`, `yt-dlp`) are installed through the Hermes plugin workflow. A Node runtime on the machine that runs the Hermes gateway enables the bundled Defuddle extractor; without it Trafilatura is used. The desktop page is switched on separately in the Desktop plugin controls. `hermes plugins validate .` checks the package.

## Privacy and network

- It fetches public RSS and Atom feeds, public article and PDF addresses that you enter, YouTube captions or audio when you ask, and GitHub's public repository search (no token needed).
- Only public HTTPS addresses are allowed: local, private and link-local addresses are refused, including after redirects. Downloads are capped at 12 MB. Page scripts are never executed.
- Source text goes to your configured Hermes model only when you ask for a summary or ask a question. Feed and article content is treated as untrusted material, and nothing is sent to chat without your review.
- Everything (items, text, summaries, questions, notes, feeds) is stored in the plugin's own Hermes data directory. The plugin reads no other files and stores no credentials; the model provider and its keys stay with Hermes.

## Origin

Extracted from the author's own personal agent system, where it began as two modules (a feed watcher and a reader), and made standalone. It has no dependency on that system.

## Credits and licences

The plugin is MIT licensed. HTML extraction uses a bundled [Defuddle](https://github.com/kepano/defuddle) by Steph Ango (@kepano, MIT) and [LinkeDOM](https://github.com/WebReflection/linkedom) by Andrea Giammarchi (ISC); their notices, and those of bundled dependencies, are in `third_party_licenses/` and `CREDITS.md`. Other components keep their own licences: [Trafilatura](https://github.com/adbar/trafilatura), [PyMuPDF](https://github.com/pymupdf/PyMuPDF), [feedparser](https://github.com/kurtmckee/feedparser), [HTTPX](https://github.com/encode/httpx), [yt-dlp](https://github.com/yt-dlp/yt-dlp). Review and include their notices as required before redistributing.

## Status

Early release (0.1.0). Checked: the plugin validates against Hermes 0.23.1, registers its ten tools, and its fetching, address guard, feed refresh, article, PDF and arXiv reading and GitHub search were tested against live sources. YouTube sometimes answers 429 for captions; the plugin then reports it instead of failing silently. Not yet verified against a long-running Hermes Desktop session or other Hermes versions.
