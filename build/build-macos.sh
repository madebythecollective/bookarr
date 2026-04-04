#!/usr/bin/env bash
set -e

# Build Bookarr.app for macOS using PyInstaller
# Output: dist/Bookarr.app and dist/Bookarr-VERSION-macos.dmg
#
# Prerequisites:
#   pip install pyinstaller
#   brew install create-dmg   (for .dmg packaging)

VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Building Bookarr $VERSION for macOS ==="
echo ""

# Clean previous builds
rm -rf build/pyinstaller dist/Bookarr.app dist/Bookarr

# Build with PyInstaller
echo "Running PyInstaller..."
pyinstaller build/bookarr.spec --distpath dist --workpath build/pyinstaller --clean

echo ""
echo "App bundle created at dist/Bookarr.app"

# Create DMG if create-dmg is available
if command -v create-dmg &>/dev/null; then
    echo ""
    echo "Creating DMG installer..."

    DMG_NAME="Bookarr-${VERSION}-macos.dmg"
    rm -f "dist/$DMG_NAME"

    create-dmg \
        --volname "Bookarr $VERSION" \
        --volicon "static/apple-touch-icon.png" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "Bookarr.app" 150 190 \
        --app-drop-link 450 190 \
        --hide-extension "Bookarr.app" \
        --no-internet-enable \
        "dist/$DMG_NAME" \
        "dist/Bookarr.app"

    echo ""
    echo "DMG created at dist/$DMG_NAME"
else
    echo ""
    echo "Skipping DMG creation (install create-dmg: brew install create-dmg)"
    echo "The .app bundle at dist/Bookarr.app can be used directly."
fi

echo ""
echo "=== Build complete ==="
