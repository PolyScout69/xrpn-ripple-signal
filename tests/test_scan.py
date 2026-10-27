"""Network-free regression tests for four entities, filing exclusion and clustering."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scan',ROOT/'scripts/scan.py')
scan=importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

class CollectorTests(unittest.TestCase):
    def test_identifies_four_entities_without_false_positives(self):
        self.assertEqual(scan.identify_entities('Evernorth pharmacy benefit Cigna health services'),[])
        self.assertEqual(scan.identify_entities('Investment strategy for companies'),[])
        self.assertEqual(scan.identify_entities('Ripple effect of inflation on markets'),[])
        self.assertIn('Evernorth',scan.identify_entities('Evernorth Holdings XRPN issues new equity'))
        self.assertIn('Strategy',scan.identify_entities('Strategy Inc (NASDAQ: MSTR) purchases bitcoin'))
        self.assertIn('Strategy',scan.identify_entities('MicroStrategy MSTR STRC preferred dividend'))
        self.assertIn('XRP Ecosystem',scan.identify_entities('XRP Ledger XRPL validators adopt new amendment'))
        self.assertNotIn('Ripple',scan.identify_entities('XRPL validators adopt new amendment'))
        self.assertIn('Ripple',scan.identify_entities('Ripple expands RLUSD bank payments'))

    def test_sec_filing_entries_are_rejected_and_purged(self):
        no=scan.make_story(title='Strategy files Form 8-K',date=scan.timestamp_now(),url='https://www.sec.gov/Archives/edgar/data/1/abc',source='SEC EDGAR',source_type='SEC',source_id='sec_strategy',entities=['Strategy'],excerpt='Form 8-K filed',category='SEC filings')
        self.assertIsNone(no)
        old={'id':'old-filing','title':'Strategy files Form 8-K','published_at':scan.timestamp_now(),'category':'SEC filings','entities':['Strategy'],'source_type':'SEC','source_id':'sec_strategy','url':'https://www.sec.gov/Archives/edgar/data/1/abc','impact':'High','score':95}
        good=self.story('Strategy buys 100 BTC in institutional markets',entity='Strategy',kind='Media',url='https://example.com/btc')
        good['coverage']=[{'title':'Filing','name':'SEC EDGAR','source_type':'SEC','url':'https://www.sec.gov/Archives/edgar/data/1/abc'}, {'title':'Report','name':'Publisher','source_type':'Media','url':'https://example.com/btc'}]
        merged,_=scan.merge_stories([old,good],[])
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0]['title'],good['title'])
        self.assertNotIn('sec.gov',str(merged[0].get('coverage',[])))

    def test_source_first_grouping_80m_facility(self):
        publisher=self.story('Evernorth Holdings (NASDAQ:XRPN) Secures Potential $80 Million Equity Facility for XRP Strategy',entity='Evernorth',kind='Media',url='https://publisher.com/one')
        official=self.story('Evernorth agrees conditional equity facility worth approximately $80 million',entity='Evernorth',kind='Official',url='https://press.com/two')
        alt=self.story('About $80 million could be raised by Evernorth; it intends to use some for XRP',entity='Evernorth',kind='Media',url='https://publisher.com/three')
        x,n=scan.merge_stories([publisher,official,alt],[])
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]['source_type'],'Official')
        self.assertEqual(len(x[0]['coverage']),3)

    def test_ripple_arf_single_event_multiple_publishers(self):
        p1=self.story('Ripple partners with Arf to bring RLUSD settlement liquidity to XRPL',entity='Ripple',url='https://example.com/a')
        p2=self.story('Arf partners with Ripple to support cross-border payments',entity='Ripple',url='https://example.com/b')
        p3=self.story('Ripple Partner Arf Brings Its $10 Billion Payments Lending Business to XRP Ledger',entity='Ripple',url='https://example.com/c')
        x,_=scan.merge_stories([p1,p2,p3],[])
        self.assertEqual(len(x),1)
        self.assertEqual(len(x[0]['coverage']),3)

    def test_different_strategy_events_remain_separate(self):
        a=self.story('Strategy Inc purchases 250 BTC and updates its reserves',entity='Strategy',url='https://example.com/a')
        b=self.story('Strategy reports STRC repurchase of $192 million',entity='Strategy',url='https://example.com/b')
        self.assertEqual(len(scan.merge_stories([a,b],[])[0]),2)

    def test_ripple_press_google_date_fallback(self):
        from email.utils import format_datetime
        from datetime import datetime,timezone
        title='Ripple partners with a regulated bank to launch institutional stablecoin settlement'
        listing=f'<div><a href="/ripple-press/bank-launch/">{title}</a></div>'
        article=f'<h1>{title}</h1><p>Ripple develops institutional digital payment and settlement services through global regulated banking partnerships.</p>'
        rss=f'<rss><channel><item><title>{title} - Ripple</title><pubDate>{format_datetime(datetime.now(timezone.utc))}</pubDate><link>https://news.google.com/rss/articles/a</link></item></channel></rss>'
        class Fake:
            def __init__(self,text):self.text=text
        def fake_fetch(url,*args,**kwargs):
            if '/bank-launch/' in url:return Fake(article)
            if 'news.google.com' in url:return Fake(rss)
            return Fake(listing)
        with patch.object(scan,'fetch',side_effect=fake_fetch),patch.object(scan.time,'sleep',return_value=None):
            rows=scan.fetch_ripple_press()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_type'],'Official')
        self.assertIn('/ripple-press/bank-launch',rows[0]['url'])

    def test_twice_daily_europe_us_and_us_evening_schedule(self):
        """Keep GitHub cron, site display and published scanner metadata aligned."""
        import re
        workflow=(ROOT/'.github/workflows/daily-scan.yml').read_text(encoding='utf-8')
        cron=re.findall(r"- cron: '(\d+) (\d+) \* \* \*'",workflow)
        scheduled=sorted(f'{int(hour):02d}:{int(minute):02d}' for minute,hour in cron)
        self.assertEqual(scheduled,['14:35','23:35'])
        site=(ROOT/'app.js').read_text(encoding='utf-8')
        self.assertIn('SCAN_TIMES_UTC = [{hour:14,minute:35},{hour:23,minute:35}]',site)
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        self.assertIn("'schedule_utc':['14:35','23:35']",scanner)
        guidance=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('two scans every day at 14:35 UTC and 23:35 UTC',guidance)

    def test_no_price_hype(self):
        self.assertFalse(scan.is_investor_news('XRP price prediction huge rally','Could hit $100'))
        self.assertTrue(scan.is_investor_news('XRP Ledger launches institutional tokenization infrastructure','On XRPL'))
        self.assertTrue(scan.is_investor_news('Rumour: SWIFT to partner with Ripple for XRP settlement','Unconfirmed agreement'))
        self.assertTrue(scan.is_investor_news('Evernorth reportedly exploring XRP treasury lending yield','Potential revenue'))
        self.assertFalse(scan.is_investor_news('XRP price prediction by analyst predicts $100','Pure speculation'))

    def test_url_safety(self):
        self.assertFalse(scan.canonical_url('javascript:alert(1)'))
        self.assertFalse(scan.canonical_url('http://bad.example'))
        self.assertTrue(scan.canonical_url('https://example.com/news?utm_source=test').endswith('/news'))

    @staticmethod
    def story(title,entity='Evernorth',kind='Media',url='https://example.com/news'):
        result=scan.make_story(title=title,date=scan.timestamp_now(),url=url,source='Publisher',source_type=kind,source_id='test',entities=[entity],excerpt=title)
        assert result
        return result

if __name__=='__main__':unittest.main()