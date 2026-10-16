# Pilot events: real-source probe

Read-only local execution: `python -m app.events.pilot_probe` from backend.
No shared Firestore cache, cloud resource or phone changes.

TurismoFVG strict parser completed in 34.876 seconds, 90 records, all with
resolved coordinates. Geographic subsets around Udine: 84 within 5 km,
90 within 10/20/30/50 km. This is NOT evidence of complete 50-km coverage:
the existing acquisition still scopes candidates to 20 km and selected towns.
Records have not yet passed the full publication date/deduplication policy.

The existing aggregate collector waits 12 seconds. This single local execution
exceeded that by almost three times. It does not establish cloud timing or
prove the sole cause of every upstream timeout.

The current TurismoFVG parser geocodes the detected municipality and sets
location_confidence=municipality. These coordinates must not be represented as
precise venue positions. The first samples share Udine municipality coordinates.

Remaining deployment gates:
- Expand source acquisition coverage before advertising radii above 20 km.
- Preserve municipality/venue confidence in response and UI.
- Filter ended events at read time, enforce maximum stale age.
- Validate explicit source success, bounded output size and deduplication.
- Durable atomic publication with concurrency protection in pilot-only storage.
- Verify total pilot costs before scheduling cloud collection.
- Wire API, radius-aware cache and saved preference, then test phone.

UI selector remains hidden until a working radius-capable callback is wired.

## Regional pagination probe

Added a separate regional listing collector and six regression tests (42 pilot
tests pass overall). Rejects empty markup, unsafe/unrecognized next links,
pagination loops and page-budget exhaustion; exceptions prevent publication.
Real read-only probes did not reach the end within either 20 or 40 pages.
This does not establish 40 distinct useful pages: inspect repeated content and
date scope before increasing the budget or scheduling. No catalog was published,
no cloud resources changed, and daily Events automation is not active.
