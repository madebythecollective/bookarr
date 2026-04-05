# Database schema

Bookarr stores all data in a SQLite database file (`bookarr.db`) in the installation directory. The database uses WAL (Write-Ahead Logging) mode for better concurrent read/write performance.

## Tables

### authors

Stores author information fetched from Open Library.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `name` | TEXT NOT NULL UNIQUE | | Author's full name |
| `ol_key` | TEXT | NULL | Open Library author key (for example, `OL1234A`) |
| `bio` | TEXT | NULL | Author biography from Open Library |
| `monitored` | INTEGER | 1 | Whether the author is monitored (1) or unmonitored (0) |
| `added_at` | TEXT | `datetime('now')` | ISO 8601 timestamp when the author was added |
| `seed_source` | TEXT | NULL | The seed category key (for example, `pulitzer_fiction`) or `manual` for user-added authors |

### books

Stores individual book entries. Each book has a single row with format toggle flags indicating which formats are wanted and which are available.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `author_id` | INTEGER | | Foreign key to `authors.id`. Cascades on delete. |
| `title` | TEXT NOT NULL | | Book title |
| `ol_key` | TEXT | NULL | Open Library work key (for example, `OL12345W`) |
| `year` | INTEGER | NULL | Publication year |
| `isbn` | TEXT | NULL | ISBN (not consistently populated) |
| `cover_id` | INTEGER | NULL | Open Library cover ID for fetching cover art |
| `monitored` | INTEGER | 1 | Whether the book is monitored for searching |
| `status` | TEXT | `missing` | Current status: `missing`, `wanted`, `downloading`, `downloaded` |
| `book_type` | TEXT | `book` | Always `book` in the unified model (retained for backward compatibility) |
| `want_ebook` | INTEGER | 0 | Whether the ebook format is wanted (1) or not (0) |
| `want_audiobook` | INTEGER | 0 | Whether the audiobook format is wanted (1) or not (0) |
| `have_ebook` | INTEGER | 0 | Whether the ebook format has been downloaded (1) or not (0) |
| `have_audiobook` | INTEGER | 0 | Whether the audiobook format has been downloaded (1) or not (0) |
| `ebook_path` | TEXT | NULL | Filesystem path for the downloaded ebook |
| `audiobook_path` | TEXT | NULL | Filesystem path for the downloaded audiobook |
| `path` | TEXT | NULL | Legacy filesystem path (retained for backward compatibility) |
| `subjects` | TEXT | NULL | Comma-separated subjects/genres from Open Library metadata enrichment |
| `author_count` | INTEGER | 1 | Number of authors (used to distinguish anthologies) |
| `added_at` | TEXT | `datetime('now')` | ISO 8601 timestamp when added |
| `last_searched` | TEXT | NULL | ISO 8601 timestamp of last background search |
| `last_result_count` | INTEGER | 0 | Number of results found in last search |
| `last_grab_reason` | TEXT | NULL | Human-readable reason for last grab attempt result |

**Unique constraint:** `(author_id, title)` - prevents duplicate entries for the same book. The previous constraint included `book_type`, but since the unified model uses one row per book, the constraint is effectively `(author_id, title)`.

### downloads

Tracks download attempts and their outcomes.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `book_id` | INTEGER | | Foreign key to `books.id` |
| `nzbget_id` | INTEGER | NULL | NZBGet queue ID (usenet downloads) |
| `nzb_name` | TEXT | NULL | Release title as shown in the download client |
| `indexer` | TEXT | NULL | Source indexer identifier (for example, `indexer-1`) |
| `size_bytes` | INTEGER | NULL | File size in bytes |
| `status` | TEXT | `queued` | Download status: `queued`, `downloading`, `completed`, `failed` |
| `started_at` | TEXT | `datetime('now')` | ISO 8601 timestamp when download was initiated |
| `completed_at` | TEXT | NULL | ISO 8601 timestamp when download finished |
| `download_client` | TEXT | `nzbget` | Client used: `nzbget` or `torrent` |
| `torrent_hash` | TEXT | NULL | Torrent info hash, or `pending` if not yet assigned |
| `error_detail` | TEXT | NULL | Detailed error information for failed downloads |

### settings

Key-value store for all user-configurable settings.

| Column | Type | Description |
|---|---|---|
| `key` | TEXT PRIMARY KEY | Setting identifier |
| `value` | TEXT | Setting value (all stored as strings) |

See [Settings reference](settings.md) for the complete list of keys.

### search_log

Records each background search cycle.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `query` | TEXT | NULL | Search query used |
| `results` | INTEGER | NULL | Total results found |
| `grabbed` | INTEGER | NULL | Number of results grabbed |
| `searched_at` | TEXT | `datetime('now')` | ISO 8601 timestamp |

### source_folders

User-configured additional directories to scan for book files.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `path` | TEXT UNIQUE NOT NULL | | Absolute filesystem path |
| `added_at` | TEXT | `datetime('now')` | ISO 8601 timestamp |

### indexer_stats

Per-query statistics for each indexer, used for the health dashboard.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | Auto-increment | Primary key |
| `indexer_id` | TEXT NOT NULL | | Prowlarr indexer ID |
| `query` | TEXT | NULL | Search query |
| `result_count` | INTEGER | 0 | Number of results returned |
| `success` | INTEGER | 1 | Whether the query succeeded (1) or failed (0) |
| `error_msg` | TEXT | NULL | Error message if the query failed |
| `queried_at` | TEXT | `datetime('now')` | ISO 8601 timestamp |

## Indexes

| Index name | Table | Column(s) | Purpose |
|---|---|---|---|
| `idx_books_status` | books | status | Fast filtering by status |
| `idx_books_author` | books | author_id | Fast lookup of books by author |
| `idx_authors_name` | authors | name | Fast author name lookups |
| `idx_istats_indexer` | indexer_stats | indexer_id | Fast per-indexer stat aggregation |
| `idx_istats_time` | indexer_stats | queried_at | Fast time-range queries for recent errors |

## Migrations

Bookarr handles schema migrations at startup in `init_db()`. Each migration is an `ALTER TABLE` statement wrapped in a try/except that ignores "column already exists" errors. This allows the same migration list to run safely on every startup.

Current migrations:

1. `ALTER TABLE books ADD COLUMN author_count INTEGER DEFAULT 1`
2. `ALTER TABLE books ADD COLUMN last_searched TEXT`
3. `ALTER TABLE books ADD COLUMN last_result_count INTEGER DEFAULT 0`
4. `ALTER TABLE downloads ADD COLUMN download_client TEXT DEFAULT 'nzbget'`
5. `ALTER TABLE downloads ADD COLUMN torrent_hash TEXT`
6. `ALTER TABLE downloads ADD COLUMN error_detail TEXT`
7. `ALTER TABLE books ADD COLUMN last_grab_reason TEXT`
8. `ALTER TABLE authors ADD COLUMN seed_source TEXT`
9. `ALTER TABLE books ADD COLUMN want_ebook INTEGER DEFAULT 0`
10. `ALTER TABLE books ADD COLUMN want_audiobook INTEGER DEFAULT 0`
11. `ALTER TABLE books ADD COLUMN have_ebook INTEGER DEFAULT 0`
12. `ALTER TABLE books ADD COLUMN have_audiobook INTEGER DEFAULT 0`
13. `ALTER TABLE books ADD COLUMN ebook_path TEXT`
14. `ALTER TABLE books ADD COLUMN audiobook_path TEXT`
15. `ALTER TABLE books ADD COLUMN subjects TEXT`

## Backup

The database is a single file. To back up:

```bash
cp bookarr.db bookarr.db.bak
```

For a consistent backup while Bookarr is running, use the SQLite backup command:

```bash
sqlite3 bookarr.db ".backup bookarr.db.bak"
```
