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
        for headline in ('Evernorth pharmacy benefit Cigna health services',
                         'Investment strategy for companies',
                         'Ripple effect of inflation on markets',
                         'XRP Ledger XRPL validators adopt new amendment'):
            self.assertEqual(scan.identify_entities(headline),[])
        self.assertIn('Evernorth',scan.identify_entities('Evernorth Holdings XRPN issues new equity'))
        self.assertIn('Strategy',scan.identify_entities('Strategy Inc (NASDAQ: MSTR) purchases bitcoin'))
        self.assertIn('Strategy',scan.identify_entities('MicroStrategy MSTR STRC preferred dividend'))
        self.assertIn('Ripple',scan.identify_entities('Ripple expands RLUSD bank payments'))
        self.assertEqual(scan.classify('Strategy Increases Bitcoin per Share'),'Treasury')
        self.assertEqual(scan.classify('Evernorth Reports XRP Treasury Holdings'),'Treasury')

    def test_retired_issuers_do_not_route_but_joint_active_company_news_survives(self):
        for headline in (
                'Lite Strategy Inc (NASDAQ: LITS) builds LTC treasury',
                'Lite Strategy, Inc. announces Litecoin buybacks',
                'Lite Strategy Incorporated earns covered-call option premiums',
                'LITS stock announces a treasury expansion',
                'Sharplink Inc earns ETH staking rewards',
                'SharpLink Gaming (NASDAQ: SBET) expands Ethereum treasury',
                'SBET stock authorises a share repurchase',
                'Hyperliquid Strategies Inc (NASDAQ: PURR) earns HYPE staking yield',
                'Forward Industries (NASDAQ: FWDI) reports SOL staking rewards',
                'Ethereum staking adoption rises as ETH rallies',
                'Litecoin network adoption rises',
                'Forward-looking strategy for Solana investors'):
            with self.subTest(headline=headline):
                self.assertEqual(scan.identify_entities(headline),[])
        cases={
            'Lite Strategy partners with Strategy Inc on a capital raise':['Strategy'],
            'Lite Strategy, Inc. and MicroStrategy MSTR discuss digital asset treasury custody':['Strategy'],
            'Evernorth Holdings and SharpLink Gaming announce treasury partnership':['Evernorth'],
            'Ripple partners with Lite Strategy on custody services':['Ripple'],
        }
        for headline,expected in cases.items():
            self.assertEqual(scan.identify_entities(headline),expected)
        self.assertEqual(set(scan.TRACKED_ENTITIES),{'Strategy','Evernorth','Ripple'})
        self.assertFalse(any(term.casefold() in query.casefold() for query in scan.NEWS_QUERIES
                             for term in ('PURR','Hyperliquid Strategies','FWDI','Forward Industries',
                                          'LITS','Lite Strategy','Litecoin','SBET','Sharplink','Ethereum')))
        self.assertEqual(scan.identify_entities('Routine treasury update',force='Lite Strategy'),[])
        self.assertEqual(scan.identify_entities('Routine treasury update',force='SharpLink Gaming'),[])
        self.assertNotIn('ETH',scan.investor_angle('Treasury'))
        self.assertNotIn('LTC',scan.investor_angle('Treasury'))

    def test_retired_archive_stories_tags_and_stale_meters_are_removed(self):
        old=[]
        for entity,ticker,title,kind in (
                ('Lite Strategy','LITS','Lite Strategy Inc increases LTC holdings per share','Official'),
                ('SharpLink Gaming','SBET','Sharplink earns ETH staking revenue','Media'),
                ('Hyperliquid Strategies','PURR','Hyperliquid Strategies expands HYPE treasury','Media'),
                ('Forward Industries','FWDI','Forward Industries increases SOL holdings','Official')):
            row=self.story(title,entity=entity,kind=kind,url='https://example.com/'+ticker)
            row['moon_meters']=[{'asset':ticker,'value':2}]
            old.append(row)
        joint=self.story('Strategy Inc and Lite Strategy announce an institutional custody partnership',
                         entity='Strategy',url='https://example.com/joint')
        joint['entities']=['Strategy','Lite Strategy']
        joint['tags']=['MSTR','Treasury','LITS','Lite Strategy','LTC','Litecoin','LitVM',
                       'SBET','SharpLink Gaming','Sharplink','Sharp Link','ETH','Ethereum','Ether']
        joint['moon_meters']=[{'asset':'MSTR','value':1},{'asset':'LITS','value':3},{'asset':'SBET','value':3}]
        official_joint=self.story('Sharplink and Evernorth Holdings announce XRP treasury funding partnership',
                                  entity='SharpLink Gaming',kind='Official',url='https://example.com/official-joint')
        official_joint['tags']=['SBET','ETH','XRPN']
        stale=self.story('Strategy adds Bitcoin to its treasury',entity='Strategy',url='https://example.com/mstr')
        stale['moon_meters']=[{'asset':'MSTR','value':1},{'asset':'LITS','value':3},{'asset':'SBET','value':3}]
        ripple=self.story('Ripple expands institutional XRP payments',entity='Ripple',url='https://example.com/ripple')
        merged,new_count=scan.merge_stories(old+[joint,official_joint,stale,ripple],[])
        self.assertEqual({row['id'] for row in merged},{joint['id'],official_joint['id'],stale['id'],ripple['id']})
        self.assertEqual(new_count,0)
        result=next(row for row in merged if row['id']==joint['id'])
        self.assertEqual(result['entities'],['Strategy'])
        self.assertEqual(result['tags'],['MSTR','Treasury'])
        result=next(row for row in merged if row['id']==official_joint['id'])
        self.assertEqual(result['entities'],['Evernorth'])
        self.assertEqual(result['tags'],['XRPN'])
        for row in merged:
            self.assertEqual(row['moon_meters'],scan.moon_for_story(row))
            self.assertTrue(all(meter['asset'] in ('MSTR','XRPN','XRP') for meter in row['moon_meters']))
        self.assertEqual([meter['asset'] for meter in next(row for row in merged if row['id']==stale['id'])['moon_meters']],['MSTR'])

    def test_scan_publishes_only_active_source_health_and_sentiment_assets(self):
        data_path=Mock()
        data_path.read_text.return_value=json.dumps({'items':[],'sources':{'sbet':{},'lits':{}}})
        with patch.object(scan,'DATA_PATH',data_path), \
                patch.object(scan,'fetch_ripple_press',return_value=[]), \
                patch.object(scan,'fetch_evernorth_news',return_value=[]), \
                patch.object(scan,'fetch_media_news',return_value=[]):
            self.assertEqual(scan.main(),0)
        published=json.loads(data_path.write_text.call_args.args[0])
        self.assertEqual(set(published['sources']),{'ripple','evernorth','media'})
        self.assertEqual(list(published['sentiment_30d']),['MSTR','XRPN'])
        self.assertEqual(published['scan']['schedule_utc'],['09:15','14:35','23:35'])
        self.assertEqual(published['scan']['status'],'live')

    def test_active_source_failures_remain_visible_and_keep_retained_archive(self):
        story=self.story('Strategy Inc buys 100 BTC for its treasury',entity='Strategy')
        for all_failed in (False,True):
            data_path=Mock()
            data_path.read_text.return_value=json.dumps({'items':[story]})
            failure=RuntimeError('Source unavailable')
            with patch.multiple(scan,DATA_PATH=data_path,
                    fetch_ripple_press=Mock(side_effect=failure),
                    fetch_evernorth_news=Mock(side_effect=failure if all_failed else None,return_value=[]),
                    fetch_media_news=Mock(side_effect=failure if all_failed else None,return_value=[])):
                self.assertEqual(scan.main(),1 if all_failed else 0)
            published=json.loads(data_path.write_text.call_args.args[0])
            self.assertEqual(published['scan']['status'],'failed' if all_failed else 'partial')
            self.assertEqual(set(published['sources']),{'ripple','evernorth','media'})
            self.assertEqual(published['sources']['ripple']['status'],'error')
            self.assertIn('Source unavailable',published['sources']['ripple']['message'])
            self.assertEqual([row['id'] for row in published['items']],[story['id']])

    def test_rss_discards_retired_only_issuers_and_keeps_joint_company_reports(self):
        from xml.sax.saxutils import escape
        titles=(
            'Lite Strategy Inc expands its Litecoin treasury',
            'Sharplink Inc announces ETH staking rewards',
            'Lite Strategy partners with Strategy Inc on custody services',
            'Evernorth Holdings and Sharplink announce XRP treasury partnership',
        )
        xml='<rss><channel>'+''.join(
            '<item><title>'+escape(title)+'</title><pubDate>'+scan.timestamp_now()+
            '</pubDate><link>https://example.com/report-'+str(index)+
            '</link><source>Publisher</source></item>' for index,title in enumerate(titles)
        )+'</channel></rss>'
        rows=scan.parse_google_news(xml)
        self.assertEqual([row['title'] for row in rows],list(titles[2:]))
        self.assertEqual([row['entities'] for row in rows],[['Strategy'],['Evernorth']])


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


    def test_treasury_event_dedup_preserves_different_purchases_and_issuers(self):
        first=self.story('Strategy Inc Acquires 1,000 BTC for Its Treasury',
                         entity='Strategy',kind='Official',url='https://example.com/mstr-one')
        syndicated=self.story('MicroStrategy Buys 1000 Bitcoin for Treasury',
                              entity='Strategy',url='https://example.com/mstr-syndicated')
        different=self.story('Strategy Inc Acquires 200 BTC for Its Treasury',
                             entity='Strategy',url='https://example.com/mstr-two')
        evernorth=self.story('Evernorth Holdings Buys XRP for Treasury',
                            entity='Evernorth',url='https://example.com/xrpn-one')
        merged,_=scan.merge_stories([first,syndicated,different,evernorth],[])
        self.assertEqual(len(merged),3)
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
        for asset in ('mstr','xrpn'):
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


    def test_two_treasury_quotes_sentiment_cards_and_crypto_logos(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        app=(ROOT/'app.js').read_text(encoding='utf-8')
        soup=BeautifulSoup(html,'html.parser')
        expected_order=['MSTR','XRPN']
        quote_order=[card.select_one('tv-single-ticker')['symbol'].split(':')[-1]
                     for card in soup.select('.market-pulse-grid > .quote-card')]
        sentiment_cards=soup.select('.stats-grid > .moon-sentiment-card')
        sentiment_order=[card.select_one('.sentiment-ticker').get_text(strip=True)
                         for card in sentiment_cards]
        self.assertEqual(quote_order,expected_order)
        self.assertEqual(sentiment_order,expected_order)
        crypto_by_ticker={'MSTR':'btc','XRPN':'xrp'}
        for ticker,card in zip(sentiment_order,sentiment_cards):
            logo=card.select_one('.sentiment-asset img')
            self.assertIsNotNone(logo)
            self.assertEqual(logo['src'],'assets/crypto/'+crypto_by_ticker[ticker]+'.svg')
            self.assertTrue(logo.get('alt','').strip())
        filters={button['data-entity'] for button in soup.select('button[data-entity]')}
        self.assertEqual(filters,{'All','Strategy','Evernorth','Ripple'})
        for ticker in expected_order:
            self.assertIn('https://www.tradingview.com/symbols/NASDAQ-'+ticker+'/',html)
        import re
        default_sources=re.search(r'const DEFAULT_SOURCES = \[(.*?)\];',app).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'",default_sources)),{'evernorth','ripple','media'})

    def test_no_price_hype(self):
        self.assertFalse(scan.is_investor_news('XRP price prediction huge rally','Could hit $100'))
        self.assertTrue(scan.is_investor_news('XRP Ledger launches institutional tokenization infrastructure','On XRPL'))
        self.assertTrue(scan.is_investor_news('Rumour: SWIFT to partner with Ripple for XRP settlement','Unconfirmed agreement'))
        self.assertTrue(scan.is_investor_news('Evernorth reportedly exploring XRP treasury lending yield','Potential revenue'))
        self.assertFalse(scan.is_investor_news('XRP price prediction by analyst predicts $100','Pure speculation'))

    def test_quote_listing_metadata_is_not_an_article(self):
        self.assertFalse(scan.is_investor_news(
            'Evernorth Holdings, Inc. (XRPN) Stock Price, News, Quote & History','XRP treasury stock'))
        self.assertFalse(scan.is_investor_news('Strategy (MSTR) Stock Quote & News','Bitcoin treasury'))
        self.assertTrue(scan.is_investor_news('Evernorth Completes Nasdaq Listing for XRPN Shares','XRP treasury company'))

    def test_static_quote_estimates_and_chart_templates_are_not_news(self):
        for headline in (
            'Strategy, Inc. Stock Price Today | MSTR Live Chart & News',
            'Strategy, Inc. (MSTR) Stock Price History & Data',
            'Strategy, Inc. (MSTR) Seasonal returns chart',
            'Strategy, Inc. (MSTR) Earnings Date, Reports and Estimates',
            'Strategy, Inc. Estimates – NASDAQ:MSTR',
            'Strategy, Inc. Estimates – NASDAQ:MSTR',
        ):
            with self.subTest(headline=headline):
                self.assertFalse(scan.is_investor_news(headline,'Company earnings and treasury stock information'))
        for headline in (
            'Strategy Inc Beats Earnings Estimates on Treasury Income',
            'Strategy Raises Earnings Estimates – NASDAQ:MSTR',
            'Strategy Inc Announces Quarterly Earnings Date',
        ):
            self.assertTrue(scan.is_investor_news(headline,'Company earnings update'))

    def test_routine_option_grants_do_not_hide_treasury_income_or_financing(self):
        for headline in (
            'A director receives 100,000 options with a $1.19 exercise price at Strategy Inc (MSTR).',
            '600,000 options awarded to Strategy Inc (MSTR) CEO carry a $1.19 exercise price.',
            'A 100,000-option annual grant at Strategy Inc (MSTR) gives director 25% immediate vesting.',
        ):
            with self.subTest(headline=headline):
                self.assertFalse(scan.is_investor_news(headline,'BTC treasury company'))
        for headline in (
            'Strategy Inc Earns Covered-Call Option Premiums on Its BTC Treasury',
            'MSTR Raises $100 Million for Bitcoin Treasury Alongside CEO Option Grant',
            'Strategy Inc Reports Financial Results Including Director Option Awards',
        ):
            self.assertTrue(scan.is_investor_news(headline,'BTC treasury company'))

    def test_recycled_earnings_period_uses_publication_date_and_keeps_current_developments(self):
        old='MSTR Q4 2024 Earnings: Loss Per Share Nearly Double Consensus Despite 4.2% Stock Gain'
        self.assertFalse(scan.is_investor_news(old,'BTC treasury stock','2026-10-30T12:00:00Z'))
        self.assertTrue(scan.is_investor_news(old,'BTC treasury stock','2025-02-01T12:00:00Z'))
        self.assertTrue(scan.is_investor_news(old,'BTC treasury stock'))
        for headline in (
            'MSTR Q4 2026 Earnings: Loss Per Share Narrows',
            'Strategy Inc Restates Q4 2024 Earnings After Accounting Review',
            'Strategy Inc Compares Q4 2024 Earnings with Current Treasury Results',
            'Strategy Inc Q4 2024 and Q4 2026 Earnings Comparison',
        ):
            self.assertTrue(scan.is_investor_news(headline,'BTC treasury company','2026-10-30T12:00:00Z'))

    def test_rss_and_archive_both_remove_recycled_earnings_and_static_pages(self):
        from xml.sax.saxutils import escape
        from datetime import datetime,timezone
        current_year=datetime.now(timezone.utc).year
        old=f'MSTR Q4 {current_year-3} Earnings: Loss Per Share Nearly Double Consensus'
        static='Strategy, Inc. Stock Price Today | MSTR Live Chart & News'
        real=f'Strategy Inc Reports Fiscal Year {current_year} Financial Results'
        rows=[self.story(title,entity='Strategy',url=f'https://example.com/noise-{i}')
              for i,title in enumerate((old,static,real))]
        xml='<rss><channel>'+''.join(
            '<item><title>'+escape(row['title'])+'</title><pubDate>'+row['published_at']+
            '</pubDate><link>'+row['url']+'</link><source>Publisher</source></item>' for row in rows
        )+'</channel></rss>'
        self.assertEqual([row['title'] for row in scan.parse_google_news(xml)],[real])
        merged,_=scan.merge_stories(rows,[])
        self.assertEqual([row['title'] for row in merged],[real])

    def test_routine_vesting_tax_withholding_is_not_material_news(self):
        for headline in (
            'Tax withholding covers 6,231 shares at $7.63 for Evernorth Holdings (XRPN) executive.',
            'At $7.63 per share, Evernorth Holdings (XRPN) CFO has 1,592 shares withheld for vesting taxes.'):
            self.assertFalse(scan.is_investor_news(headline,'Routine share settlement for vesting.'))
        self.assertTrue(scan.is_investor_news(
            'Evernorth Holdings Raises $425 Million to Expand XRP Treasury','XRP holdings and capital funding'))
        self.assertTrue(scan.is_investor_news(
            'Evernorth Holdings Announces Equity Facility for XRP Treasury Alongside Tax Withholding Disclosure','Material capital raise'))

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
