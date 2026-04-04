# Building installers

This guide covers building the macOS `.dmg` and Windows `.exe` installers from source. Most users should download pre-built installers from the [Releases page](https://github.com/johnhowrey/bookarr-public/releases/latest) instead.

## How it works

Bookarr uses [PyInstaller](https://pyinstaller.org/) to bundle the Python interpreter, all dependencies, templates, and static assets into a standalone application. Users do not need Python installed.

- **macOS:** PyInstaller creates a `.app` bundle, which is packaged into a `.dmg` with [create-dmg](https://github.com/create-dmg/create-dmg).
- **Windows:** PyInstaller creates a directory with `Bookarr.exe`, which is wrapped in an installer using [Inno Setup](https://jrsoftware.org/isinfo.php).

## Data directories

When running as a packaged app, mutable data (database, cover art cache) is stored in a platform-appropriate location:

| Platform | Data directory |
|---|---|
| macOS | `~/Library/Application Support/Bookarr/` |
| Windows | `%APPDATA%\Bookarr\` |
| Linux | `~/.bookarr/` |

Bundled assets (templates, static files) are read from inside the frozen application bundle.

## Building on macOS

### Prerequisites

```bash
pip install pyinstaller
brew install create-dmg
```

### Build

```bash
chmod +x build/build-macos.sh
build/build-macos.sh
```

### Output

- `dist/Bookarr.app` — standalone macOS application
- `dist/Bookarr-VERSION-macos.dmg` — drag-to-install disk image

## Building on Windows

### Prerequisites

1. Install Python 3.10 or later.
2. Install PyInstaller: `pip install pyinstaller`
3. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (for the installer; optional).

### Build

```cmd
build\build-windows.bat
```

### Output

- `dist\Bookarr\Bookarr.exe` — standalone Windows executable (plus supporting files)
- `dist\Bookarr-VERSION-windows-setup.exe` — Windows installer (if Inno Setup is installed)

## Automated builds (GitHub Actions)

The repository includes a GitHub Actions workflow (`.github/workflows/release.yml`) that automatically builds both macOS and Windows installers when a version tag is pushed:

```bash
git tag v0.2.0
git push origin v0.2.0
```

This triggers the workflow, which:

1. Builds the macOS `.app` and `.dmg` on a macOS runner.
2. Builds the Windows `.exe` and installer on a Windows runner.
3. Creates a GitHub Release with both installers attached.

## Build files reference

| File | Purpose |
|---|---|
| `build/bookarr.spec` | PyInstaller specification (shared by macOS and Windows) |
| `build/build-macos.sh` | macOS build script (PyInstaller + create-dmg) |
| `build/build-windows.bat` | Windows build script (PyInstaller + Inno Setup) |
| `build/installer.iss` | Inno Setup script for Windows installer |
| `.github/workflows/release.yml` | GitHub Actions CI/CD for automated releases |

## Updating the version

When releasing a new version, update the version string in:

1. `build/bookarr.spec` — `CFBundleShortVersionString` and `CFBundleVersion`
2. `build/installer.iss` — `MyAppVersion`
3. `build/build-macos.sh` — `VERSION`
4. `build/build-windows.bat` — `VERSION`
5. `templates/index.html` — version badge in sidebar and About page
6. `CHANGELOG.md` — add new version section
