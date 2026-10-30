"""Network-free issuer classification, filing exclusion and event-clustering regressions."""
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
        self.assertEqual(scan.identify_entities('Lite Strategy Inc (NASDAQ: LITS) builds LTC treasury'),['Lite Strategy'])
        self.assertEqual(scan.identify_entities('Lite Strategy announces Litecoin buybacks'),['Lite Strategy'])
        self.assertNotIn('Lite Strategy',scan.identify_entities('Strategy Inc (MSTR) buys Bitcoin'))
        self.assertNotIn('Lite Strategy',scan.identify_entities('Litecoin price rises after halving'))
        self.assertEqual(scan.identify_entities('Lite Strategy partners with Strategy MSTR on digital assets'),
                         ['Strategy','Lite Strategy'])
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
        self.assertIn("'lits', 'hypestrat', 'media'",script)
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
        self.assertIn("'hypestrat', 'media'",app)
        self.assertIn(".stats-grid>#sentiment-card-purr{grid-column:1 / -1}",css)
        self.assertIn(".quote-icon-purr",css)
        self.assertIn("('hypestrat','Hyperliquid Strategies official',fetch_hypestrat_news)",scanner)

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