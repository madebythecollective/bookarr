# Bookarr

Personal book and audiobook manager — like Radarr, but for books.

Bookarr searches usenet indexers via Prowlarr, downloads via NZBGet, and organizes your ebook and audiobook library automatically.

## Features

- **Library management** — Track ebooks and audiobooks with cover art, status, and metadata from Open Library
- **Automated search** — Background searching for wanted books across multiple usenet indexers
- **Smart scoring** — Results scored by title match, author match, preferred format, and size
- **Organized storage** — Files sorted into `Author/Title/ebook/` or `Author/Title/audiobook/` folders
- **Source folder scanning** — Monitor folders (Downloads, NAS, etc.) for new book files
- **Audiobook verification** — Checks Open Library and Audible to confirm audiobook editions exist before adding
- **Notifications** — Optional Pushover notifications for grabs and downloads
- **Curated discovery** — Browse Pulitzer, Nobel, Booker prize winners, American and world classics
- **Preferred format** — Choose EPUB, MOBI, PDF or any — matching results get priority
- **Single-file app** — One Python script, SQLite database, no complex setup

## Quick Start

### Requirements

- Python 3.10+
- [Prowlarr](https://prowlarr.com/) — usenet indexer manager (default: localhost:9696)
- [NZBGet](https://nzbget.com/) — usenet downloader (default: localhost:6789)

### Install

```bash
git clone https://github.com/johnhowrey/bookarr-public.git
cd bookarr-public
./install.sh    # or: pip install -r requirements.txt
```

### Run

```bash
python3 bookarr.py
```

Open [http://localhost:8585](http://localhost:8585) in your browser.

### Options

```
python3 bookarr.py                  # Start on default port 8585
python3 bookarr.py --port 8787      # Custom port
python3 bookarr.py --seed           # Seed with prize-winning authors
python3 bookarr.py --no-search      # Disable background searching
```

## Configuration

All settings are managed through the web UI at Settings:

- **eBook Save Path** — Where downloaded ebooks are organized
- **Audiobook Save Path** — Where downloaded audiobooks are organized
- **Source Folders** — Additional folders to scan for existing book files
- **Preferred eBook Format** — EPUB, MOBI, PDF, or Any
- **Search Interval** — How often to search for wanted books (seconds)
- **Max File Size** — Size limits for ebook and audiobook downloads
- **Language Filter** — Control which languages are imported
- **Want Format** — When wanting a book, get both formats or just one

All connection settings (Prowlarr, NZBGet, torrent client, Pushover notifications) are configured through the Settings page on first run — no need to edit any files.

## Folder Structure

Downloaded books are organized as:

```
{ebook_path}/
  Author Name/
    Book Title/
      ebook/
        filename.epub

{audiobook_path}/
  Author Name/
    Book Title/
      audiobook/
        filename.m4b
```

Existing files are automatically migrated to this structure on first startup.

## Source Folders

In addition to the ebook and audiobook save paths (which are always scanned), you can add custom source folders in Settings. When you click "Scan Now", Bookarr walks all source folders looking for book files, matches them to known books in your library by filename, and moves them into the organized folder structure.

## Running as a Service

### macOS (launchd)

```bash
./install.sh
launchctl load ~/Library/LaunchAgents/com.bookarr.plist
```

### Linux (systemd)

```bash
sudo cp service/bookarr.service /etc/systemd/system/
# Edit the file to set your paths and username
sudo systemctl daemon-reload
sudo systemctl enable --now bookarr
```

### Windows

```cmd
install.bat
python bookarr.py
```

## NZBGet Setup

1. In NZBGet, create a category called **Books** (and optionally **Audiobooks**)
2. Point the category paths to your desired save locations
3. Bookarr will post-process completed downloads and move files to the organized structure

## Seed Categories

| Category | Authors |
|---|---|
| Pulitzer Prize — Fiction | ~75 |
| Pulitzer Prize — Drama | ~26 |
| Pulitzer Prize — Poetry | ~35 |
| Pulitzer Prize — Nonfiction | ~22 |
| Nobel Prize in Literature | ~110 |
| Booker Prize Winners | ~52 |
| Classic American Authors | ~95 |
| Classic World Authors | ~90 |

## API Reference

### Library

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stats` | Library statistics |
| GET | `/api/books?status=&type=&q=&page=` | List books with filters |
| GET | `/api/authors` | List all authors |
| GET | `/api/author/{id}` | Author details |
| GET | `/api/author/{id}/books` | Books for an author |
| GET | `/api/wanted` | Wanted/downloading books |
| GET | `/api/activity` | Download history |

### Content

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/author/add` | Add author by name |
| POST | `/api/author/add-ol` | Add author by Open Library key |
| POST | `/api/book/add` | Add a book |
| POST | `/api/seed` | Seed from curated lists |
| POST | `/api/seed/trending` | Seed from trending |
| POST | `/api/book/{id}/want` | Mark as wanted |
| POST | `/api/grab` | Send NZB to NZBGet |

### Source Folders

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/source-folders` | List all source folders |
| POST | `/api/source-folders` | Add a source folder |
| POST | `/api/source-folders/delete` | Remove a source folder |
| POST | `/api/source-folders/scan` | Scan all source folders |

### System

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/settings` | Get settings |
| POST | `/api/settings` | Update settings |
| GET | `/api/browse?path=` | Browse directories |
| POST | `/api/scan` | Scan library |
| POST | `/api/cleanup` | Remove junk titles |
| POST | `/api/reset` | Clear all data |

## Architecture

- Single Python file, stdlib HTTP server (threaded)
- SQLite database with WAL mode
- All CSS and JS inline in one HTML template
- No framework dependencies — uses only `urllib`, `json`, `sqlite3`, `http.server`
- Pillow used only for generating placeholder book covers

## License

MIT
