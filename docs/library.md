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
3. Adds each work as an ebook with status "missing."
4. Checks Open Library and Audible for audiobook editions in the background. Found audiobooks are added automatically.

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

## Adding individual books

1. Navigate to **Library**.
2. Click **+ Add Book**.
3. Search by title, author, or ISBN.
4. Select a result and choose to add as ebook, audiobook, or both.

## Wanting books

A book with status "missing" is in your library but Bookarr is not actively searching for it. To start searching:

- **Single book.** Open the book detail view and click **Want**.
- **All books by an author.** Open the author's page and click **Want All**. Optionally filter by ebook or audiobook.
- **Filtered want.** Use the Library filters to find specific books, then want them individually.

When you want a book and the "When Wanting a Book" setting is set to "Both," the sibling format (ebook or audiobook) is also marked as wanted.

## Book statuses

| Status | Meaning |
|---|---|
| **Missing** | In your library but not being searched for. |
| **Wanted** | Actively searched by the background search engine. |
| **Downloading** | A release has been sent to your download client. |
| **Downloaded** | The file has been downloaded and organized in your library. |

## Monitoring

Authors and books can be individually monitored or unmonitored.

- **Unmonitored authors** are skipped entirely during background search, even if they have wanted books.
- **Unmonitored books** are skipped during background search regardless of their status.

Toggle monitoring from the author's page in Discover.

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
3. Matched files are moved to the organized folder structure: `Author Name/Book Title/ebook/` or `Author Name/Book Title/audiobook/`.
4. The book's status is updated to "downloaded" and its file path is recorded.

### Recognized file extensions

**Ebooks:** `.epub`, `.mobi`, `.azw`, `.azw3`, `.pdf`, `.djvu`, `.fb2`, `.cbz`, `.cbr`

**Audiobooks:** `.mp3`, `.m4b`, `.m4a`, `.ogg`, `.flac`

## Audiobook discovery

Bookarr checks whether audiobook editions exist before adding them to your library. This prevents your wanted list from filling with books that have no audiobook available.

The check queries two sources:

1. **Open Library.** Looks at edition data for format keywords: "audio", "audible", "cd audiobook", "mp3".
2. **Audible catalog API.** Searches by title and author name. If results are found, the audiobook exists.

### Bulk audiobook check

Click **Find Audiobooks** on the Discover page to check all authors for audiobook editions. This runs in the background and can take several minutes for large libraries.

Bookarr also automatically checks for audiobooks on startup for any authors that are missing audiobook data.

## Deleting content

- **Delete a book.** Open the book detail view and click **Delete**. If the author has no remaining books, the author is also removed.
- **Delete an author.** Open the author's page and click **Delete Author**. All books by that author are removed.
- **Reset library.** In Settings, click **Reset All** to clear all authors, books, downloads, and logs. Settings are preserved.

## Cleanup

Click **Cleanup** on the Library page (via the API at `/api/cleanup`) to remove junk titles, non-English entries, and duplicate books.
