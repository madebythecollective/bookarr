# Configuration

All Bookarr settings are managed through the web UI at **Settings**. No configuration files need to be edited manually.

On first run, all settings default to empty values. Bookarr stores configuration in the `settings` table of the SQLite database (`bookarr.db`).

## Prowlarr (indexer management)

Bookarr searches for books through [Prowlarr](https://prowlarr.com/), which manages your usenet and torrent indexers.

| Setting | Description |
|---|---|
| **Prowlarr URL** | The URL of your Prowlarr instance. Default: `http://localhost:9696` |
| **API Key** | Your Prowlarr API key. Find it in Prowlarr under Settings > General > Security. |
| **Usenet Indexer IDs** | Comma-separated list of Prowlarr indexer IDs to search for Newznab (usenet) results. Example: `1,2,3` |
| **Torrent Indexer IDs** | Comma-separated list of Prowlarr indexer IDs to search for Torznab (torrent) results. Leave empty to disable torrent searching. |

To find your indexer IDs, open Prowlarr and navigate to Indexers. The ID is shown in the URL when you edit an indexer, or in the Prowlarr API at `/api/v1/indexer`.

## NZBGet (usenet downloads)

[NZBGet](https://nzbget.com/) handles downloading NZB files from usenet.

| Setting | Description |
|---|---|
| **NZBGet URL** | The JSON-RPC endpoint. Default: `http://localhost:6789/jsonrpc` |
| **Username** | NZBGet username for authentication. |
| **Password** | NZBGet password for authentication. |

### NZBGet category setup

Create a category in NZBGet called **Books** (and optionally **Audiobooks**):

1. Open NZBGet web UI.
2. Go to **Settings > Categories**.
3. Add a category named `Books`.
4. Set the destination directory to your ebook save path (optional; Bookarr handles post-processing).

Bookarr submits downloads with the `Books` category and VeryHigh priority (100).

## Torrent client (optional)

Bookarr supports [qBittorrent](https://www.qbittorrent.org/) and [Transmission](https://transmissionbt.com/) as torrent download clients.

| Setting | Description |
|---|---|
| **Client** | Choose `qBittorrent`, `Transmission`, or leave empty to disable. |
| **Host URL** | The torrent client's web UI URL. Example: `http://localhost:8080` |
| **Username** | Web UI username. |
| **Password** | Web UI password. |
| **Category** | Category name for added torrents. Default: `bookarr` |
| **Seed Ratio Limit** | Stop seeding when this ratio is reached. Default: `1.0`. Set to `0` for unlimited. |
| **Min Seeders** | Reject torrent results with fewer seeders than this value. Default: `1` |

## Notifications (optional)

Bookarr can send push notifications through [Pushover](https://pushover.net/) when books are grabbed or downloaded.

| Setting | Description |
|---|---|
| **App Token** | Your Pushover application token. Create one at [pushover.net/apps](https://pushover.net/apps). |
| **User Key** | Your Pushover user key. Find it on your [Pushover dashboard](https://pushover.net/). |

Leave both fields empty to disable notifications.

## Library paths

| Setting | Description |
|---|---|
| **eBook Save Path** | Directory where downloaded ebooks are organized. Example: `/media/books` |
| **Audiobook Save Path** | Directory where downloaded audiobooks are organized. Example: `/media/audiobooks` |

The default folder structure is `Author Name/Book Title/files`. You can change this in Settings under the Library tab. See [Folder structure](folder-structure.md) for all available presets.

Use the **Browse** button to navigate your filesystem and select a directory.

## Language filter

Controls which languages are accepted when importing books and filtering search results.

- Select specific languages from the checklist.
- Check **All Languages** to accept everything.
- If no languages are selected, defaults to English only.

Books in non-selected languages are filtered out during author seeding and search result scoring.

## Search settings

| Setting | Default | Description |
|---|---|---|
| **Search Interval** | `900` (15 minutes) | Seconds between background search cycles. Minimum recommended: 300. |
| **Auto Search** | Enabled | When enabled, the background search engine runs automatically. Disable to search only manually. |
| **Min Score** | `30` | Minimum relevance score (0-100+) for a result to be automatically grabbed. See [Search scoring](scoring.md). |
| **Max eBook Size** | `200` MB | Reject ebook results larger than this. |
| **Max Audiobook Size** | `5000` MB | Reject audiobook results larger than this. |

## Folder structure

| Setting | Options | Description |
|---|---|---|
| **Folder Structure** | Author/Title (default), Author/Title (Format), Author Only | Controls how downloaded files are organized on disk. See [Folder structure](folder-structure.md). |

## Format preferences

| Setting | Options | Description |
|---|---|---|
| **Preferred eBook Format** | EPUB, MOBI, PDF, Any | Matching formats receive a +15 scoring bonus. |

## Command-line options

These options are set when starting Bookarr and cannot be changed through the web UI.

```
python3 bookarr.py [OPTIONS]

Options:
  --port PORT      HTTP server port (default: 8585)
  --seed           Seed all curated author categories, then exit
  --no-search      Start without the background search engine
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOOKARR_DATA_DIR` | Script directory (source) or platform data dir (packaged) | Override the directory where Bookarr stores its database, cover cache, and logs. Useful for Docker or custom deployments. |

When running in Docker, this is automatically set to `/app/data` so the database persists across container restarts via the mounted volume.
