# Municipality coats of arms

`coats/` contains one reviewed local image for every municipality profile in Scopri:

- coverage: 215/215 ISTAT municipality codes;
- runtime lookup: `frontend/src/data/discover/municipalityVisuals.json`;
- detailed source catalog: `scripts/data/municipality-coat-sources.json`;
- reproducible sync: `node scripts/sync-municipality-coats.mjs --write`.

The sync resolves the exact file through Wikidata P94 or the Italian Wikipedia municipality infobox, records the source page, downloads the image locally and validates its binary format. The application never depends on Wikimedia at runtime.

The images are used as visual identifiers in municipality profile cards. They are not presented as official municipal branding. Source and repository details remain available in the source catalog; file-specific licensing information is available from each recorded source page.

The four PNG files in this directory root are the original Pordenone, Udine, Gorizia and Trieste pilot renders. Runtime now uses their canonical ISTAT-named copies inside `coats/`.

## Reviewed municipality photography

`photos/` contains one reviewed local photograph for every municipality profile in Scopri:

- coverage: 215/215 ISTAT municipality codes;
- runtime manifest: `frontend/src/data/discover/municipalityPhotos.json`;
- source and license catalog shared with the UI: `frontend/src/data/discover/municipalityPhotoCredits.json`;
- explicit editorial selection: `scripts/data/municipality-photo-selection.json`;
- reproducible sync: `node scripts/sync-municipality-photos.mjs --write`;
- integrity check: `node scripts/validate-municipality-photos.mjs`;
- every runtime image is a local WebP asset and never depends on Wikimedia at runtime;
- Wikidata P18 and Wikimedia Commons search only provide candidates: publication always requires visual and license review.
- the user-facing attribution list is published at `https://meteofriul.it/privacy/` and linked from Settings > Information; municipality cards remain free of credit overlays.

The compact card treats each photograph as decorative and keeps the municipality name and coat of arms as its accessible identity. The source catalog retains author, license, source page, original asset and declared modifications. A catalog rebuild never changes the runtime selection automatically: deliberate ranking exceptions remain in `municipality-photo-selection-overrides.json`.
