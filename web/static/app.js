/* Portfolio Bot showcase: animations, live data, and the vs-SPY chart. Read-only. */

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ─────────────────────────────────────────────────────────────────────────
   1. Flowing gradient background (ShaderGradient-style, pure canvas).
   ───────────────────────────────────────────────────────────────────────── */
function initGradient() {
  const canvas = document.getElementById('gradient-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  // One hue only — a quiet blue field, not a multi-color gradient wash.
  const blobs = [
    { color: '147, 197, 253', r: 0.60, x: 0.78, y: 0.40, dx: 0.010, dy: 0.008, ph: 0 },
    { color: '191, 219, 254', r: 0.50, x: 0.30, y: 0.75, dx: -0.008, dy: 0.009, ph: 2 },
    { color: '219, 234, 254', r: 0.55, x: 0.55, y: 0.15, dx: 0.007, dy: -0.006, ph: 4 },
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

  // Rebase both lines to a common $1,000 start for this window. The challenger
  // starts mid-chart, so it rebases to $1,000 at ITS first point (like any new
  // fund joining a comparison) and the line simply begins there.
  const bP = pts[0].port, bS = pts[0].spy;
  const firstChal = pts.find(p => p.chal != null);
  const bC = firstChal ? firstChal.chal : null;
  const view = pts.map(p => ({
    date: p.date, port: p.port / bP * 1000, spy: p.spy / bS * 1000,
    chal: (bC && p.chal != null) ? p.chal / bC * 1000 : null,
  }));
  CHART_VIEW = view;

  const all = view.flatMap(p => [p.port, p.spy, ...(p.chal != null ? [p.chal] : [])]);
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

  // Challenger line (amber). With one data point it's just the starting dot.
  const chalIdx = view.map((p, i) => p.chal != null ? i : -1).filter(i => i >= 0);
  if (chalIdx.length >= 2) {
    const d = chalIdx.map((i, k) => `${k ? 'L' : 'M'} ${X(i).toFixed(1)} ${Y(view[i].chal).toFixed(1)}`).join(' ');
    el('path', { d, fill: 'none', stroke: '#f59e0b', 'stroke-width': 2.25,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  }
  if (chalIdx.length) {
    const li = chalIdx[chalIdx.length - 1];
    el('circle', { cx: X(li), cy: Y(view[li].chal), r: 4.5, fill: '#f59e0b' }, svg);
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

  const chalWrap = document.getElementById('lg-chal-wrap');
  if (chalIdx.length) {
    const lc = view[chalIdx[chalIdx.length - 1]].chal;
    document.getElementById('lg-chal').textContent = `${money(lc)} · ${fmtRet((lc / 1000 - 1) * 100)}`;
    chalWrap.style.display = '';
  } else {
    chalWrap.style.display = 'none';
  }

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
      (p.chal != null ? `<div class="tt-row"><span class="tt-dot" style="background:#f59e0b"></span>Challenger <b>${money2(p.chal)}</b></div>` : '') +
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

  // ── Stats strip count-ups (Sharpe/maxDD come from the verdict engine) ──
  armCountOnView('#stats-strip', () => {
    countUp(document.getElementById('stat-equity'), d.equity, { prefix: '$', decimals: 0 });
    const champ = VERDICT && VERDICT.books && VERDICT.books.champion;
    countUp(document.getElementById('stat-sharpe'), champ ? champ.sharpe : bt.sharpe, { decimals: 2 });
    countUp(document.getElementById('stat-maxdd'), champ ? champ.maxdd * 100 : bt.max_dd, { suffix: '%' });
  });

  // ── Chart ──
  CHART = d.chart || { inception: null, series: [] };
  if (CHART.series.length) { renderChart('ALL'); initChartHover(); initRangeButtons(); }

  // ── Holdings ──
  renderHoldings(d.positions);

  // ── Challenger section ──
  if (d.challenger) {
    const c = d.challenger;
    document.getElementById('challenger').style.display = '';
    document.getElementById('chal-equity').textContent = money(c.equity);
    document.getElementById('chal-since').textContent =
      (c.is_live ? 'live · Alpaca · since ' : 'since ') + c.started;
    const r = document.getElementById('chal-return');
    r.textContent = `${c.total_return >= 0 ? '+' : ''}${c.total_return.toFixed(1)}%`;
    r.classList.add(c.total_return >= 0 ? 'pos' : 'neg');
    document.getElementById('chal-days').textContent =
      `${c.days} trading day${c.days === 1 ? '' : 's'}, forward, real fills`;
    document.getElementById('chal-vol').textContent = `${c.backtest.target_vol}%`;
    document.getElementById('chal-sharpe').textContent = c.backtest.sharpe.toFixed(2);
    document.getElementById('chal-spy-sharpe').textContent = c.backtest.spy_sharpe.toFixed(2);
  }

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

}

/* ─────────────────────────────────────────────────────────────────────────
   7. Evidence: verdict report cards + the Monte Carlo fan chart.
   Data comes from /static/verdict.json, written by research/verdict.py.
   ───────────────────────────────────────────────────────────────────────── */
let VERDICT = null;

const pct = (v, dp = 1) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(dp)}%`;
const pctu = (v, dp = 1) => `${(v * 100).toFixed(dp)}%`;

function verdictCard(book, key) {
  const chip = book.sufficiency.toLowerCase();
  const [lo, hi] = book.sharpe_ci95;
  // CI bar geometry: fixed -0.5..1.6 scale so all three cards align.
  const S0 = -0.5, S1 = 1.6;
  const px = v => Math.min(Math.max((v - S0) / (S1 - S0), 0), 1) * 100;
  const rows = [
    ['CAGR', pct(book.cagr)],
    ['Volatility', pctu(book.vol)],
    ['Max drawdown', pct(book.maxdd)],
    ['Worst month', pct(book.worst_month)],
  ];
  if (book.alpha_ann != null) rows.push(['Alpha vs SPY', pct(book.alpha_ann) + '/yr']);
  if (book.beta != null) rows.push(['Beta', book.beta.toFixed(2)]);
  return `<article class="verdict-card" data-book="${key}">
    <div class="verdict-top">
      <span class="v-name">${book.name}</span>
      <span class="v-chip ${chip}">${book.sufficiency}</span>
    </div>
    <div class="v-sharpe">
      <div class="v-sharpe-num">${book.sharpe.toFixed(2)}<span> Sharpe</span></div>
      <div class="v-ci">
        <div class="v-ci-track">
          <span class="v-ci-zero" style="left:${px(0)}%"></span>
          <span class="v-ci-range ${lo > 0 ? 'pos' : ''}" style="left:${px(lo)}%;width:${px(hi) - px(lo)}%"></span>
          <span class="v-ci-dot" style="left:${px(book.sharpe)}%"></span>
        </div>
        <div class="v-ci-label">95% CI ${lo.toFixed(2)} … ${hi.toFixed(2)} · ${book.years}y of data</div>
      </div>
    </div>
    <div class="v-dsr">Deflated Sharpe <b>${pctu(book.dsr, 1)}</b><span class="v-k">after K=${book.k_trials} configs tried</span></div>
    <dl class="v-rows">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>
  </article>`;
}

function renderFan(key) {
  const svg = document.getElementById('fan-chart');
  const probs = document.getElementById('fan-probs');
  const book = VERDICT.books[key];
  if (!svg || !book || !book.monte_carlo) return;
  const mc = book.monte_carlo;
  const fan = mc.fan;
  const months = fan.days.map(d => d / 21);
  const B = q => fan.bands[q];

  const W = 880, H = 330, ML = 56, MR = 18, MT = 16, MB = 30;
  const allVals = [...B('5'), ...B('95'), 0];
  let lo = Math.min(...allVals), hi = Math.max(...allVals);
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const X = i => ML + (i / (months.length - 1)) * (W - ML - MR);
  const Y = v => (H - MB) - ((v - lo) / (hi - lo)) * (H - MT - MB);

  svg.innerHTML = '';
  const mk = (tag, attrs) => { const n = document.createElementNS(SVGNS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]); svg.appendChild(n); return n; };

  // gridlines + % labels
  for (let t = 0; t < 5; t++) {
    const v = lo + (hi - lo) * (t / 4), y = Y(v);
    mk('line', { x1: ML, y1: y, x2: W - MR, y2: y, stroke: '#eef2f7', 'stroke-width': 1 });
    const tx = mk('text', { x: ML - 10, y: y + 4, 'text-anchor': 'end',
      'font-family': 'Geist Mono, monospace', 'font-size': 11, fill: '#94a3b8' });
    tx.textContent = `${v >= 0 ? '+' : ''}${Math.round(v * 100)}%`;
  }
  // zero line
  mk('line', { x1: ML, y1: Y(0), x2: W - MR, y2: Y(0), stroke: '#cbd5e1', 'stroke-width': 1, 'stroke-dasharray': '4 4' });
  // month labels
  [3, 6, 9, 12].forEach(m => {
    const i = months.indexOf(m); if (i < 0) return;
    const tx = mk('text', { x: X(i), y: H - 8, 'text-anchor': 'middle',
      'font-family': 'Geist Mono, monospace', 'font-size': 11, fill: '#94a3b8' });
    tx.textContent = m === 12 ? '1 year' : `${m}mo`;
  });

  const path = (qs, close) => {
    const up = B(qs[0]).map((v, i) => `${i ? 'L' : 'M'} ${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ');
    if (!close) return up;
    const dn = B(qs[1]).map((v, i) => `L ${X(B(qs[1]).length - 1 - i).toFixed(1)} ${Y(B(qs[1])[B(qs[1]).length - 1 - i]).toFixed(1)}`).join(' ');
    return `${up} ${dn} Z`;
  };
  // one hue, two depths: 90% band then 50% band, then the median line
  mk('path', { d: path(['95', '5'], true), fill: 'rgba(37,99,235,0.08)' });
  mk('path', { d: path(['75', '25'], true), fill: 'rgba(37,99,235,0.18)' });
  mk('path', { d: path(['50'], false), fill: 'none', stroke: '#2563eb',
    'stroke-width': 2.25, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' });

  // terminal labels at the right edge
  const lastI = months.length - 1;
  [['95', 'best 5%'], ['50', 'median'], ['5', 'worst 5%']].forEach(([q, lab]) => {
    const v = B(q)[lastI];
    const tx = mk('text', { x: W - MR - 4, y: Y(v) + (q === '5' ? 12 : q === '95' ? -5 : -6),
      'text-anchor': 'end', 'font-family': 'Geist Mono, monospace', 'font-size': 11,
      fill: q === '50' ? '#2563eb' : '#94a3b8', 'font-weight': q === '50' ? 600 : 400 });
    tx.textContent = `${lab} ${pct(v, 0)}`;
  });

  const t = mc.terminal_1yr_pct;
  const cells = [
    ['P(−20% drawdown, 6mo)', pctu(mc.p_dd20_6mo)],
    ['P(down year)', pctu(mc.p_neg_1yr)],
    ['1-yr median outcome', pct(parseFloat(t['50']))],
    ['5th … 95th percentile', `${pct(parseFloat(t['5']), 0)} … ${pct(parseFloat(t['95']), 0)}`],
  ];
  if (mc.p_beat_bench_1yr != null) cells.push(['P(beat SPY, 1yr)', pctu(mc.p_beat_bench_1yr)]);
  probs.innerHTML = cells.map(([k, v]) =>
    `<div class="fan-prob"><div class="metric-label">${k}</div><div class="fan-prob-val">${v}</div></div>`).join('');
}

async function loadVerdict() {
  try { VERDICT = await (await fetch('/static/verdict.json')).json(); }
  catch (err) { document.getElementById('evidence').style.display = 'none'; return; }
  const grid = document.getElementById('verdict-grid');
  const order = ['champion', 'challenger', 'spy'];
  grid.innerHTML = order.filter(k => VERDICT.books[k])
    .map(k => verdictCard(VERDICT.books[k], k)).join('');
  renderFan('champion');
  document.getElementById('fan-btns').addEventListener('click', e => {
    const btn = e.target.closest('button'); if (!btn) return;
    document.querySelectorAll('#fan-btns button').forEach(b => b.classList.toggle('active', b === btn));
    renderFan(btn.dataset.book);
  });
}

/* ── Boot ── */
initGradient();
initReveal();
loadVerdict().then(loadData);
window.addEventListener('resize', () => {
  const active = document.querySelector('#range-btns button.active');
  if (active && CHART.series.length) renderChart(active.dataset.range);
});
