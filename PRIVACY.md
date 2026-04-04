# Privacy Policy

**Effective date:** April 3, 2026
**Last updated:** April 3, 2026

## Overview

Bookarr is a self-hosted application that runs entirely on your own hardware. This privacy policy explains what data the Software handles and where it goes.

**The short version:** Bookarr does not collect, transmit, or share any personal data with the Bookarr project or its maintainers.

## Data storage

All data is stored locally on your machine in a SQLite database file (`bookarr.db`) in the Bookarr installation directory. This includes:

| Data | Purpose | Storage location |
|---|---|---|
| Book and author metadata | Library management | `bookarr.db` |
| Download history | Activity tracking | `bookarr.db` |
| Configuration and credentials | Service connections | `bookarr.db` (settings table) |
| Cover art images | Display in web UI | `static/covers/` directory |
| Application logs | Debugging and monitoring | `bookarr.log` |

## Credentials

Bookarr stores service credentials (API keys, usernames, passwords) that you enter through the Settings page. These are stored in plain text in the local SQLite database. Bookarr does not encrypt stored credentials.

**You are responsible for:**

- Restricting access to the machine running Bookarr
- Securing the `bookarr.db` file from unauthorized access
- Not exposing the Bookarr web UI to the public internet without authentication

## Network requests

Bookarr makes outbound network requests to services you configure and to public APIs for metadata. It does not phone home or contact any server operated by the Bookarr project.

### Requests you configure

| Destination | Purpose | When |
|---|---|---|
| Prowlarr instance | Search indexers for books | Background search, manual search |
| NZBGet instance | Submit and monitor downloads | Grabbing releases, checking status |
| Torrent client | Submit and monitor torrents | Grabbing releases, checking status |
| Pushover API | Send push notifications | On grab or download events (if configured) |

### Automatic metadata requests

| Destination | Purpose | When |
|---|---|---|
| `openlibrary.org` | Author search, book metadata, cover images | Adding authors, seeding, cover display |
| `api.audible.com` | Verify audiobook editions exist | Adding authors, audiobook checks |

These requests include search queries (author names, book titles) and are subject to the privacy policies of those services.

## Web UI access

The Bookarr web UI is served on your local network. By default, it binds to `0.0.0.0` (all network interfaces) on port `8585`. This means any device on your local network can access it.

Bookarr does not include built-in authentication. If you need to restrict access:

- Use a reverse proxy (such as Nginx or Caddy) with authentication
- Configure firewall rules to restrict access by IP
- Bind to `127.0.0.1` only (requires modifying the source)

## Data the Bookarr project receives

**None.** Bookarr does not include analytics, telemetry, crash reporting, update checks, or any mechanism that transmits data to the project maintainers.

The only way the Bookarr project receives information from you is if you voluntarily open a GitHub issue or contribute to the repository.

## Third-party privacy policies

Services that Bookarr integrates with have their own privacy policies:

- [Open Library Privacy Policy](https://openlibrary.org/about)
- [Audible Privacy Notice](https://www.audible.com/privacy)
- [Pushover Privacy Policy](https://pushover.net/privacy)

## Data deletion

To delete all data stored by Bookarr:

1. Stop the Bookarr process.
2. Delete the `bookarr.db`, `bookarr.db-shm`, and `bookarr.db-wal` files.
3. Delete the `static/covers/` directory.
4. Delete the `bookarr.log` file.
5. Uninstall the application by removing the installation directory.

## Changes to this policy

Changes to this privacy policy will be noted in the [Changelog](CHANGELOG.md). Material changes will be highlighted in the release notes.

## Contact

For privacy questions, open an issue on the [Bookarr GitHub repository](https://github.com/johnhowrey/bookarr-public).
