# CAMS / UV recovery — 9 September 2026

## Scope and map before implementation

Owner approval: complete existing recovery, not a parallel pipeline. No UI,
cadence, Firebase, beta, or ICON changes. Air and pollen remain one atomic family.
Cloud state and artifacts are private and must never contain credentials or signed URLs.

| Phase | Air + pollen today | UV today | Gap to close |
| --- | --- | --- | --- |
| Request plan | `state/plans/cams/<day>.json` | Request in `state/uv/<day>/intent.json` | UV intent lacks explicit dataset/timestamp/fingerprint |
| Submission intent | `state/ads/<day>/<request-hash>/intent.json`, allowlisted files | `state/uv/<day>/intent.json`, create-only | An intent without a job is not evidence of rejection |
| Remote reference | Same ADS prefix, `submitted.json` includes `job.json` | Same UV prefix, `job.json` | Connect existing GET-only reconciliation; incomplete search must not resubmit |
| Waiting | ADS job is resumable, bounded polling | Saved job is resumable, 40-second polling | Persist progress independently of success; claims must allow recovery |
| Download | Local `source.grib` and completed-download evidence | Temporary `uv.grib` | Preserve verified bytes and evidence in existing private prefixes |
| Decode / validation | Temporary decoded JSON and report; lifecycle records hashes | Temporary complete `pilot-uv-v1` JSON | Persist what is needed to retry only publication |
| Publication identity | `state/publication/cams/<run>.json` freezes fingerprint/time | Single UV latest updated with compare-and-swap | Reuse identity and atomic publication, never expose partial data |
| Lifecycle | `state/runs/<identity-hash>.sqlite` via ObjectStateStore, leased/fenced | No full lifecycle record | Connect artifacts to existing progress; explicit UV progress |
| Visible release | `weather/v1/families/cams/latest.json`, core+pollen staged together, previous retained | `weather/v1/uv/latest.json`, atomic CAS | Keep family contract; preserve old valid data on failed updates |
| Verification | Family storage readback already validates release/etag/manifests | No post-write readback | Verify public reader endpoint before a component is reported verified |
| Job result | Aggregate CAMS success; UV failure only logged separately | Generic HTTPError or claim/reconcile message | Persist distinct air/pollen/UV outcomes; pending is never success |

Existing reusable code: `retrieve_cams.py` validates exact request/job bindings and
completed download evidence; `reconcile_cams_job.py` uses GET-only, exact unique
request matching and a bounded time window; `cams_lifecycle.py` and
`ContractV1Publisher` already provide idempotent staging, leases and atomic family
release/readback. UV must reuse reconciliation safeguards, adapting its different
legacy record shape rather than passing an incompatible record to regional code.

Important limitation: a full first page of remote jobs or missing request metadata
is inconclusive, not permission to POST. Legacy UV intent creation time must be
obtained from reliable storage metadata before matching remote requests.

## Implementation / acceptance gates

1. Persist verified artifacts in the existing per-request namespace; authenticate
   bytes and request identity on restoration. No source download after a verified
   download checkpoint and no decode after a verified decoded checkpoint.
2. Resume or reconcile before submitting. Preserve create-only intent protection
   against two workers submitting the same request.
3. Persist separate component progress and final outcomes. Regional success cannot
   overwrite UV pending/failure. Scheduled retries may revisit the job but must skip
   already verified acquisition/processing.
4. Only validated content can be published. A storage publication is `published`,
   not `verified`, until the public reader returns the expected identity/content.
5. Fault tests: interruption at each durable boundary; accepted submission with lost
   response; ambiguous/multiple/incomplete reconciliation; download and decode reuse;
   publication retry/response loss; UV failure with regional success; stale readback.

## Delivery status

Map completed before implementation. Implementation, test and deployment results
will be recorded separately below. Nothing in this initial map asserts that a new
recovery version has been deployed or that today's cloud runs have succeeded.

### Implementation and local gates

Implemented in the existing CAMS worker and private state namespaces:

- Exact-match GET reconciliation shared by regional CAMS and UV. Legacy UV
  intent time is read from generation-pinned GCS metadata. Neither incomplete
  searches nor an intent without a job authorize another POST.
- Regional source/completion record and decoded/report bytes use bounded 4 MiB
  immutable chunks and a final atomic descriptor under the existing ADS prefix.
  Hashes bind request, job, source and catalog. The full publication validation
  gate still runs on restored bytes; the source is not decoded again.
- UV source and validated document persist under the original UV prefix. Failed
  publication resumes from these checkpoints; existing UV latest remains CAS.
- Component outcomes are append-only under `state/dispatch/cams/<slot>/outcomes/`.
  Air/pollen share a release but each has an explicit result; UV waiting/failure
  cannot produce aggregate completion. Both storage verification and public HTTP
  readback are required for `verified`.
- Worker retries use 60/180/300-second delays only while they fit a 480-second
  budget inside the unchanged 600-second task timeout. No new scheduler or task
  retry setting. Work beyond that budget remains persistent for the next existing
  window; no promise of an additional invocation between scheduler windows.
- Public readback checks the family pointer, both manifests (215 towns), a real
  Pordenone payload for each component, and stable pointer identity. All 215 town
  payloads remain verified by the existing storage publication gate. UV HTTP
  readback compares and validates the entire document. HTTP is not claimed to
  sample all 215 towns.

Separate local gates passed: 128 worker/state/UV/reconciliation checks; 97 final
artifact/restart/reconciliation checks; 38 full contract-publisher/artifact tests;
20 final outcome-classification/readback/diagnostic checks. These groups overlap
and must not be summed as a count of unique tests.

Known baseline test limitation: `test_cams_local_lifecycle` requires the absent
untracked `cams_fvg_payload_20260903.json` fixture (12 errors). These are not counted
as passes. New fault tests use self-contained fixtures; the existing contract
publisher suite passed. The expanded suite took 716.7 seconds on Windows.

Linux build and cloud deployment are separate gates; final evidence follows.

Linux preflight `13ca59a8-7721-460f-b1a0-520abfd3ba89` passed **183 tests** in
291.8 seconds; image digest `88820b84e49a37aa03b821f715ba4ea26f2afe239ab46e3b61a6dc5ede264ea7`.
This r1 image was NOT deployed. Final review added explicit classification of
legacy acquisition error reports and a materialized checkpoint: the 430 prepared
core/pollen contract documents and manifests are preserved alongside decoded
artifacts. A reboot can authenticate them and retry only publication without
repeating projection/materialization. The final r2 build must retest these changes.

Pre-deploy CAMS configuration: timeout 600 seconds, maxRetries 0, image
`8a61d900def7eb88e58a1a7b09e0486a9a9df92d4f56b1cc508fb9961638517b`.
Pod-spec SHA-256 excluding only image:
`06ce16c7af97bed61370efdcdc22a9d5a5044a49192067562f600dba73890cfe`.
The same digest must hold after deployment; only `pilot-cams` may be updated.

Materialized restart test passed on 430 actual synthetic contract documents
(215 core + 215 pollen), authenticating manifests and the validation attestation,
with the preparation function forbidden during restore. Runtime materialization
is no longer repeated after its durable checkpoint. Test elapsed time: 26.2 s.
The test helper is imported as a module to avoid unittest rediscovering an entire
already-tested TestCase class; an accidental duplicate local run was stopped.
The r2 Linux gate also exercises that broader suite because its source snapshot
preceded this test-discovery-only correction; production Python files are identical.

### Isolated deployment

Final Linux build `d825b96e-0ea7-49e5-8170-c04c20f70fef` succeeded:
**211 tests passed in 1082.118 seconds**, with external networking disabled for
the test container. The broader discovered suite is included in that count.
Published image digest:
`53ac1a35e8b7cd2cdc29d903754b945dbb62e1bc1aecb6e39caa0c658436b5ee`.

The naturally scheduled old-worker execution `pilot-cams-fhfll` finished at
2026-09-09 15:04:13 UTC before deployment. Only the `pilot-cams` image was updated
to the tested digest; the before/after pod-spec hash excluding image matched the
baseline above exactly. No scheduler, timeout, task retry, environment, service
account, Firebase, beta, reader or UI change was deployed.

After checking that no CAMS executions remained active, started one verification
execution, `pilot-cams-5xwsg`. Its actual component/readback results are a separate
gate and must not be inferred from the successful build or deployment.

### Real verification findings and correction

The first real run failed honestly rather than claiming aggregate success:

- Regional data from the old scheduled run were already current for
  `20260909T000000Z`, with previous `20260908T000000Z`.
- The new HTTP readback incorrectly used the per-provider `manifest_path`
  field for an atomic-family component. The real family contract uses the full
  `manifest_key`. Corrected this narrow check; the test now uses the production
  family descriptor builder, and rejects a provider-latest-shaped descriptor.
  43 focused readback/worker/UV tests passed locally. Linux r3 is a separate gate.
- UV reconciliation returned `uv_reconciliation_no_match`, persisted separately
  as manual review; aggregate `complete` remained false. No duplicate POST.

An independent HTTPS check then verified the real current/previous family,
both 215-town manifests and their hashes/lengths, and Pordenone payload hashes.
UV was still `2026-09-06T00:00:00Z`; this is NOT recorded as recovered.

Additional ADS GET-only diagnosis listed 10 recent jobs, including regional jobs
and two successful UV jobs created on September 6. No newer UV job appeared in
this page, which already crosses today's submission-intent time; a next-page
link exists for older jobs. This supports the no-match result for today's
intent window, not an inference about the HTTP error code or new POST authority.
The ADS secret was used only in process memory and was not printed or persisted.

### Final deployed evidence / open UV gate

Readback correction build `c49b3cdd-48ac-4719-b556-4458ba56822d` succeeded:
**130 targeted Linux tests passed in 119.161 seconds**. Deployed final image:
`6ace00417702087bc4a59e185dd30aa2ffda49f0320e1e2e4e9edfa294829b93`.
The exact same settings-invariant hash matched before and after the image update.

Final real execution `pilot-cams-8zqvn` (15:17:10 to 15:18:33 UTC) persisted:

- air: `verified`, `20260909T000000Z`, 215 municipalities;
- pollen: `verified`, same atomic release and public readback;
- UV: `manual_review`, `uv_reconciliation_no_match`;
- aggregate: `complete: false`, execution failed as intended for incomplete UV.

Family HTTP pointer SHA-256 verified by the worker:
`511e33244b11d0e5c27ead205d95582e20b1678851b4469228b54fffb9032cb2`.
The already-current regional family was verified without another acquisition.
Previous remains September 8; UV public latest remains September 6.

A separate unauthenticated catalogue-constraints GET confirmed that all requested
UV leads 0..71 for September 9 were available at verification time. This does not
prove they were available at the original submission time and does not establish
the original HTTP failure code. There is no saved matching remote job to resume.

**Open gate:** safely authorizing a replacement UV submission after a conclusive
empty reconciliation is not implemented by this delivery. No existing intent was
deleted/overwritten and no replacement POST was forced. The recovery infrastructure
is deployed, but UV service restoration and that no-match recovery path must NOT
be represented as completed. Tests prove accepted-job/artifact/publication recovery;
today's live run proves regional reuse/readback and explicit UV non-success.

## Authorized single replacement after conclusive empty reconciliation

The user subsequently authorized one automatic replacement per logical UV run,
only after complete error-free zero-match reconciliation, with the original
history intact and no third POST. This section supersedes the open authorization
gate above, not its historical deployment results.

Implementation reuses the same `state/uv/<day>/` namespace and `enrich` pipeline:

- `intent.json` remains byte-for-byte immutable. An append-only `history/<uuid>.json`
  stores its local identity, original timestamp, parameters, fingerprint and
  generation, final conclusive-empty status and bounded GET search evidence.
- The GET-only reconciler follows explicit pagination, validates returned IDs,
  dataset, times and request metadata. Limits (10 pages, 200 jobs, 45 s), HTTP
  errors, malformed pages, missing metadata or ambiguous results fail closed.
  The whole interval from original intent minus 5 s through observation time is
  searched. A same-request job newer than that snapshot also makes it inconclusive.
  Replacement additionally requires a closed 360-second original submission
  visibility window and fresh evidence (maximum 60 s old at claim creation).
- `canonical-attempt.json` is the single create-only arbitration point. An
  original known remote reference and a replacement claimant compete for that
  same object. Only an unambiguously successful replacement create plus readback
  grants the current invocation a POST; a lost claim ACK grants none.
- The selector binds the exact logical run, original generation/hash, request
  hash and history. Attempt 2 has a distinct UUID and cannot be replaced by a
  third attempt. Stale initial/replacement creators lose POST authority.
- Original artifacts keep their existing keys. Attempt 2 uses
  `attempts/replacement-1/{remote-selection.json,job.json,source.grib,decoded.json}`.
  The remote ID is durable before polling/download; restoration uses it directly.
  Every artifact/publication phase checks the immutable selector and canonical ID.
- ADS SDK 0.5.3 and its public OpenAPI expose no documented client attempt
  correlation field. After a lost response, one exact-request GET match can be
  adopted as the sole canonical remote, but its POST origin is explicitly stored
  as `unique_exact_match_origin_unconfirmed`, not falsely attributed. Multiple
  possible matches stop. A known reference is never switched.
- Late different references are recorded as superseded and ignored. Before a
  canonical remote exists, a late original is only a neutral observation; this
  avoids racing a superseded mark against selection of that very same ID.
  Same-ID observations never supersede the canonical reference itself.
- A conclusive empty attempt-2 reconciliation after its visibility window reports
  `uv_replacement_exhausted_no_match`; there is no automatic third submission.
  Incomplete/transient reconciliation stays distinct and cannot authorize POST.

No change to UI, frequencies, Firebase, beta, regional air/pollen release or IAM.
Existing `allow_submit=False` still forbids a replacement POST.

Offline gates: 47 reconciliation tests including actual pinned SDK GET pagination;
17 replacement fault tests including two-thread claims, lost claim/POST/reference
responses, late original before/during/after replacement, publication-only retry,
unconfirmed-origin canonical choice and concurrent canonical/superseded marking.
The combined prior gate passed 106 tests; the final focused gate passed 68 tests.
These counts overlap. Linux build/deployment/live readback remain separate gates.

Primary API references inspected read-only for supported correlation fields:
https://ecmwf.github.io/ecmwf-datastores-client/_api/datastores/Client.html
https://ads.atmosphere.copernicus.eu/api/retrieve/v1/openapi.json

### Single-replacement deployment gate

Implementation commit: `c4354ac`.
Linux build `020ccee4-de10-4d93-822f-87d447715f12` passed **165 tests in 72.916 s**
with network disabled. Deployed `pilot-cams` image digest:
`da7cfe7bdef04967ad5209ef6f1e9d5acb1ea5e75578b812e4b187c19126cda7`.
The settings hash excluding image remains exactly
`06ce16c7af97bed61370efdcdc22a9d5a5044a49192067562f600dba73890cfe`.
No obsolete worker was running at deployment. Verification execution:
`pilot-cams-qjxzt`; its live outcome/readback is recorded separately below.

Original September 9 UV intent baseline before this execution:
generation `1788948060206941`, SHA-256
`75ad6e63057be58cb802f0932944bdee7e7b7c8fd0d3cf6ac0b2b478b9381b2c`.
Both must remain unchanged after the replacement.

### Live replacement result: UV recovery gate closed

Execution `pilot-cams-qjxzt` succeeded at **2026-09-09 15:53:11 UTC** (17:53 CEST).
Final persisted result: `complete: true`; air, pollen and UV each `verified`.

Actual evidence, rather than inferred from the job exit code:

- Complete GET search at 15:51:55 UTC covered the original intent interval
  from 10:00:55.210000 UTC, checked 2 jobs on 1 page, crossed the lower cutoff
  and returned zero matches. Its full evidence and original request snapshot
  are preserved in immutable history, authenticated by the selector.
- Replacement attempt UUID `70401617-7550-436a-8c91-2393f9cdd337` belongs to
  `20260909T000000Z`. One replacement submission was logged. ADS accepted it;
  the remote selection has origin `post_response` and its ID agrees with the
  persistent compatibility job record before polling/download.
- The existing worker retried that same reference after 60 seconds, then
  checkpointed source, validated the document, published, and verified HTTP.
  Regional air/pollen were already verified and were not reacquired.
- Independent public endpoint readback validated **72 real hours, 35 grid points**,
  from September 9 00:00 UTC to September 11 23:00 UTC. Two HTTP reads returned
  stable bytes matching the worker's storage/readback SHA-256:
  `cd7aa3b46af3caddaf583f205c5605849e56652915471ed1a017731230bde906`.
- Original intent SHA-256 and generation remained exactly the baseline above.
  Family CAMS latest remains September 9, previous September 8.

This closes the earlier UV no-match/restoration gate. Concurrent replacement,
lost responses, late-original classification and no-third-POST behavior were
fault-tested offline; the real execution verifies one accepted replacement and
the actual endpoint consumed by the pilot, not a simulated publication.
