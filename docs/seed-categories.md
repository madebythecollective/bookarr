# Seed categories

Bookarr includes 8 curated lists of notable authors. Seeding a category adds all authors from that list to your library and fetches their works from Open Library.

## Available categories

### Pulitzer Prize - Fiction

Approximately 75 authors who have won the Pulitzer Prize for Fiction (originally the Pulitzer Prize for the Novel). Spans from the early 20th century to present winners.

**API key:** `pulitzer_fiction`

### Pulitzer Prize - Drama

Approximately 26 authors who have won the Pulitzer Prize for Drama.

**API key:** `pulitzer_drama`

### Pulitzer Prize - Poetry

Approximately 35 authors who have won the Pulitzer Prize for Poetry.

**API key:** `pulitzer_poetry`

### Pulitzer Prize - Nonfiction

Approximately 22 authors who have won the Pulitzer Prize for General Nonfiction.

**API key:** `pulitzer_nonfiction`

### Nobel Prize in Literature

Approximately 110 authors who have been awarded the Nobel Prize in Literature. International scope, dating back to the prize's inception.

**API key:** `nobel`

### Booker Prize Winners

Approximately 52 authors who have won the Man Booker Prize (now the Booker Prize). Primarily authors writing in English, published in the UK or Commonwealth.

**API key:** `booker`

### Classic American Authors

Approximately 95 essential American authors spanning from the colonial period to the 20th century. Includes novelists, poets, essayists, and playwrights.

**API key:** `american_classics`

### Classic World Authors

Approximately 90 major authors from world literature outside the United States. Covers multiple centuries and continents.

**API key:** `world_classics`

## Seeding from the web UI

1. Navigate to **Discover**.
2. Click **Browse Lists**.
3. Select a category.
4. Bookarr begins adding authors in the background.

Seeding progress is logged to the console and `bookarr.log`. Duplicate authors (already in your library) are skipped.

## Seeding from the command line

To seed all categories at once and exit:

```bash
python3 bookarr.py --seed
```

## Seeding from the API

```
POST /api/seed
Content-Type: application/json

{"category": "pulitzer_fiction"}
```

## What happens when you seed

For each author in the category:

1. The author is added to the database with `seed_source` set to the category key.
2. Open Library is searched for the author.
3. Up to 100 works are fetched and filtered:
   - Non-English titles are removed (based on your language setting).
   - Junk entries (very short titles, duplicates) are removed.
4. Each work is added as an ebook with status "missing."
5. After all authors in the category are processed, a background audiobook check runs to find audiobook editions.

Rate limiting: the seed process waits 0.5 seconds between authors to be respectful of Open Library's API.

## Trending authors

In addition to curated categories, you can seed from Open Library's currently trending authors:

```
POST /api/seed/trending
```

Or click the trending button on the Discover page.
