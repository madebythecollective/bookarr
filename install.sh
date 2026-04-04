#!/usr/bin/env bash
set -e

echo "=== Bookarr Installer ==="
echo ""

# Check Python version
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required but not found."
    echo "Install Python from https://python.org or via your package manager."
    exit 1
fi

echo "Found Python: $PYTHON ($($PYTHON --version))"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Install directory: $SCRIPT_DIR"

# Install dependencies
echo ""
echo "Installing dependencies..."
"$PYTHON" -m pip install --break-system-packages -q pillow requests beautifulsoup4 2>/dev/null \
    || "$PYTHON" -m pip install -q pillow requests beautifulsoup4

echo "Dependencies installed."

# Create static/covers directory
mkdir -p "$SCRIPT_DIR/static/covers"

# Platform-specific service setup
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    echo ""
    echo "=== macOS Setup ==="
    PLIST_SRC="$SCRIPT_DIR/service/com.bookarr.plist"
    PLIST_DEST="$HOME/Library/LaunchAgents/com.bookarr.plist"

    if [ -f "$PLIST_SRC" ]; then
        sed "s|BOOKARR_PATH|$SCRIPT_DIR|g" "$PLIST_SRC" > "$PLIST_DEST"
        echo "LaunchAgent installed at $PLIST_DEST"
        echo ""
        echo "To start Bookarr as a service:"
        echo "  launchctl load $PLIST_DEST"
        echo ""
        echo "To stop:"
        echo "  launchctl unload $PLIST_DEST"
    fi

elif [ "$OS" = "Linux" ]; then
    echo ""
    echo "=== Linux Setup ==="
    SERVICE_SRC="$SCRIPT_DIR/service/bookarr.service"
    SERVICE_DEST="/etc/systemd/system/bookarr.service"

    if [ -f "$SERVICE_SRC" ]; then
        echo "To install as a systemd service (requires sudo):"
        echo ""
        echo "  sudo sed 's|BOOKARR_PATH|$SCRIPT_DIR|g; s|BOOKARR_USER|$USER|g' $SERVICE_SRC > $SERVICE_DEST"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable --now bookarr"
    fi
fi

echo ""
echo "=== Quick Start ==="
echo "  $PYTHON $SCRIPT_DIR/bookarr.py"
echo ""
echo "Then open http://localhost:8585 in your browser."
echo ""
echo "First run:"
echo "  1. Go to Settings and configure your Prowlarr URL and API key"
echo "  2. Configure your NZBGet or torrent client connection"
echo "  3. Set your eBook and audiobook save paths"
echo "  4. Go to Discover and add authors or seed from curated lists"
echo ""
echo "Documentation: https://github.com/madebythecollective/bookarr/tree/main/docs"
echo ""
echo "Done!"
