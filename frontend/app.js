/* ===== KALA-NETRA V3 — Blended Multi-Tone Forensic Workbench =============== */
const API = '/api/v1';
const S = { case:null, view:'overview', data:{}, excluded:new Set(), graph:null, stopGraph:null };

const api = async (p, o) => {
  const r = await fetch(API + p, o);
  if (!r.ok) throw new Error(r.status + ' ' + p);
  return r.json();
};
const post = (p, b) => api(p, {method:'POST', headers:{'Content-Type':'application/json'},
                              body:JSON.stringify(b)});
const $ = s => document.querySelector(s);
const el = (t, c, h) => { const e=document.createElement(t); if(c)e.className=c;
                          if(h!==undefined)e.innerHTML=h; return e; };
const esc = s => String(s??'').replace(/[&<>"]/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const num = (n,d=0) => (n===null||n===undefined||isNaN(n)) ? '—'
  : Number(n).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
const inr = n => '₹' + num(n,2);
const hhmm = e => new Date(e*1000).toISOString().slice(11,19);
const shortHash = h => h ? (h.slice(0,10) + '…' + h.slice(-8)) : '—';
const fmtDt = s => {
  s = Math.max(0, Math.round(s));
  if (s < 60) return '+' + s + 's';
  const m = Math.floor(s / 60), r = s % 60;
  return r ? ('+' + m + 'm ' + r + 's') : ('+' + m + 'm');
};

function toast(msg, ms=2400){
  const t=$('#toast'); t.textContent=msg; t.classList.add('on');
  clearTimeout(t._k); t._k=setTimeout(()=>t.classList.remove('on'), ms);
}
function busy(on, label){
  const p=$('#railStatus'); p.classList.toggle('busy',on);
  p.querySelector('span').textContent = on ? (label||'computing…') : 'engine ready';
}
async function copyText(txt, label='value'){
  try { await navigator.clipboard.writeText(txt); toast('Copied '+label); }
  catch { toast(label+': '+txt.slice(0,24)+'…'); }
}

/* ---------- harmonized theme palette ---------- */
function isDark(){ return document.documentElement.dataset.theme === 'dark'; }
function pal(){
  if (isDark()) {
    return {
      nodeLabel:'#F8FAFC', nodeLabelBg:'rgba(15,23,36,0.90)',
      edge:'rgba(148,163,184,0.20)', edgeHi:'rgba(96,165,250,0.85)',
      erA:'#60A5FA', erB:'#2DD4BF', grid:'rgba(96,165,250,0.07)',
      phys:'#60A5FA', app:'#FBBF24', spoof:'#FB7185',
      axis:'#94A3B8', flowTxt:'#F8FAFC', badgeBg:'#1A2336', badgeBd:'#334155',
      clusters:['#60A5FA','#2DD4BF','#FBBF24','#A78BFA','#F472B6'],
      nt:{ IMEI:'#60A5FA', IMSI:'#A78BFA', MSISDN:'#F472B6', MAC_ADDR:'#2DD4BF',
           UPI_VPA:'#FBBF24', BANK_ACCT:'#F59E0B', VEHICLE_PLATE:'#FB7185',
           CELL_TOWER_CGI:'#64748B', WIFI_BSSID:'#14B8A6', ATM_TERMINAL:'#D97706',
           APK_HASH:'#8B5CF6', IP_ADDR:'#3B82F6', CCTV_CAMERA:'#94A3B8' }
    };
  }
  return {
    nodeLabel:'#0F172A', nodeLabelBg:'rgba(255,255,255,0.94)',
    edge:'rgba(100,116,139,0.22)', edgeHi:'rgba(37,99,235,0.88)',
    erA:'#2563EB', erB:'#0D9488', grid:'rgba(37,99,235,0.065)',
    phys:'#2563EB', app:'#D97706', spoof:'#E11D48',
    axis:'#64748B', flowTxt:'#0F172A', badgeBg:'#FFFFFF', badgeBd:'#CBD5E1',
    clusters:['#2563EB','#0D9488','#D97706','#7C3AED','#E11D48'],
    nt:{ IMEI:'#2563EB', IMSI:'#7C3AED', MSISDN:'#DB2777', MAC_ADDR:'#0D9488',
         UPI_VPA:'#D97706', BANK_ACCT:'#B45309', VEHICLE_PLATE:'#E11D48',
         CELL_TOWER_CGI:'#475569', WIFI_BSSID:'#0F766E', ATM_TERMINAL:'#CA8A04',
         APK_HASH:'#6D28D9', IP_ADDR:'#1D4ED8', CCTV_CAMERA:'#64748B' }
  };
}
function applyTheme(t){
  document.documentElement.dataset.theme = t;
  localStorage.setItem('kn_theme', t);
  const btn = $('#themeBtn');
  if (btn) {
    $('#themeLabel').textContent = t === 'dark' ? 'Blended' : 'Slate';
    $('#themeIcon').innerHTML = t === 'dark'
      ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>'
      : '<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>';
  }
}

/* ---------- icons & nav ---------- */
const ICON = {
  overview:'<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-5H3zM13 8h8V3h-8z"/>',
  timeline:'<path d="M12 3v18M12 7h7M12 12h5M12 17h8M12 7H7M12 17H5"/>',
  network:'<circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="7" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7l9 9M17 9l-4 7"/>',
  clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  kinematic:'<path d="M3 18l5-9 4 5 3-7 6 11"/><circle cx="8" cy="9" r="1.6"/>',
  money:'<path d="M4 7h10a4 4 0 010 8H8M8 4v16"/><path d="M14 15l4 4 2-3"/>',
  hypo:'<path d="M12 3l8 5v8l-8 5-8-5V8z"/><path d="M12 11v6M12 8h.01"/>',
  whatif:'<path d="M5 6h9M5 12h14M5 18h7"/><circle cx="18" cy="6" r="2.2"/><circle cx="15" cy="18" r="2.2"/>',
  evidence:'<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>',
  copilot:'<path d="M4 5h16v11H9l-5 4z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/>',
  bench:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  shield:'<path d="M12 3l7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3z"/><path d="M9.5 12l2 2 3.5-4"/>'
};
const NAV = [
  ['CASE', [['overview','Overview','overview'],['timeline','Reconstruction','timeline'],
            ['evidence','Evidence ledger','evidence']]],
  ['CORRELATION', [['clock','Clock sync','clock'],['network','Entity network','network'],
                   ['kinematic','Kinematics','kinematic'],['money','Money flow','money']]],
  ['DECISION SUPPORT', [['hypo','Hypotheses','hypo'],['whatif','Counterfactual','whatif'],
                        ['copilot','Query copilot','copilot'],['bench','Benchmark','bench']]]
];

const SRC_THEME = {
  SRC_CDR_01:  { tag:'t-cy',     tint:'tint-cy' },
  SRC_UFDR_01: { tag:'t-violet', tint:'tint-violet' },
  SRC_WIFI_01: { tag:'t-teal',   tint:'tint-teal' },
  SRC_BANK_01: { tag:'t-amber',  tint:'tint-amber' },
  SRC_CCTV_01: { tag:'t-red',    tint:'tint-red' },
  SRC_GPS_01:  { tag:'t-cy',     tint:'tint-violet' }
};

function navBadge(id){
  if (!S.case) return null;
  const c = S.case.counts;
  if (id === 'overview') return { val: S.case.highlights.length, warn: true };
  if (id === 'timeline') return { val: c.causal_edges };
  if (id === 'evidence') return { val: c.events };
  if (id === 'clock')    return { val: c.anchors };
  if (id === 'network')  return { val: c.entity_links };
  if (id === 'kinematic')return { val: c.anomalies, warn: c.anomalies > 0 };
  if (id === 'money')    return { val: c.mules, warn: c.mules > 0 };
  return null;
}

function buildNav(){
  const n = $('#nav'); n.innerHTML='';
  NAV.forEach(([sec, items]) => {
    n.appendChild(el('div','nav-sec',sec));
    items.forEach(([id,label,icon]) => {
      const b = navBadge(id);
      const badgeHtml = b ? '<span class="nav-badge'+(b.warn?' warn':'')+'">'+b.val+'</span>' : '';
      const a = el('div','nav-i' + (S.view===id?' on':''),
        '<svg viewBox="0 0 24 24">'+ICON[icon]+'</svg><span>'+label+'</span>'+badgeHtml);
      a.onclick = () => { $('#rail').classList.remove('open'); go(id); };
      n.appendChild(a);
    });
  });
}

/* ---------- shell ---------- */
async function boot(){
  applyTheme(localStorage.getItem('kn_theme') || 'light');
  $('#themeBtn').onclick = () => {
    applyTheme(isDark() ? 'light' : 'dark');
    go(S.view);
  };
  $('#menuBtn').onclick = () => $('#rail').classList.toggle('open');

  const log = $('#bootLog');
  const lines = ['opening exhibits in binary mode…','hashing Merkle leaves (RFC 6962)…',
                 'solving reduced weighted Laplacian…','resolving fragmented identifiers…',
                 'reconstructing causal arborescence…'];
  let i=0; const t=setInterval(()=>{ log.textContent = lines[i++ % lines.length]; }, 420);
  try {
    S.case = await api('/case');
    S.data.timeline = await api('/timeline');
    S.data.fin = await api('/finance');
  } catch(e){ log.textContent = 'engine unreachable: ' + e.message; return; }
  clearInterval(t);
  $('#tbCase').textContent = S.case.case_title;
  $('#tbSub').textContent = S.case.case_id + '  ·  ' + S.case.counts.events +
    ' correlated records  ·  pipeline ' + S.case.runtime_ms.toFixed(0) + ' ms';
  renderKpis(); buildNav(); go('overview');
  setTimeout(()=>$('#boot').classList.add('gone'), 200);
}

function renderKpis(){
  const c = S.case.counts;
  const k = [
    ['cy',c.events,'records','evidence'],
    ['violet',c.anchors,'anchors','clock'],
    ['mint',c.entity_links,'links','network'],
    ['cy',c.causal_edges,'causal','timeline'],
    ['red',c.anomalies,'kinematic','kinematic'],
    ['amber',c.mules,'mules','money']
  ];
  const host = $('#tbKpis');
  host.innerHTML = k.map(([cl,v,l,target]) =>
    '<div class="kpi '+cl+'" data-go="'+target+'" title="Open '+target+'"><b>'+v+'</b><span>'+l+'</span></div>').join('');
  host.querySelectorAll('.kpi').forEach(elK=>elK.onclick=()=>go(elK.dataset.go));
}

const VIEWS = {};
async function go(v){
  if (S.stopGraph) { S.stopGraph(); S.stopGraph = null; }
  S.view = v; buildNav();
  const m = $('#main'); m.innerHTML = '<div class="empty">loading…</div>';
  try { m.innerHTML=''; m.appendChild(await VIEWS[v]()); }
  catch(e){ m.innerHTML = '<div class="card"><h3>error</h3><div class="sm">'+esc(e.message)+'</div></div>'; }
  window.scrollTo({top:0,behavior:'instant'});
}
function head(title, sub, right){
  const h = el('div','vh');
  h.innerHTML = '<div><h1>'+title+'</h1><p>'+sub+'</p></div>';
  if(right) h.appendChild(right);
  return h;
}
function sevClass(s){ return s==='CRITICAL'?'crit':(s==='HIGH'?'high':'med'); }
function sevTag(s){ return s==='CRITICAL'?'t-red':(s==='HIGH'?'t-amber':'t-cy'); }

/* ====================== OVERVIEW ====================== */
VIEWS.overview = async () => {
  const c = S.case, tl = S.data.timeline, fin = S.data.fin;
  const v = el('div','view');
  v.appendChild(head('Case investigation overview',
    'Six heterogeneous exhibits reconciled onto one byte-provable UTC timeline. '+
    'Every link, anomaly, and citation below is deterministically derived from raw evidence on disk.'));

  const top = el('div','grid g4');
  const lead = c.hypotheses.find(h=>h.id===c.ranked[0]);
  const tiles = [
    ['Leading hypothesis', lead.id + ' (+'+lead.support+')', lead.title, 'tint-cy', 't-cy', 'best supported', 'ki-cy', ICON.shield],
    ['Clock residual RMSE', c.clock.rmse_clock.toFixed(3)+' s', c.clock.anchor_count+' identity-free anchors', 'tint-violet', 't-violet', 'Laplacian sync', 'ki-violet', ICON.clock],
    ['Resolved profiles', c.counts.clusters, c.counts.entity_links+' accepted entity links', 'tint-teal', 't-teal', 'entity fusion', 'ki-teal', ICON.network],
    ['Forensic findings', c.highlights.length,
      c.counts.anomalies+' kinematic · '+c.detectors.length+' detectors · '+c.counts.mules+' mules', 'tint-red', 't-red', 'high priority', 'ki-red', ICON.kinematic]
  ];
  tiles.forEach(([t,b,s,tintCls,tagCls,badge,iconCls,svgPath])=>{
    const card = el('div','card '+tintCls);
    card.innerHTML =
      '<div class="kpi-head"><h3>'+t+'</h3><span class="tag '+tagCls+'">'+badge+'</span></div>'+
      '<div class="kpi-row">'+
        '<div class="big">'+b+'</div>'+
        '<div class="kpi-icon '+iconCls+'"><svg viewBox="0 0 24 24">'+svgPath+'</svg></div>'+
      '</div>'+
      '<div class="sm" style="margin-top:8px">'+esc(s)+'</div>';
    top.appendChild(card);
  });
  v.appendChild(top);

  /* Aurora-Slate Connected Detective Chain */
  const chainCard = el('div','story-band');
  chainCard.innerHTML = '<h3>Connected evidence chain<em>click any stage to trace</em></h3>';
  const strip = el('div','story-strip');
  const tracedTxt = fin && fin.max_flow && fin.max_flow.traced_inr !== undefined
    ? inr(fin.max_flow.traced_inr) : inr(fin ? fin.total_debited_inr : 0);
  const stages = [
    ['s1', '01 · Intrusion', 'Phishing & Dropper',
      'SMS dropper URL installed APK with privileged SMS/accessibility permissions on victim device.',
      'Reconstruction →', ()=>go('timeline')],
    ['s2', '02 · Takeover', 'SIM Swap & OTP Intercept',
      (c.detectors.find(d=>d.code==='SIM_SWAP_DETECTED')?.detail || 'MSISDN re-bound to suspect IMSI/IMEI; bank OTP intercepted.'),
      'Entity network →', ()=>go('network')],
    ['s3', '03 · Laundering', (fin?fin.mules.length:0)+' Mule Accounts',
      tracedTxt + ' traced via Edmonds-Karp max-flow through rapid pass-through UPI mule hops.',
      'Money flow →', ()=>go('money')],
    ['s4', '04 · Cash-Out', 'ATM + ANPR Sighting',
      'Consolidated cash dispense matched to suspect vehicle plate at Nehru Place ATM ('+
      (c.media.length?c.media[0].flags.length+' EXIF flags':'verified')+').',
      'Inspect frame →', ()=>{ const atm=tl?.steps?.find(s=>s.event_type==='ATM_CASH_WDL'); atm?provenance(atm.event_id):go('timeline'); }],
    ['s5', '05 · Contradiction', 'Spoofed GPS Alibi',
      'Application-layer GPS ping proved physically unreachable against bracketing cell/Wi-Fi records.',
      'Kinematics →', ()=>go('kinematic')]
  ];
  stages.forEach(([cls, step, title, desc, cta, act])=>{
    const node = el('div','story-node '+cls);
    node.innerHTML = '<div class="story-step">'+step+'</div><div class="story-title">'+esc(title)+'</div>'+
      '<div class="story-desc">'+esc(desc.length>112 ? desc.slice(0,110)+'…' : desc)+'</div>'+
      '<div class="story-link">'+cta+'</div>';
    node.onclick = act;
    strip.appendChild(node);
  });
  chainCard.appendChild(strip);
  v.appendChild(chainCard);

  const mid = el('div','grid g23'); mid.style.marginTop='14px';
  const alerts = el('div','card');
  alerts.innerHTML = '<h3>Forensic alerts<em>'+(c.highlights.length)+' findings</em></h3>';
  c.highlights.forEach(h=>{
    const a = el('div','alert '+sevClass(h.severity)+(h.event_id?' clickable':''));
    a.innerHTML = '<div style="flex:1"><div class="row" style="justify-content:space-between">'+
      '<div class="row"><span class="alert-k">'+esc(h.code)+'</span>'+
      '<span class="tag '+sevTag(h.severity)+'">'+h.severity+'</span></div>'+
      (h.event_id ? '<span class="tag t-cy">Inspect record →</span>' : '')+
      '</div><div class="alert-d">'+esc(h.text)+'</div></div>';
    if(h.event_id) a.onclick=()=>provenance(h.event_id);
    alerts.appendChild(a);
  });
  mid.appendChild(alerts);

  const hyp = el('div','card tint-teal');
  hyp.innerHTML = '<h3>Hypothesis support<em>ordinal, redundancy-clustered</em></h3>';
  const maxA = Math.max(...c.hypotheses.map(h=>Math.abs(h.support)),1);
  c.hypotheses.forEach(h=>{
    const d = el('div','diverge');
    const pct = Math.abs(h.support)/maxA*48;
    const grad = h.support>=0 ? 'linear-gradient(90deg,#0D9488,#2563EB)' : 'linear-gradient(90deg,#E11D48,#F59E0B)';
    const col = h.support>=0 ? 'var(--teal)' : 'var(--red)';
    d.innerHTML = '<div><b style="font-family:var(--mono);color:var(--cy2)">'+h.id+'</b>'+
      '<div class="sm" style="margin-top:2px">'+esc(h.title)+'</div></div>'+
      '<div class="dv-track"><div class="dv-fill" style="background:'+grad+';'+
      (h.support>=0?('left:50%;width:'+pct+'%'):('right:50%;width:'+pct+'%'))+'"></div></div>'+
      '<div class="num" style="color:'+col+';font-weight:700">'+(h.support>=0?'+':'')+h.support+'</div>';
    hyp.appendChild(d);
  });
  hyp.appendChild(el('div','sm','Reports auditable ordinal support over de-duplicated evidentiary clusters — never a probability of guilt.'));
  const goHyp = el('button','btn sec sm-btn','Open full comparator →');
  goHyp.style.marginTop='12px'; goHyp.onclick=()=>go('hypo');
  hyp.appendChild(goHyp);
  mid.appendChild(hyp);
  v.appendChild(mid);

  const ex = el('div','card'); ex.style.marginTop='14px';
  ex.innerHTML = '<h3>Exhibit manifest &amp; chain of custody<em>SHA-256 + RFC 6962 Merkle roots</em></h3>';
  const g = el('div','grid g3');
  c.files.forEach(f=>{
    const st = SRC_THEME[f.file_id] || { tag:'t-cy', tint:'tint-cy' };
    const card = el('div','card subcard '+st.tint);
    card.innerHTML =
      '<div class="row" style="justify-content:space-between"><span class="tag '+st.tag+'">'+f.file_id+'</span>'+
      '<span class="tag '+(f.is_clock_anchored?'t-mint':'t-red')+'">'+(f.is_clock_anchored?'clock-anchored':'unanchored')+'</span></div>'+
      '<div style="margin-top:9px;font-weight:700;font-size:13.5px;color:var(--txt)">'+esc(f.filename)+'</div>'+
      '<div class="sm">'+esc(f.label)+'</div>'+
      '<div class="grid g2" style="margin-top:10px;gap:8px">'+
        '<div><div class="sm">records</div><div class="mono">'+f.record_count+'</div></div>'+
        '<div><div class="sm">bytes · EOL</div><div class="mono">'+num(f.size_bytes)+' · '+f.line_terminator+'</div></div>'+
        '<div><div class="sm">σ timing</div><div class="mono">'+f.sigma_s.toFixed(1)+' s</div></div>'+
        '<div><div class="sm">β offset</div><div class="mono" style="color:var(--cy2);font-weight:700">'+
          (f.estimated_clock_offset_sec>=0?'+':'')+f.estimated_clock_offset_sec.toFixed(3)+' s</div></div>'+
      '</div>'+
      '<div class="sm" style="margin-top:10px">file SHA-256</div>'+
      '<div class="hash-line" title="'+esc(f.sha256_file)+'"><span>'+shortHash(f.sha256_file)+'</span>'+
        '<button class="copy-btn" data-copy="'+esc(f.sha256_file)+'" data-lbl="SHA-256">Copy</button></div>'+
      '<div class="sm" style="margin-top:7px">Merkle root</div>'+
      '<div class="hash-line" title="'+esc(f.merkle_root)+'"><span style="color:var(--violet)">'+shortHash(f.merkle_root)+'</span>'+
        '<button class="copy-btn" data-copy="'+esc(f.merkle_root)+'" data-lbl="Merkle root">Copy</button></div>';
    card.querySelectorAll('.copy-btn').forEach(btn=>btn.onclick=()=>copyText(btn.dataset.copy, btn.dataset.lbl));
    g.appendChild(card);
  });
  ex.appendChild(g);
  v.appendChild(ex);

  if(c.media && c.media.length){
    const m = el('div','card tint-amber'); m.style.marginTop='14px';
    m.innerHTML = '<h3>Multimedia header &amp; EXIF integrity</h3>';
    const row = el('div','grid g23');
    const left = el('div','');
    c.media.forEach(md=>{
      md.flags.forEach(f=>{
        const a = el('div','alert '+sevClass(f.severity));
        a.innerHTML = '<div><div class="row"><span class="alert-k">'+f.code+'</span>'+
          '<span class="tag t-red">'+f.severity+'</span></div><div class="alert-d">'+esc(f.detail)+'</div></div>';
        left.appendChild(a);
      });
      const kv = el('div','kv');
      kv.innerHTML = Object.entries(md.exif||{}).map(([k,val])=>
        '<dt>'+esc(k)+'</dt><dd>'+esc(val)+'</dd>').join('') +
        '<dt>container</dt><dd>'+md.container+'</dd><dt>frame sha-256</dt><dd>'+md.sha256+'</dd>';
      left.appendChild(kv);
    });
    row.appendChild(left);
    const img = el('div','card subcard');
    img.innerHTML = '<h3>Seized frame</h3><img src="'+API+'/frame/'+encodeURIComponent(c.media[0].file)+
      '" style="width:100%;border-radius:10px;border:1px solid var(--line)"/>'+
      '<div class="sm" style="margin-top:8px">'+esc(c.media[0].file)+'</div>';
    row.appendChild(img);
    m.appendChild(row); v.appendChild(m);
  }
  return v;
};

/* ====================== TIMELINE ====================== */
VIEWS.timeline = async () => {
  const d = S.data.timeline || (S.data.timeline = await api('/timeline'));
  const v = el('div','view');
  v.appendChild(head('Deterministic crime reconstruction',
    'Each sentence is interpolated deterministically over verified database columns — 100% citation precision, 0% hallucination. '+
    'Click any step to re-read its raw bytes from disk and validate its RFC 6962 Merkle proof.'));

  const stat = el('div','grid g4');
  [['steps',d.steps.length,'tint-cy','t-cy','narrative'],
   ['causal edges',d.storyline.length,'tint-violet','t-violet','arborescence'],
   ['citation precision',(d.citation_precision*100).toFixed(1)+'%','tint-teal','t-mint','verified'],
   ['hallucination rate',(d.hallucination_rate*100).toFixed(1)+'%','tint-mint','t-teal','no LLM']]
   .forEach(([l,val,tintCls,tagCls,sub])=>{ const k=el('div','card '+tintCls);
     k.innerHTML='<div class="kpi-head"><h3>'+l+'</h3><span class="tag '+tagCls+'">'+sub+'</span></div>'+
       '<div class="big">'+val+'</div>'; stat.appendChild(k); });
  v.appendChild(stat);

  const crit = new Set(S.case.highlights.filter(h=>h.severity==='CRITICAL').map(h=>h.event_id));
  const filterBar = el('div','card'); filterBar.style.marginTop='14px';
  filterBar.innerHTML = '<div class="row">'+
    '<input type="search" id="tlq" placeholder="filter steps by narrative, event type, or ID…" style="flex:1;min-width:220px"/>'+
    '<select id="tlf" style="width:190px"><option value="">all exhibits</option>'+
      S.case.files.map(f=>'<option value="'+f.file_id+'">'+f.file_id+'</option>').join('')+'</select>'+
    '<button class="btn sec" id="tlCrit">Critical only ('+crit.size+')</button></div>';
  v.appendChild(filterBar);

  const tl = el('div','tl'); tl.style.marginTop='16px';
  v.appendChild(tl);

  let onlyCrit = false;
  function renderSteps(){
    const q = ($('#tlq').value||'').trim().toLowerCase();
    const fid = $('#tlf').value;
    const list = d.steps.filter(s=>{
      if (onlyCrit && !crit.has(s.event_id)) return false;
      if (fid && s.file_id !== fid) return false;
      if (q && !(s.text + ' ' + s.event_type + ' ' + s.event_id).toLowerCase().includes(q)) return false;
      return true;
    });
    tl.innerHTML = '';
    if (!list.length) { tl.innerHTML = '<div class="card"><div class="empty">no matching reconstruction steps</div></div>'; return; }
    list.forEach((s, idx)=>{
      const stMeta = SRC_THEME[s.file_id] || { tag:'t-cy' };
      const dtBadge = idx > 0 ? '<span class="tag t-violet">'+fmtDt(s.t - list[idx-1].t)+'</span>' : '';
      const st = el('div','step'+(crit.has(s.event_id)?' crit':''));
      st.innerHTML = '<div class="step-h"><span class="step-t">'+hhmm(s.t)+' UTC</span>'+
        dtBadge+
        '<span class="tag t-grey">'+esc(s.event_type)+'</span>'+
        '<span class="tag '+stMeta.tag+'">'+esc(s.file_id)+'</span>'+
        (crit.has(s.event_id)?'<span class="tag t-red">CRITICAL</span>':'')+'</div>'+
        '<div class="step-b">'+esc(s.text)+'</div>'+
        '<div class="step-c"><span>'+esc(s.citation)+'</span><span class="tag t-mint">Verify Merkle proof →</span></div>';
      st.onclick = ()=>provenance(s.event_id);
      tl.appendChild(st);
    });
  }
  setTimeout(()=>{
    renderSteps();
    $('#tlq').oninput = renderSteps;
    $('#tlf').onchange = renderSteps;
    $('#tlCrit').onclick = () => {
      onlyCrit = !onlyCrit;
      $('#tlCrit').className = onlyCrit ? 'btn' : 'btn sec';
      renderSteps();
    };
  }, 10);
  return v;
};

/* ====================== CLOCK ====================== */
VIEWS.clock = async () => {
  const d = S.data.clock || (S.data.clock = await api('/clock'));
  const v = el('div','view');
  v.appendChild(head('Non-circular clock synchronisation',
    'Offsets are solved by weighted least squares on a reduced graph Laplacian, gauge-fixed on the '+
    'GPS-disciplined telecom switch (β₀ = 0), using only identity-free infrastructure anchors.'));

  const top = el('div','grid g3');
  [['anchors used', d.anchor_count, 'tint-cy', 't-cy', 'identity-free'],
   ['residual RMSE', d.rmse_clock.toFixed(4)+' s', 'tint-teal', 't-mint', 'post-sync'],
   ['rejected (z > 3.5)', d.rejected_anchors.length, 'tint-violet', d.rejected_anchors.length?'t-red':'t-teal', 'outliers']]
   .forEach(([l,val,tintCls,tagCls,sub])=>{ const k=el('div','card '+tintCls);
     k.innerHTML='<div class="kpi-head"><h3>'+l+'</h3><span class="tag '+tagCls+'">'+sub+'</span></div>'+
       '<div class="big">'+val+'</div>'; top.appendChild(k); });
  v.appendChild(top);

  const off = el('div','card'); off.style.marginTop='14px';
  off.innerHTML = '<h3>Recovered clock offsets β<em>t = τ + β</em></h3>';
  const mx = Math.max(...d.files.map(f=>Math.abs(f.estimated_clock_offset_sec)),1);
  d.files.forEach(f=>{
    const row = el('div','diverge');
    const pct = Math.abs(f.estimated_clock_offset_sec)/mx*47;
    const grad = f.estimated_clock_offset_sec>=0 ? 'linear-gradient(90deg,#2563EB,#0D9488)' : 'linear-gradient(90deg,#E11D48,#D97706)';
    const col = f.estimated_clock_offset_sec>=0?'var(--cy)':'var(--amber)';
    row.innerHTML = '<div><b style="font-family:var(--mono);font-size:12px">'+f.file_id+'</b>'+
      '<div class="sm">'+esc(f.label)+' · σ '+f.sigma_s.toFixed(1)+' s · '+f.anchor_count+' anchors</div></div>'+
      '<div class="dv-track"><div class="dv-fill" style="background:'+grad+';'+
        (f.estimated_clock_offset_sec>=0?('left:50%;width:'+pct+'%'):('right:50%;width:'+pct+'%'))+'"></div></div>'+
      '<div class="num" style="color:'+col+';font-weight:700">'+(f.estimated_clock_offset_sec>=0?'+':'')+
        f.estimated_clock_offset_sec.toFixed(2)+'s</div>';
    off.appendChild(row);
  });
  v.appendChild(off);

  const anc = el('div','card'); anc.style.marginTop='14px';
  anc.innerHTML = '<h3>Cross-exhibit anchor set<em>'+d.anchors.length+' pairs</em></h3>';
  const tw = el('div','tw');
  tw.innerHTML = '<table><thead><tr><th>type</th><th>key</th><th>exhibit i</th><th>exhibit j</th>'+
    '<th class="num">τj − τi</th><th class="num">residual</th><th class="num">z</th><th>state</th></tr></thead><tbody>'+
    d.anchors.map(a=>'<tr><td><span class="tag t-violet">'+a.anchor_type+'</span></td>'+
      '<td class="mono">'+esc(String(a.anchor_key).slice(0,34))+'</td><td class="mono">'+a.file_i+'</td>'+
      '<td class="mono">'+a.file_j+'</td><td class="num">'+(a.tau_j-a.tau_i).toFixed(2)+'s</td>'+
      '<td class="num">'+(a.residual_s===null?'—':a.residual_s.toFixed(3)+'s')+'</td>'+
      '<td class="num">'+(a.z===null?'—':a.z.toFixed(2))+'</td>'+
      '<td><span class="tag '+(a.used?'t-mint':'t-red')+'">'+(a.used?'used':'rejected')+'</span></td></tr>').join('')+
    '</tbody></table>';
  anc.appendChild(tw); v.appendChild(anc);
  return v;
};

/* ====================== NETWORK ====================== */
VIEWS.network = async () => {
  const g = S.data.graph || (S.data.graph = await api('/graph'));
  const ent = S.data.entity || (S.data.entity = await api('/entity'));
  const P = pal();
  const v = el('div','view');
  v.appendChild(head('Spatio-temporal heterogeneous entity graph',
    'Identifiers are fused across exhibits by four interpretable signals: co-record device binding, '+
    'OCR homoglyph-canonicalised string match, Adamic-Adar hub similarity, and buffered spatio-temporal co-occurrence.'));

  const wrap = el('div','canvas-wrap');
  const bar = el('div','graph-toolbar');
  const clusterButtons = '<button class="tag clickable t-cy" data-cl="">All clusters</button>' +
    ent.clusters.map(c=>'<button class="tag clickable t-grey" data-cl="'+c.cluster_id+'">'+c.cluster_id+
      ' ('+c.members.length+')</button>').join('');
  bar.innerHTML =
    '<div class="row" style="gap:6px">'+clusterButtons+'</div>'+
    '<div class="row" style="gap:7px">'+
      '<input type="search" id="gSearch" placeholder="highlight identifier…" style="width:190px;padding:6px 10px;font-size:12px"/>'+
      '<button class="btn sec sm-btn" id="gZoomIn">+</button>'+
      '<button class="btn sec sm-btn" id="gZoomOut">−</button>'+
      '<button class="btn sec sm-btn" id="gFit">Fit</button>'+
    '</div>';
  wrap.appendChild(bar);

  const stage = el('div','canvas-stage');
  const cv = el('canvas'); stage.appendChild(cv);
  stage.appendChild(el('div','ghint','click node = inspect · scroll = zoom · drag = pan'));
  const lg = el('div','legend');
  lg.innerHTML = Object.entries(P.nt).slice(0,8).map(([k,c])=>
    '<div class="lg"><i style="background:'+c+'"></i>'+k+'</div>').join('');
  stage.appendChild(lg);
  const tip = el('div','tip'); stage.appendChild(tip);
  const insp = el('div','node-inspector'); stage.appendChild(insp);
  wrap.appendChild(stage);
  v.appendChild(wrap);

  const info = el('div','grid g23'); info.style.marginTop='14px';
  const lk = el('div','card tint-cy');
  lk.innerHTML = '<h3>Accepted entity links<em>LinkScore ≥ '+S.case.config.link_threshold+' · click row to inspect</em></h3>';
  const tw = el('div','tw');
  tw.innerHTML = '<table><thead><tr><th>u</th><th>v</th><th>basis</th><th class="num">exact</th>'+
    '<th class="num">str</th><th class="num">struct</th><th class="num">s-t</th><th class="num">sites</th>'+
    '<th class="num">score</th></tr></thead><tbody>'+
    ent.links.map((l,i)=>'<tr data-i="'+i+'" style="cursor:pointer"><td class="mono">'+esc(l.u_id)+'</td>'+
      '<td class="mono">'+esc(l.v_id)+'</td><td><span class="tag t-violet">'+
      l.basis.replace(/_/g,' ').toLowerCase()+'</span></td>'+
      ['s_exact','s_str','s_struct','s_st'].map(k=>'<td class="num">'+l[k].toFixed(2)+'</td>').join('')+
      '<td class="num">'+l.distinct_sites+'</td>'+
      '<td class="num" style="color:var(--mint);font-weight:700">'+l.link_score.toFixed(3)+'</td></tr>').join('')+
    '</tbody></table>';
  tw.querySelectorAll('tr[data-i]').forEach(tr=>tr.onclick=()=>linkDetail(ent.links[+tr.dataset.i]));
  lk.appendChild(tw); info.appendChild(lk);

  const cl = el('div','card tint-violet');
  cl.innerHTML = '<h3>Resolved profiles &amp; pattern detectors</h3>';
  ent.clusters.forEach(c=>{
    const b = el('div','alert med');
    b.innerHTML = '<div><div class="row"><span class="alert-k" style="color:var(--cy2)">'+c.cluster_id+
      '</span><span class="tag t-grey">'+c.event_count+' events</span></div><div class="alert-d" style="margin-top:6px">'+
      c.member_detail.map(m=>'<span class="tag t-grey" style="margin:2px 4px 2px 0">'+m.type+' '+esc(m.id)+'</span>').join('')+
      '</div></div>';
    cl.appendChild(b);
  });
  ent.detectors.forEach(dd=>{
    const b = el('div','alert '+sevClass(dd.severity));
    b.innerHTML = '<div><div class="row"><span class="alert-k">'+dd.code+'</span><span class="tag '+
      sevTag(dd.severity)+'">'+dd.severity+'</span></div><div class="alert-d">'+esc(dd.detail)+'</div></div>';
    cl.appendChild(b);
  });
  info.appendChild(cl); v.appendChild(info);

  setTimeout(()=>drawGraph(cv, tip, insp, bar, g, ent), 30);
  return v;
};

function linkDetail(l){
  openDrawer('Entity link decomposition', l.u_id + '  ↔  ' + l.v_id);
  const b = $('#dBody');
  let h = '<dl class="kv"><dt>LinkScore</dt><dd style="color:var(--mint);font-size:14px;font-weight:700">'+
    l.link_score.toFixed(4)+'</dd><dt>decided by</dt><dd>'+l.basis+'</dd>'+
    '<dt>S_exact</dt><dd>'+l.s_exact.toFixed(4)+'</dd>'+
    '<dt>S_str</dt><dd>'+l.s_str.toFixed(4)+'</dd>'+
    '<dt>S_struct</dt><dd>'+l.s_struct.toFixed(4)+' (Adamic-Adar '+l.adamic_adar.toFixed(4)+')</dd>'+
    '<dt>S_st</dt><dd>'+l.s_st.toFixed(4)+' across '+l.distinct_sites+' distinct sites</dd></dl>';
  if(l.shared_hubs.length){
    h += '<h3 style="font-size:11px;letter-spacing:.1em;color:var(--txt3);margin:14px 0 8px;text-transform:uppercase">Shared hubs</h3>'+
      '<div class="proof">'+l.shared_hubs.map(x=>'<div class="pf"><b>'+x.contribution.toFixed(3)+
      '</b><span>'+esc(x.hub)+' · degree '+x.degree+'</span></div>').join('')+'</div>';
  }
  if(l.colocations.length){
    h += '<h3 style="font-size:11px;letter-spacing:.1em;color:var(--txt3);margin:14px 0 8px;text-transform:uppercase">Co-locations</h3>'+
      '<div class="proof">'+l.colocations.map(x=>'<div class="pf"><b>κ '+x.kappa.toFixed(3)+
      '</b><span>'+x.event_u+' ↔ '+x.event_v+' · Δt '+x.dt_s+'s · Δd '+x.d_m+'m (buffered '+x.d_eff_m+'m)</span></div>').join('')+'</div>';
  }
  if(l.co_record_events.length){
    h += '<h3 style="font-size:11px;letter-spacing:.1em;color:var(--txt3);margin:14px 0 8px;text-transform:uppercase">Co-record bindings</h3>'+
      '<div class="proof">'+l.co_record_events.map(x=>'<div class="pf"><b>bind</b><span>'+x+'</span></div>').join('')+'</div>';
  }
  b.innerHTML = h;
}

function drawGraph(cv, tip, insp, bar, g, ent){
  const P = pal();
  const dpr = window.devicePixelRatio||1;
  const W = cv.clientWidth || 800, H = cv.clientHeight || 560;
  cv.width = W*dpr; cv.height = H*dpr;
  const ctx = cv.getContext('2d'); ctx.scale(dpr,dpr);

  const keep = new Set();
  g.nodes.forEach(n=>{ if(n.cluster || n.degree>=4) keep.add(n.id); });
  ent.links.forEach(l=>{ keep.add(l.u); keep.add(l.v); });
  const kept = g.nodes.filter(n=>keep.has(n.id));
  const nodes = kept.map((n,i)=>{
    const a = i/Math.max(1,kept.length)*6.283, rad = Math.min(W,H)*(n.cluster?0.18:0.35);
    return {...n, x: W/2 + Math.cos(a)*rad, y: H/2 + Math.sin(a)*rad, vx:0, vy:0,
            r: 5.5 + Math.min(11, Math.sqrt((n.degree||1))*2.1)};
  });
  const idx = {}; nodes.forEach((n,i)=>idx[n.id]=i);
  const links = g.edges.filter(e=>idx[e.source]!==undefined && idx[e.target]!==undefined)
    .map(e=>({s:idx[e.source],t:idx[e.target],kind:'ev'}));
  ent.links.forEach(l=>{ if(idx[l.u]!==undefined && idx[l.v]!==undefined)
    links.push({s:idx[l.u],t:idx[l.v],kind:'er',score:l.link_score,meta:l}); });

  let view = {x:0,y:0,k:1}, hover=null, selected=null, drag=null, downPt=null, alpha=1;
  let activeCluster = '', queryStr = '', rafId = 0, alive = true;

  function step(){
    const k = alpha;
    for(let i=0;i<nodes.length;i++){
      const a=nodes[i];
      a.vx += (W/2 - a.x)*0.0013*k; a.vy += (H/2 - a.y)*0.0013*k;
      for(let j=i+1;j<nodes.length;j++){
        const b=nodes[j]; let dx=b.x-a.x, dy=b.y-a.y; let d2=dx*dx+dy*dy;
        if(d2<1) d2=1; if(d2>160000) continue;
        const f = 920*k/d2, d=Math.sqrt(d2);
        const fx=dx/d*f, fy=dy/d*f;
        a.vx-=fx; a.vy-=fy; b.vx+=fx; b.vy+=fy;
      }
    }
    links.forEach(l=>{
      const a=nodes[l.s], b=nodes[l.t];
      const dx=b.x-a.x, dy=b.y-a.y, d=Math.max(1,Math.hypot(dx,dy));
      const target = l.kind==='er'?74:165;
      const f = (d-target)*0.010*k;
      const fx=dx/d*f, fy=dy/d*f;
      a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy;
    });
    nodes.forEach(n=>{ n.vx*=.86; n.vy*=.86; n.x+=n.vx; n.y+=n.vy; });
    alpha = Math.max(.08, alpha*0.992);
  }

  function isMatch(n){
    if (activeCluster && n.cluster !== activeCluster) return false;
    if (queryStr && !n.label.toLowerCase().includes(queryStr) && !n.type.toLowerCase().includes(queryStr)) return false;
    return true;
  }

  function draw(){
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = P.grid;
    const stepG = 32;
    for(let x=16;x<W;x+=stepG) for(let y=16;y<H;y+=stepG) ctx.fillRect(x,y,1.6,1.6);

    ctx.save(); ctx.translate(view.x,view.y); ctx.scale(view.k,view.k);

    // soft ambient aura under each resolved profile cluster
    const clPts = {};
    nodes.forEach(n=>{ if(n.cluster){ (clPts[n.cluster] = clPts[n.cluster]||[]).push(n); } });
    Object.entries(clPts).forEach(([cid, list])=>{
      if (activeCluster && cid !== activeCluster) return;
      const cx = list.reduce((s,n)=>s+n.x,0)/list.length;
      const cy = list.reduce((s,n)=>s+n.y,0)/list.length;
      const maxR = Math.max(46, ...list.map(n=>Math.hypot(n.x-cx, n.y-cy)+28));
      const ci = parseInt(cid.slice(1))-1;
      const ccol = P.clusters[ci % P.clusters.length];
      const grad = ctx.createRadialGradient(cx, cy, 4, cx, cy, maxR);
      grad.addColorStop(0, ccol + (isDark()?'26':'1E'));
      grad.addColorStop(1, ccol + '00');
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(cx, cy, maxR, 0, 6.283); ctx.fill();
    });

    const focus = selected || hover;
    const neighborIdx = new Set();
    if (focus) {
      neighborIdx.add(idx[focus.id]);
      links.forEach(l=>{
        if (nodes[l.s]===focus) neighborIdx.add(l.t);
        if (nodes[l.t]===focus) neighborIdx.add(l.s);
      });
    }

    links.forEach(l=>{
      const a=nodes[l.s], b=nodes[l.t];
      const touchesFocus = focus && (nodes[l.s]===focus || nodes[l.t]===focus);
      const dimmed = (activeCluster || queryStr) ? (!isMatch(a) && !isMatch(b)) : (focus && !touchesFocus);
      if(l.kind==='er'){
        const gr = ctx.createLinearGradient(a.x,a.y,b.x,b.y);
        gr.addColorStop(0, P.erA); gr.addColorStop(1, P.erB);
        ctx.strokeStyle = gr;
        ctx.globalAlpha = dimmed ? 0.16 : 0.85;
        ctx.lineWidth = touchesFocus ? 2.8 : 2.1;
        ctx.setLineDash([6,4]);
      } else {
        ctx.strokeStyle = touchesFocus ? P.edgeHi : P.edge;
        ctx.globalAlpha = dimmed ? 0.25 : 1;
        ctx.lineWidth = touchesFocus ? 1.8 : 0.95;
        ctx.setLineDash([]);
      }
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      ctx.globalAlpha = 1;
    });
    ctx.setLineDash([]);

    nodes.forEach((n,ni)=>{
      const col = P.nt[n.type] || '#64748B';
      const active = isMatch(n);
      const isFocus = focus && (n===focus || neighborIdx.has(ni));
      const dim = ((activeCluster || queryStr) && !active) || (focus && !isFocus);
      ctx.globalAlpha = dim ? 0.22 : 1;

      if(n.cluster){
        const ci = parseInt(n.cluster.slice(1))-1;
        const ccol = P.clusters[ci % P.clusters.length];
        ctx.beginPath(); ctx.arc(n.x,n.y,n.r+7,0,6.283);
        ctx.fillStyle = ccol + (isDark()?'28':'20'); ctx.fill();
        ctx.strokeStyle = ccol + 'AA'; ctx.lineWidth = 1.6; ctx.stroke();
      }
      if(n === selected){
        ctx.beginPath(); ctx.arc(n.x,n.y,n.r+11,0,6.283);
        ctx.strokeStyle = P.phys; ctx.lineWidth = 2.4; ctx.stroke();
      }
      ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,6.283);
      ctx.fillStyle = col; ctx.fill();
      ctx.lineWidth = 1.8; ctx.strokeStyle = isDark()?'#121827':'#FFFFFF'; ctx.stroke();

      if(n===hover || n===selected || (active && (n.cluster || n.degree>=14)) || (queryStr && active)){
        ctx.font='600 10.5px ui-monospace,monospace';
        const lab = n.label.length>18 ? n.label.slice(0,17)+'…' : n.label;
        const tw = ctx.measureText(lab).width + 10;
        const lx = n.x - tw/2, ly = n.y - n.r - 22;
        ctx.fillStyle = P.nodeLabelBg;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(lx, ly, tw, 16, 4); else ctx.rect(lx, ly, tw, 16);
        ctx.fill();
        ctx.fillStyle = P.nodeLabel;
        ctx.textAlign='center';
        ctx.fillText(lab, n.x, ly + 11.5);
      }
      ctx.globalAlpha = 1;
    });
    ctx.restore();
  }

  function fit(pad){
    if(!nodes.length) return;
    const xs=nodes.map(n=>n.x), ys=nodes.map(n=>n.y);
    const x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
    const bw=Math.max(1,x1-x0), bh=Math.max(1,y1-y0);
    view.k = Math.max(.35, Math.min(2.1, Math.min((W-pad*2)/bw, (H-pad*2)/bh)));
    view.x = W/2 - (x0+x1)/2*view.k;
    view.y = H/2 - (y0+y1)/2*view.k;
  }

  function showInspector(n){
    if (!n) { insp.classList.remove('on'); return; }
    const erLinks = ent.links.filter(l=>l.u===n.id || l.v===n.id);
    insp.innerHTML =
      '<div class="row" style="justify-content:space-between;margin-bottom:6px">'+
        '<span class="tag t-cy">'+esc(n.type)+'</span>'+
        '<button class="x" id="inspClose" style="width:24px;height:24px;font-size:11px">✕</button></div>'+
      '<div class="mono" style="font-weight:700;font-size:12.5px;margin-bottom:4px">'+esc(n.label)+'</div>'+
      '<div class="sm">degree '+n.degree+' · '+n.events+' events'+
        (n.cluster ? ' · profile <b style="color:var(--cy2)">'+n.cluster+'</b>' : '')+'</div>'+
      (erLinks.length ? '<div class="sm" style="margin-top:6px">linked to: '+
        erLinks.map(l=>'<span class="tag t-mint" style="margin:2px 3px 0 0">'+
          esc(l.u===n.id?l.v_id:l.u_id)+' ('+l.link_score.toFixed(2)+')</span>').join('')+'</div>' : '')+
      '<div class="row" style="margin-top:10px">'+
        '<button class="btn sm-btn" id="inspEvents">Search in ledger →</button>'+
        (erLinks.length ? '<button class="btn sec sm-btn" id="inspLink">Link detail</button>' : '')+
      '</div>';
    insp.classList.add('on');
    insp.querySelector('#inspClose').onclick = () => { selected = null; showInspector(null); };
    insp.querySelector('#inspEvents').onclick = async () => {
      await go('evidence');
      setTimeout(()=>{ const i=$('#evq'); if(i){ i.value=n.label; $('#evgo').click(); } }, 50);
    };
    const lkBtn = insp.querySelector('#inspLink');
    if (lkBtn) lkBtn.onclick = () => linkDetail(erLinks[0]);
  }

  for(let i=0;i<320;i++) step();
  alpha = 0.25; fit(56);
  let frames = 0;
  function tick(){
    if (!alive) return;
    if(alpha>.085){ step(); frames++; if(frames===60 || frames===140) fit(56); }
    draw();
    rafId = requestAnimationFrame(tick);
  }
  tick();

  bar.querySelectorAll('[data-cl]').forEach(btn=>{
    btn.onclick = () => {
      activeCluster = btn.dataset.cl;
      bar.querySelectorAll('[data-cl]').forEach(b=>{
        b.className = 'tag clickable ' + (b.dataset.cl===activeCluster ? 't-cy' : 't-grey');
      });
    };
  });
  bar.querySelector('#gSearch').oninput = e => { queryStr = e.target.value.trim().toLowerCase(); };
  bar.querySelector('#gZoomIn').onclick = () => {
    const f=1.2; view.x=W/2-(W/2-view.x)*f; view.y=H/2-(H/2-view.y)*f; view.k=Math.min(4,view.k*f);
  };
  bar.querySelector('#gZoomOut').onclick = () => {
    const f=0.82; view.x=W/2-(W/2-view.x)*f; view.y=H/2-(H/2-view.y)*f; view.k=Math.max(.25,view.k*f);
  };
  bar.querySelector('#gFit').onclick = () => fit(56);

  cv.onwheel = e => { e.preventDefault();
    const f = e.deltaY<0?1.12:0.89;
    const mx=e.offsetX, my=e.offsetY;
    view.x = mx - (mx-view.x)*f; view.y = my - (my-view.y)*f;
    view.k = Math.max(.25, Math.min(4, view.k*f));
  };
  cv.onmousedown = e => { drag = {x:e.offsetX-view.x, y:e.offsetY-view.y}; downPt = {x:e.offsetX, y:e.offsetY}; };
  const onUp = e => {
    if (drag && downPt && Math.hypot(e.offsetX-downPt.x, e.offsetY-downPt.y) < 5 && e.target === cv) {
      const mx=(e.offsetX-view.x)/view.k, my=(e.offsetY-view.y)/view.k;
      let best=null, bd=1e9;
      nodes.forEach(n=>{ const d=Math.hypot(n.x-mx,n.y-my); if(d<n.r+9 && d<bd){bd=d;best=n;} });
      selected = best;
      showInspector(best);
    }
    drag=null; downPt=null;
  };
  window.addEventListener('mouseup', onUp);
  cv.onmousemove = e => {
    if(drag){ view.x = e.offsetX-drag.x; view.y = e.offsetY-drag.y; return; }
    const mx=(e.offsetX-view.x)/view.k, my=(e.offsetY-view.y)/view.k;
    let best=null, bd=1e9;
    nodes.forEach(n=>{ const d=Math.hypot(n.x-mx,n.y-my); if(d<n.r+8 && d<bd){bd=d;best=n;} });
    hover = best;
    cv.style.cursor = best ? 'pointer' : 'grab';
    if(best){
      tip.style.opacity=1;
      tip.style.left = Math.min(e.offsetX+14, cv.clientWidth-300)+'px';
      tip.style.top = (e.offsetY+14)+'px';
      tip.innerHTML = '<div style="color:'+(P.nt[best.type]||'#64748B')+';font-weight:700;font-size:11px">'+
        best.type+'</div><div class="mono" style="margin:3px 0 4px;font-weight:700">'+esc(best.label)+'</div>'+
        '<div class="sm">degree '+best.degree+' · '+best.events+' events'+
        (best.cluster?' · profile <b style="color:var(--cy2)">'+best.cluster+'</b>':'')+'</div>';
    } else tip.style.opacity=0;
  };
  cv.onmouseleave = ()=>{ tip.style.opacity=0; hover=null; };

  S.stopGraph = () => {
    alive = false;
    cancelAnimationFrame(rafId);
    window.removeEventListener('mouseup', onUp);
  };
}

/* ====================== KINEMATICS ====================== */
VIEWS.kinematic = async () => {
  const k = S.data.kin || (S.data.kin = await api('/kinematic'));
  const v = el('div','view');
  v.appendChild(head('Kinematic plausibility &amp; alibi spoofing',
    'Consecutive profile positions are evaluated via Haversine distance buffered by sensor uncertainty radii '+
    'against a '+S.case.config.v_max_ms+' m/s ground ceiling. Application-layer fixes contradicted by bracketing '+
    'physical radio records indicate a falsified alibi.'));

  const g = el('div','grid g23');
  const left = el('div','');
  k.anomalies.forEach(a=>{
    const c = el('div','card '+(a.code==='DIGITAL_LOCATION_SPOOF'?'tint-red':'tint-amber'));
    c.style.marginBottom='12px';
    c.innerHTML = '<div class="row" style="justify-content:space-between"><div class="row">'+
      '<span class="alert-k" style="color:var(--'+(a.code==='DIGITAL_LOCATION_SPOOF'?'red':'amber')+')">'+
      a.code+'</span><span class="tag '+sevTag(a.severity)+'">'+a.severity+'</span>'+
      '<span class="tag t-grey">'+a.cluster_id+'</span></div>'+
      '<div class="num" style="font-size:19px;font-weight:800;color:var(--red)">𝒦 '+a.kinematic_score.toFixed(1)+'</div></div>'+
      '<div class="alert-d" style="margin-top:8px">'+esc(a.detail)+'</div>'+
      '<div class="grid g4" style="margin-top:12px;gap:8px;padding:10px;border-radius:8px;background:var(--panel2);border:1px solid var(--line)">'+
        '<div><div class="sm">haversine</div><div class="mono">'+num(a.d_hav_m/1000,2)+' km</div></div>'+
        '<div><div class="sm">buffered</div><div class="mono">'+num(a.d_min_m/1000,2)+' km</div></div>'+
        '<div><div class="sm">Δt</div><div class="mono">'+num(a.dt_s,1)+' s</div></div>'+
        '<div><div class="sm">v required</div><div class="mono" style="color:var(--red);font-weight:700">'+num(a.v_req_ms,1)+' m/s</div></div>'+
      '</div>'+
      '<div class="row" style="margin-top:10px"><button class="btn sec sm-btn" data-e="'+a.flagged_event+'">Inspect flagged record →</button></div>';
    c.querySelector('button').onclick = ()=>provenance(a.flagged_event);
    left.appendChild(c);
  });
  if(!k.anomalies.length) left.appendChild(el('div','card','<div class="empty">no kinematic anomaly detected</div>'));
  g.appendChild(left);

  const mapCard = el('div','card tint-cy');
  mapCard.innerHTML = '<h3>Profile trajectory<em>corrected UTC</em></h3>';
  const map = el('div','map'); mapCard.appendChild(map);
  g.appendChild(mapCard); v.appendChild(g);
  setTimeout(()=>drawMap(map, k), 30);
  return v;
};

function drawMap(host, k){
  const Ppal = pal();
  const tr = (k.tracks||[]).find(t=>t.points.length) || {points:[]};
  const pts = tr.points.filter(p=>p.lat!==null);
  if(!pts.length){ host.innerHTML='<div class="empty">no geo-tagged events</div>'; return; }
  const spoof = new Set(k.anomalies.filter(a=>a.code==='DIGITAL_LOCATION_SPOOF').map(a=>a.flagged_event));
  const real = pts.filter(p=>!spoof.has(p.event_id));
  const base = real.length>1 ? real : pts;
  const W=host.clientWidth||500, H=host.clientHeight||360, P=38;
  const pad = 0.14;
  let la0=Math.min(...base.map(p=>p.lat)), la1=Math.max(...base.map(p=>p.lat));
  let lo0=Math.min(...base.map(p=>p.lon)), lo1=Math.max(...base.map(p=>p.lon));
  const dla=Math.max(1e-4,(la1-la0)), dlo=Math.max(1e-4,(lo1-lo0));
  la0-=dla*pad; la1+=dla*pad; lo0-=dlo*pad; lo1+=dlo*pad;
  const X=lo=>P+(lo-lo0)/(lo1-lo0)*(W-2*P);
  const Y=la=>H-P-(la-la0)/(la1-la0)*(H-2*P);
  const clampX=x=>Math.max(P-8,Math.min(W-P+8,x)), clampY=y=>Math.max(P-8,Math.min(H-P+8,y));
  const off = p => p.lat<la0||p.lat>la1||p.lon<lo0||p.lon>lo1;
  let s='<svg width="100%" height="100%" viewBox="0 0 '+W+' '+H+'"><defs>'+
    '<linearGradient id="tg" x1="0" x2="1"><stop offset="0" stop-color="'+Ppal.erA+'"/><stop offset="1" stop-color="'+Ppal.erB+'"/></linearGradient>'+
    '</defs>';
  for(let i=0;i<=6;i++){
    const y=P+i*(H-2*P)/6, x=P+i*(W-2*P)/6;
    s+='<line x1="'+P+'" y1="'+y+'" x2="'+(W-P)+'" y2="'+y+'" stroke="'+Ppal.grid+'"/>';
    s+='<line x1="'+x+'" y1="'+P+'" x2="'+x+'" y2="'+(H-P)+'" stroke="'+Ppal.grid+'"/>';
  }
  const px = p => [clampX(X(p.lon)), clampY(Y(p.lat))];
  for(let i=0;i<pts.length-1;i++){
    const a=pts[i], b=pts[i+1];
    const bad = spoof.has(a.event_id)||spoof.has(b.event_id);
    const [ax,ay]=px(a), [bx,by]=px(b);
    s+='<line x1="'+ax+'" y1="'+ay+'" x2="'+bx+'" y2="'+by+'" stroke="'+
       (bad?Ppal.spoof:'url(#tg)')+'" stroke-opacity="'+(bad?0.9:0.6)+'" stroke-width="'+(bad?2.4:1.8)+
       '" stroke-dasharray="'+(bad?'6 4':'none')+'"/>';
  }
  pts.forEach(p=>{
    const bad = spoof.has(p.event_id), o = off(p);
    const col = bad?Ppal.spoof:(p.layer==='PHYSICAL'?Ppal.phys:Ppal.app);
    const [x,y]=px(p);
    s+='<circle cx="'+x+'" cy="'+y+'" r="'+(bad?7.5:5)+'" fill="'+col+'" stroke="'+Ppal.badgeBg+'" stroke-width="1.6" opacity="'+(bad?1:.92)+'">'+
       '<title>'+esc(p.etype+'  '+hhmm(p.t)+'  '+p.actor+'  ['+p.lat.toFixed(4)+', '+p.lon.toFixed(4)+']')+
       '</title></circle>';
    if(bad){
      s+='<circle cx="'+x+'" cy="'+y+'" r="14" fill="none" stroke="'+Ppal.spoof+'" opacity=".68" stroke-width="1.6"/>'+
         '<circle cx="'+x+'" cy="'+y+'" r="22" fill="none" stroke="'+Ppal.spoof+'" opacity=".3"/>';
      if(o) s+='<text x="'+Math.min(x+6,W-165)+'" y="'+Math.max(P+14,y-26)+'" fill="'+Ppal.spoof+'" font-size="10.5" font-weight="700" '+
        'font-family="ui-monospace,monospace">off-map · '+p.lat.toFixed(3)+', '+p.lon.toFixed(3)+'</text>';
    }
  });
  s+='<text x="'+P+'" y="'+(P-14)+'" fill="'+Ppal.axis+'" font-size="10" font-family="ui-monospace,monospace">'+
     'frame scaled to genuine positions · '+(dla*111).toFixed(1)+' km × '+(dlo*102).toFixed(1)+' km</text>';
  s+='</svg>';
  host.innerHTML = s;
  host.insertAdjacentHTML('beforeend',
    '<div class="legend" style="left:auto;right:12px;bottom:10px;max-width:none">'+
    '<div class="lg"><i style="background:'+Ppal.phys+'"></i>physical layer</div>'+
    '<div class="lg"><i style="background:'+Ppal.app+'"></i>application layer</div>'+
    '<div class="lg"><i style="background:'+Ppal.spoof+'"></i>falsified fix</div></div>');
}

/* ====================== MONEY ====================== */
VIEWS.money = async () => {
  const f = S.data.fin || (S.data.fin = await api('/finance'));
  const v = el('div','view');
  v.appendChild(head('Financial layering &amp; mule-flow analysis',
    'Pass-through velocity is scored from balance ratio ρ, median hold time, and leg fan. '+
    'Edmonds-Karp max-flow provably traces funds from the victim account to the cash-out sink.'));

  const mf = f.max_flow || {};
  const top = el('div','grid g4');
  [['traced by max-flow', mf.traced_inr!==undefined?inr(mf.traced_inr):'—','tint-teal','t-mint','Edmonds-Karp'],
   ['total debited', inr(f.total_debited_inr),'tint-cy','t-cy','victim out'],
   ['mule accounts', f.mules.length,'tint-red','t-red','pass-through'],
   ['transaction legs', f.legs.length,'tint-violet','t-violet','ledger edges']]
   .forEach(([l,val,tintCls,tagCls,sub])=>{ const k=el('div','card '+tintCls);
     k.innerHTML='<div class="kpi-head"><h3>'+l+'</h3><span class="tag '+tagCls+'">'+sub+'</span></div>'+
       '<div class="big" style="font-size:'+(String(val).length>12?'21px':'27px')+'">'+val+'</div>'; top.appendChild(k); });
  v.appendChild(top);

  const flowCard = el('div','card'); flowCard.style.marginTop='14px';
  flowCard.innerHTML = '<h3>Siphon topology<em>victim → pass-through mules → cash-out</em></h3>';
  const host = el('div'); host.style.cssText='height:310px;position:relative';
  flowCard.appendChild(host); v.appendChild(flowCard);

  const t = el('div','card'); t.style.marginTop='14px';
  t.innerHTML = '<h3>Pass-through scoring<em>MuleScore ≥ '+S.case.config.mule_threshold+' flags a mule</em></h3>';
  const tw = el('div','tw');
  tw.innerHTML = '<table><thead><tr><th>account</th><th class="num">in</th><th class="num">out</th>'+
    '<th class="num">ρ flow</th><th class="num">median hold</th><th class="num">legs in/out</th>'+
    '<th class="num">fan</th><th class="num">MuleScore</th></tr></thead><tbody>'+
    f.accounts.slice(0,20).map(a=>'<tr><td class="mono">'+esc(a.account)+
      (a.is_mule?' <span class="tag t-red">MULE</span>':'')+'</td>'+
      '<td class="num">'+inr(a.in_inr)+'</td><td class="num">'+inr(a.out_inr)+'</td>'+
      '<td class="num">'+a.rho_flow.toFixed(4)+'</td><td class="num">'+num(a.hold_median_s,1)+' s</td>'+
      '<td class="num">'+a.legs_in+'/'+a.legs_out+'</td><td class="num">'+a.fan_factor.toFixed(3)+'</td>'+
      '<td class="num" style="font-weight:700;color:'+(a.is_mule?'var(--red)':'var(--txt2)')+'">'+
      a.mule_score.toFixed(4)+'</td></tr>').join('')+'</tbody></table>';
  t.appendChild(tw); v.appendChild(t);
  setTimeout(()=>drawFlow(host, f), 30);
  return v;
};

function drawFlow(host, f){
  const Ppal = pal();
  const mules = f.mules.map(m=>m.account);
  const victim = (f.max_flow||{}).source, cash = (f.max_flow||{}).sink;
  if(!victim || !mules.length){ host.innerHTML='<div class="empty">no layering detected</div>'; return; }
  const W=host.clientWidth||800, H=310;
  const cols=[[victim],mules,[cash]];
  const xs=[W*0.14, W*0.5, W*0.86];
  const pos={};
  cols.forEach((c,ci)=>c.forEach((n,i)=>{ pos[n]={x:xs[ci], y:26+(H-46)*(i+1)/(c.length+1)}; }));
  const mx = Math.max(...f.graph_edges.map(e=>e.amount),1);
  let s='<svg width="100%" height="'+H+'" viewBox="0 0 '+W+' '+H+'"><defs>'+
    '<linearGradient id="fg" x1="0" x2="1"><stop offset="0" stop-color="'+Ppal.phys+'" stop-opacity=".78"/>'+
    '<stop offset="0.5" stop-color="#7C3AED" stop-opacity=".74"/>'+
    '<stop offset="1" stop-color="'+Ppal.spoof+'" stop-opacity=".78"/></linearGradient></defs>';
  [['VICTIM SOURCE',xs[0]],['MULE LAYER',xs[1]],['CASH-OUT SINK',xs[2]]].forEach(([lbl,x])=>{
    s+='<text x="'+x+'" y="18" text-anchor="middle" fill="'+Ppal.axis+'" font-size="10" font-weight="700" '+
       'letter-spacing="1.2">'+lbl+'</text>';
  });
  f.graph_edges.forEach(e=>{
    const a=pos[e.src], b=pos[e.dst]; if(!a||!b) return;
    const w = Math.max(2.5, e.amount/mx*22);
    const mxp=(a.x+b.x)/2, myp=(a.y+b.y)/2;
    s+='<path d="M'+a.x+' '+a.y+' C'+mxp+' '+a.y+' '+mxp+' '+b.y+' '+b.x+' '+b.y+
       '" fill="none" stroke="url(#fg)" stroke-width="'+w+'" opacity=".68"><title>'+
       esc(e.src+' → '+e.dst+'  ₹'+num(e.amount,2))+'</title></path>';
    s+='<rect x="'+(mxp-34)+'" y="'+(myp-9)+'" width="68" height="18" rx="9" fill="'+Ppal.badgeBg+'" stroke="'+Ppal.badgeBd+'"/>'+
       '<text x="'+mxp+'" y="'+(myp+3.5)+'" text-anchor="middle" fill="'+Ppal.flowTxt+'" font-size="9.5" '+
       'font-family="ui-monospace,monospace" font-weight="600">₹'+num(e.amount/1000,1)+'k</text>';
  });
  Object.entries(pos).forEach(([n,p])=>{
    const col = n===victim ? Ppal.phys : (n===cash ? Ppal.spoof : Ppal.app);
    s+='<circle cx="'+p.x+'" cy="'+p.y+'" r="11" fill="'+col+'" stroke="'+Ppal.badgeBg+'" stroke-width="2"/>'+
       '<circle cx="'+p.x+'" cy="'+p.y+'" r="18" fill="none" stroke="'+col+'" opacity=".35" stroke-width="1.6"/>'+
       '<text x="'+p.x+'" y="'+(p.y+32)+'" text-anchor="middle" fill="'+Ppal.flowTxt+'" '+
       'font-family="ui-monospace,monospace" font-size="11" font-weight="600">'+esc(n)+'</text>';
  });
  s+='</svg>';
  host.innerHTML=s;
}

/* ====================== HYPOTHESES ====================== */
VIEWS.hypo = async () => {
  const h = S.data.hyp || (S.data.hyp = await api('/hypotheses'));
  const v = el('div','view');
  v.appendChild(head('Hypothesis comparator',
    'Competing explanations scored on an explicit ordinal scale (+30 exact match, +20 strong corroboration, '+
    '+10 circumstantial, −20 contradiction) over redundancy-clustered facts.'));

  const g = el('div','grid g3');
  const mx = Math.max(...h.hypotheses.map(x=>Math.abs(x.support)),1);
  h.hypotheses.forEach(x=>{
    const lead = h.ranked[0]===x.id;
    const c = el('div','card '+(lead?'tint-teal':'tint-red'));
    if (lead) c.style.borderColor = 'var(--teal)';
    c.innerHTML = '<div class="row" style="justify-content:space-between">'+
      '<span class="tag '+(lead?'t-teal':'t-grey')+'">'+x.id+(lead?' · best supported':'')+'</span>'+
      '<span class="num" style="font-size:23px;font-weight:800;color:'+
      (x.support>=0?'var(--teal)':'var(--red)')+'">'+(x.support>=0?'+':'')+x.support+'</span></div>'+
      '<div style="margin-top:10px;font-weight:700;font-size:14px;line-height:1.4;color:var(--txt)">'+esc(x.title)+'</div>'+
      '<div class="sm" style="margin-top:6px">'+esc(x.detail)+'</div>'+
      '<div class="bar" style="margin-top:12px"><i style="width:'+(Math.abs(x.support)/mx*100)+'%;'+
      (x.support<0?'background:linear-gradient(90deg,#E11D48,#F59E0B)':'background:linear-gradient(90deg,#0D9488,#2563EB)')+'"></i></div>';
    g.appendChild(c);
  });
  v.appendChild(g);

  const t = el('div','card'); t.style.marginTop='14px';
  t.innerHTML = '<h3>Evidentiary clusters<em>'+h.cluster_count+' independent clusters from '+
    h.scored_event_count+' scored records</em></h3>';
  const tw = el('div','tw');
  tw.innerHTML = '<table><thead><tr><th>cluster</th><th>band</th><th>representative fact</th>'+
    '<th class="num">H1</th><th class="num">H2</th><th class="num">H3</th><th class="num">merged</th></tr></thead><tbody>'+
    h.clusters.map(c=>'<tr data-e="'+c.representative+'" style="cursor:pointer">'+
      '<td class="mono">'+c.cluster_id+'</td><td><span class="tag '+
      (c.band==='EXACT_MATCH'?'t-mint':(c.band==='STRONG'?'t-cy':'t-grey'))+'">'+
      (c.band||'').toLowerCase().replace('_',' ')+'</span></td>'+
      '<td style="max-width:520px;color:var(--txt)">'+esc(c.narrative||'')+
      '<div class="sm" style="margin-top:4px;font-style:italic">'+esc(c.rationale||'')+'</div></td>'+
      ['H1','H2','H3'].map(k=>'<td class="num" style="font-weight:600;color:'+
        (c.support[k]>0?'var(--teal)':(c.support[k]<0?'var(--red)':'var(--txt3)'))+'">'+
        (c.support[k]>0?'+':'')+c.support[k]+'</td>').join('')+
      '<td class="num">'+c.redundant_count+'</td></tr>').join('')+'</tbody></table>';
  tw.querySelectorAll('tr[data-e]').forEach(tr=>tr.onclick=()=>provenance(tr.dataset.e));
  t.appendChild(tw); v.appendChild(t);
  return v;
};

/* ====================== COUNTERFACTUAL ====================== */
VIEWS.whatif = async () => {
  const v = el('div','view');
  v.appendChild(head('Counterfactual evidence shaving',
    'Toggle an exhibit off — simulating a defence admissibility challenge — and re-run the entire deterministic '+
    'pipeline in memory to quantify severed links, broken causal edges, and support delta.'));

  const g = el('div','grid g23');
  const ctl = el('div','card tint-violet');
  ctl.innerHTML = '<h3>Active exhibits</h3>'+
    '<div class="row" style="margin-bottom:12px;gap:6px">'+
      '<button class="btn sec sm-btn" id="cfCctv">Exclude CCTV DVR</button>'+
      '<button class="btn sec sm-btn" id="cfUfdr">Exclude Burner UFDR</button>'+
      '<button class="btn sec sm-btn" id="cfGps">Exclude GPS Log</button>'+
      '<button class="btn sec sm-btn" id="cfReset">Restore all</button>'+
    '</div>';
  S.case.files.forEach(f=>{
    const on = !S.excluded.has(f.file_id);
    const t = el('div','tgl '+(on?'on':'off'));
    t.innerHTML = '<div><div style="font-weight:700;font-size:12.5px;color:var(--txt)">'+f.file_id+'</div>'+
      '<div class="sm">'+esc(f.filename)+' · '+f.record_count+' records</div></div><div class="sw"></div>';
    t.onclick = () => { S.excluded.has(f.file_id)?S.excluded.delete(f.file_id):S.excluded.add(f.file_id); run(); };
    ctl.appendChild(t);
  });
  const btn = el('button','btn','Re-run counterfactual');
  btn.style.marginTop='6px'; btn.onclick=run; ctl.appendChild(btn);
  g.appendChild(ctl);
  const out = el('div',''); g.appendChild(out); v.appendChild(g);

  ctl.querySelector('#cfCctv').onclick = () => { S.excluded=new Set(['SRC_CCTV_01']); run(); };
  ctl.querySelector('#cfUfdr').onclick = () => { S.excluded=new Set(['SRC_UFDR_01']); run(); };
  ctl.querySelector('#cfGps').onclick  = () => { S.excluded=new Set(['SRC_GPS_01']); run(); };
  ctl.querySelector('#cfReset').onclick= () => { S.excluded.clear(); run(); };

  async function run(){
    ctl.querySelectorAll('.tgl').forEach((t,i)=>{
      const on = !S.excluded.has(S.case.files[i].file_id);
      t.className = 'tgl '+(on?'on':'off');
    });
    if(!S.excluded.size){ out.innerHTML = '<div class="card"><div class="empty">'+
      'All six exhibits active — toggle one off or pick a preset to measure its exact evidentiary contribution.</div></div>'; return; }
    busy(true,'re-running pipeline…');
    out.innerHTML = '<div class="card"><div class="empty">re-running…</div></div>';
    let r; try { r = await post('/counterfactual',{excluded_files:[...S.excluded], excluded_events:[]}); }
    finally { busy(false); }
    let h = '<div class="card tint-cy"><h3>Attribution delta<em>'+r.runtime_ms.toFixed(0)+' ms re-run</em></h3>';
    ['H1','H2','H3'].forEach(k=>{
      const d = r.delta_support[k];
      const grad = d>0 ? 'linear-gradient(90deg,#D97706,#E11D48)' : 'linear-gradient(90deg,#0D9488,#2563EB)';
      h += '<div class="diverge"><div><b style="font-family:var(--mono);color:var(--cy2)">'+k+'</b>'+
        '<div class="sm">'+r.support_before[k]+' → '+r.support_after[k]+'</div></div>'+
        '<div class="dv-track"><div class="dv-fill" style="left:50%;width:'+
        Math.min(48,Math.abs(d)/Math.max(1,Math.max(...Object.values(r.delta_support).map(Math.abs)))*48)+
        '%;background:'+grad+'"></div></div>'+
        '<div class="num" style="font-weight:700;color:'+(d>0?'var(--amber)':'var(--teal)')+'">'+(d>0?'−':'+')+Math.abs(d)+'</div></div>';
    });
    h += '<div class="sm">Δ shows the support carried by the excluded exhibit(s).</div></div>';

    h += '<div class="card" style="margin-top:14px"><h3>Severed inferences</h3>';
    h += '<div class="sm" style="margin-bottom:8px">Entity links lost ('+r.severed_entity_links.length+')</div>';
    h += r.severed_entity_links.length ? '<div class="proof">'+r.severed_entity_links.map(l=>
      '<div class="pf"><b>link</b><span>'+esc(l.u)+'  ↔  '+esc(l.v)+'</span></div>').join('')+'</div>'
      : '<div class="sm">none</div>';
    h += '<div class="sm" style="margin:12px 0 8px">Causal edges lost ('+r.severed_causal_edges.length+')</div>';
    h += r.severed_causal_edges.length ? '<div class="proof">'+r.severed_causal_edges.map(e=>
      '<div class="pf"><b>edge</b><span>'+esc(e.src)+' → '+esc(e.dst)+'</span></div>').join('')+'</div>'
      : '<div class="sm">none</div>';
    h += '</div>';

    h += '<div class="card" style="margin-top:14px"><h3>Pipeline after exclusion</h3><div class="grid g3">';
    [['records',r.counts_after.events,r.counts_before.events],
     ['entity links',r.counts_after.entity_links,r.counts_before.entity_links],
     ['causal edges',r.counts_after.causal_edges,r.counts_before.causal_edges],
     ['kinematic alerts',r.anomalies_after,r.counts_before.anomalies],
     ['mule accounts',r.mules_after,r.counts_before.mules],
     ['clock RMSE',r.clock.rmse_after.toFixed(3)+'s',r.clock.rmse_before.toFixed(3)+'s']]
     .forEach(([l,a,b])=>{ h+='<div><div class="sm">'+l+'</div><div class="mono" style="font-size:15px;font-weight:700">'+
       a+' <span style="color:var(--txt3);font-size:11px;font-weight:400">was '+b+'</span></div></div>'; });
    h += '</div>';
    if(r.clock.unanchored_after.length)
      h += '<div class="alert high" style="margin-top:12px"><div><div class="alert-k">CLOCK_ANCHOR_LOST</div>'+
        '<div class="alert-d">These exhibits fall outside the reference connected component and are no longer '+
        'clock-anchored: '+r.clock.unanchored_after.join(', ')+'</div></div></div>';
    h += '<div class="sm" style="margin-top:12px">Profiles after exclusion</div>'+
      r.clusters_after.map(c=>'<div class="mono" style="margin-top:4px">'+esc(c)+'</div>').join('');
    h += '</div>';
    out.innerHTML = h;
  }
  run();
  return v;
};

/* ====================== EVIDENCE ====================== */
VIEWS.evidence = async () => {
  const v = el('div','view');
  v.appendChild(head('Evidence ledger',
    'Every parsed record, bound to the exact byte range of its raw exhibit. Click any row to re-read '+
    'those bytes from disk and validate its Merkle inclusion proof.'));
  const bar = el('div','card');
  bar.innerHTML = '<div class="row">'+
    '<input type="search" id="evq" placeholder="search identifiers, narrative, event id…" style="flex:1;min-width:240px"/>'+
    '<select id="evf" style="width:200px"></select><select id="evt" style="width:220px"></select>'+
    '<button class="btn" id="evgo">Search</button></div>';
  v.appendChild(bar);
  const out = el('div','card'); out.style.marginTop='14px'; v.appendChild(out);

  const load = async () => {
    const q = $('#evq').value, f = $('#evf').value, t = $('#evt').value;
    out.innerHTML = '<div class="empty">loading…</div>';
    const d = await api('/events?limit=500'+(q?'&q='+encodeURIComponent(q):'')+
      (f?'&file_id='+f:'')+(t?'&event_type='+t:''));
    if(!$('#evf').options.length){
      $('#evf').innerHTML = '<option value="">all exhibits</option>'+
        S.case.files.map(x=>'<option>'+x.file_id+'</option>').join('');
      $('#evt').innerHTML = '<option value="">all event types</option>'+
        d.event_types.map(x=>'<option>'+x+'</option>').join('');
    }
    out.innerHTML = '<h3>Records<em>showing '+d.events.length+' of '+d.total+'</em></h3>';
    const tw = el('div','tw'); tw.style.maxHeight='640px';
    tw.innerHTML = '<table><thead><tr><th>corrected UTC</th><th>exhibit</th><th>type</th>'+
      '<th>actor</th><th>target</th><th>narrative</th><th class="num">bytes</th></tr></thead><tbody>'+
      d.events.map(e=>{
        const stMeta = SRC_THEME[e.file_id] || { tag:'t-grey' };
        return '<tr data-e="'+e.event_id+'" style="cursor:pointer">'+
          '<td class="mono">'+hhmm(e.corrected_timestamp_epoch)+'</td>'+
          '<td><span class="tag '+stMeta.tag+'">'+e.file_id.replace('SRC_','').replace('_01','')+'</span></td>'+
          '<td class="mono" style="color:var(--cy2);font-weight:600">'+e.event_type+'</td>'+
          '<td class="mono">'+esc(e.actor_id)+'</td><td class="mono">'+esc(e.target_id)+'</td>'+
          '<td style="max-width:520px;color:var(--txt)">'+esc(e.narrative)+'</td>'+
          '<td class="num">'+e.byte_offset_start+'–'+e.byte_offset_end+'</td></tr>';
      }).join('')+'</tbody></table>';
    tw.querySelectorAll('tr[data-e]').forEach(tr=>tr.onclick=()=>provenance(tr.dataset.e));
    out.appendChild(tw);
  };
  setTimeout(()=>{ load(); $('#evgo').onclick=load;
    $('#evq').onkeydown=e=>{if(e.key==='Enter')load();};
    $('#evf').onchange=load; $('#evt').onchange=load; }, 20);
  return v;
};

/* ====================== COPILOT ====================== */
VIEWS.copilot = async () => {
  const v = el('div','view');
  v.appendChild(head('Air-gapped query copilot',
    'Natural-language investigator questions translate into a structured JSON query AST (local Ollama with '+
    '2 s timeout, or deterministic regex fallback) — zero outbound network traffic.'));
  const bar = el('div','card tint-cy');
  bar.innerHTML = '<div class="row"><input type="text" id="q" style="flex:1;min-width:280px" '+
    'placeholder="e.g. show all events involving the burner phone within 20 minutes of the SIM swap"/>'+
    '<button class="btn" id="qgo">Ask</button></div>'+
    '<div class="row" style="margin-top:10px;gap:7px" id="qex"></div>';
  v.appendChild(bar);
  const out = el('div',''); out.style.marginTop='14px'; v.appendChild(out);
  const examples = ['show all events involving 352099118822771 within 20 minutes of the SIM swap',
                    'every ATM withdrawal and plate reading','wifi associations between 14:10 and 14:30',
                    'all UPI transfers after 14:30','what did vehicle DL8CAF5031 do'];
  setTimeout(()=>{
    $('#qex').innerHTML = examples.map(e=>'<span class="tag clickable t-grey">'+esc(e)+'</span>').join('');
    $('#qex').querySelectorAll('.tag').forEach((t,i)=>t.onclick=()=>{ $('#q').value=examples[i]; ask(); });
    $('#qgo').onclick=ask; $('#q').onkeydown=e=>{if(e.key==='Enter')ask();};
  },20);
  async function ask(){
    const q = $('#q').value.trim(); if(!q) return;
    busy(true,'parsing query…'); out.innerHTML='<div class="card"><div class="empty">parsing query…</div></div>';
    let r; try{ r = await post('/query',{question:q,use_llm:true}); } finally { busy(false); }
    const astClean = {
      actor_types:r.ast.actor_types, actor_ids:r.ast.actor_ids,
      time_window_utc:r.ast.time_window_utc, event_types:r.ast.event_types
    };
    let h = '<div class="card tint-violet"><h3>Compiled query AST<em>parser: '+esc(r.ast.parser)+'</em></h3>'+
      '<div class="row" style="margin-bottom:10px;gap:8px">'+
        '<span class="tag t-cy">types: '+esc((astClean.actor_types||[]).join(', '))+'</span>'+
        '<span class="tag t-violet">events: '+esc((astClean.event_types||[]).join(', '))+'</span>'+
        (astClean.actor_ids?.length?'<span class="tag t-mint">ids: '+esc(astClean.actor_ids.join(', '))+'</span>':'')+
        '<span class="tag t-grey">window: '+esc((astClean.time_window_utc||[]).join(' → '))+'</span>'+
      '</div>'+
      '<pre class="raw">'+esc(JSON.stringify(astClean,null,2))+'</pre></div>';
    h += '<div class="card" style="margin-top:14px"><h3>Matches<em>'+r.match_count+' records</em></h3>';
    h += '<div class="tw" style="max-height:560px"><table><thead><tr><th>UTC</th><th>type</th><th>actor</th>'+
      '<th>narrative</th></tr></thead><tbody>'+r.events.map(e=>'<tr data-e="'+e.event_id+'" style="cursor:pointer">'+
      '<td class="mono">'+hhmm(e.t)+'</td><td class="mono" style="color:var(--cy2);font-weight:600">'+e.event_type+'</td>'+
      '<td class="mono">'+esc(e.actor_id)+'</td><td style="color:var(--txt)">'+esc(e.narrative)+'</td></tr>').join('')+
      '</tbody></table></div></div>';
    out.innerHTML = h;
    out.querySelectorAll('tr[data-e]').forEach(tr=>tr.onclick=()=>provenance(tr.dataset.e));
  }
  return v;
};

/* ====================== BENCHMARK ====================== */
VIEWS.bench = async () => {
  busy(true,'running benchmark…');
  let m; try { m = S.data.metrics || (S.data.metrics = await api('/metrics')); } finally { busy(false); }
  const v = el('div','view');
  const verBtn = el('button','btn sec sm-btn','Re-verify all Merkle proofs');
  verBtn.onclick = async () => {
    busy(true,'verifying bytes…');
    try {
      const vr = await api('/verify');
      toast('Verified '+vr.events_verified+' records ('+vr.verification_rate+'%)');
    } finally { busy(false); }
  };
  v.appendChild(head('Benchmark evaluation',
    'Scored against synthetic benchmark ground truth: clock offset RMSE, pairwise entity resolution, '+
    'causal attack chain F1, spoofing & mule recall, and byte-level Merkle verification.', verBtn));

  const hd = m.headline;
  const g = el('div','grid g4');
  [['RMSE β', hd.RMSE_beta_s.toFixed(3)+' s','tint-teal','t-mint','target ≤ 1.800 s'],
   ['entity F1', hd.entity_F1.toFixed(3),'tint-cy','t-cy','pairwise closure'],
   ['causal F1', hd.causal_F1.toFixed(3),'tint-violet','t-violet','arborescence'],
   ['provenance', hd.provenance_verification_rate_pct.toFixed(1)+'%','tint-mint','t-mint','Merkle validated'],
   ['spoof recall', (hd.spoof_recall*100).toFixed(0)+'%','tint-red','t-red','GPS alibi'],
   ['mule recall', (hd.mule_recall*100).toFixed(0)+'%','tint-amber','t-amber','pass-through'],
   ['citation precision', (hd.citation_precision*100).toFixed(0)+'%','tint-teal','t-teal','deterministic'],
   ['hallucination', (hd.hallucination_rate*100).toFixed(0)+'%','tint-cy','t-mint','no LLM']]
   .forEach(([l,val,tintCls,tagCls,s])=>{ const k=el('div','card '+tintCls);
     k.innerHTML='<div class="kpi-head"><h3>'+l+'</h3><span class="tag '+tagCls+'">'+s+'</span></div>'+
       '<div class="big">'+val+'</div>'; g.appendChild(k); });
  v.appendChild(g);

  const d = el('div','grid g2'); d.style.marginTop='14px';
  const c1 = el('div','card');
  c1.innerHTML = '<h3>Clock-offset estimation error<em>'+m.clock_offset_estimation.anchors_used+' anchors</em></h3>'+
    '<div class="tw"><table><thead><tr><th>exhibit</th><th class="num">error (s)</th></tr></thead><tbody>'+
    Object.entries(m.clock_offset_estimation.per_file_error_s).map(([k,x])=>
      '<tr><td class="mono">'+k+'</td><td class="num" style="font-weight:600;color:'+
      (Math.abs(x)<1?'var(--mint)':'var(--amber)')+'">'+(x>=0?'+':'')+x.toFixed(3)+'</td></tr>').join('')+
    '</tbody></table></div><div class="sm" style="margin-top:10px">MAE '+
    m.clock_offset_estimation.mae_beta_s.toFixed(4)+' s · RMSE '+
    m.clock_offset_estimation.rmse_beta_s.toFixed(4)+' s · '+
    (m.clock_offset_estimation.pass?'<span class="tag t-mint">PASS</span>':'<span class="tag t-red">FAIL</span>')+'</div>';
  d.appendChild(c1);

  const c2 = el('div','card');
  const e=m.entity_resolution, a=m.causal_chain;
  c2.innerHTML = '<h3>Resolution &amp; reconstruction</h3>'+
    '<div class="tw"><table><thead><tr><th>metric</th><th class="num">precision</th><th class="num">recall</th>'+
    '<th class="num">F1</th><th class="num">TP/pred/GT</th></tr></thead><tbody>'+
    '<tr><td>entity pairs</td><td class="num">'+e.precision.toFixed(3)+'</td><td class="num">'+e.recall.toFixed(3)+
    '</td><td class="num" style="color:var(--mint);font-weight:700">'+e.f1.toFixed(3)+'</td><td class="num">'+
    e.true_positives+'/'+e.pred_pairs+'/'+e.gt_pairs+'</td></tr>'+
    '<tr><td>causal edges</td><td class="num">'+a.precision.toFixed(3)+'</td><td class="num">'+a.recall.toFixed(3)+
    '</td><td class="num" style="color:var(--mint);font-weight:700">'+a.f1.toFixed(3)+'</td><td class="num">'+
    a.true_positives+'/'+a.pred_edges+'/'+a.gt_edges+'</td></tr></tbody></table></div>'+
    '<div class="sm" style="margin-top:10px">detectors: SIM-swap '+(m.detectors.sim_swap_detected?'✔':'✘')+
    ' · burner pair '+(m.detectors.burner_pair_detected?'✔':'✘')+
    ' · split custody '+(m.detectors.split_custody_detected?'✔':'✘')+
    ' · media flags: '+m.detectors.media_tamper_flags.join(', ')+'</div>'+
    '<div class="sm" style="margin-top:6px">max-flow traced '+inr(m.detectors.traced_inr)+
    ' vs expected '+inr(m.detectors.expected_traced_inr)+' → '+
    (m.detectors.traced_match?'<span class="tag t-mint">MATCH</span>':'<span class="tag t-red">MISMATCH</span>')+'</div>';
  d.appendChild(c2); v.appendChild(d);

  const p = el('div','card tint-teal'); p.style.marginTop='14px';
  p.innerHTML = '<h3>Cryptographic provenance verification</h3>'+
    '<div class="sm">Every cited byte range was re-read from disk, re-hashed as a domain-separated '+
    'Merkle leaf, and validated against the per-exhibit Merkle root.</div>'+
    '<div class="grid g4" style="margin-top:12px">'+
    '<div><div class="sm">verified</div><div class="big" style="color:var(--mint);font-size:24px">'+
      m.provenance.events_verified+'</div></div>'+
    '<div><div class="sm">failures</div><div class="big" style="font-size:24px;color:'+
      (m.provenance.events_failed?'var(--red)':'var(--mint)')+'">'+m.provenance.events_failed+'</div></div>'+
    '<div><div class="sm">match rate</div><div class="big" style="color:var(--mint);font-size:24px">'+
      m.provenance.verification_rate.toFixed(1)+'%</div></div>'+
    '<div><div class="sm">file digests</div><div class="big" style="color:var(--mint);font-size:24px">'+
      (m.provenance.file_digests_match?'MATCH':'FAIL')+'</div></div></div>';
  v.appendChild(p);
  return v;
};

/* ====================== PROVENANCE DRAWER ====================== */
function openDrawer(title, sub){
  $('#dTitle').textContent = title; $('#dSub').textContent = sub||'';
  $('#drawer').classList.add('on'); $('#scrim').classList.add('on');
}
function closeDrawer(){ $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); }
$('#dClose').onclick = closeDrawer; $('#scrim').onclick = closeDrawer;
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDrawer(); });

async function provenance(eid){
  if(!eid) return;
  openDrawer('Byte-offset provenance', eid);
  const b = $('#dBody'); b.innerHTML = '<div class="empty">re-reading raw bytes…</div>';
  let p; try { p = await api('/provenance/'+encodeURIComponent(eid)); }
  catch(e){ b.innerHTML = '<div class="empty">'+esc(e.message)+'</div>'; return; }
  const ok = p.leaf_match && p.proof_valid;
  b.innerHTML =
    '<div class="row" style="margin-bottom:14px">'+
      '<span class="tag '+(ok?'t-mint':'t-red')+'">'+(ok?'VERIFIED AGAINST RAW EXHIBIT':'VERIFICATION FAILED')+'</span>'+
      '<span class="tag t-grey">'+esc(p.filename)+'</span></div>'+
    '<dl class="kv">'+
      '<dt>raw log value</dt><dd>'+esc(p.raw_timestamp_utc)+'</dd>'+
      '<dt>clock correction</dt><dd style="color:var(--cy2);font-weight:700">'+(p.clock_offset_applied_sec>=0?'+':'')+
        p.clock_offset_applied_sec.toFixed(3)+' s</dd>'+
      '<dt>corrected UTC</dt><dd style="color:var(--mint);font-weight:700">'+esc(p.corrected_timestamp_utc)+'</dd>'+
      '<dt>byte range</dt><dd>'+p.byte_offset_start+' – '+p.byte_offset_end+
        ' ('+(p.byte_offset_end-p.byte_offset_start)+' bytes)</dd>'+
      '<dt>leaf (stored)</dt><dd>'+p.leaf_sha256_stored+'</dd>'+
      '<dt>leaf (re-hashed)</dt><dd style="color:'+(p.leaf_match?'var(--mint)':'var(--red)')+'">'+
        p.leaf_sha256_recomputed+'</dd>'+
      '<dt>Merkle root</dt><dd style="color:var(--violet)">'+p.merkle_root+'</dd>'+
      '<dt>exhibit SHA-256</dt><dd>'+p.file_sha256+'</dd>'+
    '</dl>'+
    '<h3 style="font-size:11px;letter-spacing:.1em;color:var(--txt3);margin:4px 0 8px;text-transform:uppercase">Raw bytes on disk</h3>'+
    '<pre class="raw">'+esc(p.raw_bytes)+'</pre>'+
    '<h3 style="font-size:11px;letter-spacing:.1em;color:var(--txt3);margin:16px 0 8px;text-transform:uppercase">'+
      'Merkle inclusion proof ('+p.merkle_proof.length+' siblings, O(log₂ N))</h3>'+
    '<div class="proof">'+p.merkle_proof.map(s=>'<div class="pf"><b>L'+s.level+' '+s.position+
      '</b><span>'+s.hash+'</span></div>').join('')+'</div>'+
    '<div class="row" style="margin-top:14px"><span class="tag '+(p.proof_valid?'t-mint':'t-red')+'">'+
      (p.proof_valid?'proof recomputes the published Merkle root':'proof does not validate')+'</span></div>';
}

/* ====================== PDF ====================== */
$('#btnPdf').onclick = async () => {
  busy(true,'rendering dossier…'); toast('building BSA §63(4)(c) dossier…');
  try{
    const r = await fetch(API + '/export-section63-pdf');
    const blob = await r.blob();
    const u = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href=u; a.download='KALA_NETRA_BSA_Sec63_Dossier.pdf'; a.click();
    URL.revokeObjectURL(u);
    toast('dossier downloaded');
  } catch(e){ toast('export failed: '+e.message); }
  finally { busy(false); }
};

boot();
