"""Small synthetic public-metadata fixtures for offline CAMS unit tests."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import cams_request_plan as cams


TEST_DATE = "2026-09-04"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def public_metadata_documents(*, run_date=TEST_DATE, leads=None):
    leads = list(cams.EXPECTED_LEADS if leads is None else map(str, leads))
    form = [
        {"name": "variable", "type": "StringListWidget", "details": {"values": list(cams.EXPECTED_VARIABLE_IDS)}},
        {"name": "model", "type": "StringListWidget", "details": {"values": ["ensemble", "chimere"]}},
        {"name": "level", "type": "StringListWidget", "details": {"values": ["0", "50"]}},
        {"name": "date", "type": "DateRangeWidget", "details": {"minStart": "2023-08-30", "maxEnd": run_date}},
        {"name": "type", "type": "StringListWidget", "details": {"values": ["analysis", "forecast"]}},
        {"name": "time", "type": "StringListWidget", "details": {"values": ["00:00", "01:00"]}},
        {"name": "leadtime_hour", "type": "StringListWidget", "details": {"values": list(cams.EXPECTED_LEADS)}},
        {"name": "data_format", "type": "StringChoiceWidget", "details": {"values": ["grib", "netcdf_zip"]}},
        {"name": "area", "type": "GeographicExtentWidget", "details": {"range": {"n": 90, "w": -180, "s": -90, "e": 180}}},
        {"name": "licences", "type": "LicenceWidget", "details": {"licences": [{"id": "cc-by", "spdx_identifier": cams.LICENSE_IDENTIFIER, "attachment_url": cams.LICENSE_URL}]}},
    ]
    constraints = [{
        "date": [run_date],
        "leadtime_hour": leads,
        "level": ["0"],
        "model": ["ensemble"],
        "time": ["00:00"],
        "type": ["forecast"],
        "variable": list(cams.EXPECTED_VARIABLE_IDS),
    }]
    form_raw = encoded(form)
    constraints_raw = encoded(constraints)
    form_hash = hashlib.sha256(form_raw).hexdigest()
    constraints_hash = hashlib.sha256(constraints_raw).hexdigest()
    form_url = cams.OBJECT_STORE_PREFIX.join(
        (f"https://{cams.OBJECT_STORE_HOST}:443", f"form_{form_hash}.json")
    )
    constraints_url = cams.OBJECT_STORE_PREFIX.join(
        (f"https://{cams.OBJECT_STORE_HOST}:443", f"constraints_{constraints_hash}.json")
    )
    catalogue = {
        "id": cams.DATASET,
        "license": cams.LICENSE_IDENTIFIER,
        "sci:doi": "10.24381/a4005cee",
        "extent": {"temporal": {"interval": [["2023-08-30T00:00:00Z", f"{run_date}T00:00:00Z"]]}},
        "cads:sanity_check": {"status": "available", "timestamp": f"{run_date}T06:20:26Z"},
        "links": [
            {"rel": "license", "href": cams.LICENSE_URL, "id": "cc-by"},
            {"rel": "form", "href": form_url, "type": "application/json"},
            {"rel": "constraints", "href": constraints_url, "type": "application/json"},
        ],
    }
    catalogue_raw = encoded(catalogue)
    return {
        "catalogue": catalogue,
        "catalogue_raw": catalogue_raw,
        "catalogue_sha256": hashlib.sha256(catalogue_raw).hexdigest(),
        "form": form,
        "form_raw": form_raw,
        "form_url": form_url,
        "form_sha256": form_hash,
        "constraints": constraints,
        "constraints_raw": constraints_raw,
        "constraints_url": constraints_url,
        "constraints_sha256": constraints_hash,
    }


def valid_evidence(*, run_date=TEST_DATE, area=cams.DEFAULT_AREA):
    documents = public_metadata_documents(run_date=run_date)
    return cams.validate_public_metadata(
        run_date,
        area=area,
        catalogue=documents["catalogue"],
        catalogue_url=cams.CATALOGUE_URL,
        catalogue_sha256=documents["catalogue_sha256"],
        form=documents["form"],
        form_url=documents["form_url"],
        form_sha256=documents["form_sha256"],
        constraints=documents["constraints"],
        constraints_url=documents["constraints_url"],
        constraints_sha256=documents["constraints_sha256"],
        checked_at_utc=f"{run_date}T08:00:00Z",
    )


def valid_plan(*, run_date=TEST_DATE, area=cams.DEFAULT_AREA, data_format="grib"):
    return cams.build_request_plan(
        run_date,
        metadata_evidence=valid_evidence(run_date=run_date, area=area),
        area=area,
        data_format=data_format,
    )


def write_valid_plan(directory, *, run_date=TEST_DATE, area=cams.DEFAULT_AREA, data_format="grib"):
    plan = valid_plan(run_date=run_date, area=area, data_format=data_format)
    raw = cams.encode_request_plan(plan)
    path = Path(directory) / f"cams-request-plan-{run_date}.json"
    path.write_bytes(raw)
    return path, plan, raw, hashlib.sha256(raw).hexdigest()


class FakeCookies:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class FakeResponse:
    def __init__(self, raw, *, status=200, content_type="application/json", history=None):
        self.content = raw
        self.status_code = status
        self.history = [] if history is None else history
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(raw)),
            "Content-Encoding": "identity",
        }
        self.closed = False

    def close(self):
        self.closed = True


class FakePublicSession:
    def __init__(self, documents=None):
        self.documents = documents or public_metadata_documents()
        self.cookies = FakeCookies()
        self.trust_env = True
        self.calls = []
        self.closed = False
        self.responses = {
            cams.CATALOGUE_URL: FakeResponse(self.documents["catalogue_raw"]),
            self.documents["form_url"]: FakeResponse(self.documents["form_raw"]),
            self.documents["constraints_url"]: FakeResponse(self.documents["constraints_raw"]),
        }

    def get(self, url, **kwargs):
        self.calls.append((url, deepcopy(kwargs)))
        return self.responses[url]

    def close(self):
        self.closed = True
