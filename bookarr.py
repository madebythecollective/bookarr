#!/usr/bin/env python3
"""
Bookarr — Book Manager and Automation
Like Radarr, but for books. Searches usenet indexers via Prowlarr,
downloads via NZBGet, manages your ebook library.

Usage:
    python3 bookarr.py                  # Start web UI on port 8585
    python3 bookarr.py --port 8787      # Custom port
    python3 bookarr.py --seed           # Seed with prize-winning authors
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from functools import wraps
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ensure print output isn't buffered (important for launchd log capture)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ---------------------------------------------------------------------------
# Configuration — path resolution
# ---------------------------------------------------------------------------
# When running from source, all paths are relative to this script file.
# When running as a packaged app (PyInstaller), bundled assets (templates,
# static files) are inside the frozen bundle, while mutable data (database,
# covers, logs) goes to a platform-appropriate user data directory.

def _get_paths():
    # BOOKARR_DATA_DIR env var overrides the data directory (useful for Docker)
    env_data_dir = os.environ.get("BOOKARR_DATA_DIR")

    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        bundle_dir = sys._MEIPASS
        if env_data_dir:
            data_dir = env_data_dir
        elif sys.platform == 'darwin':
            data_dir = os.path.join(os.path.expanduser("~"), "Library",
                                    "Application Support", "Bookarr")
        elif sys.platform == 'win32':
            data_dir = os.path.join(os.environ.get("APPDATA",
                                    os.path.expanduser("~")), "Bookarr")
        else:
            data_dir = os.path.join(os.path.expanduser("~"), ".bookarr")
        os.makedirs(data_dir, exist_ok=True)
    else:
        # Running from source — everything in the script directory
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = env_data_dir if env_data_dir else bundle_dir
        if env_data_dir:
            os.makedirs(data_dir, exist_ok=True)
    return bundle_dir, data_dir

_BUNDLE_DIR, _DATA_DIR = _get_paths()

DB_PATH = os.path.join(_DATA_DIR, "bookarr.db")
TEMPLATE_DIR = os.path.join(_BUNDLE_DIR, "templates")
COVER_CACHE_DIR = os.path.join(_DATA_DIR, "static", "covers")
STATIC_DIR = os.path.join(_BUNDLE_DIR, "static")

# --- Initial defaults (seeded into DB on first run, then managed via Settings UI) ---
# For a fresh install, set these to your values. After first run, use Settings.
_INIT_PROWLARR_URL = "http://localhost:9696"
_INIT_PROWLARR_API_KEY = ""
_INIT_PROWLARR_INDEXER_IDS = "1,2,3"
_INIT_NZBGET_URL = "http://localhost:6789/jsonrpc"
_INIT_NZBGET_USER = ""
_INIT_NZBGET_PASS = ""
_INIT_EBOOK_PATH = ""
_INIT_AUDIOBOOK_PATH = ""

# Newznab/Torznab categories
CAT_EBOOK = "7000,7020,7030,7040,7050,7060"
CAT_AUDIOBOOK = "3000,3030,3040"
CAT_BOOKS_ALL = "7000,7020,7030,7040,7050,7060,3000,3030,3040"

# Open Library API
OL_SEARCH_AUTHORS = "https://openlibrary.org/search/authors.json"
OL_SEARCH_BOOKS = "https://openlibrary.org/search.json"
OL_AUTHOR_WORKS = "https://openlibrary.org/authors/{}/works.json"
OL_AUTHOR_INFO = "https://openlibrary.org/authors/{}.json"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ol_key TEXT,
            bio TEXT,
            monitored INTEGER DEFAULT 1,
            added_at TEXT DEFAULT (datetime('now')),
            UNIQUE(name)
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            ol_key TEXT,
            year INTEGER,
            isbn TEXT,
            cover_id INTEGER,
            monitored INTEGER DEFAULT 1,
            status TEXT DEFAULT 'missing',
            book_type TEXT DEFAULT 'ebook',
            path TEXT,
            author_count INTEGER DEFAULT 1,
            added_at TEXT DEFAULT (datetime('now')),
            UNIQUE(author_id, title, book_type)
        );
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER REFERENCES books(id),
            nzbget_id INTEGER,
            nzb_name TEXT,
            indexer TEXT,
            size_bytes INTEGER,
            status TEXT DEFAULT 'queued',
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'english');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('search_interval', '900');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_search', '1');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('max_size_mb_ebook', '200');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('max_size_mb_audiobook', '5000');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('min_score', '30');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('want_format', 'both');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('min_seeders', '1');
        CREATE TABLE IF NOT EXISTS search_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            results INTEGER,
            grabbed INTEGER,
            searched_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS source_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            added_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS indexer_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indexer_id TEXT NOT NULL,
            query TEXT,
            result_count INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_msg TEXT,
            queried_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
        CREATE INDEX IF NOT EXISTS idx_books_author ON books(author_id);
        CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name);
        CREATE INDEX IF NOT EXISTS idx_istats_indexer ON indexer_stats(indexer_id);
        CREATE INDEX IF NOT EXISTS idx_istats_time ON indexer_stats(queried_at);
    """)
    # Seed initial config from constants (only inserted on first run)
    for key, val in [
        ("ebook_path", _INIT_EBOOK_PATH),
        ("audiobook_path", _INIT_AUDIOBOOK_PATH),
        ("preferred_ebook_format", "epub"),
        ("prowlarr_url", _INIT_PROWLARR_URL),
        ("prowlarr_api_key", _INIT_PROWLARR_API_KEY),
        ("prowlarr_indexer_ids", _INIT_PROWLARR_INDEXER_IDS),
        ("nzbget_url", _INIT_NZBGET_URL),
        ("nzbget_user", _INIT_NZBGET_USER),
        ("nzbget_pass", _INIT_NZBGET_PASS),
        ("torrent_client", ""),
        ("torrent_host", ""),
        ("torrent_user", ""),
        ("torrent_pass", ""),
        ("torrent_category", "bookarr"),
        ("torrent_indexer_ids", ""),
        ("seed_ratio_limit", "1.0"),
        ("seed_time_limit", "0"),
        ("pushover_token", ""),
        ("pushover_user", ""),
    ]:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    # Migration: add columns if missing
    for migration in [
        "ALTER TABLE books ADD COLUMN author_count INTEGER DEFAULT 1",
        "ALTER TABLE books ADD COLUMN last_searched TEXT",
        "ALTER TABLE books ADD COLUMN last_result_count INTEGER DEFAULT 0",
        "ALTER TABLE downloads ADD COLUMN download_client TEXT DEFAULT 'nzbget'",
        "ALTER TABLE downloads ADD COLUMN torrent_hash TEXT",
        "ALTER TABLE downloads ADD COLUMN error_detail TEXT",
        "ALTER TABLE books ADD COLUMN last_grab_reason TEXT",
        "ALTER TABLE authors ADD COLUMN seed_source TEXT",
    ]:
        try:
            conn.execute(migration)
        except Exception:
            pass  # Column already exists
    # Backfill seed_source for existing authors that have no value yet
    _backfill_seed_source(conn)
    conn.commit()
    conn.close()


def _backfill_seed_source(conn):
    """Set seed_source for existing authors based on SEED_CATEGORIES membership."""
    rows = conn.execute("SELECT id, name FROM authors WHERE seed_source IS NULL").fetchall()
    if not rows:
        return
    # Build lookup: author name (lower) -> category key
    name_to_cat = {}
    for key, cat in SEED_CATEGORIES.items():
        for author_name in cat["authors"]:
            name_to_cat[author_name.lower().strip()] = key
    updated = 0
    for row in rows:
        source = name_to_cat.get(row["name"].lower().strip(), "manual")
        conn.execute("UPDATE authors SET seed_source=? WHERE id=?", (source, row["id"]))
        updated += 1
    if updated:
        print(f"[Backfill] Set seed_source on {updated} authors")

# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_ebook_path():
    return get_setting("ebook_path", "")

def get_audiobook_path():
    return get_setting("audiobook_path", "")

def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

# Language patterns for filtering non-English results
NON_ENGLISH_PATTERNS = [
    # German
    r"\b(german|deutsch|ger)\b", r"\.DE\.", r"-DE-", r"\bDE\b",
    # French
    r"\b(french|francais|fra|fre)\b", r"\.FR\.", r"-FR-", r"\bFRENch\b",
    # Spanish
    r"\b(spanish|espanol|spa|esp)\b", r"\.ES\.", r"-ES-",
    # Italian
    r"\b(italian|italiano|ita)\b", r"\.IT\.", r"-IT-",
    # Portuguese
    r"\b(portuguese|portugues|por)\b", r"\.PT\.", r"-PT-",
    # Dutch
    r"\b(dutch|nederlands|nld)\b", r"\.NL\.", r"-NL-",
    # Russian
    r"\b(russian|russkiy|rus)\b", r"\.RU\.", r"-RU-",
    # Chinese
    r"\b(chinese|zhongwen|chi|chn)\b", r"\.CN\.", r"-CN-",
    # Japanese
    r"\b(japanese|nihongo|jpn)\b", r"\.JP\.", r"-JP-",
    # Korean
    r"\b(korean|hangugeo|kor)\b", r"\.KR\.", r"-KR-",
    # Swedish
    r"\b(swedish|svenska|swe)\b", r"\.SE\.", r"-SE-",
    # Generic foreign markers
    r"\bforeign\b", r"\bmulti\b",
]

# Compile patterns once
_NON_ENGLISH_RE = [re.compile(p, re.IGNORECASE) for p in NON_ENGLISH_PATTERNS]

def is_non_english(text):
    """Check if a release title appears to be non-English."""
    for pattern in _NON_ENGLISH_RE:
        if pattern.search(text):
            return True
    return False

def normalize_title(title):
    """Normalize a book title for deduplication. Lowercase, strip articles,
    remove subtitles, edition markers, and parenthetical annotations."""
    t = title.lower().strip()
    # Remove leading articles
    for article in ('the ', 'a ', 'an '):
        if t.startswith(article):
            t = t[len(article):]
    # Remove parenthetical content: "(Esprios Classics)", "(retail)", etc.
    t = re.sub(r'\([^)]*\)', '', t)
    # Remove everything after colon/dash subtitle markers for dedup
    t = re.split(r'\s*[:\-—–]\s*', t)[0]
    # Remove common edition/variant markers
    t = re.sub(r'\b(annotated|illustrated|unabridged|abridged|revised|expanded|'
               r'complete|collected|selected|deluxe|limited|special|classic[s]?|'
               r'esprios|edition|editon|reprint|facsimile)\b', '', t)
    # Collapse whitespace and strip punctuation
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# Patterns that indicate junk/non-book entries from Open Library
_JUNK_PATTERNS = [
    # Study guides & academic
    r'sparknotes', r'cliffsnotes', r'cliff\'?s\s+notes', r'study\s+guide',
    r'literature\s+guide', r'critical\s+(perspectives|essays|companion)',
    r'reader\'?s?\s+guide', r'teacher\'?s?\s+guide', r'teaching\s+guide',
    r'prentice\s+hall', r'holt\s+mcdougal', r'norton\s+anthology',
    r'scribner\s+library', r'multiple\s+critical',
    r'bloom\'?s?\s+(guides?|notes|reviews)',
    r'masterplots', r'magill\'?s', r'twayne\'?s',
    r'\bbedford\s+introduction\b', r'\bintroduction\s+to\s+literature\b',
    r'\bsightlines\s+\d',
    # Textbooks / college readers
    r'\bcollege\b.*\b(reader|english|reading)\b',
    r'\b(reader|english|reading)\b.*\bcollege\b',
    r'\bcollege\s+of\b', r'\buniversity\s+press\b',
    r'\beac\s+\d', r'\benglish\s+\d{2,3}\b',
    r'\bcourse\s+(reader|packet|pack)\b',
    # Foreign editions
    r'spanish\s+edition', r'german\s+edition', r'french\s+edition',
    r'italian\s+edition', r'portuguese\s+edition', r'russian\s+edition',
    r'chinese\s+edition', r'japanese\s+edition', r'korean\s+edition',
    r'arabic\s+edition', r'dutch\s+edition', r'swedish\s+edition',
    r'turkish\s+edition', r'hebrew\s+edition', r'polish\s+edition',
    r'\bedition\b.*\bspanish\b', r'\bedition\b.*\bgerman\b',
    r'\bem\s+portugu', r'do\s+brasil\b',
    r'en\s+espa', r'auf\s+deutsch', r'en\s+fran',
    # Boxed sets / collections
    r'boxed?\s+set', r'box\s+\w+',
    r'three-book\s+collection', r'four-book\s+collection',
    r'\b\d+-book\s+collection',
    # Collected/Complete/Selected works
    r'collected\s+works\b', r'collected\s+plays\b', r'collected\s+stories\b',
    r'complete\s+works\b', r'complete\s+novels\b', r'complete\s+stories\b',
    r'selected\s+works\b', r'selected\s+stories\b',
    # Opera/music
    r'\bvocal\s+score\b', r'\bopera\b.*\bscore\b', r'\blibretto\b',
    # Volumes/bands
    r'\b(vol|volume)\s*\.?\s*\d', r'\bband\s+\d',
    # Non-English packaging
    r'coleccion\s+\w+', r'kit\s+de\s+lectura', r'\bbiblioteca\b',
    # Misc junk
    r'\bessay\s+on\s+going\b', r'\bdebate\s+on\b',
    r'peerless\s+\w+', r'esprios\s+classics',
    r'\bforecast[s]?\s+of\b', r'\bpress\s+cutting[s]?\b',
    r'\bwhat\s+\w+ism\s+is\b', r'\bcorrespond[ae]nce\b',
    # Anthologies / "best of" / multi-author compilations
    r'best\s+(american|british)\s+short\s+stories\s+\d',
    r'\byear\'?s?\s+best\s+(fantasy|horror|science|dark|mystery)',
    r'\bgreatest\s+(mysteries|stories|tales|novels|hits)',
    r'\btreasury\s+of\b', r'\barchives?\b',
    r'\bantholog(y|ies)\b', r'\bcompendium\b',
    r'\bgranta\s+#?\d', r'\bmagazine\s+#?\d',
    r'\b\d+\s+stories\]', r'\[\d+\s+\w+\]',  # [24 stories], [18 stories]
    r'moving\s+beyond\s+the\s+page',
    r'do-it-yourself',
]
_JUNK_RE = [re.compile(p, re.IGNORECASE) for p in _JUNK_PATTERNS]

def is_junk_title(title):
    """Check if a title is a study guide, anthology, textbook, or other non-original work."""
    if not title:
        return True
    # Very short titles (single char, digit)
    stripped = title.strip()
    if len(stripped) <= 2:
        return True
    # Pure numbers
    if stripped.isdigit():
        return True
    # Known junk patterns
    for pat in _JUNK_RE:
        if pat.search(title):
            return True
    return False

def is_english_title(title):
    """Check if a book title appears to be in English.
    Uses multiple heuristics: non-ASCII character ratio, non-Latin scripts,
    transliteration detection, and comprehensive foreign-language word detection."""
    if not title:
        return False

    # Reject non-Latin scripts immediately (Cyrillic, CJK, Arabic, Devanagari, Thai, Hebrew)
    if re.search(r'[\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF'
                 r'\u0600-\u06FF\u0900-\u097F\u0E00-\u0E7F\u0590-\u05FF]', title):
        return False

    # Check ratio of non-ASCII characters — English titles are mostly ASCII
    non_ascii = sum(1 for c in title if ord(c) > 127)
    if len(title) > 3 and non_ascii / len(title) > 0.15:
        return False

    # Reject specific accented chars that are very rare in English titles
    if re.search(r'[äöüßàâçèêëîïôùûÿæœñáéíóúãõąćęłńśźżčřšžůďåøėėṭṿḥṣẓḍḳḷṃṇṛðþ]', title, re.IGNORECASE):
        return False

    # Detect combining diacritical marks (used in transliterations)
    if re.search(r'[\u0300-\u036F\uFE20-\uFE2F]', title):
        return False

    # Detect transliterated titles (Hebrew, Russian, etc.)
    t_lower = title.lower()
    # Hebrew transliteration markers
    if 'ʻ' in title or 'ʾ' in title:
        return False
    # CJK romanization (pinyin) — many 1-2 letter syllables in a row
    tiny_words = re.findall(r'\b[a-z]{1,2}\b', t_lower)
    all_words = re.findall(r'\b[a-z]+\b', t_lower)
    if len(all_words) >= 5 and len(tiny_words) / len(all_words) > 0.5:
        return False
    # Common transliteration markers
    if re.search(r'︠|︡|̐', title):
        return False
    # Hebrew "Ha-" prefix pattern or hyphenated Hebrew transliteration
    if re.search(r'\bha-[A-Z]', title):
        return False
    # Hyphenated transliteration patterns (she-tsarikh, al-kitab, etc.)
    if re.search(r'\b\w+-\w+-\w+', t_lower) and not re.search(r'(do-it|self-|well-|ill-|all-|re-|pre-|non-|co-|anti-|semi-|multi-|inter-|over-|under-|out-)', t_lower):
        hyphen_parts = re.findall(r'\b(\w+-\w+(?:-\w+)*)\b', t_lower)
        for part in hyphen_parts:
            pieces = part.split('-')
            if len(pieces) >= 3 and all(len(p) <= 6 for p in pieces):
                return False

    # Short titles (1-3 words) starting with foreign articles are likely foreign
    title_words = t_lower.split()
    if len(title_words) <= 3 and title_words[0] in ('la', 'le', 'il', 'el', 'los', 'las', 'les', 'die', 'das', 'der', 'den'):
        return False

    # Explicit language markers in parentheses (including "Em Portuguese do Brasil" etc.)
    if re.search(r'\(\s*(em\s+)?(spanish|french|german|italian|portugu\w*|russian|polish|dutch|'
                 r'swedish|chinese|japanese|korean|arabic|hebrew|turkish|czech|hungarian|'
                 r'finnish|greek|romanian|croatian|serbian|bulgarian|ukrainian|hindi|'
                 r'catalan|basque|galician|esperanto)', t_lower):
        return False

    # Comprehensive foreign word detection
    foreign_words = {
        # German
        'und', 'der', 'die', 'das', 'ein', 'eine', 'dem', 'den', 'des',
        'nicht', 'ist', 'ich', 'auf', 'auch', 'sich', 'von', 'aus',
        'nach', 'wie', 'aber', 'bei', 'gesammelt', 'schriften',
        'rede', 'gedichte', 'geschichten', 'briefe', 'zwischen',
        'oder', 'uber', 'ohne', 'zeit', 'leben', 'welt', 'kleine',
        'grosse', 'neue', 'alte', 'mein', 'dein', 'sein', 'ihre',
        'herr', 'frau', 'mann', 'haus', 'buch', 'teil',
        # French
        'les', 'des', 'une', 'dans', 'avec', 'sur', 'pour', 'pas',
        'sont', 'tout', 'qui', 'cette', 'mais', 'nous',
        'comme', 'aussi', 'peut', 'entre', 'chez', 'vers',
        'lettres', 'oeuvres', 'histoire', 'nouvelles', 'poemes',
        'contes', 'essai', 'essais', 'recueil', 'chansons',
        'homme', 'femme', 'monde', 'mort', 'vie', 'amour',
        'vraie', 'selon', 'origines', 'petit', 'petite',
        'grande', 'vieux', 'beau', 'belle', 'fou', 'folle',
        'jour', 'nuit', 'roi', 'reine', 'fille', 'dieu',
        'terre', 'ciel', 'coeur', 'sang', 'hiver',
        'deux', 'trois', 'quatre', 'cinq', 'sept', 'huit', 'neuf', 'dix',
        'collines', 'vertes', 'temps', 'sans', 'sous', 'contre',
        # Spanish
        'los', 'las', 'del', 'con', 'por', 'para',
        'como', 'pero', 'todo', 'esta', 'cuando', 'donde',
        'novela', 'cuentos', 'poesias', 'historias',
        'muerte', 'hombre', 'mujer', 'tierra',
        'alegre', 'triste', 'nuevo', 'nueva',
        'mala', 'raza', 'manantial', 'agota', 'sobre',
        'hijo', 'hija', 'pueblo', 'calle', 'sangre',
        'viejo', 'armas', 'adios', 'reportajes', 'discursos',
        'novelas', 'relatos', 'feliz', 'indocumentado', 'coronel',
        'tiene', 'quien', 'escriba', 'asalto', 'olor', 'guayaba',
        'comentario', 'textos', 'lectura', 'obras', 'completas',
        'laberinto', 'porwania', 'smutnych', 'dziwkach', 'rzecz',
        # Italian
        'gli', 'della', 'nella', 'delle', 'degli', 'dello', 'nel',
        'che', 'sono', 'per', 'come',
        'questo', 'quella', 'tutti', 'tutto', 'anche', 'ancora',
        'poesie', 'racconti', 'opere', 'saggi', 'lettere', 'primi',
        'romanzo', 'storia', 'uomo', 'donna', 'amore',
        'manoscritti', 'barbare', 'odi', 'tragedia', 'falsa', 'vero',
        'scritti', 'studi', 'memorie', 'pensieri', 'discorsi',
        'confessioni', 'battaglie', 'notte', 'giorno',
        'pomeriggio', 'senza', 'tre', 'soldati', 'venere', 'paese',
        'alto', 'azioni', 'reazioni', 'annodomini',
        # Portuguese
        'uma', 'mais', 'isso', 'quando',
        'muito', 'depois', 'ainda', 'outro', 'outros',
        # Dutch
        'het', 'een', 'voor', 'naar', 'zijn', 'niet',
        'heeft', 'werd', 'wordt', 'deze', 'geen',
        # Scandinavian
        'och', 'att', 'som', 'inte', 'eller', 'har',
        'vid', 'mot', 'mycket', 'efter', 'alla', 'utan',
        'med', 'automobil', 'barnet', 'tagewerk', 'unser',
        # Polish
        'nie', 'jest', 'tak', 'jak', 'ale', 'przy',
        'dusza', 'zgubiona', 'wyrazisty',
        # Danish/Norwegian
        'digte', 'ord',
        # Russian transliteration
        'dneĭ', 'smerti', 'storona', 'otkrytom', 'kolokol',
        # Turkish transliteration
        'yolculuk', 'yabancinin', 'cocugu', 'cocuk',
        # Hebrew transliteration
        'devarim', 'tsarikh', 'tsarikhe', 'kitsur', 'haggadah',
        'sefer', 'midrash', 'mishnah', 'talmud', 'zeh',
        'makom', 'shamayim', 'gesher', 'shalom',
        # Misc transliterations
        'desperaishen',
        # Spanish additions
        'orilla', 'pasion', 'femre',
        # Latin (common in titles)
        'rerum', 'vitae', 'liber', 'opus', 'magna',
        'contra', 'scripta', 'quod', 'tertia', 'secunda',
    }

    words = set(re.findall(r'\b[a-z]+\b', t_lower))
    # Count foreign word matches
    matches = words & foreign_words
    # Words that are both English and foreign — don't count
    ambiguous = {'a', 'i', 'in', 'on', 'me', 'no', 'so', 'us', 'or', 'an',
                 'as', 'at', 'it', 'is', 'if', 'to', 'do', 'de', 'el',
                 'he', 'we', 'my', 'be', 'go', 'up', 'by', 'am', 'not',
                 'van', 'non', 'con', 'grand', 'que', 'la', 'mer',
                 'vie', 'nova', 'prima', 'band', 'mars', 'sol', 'casa',
                 'amor'}
    matches -= ambiguous

    if len(matches) >= 1:
        return False

    # Check for words with common foreign-language endings
    foreign_endings = (
        'zioni', 'zione', 'keit', 'heit', 'schaft', 'ung',
        'stvo', 'nost', 'iky', 'kazy', 'niki', 'iche', 'iche',
    )
    for w in words:
        if len(w) > 4 and any(w.endswith(end) for end in foreign_endings):
            return False

    # For multi-word titles, require at least one common English word
    # This catches remaining foreign titles that slip past the word list
    if len(words) >= 3:
        common_english = {
            'the', 'and', 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'from',
            'by', 'an', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'shall', 'can', 'must', 'not', 'but', 'or', 'nor', 'so',
            'yet', 'both', 'either', 'neither', 'each', 'every', 'all', 'any',
            'few', 'more', 'most', 'other', 'some', 'such', 'than', 'too',
            'very', 'just', 'about', 'above', 'after', 'again', 'against',
            'before', 'between', 'into', 'through', 'during', 'under', 'over',
            'out', 'up', 'down', 'off', 'then', 'once', 'here', 'there',
            'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom',
            'this', 'that', 'these', 'those', 'his', 'her', 'its', 'our',
            'their', 'my', 'your', 'he', 'she', 'it', 'we', 'they', 'them',
            'him', 'me', 'you', 'us', 'new', 'old', 'first', 'last', 'long',
            'great', 'little', 'own', 'right', 'big', 'high', 'good', 'best',
            'man', 'woman', 'day', 'night', 'time', 'year', 'way', 'world',
            'life', 'death', 'love', 'war', 'king', 'god', 'lord', 'son',
            'house', 'city', 'land', 'book', 'story', 'stories', 'tale', 'tales',
            'poems', 'poetry', 'letters', 'collected', 'selected', 'complete',
            'dark', 'light', 'black', 'white', 'red', 'blue', 'green', 'golden',
            'wild', 'lost', 'dead', 'last', 'secret', 'silent', 'sacred',
            'blood', 'fire', 'water', 'wind', 'stone', 'dream', 'heart',
            'among', 'beyond', 'without', 'within', 'upon', 'across', 'along',
        }
        if not (words & common_english):
            return False

    return True

# ---------------------------------------------------------------------------
# Audiobook Verification (Open Library + Audible fallback)
# ---------------------------------------------------------------------------

def check_audiobook_exists(author_name, title, ol_key=None):
    """Check if an audiobook exists via Open Library editions (primary) or Audible catalog (fallback)."""
    # Primary: check Open Library editions for audiobook formats
    if ol_key:
        try:
            url = f"https://openlibrary.org/works/{ol_key}/editions.json?limit=100"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Bookarr/1.0 (book automation)")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                for edition in data.get("entries", []):
                    fmt = (edition.get("physical_format") or "").lower()
                    if any(kw in fmt for kw in ("audio", "audible", "cd audiobook", "mp3")):
                        print(f"[Audiobook] OL hit: '{title}' has audiobook edition (format: {fmt})")
                        return True
        except Exception as e:
            print(f"[Audiobook] OL error checking '{title}': {e}")

    # Fallback: check Audible catalog API
    try:
        query = urllib.parse.quote(f"{title}")
        author_q = urllib.parse.quote(f"{author_name}")
        url = f"https://api.audible.com/1.0/catalog/products?title={query}&author={author_q}&num_results=1"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Bookarr/1.0 (book automation)")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("total_results", 0) > 0:
                print(f"[Audiobook] Audible hit: '{title}' by {author_name}")
                return True
    except Exception as e:
        print(f"[Audiobook] Audible error checking '{title}': {e}")

    return False

# ---------------------------------------------------------------------------
# Open Library API
# ---------------------------------------------------------------------------

def ol_request(url, timeout=15):
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Bookarr/1.0 (book automation)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[OL] Error fetching {url}: {e}")
        return None

def search_books_ol(query, limit=20):
    """Search Open Library for books by title, author, or ISBN."""
    url = f"{OL_SEARCH_BOOKS}?q={urllib.parse.quote(query)}&limit={limit}&language=eng"
    data = ol_request(url)
    if not data:
        return []
    results = []
    for doc in data.get("docs", []):
        cover_id = doc.get("cover_i")
        author_keys = doc.get("author_key", [])
        results.append({
            "key": doc.get("key", "").replace("/works/", ""),
            "title": doc.get("title", ""),
            "author_name": ", ".join(doc.get("author_name", [])),
            "author_key": author_keys[0] if author_keys else "",
            "year": doc.get("first_publish_year"),
            "cover_id": cover_id,
            "edition_count": doc.get("edition_count", 0),
            "isbn": (doc.get("isbn", []) or [""])[0],
        })
    return results

def search_author_ol(name):
    """Search Open Library for an author, return list of matches."""
    url = f"{OL_SEARCH_AUTHORS}?q={urllib.parse.quote(name)}&limit=5"
    data = ol_request(url)
    if not data:
        return []
    results = []
    for doc in data.get("docs", []):
        results.append({
            "key": doc.get("key", ""),
            "name": doc.get("name", ""),
            "work_count": doc.get("work_count", 0),
            "top_work": doc.get("top_work", ""),
            "birth_date": doc.get("birth_date", ""),
        })
    return results

def get_author_works(ol_key, limit=100):
    """Get an author's works from Open Library."""
    url = OL_AUTHOR_WORKS.format(ol_key) + f"?limit={limit}"
    data = ol_request(url)
    if not data:
        return []
    works = []
    for entry in data.get("entries", []):
        title = entry.get("title", "")
        if not title:
            continue
        # Get year from first_publish_date or created
        year = None
        fpd = entry.get("first_publish_date", "")
        if fpd:
            m = re.search(r"(\d{4})", fpd)
            if m:
                year = int(m.group(1))
        # Get cover ID
        covers = entry.get("covers", [])
        cover_id = covers[0] if covers else None
        # Skip negative cover IDs (placeholders)
        if cover_id and cover_id < 0:
            cover_id = None
        author_count = len(entry.get("authors", []))
        if author_count < 1:
            author_count = 1
        works.append({
            "key": entry.get("key", "").replace("/works/", ""),
            "title": title,
            "year": year,
            "cover_id": cover_id,
            "author_count": author_count,
        })
    return works

def get_author_info(ol_key):
    """Get author bio from Open Library."""
    url = OL_AUTHOR_INFO.format(ol_key)
    data = ol_request(url)
    if not data:
        return {}
    bio = data.get("bio", "")
    if isinstance(bio, dict):
        bio = bio.get("value", "")
    return {
        "name": data.get("name", ""),
        "bio": bio[:500] if bio else "",
        "birth_date": data.get("birth_date", ""),
        "death_date": data.get("death_date", ""),
    }

# ---------------------------------------------------------------------------
# Prowlarr / Indexer Search (Newznab + Torznab)
# ---------------------------------------------------------------------------

def search_prowlarr(query, indexer_id, categories=CAT_BOOKS_ALL):
    """Search a Prowlarr indexer endpoint (handles both Newznab and Torznab)."""
    prowlarr_url = get_setting("prowlarr_url", "").rstrip("/")
    api_key = get_setting("prowlarr_api_key", "")
    if not prowlarr_url or not api_key:
        return []
    url = (f"{prowlarr_url}/{indexer_id}/api?"
           f"apikey={api_key}&t=search"
           f"&q={urllib.parse.quote(query)}&cat={categories}&limit=50")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            tree = ET.parse(resp)
    except Exception as e:
        print(f"[Search] Error querying indexer {indexer_id}: {e}")
        return []

    results = []
    ns = {
        "newznab": "http://www.newznab.com/DTD/2010/feeds/attributes/",
        "torznab": "http://torznab.com/schemas/2015/feed",
    }
    for item in tree.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        # Get attributes from both namespaces
        attrs = {}
        for attr in item.findall("newznab:attr", ns):
            attrs[attr.get("name", "")] = attr.get("value", "")
        for attr in item.findall("torznab:attr", ns):
            attrs[attr.get("name", "")] = attr.get("value", "")
        size = int(attrs.get("size", "0"))
        cat = attrs.get("category", "")
        seeders = int(attrs.get("seeders", "0")) if "seeders" in attrs else None
        leechers = int(attrs.get("leechers", "0")) if "leechers" in attrs else None

        # Detect protocol
        enclosure = item.find("enclosure")
        enc_type = enclosure.get("type", "") if enclosure is not None else ""
        protocol = "torrent" if ("bittorrent" in enc_type or seeders is not None) else "usenet"

        results.append({
            "title": title,
            "link": link,
            "size": size,
            "category": cat,
            "indexer_id": indexer_id,
            "guid": item.findtext("guid", ""),
            "protocol": protocol,
            "seeders": seeders,
            "leechers": leechers,
        })
    return results

def _log_indexer_stat(indexer_id, query, result_count, success=True, error_msg=None):
    """Record an indexer query result for health tracking."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO indexer_stats (indexer_id, query, result_count, success, error_msg) VALUES (?,?,?,?,?)",
            (str(indexer_id), query, result_count, 1 if success else 0, error_msg)
        )
        # Prune old stats (keep last 7 days)
        conn.execute("DELETE FROM indexer_stats WHERE queried_at < datetime('now', '-7 days')")
        conn.commit()
        conn.close()
    except Exception:
        pass

def search_all_indexers(query, categories=CAT_BOOKS_ALL):
    """Search all configured usenet and torrent indexers via Prowlarr."""
    all_results = []
    # Usenet indexers
    usenet_ids = get_setting("prowlarr_indexer_ids", "")
    if usenet_ids:
        for idx_id in [x.strip() for x in usenet_ids.split(",") if x.strip()]:
            try:
                results = search_prowlarr(query, idx_id, categories)
                all_results.extend(results)
                _log_indexer_stat(idx_id, query, len(results))
            except Exception as e:
                print(f"[Search] Usenet indexer {idx_id} error: {e}")
                _log_indexer_stat(idx_id, query, 0, success=False, error_msg=str(e)[:200])
    # Torrent indexers
    torrent_ids = get_setting("torrent_indexer_ids", "")
    if torrent_ids:
        for idx_id in [x.strip() for x in torrent_ids.split(",") if x.strip()]:
            try:
                results = search_prowlarr(query, idx_id, categories)
                all_results.extend(results)
                _log_indexer_stat(idx_id, query, len(results))
            except Exception as e:
                print(f"[Search] Torrent indexer {idx_id} error: {e}")
                _log_indexer_stat(idx_id, query, 0, success=False, error_msg=str(e)[:200])
    return all_results

def _sanitize_path(name):
    """Remove chars that are invalid in file/folder names."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip().rstrip('.')


def score_result(result, book_title, author_name, book_type="ebook"):
    """Score a search result for relevance to a specific book."""
    title_lower = result["title"].lower()
    book_lower = book_title.lower()
    author_lower = author_name.lower()
    score = 0

    # --- Language filter ---
    lang_pref = get_setting("language", "english")
    if lang_pref != "any" and is_non_english(result["title"]):
        return -1  # Hard reject

    # --- Music/soundtrack filter ---
    # Reject releases that are clearly music albums, not books or audiobooks
    music_indicators = ["flac", "16bit", "24bit", "32bit", "wavpack", "dsd", "sacd",
                        "vinyl", "lp-", "-lp", "discography", "remaster", "deluxe edition",
                        "original cast recording", "original soundtrack", "ost-", "-ost",
                        "soundtrack", "album", "single", "v0", "320kbps", "44khz", "48khz",
                        "96khz", "192khz", "cd-flac", "web-flac"]
    if any(ind in title_lower for ind in music_indicators):
        # Exception: don't reject if it also clearly says "audiobook" or "narrated"
        if not any(ok in title_lower for ok in ["audiobook", "narrated", "unabridged", "read by"]):
            return -1  # Hard reject music

    # Author name match
    author_parts = author_lower.split()
    for part in author_parts:
        if len(part) > 2 and part in title_lower:
            score += 20

    # Book title match
    book_words = [w for w in book_lower.split() if len(w) > 2]
    matched_words = sum(1 for w in book_words if w in title_lower)
    if book_words:
        score += int(60 * matched_words / len(book_words))

    # Format preferences
    if book_type == "ebook":
        pref_fmt = get_setting("preferred_ebook_format", "epub").lower()
        if pref_fmt != "any":
            if pref_fmt in title_lower:
                score += 15  # Bonus for matching preferred format
        if "epub" in title_lower:
            score += 10
        if "mobi" in title_lower or "azw" in title_lower:
            score += 5
        if "pdf" in title_lower:
            score += 2
    elif book_type == "audiobook":
        if "audiobook" in title_lower:
            score += 10
        if "mp3" in title_lower:
            score += 5
        if "m4b" in title_lower:
            score += 8

    # Size limits from settings
    size_mb = result["size"] / (1024 * 1024) if result["size"] else 0
    max_size = int(get_setting(
        "max_size_mb_audiobook" if book_type == "audiobook" else "max_size_mb_ebook", "200"
    ))
    if size_mb > max_size and size_mb > 0:
        score -= 50

    # Penalize very small files
    if 0 < size_mb < 0.1:
        score -= 10

    # Penalize if it looks like a collection/pack
    if any(w in title_lower for w in ["pack", "collection", "bundle", "top-ebooks"]):
        score -= 40

    # Torrent health: seeders bonus/penalty
    seeders = result.get("seeders")
    if seeders is not None:
        min_seeders = int(get_setting("min_seeders", "1"))
        if seeders == 0:
            score -= 30  # Dead torrent
        elif seeders < min_seeders:
            score -= 15
        elif seeders >= 10:
            score += 10
        elif seeders >= 5:
            score += 5

    return max(0, score)

# ---------------------------------------------------------------------------
# Pushover Notifications
# ---------------------------------------------------------------------------

def send_pushover(title, message):
    """Send a Pushover notification (configure token/user in Settings)."""
    token = get_setting("pushover_token", "")
    user = get_setting("pushover_user", "")
    if not token or not user:
        return
    try:
        data = urllib.parse.urlencode({
            "token": token,
            "user": user,
            "title": title,
            "message": message,
        }).encode()
        req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[Pushover] Error: {e}")

# ---------------------------------------------------------------------------
# NZBGet
# ---------------------------------------------------------------------------

def nzbget_call(method, params=None):
    """Call NZBGet JSON-RPC API."""
    import base64
    url = get_setting("nzbget_url", "")
    if not url:
        return None
    nzbget_user = get_setting("nzbget_user", "")
    nzbget_pass = get_setting("nzbget_pass", "")
    payload = {"method": method, "params": params or []}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    creds = base64.b64encode(f"{nzbget_user}:{nzbget_pass}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("result")
    except Exception as e:
        print(f"[NZBGet] Error: {e}")
        return None

def fetch_nzb(url):
    """Download an NZB file from a URL, following redirects with proper User-Agent."""
    import base64
    try:
        # Build opener that sends User-Agent on redirects too
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", "Bookarr/1.0 (book automation)")]
        with opener.open(url, timeout=30) as resp:
            content = resp.read()
            if content and b"<nzb" in content.lower():
                return base64.b64encode(content).decode()
            print(f"[NZBGet] Downloaded content doesn't look like an NZB ({len(content)} bytes)")
            return None
    except Exception as e:
        print(f"[NZBGet] Failed to fetch NZB from {url[:80]}: {e}")
        return None

def send_to_nzbget(nzb_url, title, category="Books"):
    """Fetch NZB from URL, then send content to NZBGet."""
    # Download the NZB ourselves (handles redirects properly)
    nzb_content = fetch_nzb(nzb_url)
    if not nzb_content:
        print(f"[NZBGet] Could not fetch NZB for: {title}")
        return 0

    result = nzbget_call("append", [
        title + ".nzb",     # NZBFilename
        nzb_content,        # Content (base64-encoded NZB)
        category,           # Category
        100,                # Priority (100 = VeryHigh — books/audiobooks)
        False,              # AddToTop
        False,              # AddPaused
        "",                 # DupeKey
        0,                  # DupeScore
        "score",            # DupeMode
        []                  # PPParameters
    ])
    return result  # Returns NZBID or 0 on failure

# ---------------------------------------------------------------------------
# Torrent Clients (qBittorrent, Transmission)
# ---------------------------------------------------------------------------

def _qbit_login():
    """Login to qBittorrent Web API, return session cookie string or None."""
    host = get_setting("torrent_host", "").rstrip("/")
    user = get_setting("torrent_user", "")
    pwd = get_setting("torrent_pass", "")
    if not host:
        return None
    data = urllib.parse.urlencode({"username": user, "password": pwd}).encode()
    try:
        req = urllib.request.Request(f"{host}/api/v2/auth/login", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            for cookie in (resp.headers.get_all("Set-Cookie") or []):
                if "SID=" in cookie:
                    return cookie.split(";")[0]
        return None
    except Exception as e:
        print(f"[qBit] Login error: {e}")
        return None

def send_to_qbittorrent(torrent_url, title, category=None):
    """Send a torrent URL or magnet to qBittorrent. Returns torrent hash on success, None on failure."""
    cookie = _qbit_login()
    if not cookie:
        print("[qBit] Could not login")
        return None
    host = get_setting("torrent_host", "").rstrip("/")
    cat = category or get_setting("torrent_category", "bookarr")
    data = urllib.parse.urlencode({
        "urls": torrent_url,
        "category": cat,
        "rename": title,
    }).encode()
    try:
        req = urllib.request.Request(f"{host}/api/v2/torrents/add", data=data)
        req.add_header("Cookie", cookie)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = resp.read().decode()
            if result.strip().lower() in ("ok.", "ok"):
                print(f"[qBit] Added: {title}")
                # Try to find the hash by matching the name we set via rename
                time.sleep(1)  # Brief wait for qBit to register the torrent
                torrents = _qbit_torrents(cat)
                for t in torrents:
                    if t.get("name") == title:
                        thash = t.get("hash", "")
                        if thash:
                            print(f"[qBit] Found hash: {thash}")
                            return thash
                # Fallback: return True-ish marker if hash not found yet
                print(f"[qBit] Added but could not find hash for: {title}")
                return "pending"
            print(f"[qBit] Unexpected response: {result[:100]}")
            return None
    except Exception as e:
        print(f"[qBit] Error adding torrent: {e}")
        return None

def _qbit_torrents(category=None):
    """List torrents from qBittorrent, optionally filtered by category."""
    cookie = _qbit_login()
    if not cookie:
        return []
    host = get_setting("torrent_host", "").rstrip("/")
    cat = category or get_setting("torrent_category", "bookarr")
    url = f"{host}/api/v2/torrents/info?category={urllib.parse.quote(cat)}"
    try:
        req = urllib.request.Request(url)
        req.add_header("Cookie", cookie)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[qBit] Error listing torrents: {e}")
        return []

def _qbit_remove(torrent_hash, delete_files=False):
    """Remove a torrent from qBittorrent."""
    cookie = _qbit_login()
    if not cookie:
        return
    host = get_setting("torrent_host", "").rstrip("/")
    data = urllib.parse.urlencode({
        "hashes": torrent_hash,
        "deleteFiles": str(delete_files).lower(),
    }).encode()
    try:
        req = urllib.request.Request(f"{host}/api/v2/torrents/delete", data=data)
        req.add_header("Cookie", cookie)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[qBit] Error removing torrent: {e}")

def send_to_transmission(torrent_url, title, category=None):
    """Send a torrent URL or magnet to Transmission. Returns True on success."""
    import base64
    host = get_setting("torrent_host", "").rstrip("/")
    user = get_setting("torrent_user", "")
    pwd = get_setting("torrent_pass", "")
    if not host:
        return None
    rpc_url = f"{host}/transmission/rpc"
    payload = json.dumps({
        "method": "torrent-add",
        "arguments": {"filename": torrent_url}
    }).encode()

    # Transmission requires X-Transmission-Session-Id (get it from 409 response)
    session_id = ""
    for attempt in range(2):
        try:
            req = urllib.request.Request(rpc_url, data=payload,
                                         headers={"Content-Type": "application/json",
                                                   "X-Transmission-Session-Id": session_id})
            if user:
                creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                req.add_header("Authorization", f"Basic {creds}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if result.get("result") == "success":
                    print(f"[Transmission] Added: {title}")
                    return True
                print(f"[Transmission] Error: {result.get('result')}")
                return None
        except urllib.error.HTTPError as e:
            if e.code == 409:
                session_id = e.headers.get("X-Transmission-Session-Id", "")
                continue
            print(f"[Transmission] HTTP error: {e}")
            return None
        except Exception as e:
            print(f"[Transmission] Error: {e}")
            return None
    return None

def send_to_torrent_client(torrent_url, title, category=None):
    """Route to the configured torrent client. Returns torrent hash (or 'pending') on success, None on failure."""
    client = get_setting("torrent_client", "")
    if client == "qbittorrent":
        return send_to_qbittorrent(torrent_url, title, category)
    elif client == "transmission":
        return send_to_transmission(torrent_url, title, category)
    else:
        print(f"[Torrent] No torrent client configured (got '{client}')")
        return None

def test_prowlarr():
    """Test Prowlarr connection. Returns (success, message)."""
    url = get_setting("prowlarr_url", "").rstrip("/")
    key = get_setting("prowlarr_api_key", "")
    if not url or not key:
        return False, "Prowlarr URL or API key not configured"
    try:
        req = urllib.request.Request(f"{url}/api/v1/health?apikey={key}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return True, f"Connected to {url}"
    except Exception as e:
        return False, str(e)

def test_nzbget():
    """Test NZBGet connection. Returns (success, message)."""
    url = get_setting("nzbget_url", "")
    if not url:
        return False, "NZBGet URL not configured"
    result = nzbget_call("version")
    if result:
        return True, f"NZBGet v{result}"
    return False, "Could not connect to NZBGet"

def test_torrent_client():
    """Test torrent client connection. Returns (success, message)."""
    client = get_setting("torrent_client", "")
    if not client:
        return False, "No torrent client configured"
    host = get_setting("torrent_host", "")
    if not host:
        return False, "Torrent host not configured"
    if client == "qbittorrent":
        cookie = _qbit_login()
        if cookie:
            return True, f"Connected to qBittorrent at {host}"
        return False, "Could not login to qBittorrent"
    elif client == "transmission":
        # Quick test: try to get session
        try:
            import base64
            rpc_url = f"{host.rstrip('/')}/transmission/rpc"
            req = urllib.request.Request(rpc_url)
            user = get_setting("torrent_user", "")
            if user:
                pwd = get_setting("torrent_pass", "")
                creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                req.add_header("Authorization", f"Basic {creds}")
            urllib.request.urlopen(req, timeout=10)
            return True, f"Connected to Transmission at {host}"
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return True, f"Connected to Transmission at {host}"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)
    return False, f"Unknown client: {client}"

# ---------------------------------------------------------------------------
# Library scanning
# ---------------------------------------------------------------------------

BOOK_EXTENSIONS = {".epub", ".mobi", ".azw", ".azw3", ".pdf", ".djvu", ".fb2", ".cbz", ".cbr"}

def scan_library():
    """Scan save paths and source folders, match files to known books, and organize them."""
    conn = get_db()
    matched = 0

    # Collect all folders to scan: save paths + custom source folders
    scan_dirs = [get_ebook_path(), get_audiobook_path()]
    try:
        source_rows = conn.execute("SELECT path FROM source_folders").fetchall()
        for r in source_rows:
            if r["path"] not in scan_dirs:
                scan_dirs.append(r["path"])
    except Exception:
        pass

    for root_dir in scan_dirs:
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in BOOK_EXTENSIONS and ext not in {".mp3", ".m4b", ".m4a", ".ogg", ".flac"}:
                    continue
                fpath = os.path.join(dirpath, fname)
                # Try to match by filename
                name_clean = os.path.splitext(fname)[0].lower()
                # Search for matching book
                row = conn.execute(
                    "SELECT b.id, b.book_type, a.name as author_name, b.title "
                    "FROM books b JOIN authors a ON b.author_id = a.id "
                    "WHERE b.status != 'downloaded' AND lower(b.title) LIKE ?",
                    (f"%{name_clean[:30]}%",)
                ).fetchone()
                if row:
                    # If file is not already in the organized location, move it
                    root = get_audiobook_path() if row["book_type"] == "audiobook" else get_ebook_path()
                    fmt_folder = "audiobook" if row["book_type"] == "audiobook" else "ebook"
                    organized_dir = os.path.join(
                        root,
                        _sanitize_path(row["author_name"]),
                        _sanitize_path(row["title"]),
                        fmt_folder
                    )
                    # Only move if not already in organized structure
                    if not fpath.startswith(organized_dir):
                        try:
                            os.makedirs(organized_dir, exist_ok=True)
                            dest = os.path.join(organized_dir, fname)
                            shutil.move(fpath, dest)
                            fpath = dest
                            print(f"[Scan] Organized: {fname} -> {organized_dir}")
                        except Exception as e:
                            print(f"[Scan] Error moving {fname}: {e}")

                    conn.execute("UPDATE books SET status='downloaded', path=? WHERE id=?",
                                 (fpath, row["id"]))
                    matched += 1
    conn.commit()
    conn.close()
    return matched


def reorganize_library():
    """One-time migration: move existing files from Author/ to Author/Title/format/ structure."""
    conn = get_db()
    books = conn.execute("""
        SELECT b.id, b.title, b.book_type, b.path, a.name as author_name
        FROM books b JOIN authors a ON b.author_id = a.id
        WHERE b.status = 'downloaded' AND b.path IS NOT NULL AND b.path != ''
    """).fetchall()

    moved = 0
    for book in books:
        old_path = book["path"]
        if not os.path.isfile(old_path):
            continue

        root = get_audiobook_path() if book["book_type"] == "audiobook" else get_ebook_path()
        fmt_folder = "audiobook" if book["book_type"] == "audiobook" else "ebook"
        organized_dir = os.path.join(
            root,
            _sanitize_path(book["author_name"]),
            _sanitize_path(book["title"]),
            fmt_folder
        )

        # Skip if already in correct structure
        if old_path.startswith(organized_dir):
            continue

        try:
            os.makedirs(organized_dir, exist_ok=True)
            new_path = os.path.join(organized_dir, os.path.basename(old_path))
            shutil.move(old_path, new_path)
            conn.execute("UPDATE books SET path=? WHERE id=?", (new_path, book["id"]))
            moved += 1
        except Exception as e:
            print(f"[Migrate] Error moving {old_path}: {e}")

    conn.commit()
    conn.close()
    if moved:
        print(f"[Migrate] Reorganized {moved} files into Author/Title/format/ structure")
    return moved

# ---------------------------------------------------------------------------
# Background search engine
# ---------------------------------------------------------------------------

class SearchEngine:
    def __init__(self):
        self._running = False
        self._thread = None
        # Search progress tracking
        self._search_active = False
        self._search_total = 0
        self._search_done = 0
        self._search_current = ""
        self._search_grabbed = 0
        self._search_started_at = None

    def get_progress(self):
        """Return current search progress state."""
        return {
            "active": self._search_active,
            "total": self._search_total,
            "done": self._search_done,
            "current": self._search_current,
            "grabbed": self._search_grabbed,
            "started_at": self._search_started_at,
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        interval = int(get_setting("search_interval", "900"))
        print(f"[Search] Background search started (every {interval}s)")

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            try:
                self._check_downloads()
            except Exception as e:
                print(f"[Downloads] Check error: {e}")
            try:
                self._search_wanted()
            except Exception as e:
                print(f"[Search] Error: {e}")
            time.sleep(int(get_setting("search_interval", "900")))

    def _check_downloads(self):
        """Check NZBGet and torrent clients for completed/failed downloads."""
        self._check_nzbget_downloads()
        self._check_torrent_downloads()
        self._check_stalled_downloads()

    def _check_nzbget_downloads(self):
        """Check NZBGet for completed/failed downloads and update book status."""
        conn = get_db()
        downloading = conn.execute("""
            SELECT d.id, d.book_id, d.nzbget_id, d.nzb_name, d.size_bytes,
                   b.title, b.book_type, a.name as author_name
            FROM downloads d
            JOIN books b ON d.book_id = b.id
            JOIN authors a ON b.author_id = a.id
            WHERE d.status = 'downloading' AND d.nzbget_id IS NOT NULL
              AND (d.download_client IS NULL OR d.download_client = 'nzbget')
        """).fetchall()
        if not downloading:
            conn.close()
            return

        # Check NZBGet history for these IDs
        history = nzbget_call("history", [False])
        if not history:
            conn.close()
            return

        hist_by_id = {h["NZBID"]: h for h in history}
        updated = 0

        for dl in downloading:
            nzb_id = dl["nzbget_id"]
            if nzb_id not in hist_by_id:
                continue  # Still in queue, not finished yet

            h = hist_by_id[nzb_id]
            status = h.get("Status", "")
            file_size = h.get("FileSizeLo", 0) + (h.get("FileSizeHi", 0) << 32)

            if "SUCCESS" in status:
                # Find the downloaded file, preferring the user's format
                dest_dir = h.get("DestDir", "")
                file_path = ""
                if dest_dir and os.path.isdir(dest_dir):
                    pref_fmt = get_setting("preferred_ebook_format", "epub").lower()
                    candidates = []
                    for fname in os.listdir(dest_dir):
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in BOOK_EXTENSIONS or ext in {".mp3", ".m4b", ".m4a", ".ogg", ".flac"}:
                            fsize = os.path.getsize(os.path.join(dest_dir, fname))
                            candidates.append((fname, ext, fsize))
                    # Sort: preferred format first, then by extension
                    if candidates:
                        candidates.sort(key=lambda x: (0 if x[1] == f".{pref_fmt}" else 1, x[0]))
                        file_path = os.path.join(dest_dir, candidates[0][0])
                        if not file_size:
                            file_size = candidates[0][2]

                # Post-processing: organize the file
                final_path = self._post_process(
                    file_path, dl["book_type"], dl["author_name"], dl["title"])

                conn.execute("UPDATE books SET status='downloaded', path=? WHERE id=?",
                             (final_path or file_path, dl["book_id"]))
                conn.execute("""UPDATE downloads SET status='completed', completed_at=datetime('now'),
                                size_bytes=CASE WHEN size_bytes IS NULL OR size_bytes=0 THEN ? ELSE size_bytes END
                                WHERE id=?""",
                             (file_size, dl["id"]))
                updated += 1
                print(f"[Downloads] Completed: {dl['title']}")

            elif "FAILURE" in status or "DELETED" in status:
                # Capture detailed error info from NZBGet
                error_detail = status
                msg = h.get("Message", "")
                if msg:
                    error_detail = f"{status}: {msg}"
                # Check for common failure patterns
                health = h.get("Health", 0)
                if health and health < 1000:
                    error_detail += f" (health: {health/10:.0f}%)"
                move_status = h.get("MoveStatus", "")
                if move_status and move_status != "NONE":
                    error_detail += f" [move: {move_status}]"
                par_status = h.get("ParStatus", "")
                if par_status and par_status not in ("NONE", "SUCCESS"):
                    error_detail += f" [par: {par_status}]"
                unpack_status = h.get("UnpackStatus", "")
                if unpack_status and unpack_status not in ("NONE", "SUCCESS"):
                    error_detail += f" [unpack: {unpack_status}]"

                conn.execute("UPDATE books SET status='wanted' WHERE id=?", (dl["book_id"],))
                conn.execute("""UPDATE downloads SET status='failed', completed_at=datetime('now'),
                                error_detail=? WHERE id=?""",
                             (error_detail, dl["id"]))
                updated += 1
                print(f"[Downloads] Failed: {dl['title']} ({error_detail})")

        if updated:
            conn.commit()
        conn.close()

    def _check_torrent_downloads(self):
        """Check torrent client for completed/failed downloads."""
        client = get_setting("torrent_client", "")
        if not client:
            return

        conn = get_db()
        downloading = conn.execute("""
            SELECT d.id, d.book_id, d.torrent_hash, d.nzb_name,
                   b.title, b.book_type, a.name as author_name
            FROM downloads d
            JOIN books b ON d.book_id = b.id
            JOIN authors a ON b.author_id = a.id
            WHERE d.status = 'downloading' AND d.download_client = 'torrent'
        """).fetchall()
        if not downloading:
            conn.close()
            return

        # Get all torrents from the client
        if client == "qbittorrent":
            torrents = _qbit_torrents()
            torrent_map = {t.get("hash", "").lower(): t for t in torrents}
            # Also build a name-based map for fallback matching
            torrent_name_map = {t.get("name", ""): t for t in torrents if t.get("name")}
        else:
            conn.close()
            return  # Transmission check would need different implementation

        updated = 0
        for dl in downloading:
            thash = (dl["torrent_hash"] or "").lower()
            t = None
            if thash and thash != "pending" and thash in torrent_map:
                t = torrent_map[thash]
            else:
                # Fallback: match by nzb_name (which was used as the rename param)
                dl_name = dl["nzb_name"] or ""
                if dl_name and dl_name in torrent_name_map:
                    t = torrent_name_map[dl_name]
                    # Backfill the hash for future lookups
                    new_hash = t.get("hash", "")
                    if new_hash:
                        conn.execute("UPDATE downloads SET torrent_hash=? WHERE id=?",
                                     (new_hash, dl["id"]))
                        thash = new_hash.lower()
                        print(f"[Torrent] Backfilled hash for: {dl_name} -> {new_hash}")
                else:
                    # Also try matching by the "author - title" pattern
                    expected_name = f"{dl['author_name']} - {dl['title']}"
                    if expected_name in torrent_name_map:
                        t = torrent_name_map[expected_name]
                        new_hash = t.get("hash", "")
                        if new_hash:
                            conn.execute("UPDATE downloads SET torrent_hash=? WHERE id=?",
                                         (new_hash, dl["id"]))
                            thash = new_hash.lower()
                            print(f"[Torrent] Backfilled hash for: {expected_name} -> {new_hash}")
            if not t:
                continue
            state = t.get("state", "")
            progress = t.get("progress", 0)
            file_size = t.get("total_size", 0) or t.get("size", 0)

            if state in ("uploading", "stalledUP", "pausedUP", "forcedUP", "queuedUP") or progress >= 1.0:
                # Torrent completed — find the file
                content_path = t.get("content_path", "") or t.get("save_path", "")
                file_path = ""
                if content_path and os.path.isdir(content_path):
                    pref_fmt = get_setting("preferred_ebook_format", "epub").lower()
                    candidates = []
                    for root_dir, dirs, files in os.walk(content_path):
                        for fname in files:
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in BOOK_EXTENSIONS or ext in {".mp3", ".m4b", ".m4a", ".ogg", ".flac"}:
                                fpath = os.path.join(root_dir, fname)
                                candidates.append((fpath, ext, os.path.getsize(fpath)))
                    if candidates:
                        candidates.sort(key=lambda x: (0 if x[1] == f".{pref_fmt}" else 1, -x[2]))
                        file_path = candidates[0][0]
                        if not file_size:
                            file_size = candidates[0][2]
                elif content_path and os.path.isfile(content_path):
                    file_path = content_path
                    if not file_size:
                        file_size = os.path.getsize(content_path)

                final_path = self._post_process(
                    file_path, dl["book_type"], dl["author_name"], dl["title"])

                conn.execute("UPDATE books SET status='downloaded', path=? WHERE id=?",
                             (final_path or file_path, dl["book_id"]))
                conn.execute("""UPDATE downloads SET status='completed', completed_at=datetime('now'),
                                size_bytes=CASE WHEN size_bytes IS NULL OR size_bytes=0 THEN ? ELSE size_bytes END
                                WHERE id=?""",
                             (file_size, dl["id"]))
                # Check seed ratio limit and remove if met
                ratio = t.get("ratio", 0)
                seed_ratio = float(get_setting("seed_ratio_limit", "1.0"))
                if seed_ratio > 0 and ratio >= seed_ratio:
                    _qbit_remove(thash, delete_files=False)
                updated += 1
                print(f"[Torrent] Completed: {dl['title']}")

            elif state in ("error", "missingFiles"):
                error_detail = f"Torrent {state}"
                if t.get("num_seeds", 0) == 0:
                    error_detail += " (no seeders)"
                conn.execute("UPDATE books SET status='wanted' WHERE id=?", (dl["book_id"],))
                conn.execute("""UPDATE downloads SET status='failed', completed_at=datetime('now'),
                                error_detail=? WHERE id=?""",
                             (error_detail, dl["id"]))
                updated += 1
                print(f"[Torrent] Failed: {dl['title']} ({error_detail})")

        if updated:
            conn.commit()
        conn.close()

    def _check_stalled_downloads(self):
        """Detect downloads stuck in 'downloading' for >48 hours that no longer exist in any client."""
        conn = get_db()
        stalled = conn.execute("""
            SELECT d.id, d.book_id, d.nzbget_id, d.torrent_hash, d.nzb_name,
                   d.download_client, b.title
            FROM downloads d
            JOIN books b ON d.book_id = b.id
            WHERE d.status = 'downloading'
              AND d.started_at < datetime('now', '-48 hours')
        """).fetchall()
        if not stalled:
            conn.close()
            return

        # Build lookup maps for active downloads in each client
        nzbget_ids = set()
        torrent_hashes = set()
        torrent_names = set()

        # Check NZBGet queue + history
        try:
            queue = nzbget_call("listgroups") or []
            history = nzbget_call("history", [False]) or []
            for item in queue + history:
                nid = item.get("NZBID")
                if nid:
                    nzbget_ids.add(nid)
        except Exception:
            pass

        # Check torrent client
        client = get_setting("torrent_client", "")
        if client == "qbittorrent":
            try:
                torrents = _qbit_torrents()
                for t in torrents:
                    h = t.get("hash", "").lower()
                    if h:
                        torrent_hashes.add(h)
                    n = t.get("name", "")
                    if n:
                        torrent_names.add(n)
            except Exception:
                pass

        updated = 0
        for dl in stalled:
            found = False
            if dl["download_client"] == "nzbget" and dl["nzbget_id"]:
                found = dl["nzbget_id"] in nzbget_ids
            elif dl["download_client"] == "torrent":
                thash = (dl["torrent_hash"] or "").lower()
                found = (thash and thash in torrent_hashes) or (dl["nzb_name"] and dl["nzb_name"] in torrent_names)

            if not found:
                error_detail = "Stalled: not found in download client after 48h"
                conn.execute("UPDATE books SET status='wanted' WHERE id=?", (dl["book_id"],))
                conn.execute("""UPDATE downloads SET status='failed', completed_at=datetime('now'),
                                error_detail=? WHERE id=?""",
                             (error_detail, dl["id"]))
                updated += 1
                print(f"[Downloads] Stalled: {dl['title']} — {error_detail}")

        if updated:
            conn.commit()
        conn.close()

    def _post_process(self, file_path, book_type, author_name, title):
        """Move downloaded files to the organized library folder.
        Structure: {root}/{Author Name}/{Book Title}/{ebook|audiobook}/{filename}
        """
        if not file_path or not os.path.isfile(file_path):
            return file_path

        try:
            root = get_audiobook_path() if book_type == "audiobook" else get_ebook_path()
            fmt_folder = "audiobook" if book_type == "audiobook" else "ebook"
            dest_dir = os.path.join(
                root,
                _sanitize_path(author_name),
                _sanitize_path(title),
                fmt_folder
            )
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(file_path))
            shutil.move(file_path, dest)
            print(f"[Post] Moved {book_type} to {dest}")
            return dest

        except Exception as e:
            print(f"[Post] Error processing {file_path}: {e}")
        return file_path

    def _search_wanted(self):
        conn = get_db()
        # Get wanted books with their author names
        # Prioritize audiobooks: grab 25 audiobooks + 25 ebooks per batch
        wanted_audio = conn.execute("""
            SELECT b.id, b.title, b.year, b.book_type, a.name as author_name
            FROM books b JOIN authors a ON b.author_id = a.id
            WHERE b.status = 'wanted' AND b.monitored = 1 AND a.monitored = 1
              AND b.book_type = 'audiobook'
            ORDER BY b.last_searched ASC NULLS FIRST, b.added_at ASC
            LIMIT 25
        """).fetchall()
        wanted_ebook = conn.execute("""
            SELECT b.id, b.title, b.year, b.book_type, a.name as author_name
            FROM books b JOIN authors a ON b.author_id = a.id
            WHERE b.status = 'wanted' AND b.monitored = 1 AND a.monitored = 1
              AND b.book_type = 'ebook'
            ORDER BY b.last_searched ASC NULLS FIRST, b.added_at ASC
            LIMIT 25
        """).fetchall()
        wanted = list(wanted_audio) + list(wanted_ebook)

        if not wanted:
            self._search_active = False
            return

        print(f"[Search] Searching for {len(wanted)} wanted books...")
        grabbed = 0

        # Set progress tracking
        self._search_active = True
        self._search_total = len(wanted)
        self._search_done = 0
        self._search_grabbed = 0
        self._search_current = ""
        self._search_started_at = datetime.now().isoformat()

        for book in wanted:
            # Pick category based on book type
            cat = CAT_AUDIOBOOK if book["book_type"] == "audiobook" else CAT_EBOOK

            # Update progress
            self._search_current = f"{book['author_name']} — {book['title']}"

            # Mark as being searched
            conn.execute("UPDATE books SET last_searched=datetime('now') WHERE id=?", (book["id"],))
            conn.commit()

            # Search by author + title
            query = f"{book['author_name']} {book['title']}"
            results = search_all_indexers(query, cat)

            if not results:
                # Try just the title
                results = search_all_indexers(book["title"], cat)

            # For audiobooks, try additional search strategies
            if not results and book["book_type"] == "audiobook":
                # Try author + title + "audiobook"
                results = search_all_indexers(f"{query} audiobook", CAT_BOOKS_ALL)
                if not results:
                    # Try with just author last name + title
                    last_name = book["author_name"].split()[-1] if book["author_name"] else ""
                    if last_name:
                        results = search_all_indexers(f"{last_name} {book['title']}", cat)
                if not results:
                    # Try broader search in all book categories
                    results = search_all_indexers(query, CAT_BOOKS_ALL)

            # Update result count
            conn.execute("UPDATE books SET last_result_count=? WHERE id=?",
                         (len(results), book["id"]))

            if not results:
                conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                             ("no results found from any indexer", book["id"]))
                conn.commit()
                continue

            # Score and pick best result (filter out language rejects at -1)
            scored = [(score_result(r, book["title"], book["author_name"], book["book_type"]), r)
                       for r in results]
            scored = [(s, r) for s, r in scored if s >= 0]  # Remove hard rejects
            scored.sort(key=lambda x: x[0], reverse=True)

            if not scored:
                conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                             (f"all {len(results)} results rejected by filters", book["id"]))
                continue

            best_score, best = scored[0]
            min_score = int(get_setting("min_score", "30"))
            if best_score < min_score:
                conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                             (f"best score {best_score} below minimum {min_score}", book["id"]))
                continue  # Too low confidence

            # Route to the right download client based on protocol
            dl_name = f"{book['author_name']} - {book['title']}"
            dl_cat = "Audiobooks" if book["book_type"] == "audiobook" else "Books"
            protocol = best.get("protocol", "usenet")

            if protocol == "torrent":
                torrent_cat = get_setting("torrent_category", "bookarr")
                torrent_result = send_to_torrent_client(best["link"], dl_name, torrent_cat)
                if torrent_result:
                    torrent_hash = torrent_result if torrent_result != "pending" else None
                    conn.execute("UPDATE books SET status='downloading' WHERE id=?", (book["id"],))
                    conn.execute(
                        "INSERT INTO downloads (book_id, nzb_name, indexer, size_bytes, status, download_client, torrent_hash) "
                        "VALUES (?, ?, ?, ?, 'downloading', 'torrent', ?)",
                        (book["id"], best["title"], f"indexer-{best['indexer_id']}", best["size"], torrent_hash)
                    )
                    grabbed += 1
                    size_mb = best['size']/1024/1024 if best['size'] else 0
                    seeders = best.get('seeders', '?')
                    print(f"[Search] Grabbed (torrent): {dl_name} ({size_mb:.0f}MB, {seeders} seeders)")
            else:
                nzbget_id = send_to_nzbget(best["link"], dl_name, dl_cat)
                if nzbget_id and nzbget_id > 0:
                    conn.execute("UPDATE books SET status='downloading' WHERE id=?", (book["id"],))
                    conn.execute(
                        "INSERT INTO downloads (book_id, nzbget_id, nzb_name, indexer, size_bytes, status, download_client) "
                        "VALUES (?, ?, ?, ?, ?, 'downloading', 'nzbget')",
                        (book["id"], nzbget_id, best["title"], f"indexer-{best['indexer_id']}", best["size"])
                    )
                    grabbed += 1
                    size_mb = best['size']/1024/1024 if best['size'] else 0
                    print(f"[Search] Grabbed (usenet): {dl_name} ({size_mb:.0f}MB)")

            # Update progress
            self._search_done += 1
            self._search_grabbed = grabbed

            # Be polite to indexers
            time.sleep(2)

        # Search complete
        self._search_active = False
        self._search_current = ""

        conn.commit()
        conn.close()

        if grabbed:
            conn2 = get_db()
            conn2.execute("INSERT INTO search_log (query, results, grabbed) VALUES (?, ?, ?)",
                          ("background", len(wanted), grabbed))
            conn2.commit()
            conn2.close()
            print(f"[Search] Grabbed {grabbed} of {len(wanted)} wanted books")

    def search_single_book(self, book_id):
        """Search for a single book immediately. Used after wanting a book."""
        conn = get_db()
        book = conn.execute("""
            SELECT b.id, b.title, b.year, b.book_type, a.name as author_name
            FROM books b JOIN authors a ON b.author_id = a.id
            WHERE b.id = ? AND b.status = 'wanted'
        """, (book_id,)).fetchone()
        if not book:
            conn.close()
            return

        print(f"[Search] Immediate search for: {book['author_name']} — {book['title']}")
        cat = CAT_AUDIOBOOK if book["book_type"] == "audiobook" else CAT_EBOOK

        # Mark as being searched
        conn.execute("UPDATE books SET last_searched=datetime('now') WHERE id=?", (book["id"],))
        conn.commit()

        # Search by author + title
        query = f"{book['author_name']} {book['title']}"
        results = search_all_indexers(query, cat)

        if not results:
            results = search_all_indexers(book["title"], cat)

        conn.execute("UPDATE books SET last_result_count=? WHERE id=?",
                     (len(results), book["id"]))

        if not results:
            conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                         ("no results found from any indexer", book["id"]))
            conn.commit()
            conn.close()
            print(f"[Search] No results for: {book['title']}")
            return

        # Score and pick best result
        scored = [(score_result(r, book["title"], book["author_name"], book["book_type"]), r)
                   for r in results]
        scored = [(s, r) for s, r in scored if s >= 0]
        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                         (f"all {len(results)} results rejected by filters", book["id"]))
            conn.commit()
            conn.close()
            print(f"[Search] All results rejected for: {book['title']}")
            return

        best_score, best = scored[0]
        min_score = int(get_setting("min_score", "30"))
        if best_score < min_score:
            conn.execute("UPDATE books SET last_grab_reason=? WHERE id=?",
                         (f"best score {best_score} below minimum {min_score}", book["id"]))
            conn.commit()
            conn.close()
            print(f"[Search] Best score {best_score} < {min_score} for: {book['title']}")
            return

        # Route to the right download client
        dl_name = f"{book['author_name']} - {book['title']}"
        dl_cat = "Audiobooks" if book["book_type"] == "audiobook" else "Books"
        protocol = best.get("protocol", "usenet")

        if protocol == "torrent":
            torrent_cat = get_setting("torrent_category", "bookarr")
            torrent_result = send_to_torrent_client(best["link"], dl_name, torrent_cat)
            if torrent_result:
                torrent_hash = torrent_result if torrent_result != "pending" else None
                conn.execute("UPDATE books SET status='downloading', last_grab_reason='grabbed' WHERE id=?",
                             (book["id"],))
                conn.execute(
                    "INSERT INTO downloads (book_id, nzb_name, indexer, size_bytes, status, download_client, torrent_hash) "
                    "VALUES (?, ?, ?, ?, 'downloading', 'torrent', ?)",
                    (book["id"], best["title"], f"indexer-{best['indexer_id']}", best["size"], torrent_hash)
                )
                size_mb = best['size']/1024/1024 if best['size'] else 0
                print(f"[Search] Grabbed (torrent): {dl_name} ({size_mb:.0f}MB)")
        else:
            nzbget_id = send_to_nzbget(best["link"], dl_name, dl_cat)
            if nzbget_id and nzbget_id > 0:
                conn.execute("UPDATE books SET status='downloading', last_grab_reason='grabbed' WHERE id=?",
                             (book["id"],))
                conn.execute(
                    "INSERT INTO downloads (book_id, nzbget_id, nzb_name, indexer, size_bytes, status, download_client) "
                    "VALUES (?, ?, ?, ?, ?, 'downloading', 'nzbget')",
                    (book["id"], nzbget_id, best["title"], f"indexer-{best['indexer_id']}", best["size"])
                )
                size_mb = best['size']/1024/1024 if best['size'] else 0
                print(f"[Search] Grabbed (usenet): {dl_name} ({size_mb:.0f}MB)")

        conn.commit()
        conn.close()

search_engine = SearchEngine()

# ---------------------------------------------------------------------------
# Vintage cover generation
# ---------------------------------------------------------------------------

COVER_COLORS = [
    (226, 106, 44),   # Bookarr orange
    (0, 133, 105),    # Emerald
    (0, 120, 170),    # Sky blue
    (58, 52, 44),     # Dark brown (kraft)
    (140, 30, 70),    # Rose
    (55, 70, 115),    # Navy
    (65, 135, 135),   # Teal
    (185, 80, 55),    # Terracotta
]
CREAM = (245, 240, 230)
DARK_TEXT = (45, 42, 38)

def _get_font(style, size):
    """Load a system font, with fallbacks."""
    from PIL import ImageFont
    paths = {
        'serif': [
            '/System/Library/Fonts/Supplemental/Georgia Bold.ttf',
            '/System/Library/Fonts/Supplemental/Georgia.ttf',
        ],
        'serif-regular': [
            '/System/Library/Fonts/Supplemental/Georgia.ttf',
        ],
        'sans': [
            '/System/Library/Fonts/Supplemental/Futura.ttc',
            '/System/Library/Fonts/Helvetica.ttc',
        ],
    }
    for path in paths.get(style, []):
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default(size=size)

def _wrap_text(draw, text, font, max_width):
    """Wrap text to fit within max_width, return list of lines."""
    words = text.split()
    lines = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]

def generate_vintage_cover(book_id, title, author_name):
    """Generate a Field Notes-inspired book cover. Clean, utilitarian, Futura type."""
    from PIL import Image, ImageDraw
    import hashlib

    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(COVER_CACHE_DIR, f"{book_id}.png")

    if os.path.exists(cache_path):
        return cache_path

    W, H = 300, 450
    pad = 24  # margin on all sides

    # Deterministic color from author name
    color_idx = int(hashlib.md5(author_name.lower().encode()).hexdigest(), 16) % len(COVER_COLORS)
    bg_color = COVER_COLORS[color_idx]

    img = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    white = (255, 255, 255)
    white_dim = (255, 255, 255, 180)
    max_text_w = W - pad * 2

    # --- Top accent bar ---
    draw.rectangle([0, 0, W, 6], fill=(226, 106, 44))

    # --- Thin border frame inset ---
    draw.rectangle([pad - 6, pad, W - pad + 6, H - pad],
                   outline=white, width=1)

    # --- Author name (top, left-aligned, uppercase, small) ---
    author_text = author_name.upper()
    for asize in [13, 12, 11, 10]:
        author_font = _get_font('sans', asize)
        author_lines = _wrap_text(draw, author_text, author_font, max_text_w - 20)
        line_h = asize + 4
        total_h = len(author_lines) * line_h
        if len(author_lines) <= 2:
            break

    author_y = pad + 16
    for line in author_lines:
        draw.text((pad + 10, author_y), line, fill=white, font=author_font)
        author_y += line_h

    # --- Thin rule below author ---
    rule_y = author_y + 10
    draw.line([(pad + 10, rule_y), (W - pad - 10, rule_y)], fill=white, width=1)

    # --- Title (center of cover, left-aligned, large) ---
    title_area_top = rule_y + 20
    title_area_bottom = H - pad - 80
    title_area_h = title_area_bottom - title_area_top

    for tsize in [36, 32, 28, 24, 22, 20, 18, 16]:
        title_font = _get_font('sans', tsize)
        title_lines = _wrap_text(draw, title, title_font, max_text_w - 20)
        line_h = tsize + 8
        total_h = len(title_lines) * line_h
        if total_h <= title_area_h and len(title_lines) <= 6:
            break

    title_y = title_area_top + (title_area_h - total_h) // 2
    for line in title_lines:
        draw.text((pad + 10, title_y), line, fill=white, font=title_font)
        title_y += line_h

    # --- Bottom: thin rule + "BOOKARR" label ---
    bot_rule_y = H - pad - 50
    draw.line([(pad + 10, bot_rule_y), (W - pad - 10, bot_rule_y)], fill=white, width=1)

    # "BOOKARR" centered below rule
    label_font = _get_font('sans', 11)
    label = "BOOKARR"
    bbox = draw.textbbox((0, 0), label, font=label_font)
    lw = bbox[2] - bbox[0]
    draw.text(((W - lw) // 2, bot_rule_y + 12), label, fill=white, font=label_font)

    img.save(cache_path, 'PNG')
    return cache_path

# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------

def render_template(name, **kwargs):
    """Simple template renderer with variable substitution."""
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path) as f:
        html = f.read()
    for key, value in kwargs.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html

def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, default=str).encode())

def html_response(handler, html, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(html.encode())

class BookarrHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        path = self.path.split("?")[0]
        params = {}
        if "?" in self.path:
            params = dict(urllib.parse.parse_qsl(self.path.split("?")[1]))

        # --- API endpoints ---
        if path == "/api/stats":
            self._api_stats()
        elif path == "/api/books":
            self._api_books_list(params)
        elif path == "/api/authors":
            self._api_authors_list()
        elif path.startswith("/api/author/") and path.endswith("/books"):
            author_id = int(path.split("/")[3])
            self._api_author_books(author_id)
        elif path.startswith("/api/author/") and path.endswith("/similar"):
            author_id = int(path.split("/")[3])
            self._api_author_similar(author_id)
        elif path.startswith("/api/author/"):
            author_id = int(path.split("/")[3])
            self._api_author_detail(author_id)
        elif path == "/api/wanted":
            self._api_wanted()
        elif path == "/api/activity":
            self._api_activity()
        elif path == "/api/search":
            self._api_search(params.get("q", ""), params.get("type", "indexer"), params.get("book_id"))
        elif path == "/api/search/author":
            self._api_search_author_ol(params.get("q", ""))
        elif path == "/api/search/book":
            self._api_search_book_ol(params.get("q", ""))
        elif path.startswith("/api/book/") and path.count("/") == 3:
            book_id = int(path.split("/")[3])
            self._api_book_detail(book_id)
        elif path == "/api/search/progress":
            json_response(self, search_engine.get_progress())
        elif path == "/api/indexer/health":
            self._api_indexer_health()
        elif path == "/api/seed/categories":
            self._api_seed_categories()
        elif path == "/api/settings":
            self._api_get_settings()
        elif path == "/api/browse":
            self._api_browse(params.get("path", "/"))
        elif path.startswith("/api/cover/gen/"):
            book_id = int(path.split("/")[-1])
            self._api_cover_generated(book_id)
        elif path.startswith("/api/cover/"):
            cover_id = path.split("/")[-1]
            self._api_cover(cover_id, params.get("size", "M"))
        # --- Test connection endpoints ---
        elif path == "/api/test/prowlarr":
            ok, msg = test_prowlarr()
            json_response(self, {"success": ok, "message": msg})
        elif path == "/api/test/nzbget":
            ok, msg = test_nzbget()
            json_response(self, {"success": ok, "message": msg})
        elif path == "/api/test/torrent":
            ok, msg = test_torrent_client()
            json_response(self, {"success": ok, "message": msg})
        # --- Source folders API ---
        elif path == "/api/source-folders":
            self._api_source_folders_list()
        # --- HTML pages ---
        elif path in ("/", "/index"):
            self._page_index()
        elif path == "/favicon.ico":
            self._serve_static("/static/favicon.ico")
        elif path.startswith("/static/"):
            self._serve_static(path)
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        path = self.path

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == "/api/author/add":
            self._api_add_author(data)
        elif path == "/api/author/add-ol":
            self._api_add_author_ol(data)
        elif path == "/api/book/add":
            self._api_add_book(data)
        elif path.startswith("/api/author/") and path.endswith("/toggle"):
            author_id = int(path.split("/")[3])
            self._api_toggle_author(author_id)
        elif path.startswith("/api/author/") and path.endswith("/delete"):
            author_id = int(path.split("/")[3])
            self._api_delete_author(author_id)
        elif path.startswith("/api/book/") and path.endswith("/want"):
            book_id = int(path.split("/")[3])
            self._api_want_book(book_id)
        elif path.startswith("/api/book/") and path.endswith("/unwant"):
            book_id = int(path.split("/")[3])
            self._api_unwant_book(book_id)
        elif path.startswith("/api/book/") and path.endswith("/delete"):
            book_id = int(path.split("/")[3])
            self._api_delete_book(book_id)
        elif path == "/api/book/want-all":
            self._api_want_all(data)
        elif path == "/api/author/add-audiobooks":
            self._api_add_audiobooks(data)
        elif path == "/api/audiobooks/check-all":
            threading.Thread(target=_check_all_audiobooks_background, daemon=True).start()
            json_response(self, {"status": "started", "message": "Background audiobook check started for all authors"})
        elif path.startswith("/api/download/") and path.endswith("/retry"):
            download_id = int(path.split("/")[3])
            self._api_retry_download(download_id)
        elif path == "/api/grab":
            self._api_grab(data)
        elif path == "/api/search/now":
            self._api_search_now()
        elif path == "/api/scan":
            self._api_scan_library()
        elif path == "/api/settings":
            self._api_update_settings(data)
        elif path == "/api/seed":
            self._api_seed(data)
        elif path == "/api/seed/trending":
            self._api_seed_trending()
        elif path == "/api/source-folders":
            self._api_source_folders_add(data)
        elif path == "/api/source-folders/delete":
            self._api_source_folders_delete(data)
        elif path == "/api/source-folders/scan":
            self._api_source_folders_scan()
        elif path == "/api/reset":
            self._api_reset()
        elif path == "/api/cleanup":
            self._api_cleanup()
        elif path == "/api/backfill-counts":
            threading.Thread(target=backfill_author_counts, daemon=True).start()
            json_response(self, {"status": "backfill started"})
        else:
            self.send_error(404)

    # --- API implementations ---

    def _api_stats(self):
        conn = get_db()
        stats = {
            "authors": conn.execute("SELECT COUNT(*) c FROM authors").fetchone()["c"],
            "authors_monitored": conn.execute("SELECT COUNT(*) c FROM authors WHERE monitored=1").fetchone()["c"],
            "books": conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"],
            "ebooks": conn.execute("SELECT COUNT(*) c FROM books WHERE book_type='ebook'").fetchone()["c"],
            "audiobooks": conn.execute("SELECT COUNT(*) c FROM books WHERE book_type='audiobook'").fetchone()["c"],
            "wanted": conn.execute("SELECT COUNT(*) c FROM books WHERE status='wanted'").fetchone()["c"],
            "downloading": conn.execute("SELECT COUNT(*) c FROM books WHERE status='downloading'").fetchone()["c"],
            "downloaded": conn.execute("SELECT COUNT(*) c FROM books WHERE status='downloaded'").fetchone()["c"],
            "missing": conn.execute("SELECT COUNT(*) c FROM books WHERE status='missing'").fetchone()["c"],
        }
        conn.close()
        json_response(self, stats)

    def _api_books_list(self, params):
        status = params.get("status", "")
        exclude_status = params.get("exclude_status", "")
        search = params.get("q", "")
        book_type = params.get("type", "")
        page = int(params.get("page", "1"))
        per_page = int(params.get("per_page", "100"))
        offset = (page - 1) * per_page

        conn = get_db()
        where = []
        args = []
        if status:
            where.append("b.status = ?")
            args.append(status)
        if exclude_status:
            where.append("b.status != ?")
            args.append(exclude_status)
        if book_type:
            where.append("b.book_type = ?")
            args.append(book_type)
        if search:
            where.append("(b.title LIKE ? OR a.name LIKE ?)")
            args.extend([f"%{search}%", f"%{search}%"])
        category = params.get("category", "")
        if category == "novel":
            where.append("b.author_count = 1")
        elif category == "anthology":
            where.append("b.author_count > 1")

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        total = conn.execute(
            f"SELECT COUNT(*) c FROM books b JOIN authors a ON b.author_id = a.id{where_sql}", args
        ).fetchone()["c"]

        rows = conn.execute(
            f"SELECT b.*, a.name as author_name FROM books b "
            f"JOIN authors a ON b.author_id = a.id{where_sql} "
            f"ORDER BY a.name, b.year, b.title LIMIT ? OFFSET ?",
            args + [per_page, offset]
        ).fetchall()
        conn.close()
        json_response(self, {"total": total, "page": page, "per_page": per_page, "books": [dict(r) for r in rows]})

    def _api_authors_list(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT a.*, COUNT(b.id) as book_count,
                   SUM(CASE WHEN b.status='downloaded' THEN 1 ELSE 0 END) as downloaded_count,
                   SUM(CASE WHEN b.status='wanted' THEN 1 ELSE 0 END) as wanted_count,
                   SUM(CASE WHEN b.book_type='ebook' THEN 1 ELSE 0 END) as ebook_count,
                   SUM(CASE WHEN b.book_type='audiobook' THEN 1 ELSE 0 END) as audiobook_count
            FROM authors a LEFT JOIN books b ON b.author_id = a.id
            GROUP BY a.id ORDER BY a.name
        """).fetchall()
        authors = [dict(r) for r in rows]
        conn.close()
        json_response(self, authors)

    def _api_author_detail(self, author_id):
        conn = get_db()
        author = conn.execute("SELECT * FROM authors WHERE id=?", (author_id,)).fetchone()
        if not author:
            json_response(self, {"error": "not found"}, 404)
            return
        json_response(self, dict(author))

    def _api_author_books(self, author_id):
        conn = get_db()
        rows = conn.execute("SELECT * FROM books WHERE author_id=? ORDER BY year, title", (author_id,)).fetchall()
        books = [dict(r) for r in rows]
        conn.close()
        json_response(self, books)

    def _api_author_similar(self, author_id):
        """Return similar authors: same seed_source + cross-category matches."""
        conn = get_db()
        author = conn.execute("SELECT * FROM authors WHERE id=?", (author_id,)).fetchone()
        if not author:
            json_response(self, [])
            conn.close()
            return

        similar = {}  # id -> {author dict, reasons: []}

        # Tier 1: same seed_source (if not manual)
        if author["seed_source"] and author["seed_source"] != "manual":
            rows = conn.execute(
                "SELECT id, name, seed_source FROM authors WHERE seed_source=? AND id!=? ORDER BY name",
                (author["seed_source"], author_id)
            ).fetchall()
            source_label = SEED_CATEGORIES.get(author["seed_source"], {}).get("name", author["seed_source"])
            for r in rows:
                similar[r["id"]] = {"id": r["id"], "name": r["name"], "seed_source": r["seed_source"],
                                    "reasons": [source_label]}

        # Tier 2: cross-category — check all SEED_CATEGORIES for this author's name
        author_lower = author["name"].lower().strip()
        matching_cats = []
        for key, cat in SEED_CATEGORIES.items():
            for name in cat["authors"]:
                if name.lower().strip() == author_lower:
                    matching_cats.append(key)
                    break

        if matching_cats:
            for cat_key in matching_cats:
                cat_label = SEED_CATEGORIES[cat_key]["name"]
                rows = conn.execute(
                    "SELECT id, name, seed_source FROM authors WHERE seed_source=? AND id!=?",
                    (cat_key, author_id)
                ).fetchall()
                for r in rows:
                    if r["id"] in similar:
                        if cat_label not in similar[r["id"]]["reasons"]:
                            similar[r["id"]]["reasons"].append(cat_label)
                    else:
                        similar[r["id"]] = {"id": r["id"], "name": r["name"], "seed_source": r["seed_source"],
                                            "reasons": [cat_label]}

        conn.close()
        result = list(similar.values())[:5]
        json_response(self, result)

    def _api_book_detail(self, book_id):
        conn = get_db()
        book = conn.execute("""
            SELECT b.*, a.name as author_name, a.id as author_id, a.ol_key as author_ol_key
            FROM books b JOIN authors a ON b.author_id = a.id WHERE b.id=?
        """, (book_id,)).fetchone()
        if not book:
            json_response(self, {"error": "not found"}, 404)
            conn.close()
            return

        # Download history for this book
        downloads = conn.execute("""
            SELECT * FROM downloads WHERE book_id=? ORDER BY started_at DESC
        """, (book_id,)).fetchall()

        # Other books by same author (limit 20, exclude current)
        other_books = conn.execute("""
            SELECT id, title, book_type, status, cover_id, year
            FROM books WHERE author_id=? AND id!=? ORDER BY year, title LIMIT 20
        """, (book["author_id"], book_id)).fetchall()

        # Sibling format (ebook <-> audiobook)
        sibling = conn.execute("""
            SELECT id, book_type, status FROM books
            WHERE author_id=? AND title=? AND id!=?
        """, (book["author_id"], book["title"], book_id)).fetchone()

        conn.close()
        result = dict(book)
        result["downloads"] = [dict(d) for d in downloads]
        result["other_books"] = [dict(b) for b in other_books]
        result["sibling"] = dict(sibling) if sibling else None
        json_response(self, result)

    def _api_delete_book(self, book_id):
        conn = get_db()
        # Get author_id before deleting so we can redirect
        book = conn.execute("SELECT author_id FROM books WHERE id=?", (book_id,)).fetchone()
        author_id = book["author_id"] if book else None
        conn.execute("DELETE FROM downloads WHERE book_id=?", (book_id,))
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        # Clean up generated cover cache
        cache_path = os.path.join(COVER_CACHE_DIR, f"{book_id}.png")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except OSError:
                pass
        conn.commit()
        # Clean up orphaned authors
        conn.execute("DELETE FROM authors WHERE id NOT IN (SELECT DISTINCT author_id FROM books)")
        conn.commit()
        conn.close()
        json_response(self, {"status": "deleted", "author_id": author_id})

    def _api_wanted(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT b.*, a.name as author_name
            FROM books b JOIN authors a ON b.author_id = a.id
            WHERE b.status IN ('wanted', 'downloading')
            ORDER BY b.status DESC, b.added_at DESC
        """).fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    def _api_activity(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT d.id, d.book_id, d.nzbget_id, d.nzb_name, d.indexer,
                   d.size_bytes, d.status, d.started_at, d.completed_at,
                   d.download_client, d.torrent_hash, d.error_detail,
                   b.title as book_title, b.book_type, a.name as author_name
            FROM downloads d
            JOIN books b ON d.book_id = b.id
            JOIN authors a ON b.author_id = a.id
            ORDER BY d.started_at DESC LIMIT 50
        """).fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    def _api_indexer_health(self):
        """Return per-indexer health stats from recent queries."""
        conn = get_db()
        # Check if table exists (first run before restart)
        try:
            rows = conn.execute("""
                SELECT indexer_id,
                       COUNT(*) as total_queries,
                       SUM(success) as successes,
                       COUNT(*) - SUM(success) as failures,
                       ROUND(AVG(result_count), 1) as avg_results,
                       MAX(queried_at) as last_query,
                       SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as failure_rate
                FROM indexer_stats
                WHERE queried_at > datetime('now', '-7 days')
                GROUP BY indexer_id
                ORDER BY indexer_id
            """).fetchall()
            # Also get recent errors per indexer
            recent_errors = conn.execute("""
                SELECT indexer_id, error_msg, queried_at
                FROM indexer_stats
                WHERE success=0 AND queried_at > datetime('now', '-24 hours')
                ORDER BY queried_at DESC LIMIT 20
            """).fetchall()
        except Exception:
            rows = []
            recent_errors = []
        # Get last background search info
        last_search = conn.execute(
            "SELECT * FROM search_log ORDER BY searched_at DESC LIMIT 1"
        ).fetchone()
        search_interval = int(get_setting("search_interval", "900"))
        conn.close()
        json_response(self, {
            "indexers": [dict(r) for r in rows],
            "recent_errors": [dict(r) for r in recent_errors],
            "last_search": dict(last_search) if last_search else None,
            "search_interval_min": search_interval // 60,
        })

    def _api_search(self, query, search_type, book_id=None):
        if not query:
            json_response(self, [])
            return
        results = search_all_indexers(query, CAT_BOOKS_ALL)

        # If book_id provided, score results against the book
        if book_id:
            try:
                conn = get_db()
                book = conn.execute("""
                    SELECT b.title, b.book_type, a.name as author_name
                    FROM books b JOIN authors a ON b.author_id = a.id WHERE b.id=?
                """, (int(book_id),)).fetchone()
                conn.close()
                if book:
                    scored_results = []
                    for r in results:
                        s = score_result(r, book["title"], book["author_name"], book["book_type"])
                        if s >= 0:  # Filter out hard rejects
                            r["score"] = s
                            scored_results.append(r)
                    scored_results.sort(key=lambda r: r["score"], reverse=True)
                    json_response(self, scored_results[:100])
                    return
            except Exception:
                pass

        # Default: sort by size descending
        results.sort(key=lambda r: r["size"], reverse=True)
        json_response(self, results[:100])

    def _api_search_author_ol(self, query):
        if not query:
            json_response(self, [])
            return
        results = search_author_ol(query)
        json_response(self, results)

    def _api_search_book_ol(self, query):
        """Search Open Library for books."""
        if not query:
            json_response(self, [])
            return
        results = search_books_ol(query)
        json_response(self, results)

    def _api_add_book(self, data):
        """Add a single book (and its author if needed) from Open Library search result."""
        title = data.get("title", "").strip()
        author_name = data.get("author_name", "").strip()
        author_key = data.get("author_key", "")
        ol_key = data.get("ol_key", "")
        year = data.get("year")
        cover_id = data.get("cover_id")
        book_type = data.get("book_type", "ebook")

        if not title:
            json_response(self, {"error": "title required"}, 400)
            return

        conn = get_db()

        # Find or create author
        author_id = None
        if author_name:
            row = conn.execute("SELECT id FROM authors WHERE name=?", (author_name,)).fetchone()
            if row:
                author_id = row["id"]
            else:
                bio = ""
                if author_key:
                    try:
                        info = get_author_info(author_key)
                        bio = info.get("bio", "")
                    except Exception:
                        pass
                conn.execute("INSERT OR IGNORE INTO authors (name, ol_key, bio) VALUES (?, ?, ?)",
                             (author_name, author_key, bio))
                conn.commit()
                row = conn.execute("SELECT id FROM authors WHERE name=?", (author_name,)).fetchone()
                author_id = row["id"] if row else None

        if not author_id:
            json_response(self, {"error": "could not create author"}, 400)
            conn.close()
            return

        # Add the book (both ebook and audiobook if requested)
        types = [book_type] if book_type != "both" else ["ebook", "audiobook"]
        added = 0
        for bt in types:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO books "
                    "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                    "VALUES (?, ?, ?, ?, ?, 'wanted', ?, ?)",
                    (author_id, title, ol_key, year, cover_id, bt,
                     data.get("author_count", 1))
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    added += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()
        json_response(self, {"status": "added", "added": added, "author_id": author_id})

    def _api_add_author(self, data):
        name = data.get("name", "").strip()
        if not name:
            json_response(self, {"error": "name required"}, 400)
            return

        conn = get_db()
        # Check if already exists
        existing = conn.execute("SELECT id FROM authors WHERE name=?", (name,)).fetchone()
        if existing:
            json_response(self, {"id": existing["id"], "status": "exists"})
            conn.close()
            return

        # Search Open Library
        ol_results = search_author_ol(name)
        ol_key = ""
        bio = ""
        if ol_results:
            best = ol_results[0]
            ol_key = best["key"]
            info = get_author_info(ol_key)
            bio = info.get("bio", "")
            # Use the canonical name from OL if close enough
            if best["name"].lower().replace(" ", "") == name.lower().replace(" ", ""):
                name = best["name"]

        conn.execute("INSERT INTO authors (name, ol_key, bio, seed_source) VALUES (?, ?, ?, 'manual')",
                     (name, ol_key, bio))
        author_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Fetch works — filter, dedup, add ebook entries (audiobooks checked in background)
        books_added = 0
        lang_pref = get_setting("language", "english")
        if ol_key:
            works = get_author_works(ol_key, limit=200)
            clean_works = _filter_and_dedup_works(works, lang_pref)
            for w in clean_works:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO books "
                        "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                        "VALUES (?, ?, ?, ?, ?, 'missing', 'ebook', ?)",
                        (author_id, w["title"], w["key"], w["year"],
                         w.get("cover_id"), w.get("author_count", 1))
                    )
                    books_added += 1
                except sqlite3.IntegrityError:
                    pass

        conn.commit()
        conn.close()
        json_response(self, {"id": author_id, "status": "added", "books": books_added})

        # Check for audiobooks in background thread
        threading.Thread(
            target=_check_audiobooks_background,
            args=(author_id, name),
            daemon=True
        ).start()

    def _api_add_author_ol(self, data):
        """Add author by Open Library key."""
        ol_key = data.get("ol_key", "")
        if not ol_key:
            json_response(self, {"error": "ol_key required"}, 400)
            return

        info = get_author_info(ol_key)
        name = info.get("name") or data.get("name", "Unknown")

        conn = get_db()
        existing = conn.execute("SELECT id FROM authors WHERE name=?", (name,)).fetchone()
        if existing:
            json_response(self, {"id": existing["id"], "status": "exists"})
            conn.close()
            return

        conn.execute("INSERT INTO authors (name, ol_key, bio, seed_source) VALUES (?, ?, ?, 'manual')",
                     (name, ol_key, info.get("bio", "")))
        author_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        works = get_author_works(ol_key, limit=200)
        lang_pref = get_setting("language", "english")
        clean_works = _filter_and_dedup_works(works, lang_pref)
        books_added = 0
        for w in clean_works:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO books "
                    "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                    "VALUES (?, ?, ?, ?, ?, 'missing', 'ebook', ?)",
                    (author_id, w["title"], w["key"], w["year"],
                     w.get("cover_id"), w.get("author_count", 1))
                )
                books_added += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()
        json_response(self, {"id": author_id, "status": "added", "books": books_added})

        # Check for audiobooks in background thread
        threading.Thread(
            target=_check_audiobooks_background,
            args=(author_id, name),
            daemon=True
        ).start()

    def _api_toggle_author(self, author_id):
        conn = get_db()
        conn.execute("UPDATE authors SET monitored = NOT monitored WHERE id=?", (author_id,))
        conn.commit()
        row = conn.execute("SELECT monitored FROM authors WHERE id=?", (author_id,)).fetchone()
        conn.close()
        json_response(self, {"monitored": bool(row["monitored"]) if row else False})

    def _api_delete_author(self, author_id):
        conn = get_db()
        conn.execute("DELETE FROM books WHERE author_id=?", (author_id,))
        conn.execute("DELETE FROM authors WHERE id=?", (author_id,))
        conn.commit()
        conn.close()
        json_response(self, {"status": "deleted"})

    def _api_want_book(self, book_id):
        conn = get_db()
        conn.execute("UPDATE books SET status='wanted' WHERE id=? AND status='missing'", (book_id,))
        wanted = 1

        # Check want_format setting — also want the sibling format if applicable
        sibling_id = None
        pref = get_setting("want_format", "both")
        if pref == "both":
            book = conn.execute(
                "SELECT author_id, title, book_type FROM books WHERE id=?", (book_id,)
            ).fetchone()
            if book:
                sibling_type = "audiobook" if book["book_type"] == "ebook" else "ebook"
                conn.execute(
                    "UPDATE books SET status='wanted' WHERE author_id=? AND title=? "
                    "AND book_type=? AND status='missing'",
                    (book["author_id"], book["title"], sibling_type)
                )
                wanted += conn.execute("SELECT changes()").fetchone()[0]
                sib = conn.execute(
                    "SELECT id FROM books WHERE author_id=? AND title=? AND book_type=? AND status='wanted'",
                    (book["author_id"], book["title"], sibling_type)
                ).fetchone()
                if sib:
                    sibling_id = sib["id"]

        conn.commit()
        conn.close()
        json_response(self, {"status": "wanted", "wanted": wanted})

        # Trigger immediate search in background
        threading.Thread(target=search_engine.search_single_book, args=(book_id,), daemon=True).start()
        if sibling_id:
            threading.Thread(target=search_engine.search_single_book, args=(sibling_id,), daemon=True).start()

    def _api_unwant_book(self, book_id):
        conn = get_db()
        conn.execute("UPDATE books SET status='missing' WHERE id=? AND status='wanted'", (book_id,))
        conn.commit()
        conn.close()
        json_response(self, {"status": "missing"})

    def _api_want_all(self, data):
        author_id = data.get("author_id")
        book_type = data.get("book_type", "")  # "" = all types, "ebook", "audiobook"
        conn = get_db()
        if author_id:
            if book_type:
                conn.execute("UPDATE books SET status='wanted' WHERE author_id=? AND status='missing' AND book_type=?",
                             (author_id, book_type))
            else:
                conn.execute("UPDATE books SET status='wanted' WHERE author_id=? AND status='missing'",
                             (author_id,))
        conn.commit()
        count = conn.execute("SELECT changes()").fetchone()[0]
        conn.close()
        json_response(self, {"wanted": count})

        # Trigger background search for all wanted books
        if count > 0:
            threading.Thread(target=search_engine._search_wanted, daemon=True).start()

    def _api_add_audiobooks(self, data):
        """Create audiobook entries for an author's books, checking Open Library + Audible."""
        author_id = data.get("author_id")
        if not author_id:
            json_response(self, {"error": "author_id required"}, 400)
            return
        conn = get_db()
        author = conn.execute("SELECT name FROM authors WHERE id=?", (author_id,)).fetchone()
        author_name = author["name"] if author else ""
        ebooks = conn.execute(
            "SELECT title, ol_key, year, cover_id, author_count FROM books WHERE author_id=? AND book_type='ebook'",
            (author_id,)
        ).fetchall()
        added = 0
        checked = 0
        for eb in ebooks:
            # Skip if audiobook entry already exists
            existing = conn.execute(
                "SELECT id FROM books WHERE author_id=? AND title=? AND book_type='audiobook'",
                (author_id, eb["title"])
            ).fetchone()
            if existing:
                continue
            checked += 1
            if check_audiobook_exists(author_name, eb["title"], ol_key=eb["ol_key"]):
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO books "
                        "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                        "VALUES (?, ?, ?, ?, ?, 'missing', 'audiobook', ?)",
                        (author_id, eb["title"], eb["ol_key"], eb["year"],
                         eb["cover_id"], eb["author_count"] or 1)
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    pass
            time.sleep(0.3)
        conn.commit()
        conn.close()
        json_response(self, {"added": added, "checked": checked})

    def _api_retry_download(self, download_id):
        """Retry a failed download by resetting the book to wanted and searching again."""
        conn = get_db()
        dl = conn.execute("""
            SELECT d.id, d.book_id FROM downloads d WHERE d.id=?
        """, (download_id,)).fetchone()
        if not dl:
            conn.close()
            json_response(self, {"error": "download not found"}, 404)
            return
        book_id = dl["book_id"]
        conn.execute("UPDATE books SET status='wanted' WHERE id=?", (book_id,))
        conn.commit()
        conn.close()
        json_response(self, {"status": "retrying", "book_id": book_id})
        # Trigger immediate search in background
        threading.Thread(target=search_engine.search_single_book, args=(book_id,), daemon=True).start()

    def _api_grab(self, data):
        """Manually grab a search result for a book."""
        link = data.get("link", "")
        book_id = data.get("book_id")
        title = data.get("title", "Manual grab")
        protocol = data.get("protocol", "usenet")
        size_bytes = data.get("size", 0)

        if not link:
            json_response(self, {"error": "link required"}, 400)
            return

        if protocol == "torrent":
            cat = get_setting("torrent_category", "bookarr")
            torrent_result = send_to_torrent_client(link, title, cat)
            if torrent_result:
                torrent_hash = torrent_result if torrent_result != "pending" else None
                conn = get_db()
                if book_id:
                    conn.execute("UPDATE books SET status='downloading' WHERE id=?", (book_id,))
                    conn.execute(
                        "INSERT INTO downloads (book_id, nzb_name, size_bytes, status, download_client, torrent_hash) "
                        "VALUES (?, ?, ?, 'downloading', 'torrent', ?)",
                        (book_id, title, size_bytes, torrent_hash)
                    )
                conn.commit()
                conn.close()
                json_response(self, {"status": "ok", "client": "torrent"})
            else:
                json_response(self, {"error": "Failed to send to torrent client"}, 500)
        else:
            nzbget_id = send_to_nzbget(link, title)
            if nzbget_id and nzbget_id > 0:
                conn = get_db()
                if book_id:
                    conn.execute("UPDATE books SET status='downloading' WHERE id=?", (book_id,))
                    conn.execute(
                        "INSERT INTO downloads (book_id, nzbget_id, nzb_name, size_bytes, status, download_client) "
                        "VALUES (?, ?, ?, ?, 'downloading', 'nzbget')",
                        (book_id, nzbget_id, title, size_bytes)
                    )
                conn.commit()
                conn.close()
                json_response(self, {"nzbget_id": nzbget_id, "client": "nzbget"})
            else:
                json_response(self, {"error": "Failed to send to NZBGet"}, 500)

    def _api_search_now(self):
        """Trigger an immediate background search."""
        threading.Thread(target=search_engine._search_wanted, daemon=True).start()
        json_response(self, {"status": "search triggered"})

    def _api_get_settings(self):
        json_response(self, get_all_settings())

    def _api_update_settings(self, data):
        valid_keys = {
            # Library
            "language", "ebook_path", "audiobook_path", "want_format",
            "preferred_ebook_format",
            # Search
            "search_interval", "auto_search", "min_score",
            "max_size_mb_ebook", "max_size_mb_audiobook",
            # Prowlarr / Indexers
            "prowlarr_url", "prowlarr_api_key", "prowlarr_indexer_ids",
            "torrent_indexer_ids", "min_seeders",
            # NZBGet (Usenet)
            "nzbget_url", "nzbget_user", "nzbget_pass",
            # Torrent client
            "torrent_client", "torrent_host", "torrent_user", "torrent_pass",
            "torrent_category", "seed_ratio_limit", "seed_time_limit",
            # Notifications
            "pushover_token", "pushover_user",
        }
        updated = 0
        for key, value in data.items():
            if key in valid_keys:
                set_setting(key, value)
                updated += 1
        json_response(self, {"updated": updated, "settings": get_all_settings()})

    def _api_browse(self, browse_path):
        """List directories at a given path for the folder picker."""
        browse_path = os.path.expanduser(browse_path)
        if not os.path.isdir(browse_path):
            browse_path = os.path.dirname(browse_path)
            if not os.path.isdir(browse_path):
                browse_path = "/"
        dirs = []
        try:
            for entry in sorted(os.scandir(browse_path), key=lambda e: e.name.lower()):
                if entry.is_dir() and not entry.name.startswith('.'):
                    dirs.append(entry.name)
        except PermissionError:
            pass
        parent = os.path.dirname(browse_path) if browse_path != "/" else None
        json_response(self, {"path": browse_path, "parent": parent, "dirs": dirs})

    def _api_scan_library(self):
        matched = scan_library()
        json_response(self, {"matched": matched})

    def _api_seed_categories(self):
        """Return available seed categories with author counts."""
        categories = []
        for key, cat in SEED_CATEGORIES.items():
            categories.append({
                "key": key,
                "name": cat["name"],
                "description": cat.get("description", ""),
                "author_count": len(cat["authors"]),
            })
        json_response(self, categories)

    def _api_seed(self, data=None):
        """Seed database with authors from a specific category or all."""
        category = (data or {}).get("category", "")
        if category:
            cat = SEED_CATEGORIES.get(category)
            if not cat:
                json_response(self, {"error": f"Unknown category: {category}"}, 400)
                return
            threading.Thread(
                target=seed_authors,
                kwargs={"category_key": category},
                daemon=True
            ).start()
            json_response(self, {
                "status": "seeding started",
                "category": cat["name"],
                "author_count": len(cat["authors"]),
            })
        else:
            threading.Thread(target=seed_authors, daemon=True).start()
            total = sum(len(c["authors"]) for c in SEED_CATEGORIES.values())
            json_response(self, {"status": "seeding started", "author_count": total})

    def _api_seed_trending(self):
        """Seed with currently trending authors from Open Library."""
        def _do_trending():
            authors = fetch_trending_authors()
            if authors:
                print(f"[Trending] Found {len(authors)} trending authors")
                seed_authors(author_list=authors, category_key='trending')
            else:
                print("[Trending] No trending authors found")
        threading.Thread(target=_do_trending, daemon=True).start()
        json_response(self, {"status": "fetching trending authors..."})

    def _api_reset(self):
        """Clear all authors and books, keep settings."""
        conn = get_db()
        conn.execute("DELETE FROM downloads")
        conn.execute("DELETE FROM books")
        conn.execute("DELETE FROM authors")
        conn.execute("DELETE FROM search_log")
        conn.execute("DELETE FROM indexer_stats")
        conn.commit()
        conn.close()
        json_response(self, {"status": "reset complete"})

    def _api_cleanup(self):
        """Re-check all titles against current English filter and dedup. Remove junk and foreign titles."""
        conn = get_db()
        lang_pref = get_setting("language", "english")
        # Get all books grouped by author
        books = conn.execute("""
            SELECT b.id, b.title, b.book_type, b.author_id, b.status
            FROM books b ORDER BY b.author_id, b.title
        """).fetchall()

        removed_lang = 0
        removed_junk = 0
        removed_dedup = 0
        # Track seen normalized titles per (author_id, book_type) for dedup
        seen = {}

        for b in books:
            title = b["title"]
            key = (b["author_id"], b["book_type"])

            # Remove junk
            if is_junk_title(title):
                conn.execute("DELETE FROM books WHERE id=?", (b["id"],))
                removed_junk += 1
                continue

            # Remove non-English
            if lang_pref != "any" and not is_english_title(title):
                conn.execute("DELETE FROM books WHERE id=?", (b["id"],))
                removed_lang += 1
                continue

            # Dedup by normalized title
            norm = normalize_title(title)
            if key not in seen:
                seen[key] = set()
            if norm in seen[key]:
                # Keep the one with the earlier ID (original), delete this duplicate
                if b["status"] not in ("wanted", "downloading", "downloaded"):
                    conn.execute("DELETE FROM books WHERE id=?", (b["id"],))
                    removed_dedup += 1
                    continue
            seen[key].add(norm)

        # Remove authors with no remaining books
        conn.execute("DELETE FROM authors WHERE id NOT IN (SELECT DISTINCT author_id FROM books)")
        orphaned = conn.execute("SELECT changes()").fetchone()[0]

        conn.commit()
        conn.close()
        total = removed_lang + removed_junk + removed_dedup
        print(f"[Cleanup] Removed {total} books: {removed_lang} foreign, {removed_junk} junk, {removed_dedup} duplicates. {orphaned} orphan authors removed.")
        json_response(self, {
            "removed_foreign": removed_lang,
            "removed_junk": removed_junk,
            "removed_duplicates": removed_dedup,
            "removed_orphan_authors": orphaned,
            "total_removed": total,
        })

    def _api_source_folders_list(self):
        """List all source folders (auto save paths + custom ones)."""
        conn = get_db()
        custom = conn.execute("SELECT path, added_at FROM source_folders ORDER BY path").fetchall()
        conn.close()
        folders = [
            {"path": get_ebook_path(), "type": "auto", "label": "eBook Save Path"},
            {"path": get_audiobook_path(), "type": "auto", "label": "Audiobook Save Path"},
        ]
        for r in custom:
            folders.append({"path": r["path"], "type": "custom", "added_at": r["added_at"]})
        json_response(self, folders)

    def _api_source_folders_add(self, data):
        """Add a custom source folder."""
        path = data.get("path", "").strip()
        if not path:
            json_response(self, {"error": "path required"}, 400)
            return
        if not os.path.isdir(path):
            json_response(self, {"error": "directory not found"}, 400)
            return
        conn = get_db()
        try:
            conn.execute("INSERT INTO source_folders (path) VALUES (?)", (path,))
            conn.commit()
        except sqlite3.IntegrityError:
            json_response(self, {"error": "folder already added"}, 400)
            conn.close()
            return
        conn.close()
        json_response(self, {"status": "added", "path": path})

    def _api_source_folders_delete(self, data):
        """Remove a custom source folder."""
        path = data.get("path", "").strip()
        conn = get_db()
        conn.execute("DELETE FROM source_folders WHERE path=?", (path,))
        conn.commit()
        conn.close()
        json_response(self, {"status": "deleted"})

    def _api_source_folders_scan(self):
        """Trigger a scan of all source folders."""
        def _do_scan():
            matched = scan_library()
            print(f"[Scan] Source folder scan complete: {matched} files matched")
        threading.Thread(target=_do_scan, daemon=True).start()
        json_response(self, {"status": "scan started"})

    def _api_cover(self, cover_id, size="M"):
        """Proxy book cover from Open Library."""
        if not cover_id or cover_id == "None" or cover_id == "null":
            self.send_error(404)
            return
        size = size if size in ("S", "M", "L") else "M"
        url = f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Bookarr/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) < 100:  # Placeholder image
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
        except Exception:
            self.send_error(404)

    def _api_cover_generated(self, book_id):
        """Serve a generated vintage Penguin-style cover for books without cover art."""
        conn = get_db()
        book = conn.execute("""
            SELECT b.title, a.name as author_name
            FROM books b JOIN authors a ON b.author_id = a.id WHERE b.id=?
        """, (book_id,)).fetchone()
        conn.close()
        if not book:
            self.send_error(404)
            return
        try:
            cache_path = generate_vintage_cover(book_id, book["title"], book["author_name"])
            with open(cache_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=604800")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"[Cover] Error generating cover for book {book_id}: {e}")
            self.send_error(500)

    def _page_index(self):
        html = render_template("index.html")
        html_response(self, html)

    def _serve_static(self, path):
        rel = path.lstrip("/")
        # Covers are mutable (cached at runtime) — serve from data dir
        if rel.startswith("static/covers/"):
            fpath = os.path.join(_DATA_DIR, rel)
        else:
            # Bundled static assets (favicons, etc.)
            fpath = os.path.join(_BUNDLE_DIR, rel)
        if not os.path.isfile(fpath):
            self.send_error(404)
            return
        ext = os.path.splitext(fpath)[1]
        ct = {"css": "text/css", "js": "application/javascript", "svg": "image/svg+xml", "png": "image/png", "ico": "image/x-icon"}.get(ext.lstrip("."), "text/plain")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        with open(fpath, "rb") as f:
            self.wfile.write(f.read())


class ThreadedHTTPServer(HTTPServer):
    """Handle requests in separate threads."""
    allow_reuse_address = True
    def process_request(self, request, client_address):
        t = threading.Thread(target=self.finish_request, args=(request, client_address))
        t.daemon = True
        t.start()

# ---------------------------------------------------------------------------
# Author seed data
# ---------------------------------------------------------------------------

SEED_CATEGORIES = {
    "pulitzer_fiction": {
        "name": "Pulitzer Prize \u2014 Fiction",
        "description": "Pulitzer Prize for Fiction winners",
        "authors": [
            "Edith Wharton", "Willa Cather", "Margaret Wilson", "Edna Ferber",
            "Louis Bromfield", "Thornton Wilder", "Julia Peterkin", "Oliver La Farge",
            "Pearl S. Buck", "T. S. Stribling", "Caroline Miller", "Josephine Johnson",
            "Harold L. Davis", "Margaret Mitchell", "John Phillips Marquand",
            "Marjorie Kinnan Rawlings", "Ellen Glasgow", "Upton Sinclair",
            "Martin Flavin", "James A. Michener", "James Gould Cozzens",
            "Robert Lewis Taylor", "Allen Drury", "Harper Lee", "Edwin O'Connor",
            "Katherine Anne Porter", "Shirley Ann Grau", "Bernard Malamud",
            "William Styron", "N. Scott Momaday", "Jean Stafford", "Wallace Stegner",
            "Eudora Welty", "Michael Shaara", "Saul Bellow", "James Alan McPherson",
            "John Cheever", "John Kennedy Toole", "Norman Mailer", "John Updike",
            "Alice Walker", "William Kennedy", "Alison Lurie", "Larry McMurtry",
            "Peter Taylor", "Toni Morrison", "Anne Tyler", "Oscar Hijuelos",
            "Jane Smiley", "Robert Olen Butler", "E. Annie Proulx",
            "Carol Shields", "Richard Ford", "Steven Millhauser", "Philip Roth",
            "Michael Cunningham", "Jhumpa Lahiri", "Michael Chabon",
            "Richard Russo", "Jeffrey Eugenides", "Edward P. Jones",
            "Marilynne Robinson", "Geraldine Brooks", "Cormac McCarthy",
            "Junot Díaz", "Elizabeth Strout", "Paul Harding", "Jennifer Egan",
            "Andrew Sean Greer", "Richard Powers", "Anthony Doerr",
            "Colson Whitehead", "Donna Tartt", "Viet Thanh Nguyen",
            "Joshua Cohen", "Hernan Diaz", "Jayne Anne Phillips",
        ],
    },
    "pulitzer_drama": {
        "name": "Pulitzer Prize \u2014 Drama",
        "description": "Pulitzer Prize for Drama winners",
        "authors": [
            "Eugene O'Neill", "Tennessee Williams", "Arthur Miller",
            "Edward Albee", "August Wilson", "Tony Kushner",
            "David Auburn", "Nilo Cruz", "Doug Wright", "John Patrick Shanley",
            "David Lindsay-Abaire", "Tracy Letts", "Lynn Nottage",
            "Tom Kitt", "Bruce Norris", "Quiara Alegría Hudes",
            "Ayad Akhtar", "Annie Baker", "Stephen Adly Guirgis",
            "Lin-Manuel Miranda", "Paula Vogel", "Martyna Majok",
            "Jackie Sibblies Drury", "Michael R. Jackson", "James Ijames",
            "Sanaz Toossi",
        ],
    },
    "pulitzer_poetry": {
        "name": "Pulitzer Prize \u2014 Poetry",
        "description": "Pulitzer Prize for Poetry winners",
        "authors": [
            "Robert Frost", "Carl Sandburg", "Edna St. Vincent Millay",
            "Robert Penn Warren", "W. H. Auden", "Gwendolyn Brooks",
            "Marianne Moore", "Wallace Stevens", "Elizabeth Bishop",
            "Theodore Roethke", "Richard Wilbur", "Stanley Kunitz",
            "Anne Sexton", "Sylvia Plath", "James Wright",
            "Maxine Kumin", "Robert Lowell", "John Ashbery",
            "Howard Nemerov", "James Merrill", "Mary Oliver",
            "Charles Simic", "Rita Dove", "Yusef Komunyakaa",
            "Philip Levine", "Mark Strand", "Charles Wright",
            "Paul Muldoon", "Natasha Trethewey", "Tracy K. Smith",
            "Tyehimba Jess", "Frank Bidart", "Forrest Gander",
            "Jericho Brown", "Louise Glück", "Diane Seuss",
        ],
    },
    "pulitzer_nonfiction": {
        "name": "Pulitzer Prize \u2014 Nonfiction",
        "description": "Pulitzer Prize for General Nonfiction winners",
        "authors": [
            "David Halberstam", "Barbara Tuchman", "Robert Caro",
            "Annie Dillard", "E. O. Wilson", "Carl Sagan",
            "J. Anthony Lukas", "Richard Rhodes", "Neil Sheehan",
            "Doris Kearns Goodwin", "Garry Wills", "Lawrence Wright",
            "Jared Diamond", "Annette Gordon-Reed", "Isabel Wilkerson",
            "Siddhartha Mukherjee", "Stephen Greenblatt",
            "Matthew Desmond", "Jack E. Davis", "David W. Blight",
            "Greg Grandin", "Les Payne", "Winfred Rembert",
        ],
    },
    "nobel": {
        "name": "Nobel Prize in Literature",
        "description": "Nobel Prize in Literature winners",
        "authors": [
            "Sully Prudhomme", "Theodor Mommsen", "Bjørnstjerne Bjørnson", "Frédéric Mistral",
            "José Echegaray", "Henryk Sienkiewicz", "Giosuè Carducci", "Rudyard Kipling",
            "Rudolf Christoph Eucken", "Selma Lagerlöf", "Paul Heyse", "Maurice Maeterlinck",
            "Gerhart Hauptmann", "Rabindranath Tagore", "Romain Rolland", "Verner von Heidenstam",
            "Karl Adolph Gjellerup", "Henrik Pontoppidan", "Carl Spitteler",
            "Knut Hamsun", "Anatole France", "Jacinto Benavente", "William Butler Yeats",
            "Władysław Reymont", "George Bernard Shaw", "Grazia Deledda", "Henri Bergson",
            "Sigrid Undset", "Thomas Mann", "Sinclair Lewis", "Erik Axel Karlfeldt",
            "John Galsworthy", "Ivan Bunin", "Luigi Pirandello", "Eugene O'Neill",
            "Roger Martin du Gard", "Pearl S. Buck", "Frans Eemil Sillanpää",
            "Johannes V. Jensen", "Gabriela Mistral", "Hermann Hesse", "André Gide",
            "T. S. Eliot", "William Faulkner", "Bertrand Russell", "Pär Lagerkvist",
            "François Mauriac", "Winston Churchill", "Ernest Hemingway",
            "Halldór Laxness", "Juan Ramón Jiménez", "Albert Camus", "Boris Pasternak",
            "Salvatore Quasimodo", "Saint-John Perse", "Ivo Andrić", "John Steinbeck",
            "Giorgos Seferis", "Jean-Paul Sartre", "Mikhail Sholokhov",
            "Shmuel Yosef Agnon", "Nelly Sachs", "Miguel Ángel Asturias",
            "Yasunari Kawabata", "Samuel Beckett", "Aleksandr Solzhenitsyn",
            "Pablo Neruda", "Heinrich Böll", "Patrick White", "Eyvind Johnson",
            "Harry Martinson", "Eugenio Montale", "Saul Bellow", "Vicente Aleixandre",
            "Isaac Bashevis Singer", "Odysseas Elytis", "Czesław Miłosz",
            "Elias Canetti", "Gabriel García Márquez", "William Golding",
            "Jaroslav Seifert", "Claude Simon", "Wole Soyinka", "Joseph Brodsky",
            "Naguib Mahfouz", "Camilo José Cela", "Octavio Paz",
            "Nadine Gordimer", "Derek Walcott", "Toni Morrison", "Kenzaburō Ōe",
            "Seamus Heaney", "Wisława Szymborska", "Dario Fo", "José Saramago",
            "Günter Grass", "Gao Xingjian", "V. S. Naipaul", "Imre Kertész",
            "J. M. Coetzee", "Elfriede Jelinek", "Harold Pinter", "Orhan Pamuk",
            "Doris Lessing", "J. M. G. Le Clézio", "Herta Müller", "Mario Vargas Llosa",
            "Tomas Tranströmer", "Mo Yan", "Alice Munro", "Patrick Modiano",
            "Svetlana Alexievich", "Bob Dylan", "Kazuo Ishiguro", "Olga Tokarczuk",
            "Peter Handke", "Louise Glück", "Abdulrazak Gurnah", "Annie Ernaux",
            "Jon Fosse", "Han Kang",
        ],
    },
    "booker": {
        "name": "Booker Prize Winners",
        "description": "Man Booker / Booker Prize winning authors",
        "authors": [
            "P. H. Newby", "Bernice Rubens", "V. S. Naipaul", "John Berger",
            "J. G. Farrell", "Nadine Gordimer", "Stanley Middleton",
            "Ruth Prawer Jhabvala", "David Storey", "Paul Scott",
            "Iris Murdoch", "William Golding", "Thomas Keneally",
            "J. M. Coetzee", "Anita Brookner", "Keri Hulme", "Kingsley Amis",
            "Penelope Lively", "Peter Carey", "Kazuo Ishiguro", "A. S. Byatt",
            "Ben Okri", "Michael Ondaatje", "Barry Unsworth", "Roddy Doyle",
            "James Kelman", "Pat Barker", "Graham Swift", "Arundhati Roy",
            "Ian McEwan", "Margaret Atwood", "Yann Martel", "DBC Pierre",
            "Alan Hollinghurst", "John Banville", "Kiran Desai",
            "Anne Enright", "Aravind Adiga", "Hilary Mantel", "Howard Jacobson",
            "Julian Barnes", "Eleanor Catton", "Richard Flanagan",
            "Marlon James", "Paul Beatty", "George Saunders", "Anna Burns",
            "Bernardine Evaristo", "Douglas Stuart", "Damon Galgut",
            "Shehan Karunatilaka", "Paul Lynch", "Samantha Harvey",
        ],
    },
    "american_classics": {
        "name": "Classic American Authors",
        "description": "Essential American literature across genres",
        "authors": [
            "Mark Twain", "Herman Melville", "Edgar Allan Poe", "Walt Whitman",
            "Emily Dickinson", "Henry David Thoreau", "Ralph Waldo Emerson",
            "Nathaniel Hawthorne", "F. Scott Fitzgerald", "Henry James",
            "Edith Wharton", "Jack London", "Louisa May Alcott",
            "Langston Hughes", "Zora Neale Hurston", "James Baldwin",
            "Flannery O'Connor", "Raymond Carver", "Kurt Vonnegut",
            "Ray Bradbury", "Philip K. Dick", "Ursula K. Le Guin",
            "Octavia Butler", "Toni Morrison", "Maya Angelou",
            "Joan Didion", "Truman Capote", "J. D. Salinger",
            "Sylvia Plath", "Jack Kerouac", "Allen Ginsberg",
            "William S. Burroughs", "Thomas Pynchon", "Don DeLillo",
            "Saul Bellow", "Philip Roth", "John Updike", "Joyce Carol Oates",
            "Cormac McCarthy", "Larry McMurtry", "Raymond Chandler",
            "Dashiell Hammett", "Stephen King", "Anne Rice",
            "John Irving", "Tim O'Brien", "Denis Johnson",
            "David Foster Wallace", "George R. R. Martin",
            "Donna Tartt", "Marilynne Robinson", "Louise Erdrich",
            "Amy Tan", "Sandra Cisneros", "Maxine Hong Kingston",
            "James Ellroy", "Elmore Leonard", "Robert Penn Warren",
            "Thornton Wilder", "John Steinbeck", "Ernest Hemingway",
            "William Faulkner", "Scott Turow", "Michael Crichton",
            "Tom Clancy", "John Grisham", "Harper Lee",
            "Tennessee Williams", "Arthur Miller", "Eugene O'Neill",
            "Edward Albee", "Sam Shepard", "David Mamet",
            "August Wilson", "Lorraine Hansberry", "Suzan-Lori Parks",
            "Tony Kushner", "Annie Proulx", "Barbara Kingsolver",
            "Richard Wright", "Ralph Ellison", "James Fenimore Cooper",
            "Washington Irving", "O. Henry", "Ambrose Bierce",
            "Shirley Jackson", "Carson McCullers", "William Styron",
            "Gore Vidal", "Norman Mailer",
            "Ken Kesey", "Hunter S. Thompson", "Tom Wolfe",
            "Dorothy Parker", "Djuna Barnes", "Nella Larsen",
            "Theodore Dreiser", "Sinclair Lewis", "Upton Sinclair",
            "John Dos Passos", "Robert Frost", "Wallace Stevens",
            "e. e. cummings", "Ezra Pound", "T. S. Eliot",
        ],
    },
    "world_classics": {
        "name": "Classic World Authors",
        "description": "Essential world literature across cultures and centuries",
        "authors": [
            "Homer", "Virgil", "Dante Alighieri", "Geoffrey Chaucer",
            "Miguel de Cervantes", "William Shakespeare", "John Milton",
            "Molière", "Jonathan Swift", "Voltaire", "Johann Wolfgang von Goethe",
            "Jane Austen", "Lord Byron", "Percy Bysshe Shelley", "John Keats",
            "Mary Shelley", "Honoré de Balzac", "Victor Hugo", "Alexandre Dumas",
            "Charles Dickens", "Charlotte Brontë", "Emily Brontë",
            "George Eliot", "Fyodor Dostoevsky", "Leo Tolstoy",
            "Ivan Turgenev", "Anton Chekhov", "Gustave Flaubert",
            "Émile Zola", "Guy de Maupassant", "Marcel Proust",
            "Franz Kafka", "James Joyce", "Virginia Woolf",
            "D. H. Lawrence", "Joseph Conrad", "Oscar Wilde",
            "Thomas Hardy", "Robert Louis Stevenson", "Rudyard Kipling",
            "H. G. Wells", "Arthur Conan Doyle", "Bram Stoker",
            "Mikhail Bulgakov", "Vladimir Nabokov", "Jorge Luis Borges",
            "Julio Cortázar", "Gabriel García Márquez", "Pablo Neruda",
            "Octavio Paz", "Isabel Allende", "Carlos Fuentes",
            "Mario Vargas Llosa", "Roberto Bolaño", "Chinua Achebe",
            "Ngũgĩ wa Thiong'o", "Wole Soyinka", "Naguib Mahfouz",
            "Orhan Pamuk", "Haruki Murakami", "Yukio Mishima",
            "Murasaki Shikibu", "Rabindranath Tagore", "R. K. Narayan",
            "Salman Rushdie", "Arundhati Roy", "Khaled Hosseini",
            "Albert Camus", "Jean-Paul Sartre", "Simone de Beauvoir",
            "Samuel Beckett", "Bertolt Brecht", "Thomas Mann",
            "Hermann Hesse", "Günter Grass", "Patrick Süskind",
            "Italo Calvino", "Umberto Eco", "Elena Ferrante",
            "Nikolai Gogol", "Alexander Pushkin",
            "Anna Akhmatova", "Milan Kundera", "Bohumil Hrabal",
            "W. B. Yeats", "Seamus Heaney", "Derek Walcott",
            "Margaret Atwood", "Alice Munro", "Michael Ondaatje",
            "Kazuo Ishiguro", "Zadie Smith", "Chimamanda Ngozi Adichie",
            "Han Kang", "Mo Yan", "Lu Xun", "Banana Yoshimoto",
            "Rainer Maria Rilke", "Fernando Pessoa", "Wisława Szymborska",
        ],
    },
}

def _check_audiobooks_background(author_id, author_name):
    """Background thread: check Open Library + Audible for audiobooks and add entries."""
    # Step 1: Read ebook titles (quick DB read, then close)
    conn = get_db()
    ebooks = conn.execute(
        "SELECT title, ol_key, year, cover_id, author_count FROM books "
        "WHERE author_id=? AND book_type='ebook'", (author_id,)
    ).fetchall()
    existing_audio = set()
    for row in conn.execute(
        "SELECT title FROM books WHERE author_id=? AND book_type='audiobook'", (author_id,)
    ).fetchall():
        existing_audio.add(row["title"])
    conn.close()

    # Filter to only titles that need checking
    to_check = [eb for eb in ebooks if eb["title"] not in existing_audio]
    if not to_check:
        return

    # Step 2: Check Open Library + Audible concurrently
    def _check_one(eb):
        return (eb, check_audiobook_exists(author_name, eb["title"], ol_key=eb["ol_key"]))

    to_add = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for eb, found in pool.map(_check_one, to_check):
            if found:
                to_add.append(eb)

    # Step 3: Batch insert with retry (quick DB write, then close)
    if to_add:
        for attempt in range(5):
            try:
                conn = get_db()
                for eb in to_add:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO books "
                            "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                            "VALUES (?, ?, ?, ?, ?, 'missing', 'audiobook', ?)",
                            (author_id, eb["title"], eb["ol_key"], eb["year"],
                             eb["cover_id"], eb["author_count"] or 1)
                        )
                    except sqlite3.IntegrityError:
                        pass
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError:
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(2 + attempt * 2)
    print(f"[Audiobook] {author_name}: found {len(to_add)} audiobooks")

def _check_all_audiobooks_background():
    """Background thread: check Open Library + Audible for audiobooks across ALL authors missing audiobook entries."""
    conn = get_db()
    # Find authors who have ebooks but no audiobooks yet
    authors = conn.execute("""
        SELECT DISTINCT a.id, a.name FROM authors a
        JOIN books b ON b.author_id = a.id AND b.book_type = 'ebook'
        WHERE a.id NOT IN (
            SELECT DISTINCT author_id FROM books WHERE book_type = 'audiobook'
        )
        ORDER BY a.name
    """).fetchall()
    conn.close()
    # Wait for any active seed to finish before hammering the DB
    if _seed_lock.locked():
        print("[Audiobook] Waiting for seed to finish before checking audiobooks...")
    with _seed_lock:
        pass  # Just wait for it to be free
    print(f"[Audiobook] Bulk audiobook check: {len(authors)} authors without audiobooks")
    for i, author in enumerate(authors):
        # Pause if a seed starts while we're running
        if _seed_lock.locked():
            print("[Audiobook] Pausing audiobook check — seed in progress...")
            with _seed_lock:
                pass
        _check_audiobooks_background(author["id"], author["name"])
        if (i + 1) % 10 == 0:
            print(f"[Audiobook] Bulk progress: {i+1}/{len(authors)} authors checked")
    print(f"[Audiobook] Bulk audiobook check complete: {len(authors)} authors processed")

def _filter_and_dedup_works(works, lang_pref="english"):
    """Filter works for language, junk, and deduplicate by normalized title.
    Returns list of unique, clean works."""
    seen_titles = set()
    filtered = []
    for w in works:
        title = w["title"]
        # Skip junk entries (study guides, anthologies, textbooks, etc.)
        if is_junk_title(title):
            continue
        # Skip non-English titles if language preference is set
        if lang_pref != "any" and not is_english_title(title):
            continue
        # Deduplicate by normalized title
        norm = normalize_title(title)
        if norm in seen_titles or not norm:
            continue
        seen_titles.add(norm)
        filtered.append(w)
    return filtered

def backfill_author_counts():
    """Re-fetch author_count from Open Library for all authors."""
    conn = get_db()
    authors = conn.execute("SELECT id, name, ol_key FROM authors WHERE ol_key IS NOT NULL AND ol_key != ''").fetchall()
    conn.close()
    updated = 0
    for i, a in enumerate(authors):
        try:
            works = get_author_works(a["ol_key"], limit=200)
            work_counts = {}
            for w in works:
                work_counts[w["key"]] = w.get("author_count", 1)
            for attempt in range(5):
                try:
                    conn2 = get_db()
                    books = conn2.execute("SELECT id, ol_key FROM books WHERE author_id=?", (a["id"],)).fetchall()
                    for b in books:
                        ac = work_counts.get(b["ol_key"], 1)
                        if ac != 1:
                            conn2.execute("UPDATE books SET author_count=? WHERE id=?", (ac, b["id"]))
                            updated += 1
                    conn2.commit()
                    conn2.close()
                    break
                except Exception as e:
                    try:
                        conn2.close()
                    except Exception:
                        pass
                    if attempt < 4:
                        time.sleep(2 + attempt)
                    else:
                        print(f"[Backfill] DB error for {a['name']}: {e}")
        except Exception as e:
            print(f"[Backfill] Error for {a['name']}: {e}")
        if (i + 1) % 20 == 0:
            print(f"[Backfill] Progress: {i+1}/{len(authors)} ({updated} updated)")
        time.sleep(0.5)
    print(f"[Backfill] Done. Updated author_count on {updated} books.")

_seed_lock = threading.Lock()  # Held while seed_authors is actively writing to DB

def _find_seed_source(name):
    """Look up which SEED_CATEGORIES list an author belongs to. Returns category key or None."""
    lower = name.lower().strip()
    for key, cat in SEED_CATEGORIES.items():
        for author_name in cat["authors"]:
            if author_name.lower().strip() == lower:
                return key
    return None


def seed_authors(author_list=None, category_key=None):
    """Add authors to the database. Only creates audiobook entries when iTunes confirms they exist.

    Args:
        author_list: explicit list of author names to seed
        category_key: key into SEED_CATEGORIES to use
    """
    if author_list is None and category_key:
        cat = SEED_CATEGORIES.get(category_key)
        if not cat:
            print(f"[Seed] Unknown category: {category_key}")
            return
        author_list = cat["authors"]
        print(f"[Seed] Seeding category: {cat['name']}")
    elif author_list is None:
        # Default: seed all categories
        author_list = []
        for cat in SEED_CATEGORIES.values():
            author_list.extend(cat["authors"])

    # Deduplicate author names
    seen = set()
    unique = []
    for name in author_list:
        key = name.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(name)

    _seed_lock.acquire()
    print(f"[Seed] Adding {len(unique)} unique authors (ebooks only, audiobooks checked in background)...")
    conn = get_db()
    added = 0
    skipped = 0
    total_ebooks = 0

    for i, name in enumerate(unique):
        existing = conn.execute("SELECT id FROM authors WHERE name=?", (name,)).fetchone()
        if existing:
            skipped += 1
            continue

        # Look up on Open Library
        ol_key = ""
        bio = ""
        try:
            ol_results = search_author_ol(name)
            if ol_results:
                best = ol_results[0]
                ol_key = best["key"]
                info = get_author_info(ol_key)
                bio = info.get("bio", "")
        except Exception as e:
            print(f"[Seed] OL error for {name}: {e}")

        # Determine seed_source for this author
        author_source = category_key or _find_seed_source(name) or 'manual'

        try:
            conn.execute("INSERT OR IGNORE INTO authors (name, ol_key, bio, seed_source) VALUES (?, ?, ?, ?)",
                         (name, ol_key, bio, author_source))
            row = conn.execute("SELECT id FROM authors WHERE name=?", (name,)).fetchone()
            author_id = row["id"] if row else None
            if not author_id:
                skipped += 1
                continue

            # Fetch works, filter, and deduplicate — ebooks only
            lang_pref = get_setting("language", "english")
            if ol_key:
                works = get_author_works(ol_key, limit=100)
                clean_works = _filter_and_dedup_works(works, lang_pref)
                for w in clean_works:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO books "
                            "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                            "VALUES (?, ?, ?, ?, ?, 'missing', 'ebook', ?)",
                            (author_id, w["title"], w["key"], w["year"],
                             w.get("cover_id"), w.get("author_count", 1))
                        )
                        total_ebooks += 1
                    except sqlite3.IntegrityError:
                        pass

            added += 1
            # Commit after every author to avoid holding write lock too long
            conn.commit()
            if (i + 1) % 5 == 0:
                print(f"[Seed] Progress: {i+1}/{len(unique)} ({added} added, {skipped} skipped, "
                      f"{total_ebooks} ebooks)")
            time.sleep(0.5)  # Be polite to Open Library

        except sqlite3.IntegrityError:
            skipped += 1
        except sqlite3.OperationalError:
            # DB locked — retry this author after a pause
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(3)
            conn = get_db()
            try:
                conn.execute("INSERT OR IGNORE INTO authors (name, ol_key, bio, seed_source) VALUES (?, ?, ?, ?)",
                             (name, ol_key, bio, author_source))
                row = conn.execute("SELECT id FROM authors WHERE name=?", (name,)).fetchone()
                if row:
                    author_id = row["id"]
                    lang_pref = get_setting("language", "english")
                    if ol_key:
                        works = get_author_works(ol_key, limit=100)
                        clean_works = _filter_and_dedup_works(works, lang_pref)
                        for w in clean_works:
                            try:
                                conn.execute(
                                    "INSERT OR IGNORE INTO books "
                                    "(author_id, title, ol_key, year, cover_id, status, book_type, author_count) "
                                    "VALUES (?, ?, ?, ?, ?, 'missing', 'ebook', ?)",
                                    (author_id, w["title"], w["key"], w["year"],
                                     w.get("cover_id"), w.get("author_count", 1))
                                )
                                total_ebooks += 1
                            except sqlite3.IntegrityError:
                                pass
                    added += 1
                    conn.commit()
            except Exception as e2:
                print(f"[Seed] Retry also failed for {name}: {e2}")
        except Exception as e:
            print(f"[Seed] Error adding {name}: {e}")

    conn.commit()
    conn.close()
    _seed_lock.release()
    print(f"[Seed] Complete: {added} authors added, {skipped} skipped, "
          f"{total_ebooks} ebooks")

    # Kick off background audiobook checking after seeding finishes
    if added > 0:
        print("[Seed] Starting background audiobook check for all authors...")
        threading.Thread(target=_check_all_audiobooks_background, daemon=True).start()

def fetch_trending_authors():
    """Fetch trending authors from Open Library's trending API."""
    url = "https://openlibrary.org/trending/weekly.json?limit=50"
    data = ol_request(url)
    if not data:
        return []
    seen = set()
    authors = []
    for work in data.get("works", []):
        for author in work.get("authors", []):
            name = author.get("name", "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                authors.append(name)
    return authors

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Bookarr — Book Manager and Automation")
    parser.add_argument("--port", type=int, default=8585)
    parser.add_argument("--seed", action="store_true", help="Seed with prize-winning authors")
    parser.add_argument("--no-search", action="store_true", help="Disable background search")
    args = parser.parse_args()

    init_db()
    print(f"[Bookarr] Database initialized at {DB_PATH}")

    # One-time migration to new folder structure
    if not get_setting("folder_structure_migrated"):
        print("[Bookarr] Migrating library to Author/Title/format/ structure...")
        reorganize_library()
        set_setting("folder_structure_migrated", "1")

    if args.seed:
        seed_authors()
        return

    # Start background search
    if not args.no_search:
        search_engine.start()

    # Auto-check audiobooks for any authors that don't have them yet
    conn = get_db()
    missing_count = conn.execute("""
        SELECT COUNT(DISTINCT a.id) FROM authors a
        JOIN books b ON b.author_id = a.id AND b.book_type = 'ebook'
        WHERE a.id NOT IN (SELECT DISTINCT author_id FROM books WHERE book_type = 'audiobook')
    """).fetchone()[0]
    conn.close()
    if missing_count > 0:
        print(f"[Bookarr] {missing_count} authors missing audiobook data — starting background check...")
        threading.Thread(target=_check_all_audiobooks_background, daemon=True).start()

    # Start web server
    server = ThreadedHTTPServer(("0.0.0.0", args.port), BookarrHandler)
    print(f"[Bookarr] Web UI at http://localhost:{args.port}")
    print(f"[Bookarr] eBook path: {get_ebook_path()}")
    print(f"[Bookarr] Audiobook path: {get_audiobook_path()}")
    print(f"[Bookarr] Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Bookarr] Shutting down...")
        search_engine.stop()
        server.shutdown()

if __name__ == "__main__":
    main()
