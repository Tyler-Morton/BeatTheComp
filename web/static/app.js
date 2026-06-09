/* Portfolio Bot showcase: animations, live data, and the vs-SPY chart. Read-only. */

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ─────────────────────────────────────────────────────────────────────────
   1. Flowing gradient background (ShaderGradient-style, pure canvas).
   ───────────────────────────────────────────────────────────────────────── */
function initGradient() {
  const canvas = document.getElementById('gradient-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const blobs = [
    { color: '99, 179, 237',  r: 0.55, x: 0.75, y: 0.45, dx: 0.018, dy: 0.013, ph: 0 },
    { color: '134, 239, 172', r: 0.45, x: 0.25, y: 0.70, dx: -0.014, dy: 0.016, ph: 2 },
    { color: '147, 197, 253', r: 0.50, x: 0.50, y: 0.20, dx: 0.012, dy: -0.011, ph: 4 },
    { color: '125, 211, 252', r: 0.40, x: 0.85, y: 0.80, dx: -0.016, dy: -0.013, ph: 1 },
  ];
  let w, h, t = 0;
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener('resize', resize);
  function draw() {
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'multiply';
    for (const b of blobs) {
      const cx = (b.x + Math.sin(t * b.dx + b.ph) * 0.12) * w;
      const cy = (b.y + Math.cos(t * b.dy + b.ph) * 0.12) * h;
      const rad = b.r * Math.min(w, h) * 1.4;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
      g.addColorStop(0, `rgba(${b.color}, 0.42)`);
      g.addColorStop(1, `rgba(${b.color}, 0)`);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
    t += 1;
    if (!REDUCED) requestAnimationFrame(draw);
  }
  draw();
}

/* ─────────────────────────────────────────────────────────────────────────
   2. Count-up animation.
   ───────────────────────────────────────────────────────────────────────── */
function countUp(el, target, { decimals = 0, prefix = '', suffix = '', dur = 1100 } = {}) {
  const fmt = v => `${prefix}${v.toFixed(decimals)}${suffix}`;
  if (REDUCED) { el.textContent = fmt(target); return; }
  const start = performance.now();
  function frame(now) {
    const p = Math.min((now - start) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(target * eased);
    if (p < 1) requestAnimationFrame(frame); else el.textContent = fmt(target);
  }
  requestAnimationFrame(frame);
}

/* ─────────────────────────────────────────────────────────────────────────
   3. Scroll reveal.
   ───────────────────────────────────────────────────────────────────────── */
function initReveal() {
  const els = document.querySelectorAll('.reveal');
  if (REDUCED) { els.forEach(e => e.classList.add('in')); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.15 });
  els.forEach(e => io.observe(e));
}

/* Run a count-up once its container scrolls into view. Hardened so the numbers
   can never get stuck on a placeholder if IntersectionObserver misbehaves. */
function armCountOnView(containerSel, runner) {
  const el = document.querySelector(containerSel);
  if (!el) return;
  let done = false;
  const fire = () => { if (!done) { done = true; runner(); } };
  const inView = () => {
    const r = el.getBoundingClientRect();
    return r.top < window.innerHeight * 0.85 && r.bottom > 0;
  };
  if (inView()) { fire(); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { fire(); io.disconnect(); } });
  }, { threshold: 0.25 });
  io.observe(el);
  setTimeout(() => { if (!done && (inView() || window.scrollY > el.offsetTop - window.innerHeight)) fire(); }, 8000);
}

/* ─────────────────────────────────────────────────────────────────────────
   4. The vs-SPY chart.
   ───────────────────────────────────────────────────────────────────────── */
const SVGNS = 'http://www.w3.org/2000/svg';
const VB = { w: 880, h: 380, ml: 56, mr: 18, mt: 18, mb: 34 };
const PLOT = {
  x0: VB.ml, x1: VB.w - VB.mr, y0: VB.mt, y1: VB.h - VB.mb,
  get w() { return this.x1 - this.x0; }, get h() { return this.y1 - this.y0; },
};

let CHART = { inception: null, series: [] };
let CHART_VIEW = [];   // currently-rendered, rebased points (for the tooltip)

const money = v => '$' + Math.round(v).toLocaleString('en-US');
const money2 = v => '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const parseDate = s => new Date(s + 'T00:00:00');

function filterRange(range) {
  const s = CHART.series.filter(p => p.spy != null);
  if (!s.length) return [];
  const end = parseDate(s[s.length - 1].date);
  let cutoff;
  if (range === 'YTD') return s;                                   // series already starts Jan 2
  if (range === 'ALL') cutoff = parseDate(CHART.inception);
  else { const days = range === '1W' ? 7 : 30; cutoff = new Date(end); cutoff.setDate(cutoff.getDate() - days); }
  const out = s.filter(p => parseDate(p.date) >= cutoff);
  return out.length >= 2 ? out : s;
}

function el(tag, attrs, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

function renderChart(range) {
  const svg = document.getElementById('equity-chart');
  if (!svg) return;
  const pts = filterRange(range);
  if (pts.length < 2) return;

  // Rebase both lines to a common $1,000 start for this window.
  const bP = pts[0].port, bS = pts[0].spy;
  const view = pts.map(p => ({ date: p.date, port: p.port / bP * 1000, spy: p.spy / bS * 1000 }));
  CHART_VIEW = view;

  const all = view.flatMap(p => [p.port, p.spy]);
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || hi * 0.02;
  lo -= pad; hi += pad;

  const n = view.length;
  const X = i => PLOT.x0 + (i / (n - 1)) * PLOT.w;
  const Y = v => PLOT.y1 - ((v - lo) / (hi - lo)) * PLOT.h;

  svg.innerHTML = '';
  const defs = el('defs', {}, svg);
  const grad = el('linearGradient', { id: 'port-fill', x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  el('stop', { offset: '0%', 'stop-color': 'rgba(37,99,235,0.14)' }, grad);
  el('stop', { offset: '100%', 'stop-color': 'rgba(37,99,235,0)' }, grad);

  // Horizontal gridlines + y-axis $ labels
  const ticks = 5;
  for (let i = 0; i < ticks; i++) {
    const v = lo + (hi - lo) * (i / (ticks - 1));
    const y = Y(v);
    el('line', { x1: PLOT.x0, y1: y, x2: PLOT.x1, y2: y, stroke: '#eef2f7', 'stroke-width': 1 }, svg);
    const tx = el('text', { x: PLOT.x0 - 10, y: y + 4, 'text-anchor': 'end',
      'font-family': 'Geist Mono, monospace', 'font-size': 11, fill: '#94a3b8' }, svg);
    tx.textContent = '$' + Math.round(v).toLocaleString('en-US');
  }

  // X-axis date labels (about 5 across)
  const labels = Math.min(5, n);
  for (let i = 0; i < labels; i++) {
    const idx = Math.round((i / (labels - 1)) * (n - 1));
    const d = parseDate(view[idx].date);
    const tx = el('text', { x: X(idx), y: VB.h - 12, 'text-anchor': i === 0 ? 'start' : i === labels - 1 ? 'end' : 'middle',
      'font-family': 'Geist Mono, monospace', 'font-size': 11, fill: '#94a3b8' }, svg);
    tx.textContent = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  const linePath = (key) => view.map((p, i) => `${i ? 'L' : 'M'} ${X(i).toFixed(1)} ${Y(p[key]).toFixed(1)}`).join(' ');

  // Portfolio area fill
  const areaD = linePath('port') + ` L ${X(n - 1).toFixed(1)} ${PLOT.y1} L ${X(0).toFixed(1)} ${PLOT.y1} Z`;
  el('path', { d: areaD, fill: 'url(#port-fill)' }, svg);

  // SPY line (dashed gray)
  el('path', { d: linePath('spy'), fill: 'none', stroke: '#94a3b8', 'stroke-width': 1.75,
    'stroke-dasharray': '5 4', 'stroke-linejoin': 'round' }, svg);

  // Portfolio line (solid blue) with a draw-in animation
  const port = el('path', { d: linePath('port'), fill: 'none', stroke: '#2563eb', 'stroke-width': 2.5,
    'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  if (!REDUCED) {
    const len = port.getTotalLength();
    port.style.strokeDasharray = len; port.style.strokeDashoffset = len;
    port.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 1100, easing: 'cubic-bezier(0.23,1,0.32,1)', fill: 'forwards' });
  }

  // End dots
  el('circle', { cx: X(n - 1), cy: Y(view[n - 1].spy), r: 3.5, fill: '#94a3b8' }, svg);
  el('circle', { cx: X(n - 1), cy: Y(view[n - 1].port), r: 4.5, fill: '#2563eb' }, svg);

  // Legend: each line shows its own value AND its own return, so the vs-SPY
  // badge can't be misread as the portfolio's loss.
  const last = view[n - 1];
  const portRet = (last.port / 1000 - 1) * 100;
  const spyRet = (last.spy / 1000 - 1) * 100;
  const fmtRet = r => `${r >= 0 ? '+' : ''}${r.toFixed(1)}%`;
  document.getElementById('lg-port').textContent = `${money(last.port)} · ${fmtRet(portRet)}`;
  document.getElementById('lg-spy').textContent = `${money(last.spy)} · ${fmtRet(spyRet)}`;
  const diff = portRet - spyRet;
  const diffEl = document.getElementById('lg-diff');
  diffEl.textContent = `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}% vs S&P`;
  diffEl.className = 'lg-diff ' + (diff >= 0 ? 'pos' : 'neg');

  // Stash geometry for the hover handler
  svg._geo = { X, Y, n };
}

function initChartHover() {
  const area = document.getElementById('chart-area');
  const svg = document.getElementById('equity-chart');
  const cross = document.getElementById('chart-crosshair');
  const tip = document.getElementById('chart-tooltip');
  if (!area) return;

  const move = (clientX) => {
    if (!CHART_VIEW.length) return;
    const rect = area.getBoundingClientRect();
    const frac = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
    const n = CHART_VIEW.length;
    const idx = Math.round(frac * (n - 1));
    const p = CHART_VIEW[idx];
    const pxX = (PLOT.x0 + (idx / (n - 1)) * PLOT.w) / VB.w * rect.width;

    cross.style.left = pxX + 'px';
    cross.style.height = svg.getBoundingClientRect().height + 'px';
    cross.style.opacity = '1';

    const d = parseDate(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const diff = (p.port - p.spy) / 1000 * 100;
    tip.innerHTML =
      `<div class="tt-date">${d}</div>` +
      `<div class="tt-row"><span class="tt-dot" style="background:#2563eb"></span>Portfolio <b>${money2(p.port)}</b></div>` +
      `<div class="tt-row"><span class="tt-dot" style="background:#94a3b8"></span>S&amp;P 500 <b>${money2(p.spy)}</b></div>` +
      `<div class="tt-row" style="color:${diff >= 0 ? '#34d399' : '#f87171'}">${diff >= 0 ? '+' : ''}${diff.toFixed(1)}% vs S&amp;P</div>`;
    const clamped = Math.min(Math.max(pxX, 70), rect.width - 70);
    tip.style.left = clamped + 'px';
    tip.style.opacity = '1';
  };

  area.addEventListener('mousemove', e => move(e.clientX));
  area.addEventListener('mouseleave', () => { cross.style.opacity = '0'; tip.style.opacity = '0'; });
}

function initRangeButtons() {
  const wrap = document.getElementById('range-btns');
  if (!wrap) return;
  wrap.addEventListener('click', e => {
    const btn = e.target.closest('button'); if (!btn) return;
    wrap.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
    renderChart(btn.dataset.range);
  });
}

/* ─────────────────────────────────────────────────────────────────────────
   5. Current holdings: an allocation bar plus a value/weight list.
   ───────────────────────────────────────────────────────────────────────── */
const HOLD_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4',
  '#ec4899', '#f97316', '#14b8a6', '#a855f7', '#64748b'];
const isCash = sym => sym === 'SHV' || sym === 'BIL' || sym === 'SGOV';

function renderHoldings(positions) {
  const bar = document.getElementById('alloc-bar');
  const list = document.getElementById('holdings-list');
  if (!bar || !list) return;
  if (!positions || !positions.length) {
    document.getElementById('holdings').style.display = 'none';
    return;
  }

  const color = (sym, i) => isCash(sym) ? '#94a3b8' : HOLD_COLORS[i % HOLD_COLORS.length];
  const maxWt = Math.max(...positions.map(p => p.weight));

  bar.innerHTML = positions.map((p, i) =>
    `<div class="alloc-seg" style="width:${p.weight}%;background:${color(p.symbol, i)}" title="${p.symbol} ${p.weight}%"></div>`
  ).join('');

  list.innerHTML = positions.map((p, i) => {
    const c = color(p.symbol, i);
    const tag = isCash(p.symbol) ? '<span class="holding-tag">Cash</span>' : '';
    return `<div class="holding-row">
      <div class="holding-id"><span class="holding-dot" style="background:${c}"></span>
        <span class="holding-sym">${p.symbol}</span>${tag}</div>
      <div class="holding-track"><div class="holding-fill" style="width:${(p.weight / maxWt * 100).toFixed(1)}%;background:${c}"></div></div>
      <div class="holding-nums"><div class="holding-val">${money2(p.value)}</div>
        <div class="holding-wt">${p.weight}% of book</div></div>
    </div>`;
  }).join('');
}

/* ─────────────────────────────────────────────────────────────────────────
   6. Fetch live data and populate the page.
   ───────────────────────────────────────────────────────────────────────── */
function setSigned(el, val, { decimals = 2, suffix = '%' } = {}) {
  const sign = val > 0 ? '+' : '';
  el.textContent = `${sign}${val.toFixed(decimals)}${suffix}`;
  el.classList.add(val >= 0 ? 'pos' : 'neg');
}

async function loadData() {
  let d;
  try { d = await (await fetch('/api/stats')).json(); }
  catch (err) { document.getElementById('badge-value').textContent = 'offline'; return; }

  const bt = d.backtest, m = d.metrics;
  const sign = d.day_change >= 0 ? '+' : '';

  // ── Hero badge ──
  const badgeVal = document.getElementById('badge-value');
  if (!REDUCED) countUp(badgeVal, d.equity, { prefix: '$', decimals: 0, dur: 1200 });
  else badgeVal.textContent = money(d.equity);
  const badgeDelta = document.getElementById('badge-delta');
  badgeDelta.textContent = `${sign}${d.day_change.toFixed(2)} (${sign}${d.day_change_pct.toFixed(2)}%) today`;
  badgeDelta.classList.toggle('neg', d.day_change < 0);
  document.getElementById('hero-status').textContent =
    (d.is_live ? 'Live on Alpaca' : 'Last recorded run') + ' · since May 2026';

  // ── Regime + today (text) ──
  const regimeEl = document.getElementById('stat-regime');
  regimeEl.textContent = d.regime.replace('_', ' ');
  regimeEl.className = 'stat-value ' + (d.regime === 'RISK_OFF' ? 'red' : d.regime === 'CHOPPY' ? 'blue' : 'green');
  document.getElementById('stat-regime-sub').textContent = d.regime_label.toLowerCase() + ' market';
  const todayEl = document.getElementById('stat-today');
  todayEl.textContent = `${sign}${d.day_change_pct.toFixed(2)}%`;
  todayEl.className = 'stat-value ' + (d.day_change < 0 ? 'red' : 'green');
  document.getElementById('stat-equity-sub').textContent = d.is_live ? 'live · Alpaca' : 'last run · ' + d.last_run;

  // ── Stats strip count-ups ──
  armCountOnView('#stats-strip', () => {
    countUp(document.getElementById('stat-equity'), d.equity, { prefix: '$', decimals: 0 });
    countUp(document.getElementById('stat-sharpe'), bt.sharpe, { decimals: 2 });
    countUp(document.getElementById('stat-maxdd'), bt.max_dd, { suffix: '%' });
  });

  // ── Chart ──
  CHART = d.chart || { inception: null, series: [] };
  if (CHART.series.length) { renderChart('ALL'); initChartHover(); initRangeButtons(); }

  // ── Holdings ──
  renderHoldings(d.positions);

  // ── Since-inception metrics ──
  if (m) {
    const set = (id, txt, cls) => { const e = document.getElementById(id); e.textContent = txt; if (cls) e.classList.add(cls); };
    set('m-total', `${m.total_return > 0 ? '+' : ''}${m.total_return}%`, m.total_return >= 0 ? 'pos' : 'neg');
    if (m.alpha != null) set('m-alpha', `${m.alpha > 0 ? '+' : ''}${m.alpha}%`, m.alpha >= 0 ? 'pos' : 'neg');
    else set('m-alpha', 'n/a');
    set('m-best', `+${m.best_day}%`, 'pos');
    set('m-worst', `${m.worst_day}%`, 'neg');
    set('m-win', `${m.win_rate}%`);
    set('m-days', `${m.days_live}`);
    set('m-rebal', `${m.rebalances}`);
    set('m-cash', m.cash_pct != null ? `${m.cash_pct}%` : 'n/a');
  }

  // ── Backtest numbers ──
  document.getElementById('num-dd-raw').textContent = bt.max_dd_raw;
  armCountOnView('#backtest', () => {
    countUp(document.getElementById('num-dsr'), bt.dsr, { decimals: 1, suffix: '%' });
    countUp(document.getElementById('num-sharpe'), bt.sharpe, { decimals: 2 });
    countUp(document.getElementById('num-vol'), bt.vol_reduction, { suffix: '%' });
    countUp(document.getElementById('num-dd'), bt.max_dd, { suffix: '%' });
  });
}

/* ── Boot ── */
initGradient();
initReveal();
loadData();
window.addEventListener('resize', () => {
  const active = document.querySelector('#range-btns button.active');
  if (active && CHART.series.length) renderChart(active.dataset.range);
});
