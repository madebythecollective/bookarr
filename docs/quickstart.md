# Quick start

Get Bookarr running and searching for books in under 5 minutes.

## Prerequisites

Before you begin, make sure you have:

- Python 3.10 or later installed
- A running [Prowlarr](https://prowlarr.com/) instance with at least one indexer configured
- A running [NZBGet](https://nzbget.com/) instance (or a torrent client)

## Step 1: Install and start Bookarr

```bash
git clone https://github.com/johnhowrey/bookarr-public.git
cd bookarr-public
pip install -r requirements.txt
python3 bookarr.py
```

Open [http://localhost:8585](http://localhost:8585) in your browser.

## Step 2: Configure your connections

Navigate to **Settings** in the sidebar.

1. **Prowlarr.** Enter your Prowlarr URL and API key. Add your usenet indexer IDs (comma-separated). Click **Test Connection** to verify.
2. **NZBGet.** Enter your NZBGet URL, username, and password. Click **Test Connection** to verify.
3. **Library paths.** Set your eBook and audiobook save paths. These are the directories where Bookarr organizes downloaded files.

Click **Save** at the bottom of the page.

## Step 3: Add your first author

Navigate to **Discover** in the sidebar.

1. Click **+ Add Author**.
2. Search for an author by name (for example, "Cormac McCarthy").
3. Select the author from the search results.

Bookarr fetches the author's works from Open Library, adds them as ebooks, and checks for audiobook editions in the background.

## Step 4: Want some books

Navigate to **Library** in the sidebar. You should see the author's books listed with a "missing" status.

- Click a book to open its detail view, then click **Want** to mark it for download.
- Or go to the author's page in Discover and click **Want All** to want every book at once.

## Step 5: Let the search engine work

Bookarr's background search engine automatically searches your configured indexers for wanted books every 15 minutes (configurable in Settings). When it finds a result that scores above the minimum threshold, it sends it to NZBGet automatically.

To trigger an immediate search, click **Search Now** on the Library page.

## What happens next

1. Bookarr searches Prowlarr for each wanted book.
2. Results are scored by title match, author match, format, and size.
3. The best result above your minimum score is sent to NZBGet.
4. Bookarr monitors NZBGet for completion.
5. Completed downloads are moved to your library in the `Author/Title/ebook/` or `Author/Title/audiobook/` folder structure.
6. The book's status updates to "downloaded."

## Next steps

- [Configuration](configuration.md) - Fine-tune search intervals, scoring thresholds, and format preferences
- [Managing your library](library.md) - Seed from curated lists, scan existing folders, manage authors
- [Running as a service](service.md) - Set up Bookarr to start automatically on boot
