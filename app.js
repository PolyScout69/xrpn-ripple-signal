/* Signal: browser-only dashboard. Scheduled data collection lives in scripts/scan.py. */
(() => {
  'use strict';
  const DATA_URL = './data/news.json';
  const STORAGE_SAVED = 'signal.saved.v1';
  const STORAGE_READ = 'signal.read.v1';
  const MOON_TICKS = [-3,-2,-1,0,1,2,3];
  // Keep in sync with .github/workflows/daily-scan.yml and scripts/scan.py.
  // European morning, US morning and US after-hours news cycles (UTC).
  const SCAN_TIMES_UTC = [{hour:9,minute:15},{hour:14,minute:35},{hour:23,minute:35}];
  const MOON_ASSETS = {Ripple:'XRP', 'XRP Ecosystem':'XRP', Evernorth:'XRPN', Strategy:'MSTR'};
  const DEFAULT_SOURCES = ['evernorth', 'ripple', 'media'];
  const state = { data: null, view: 'overview', entity: 'All', impact: 'All', moon: 'All', category: 'All', days: 30, sort: 'latest', query: '', saved: loadSet(STORAGE_SAVED), read: loadSet(STORAGE_READ), filtered: [] };
  let toastTimer;

  const $ = id => document.getElementById(id);
  const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl = url => { try { const u = new URL(url); return u.protocol === 'https:' ? u.href : '#'; } catch { return '#'; } };
  const time = value => { const d = new Date(value); return Number.isFinite(+d) ? +d : 0; };
  const ageDays = item => (Date.now() - time(item.published_at)) / 86400000;
  const recent = (item, days) => ageDays(item) >= -1 && ageDays(item) <= days;
  const fmtDate = (value, opts = {day:'numeric',month:'short',year:'numeric'}) => {
    if (!time(value)) return 'Unknown date';
    return new Intl.DateTimeFormat('en-GB', {timeZone:'UTC',...opts}).format(new Date(value));
  };
  const fmtNum = n => new Intl.NumberFormat('en-GB').format(n);
  function loadSet(key) { try { const a = JSON.parse(localStorage.getItem(key) || '[]'); return new Set(Array.isArray(a) ? a : []); } catch { return new Set(); } }
  function storeSet(key, values) { try { localStorage.setItem(key, JSON.stringify([...values])); } catch { /* private mode */ } }
  function notify(message) { const el=$('toast'); el.textContent=message; el.classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.classList.remove('show'),2600); }

  function impactPill(impact) { const v=['High','Medium','Low'].includes(impact) ? impact : 'Low'; return `<span class="impact-badge ${v}">${v.toUpperCase()} IMPACT</span>`; }
  function saveButton(item) { const saved=state.saved.has(item.id); return `<button type="button" class="save-button ${saved?'saved':''}" data-save="${esc(item.id)}" aria-label="${saved?'Remove saved story':'Save story'}" title="${saved?'Remove saved story':'Save story'}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4V4.5Z"/></svg></button>`; }
  function entityLabel(item) {
    const names=(item.entities||[]);
    if (!names.length) return `<span class="entity-label">OTHER</span>`;
    return names.map(name=>`<span class="entity-label ${name==='Ripple'?'ripple':name==='XRP Ecosystem'?'ecosystem':name==='Strategy'?'strategy':''}">${esc(name.toUpperCase())}</span>`).join('<span class="tag-slash">/</span>');
  }
  function coverageHTML(item) {
    const links=(item.coverage||[]).filter(link=>link && link.url && safeUrl(link.url)!=='#' && link.url!==item.url).slice(0,12);
    if (!links.length) return '';
    return `<details class="coverage-details"><summary>${links.length} more ${links.length===1?'source':'sources'} covering this event</summary><div class="coverage-links">${links.map(link=>`<a href="${esc(safeUrl(link.url))}" target="_blank" rel="noopener noreferrer">${esc(link.name || 'Other source')} <span>↗</span></a>`).join('')}</div></details>`;
  }
  function dateLine(item) { return fmtDate(item.published_at,{day:'numeric',month:'short',year:'numeric'}).toUpperCase(); }

  function visibleMoonSignals(item) {
    const signals = Array.isArray(item.moon_meters) ? item.moon_meters : [];
    const asset = MOON_ASSETS[state.entity];
    return asset ? signals.filter(m => m.asset === asset) : signals;
  }
  function moonValue(item) {
    const signals = visibleMoonSignals(item);
    return signals.length && Number.isInteger(signals[0].value) && signals[0].value >= -3 && signals[0].value <= 3 ? signals[0].value : null;
  }
  function moonHTML(item) {
    const signals=visibleMoonSignals(item);
    if (!signals.length) return '<div class="moon-awaiting">Moon Meter awaiting next scan</div>';
    return '<div class="moon-meters">'+signals.map(m=>{
      const rated=typeof m.value==='number' && Number.isInteger(m.value) && m.value>=-3 && m.value<=3;
      const value=rated?m.value:null, direction=!rated?'unrated':value>0?'positive':value<0?'negative':'neutral';
      const display=!rated?'—':value>0?'+'+value:String(value);
      const label=m.label||(!rated?'Not rated':value>0?'Bullish':value<0?'Bearish':'Neutral');
      const segments=MOON_TICKS.map(tick=>{
        const sign=tick<0?'negative':tick>0?'positive':'neutral';
        return '<span class="moon-step '+sign+(tick===value?' is-selected':'')+'" aria-hidden="true"><span class="moon-bar"></span><span class="moon-tick">'+(tick>0?'+':'')+tick+'</span></span>';
      }).join('');
      const accessible=rated? 'role="meter" aria-valuemin="-3" aria-valuemax="3" aria-valuenow="'+value+'" aria-valuetext="'+esc(label)+'"': 'role="group" aria-label="Not rated because source evidence is insufficient"';
      const source=m.confidence==='Insufficient'?'Insufficient detail':m.confidence==='Unverified'?'UNVERIFIED CLAIM':m.confidence==='Conditional'?'Forward-looking assumption':m.confidence==='High'?'Primary-source headline':'Secondary news report';
      const scenario=m.scenario==='rumour'?'RUMOUR · IF TRUE':m.scenario==='assumption'?'ASSUMED TRUE':'IF TRUE';
      return '<div class="moon-meter '+direction+'"><div class="moon-header"><div class="moon-heading"><span class="moon-orbit" aria-hidden="true">◕</span><span class="moon-name">MOON METER</span><span class="moon-asset">'+esc(m.asset)+'</span><span class="moon-scenario '+esc(m.scenario||'reported')+'">'+esc(scenario)+'</span></div><div class="moon-readout"><strong>'+display+'</strong><span>'+esc(label)+'</span></div></div><div class="moon-scale" '+accessible+' aria-label="Moon Meter for '+esc(m.asset)+'">'+segments+'</div><p class="moon-explanation">'+esc(m.reason||'Verify the original source.')+'</p><div class="moon-evidence">'+esc(source)+' · Impact IF TRUE, not likelihood or a price forecast</div></div>';
    }).join('')+'</div>';
  }

  function featureHTML(item) {
    return `<article class="featured" aria-label="Lead investor story">
      <div class="feature-tagline"><span class="feature-icon"></span> TOP INVESTOR SIGNAL <span class="feature-faint">/</span> ${esc(item.category.toUpperCase())} ${impactPill(item.impact)}</div>
      <h3 class="featured-title">${esc(item.title)}</h3>
      <p class="featured-excerpt">${esc(item.excerpt)}</p>
      <div class="investor-angle"><strong>WHY INVESTORS SHOULD CARE</strong>${esc(item.why_it_matters)}</div>
      ${moonHTML(item)}
      <div class="feature-bottom"><div class="feature-source"><span class="feature-authority">${item.source_type==='Official'?'OFFICIAL SOURCE':'FINANCIAL NEWS'}</span><span>${esc(item.source)} · ${esc(dateLine(item))}</span></div><div class="feature-actions">${saveButton(item)}<a class="feature-open" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">Read original source <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></a></div></div>${coverageHTML(item)}
    </article>`;
  }
  function storyHTML(item) {
    return `<article class="story-card ${state.read.has(item.id)?'is-read':''}" data-story="${esc(item.id)}">
      <div class="story-top"><div class="story-tags">${entityLabel(item)}<span class="tag-slash">/</span><span class="category-label">${esc((item.category||'News').toUpperCase())}</span></div><span class="story-date">${esc(dateLine(item))}</span></div>
      <h3 class="story-title">${esc(item.title)}</h3><p class="story-desc">${esc(item.excerpt)}</p>
      <div class="story-why"><strong>INVESTOR ANGLE</strong> ${esc(item.why_it_matters)}</div>
      ${moonHTML(item)}
      <div class="story-bottom"><div class="story-source"><span class="source-dot ${esc((item.source_type||'').toLowerCase())}"></span>${esc(item.source)} ${impactPill(item.impact)}</div><div class="story-actions"><button class="read-button" data-read="${esc(item.id)}" type="button" title="${state.read.has(item.id)?'Mark unread':'Mark read'}" aria-label="${state.read.has(item.id)?'Mark unread':'Mark read'}">${state.read.has(item.id)?'Unread':'Mark read'}</button>${saveButton(item)}<a class="story-open" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer" aria-label="Read original source: ${esc(item.title)}">Source <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></a></div></div>${coverageHTML(item)}
    </article>`;
  }
  function matches(item) {
    if (!item || !Array.isArray(item.entities)) return false;
    if (item.category==='SEC filings'||item.source_type==='SEC'||String(item.source_id||'').startsWith('sec_')) return false;
    if (state.entity !== 'All' && !item.entities.includes(state.entity)) return false;
    if (state.category !== 'All' && item.category !== state.category) return false;
    if (state.impact !== 'All' && item.impact !== state.impact) return false;
    const mv = moonValue(item);
    if (state.moon === 'bullish' && !(mv > 0)) return false;
    if (state.moon === 'bearish' && !(mv < 0)) return false;
    if (state.moon === 'neutral' && mv !== 0) return false;
    if (state.moon === 'unrated' && mv !== null) return false;
    if (!recent(item,state.days)) return false;
    if (state.view === 'high' && item.impact !== 'High') return false;
    if (state.view === 'partnerships' && item.category !== 'Partnerships') return false;
    if (state.view === 'saved' && !state.saved.has(item.id)) return false;
    if (state.query.trim()) {
      const blob=[item.title,item.excerpt,item.why_it_matters,item.source,item.category,...item.entities,...(item.tags||[])].join(' ').toLowerCase();
      if (!blob.includes(state.query.trim().toLowerCase())) return false;
    }
    return true;
  }
  const VIEWS = {overview:'Latest developments',high:'High-impact developments',partnerships:'Partnership tracker',saved:'Saved stories'};
  function chooseFeature(items) {
    if (state.view !== 'overview' || !items.length) return null;
    // Feature score balances materiality and news freshness; the rest remain chronological.
    return [...items].sort((a,b)=>(b.score||0)-(a.score||0) || time(b.published_at)-time(a.published_at))[0];
  }
  function renderFeed() {
    if (!state.data) return;
    const match=state.data.items.filter(matches);
    match.sort((a,b)=>state.sort==='moon-bullish'?(moonValue(b)??-4)-(moonValue(a)??-4)||time(b.published_at)-time(a.published_at):state.sort==='moon-bearish'?(moonValue(a)??4)-(moonValue(b)??4)||time(b.published_at)-time(a.published_at):state.sort==='impact'?(b.score||0)-(a.score||0)||time(b.published_at)-time(a.published_at):state.sort==='oldest'?time(a.published_at)-time(b.published_at):time(b.published_at)-time(a.published_at));
    state.filtered=match;
    const feature=chooseFeature(match);
    const rest=feature?match.filter(x=>x.id!==feature.id):match;
    $('featured-container').innerHTML=feature?featureHTML(feature):'';
    $('feed-list').innerHTML=rest.map(storyHTML).join('');
    $('no-results').hidden=match.length>0;
    $('feed-foot').textContent=match.length?`Showing ${fmtNum(match.length)} sourced ${match.length===1?'development':'developments'} · Select “Source” to read the original`:'';
    $('feed-heading').firstChild.textContent=VIEWS[state.view]+' ';
    $('feed-total').textContent=fmtNum(match.length);
    $('crumb-view').textContent=state.view==='overview'?'OVERVIEW':VIEWS[state.view].toUpperCase();
    document.querySelectorAll('[data-view]').forEach(btn=>{const active=btn.dataset.view===state.view;btn.classList.toggle('is-active',active);btn.setAttribute('aria-current',active?'page':'false');});
    document.querySelectorAll('[data-entity]').forEach(btn=>btn.classList.toggle('selected',btn.dataset.entity===state.entity));
    $('saved-nav-count').textContent=state.saved.size;
    $('high-nav-count').textContent=state.data.items.filter(x=>x.impact==='High'&&recent(x,30)).length;
    $('category-select').value=state.category;
    $('impact-select').value=state.impact;
    $('moon-select').value=state.moon;
    $('period-select').value=String(state.days);
    $('sort-select').value=state.sort;
  }
  // Browser fallback for pre-upgrade snapshots or delayed CI scans. Uses the
  // same weighted event principles as scripts/sentiment.py; server data wins.
  function provisionalSentiment(asset) {
    const end=time(state.data?.scan?.ran_at) || Date.now();
    const ms=86400000;
    const iw={High:4.5,Medium:2.25,Low:1};
    const sw={Official:1.15,SEC:1.15,Media:1,News:1};
    const qw={reported:1,assumption:0.90,rumour:0.72};
    const events=new Map();
    const families=[
      ['equity',/equity (?:purchase )?facility|cantor.*facility/],
      ['warrants',/11\.?5\s*m(?:illion)?.*shares|register.*shares.*warrant/],
      ['vote',/(?:shareholder|merger) (?:vote|approval)|shareholders? approve/],
      ['merger',/complet.*(?:business combination|merger)/],
      ['yield',/(?:xrp.*(?:yield|lending)|(?:yield|lending).*xrp|(?:treasury|xrp).*(?:coinbase|kraken|bitgo))/],
      ['pershare',/(?:xrp|bitcoin|btc) per (?:fully diluted |diluted )?share/],
      ['listing',/(?:nasdaq|go(?:es|ing)? public).*(?:debut|list|begins trading)/],
      ['uphold',/uphold.*(?:list|stock|access)/],
      ['drawdown',/(?:treasury|xrp|bitcoin|btc).*(?:loss|loses?|lost|drop|down)/],
      ['preferred',/(?:repurchas|redeem|buyback).*(?:preferred|strc|strk|strf)|(?:preferred|strc|strk|strf).*(?:repurchas|redeem|buyback)/],
      ['btc',/(?:acquir|buys?|purchas).*(?:bitcoin|btc)/]
    ];
    const weekCode=(stamp)=>{
      const d=new Date(stamp);
      d.setUTCHours(0,0,0,0);
      d.setUTCDate(d.getUTCDate()+4-(d.getUTCDay()||7));
      const y=d.getUTCFullYear(), start=Date.UTC(y,0,1);
      return y+'W'+Math.ceil(((+d-start)/ms+1)/7);
    };
    let total=0;
    for(const story of (state.data?.items || [])) {
      const date=time(story.published_at), age=(end-date)/ms;
      if(!date || age<0 || age>30 || story.source_type==='SEC' || story.category==='SEC filings')continue;
      const meter=(story.moon_meters||[]).find(m=>m.asset===asset);
      if(!meter || !Number.isInteger(meter.value) || meter.value < -3 || meter.value > 3)continue;
      total++;
      const strength=Math.abs(meter.value), impact=iw[story.impact]||1;
      const weight=impact*(sw[story.source_type]||1)*(qw[meter.scenario]||1)*
        Math.exp(-Math.LN2*age/17)*Math.max(.9,Math.min(1.12,1+((Number(story.score)||70)-75)/250))*
        (1+.2*Math.max(0,strength-1));
      const headline=String(story.title||'').toLowerCase();
      const family=families.find(([name,exp])=>exp.test(headline));
      const key=family?asset+':'+family[0]+':'+weekCode(date)+':'+Math.sign(meter.value):
        asset+':story:'+(story.id||story.url||story.title);
      const candidate={id:story.id,title:story.title,url:story.url,value:meter.value,weight,
        impact:story.impact,scenario:meter.scenario||'reported',published_at:story.published_at,
        reason:meter.reason};
      const prior=events.get(key);
      if(!prior || strength>Math.abs(prior.value) ||
          (strength===Math.abs(prior.value) && weight>prior.weight))events.set(key,candidate);
    }
    const entries=[...events.values()],directional=entries.filter(x=>x.value!==0),
      neutral=entries.filter(x=>x.value===0);
    const numerator=directional.reduce((sum,x)=>sum+x.value*x.weight,0);
    const denominator=directional.reduce((sum,x)=>sum+x.weight,0)+.08*
      neutral.reduce((sum,x)=>sum+x.weight,0);
    const raw=denominator?numerator/denominator:0;
    const mag=Math.abs(raw), step=mag<.35?0:mag>=2.3&&directional.length>=2?3:mag>=1.35?2:1;
    const value=raw<0?-step:step;
    const labels={'-3':'Very bearish','-2':'Bearish','-1':'Slightly bearish',
      '0':'Neutral','1':'Slightly bullish','2':'Bullish','3':'Very bullish'};
    const coverage=directional.length<3?'Limited coverage':
      directional.length<7?'Moderate coverage':'Broad coverage';
    return {value,label:labels[String(value)],raw_score:Math.round(raw*100)/100,
      stories:total,independent_events:entries.length,directional_events:directional.length,
      distinct_catalysts:directional.length,neutral_events:neutral.length,coverage,provisional:true,
      drivers:directional.sort((a,b)=>Math.abs(b.value*b.weight)-Math.abs(a.value*a.weight)).slice(0,4)};
  }

  function renderSentiment(asset) {
    const id=asset.toLowerCase();
    const item=state.data?.sentiment_30d?.[asset] || provisionalSentiment(asset);
    const card=$('sentiment-card-'+id);
    const valueEl=$('sentiment-'+id+'-value');
    const labelEl=$('sentiment-'+id+'-label');
    const scale=$('sentiment-'+id+'-scale');
    const line=$('sentiment-'+id+'-subline');
    const detail=$('sentiment-'+id+'-details');
    if(!item || !Number.isInteger(item.value) || item.value < -3 || item.value > 3) {
      valueEl.textContent='—';
      labelEl.textContent='Awaiting scan';
      line.textContent='Sentiment calculated during the next news scan';
      scale.innerHTML='';
      detail.textContent='Once scanned, this card will show a weighted 30-day summary of relevant stories.';
      return;
    }
    const value=item.value;
    const tone=value>0?'positive':value<0?'negative':'neutral';
    card.classList.remove('sentiment-positive','sentiment-negative','sentiment-neutral');
    card.classList.add('sentiment-'+tone);
    valueEl.textContent=value>0?'+'+value:String(value);
    labelEl.textContent=item.label || (value>0?'Bullish':value<0?'Bearish':'Neutral');
    scale.setAttribute('role','meter');
    scale.setAttribute('aria-valuemin','-3');
    scale.setAttribute('aria-valuemax','3');
    scale.setAttribute('aria-valuenow',String(value));
    scale.setAttribute('aria-valuetext',labelEl.textContent);
    scale.innerHTML=MOON_TICKS.map(tick=>'<span class="sentiment-step '+(tick<0?'negative':tick>0?'positive':'neutral')+(tick===value?' is-selected':'')+'"><span class="sentiment-bar"></span><span class="sentiment-tick">'+(tick>0?'+'+tick:tick)+'</span></span>').join('');
    const all=Number(item.stories)||0;
    const directional=Number(item.directional_events)||0;
    const coverage=item.coverage||'Coverage unknown';
    line.innerHTML=(item.provisional?'<span class="sentiment-provisional">Provisional · awaiting recalculated scan</span>':'')+'<strong>'+directional+'</strong> directional '+(directional===1?'event':'events')+' · '+all+' '+(all===1?'story':'stories')+' <span class="sentiment-coverage '+(coverage==='Limited coverage'?'limited':'')+'">'+esc(coverage)+'</span>';
    const raw=Number(item.raw_score);
    const rawText=Number.isFinite(raw)?(raw>0?'+':'')+raw.toFixed(2):'—';
    const stats='<div class="sentiment-detail-stats">Weighted index <strong>'+esc(rawText)+'</strong> / 3 · '+Number(item.independent_events||0) +' distinct events · '+Number(item.distinct_catalysts||0)+' catalyst themes · '+Number(item.neutral_events||0)+' neutral events</div>';
    const drivers=Array.isArray(item.drivers)?item.drivers.slice(0,4):[];
    const driverList=drivers.length?'<ol class="sentiment-driver-list">'+drivers.map(d=>{
      const dv=Number(d.value)||0;
      const url=safeUrl(d.url);
      const title=esc(d.title||'Investor news');
      const label='<span class="sentiment-driver-score '+(dv>0?'positive':'negative')+'">'+(dv>0?'+'+dv:dv)+'</span>';
      const link=url!=='#'?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+title+'</a>':title;
      return '<li>'+label+'<span>'+link+'<small>'+esc(d.impact||'')+' impact · '+esc(d.scenario||'reported')+'</small></span></li>';
    }).join('')+'</ol>':'<p>No directional catalysts in the selected period.</p>';
    detail.innerHTML=stats+driverList+'<p class="sentiment-disclaimer">Impact-weighted, recency-adjusted, deduplicated IF-TRUE scenarios. A score is not a price forecast or evidence a rumour is true. See methodology for details.</p>';
  }
  function renderStats() {
    const items=state.data.items;
    $('stat-new').textContent=fmtNum(items.filter(i=>recent(i,1)).length);
    $('stat-high').textContent=fmtNum(items.filter(i=>i.impact==='High'&&recent(i,7)).length);
    renderSentiment('XRPN');
    renderSentiment('MSTR');
    $('chart-total').textContent=fmtNum(items.filter(i=>recent(i,30)).length);
    renderChart(items);
  }
  function renderChart(items) {
    const today=new Date(), end=Date.UTC(today.getUTCFullYear(),today.getUTCMonth(),today.getUTCDate()+1);
    const counts=Array.from({length:15},(_,idx)=>items.filter(i=>{const t=time(i.published_at);const age=(end-t)/86400000;return age>=2*idx&&age<2*(idx+1);}).length).reverse();
    const max=Math.max(1,...counts);
    $('bar-chart').innerHTML=counts.map((v,i)=>`<div class="bar-wrap" title="${v} ${v===1?'story':'stories'} in two-day period"><div class="bar ${i>=12?'highlight':''}" style="height:${Math.max(3,v/max*100)}%"></div></div>`).join('');
    $('bar-chart').setAttribute('aria-label',`News published in the last 30 days, per two-day interval: ${counts.join(', ')}`);
  }
  function nextScanUTC() {
    const now=new Date();
    const y=now.getUTCFullYear(), m=now.getUTCMonth(), day=now.getUTCDate();
    const slots=SCAN_TIMES_UTC.map(slot=>new Date(Date.UTC(y,m,day,slot.hour,slot.minute)));
    const next=slots.find(slot=>slot>now) || new Date(Date.UTC(y,m,day+1,SCAN_TIMES_UTC[0].hour,SCAN_TIMES_UTC[0].minute));
    return `Next scheduled ~${new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'UTC',hourCycle:'h23'}).format(next)} UTC`;
  }
  function renderSources() {
    const src=state.data.sources||{};
    $('source-list').innerHTML=DEFAULT_SOURCES.map(id=>{const x=src[id]||{};const s=x.status||'pending';const label={ok:'Checked',degraded:'Partial',error:'Error',needs_setup:'Setup needed',pending:'Pending'}[s]||s;
      return `<div class="source-item" title="${esc(x.message||'')}" ><span class="source-status-indicator ${esc(s)}"></span><span class="source-item-name">${esc(x.name||id)}</span><span class="source-item-status">${esc(label)}</span></div>`;}).join('');
    const num=DEFAULT_SOURCES.filter(id=>src[id]?.status==='ok').length;
    const mode=state.data.scan?.status||'starter';
    $('health-legend').textContent=mode==='starter'?'NOT STARTED':`${num} / ${DEFAULT_SOURCES.length} CHECKED`;
    $('source-note').textContent=mode==='starter'?'A hand-verified snapshot is included. Three daily scans refresh the source feed.':num===DEFAULT_SOURCES.length?'All monitored sources checked at the last run; reporting may be delayed.':'Some monitoring sources were unavailable at the last run; published items may be delayed.';
    const pulse=$('sidebar-pulse');pulse.className='signal-pulse';
    if(mode==='starter')pulse.classList.add('pending');else if(mode==='failed')pulse.classList.add('error');
    $('sidebar-status-title').textContent=mode==='starter'?'Starter edition':mode==='live'||mode==='ok'?'Automated monitoring':mode==='partial'?'Partial coverage':'Source errors';
    $('sidebar-status-desc').textContent=mode==='starter'?'Automatic scans not yet run':mode==='failed'?'Latest scan failed':`3 daily scans · 09:15, 14:35 & 23:35 UTC`;
  }
  function renderScan() {
    const scan=state.data.scan||{};
    if(scan.status==='starter') { $('scan-label').textContent='Curated starter edition';$('scan-description').textContent='Verified 26 Oct 2026 · automated scans start on deployment'; }
    else if(scan.status==='failed'||scan.status==='error') { $('scan-label').textContent='Scan failed';$('scan-description').textContent='Last attempt '+fmtDate(scan.ran_at,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' UTC · check source health'; }
    else { $('scan-label').textContent=scan.status==='partial'?'Partially updated':'Monitoring active';$('scan-description').textContent=`Last scan ${fmtDate(scan.ran_at,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})} UTC · ${nextScanUTC()}`; }
    $('scan-icon').classList.toggle('failed',scan.status==='failed'||scan.status==='error');
  }
  function renderAll() { renderStats();renderScan();renderSources();renderFeed(); }
  async function fetchData(showFeedback=false) {
    const button=$('refresh-btn'); button.classList.add('is-loading');button.disabled=true;
    try {
      const response=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json();
      if(!Array.isArray(data.items)||!data.scan)throw new Error('Invalid data format');
      const previous=state.data?.scan?.ran_at;
      // Drop legacy filing items and links from previously cached snapshots.
      data.items=data.items.filter(x=>x.category!=='SEC filings'&&x.source_type!=='SEC'&&!String(x.source_id||'').startsWith('sec_'));
      data.items.forEach(x=>{if(Array.isArray(x.coverage))x.coverage=x.coverage.filter(c=>c.source_type!=='SEC'&&!/sec\.gov\/Archives\/edgar/i.test(c.url||''));});
      state.data=data;renderAll();
      if(showFeedback)notify(previous!==data.scan.ran_at?'Latest published snapshot loaded':'Already showing the latest published snapshot');
    } catch(error) {
      console.error('Could not load news.json:',error);
      if(!state.data){ $('scan-label').textContent='News file unavailable';$('scan-description').textContent='Serve this folder over HTTP (see README).';$('no-results').hidden=false; }
      notify('Could not load news snapshot. Please check your connection.');
    } finally {button.classList.remove('is-loading');button.disabled=false;}
  }
  function setView(view) {
    if(!VIEWS[view])return;
    state.view=view;
    if(view==='partnerships'){state.category='All';}
    state.days=view==='saved'?3650:30;
    state.entity='All';state.query='';$('search-input').value='';
    renderFeed();
    if(window.matchMedia('(max-width:820px)').matches) document.querySelector('.section-heading')?.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function clearFilters() {
    state.view='overview';state.entity='All';state.impact='All';state.moon='All';state.category='All';state.days=30;state.sort='latest';state.query='';$('search-input').value='';renderFeed();
  }
  function csvCell(value) {let text=String(value??''); if(/^[\s]*[=+\-@]/.test(text)) text="'"+text; return `"${text.replace(/"/g,'""')}"`;}
  function exportCSV() {
    if(!state.filtered.length){notify('No stories in the current view');return;}
    const fields=['Date','Entity','Topic','Impact','Moon asset','Moon score','Moon evidence','Moon scenario','Moon rationale','Headline','Source','Summary','Investor angle','Original URL'];
    const rows=state.filtered.map(i=>{const meters=visibleMoonSignals(i);return [dateLine(i),(i.entities||[]).join(' / '),i.category,i.impact,meters.map(m=>m.asset).join(' | '),meters.map(m=>m.value===null?'Not rated':m.value>0?'+'+m.value:m.value).join(' | '),meters.map(m=>m.confidence||'').join(' | '),meters.map(m=>m.scenario||'reported').join(' | '),meters.map(m=>m.reason).join(' | '),i.title,i.source,i.excerpt,i.why_it_matters,i.url].map(csvCell).join(',')});
    const contents='\ufeff'+[fields.map(csvCell).join(','),...rows].join('\r\n');
    const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([contents],{type:'text/csv;charset=utf-8;'}));link.download=`signal-investor-news-${new Date().toISOString().slice(0,10)}.csv`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);notify('CSV export prepared');
  }
  document.addEventListener('click', e => {
    const nav=e.target.closest('[data-view]');if(nav){setView(nav.dataset.view);return;}
    const ent=e.target.closest('[data-entity]');if(ent){state.entity=ent.dataset.entity;renderFeed();return;}
    const save=e.target.closest('[data-save]');if(save){const id=save.dataset.save;state.saved.has(id)?state.saved.delete(id):state.saved.add(id);storeSet(STORAGE_SAVED,state.saved);renderFeed();notify(state.saved.has(id)?'Story saved locally':'Story removed from saved');return;}
    const read=e.target.closest('[data-read]');if(read){const id=read.dataset.read;state.read.has(id)?state.read.delete(id):state.read.add(id);storeSet(STORAGE_READ,state.read);renderFeed();return;}
  });
  $('search-input').addEventListener('input',e=>{state.query=e.target.value;renderFeed();});
  $('category-select').addEventListener('change',e=>{state.category=e.target.value;renderFeed();});
  $('impact-select').addEventListener('change',e=>{state.impact=e.target.value;renderFeed();});
  $('moon-select').addEventListener('change',e=>{state.moon=e.target.value;renderFeed();});
  $('period-select').addEventListener('change',e=>{state.days=Number(e.target.value);renderFeed();});
  $('sort-select').addEventListener('change',e=>{state.sort=e.target.value;renderFeed();});
  $('clear-filters').addEventListener('click',clearFilters);
  $('export-button').addEventListener('click',exportCSV);
  $('refresh-btn').addEventListener('click',()=>fetchData(true));
  const method=$('method-dialog');$('method-btn').addEventListener('click',()=>method.showModal());$('about-btn').addEventListener('click',()=>method.showModal());$('dialog-close').addEventListener('click',()=>method.close());
  method.addEventListener('click',e=>{if(e.target===method)method.close();});
  $('header-date').textContent=fmtDate(new Date().toISOString(),{weekday:'short',day:'numeric',month:'short',year:'numeric'}).toUpperCase();
  $('footer-year').textContent=new Date().getFullYear();
  fetchData();
})();
