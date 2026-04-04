# Changelog

All notable changes to Bookarr are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-03

### Added

- **Audiobook search improvements.** Audiobooks now use expanded Newznab categories (3000, 3030, 3040) and multiple fallback search strategies: author + title + "audiobook", author last name + title, and broader category search.
- **Music and soundtrack filter.** Search results containing FLAC, vinyl, LP, SACD, DSD, soundtrack, or other music indicators are automatically rejected. Results that also contain "audiobook", "narrated", or "unabridged" are exempt from this filter.
- **Pushover notifications.** Optional push notifications via [Pushover](https://pushover.net/). Configure your app token and user key in Settings. Notifications fire on grab and download events.
- **Balanced search batching.** Background search now processes 25 audiobooks and 25 ebooks per cycle (previously 50 of either, which could starve audiobooks).
- **Auto-check audiobooks on startup.** Authors missing audiobook data are automatically checked against Open Library and Audible when Bookarr starts.
- **URL hash routing.** The browser URL now reflects the current page (`#library`, `#discover`, `#activity`, `#settings`). Refreshing or sharing a URL returns to the correct page.
- **About page.** New navigation item with project information, version, and links to documentation, legal notices, and source code.

### Changed

- **Audiobook verification switched from iTunes to Open Library + Audible.** The audiobook existence check now queries Open Library edition data for audio formats and falls back to the Audible catalog API. iTunes/Apple Books lookup was removed.
- **Concurrent audiobook checking.** Audiobook verification now uses 4 concurrent workers (previously sequential, 1 worker). This significantly speeds up bulk audiobook checks.
- **NZBGet priority increased.** Book downloads are now submitted with VeryHigh priority (100) instead of Normal (0).
- **Rate-limit sleeps removed.** Removed 0.3-second and 0.5-second sleeps between Open Library and Audible checks, and the 1-second sleep between bulk audiobook author checks. The search interval and concurrency controls provide sufficient rate limiting.
- **All credentials configurable via Settings UI.** Prowlarr API key, NZBGet credentials, file paths, and Pushover tokens are no longer hardcoded. All values default to empty and are configured through the web interface on first run.

### Fixed

- **Database lock contention.** Fixed SQLite locking issues between the seed process and background audiobook checker by coordinating access through a shared lock.

## [0.1.0] - 2026-02-21

### Added

- Initial release of Bookarr.
- **Library management.** Track ebooks and audiobooks with cover art, status, and metadata from Open Library.
- **Automated search.** Background searching for wanted books across multiple usenet indexers via Prowlarr.
- **Smart scoring.** Results scored by title match, author match, preferred format, file size, and seeder count.
- **Organized storage.** Downloaded files automatically sorted into `Author/Title/ebook/` or `Author/Title/audiobook/` folder structure.
- **Source folder scanning.** Monitor additional folders (Downloads, NAS) for book files and match them to library entries.
- **Curated discovery.** Browse and seed authors from Pulitzer, Nobel, Booker prize winners, American and world classics (8 categories, ~500 authors).
- **Trending authors.** Seed from Open Library's trending authors list.
- **Preferred format support.** Choose EPUB, MOBI, PDF, or any. Matching formats receive priority in scoring.
- **Torrent client support.** Optional qBittorrent or Transmission integration alongside NZBGet.
- **Web UI.** Single-page application with Library, Discover, Activity, and Settings pages.
- **Generated cover art.** Vintage Field Notes-style placeholder covers for books without Open Library cover images.
- **Service files.** macOS launchd plist and Linux systemd unit file for running as a background service.
- **Install scripts.** Automated setup for macOS, Linux, and Windows.

[0.2.0]: https://github.com/johnhowrey/bookarr-public/releases/tag/v0.2.0
[0.1.0]: https://github.com/johnhowrey/bookarr-public/releases/tag/v0.1.0
