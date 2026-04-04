# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Bookarr.

Builds a standalone application that bundles Python, all dependencies,
templates, and static assets. Users don't need Python installed.

Usage:
    pyinstaller build/bookarr.spec

macOS output: dist/Bookarr.app
Windows output: dist/Bookarr/Bookarr.exe
"""

import platform

block_cipher = None

a = Analysis(
    ['../bookarr.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../templates', 'templates'),
        ('../static/favicon.ico', 'static'),
        ('../static/favicon.svg', 'static'),
        ('../static/favicon-16.png', 'static'),
        ('../static/favicon-32.png', 'static'),
        ('../static/apple-touch-icon.png', 'static'),
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'requests',
        'bs4',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'xml.sax',
        'pydoc',
        'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if platform.system() == 'Darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Bookarr',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon='../static/favicon.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Bookarr',
    )
    app = BUNDLE(
        coll,
        name='Bookarr.app',
        icon='../static/apple-touch-icon.png',
        bundle_identifier='com.bookarr.app',
        info_plist={
            'CFBundleDisplayName': 'Bookarr',
            'CFBundleShortVersionString': '0.2.0',
            'CFBundleVersion': '0.2.0',
            'LSMinimumSystemVersion': '10.15',
            'LSUIElement': False,
            'NSHighResolutionCapable': True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Bookarr',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon='../static/favicon.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Bookarr',
    )
