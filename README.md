# Bookarr

Personal book and audiobook manager — like Radarr, but for books.

Bookarr searches usenet and torrent indexers via Prowlarr, downloads via NZBGet or torrent clients, and organizes your ebook and audiobook library automatically.

## Features

- **Library management** — Track ebooks and audiobooks with cover art, status, and metadata from Open Library
- **Automated search** — Background searching for wanted books across multiple usenet and torrent indexers
- **Smart scoring** — Results scored by title match, author match, preferred format, and size
- **Organized storage** — Files sorted into `Author/Title/ebook/` or `Author/Title/audiobook/` folders
- **Source folder scanning** — Monitor folders (Downloads, NAS, etc.) for new book files
- **Audiobook verification** — Checks Open Library and Audible to confirm audiobook editions exist before adding
- **Notifications** — Optional Pushover push notifications for grabs and downloads
- **Curated discovery** — Browse Pulitzer, Nobel, Booker prize winners, American and world classics (~500 authors)
- **Preferred format** — Choose EPUB, MOBI, PDF or any — matching results get priority
- **Single-file app** — One Python script, SQLite database, no complex setup

## Quick start

```bash
git clone https://github.com/johnhowrey/bookarr-public.git
cd bookarr-public
pip install -r requirements.txt
python3 bookarr.py
```

Open [http://localhost:8585](http://localhost:8585) in your browser. Configure your Prowlarr and NZBGet connections in **Settings**, add an author, and start searching.

For detailed setup instructions, see the [Quick start guide](docs/quickstart.md).

## Requirements

- Python 3.10 or later
- [Prowlarr](https://prowlarr.com/) — usenet/torrent indexer manager
- [NZBGet](https://nzbget.com/) or a torrent client (qBittorrent, Transmission)

## Documentation

### Getting started

| Guide | Description |
|---|---|
| [Installation](docs/installation.md) | Install on macOS, Linux, or Windows |
| [Quick start](docs/quickstart.md) | Get running in under 5 minutes |
| [Configuration](docs/configuration.md) | Configure connections, library paths, and search settings |

### Using Bookarr

| Guide | Description |
|---|---|
| [Managing your library](docs/library.md) | Add authors, want books, scan folders, organize files |
| [Search and downloads](docs/search.md) | How automated search works, manual search, download flow |
| [Notifications](docs/notifications.md) | Set up Pushover push notifications |

### Reference

| Document | Description |
|---|---|
| [API reference](docs/api.md) | Complete HTTP API with request/response examples |
| [Database schema](docs/database.md) | Tables, columns, indexes, and migrations |
| [Settings reference](docs/settings.md) | Every setting key, valid values, and defaults |
| [Seed categories](docs/seed-categories.md) | Curated author lists (Pulitzer, Nobel, Booker, classics) |

### Technical details

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Components, threading model, external integrations |
| [Search scoring](docs/scoring.md) | Scoring factors, thresholds, rejection rules |
| [Folder structure](docs/folder-structure.md) | How files are organized on disk |
| [Running as a service](docs/service.md) | macOS launchd, Linux systemd, Windows service setup |

## Command-line options

```
python3 bookarr.py                  # Start on default port 8585
python3 bookarr.py --port 8787      # Custom port
python3 bookarr.py --seed           # Seed with prize-winning authors
python3 bookarr.py --no-search      # Disable background searching
```

## Legal

- [Terms of Use](TERMS.md)
- [Privacy Policy](PRIVACY.md)
- [Disclaimer](DISCLAIMER.md)
- [Changelog](CHANGELOG.md)

Bookarr does not host, distribute, or provide any copyrighted content. It is a tool that connects to services you configure and operate independently. You are responsible for ensuring your use complies with all applicable laws. See the [Disclaimer](DISCLAIMER.md) for full details.

## License

[MIT](LICENSE) — Copyright 2025 John Howrey
