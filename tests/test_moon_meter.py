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
        self.assertEqual(moon_for_story({'title':'Strategy files Form 8-K reported items 7.01','entities':['Strategy'],'source_type':'SEC','category':'SEC filings'}),[])
        self.assertEqual(score('Strategy buys 1,000 bitcoin for treasury', 'Strategy')['value'],1)
        self.assertEqual(score('SEC approves spot XRP ETF','XRP Ecosystem')['value'],3)
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

    def test_optimistic_ripple_impact_still_distinguishes_direct_token_use(self):
        self.assertEqual(score('Ripple Treasury introduces RLUSD always-on platform','Ripple')['value'],1)
        self.assertEqual(score('Ripple partners with bank for new corporate payments','Ripple')['value'],1)
        self.assertEqual(score('Ripple integrates XRP Ledger XRPL settlement with institution','Ripple')['value'],2)

    def test_standalone_filing_has_no_moon_rating(self):
        for form in ('S-3','10-Q','8-K'):
            self.assertEqual(moon_for_story({'title':f'Evernorth files Form {form}', 'entities':['Evernorth'], 'category':'SEC filings','source_type':'SEC','source_id':'sec_evernorth'}),[])

    def test_media_source_caution_and_range(self):
        m=score('Evernorth files for bankruptcy',kind='Media')
        self.assertEqual(m['value'],-3)
        self.assertIn('solvency',m['reason'])
        for title in ('ETF approval denied','Strategy reports new bitcoin treasury plan','Spot XRP ETF launch date'):
            for ent in ['Ripple','Evernorth','XRP Ecosystem','Strategy']:
                v=score(title,ent)['value']
                self.assertLessEqual(v,3)
                self.assertGreaterEqual(v,-3)

    def test_rumour_scenario_is_scored_as_if_true_and_marked_unverified(self):
        m=score('SWIFT Ripple XRP partnership rumor sparks speculation','Ripple','Media')
        self.assertEqual(m['value'],3)
        self.assertEqual(m['confidence'],'Unverified')
        self.assertEqual(m['scenario'],'rumour')
        self.assertTrue(m['if_true'])
        self.assertIn('RUMOUR IS TRUE',m['reason'])

    def test_negative_rumours_are_not_automatically_bullish(self):
        m=score('Rumour: Evernorth files for bankruptcy','Evernorth','Media')
        self.assertEqual(m['value'],-3)
        self.assertEqual(m['scenario'],'rumour')

    def test_planned_treasury_yield_scenario(self):
        m=score('Evernorth could earn yield by lending XRP treasury assets','Evernorth','Media')
        self.assertEqual(m['value'],2)
        self.assertEqual(m['scenario'],'assumption')
        self.assertEqual(m['confidence'],'Conditional')

    def test_if_true_evernorth_merger_approval(self):
        m=score('Evernorth crypto merger reportedly wins shareholder vote','Evernorth','Media')
        self.assertEqual(m['value'],2)
        self.assertEqual(m['scenario'],'rumour')

    def test_non_catalyst_rumour_is_not_forced_positive(self):
        m=score('Rumour: general XRP market chatter','Ripple','Media')
        self.assertEqual(m['value'],0)
        self.assertEqual(m['scenario'],'rumour')

    def test_funding_and_clickbait_are_not_false_bullish_signals(self):
        self.assertEqual(score('Evernorth to buy more XRP with filing for 11.5M new XRPN stock shares','Evernorth')['value'],-1)
        self.assertEqual(score('Evernorth raises funds to buy more XRP','Evernorth')['value'],0)
        self.assertIsNone(score('Is the MSTR Bubble Bursting?','Strategy','Media')['value'])

    def test_per_share_accumulation_stronger_than_gross_buying(self):
        self.assertEqual(score('Strategy buys 1,000 bitcoin','Strategy')['value'],1)
        self.assertEqual(score('Strategy reports Bitcoin per diluted share rises 8%','Strategy')['value'],2)
        self.assertEqual(score('Strategy reports Bitcoin per fully diluted share declines 12%','Strategy')['value'],-2)

    def test_xrp_extreme_if_true_score(self):
        m=score('SEC approves spot XRP ETF with net inflows $2 billion','XRP Ecosystem','Official')
        self.assertEqual(m['value'],3)
        self.assertEqual(m['method'],'headline_if_true_v4')

    def test_xrpn_scaled_institutional_treasury_yield_is_plus_three(self):
        m=score('Nasdaq-Listed Evernorth Targets Yield on $648 Million XRP Treasury as Four Institutional Partners Join',kind='Media')
        self.assertEqual(m['value'],3)
        self.assertIn('sustainable net income',m['reason'])
        m2=score('Evernorth Puts 473 Million XRP Treasury to Work With Ripple, Coinbase, Kraken and BitGo',kind='Media')
        self.assertEqual(m2['value'],3)

    def test_xrpn_per_share_and_listing_are_bullish_if_true(self):
        self.assertEqual(score('Evernorth XRP Holdings to Target Higher XRP Per Share',kind='Media')['value'],2)
        self.assertEqual(score('Evernorth Completes Business Combination with Armada',kind='Official')['value'],2)
        self.assertEqual(score('XRP Treasury Firm Evernorth Gets SEC Nod, Eyes Nasdaq Listing',kind='Media')['value'],2)
        self.assertEqual(score('Uphold Lists Evernorth XRPN Stock, Expanding Access',kind='Media')['value'],1)

    def test_xrpn_warrant_dilution_and_treasury_drawdown_not_optimistic(self):
        self.assertEqual(score('Evernorth Registers 11.5 Million Shares Tied to Warrants',kind='Media')['value'],-1)
        self.assertEqual(score('Evernorth XRP treasury lost $443 Million before its debut',kind='Media')['value'],-2)
        self.assertEqual(score('Evernorth announces $80m equity purchase facility',kind='Media')['value'],-1)

    def test_strategy_preferred_repurchase_if_true(self):
        m=score('Strategy Acquires 250 Bitcoin for $21.5M, Repurchases $192.4M of STRC Preferred Stock','Strategy','Media')
        self.assertEqual(m['value'],2)
        self.assertEqual(score('Strategy proposes daily preferred dividends','Strategy','Media')['value'],0)

    def test_strategy_paused_bitcoin_and_strc_buybacks_are_mixed(self):
        self.assertEqual(score('Strategy pauses Bitcoin buying for a week, repurchases $205M in STRC','Strategy','Media')['value'],1)
        self.assertEqual(score('Strategy spends $205 million on STRC preferred buyback instead of buying bitcoin','Strategy','Media')['value'],2)

    def test_strategy_hidden_buyback_dependency_is_bearish_if_true(self):
        result=score('Strategy STRC preferred stock market has hidden dependency on its own buybacks','Strategy','Media')
        self.assertEqual(result['value'],-1)

    def test_generic_hype_does_not_become_plus_three(self):
        self.assertEqual(score('Evernorth says something special is planned','Evernorth','Media')['value'],0)
        self.assertEqual(score('Ripple new product launch for RLUSD','Ripple','Media')['value'],1)

    def test_merged_articles_recompute_once_per_asset(self):
        item={'title':'Evernorth announces equity facility','excerpt':'May issue additional shares','entities':['Evernorth','Ripple','XRP Ecosystem'],'source_type':'Official'}
        meters=moon_for_story(item)
        self.assertEqual([x['asset'] for x in meters],['XRPN','XRP'])
        self.assertEqual(meters[0]['value'],-1)

if __name__=='__main__':unittest.main()
