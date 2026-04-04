# Running as a service

This guide covers setting up Bookarr to start automatically on boot and restart on failure.

## macOS (launchd)

macOS uses `launchd` for managing background services. Bookarr includes a plist file for this.

### Automatic setup

The install script handles this for you:

```bash
./install.sh
```

### Manual setup

1. Copy the plist to your LaunchAgents directory:

```bash
cp service/com.bookarr.plist ~/Library/LaunchAgents/
```

2. Edit the plist and replace `BOOKARR_PATH` with the absolute path to your Bookarr installation:

```bash
nano ~/Library/LaunchAgents/com.bookarr.plist
```

Replace all instances of `BOOKARR_PATH` (for example, `/Users/yourname/bookarr-public`).

3. Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.bookarr.plist
```

### Managing the service

| Action | Command |
|---|---|
| Start | `launchctl load ~/Library/LaunchAgents/com.bookarr.plist` |
| Stop | `launchctl unload ~/Library/LaunchAgents/com.bookarr.plist` |
| Check status | `launchctl list | grep bookarr` |
| View logs | `tail -f /path/to/bookarr-public/bookarr.log` |

### Plist configuration details

| Key | Value | Description |
|---|---|---|
| `Label` | `com.bookarr` | Service identifier |
| `RunAtLoad` | `true` | Start when the plist is loaded (login) |
| `KeepAlive` | `true` | Restart automatically if the process exits |
| `StandardOutPath` | `BOOKARR_PATH/bookarr.log` | stdout log file |
| `StandardErrorPath` | `BOOKARR_PATH/bookarr.log` | stderr log file |

## Linux (systemd)

### Setup

1. Copy the service file:

```bash
sudo cp service/bookarr.service /etc/systemd/system/
```

2. Edit the service file:

```bash
sudo nano /etc/systemd/system/bookarr.service
```

Replace `BOOKARR_PATH` with the absolute path to your Bookarr installation (for example, `/opt/bookarr`).

Replace `BOOKARR_USER` with the user account that should run Bookarr.

3. Reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bookarr
```

### Managing the service

| Action | Command |
|---|---|
| Start | `sudo systemctl start bookarr` |
| Stop | `sudo systemctl stop bookarr` |
| Restart | `sudo systemctl restart bookarr` |
| Check status | `sudo systemctl status bookarr` |
| View logs | `journalctl -u bookarr -f` |
| Disable auto-start | `sudo systemctl disable bookarr` |

### Service configuration details

| Key | Value | Description |
|---|---|---|
| `Type` | `simple` | The process runs in the foreground |
| `Restart` | `on-failure` | Restart only on non-zero exit |
| `RestartSec` | `10` | Wait 10 seconds before restarting |
| `WantedBy` | `multi-user.target` | Start in normal multi-user mode |

## Windows

Bookarr does not include a native Windows service. There are several options for running it in the background.

### Option 1: NSSM (recommended)

[NSSM](https://nssm.cc/) (Non-Sucking Service Manager) wraps any executable as a Windows service.

1. Download NSSM from [nssm.cc](https://nssm.cc/).
2. Install the service:

```cmd
nssm install Bookarr python C:\path\to\bookarr-public\bookarr.py
nssm set Bookarr AppDirectory C:\path\to\bookarr-public
nssm start Bookarr
```

3. Manage the service:

```cmd
nssm status Bookarr
nssm stop Bookarr
nssm remove Bookarr confirm
```

### Option 2: Task Scheduler

1. Open Task Scheduler.
2. Create a new task with trigger "At startup."
3. Set the action to run `python` with argument `C:\path\to\bookarr-public\bookarr.py`.
4. Set "Start in" to the Bookarr installation directory.
5. Check "Run whether user is logged on or not."

### Option 3: Run manually

Run Bookarr in a terminal window:

```cmd
python bookarr.py
```

The process runs until the terminal is closed.

## Custom port

All service configurations use the default port (8585). To use a custom port, modify the service file to include the `--port` argument:

**macOS plist:**
```xml
<array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>BOOKARR_PATH/bookarr.py</string>
    <string>--port</string>
    <string>8787</string>
</array>
```

**Linux systemd:**
```ini
ExecStart=/usr/bin/python3 BOOKARR_PATH/bookarr.py --port 8787
```

## Verifying the service is running

After starting the service, verify Bookarr is accessible:

```bash
curl -s http://localhost:8585/api/stats | head -c 100
```

You should see a JSON response with library statistics. If the connection is refused, check the service status and log files.
