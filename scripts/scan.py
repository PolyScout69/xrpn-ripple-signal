#!/usr/bin/env python3
"""Source-first daily investor news collector. Standard library only."""
import datetime as dt, email.utils, hashlib, json, os, pathlib, re, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]; DEST=ROOT/'data/news.json'
now=dt.datetime.now(dt.timezone.utc)
stamp=now.isoformat().replace('+00:00','Z')
data=json.loads(DEST.read_text())
items={x['id']:x for x in data.get('items',[])}
headers={'User-Agent':'SignalInvestNews/1.0 (research news dashboard)','Accept':'application/json,application/xml,application/rss+xml,text/xml'}
def fetch(url,sec=False):
    h=dict(headers)
    if sec:
        agent=os.getenv('SEC_USER_AGENT','').strip()
        if '@' not in agent: raise RuntimeError('SEC_USER_AGENT with real contact email must be configured as a repository variable')
        h['User-Agent']=agent
    with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=18) as response:return response.read()
def classify(title):
    t=title.lower()
    if any(w in t for w in ['8-k','10-k','10-q','form s-','filing','sec filing','prospectus']):return 'SEC filings'
    if any(w in t for w in ['financ','equity','share sale','offering','capital','dilution']):return 'Capital markets'
    if any(w in t for w in ['treasury','yield','xrp holdings']):return 'Treasury'
    if any(w in t for w in ['partner','agreement','collaborat','integrat']):return 'Partnerships'
    if any(w in t for w in ['platform','launch','product','service','custody','rlusd']):return 'Products'
    if any(w in t for w in ['sec','regulat','legal','lawsuit']):return 'Regulation'
    return 'Adoption'
def add(title,url,date,source,type_,entities,excerpt):
    if not title or not url:return
    ident=hashlib.sha256(url.encode()).hexdigest()[:16]
    if ident in items:return
    cat=classify(title)
    high=cat in ['SEC filings','Capital markets','Treasury','Partnerships'] or bool(re.search(r'\b(acquir|merger|approval|lawsuit)\b',title,re.I))
    impact='High' if high else 'Medium'
    angle={'SEC filings':'Read original documents and watch material changes to financing, risks and share count.','Capital markets':'Assess cost of capital, dilution and financing execution.','Treasury':'Monitor treasury returns, risk controls and XRP per share.','Partnerships':'Track measurable adoption and whether announced deals generate revenue.','Products':'Monitor real product usage and commercial demand.','Regulation':'Track the legal implications for business operations.'}.get(cat,'Look for measurable adoption and business impact.')
    items[ident]=dict(id=ident,title=title,published_at=date,entities=entities,category=cat,impact=impact,score=88 if high else 65,source=source,source_type=type_,source_id=type_.lower(),url=url,excerpt=excerpt or title,why_it_matters=angle,added_at=stamp)
def report(key,fn):
    try:
        seen=fn()
        data['sources'][key]=dict(name=data['sources'][key].get('name',key),status='ok',checked_at=stamp,items_seen=seen,message='Latest scan completed')
    except Exception as exc:
        data['sources'][key]=dict(name=data['sources'][key].get('name',key),status='error',checked_at=stamp,items_seen=0,message=str(exc)[:180])
def rss():
    count=0
    terms=['Evernorth Holdings XRPN XRP','Ripple company partnership payment RLUSD','Evernorth Holdings SEC filing']
    for q in terms:
        url='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
        root=ET.fromstring(fetch(url))
        for el in root.findall('.//item')[:30]:
            title=(el.findtext('title') or '').strip(); link=(el.findtext('link') or '').strip()
            low=title.lower()
            if 'evernorth' not in low and 'ripple' not in low:continue
            if 'evernorth' in low and not any(x in low for x in ['xrpn','xrp','treasury','crypto','blockchain','digital asset']):continue
            pub=el.findtext('pubDate') or ''
            try:date=email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
            except Exception:continue
            if (now-dt.datetime.fromisoformat(date.replace('Z','+00:00'))).days>40:continue
            ent=['Evernorth'] if 'evernorth' in low else ['Ripple']
            add(title,link,date,'Google News RSS','News',ent,title)
            count+=1
    if not count:raise RuntimeError('RSS returned no relevant headlines')
    return count
def sec():
    obj=json.loads(fetch('https://data.sec.gov/submissions/CIK0002092592.json',True))
    recent=obj.get('filings',{}).get('recent',{})
    count=0
    for accession,form,date,doc in zip(recent.get('accessionNumber',[]),recent.get('form',[]),recent.get('filingDate',[]),recent.get('primaryDocument',[])):
        if form not in ['8-K','10-Q','10-K','S-1','S-3','S-4','424B3','424B5','SC 13D','SC 13G','4','3','5']:continue
        if (now.date()-dt.date.fromisoformat(date)).days>180:continue
        link='https://www.sec.gov/Archives/edgar/data/2092592/'+accession.replace('-','')+'/'+doc
        add('Evernorth SEC '+form+' filed '+date,link,date+'T12:00:00Z','SEC EDGAR','SEC',['Evernorth'],'Official '+form+' filing. Open the original document for full details.')
        count+=1
    return count
report('sec',sec)
report('media',rss)
for key in ('ripple','evernorth'):
    data['sources'][key].update(status='not_checked',checked_at=stamp,message='Official-source discovery not configured; related stories may appear through news feeds')
data['items']=sorted(items.values(),key=lambda i:i['published_at'],reverse=True)[:500]
data['scan']={'status':'ok' if any(v['status']=='ok' for v in data['sources'].values()) else 'error','ran_at':stamp,'schedule_utc':'18:00','new_items':max(0,len(items)-len(json.loads(DEST.read_text()).get('items',[]))),'source_note':'Sources with errors are identified; coverage is not exhaustive.'}
DEST.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print('Stories:',len(data['items']),'Source statuses:',{k:v['status'] for k,v in data['sources'].items()})
if not any(v['status']=='ok' for v in data['sources'].values()):raise SystemExit('All configured news scans failed')
