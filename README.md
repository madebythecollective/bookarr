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

## Download

Download the latest release for your platform — no Python or technical setup required:

| Platform | Download | Notes |
|---|---|---|
| **macOS** | [Bookarr-0.2.0-macos.dmg](https://github.com/johnhowrey/bookarr-public/releases/latest) | Open the DMG and drag Bookarr to Applications |
| **Windows** | [Bookarr-0.2.0-windows-setup.exe](https://github.com/johnhowrey/bookarr-public/releases/latest) | Run the installer, launch from Start Menu |
| **Docker** | See [Docker install](docs/installation.md#docker) | `docker compose up -d` |
| **From source** | See below | Requires Python 3.10+ |

After launching, open [http://localhost:8585](http://localhost:8585) and configure your connections in **Settings**.

### From source

For developers or if you prefer running from source:

```bash
git clone https://github.com/johnhowrey/bookarr-public.git
cd bookarr-public
pip install -r requirements.txt
python3 bookarr.py
```

For detailed setup, see the [installation guide](docs/installation.md) and [quick start](docs/quickstart.md).

## Requirements

Bookarr needs at least one indexer manager and one download client:

- [Prowlarr](https://prowlarr.com/) — usenet/torrent indexer manager
- [NZBGet](https://nzbget.com/) or a torrent client (qBittorrent, Transmission)

These are configured through the Bookarr Settings page after installation. If you're already running Sonarr or Radarr, your existing Prowlarr and download client work with Bookarr too.

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
