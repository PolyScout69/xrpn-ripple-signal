/* Signal: browser-only dashboard. Scheduled data collection lives in scripts/scan.py. */
(() => {
  'use strict';
  const DATA_URL = './data/news.json';
  const STORAGE_SAVED = 'signal.saved.v1';
  const STORAGE_READ = 'signal.read.v1';
  const DEFAULT_SOURCES = ['sec_evernorth', 'sec_strategy', 'evernorth', 'ripple', 'media'];
  const state = { data: null, view: 'overview', entity: 'All', impact: 'All', category: 'All', days: 30, sort: 'latest', query: '', saved: loadSet(STORAGE_SAVED), read: loadSet(STORAGE_READ), filtered: [] };
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

  function featureHTML(item) {
    return `<article class="featured" aria-label="Lead investor story">
      <div class="feature-tagline"><span class="feature-icon"></span> TOP INVESTOR SIGNAL <span class="feature-faint">/</span> ${esc(item.category.toUpperCase())} ${impactPill(item.impact)}</div>
      <h3 class="featured-title">${esc(item.title)}</h3>
      <p class="featured-excerpt">${esc(item.excerpt)}</p>
      <div class="investor-angle"><strong>WHY INVESTORS SHOULD CARE</strong>${esc(item.why_it_matters)}</div>
      <div class="feature-bottom"><div class="feature-source"><span class="feature-authority">${item.source_type==='SEC'?'PRIMARY FILING':item.source_type==='Official'?'OFFICIAL SOURCE':'FINANCIAL NEWS'}</span><span>${esc(item.source)} · ${esc(dateLine(item))}</span></div><div class="feature-actions">${saveButton(item)}<a class="feature-open" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">Read original source <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></a></div></div>${coverageHTML(item)}
    </article>`;
  }
  function storyHTML(item) {
    return `<article class="story-card ${state.read.has(item.id)?'is-read':''}" data-story="${esc(item.id)}">
      <div class="story-top"><div class="story-tags">${entityLabel(item)}<span class="tag-slash">/</span><span class="category-label">${esc((item.category||'News').toUpperCase())}</span></div><span class="story-date">${esc(dateLine(item))}</span></div>
      <h3 class="story-title">${esc(item.title)}</h3><p class="story-desc">${esc(item.excerpt)}</p>
      <div class="story-why"><strong>INVESTOR ANGLE</strong> ${esc(item.why_it_matters)}</div>
      <div class="story-bottom"><div class="story-source"><span class="source-dot ${esc((item.source_type||'').toLowerCase())}"></span>${esc(item.source)} ${impactPill(item.impact)}</div><div class="story-actions"><button class="read-button" data-read="${esc(item.id)}" type="button" title="${state.read.has(item.id)?'Mark unread':'Mark read'}" aria-label="${state.read.has(item.id)?'Mark unread':'Mark read'}">${state.read.has(item.id)?'Unread':'Mark read'}</button>${saveButton(item)}<a class="story-open" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer" aria-label="Read original source: ${esc(item.title)}">Source <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></a></div></div>${coverageHTML(item)}
    </article>`;
  }
  function matches(item) {
    if (!item || !Array.isArray(item.entities)) return false;
    if (state.entity !== 'All' && !item.entities.includes(state.entity)) return false;
    if (state.category !== 'All' && item.category !== state.category) return false;
    if (state.impact !== 'All' && item.impact !== state.impact) return false;
    if (!recent(item,state.days)) return false;
    if (state.view === 'high' && item.impact !== 'High') return false;
    if (state.view === 'sec' && item.category !== 'SEC filings') return false;
    if (state.view === 'partnerships' && item.category !== 'Partnerships') return false;
    if (state.view === 'saved' && !state.saved.has(item.id)) return false;
    if (state.query.trim()) {
      const blob=[item.title,item.excerpt,item.why_it_matters,item.source,item.category,...item.entities,...(item.tags||[])].join(' ').toLowerCase();
      if (!blob.includes(state.query.trim().toLowerCase())) return false;
    }
    return true;
  }
  const VIEWS = {overview:'Latest developments',high:'High-impact developments',sec:'SEC filing monitor',partnerships:'Partnership tracker',saved:'Saved stories'};
  function chooseFeature(items) {
    if (state.view !== 'overview' || !items.length) return null;
    // Feature score balances materiality and news freshness; the rest remain chronological.
    return [...items].sort((a,b)=>(b.score||0)-(a.score||0) || time(b.published_at)-time(a.published_at))[0];
  }
  function renderFeed() {
    if (!state.data) return;
    const match=state.data.items.filter(matches);
    match.sort((a,b)=>state.sort==='impact'?(b.score||0)-(a.score||0)||time(b.published_at)-time(a.published_at):state.sort==='oldest'?time(a.published_at)-time(b.published_at):time(b.published_at)-time(a.published_at));
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
    $('period-select').value=String(state.days);
    $('sort-select').value=state.sort;
  }
  function renderStats() {
    const items=state.data.items;
    $('stat-new').textContent=fmtNum(items.filter(i=>recent(i,1)).length);
    $('stat-high').textContent=fmtNum(items.filter(i=>i.impact==='High'&&recent(i,7)).length);
    $('stat-sec').textContent=fmtNum(items.filter(i=>i.category==='SEC filings'&&recent(i,30)).length);
    const sources=Object.keys(state.data.sources||{});
    const ok=sources.filter(k=>state.data.sources?.[k]?.status==='ok').length;
    $('stat-health').textContent=`${ok}/${sources.length}`;
    $('stat-health-sub').textContent=ok===sources.length?'All monitoring sources checked':ok===0?'Sources need attention':`${sources.length-ok} channels need attention`;
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
    const now=new Date(); let next=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),18));
    if (+next<=+now) next=new Date(+next+86400000);
    return `Next scheduled ~${new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'UTC',hourCycle:'h23'}).format(next)} UTC`;
  }
  function renderSources() {
    const src=state.data.sources||{};
    $('source-list').innerHTML=DEFAULT_SOURCES.map(id=>{const x=src[id]||{};const s=x.status||'pending';const label={ok:'Checked',degraded:'Partial',error:'Error',needs_setup:'Setup needed',pending:'Pending'}[s]||s;
      return `<div class="source-item" title="${esc(x.message||'')}" ><span class="source-status-indicator ${esc(s)}"></span><span class="source-item-name">${esc(x.name||id)}</span><span class="source-item-status">${esc(label)}</span></div>`;}).join('');
    const num=DEFAULT_SOURCES.filter(id=>src[id]?.status==='ok').length;
    const mode=state.data.scan?.status||'starter';
    $('health-legend').textContent=mode==='starter'?'NOT STARTED':`${num} / ${DEFAULT_SOURCES.length} CHECKED`;
    $('source-note').textContent=mode==='starter'?'A hand-verified snapshot is included. Daily automation refreshes the source feed.':num===DEFAULT_SOURCES.length?'All five sources checked at the last run; reporting may be delayed.':'Some source checks need attention. SEC EDGAR requires a valid SEC_USER_AGENT repository variable; other sources may be delayed.';
    const pulse=$('sidebar-pulse');pulse.className='signal-pulse';
    if(mode==='starter')pulse.classList.add('pending');else if(mode==='failed')pulse.classList.add('error');
    $('sidebar-status-title').textContent=mode==='starter'?'Starter edition':mode==='live'||mode==='ok'?'Automated monitoring':mode==='partial'?'Partial coverage':'Source errors';
    $('sidebar-status-desc').textContent=mode==='starter'?'Automatic scans not yet run':mode==='failed'?'Latest scan failed':`Daily checks · 18:00 UTC`;
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
      state.data=data;renderAll();
      if(showFeedback)notify(previous!==data.scan.ran_at?'Latest published snapshot loaded':'Already showing the latest published snapshot');
    } catch(error) {
      console.error('Could not load news.json:',error);
      if(!state.data){ $('scan-label').textContent='News file unavailable';$('scan-description').textContent='Serve this folder over HTTP (see README).';$('no-results').hidden=false;$('stat-health').textContent='—'; }
      notify('Could not load news snapshot. Please check your connection.');
    } finally {button.classList.remove('is-loading');button.disabled=false;}
  }
  function setView(view) {
    if(!VIEWS[view])return;
    state.view=view;
    if(view==='sec'||view==='partnerships'){state.category='All';}
    state.days=view==='saved'?3650:30;
    state.entity='All';state.query='';$('search-input').value='';
    renderFeed();
    if(window.matchMedia('(max-width:820px)').matches) document.querySelector('.section-heading')?.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function clearFilters() {
    state.view='overview';state.entity='All';state.impact='All';state.category='All';state.days=30;state.sort='latest';state.query='';$('search-input').value='';renderFeed();
  }
  function csvCell(value) {let text=String(value??''); if(/^[\s]*[=+\-@]/.test(text)) text="'"+text; return `"${text.replace(/"/g,'""')}"`;}
  function exportCSV() {
    if(!state.filtered.length){notify('No stories in the current view');return;}
    const fields=['Date','Entity','Topic','Impact','Headline','Source','Summary','Investor angle','Original URL'];
    const rows=state.filtered.map(i=>[dateLine(i),(i.entities||[]).join(' / '),i.category,i.impact,i.title,i.source,i.excerpt,i.why_it_matters,i.url].map(csvCell).join(','));
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