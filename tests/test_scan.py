"""Network-free issuer classification, filing exclusion and event-clustering regressions."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scan',ROOT/'scripts/scan.py')
scan=importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

class CollectorTests(unittest.TestCase):
    def test_identifies_tracked_companies_without_false_positives(self):
        self.assertEqual(scan.identify_entities('Evernorth pharmacy benefit Cigna health services'),[])
        self.assertEqual(scan.identify_entities('Investment strategy for companies'),[])
        self.assertEqual(scan.identify_entities('Ripple effect of inflation on markets'),[])
        self.assertIn('Evernorth',scan.identify_entities('Evernorth Holdings XRPN issues new equity'))
        self.assertIn('Strategy',scan.identify_entities('Strategy Inc (NASDAQ: MSTR) purchases bitcoin'))
        self.assertIn('Strategy',scan.identify_entities('MicroStrategy MSTR STRC preferred dividend'))
        self.assertEqual(scan.identify_entities('Lite Strategy Inc (NASDAQ: LITS) builds LTC treasury'),[])
        self.assertEqual(scan.identify_entities('Lite Strategy announces Litecoin buybacks'),[])
        self.assertNotIn('Lite Strategy',scan.identify_entities('Strategy Inc (MSTR) buys Bitcoin'))
        self.assertNotIn('Lite Strategy',scan.identify_entities('Litecoin price rises after halving'))
        self.assertEqual(scan.identify_entities('Lite Strategy partners with Strategy MSTR on digital assets'),
                         ['Strategy'])
        self.assertEqual(scan.identify_entities('XRP Ledger XRPL validators adopt new amendment'),[])
        self.assertNotIn('Ripple',scan.identify_entities('XRPL validators adopt new amendment'))
        self.assertIn('Ripple',scan.identify_entities('Ripple expands RLUSD bank payments'))

    def test_retired_issuers_do_not_route_but_joint_active_company_news_survives(self):
        for headline in (
                'Lite Strategy, Inc. (LITS) announces Litecoin treasury buyback',
                'Hyperliquid Strategies Inc (NASDAQ: PURR) earns HYPE staking yield',
                'PURR stock expands its HYPE treasury',
                'Forward Industries (NASDAQ: FWDI) reports SOL staking rewards'):
            self.assertEqual(scan.identify_entities(headline),[])
        cases={
            'Lite Strategy partners with Strategy Inc on a capital raise':['Strategy'],
            'Evernorth and Forward Industries announce institutional treasury partnership':['Evernorth'],
            'SharpLink Gaming and Hyperliquid Strategies announce staking partnership':['SharpLink Gaming'],
            'Ripple partners with Forward Industries on custody services':['Ripple'],
        }
        for headline,expected in cases.items():
            self.assertEqual(scan.identify_entities(headline),expected)
        self.assertEqual(set(scan.TRACKED_ENTITIES),{'Strategy','Evernorth','SharpLink Gaming','Ripple'})
        self.assertFalse(any(term in query for query in scan.NEWS_QUERIES
                             for term in ('LITS','Lite Strategy','PURR','Hyperliquid Strategies','FWDI','Forward Industries')))

    def test_retired_archive_stories_tags_and_stale_meters_are_removed(self):
        old=[]
        for entity,ticker,title in (
                ('Lite Strategy','LITS','Lite Strategy Inc builds Litecoin treasury'),
                ('Hyperliquid Strategies','PURR','Hyperliquid Strategies expands HYPE treasury'),
                ('Forward Industries','FWDI','Forward Industries increases SOL holdings')):
            row=self.story(title,entity=entity,url='https://example.com/'+ticker)
            row['moon_meters']=[{'asset':ticker,'value':2}]
            old.append(row)
        joint=self.story('Sharplink and Forward Industries announce institutional staking partnership',
                         entity='SharpLink Gaming',url='https://example.com/joint')
        joint['entities']=['SharpLink Gaming','Forward Industries']
        joint['tags']=['SBET','Treasury','FWDI','Forward Industries','SOL']
        joint['moon_meters']=[{'asset':'SBET','value':1},{'asset':'FWDI','value':2}]
        stale=self.story('Strategy adds Bitcoin to its treasury',entity='Strategy',url='https://example.com/mstr')
        stale['moon_meters']=[{'asset':'MSTR','value':1},{'asset':'LITS','value':3}]
        ripple=self.story('Ripple expands institutional XRP payments',entity='Ripple',url='https://example.com/ripple')
        merged,_=scan.merge_stories(old+[joint,stale,ripple],[])
        self.assertEqual({row['id'] for row in merged},{joint['id'],stale['id'],ripple['id']})
        result=next(row for row in merged if row['id']==joint['id'])
        self.assertEqual(result['entities'],['SharpLink Gaming'])
        self.assertEqual(result['tags'],['SBET','Treasury'])
        self.assertEqual([meter['asset'] for meter in result['moon_meters']],['SBET'])
        result=next(row for row in merged if row['id']==stale['id'])
        self.assertEqual([meter['asset'] for meter in result['moon_meters']],['MSTR'])
        self.assertTrue(all(meter['asset'] not in ('LITS','PURR','FWDI')
                            for row in merged for meter in row['moon_meters']))

    def test_scan_publishes_only_active_source_health_and_sentiment_assets(self):
        data_path=Mock()
        data_path.read_text.return_value=json.dumps({'items':[]})
        with patch.object(scan,'DATA_PATH',data_path), \
                patch.object(scan,'fetch',side_effect=AssertionError('Unexpected network request')), \
                patch.object(scan,'fetch_ripple_press',return_value=[]), \
                patch.object(scan,'fetch_evernorth_news',return_value=[]), \
                patch.object(scan,'fetch_sbet_news',return_value=[]), \
                patch.object(scan,'fetch_media_news',return_value=[]):
            self.assertEqual(scan.main(),0)
        published=json.loads(data_path.write_text.call_args.args[0])
        self.assertEqual(set(published['sources']),{'ripple','evernorth','sbet','media'})
        self.assertEqual(list(published['sentiment_30d']),['MSTR','XRPN','SBET'])
        self.assertEqual(published['scan']['schedule_utc'],['09:15','14:35','23:35'])
        self.assertEqual(published['scan']['status'],'live')

    def test_sharplink_is_company_specific_and_keeps_stock_ticker_distinct(self):
        for headline in ('Sharplink Inc earns ETH staking rewards',
                         'SharpLink Gaming (NASDAQ: SBET) expands Ethereum treasury',
                         'SBET stock authorises a share repurchase'):
            self.assertEqual(scan.identify_entities(headline),['SharpLink Gaming'])
        for headline in ('Ethereum staking adoption rises as ETH rallies',
                         'Solana network validators increase SOL revenue',
                         'Forward-looking strategy for Solana investors',
                         'Ford Motor Company launches new vehicle',
                         'BitMine adds ETH to its treasury'):
            self.assertEqual(scan.identify_entities(headline),[])
        self.assertEqual(scan.classify('Sharplink Increases ETH per Share'),'Treasury')

    def test_retired_ecosystem_is_removed_from_archive_and_company_tags_survive(self):
        network=self.story('XRP Ledger validators adopt new institutional tokenization amendment',
                           entity='XRP Ecosystem',url='https://example.com/network')
        mixed=self.story('Evernorth Holdings expands XRP treasury lending yield',
                         entity='Evernorth',url='https://example.com/issuer')
        mixed['entities']=['Evernorth','XRP Ecosystem']
        mixed['tags']=['Treasury','XRP Ecosystem']
        mixed['moon_meters']=[{'asset':'XRPN','value':1},{'asset':'XRP','value':2}]
        ripple=self.story('Ripple partners with a bank on XRP Ledger settlement',
                          entity='Ripple',url='https://example.com/ripple')
        ripple['entities']=['Ripple','XRP Ecosystem']
        merged,_=scan.merge_stories([network,mixed,ripple],[])
        self.assertEqual(len(merged),2)
        self.assertTrue(all('XRP Ecosystem' not in item['entities'] for item in merged))
        evernorth=next(item for item in merged if item['id']==mixed['id'])
        self.assertEqual(evernorth['entities'],['Evernorth'])
        self.assertEqual(evernorth['tags'],['Treasury'])
        self.assertEqual([meter['asset'] for meter in evernorth['moon_meters']],['XRPN'])
        self.assertFalse(any(query.startswith(('"XRP Ledger"','"XRPL"','"XRP" ETF'))
                             for query in scan.NEWS_QUERIES))

    def test_sbet_issuer_widget_keeps_dated_release_identity(self):
        from datetime import datetime,timezone
        date=datetime.now(timezone.utc).strftime('%b %d, %Y')
        first='https://www.pressviewer.com/profiles/investor/NewsPrint.asp?v=6&b=2597&ID=171901&m=rl'
        second='https://www.pressviewer.com/profiles/investor/NewsPrint.asp?v=6&b=2597&ID=171902&m=rl'
        def card(url,title,stamp):
            return f'<div class="PressItem38"><div class="PressItem38Date">{stamp}</div><div class="PressItem38Headline"><a href="{url}">{title}</a></div><div class="PressItem38Body"></div></div>'
        listing=card(first,'Sharplink Reports New ETH Staking Rewards',date)+card(
            second,'Sharplink Announces Quarterly Earnings Conference Call',date)+card(
            'https://example.com/untrusted','Unrelated sponsor announces new investment',date)+card(
            first+'&undated=1','Sharplink Reports Ethereum Treasury Holdings','')
        with patch.object(scan,'fetch',return_value=type('Response',(),{'text':listing})()):
            rows=scan.fetch_sbet_news()
        self.assertEqual(len(rows),2)
        self.assertEqual({row['url'] for row in rows},{first,second})
        self.assertNotEqual(rows[0]['id'],rows[1]['id'])
        self.assertTrue(all(row['entities']==['SharpLink Gaming'] and row['source_id']=='sbet'
                            and row['source_type']=='Official' for row in rows))


    def test_sbet_source_failures_are_not_reported_as_success(self):
        with patch.object(scan,'fetch',side_effect=RuntimeError('Source unavailable')):
            with self.assertRaisesRegex(RuntimeError,'Source unavailable'):
                scan.fetch_sbet_news()
        with patch.object(scan,'fetch',return_value=type('Response',(),{'text':'<html>No releases</html>'})()):
            with self.assertRaises(ValueError):
                scan.fetch_sbet_news()


    def test_treasury_event_dedup_preserves_different_purchases_and_issuers(self):
        first=self.story('Sharplink Acquires 1,000,000 ETH for Ethereum Treasury',
                         entity='SharpLink Gaming',kind='Official',url='https://example.com/sbet-one')
        syndicated=self.story('SharpLink Gaming Buys 1 Million ETH for Treasury',
                              entity='SharpLink Gaming',url='https://example.com/sbet-syndicated')
        different=self.story('Sharplink Acquires 20,000 ETH for Ethereum Treasury',
                             entity='SharpLink Gaming',url='https://example.com/sbet-two')
        strategy=self.story('Strategy Buys 1,000 BTC for Treasury',
                            entity='Strategy',url='https://example.com/mstr-one')
        holdings=self.story('Sharplink Reports Holdings of 1 Million ETH',
                            entity='SharpLink Gaming',url='https://example.com/sbet-holdings')
        merged,_=scan.merge_stories([first,syndicated,different,strategy,holdings],[])
        self.assertEqual(len(merged),4)
        original=next(row for row in merged if row['id']==first['id'])
        self.assertEqual(len(original['coverage']),2)

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

    @staticmethod
    def this_week_story(title, days_before_this_monday=0, kind='Media', url='https://example.com/story'):
        """Fixture anchored to this week, so weekly dedup tests remain current."""
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc)
        monday=(today-timedelta(days=today.weekday()+7*days_before_this_monday)).replace(
            hour=1,minute=0,second=0,microsecond=0)
        item=CollectorTests.story(title,entity='Strategy',kind=kind,url=url)
        item['published_at']=monday.isoformat().replace('+00:00','Z')
        return item

    def test_strc_buyback_aliases_205m_and_204_9m_collapse_to_one_event(self):
        stories=[
            self.this_week_story(
                'Strategy spends $205 million on STRC preferred buyback instead of buying bitcoin',
                url='https://example.com/buyback-a'),
            self.this_week_story(
                'Strategy Bitcoin Purchases Pause as STRC Buybacks Hit $205M',
                url='https://example.com/buyback-b'),
            self.this_week_story(
                'MicroStrategy Pauses Bitcoin Purchases, Spends $205M on STRC Buybacks',
                url='https://example.com/buyback-c'),
            self.this_week_story(
                'Strategy Pauses Bitcoin Buys, Spends $204.9M on STRC Buyback',
                url='https://example.com/buyback-d'),
            self.this_week_story(
                'Strategy (MSTR) Pauses Bitcoin Buying and Spends $205 Million on Preferred Stock',
                url='https://example.com/buyback-e'),
        ]
        merged,_=scan.merge_stories(stories,[])
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]['coverage']),5)
        self.assertEqual({row['url'] for row in merged[0]['coverage']},
                         {item['url'] for item in stories})

    def test_strc_buybacks_distinct_week_and_distinct_transaction_size(self):
        this_week=self.this_week_story('Strategy repurchases $205M STRC',
                                        url='https://example.com/now')
        last_week=self.this_week_story('Strategy repurchases $193M STRC',
                                        days_before_this_monday=1,
                                        url='https://example.com/lastweek')
        also_this_week=self.this_week_story('Strategy repurchases $139M STRC',
                                             url='https://example.com/other')
        merged,_=scan.merge_stories([this_week,last_week,also_this_week],[])
        self.assertEqual(len(merged),3)

    def test_strc_buyback_not_same_as_authorisation_or_dividend(self):
        current=self.this_week_story('Strategy STRC repurchases total $205M',
                                       url='https://example.com/current')
        cap=self.this_week_story('Strategy expands STRC buyback program cap to $3 billion',
                                  url='https://example.com/authorization')
        dividend=self.this_week_story('Strategy declares conditional daily STRC dividends for November',
                                       url='https://example.com/dividend')
        x,_=scan.merge_stories([current,cap,dividend],[])
        self.assertEqual(len(x),3)
        self.assertEqual(scan.strategy_strc_event(current)[0],'buyback')
        self.assertEqual(scan.strategy_strc_event(cap)[0],'buyback-cap')
        self.assertIsNone(scan.strategy_strc_event(dividend))

    def test_strc_amount_picks_buyback_not_bitcoin_purchase(self):
        title='Strategy buys $21.5M in Bitcoin as STRC buyback tops $192M'
        item=self.this_week_story(title)
        self.assertAlmostEqual(scan.strategy_strc_event(item)[2],192.0)
        title='Strategy Acquires 250 Bitcoin for $21.5M, Repurchases $192.4M of STRC Preferred Stock'
        item=self.this_week_story(title)
        self.assertAlmostEqual(scan.strategy_strc_event(item)[2],192.4)

    def test_strc_many_reporters_are_preserved_not_new_feed_cards(self):
        articles=[self.this_week_story(
            'Strategy pauses BTC buying after $205M STRC buyback; outlet '+str(i),
            url='https://example.com/report-'+str(i)) for i in range(23)]
        merged,_=scan.merge_stories(articles,[])
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]['coverage']),23)

    def test_evernorth_similar_named_events_merge_but_not_unrelated(self):
        facility=self.story('Evernorth Holdings Secures $80.7 Million Equity Facility for XRP Treasury',
                            entity='Evernorth',url='https://example.com/facility')
        facility2=self.story('Evernorth announces committed $80M equity funding via Cantor',
                             entity='Evernorth',url='https://example.com/facility2')
        warrant=self.story('Evernorth Registers 11.5M Shares Tied to Warrants',
                            entity='Evernorth',url='https://example.com/warrants')
        warrant2=self.story('Evernorth Holdings files to register 11.5 million shares with warrants',
                             entity='Evernorth',url='https://example.com/warrants2')
        merged,_=scan.merge_stories([facility,facility2,warrant,warrant2],[])
        self.assertEqual(len(merged),2)
        self.assertEqual(sorted(len(x['coverage']) for x in merged),[2,2])

    def test_evernorth_merger_vote_articles_are_one_story_but_closing_is_new(self):
        original=self.story('Evernorth Merger Vote Passes, Clearing Path for 473M XRP Treasury Deal',
                            entity='Evernorth',kind='Media',url='https://example.com/approved')
        other=self.story('XRP Gains After Evernorth Merger Vote Passes As 473M XRP Treasury Deal Advances',
                         entity='Evernorth',kind='Media',url='https://example.com/merger-vote')
        official=self.story('Shareholders Approve Evernorth Business Combination; Nasdaq Trading Soon',
                            entity='Evernorth',kind='Official',url='https://example.com/issuer')
        closing=self.story('Evernorth Completes Business Combination with Armada',
                           entity='Evernorth',kind='Official',url='https://example.com/closing')
        merged,_=scan.merge_stories([original,other,official,closing],[])
        self.assertEqual(len(merged),2)
        vote=[x for x in merged if 'Approval' in x['title'] or 'Approve' in x['title'] or 'Vote' in x['title']]
        self.assertEqual(len(vote),1)
        self.assertEqual(vote[0]['source_type'],'Official')
        self.assertEqual(len(vote[0]['coverage']),3)


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

    def test_three_daily_europe_us_and_us_evening_schedule(self):
        """Keep GitHub cron, site display and published scanner metadata aligned."""
        import re
        workflow=(ROOT/'.github/workflows/daily-scan.yml').read_text(encoding='utf-8')
        cron=re.findall(r"- cron: '(\d+) (\d+) \* \* \*'",workflow)
        scheduled=sorted(f'{int(hour):02d}:{int(minute):02d}' for minute,hour in cron)
        self.assertEqual(scheduled,['09:15','14:35','23:35'])
        site=(ROOT/'app.js').read_text(encoding='utf-8')
        self.assertIn('SCAN_TIMES_UTC = [{hour:9,minute:15},{hour:14,minute:35},{hour:23,minute:35}]',site)
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        self.assertIn("'schedule_utc':['09:15','14:35','23:35']",scanner)
        guidance=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('three scans every day at 09:15, 14:35 and 23:35 UTC',guidance)

    def test_homepage_has_both_stock_price_widgets(self):
        """XRPN and MSTR should be visible at the top, including on mobile."""
        homepage=(ROOT/'index.html').read_text(encoding='utf-8')
        stylesheet=(ROOT/'styles.css').read_text(encoding='utf-8')
        self.assertEqual(homepage.count('<tv-single-ticker symbol="NASDAQ:XRPN"'), 1)
        self.assertEqual(homepage.count('<tv-single-ticker symbol="NASDAQ:MSTR"'), 1)
        self.assertIn('widgets.tradingview-widget.com/w/en/tv-single-ticker.js', homepage)
        self.assertIn('Latest available quotes', homepage)
        self.assertIn('Quotes supplied by TradingView and may be delayed', homepage)
        self.assertLess(homepage.index('class="market-pulse"'), homepage.index('<header class="hero">'))
        self.assertIn('.market-pulse-grid{grid-template-columns:minmax(0,1fr)', stylesheet)

    def test_homepage_has_weighted_moon_sentiment_instead_of_old_cards(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'app.js').read_text(encoding='utf-8')
        css=(ROOT/'styles.css').read_text(encoding='utf-8')
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        for asset in ('mstr','xrpn','sbet'):
            self.assertIn('id="sentiment-card-'+asset+'"',html)
            self.assertIn('id="sentiment-'+asset+'-value"',html)
        self.assertNotIn('id="stat-treasury"',html)
        self.assertNotIn('id="stat-health"',html)
        self.assertNotIn("'stat-health'",script)
        self.assertIn('Moon Sentiment — 30-day weighted index',html)
        self.assertIn('Limited coverage',script)
        self.assertIn('.moon-sentiment-card',css)
        self.assertIn("'sentiment_30d':sentiment_30d",scanner)
        self.assertIn('.slice(0,48)',script)


    def test_only_three_treasury_quotes_sentiment_cards_and_crypto_logos(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        app=(ROOT/'app.js').read_text(encoding='utf-8')
        soup=BeautifulSoup(html,'html.parser')
        expected_order=['MSTR','XRPN','SBET']
        quote_order=[card.select_one('tv-single-ticker')['symbol'].split(':')[-1]
                     for card in soup.select('.market-pulse-grid > .quote-card')]
        sentiment_cards=soup.select('.stats-grid > .moon-sentiment-card')
        sentiment_order=[card.select_one('.sentiment-ticker').get_text(strip=True)
                         for card in sentiment_cards]
        self.assertEqual(quote_order,expected_order)
        self.assertEqual(sentiment_order,expected_order)
        crypto_by_ticker={'MSTR':'btc','XRPN':'xrp','SBET':'eth'}
        for ticker,card in zip(sentiment_order,sentiment_cards):
            logo=card.select_one('.sentiment-asset img')
            self.assertIsNotNone(logo)
            self.assertEqual(logo['src'],'assets/crypto/'+crypto_by_ticker[ticker]+'.svg')
            self.assertTrue(logo.get('alt','').strip())
        filters={button['data-entity'] for button in soup.select('button[data-entity]')}
        self.assertEqual(filters,{'All','Strategy','Evernorth','SharpLink Gaming','Ripple'})
        for ticker in expected_order:
            self.assertIn('https://www.tradingview.com/symbols/NASDAQ-'+ticker+'/',html)
        import re
        default_sources=re.search(r'const DEFAULT_SOURCES = \[(.*?)\];',app).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'",default_sources)),{'evernorth','ripple','sbet','media'})

    def test_no_price_hype(self):
        self.assertFalse(scan.is_investor_news('XRP price prediction huge rally','Could hit $100'))
        self.assertTrue(scan.is_investor_news('XRP Ledger launches institutional tokenization infrastructure','On XRPL'))
        self.assertTrue(scan.is_investor_news('Rumour: SWIFT to partner with Ripple for XRP settlement','Unconfirmed agreement'))
        self.assertTrue(scan.is_investor_news('Evernorth reportedly exploring XRP treasury lending yield','Potential revenue'))
        self.assertFalse(scan.is_investor_news('XRP price prediction by analyst predicts $100','Pure speculation'))

    def test_quote_listing_metadata_is_not_an_article(self):
        self.assertFalse(scan.is_investor_news(
            'Sharplink, Inc. (SBET) Stock Price, News, Quote & History','Ethereum treasury stock'))
        self.assertFalse(scan.is_investor_news('Strategy (MSTR) Stock Quote & News','Bitcoin treasury'))
        self.assertTrue(scan.is_investor_news('Evernorth Completes Nasdaq Listing for XRPN Shares','XRP treasury company'))

    def test_routine_vesting_tax_withholding_is_not_material_news(self):
        for headline in (
            'Tax withholding covers 6,231 shares at $7.63 for Sharplink (SBET) executive Michael D. Camarda.',
            'At $7.63 per share, Sharplink (SBET) CFO DeLucia has 1,592 shares withheld for vesting taxes.'):
            self.assertFalse(scan.is_investor_news(headline,'Routine share settlement for vesting.'))
        self.assertTrue(scan.is_investor_news(
            'Sharplink Raises $425 Million to Expand Ethereum Treasury','ETH holdings and capital funding'))
        self.assertTrue(scan.is_investor_news(
            'Sharplink Announces Equity Facility for ETH Treasury Alongside Tax Withholding Disclosure','Material capital raise'))

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
