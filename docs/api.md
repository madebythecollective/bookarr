# API reference

Bookarr exposes an HTTP API on the same port as the web UI (default: 8585). All endpoints accept and return JSON.

## Conventions

- **Base URL:** `http://localhost:8585`
- **Content-Type:** `application/json` for POST requests with a body.
- **Success responses:** Return a JSON object with a `status` or `data` field and HTTP 200.
- **Error responses:** Return `{"error": "message"}` with HTTP 400 or 500.
- **Authentication:** None. The API is unauthenticated. Restrict network access if needed.

## Library

### Get library statistics

```
GET /api/stats
```

Returns aggregate counts for the library.

**Response:**

```json
{
  "authors": 150,
  "authors_monitored": 142,
  "books": 2340,
  "ebooks": 1800,
  "audiobooks": 540,
  "wanted": 89,
  "downloading": 3,
  "downloaded": 1200,
  "missing": 1048
}
```

### List books

```
GET /api/books?status=STATUS&type=TYPE&q=QUERY&page=PAGE&per_page=PER_PAGE&category=CATEGORY&exclude_status=STATUS
```

Returns a paginated list of books.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status: `missing`, `wanted`, `downloading`, `downloaded` |
| `exclude_status` | string | Exclude a status from results |
| `type` | string | Filter by book type: `ebook`, `audiobook` |
| `q` | string | Search book titles and author names |
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Results per page (default: 100) |
| `category` | string | Filter by `novel` (author_count = 1) or `anthology` (author_count > 1) |

**Response:**

```json
{
  "books": [
    {
      "id": 1,
      "title": "Blood Meridian",
      "author_id": 5,
      "author_name": "Cormac McCarthy",
      "year": 1985,
      "status": "wanted",
      "book_type": "ebook",
      "cover_id": 12345678,
      "monitored": 1,
      "author_count": 1,
      "ol_key": "OL12345W",
      "path": null
    }
  ],
  "total": 2340,
  "page": 1,
  "per_page": 100
}
```

### Get book detail

```
GET /api/book/BOOK_ID
```

Returns full book details including download history and related books.

### List wanted books

```
GET /api/wanted
```

Returns all books with status `wanted` or `downloading`.

### Get download activity

```
GET /api/activity
```

Returns the 50 most recent download records.

**Response item fields:**

| Field | Type | Description |
|---|---|---|
| `id` | integer | Download record ID |
| `book_id` | integer | Associated book ID |
| `nzbget_id` | integer | NZBGet queue ID |
| `nzb_name` | string | Release title |
| `indexer` | string | Source indexer identifier |
| `size_bytes` | integer | File size in bytes |
| `status` | string | `queued`, `downloading`, `completed`, `failed` |
| `started_at` | string | ISO 8601 timestamp |
| `completed_at` | string | ISO 8601 timestamp or null |
| `download_client` | string | `nzbget` or `torrent` |
| `torrent_hash` | string | Torrent info hash or null |
| `error_detail` | string | Error description or null |

## Authors

### List all authors

```
GET /api/authors
```

Returns all authors with aggregate book counts.

**Response item fields:**

| Field | Type | Description |
|---|---|---|
| `id` | integer | Author ID |
| `name` | string | Author name |
| `ol_key` | string | Open Library author key |
| `bio` | string | Author biography |
| `monitored` | integer | 1 = monitored, 0 = unmonitored |
| `seed_source` | string | Seed category key or "manual" |
| `book_count` | integer | Total books |
| `downloaded_count` | integer | Books with status "downloaded" |
| `wanted_count` | integer | Books with status "wanted" |
| `ebook_count` | integer | Ebook entries |
| `audiobook_count` | integer | Audiobook entries |

### Get author detail

```
GET /api/author/AUTHOR_ID
```

### Get author books

```
GET /api/author/AUTHOR_ID/books
```

Returns all books for an author, ordered by year and title.

### Get similar authors

```
GET /api/author/AUTHOR_ID/similar
```

Returns up to 5 similar authors based on shared seed categories and cross-category membership.

### Add author by name

```
POST /api/author/add
```

**Request body:**

```json
{
  "name": "Cormac McCarthy"
}
```

Searches Open Library, adds the author and their works. Returns the new author record.

### Add author by Open Library key

```
POST /api/author/add-ol
```

**Request body:**

```json
{
  "ol_key": "OL1234A",
  "name": "Cormac McCarthy"
}
```

### Toggle author monitoring

```
POST /api/author/AUTHOR_ID/toggle
```

Toggles the author's monitored flag between 1 and 0.

### Delete author

```
POST /api/author/AUTHOR_ID/delete
```

Deletes the author and all their books.

## Books

### Add a book

```
POST /api/book/add
```

**Request body:**

```json
{
  "title": "Blood Meridian",
  "author_name": "Cormac McCarthy",
  "author_key": "OL1234A",
  "ol_key": "OL5678W",
  "year": 1985,
  "cover_id": 12345678,
  "book_type": "ebook"
}
```

The `book_type` field accepts `ebook`, `audiobook`, or `both` (creates both entries).

### Want a book

```
POST /api/book/BOOK_ID/want
```

Sets book status to "wanted." If the "When Wanting a Book" setting is "both," also wants the sibling format.

### Unwant a book

```
POST /api/book/BOOK_ID/unwant
```

Sets book status back to "missing."

### Want all books by author

```
POST /api/book/want-all
```

**Request body:**

```json
{
  "author_id": 5,
  "book_type": ""
}
```

The `book_type` field filters which books to want: `""` (all), `"ebook"`, or `"audiobook"`.

### Delete a book

```
POST /api/book/BOOK_ID/delete
```

Deletes the book. If the author has no remaining books, the author is also deleted.

## Audiobooks

### Check audiobooks for author

```
POST /api/author/add-audiobooks
```

**Request body:**

```json
{
  "author_id": 5
}
```

Checks Open Library and Audible for audiobook editions of the author's ebooks. Runs in a background thread.

### Check all audiobooks

```
POST /api/audiobooks/check-all
```

Checks audiobook availability for all authors that have ebooks but no audiobook entries. Runs in the background.

## Search

### Search indexers

```
GET /api/search?q=QUERY&type=indexer&book_id=BOOK_ID
```

Searches all configured Prowlarr indexers. If `book_id` is provided, results are scored against that book.

### Search Open Library for authors

```
GET /api/search/author?q=QUERY
```

### Search Open Library for books

```
GET /api/search/book?q=QUERY
```

### Get search progress

```
GET /api/search/progress
```

**Response:**

```json
{
  "active": true,
  "total": 50,
  "done": 23,
  "current": "Blood Meridian by Cormac McCarthy",
  "grabbed": 5,
  "started_at": "2026-04-03T10:30:00"
}
```

### Trigger immediate search

```
POST /api/search/now
```

## Downloads

### Grab a release

```
POST /api/grab
```

**Request body:**

```json
{
  "link": "https://indexer.example.com/getnzb/abc123",
  "book_id": 42,
  "title": "Blood Meridian",
  "protocol": "usenet",
  "size_bytes": 2500000
}
```

The `protocol` field determines the download client: `"usenet"` sends to NZBGet, `"torrent"` sends to the configured torrent client.

### Retry a failed download

```
POST /api/download/DOWNLOAD_ID/retry
```

## Seeding

### List seed categories

```
GET /api/seed/categories
```

**Response:**

```json
[
  {
    "key": "pulitzer_fiction",
    "name": "Pulitzer Prize \u2014 Fiction",
    "description": "Winners of the Pulitzer Prize for Fiction",
    "author_count": 75
  }
]
```

### Seed a category

```
POST /api/seed
```

**Request body:**

```json
{
  "category": "pulitzer_fiction"
}
```

Runs in a background thread. Duplicate authors are skipped.

### Seed from trending

```
POST /api/seed/trending
```

Fetches trending authors from Open Library and adds them.

## Source folders

### List source folders

```
GET /api/source-folders
```

Returns both automatic (save paths) and custom source folders.

### Add source folder

```
POST /api/source-folders
```

**Request body:**

```json
{
  "path": "/mnt/nas/downloads"
}
```

### Remove source folder

```
POST /api/source-folders/delete
```

**Request body:**

```json
{
  "path": "/mnt/nas/downloads"
}
```

### Scan source folders

```
POST /api/source-folders/scan
```

Scans all source folders for book files in the background.

## System

### Get all settings

```
GET /api/settings
```

Returns all settings as a key-value object.

### Update settings

```
POST /api/settings
```

**Request body:** A JSON object with setting keys and their new values.

```json
{
  "search_interval": "600",
  "min_score": "40"
}
```

### Browse directories

```
GET /api/browse?path=/
```

Returns a list of subdirectories at the given path for the folder browser UI.

### Scan library

```
POST /api/scan
```

Scans ebook and audiobook save paths plus all source folders for book files.

### Cleanup library

```
POST /api/cleanup
```

Removes junk titles, non-English entries, and duplicates.

### Reset library

```
POST /api/reset
```

Deletes all authors, books, downloads, and logs. Settings are preserved.

### Backfill author counts

```
POST /api/backfill-counts
```

Re-fetches `author_count` from Open Library for all books.

## Connection tests

### Test Prowlarr

```
GET /api/test/prowlarr
```

**Response:**

```json
{
  "success": true,
  "message": "Connected to Prowlarr (3 indexers)"
}
```

### Test NZBGet

```
GET /api/test/nzbget
```

### Test torrent client

```
GET /api/test/torrent
```

## Indexer health

### Get indexer statistics

```
GET /api/indexer/health
```

Returns per-indexer statistics and recent errors.

**Response:**

```json
{
  "indexers": [
    {
      "indexer_id": "1",
      "total_queries": 500,
      "successes": 485,
      "failures": 15,
      "avg_results": 12.3,
      "last_query": "2026-04-03T10:30:00",
      "failure_rate": 3.0
    }
  ],
  "recent_errors": [
    {
      "indexer_id": "2",
      "query": "Blood Meridian",
      "error_msg": "Connection timeout",
      "queried_at": "2026-04-03T10:25:00"
    }
  ]
}
```

## Cover art

### Get Open Library cover

```
GET /api/cover/COVER_ID?size=M
```

Proxies cover images from Open Library. Sizes: `S` (small), `M` (medium), `L` (large).

### Generate placeholder cover

```
GET /api/cover/gen/BOOK_ID
```

Generates a vintage Field Notes-style cover image (PNG) for books without Open Library covers. Generated images are cached in `static/covers/`.
