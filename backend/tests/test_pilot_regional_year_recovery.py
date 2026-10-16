import unittest
from datetime import date

from app.events.pilot_regional_year_recovery import (
    recover_barcolana_2026_locale, recover_calendar_anchored_weekends,
    recover_current_year_detail,
    recover_discrete_edition, recover_end_only_exhibition,
    recover_month_range_exhibition, recover_prior_edition_in_description,
)


TODAY = date(2026, 10, 5)
BASE = 'https://www.turismofvg.it/eventi/'


def html(title, date_text, description, *, category=None):
    category_row = (f'<div style="background-image: url(icn__tag.svg)">'
                    f'{category}</div>' if category else '')
    return (f'<h1>{title}</h1><div class="body_col1"><h2>Descrizione</h2>'
            f'<p>{description}</p></div><div class="body_col2">'
            f'{category_row}'
            '<div style="background-image: url(icn__calendar.svg)">'
            f'{date_text}</div>'
            '<div style="background-image: url(icn__pin.svg)">Moggio Udinese</div>'
            '</div><div class="c-detail__actions"></div>')


def entry(url, title, badges=None):
    return {'kind': 'calendar', 'identity_conflict': False,
            'candidate': {'source': 'TurismoFVG', 'url': url, 'title': title,
                          'event_city': 'Moggio Udinese',
                          'discovery_kind': 'filtered_calendar',
                          'listing_occurrences': badges or []}}


class RegionalYearRecoveryTests(unittest.TestCase):
    def test_barcolana_2026_reconciles_only_verified_german_detail(self):
        url = BASE + '58a-ed-barcolana'
        listing = entry(url, '58a Ed. Barcolana.')
        listing['candidate']['event_city'] = 'Trieste'
        source = html('58. Barcolana',
                      'Freitag, 2. Oktober 2026 - Sonntag, 11. Oktober 2026',
                      'Barcolana 58 findet vom 2. bis 11. Oktober 2026 statt.').replace(
                          'Moggio Udinese', 'Triest')
        result = recover_barcolana_2026_locale(url, listing, source, today=TODAY)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual((result['event']['start_date'], result['event']['end_date']),
                         ('2026-10-02', '2026-10-11'))
        self.assertEqual(result['event']['event_city'], 'Trieste')
        self.assertNotIn('description_excerpt', result['event'])
        self.assertIsNone(recover_barcolana_2026_locale(
            url, listing, source.replace('11. Oktober', '12. Oktober'), today=TODAY))
        self.assertIsNone(recover_barcolana_2026_locale(
            url, listing, source, today=date(2027, 10, 5)))

    def test_yearless_weekend_show_needs_calendar_and_recent_sitemap_anchor(self):
        url = BASE + 'articolo-8'
        source = html(
            'Articolo 8', 'Venerdì, sabato e domenica fino al 29 novembre',
            'Da sabato 12 settembre la mostra è aperta. Sarà visitabile ogni '
            'venerdì, sabato e domenica fino al 29 novembre.',
            category='Mostre')
        candidate = {**entry(url, 'Articolo 8'), 'in_sitemap': True,
                     'sitemap_lastmod': '2026-09-11T10:21:28Z'}
        result = recover_calendar_anchored_weekends(
            url, candidate, source, today=TODAY)
        self.assertEqual(result['event']['start_date'], '2026-09-12')
        self.assertEqual(result['event']['end_date'], '2026-11-29')
        self.assertIsNone(recover_calendar_anchored_weekends(
            url, {**candidate, 'sitemap_lastmod': '2025-09-11T10:21:28Z'},
            source, today=TODAY))
        self.assertIsNone(recover_calendar_anchored_weekends(
            url, candidate,
            source.replace('sabato 12 settembre', 'sabato 13 settembre'),
            today=TODAY))
        self.assertIsNone(recover_calendar_anchored_weekends(
            url, candidate, source.replace('Articolo 8</h1>', 'Un altro evento</h1>'),
            today=TODAY))

    def test_sitemap_exhibition_explicitly_ended_in_prior_edition(self):
        source = html('Mostra Presepi',
                      "Natale a Moggio dall'11 dicembre al 15 gennaio",
                      "Orari Mostra dal 24 dicembre all'8 gennaio 2023.",
                      category='Mostre')
        entry = {'kind': 'sitemap_only',
                 'sitemap_lastmod': '2022-12-23T18:19:52Z'}
        result = recover_prior_edition_in_description(entry, source, today=TODAY)
        self.assertEqual(result['status'], 'past_event')
        self.assertEqual(result['programme_year'], 2023)
        self.assertIsNone(recover_prior_edition_in_description(
            entry, source.replace('2023', '2026'), today=TODAY))
        self.assertIsNone(recover_prior_edition_in_description(
            {**entry, 'kind': 'calendar'}, source, today=TODAY))

    def test_cross_year_list_keeps_only_exact_current_year_days(self):
        url = BASE + 'lo-scrigno'
        source = html('Lo scrigno del Doge',
                      '25 aprile, 2 giugno, 20 settembre, 1° novembre, '
                      '8 dicembre 2026 e 6 gennaio 2027',
                      'Mercatino di antiquariato e modernariato.')
        candidate = entry(url, 'Lo scrigno del Doge', [
            '2026-01-06', '2026-04-25', '2026-11-01', '2026-12-08'])
        result = recover_discrete_edition(url, candidate, source, today=TODAY)
        self.assertEqual(result['event']['verified_programme_occurrences'], [
            '2026-04-25', '2026-06-02', '2026-09-20',
            '2026-11-01', '2026-12-08'])
        self.assertEqual(result['ignored_listing_occurrences'], ['2026-01-06'])
        self.assertEqual(result['event']['end_date'], '2026-12-08')
        self.assertIsNone(recover_discrete_edition(
            url, candidate, source.replace('e 6 gennaio', 'e dal 6 gennaio'),
            today=TODAY))
        bad_badge = entry(url, 'Lo scrigno del Doge', ['2026-10-31'])
        self.assertIsNone(recover_discrete_edition(
            url, bad_badge, source, today=TODAY))

    def test_exhibition_month_range_keeps_month_precision(self):
        url = BASE + 'radici-nella-pietra'
        source = html('Radici nella pietra', 'Maggio 2026',
                      'Mostra fotografica: maggio - dicembre 2026.',
                      category='Mostre')
        result = recover_month_range_exhibition(
            url, entry(url, 'Radici nella pietra', ['2026-05-29']),
            source, today=TODAY)
        self.assertEqual(result['event']['schedule_kind'], 'month_range')
        self.assertEqual(result['event']['date_label'], 'maggio–dicembre 2026')
        self.assertEqual(result['event']['end_date'], '2026-12-31')
        self.assertIsNone(recover_month_range_exhibition(
            url, entry(url, 'Radici nella pietra'),
            source.replace('maggio - dicembre 2026', 'maggio 2026'),
            today=TODAY))

    def test_public_day_inside_month_needs_matching_weekday(self):
        url = BASE + 'risvegli'
        source = html('Risvegli', 'ottobre 2026',
                      'Il momento pubblico principale sarà domenica 11 ottobre, '
                      'giornata conclusiva delle residenze.')
        result = recover_current_year_detail(
            url, entry(url, 'Risvegli'), source, today=TODAY)
        self.assertEqual(result['event']['verified_programme_occurrences'],
                         ['2026-10-11'])
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Risvegli'),
            source.replace('domenica 11 ottobre', 'sabato 11 ottobre'),
            today=TODAY))

    def test_named_programme_dates_require_correct_weekdays(self):
        url = BASE + 'autunno-nei-libri-2026'
        description = ('Programma: Venerdì 9 ottobre ore 20.30 - Storie; '
                       'Sabato 24 ottobre ore 20.30 - Cronache; '
                       'Venerdì 6 novembre ore 18.00 - Atomo.')
        source = html('Autunno nei Libri 2026', 'Autunno nei libri 2026',
                      description)
        result = recover_current_year_detail(
            url, entry(url, 'Autunno nei Libri 2026'), source, today=TODAY)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['event']['verified_programme_occurrences'],
                         ['2026-10-09', '2026-10-24', '2026-11-06'])
        self.assertEqual(result['detail_date_full'], 'Autunno nei libri 2026')
        self.assertIn('9 ottobre 2026', result['resolved_date_full'])
        self.assertIn('description_excerpt', result['event'])
        wrong_weekday = source.replace('Venerdì 9 ottobre', 'Giovedì 9 ottobre')
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Autunno nei Libri 2026'), wrong_weekday,
            today=TODAY))

    def test_exhibition_period_needs_explicit_year_in_date_row(self):
        url = BASE + 'biocomics'
        description = ('La mostra sarà visitabile dal giorno 19 settembre '
                       'al 18 ottobre nelle giornate di venerdì, sabato e domenica.')
        source = html('Biocomics', 'Gnots a Mueç 2026', description)
        result = recover_current_year_detail(
            url, entry(url, 'Biocomics'), source, today=TODAY)
        self.assertEqual((result['event']['start_date'], result['event']['end_date']),
                         ('2026-09-19', '2026-10-18'))
        self.assertNotIn('verified_programme_occurrences', result['event'])
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Biocomics'), source.replace('2026', '2025'),
            today=TODAY))

    def test_two_programme_periods_need_year_repeated_in_detail(self):
        url = BASE + 'saperi-sapori-fvg'
        row = 'dal 2 al 5 ottobre e dal 9 al 12 ottobre'
        source = html('Saperi & Sapori FVG', row,
                      'La manifestazione si svolgerà dal 2 al 5 ottobre e '
                      'dal 9 al 12 ottobre 2026.')
        result = recover_current_year_detail(
            url, entry(url, 'Saperi & Sapori FVG'), source, today=TODAY)
        days = result['event']['verified_programme_occurrences']
        self.assertEqual((days[0], days[-1], len(days)),
                         ('2026-10-02', '2026-10-12', 8))
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Saperi & Sapori FVG'),
            source.replace('2026', '2027'), today=TODAY))
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Saperi & Sapori FVG', ['2026-10-08']),
            source, today=TODAY))

    def test_weekend_exhibition_needs_explicit_year_and_matching_weekdays(self):
        url = BASE + 'mostra-fotografica'
        source = html(
            'Mostra fotografica', 'Venerdì, sabato e domenica fino al 29 novembre',
            'Da sabato 12 settembre 2026 la mostra è aperta. La mostra sarà '
            'visitabile ogni venerdì, sabato e domenica fino al 29 novembre.')
        result = recover_current_year_detail(
            url, entry(url, 'Mostra fotografica'), source, today=TODAY)
        self.assertEqual((result['event']['start_date'], result['event']['end_date']),
                         ('2026-09-12', '2026-11-29'))
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Mostra fotografica'),
            source.replace('settembre 2026', 'settembre'), today=TODAY))
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'Mostra fotografica'),
            source.replace('sabato 12 settembre', 'sabato 13 settembre'),
            today=TODAY))
        self.assertIsNone(recover_current_year_detail(
            url, {'kind': 'sitemap_only'}, source, today=TODAY))


    def test_end_only_row_needs_correlated_opening_and_daily_end(self):
        url = BASE + 'mostra-c-era-una-volta'
        description = (
            'Nel 2024 la cineteca ha acquisito il fondo. La mostra si '
            'inaugura venerdì 1 maggio alle ore 11. Sarà aperta tutti '
            'i giorni fino al 15 novembre 2026.')
        source = html('C\'era una volta', 'Fino al 15 novembre 2026',
                      description)
        result = recover_current_year_detail(
            url, entry(url, 'C\'era una volta'), source, today=TODAY)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual((result['event']['start_date'],
                          result['event']['end_date']),
                         ('2026-05-01', '2026-11-15'))
        self.assertIn('Fino al 15 novembre 2026', result['detail_date_full'])
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'C\'era una volta'),
            source.replace('venerdì 1 maggio', 'giovedì 1 maggio'),
            today=TODAY))
        self.assertIsNone(recover_current_year_detail(
            url, entry(url, 'C\'era una volta'),
            source.replace('15 novembre 2026.', '16 novembre 2026.'),
            today=TODAY))

    def test_end_only_exhibition_keeps_opening_date_unknown(self):
        url = BASE + 'mostra-memorie-riflesse'
        source = html(
            'Mostra Memorie riflesse', 'Fino al 7 gennaio 2027',
            'Orari di apertura Giovedì e Venerdì: 10.30-12.30. '
            'Sabato e domenica: 10.00-12.30.', category='Mostre')
        result = recover_end_only_exhibition(
            url, entry(url, 'Mostra Memorie riflesse'), source, today=TODAY)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertIsNone(result['event']['start_date'])
        self.assertEqual(result['event']['end_date'], '2027-01-07')
        self.assertEqual(result['event']['date_evidence'],
                         'Fino al 7 gennaio 2027')
        self.assertIsNone(recover_end_only_exhibition(
            url, entry(url, 'Mostra Memorie riflesse'),
            source.replace('Orari di apertura', 'Informazioni'), today=TODAY))
        self.assertIsNone(recover_end_only_exhibition(
            url, entry(url, 'Mostra Memorie riflesse', ['2026-10-08']),
            source, today=TODAY))


if __name__ == '__main__':
    unittest.main()
