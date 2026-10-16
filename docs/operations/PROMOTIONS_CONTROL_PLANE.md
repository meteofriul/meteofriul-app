# Promotions control plane

## Safety baseline

The Meteo Friûl application contains no enabled embedded campaign. The backend
also returns an explicit disabled catalog when no administrative state exists.
Therefore a missing API, an unreadable cache, an expired cache, an empty
catalog, or a disabled switch all hide the placement.

This cutover does not change the Android version, run `android:sync`, or create
an APK/AAB. Android release work must remain a later, separate commit.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| `INSERZIONI` panel | Private campaign editing, Firebase sign-in, image upload and explicit publication. |
| Firebase Authentication | Identifies the operator; only `adsAdmin: true` is accepted. |
| Firebase Storage | Stores versioned creative images under `promotion-images/`. |
| Ordinary Cloud Run API | Stores private state, increments revisions, publishes the sanitized catalog and aggregates delivery metrics. |
| Meteo Friûl app | Reads the public catalog on startup, foreground and every five minutes; records only aggregate impression/open events. |

Private campaign data is stored in `promotion_admin_state/current`. Aggregate
daily counters use `promotion_daily_metrics`. The public catalog is derived on
read from the private state and never contains contact, billing, payment,
invoice or internal-note fields.

## API contract

- `GET /api/promotions/catalog`: public sanitized catalog;
- `POST /api/promotions/events`: App Check protected aggregate event;
- `GET /api/admin/promotions/state`: Firebase `adsAdmin` state read;
- `GET /api/admin/promotions/availability`: authenticated availability read for
  one or more `page` values and a `startDate`/`endDate` interval (maximum 93
  days);
- `PUT /api/admin/promotions/state`: Firebase `adsAdmin` state replacement with
  `expectedRevision` conflict protection and transactional availability check.

The public catalog is an additive, backward-compatible `schemaVersion: 2`
contract. It declares `Europe/Rome`, the three supported placements, a
120-second client rotation interval and a maximum of three simultaneous
rotation campaigns per placement. Version 1 clients keep using the unchanged
campaign fields and continue to render Home; version 2 clients also render
Events and Discover. A client must fail closed on a schema version newer than
the maximum it supports. The public campaign keeps `scheduleMode`,
`activeMonth`, date bounds, selected dates and optional `startTime`/`endTime`
so a cached client can also stop a card exactly at its Rome-time boundary.

The switch order is: global switch, placement switch, active campaign, valid
schedule. All four conditions must pass. Pausing a campaign changes its status
without deleting private data, images, metrics or billing information.

## Availability contract

- The canonical timezone is `Europe/Rome`.
- Placements are `home`, `events` and `discover`.
- `bookingMode` is `exclusive` or `rotation`. Legacy `deliveryMode` values are
  accepted; `rotation` retains its meaning and `all_selected` is treated as an
  exclusive reservation.
- `startTime` and `endTime` are optional `HH:MM` values. Missing values mean
  `00:00` and `24:00`. Intervals are half-open, so `08:00–12:00` and
  `12:00–18:00` do not overlap.
- `draft` and `archived` campaigns do not reserve. `scheduled`, `active` and
  `paused` campaigns do reserve, independently of the global and placement
  switches.
- An exclusive reservation cannot overlap any other reservation on the same
  page. Rotation allows at most three simultaneous sponsors and cannot overlap
  an exclusive reservation.
- Only one card is visible in each placement at a time. When two or three
  rotation campaigns are available, the client advances every two minutes;
  this does not change the five-minute catalog refresh or the daily caps.
- Every write rereads the current state, checks revision and availability, and
  writes the new revision in one Firestore transaction. Conflicts return HTTP
  `409` with page, date, overlapping time and occupying campaign.

## First controlled activation

1. Deploy the ordinary API image containing the promotion routes.
2. Verify `COMMUNITY_STORAGE=firestore`, the Firebase project identity and the
   exact panel CORS origin.
3. Review existing Storage rules before deploying the panel `storage.rules`;
   Firebase rule deployment replaces the current ruleset atomically.
4. Grant the exact operator account its custom claim. Run without `--apply`
   first:

   ```powershell
   py backend/tools/set_ads_admin_claim.py --email operator@example.test --enable
   py backend/tools/set_ads_admin_claim.py --email operator@example.test --enable --apply
   ```

5. Deploy the `INSERZIONI` Hosting target and sign in.
6. Confirm the remote state reads `adsEnabled: false` and revision `0` before
   importing or publishing any local campaign.
7. Test creation, image upload, publish, pause and stale-cache disappearance
   while keeping the global switch off.
8. Only after this control plane is verified should a later guarded AAB include
   the catalog reader.

Custom-claim changes require a refreshed Firebase ID token. The panel requests
a fresh token on remote reload. Revocation uses the same tool with `--disable`.
