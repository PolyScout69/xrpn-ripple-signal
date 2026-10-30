"""Network-free issuer classification, filing exclusion and event-clustering regressions."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch
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
        self.assertEqual(scan.identify_entities('Lite Strategy Inc (NASDAQ: LITS) builds LTC treasury'),['Lite Strategy'])
        self.assertEqual(scan.identify_entities('Lite Strategy announces Litecoin buybacks'),['Lite Strategy'])
        self.assertNotIn('Lite Strategy',scan.identify_entities('Strategy Inc (MSTR) buys Bitcoin'))
        self.assertNotIn('Lite Strategy',scan.identify_entities('Litecoin price rises after halving'))
        self.assertEqual(scan.identify_entities('Lite Strategy partners with Strategy MSTR on digital assets'),
                         ['Strategy','Lite Strategy'])
        self.assertEqual(scan.identify_entities('XRP Ledger XRPL validators adopt new amendment'),[])
        self.assertNotIn('Ripple',scan.identify_entities('XRPL validators adopt new amendment'))
        self.assertIn('Ripple',scan.identify_entities('Ripple expands RLUSD bank payments'))

    def test_sbet_fwdi_are_company_specific_and_keep_stock_tickers_distinct(self):
        for headline in ('Sharplink Inc earns ETH staking rewards',
                         'SharpLink Gaming (NASDAQ: SBET) expands Ethereum treasury',
                         'SBET stock authorises a share repurchase'):
            self.assertEqual(scan.identify_entities(headline),['SharpLink Gaming'])
        for headline in ('Forward Industries Inc (NASDAQ: FWDI) increases Solana holdings',
                         'FWDI reports SOL staking rewards'):
            self.assertEqual(scan.identify_entities(headline),['Forward Industries'])
        for headline in ('Ethereum staking adoption rises as ETH rallies',
                         'Solana network validators increase SOL revenue',
                         'Forward-looking strategy for Solana investors',
                         'Ford Motor Company launches new vehicle',
                         'BitMine adds ETH to its treasury'):
            self.assertEqual(scan.identify_entities(headline),[])
        self.assertEqual(scan.classify('Sharplink Increases ETH per Share'),'Treasury')
        self.assertEqual(scan.classify('Forward Industries Reports SOL Staking Rewards'),'Treasury')

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

    def test_fwdi_organization_rss_is_dated_primary_coverage(self):
        from datetime import datetime,timezone
        from email.utils import format_datetime
        date=format_datetime(datetime.now(timezone.utc))
        link='https://www.globenewswire.com/news-release/2026/10/01/forward-sol-treasury.html'
        xml=f'<rss><channel><title>Forward Industries, Inc.</title><item><title>Forward Reports New SOL Staking Rewards</title><link>{link}</link><pubDate>{date}</pubDate><description>Forward Industries adds Solana to its treasury from validator income.</description></item><item><title>Undated issuer story is not current coverage</title><link>{link}?other=1</link></item></channel></rss>'
        with patch.object(scan,'fetch',return_value=type('Response',(),{'text':xml})()):
            rows=scan.fetch_fwdi_news()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['entities'],['Forward Industries'])
        self.assertEqual(rows[0]['source_id'],'fwdi')
        self.assertEqual(rows[0]['source_type'],'Official')
        self.assertEqual(rows[0]['url'],link)

    def test_new_official_source_failures_are_not_reported_as_success(self):
        with patch.object(scan,'fetch',side_effect=RuntimeError('Source unavailable')):
            with self.assertRaisesRegex(RuntimeError,'Source unavailable'):
                scan.fetch_sbet_news()
            with self.assertRaisesRegex(ValueError,'GlobeNewswire RSS: Source unavailable.*company archive: Source unavailable'):
                scan.fetch_fwdi_news()
            self.assertNotIn('fwdi',scan.SOURCE_WARNINGS)
        for reader,empty in ((scan.fetch_sbet_news,'<html>No releases</html>'),
                             (scan.fetch_fwdi_news,'<rss><channel/></rss>')):
            with patch.object(scan,'fetch',return_value=type('Response',(),{'text':empty})()):
                with self.assertRaises(ValueError):
                    reader()

    def test_fwdi_primary_failure_uses_dated_first_party_archive_with_warning(self):
        from datetime import datetime,timezone
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        link='https://forwardindustries.com/insights/forward-industries-reports-sol-staking'
        sitemap=f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{link}</loc></url><url><loc>https://example.com/insights/untrusted</loc></url></urlset>'
        article=f'<div data-framer-name="Article Hero"><h1>Forward Industries Reports SOL Staking Rewards</h1><time datetime="{day}T00:00:00.000Z">{day}</time></div><div data-framer-name="Article Wrapper"><div data-framer-component-type="RichTextContainer"><p>Forward Industries reports additional SOL staking rewards from its institutional validator strategy.</p></div></div>'
        calls=[]
        def fake_fetch(url):
            calls.append(url)
            if url==scan.FWDI_NEWS_RSS:
                raise RuntimeError('403 from syndicator')
            return type('Response',(),{'text':sitemap if url==scan.FWDI_SITEMAP else article})()
        with patch.object(scan,'fetch',side_effect=fake_fetch):
            rows=scan.fetch_fwdi_news()
        self.assertEqual(calls,[scan.FWDI_NEWS_RSS,scan.FWDI_SITEMAP,link])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['url'],link)
        self.assertEqual(rows[0]['published_at'][:10],day)
        self.assertEqual(rows[0]['source_type'],'Official')
        self.assertEqual(rows[0]['source_id'],'fwdi')
        self.assertIn('coverage may be incomplete',scan.SOURCE_WARNINGS['fwdi'])

    def test_fwdi_fallback_caps_details_and_does_not_invent_publication_dates(self):
        links=[f'https://forwardindustries.com/insights/release-{i}' for i in range(20)]
        sitemap='<urlset>'+''.join(f'<url><loc>{url}</loc></url>' for url in links)+'</urlset>'
        calls=[]
        def fake_fetch(url):
            calls.append(url)
            text=sitemap if url==scan.FWDI_SITEMAP else '<h1>Forward Industries Announces New Solana Treasury Program</h1>'
            return type('Response',(),{'text':text})()
        with patch.object(scan,'fetch',side_effect=fake_fetch):
            with self.assertRaisesRegex(ValueError,'no usable dated'):
                scan.fetch_fwdi_site_news()
        self.assertEqual(calls,[scan.FWDI_SITEMAP]+links[:16])

    def test_new_treasury_event_dedup_preserves_different_purchases_and_issuers(self):
        first=self.story('Sharplink Acquires 1,000,000 ETH for Ethereum Treasury',
                         entity='SharpLink Gaming',kind='Official',url='https://example.com/sbet-one')
        syndicated=self.story('SharpLink Gaming Buys 1 Million ETH for Treasury',
                              entity='SharpLink Gaming',url='https://example.com/sbet-syndicated')
        different=self.story('Sharplink Acquires 20,000 ETH for Ethereum Treasury',
                             entity='SharpLink Gaming',url='https://example.com/sbet-two')
        forward=self.story('Forward Industries Buys 1 Million SOL for Treasury',
                           entity='Forward Industries',url='https://example.com/fwdi-one')
        holdings=self.story('Forward Industries Reports Holdings of 1 Million SOL',
                            entity='Forward Industries',url='https://example.com/fwdi-holdings')
        merged,_=scan.merge_stories([first,syndicated,different,forward,holdings],[])
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

    def test_lits_issuer_archive_parsing_and_date(self):
        """A real linked issuer announcement should become one dated LITS story."""
        from datetime import datetime,timezone
        date=datetime.now(timezone.utc).strftime('%B %d, %Y')
        title='Lite Strategy Announces Covered Call Income from Litecoin Treasury'
        link='https://litestrategy.gcs-web.com/news-releases/news-release-details/lite-strategy-income'
        listing=f'<div><time>{date}</time><a href="{link}">{title}</a></div>'
        article=f'<h1>{title}</h1><time>{date}</time><p>Lite Strategy reports recurring covered call options income from the LTC treasury and plans to add more LTC per share for existing shareholders.</p>'
        class Fake:
            def __init__(self,text):self.text=text
        def fake_fetch(url):
            if url==link:return Fake(article)
            return Fake(listing)
        with patch.object(scan,'fetch',side_effect=fake_fetch):
            rows=scan.fetch_lits_news()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['entities'],['Lite Strategy'])
        self.assertEqual(rows[0]['source_type'],'Official')
        self.assertEqual(rows[0]['source_id'],'lits')
        self.assertEqual(rows[0]['url'],link)

    def test_lits_story_classification_and_dedup(self):
        main=self.story('Lite Strategy Marks 15 Years of Litecoin with Launch of Proof of Time Archive',
                        entity='Lite Strategy',kind='Official',url='https://example.com/lits-issuer')
        alt=self.story('Lite Strategy LITS launches Proof of Time Litecoin archive for 15th anniversary',
                       entity='Lite Strategy',kind='Media',url='https://example.com/lits-media')
        other=self.story('Lite Strategy Announces LTC Covered Call Yield Program',
                         entity='Lite Strategy',kind='Official',url='https://example.com/lits-options')
        merged,_=scan.merge_stories([main,alt,other],[])
        self.assertEqual(len(merged),2)
        self.assertEqual(sorted(len(x['coverage']) for x in merged),[1,2])
        self.assertEqual(scan.classify('Lite Strategy reports increasing LTC per share'),'Treasury')

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
        self.assertIn('.market-pulse-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))', stylesheet)
        self.assertIn('.market-pulse-grid{grid-template-columns:minmax(0,1fr)', stylesheet)

    def test_homepage_has_weighted_moon_sentiment_instead_of_old_cards(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'app.js').read_text(encoding='utf-8')
        css=(ROOT/'styles.css').read_text(encoding='utf-8')
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        for asset in ('xrpn','mstr'):
            self.assertIn('id="sentiment-card-'+asset+'"',html)
            self.assertIn('id="sentiment-'+asset+'-value"',html)
            self.assertIn("renderSentiment('"+asset.upper()+"')",script)
        self.assertNotIn('id="stat-treasury"',html)
        self.assertNotIn('id="stat-health"',html)
        self.assertNotIn("'stat-health'",script)
        self.assertIn('Moon Sentiment — 30-day weighted index',html)
        self.assertIn('Limited coverage',script)
        self.assertIn('.moon-sentiment-card',css)
        self.assertIn("'sentiment_30d':sentiment_30d",scanner)
        self.assertIn('.slice(0,48)',script)

    def test_homepage_lits_price_filter_and_sentiment(self):
        homepage=(ROOT/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'app.js').read_text(encoding='utf-8')
        css=(ROOT/'styles.css').read_text(encoding='utf-8')
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        self.assertEqual(homepage.count('<tv-single-ticker symbol="NASDAQ:LITS"'),1)
        self.assertIn('https://www.tradingview.com/symbols/NASDAQ-LITS/',homepage)
        self.assertIn('data-entity="Lite Strategy"',homepage)
        self.assertIn('id="sentiment-card-lits"',homepage)
        self.assertIn("renderSentiment('LITS')",script)
        self.assertIn("'Lite Strategy':'LITS'",script)
        for source_id in ('lits','hypestrat','sbet','fwdi','media'):
            self.assertIn("'"+source_id+"'",script)
        self.assertIn(".quote-icon-lits",css)
        self.assertIn("('lits','Lite Strategy official',fetch_lits_news)",scanner)


    def test_purr_ticker_and_hype_token_are_not_confused(self):
        self.assertEqual(
            scan.identify_entities('Hyperliquid Strategies Inc (NASDAQ: PURR) earns HYPE staking yield'),
            ['Hyperliquid Strategies'])
        self.assertEqual(
            scan.identify_entities('PURR stock expands HYPE treasury buyback plan'),
            ['Hyperliquid Strategies'])
        self.assertNotIn('Hyperliquid Strategies',
                         scan.identify_entities('HYPE token rallies on Hyperliquid network activity'))
        self.assertNotIn('Hyperliquid Strategies',
                         scan.identify_entities('PURR meme coin launches on Hyperliquid'))
        self.assertNotIn('Hyperliquid Strategies',
                         scan.identify_entities('Hyperion DeFi expands HYPE treasury'))
        self.assertEqual(scan.classify('Hyperliquid Strategies Reports HYPE Treasury Staking Revenue'),'Treasury')

    def test_hypestrat_official_press_release_archive(self):
        """Primary release links and dates load without network dependence."""
        from datetime import datetime, timezone
        date=datetime.now(timezone.utc).strftime('%B %d, %Y')
        title='Hyperliquid Strategies Inc Announces Increase of Stock Repurchase Program to $100 Million'
        url='https://www.prnewswire.com/news-releases/hyperliquid-strategies-inc-announces-increase-of-stock-repurchase-program-to-100-million-302918312.html'
        listing=f'<div><time>{date}</time><a href="{url}">{title}</a></div>'
        article=f'<h1>{title}</h1><time>{date}</time><p>Hyperliquid Strategies Inc, Nasdaq PURR, is expanding its common stock repurchase authorisation from $30 million to $100 million as part of its HYPE treasury management strategy.</p>'
        class Fake:
            def __init__(self,txt):self.text=txt
        def fake_fetch(target):
            return Fake(article if target==url else listing)
        with patch.object(scan,'fetch',side_effect=fake_fetch):
            rows=scan.fetch_hypestrat_news()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['entities'],['Hyperliquid Strategies'])
        self.assertEqual(rows[0]['source_type'],'Official')
        self.assertEqual(rows[0]['source_id'],'hypestrat')
        self.assertEqual(rows[0]['url'],url)

    def test_hypestrat_duplicate_buyback_news_keeps_source_links(self):
        main=self.story('Hyperliquid Strategies Inc Increases Stock Repurchase Program to $100 Million',
                        entity='Hyperliquid Strategies',kind='Official',
                        url='https://example.com/purr-issuer')
        other=self.story('PURR Buyback Raised to $100M by Hyperliquid Strategies',
                         entity='Hyperliquid Strategies',kind='Media',
                         url='https://example.com/purr-media')
        merger=self.story('Lite Strategy Announces 20 Million LTC Treasury Shares',
                          entity='Lite Strategy',kind='Media',
                          url='https://example.com/lits-other')
        merged,_=scan.merge_stories([main,other,merger],[])
        self.assertEqual(len(merged),2)
        related=next(x for x in merged if 'Hyperliquid Strategies' in x['entities'])
        self.assertEqual(related['source_type'],'Official')
        self.assertEqual(len(related['coverage']),2)

    def test_purr_appears_in_quote_filter_and_sentiment_ui(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        app=(ROOT/'app.js').read_text(encoding='utf-8')
        css=(ROOT/'styles.css').read_text(encoding='utf-8')
        scanner=(ROOT/'scripts/scan.py').read_text(encoding='utf-8')
        for token in ('<tv-single-ticker symbol="NASDAQ:PURR"', 'id="sentiment-card-purr"',
                      'data-entity="Hyperliquid Strategies"','class="sentiment-ticker">PURR</strong>'):
            self.assertIn(token,html)
        self.assertIn('https://www.tradingview.com/symbols/NASDAQ-PURR/',html)
        self.assertIn("renderSentiment('PURR')",app)
        self.assertIn("'Hyperliquid Strategies':'PURR'",app)
        for source_id in ('hypestrat','sbet','fwdi','media'):
            self.assertIn("'"+source_id+"'",app)
        soup=BeautifulSoup(html,'html.parser')
        expected_order=['MSTR','XRPN','SBET','PURR','FWDI','LITS']
        quote_order=[card.select_one('tv-single-ticker')['symbol'].split(':')[-1]
                     for card in soup.select('.market-pulse-grid > .quote-card')]
        sentiment_cards=soup.select('.stats-grid > .moon-sentiment-card')
        sentiment_order=[card.select_one('.sentiment-ticker').get_text(strip=True)
                         for card in sentiment_cards]
        self.assertEqual(quote_order,expected_order)
        self.assertEqual(sentiment_order,quote_order)
        crypto_by_ticker={'MSTR':'btc','XRPN':'xrp','SBET':'eth',
                          'PURR':'hype','FWDI':'sol','LITS':'ltc'}
        for ticker,card in zip(sentiment_order,sentiment_cards):
            logo=card.select_one('.sentiment-asset img')
            self.assertIsNotNone(logo)
            self.assertEqual(logo['src'],'assets/crypto/'+crypto_by_ticker[ticker]+'.svg')
            self.assertTrue(logo.get('alt','').strip())
        self.assertIn(".quote-icon-purr",css)
        self.assertIn("('hypestrat','Hyperliquid Strategies official',fetch_hypestrat_news)",scanner)

    def test_no_price_hype(self):
        self.assertFalse(scan.is_investor_news('XRP price prediction huge rally','Could hit $100'))
        self.assertTrue(scan.is_investor_news('XRP Ledger launches institutional tokenization infrastructure','On XRPL'))
        self.assertTrue(scan.is_investor_news('Rumour: SWIFT to partner with Ripple for XRP settlement','Unconfirmed agreement'))
        self.assertTrue(scan.is_investor_news('Evernorth reportedly exploring XRP treasury lending yield','Potential revenue'))
        self.assertFalse(scan.is_investor_news('XRP price prediction by analyst predicts $100','Pure speculation'))

    def test_quote_listing_metadata_is_not_an_article(self):
        self.assertFalse(scan.is_investor_news(
            'Sharplink, Inc. (SBET) Stock Price, News, Quote & History','Ethereum treasury stock'))
        self.assertFalse(scan.is_investor_news('Forward Industries (FWDI) Stock Quote & News','Solana treasury'))
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
