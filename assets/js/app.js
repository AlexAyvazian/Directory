/* County Employee Intelligence Atlas — unified Map | Directory application.
   One dataset (window.ATLAS_DATA) and one selection state shared by both views. */
(function () {
'use strict';
const D = window.ATLAS_DATA, TOPO = window.US_ATLAS;

/* ------------------------------------------------------------------ data indexes */
const STATES = D.states;
const STATE_BY = Object.fromEntries(STATES.map(s => [s.abbr, s]));
const ABBR_BY_FIPS = Object.fromEntries(STATES.map(s => [s.fips, s.abbr]));
const J = D.jurisdictions;
const JID = new Map(J.map(j => [j.id, j]));
const byAbbr = new Map(), byFips = new Map();
J.forEach(j => {
  if (!byAbbr.has(j.abbr)) byAbbr.set(j.abbr, []);
  byAbbr.get(j.abbr).push(j);
  if (j.fips) { if (!byFips.has(j.fips)) byFips.set(j.fips, []); byFips.get(j.fips).push(j); }
});
const RECS = J.filter(j => j.contacts); 
const recsByAbbr = new Map(); RECS.filter(j=>j.level!=='state').forEach(j => { if (!recsByAbbr.has(j.abbr)) recsByAbbr.set(j.abbr, []); recsByAbbr.get(j.abbr).push(j); });
const STATES_WITH_DATA = new Set(RECS.map(j => j.abbr));

/* ------------------------------------------------------------------ shared selection */
const sel = { view: 'map', abbr: null, jid: null, fips: null, focus: false };

/* ------------------------------------------------------------------ helpers */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const cname = j => j.recCounty || j.county;
const ISP1 = j => j.src === 'p1';                  // wording as it appears in the source records
const fullName = j => j.full || j.county;                     // official name from the master roster
const roleMatches = (hay,role) => role==='hr' ? /human resources?|\bhr\b|personnel/.test(hay) : hay.includes(role);
const recordHay = j => (j.contacts || []).map(c => c.label + ' ' + c.value).join(' ').toLowerCase();
const stateName = ab => (STATE_BY[ab] || {}).name || ab;
function cleanName(v) { return String(v || '').replace(/\s*\([^)]*\)/g, '').replace(/(Via|Department|Office)/gi, '').trim(); }
function primaryContact(j) { const cs = j.contacts || []; return cs.find(c => c.value && !/^\(/.test(c.value)) || cs[0] || { label: 'Contact', value: cname(j) }; }
const linkedinMap = (name, j) => 'https://www.linkedin.com/search/results/people/?keywords=' + encodeURIComponent(`${cleanName(name)} ${cname(j)} County ${stateName(j.abbr)}`);
const linkedinDir = (name, j) => 'https://www.linkedin.com/search/results/people/?keywords=' + encodeURIComponent(`${name} ${cname(j)} County ${stateName(j.abbr)}`);
const googleMap = j => 'https://www.google.com/search?q=' + encodeURIComponent(`${cname(j)} County ${j.abbr} HR risk procurement county administrator`);
function extraRows(j) {   // fields from the master spreadsheet, shown only when populated
  const rows = [];
  const add = (label, v, kind) => { if (v) rows.push({ label, v, kind }); };
  add('Research contact', [j.name, j.title].filter(Boolean).join(' — '));
  add('Email', j.email, 'mail'); add('Phone', j.phone, 'tel');
  add('Backup contact', [j.backupName, j.backupTitle].filter(Boolean).join(' — ')); add('Backup email', j.backupEmail, 'mail');
  add('General HR email', j.hrEmail, 'mail'); add('Procurement email', j.procEmail, 'mail');
  add('HR page', j.hrUrl, 'url'); add('Official site', j.site, 'url'); add('Source', j.sourceUrl, 'url'); add('Notes', j.notes);
  return rows;
}
function extraHtml(j) {
  let h = extraRows(j).map(r => {
    let v = esc(r.v);
    if (r.kind === 'mail') v = `<a href="mailto:${esc(r.v)}">${v}</a>`;
    else if (r.kind === 'tel') v = `<a href="tel:${esc(r.v)}">${v}</a>`;
    else if (r.kind === 'url' && /^https?:/i.test(r.v)) v = `<a target="_blank" rel="noopener" href="${esc(r.v)}">${v}</a>`;
    return `<div class="contact"><label>${esc(r.label)}</label><div>${v}</div></div>`;
  }).join('');
  (j.seeds || []).forEach(sd => {   // source-listed contacts from the seed file
    const bits = [esc(sd.name) + (sd.title ? ' — ' + esc(sd.title) : '')];
    if (sd.email) bits.push(`<a href="mailto:${esc(sd.email)}">${esc(sd.email)}</a>` + (sd.emailType ? ` <small>(${esc(sd.emailType)})</small>` : ''));
    if (sd.phone) bits.push(`<a href="tel:${esc(sd.phone)}">${esc(sd.phone)}</a>`);
    if (sd.department) bits.push(esc(sd.department));
    if (sd.sourceFile) bits.push('<small>' + esc(sd.sourceFile) + '</small>');
    if (sd.sourceStatus && !/^official-registry-snapshot$/.test(sd.sourceStatus)) bits.push('<small>Research status: ' + esc(sd.sourceStatus.replace(/[_-]+/g,' ')) + '</small>');
    if (sd.sourceUrl && /^https?:/i.test(sd.sourceUrl)) bits.push(`<a target="_blank" rel="noopener" href="${esc(sd.sourceUrl)}">${esc(sd.sourceName || 'Source')}</a>` + (sd.sourceChecked ? ` <small>checked ${esc(sd.sourceChecked)}</small>` : ''));
    h += `<div class="contact"><label>Source-listed contact</label><div>${bits.join('<br>')}</div></div>`;
  });
  (j.registryMailboxes || []).forEach(mb => {
    const bits = [esc(mb.department || 'Department mailbox')];
    if (mb.email) bits.push('<a href="mailto:' + esc(mb.email) + '">' + esc(mb.email) + '</a>');
    if (mb.phone) bits.push('<a href="tel:' + esc(mb.phone) + '">' + esc(mb.phone) + '</a>');
    if (mb.sourceUrl && /^https:\/\//i.test(mb.sourceUrl))
      bits.push('<a target="_blank" rel="noopener noreferrer" href="' + esc(mb.sourceUrl) + '">Official source ↗</a>');
    h += '<div class="contact"><label>Department contact (not a person)</label><div>' + bits.join('<br>') + '</div></div>';
  });
  if (j.registrySources && j.registrySources.length) {
    h += '<div class="contact"><label>Official county employee registries</label><div>' +
      j.registrySources.map(s => /^https:\/\//i.test(s.url) ?
        '<a target="_blank" rel="noopener noreferrer" href="' + esc(s.url) + '">' + esc(s.department || 'County directory') + ' ↗</a>' : ''
      ).filter(Boolean).join('<br>') +
      (j.registryCheckedAt ? '<br><small>Last successful check: ' + esc(j.registryCheckedAt) + '</small>' : '') +
      (j.registryLastError ? '<br><small>Refresh issue: previous records retained</small>' : '') +
      '</div></div>';
  }
  if (j.p2) h += j.p2.map(c => `<div class="contact"><label>Part 2 · ${esc(c.label)}</label><div>${esc(c.value)}</div></div>`).join('');
  return h;
}
const contactsHtml = (j, n) => (j.contacts || []).slice(0, n || 99).map(c => `<div class="contact"><label>${esc(c.label)}</label><div>${esc(c.value)}</div></div>`).join('');

/* ------------------------------------------------------------------ selection API */
function selectState(abbr) { $('scopeSel').value = 'records'; sel.abbr = abbr; sel.jid = null; sel.fips = null; sel.focus = false; sync(); }
function selectJurisdiction(j, focus) { $('scopeSel').value = j.level === 'state' ? 'state' : 'records';
  sel.abbr = j.abbr; sel.jid = j.id; sel.fips = j.fips || null; sel.focus = !!focus; sync();
}
function selectFips(fips) { $('scopeSel').value = 'records';
  const list = byFips.get(fips) || [];
  sel.abbr = ABBR_BY_FIPS[fips.slice(0, 2)]; sel.fips = fips;
  sel.jid = (list.find(j => j.contacts) || list[0] || {}).id || null; sel.focus = false;
  sync();
}
function clearAll() { sel.abbr = null; sel.jid = null; sel.fips = null; sel.focus = false; sync(); }
function selectedGroup() {   // jurisdictions that make up the current county selection
  if (sel.fips && byFips.has(sel.fips)) return byFips.get(sel.fips);
  const j = sel.jid && JID.get(sel.jid); return j ? [j] : [];
}

/* ------------------------------------------------------------------ view switching + URL hash */
function setView(v) {
  sel.view = v;
  if (v === 'dir' && sel.jid) sel.focus = true;      // arriving from the map with a county selected -> show that county's records
  document.body.dataset.view = v;
  $('view-map').hidden = v !== 'map'; $('view-dir').hidden = v !== 'dir';
  $('navMap').setAttribute('aria-pressed', v === 'map'); $('navDir').setAttribute('aria-pressed', v === 'dir');
  window.scrollTo(0, 0);
  sync();
  if (v === 'map') requestAnimationFrame(() => { updateSize(); renderMap(); });
}
function writeHash() {
  let h = sel.view === 'dir' ? '#directory' : '#map';
  if (sel.abbr) h += '/' + sel.abbr + (sel.jid ? '/' + sel.jid : sel.view === 'dir' && $('scopeSel').value === 'state' ? '/state-agencies' : '');
  try { history.replaceState(null, '', h); } catch (e) { /* file:// in some browsers */ }
}
function readHash() {
  const m = location.hash.replace('#', '').split('/');
  const view = m[0] === 'directory' ? 'dir' : 'map';
  sel.abbr = null; sel.jid = null; sel.fips = null; sel.focus = false;
  if (m[1] && STATE_BY[m[1]]) { sel.abbr = m[1]; const j = m[2] && JID.get(m[2]); if (m[2] === 'state-agencies') $('scopeSel').value = 'state'; if (j && j.abbr === m[1]) { $('scopeSel').value = j.level === 'state' ? 'state' : 'records'; sel.jid = j.id; sel.fips = j.fips || null; } }
  return view;
}
function sync() {   // keep nav chrome + hash in step with selection
  const c = $('crumb');
  if (sel.abbr) {
    const g = selectedGroup(); const j = g[0];
    $('crumbText').textContent = stateName(sel.abbr) + (j ? ' › ' + (g.length > 1 && sel.fips ? countyLabel(sel.fips) : fullName(j)) : '');
    c.hidden = false;
  } else c.hidden = true;
  writeHash();
  if (sel.view === 'dir') renderDir();
  else { renderCard(); refreshHighlights(); }
}
function countyLabel(fips) { const f = countyFeat.get(fips); return f ? f.properties.name + ' County' : fips; }

/* ================================================================== MAP VIEW */
const svg = d3.select('#mapSvg'), tooltip = d3.select('#tooltip');
let width = 0, height = 0, statesGeo = [], countiesGeo = [], busy = false;
const countyFeat = new Map();
const stateFeatByAbbr = new Map();
const NS = { has: j => j.contacts };

function initGeo() {
  statesGeo = topojson.feature(TOPO, TOPO.objects.states).features;
  countiesGeo = topojson.feature(TOPO, TOPO.objects.counties).features;
  countiesGeo.forEach(f => countyFeat.set(String(f.id).padStart(5, '0'), f));
  statesGeo.forEach(f => stateFeatByAbbr.set(ABBR_BY_FIPS[String(f.id).padStart(2, '0')], f));
}
function updateSize() { const n = document.querySelector('#view-map .mapShell'); width = n.clientWidth; height = n.clientHeight; svg.attr('viewBox', [0, 0, width, height]); }
const roleVal = () => $('mapRole').value.toLowerCase();
const matchesRole = j => { const r = roleVal(); return !r || roleMatches(recordHay(j),r); };
function fipsHasData(fips) { return (byFips.get(fips) || []).some(j => j.contacts && matchesRole(j)); }
function fipsAnyData(fips) { return (byFips.get(fips) || []).some(j => j.contacts); }

function renderMap(opts) {
  if (!width || !height) updateSize(); if (!width) return;
  opts = opts || {};
  svg.selectAll('*').remove();
  if (sel.abbr) renderStateMap(sel.abbr, opts); else renderUSMap(opts);
  renderCard();
}
const usLayout = () => { const k = Math.min(width / 975, height / 610) * 0.97; return { k, tx: (width - 975 * k) / 2, ty: (height - 610 * k) / 2 }; };

function renderUSMap(opts) {
  $('stateAgencyBtn').style.display = 'none'; $('backBtn').style.display = 'none'; $('stateDirBtn').style.display = 'none';
  $('mapLabel').textContent = 'U.S. map · click a highlighted state to open its county map';
  $('modeBadge').textContent = 'U.S. map';
  $('legend').innerHTML = '<div><i class="stateData"></i>State with contact data</div><div><i class="noData"></i>No contact data yet</div>';
  const L = usLayout(), path = d3.geoPath();
  const g = svg.append('g').attr('class', 'usLayer' + (opts.fade ? ' fadeIn' : '')).attr('transform', `translate(${L.tx},${L.ty}) scale(${L.k})`);
  g.selectAll('path').data(statesGeo).join('path')
    .attr('class', d => { const ab = ABBR_BY_FIPS[String(d.id).padStart(2, '0')]; return 'state' + (STATES_WITH_DATA.has(ab) ? ' hasData' : ''); })
    .attr('d', path)
    .on('mousemove', (ev, d) => { const ab = ABBR_BY_FIPS[String(d.id).padStart(2, '0')]; const n = (recsByAbbr.get(ab) || []).length; const tot = (byAbbr.get(ab) || []).filter(j=>j.level!=='state').length; showTip(ev, `<b>${esc(stateName(ab))}</b><br>${n} imported county record${n === 1 ? '' : 's'}<br><span style="color:#91a6c8">${tot} counties tracked</span>`); })
    .on('mouseleave', hideTip)
    .on('click', (ev, d) => { const ab = ABBR_BY_FIPS[String(d.id).padStart(2, '0')]; if (ab) zoomIntoState(d, ab, L); });
}
function zoomIntoState(feat, abbr, L) {
  if (busy) return; busy = true; hideTip();
  const [[x0, y0], [x1, y1]] = d3.geoPath().bounds(feat);
  const w = (x1 - x0) * L.k, h = (y1 - y0) * L.k;
  const f = 0.82 * Math.min(width / w, height / h), k = L.k * f;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const tx = width / 2 - k * cx, ty = height / 2 - k * cy;
  const fid = String(feat.id).padStart(2, '0');
  const g = svg.select('g.usLayer');
  g.selectAll('path').filter(d => String(d.id).padStart(2, '0') !== fid).transition().duration(600).style('opacity', 0);
  g.transition().duration(650).ease(d3.easeCubicInOut).attr('transform', `translate(${tx},${ty}) scale(${k})`)
    .on('end', () => { busy = false; selectState(abbr); renderMap({ fade: true }); });
}

function renderStateMap(abbr, opts) {
  const n=(byAbbr.get(abbr)||[]).filter(j=>j.level==='state').length;
  $('stateAgencyBtn').style.display=n?'inline-block':'none';
  $('stateAgencyBtn').textContent=`State agencies (${n}) →`;
  $('backBtn').style.display = 'inline-block'; $('stateDirBtn').style.display = 'inline-block';
  $('stateDirBtn').textContent = `${stateName(abbr)} in Directory →`;
  const fips = STATES.find(s => s.abbr === abbr).fips;
  const recs = recsByAbbr.get(abbr) || [];
  $('mapLabel').textContent = `${stateName(abbr)} county boundary map · green counties have imported contacts`;
  $('modeBadge').textContent = `County map · ${recs.length} record${recs.length === 1 ? '' : 's'}`;
  $('legend').innerHTML = '<div><i class="data"></i>County with contacts</div><div><i class="noData"></i>No contacts yet</div><div><i class="sel"></i>Selected</div>';
  const cF = countiesGeo.filter(d => String(d.id).padStart(5, '0').slice(0, 2) === fips);
  const sF = stateFeatByAbbr.get(abbr);
  const pad = 24;
  const proj = d3.geoIdentity().reflectY(false).fitSize([width - pad * 2, height - pad * 2], { type: 'FeatureCollection', features: sF ? [sF] : cF });
  const path = d3.geoPath(proj);
  const g = svg.append('g').attr('class', 'countyLayer' + (opts.fade ? ' fadeIn' : '')).attr('transform', `translate(${pad},${pad})`);
  g.selectAll('path').data(cF).join('path').attr('d', path)
    .on('mousemove', (ev, d) => countyTip(ev, String(d.id).padStart(5, '0')))
    .on('mouseleave', hideTip)
    .on('click', (ev, d) => { hideTip(); selectFips(String(d.id).padStart(5, '0')); });
  refreshHighlights();
}
function countyClass(fid) {
  const has = fipsAnyData(fid), match = fipsHasData(fid);
  return 'county' + (has ? ' hasData' : '') + (has && !match ? ' dim' : '') + (sel.fips === fid ? ' active' : '');
}
function refreshHighlights() {
  svg.selectAll('g.countyLayer path').attr('class', d => countyClass(String(d.id).padStart(5, '0')));
}
function countyTip(ev, fid) {
  const f = countyFeat.get(fid), list = byFips.get(fid) || [];
  const recs = list.filter(j => j.contacts);
  const nm = list.length ? (list.length === 1 ? fullName(list[0]) : f.properties.name + ' County') : f.properties.name + ' County';
  let sub;
  if (recs.length) { const n = recs.reduce((a, j) => a + j.contacts.length, 0); sub = `Contact data available · ${n} contact${n === 1 ? '' : 's'}${recs.length > 1 ? ' · ' + recs.length + ' records' : ''}`; }
  else if (list.length) sub = 'No imported contact yet · tracked in roster';
  else sub = 'No imported contact yet';
  showTip(ev, `<b>${esc(nm)}</b><br>${esc(sub)}`);
}

/* ---- selected county card (map view; a popover, not a roster) ---- */
function renderCard() {
  const card = $('selectedCard');
  if (sel.view !== 'map' || !sel.abbr || !(sel.fips || sel.jid)) { card.hidden = true; return; }
  const group = selectedGroup();
  const f = sel.fips && countyFeat.get(sel.fips);
  const title = group.length === 1 ? `${fullName(group[0])}, ${group[0].abbr}` : `${f ? f.properties.name + ' County' : stateName(sel.abbr)}, ${sel.abbr}`;
  let body = '';
  if (!group.length) {
    body = `<div class="muted">No imported contact yet for this county. It is not part of the master roster.</div>`;
  } else group.forEach(j => {
    const p = primaryContact(j);
    const head = group.length > 1 ? `<div class="jTitle">${esc(fullName(j))}</div>` : '';
    const inner = j.contacts
      ? contactsHtml(j) + extraHtml(j)
      : `<div class="muted">No imported contact yet. Research status: <b>${esc(j.status)}</b>.</div>` + extraHtml(j);
    const links = j.contacts
      ? `<a class="btn" target="_blank" rel="noopener" href="${linkedinMap(p.value, j)}">LinkedIn</a><a class="btn" target="_blank" rel="noopener" href="${googleMap(j)}">Google</a>`
      : `<a class="btn" target="_blank" rel="noopener" href="${googleMap(j)}">Google</a>`;
    body += `<div class="jGroup">${head}${inner}<div class="links">${links}<button class="btn primary" type="button" data-open="${esc(j.id)}">Open in Directory</button></div></div>`;
  });
  const n = group.reduce((a, j) => a + (j.contacts ? j.contacts.length : 0), 0);
  card.innerHTML = `<button class="cardClose" type="button" aria-label="Close" data-close="1">×</button><div class="countyName">${esc(title)}</div><div class="cardSub">${n ? n + ' imported contact' + (n === 1 ? '' : 's') : 'Awaiting contact research'}</div><div class="govdirMount"></div>${body}`;
  card.hidden = false;
  if (sel.fips && /^\\d{5}$/.test(sel.fips)) window.GovDirUI?.mount(card.querySelector('.govdirMount'), sel.fips);
}
$('selectedCard').addEventListener('click', e => {
  const t = e.target.closest('[data-open],[data-close]'); if (!t) return;
  if (t.dataset.close) { sel.jid = null; sel.fips = null; sel.focus = false; sync(); return; }
  const j = JID.get(t.dataset.open); if (j) { selectJurisdiction(j, true); setView('dir'); }
});
function showTip(ev, html) { tooltip.style('display', 'block').style('left', (ev.clientX + 14) + 'px').style('top', (ev.clientY + 14) + 'px').html(html); }
function hideTip() { tooltip.style('display', 'none'); }

/* ---- map toolbar: jump-to search, role filter, back, directory shortcut ---- */
function searchHits(q) {
  q = q.toLowerCase().trim(); if (q.length < 2) return [];
  const out = [];
  STATES.forEach(s => { if (s.name.toLowerCase().includes(q) || s.abbr.toLowerCase() === q) out.push({ t: 's', s }); });
  for (const j of RECS) {
    if ((stateName(j.abbr) + ' ' + j.abbr + ' ' + cname(j) + ' ' + fullName(j) + ' ' + recordHay(j)).toLowerCase().includes(q)) out.push({ t: 'j', j });
    if (out.length >= 40) break;
  }
  return out.slice(0, 40);
}
function renderResults() {
  const box = $('mapResults'), hits = searchHits($('mapSearch').value);
  if (!hits.length) { box.hidden = true; box.innerHTML = ''; if ($('mapSearch').value.trim().length > 1) { box.hidden = false; box.innerHTML = '<div class="muted" style="padding:10px 12px">No matching states, counties or contacts.</div>'; } return; }
  box.innerHTML = hits.map((h, i) => h.t === 's'
    ? `<div class="listItem" data-i="${i}"><b>${esc(h.s.name)}</b><span class="pill">State · ${(recsByAbbr.get(h.s.abbr) || []).length} records</span></div>`
    : `<div class="listItem" data-i="${i}"><b>${esc(fullName(h.j))}, ${h.j.abbr}</b><span class="pill">${esc(primaryContact(h.j).label)} · ${esc(primaryContact(h.j).value)}</span></div>`).join('');
  box._hits = hits; box.hidden = false;
}
$('mapSearch').addEventListener('input', renderResults);
$('mapSearch').addEventListener('keydown', e => { if (e.key === 'Escape') { $('mapResults').hidden = true; } if (e.key === 'Enter') { const f = $('mapResults').querySelector('.listItem'); if (f) f.click(); } });
$('mapResults').addEventListener('click', e => {
  const it = e.target.closest('.listItem'); if (!it) return;
  const h = $('mapResults')._hits[+it.dataset.i]; $('mapResults').hidden = true; $('mapSearch').value = '';
  if (h.t === 's') selectState(h.s.abbr); else selectJurisdiction(h.j, false);
  renderMap({ fade: true });
});
document.addEventListener('click', e => { if (!e.target.closest('.mapToolbar')) $('mapResults').hidden = true; });
$('mapRole').addEventListener('change', () => { refreshHighlights(); });
$('backBtn').onclick = () => { clearAll(); renderMap({ fade: true }); };
$('stateAgencyBtn').onclick=()=>{sel.jid=null;sel.fips=null;sel.focus=false;$('scopeSel').value='state';setView('dir');};
$('stateDirBtn').onclick = () => { sel.jid = null; sel.fips = null; sel.focus = false; setView('dir'); };
document.addEventListener('keydown', e => { if (e.key === 'Escape' && sel.view === 'map' && (sel.jid || sel.fips)) { sel.jid = null; sel.fips = null; sync(); } });
window.addEventListener('resize', () => { if (sel.view === 'map') { updateSize(); renderMap(); } });

/* ================================================================== DIRECTORY VIEW */
const tabsEl = $('tabs'), cardsEl = $('cards'), gridEl = $('mapGrid'), drawer = $('drawer');
const dirState = () => sel.abbr || 'AL';

function renderTabs() {
  const q = $('globalSearch').value.toLowerCase(); tabsEl.innerHTML = '';
  STATES.forEach(s => {
    const recs = RECS.filter(j=>j.abbr===s.abbr);
    const hay = (s.name + ' ' + s.abbr + ' ' + recs.map(r => cname(r) + ' ' + r.contacts.map(c => c.value).join(' ')).join(' ')).toLowerCase();
    if (q && !hay.includes(q)) return;
    const b = document.createElement('button'); b.className = 'tab ' + (s.abbr === dirState() ? 'active' : '');
    b.innerHTML = `<span><b>${s.abbr}</b><br><small>${esc(s.name)}</small></span><small>${s.count}</small>`;
    b.onclick = () => { selectState(s.abbr); }; tabsEl.appendChild(b);
  });
}
function focusList() { return sel.focus ? selectedGroup() : null; }
function renderStateDirectory(ab,st) {
 $('stateName').textContent=st.name+' · State agencies & colleges';
 const agencies=(byAbbr.get(ab)||[]).filter(j=>j.level==='state');
 $('stateMeta').textContent=agencies.length+' statewide organizations · select an agency or search contacts';
 $('focusBar').hidden=true;gridEl.innerHTML='';cardsEl.innerHTML='';
 const allChip=document.createElement('button');allChip.className='countyChip';allChip.textContent='All state agencies';allChip.onclick=()=>{sel.jid=null;sel.focus=false;sync();};gridEl.appendChild(allChip);
 agencies.forEach(j=>{const chip=document.createElement('button');chip.className='countyChip'+(sel.jid===j.id?' sel':'');chip.textContent=cname(j);chip.onclick=()=>{sel.jid=j.id;sel.focus=true;sync();};gridEl.appendChild(chip);});
 const q=($('stateSearch').value+' '+$('globalSearch').value).trim().toLowerCase(),role=$('roleFilter').value.toLowerCase();
 let rows=agencies.filter(j=>!sel.jid||j.id===sel.jid).flatMap(j=>(j.seeds||[]).map(c=>({j,c})));
 const roleMatch=(hay)=>roleMatches(hay,role);
 rows=rows.filter(({j,c})=>{const h=[j.county,c.name,c.title,c.department,c.email,c.phone].join(' ').toLowerCase();return(!q||h.includes(q))&&(!role||roleMatch(h));});
 rows.sort((a,b)=>$('sortBy').value==='contact'?a.c.name.localeCompare(b.c.name):a.j.county.localeCompare(b.j.county)||a.c.name.localeCompare(b.c.name));
 let visible=0;
 const more=document.createElement('button');more.className='btn';more.type='button';
 const append=()=>{const end=Math.min(visible+100,rows.length);for(;visible<end;visible++){const {j,c}=rows[visible];const card=document.createElement('div');card.className='card';card.innerHTML=`<div class="badge">${esc(j.county)}</div><div class="county">${esc(c.name||c.title)}</div>${extraHtml({seeds:[c]})}`;cardsEl.appendChild(card);}more.textContent=`Show more (${rows.length-visible} remaining)`;more.hidden=visible>=rows.length;cardsEl.appendChild(more);};more.onclick=append;append();
 if(!rows.length)cardsEl.innerHTML='<div class="empty">No state contacts match this view.</div>';
}

function renderDir() {
  renderTabs();
  const ab = dirState(), st = STATE_BY[ab];
  if ($('scopeSel').value === 'state') { renderStateDirectory(ab,st); return; }
  const all = $('scopeSel').value === 'all';
  let base = (byAbbr.get(ab) || []).filter(j => j.level !== 'state' && (all || j.contacts));
  const focus = focusList(), fids = focus && focus.length ? new Set(focus.map(j => j.id)) : null;
  let recs = base.slice();
  if (fids) recs = recs.filter(j => fids.has(j.id));
  const q = $('stateSearch').value.toLowerCase(), role = $('roleFilter').value.toLowerCase();
  if (q) recs = recs.filter(r => (cname(r) + ' ' + fullName(r) + ' ' + (r.contacts || []).map(c => c.label + ' ' + c.value).join(' ')).toLowerCase().includes(q));
  if (role) recs = recs.filter(r => roleMatches(recordHay(r),role));
  if ($('sortBy').value === 'contact') recs.sort((a, b) => ((a.contacts && a.contacts[0] && a.contacts[0].value) || '￿').localeCompare((b.contacts && b.contacts[0] && b.contacts[0].value) || '￿'));
  else recs.sort((a, b) => cname(a).localeCompare(cname(b)));
  $('stateName').textContent = `${st.name} ${st.abbr === 'DC' ? '' : '(' + st.abbr + ')'}`;
  $('stateMeta').textContent = `${st.count} extracted card${st.count === 1 ? '' : 's'}${st.count > st.p1 ? ` (${st.p1} from Part 1, ${st.count - st.p1} from Part 2)` : ' from Part 1'} ${st.completeListedCount ? ` · ${st.completeListedCount} jurisdictions listed in source request` : ''} · ${st.rosterCount} tracked in master roster`;

  // focus banner (county carried over from the map, or picked here)
  const fb = $('focusBar');
  if (fids) {
    const g = focus[0], lbl = focus.length > 1 && sel.fips ? countyLabel(sel.fips) : fullName(g);
    fb.hidden = false; fb.innerHTML = `<span>Showing records for <b>${esc(lbl)}, ${ab}</b></span><button class="btn" type="button" id="focusClear">Show all ${esc(st.name)} counties</button>`;
    $('focusClear').onclick = () => { sel.focus = false; renderDir(); };
  } else { fb.hidden = true; fb.innerHTML = ''; }

  // county selector chips (no geography — browse by county)
  gridEl.innerHTML = '';
  base.slice().sort((a, b) => cname(a).localeCompare(cname(b))).forEach(r => {
    const chip = document.createElement('div');
    chip.className = 'countyChip' + (r.contacts ? '' : ' pending') + (fids && fids.has(r.id) ? ' sel' : '');
    chip.textContent = cname(r); chip.title = fullName(r) + (r.contacts ? '' : ' — contacts pending');
    chip.onclick = () => { selectJurisdiction(r, true); openDrawer(r); };
    gridEl.appendChild(chip);
  });
  if (!base.length) gridEl.innerHTML = '<div class="note" style="margin:0">No counties to browse in this view.</div>';

  cardsEl.innerHTML = '';
  if (!recs.length) {
    cardsEl.innerHTML = fids || q || role
      ? '<div class="empty">No records match the current filters.</div>'
      : `<div class="empty">No county employee data extracted for this state yet. ${st.rosterCount ? `${st.rosterCount} counties are tracked in the master roster — switch to <b>All tracked counties</b> to browse them.` : 'The tab is ready for Part 2 data.'}</div>`;
    return;
  }
  recs.forEach(r => {
    const div = document.createElement('div'); div.className = 'card' + (r.contacts ? '' : ' pending');
    if (r.contacts) {
      const primary = r.contacts.find(c => !c.value.startsWith('(Via')) || r.contacts[0];
      div.innerHTML = `<div class="badge">${r.abbr} outreach target</div><div class="county">${esc(cname(r))}</div>${contactsHtml(r, 4)}${extraHtml(r)}<div class="buttons"><a class="btn" target="_blank" href="${linkedinDir((primary && primary.value) || cname(r), r)}">LinkedIn Search</a><a class="btn" target="_blank" href="https://www.google.com/search?q=${encodeURIComponent(cname(r) + ' County ' + r.abbr + ' HR risk procurement')}">Google</a></div>`;
    } else {
      div.innerHTML = `<div class="badge">${r.abbr} · contacts pending</div><div class="county">${esc(fullName(r))}</div><div class="contact"><label>Research status</label><div>${esc(r.status)}</div></div>${extraHtml(r)}<div class="buttons"><a class="btn" target="_blank" href="https://www.google.com/search?q=${encodeURIComponent(fullName(r) + ' ' + st.name + ' human resources risk management procurement')}">County Search</a></div>`;
    }
    div.onclick = e => { if (e.target.tagName !== 'A') { sel.abbr = r.abbr; sel.jid = r.id; sel.fips = r.fips || null; writeHash(); syncCrumb(); openDrawer(r); } };
    cardsEl.appendChild(div);
  });
}
function syncCrumb() { const keep = sel.view; sel.view = 'dir'; const c = $('crumb'); const g = selectedGroup(); if (sel.abbr) { $('crumbText').textContent = stateName(sel.abbr) + (g[0] ? ' › ' + fullName(g[0]) : ''); c.hidden = false; } sel.view = keep; }
function openDrawer(r) {
  const body = $('drawerBody'), st = stateName(r.abbr);
  if (r.contacts) {
    body.innerHTML = `<h3>${esc(cname(r))} · ${r.abbr}</h3><p class="note">${esc(st)} county/jurisdiction outreach card.</p>${contactsHtml(r)}${extraHtml(r)}<div class="buttons">${r.contacts.map(c => c.value).filter(v => !v.startsWith('(Via')).slice(0, 3).map(v => `<a class="btn" target="_blank" href="${linkedinDir(v, r)}">Search ${esc(v.split(' ')[0])}</a>`).join('')}<a class="btn" target="_blank" href="https://www.google.com/search?q=${encodeURIComponent(cname(r) + ' County ' + r.abbr + ' human resources risk management procurement')}">County Search</a></div><div class="note">Verification status: imported from Part 1; confirm before formal outreach.</div>`;
  } else {
    body.innerHTML = `<h3>${esc(fullName(r))} · ${r.abbr}</h3><p class="note">${esc(st)} county tracked in the master roster — no contacts imported yet.</p><div class="contact"><label>Research status</label><div>${esc(r.status)}</div></div>${extraHtml(r)}<div class="buttons"><a class="btn" target="_blank" href="https://www.google.com/search?q=${encodeURIComponent(fullName(r) + ' ' + st + ' human resources risk management procurement')}">County Search</a></div>`;
  }
  if (r.fips && r.level !== 'state') {
    const officeMount = document.createElement('div');
    officeMount.className = 'govdirMount';
    const intro = body.querySelector('p.note');
    if (intro) intro.insertAdjacentElement('afterend', officeMount);
    else body.prepend(officeMount);
    window.GovDirUI?.mount(officeMount, r.fips);
  }
  drawer.classList.add('open');
}
['globalSearch', 'stateSearch', 'roleFilter', 'sortBy', 'scopeSel'].forEach(id => $(id).addEventListener('input', () => { if (id === 'scopeSel') { sel.jid=null;sel.fips=null;sel.focus=false;writeHash(); } if (sel.view === 'dir') renderDir(); }));
$('drawerClose').onclick = () => drawer.classList.remove('open');

/* ================================================================== shell wiring */
$('navMap').onclick = () => { if (sel.view !== 'map') setView('map'); };
$('navDir').onclick = () => { if (sel.view !== 'dir') setView('dir'); };
$('crumbClear').onclick = () => { clearAll(); if (sel.view === 'map') renderMap({ fade: true }); };
document.addEventListener('mousemove', e => {
  [['#view-map .cursorGlow'], ['#cursorLight']].forEach(([s]) => { const g = document.querySelector(s); if (g) { g.style.left = e.clientX + 'px'; g.style.top = e.clientY + 'px'; } });
});
$('totalRecords').textContent = RECS.length.toLocaleString();
$('stateCount').textContent = STATES_WITH_DATA.size;
$('rosterCount').textContent = J.filter(j => !j.extra).length.toLocaleString();
$('navStats').innerHTML = `<b>${RECS.filter(j=>j.level!=='state').length.toLocaleString()}</b> county records · <b>${STATES_WITH_DATA.size}</b> states with data`;

function boot() {
  initGeo();
  $('loading').style.display = 'none';
  const v = readHash();
  setView(v);
  if (v === 'dir' && sel.jid) sel.focus = true;
  if (v === 'map') { updateSize(); renderMap(); }
  window.__atlas = { sel, selectState, selectFips, selectJurisdiction, setView, J, RECS };   // handy for debugging / tests
}
window.addEventListener('hashchange', () => { /* manual hash edits: reload state */ const v = readHash(); setView(v); });
boot();
})();
