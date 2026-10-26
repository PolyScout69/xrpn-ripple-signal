"""Network-free regression tests for SEC matching, four entities and clustering."""
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

    def test_sec_filers_use_distinct_ciks(self):
        self.assertEqual(scan.SEC_CIK,2092592)
        self.assertEqual(scan.STRATEGY_CIK,1050446)
        for cik,company,fn in ((2092592,'Evernorth Holdings Inc.',scan.fetch_sec_filings),
                               (1050446,'Strategy Inc',scan.fetch_strategy_sec_filings)):
            payload={'cik':cik,'name':company,'filings':{'recent':{
                'form':['8-K','4','XYZ'],
                'accessionNumber':['0001628280-26-067061','0001628280-26-067062','0001628280-26-067063'],
                'primaryDocument':['report-8k.htm','form4.xml','other.txt'],
                'filingDate':[scan.timestamp_now()[:10]]*3,
                'items':['1.01, 9.01','','']}}}
            class Fake:
                def json(self):return payload
            with patch.object(scan,'fetch',return_value=Fake()): rows=fn()
            self.assertEqual(len(rows),2)
            self.assertIn(f'/data/{cik}/',rows[0]['url'])
            self.assertIn('Form 8-K',rows[0]['title'])
            self.assertIn('1.01',rows[0]['title'])
            self.assertEqual(rows[0]['entities'],['Evernorth' if cik==2092592 else 'Strategy'])

    def test_sec_different_accessions_not_grouped(self):
        a=self.story('Strategy files Form 8-K · reported items 1.01',entity='Strategy',kind='SEC',url='https://sec.gov/filing1')
        b=self.story('Strategy files Form 8-K · reported items 1.01',entity='Strategy',kind='SEC',url='https://sec.gov/filing2')
        a['accession']='000001';b['accession']='000002'
        self.assertFalse(scan.duplicates(a,b))

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

    def test_no_price_hype(self):
        self.assertFalse(scan.is_investor_news('XRP price prediction huge rally','Could hit $100'))
        self.assertTrue(scan.is_investor_news('XRP Ledger launches institutional tokenization infrastructure','On XRPL'))

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