"""Rules-based Moon Meter regression tests (offline)."""
import unittest
from scripts.moon_meter import moon_for_story


def score(title, entity='Evernorth', kind='Official', category='Adoption', excerpt=''):
    item = dict(title=title, entities=[entity], category=category, excerpt=excerpt, source_type=kind)
    value=moon_for_story(item)
    assert len(value)==1
    return value[0]


class MoonMeterTests(unittest.TestCase):
    def test_seven_point_scale(self):
        self.assertEqual(score('Evernorth files for Chapter 11 bankruptcy')['value'],-3)
        self.assertEqual(score('XRPL security breach and exploit', 'XRP Ecosystem')['value'],-2)
        self.assertEqual(score('Evernorth announces $80m equity purchase facility')['value'],-1)
        self.assertIsNone(score('Strategy files Form 8-K reported items 7.01', 'Strategy', 'SEC', 'SEC filings')['value'])
        self.assertEqual(score('Strategy buys 1,000 bitcoin for treasury', 'Strategy')['value'],1)
        self.assertEqual(score('SEC approves spot XRP ETF','XRP Ecosystem')['value'],2)
        self.assertEqual(score('Strategy reports Bitcoin per fully diluted share increases 25% after dilution','Strategy')['value'],3)

    def test_asset_routing(self):
        for entity, asset in [('Ripple','XRP'),('XRP Ecosystem','XRP'),('Evernorth','XRPN'),('Strategy','MSTR')]:
            self.assertEqual(score('Routine update',entity)['asset'],asset)
        both=moon_for_story(dict(title='Ripple and XRPL cooperate on network',entities=['Ripple','XRP Ecosystem'],source_type='Official'))
        self.assertEqual([m['asset'] for m in both],['XRP'])
        multi=moon_for_story(dict(title='Evernorth and Ripple announce agreement',entities=['Evernorth','Ripple'],source_type='Official'))
        self.assertEqual({m['asset'] for m in multi},{'XRPN','XRP'})

    def test_impact_is_not_price_direction(self):
        meter=moon_for_story(dict(title='Evernorth announces share sale',entities=['Evernorth'],source_type='Official',impact='High'))
        self.assertEqual(meter[0]['value'],-1)

    def test_uncertain_company_product_not_guaranteed_xrp_positive(self):
        self.assertEqual(score('Ripple Treasury introduces RLUSD always-on platform','Ripple')['value'],0)
        self.assertEqual(score('Ripple partners with bank for new corporate payments','Ripple')['value'],0)
        self.assertEqual(score('Ripple integrates XRP Ledger XRPL settlement with institution','Ripple')['value'],1)

    def test_routine_sec_and_generic_disclosures_neutral(self):
        self.assertIsNone(score('Evernorth files Form S-3','Evernorth','SEC','SEC filings')['value'])
        self.assertIsNone(score('Strategy files Form 10-Q','Strategy','SEC','SEC filings')['value'])

    def test_media_source_caution_and_range(self):
        m=score('Evernorth files for bankruptcy',kind='Media')
        self.assertEqual(m['value'],-2)
        self.assertIn('primary',m['reason'])
        for title in ('ETF approval denied','Strategy reports new bitcoin treasury plan','Spot XRP ETF launch date'):
            for ent in ['Ripple','Evernorth','XRP Ecosystem','Strategy']:
                v=score(title,ent)['value']
                self.assertLessEqual(v,3)
                self.assertGreaterEqual(v,-3)

    def test_rumor_is_not_a_bullish_signal(self):
        value=score('SWIFT Ripple XRP partnership rumor sparks speculation','Ripple','Media')
        self.assertIsNone(value['value'])
        self.assertEqual(value['confidence'],'Insufficient')

    def test_funding_and_clickbait_are_not_false_bullish_signals(self):
        self.assertEqual(score('Evernorth to buy more XRP with filing for 11.5M new XRPN stock shares','Evernorth')['value'],-1)
        self.assertEqual(score('Evernorth raises funds to buy more XRP','Evernorth')['value'],0)
        self.assertIsNone(score('Is the MSTR Bubble Bursting?','Strategy','Media')['value'])

    def test_per_share_accumulation_stronger_than_gross_buying(self):
        self.assertEqual(score('Strategy buys 1,000 bitcoin','Strategy')['value'],1)
        self.assertEqual(score('Strategy reports Bitcoin per diluted share rises 8%','Strategy')['value'],2)
        self.assertEqual(score('Strategy reports Bitcoin per fully diluted share declines 12%','Strategy')['value'],-2)

    def test_xrp_extreme_requires_verification_and_flows(self):
        m=score('SEC approves spot XRP ETF with net inflows $2 billion','XRP Ecosystem','Official')
        self.assertEqual(m['value'],3)
        self.assertEqual(m['method'],'headline_rules_v2')

    def test_merged_articles_recompute_once_per_asset(self):
        item={'title':'Evernorth announces equity facility','excerpt':'May issue additional shares','entities':['Evernorth','Ripple','XRP Ecosystem'],'source_type':'Official'}
        meters=moon_for_story(item)
        self.assertEqual([x['asset'] for x in meters],['XRPN','XRP'])
        self.assertEqual(meters[0]['value'],-1)

if __name__=='__main__':unittest.main()
