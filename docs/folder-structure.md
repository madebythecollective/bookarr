# Folder structure

Bookarr organizes downloaded books into a consistent directory hierarchy based on author, title, and format.

## Directory layout

```
{ebook_path}/
  Author Name/
    Book Title/
      ebook/
        filename.epub

{audiobook_path}/
  Author Name/
    Book Title/
      audiobook/
        filename.m4b
```

Each book gets its own directory under the author, with a subdirectory for the format type (`ebook/` or `audiobook/`). This structure keeps ebook and audiobook files for the same title organized separately, even when the ebook and audiobook save paths point to the same root directory.

## Examples

With ebook path `/media/books` and audiobook path `/media/audiobooks`:

```
/media/books/
  Cormac McCarthy/
    Blood Meridian/
      ebook/
        Blood.Meridian.epub
    The Road/
      ebook/
        The.Road.epub

/media/audiobooks/
  Cormac McCarthy/
    Blood Meridian/
      audiobook/
        Blood.Meridian.m4b
    The Road/
      audiobook/
        The.Road.mp3
```

## Automatic migration

On first startup, Bookarr checks for books that were downloaded under a flat structure (files directly in the author directory) and migrates them to the `Author/Title/format/` hierarchy.

This migration runs once and sets the `folder_structure_migrated` setting to `1`. It does not run again on subsequent startups.

## Recognized file extensions

### Ebooks

| Extension | Format |
|---|---|
| `.epub` | EPUB |
| `.mobi` | Mobipocket |
| `.azw` | Amazon Kindle |
| `.azw3` | Amazon Kindle Format 8 |
| `.pdf` | PDF |
| `.djvu` | DjVu |
| `.fb2` | FictionBook |
| `.cbz` | Comic Book Archive (ZIP) |
| `.cbr` | Comic Book Archive (RAR) |

### Audiobooks

| Extension | Format |
|---|---|
| `.mp3` | MP3 audio |
| `.m4b` | MPEG-4 audiobook |
| `.m4a` | MPEG-4 audio |
| `.ogg` | Ogg Vorbis |
| `.flac` | Free Lossless Audio Codec |

## Post-processing

When a download completes (from NZBGet or a torrent client), Bookarr:

1. Locates the downloaded file in the download client's destination directory.
2. Determines the target path: `{save_path}/{Author Name}/{Book Title}/{ebook|audiobook}/`.
3. Creates the directory structure if it does not exist.
4. Moves the file to the target directory.
5. Updates the book's `path` field in the database with the new location.
6. Sets the book's status to `downloaded`.

## Source folder scanning

When scanning source folders, Bookarr:

1. Walks each folder recursively.
2. Skips hidden files and directories (names starting with `.`).
3. Checks each file's extension against the recognized list.
4. Normalizes the filename (lowercase, stripped of common separators) and compares the first 30 characters against book titles in the database.
5. Matched files are moved into the organized structure.
6. Unmatched files are left in place.
