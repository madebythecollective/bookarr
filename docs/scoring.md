# Search scoring

Bookarr scores every search result to determine whether it should be automatically grabbed. This document explains every scoring factor, the thresholds, and the rejection rules.

## Overview

The `score_result` function assigns an integer score to each search result. Scores can range from -1 (hard reject) to roughly 100+ (perfect match). Only results scoring at or above your configured **Min Score** (default: 30) are automatically grabbed by the background search engine.

## Hard rejections (score = -1)

These conditions cause a result to be immediately rejected regardless of other factors.

### Non-English filter

If your language preference is not set to "any," results that appear to be non-English are rejected. Detection uses regex patterns for:

- **German:** "german", "deutsch", ".DE.", "-DE-"
- **French:** "french", "francais", ".FR.", "-FR-"
- **Spanish:** "spanish", "espanol", ".ES.", "-ES-"
- **Italian:** "italian", "italiano", ".IT."
- **Portuguese:** "portuguese", ".PT.", "-PT-"
- **Russian:** "russian", ".RU."
- **Chinese:** "chinese", ".CN."
- **Japanese:** "japanese", ".JP."
- **Korean:** "korean", ".KR."
- **Dutch:** "dutch", ".NL."
- **Swedish:** "swedish", ".SE."
- **Polish:** "polish", ".PL."

### Music and soundtrack filter

Results containing any of these indicators are rejected as music releases, not books:

`flac`, `16bit`, `24bit`, `32bit`, `wavpack`, `dsd`, `sacd`, `vinyl`, `lp-`, `-lp`, `discography`, `remaster`, `deluxe edition`, `original cast recording`, `original soundtrack`, `ost-`, `-ost`, `soundtrack`, `album`, `single`, `v0`, `320kbps`, `44khz`, `48khz`, `96khz`, `192khz`, `cd-flac`, `web-flac`

**Exception:** Results also containing "audiobook", "narrated", "unabridged", or "read by" are not rejected by this filter.

## Scoring factors

### Author name match: up to +60

Each part of the author's name (words longer than 2 characters) is checked against the result title.

- **+20 per matching name part.**
- Example: "Cormac McCarthy" has two parts. Both matching = +40.

### Title match: up to +60

Calculated as a proportion of matching words:

```
+60 x (matched_title_words / total_title_words)
```

Each word from the book title (longer than 2 characters, lowercased) is checked against the result title. The score scales linearly with the fraction of words matched.

- Example: Book title "Blood Meridian" (2 significant words). Both found in result = +60. One found = +30.

### Format preference (ebook): up to +15

Applies when the book type is "ebook":

| Condition | Bonus |
|---|---|
| Result contains the user's preferred format (for example, "epub") | +15 |
| Result contains "epub" (if not already preferred) | +10 |
| Result contains "mobi" or "azw" | +5 |
| Result contains "pdf" | +2 |

### Format preference (audiobook): up to +10

Applies when the book type is "audiobook":

| Condition | Bonus |
|---|---|
| Result contains "audiobook" | +10 |
| Result contains "m4b" | +8 |
| Result contains "mp3" | +5 |

### Size penalties

| Condition | Penalty |
|---|---|
| File size exceeds the configured maximum (ebook: 200 MB, audiobook: 5000 MB) | -50 |
| File size is less than 0.1 MB | -10 |

### Collection and pack penalty

Results containing any of these terms receive a **-40 penalty**:

`pack`, `collection`, `bundle`, `top-ebooks`

These are typically bulk uploads that may not contain the specific book being searched.

### Torrent seeder scoring

Applies only to torrent results (not usenet):

| Condition | Effect |
|---|---|
| 0 seeders | -30 |
| Below configured min_seeders | -15 |
| 10 or more seeders | +10 |
| 5-9 seeders | +5 |

## Score examples

**Strong match (ebook):**
- Author "Cormac McCarthy" both parts match: +40
- Title "Blood Meridian" both words match: +60
- Preferred format EPUB found: +15
- File size 2 MB (within limits): no penalty
- **Total: 115** (excellent, auto-grabbed)

**Partial match:**
- Author last name matches: +20
- Title 2 of 4 words match: +30
- No format match: +0
- **Total: 50** (above default threshold, grabbed)

**Poor match:**
- Author name not found: +0
- Title 1 of 3 words match: +20
- Collection keyword found: -40
- **Total: 0** (below threshold, rejected)

## Configuring the threshold

The **Min Score** setting (default: 30) controls the auto-grab threshold:

- **Lower values (10-20):** More aggressive. Grabs more results but with higher risk of incorrect matches.
- **Default (30):** Balanced. Requires reasonable title and author matching.
- **Higher values (50-70):** Conservative. Only grabs strong matches with format preference.
- **Very high (80+):** Requires near-perfect title match, author match, and preferred format.

Adjust in **Settings > Search > Min Score**.
