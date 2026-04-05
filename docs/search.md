# Search and downloads

Bookarr automates searching for wanted books and sending results to your download client. This guide explains how the search engine works, what happens during a search, and how to search manually.

## Background search engine

The background search engine is a daemon thread that runs continuously while Bookarr is active. It performs two tasks on a loop:

1. **Search for wanted books.** Query Prowlarr indexers for books with status "wanted."
2. **Check downloads.** Monitor NZBGet and torrent clients for completed or failed downloads.

### Search cycle

Each cycle processes up to 50 wanted books: 25 audiobooks and 25 ebooks. Books are prioritized by:

1. Books that have never been searched (oldest first).
2. Books that were searched least recently.

For each book, the search engine:

1. Queries all configured indexers with `"Author Name Book Title"`.
2. If no results, retries with just the book title.
3. For audiobooks, tries additional strategies:
   - Author + title + "audiobook" (searching all book categories)
   - Author last name + title
   - Author + title (searching all book categories)
4. Scores each result. See [Search scoring](scoring.md). Results must meet the 50%+ title word match threshold or include the author's last name; weak single-word matches without author confirmation are hard-rejected.
5. Filters out results with a score below the minimum threshold.
6. If a qualifying result is found, sends it to the download client. On 500 errors, the frontend retries once automatically.
7. Updates the book's `last_searched` timestamp and `last_result_count`.
8. Waits 2 seconds before processing the next book.

The cycle repeats after the configured search interval (default: 900 seconds / 15 minutes).

### Disabling background search

Start Bookarr with the `--no-search` flag to disable the background search engine entirely:

```bash
python3 bookarr.py --no-search
```

Or set **Auto Search** to off in Settings. The search engine thread still runs but skips the search phase.

## Manual search

### Search from the Library page

Click **Search Now** on the Library page to trigger an immediate background search cycle.

### Search from a book detail view

Open a book's detail view and click the search icon to search indexers specifically for that book. Results are displayed with scores and you can manually grab any result.

### Search indexers directly

Use the search bar in the Library page to search your configured indexers by any query. Results are displayed with:

- Title and indexer source
- File size
- Score (if searching for a specific book)
- Protocol (usenet or torrent)
- Grab button

## Download flow

### Usenet (NZBGet)

1. Bookarr fetches the NZB file from the indexer URL.
2. The NZB content is base64-encoded and submitted to NZBGet via JSON-RPC.
3. Downloads are submitted with category `Books` and priority `100` (VeryHigh).
4. Bookarr polls NZBGet history for completion.
5. On success, the downloaded file is moved to the organized folder structure.
6. On failure, the error details are captured (health percentage, PAR status, unpack status).

### Torrent (qBittorrent)

1. Bookarr submits the torrent URL to qBittorrent's web API.
2. The torrent is added with the configured category.
3. Bookarr polls qBittorrent for torrent state changes.
4. States `uploading`, `stalledUP`, `queuedUP`, or `forcedUP` indicate completion.
5. On completion, the file is moved to the organized folder structure.
6. If the seed ratio limit is reached, the torrent is removed from the client.

### Torrent (Transmission)

1. Bookarr submits the torrent URL via Transmission's JSON-RPC API.
2. Download monitoring for Transmission is not yet fully implemented.

### Post-processing

After a download completes successfully:

1. Bookarr identifies the downloaded file in the download client's destination directory.
2. The file is routed by extension: ebook files to the ebook save path, audio files to the audiobook save path, organized according to the configured folder structure preset.
3. The book's format flags (`have_ebook`/`have_audiobook`) and paths are updated. Status is set to "downloaded."

### Stalled downloads

Downloads stuck in "downloading" status for more than 48 hours with no corresponding entry in the download client are automatically reset to "wanted" status so the search engine can try again.

### Failed downloads

Failed downloads are recorded with error details. You can retry a failed download from the Activity page. The error detail captures:

- NZBGet status message
- Health percentage (for incomplete downloads)
- PAR repair status
- Unpack status
- Move status

## Search progress

The search engine reports its progress through the `/api/search/progress` endpoint, which the UI polls to display:

- Whether a search is currently active
- Total books being searched
- How many have been processed
- Which book is currently being searched
- How many have been grabbed this cycle
