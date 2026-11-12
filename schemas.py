READING_SEARCH = {
    "name": "reading_search",
    "description": "Search feed stories, saved links, and the user's reading history. Returns matching titles, summaries, source and URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Words to find in titles and summaries."},
            "saved_only": {"type": "boolean", "description": "Search only items the user saved."},
        },
        "required": ["query"],
    },
}

READING_OPEN = {
    "name": "reading_open",
    "description": "Fetch and extract a public article, PDF, arXiv paper, or YouTube transcript for the current conversation. Returns source text and extraction metadata; page scripts are never run.",
    "parameters": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "Public HTTPS article, paper, or PDF URL."}},
        "required": ["url"],
    },
}

READING_SUMMARIZE = {
    "name": "reading_summarize",
    "description": "Read and summarize a public article, PDF, arXiv paper, or YouTube video using the user's configured Hermes model. Saves the reading and source text in the plugin's private data store.",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
}

READING_ASK = {
    "name": "reading_ask",
    "description": "Answer a question only from source text previously opened by reading_open or reading_summarize. Includes the original source URL.",
    "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}, "question": {"type": "string"}}, "required": ["item_id", "question"]},
}

READING_SAVE = {
    "name": "reading_save",
    "description": "Save a public article or paper to the user's Hermes Reading list. This writes only to this plugin's private data store.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "title": {"type": "string"},
            "note": {"type": "string", "description": "Optional short note about why the user saved it."},
        },
        "required": ["url", "title"],
    },
}

READING_LIST = {
    "name": "reading_list",
    "description": "List the user's saved links and reading history, including summaries and source status.",
    "parameters": {"type": "object", "properties": {}},
}

READING_SOURCES = {
    "name": "reading_sources",
    "description": "List the public news feeds enabled by the user.",
    "parameters": {"type": "object", "properties": {}},
}

READING_NOTE = {
    "name": "reading_note",
    "description": "Save a completed summary and its source link as a Markdown note in Hermes Reading's own private data directory.",
    "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
}

READING_DELETE = {
    "name": "reading_delete",
    "description": "Delete one item from Hermes Reading history and its saved-link list. Its exported Markdown notes remain in the plugin data directory. Use only when the user explicitly asks to remove it.",
    "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
}

READING_PROJECTS = {
    "name": "reading_projects",
    "description": "Search public GitHub repositories by topic, name, and optional programming language. Returns repository links, descriptions, language, stars, and last update.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "language": {"type": "string", "description": "Optional language filter such as Python, Rust, or TypeScript."},
        },
        "required": ["query"],
    },
}
