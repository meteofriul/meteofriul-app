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

The public catalog uses `schemaVersion: 2`. The optional `visibleFields`
extension preserves legacy payloads, but Android 0.1.14 compatibility depends
on the selected text fields; see the compatibility section below. It declares
`Europe/Rome`, three supported placements, per-placement rotation intervals
(120 seconds by default; allowed values 30, 60, 120 and 300) and a maximum of
five simultaneous rotation campaigns per placement. A client must fail closed
on a schema version newer than
the maximum it supports. The public campaign keeps `scheduleMode`,
`activeMonth`, date bounds, selected dates and optional `startTime`/`endTime`
so a cached client can also stop a card exactly at its Rome-time boundary.

The switch order is: global switch, placement switch, active campaign, valid
schedule. All four conditions must pass. Pausing a campaign changes its status
without deleting private data, images, metrics or billing information.

## Selected card text and Android 0.1.14 compatibility

The admin campaign accepts `cardVisibleFields`, an ordered list drawn from
`businessName`, `category`, `address`, `city`, `title` and `description`.
Duplicates and unknown entries are removed. An explicit empty selection is
invalid for an active campaign. Without a list, legacy defaults apply:
`businessName`, the selected legacy `cardDetails`, `title`, `description`.
The explicit selection takes precedence over `cardDetails`.

| Admin field | Public campaign field |
| --- | --- |
| `businessName` | `title` |
| `category` | `category` |
| `address` (value from `businessAddress`) | `businessAddress` |
| `city` | `location` |
| `title` | `headline` |
| `description` | `text` |

The public response includes `visibleFields` and replaces each unselected
text value with an empty string. It does not return hidden texts as legacy
fallbacks. This is a text-display contract, not an anonymization mechanism:
the public creative, destination URL and existing advertiser grouping ID remain
part of the campaign. Contact, invoice and internal-note fields stay private.
At least one selected text must be nonempty. A selected headline or description
must have its value; either may be empty when hidden. Existing active-campaign
requirements for business name, city, HTTPS image/URL and placement still apply.

The updated client accepts cards with any valid nonempty text selection and
renders only selected rows in Home, Events and Discover, including accessible
names. The advertising label and CTA remain visible. A visible headline gets
the primary text hierarchy; without it, the business/location row remains
primary. Catalog refresh, cache expiry, campaign IDs, rotation and aggregate
impression/open events keep their existing contracts.

**Android 0.1.14 requires both public `title` and `text`.** It ignores
`visibleFields` and silently drops a campaign if either required value is
empty. Therefore a campaign remains compatible only with `businessName` and
`description` selected and populated. Optional fields can be hidden safely;
unrestricted selection requires an updated Android client. The API does not
enforce this rollout restriction: it also serves newer clients. Before any
future production rollout, verify the active panel selections and preserve
both required fields while supporting 0.1.14, or complete a separate client
upgrade plan. Do not describe the unrestricted contract as fully compatible.

Automated evidence uses synthetic API responses shared by backend tests and
both client normalizers, including an unchanged excerpt from 0.1.14. It covers
admin/public separation, all 63 nonempty selections, legacy acceptance,
current rendering and offline cache expiry. This is not a physical-device or
minified Android release test. See
`SPONSOR_CARD_RECOVERY_20261017.txt` for the candidate verification record.

Sponsor retention, closure, erasure and document-lifecycle work are excluded
from this recovery. The separate `INSERZIONI` repository is unchanged.

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
  page. Rotation allows at most five simultaneous sponsors and cannot overlap
  an exclusive reservation.
- Only one card is visible in each placement at a time. When two to five
  rotation campaigns are available, the client advances at the configured interval;
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
