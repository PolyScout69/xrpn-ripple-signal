"""Offline regression tests for the 30-day weighted Moon Sentiment index."""
from datetime import datetime, timedelta, timezone
import unittest

from scripts.sentiment import aggregate_sentiment

AS_OF = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)


def story(title, asset='XRPN', value=1, impact='Medium', age=1,
          source_type='Media', scenario='reported', identifier=None, score=76):
    published = AS_OF - timedelta(days=age)
    return {
        'id': identifier or title, 'title': title,
        'published_at': published.isoformat().replace('+00:00', 'Z'),
        'entities': [{'XRPN': 'Evernorth', 'MSTR': 'Strategy', 'SBET': 'SharpLink Gaming'}[asset]],
        'source_type': source_type, 'category': 'Treasury',
        'impact': impact, 'score': score,
        'url': 'https://example.com/' + str(len(title)),
        'moon_meters': [{
            'asset': asset, 'value': value, 'scenario': scenario,
            'reason': 'If true, this may affect the issuer.'
        }]
    }


class SentimentTests(unittest.TestCase):
    def check(self, items, ticker='XRPN'):
        return aggregate_sentiment(items, AS_OF)[ticker]

    def test_all_neutral_is_neutral_not_bullish(self):
        s = self.check([story(f'Routine XRPN update {i}', value=0, impact='High')
                        for i in range(20)])
        self.assertEqual(s['value'], 0)
        self.assertEqual(s['directional_events'], 0)

    def test_neutral_headlines_do_not_drown_material_news(self):
        items = [story(f'Generic XRPN routine report {i}', value=0, impact='High')
                 for i in range(18)]
        items.extend([
            story('XRPN important strategic treasury launch', value=2, impact='High'),
            story('XRPN material profitable commercial deal', value=2, impact='High'),
        ])
        s = self.check(items)
        self.assertGreaterEqual(s['value'], 1)
        self.assertEqual(s['directional_events'], 2)
        self.assertEqual(s['stories'], 20)

    def test_major_negative_event_outweighs_many_minor_positives(self):
        items = [
            story('XRPN severe drawdown', value=-3, impact='High', age=1),
            story('XRPN small update alpha', value=1, impact='Low', age=5),
            story('XRPN small update beta', value=1, impact='Low', age=6),
            story('XRPN small update gamma', value=1, impact='Low', age=7),
        ]
        s = self.check(items)
        self.assertLess(s['value'], 0)

    def test_material_positive_outweighs_minor_negative(self):
        s = self.check([
            story('XRPN major positive treasury event', value=2, impact='High', age=1),
            story('XRPN minor operational risk', value=-1, impact='Low', age=10),
        ])
        self.assertGreaterEqual(s['value'], 1)

    def test_deduplicated_family_does_not_manufacture_bullishness(self):
        a = story('Evernorth partners with Kraken for XRP yield', value=2, identifier='a')
        b = story('Evernorth announces XRP yield with Coinbase', value=2, identifier='b')
        c = story('Evernorth equity facility may dilute shareholders', value=-1, identifier='c')
        s = self.check([a, b, c])
        self.assertEqual(s['stories'], 3)
        self.assertEqual(s['independent_events'], 2)
        self.assertEqual(s['directional_events'], 2)

    def test_same_strc_repurchase_headlined_in_reverse_word_order_counts_once(self):
        items=[
            story('Strategy pauses Bitcoin purchases, makes STRC preferred buyback',
                  'MSTR', value=1, identifier='a'),
            story('STRC repurchases hit $205 million at Strategy',
                  'MSTR', value=1, identifier='b'),
            story('MSTR buyback of STRC preferred totals $205 million',
                  'MSTR', value=1, identifier='c'),
        ]
        summary=self.check(items,ticker='MSTR')
        self.assertEqual(summary['stories'],3)
        self.assertEqual(summary['directional_events'],1)

    def test_repeated_weekly_story_has_one_catalyst_theme(self):
        rows=[
            story('Strategy repurchases $200m STRC preferred', 'MSTR', value=2, age=1),
            story('Strategy STRC buyback reaches $190m', 'MSTR', value=2, age=8),
            story('Strategy repurchases preferred STRC worth $180m', 'MSTR', value=2, age=15),
        ]
        summary=self.check(rows,ticker='MSTR')
        self.assertEqual(summary['independent_events'],3)
        self.assertEqual(summary['distinct_catalysts'],1)
        self.assertEqual(summary['coverage'],'Limited coverage')
        self.assertEqual(len(summary['drivers']),1)

    def test_recency_half_life_rewards_recent_major_catalyst(self):
        recent = story('XRPN fresh institutional event', value=2, impact='High', age=1)
        old = story('XRPN older competing event', value=-2, impact='High', age=27)
        s = self.check([recent, old])
        self.assertGreater(s['raw_score'], 0)

    def test_outside_30_days_and_future_stories_are_ignored(self):
        s = self.check([
            story('XRPN within the window', value=2, age=1),
            story('XRPN stale older story', value=-3, age=31),
            story('XRPN future-dated article', value=-3, age=-1),
        ])
        self.assertEqual(s['stories'], 1)
        self.assertGreater(s['value'], 0)

    def test_rumour_is_not_presented_as_verified(self):
        s = self.check([story('Evernorth unconfirmed big yield rumour',
                              value=3, scenario='rumour')])
        self.assertEqual(s['drivers'][0]['scenario'], 'rumour')
        self.assertNotEqual(s['coverage'], 'Broad coverage')
        # A single sensational claim is not enough to set the entire month to +3.
        self.assertLess(s['value'], 3)

    def test_mstr_thin_coverage_is_flagged_not_forced_to_zero(self):
        s = self.check([story('Strategy purchases BTC', 'MSTR', value=1)], ticker='MSTR')
        self.assertEqual(s['value'], 1)
        self.assertEqual(s['coverage'], 'Limited coverage')
        self.assertEqual(s['stories'], 1)

    def test_two_exceptional_independent_events_may_reach_plus_three(self):
        s = self.check([
            story('Evernorth earns $200m in material net lending profit',
                  value=3, impact='High'),
            story('Evernorth reports XRP holdings per diluted share increase 35%',
                  value=3, impact='High'),
        ])
        self.assertEqual(s['value'], 3)

    def test_insufficient_and_sec_entries_excluded(self):
        bad = story('Unrated hypothetical', value=0)
        bad['moon_meters'][0]['value'] = None
        sec = story('SEC filing headlines alone', value=3)
        sec['source_type'] = 'SEC'
        s = self.check([bad, sec])
        self.assertEqual(s['stories'], 0)
        self.assertEqual(s['value'], 0)

    def test_three_company_sentiment_stays_independent_and_ordered(self):
        results = aggregate_sentiment([
            story('SharpLink earns material ETH staking income', 'SBET', value=2, impact='High'),
            story('SharpLink routine shareholder presentation', 'SBET', value=0, impact='Low'),
            story('Strategy Bitcoin treasury custody loss', 'MSTR', value=-2, impact='High'),
            story('Strategy appoints director', 'MSTR', value=1, impact='Low'),
            story('Evernorth routine shareholder update', 'XRPN', value=0),
        ], AS_OF)
        self.assertEqual(list(results), ['MSTR', 'XRPN', 'SBET'])
        self.assertGreater(results['SBET']['value'], 0)
        self.assertLess(results['MSTR']['value'], 0)
        self.assertEqual(results['SBET']['stories'], 2)
        self.assertEqual(results['MSTR']['stories'], 2)
        self.assertEqual(results['XRPN']['value'], 0)

    def test_removed_issuers_and_archived_meter_values_cannot_reenter_sentiment(self):
        retired = ('Lite Strategy', 'Hyperliquid Strategies', 'Forward Industries')
        archived = story('Retired issuer treasury announcement', 'MSTR', value=3)
        archived['entities'] = list(retired)
        # Even a stale active-asset meter must not count without its issuer.
        archived['moon_meters'].extend({'asset': ticker, 'value': 3}
                                      for ticker in ('LITS', 'PURR', 'FWDI'))
        results = aggregate_sentiment([archived], AS_OF)
        self.assertEqual(list(results), ['MSTR', 'XRPN', 'SBET'])
        self.assertTrue(all(result['stories'] == 0 for result in results.values()))
        mixed = story('SharpLink joint company announcement', 'SBET', value=1)
        mixed['entities'].extend(retired)
        mixed['moon_meters'].extend(archived['moon_meters'])
        results = aggregate_sentiment([mixed], AS_OF)
        self.assertEqual(results['SBET']['stories'], 1)
        self.assertEqual(results['MSTR']['stories'], 0)

    def test_sbet_duplicate_buyback_and_staking_coverage_counts_once(self):
        for titles in (
            ('SharpLink announces stock repurchase authorization', 'SBET buyback approved'),
            ('SharpLink ETH staking revenue increases', 'SBET earns higher staking income'),
        ):
            with self.subTest(titles=titles):
                result = self.check([
                    story(titles[0], 'SBET', value=1, identifier='issuer'),
                    story(titles[1], 'SBET', value=1, identifier='syndicated'),
                ], ticker='SBET')
                self.assertEqual(result['stories'], 2)
                self.assertEqual(result['directional_events'], 1)

    def test_three_treasury_cards_report_no_stories_without_manufacturing_score(self):
        for ticker in ('MSTR', 'XRPN', 'SBET'):
            with self.subTest(ticker=ticker):
                result = self.check([], ticker=ticker)
                self.assertEqual(result['stories'], 0)
                self.assertEqual(result['value'], 0)
                self.assertIn(result['coverage'], ('No coverage', 'Limited coverage'))

if __name__ == '__main__':
    unittest.main()

