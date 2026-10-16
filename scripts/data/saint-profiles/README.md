# Saint profile review batches

This directory contains month-level review artifacts used to build
`frontend/src/data/almanac/saintProfiles.json`.

Each batch must:

- use the primary calendar entry in `frontend/src/data/almanac/saints.json`;
- cite the matching 2026 CEI `santo-del-giorno` page;
- provide a concise, factual Italian description only when verified;
- provide Friulian copy only after a dedicated language review;
- avoid devotional filler, unsupported details, and Italian fallback in FUR.

The month files are staging artifacts. The application reads only the merged,
validated catalog in `frontend/src/data/almanac/saintProfiles.json`.

## Current coverage

- 366 calendar dates represented;
- 364 concise Italian profiles approved against CEI;
- 2 records (`03-30`, `04-12`) intentionally left without description because
  the 2026 CEI pages expose the movable celebration title but no descriptive
  Martirologio text;
- 364 Friulian descriptions are reviewed in six month-pair batches plus the
  dedicated 21-28 July batch inherited from the first UI profile pass; the two
  dates without an Italian source remain empty and `pending_review`;
- the leap-day record uses the valid CEI page for 29 February 2024 rather than
  the invalid 2026 date, which CEI resolves as 1 March.
