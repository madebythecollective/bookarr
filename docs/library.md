# Managing your library

This guide covers adding content to your library, organizing files, and managing authors and books.

## Adding authors

### Search and add

1. Navigate to **Discover**.
2. Click **+ Add Author**.
3. Type an author name and select from the Open Library search results.

When you add an author, Bookarr:

1. Fetches up to 200 works from Open Library.
2. Filters out non-English titles (based on your language setting), junk entries, and duplicates.
3. Adds each work as a book with status "missing." Format flags (`want_ebook`, `want_audiobook`) are unset until you choose which formats you want.

### Seed from curated lists

Bookarr includes 8 curated lists with approximately 500 authors:

| Category | Authors |
|---|---|
| Pulitzer Prize - Fiction | ~75 |
| Pulitzer Prize - Drama | ~26 |
| Pulitzer Prize - Poetry | ~35 |
| Pulitzer Prize - Nonfiction | ~22 |
| Nobel Prize in Literature | ~110 |
| Booker Prize Winners | ~52 |
| Classic American Authors | ~95 |
| Classic World Authors | ~90 |

To seed from a category:

1. Navigate to **Discover**.
2. Click **Browse Lists**.
3. Select a category to seed all authors from that list.

Seeding runs in the background. Duplicate authors are skipped.

### Seed from trending

Click the trending button on the Discover page to fetch and seed currently trending authors from Open Library.

## Import from disk

If you already have books organized in an Author/Title folder structure, Bookarr can discover and import them:

1. Set your **eBook Save Path** and/or **Audiobook Save Path** in Settings.
2. Navigate to **Library** and click **Import from Disk** (or call `POST /api/import`).
3. Bookarr walks the configured paths, matches Author/Title folders to existing library entries, and creates new entries for unrecognized books.
4. Format flags (`have_ebook`, `have_audiobook`) are set based on file types found.

## Adding individual books

1. Navigate to **Library**.
2. Click **+ Add Book**.
3. Search by title, author, or ISBN.
4. Select a result to add it to your library. Use the format toggles to choose ebook, audiobook, or both.

## Wanting books

A book with status "missing" is in your library but Bookarr is not actively searching for it. To start searching:

- **Single book.** Open the book detail view and use the format toggles to want the ebook, audiobook, or both independently.
- **All books by an author.** Open the author's page and click **Want All**.
- **Filtered want.** Use the Library filters to find specific books, then want them individually.

Each book has independent format toggles: `want_ebook` and `want_audiobook`. You can want one format without the other.

## Book statuses

| Status | Meaning |
|---|---|
| **Missing** | In your library but not being searched for. |
| **Wanted** | Actively searched by the background search engine. |
| **Downloading** | A release has been sent to your download client. |
| **Downloaded** | The file has been downloaded and organized in your library. |

## Library views

The Library page supports two views:

- **Books view.** The default grid/list of all books with filtering by status, genre, and search.
- **Authors view.** Toggle to see authors with aggregate counts. Click an author to view their books with prev/next navigation between authors.

### Genre filtering

Books can be filtered by subject/genre. Subjects are populated from Open Library during metadata enrichment. Use the genre dropdown on the Library page to filter.

## Monitoring

Authors and books can be individually monitored or unmonitored.

- **Unmonitored authors** are skipped entirely during background search, even if they have wanted books.
- **Unmonitored books** are skipped during background search regardless of their status. Toggle per-book monitoring from the book detail view.

Toggle author monitoring from the author's page. Toggle book monitoring from the book detail view or via `POST /api/book/{id}/toggle-monitor`.

## Metadata enrichment

Click **Enrich Metadata** (or call `POST /api/enrich`) to start a background job that fetches year, cover art, and subjects from Open Library for books missing this data. Enriched subjects power the genre filtering feature.

## Refresh author books

From an author's detail page, click **Refresh Books** (or call `POST /api/author/{id}/refresh`) to re-fetch the author's works list from Open Library. This discovers new titles that were published or added to Open Library since the author was originally seeded.

## Scanning source folders

Bookarr can scan directories on your filesystem for existing book files and match them to books in your library.

### Automatic source folders

Your ebook and audiobook save paths are always scanned.

### Custom source folders

Add additional folders (Downloads directory, NAS shares, external drives) through **Settings > Source Folders**:

1. Click **Add Folder**.
2. Use the folder browser to select a directory.
3. Click **Scan Now** to scan all source folders.

### How scanning works

1. Bookarr walks each source folder recursively, skipping hidden files and directories.
2. For each file with a recognized extension, it normalizes the filename and compares the first 30 characters against book titles in the database.
3. Matched files are moved to the organized folder structure based on the configured folder structure preset. Files are routed by extension: ebook files to the ebook path, audio files to the audiobook path.
4. The book's format flags (`have_ebook`/`have_audiobook`) and paths are updated accordingly.

### Recognized file extensions

**Ebooks:** `.epub`, `.mobi`, `.azw`, `.azw3`, `.pdf`, `.djvu`, `.fb2`, `.cbz`, `.cbr`

**Audiobooks:** `.mp3`, `.m4b`, `.m4a`, `.ogg`, `.flac`

## Deleting content

- **Delete a book.** Open the book detail view and click **Delete**. If the author has no remaining books, the author is also removed.
- **Delete an author.** Open the author's page and click **Delete Author**. All books by that author are removed.
- **Reset library.** In Settings, click **Reset All** to clear all authors, books, downloads, and logs. Settings are preserved.

## Cleanup

Click **Cleanup** on the Library page (via the API at `/api/cleanup`) to remove junk titles, non-English entries, and duplicate books.
