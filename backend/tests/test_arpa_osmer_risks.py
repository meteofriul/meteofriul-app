from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

import requests

from app.weather.arpa_osmer_risks import (
    ARPA_OSMER_AMR_ARCHIVE_URL,
    ARPA_OSMER_RISKS_URL,
    ArpaOsmerRisksParseError,
    ArpaOsmerRisksSource,
    ArpaOsmerRisksUnavailable,
    parse_osmer_amr_archive,
    parse_osmer_pcr_page,
    parse_osmer_risks_page,
    parse_osmer_risks_snapshot,
)


def pcr_inactive_panel() -> str:
    return """
    <div class="panel panel-primary">
      <div id="allerta_head" class="panel-heading">
        PCR - Nessuna allerta in corso
      </div>
      <div id="allerta_body" class="panel-body nopadd">
        <div class="bgrimg">
          <img src="mappa_zone_allerta.php?cont&amp;dim=346&amp;z=" />
        </div>
        <div class="text-center sipadd">
          maggiori dettagli su<br>
          <a href="https://www.protezionecivile.fvg.it/it/previsione-ed-allerta">
            www.protezionecivile.fvg.it
          </a>
        </div>
      </div>
    </div>
    """


def pcr_active_panel(
    headline: str = (
        "PCR - Allerta dalle ore 12:00 di mercoledì "
        "alle ore 08:00 di giovedì"
    ),
    *,
    dimension: str = "346",
    levels: str = "1,0,2,1",
    pdf_name: str = "Allerta_regionale_22-2026.pdf",
    pdf_url: str | None = None,
) -> str:
    document_url = pdf_url or (
        "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/" + pdf_name
    )
    return f"""
    <div class="panel panel-primary">
      <div id="allerta_head" class="panel-heading">{headline}</div>
      <div id="allerta_body" class="panel-body nopadd">
        <img src="mappa_zone_allerta.php?cont&amp;dim={dimension}&amp;z={levels}" />
        <div class="text-center sipadd">
          <a href="https://www.protezionecivile.fvg.it/it/previsione-ed-allerta">
            maggiori dettagli
          </a>
          <a href="{document_url}">
            allerta PDF
          </a>
        </div>
      </div>
    </div>
    """


def bvmr_panel(
    *,
    source_date: str = "20260814",
    levels: str = "0,0,0,0,1,1,1,1,1",
    summary: str = "Molto caldo; non sono previsti fenomeni significativi.",
) -> str:
    return f"""
    <div class="panel panel-primary">
      <div class="panel-heading">CFD - Bollettino di vigilanza</div>
      <div class="panel-body nopadd">
        <a title="Bollettino di vigilanza meteorologica regionale" href="cfd.php?ln=">
          <div class="bgrimg">
            <img alt="bvmr" src="mappa_zone_cfd.php?cont&amp;dim=346&amp;z={levels}&amp;d={source_date}&amp;ln=" />
          </div>
        </a>
        <div class="text-justify sipadd">{summary}</div>
      </div>
    </div>
    """


def amr_form(*, years=(2026, 2025, 2024)) -> str:
    options = "".join(
        f'<option value="{year}">{year}</option>' for year in years
    )
    return f"""
    <div class="panel panel-primary">
      <div class="panel-heading bg-primary">CFD - Avviso Meteorologico Regionale</div>
      <div class="panel-body">
        <form class="pdfCont" id="frm_amr" name="amr" method="post" action="/rischi_meteo.php">
          <select id="anno" class="form-control data" name="anno">{options}</select>
          <div id="arch_amr" name="amr"> scegli l'anno </div>
        </form>
      </div>
    </div>
    """


def risks_page(*, pcr: str | None = None, bvmr: str | None = None, amr: str | None = None) -> str:
    return (
        "<!doctype html><html><body>"
        + (pcr if pcr is not None else pcr_inactive_panel())
        + (bvmr if bvmr is not None else bvmr_panel())
        + (amr if amr is not None else amr_form())
        + "</body></html>"
    )


def amr_archive(*dates: str, selected: str | None = None) -> str:
    chosen = selected or (max(dates) if dates else "")
    options = []
    for date in dates:
        path = f"cfd/amr//2026//{date}/OSMER-avviso_meteo-{date}.pdf"
        selected_attribute = " selected" if date == chosen else ""
        options.append(
            f'<option value="{path}" data-href="{path}"{selected_attribute}>{date}</option>'
        )
    selected_path = f"cfd/amr//2026//{chosen}/OSMER-avviso_meteo-{chosen}.pdf"
    html = f"""
      <select id="sel_amr" class="form-control files">{''.join(options)}</select>
      <div class="pdfcont" id="pdfCont_amr">
        <object id="pdf_amr" data="{selected_path}" type="application/pdf"></object>
        <a id="linkpdf_amr" href="{selected_path}">apri il file</a>
      </div>
    """
    return json.dumps(html)


class ArpaOsmerRisksParserTests(unittest.TestCase):
    def test_parses_real_320px_yellow_and_orange_panels_together(self):
        parsed = parse_osmer_pcr_page(
            risks_page(
                pcr=(
                    pcr_active_panel(
                        "PCR - Allerta dalle ore 12:00 di giovedì alle ore 23:59 di venerdì",
                        dimension="320",
                        levels="1,1,1,1",
                        pdf_url=(
                            "https://pianiemergenza.protezionecivile.fvg.it/"
                            "alerts/23_2026.pdf"
                        ),
                    )
                    + pcr_active_panel(
                        "PCR - Allerta dalle ore 18:00 di giovedì alle ore 23:59 di venerdì",
                        dimension="320",
                        levels="2,2,2,2",
                        pdf_url=(
                            "https://pianiemergenza.protezionecivile.fvg.it/"
                            "alerts/24_2026.pdf"
                        ),
                    )
                )
            )
        )

        self.assertEqual(parsed["status"], "active")
        self.assertEqual(len(parsed["alerts"]), 2)
        self.assertEqual(
            [item["level"] for item in parsed["alerts"][0]["zone_levels"]],
            [1, 1, 1, 1],
        )
        self.assertEqual(
            [item["level"] for item in parsed["alerts"][1]["zone_levels"]],
            [2, 2, 2, 2],
        )
        self.assertTrue(
            parsed["alerts"][0]["document_urls"][0].endswith("/23_2026.pdf")
        )
        self.assertTrue(
            parsed["alerts"][1]["document_urls"][0].endswith("/24_2026.pdf")
        )

    def test_explicit_inactive_state_and_bvmr_are_parsed(self):
        parsed = parse_osmer_risks_page(risks_page())

        self.assertEqual(parsed["pcr"]["status"], "inactive")
        self.assertTrue(parsed["pcr"]["explicit"])
        self.assertTrue(parsed["pcr"]["can_confirm_inactive"])
        self.assertEqual(parsed["pcr"]["alerts"], [])
        self.assertEqual(parsed["bvmr"]["source_date"], "2026-08-14")
        self.assertEqual(parsed["bvmr"]["zone_levels"][4], {"zone": "Pianura PN", "level": 1})
        self.assertEqual(parsed["amr_archive"]["requested_year"], 2026)

    def test_multiple_active_panels_preserve_links_without_inventing_dates(self):
        pcr = pcr_active_panel() + pcr_active_panel(
            "PCR - Allerta dalle ore 00:00 di giovedì alle ore 23:59 di giovedì",
            levels="0,1,1,0",
            pdf_name="Allerta_regionale_23-2026.pdf",
        )
        parsed = parse_osmer_risks_page(risks_page(pcr=pcr))

        self.assertEqual(parsed["pcr"]["status"], "active")
        self.assertFalse(parsed["pcr"]["can_confirm_inactive"])
        self.assertEqual(len(parsed["pcr"]["alerts"]), 2)
        first = parsed["pcr"]["alerts"][0]
        self.assertEqual(first["start_weekday"], "mercoledì")
        self.assertEqual(first["end_time"], "08:00")
        self.assertNotIn("valid_from", first)
        self.assertEqual(first["zone_levels"][2], {"zone": "FVG-C", "level": 2})
        self.assertEqual(len(first["document_urls"]), 1)

    def test_active_link_is_optional_but_untrusted_links_are_rejected(self):
        without_links = pcr_active_panel()
        without_links = without_links.replace(
            '<a href="https://www.protezionecivile.fvg.it/it/previsione-ed-allerta">\n'
            "            maggiori dettagli\n"
            "          </a>",
            "",
        ).replace(
            '<a href="https://cfd.protezionecivile.fvg.it/docs/alerts/2026/Allerta_regionale_22-2026.pdf">\n'
            "            allerta PDF\n"
            "          </a>",
            "",
        )
        parsed = parse_osmer_pcr_page(risks_page(pcr=without_links))
        self.assertEqual(parsed["status"], "active")
        self.assertIsNone(parsed["alerts"][0]["detail_url"])
        self.assertEqual(parsed["alerts"][0]["document_urls"], [])

        unsafe = pcr_active_panel().replace(
            "https://www.protezionecivile.fvg.it/it/previsione-ed-allerta",
            "https://example.invalid/fake-alert",
        )
        with self.assertRaisesRegex(
            ArpaOsmerRisksParseError, "unexpected_source_url"
        ):
            parse_osmer_pcr_page(risks_page(pcr=unsafe))

    def test_only_exact_inactive_marker_can_clear(self):
        variants = (
            "PCR - Nessuna allerta",
            "PCR - Probabilmente nessuna allerta in corso",
            "Nessuna allerta in corso",
        )
        for marker in variants:
            with self.subTest(marker=marker):
                panel = pcr_inactive_panel().replace(
                    "PCR - Nessuna allerta in corso", marker
                )
                with self.assertRaisesRegex(
                    ArpaOsmerRisksParseError, "unknown_pcr_marker"
                ):
                    parse_osmer_risks_page(risks_page(pcr=panel))

    def test_mixed_active_and_inactive_panels_fail_closed(self):
        with self.assertRaisesRegex(ArpaOsmerRisksParseError, "mixed_pcr_state"):
            parse_osmer_risks_page(
                risks_page(pcr=pcr_inactive_panel() + pcr_active_panel())
            )

    def test_incomplete_or_inconsistent_pcr_never_becomes_inactive(self):
        cases = (
            pcr_inactive_panel().replace("&amp;z=", "&amp;z=0,0,0,0"),
            pcr_inactive_panel().replace('</div>\n    </div>', "", 1),
            pcr_active_panel(levels="0,0,0,0"),
        )
        for panel in cases:
            with self.subTest(panel=panel[:80]):
                with self.assertRaises(ArpaOsmerRisksParseError):
                    parse_osmer_risks_page(risks_page(pcr=panel))

    def test_malformed_bvmr_map_or_missing_summary_fails(self):
        malformed = (
            bvmr_panel(levels="0,0,0"),
            bvmr_panel(source_date="20260230"),
            bvmr_panel(summary="").replace(
                '<div class="text-justify sipadd"></div>', ""
            ),
        )
        for panel in malformed:
            with self.subTest(panel=panel[-100:]):
                with self.assertRaises(ArpaOsmerRisksParseError):
                    parse_osmer_risks_page(risks_page(bvmr=panel))

    def test_semantic_revision_ignores_whitespace_and_changes_with_content(self):
        compact = risks_page()
        spaced = compact.replace(">", ">  \n").replace("<", "  <")
        first = parse_osmer_risks_page(compact)
        second = parse_osmer_risks_page(spaced)
        changed = parse_osmer_risks_page(
            risks_page(bvmr=bvmr_panel(summary="Sono previsti temporali forti."))
        )

        self.assertEqual(first["revision"], second["revision"])
        self.assertNotEqual(first["revision"], changed["revision"])


class ArpaOsmerAmrArchiveTests(unittest.TestCase):
    def test_parses_emission_history_without_claiming_current_validity(self):
        parsed = parse_osmer_amr_archive(
            amr_archive("20260123", "20260725"), year=2026
        )

        self.assertEqual(parsed["status"], "emissions_present")
        self.assertEqual(parsed["latest_source_date"], "2026-07-25")
        self.assertFalse(parsed["can_confirm_no_active_amr"])
        self.assertTrue(parsed["emissions"][-1]["selected"])
        self.assertEqual(
            parsed["emissions"][-1]["document_url"],
            "https://www.meteo.fvg.it/cfd/amr/2026/20260725/OSMER-avviso_meteo-20260725.pdf",
        )

    def test_only_exact_json_absence_marker_is_accepted(self):
        parsed = parse_osmer_amr_archive(json.dumps("file non presente"), year=2026)
        self.assertEqual(parsed["status"], "no_emissions_for_year")
        self.assertTrue(parsed["explicit"])
        self.assertFalse(parsed["can_confirm_no_active_amr"])

        for payload in (
            json.dumps("nessun file"),
            json.dumps("FILE NON PRESENTE"),
            "file non presente",
            json.dumps({"message": "file non presente"}),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ArpaOsmerRisksParseError):
                    parse_osmer_amr_archive(payload, year=2026)

    def test_rejects_stale_selection_and_mismatched_year(self):
        with self.assertRaisesRegex(
            ArpaOsmerRisksParseError, "stale_amr_archive_selection"
        ):
            parse_osmer_amr_archive(
                amr_archive("20260123", "20260725", selected="20260123"),
                year=2026,
            )
        with self.assertRaisesRegex(
            ArpaOsmerRisksParseError, "unexpected_amr_document"
        ):
            parse_osmer_amr_archive(
                amr_archive("20260123").replace("2026", "2025"), year=2026
            )


class _FakeResponse:
    def __init__(self, text: str, *, headers=None, error: Exception | None = None):
        self.text = text
        self.headers = headers or {}
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class ArpaOsmerRisksSnapshotTests(unittest.TestCase):
    def test_http_date_not_fetch_time_is_the_external_ordering_clock(self):
        fetched_at = datetime(2026, 8, 14, 13, 30, tzinfo=timezone.utc)
        parsed = parse_osmer_risks_snapshot(
            risks_page(),
            json.dumps("file non presente"),
            response_headers={
                "Date": "Fri, 14 Aug 2026 11:29:50 GMT",
                "Age": "120",
                "Cache-Control": "public, max-age=3600",
            },
            fetched_at=fetched_at,
        )

        timing = parsed["source_timing"]
        self.assertEqual(timing["fetched_at"], "2026-08-14T13:30:00+00:00")
        self.assertEqual(timing["source_observed_at"], "2026-08-14T11:29:50+00:00")
        self.assertEqual(timing["source_timestamp_kind"], "http_date")
        self.assertEqual(timing["age_seconds"], 120)
        self.assertEqual(timing["cache_max_age_seconds"], 3600)
        self.assertTrue(parsed["can_confirm_pcr_inactive"])

    def test_without_server_timestamp_fetch_time_is_not_used_for_ordering(self):
        parsed = parse_osmer_risks_snapshot(
            risks_page(),
            json.dumps("file non presente"),
            fetched_at=datetime(2026, 8, 14, 13, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(parsed["pcr"]["status"], "inactive")
        self.assertIsNone(parsed["source_timing"]["source_observed_at"])
        self.assertFalse(parsed["source_timing"]["comparable_to_external_events"])
        self.assertTrue(parsed["can_confirm_pcr_inactive"])

    def test_pcr_parser_and_fetch_are_independent_from_bvmr_and_amr(self):
        page = risks_page(
            bvmr="<div>schema BVMR cambiato</div>",
            amr="<div>archivio AMR non disponibile</div>",
        )
        parsed = parse_osmer_pcr_page(page)
        self.assertEqual(parsed["status"], "inactive")

        session = _FakeSession(
            [
                _FakeResponse(
                    page,
                    headers={"Date": "Fri, 14 Aug 2026 11:29:50 GMT"},
                )
            ]
        )
        source = ArpaOsmerRisksSource(
            session=session,
            now=lambda: datetime(2026, 8, 14, 13, 30, tzinfo=timezone.utc),
        )
        fetched = source.fetch_pcr()

        self.assertEqual(fetched["pcr"]["status"], "inactive")
        self.assertTrue(fetched["can_confirm_pcr_inactive"])
        self.assertEqual(fetched["source_mode"], "raw_official_page")
        self.assertEqual(len(session.calls), 1)

    def test_adapter_fetches_page_then_matching_amr_year(self):
        session = _FakeSession(
            [
                _FakeResponse(
                    risks_page(),
                    headers={"Date": "Fri, 14 Aug 2026 11:29:50 GMT"},
                ),
                _FakeResponse(json.dumps("file non presente")),
            ]
        )
        source = ArpaOsmerRisksSource(
            session=session,
            now=lambda: datetime(2026, 8, 14, 13, 30, tzinfo=timezone.utc),
        )

        parsed = source.fetch()

        self.assertEqual(parsed["status"], "available")
        self.assertEqual(session.calls[0][0], ARPA_OSMER_RISKS_URL)
        self.assertEqual(session.calls[1][0], ARPA_OSMER_AMR_ARCHIVE_URL)
        self.assertEqual(
            session.calls[1][1]["params"],
            {"l": "", "ln": "", "a": "2026", "m": "", "t": "amr"},
        )

    def test_adapter_maps_network_and_parse_failures_to_unavailable(self):
        network_source = ArpaOsmerRisksSource(
            session=_FakeSession(
                [_FakeResponse("", error=requests.ConnectionError("offline"))]
            )
        )
        with self.assertRaisesRegex(
            ArpaOsmerRisksUnavailable, "source_request_failed"
        ):
            network_source.fetch()

        parse_source = ArpaOsmerRisksSource(
            session=_FakeSession([_FakeResponse("<html>maintenance</html>")])
        )
        with self.assertRaisesRegex(
            ArpaOsmerRisksUnavailable, "source_page_unrecognized"
        ):
            parse_source.fetch()


if __name__ == "__main__":
    unittest.main()
