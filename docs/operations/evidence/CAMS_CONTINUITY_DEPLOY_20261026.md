# Ricevuta del deploy CAMS — 26 ottobre 2026

Dati riepilogativi pubblicabili; configurazioni e log completi restano nelle evidenze locali private.

```json
{
  "source_commit": "026d5ca064fdbeebb30403b458929cd6ea1e79c0",
  "build_id": "5e8d4abe-12cf-4871-8f6a-3e205595454f",
  "image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e",
  "rollback_image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:40f64c406144128b3f2768b8eaaaf82c43a0c2cb03855ee45276ee76d4d0d795",
  "deployment": {
    "time": "2026-10-26T10:57:09.647802+00:00",
    "commit": "026d5ca064fdbeebb30403b458929cd6ea1e79c0",
    "image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e",
    "rollback_image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:40f64c406144128b3f2768b8eaaaf82c43a0c2cb03855ee45276ee76d4d0d795",
    "only_image_and_continuity_flag_changed": true,
    "scheduler_unchanged": true,
    "other_job_templates_unchanged": 12,
    "http_and_all_services_unchanged": 6,
    "sponsors_disabled": true,
    "no_manual_execution": true,
    "new_family_verified": false
  },
  "policy": {
    "time": "2026-10-26T10:57:18.351631+00:00",
    "key": "cams-failures",
    "only_approved_fields_changed": true,
    "other_policies_unchanged": 22,
    "notification_prompts": [
      "OPENED"
    ],
    "window_seconds": 28800,
    "failure_count_threshold": 2,
    "notification_channels_unchanged": true,
    "data_recovery_verified": false
  },
  "http": {
    "source_run_id": "20261026T000000Z",
    "payloads_verified": 4,
    "all_municipalities_verified": false,
    "native_and_web_cors_sample": true,
    "current_hour_samples_verified": true,
    "new_family_verified": false
  },
  "ordinary_targets": {
    "first": {
      "scheduled": "2026-10-26T11:00:00+00:00",
      "image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e",
      "expected_continuity": "legacy_no_grant",
      "state": "pending"
    },
    "new-family": {
      "scheduled": "2026-10-27T09:00:00+00:00",
      "image": "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e",
      "minimum_source_run_id": "20261027T000000Z",
      "state": "pending"
    },
    "automation_created": false,
    "events_followup": "deleted by owner request"
  },
  "evidence": [
    {
      "file": "package.json",
      "sha256": "366ed1af7f43469660efbef65f05ef346ca41924021d44fc9d878482e41d8f69"
    },
    {
      "file": "source-inventory.json",
      "sha256": "e4aaa95be8bdb647becd003ff74a1278fc03f4b46a686ee4e5401862412fb2af"
    },
    {
      "file": "main-ci.json",
      "sha256": "b0ecb01677883639201fa062e714ff7935b751b49ea9556b3d243a76a25aea14"
    },
    {
      "file": "build-submission.json",
      "sha256": "033cb6c285e30daaf9bb59662a17b5fb31c7cac400386b4201ee835faa21afb5"
    },
    {
      "file": "build-status.json",
      "sha256": "da31df26008ed2221f7120f0dad6c2b39371e1a55dc6985b8d35f2dbdbf50ac5"
    },
    {
      "file": "candidate-image.json",
      "sha256": "99f30e06866de18ed1898b4be9f8f759d6cd47bbaf6621b4759953d7970a90e7"
    },
    {
      "file": "preflight.json",
      "sha256": "fa2219c07b2c44341c5cd6e82d41d9cf8f16720a0b31dea8ebaa7387260a4dfc"
    },
    {
      "file": "http-compatibility.json",
      "sha256": "0687147c946d64f14c4662a140e8aa68e0302b0b1c6d78288cff8669d1072008"
    },
    {
      "file": "rollback-compatibility.json",
      "sha256": "0a78eaebe37d6cc75221f18430293947b3047c5545c1e273c4e18449bbc40969"
    },
    {
      "file": "deployment-checks.json",
      "sha256": "e48587681d76774bbfc898a0aaf6a5de498d6b6b23719db980a2cae93a7d1baa"
    },
    {
      "file": "policy-verification.json",
      "sha256": "0972500646883dfcb92048aa8cdb783492a5e318b62758c85c0ebf2b217f0789"
    },
    {
      "file": "http-before-summary.json",
      "sha256": "2d681fa6d42235f66233c37732f5012a23661a7bf22b2f512834ebcd2dbde7c8"
    },
    {
      "file": "http-after-summary.json",
      "sha256": "7b3d28867b21392586803bc113bbf68ebea911098b78f1f9422999970d0a8043"
    },
    {
      "file": "ordinary-targets.json",
      "sha256": "75cfa357c89c78b4f6a5906ca74e16117656d97e24efa1cd3983ad76b5fad447"
    }
  ],
  "scripts": [
    {
      "file": "check_rollback.py",
      "sha256": "59443ba54032f1b93f7ece7dc274d23dd501d97a917756e4d20ee123a35c3428"
    },
    {
      "file": "common.py",
      "sha256": "087fa008939cb15b2b7dc8cf0f17361ed8cb8cb77282d1e0068b884ba8772626"
    },
    {
      "file": "finalize.py",
      "sha256": "f4c071840c001b654c8fa4696a58c66365ba5a439ef626db02909189e149fa31"
    },
    {
      "file": "operate.py",
      "sha256": "6eecbb20e762794c5205c044f07992b54f3e9bcd18dfe5b6cb99c16180f6bcd7"
    },
    {
      "file": "preflight.py",
      "sha256": "821166f20368f38eb912f37bb6a696e2aca635fe04211d8e6d01ed70e4c214fb"
    },
    {
      "file": "read_rollback_code.py",
      "sha256": "eb5c84259f8ae952f02296415f758d5dbc76a41b3037ad1564f7d588e8bf0c3c"
    },
    {
      "file": "verify_http.py",
      "sha256": "388915aa933e620092917c899bac42b6e7f3d287f0793dc5e3ee958f741bfa1f"
    },
    {
      "file": "verify_ordinary.py",
      "sha256": "ace26c77c5a2b0c4bbf9dbc7e28f841cc86cdea5b07a0cb0b58bc0277eb3b8d4"
    }
  ],
  "container_tests": {
    "count": 433,
    "seconds": 209.468,
    "result": "OK",
    "network": "none"
  }
}
```
