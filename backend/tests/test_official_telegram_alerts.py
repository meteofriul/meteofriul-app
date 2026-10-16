from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

import requests

from app.weather.official_telegram_alerts import (
    OFFICIAL_TELEGRAM_URL,
    OfficialTelegramParserError,
    fetch_official_telegram_channel,
    parse_official_telegram_channel,
)


def channel_page(*messages: str) -> str:
    return '<section class="tgme_channel_history">' + "".join(messages) + "</section>"


def message(post_id: int, text: str, *, published_at: str, links=()) -> str:
    anchors = "".join(f'<a href="{link}">{link}</a>' for link in links)
    return f"""
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message js-widget_message" data-post="ProtCivileFVG/{post_id}">
        <div class="tgme_widget_message_text js-message_text">{text}{anchors}</div>
        <a class="tgme_widget_message_date"><time datetime="{published_at}">12:00</time></a>
      </div>
    </div>
    """


PDF_22 = (
    "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
    "Allerta_regionale_22-2026_25072026-13_08.pdf"
)
PDF_23 = (
    "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
    "Allerta_regionale_23-2026_19082026-14_57.pdf"
)
PDF_24 = (
    "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
    "Allerta_regionale_24-2026_20082026-11_36.pdf"
)
VALID_PDF = b"%PDF-1.7\n" + (b"0" * 600) + b"\n%%EOF\n"


class _FakeResponse:
    def __init__(self, *, text="", content=b"", headers=None, url="", error=None):
        self.text = text
        self._content = content
        self.headers = dict(headers or {})
        self.url = url
        self._error = error
        self.closed = False

    def raise_for_status(self):
        if self._error:
            raise self._error

    def iter_content(self, chunk_size=64 * 1024):
        del chunk_size
        yield self._content

    def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class OfficialTelegramAlertsTests(unittest.TestCase):
    def test_metadata_fetch_skips_active_pdf_download_when_explicitly_disabled(self):
        page = channel_page(
            message(
                862,
                "#AllertameteoFVG - ALLERTA REGIONALE 23 DEL 2026<br>"
                "DALLE ORE 12:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 "
                "DI VENERDÌ 21/08/26 ALLERTA GIALLA PER TEMPORALI FORTI "
                "SU TUTTA LA REGIONE.",
                published_at="2026-08-19T12:57:42+00:00",
                links=(PDF_23,),
            )
        )
        session = _FakeSession(_FakeResponse(text=page))

        result = fetch_official_telegram_channel(
            session=session,
            now=lambda: datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            verify_active_pdfs=False,
        )

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][0], OFFICIAL_TELEGRAM_URL)
        self.assertEqual(result["alerts"][0]["alert_number"], 23)
        self.assertNotIn("pdf_sha256", result["alerts"][0])

    def test_fetch_retries_channel_once_after_timeout(self):
        page = channel_page(
            message(
                862,
                "#AllertameteoFVG - ALLERTA REGIONALE 23 DEL 2026<br>"
                "DALLE ORE 12:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 "
                "DI VENERDÌ 21/08/26 ALLERTA GIALLA PER TEMPORALI FORTI "
                "SU TUTTA LA REGIONE.",
                published_at="2026-08-19T12:57:42+00:00",
                links=(PDF_23,),
            )
        )
        page_response = _FakeResponse(text=page)
        session = _FakeSession(
            requests.ReadTimeout("first attempt timed out"),
            page_response,
            _FakeResponse(
                content=VALID_PDF,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(VALID_PDF)),
                },
                url=PDF_23,
            ),
        )

        result = fetch_official_telegram_channel(
            session=session,
            now=lambda: datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[0][0], OFFICIAL_TELEGRAM_URL)
        self.assertEqual(session.calls[1][0], OFFICIAL_TELEGRAM_URL)
        self.assertTrue(page_response.closed)
        self.assertEqual(
            result["alerts"][0]["pdf_sha256"],
            hashlib.sha256(VALID_PDF).hexdigest(),
        )

    def test_parses_real_alerts_23_and_24_with_weekdays_and_two_digit_years(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    862,
                    "#AllertameteoFVG - ALLERTA REGIONALE 23 DEL 2026<br>"
                    "DALLE ORE 12:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 "
                    "DI VENERDÌ 21/08/26 ALLERTA GIALLA PER TEMPORALI FORTI "
                    "E CRITICITA' IDROGEOLOGICA SU TUTTA LA REGIONE.",
                    published_at="2026-08-19T12:57:42+00:00",
                    links=(PDF_23,),
                ),
                message(
                    863,
                    "#AllertameteoFVG - ALLERTA REGIONALE 24 DEL 2026<br>"
                    "DALLE ORE 18:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 "
                    "DI VENERDÌ 21/08/26 ALLERTA ARANCIONE PER TEMPORALI FORTI "
                    "E CRITICITA' IDROGEOLOGICA SU TUTTA LA REGIONE.",
                    published_at="2026-08-20T09:36:58+00:00",
                    links=(PDF_24,),
                ),
            )
        )

        alerts = {alert["id"]: alert for alert in parsed["alerts"]}
        self.assertEqual(set(alerts), {
            "allerta-regionale-23-2026",
            "allerta-regionale-24-2026",
        })
        yellow = alerts["allerta-regionale-23-2026"]
        orange = alerts["allerta-regionale-24-2026"]
        self.assertEqual(yellow["level"], "gialla")
        self.assertEqual(yellow["valid_from"], "2026-08-20T12:00:00+02:00")
        self.assertEqual(yellow["valid_to"], "2026-08-22T00:00:00+02:00")
        self.assertEqual(orange["level"], "arancione")
        self.assertEqual(orange["valid_from"], "2026-08-20T18:00:00+02:00")
        self.assertEqual(orange["valid_to"], "2026-08-22T00:00:00+02:00")
        self.assertEqual(orange["zones"], ["FVG-A", "FVG-B", "FVG-C", "FVG-D"])
        self.assertEqual(orange["area"], "Tutta la regione")

    def test_parses_official_alert_without_using_absence_as_inactive(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    861,
                    "#AllertameteoFVG - ALLERTA REGIONALE 22 DEL 2026<br>"
                    "DALLE ORE 06:00 ALLE ORE 24:00 DI DOMENICA 26/07 "
                    "ALLERTA GIALLA PER TEMPORALI FORTI SULLE ZONE FVG-A, FVG-C E FVG-D",
                    published_at="2026-07-25T11:08:42+00:00",
                    links=(PDF_22,),
                )
            )
        )

        self.assertFalse(parsed["can_confirm_inactive"])
        self.assertEqual(parsed["latest_post_id"], 861)
        self.assertEqual(len(parsed["alerts"]), 1)
        alert = parsed["alerts"][0]
        self.assertEqual(alert["id"], "allerta-regionale-22-2026")
        self.assertEqual(alert["level"], "gialla")
        self.assertEqual(alert["zones"], ["FVG-A", "FVG-C", "FVG-D"])
        self.assertEqual(alert["valid_from"], "2026-07-26T06:00:00+02:00")
        self.assertEqual(alert["valid_to"], "2026-07-27T00:00:00+02:00")
        self.assertIn("temporali", alert["risks"])
        self.assertEqual(alert["pdf_url"], PDF_22)

    def test_parses_real_2024_mixed_criticity_format_and_spaced_zones(self):
        pdf_url = (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2024/"
            "Allerta_regionale_31-2024_07102024-13_46.pdf"
        )
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    428,
                    "#AllertameteoFVG - ALLERTA REGIONALE 31 DEL 2024<br>"
                    "DALLE 12:00 del 08/10 ALLE 12:00 DEL 09/10<br>"
                    "- CRITICITA' IDROGEOLOGICA ARANCIONE SULLA ZONA FVG A E "
                    "FVG B E GIALLA SU FVG C;<br>"
                    "- CRITICITA' IDRAULICA GIALLA SULLA ZONA FVG A-B-C;<br>"
                    "- CRITICITA' IDRAULICA COSTIERA GIALLA SULLA ZONA FVG-C "
                    "E FVG-D PER MAREGGIATE SULLE COSTE ESPOSTE.",
                    published_at="2024-10-07T11:46:14+00:00",
                    links=(pdf_url,),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["level"], "arancione")
        self.assertEqual(alert["levels"], ["arancione", "gialla"])
        self.assertTrue(alert["mixed_levels"])
        self.assertEqual(alert["zones"], ["FVG-A", "FVG-B", "FVG-C", "FVG-D"])
        self.assertEqual(alert["valid_from"], "2024-10-08T12:00:00+02:00")
        self.assertEqual(alert["valid_to"], "2024-10-09T12:00:00+02:00")

    def test_parses_real_2025_whole_hour_and_explicit_year_format(self):
        pdf_url = (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2025/"
            "Allerta_regionale_25-2025_17112025-12_33.pdf"
        )
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    533,
                    "#AllertameteoFVG - ALLERTA REGIONALE 25 DEL 2025<br>"
                    "DALLE 12 DEL 17/11/2025 ALLE 12 DEL 18/11/2025 "
                    "ALLERTA GIALLA IDROGEOLOGICA SU FVG-B, E ARANCIONE "
                    "IDRAULICA E IDROGEOLOGICA SU FVG-C PER PIOGGE MODERATE "
                    "E LOCALMENTE INTENSE",
                    published_at="2025-11-17T11:33:34+00:00",
                    links=(pdf_url,),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["level"], "arancione")
        self.assertEqual(alert["levels"], ["arancione", "gialla"])
        self.assertTrue(alert["mixed_levels"])
        self.assertEqual(alert["zones"], ["FVG-B", "FVG-C"])
        self.assertEqual(alert["valid_from"], "2025-11-17T12:00:00+01:00")
        self.assertEqual(alert["valid_to"], "2025-11-18T12:00:00+01:00")

    def test_arancio_variant_is_normalized_to_orange(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    951,
                    "#AllertameteoFVG - ALLERTA REGIONALE 31 DEL 2026<br>"
                    "DALLE 12 DEL 20/10/2026 ALLE 12 DEL 21/10/2026 "
                    "ALLERTA GIALLA SU FVG-A E ALLERTA ARANCIO SU FVG-B",
                    published_at="2026-10-20T09:00:00+00:00",
                    links=(
                        "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                        "Allerta_regionale_31-2026.pdf",
                    ),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["level"], "arancione")
        self.assertEqual(alert["levels"], ["arancione", "gialla"])

    def test_same_day_window_and_whole_region_are_normalized(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    859,
                    "#AllertameteoFVG - ALLERTA REGIONALE 20 DEL 2026<br>"
                    "DALLE ORE 00:00 ALLE ORE 24:00 DEL 17/07 "
                    "ALLERTA GIALLA PER TEMPORALI FORTI SU TUTTE LE ZONE",
                    published_at="2026-07-16T12:50:47+00:00",
                    links=(PDF_22.replace("22-2026", "20-2026"),),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["zones"], ["FVG-A", "FVG-B", "FVG-C", "FVG-D"])
        self.assertEqual(alert["area"], "Tutta la regione")
        self.assertEqual(alert["valid_to"], "2026-07-18T00:00:00+02:00")

    def test_latest_revision_wins_for_same_alert_number(self):
        first_pdf = PDF_22.replace("22-2026", "16-2026").replace("13_08", "15_42")
        second_pdf = first_pdf.replace("15_42", "16_22")
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    854,
                    "#AllertameteoFVG - ALLERTA REGIONALE 16 DEL 2026<br>"
                    "DALLE ORE 18:00 DEL 05/06 ALLE ORE 06:00 DEL 06/06 "
                    "ALLERTA GIALLA IDROGEOLOGICA SU ZONA FVG-A",
                    published_at="2026-06-05T13:42:59+00:00",
                    links=(first_pdf,),
                ),
                message(
                    855,
                    "#AllertameteoFVG - ALLERTA REGIONALE 16 DEL 2026<br>"
                    "DALLE ORE 18:00 DEL 05/06 ALLE ORE 06:00 DEL 06/06 "
                    "ALLERTA GIALLA IDROGEOLOGICA SU ZONA FVG-A",
                    published_at="2026-06-05T14:22:06+00:00",
                    links=(second_pdf,),
                ),
            )
        )

        self.assertEqual(len(parsed["alerts"]), 1)
        self.assertEqual(parsed["alerts"][0]["telegram_post_id"], 855)
        self.assertEqual(parsed["alerts"][0]["pdf_url"], second_pdf)

    def test_winter_validity_uses_the_fvg_standard_time_offset(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    900,
                    "#AllertameteoFVG - ALLERTA REGIONALE 1 DEL 2027<br>"
                    "DALLE ORE 06:00 DEL 02/01 ALLE ORE 18:00 DEL 02/01 "
                    "ALLERTA GIALLA PER NEVE SU ZONA FVG-A",
                    published_at="2027-01-01T12:00:00+00:00",
                    links=(
                        "https://cfd.protezionecivile.fvg.it/docs/alerts/2027/"
                        "Allerta_regionale_1-2027.pdf",
                    ),
                )
            )
        )

        self.assertEqual(parsed["alerts"][0]["valid_from"], "2027-01-02T06:00:00+01:00")
        self.assertEqual(parsed["alerts"][0]["valid_to"], "2027-01-02T18:00:00+01:00")

    def test_validity_window_can_cross_new_year_but_never_run_backwards(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    901,
                    "#AllertameteoFVG - ALLERTA REGIONALE 50 DEL 2026<br>"
                    "DALLE ORE 18:00 DEL 31/12 ALLE ORE 06:00 DEL 01/01 "
                    "ALLERTA GIALLA PER NEVE SU ZONA FVG-A",
                    published_at="2026-12-31T12:00:00+00:00",
                    links=(
                        "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                        "Allerta_regionale_50-2026.pdf",
                    ),
                )
            )
        )

        self.assertEqual(parsed["alerts"][0]["valid_from"], "2026-12-31T18:00:00+01:00")
        self.assertEqual(parsed["alerts"][0]["valid_to"], "2027-01-01T06:00:00+01:00")

        with self.assertRaisesRegex(
            OfficialTelegramParserError, "unrecognized_official_alert_validity"
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        902,
                        "#AllertameteoFVG - ALLERTA REGIONALE 51 DEL 2026<br>"
                        "DALLE ORE 18:00 DEL 31/12 ALLE ORE 06:00 DEL 31/12 "
                        "ALLERTA GIALLA PER NEVE SU ZONA FVG-A",
                        published_at="2026-12-31T12:00:00+00:00",
                        links=(
                            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                            "Allerta_regionale_51-2026.pdf",
                        ),
                    )
                )
            )

    def test_december_publication_can_resolve_an_entirely_january_window(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    904,
                    "#AllertameteoFVG - ALLERTA REGIONALE 53 DEL 2026<br>"
                    "DALLE ORE 00:00 ALLE ORE 12:00 DEL 01/01 "
                    "ALLERTA GIALLA PER NEVE SU ZONA FVG-A",
                    published_at="2026-12-31T20:00:00+00:00",
                    links=(
                        "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                        "Allerta_regionale_53-2026.pdf",
                    ),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["valid_from"], "2027-01-01T00:00:00+01:00")
        self.assertEqual(alert["valid_to"], "2027-01-01T12:00:00+01:00")

    def test_rejects_invalid_identity_number_and_incoherent_year(self):
        cases = (
            (
                0,
                2026,
                "2026-07-10T12:00:00+00:00",
                "unrecognized_official_alert_identity",
            ),
            (
                -1,
                2026,
                "2026-07-10T12:00:00+00:00",
                "unrecognized_official_alert_post",
            ),
            (
                1,
                2028,
                "2026-07-10T12:00:00+00:00",
                "unrecognized_official_alert_identity",
            ),
        )
        for number, year, published_at, expected_error in cases:
            with self.subTest(number=number, year=year):
                with self.assertRaisesRegex(
                    OfficialTelegramParserError, expected_error
                ):
                    parse_official_telegram_channel(
                        channel_page(
                            message(
                                910 + number,
                                f"#AllertameteoFVG - ALLERTA REGIONALE {number} "
                                f"DEL {year}<br>"
                                "DALLE ORE 06:00 ALLE ORE 18:00 DEL 11/07 "
                                "ALLERTA GIALLA PER TEMPORALI SU ZONA FVG-A",
                                published_at=published_at,
                                links=(
                                    "https://cfd.protezionecivile.fvg.it/docs/alerts/"
                                    f"{year}/Allerta_regionale_{number}-{year}.pdf",
                                ),
                            )
                        )
                    )

    def test_rejects_implausible_validity_windows(self):
        cases = (
            (
                "DALLE ORE 00:00 DEL 01/07 ALLE ORE 00:00 DEL 09/07",
                "2026-06-30T12:00:00+00:00",
            ),
            (
                "DALLE ORE 06:00 ALLE ORE 18:00 DEL 09/07",
                "2026-07-01T12:00:00+00:00",
            ),
            (
                "DALLE ORE 06:00 ALLE ORE 18:00 DEL 01/07",
                "2026-07-02T12:00:00+00:00",
            ),
        )
        for index, (validity, published_at) in enumerate(cases, start=1):
            with self.subTest(validity=validity, published_at=published_at):
                with self.assertRaisesRegex(
                    OfficialTelegramParserError,
                    "unrecognized_official_alert_validity",
                ):
                    parse_official_telegram_channel(
                        channel_page(
                            message(
                                920 + index,
                                "#AllertameteoFVG - ALLERTA REGIONALE "
                                f"{60 + index} DEL 2026<br>{validity} "
                                "ALLERTA GIALLA PER TEMPORALI SU ZONA FVG-A",
                                published_at=published_at,
                                links=(
                                    "https://cfd.protezionecivile.fvg.it/docs/alerts/"
                                    f"2026/Allerta_regionale_{60 + index}-2026.pdf",
                                ),
                            )
                        )
                    )

    def test_non_alert_posts_are_ignored_but_do_not_confirm_inactive(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    840,
                    "Pubblichiamo la nota informativa valanghe",
                    published_at="2026-05-08T11:03:29+00:00",
                )
            )
        )
        self.assertEqual(parsed["alerts"], [])
        self.assertFalse(parsed["can_confirm_inactive"])

    def test_rejects_a_truncated_latest_own_channel_message(self):
        truncated_alert = """
        <div class="tgme_widget_message js-widget_message" data-post="ProtCivileFVG/841">
          <div class="tgme_widget_message_text js-message_text">
            #AllertameteoFVG - ALLERTA REGIONALE 30 DEL 2026
        """
        with self.assertRaisesRegex(
            OfficialTelegramParserError,
            "invalid_channel_html",
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        840,
                        "Pubblichiamo la nota informativa valanghe",
                        published_at="2026-05-08T11:03:29+00:00",
                    ),
                    truncated_alert,
                )
            )

    def test_rejects_explicit_date_year_inconsistent_with_the_alert(self):
        with self.assertRaisesRegex(
            OfficialTelegramParserError, "unrecognized_official_alert_validity"
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        952,
                        "#AllertameteoFVG - ALLERTA REGIONALE 30 DEL 2026<br>"
                        "DALLE 12 DEL 14/08/2025 ALLE 12 DEL 15/08/2025 "
                        "ALLERTA GIALLA PER TEMPORALI SU FVG-A",
                        published_at="2026-08-14T09:00:00+00:00",
                        links=(
                            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                            "Allerta_regionale_30-2026.pdf",
                        ),
                    )
                )
            )

    def test_accepts_explicit_years_for_a_real_new_year_rollover(self):
        parsed = parse_official_telegram_channel(
            channel_page(
                message(
                    953,
                    "#AllertameteoFVG - ALLERTA REGIONALE 40 DEL 2026<br>"
                    "DALLE 18 DEL 31/12/2026 ALLE 06 DEL 01/01/2027 "
                    "ALLERTA GIALLA PER NEVE SU FVG-A",
                    published_at="2026-12-31T12:00:00+00:00",
                    links=(
                        "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                        "Allerta_regionale_40-2026.pdf",
                    ),
                )
            )
        )

        alert = parsed["alerts"][0]
        self.assertEqual(alert["valid_from"], "2026-12-31T18:00:00+01:00")
        self.assertEqual(alert["valid_to"], "2027-01-01T06:00:00+01:00")

    def test_rejects_official_pdf_for_a_different_alert_identity(self):
        with self.assertRaisesRegex(
            OfficialTelegramParserError,
            "unrecognized_official_alert_pdf_identity",
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        954,
                        "#AllertameteoFVG - ALLERTA REGIONALE 30 DEL 2026<br>"
                        "DALLE 12 DEL 14/08/2026 ALLE 12 DEL 15/08/2026 "
                        "ALLERTA GIALLA PER TEMPORALI SU FVG-A",
                        published_at="2026-08-14T09:00:00+00:00",
                        links=(
                            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                            "Allerta_regionale_22-2026_14082026-11_00.pdf",
                        ),
                    )
                )
            )

    def test_rejects_alert_post_without_allowed_official_pdf(self):
        with self.assertRaisesRegex(
            OfficialTelegramParserError, "unrecognized_official_alert_post"
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        861,
                        "#AllertameteoFVG - ALLERTA REGIONALE 22 DEL 2026<br>"
                        "DALLE ORE 06:00 ALLE ORE 24:00 DEL 26/07 ALLERTA GIALLA",
                        published_at="2026-07-25T11:08:42+00:00",
                        links=("https://example.invalid/fake.pdf",),
                    )
                )
            )

    def test_rejects_impossible_calendar_dates_as_a_parser_failure(self):
        with self.assertRaisesRegex(
            OfficialTelegramParserError, "unrecognized_official_alert_validity"
        ):
            parse_official_telegram_channel(
                channel_page(
                    message(
                        903,
                        "#AllertameteoFVG - ALLERTA REGIONALE 52 DEL 2026<br>"
                        "DALLE ORE 06:00 DEL 31/02 ALLE ORE 18:00 DEL 31/02 "
                        "ALLERTA GIALLA PER NEVE SU ZONA FVG-A",
                        published_at="2026-02-28T12:00:00+00:00",
                        links=(
                            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                            "Allerta_regionale_52-2026.pdf",
                        ),
                    )
                )
            )

    def test_rejects_unrecognized_or_partial_channel_page(self):
        for html in ("", "<html><body>Telegram</body></html>", '<div data-post="Other/1"></div>'):
            with self.subTest(html=html):
                with self.assertRaisesRegex(
                    OfficialTelegramParserError, "unrecognized_channel_page"
                ):
                    parse_official_telegram_channel(html)

    def test_fetch_verifies_the_current_official_pdf_bytes(self):
        page = channel_page(
            message(
                861,
                "#AllertameteoFVG - ALLERTA REGIONALE 22 DEL 2026<br>"
                "DALLE ORE 06:00 ALLE ORE 24:00 DI DOMENICA 26/07 "
                "ALLERTA GIALLA PER TEMPORALI FORTI SULLE ZONE FVG-A E FVG-C",
                published_at="2026-07-25T11:08:42+00:00",
                links=(PDF_22,),
            )
        )
        pdf = VALID_PDF
        page_response = _FakeResponse(text=page)
        pdf_response = _FakeResponse(
            content=pdf,
            headers={"Content-Type": "application/pdf", "Content-Length": str(len(pdf))},
            url=PDF_22,
        )
        session = _FakeSession(page_response, pdf_response)

        result = fetch_official_telegram_channel(
            session=session,
            now=lambda: datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
        )

        alert = result["alerts"][0]
        self.assertEqual(alert["pdf_sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(alert["pdf_size_bytes"], len(pdf))
        self.assertEqual(alert["pdf_verified_at"], "2026-07-26T12:00:00+00:00")
        self.assertTrue(session.calls[1][1]["stream"])
        self.assertTrue(pdf_response.closed)

    def test_fetch_downloads_only_the_one_active_pdf_from_mixed_history(self):
        messages = []
        for number, day in enumerate(range(2, 11), start=1):
            pdf_url = (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                f"Allerta_regionale_{number}-2026.pdf"
            )
            messages.append(
                message(
                    930 + number,
                    f"#AllertameteoFVG - ALLERTA REGIONALE {number} DEL 2026<br>"
                    f"DALLE ORE 00:00 ALLE ORE 12:00 DEL {day:02d}/07 "
                    "ALLERTA GIALLA PER TEMPORALI SU ZONA FVG-A",
                    published_at=f"2026-07-{day - 1:02d}T12:00:00+00:00",
                    links=(pdf_url,),
                )
            )

        active_pdf_url = (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
            "Allerta_regionale_10-2026.pdf"
        )
        messages.append(
            message(
                940,
                "#AllertameteoFVG - ALLERTA REGIONALE 10 DEL 2026<br>"
                "DALLE ORE 06:00 ALLE ORE 24:00 DEL 11/07 "
                "ALLERTA GIALLA PER TEMPORALI SU ZONA FVG-A",
                published_at="2026-07-10T12:00:00+00:00",
                links=(active_pdf_url,),
            )
        )
        pdf = VALID_PDF
        session = _FakeSession(
            _FakeResponse(text=channel_page(*messages)),
            _FakeResponse(
                content=pdf,
                headers={
                    "Content-Type": "application/pdf; charset=binary",
                    "Content-Length": str(len(pdf)),
                },
                url=active_pdf_url,
            ),
        )

        result = fetch_official_telegram_channel(
            session=session,
            now=lambda: datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[1][0], active_pdf_url)
        self.assertEqual(len(result["alerts"]), 10)
        self.assertEqual(
            [alert["alert_number"] for alert in result["alerts"] if "pdf_sha256" in alert],
            [10],
        )

    def test_fetch_verifies_an_issued_alert_before_its_validity_starts(self):
        page = channel_page(
            message(
                950,
                "#AllertameteoFVG - ALLERTA REGIONALE 30 DEL 2026<br>"
                "DALLE ORE 18:00 DEL 14/08 ALLE ORE 06:00 DEL 15/08 "
                "ALLERTA GIALLA PER TEMPORALI SU ZONA FVG-A",
                published_at="2026-08-14T10:00:00+00:00",
                links=(
                    "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                    "Allerta_regionale_30-2026.pdf",
                ),
            )
        )
        pdf_url = (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
            "Allerta_regionale_30-2026.pdf"
        )
        session = _FakeSession(
            _FakeResponse(text=page),
            _FakeResponse(
                content=VALID_PDF,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(VALID_PDF)),
                },
                url=pdf_url,
            ),
        )

        result = fetch_official_telegram_channel(
            session=session,
            now=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(result["alerts"][0]["pdf_sha256"], hashlib.sha256(VALID_PDF).hexdigest())

    def test_fetch_fails_closed_for_non_pdf_or_redirected_content(self):
        page = channel_page(
            message(
                861,
                "#AllertameteoFVG - ALLERTA REGIONALE 22 DEL 2026<br>"
                "DALLE ORE 06:00 ALLE ORE 24:00 DI DOMENICA 26/07 "
                "ALLERTA GIALLA PER TEMPORALI FORTI SULLE ZONE FVG-A E FVG-C",
                published_at="2026-07-25T11:08:42+00:00",
                links=(PDF_22,),
            )
        )
        cases = (
            _FakeResponse(
                content=b"<html>not a pdf</html>",
                headers={"Content-Type": "text/html"},
                url=PDF_22,
            ),
            _FakeResponse(
                content=b"%PDF-1.7\ncontent",
                headers={"Content-Type": "application/pdf"},
                url="https://example.invalid/redirect.pdf",
            ),
            _FakeResponse(
                content=VALID_PDF,
                headers={"Content-Type": "application/pdf"},
                url=(
                    "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                    "Allerta_regionale_21-2026.pdf"
                ),
            ),
            _FakeResponse(
                content=b"not really a PDF",
                headers={"Content-Type": "application/pdf"},
                url=PDF_22,
            ),
            _FakeResponse(
                content=VALID_PDF,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(VALID_PDF) + 1),
                },
                url=PDF_22,
            ),
            _FakeResponse(
                content=b"%PDF-1.7\nshort\n%%EOF",
                headers={"Content-Type": "application/pdf"},
                url=PDF_22,
            ),
            _FakeResponse(
                content=b"%PDF-1.7\ncontent",
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Length": str(12 * 1024 * 1024 + 1),
                },
                url=PDF_22,
            ),
        )
        for pdf_response in cases:
            with self.subTest(url=pdf_response.url):
                session = _FakeSession(_FakeResponse(text=page), pdf_response)
                with self.assertRaises(OfficialTelegramParserError):
                    fetch_official_telegram_channel(
                        session=session,
                        now=lambda: datetime(
                            2026, 7, 26, 12, 0, tzinfo=timezone.utc
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
