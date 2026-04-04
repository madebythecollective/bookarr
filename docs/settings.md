# Settings reference

Complete reference for every setting key stored in the `settings` table. All values are stored as strings.

## Library

| Key | Default | Valid values | Description |
|---|---|---|---|
| `ebook_path` | `""` (empty) | Absolute directory path | Directory where ebooks are organized into `Author/Title/ebook/` subfolders. |
| `audiobook_path` | `""` (empty) | Absolute directory path | Directory where audiobooks are organized into `Author/Title/audiobook/` subfolders. |
| `language` | `"english"` | `"any"`, `"english"`, or comma-separated language names | Controls which languages are accepted during import and search result filtering. |
| `want_format` | `"both"` | `"both"`, `"ebook"`, `"audiobook"` | When wanting a book, whether to also want the sibling format automatically. |
| `preferred_ebook_format` | `"epub"` | `"epub"`, `"mobi"`, `"pdf"`, `"any"` | Preferred ebook format. Matching results receive a +15 scoring bonus. |

## Search

| Key | Default | Valid values | Description |
|---|---|---|---|
| `search_interval` | `"900"` | Positive integer (seconds) | Time between background search cycles. 900 = 15 minutes. |
| `auto_search` | `"1"` | `"0"`, `"1"` | Enable (`1`) or disable (`0`) automatic background searching. |
| `min_score` | `"30"` | `"0"` to `"100"` | Minimum relevance score for a result to be automatically grabbed. |
| `max_size_mb_ebook` | `"200"` | Positive integer (MB) | Maximum file size for ebook downloads. Results exceeding this are penalized -50 points. |
| `max_size_mb_audiobook` | `"5000"` | Positive integer (MB) | Maximum file size for audiobook downloads. Results exceeding this are penalized -50 points. |

## Prowlarr

| Key | Default | Valid values | Description |
|---|---|---|---|
| `prowlarr_url` | `"http://localhost:9696"` | URL | Prowlarr API base URL. |
| `prowlarr_api_key` | `""` (empty) | String | Prowlarr API key. Found in Prowlarr under Settings > General > Security. |
| `prowlarr_indexer_ids` | `"1,2,3"` | Comma-separated integers | Prowlarr indexer IDs for Newznab (usenet) searches. |
| `torrent_indexer_ids` | `""` (empty) | Comma-separated integers | Prowlarr indexer IDs for Torznab (torrent) searches. Leave empty to disable. |

## NZBGet

| Key | Default | Valid values | Description |
|---|---|---|---|
| `nzbget_url` | `"http://localhost:6789/jsonrpc"` | URL | NZBGet JSON-RPC endpoint. |
| `nzbget_user` | `""` (empty) | String | NZBGet username. |
| `nzbget_pass` | `""` (empty) | String | NZBGet password. |

## Torrent client

| Key | Default | Valid values | Description |
|---|---|---|---|
| `torrent_client` | `""` (empty) | `""`, `"qbittorrent"`, `"transmission"` | Torrent client to use. Empty disables torrent support. |
| `torrent_host` | `""` (empty) | URL | Torrent client web UI URL. |
| `torrent_user` | `""` (empty) | String | Torrent client username. |
| `torrent_pass` | `""` (empty) | String | Torrent client password. |
| `torrent_category` | `"bookarr"` | String | Category name assigned to torrents added by Bookarr. |
| `seed_ratio_limit` | `"1.0"` | Decimal number | Stop seeding when this upload/download ratio is reached. `0` = no limit. |
| `seed_time_limit` | `"0"` | Integer (minutes) | Stop seeding after this many minutes. `0` = no limit. |
| `min_seeders` | `"1"` | Non-negative integer | Reject torrent results with fewer seeders. |

## Notifications

| Key | Default | Valid values | Description |
|---|---|---|---|
| `pushover_token` | `""` (empty) | String | Pushover application API token. |
| `pushover_user` | `""` (empty) | String | Pushover user key. |

Both must be set for notifications to fire. If either is empty, notifications are silently skipped.

## Internal

| Key | Default | Valid values | Description |
|---|---|---|---|
| `folder_structure_migrated` | `""` (empty) | `"1"` | Set to `1` after the one-time library reorganization to `Author/Title/format/` structure. Do not modify manually. |
