import unittest
from app.events.engine import extract_turismofvg_detail_metadata


class LabelledDetailTests(unittest.TestCase):
    def row(self, icon, value):
        return f'<div style="background-image: url(\'icn__{icon}.svg\');">{value}</div>'

    def test_clock_is_not_venue_and_address_retains_break(self):
        html = ''.join(self.row(k, v) for k, v in [
            ('calendar', 'lunedì 7 settembre 2026'), ('pin--red', 'Pordenone'),
            ('clock--red', '16:00'), ('building', 'Palazzo Gregoris<br>Corso Vittorio Emanuele, 44'),
            ('people', 'Tutti')])
        result = extract_turismofvg_detail_metadata(html)
        self.assertEqual(result['time'], '16:00')
        self.assertEqual(result['venue'], 'Palazzo Gregoris')
        self.assertEqual(result['address'], 'Corso Vittorio Emanuele, 44')
        self.assertEqual(result['audience'], 'Tutti')

    def test_missing_venue_does_not_promote_audience(self):
        result = extract_turismofvg_detail_metadata(self.row('calendar', '7 settembre 2026') +
            self.row('pin--red', 'Pordenone') + self.row('people', 'Tutti'))
        self.assertNotIn('venue', result)
        self.assertNotIn('time', result)
        self.assertEqual(result['event_city'], 'Pordenone')
