#!/usr/bin/env python3
"""Daily, source-first investor news scan for Strategy, Evernorth, SharpLink Gaming and Ripple.

Sources: official issuer announcements plus company-specific financial RSS.
Standalone SEC filing records are deliberately excluded from the feed and Moon Meter.
Coverage is grouped by event. No language model invents summaries or ratings.

Run: python scripts/scan.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'news.json'
# Make shared price-direction scoring importable for both CI and local tests.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.moon_meter import moon_for_story
from scripts.sentiment import aggregate_sentiment
RIPPLE_PRESS_URL = 'https://ripple.com/press-releases/'
EVERNORTH_HOME = 'https://www.evernorth.xyz/'
EVERNORTH_WIRE = 'https://www.prnewswire.com/news/evernorth-holdings-inc./'
# Public news-widget endpoints used by the companies' investor pages.
# The B2i API parameter is a public website identifier, not a private token.
SBET_NEWS_URL = 'https://www.b2i.us/b2i/LibraryFeed.asp?b=2597&api=Ex4Bw5Wv2&i=30&out=38&a=1'
TRACKED_ENTITIES = ('Strategy', 'Evernorth', 'SharpLink Gaming', 'Ripple')
RETIRED_TAGS = frozenset(('xrp ecosystem', 'lite strategy', 'lits', 'hyperliquid strategies',
                          'purr', 'forward industries', 'fwdi', 'litecoin', 'ltc', 'hype', 'solana', 'sol'))
MAX_AGE_DAYS = 365
MAX_STORIES = 500
REQUEST_TIMEOUT = 22
USER_AGENT = 'SignalInvestorNews/1.0 (investor news aggregator; public sources)'
NEWS_QUERIES = [
    '"Evernorth Holdings" XRP financing treasury shares -Cigna -pharmacy',
    '"XRPN" partnership XRP treasury capital raise',
    '"Ripple Labs" OR "Ripple Treasury" OR "Ripple Custody" partnership OR launch OR banking',
    '"Ripple" "XRP" (rumor OR rumour OR reportedly OR potential) (SWIFT OR bank OR partnership OR settlement OR ETF)',
    '"Evernorth" "XRPN" (rumor OR rumour OR reportedly OR exploring) (yield OR lending OR partnership OR treasury)',
    '"Strategy Inc" "MSTR" bitcoin treasury acquisitions capital',
    '"MicroStrategy" "MSTR" bitcoin preferred STRC earnings',
    '"Sharplink" (SBET OR Ethereum OR ETH) (treasury OR staking OR earnings OR shares OR buyback)',
    '"SharpLink Gaming" (Ethereum OR ETH OR SBET)',
    '"SBET" (treasury OR staking OR repurchase OR dilution)',
    '"Strategy" "MSTR" bitcoin purchase treasury financing',
    '"Michael Saylor" "MSTR" bitcoin purchases treasury',
    '"Strategy" ("STRC" OR "STRK" OR "STRF") preferred shares dividends buyback',
]
MONTH_DATE = re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+20\d{2}\b',re.I)
DATE_PATTERNS = ('%b %d, %Y', '%B %d, %Y', '%b %d %Y', '%B %d %Y', '%b. %d, %Y')
STOP = set('the a an and or in of for to on by with from as at into that is will new has have its their about announces announce says launch launches unveils introduces today company inc holdings labs support investor global'.split())
NEGATIVE_MEDIA = (
    'price prediction', 'price target', 'could hit $', 'will hit $',
    'technical analysis', 'whale alert', 'moonshot', 'best altcoins',
    'buy now', 'surge to $', 'breakout signal', 'top crypto picks',
    'will xrp reach', 'trader predicts', 'charts signal', 'analyst predicts',
    'short squeeze', 'stock surges', 'stock moved', 'performance duel',
    'how to play', 'traders eye', 'price forecast', 'price outlook',
    'bulls build', 'market sentiment', 'community insights', 'price prediction',
    'price targets', 'up or down today', 'what signal does', 'buy the dip',
    'which is the better buy', 'holders have been waiting for',
    'how high can', 'crypto millionaire', 'bitcoin windfall', 'as xrp jumps',
    'what price will', 'massive rally', 'millionaire', 'meme coin',
)
TOPIC_HINTS = ('share','equity','offering','warrant',
    'capital','rais','fund','facility','financ','treasury','xrp per share','yield','liquidity','institution','partnership',
    'partner','collaborat','custody','payment','settlement','tokeniz','tokenis',
    'product','launch','license','licence','lawsuit','regulat','merger','acquisition',
    'integration','rlusd','lending','bank','rwa','onchain','xrpl',
    'mstr','microstrategy','saylor','strc','strk','strf',
    'acquir','purchas','repurchas','preferred','convertible','dividend','reserve','earnings',
    'etf','validator','amendment','amm','dex','defi','network',
    'covered call','nav per share','option premium','staking','validator commission','adjusted nav',
    'sharplink','sbet','ethereum','ether treasury','eth per share')
LOG = logging.getLogger('signal')


def session_factory() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=3, connect=2, read=2, backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET'], respect_retry_after_header=True)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

SESSION = session_factory()


def fetch(url: str) -> requests.Response:
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json,text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
    }
    response = SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response


def timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_date(value: str | None, date_only: bool = False) -> str | None:
    if not value:
        return None
    text = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (ValueError, TypeError, IndexError):
            clean = text.replace('Sept ', 'Sep ').replace('September.', 'September')
            for pattern in DATE_PATTERNS:
                try:
                    dt = datetime.strptime(clean, pattern)
                    break
                except ValueError:
                    continue
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if date_only:
        dt = dt.replace(hour=12,minute=0,second=0,microsecond=0)
    return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def is_recent(date_str: str | None) -> bool:
    try:
        t = datetime.fromisoformat(str(date_str).replace('Z','+00:00'))
        return datetime.now(timezone.utc)-timedelta(days=MAX_AGE_DAYS) <= t <= datetime.now(timezone.utc)+timedelta(days=1)
    except (ValueError,TypeError):
        return False


def plain_text(html: str, max_length: int = 210) -> str:
    stripped = BeautifulSoup(str(html or ''), 'html.parser').get_text(' ',strip=True)
    stripped = re.sub(r'\s+', ' ', stripped).strip()
    if len(stripped) > max_length:
        return stripped[:max_length].rsplit(' ',1)[0].rstrip('.,;')+'…'
    return stripped


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.netloc:
        return ''
    # Advertising / link-tracking fragments shouldn't create duplicate articles.
    params=[(k,v) for k,v in urllib.parse.parse_qsl(parsed.query) if not k.lower().startswith(('utm_','fbclid','gclid'))]
    return urllib.parse.urlunsplit((parsed.scheme,parsed.netloc.lower(),parsed.path,urllib.parse.urlencode(params),'')).rstrip('/')


def identify_entities(content: str, force: str | None = None) -> list[str]:
    """Match tracked companies; generic token/network headlines are not issuers."""
    if force in TRACKED_ENTITIES:
        return [force]
    x = content.lower()
    # Strategy is an ordinary English noun. Strip the retired issuer's name
    # before matching so Lite Strategy, Inc. cannot be mistaken for MSTR,
    # while a story mentioning both companies still retains real MSTR news.
    strategy_text=re.sub(r'\blite\s+strategy(?:\s*,?\s*(?:inc\.?|incorporated))?', ' ', x)
    strategy = bool(re.search(r'\bmicrostrategy\b|\bmstr\b|\bstrategy inc\b|\bstrategy incorporated\b|\bstrategy\s*\(nasdaq', strategy_text)) or bool(re.search(r'\bstrategy\b', strategy_text) and any(v in strategy_text for v in ('btc yield','strc','strf','strk','michael saylor','bitcoin treasury company','bitcoin acquisitions')))
    if 'michael saylor' in strategy_text and any(v in strategy_text for v in ('bitcoin', 'mstr', 'treasury', 'strategy')):
        strategy = True
    sharplink = bool(re.search(r'\bsharplink\b|\bsharp\s+link\s+gaming\b|\bsbet\b', x))
    evernorth = bool('xrpn' in x or 'evernorth holdings' in x or ('evernorth' in x and ('xrp' in x or 'treasury' in x)))
    if any(v in x for v in ('pharmacy', 'cigna', 'health services')) and not any(v in x for v in ('xrpn', 'xrp treasury', 'digital asset treasury')):
        evernorth = False
    # Ripple company news; a casual "Ripple (XRP)" price headline is not automatically company news.
    ripple = bool(re.search(r'\bripple\b', x) and any(v in x for v in (
        'ripple labs', 'ripple treasury', 'ripple payments', 'ripple custody', 'rlusd',
        'partnership', 'partners', 'payment', 'bank', 'acquir', 'license', 'licence',
        'company', 'enterprise', 'custody', 'product', 'launch', 'settlement', 'prime')))
    result = []
    if evernorth: result.append('Evernorth')
    if ripple: result.append('Ripple')
    if strategy: result.append('Strategy')
    if sharplink: result.append('SharpLink Gaming')
    return result


def classify(title: str, excerpt: str = '', force_sec: bool = False) -> str:
    if force_sec:return 'SEC filings'
    text=(title+' '+excerpt).lower()
    title_low=title.lower()
    if any(p in title_low for p in ('10-k','10-q','8-k','sec filing','registration statement','form s-1','form s-3','prospectus','insider transaction')):
        return 'SEC filings'
    if any(p in title_low for p in ('equity facility','capital raise','share sale','stock offering','shares issued','share issuance','warrant','ipo','nasdaq listing','business combination','shareholder vote','merger','funding round','at-the-market','atm program','preferred stock','convertible notes','buyback','repurchase')):
        return 'Capital markets'
    if any(p in title_low for p in ('xrp treasury','treasury deployment','xrp per share','lending protocol','liquidity report','yield strateg','bitcoin treasury','btc yield','btc purchase','bitcoin purchase','acquires bitcoin','buys bitcoin','btc holdings','bitcoin holdings','bitcoin per share','covered call options','option premium','staking revenue','staking yield','validator commissions',
            'ethereum treasury','ether treasury','eth treasury','eth per share','eth holdings','ethereum holdings','staking rewards')):
        return 'Treasury'
    if any(p in title_low for p in ('regulation','regulatory','sec lawsuit','court rules','license approved','licence','legislation','digital asset policy')):
        return 'Regulation'
    if any(p in title_low for p in ('names chief','appoints ','chief investment officer','new ceo','new cfo','board member')):
        return 'Leadership'
    if any(p in title_low for p in ('partners','partner with','partner to','partner for','partnership','collaborat','strategic relationship','deepens relationship')):
        return 'Partnerships'
    if any(p in title_low for p in ('launch','introduc','new platform','new product','rolls out','unveil','prime expands','perpetual swaps','offering')):
        return 'Products'
    if any(p in title_low for p in ('tokenis','tokeniz','institutional','adoption','integrat','custody','xrpl','xrp ledger','stablecoin','payments','validator','amendment','amm','dex','defi','etf')):
        return 'Adoption'
    # If the lead doesn't signal a topic, use the supporting snippet as backup.
    if 'treasury' in text or 'xrp per share' in text:return 'Treasury'
    if 'sec' in text or 'regulation' in text:return 'Regulation'
    return 'Adoption'


def score_story(title: str, category: str, source_type: str, entities: list[str]) -> tuple[str,int]:
    x=title.lower()
    score={'SEC':84,'Official':72,'Media':54,'News':54}.get(source_type,50)
    bonus={'SEC filings':10,'Capital markets':14,'Treasury':11,'Partnerships':8,'Products':8,'Regulation':10,'Adoption':6,'Leadership':4}.get(category,0)
    score+=bonus
    if any(e in entities for e in TRACKED_ENTITIES if e != 'Ripple'):score+=5
    if any(k in x for k in ('equity facility','dilution','material agreement','financing','s-1','10-k','10-q','share offering','bitcoin purchase','repurchase','preferred stock')):score+=8
    if any(k in x for k in ('institutional','bank','xrpl','xrp ledger','strategic','treasury','settlement','covered call','staking','validator','ethereum')):score+=3
    score=min(99,score)
    return ('High' if score>=83 else 'Medium' if score>=66 else 'Low'),score


def investor_angle(category: str) -> str:
    return {
      'SEC filings':'Primary regulatory disclosure. Review the full filing for material agreements, risk factors, governance changes and potential effects on share count.',
      'Capital markets':'Capital access can fund growth or treasury purchases but financing may dilute equity holders or create fixed obligations. Check issuance prices, net proceeds, debt, and coin holdings per share.',
      'Treasury':'Track BTC, XRP or ETH holdings per diluted share, staking or option income, funding costs, custody and counterparty risk. Gross token holdings do not alone prove accretion.',
      'Partnerships':'A strategic relationship can expand distribution, but announced plans do not confirm revenue, usage or completed integration.',
      'Products':'A product announcement can expand the offering; adoption, transaction volumes and commercial economics remain to be demonstrated.',
      'Adoption':'Track active usage and measurable adoption. Network activity does not automatically translate into token price appreciation or company revenue.',
      'Regulation':'A change in regulation could affect eligibility and adoption. Verify the original ruling, rule or company disclosure before acting.',
      'Leadership':'A senior appointment may influence execution, risk controls and strategy. Track subsequent measurable results.',
    }.get(category,'Check the original report for financial significance, implementation status and risks.')


def make_story(*, title: str, date: str, url: str, source: str, source_type: str,
    source_id: str, entities: list[str], excerpt: str, category: str | None = None,
    date_only: bool = False) -> dict | None:
    title=plain_text(title,230)
    safe_url=canonical_url(url)
    normalized=normalize_date(date,date_only=date_only)
    if len(title)<16 or not safe_url or not normalized or not is_recent(normalized) or not entities:
        return None
    category=category or classify(title,excerpt)
    if category=='SEC filings' or source_type=='SEC' or str(source_id).startswith('sec_'):
        return None
    impact,score=score_story(title,category,source_type,entities)
    return {
        'id':hashlib.sha1(safe_url.encode()).hexdigest()[:14],
        'title':title,'published_at':normalized,'date_only':date_only,
        'entities':entities,'category':category,'impact':impact,'score':score,
        'source':source,'source_type':source_type,'source_id':source_id,
        'url':safe_url,'excerpt':plain_text(excerpt,235) or 'Open the original report for details.',
        'why_it_matters':investor_angle(category),'tags':[],
        'added_at':timestamp_now(),'verified_seed':False,
    }


def extract_date(text: str) -> str | None:
    match=MONTH_DATE.search(text or '')
    return normalize_date(match.group(0)) if match else None


def news_context(element) -> str:
    """Look for a displayed date near a headline, without swallowing the whole page."""
    node=element
    for _ in range(4):
        if node is None:break
        value=node.get_text(' ',strip=True)
        if len(value)<1100 and MONTH_DATE.search(value):return value
        node=node.parent
    return ''


def fetch_ripple_press() -> list[dict]:
    html=fetch(RIPPLE_PRESS_URL).text
    soup=BeautifulSoup(html,'html.parser')
    candidates={}
    for a in soup.find_all('a',href=True):
        link=urllib.parse.urljoin(RIPPLE_PRESS_URL,a['href'])
        if not re.match(r'https://(?:www\.)?ripple\.com/ripple-press/',link):continue
        title=plain_text(a.get_text(' ',strip=True),240)
        if len(title)<25:continue
        candidates[canonical_url(link)]=(title,extract_date(news_context(a)))
    if not candidates:
        raise ValueError('Ripple press-centre layout may have changed: no article links found.')
    stories=[]
    for link,(fallback_title,date_from_listing) in list(candidates.items())[:13]:
        try:
            article=BeautifulSoup(fetch(link).text,'html.parser')
            heading=article.find('h1')
            title=heading.get_text(' ',strip=True) if heading else fallback_title
            whole_text=article.get_text(' ',strip=True)
            heading_at=whole_text.lower().find(title[:30].lower())
            nearby=whole_text[heading_at:heading_at+1600] if heading_at >= 0 else whole_text[:4000]
            meta_date=''
            for meta in article.find_all('meta'):
                if meta.get('property','').lower() in ('article:published_time','article:modified_time') or meta.get('name','').lower() in ('date','pubdate','datepublished','dc.date'):
                    meta_date=normalize_date(meta.get('content','')) or ''
                    if meta_date:break
            if not meta_date:
                for tag in article.find_all('time'):
                    meta_date=normalize_date(tag.get('datetime','')) or extract_date(tag.get_text(' ',strip=True)) or ''
                    if meta_date:break
            raw_html=str(article)
            raw_date=re.search(r'\b(?:datePublished|dateCreated|published_time|publish_date)\b[^<]{0,200}?(20\d{2}-\d{2}-\d{2})', raw_html, re.I)
            date=date_from_listing or meta_date or extract_date(nearby) or extract_date(whole_text[:14000]) or (normalize_date(raw_date.group(1)) if raw_date else None) or extract_date(raw_html[:50000])
            if not date:continue
            paragraphs=[plain_text(p.get_text(' ',strip=True),260) for p in article.find_all('p')]
            lead=next((p for p in paragraphs if 75<len(p)<260 and not p.lower().startswith(('cookies','read more','forward-looking'))),'')
            if not lead:
                # Several Ripple releases use a subtitle rather than a <p> intro.
                lead=next((plain_text(t.get_text(' ',strip=True),240) for t in article.find_all(['h2','h3']) if len(t.get_text(' ',strip=True))>55),'')
            story=make_story(title=title,date=date,url=link,source='Ripple press centre',source_type='Official',source_id='ripple',entities=['Ripple'],excerpt=lead or title,date_only=True)
            if story:stories.append(story)
        except Exception as exc:
            LOG.warning('Could not open Ripple press article %s: %s',link,exc)
        time.sleep(0.15)
    if not stories:
        # Some versions of Ripple's front end omit dates from machine-readable
        # article HTML. Correlate issuer-hosted headlines with indexed RSS dates;
        # keep the *issuer* URL as the primary story link.
        try:
            q=urllib.parse.urlencode({'q':'site:ripple.com/ripple-press Ripple','hl':'en-US','gl':'US','ceid':'US:en'})
            indexed=rss_items(fetch('https://news.google.com/rss/search?'+q).text)
            for link,(issuer_title,_) in candidates.items():
                x=norm_words(issuer_title)
                if len(x)<3:continue
                best=None
                best_score=0
                for row in indexed:
                    y=norm_words(row.get('title',''))
                    common=len(x & y)
                    score=common/max(1,min(len(x),len(y)))
                    if common>=3 and score>best_score:
                        best,best_score=row,score
                if best and best_score>=.67:
                    story=make_story(title=issuer_title,date=best.get('date'),url=link,
                        source='Ripple press centre',source_type='Official',source_id='ripple',
                        entities=['Ripple'],excerpt=issuer_title)
                    if story:stories.append(story)
        except Exception as exc:
            LOG.warning('Ripple official date fallback unavailable: %s',exc)
    if not stories:raise ValueError('Ripple press articles found, but dates/details could not be extracted.')
    return stories


def fetch_evernorth_news() -> list[dict]:
    """Monitor the issuer site, backed by its official PR Newswire release archive.

    Evernorth's homepage includes CMS cards that may be dynamically linked.
    PR Newswire articles are issuer-issued company releases, not third-party
    editorials, and provide persistent canonical links when a card has no URL.
    """
    sources=[]
    try:
        sources.append((EVERNORTH_HOME,BeautifulSoup(fetch(EVERNORTH_HOME).text,'html.parser')))
    except Exception as exc:
        LOG.warning('Evernorth company website unavailable: %s',exc)
    try:
        sources.append((EVERNORTH_WIRE,BeautifulSoup(fetch(EVERNORTH_WIRE).text,'html.parser')))
    except Exception as exc:
        LOG.warning('Evernorth issuer newswire unavailable: %s',exc)
    if not sources:
        raise ValueError('Neither the company website nor its issuer newswire responded.')
    links=[]
    for homepage,soup in sources:
        for a in soup.find_all('a',href=True):
            url=urllib.parse.urljoin(homepage,a['href'])
            title=plain_text(a.get_text(' ',strip=True),210)
            allowed=(homepage==EVERNORTH_HOME and 'evernorth.xyz' in urllib.parse.urlsplit(url).netloc) or (homepage==EVERNORTH_WIRE and '/news-releases/' in url)
            if allowed and 27<=len(title)<=210 and 'evernorth' in title.lower() and not re.search(r'health|pharmacy|cigna',title,re.I):
                links.append((title,url,extract_date(news_context(a)),homepage))
        if homepage==EVERNORTH_HOME:
            for heading in soup.find_all(['h2','h3','h4']):
                title=plain_text(heading.get_text(' ',strip=True),210)
                if len(title)<27 or not any(k in title.lower() for k in ('evernorth','xrp liquidity report')):continue
                anc=heading.find_parent('a',href=True)
                if not anc:
                    node=heading
                    for _ in range(3):
                        node=node.parent
                        if not node:break
                        anc=node.find('a',href=True)
                        if anc:break
                if anc:
                    url=urllib.parse.urljoin(EVERNORTH_HOME,anc.get('href',''))
                    links.append((title,url,extract_date(news_context(heading)),homepage))
    stories=[]
    seen=set()
    for title,url,date,homepage in links[:55]:
        safe_url=canonical_url(url)
        if not safe_url or safe_url in seen or safe_url==canonical_url(homepage):continue
        source_name='Evernorth official site' if homepage==EVERNORTH_HOME else 'Evernorth Holdings / PR Newswire'
        if not date:
            try:
                article=BeautifulSoup(fetch(url).text,'html.parser')
                date=extract_date(article.get_text(' ',strip=True)[:2400])
            except Exception as exc:
                LOG.debug('Cannot retrieve publisher date %s: %s',url,exc)
        if not date:continue
        story=make_story(title=title,date=date,url=url,source=source_name,source_type='Official',source_id='evernorth',entities=['Evernorth'],excerpt=f'Issuer announcement: {title}',date_only=True)
        if story:
            stories.append(story)
            seen.add(safe_url)
    if not stories:
        raise ValueError('Company/newswire sites responded but no dated, linked issuer announcements could be extracted.')
    return stories


def fetch_sbet_news() -> list[dict]:
    """Read the official Sharplink investor-page B2i press-release widget.

    Its archive provides publication dates and stable HTML release links.
    Keep the release's ID and company query parameters: they identify the
    article, unlike optional marketing parameters removed by canonical_url.
    """
    soup=BeautifulSoup(fetch(SBET_NEWS_URL).text,'html.parser')
    stories=[]
    seen=set()
    for card in soup.select('.PressItem38')[:30]:
        anchor=card.select_one('.PressItem38Headline a[href]')
        date_node=card.select_one('.PressItem38Date')
        if anchor is None or date_node is None:
            continue
        url=canonical_url(urllib.parse.urljoin(SBET_NEWS_URL,anchor['href']))
        host=urllib.parse.urlsplit(url).hostname
        if host not in ('www.pressviewer.com','pressviewer.com','www.b2i.us','b2i.us',
                        'www.sharplink.com','sharplink.com') or url in seen:
            continue
        title=plain_text(anchor.get_text(' ',strip=True),230)
        date=extract_date(date_node.get_text(' ',strip=True))
        if not date:
            continue
        body=card.select_one('.PressItem38Body')
        excerpt=plain_text(body.get_text(' ',strip=True),235) if body else ''
        item=make_story(title=title,date=date,url=url,
                        source='Sharplink investor relations',source_type='Official',
                        source_id='sbet',entities=['SharpLink Gaming'],
                        excerpt=excerpt or 'Issuer announcement: '+title,date_only=True)
        if item:
            stories.append(item)
            seen.add(url)
    if not stories:
        raise ValueError('Sharplink official news widget yielded no usable dated release links.')
    return stories


def rss_items(xml_text: str) -> list[dict]:
    root=ET.fromstring(xml_text)
    result=[]
    for item in root.findall('.//item'):
        def value(name):
            el=item.find(name)
            return ((el.text or '').strip() if el is not None else '')
        source_el=item.find('source')
        result.append({
            'title':value('title'), 'url':value('link'), 'date':value('pubDate'),
            'excerpt':value('description'),
            'publisher':(source_el.text or '').strip() if source_el is not None else '',
        })
    return result


def is_investor_news(title: str, excerpt: str) -> bool:
    text=(title+' '+excerpt).lower()
    headline=title.lower()
    # Search indexes also return persistent quote landing pages as "news".
    # The template wording is distinct from an actual exchange-listing event.
    if re.search(r'\b(?:stock|share) price\b.{0,45}\bquote\b.{0,20}\b(?:history|historical)\b',headline):
        return False
    if re.search(r'\b(?:stock|share) (?:price|quote)\s*[,|:/&–-]\s*(?:news|quote|chart|historical)\b',headline):
        return False
    # Routine share withholding to settle an executive's vesting taxes is
    # filing-derived administrative noise, not a new treasury investment.
    withholding=bool(re.search(r'\btax[\s-]+withhold(?:ing|ings)?\b|\bwithheld\b.{0,55}\b(?:tax|taxes|vesting)\b|\bvesting\b.{0,45}\b(?:tax|taxes|withhold\w*)\b',headline))
    material=bool(re.search(r'\b(?:capital raise|equity facility|share offering|public offering|private placement|treasury (?:purchase|acquisition|funding)|staking (?:revenue|yield|rewards))\b|\brais(?:e|es|ed|ing)\b.{0,35}\b(?:million|billion|funds?|capital)\b',headline))
    if withholding and not material:
        return False
    if any(term in text for term in NEGATIVE_MEDIA):return False
    if any(v in text for v in ('binance square', 'price forecast', 'massive price rally', 'exclusive price prediction')):return False
    if ('cigna' in text or 'pharmacy' in text or 'health services' in text) and not 'xrpn' in text:return False
    return any(term in text for term in TOPIC_HINTS)


def parse_google_news(xml_text: str) -> list[dict]:
    stories=[]
    for entry in rss_items(xml_text):
        raw_title=plain_text(entry['title'],230)
        publisher=entry['publisher'] or 'Google News publisher'
        if raw_title.endswith(' - '+publisher):raw_title=raw_title[:-(len(publisher)+3)]
        excerpt=plain_text(entry['excerpt'],210)
        entities=identify_entities(raw_title+' '+excerpt)
        if not entities or not is_investor_news(raw_title,excerpt):continue
        category=classify(raw_title,excerpt)
        # Google's RSS hyperlinks are a gateway to the publisher, not the original URL.
        story=make_story(title=raw_title,date=entry['date'],url=entry['url'],source=publisher+' · via Google News',source_type='Media',source_id='media',entities=entities,excerpt=excerpt or raw_title,category=category)
        if story:stories.append(story)
    return stories


def fetch_media_news() -> list[dict]:
    articles=[]
    successes=0
    for query in NEWS_QUERIES:
        params=urllib.parse.urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
        url=f'https://news.google.com/rss/search?{params}'
        try:
            text=fetch(url).text
            articles.extend(parse_google_news(text))
            successes+=1
        except Exception as exc:
            LOG.warning('Google News search failed (%s): %s',query[:40],exc)
    if not successes:raise ValueError('All Google News RSS requests failed.')
    return articles


# Multi-outlet coverage of the same announcement must occupy ONE feed card.
EVENT_STOP = STOP | set('''ripple evernorth strategy microstrategy xrp xrpl ledger bitcoin btc digital assets crypto
    partners partnership announces announced plans planned secures secures potential committed
    reports report backed reveals update updates fund funds funded initiative holdings buys buying
    purchase purchases acquire acquires acquired announces announces expansion expands 
    xrpn mstr business cryptocurrency dollars million billion approximately intended'''.split())


def norm_words(title: str) -> set[str]:
    text = plain_text(title, 230).lower()
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:million|mn|m)\b', r'\1m', text)
    text = re.sub(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:billion|bn|b)\b', r'\1b', text)
    return {w for w in re.findall(r'[a-z0-9]+', text) if len(w)>2 and w not in EVENT_STOP}


# Semantic event matching for recurring Strategy (MSTR) disclosures.
# The same STRC repurchase is reported as a buyback, preferred-stock spend,
# or a week without BTC purchases. Headline token overlap is not sufficient.
STRC_INSTRUMENT = re.compile(r'\bstrc\b|\bstretch\b|\bpreferred(?:\s+(?:stock|shares?))?\b', re.I)
STRC_BUYBACK = re.compile(r'\brepurchas\w*\b|\bbuy[\s-]?backs?\b|\bbuying back\b|\bbought back\b', re.I)
STRC_SPEND = re.compile(
    r'\b(?:spends?|spent|spending)\b.{0,80}\b(?:strc|preferred\s+(?:stock|shares?))\b', re.I)
STRC_AUTHORIZATION = re.compile(
    r'\b(?:raises?|boosts?|doubles?|expands?|increases?)\b.{0,85}\b(?:buy[\s-]?back|repurchas\w*)\b'
    r'.{0,65}\b(?:cap|program(?:me)?|authoriz\w*|limit)\b|'
    r'\b(?:buy[\s-]?back|repurchas\w*)\b.{0,60}\b(?:cap|program(?:me)?|authoriz\w*|limit)\b'
    r'.{0,45}\b(?:to|reaches?|raised|boost\w*|expand\w*)\b|'
    r'\b(?:doubles?|raises?|boosts?|expands?)\b.{0,70}\bbuy[\s-]?back\b.{0,40}\bto\b'
    r'.{0,15}\$\s*\d+(?:\.\d+)?\s*(?:billion|bn|b)\b', re.I)
NEWS_MONEY = re.compile(
    r'(?:\$\s*|usd\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|mn|m|billion|bn|b)\b', re.I)
MAX_COVERAGE_LINKS = 48


def _news_week(date: str) -> str:
    """Publication ISO week, not calendar month: weekly repurchases are distinct."""
    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
    year, week, _ = dt.isocalendar()
    return f'{year}-W{week:02d}'


def _strc_transaction_amount(title: str) -> float | None:
    """Find the STRC amount even when a headline also states BTC spending."""
    instrument=[m.start() for m in re.finditer(
        r'\bstrc\b|\bpreferred(?:\s+(?:stock|shares?))?\b',title,re.I)]
    action=[m.start() for m in re.finditer(
        r'\brepurchas\w*\b|\bbuy[\s-]?backs?\b',title,re.I)]
    bitcoin=[m.start() for m in re.finditer(r'\b(?:bitcoin|btc)\b',title,re.I)]
    if not instrument and not action:
        return None
    ranked=[]
    for match in NEWS_MONEY.finditer(title):
        amount=float(match.group(1).replace(',', ''))
        if match.group(2).lower() in ('billion','bn','b'):
            amount*=1000
        if amount <= 0:
            continue
        asset_distance=min((abs(match.start()-i) for i in instrument),default=100)
        action_distance=min((abs(match.start()-i) for i in action),default=100)
        btc_distance=min((abs(match.start()-i) for i in bitcoin),default=999)
        # The amount closest to STRC/preferred stock is the repurchase.
        # Penalise an amount explicitly closest to the BTC leg.
        distance=2*asset_distance+0.35*action_distance
        if btc_distance<asset_distance and btc_distance<32:
            distance+=120
        ranked.append((distance,amount))
    return min(ranked,default=(999,None))[1]


def strategy_strc_event(item: dict) -> tuple[str,str,float | None] | None:
    """Return (event type, ISO week, STRC amount in USD millions).

    Distinguishes a weekly repurchase from a buyback-authorisation increase
    and from a dividend announcement, and preserves a new event next week.
    """
    if 'Strategy' not in item.get('entities',[]):
        return None
    title=str(item.get('title') or '').lower()
    if not STRC_INSTRUMENT.search(title):
        return None
    date=normalize_date(item.get('published_at'))
    if not date:
        return None
    week=_news_week(date)
    if STRC_AUTHORIZATION.search(title):
        return ('buyback-cap',week,None)
    if STRC_BUYBACK.search(title) or STRC_SPEND.search(title):
        return ('buyback',week,_strc_transaction_amount(title))
    return None


def _compatible_strc_amount(a: float | None, b: float | None) -> bool:
    """Allow $204.9m / $205m but not $139m / $205m."""
    return a is None or b is None or abs(a-b) <= max(2.5, min(a,b)*0.025)


def event_key(item: dict) -> str:
    title = (item.get('title','') or '').lower()
    entities = set(item.get('entities') or [])
    stamp = (item.get('published_at') or '')[:7]
    amount = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:million|mn|m)\b', title)
    amount_key = ((amount.group(1) + 'm') if amount else '')
    # Treasury updates repeat frequently. A disclosed token amount and the
    # reporting week separate a new purchase from recycled media coverage.
    if 'SharpLink Gaming' in entities:
        coin=r'(?:eth|ether|ethereum)'
        token_amount=re.search(r'\b(\d[\d,.]*(?:\s*(?:million|billion|m|b))?)\s+'+coin+r'\b',title)
        if token_amount:
            action=('purchase' if re.search(r'\b(?:acquir\w*|purchas\w*|buys?|bought)\b',title)
                    else 'holdings' if re.search(r'\b(?:holdings?|holds?|held|reserve\w*)\b',title)
                    else 'staking' if re.search(r'\b(?:staking|staked|rewards?)\b',title) else '')
            if action:
                raw=re.sub(r'[,\s]','',token_amount.group(1))
                number=re.match(r'(\d+(?:\.\d+)?)(million|billion|m|b)?$',raw)
                if number:
                    multiplier={'million':1e6,'m':1e6,'billion':1e9,'b':1e9}.get(number.group(2),1)
                    quantity=format(float(number.group(1))*multiplier,'.12g')
                    return 'sbet:'+action+':'+quantity+':'+_news_week(item['published_at'])
    # These issuer-specific one-off announcements can be worded very
    # differently by different publishers; their economic event is the same.
    if 'Evernorth' in entities:
        # Distinct publisher headlines for the same shareholder approval of
        # the Armada business combination are one event (not the later closing).
        vote = bool(re.search(r'\b(?:merger|business combination|shareholder vote)\b', title))
        vote_approval = bool(re.search(
            r'\b(?:approv\w*|passes?|passed|clears?|cleared)\b', title))
        if vote and vote_approval and not re.search(
                r'\b(?:completes?|completed|closed|closing)\b', title):
            return 'evernorth:armada-business-combination-vote:2026'
        if re.search(r'\b(?:80|80\.7)\s*(?:m|million)\b', title) and any(
                x in title for x in ('facility','raise','equity','fund','cantor','committed')):
            return 'evernorth:80m-equity-facility:'+stamp
        if re.search(r'\b11\.?5\s*(?:m|million)\b',title) and re.search(
                r'\bshares?\b',title) and re.search(r'\bregister\w*|\bwarrants?\b',title):
            return 'evernorth:11.5m-share-registration:'+stamp
        if 'uphold' in title and any(x in title for x in ('xrpn','stock','shares')):
            return 'evernorth:uphold-stock-listing:'+stamp
    if 'Ripple' in entities and re.search(r'\bocc\b|\boffice of the comptroller\b',title):
        if 'bank' in title and ('final approval' in title or 'receives approval' in title):
            return 'ripple:occ-final-trust-bank-approval:'+stamp
    if 'arf' in title and 'Ripple' in entities and any(v in title for v in ('rlusd','payment','liquidity','partner','xrp ledger','xrpl','lending')):
        return 'ripple:arf-rlusd-liquidity:'+stamp
    if 'Strategy' in entities and any(v in title for v in ('acquir','purchas','buys','bitcoin holdings','btc holdings')):
        btc = re.search(r'(\d[\d,]*)\s*(?:btc|bitcoin)', title)
        if btc:
            return 'strategy:btc-purchase:'+btc.group(1).replace(',','')+':'+_news_week(item['published_at'])
    return ''


def duplicates(a: dict, b: dict) -> bool:
    if canonical_url(a.get('url','')) and canonical_url(a.get('url','')) == canonical_url(b.get('url','')):
        return True
    if a.get('source_type') == 'SEC' and b.get('source_type') == 'SEC' and a.get('accession') != b.get('accession'):
        return False
    if not set(a.get('entities',[])).intersection(b.get('entities',[])):
        return False
    da, db = normalize_date(a.get('published_at')), normalize_date(b.get('published_at'))
    if not da or not db:return False
    diff = abs((datetime.fromisoformat(da.replace('Z','+00:00'))-datetime.fromisoformat(db.replace('Z','+00:00'))).total_seconds())/86400
    sa, sb = strategy_strc_event(a), strategy_strc_event(b)
    if sa and sb:
        # Never fold two distinct weekly purchases into one story, nor
        # confuse a new $3bn buyback authorisation with a $205m purchase.
        if sa[:2] != sb[:2] or diff > 7:
            return False
        if sa[0] == 'buyback':
            return _compatible_strc_amount(sa[2],sb[2])
        return True
    ka, kb = event_key(a), event_key(b)
    if ka and kb:
        # Two different named events must not be joined by generic wording.
        return ka == kb and diff <= 12
    # The same named commercial counterparty generates several reworded headlines.
    # Restrict this shortcut to the same issuer, week and commercial topic.
    counterparties=('drivewealth','arf','cross river','meritz','settlemint','privy','zilo','licuido','bitso')
    matching=[p for p in counterparties if p in a.get('title','').lower() and p in b.get('title','').lower()]
    commercial=('Partnerships','Products','Adoption')
    if matching and diff <= 6 and a.get('category') in commercial and b.get('category') in commercial:
        return True
    if diff > 4: return False
    a_words, b_words = norm_words(a.get('title','')), norm_words(b.get('title',''))
    if not a_words or not b_words: return False
    shared = a_words & b_words
    overlap = len(shared) / min(len(a_words),len(b_words))
    similarity = SequenceMatcher(None,a.get('title','').lower(),b.get('title','').lower()).ratio()
    # Must share multiple meaningful tokens, never just Ripple/XRP or Strategy/BTC.
    return (len(shared)>=3 and overlap>=.64 and (similarity>=.38 or len(shared)>=5)) or (len(shared)>=4 and similarity>=.74)


def priority(item: dict) -> tuple:
    return (int(item.get('verified_seed',False)),{'SEC':4,'Official':3,'Media':2,'News':1}.get(item.get('source_type'),0),item.get('score',0),item.get('published_at',''))


def coverage(item: dict) -> list[dict]:
    links = item.get('coverage') if isinstance(item.get('coverage'),list) else []
    links = list(links)+[{
        'title':item.get('title',''), 'name':item.get('source','Original source'),
        'url':item.get('url',''), 'source_type':item.get('source_type','Media'),
        'published_at':item.get('published_at','')
    }]
    unique={}
    for entry in links:
        if entry.get('source_type')=='SEC' or 'sec.gov/archives/edgar' in str(entry.get('url','')).lower():
            continue
        url=canonical_url(entry.get('url',''))
        if url and url not in unique:
            unique[url]={**entry,'url':url}
    return list(unique.values())[:MAX_COVERAGE_LINKS]


def publishable(item: dict) -> bool:
    """Exclude standalone filing records from both the site and Moon Meter."""
    return (isinstance(item,dict) and item.get('category')!='SEC filings'
            and item.get('source_type')!='SEC'
            and not str(item.get('source_id','')).startswith('sec_'))


def merge_stories(old: list[dict], incoming: list[dict]) -> tuple[list[dict],int]:
    # Re-cluster old archive as well as new entries, fixing historical duplicates.
    existing_ids={x.get('id') for x in old if publishable(x)}
    candidates=[dict(x) for x in [*old,*incoming] if publishable(x) and is_recent(x.get('published_at'))]
    for item in candidates:
        previous_entities=item.get('entities') or []
        # Remove retired issuers and standalone network coverage from the archive.
        # A joint report remains visible whenever an active company is covered.
        item['entities']=[entity for entity in previous_entities if entity in TRACKED_ENTITIES]
        if item.get('source_type') in ('Media','News') and not is_investor_news(item.get('title',''),item.get('excerpt','')):
            item['rejected_as_noise']=True
        if item.get('source_type') in ('Media','News'):
            found=identify_entities((item.get('title') or '')+' '+(item.get('excerpt') or ''))
            if found: item['entities']=found
        item['tags']=[tag for tag in (item.get('tags') or []) if str(tag).strip().casefold() not in RETIRED_TAGS]
        item['why_it_matters']=investor_angle(item.get('category',''))
    candidates=[item for item in candidates if item.get('entities') and not item.get('rejected_as_noise')]
    candidates.sort(key=priority,reverse=True)
    consolidated=[]
    for item in candidates:
        item.setdefault('source_type','Media')
        if item.get('source_type')=='News': item['source_type']='Media'
        duplicate=next((target for target in consolidated if duplicates(item,target)),None)
        if duplicate is None:
            item['coverage']=coverage(item)
            consolidated.append(item)
        else:
            seen_urls={c['url'] for c in duplicate.get('coverage',[])}
            for source in coverage(item):
                if source['url'] not in seen_urls and len(duplicate['coverage']) < MAX_COVERAGE_LINKS:
                    duplicate['coverage'].append(source)
                    seen_urls.add(source['url'])
            # Keep the best primary source (SEC or issuer); preserve earlier IDs for saved stories.
            if item.get('score',0)>duplicate.get('score',0):
                duplicate['score']=item['score']
            if item.get('impact')=='High':duplicate['impact']='High'
            duplicate['entities']=sorted(set(duplicate.get('entities',[]))|set(item.get('entities',[])))
    consolidated.sort(key=lambda x:(x.get('published_at',''),x.get('score',0)),reverse=True)
    current=consolidated[:MAX_STORIES]
    # Refresh meters after entity merging, including stale assets on otherwise
    # unchanged archived stories. Removed tickers cannot survive normalisation.
    for item in current:
        item['moon_meters']=moon_for_story(item)
    added=sum(1 for x in current if x.get('id') not in existing_ids)
    return current,added


def main() -> int:
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    previous=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    stamp=timestamp_now()
    statuses={}
    incoming=[]
    sources=(
        ('ripple','Ripple press centre',fetch_ripple_press),
        ('evernorth','Evernorth official',fetch_evernorth_news),
        ('sbet','Sharplink official',fetch_sbet_news),
        ('media','Company-specific financial news',fetch_media_news),
    )
    for key,name,reader in sources:
        try:
            stories=reader()
            incoming.extend(stories)
            statuses[key]={'name':name,'status':'ok','items_seen':len(stories),'checked_at':stamp,'message':f'Fetched {len(stories)} matching items.'}
            LOG.info('%s: %s items',name,len(stories))
        except Exception as exc:
            statuses[key]={'name':name,'status':'error','items_seen':0,'checked_at':stamp,'message':str(exc)[:240]}
            LOG.warning('%s: %s',name,exc)
    ready=sum(1 for x in statuses.values() if x['status']=='ok')
    status='live' if ready==len(sources) else 'partial' if ready else 'failed'
    items,new_count=merge_stories(previous.get('items',[]),incoming)
    # Rate all visible stories, including previously collected items and clustered sources.
    for item in items:
        item['moon_meters'] = moon_for_story(item)
        # Impact is about the potential significance of the claim IF TRUE,
        # rather than whether an outlet was classified as official or media.
        # Preserve strong downside and avoid assigning High to generic hype.
        strongest=max((abs(m.get('value')) for m in item['moon_meters']
                      if type(m.get('value')) is int), default=0)
        if strongest == 3 and item.get('category') in (
                'Treasury','Capital markets','Partnerships','Regulation','Products'):
            item['impact']='High'
        elif strongest >= 2 and item.get('impact')=='Low':
            item['impact']='Medium'
    sentiment_30d = aggregate_sentiment(items, stamp)
    out={
      'name':'Signal | Strategy · Evernorth · SharpLink Gaming · Ripple', 'version':2,
      'scan':{'status':status,'ran_at':stamp,'starter_as_of':previous.get('scan',{}).get('starter_as_of'),
              'schedule_utc':['09:15','14:35','23:35'],
              'schedule_focus':['European morning announcements','US pre-market and early session','US after-market and evening'],
              'new_items':new_count,
              'source_note':'Automated scan of issuer releases and company-specific financial news; standalone filing records excluded.'},
      'sources':statuses,'sentiment_30d':sentiment_30d,'items':items,
    }
    DATA_PATH.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    LOG.info('Wrote %s stories; %s new; %s sources OK',len(items),new_count,ready)
    if status=='failed':
        # Persist the failure to the public dashboard, then fail the workflow visibly.
        return 1
    return 0

if __name__=='__main__':sys.exit(main())
