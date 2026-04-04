# Architecture

Bookarr is a single-file Python application with no framework dependencies. This document describes how it is built.

## Design philosophy

- **Single-file application.** All server logic lives in `bookarr.py` (~3,800 lines). The web UI is a single HTML template with inline CSS and JavaScript.
- **Standard library first.** The HTTP server, database, URL handling, XML parsing, and threading all use Python standard library modules. Only three external packages are required: `pillow` (cover image generation), `requests` (HTTP client), and `beautifulsoup4` (HTML parsing).
- **SQLite database.** All state is stored in a single SQLite file with WAL mode for concurrent access.
- **No build step.** No compilation, transpilation, bundling, or asset pipeline. The application runs directly from source.

## Components

```
bookarr.py
  +-- HTTP Server (ThreadedHTTPServer)
  |     +-- BookarrHandler (do_GET, do_POST)
  |           +-- API endpoints (/api/*)
  |           +-- Static file serving (/static/*)
  |           +-- Template rendering (/)
  |
  +-- Search Engine (daemon thread)
  |     +-- _search_wanted() loop
  |     +-- _check_downloads() loop
  |
  +-- Background Tasks (daemon threads)
  |     +-- Seed authors
  |     +-- Check audiobooks
  |     +-- Scan source folders
  |     +-- Auto-check audiobooks on startup
  |
  +-- SQLite Database (bookarr.db)
        +-- WAL mode
        +-- Connection per request/thread
```

## HTTP server

Bookarr uses Python's `http.server.HTTPServer` wrapped in `ThreadedHTTPServer` (which mixes in `socketserver.ThreadingMixIn`) to handle concurrent requests.

The `BookarrHandler` class extends `BaseHTTPRequestHandler` and implements:

- **`do_GET`** - Routes GET requests to API handlers or serves static files and the HTML template.
- **`do_POST`** - Routes POST requests to API handlers.

Each request creates a new handler instance. There is no session state, middleware, or routing framework.

### Request routing

Routing is handled by string matching on `self.path` within `do_GET` and `do_POST`. API endpoints follow the pattern `/api/resource/action`.

### Template rendering

The single HTML template (`templates/index.html`) is read from disk on each request and served as-is. The template contains all CSS and JavaScript inline. The client-side JavaScript fetches data from the API and renders the UI dynamically.

## Database access

Each thread creates its own SQLite connection via `get_db()`. Connections use:

- **WAL mode** for concurrent read access while a write is in progress.
- **Row factory** set to `sqlite3.Row` for dictionary-style column access.
- **`check_same_thread=False`** to allow connections to be used across threads (though in practice each thread creates its own).

Database initialization (`init_db()`) runs on startup and:

1. Creates all tables if they do not exist.
2. Seeds initial settings from `_INIT_*` constants (only on first run, using `INSERT OR IGNORE`).
3. Runs schema migrations (ALTER TABLE statements, ignoring errors for already-existing columns).
4. Backfills computed fields (`seed_source`).

## Search engine

The `SearchEngine` class runs as a daemon thread with two interleaved tasks:

### Search cycle

1. Query the database for up to 50 wanted books (25 audiobooks + 25 ebooks).
2. For each book, search all configured Prowlarr indexers.
3. Score results using `score_result()`.
4. Send the best qualifying result to the download client.
5. Sleep for the configured search interval.

### Download monitoring

After each search cycle, the engine checks:

1. **NZBGet history** for completed or failed downloads.
2. **Torrent client** for state changes (completed, errored).
3. **Stalled downloads** (stuck for 48+ hours with no client-side match).

### Thread safety

- A `threading.Lock` (`_seed_lock`) coordinates between the seed process and audiobook checker to prevent concurrent database-heavy operations.
- Each background task uses its own database connection.
- The search engine sets `_search_active` flag for UI progress polling.

## Background tasks

Long-running operations spawn as daemon threads to avoid blocking the HTTP server:

| Task | Trigger | Duration |
|---|---|---|
| Seed authors | POST `/api/seed` | Minutes (depends on author count) |
| Check audiobooks (per author) | POST `/api/author/add-audiobooks` | Seconds |
| Check all audiobooks | POST `/api/audiobooks/check-all` or startup | Minutes to hours |
| Scan source folders | POST `/api/source-folders/scan` | Seconds to minutes |
| Library reorganization | First startup | Seconds to minutes |

## External integrations

### Open Library

- **Author search:** `openlibrary.org/search/authors.json`
- **Author works:** `openlibrary.org/authors/OL_KEY/works.json`
- **Book search:** `openlibrary.org/search.json`
- **Edition data:** `openlibrary.org/works/OL_KEY/editions.json`
- **Cover art:** `covers.openlibrary.org/b/id/COVER_ID-SIZE.jpg`

All requests use `urllib.request` with timeouts.

### Audible

- **Catalog search:** `api.audible.com/1.0/catalog/products`
- Used only for audiobook existence verification (title + author search).

### Prowlarr

- **Newznab search:** `{prowlarr_url}/api/v1/indexer/INDEXER_ID/newznab?apikey=KEY&t=search&q=QUERY&cat=CATEGORIES`
- Returns XML (Newznab RSS format), parsed with `xml.etree.ElementTree`.

### NZBGet

- **JSON-RPC:** POST to `{nzbget_url}` with method and params.
- Authentication via HTTP Basic.

### qBittorrent

- **Web API v2:** Login, add torrent, list torrents, delete torrent.
- Authentication via session cookie.

### Transmission

- **JSON-RPC:** POST to `{host}/transmission/rpc`.
- Handles 409 CSRF challenge (X-Transmission-Session-Id header).

### Pushover

- **Push notification:** POST to `api.pushover.net/1/messages.json`.
- Sends app token, user key, title, and message.

## File structure

```
bookarr-public/
  bookarr.py            Main application (all server logic)
  templates/
    index.html          Web UI (HTML + inline CSS + inline JS)
  static/
    favicon.ico         Browser favicon
    favicon-16.png      16x16 favicon
    favicon-32.png      32x32 favicon
    favicon.svg         SVG favicon
    apple-touch-icon.png  iOS icon
    covers/             Cached cover art (generated at runtime)
  service/
    com.bookarr.plist   macOS launchd service
    bookarr.service     Linux systemd service
  docs/                 Documentation
  bookarr.db            SQLite database (created at runtime)
  bookarr.log           Application log (created at runtime)
```

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pillow` | Any | Generate placeholder book cover images |
| `requests` | Any | HTTP client for some external API calls |
| `beautifulsoup4` | Any | Parse HTML responses |

Standard library modules used: `argparse`, `base64`, `concurrent.futures`, `datetime`, `functools`, `http.server`, `json`, `os`, `re`, `shutil`, `sqlite3`, `sys`, `threading`, `time`, `urllib`, `xml.etree.ElementTree`.
