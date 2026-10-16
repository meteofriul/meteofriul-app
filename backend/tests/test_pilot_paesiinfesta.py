import json
import unittest
from datetime import date

from app.events.pilot_paesiinfesta import (
    BASE, LISTS, SURFACES, SITEMAP_INDEX, SOURCE, carnevale_exclusion,
    collect_paesiinfesta,
    detail_event, listing_cards, listing_range, municipality, presepi_events,
    sitemap_delta, sitemap_detail_event, surface_cards,
)
from app.events.pilot_source_policy import gate_batch


RAUSCEDO = ('https://paesiinfesta.com/friuli-venezia-giulia/pordenone/'
            'sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/')
CAMPOFORMIDO = 'https://paesiinfesta.com/friuli-venezia-giulia/udine/campoformido/'


def card(url, *, region, locality, label, dates, category='sagra'):
    return (f'<div class="e-loop-item type-post category-{category} regione-{region}">'
            f'<h2><a href="{url}">{locality}</a></h2>'
            f'<div class="elementor-widget-text-editor">{label}</div>'
            f'<div class="elementor-widget-text-editor">{dates}</div></div>')


def detail(*, title='Le Radici del Vino', start='09/10/2026', end='11/10/2026',
           schema=True, reenactment=False,
           locality='Rauscedo di San Giorgio della Richinvelda',
           municipality_name='San Giorgio della Richinvelda'):
    heads = ('<h2>Campoformido</h2><h1>Un giorno con Napoleone</h1>' if reenactment
             else f'<h1>Sagra di {locality}</h1><h2>{title}</h2>')
    event_schema = {'@type': 'Event', 'name': locality,
                    'startDate': f'{start[6:]}-{start[3:5]}-{start[:2]}',
                    'endDate': f'{end[6:]}-{end[3:5]}-{end[:2]}',
                    'description': f'Comune di {municipality_name}'}
    structured = (f'<script type="application/ld+json">{json.dumps(event_schema)}</script>'
                  if schema else '')
    intro = ('<div class="elementor-widget-text-editor">'
             'La rievocazione storica Un giorno con Napoleone si svolge a Campoformido.'
             '</div>' if reenactment else '')
    return (heads + f'<div class="elementor-widget-text-editor">dal {start}</div>'
            f'<div class="elementor-widget-text-editor">al {end}</div>'
            + intro + '<h3>PROGRAMMA</h3>' + structured)


def sitemap_pages(*urls, modified='2026-09-01T10:00:00+00:00'):
    post_map = BASE + '/post-sitemap1.xml'
    return {SITEMAP_INDEX: '<sitemapindex><sitemap><loc>' + post_map
            + '</loc></sitemap></sitemapindex>',
            post_map: '<urlset>' + ''.join(
                '<url><loc>' + url + '</loc><lastmod>' + modified
                + '</lastmod></url>' for url in urls) + '</urlset>'}


class Response:
    def __init__(self, url, html):
        self.url, self.html, self.status_code = url, html, 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.html.encode('utf-8')


class PaesiInFestaTests(unittest.TestCase):
    def test_explicit_schema_municipality_stops_before_organizer(self):
        town = municipality('San Paolo al Tagliamento',
                            'Comune di Morsano al Tagliamento Pro Loco San Paolo')
        self.assertEqual(town.name, 'Morsano al Tagliamento')
        self.assertIsNone(municipality('San Paolo al Tagliamento',
                                       'La festa ricorda Morsano al Tagliamento'))

    def test_listing_dates_cover_apostrophes_cross_year_and_enumerated_days(self):
        examples = [
            ('dal 24 settembre all’11 ottobre 2026', '2026-09-24', '2026-10-11'),
            ('9^ Fiera dal 9 all’11 ottobre 2026', '2026-10-09', '2026-10-11'),
            ('dall’8 al 18 ottobre 2026', '2026-10-08', '2026-10-18'),
            ('dal 8 dicembre 2026 al 17 gennaio 2027', '2026-12-08', '2027-01-17'),
            ('19-20 Settembre 2026', '2026-09-19', '2026-09-20'),
            ('9 – 10 – 11 Ottobre 2026', '2026-10-09', '2026-10-11'),
        ]
        for value, start, end in examples:
            with self.subTest(value=value):
                self.assertEqual(tuple(map(str, listing_range(value))), (start, end))

    def test_listing_deduplicates_main_cards_and_ignores_footer_carousel(self):
        entry = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        html = '<main id="content">' + entry + entry + '</main><footer>' + entry + '</footer>'
        found = listing_cards(html, kind='sagre')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['url'], RAUSCEDO)

    def test_detail_uses_event_title_and_checks_both_date_surfaces(self):
        entry = {'url': RAUSCEDO, 'kind': 'sagre',
                 'locality': 'Rauscedo di San Giorgio della Richinvelda',
                 'label': 'Le Radici del Vino',
                 'date_text': '9^ Fiera Viticoltura d’Eccellenza dal 9 all’11 ottobre 2026'}
        event = detail_event(detail(), entry, today=date(2026, 10, 6))
        self.assertEqual((event['title'], event['event_city'], event['start_date']),
                         ('Le Radici del Vino', 'San Giorgio della Richinvelda', '2026-10-09'))
        self.assertEqual(event['description_source_url'], RAUSCEDO)
        with self.assertRaisesRegex(ValueError, 'listing/detail date conflict'):
            detail_event(detail(start='10/10/2026'), entry, today=date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, 'visible/structured date conflict'):
            detail_event(detail().replace('2026-10-09', '2025-10-09'), entry,
                         today=date(2026, 10, 6))

    def test_presepi_child_dates_override_stale_parent_header(self):
        html = ('<h1>Sagra di Appuntamenti con i Presepi</h1>'
                '<div>dal 07/12/2025</div><div>al 18/01/2026</div>'
                '<div class="elementor-widget-text-editor">'
                '<h4>CANEVA (PN)<br>Dal 13 dicembre 2026 al 6 gennaio 2027</h4>'
                '<p>Rassegna Presepi in Castello. La rassegna è allestita nel borgo.</p>'
                '<h4>CASTELMONTE – Santuario (UD)<br>Dal 24 dicembre 2026 al 6 gennaio 2027</h4>'
                '<p>Il presepio è allestito presso la cripta del Santuario.</p>'
                '<h4>POFFABRO (FRISANCO – PN)<br>Dall’8 dicembre 2026 al 10 gennaio 2027</h4>'
                '<p>Presepe tra i presepi nelle vie del borgo.</p>'
                '<h4>ANNONE VENETO (VE)<br>Dal 24 dicembre 2026 al 10 gennaio 2027</h4>'
                '<p>Presepio Vivente di Annone Veneto.</p>'
                '<h4>SPILIMBERGO (PN)<br>Dicembre 2026 – Gennaio 2027</h4>'
                '<p>Presepio di mosaico.</p></div>')
        entry = {'url': 'https://paesiinfesta.com/appuntamenti-con-i-presepi/',
                 'date_text': 'dal 8 dicembre 2026 al 10 gennaio 2027'}
        events, excluded = presepi_events(html, entry, today=date(2026, 10, 6))
        self.assertEqual(len(events), 3)
        self.assertEqual({event['event_city'] for event in events},
                         {'Caneva', 'Prepotto', 'Frisanco'})
        self.assertEqual({item['reason'] for item in excluded},
                         {'outside_fvg', 'month_only_period'})

    def test_provisional_cross_town_carnival_is_not_one_event(self):
        html = ('<h1>Carnevale in piazza</h1><h2>Sfilate con i Carri Allegorici</h2>'
                '<p>Il calendario delle sfilate è stato realizzato in base al '
                'calendario pregresso 2026.</p>')
        self.assertIsNone(carnevale_exclusion(html))
        with self.assertRaisesRegex(ValueError, 'provisional notice changed'):
            carnevale_exclusion(html.replace('calendario pregresso 2026', 'nuove conferme'))

    def test_cross_check_detects_new_active_card_and_archived_conflict(self):
        extra = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        found, examined = surface_cards(extra, surface='home', today=date(2026, 10, 6))
        self.assertEqual((len(found), examined), (1, 1))
        archived = extra.replace('category-sagra',
                                 'category-sagra category-eventi-passati')
        with self.assertRaisesRegex(ValueError, 'active card marked archived'):
            surface_cards(archived, surface='archive', today=date(2026, 10, 6))
        # The archive label can flip on the last scheduled day. The dated
        # listing and detail still identify an event ending today.
        found, examined = surface_cards(archived, surface='archive',
                                        today=date(2026, 10, 11))
        self.assertEqual((len(found), examined), (1, 1))

    def test_sitemap_delta_publishes_verified_unlisted_sagra(self):
        pages = sitemap_pages(RAUSCEDO, modified='2026-10-07T10:00:00+00:00')
        pages[RAUSCEDO] = ('<meta name="description" content="Le Radici del Vino '
                           'presenta degustazioni e incontri a Rauscedo.">' + detail())

        def get(url, **_):
            return Response(url, pages[url])

        proof, events, review = sitemap_delta(get, {}, today=date(2026, 10, 6))
        self.assertEqual((proof['changed_unlisted'], proof['changed_checked']), (1, 1))
        self.assertEqual(review, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_city'], 'San Giorgio della Richinvelda')
        self.assertEqual(events[0]['description_source_url'], RAUSCEDO)
        self.assertEqual(events[0]['discovery_kind'], 'sitemap')
        overlap = {'url': BASE + '/other/', 'locality': 'Rauscedo di San Giorgio della Richinvelda',
                   'label': 'Altro titolo', 'date_text': 'dal 9 all’11 ottobre 2026'}
        _, events, review = sitemap_delta(get, {overlap['url']: overlap},
                                          today=date(2026, 10, 6))
        self.assertEqual(events, [])
        self.assertIn('overlaps listed event', review[0]['reason'])
        pages[RAUSCEDO] = detail(start='01/09/2026', end='02/09/2026')
        proof, events, review = sitemap_delta(get, {}, today=date(2026, 10, 6))
        self.assertEqual(events, [])
        self.assertEqual(review, [])

    def test_sitemap_only_reenactment_and_conflicting_schema(self):
        event = sitemap_detail_event(detail(schema=False, reenactment=True),
                                     CAMPOFORMIDO, today=date(2026, 10, 6))
        self.assertEqual((event['title'], event['event_city']),
                         ('Un giorno con Napoleone', 'Campoformido'))
        self.assertEqual(event['description_source_url'], CAMPOFORMIDO)
        changed = detail().replace('2026-10-09', '2025-10-09')
        with self.assertRaisesRegex(ValueError, 'visible/structured dates conflict'):
            sitemap_detail_event(changed, RAUSCEDO, today=date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, 'programme missing'):
            sitemap_detail_event(detail().replace('<h3>PROGRAMMA</h3>', ''),
                                 RAUSCEDO, today=date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, 'municipality unresolved or conflicting'):
            sitemap_detail_event(detail(municipality_name='Pordenone'),
                                 RAUSCEDO, today=date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, 'URL/province conflict'):
            sitemap_detail_event(detail(),
                                 BASE + '/friuli-venezia-giulia/udine/rauscedo/',
                                 today=date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, 'title/date year conflict'):
            sitemap_detail_event(detail(title='Le Radici del Vino 2027'),
                                 RAUSCEDO, today=date(2026, 10, 6))

    def test_collector_reads_every_discovered_fvg_detail_and_gate_checks_count(self):
        sagra = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        reenactment = card(CAMPOFORMIDO, region='friuli-venezia-giulia',
                           locality='Campoformido', label='Un giorno con Napoleone',
                           dates='9 – 10 – 11 Ottobre 2026',
                           category='rievocazione-storica')
        pages = {LISTS['sagre']: '<main id="content">' + sagra + '</main>',
                 LISTS['rievocazioni']: '<main id="content">' + reenactment + '</main>',
                 RAUSCEDO: detail(),
                 CAMPOFORMIDO: detail(schema=False, reenactment=True)}
        pages.update({url: sagra + reenactment for url in SURFACES.values()})
        pages.update(sitemap_pages(RAUSCEDO, CAMPOFORMIDO))
        calls = []

        def get(url, **_):
            calls.append(url)
            return Response(url, pages[url])

        batch = collect_paesiinfesta(get=get, today=date(2026, 10, 6))
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(len(batch['events']), 2)
        self.assertEqual(set(calls), set(pages))
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'ok')
        batch['verification']['detail_pages_read'] = 1
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'error')

    def test_one_conflicting_card_is_quarantined_without_hiding_valid_card(self):
        sagra = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        reenactment = card(CAMPOFORMIDO, region='friuli-venezia-giulia',
                           locality='Campoformido', label='Un giorno con Napoleone',
                           dates='9 – 10 – 11 Ottobre 2026',
                           category='rievocazione-storica')
        pages = {LISTS['sagre']: '<main id="content">' + sagra + '</main>',
                 LISTS['rievocazioni']: '<main id="content">' + reenactment + '</main>',
                 RAUSCEDO: detail(),
                 CAMPOFORMIDO: detail(schema=False, reenactment=True)}
        pages.update({url: sagra + reenactment for url in SURFACES.values()})
        pages.update(sitemap_pages(RAUSCEDO, CAMPOFORMIDO))

        def get(url, **_):
            return Response(url, pages[url])

        archive_tag = reenactment.replace('category-rievocazione-storica',
                                          'category-rievocazione-storica category-eventi-passati')
        pages[SURFACES['archive']] = sagra + archive_tag
        batch = collect_paesiinfesta(get=get, today=date(2026, 10, 6))
        gated = gate_batch(SOURCE, batch, today=date(2026, 10, 6))
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual({item['url'] for item in gated['events']}, {RAUSCEDO})
        self.assertEqual(gated['review_required'], [
            {'url': CAMPOFORMIDO, 'reason': 'future_card_marked_archived'}])
        self.assertEqual(batch['verification']['quarantined_before_detail'], 1)

        pages[SURFACES['archive']] = sagra + reenactment
        pages[CAMPOFORMIDO] = detail(schema=False, reenactment=True,
                                    end='12/10/2026')
        batch = collect_paesiinfesta(get=get, today=date(2026, 10, 6))
        gated = gate_batch(SOURCE, batch, today=date(2026, 10, 6))
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual({item['url'] for item in gated['events']}, {RAUSCEDO})
        self.assertEqual(gated['review_required'][0]['url'], CAMPOFORMIDO)
        self.assertEqual(gated['review_required'][0]['reason'], 'detail_conflict')
        self.assertEqual(batch['verification']['quarantined_before_detail'], 0)

    def test_new_provincial_card_enters_same_detail_gate(self):
        sagra = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        reenactment = card(CAMPOFORMIDO, region='friuli-venezia-giulia',
                           locality='Campoformido', label='Un giorno con Napoleone',
                           dates='9 – 10 – 11 Ottobre 2026',
                           category='rievocazione-storica')
        pages = {LISTS['sagre']: '<main id="content">' + sagra + '</main>',
                 LISTS['rievocazioni']: '<main id="content">' + reenactment + '</main>',
                 RAUSCEDO: detail(),
                 CAMPOFORMIDO: detail(schema=False, reenactment=True)}
        pages.update({url: sagra + reenactment for url in SURFACES.values()})
        pages.update(sitemap_pages(RAUSCEDO, CAMPOFORMIDO))
        extra_url = ('https://paesiinfesta.com/friuli-venezia-giulia/pordenone/'
                     'sagra-di-rauscedo-di-gan-giorgio-della-richinvelda-nuova/')
        extra = card(extra_url, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        pages[SURFACES['pordenone']] += extra
        pages[extra_url] = detail()

        def get(url, **_):
            return Response(url, pages[url])

        batch = collect_paesiinfesta(get=get, today=date(2026, 10, 6))
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual({event['url'] for event in batch['events']},
                         {RAUSCEDO, CAMPOFORMIDO, extra_url})
        self.assertEqual(batch['verification']['extra_active_urls'], 1)
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'ok')

    def test_sitemap_only_event_enters_collector_and_publication_gate(self):
        sagra = card(RAUSCEDO, region='friuli-venezia-giulia',
                     locality='Rauscedo di San Giorgio della Richinvelda',
                     label='Le Radici del Vino', dates='dal 9 all’11 ottobre 2026')
        reenactment = card(CAMPOFORMIDO, region='friuli-venezia-giulia',
                           locality='Campoformido', label='Un giorno con Napoleone',
                           dates='9 – 10 – 11 Ottobre 2026',
                           category='rievocazione-storica')
        new_url = BASE + '/friuli-venezia-giulia/pordenone/sagra-di-cordenons-nuova/'
        pages = {LISTS['sagre']: '<main id="content">' + sagra + '</main>',
                 LISTS['rievocazioni']: '<main id="content">' + reenactment + '</main>',
                 RAUSCEDO: detail(),
                 CAMPOFORMIDO: detail(schema=False, reenactment=True),
                 new_url: detail(title='Festa delle Zucche', start='24/10/2026',
                                 end='25/10/2026', locality='Cordenons',
                                 municipality_name='Cordenons')}
        pages.update({url: sagra + reenactment for url in SURFACES.values()})
        pages.update(sitemap_pages(RAUSCEDO, CAMPOFORMIDO, new_url,
                                   modified='2026-10-07T10:00:00+00:00'))

        def get(url, **_):
            return Response(url, pages[url])

        batch = collect_paesiinfesta(get=get, today=date(2026, 10, 6))
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(batch['verification']['sitemap']['active_added'], 1)
        self.assertEqual({event['url'] for event in batch['events']},
                         {RAUSCEDO, CAMPOFORMIDO, new_url})
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
