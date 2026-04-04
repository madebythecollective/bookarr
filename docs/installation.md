# Installation

This guide covers installing Bookarr on macOS, Linux, and Windows.

## Recommended: Download the installer

The easiest way to install Bookarr is to download the installer for your platform from the [Releases page](https://github.com/madebythecollective/bookarr/releases/latest). No Python installation or command-line knowledge is required.

| Platform | File | What to do |
|---|---|---|
| **macOS** | `Bookarr-x.x.x-macos.dmg` | Open the DMG, drag Bookarr to your Applications folder, launch it. |
| **Windows** | `Bookarr-x.x.x-windows-setup.exe` | Run the installer. Bookarr appears in your Start Menu. |

After launching, open [http://localhost:8585](http://localhost:8585) in your browser to access the Bookarr web UI.

### macOS installer details

- The Bookarr app bundles everything it needs — no Python installation required.
- Data (database, cover art cache) is stored in `~/Library/Application Support/Bookarr/`.
- To uninstall, drag Bookarr out of your Applications folder. Optionally delete the data directory.

### Windows installer details

- The installer includes everything — no Python installation required.
- You can choose to add a Desktop shortcut and auto-start with Windows.
- The installer can add a Windows Firewall rule for port 8585.
- Data (database, cover art cache) is stored in `%APPDATA%\Bookarr\`.
- To uninstall, use "Add or Remove Programs" in Windows Settings.

## Requirements

Whether you use the installer or run from source, you need:

- **[Prowlarr](https://prowlarr.com/)** — Usenet and torrent indexer manager. Bookarr searches through Prowlarr's API.
- **[NZBGet](https://nzbget.com/)** or a **torrent client** — At least one download client for automated downloads.

These are configured through the Bookarr **Settings** page after installation. If you already use Sonarr or Radarr, your existing Prowlarr and download client work with Bookarr.

---

## Alternative: Install from source

The following options are for users who prefer running from source. Python 3.10 or later and pip are required.

Bookarr has three Python dependencies: `pillow`, `requests`, and `beautifulsoup4`. These are installed automatically by the install script or via pip.

## macOS (from source)

### Option 1: Install script

```bash
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
./install.sh
```

The install script:

1. Verifies Python 3.10+ is available.
2. Installs Python dependencies (`pillow`, `requests`, `beautifulsoup4`).
3. Creates the `static/covers/` directory for cached cover art.
4. Installs a launchd plist to `~/Library/LaunchAgents/com.bookarr.plist` so Bookarr starts automatically and restarts on failure.

After installation, start the service:

```bash
launchctl load ~/Library/LaunchAgents/com.bookarr.plist
```

To stop it:

```bash
launchctl unload ~/Library/LaunchAgents/com.bookarr.plist
```

### Option 2: Manual install

```bash
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
pip install -r requirements.txt
python3 bookarr.py
```

### Homebrew Python note

If you use Homebrew Python on macOS, PEP 668 prevents pip from installing packages globally. Use:

```bash
pip install --break-system-packages -r requirements.txt
```

Or create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 bookarr.py
```

## Linux

### Option 1: Install script

```bash
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
./install.sh
```

The install script installs dependencies and prints instructions for setting up the systemd service.

### Option 2: Manual install with systemd

```bash
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
pip install -r requirements.txt
```

Set up the systemd service:

```bash
sudo cp service/bookarr.service /etc/systemd/system/
```

Edit the service file to set your paths and username:

```bash
sudo nano /etc/systemd/system/bookarr.service
```

Replace `BOOKARR_PATH` with the absolute path to your Bookarr directory (for example, `/opt/bookarr`) and `BOOKARR_USER` with the user account that should run Bookarr.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bookarr
```

Check status:

```bash
sudo systemctl status bookarr
journalctl -u bookarr -f
```

## Windows

### Option 1: Install script

```cmd
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
install.bat
```

The install script installs Python dependencies and creates the covers directory.

### Option 2: Manual install

```cmd
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
pip install -r requirements.txt
python bookarr.py
```

### Running as a Windows service

Bookarr does not include a native Windows service wrapper. To run it as a service, use [NSSM](https://nssm.cc/):

```cmd
nssm install Bookarr python C:\path\to\bookarr\bookarr.py
nssm set Bookarr AppDirectory C:\path\to\bookarr
nssm start Bookarr
```

## Docker

### Docker Compose (recommended)

```bash
git clone https://github.com/madebythecollective/bookarr.git
cd bookarr
```

Edit `docker-compose.yml` to mount your media directories:

```yaml
volumes:
  - ./data:/app/data
  - /path/to/ebooks:/books
  - /path/to/audiobooks:/audiobooks
```

Start the container:

```bash
docker compose up -d
```

Then configure your save paths in Settings to `/books` and `/audiobooks` (the container-side mount points).

### Docker CLI

```bash
docker build -t bookarr .
docker run -d \
  --name bookarr \
  -p 8585:8585 \
  -v $(pwd)/data:/app/data \
  -v /path/to/ebooks:/books \
  -v /path/to/audiobooks:/audiobooks \
  --restart unless-stopped \
  bookarr
```

### Health check

The Docker image includes a health check that polls `/api/stats` every 30 seconds. Check container health with:

```bash
docker inspect --format='{{.State.Health.Status}}' bookarr
```

## Verifying the installation

After starting Bookarr, open your browser to [http://localhost:8585](http://localhost:8585). You should see the Bookarr web UI with the Library page.

If Bookarr does not start, check:

1. **Port conflict.** Another application may be using port 8585. Use `--port` to choose a different port: `python3 bookarr.py --port 8787`
2. **Python version.** Run `python3 --version` and confirm it is 3.10 or later.
3. **Missing dependencies.** Run `pip install -r requirements.txt` again and check for errors.
4. **Logs.** Check `bookarr.log` in the installation directory for error messages.

## Updating

To update Bookarr to the latest version:

```bash
cd bookarr
git pull origin main
pip install -r requirements.txt
```

Then restart the service. Your database and settings are preserved across updates.

## Uninstalling

1. Stop the Bookarr service (launchd, systemd, or terminate the process).
2. Remove the service file if installed (`~/Library/LaunchAgents/com.bookarr.plist` on macOS, `/etc/systemd/system/bookarr.service` on Linux).
3. Delete the installation directory.

All data (database, covers, logs) is stored inside the installation directory and is removed with it.
