# Folder structure

Bookarr organizes downloaded books into a configurable directory hierarchy. The folder structure is set in **Settings > Library > Folder Structure**.

## Presets

### Author/Title (default)

Files are placed directly in an Author/Title directory with no format subdirectory. Ebook files go to the ebook path and audio files go to the audiobook path based on file extension.

```
{ebook_path}/
  Author Name/
    Book Title/
      filename.epub

{audiobook_path}/
  Author Name/
    Book Title/
      filename.m4b
```

### Author/Title (Format)

Adds a format subdirectory inside the title folder. Useful when ebook and audiobook save paths point to the same root directory.

```
{save_path}/
  Author Name/
    Book Title/
      ebook/
        filename.epub
      audiobook/
        filename.m4b
```

### Author Only

Files are placed directly in the author directory without a title subdirectory.

```
{ebook_path}/
  Author Name/
    filename.epub

{audiobook_path}/
  Author Name/
    filename.m4b
```

## Examples

With the default Author/Title preset, ebook path `/media/books`, and audiobook path `/media/audiobooks`:

```
/media/books/
  Cormac McCarthy/
    Blood Meridian/
      Blood.Meridian.epub
    The Road/
      The.Road.epub

/media/audiobooks/
  Cormac McCarthy/
    Blood Meridian/
      Blood.Meridian.m4b
    The Road/
      The.Road.mp3
```

## File routing

Regardless of how a book is tagged in the database, files are routed to the correct library path based on their extension:

- **Ebook extensions** (`.epub`, `.mobi`, `.azw`, `.azw3`, `.pdf`, `.djvu`, `.fb2`, `.cbz`, `.cbr`) always go to the ebook save path.
- **Audio extensions** (`.mp3`, `.m4b`, `.m4a`, `.ogg`, `.flac`) always go to the audiobook save path.

## Automatic migration

On first startup, Bookarr checks for books that were downloaded under an older structure and migrates them to the configured layout.

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
2. Routes the file to the ebook or audiobook save path based on file extension.
3. Determines the target path using the configured folder structure preset.
4. Creates the directory structure if it does not exist.
5. Moves the file to the target directory.
6. Updates the book's `ebook_path` or `audiobook_path` and sets the corresponding `have_ebook` or `have_audiobook` flag.
7. Sets the book's status to `downloaded`.

## Source folder scanning

When scanning source folders, Bookarr:

1. Walks each folder recursively.
2. Skips hidden files and directories (names starting with `.`).
3. Checks each file's extension against the recognized list.
4. Normalizes the filename (lowercase, stripped of common separators) and compares the first 30 characters against book titles in the database.
5. Matched files are moved into the organized structure.
6. Unmatched files are left in place.
