"""The official distributor keeps LITS coverage available during IR outages."""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from scripts import scan


class LiteStrategyWireTests(TestCase):
    def test_issuer_outage_uses_only_dated_lite_strategy_wire_releases(self):
        date = datetime.now(timezone.utc).strftime('%B %d, %Y')
        title = 'Lite Strategy Announces Litecoin Treasury Income'
        path = '/news-release/2026/10/13/3380049/0/en/lite-strategy-release.html'

        def row(issuer, href, stamp=date):
            return f'''<div class="newsLink"><div class="date-source">
                <span>{stamp}</span><span>Source: <a class="sourceLink">{issuer}</a></span>
                </div><div class="mainLink"><a href="{href}">{title}</a></div>
                <div class="newsTxt">Lite Strategy reports income on its Litecoin treasury.</div></div>'''

        archive = (row('Lite Strategy, Inc.', path)
                   + row('Another Company', '/news-release/other.html')
                   + row('Lite Strategy, Inc.', 'https://example.com/news-release/spoof.html')
                   + row('Lite Strategy, Inc.', '/news-release/undated.html', ''))

        def fetch(url):
            if url in (scan.LITS_IR_URL, scan.LITS_IR_FALLBACK):
                raise RuntimeError('IR host unavailable')
            self.assertEqual(url, scan.LITS_WIRE_URL)
            return Mock(text=archive)

        with patch.object(scan, 'fetch', side_effect=fetch):
            rows = scan.fetch_lits_news()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://rss.globenewswire.com' + path)
        self.assertEqual(rows[0]['published_at'], scan.normalize_date(date, date_only=True))
        self.assertTrue(rows[0]['date_only'])
        self.assertEqual(rows[0]['source_type'], 'Official')
        self.assertEqual(rows[0]['source_id'], 'lits')
        self.assertEqual(rows[0]['entities'], ['Lite Strategy'])
        self.assertIn('GlobeNewswire', rows[0]['source'])
