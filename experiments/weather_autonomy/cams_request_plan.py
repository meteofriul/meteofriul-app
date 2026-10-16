"""Create an immutable CAMS request plan from anonymous public ADS metadata.

This module performs GET requests only against a small allow-list of official
HTTPS endpoints.  It never reads ADS credentials, accepts terms, submits a
retrieval, downloads forecast data, or mutates an existing plan.  A plan is
created only after the catalogue, form and constraints select the exact
28-variable, surface ensemble forecast for lead hours 0..96. Retrieval and
decode remain separate gates before publication.
"""

import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests

from local_pipeline.operational_diagnostics import attach_error_fields, emit, error_fields


DATASET = "cams-europe-air-quality-forecasts"
DEFAULT_AREA = (46.7, 12.2, 45.5, 14.0)  # North, West, South, East.
CATALOGUE_URL = (
    "https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/"
    + DATASET
)
LICENSE_IDENTIFIER = "CC-BY-4.0"
LICENSE_URL = "https://spdx.org/licenses/CC-BY-4.0"
ADS_DOCUMENTATION_URL = (
    "https://confluence.ecmwf.int/spaces/CKB/pages/202163324/"
    "Atmosphere+Data+Store+ADS+documentation"
)
DOCUMENTED_FIELD_LIMIT = 5000
MAX_PUBLIC_DOCUMENT_BYTES = 8 * 1024 * 1024
OBJECT_STORE_HOST = "object-store.os-api.cci2.ecmwf.int"
OBJECT_STORE_PREFIX = f"/cci2-prod-catalogue/resources/{DATASET}/"
PLAN_SCHEMA_VERSION = 2

_VARIABLES = (
    ("alder_pollen", "Alder pollen"),
    ("ammonia", "Ammonia"),
    ("birch_pollen", "Birch pollen"),
    ("carbon_monoxide", "Carbon monoxide"),
    ("formaldehyde", "Formaldehyde"),
    ("glyoxal", "Glyoxal"),
    ("grass_pollen", "Grass pollen"),
    ("mugwort_pollen", "Mugwort pollen"),
    ("nitrogen_dioxide", "Nitrogen dioxide"),
    ("nitrogen_monoxide", "Nitrogen monoxide"),
    ("non_methane_vocs", "Non-methane volatile organic compounds (VOCs)"),
    ("olive_pollen", "Olive pollen"),
    ("ozone", "Ozone"),
    ("particulate_matter_2.5um", "Particulate matter < 2.5 µm (PM2.5)"),
    ("pm2.5_ammonium", "PM2.5, ammonium"),
    ("pm2.5_nitrate", "PM2.5, nitrate"),
    ("residential_elementary_carbon", "PM2.5, residential elementary carbon"),
    ("secondary_inorganic_aerosol", "PM2.5, secondary inorganic aerosol"),
    ("pm2.5_sulphate", "PM2.5, sulphate"),
    ("total_elementary_carbon", "PM2.5, total elementary carbon"),
    ("pm2.5_total_organic_matter", "PM2.5, total organic matter"),
    ("particulate_matter_10um", "Particulate matter < 10 µm (PM10)"),
    ("dust", "PM10, dust"),
    ("pm10_sea_salt_dry", "PM10, sea salt (dry)"),
    ("pm10_wildfires", "PM10, wildfires"),
    ("peroxyacyl_nitrates", "Peroxyacyl nitrates"),
    ("ragweed_pollen", "Ragweed pollen"),
    ("sulphur_dioxide", "Sulphur dioxide"),
)
_VALIDATED_VARIABLES = frozenset(
    (
        "nitrogen_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "particulate_matter_2.5um",
        "particulate_matter_10um",
        "dust",
    )
)
EXPECTED_VARIABLE_IDS = tuple(sorted(name for name, _ in _VARIABLES))
EXPECTED_LEADS = tuple(str(hour) for hour in range(97))
_CONSTRAINT_KEYS = frozenset(
    ("date", "leadtime_hour", "level", "model", "time", "type", "variable")
)
_PLAN_TOP_KEYS = frozenset(
    (
        "schema_version",
        "kind",
        "status",
        "dataset",
        "run_date",
        "retrieval_performed",
        "credentials_read",
        "terms_accepted",
        "scope",
        "sources",
        "metadata_evidence",
        "licence",
        "variables",
        "counts",
        "request_groups",
        "cadence",
        "measurements",
        "gaps_not_filled_by_this_dataset",
        "limitations",
    )
)


class PublicMetadataError(ValueError):
    """Public metadata is unsafe, malformed, ambiguous or inconsistent."""


class PublicMetadataUnavailable(PublicMetadataError):
    """The requested complete run is not yet represented in constraints."""


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PublicMetadataError("Public JSON contains a duplicate key")
        result[key] = value
    return result


def strict_json_loads(raw):
    if not isinstance(raw, (bytes, bytearray)):
        raise PublicMetadataError("Expected bounded JSON bytes")
    try:
        def reject_constant(_value):
            raise PublicMetadataError("JSON non-finite constants are forbidden")

        return json.loads(
            bytes(raw).decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=reject_constant,
        )
    except PublicMetadataError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicMetadataError("Public metadata is not strict UTF-8 JSON") from None


def canonical_date(value):
    if type(value) is not str:
        raise PublicMetadataError("Run date must be an explicit ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise PublicMetadataError("Run date must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise PublicMetadataError("Run date must be canonical YYYY-MM-DD")
    return value


def canonical_utc(value):
    if type(value) is not str:
        raise PublicMetadataError("Metadata timestamp must be an ISO UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PublicMetadataError("Metadata timestamp is invalid") from None
    if parsed.tzinfo is None:
        raise PublicMetadataError("Metadata timestamp must carry a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_area(area):
    if not isinstance(area, (tuple, list)) or len(area) != 4:
        raise PublicMetadataError("Area must contain North, West, South, East")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in area
    ):
        raise PublicMetadataError("Area bounds must be finite numbers")
    north, west, south, east = map(float, area)
    if not 45.0 <= south < north <= 47.2 or not 11.8 <= west < east <= 14.5:
        raise PublicMetadataError(
            "Area must remain within the bounded Friuli Venezia Giulia pilot region"
        )
    return [north, west, south, east]


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PublicMetadataError("Metadata SHA-256 must be 64 lowercase hex characters")
    return value


def _safe_resource_url(url, kind):
    if type(url) is not str:
        raise PublicMetadataError("Public metadata link is not a string")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise PublicMetadataError("Public metadata link has an invalid port") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname != OBJECT_STORE_HOST
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise PublicMetadataError("Public metadata link is outside the approved HTTPS host")
    filename = parsed.path.removeprefix(OBJECT_STORE_PREFIX)
    if parsed.path != OBJECT_STORE_PREFIX + filename:
        raise PublicMetadataError("Public metadata link has an unapproved path")
    match = re.fullmatch(rf"{re.escape(kind)}_([0-9a-f]{{64}})\.json", filename)
    if match is None:
        raise PublicMetadataError("Public metadata filename is not content-addressed")
    return match.group(1)


def _values(field, name):
    if not isinstance(field, dict) or field.get("name") != name:
        raise PublicMetadataError(f"Public form field {name} is malformed")
    details = field.get("details")
    values = details.get("values") if isinstance(details, dict) else None
    if (
        not isinstance(values, list)
        or any(type(value) is not str for value in values)
        or len(values) != len(set(values))
    ):
        raise PublicMetadataError(f"Public form values for {name} are malformed")
    return values


def _exact_strings(value, expected, label):
    if (
        not isinstance(value, list)
        or any(type(item) is not str for item in value)
        or len(value) != len(set(value))
        or set(value) != set(expected)
    ):
        raise PublicMetadataError(f"Public metadata has unexpected {label}")


def _date_token_covers(token, run_date):
    if type(token) is not str:
        raise PublicMetadataError("Constraint date is not a string")
    pieces = token.split("/")
    if len(pieces) not in (1, 2):
        raise PublicMetadataError("Constraint date is not an ISO date or range")
    start = canonical_date(pieces[0])
    end = canonical_date(pieces[-1])
    if start > end:
        raise PublicMetadataError("Constraint date range is inverted")
    return start <= run_date <= end


def _date_values_cover(values, run_date):
    if (
        not isinstance(values, list)
        or not values
        or any(type(value) is not str for value in values)
        or len(values) != len(set(values))
    ):
        raise PublicMetadataError("Constraint dates are malformed")
    return any(_date_token_covers(value, run_date) for value in values)


def _one_link(catalogue, relation):
    links = catalogue.get("links")
    if not isinstance(links, list):
        raise PublicMetadataError("Catalogue links are malformed")
    matches = [link for link in links if isinstance(link, dict) and link.get("rel") == relation]
    if len(matches) != 1 or matches[0].get("type") != "application/json":
        raise PublicMetadataError(f"Catalogue must expose exactly one JSON {relation} link")
    return matches[0].get("href")


def _validate_catalogue(catalogue, run_date):
    if not isinstance(catalogue, dict) or catalogue.get("id") != DATASET:
        raise PublicMetadataError("Catalogue dataset identifier does not match")
    if catalogue.get("license") != LICENSE_IDENTIFIER:
        raise PublicMetadataError("Catalogue licence is not CC-BY-4.0")
    if catalogue.get("sci:doi") != "10.24381/a4005cee":
        raise PublicMetadataError("Catalogue DOI does not match the approved dataset")
    sanity = catalogue.get("cads:sanity_check")
    if not isinstance(sanity, dict) or sanity.get("status") not in {"available", "down"}:
        raise attach_error_fields(
            PublicMetadataUnavailable("CAMS catalogue sanity status is not available"),
            reason_code="catalogue_sanity_unavailable",
            retryable=True,
        )
    # ADS can report a failing catalogue sanity check while the exact forecast
    # remains retrievable. An explicit disabled reason is different: do not
    # submit a request for a dataset that the provider disabled.
    if catalogue.get("cads:disabled_reason") is not None:
        raise attach_error_fields(
            PublicMetadataUnavailable("CAMS catalogue is explicitly disabled"),
            reason_code="catalogue_disabled",
            retryable=True,
        )
    sanity_status = sanity["status"]
    sanity_timestamp = canonical_utc(sanity.get("timestamp"))

    intervals = catalogue.get("extent", {}).get("temporal", {}).get("interval")
    if not isinstance(intervals, list) or not intervals:
        raise PublicMetadataError("Catalogue temporal extent is missing")
    covered = False
    for interval in intervals:
        if not isinstance(interval, list) or len(interval) != 2:
            raise PublicMetadataError("Catalogue temporal interval is malformed")
        start = canonical_utc(interval[0])[:10]
        end = canonical_utc(interval[1])[:10]
        if start <= run_date <= end:
            covered = True
    if not covered:
        error = PublicMetadataUnavailable("Requested CAMS date is outside catalogue coverage")
        attach_error_fields(error, reason_code="catalogue_date_unavailable", run_date=run_date)
        raise error

    links = catalogue.get("links")
    if not isinstance(links, list):
        raise PublicMetadataError("Catalogue links are malformed")
    licence_links = [
        link
        for link in links
        if isinstance(link, dict) and link.get("rel") == "license"
    ]
    if (
        len(licence_links) != 1
        or licence_links[0].get("href") != LICENSE_URL
        or licence_links[0].get("id") != "cc-by"
    ):
        raise PublicMetadataError("Catalogue CC-BY-4.0 link does not match")
    form_url = _one_link(catalogue, "form")
    constraints_url = _one_link(catalogue, "constraints")
    _safe_resource_url(form_url, "form")
    _safe_resource_url(constraints_url, "constraints")
    return form_url, constraints_url, sanity_status, sanity_timestamp


def _validate_form(form, run_date, area):
    if not isinstance(form, list):
        raise PublicMetadataError("Public form must be a JSON array")
    named = {}
    for field in form:
        if not isinstance(field, dict):
            raise PublicMetadataError("Public form contains a malformed field")
        name = field.get("name")
        if type(name) is str:
            if name in named:
                raise PublicMetadataError("Public form contains a duplicate field")
            named[name] = field

    _exact_strings(_values(named.get("variable"), "variable"), EXPECTED_VARIABLE_IDS, "variables")
    if "ensemble" not in _values(named.get("model"), "model"):
        raise PublicMetadataError("Public form does not expose the ensemble")
    if "0" not in _values(named.get("level"), "level"):
        raise PublicMetadataError("Public form does not expose surface level 0")
    if "forecast" not in _values(named.get("type"), "type"):
        raise PublicMetadataError("Public form does not expose forecast type")
    if "00:00" not in _values(named.get("time"), "time"):
        raise PublicMetadataError("Public form does not expose base time 00:00")
    _exact_strings(_values(named.get("leadtime_hour"), "leadtime_hour"), EXPECTED_LEADS, "lead hours")
    formats = _values(named.get("data_format"), "data_format")
    if set(formats) != {"grib", "netcdf_zip"}:
        raise PublicMetadataError("Public form formats changed")

    date_field = named.get("date")
    if not isinstance(date_field, dict) or date_field.get("type") != "DateRangeWidget":
        raise PublicMetadataError("Public form date field changed")
    details = date_field.get("details")
    if not isinstance(details, dict):
        raise PublicMetadataError("Public form date range is malformed")
    minimum = canonical_date(details.get("minStart"))
    maximum = canonical_date(details.get("maxEnd"))
    if minimum > maximum:
        raise PublicMetadataError("Public form date range is inverted")
    if not minimum <= run_date <= maximum:
        error = PublicMetadataUnavailable("Requested CAMS date is outside the public form")
        attach_error_fields(error, reason_code="form_date_unavailable", run_date=run_date)
        raise error

    area_field = named.get("area")
    if not isinstance(area_field, dict) or area_field.get("type") != "GeographicExtentWidget":
        raise PublicMetadataError("Public form geographic field changed")
    area_range = area_field.get("details", {}).get("range")
    if not isinstance(area_range, dict):
        raise PublicMetadataError("Public form geographic range is malformed")
    try:
        range_values = {key: float(area_range[key]) for key in ("n", "w", "s", "e")}
    except (KeyError, TypeError, ValueError):
        raise PublicMetadataError("Public form geographic range is malformed") from None
    north, west, south, east = area
    if not (
        range_values["s"] <= south < north <= range_values["n"]
        and range_values["w"] <= west < east <= range_values["e"]
    ):
        raise PublicMetadataError("Requested area is outside the public form range")

    licence_field = named.get("licences")
    licences = (
        licence_field.get("details", {}).get("licences")
        if isinstance(licence_field, dict)
        else None
    )
    if not isinstance(licences, list) or len(licences) != 1:
        raise PublicMetadataError("Public form licence widget changed")
    licence = licences[0]
    if (
        not isinstance(licence, dict)
        or licence.get("id") != "cc-by"
        or licence.get("spdx_identifier") != LICENSE_IDENTIFIER
        or licence.get("attachment_url") != LICENSE_URL
    ):
        raise PublicMetadataError("Public form licence is not exact CC-BY-4.0")


def _validate_constraints(constraints, run_date, *, metadata_sha256=None):
    diagnostic = {
        "provider": "cams",
        "stage": "constraints_validation",
        "run_date": run_date,
        "metadata_sha256": metadata_sha256,
        "constraints_rows": len(constraints) if isinstance(constraints, list) else 0,
        "date_rows": 0,
        "compatible_rows": 0,
        "missing_model_rows": 0,
        "missing_level_rows": 0,
        "missing_type_rows": 0,
        "missing_time_rows": 0,
        "missing_variable_rows": 0,
        "missing_variable_count": 0,
    }

    def failed(error, reason):
        # Aggregate only counts and controlled reason codes. Never serialize a
        # constraint row, date token, variable name or public response body.
        attach_error_fields(error, **diagnostic, reason_code=reason, validation_status="failed")
        emit("weather_public_metadata_validation", **{
            **error_fields(error), "status": "failed",
            "severity": "WARNING" if isinstance(error, PublicMetadataUnavailable) else "ERROR",
        })
        return error

    if not isinstance(constraints, list):
        raise failed(PublicMetadataError("Public constraints must be a JSON array"), "constraints_not_array")
    compatible = []
    for row in constraints:
        if not isinstance(row, dict) or set(row) != _CONSTRAINT_KEYS:
            raise failed(PublicMetadataError("Public constraints contain a malformed row"), "constraints_malformed_row")
        try:
            date_covered = _date_values_cover(row["date"], run_date)
        except PublicMetadataError as error:
            raise failed(error, "constraints_malformed_dates")
        if not date_covered:
            continue
        diagnostic["date_rows"] += 1
        for key in ("model", "level", "type", "time", "variable", "leadtime_hour"):
            values = row[key]
            if (
                not isinstance(values, list)
                or any(type(value) is not str for value in values)
                or len(values) != len(set(values))
            ):
                raise failed(PublicMetadataError("Public constraints contain malformed selections"),
                             "constraints_malformed_selections")
        for key, expected in (("model", {"ensemble"}), ("level", {"0"}),
                              ("type", {"forecast"}), ("time", {"00:00"}),
                              ("variable", set(EXPECTED_VARIABLE_IDS))):
            missing = expected - set(row[key])
            diagnostic[f"missing_{key}_rows"] += bool(missing)
            if key == "variable":
                diagnostic["missing_variable_count"] = max(diagnostic["missing_variable_count"], len(missing))
        # A constraint row describes selectable values, not a mandatory request
        # containing every listed value.  The live ADS row can therefore expose
        # all surface models while our explicit request selects only ensemble.
        # Accept only rows selecting every requested singleton and some variables;
        # the eventual plan still emits the exact narrow 28x97 request below.
        requested_subset_is_selectable = (
            {"ensemble"} <= set(row["model"])
            and {"0"} <= set(row["level"])
            and {"forecast"} <= set(row["type"])
            and {"00:00"} <= set(row["time"])
            and bool(set(EXPECTED_VARIABLE_IDS) & set(row["variable"]))
        )
        if requested_subset_is_selectable:
            compatible.append(row)
            diagnostic["compatible_rows"] += 1
    # ADS may partition air and pollen into disjoint variable rows. Each row
    # must independently select the same model/date/level/time/type and all
    # 97 leads; a union of unrelated dimensions must never imply availability.
    covered = set()
    overlapping = False
    for row in compatible:
        requested_variables = set(row["variable"]) & set(EXPECTED_VARIABLE_IDS)
        overlapping |= bool(covered & requested_variables)
        covered.update(requested_variables)
    if overlapping or covered != set(EXPECTED_VARIABLE_IDS):
        reason = ("constraints_multiple_compatible_rows" if overlapping else
                  "constraints_no_date_rows" if diagnostic["date_rows"] == 0 else
                  "constraints_no_compatible_rows")
        raise failed(PublicMetadataUnavailable(
            "CAMS constraints do not contain unambiguous complete surface ensemble coverage"
        ), reason)
    available_requested_leads = set(EXPECTED_LEADS)
    for row in compatible:
        available_requested_leads.intersection_update(row["leadtime_hour"])
    numeric = [int(value) for value in available_requested_leads if value.isdigit()]
    maximum = max(numeric) if numeric else None
    diagnostic.update(leadcount=len(available_requested_leads), maxlead=maximum,
                      missing_lead_count=len(set(EXPECTED_LEADS) - available_requested_leads))
    if available_requested_leads != set(EXPECTED_LEADS):
        raise failed(PublicMetadataUnavailable(
            "CAMS run is incomplete: "
            f"{len(available_requested_leads)}/97 lead hours, maximum={maximum}"
        ), "constraints_incomplete_leads")
    emit("weather_public_metadata_validation", **diagnostic,
         status="passed", reason_code="constraints_validated", validation_status="passed")
    return {
        "date": list(compatible[0]["date"]) if len(compatible) == 1 else [run_date],
        "model": ["ensemble"],
        "level": ["0"],
        "type": ["forecast"],
        "time": ["00:00"],
        "leadtime_hour": list(EXPECTED_LEADS),
        "variable": list(EXPECTED_VARIABLE_IDS),
    }


def validate_public_metadata(
    run_date,
    *,
    area,
    catalogue,
    catalogue_url,
    catalogue_sha256,
    form,
    form_url,
    form_sha256,
    constraints,
    constraints_url,
    constraints_sha256,
    checked_at_utc,
):
    """Validate decoded official documents and return compact immutable evidence."""
    run_date = canonical_date(run_date)
    area = canonical_area(area)
    if catalogue_url != CATALOGUE_URL:
        raise PublicMetadataError("Catalogue URL does not match the approved dataset")
    form_link, constraints_link, sanity_status, sanity_timestamp = _validate_catalogue(catalogue, run_date)
    if form_url != form_link or constraints_url != constraints_link:
        raise PublicMetadataError("Fetched metadata URLs differ from catalogue links")
    if _safe_resource_url(form_url, "form") != _canonical_sha256(form_sha256):
        raise PublicMetadataError("Form URL hash does not match its response bytes")
    if _safe_resource_url(constraints_url, "constraints") != _canonical_sha256(constraints_sha256):
        raise PublicMetadataError("Constraints URL hash does not match its response bytes")
    _validate_form(form, run_date, area)
    selection = _validate_constraints(constraints, run_date, metadata_sha256=constraints_sha256)
    if sanity_status == "down":
        emit(
            "weather_public_metadata_validation", provider="cams", stage="catalogue_validation",
            status="passed", severity="WARNING",
            reason_code="catalogue_sanity_down_constraints_validated", validation_status="passed",
        )
    return {
        "schema_version": 1,
        "kind": "cams_public_metadata_evidence",
        "dataset": DATASET,
        "run_date": run_date,
        "checked_at_utc": canonical_utc(checked_at_utc),
        "documents": {
            "catalogue": {
                "url": catalogue_url,
                "sha256": _canonical_sha256(catalogue_sha256),
            },
            "form": {"url": form_url, "sha256": _canonical_sha256(form_sha256)},
            "constraints": {
                "url": constraints_url,
                "sha256": _canonical_sha256(constraints_sha256),
            },
        },
        "catalogue_sanity": {"status": sanity_status, "timestamp": sanity_timestamp},
        "licence": {
            "identifier": LICENSE_IDENTIFIER,
            "url": LICENSE_URL,
            "dataset_doi": "10.24381/a4005cee",
        },
        "validated_selection": selection,
    }


def _fetch_document(session, url):
    try:
        response = session.get(
            url,
            timeout=(10, 30),
            allow_redirects=False,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            auth=None,
        )
    except requests.RequestException:
        raise PublicMetadataUnavailable("Official public metadata GET failed") from None
    try:
        if response.status_code != 200 or getattr(response, "history", None):
            raise PublicMetadataUnavailable("Official public metadata did not return direct HTTP 200")
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise PublicMetadataError("Official public metadata is not application/json")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise PublicMetadataError("Official public metadata was unexpectedly encoded")
        raw = response.content
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_PUBLIC_DOCUMENT_BYTES:
            raise PublicMetadataError("Official public metadata has an unsafe byte size")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                if int(declared) != len(raw):
                    raise PublicMetadataError("Public metadata Content-Length mismatch")
            except ValueError:
                raise PublicMetadataError("Public metadata Content-Length is invalid") from None
        return strict_json_loads(raw), raw, _sha256(raw)
    finally:
        response.close()


def fetch_verified_metadata(run_date, *, area=DEFAULT_AREA, session=None, checked_at_utc=None):
    """Discover and verify form/constraints using anonymous GET requests only."""
    run_date = canonical_date(run_date)
    area = canonical_area(area)
    own_session = session is None
    session = session or requests.Session()
    session.trust_env = False
    session.cookies.clear()
    try:
        catalogue, catalogue_raw, catalogue_hash = _fetch_document(session, CATALOGUE_URL)
        form_url, constraints_url, _, _ = _validate_catalogue(catalogue, run_date)
        form, form_raw, form_hash = _fetch_document(session, form_url)
        constraints, constraints_raw, constraints_hash = _fetch_document(session, constraints_url)
        # The byte variables are intentionally kept until every detached digest
        # has been compared; no decoded document is persisted in the plan.
        assert catalogue_raw and form_raw and constraints_raw
        return validate_public_metadata(
            run_date,
            area=area,
            catalogue=catalogue,
            catalogue_url=CATALOGUE_URL,
            catalogue_sha256=catalogue_hash,
            form=form,
            form_url=form_url,
            form_sha256=form_hash,
            constraints=constraints,
            constraints_url=constraints_url,
            constraints_sha256=constraints_hash,
            checked_at_utc=checked_at_utc
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    finally:
        if own_session:
            session.close()


def _validate_evidence(evidence, run_date):
    if not isinstance(evidence, dict):
        raise PublicMetadataError("Verified public metadata evidence is required")
    expected_keys = {
        "schema_version",
        "kind",
        "dataset",
        "run_date",
        "checked_at_utc",
        "documents",
        "catalogue_sanity",
        "licence",
        "validated_selection",
    }
    if set(evidence) != expected_keys:
        raise PublicMetadataError("Metadata evidence schema changed")
    if (
        evidence.get("schema_version") != 1
        or evidence.get("kind") != "cams_public_metadata_evidence"
        or evidence.get("dataset") != DATASET
        or evidence.get("run_date") != run_date
    ):
        raise PublicMetadataError("Metadata evidence identity does not match")
    if canonical_utc(evidence.get("checked_at_utc")) != evidence.get("checked_at_utc"):
        raise PublicMetadataError("Metadata evidence timestamp is not canonical UTC")
    documents = evidence.get("documents")
    if not isinstance(documents, dict) or set(documents) != {"catalogue", "form", "constraints"}:
        raise PublicMetadataError("Metadata evidence document set changed")
    for key in ("catalogue", "form", "constraints"):
        record = documents[key]
        if not isinstance(record, dict) or set(record) != {"url", "sha256"}:
            raise PublicMetadataError("Metadata evidence document record changed")
        _canonical_sha256(record["sha256"])
    if documents["catalogue"]["url"] != CATALOGUE_URL:
        raise PublicMetadataError("Metadata evidence catalogue URL changed")
    for kind in ("form", "constraints"):
        if _safe_resource_url(documents[kind]["url"], kind) != documents[kind]["sha256"]:
            raise PublicMetadataError("Metadata evidence content-addressed URL mismatch")
    sanity = evidence.get("catalogue_sanity")
    if (not isinstance(sanity, dict) or set(sanity) != {"status", "timestamp"}
            or sanity["status"] not in {"available", "down"}):
        raise PublicMetadataError("Metadata evidence sanity status changed")
    if canonical_utc(sanity["timestamp"]) != sanity["timestamp"]:
        raise PublicMetadataError("Metadata sanity timestamp is not canonical UTC")
    if evidence.get("licence") != {
        "identifier": LICENSE_IDENTIFIER,
        "url": LICENSE_URL,
        "dataset_doi": "10.24381/a4005cee",
    }:
        raise PublicMetadataError("Metadata evidence licence changed")
    selection = evidence.get("validated_selection")
    if not isinstance(selection, dict) or set(selection) != _CONSTRAINT_KEYS:
        raise PublicMetadataError("Metadata evidence selection changed")
    if not _date_values_cover(selection["date"], run_date):
        raise PublicMetadataError("Metadata evidence date does not cover the plan")
    _exact_strings(selection["model"], ("ensemble",), "model")
    _exact_strings(selection["level"], ("0",), "level")
    _exact_strings(selection["type"], ("forecast",), "type")
    _exact_strings(selection["time"], ("00:00",), "time")
    _exact_strings(selection["variable"], EXPECTED_VARIABLE_IDS, "variables")
    _exact_strings(selection["leadtime_hour"], EXPECTED_LEADS, "lead hours")
    return evidence


def build_request_plan(run_date, *, metadata_evidence, area=DEFAULT_AREA, data_format="grib"):
    """Build a deterministic plan only from already verified public evidence."""
    run_date = canonical_date(run_date)
    area = canonical_area(area)
    evidence = deepcopy(_validate_evidence(metadata_evidence, run_date))
    if data_format not in ("grib", "netcdf_zip"):
        raise PublicMetadataError("Format must be grib or netcdf_zip")
    variables = [
        {
            "id": name,
            "label": label,
            "category": "pollen" if name.endswith("_pollen") else "air_quality",
            "validation": (
                "regularly_validated_in_situ_by_provider"
                if name in _VALIDATED_VARIABLES
                else "experimental_unvalidated_by_provider"
            ),
        }
        for name, label in _VARIABLES
    ]
    request = {
        "variable": [row["id"] for row in variables],
        "model": ["ensemble"],
        "level": ["0"],
        "date": [f"{run_date}/{run_date}"],
        "type": ["forecast"],
        "time": ["00:00"],
        "leadtime_hour": list(EXPECTED_LEADS),
        "data_format": data_format,
        "area": area,
    }
    fields = len(variables) * len(EXPECTED_LEADS)
    if fields > DOCUMENTED_FIELD_LIMIT:
        raise PublicMetadataError("Verified request exceeds documented field limit")
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "kind": "cams_verified_request_plan",
        "status": "verified_public_metadata_no_retrieval",
        "dataset": DATASET,
        "run_date": run_date,
        "retrieval_performed": False,
        "credentials_read": False,
        "terms_accepted": False,
        "scope": (
            "All 28 variables in the verified surface ensemble forecast; "
            "not all models or atmospheric levels."
        ),
        "sources": {
            "catalogue": evidence["documents"]["catalogue"],
            "form": evidence["documents"]["form"],
            "constraints": evidence["documents"]["constraints"],
            "access_and_field_limits": {"url": ADS_DOCUMENTATION_URL},
        },
        "metadata_evidence": evidence,
        "licence": {
            "catalogue_identifier": LICENSE_IDENTIFIER,
            "url": LICENSE_URL,
            "accepted_by_this_tool": False,
            "attribution_required": True,
            "dataset_doi": "10.24381/a4005cee",
        },
        "variables": variables,
        "counts": {
            "variables": len(variables),
            "pollen": sum(row["category"] == "pollen" for row in variables),
            "air_quality": sum(row["category"] == "air_quality" for row in variables),
            "hourly_instants": len(EXPECTED_LEADS),
            "model_selections": 1,
            "level_selections": 1,
            "dates": 1,
            "requested_fields": fields,
            "documented_field_limit_per_request": DOCUMENTED_FIELD_LIMIT,
        },
        "request_groups": [
            {
                "id": "ensemble_surface_all_variables",
                "reason": "The exact verified row permits 2716 fields without a split.",
                "request": request,
            }
        ],
        "cadence": {
            "model_base_time_utc": "00:00",
            "nominal_runs_per_day": 1,
            "native_lead_hours": [0, 96],
            "hourly_data_retained": True,
            "scheduler_created": False,
        },
        "measurements": {
            "downloaded_weather_bytes": None,
            "queue_seconds": None,
            "decode_seconds": None,
            "payload_bytes": None,
            "reason": "No authenticated retrieval has been performed by this plan tool.",
        },
        "gaps_not_filled_by_this_dataset": [
            "weather_temperature_forecast",
            "precipitation_probability",
            "visibility",
            "five_day_weather_forecast",
        ],
        "limitations": [
            "Surface ensemble is approximately 0.1 degree resolution, not a local sensor observation.",
            "Only NO, NO2, SO2, ozone, PM2.5, PM10 and dust are regularly validated by the provider; all other variables are experimental.",
            "Public availability does not prove delivery, queue time, terms acceptance or affordability.",
            "The detached plan SHA-256 must be carried through intent, job and decoder provenance.",
            "A later date requires a newly fetched and verified immutable request plan.",
        ],
    }


def canonical_request_bytes(request):
    return json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def request_sha256(request):
    return _sha256(canonical_request_bytes(request))


def validate_request_plan(plan):
    """Fail closed unless the whole plan equals its deterministic reconstruction."""
    if not isinstance(plan, dict) or set(plan) != _PLAN_TOP_KEYS:
        raise PublicMetadataError("Request plan schema changed")
    if (
        plan.get("schema_version") != PLAN_SCHEMA_VERSION
        or plan.get("kind") != "cams_verified_request_plan"
        or plan.get("dataset") != DATASET
    ):
        raise PublicMetadataError("Request plan identity changed")
    groups = plan.get("request_groups")
    if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], dict):
        raise PublicMetadataError("Request plan must contain exactly one request group")
    request = groups[0].get("request")
    if not isinstance(request, dict):
        raise PublicMetadataError("Request plan request is malformed")
    expected = build_request_plan(
        plan.get("run_date"),
        metadata_evidence=plan.get("metadata_evidence"),
        area=request.get("area"),
        data_format=request.get("data_format"),
    )
    if plan != expected:
        raise PublicMetadataError("Request plan differs from its verified reconstruction")
    return plan


def encode_request_plan(plan):
    validate_request_plan(plan)
    return (
        json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_verified_request_plan(path):
    """Read exact plan bytes once; return validated plan, bytes and detached hash."""
    path = Path(path)
    if not path.is_file():
        raise PublicMetadataError("Request plan path or byte size is invalid")
    expected_size = path.stat().st_size
    if not 1 <= expected_size <= 1024 * 1024:
        raise PublicMetadataError("Request plan path or byte size is invalid")
    raw = path.read_bytes()
    if len(raw) != expected_size:
        raise PublicMetadataError("Request plan changed while it was being read")
    plan = strict_json_loads(raw)
    validate_request_plan(plan)
    return plan, raw, _sha256(raw)


def create_verified_request_plan(run_date, *, area=DEFAULT_AREA, data_format="grib"):
    """Library entry point: metadata failures retain their typed exceptions.

    This only reads public metadata. It never submits an ADS acquisition or
    translates unavailable/invalid metadata into process-level CLI exits.
    """
    evidence = fetch_verified_metadata(run_date, area=area)
    return build_request_plan(
        run_date, metadata_evidence=evidence, area=area, data_format=data_format,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Explicit UTC model date YYYY-MM-DD")
    parser.add_argument("--output", required=True, type=Path, help="NEW immutable plan JSON")
    parser.add_argument("--area", nargs=4, type=float, metavar=("N", "W", "S", "E"), default=DEFAULT_AREA)
    parser.add_argument("--data-format", choices=("grib", "netcdf_zip"), default="grib")
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("Output must be a new file in an existing directory")
    try:
        plan = create_verified_request_plan(args.date, area=args.area, data_format=args.data_format)
        encoded = encode_request_plan(plan)
        with args.output.open("xb") as stream:
            stream.write(encoded)
    except PublicMetadataError as exc:
        fields = error_fields(exc)
        fields.setdefault("stage", "public_metadata_plan")
        fields.setdefault("provider", "cams")
        fields.setdefault("run_date", args.date)
        fields.setdefault("reason_code", "public_metadata_unavailable" if isinstance(exc, PublicMetadataUnavailable)
                          else "public_metadata_invalid")
        fields.setdefault("validation_status", "failed")
        if not getattr(exc, "weather_diagnostics", None):
            emit("weather_public_metadata_validation", **{
                **fields, "status": "failed",
                "severity": "WARNING" if isinstance(exc, PublicMetadataUnavailable) else "ERROR",
            })
        try:
            parser.error(str(exc))
        except SystemExit as stopped:
            attach_error_fields(stopped, **fields)
            raise
    print(
        json.dumps(
            {
                "status": "verified_plan_written_no_retrieval",
                "run_date": plan["run_date"],
                "output": str(args.output),
                "plan_sha256": _sha256(encoded),
                "request_sha256": request_sha256(plan["request_groups"][0]["request"]),
            },
            separators=(",", ":"),
        )
    )
    return plan


if __name__ == "__main__":
    main()
