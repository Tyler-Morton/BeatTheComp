/* Trading desk front end. Vanilla JS, hand-rolled SVG charts, hash routing.
   Everything here is read-only: it only GETs the JSON the Flask app serves. */
"use strict";

// ───────────────────────────── formatting ─────────────────────────────
const MINUS = "−";
const isNum = (v) => typeof v === "number" && isFinite(v);
const sign = (v) => (v > 0 ? "+" : v < 0 ? MINUS : "");
function money(v, opts = {}) {
  if (!isNum(v)) return "—";
  const big = Math.abs(v) >= 10000 && !opts.cents;
  const s = Math.abs(v).toLocaleString("en-US", {
    minimumFractionDigits: big ? 0 : 2, maximumFractionDigits: big ? 0 : 2,
  });
  return (opts.signed ? sign(v) : v < 0 ? MINUS : "") + "$" + s;
}
function pct(v, d = 1, signed = true) {
  if (!isNum(v)) return "—";
  const s = Math.abs(v * 100).toFixed(d);
  return (signed ? sign(v) : v < 0 ? MINUS : "") + s + "%";
}
function num(v, d = 2) { return isNum(v) ? (v < 0 ? MINUS : "") + Math.abs(v).toFixed(d) : "—"; }
const cls = (v) => (!isNum(v) || v === 0 ? "" : v > 0 ? "pos" : "neg");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function dshort(s) { if (!s) return "—"; const [, m, d] = s.slice(0, 10).split("-"); return `${MONTHS[+m - 1]} ${+d}`; }
function dlong(s) { if (!s) return "—"; const [y, m, d] = s.slice(0, 10).split("-"); return `${MONTHS[+m - 1]} ${+d}, ${y}`; }
function ago(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400 * 1.5) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const $ = (sel, root = document) => root.querySelector(sel);

// ───────────────────────────── data ─────────────────────────────
const cache = new Map();
async function api(path, fresh = false) {
  if (!fresh && cache.has(path)) return cache.get(path);
  const p = fetch(path, { cache: "no-store" }).then((r) => {
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  });
  cache.set(path, p);
  p.catch(() => cache.delete(path));
  return p;
}

const BOOK_COLOR = { champion: "var(--s1)", challenger: "var(--s2)", volbot: "var(--s3)" };
const SERIES_VARS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];
const STATUS_LABEL = { ran: "Ran", missed: "Missed", failed: "Failed", scheduled: "Scheduled" };

// ───────────────────────────── tooltip ─────────────────────────────
const tip = () => $("#tip");
function showTip(html, x, y) {
  const t = tip();
  t.innerHTML = html;
  t.hidden = false;
  const r = t.getBoundingClientRect();
  let left = x + 14, top = y + 14;
  if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
  if (top + r.height > window.innerHeight - 8) top = y - r.height - 14;
  t.style.left = Math.max(8, left) + "px";
  t.style.top = Math.max(8, top) + "px";
}
function hideTip() { tip().hidden = true; }
function tipRows(date, rows) {
  return `<div class="d">${dlong(date)}</div>` + rows.map((r) =>
    `<div class="r"><span class="l">${r.sw || ""}${esc(r.label)}</span><span class="v">${r.value}</span></div>`).join("");
}
const sw = (color, kind = "line") =>
  kind === "dash" ? `<i class="swatch dash"></i>` : `<i class="swatch ${kind}" style="background:${color}"></i>`;

// ───────────────────────────── charts ─────────────────────────────
const NS = "http://www.w3.org/2000/svg";
function niceTicks(lo, hi, n = 5) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const raw = (hi - lo) / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return { ticks: out, lo: Math.min(lo, out[0]), hi: Math.max(hi, out[out.length - 1]) };
}
function monthTicks(dates, maxN) {
  const idx = [];
  for (let i = 1; i < dates.length; i++) if (dates[i].slice(5, 7) !== dates[i - 1].slice(5, 7)) idx.push(i);
  if (!idx.length && dates.length) idx.push(0);
  if (idx.length <= maxN) return idx;
  const k = Math.ceil(idx.length / maxN);
  return idx.filter((_, i) => i % k === 0);
}
function weekTicks(dates, maxN) {
  const step = Math.max(1, Math.ceil(dates.length / maxN));
  const out = [];
  for (let i = 0; i < dates.length; i += step) out.push(i);
  return out;
}

/* Responsive chart mount: re-draws on width change. */
function mount(host, draw) {
  let w = 0;
  const go = () => {
    const nw = Math.floor(host.clientWidth);
    if (nw && nw !== w) { w = nw; host.innerHTML = ""; draw(nw); }
  };
  const ro = new ResizeObserver(go);
  ro.observe(host);
  go();
}

/**
 * Line chart on a trading-day x axis.
 * opt: { dates, series:[{label,color,values,dash,width,fill}], height, yFmt, tipFmt, zero, yMin, yMax }
 */
function lineChart(host, opt) {
  mount(host, (W) => {
    const H = opt.height || 240;
    const n = opt.dates.length;
    const all = opt.series.flatMap((s) => s.values).filter(isNum);
    if (!n || !all.length) { host.innerHTML = `<div class="empty">No data yet</div>`; return; }
    let lo = Math.min(...all), hi = Math.max(...all);
    if (isNum(opt.zero)) { lo = Math.min(lo, opt.zero); hi = Math.max(hi, opt.zero); }
    if (isNum(opt.yMin)) lo = Math.min(lo, opt.yMin);
    if (isNum(opt.yMax)) hi = Math.max(hi, opt.yMax);
    const pad = (hi - lo) * 0.06 || 1;
    const nt = niceTicks(lo - (isNum(opt.yMin) ? 0 : pad), hi + (isNum(opt.yMax) ? 0 : pad), opt.ticks || (H < 150 ? 3 : 5));
    const yLabels = nt.ticks.map(opt.yFmt);
    const ml = Math.max(...yLabels.map((s) => s.length)) * 6.6 + 10;
    const m = { l: ml, r: 8, t: 8, b: 22 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const x = (i) => m.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
    const y = (v) => m.t + ih - ((v - nt.lo) / (nt.hi - nt.lo)) * ih;

    let g = "";
    nt.ticks.forEach((t, k) => {
      g += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`;
      g += `<text class="tick" x="${m.l - 8}" y="${y(t) + 3.5}" text-anchor="end">${esc(yLabels[k])}</text>`;
    });
    if (isNum(opt.zero)) g += `<line class="base" x1="${m.l}" x2="${W - m.r}" y1="${y(opt.zero)}" y2="${y(opt.zero)}"/>`;
    const xt = n > 70 ? monthTicks(opt.dates, Math.max(2, Math.floor(iw / 70))) : weekTicks(opt.dates, Math.max(2, Math.floor(iw / 80)));
    xt.forEach((i) => {
      const lab = n > 70 ? MONTHS[+opt.dates[i].slice(5, 7) - 1] : dshort(opt.dates[i]);
      g += `<text class="tick" x="${x(i)}" y="${H - 6}" text-anchor="middle">${lab}</text>`;
    });

    let paths = "";
    opt.series.forEach((s) => {
      let d = "", started = false, first = -1, last = -1;
      s.values.forEach((v, i) => {
        if (!isNum(v)) { started = false; return; }
        d += `${started ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        started = true;
        if (first < 0) first = i;
        last = i;
      });
      if (s.fill && first >= 0) {
        const base = y(isNum(opt.zero) ? opt.zero : nt.lo);
        paths += `<path d="${d}L${x(last)},${base}L${x(first)},${base}Z" fill="${s.color}" opacity="${s.fillOpacity ?? 0.12}" stroke="none"/>`;
      }
      paths += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width || 2}" stroke-linejoin="round" stroke-linecap="round" ${s.dash ? 'stroke-dasharray="4 4"' : ""}/>`;
    });

    host.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.aria || "chart")}">
      ${g}${paths}<g class="hover"></g><rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}"/></svg>`;
    const svg = host.querySelector("svg"), hov = svg.querySelector(".hover"), hit = svg.querySelector(".hit");
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ev.clientX - r.left;
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / iw) * (n - 1))));
      let h = `<line class="xh" x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}"/>`;
      const rows = [];
      opt.series.forEach((s) => {
        const v = s.values[i];
        if (!isNum(v)) return;
        h += `<circle cx="${x(i)}" cy="${y(v)}" r="4" fill="${s.color}" stroke="var(--surface)" stroke-width="2"/>`;
        rows.push({ label: s.label, value: (opt.tipFmt || opt.yFmt)(v, s, i), sw: sw(s.color, s.dash ? "dash" : "line") });
      });
      hov.innerHTML = h;
      showTip(tipRows(opt.dates[i], rows.concat(opt.extraTip ? opt.extraTip(i) : [])), ev.clientX, ev.clientY);
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerleave", () => { hov.innerHTML = ""; hideTip(); });
  });
}

/** Stacked 100% area of weights. opt: { dates, keys:[{key,label,color}], rows } */
function stackChart(host, opt) {
  mount(host, (W) => {
    const H = opt.height || 220, n = opt.dates.length;
    if (!n) { host.innerHTML = `<div class="empty">No positions logged</div>`; return; }
    const m = { l: 40, r: 8, t: 6, b: 22 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const x = (i) => m.l + (n === 1 ? 0 : (i / (n - 1)) * iw);
    const y = (v) => m.t + ih - v * ih;
    let g = "";
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      g += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`;
      g += `<text class="tick" x="${m.l - 8}" y="${y(t) + 3.5}" text-anchor="end">${t * 100}%</text>`;
    });
    const xt = n > 70 ? monthTicks(opt.dates, Math.floor(iw / 70)) : weekTicks(opt.dates, Math.floor(iw / 80));
    xt.forEach((i) => g += `<text class="tick" x="${x(i)}" y="${H - 6}" text-anchor="middle">${n > 70 ? MONTHS[+opt.dates[i].slice(5, 7) - 1] : dshort(opt.dates[i])}</text>`);
    const cum = new Array(n).fill(0);
    let areas = "";
    opt.keys.forEach((k) => {
      const lo = cum.slice();
      opt.rows.forEach((r, i) => { cum[i] += r[k.key] || 0; });
      let d = "";
      for (let i = 0; i < n; i++) d += `${i ? "L" : "M"}${x(i).toFixed(1)},${y(Math.min(1, cum[i])).toFixed(1)}`;
      for (let i = n - 1; i >= 0; i--) d += `L${x(i).toFixed(1)},${y(Math.min(1, lo[i])).toFixed(1)}`;
      areas += `<path d="${d}Z" fill="${k.color}" stroke="var(--surface)" stroke-width="0.75"/>`;
    });
    host.innerHTML = `<svg width="${W}" height="${H}" role="img" aria-label="Allocation over time">${areas}${g}<g class="hover"></g>
      <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}"/></svg>`;
    const svg = host.querySelector("svg"), hov = svg.querySelector(".hover");
    svg.querySelector(".hit").addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(n - 1, Math.round(((ev.clientX - r.left - m.l) / iw) * (n - 1))));
      hov.innerHTML = `<line class="xh" x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}"/>`;
      const rows = opt.keys.map((k) => ({ k, v: opt.rows[i][k.key] || 0 })).filter((o) => o.v >= 0.001)
        .sort((a, b) => b.v - a.v)
        .map((o) => ({ label: o.k.label, value: pct(o.v, 1, false), sw: sw(o.k.color, "") }));
      showTip(tipRows(opt.dates[i], rows), ev.clientX, ev.clientY);
    });
    svg.querySelector(".hit").addEventListener("pointerleave", () => { hov.innerHTML = ""; hideTip(); });
  });
}

/** Simple bars on a trading-day axis. opt: { dates, values, color, yFmt, height } */
function barChart(host, opt) {
  mount(host, (W) => {
    const H = opt.height || 160, n = opt.dates.length;
    if (!n) { host.innerHTML = `<div class="empty">No rebalances yet</div>`; return; }
    const hi = Math.max(...opt.values.filter(isNum), 0.0001);
    const nt = niceTicks(0, hi, 3);
    const labels = nt.ticks.map(opt.yFmt);
    const m = { l: Math.max(...labels.map((s) => s.length)) * 6.6 + 10, r: 8, t: 6, b: 22 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const bw = iw / n, gap = Math.min(2, bw * 0.3);
    const y = (v) => m.t + ih - (v / nt.hi) * ih;
    let g = "";
    nt.ticks.forEach((t, k) => {
      g += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`;
      g += `<text class="tick" x="${m.l - 8}" y="${y(t) + 3.5}" text-anchor="end">${labels[k]}</text>`;
    });
    g += `<line class="base" x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}"/>`;
    const xt = n > 70 ? monthTicks(opt.dates, Math.floor(iw / 70)) : weekTicks(opt.dates, Math.floor(iw / 80));
    xt.forEach((i) => g += `<text class="tick" x="${m.l + (i + 0.5) * bw}" y="${H - 6}" text-anchor="middle">${n > 70 ? MONTHS[+opt.dates[i].slice(5, 7) - 1] : dshort(opt.dates[i])}</text>`);
    let bars = "";
    opt.values.forEach((v, i) => {
      if (!isNum(v) || v <= 0) return;
      const h = Math.max(1, y(0) - y(v));
      const r = Math.min(2, (bw - gap) / 2, h / 2);
      const x0 = m.l + i * bw + gap / 2, w = Math.max(1, bw - gap), yt = y(0) - h;
      bars += `<path d="M${x0},${y(0)}V${yt + r}Q${x0},${yt} ${x0 + r},${yt}H${x0 + w - r}Q${x0 + w},${yt} ${x0 + w},${yt + r}V${y(0)}Z" fill="${opt.color}"/>`;
    });
    host.innerHTML = `<svg width="${W}" height="${H}" role="img" aria-label="${esc(opt.aria || "bars")}">${g}${bars}<g class="hover"></g>
      <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}"/></svg>`;
    const svg = host.querySelector("svg"), hov = svg.querySelector(".hover");
    svg.querySelector(".hit").addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(n - 1, Math.floor((ev.clientX - r.left - m.l) / bw)));
      hov.innerHTML = `<rect x="${m.l + i * bw}" y="${m.t}" width="${bw}" height="${ih}" fill="var(--ink)" opacity=".05"/>`;
      showTip(tipRows(opt.dates[i], [{ label: opt.label || "Value", value: opt.yFmt(opt.values[i] || 0, true) }]), ev.clientX, ev.clientY);
    });
    svg.querySelector(".hit").addEventListener("pointerleave", () => { hov.innerHTML = ""; hideTip(); });
  });
}

function sparkline(series, color) {
  const pts = series.filter((p) => isNum(p.eq));
  if (pts.length < 2) return "";
  const W = 300, H = 66;
  const e0 = pts[0].eq, s0 = pts.find((p) => isNum(p.spy))?.spy;
  const book = pts.map((p) => p.eq / e0);
  const spy = s0 ? pts.map((p) => (isNum(p.spy) ? p.spy / s0 : null)) : [];
  const vals = book.concat(spy.filter(isNum));
  const lo = Math.min(...vals, 1), hi = Math.max(...vals, 1);
  const x = (i) => (i / (pts.length - 1)) * W;
  const y = (v) => 4 + (H - 8) - ((v - lo) / (hi - lo || 1)) * (H - 8);
  const path = (a) => a.map((v, i) => (isNum(v) ? `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}` : "")).join("");
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="${W}" y1="${y(1)}" y2="${y(1)}" stroke="var(--grid)" stroke-width="1" vector-effect="non-scaling-stroke"/>
    ${spy.length ? `<path d="${path(spy)}" fill="none" stroke="var(--spy)" stroke-width="1.5" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"/>` : ""}
    <path d="${path(book)}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
  </svg>`;
}

// ───────────────────────────── components ─────────────────────────────
function statusPill(st) {
  if (!st) return "";
  const gh = st.gh ? ` · Actions: ${st.gh.conclusion || st.gh.status} ${ago(st.gh.at)}` : "";
  const title = `Last log row ${st.last_log || "none"}; expected ${st.expected}${gh}${st.pending_today ? " · today's run not yet due" : ""}`;
  return `<span class="pill ${st.state}" title="${esc(title)}"><span class="dot"></span>${esc(st.label)}</span>`;
}
function kpiStrip(items) {
  return `<div class="kpis" style="--n:${items.length}">${items.map((k) => `
    <div class="kpi"><div class="k">${esc(k.k)}</div><div class="v ${k.cls || ""}">${k.v}</div>${k.s ? `<div class="s">${k.s}</div>` : ""}</div>`).join("")}</div>`;
}
function card(title, body, { sub = "", right = "", id = "", foot = "" } = {}) {
  return `<section class="card"${id ? ` id="${id}"` : ""}>
    <div class="card-head"><div><h2>${title}</h2>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${right}</div>
    ${body}${foot ? `<div class="card-foot">${foot}</div>` : ""}</section>`;
}
function seg(name, opts, on) {
  return `<div class="seg" role="tablist" data-seg="${name}">${opts.map((o) =>
    `<button type="button" role="tab" data-v="${o.v}" class="${o.v === on ? "on" : ""}" aria-selected="${o.v === on}">${o.label}${o.count != null ? `<span class="c">${o.count}</span>` : ""}</button>`).join("")}</div>`;
}
function bindSeg(root, name, fn) {
  const el = root.querySelector(`[data-seg="${name}"]`);
  if (!el) return;
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    el.querySelectorAll("button").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); });
    fn(b.dataset.v);
  });
}
function loading() { return `<div class="skeleton"></div><div class="grid g3 mt"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`; }
function errorBox(e) { return `<div class="callout warn"><span class="bar"></span><div><b>Couldn't load data.</b> ${esc(e.message || e)}</div></div>`; }

// ───────────────────────────── Desk ─────────────────────────────
async function renderDesk(view) {
  const d = await api("/api/desk");
  setAsOf(d.generated);
  const books = d.books;
  const ran = books.filter((b) => b.status.state === "ran").length;
  const beating = books.filter((b) => isNum(b.stats.vs_spy) && b.stats.vs_spy > 0).length;
  const lastLog = books.map((b) => b.status.last_log).filter(Boolean).sort().pop();
  const r = d.research;

  view.innerHTML = `
    <div class="page-head">
      <div><h1>Desk</h1><p>Three paper books, each against SPY over its own live window. Numbers come from the logs the bots commit after every run.</p></div>
    </div>
    ${kpiStrip([
      { k: "Last runs", v: `${ran} of ${books.length}`, s: `ran on schedule · latest log ${dshort(lastLog)}` },
      { k: "Beating SPY since inception", v: `${beating} of ${books.length}`, s: "same dates, price return" },
      { k: "Research ledger", v: r ? `${r.total}` : "—", s: r ? `${r.PASS} pass · ${r.FAIL} fail · ${r["PRE-REGISTERED"]} open` : "experiments.md not found" },
      { k: "Alerts, last 30 days", v: `${d.alerts_30d}`, s: "from alerts.log" },
    ])}
    <div class="grid g3 mt">${books.map(bookCard).join("")}</div>
    <div class="grid g-2-1 mt">
      ${card("Growth of 100, all books vs SPY", `<div class="card-body"><div class="legend" id="perf-legend"></div><div class="chart mt" id="perf"></div></div>`,
        { sub: "Each line rebased to 100 at the start of the window, or at the book's first day if later", right: seg("win", [{ v: "1M", label: "1M" }, { v: "3M", label: "3M" }, { v: "ALL", label: "All" }], "ALL") })}
      <div class="stack">${metaCard(d.meta)}${latestCard(r)}</div>
    </div>`;

  view.querySelectorAll(".book-card").forEach((el) => el.addEventListener("click", () => (location.hash = el.dataset.href)));
  view.querySelectorAll(".book-card").forEach((el) => el.addEventListener("keydown", (e) => { if (e.key === "Enter") location.hash = el.dataset.href; }));

  const draw = (win) => perfChart($("#perf", view), $("#perf-legend", view), books, win);
  draw("ALL");
  bindSeg(view, "win", draw);
}

function bookCard(b) {
  const s = b.stats, color = BOOK_COLOR[b.id];
  return `<article class="card book-card" tabindex="0" role="link" data-href="#/book/${b.id}" aria-label="${esc(b.name)} detail">
    <div class="top"><div class="name"><i class="swatch" style="background:${color}"></i>${esc(b.name)}</div>${statusPill(b.status)}</div>
    <div class="desc">${esc(b.desc)}</div>
    <div class="eq"><span class="big">${money(s.equity)}</span>
      <span class="chg ${cls(s.day_pnl)}">${money(s.day_pnl, { signed: true, cents: true })} (${pct(s.day_pct, 2)})</span><span class="muted" style="font-size:12px">last session</span></div>
    <div class="spark">${sparkline(b.series, color)}</div>
    <div class="mini">
      <div><div class="k">Return</div><div class="v ${cls(s.total_return)}">${pct(s.total_return)}</div></div>
      <div><div class="k">vs SPY</div><div class="v ${cls(s.vs_spy)}">${pct(s.vs_spy)}</div></div>
      <div><div class="k">Max DD</div><div class="v">${pct(s.max_drawdown, 1)}</div></div>
      <div><div class="k">Sharpe</div><div class="v">${num(s.sharpe)}</div></div>
    </div>
    <div class="foot-line"><span>${s.obs || 0} sessions since ${dshort(s.start)}</span><span class="go">Open book →</span></div>
  </article>`;
}

function perfChart(host, legend, books, win) {
  const allDates = [...new Set(books.flatMap((b) => b.series.map((p) => p.d)))].sort();
  if (!allDates.length) { host.innerHTML = `<div class="empty">No data</div>`; return; }
  const last = allDates[allDates.length - 1];
  const back = { "1M": 31, "3M": 92 }[win];
  let start = allDates[0];
  if (back) { const t = new Date(last); t.setDate(t.getDate() - back); start = t.toISOString().slice(0, 10); }
  const dates = allDates.filter((d) => d >= start);
  const maps = books.map((b) => new Map(b.series.map((p) => [p.d, p])));
  // SPY: take it from whichever book has a SPY print on each date.
  const spyAt = (d) => { for (const m of maps) { const p = m.get(d); if (p && isNum(p.spy)) return p.spy; } return null; };
  // Forward-fill at most 5 calendar days: a longer hole is a logging gap, and
  // the line should break there instead of drawing a flat month that never happened.
  const ffill = (arr) => {
    let lv = null, ld = null;
    return arr.map((v, i) => {
      if (isNum(v)) { lv = v; ld = dates[i]; return v; }
      if (ld && (new Date(dates[i]) - new Date(ld)) / 86400000 <= 5) return lv;
      return null;
    });
  };

  const series = books.map((b, k) => {
    const raw = dates.map((d) => maps[k].get(d)?.eq ?? null);
    const firstI = raw.findIndex(isNum);
    const filled = ffill(raw);
    const base = filled[firstI];
    return { label: b.name, color: BOOK_COLOR[b.id], values: filled.map((v) => (isNum(v) ? (v / base) * 100 : null)) };
  });
  const spyRaw = ffill(dates.map(spyAt));
  const s0 = spyRaw.find(isNum);
  series.push({ label: "SPY", color: "var(--spy)", dash: true, width: 1.5, values: spyRaw.map((v) => (isNum(v) ? (v / s0) * 100 : null)) });

  legend.innerHTML = series.map((s) => {
    const lastV = [...s.values].reverse().find(isNum);
    return `<span>${sw(s.color, s.dash ? "dash" : "line")}${esc(s.label)} <b class="tnum ${cls(lastV - 100)}" style="font-weight:600">${pct((lastV - 100) / 100)}</b></span>`;
  }).join("");
  lineChart(host, {
    dates, series, height: window.innerWidth > 1080 ? 470 : 280, zero: 100, aria: "Books indexed to 100 vs SPY",
    yFmt: (v) => v.toFixed(0), tipFmt: (v) => `${v.toFixed(1)} <span class="muted">(${pct((v - 100) / 100)})</span>`,
  });
}

function latestCard(r) {
  if (!r || !r.latest) return "";
  const rows = r.latest.map((e) => `<a class="list-row" href="#/research" style="display:flex">
    <div class="what"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
      <span class="mono ink2">${esc(e.id)}</span>${statusTag(e.status)}</div>
      <div style="font-weight:600;margin-top:2px">${esc(e.title)}</div>
      <div class="ink2 clamp2" style="font-size:12.5px;margin-top:2px">${esc(e.key)}</div></div></a>`).join("");
  return card("Latest from the ledger", rows, { sub: "Most recently dated research entries" });
}
function statusTag(st) {
  const label = st === "PRE-REGISTERED" ? "Pre-registered" : st[0] + st.slice(1).toLowerCase();
  return `<span class="pill ${st}"><span class="dot"></span>${label}</span>`;
}

function metaCard(meta) {
  if (!meta) return card("Meta-book allocator", `<div class="empty">No shadow allocator log yet</div>`, { sub: "Shadow only" });
  const stale = (Date.now() - new Date(meta.d).getTime()) / 86400000 > 7;
  const rows = Object.entries(meta.weights).map(([k, w]) => `
    <tr><td><span style="display:inline-flex;gap:8px;align-items:center"><i class="swatch" style="background:${BOOK_COLOR[k]}"></i>${{ champion: "Champion", challenger: "Challenger", volbot: "VolBot" }[k] || esc(k)}</span></td>
      <td style="width:55%"><div class="wbar"><div class="track"><div class="fill" style="width:${(w || 0) * 100}%;background:${BOOK_COLOR[k]}"></div></div><span class="tnum">${pct(w, 1, false)}</span></div></td></tr>`).join("");
  return card("Meta-book allocator", `<div class="tbl-wrap"><table><tbody>${rows}</tbody></table></div>`, {
    sub: `ERC shadow weights · not traded · as of ${dlong(meta.d)}`,
    right: stale ? `<span class="pill missed" title="The shadow log has not been written for over a week"><span class="dot"></span>Stale</span>` : "",
    foot: `${meta.obs_days} common days observed. ${esc(meta.note)}`,
  });
}

// ───────────────────────────── Book detail ─────────────────────────────
async function renderBook(view, id) {
  const b = await api(`/api/book/${id}`);
  setAsOf(null);
  const s = b.stats, det = b.detail || {}, color = BOOK_COLOR[id];
  const bookTabs = seg("book", [{ v: "champion", label: "Champion" }, { v: "challenger", label: "Challenger" }, { v: "volbot", label: "VolBot" }], id);

  const kpis = [
    { k: "Equity", v: money(s.equity), s: `from ${money(s.start_equity)} · ${dshort(s.start)}` },
    { k: "Last session", v: `<span class="${cls(s.day_pnl)}">${money(s.day_pnl, { signed: true, cents: true })}</span>`, s: pct(s.day_pct, 2) },
    { k: "Return", v: pct(s.total_return), cls: cls(s.total_return), s: `SPY ${pct(s.spy_return)} same window` },
    { k: "vs SPY", v: pct(s.vs_spy), cls: cls(s.vs_spy), s: "price return" },
    { k: "Drawdown", v: pct(s.drawdown, 1), s: `max ${pct(s.max_drawdown, 1)}` },
    { k: "Sharpe (live)", v: num(s.sharpe), s: `${s.obs} obs · vol ${pct(s.vol, 1, false)}` },
  ];

  view.innerHTML = `
    <div class="page-head">
      <div><div class="crumb"><a href="#/desk">Desk</a> / Books</div>
        <h1 style="display:flex;align-items:center;gap:10px"><i class="swatch" style="background:${color};width:12px;height:12px"></i>${esc(b.name)} ${statusPill(b.status)}</h1>
        <p>${esc(b.desc)}</p></div>
      ${bookTabs}
    </div>
    ${s.obs && s.obs < 126 ? `<div class="callout" style="margin-bottom:16px"><span class="bar"></span><div><b>${s.obs} sessions is a short sample.</b> A live Sharpe over fewer than ~6 months has a confidence interval wider than the number itself.${b.verdict ? " The graded verdict is the backtest evidence at the bottom of this page." : ""}</div></div>` : ""}
    ${kpiStrip(kpis)}
    <div class="stack mt">
      ${card("Equity vs SPY", `<div class="card-body"><div class="legend">
          <span>${sw(color)}${esc(b.name)}</span><span>${sw("", "dash")}SPY, same starting capital</span></div>
          <div class="chart mt" id="eq"></div>
          <div class="muted" style="font-size:12px;margin:10px 0 4px">Drawdown from running peak</div>
          <div class="chart" id="dd"></div></div>`, { sub: `${dlong(s.start)} to ${dlong(s.last)}`,
          foot: (b.gaps || []).length ? "Log gaps, joined by a straight line: " + b.gaps.map((g) => `${dshort(g.from)} to ${dshort(g.to)} (${g.missing} sessions missing)`).join("; ") + "." : "" })}
      ${id === "volbot" ? volbotSections(det) : equitySections(det, id)}
      ${b.verdict ? verdictCard(b.verdict) : ""}
    </div>`;
  bindSeg(view, "book", (v) => (location.hash = `#/book/${v}`));

  const dates = b.series.map((p) => p.d);
  const s0 = b.series.find((p) => isNum(p.spy))?.spy;
  const e0 = b.series[0]?.eq;
  lineChart($("#eq", view), {
    dates, height: 260, aria: "Equity vs SPY",
    series: [
      { label: "SPY (same capital)", color: "var(--spy)", dash: true, width: 1.5, values: b.series.map((p) => (isNum(p.spy) && s0 ? (p.spy / s0) * e0 : null)) },
      { label: b.name, color, values: b.series.map((p) => p.eq), fill: true, fillOpacity: 0.07 },
    ],
    yFmt: (v) => (v < 0 ? MINUS : "") + "$" + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 }),
    tipFmt: (v) => money(v, { cents: true }),
  });
  lineChart($("#dd", view), {
    dates, height: 110, zero: 0, aria: "Drawdown", ticks: 2,
    series: [{ label: "Drawdown", color: "var(--neg)", width: 1.5, values: b.series.map((p) => p.dd), fill: true, fillOpacity: 0.12 }],
    yFmt: (v) => pct(v, 0), tipFmt: (v) => pct(v, 2),
  });

  const mb = view.querySelector("[data-more]");
  if (mb) mb.addEventListener("click", () => {
    view.querySelectorAll("tr.extra").forEach((tr) => (tr.hidden = false));
    mb.remove();
  });
  if (det.error) return;
  if (id === "volbot") drawVolbot(view, det); else drawEquityBook(view, det, id);
}

function equitySections(det, id) {
  if (det.error) return errorBox(det.error);
  const w = det.weights;
  const cur = w.current || [];
  const dust = cur.filter((p) => p.w < 0.005);
  const hold = cur.filter((p) => p.w >= 0.005).map((p, i) => {
    const key = (w.symbols || []).includes(p.sym) ? p.sym : p.sym === "SHV" ? "Cash" : "Other";
    const c = colorFor(w.symbols, key);
    return `<tr><td><span class="mono">${esc(p.sym)}</span>${p.sym === "SHV" ? ' <span class="muted">cash sleeve</span>' : ""}</td>
      <td style="width:58%"><div class="wbar"><div class="track"><div class="fill" style="width:${Math.min(100, p.w * 100)}%;background:${c}"></div></div><span class="tnum" style="min-width:48px;text-align:right">${pct(p.w, 1, false)}</span></div></td></tr>`;
  }).join("");
  const turn = w.turnover || [];
  const avgT = turn.length ? turn.reduce((a, t) => a + (t.v || 0), 0) / turn.length : null;
  const ov = det.overlay, rg = det.regime;
  const lastOv = ov.series.length ? ov.series[ov.series.length - 1].v : null;

  return `
    <div class="grid g-1-1">
      ${card("Holdings", `<div class="tbl-wrap"><table><thead><tr><th>Symbol</th><th>Target weight</th></tr></thead><tbody>${hold || `<tr><td colspan="2" class="empty">No weights logged</td></tr>`}</tbody></table></div>`
        + (dust.length ? `<div class="card-foot">${dust.length} more under 0.5%: ${dust.map((p) => esc(p.sym)).join(", ")} (${pct(dust.reduce((a, p) => a + p.w, 0), 1, false)} combined)</div>` : ""),
        { sub: `Target weights logged ${dlong(w.as_of)}. Live fills can drift from these.` })}
      ${card("Allocation over time", `<div class="card-body"><div class="legend" id="alloc-legend"></div><div class="chart mt" id="alloc"></div></div>`,
        { sub: "Top six symbols by average weight; everything else in Other" })}
    </div>
    <div class="grid g-1-1">
      ${card("Risk overlay", `<div class="card-body"><div class="chart" id="overlay"></div>
          ${rg ? `<div class="muted" style="font-size:12px;margin:12px 0 6px;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><span>Regime by session</span>
            <span class="legend" style="font-size:12px"><span><i class="swatch rg-RISK_ON"></i>Risk-on</span><span><i class="swatch rg-CHOPPY"></i>Choppy</span><span><i class="swatch rg-RISK_OFF"></i>Risk-off</span></span></div>
            <div class="regime-strip" id="regime"></div>` : ""}</div>`,
        { sub: esc(ov.label), right: `<span class="tnum" style="font-weight:600">${isNum(lastOv) ? (id === "champion" ? pct(lastOv, 0, false) : num(lastOv, 2)) : "—"}</span>`,
          foot: esc(ov.target_note) + (rg?.signals ? ` Latest vote ${dshort(rg.signals.at)}: vol ${esc(rg.signals.vol)}, trend ${esc(rg.signals.trend)}, flight ${esc(rg.signals.flight)} → <b>${esc(rg.current)}</b>, strategy ${esc(rg.strategy)}.` : "") })}
      ${card("Turnover", `<div class="card-body"><div class="chart" id="turn"></div></div>`,
        { sub: "One-way: ½ × Σ|Δweight| between logged sessions",
          right: avgT != null ? `<span class="tnum" style="font-weight:600">${(avgT * 252).toFixed(0)}× / yr</span>` : "",
          foot: avgT != null ? `Average ${pct(avgT, 1, false)} per session over ${turn.length} sessions, annualised at 252 days. Every unit of turnover pays the spread.` : "" })}
    </div>
    ${card("Rebalances", rebalanceTable(det.rebalances), { sub: `${det.rebalances.length} sessions with orders, newest first` })}`;
}

function colorFor(symbols, key) {
  if (key === "Cash") return "var(--s-cash)";
  if (key === "Other") return "var(--s-other)";
  const i = (symbols || []).indexOf(key);
  return SERIES_VARS[i] || "var(--s-other)";
}

function rebalanceTable(rows) {
  if (!rows.length) return `<div class="empty">No rebalances logged</div>`;
  const notes = rows.some((r) => r.note);
  const body = rows.map((r, i) => `<tr${i >= 12 ? ' class="extra" hidden' : ""}>
    <td class="tnum" style="white-space:nowrap">${dshort(r.d)}</td>
    <td class="r tnum">${r.orders}</td>
    <td class="r tnum">${pct(r.turnover, 1, false)}</td>
    <td>${r.moves.map((m) => `<span class="chip"><span class="${cls(m.dw)}">${sign(m.dw)}${Math.abs(m.dw * 100).toFixed(1)}</span> ${esc(m.sym)}</span>`).join("") || '<span class="muted">rounding only</span>'}</td>
    ${notes ? `<td class="muted hide-sm" style="font-size:12px">${esc(r.note)}</td>` : ""}</tr>`).join("");
  return `<div class="tbl-wrap"><table><thead><tr><th>Date</th><th class="r">Orders</th><th class="r">Turnover</th><th>Largest weight moves (pts)</th>${notes ? '<th class="hide-sm">Note</th>' : ""}</tr></thead><tbody>${body}</tbody></table></div>`
    + (rows.length > 12 ? `<button type="button" class="more-btn" data-more>Show all ${rows.length} sessions</button>` : "");
}

function drawEquityBook(view, det, id) {
  const w = det.weights;
  const keys = (w.symbols || []).map((k) => ({ key: k, label: k === "Cash" ? "Cash (SHV)" : k, color: colorFor(w.symbols, k) }));
  $("#alloc-legend", view).innerHTML = keys.map((k) => `<span>${sw(k.color, "")}${esc(k.label)}</span>`).join("");
  stackChart($("#alloc", view), { dates: w.rows.map((r) => r.d), keys, rows: w.rows, height: 230 });

  const ov = det.overlay;
  const series = [{ label: id === "champion" ? "Gross exposure" : "Vol scaler", color: "var(--accent)", values: ov.series.map((p) => p.v), fill: true, fillOpacity: 0.08 }];
  lineChart($("#overlay", view), {
    dates: ov.series.map((p) => p.d), series, height: 190, yMin: 0, yMax: 1, aria: ov.label,
    yFmt: (v) => (id === "champion" ? pct(v, 0, false) : v.toFixed(2)),
    tipFmt: (v) => (id === "champion" ? pct(v, 1, false) : v.toFixed(3)),
    extraTip: ov.est_vol ? (i) => [{ label: "Est. vol", value: pct(ov.est_vol[i]?.v, 1, false) }] : null,
  });
  if (det.regime) {
    $("#regime", view).innerHTML = det.regime.series.map((r) => `<i class="rg-${esc(r.regime)}" style="flex:1" title="${dshort(r.d)} · ${esc(r.regime)} · ${esc(r.strategy)}"></i>`).join("");
  }
  barChart($("#turn", view), { dates: w.turnover.map((t) => t.d), values: w.turnover.map((t) => t.v), color: "var(--accent)", height: 190, label: "Turnover", yFmt: (v) => pct(v, 0, false), aria: "Turnover per session" });
}

function volbotSections(det) {
  if (det.error) return errorBox(det.error);
  const ts = det.trade_stats, st = det.state;
  const trades = det.trades.map((t) => `<tr>
      <td class="tnum" style="white-space:nowrap">${dshort(t.entry)} → ${dshort(t.exit)}</td>
      <td><span class="mono">${esc(t.u)}</span> <span class="muted">exp ${dshort(t.exp)}</span></td>
      <td class="r tnum">${t.qty}</td>
      <td class="tnum hide-sm muted">${esc(t.strikes)}</td>
      <td class="r tnum">${money(t.credit, { cents: true })}</td>
      <td class="r tnum">${money(t.exit_cost, { cents: true })}</td>
      <td class="r tnum ${cls(t.pnl)}" style="font-weight:600">${money(t.pnl, { signed: true, cents: true })}</td>
      <td>${esc(t.reason)}</td></tr>`).join("");
  const flags = det.flags || {};
  return `
    <div class="callout warn"><span class="bar"></span><div><b>Entries halted.</b> ${esc(det.note)}. Open rungs: ${st.open_rungs}. Last entries: ${Object.entries(st.last_entry || {}).map(([u, d]) => `${esc(u)} ${dshort(d)}`).join(", ") || "none"}.</div></div>
    ${card("Closed trades", `<div class="tbl-wrap"><table><thead><tr><th>Held</th><th>Underlying</th><th class="r">Qty</th><th class="hide-sm">Put / call spreads</th><th class="r">Credit</th><th class="r">Exit</th><th class="r">P&amp;L</th><th>Reason</th></tr></thead><tbody>${trades || `<tr><td colspan="8" class="empty">No closed trades</td></tr>`}</tbody></table></div>`,
      { sub: `${ts.n} condors closed · ${ts.wins} winners`, right: `<span class="tnum ${cls(ts.realized)}" style="font-weight:600">${money(ts.realized, { signed: true, cents: true })} realised</span>` })}
    <div class="grid g-1-1">
      ${card("Implied vol by underlying", `<div class="card-body"><div class="legend"><span>${sw("var(--s1)")}SPY</span><span>${sw("var(--s2)")}QQQ</span><span>${sw("var(--s3)")}IWM</span></div><div class="chart mt" id="iv"></div></div>`,
        { sub: "Index vol (VIX / VXN / RVX) logged each session",
          foot: `Latest: term structure ${flags.contango ? "in contango" : flags.contango === false ? "inverted" : "unknown"}; rich-vol tercile ${Object.entries(flags.rich || {}).filter(([, v]) => v).map(([u]) => u).join(", ") || "none"}.` })}
      ${card("Capital at risk", `<div class="card-body"><div class="chart" id="atrisk"></div></div>`, { sub: "Max loss of open condors / equity", foot: esc(det.overlay.target_note) })}
    </div>`;
}

function drawVolbot(view, det) {
  const d = det.iv.map((r) => r.d);
  lineChart($("#iv", view), {
    dates: d, height: 200, aria: "Implied vol",
    series: [["SPY", "var(--s1)"], ["QQQ", "var(--s2)"], ["IWM", "var(--s3)"]].map(([k, c]) => ({ label: k, color: c, values: det.iv.map((r) => r[k]) })),
    yFmt: (v) => v.toFixed(0), tipFmt: (v) => v.toFixed(1),
  });
  lineChart($("#atrisk", view), {
    dates: det.overlay.series.map((p) => p.d), height: 200, yMin: 0, yMax: 0.25, zero: 0, aria: "Capital at risk",
    series: [{ label: "At risk", color: "var(--accent)", values: det.overlay.series.map((p) => p.v ?? 0), fill: true, fillOpacity: 0.1 }],
    yFmt: (v) => pct(v, 0, false), tipFmt: (v) => pct(v, 1, false),
    extraTip: (i) => [{ label: "Max loss", value: money(det.overlay.series[i].usd) }, { label: "Open rungs", value: String(det.overlay.series[i].rungs) }],
  });
}

function verdictCard(v) {
  const suff = v.sufficiency || "—";
  const st = suff === "CONFIRMED" ? "PASS" : suff === "INSUFFICIENT" ? "FAIL" : "INCONCLUSIVE";
  const ci = v.sharpe_ci95 ? `${num(v.sharpe_ci95[0])} to ${num(v.sharpe_ci95[1])}` : "—";
  return card("Backtest evidence", kpiStrip([
    { k: "Grade", v: `<span class="pill ${st}" style="font-size:12.5px"><span class="dot"></span>${esc(suff)}</span>`, s: `${num(v.years, 1)} yrs of history` },
    { k: "Sharpe", v: num(v.sharpe), s: `95% CI ${ci}` },
    { k: "Deflated Sharpe", v: pct(v.dsr, 1, false), s: `K = ${v.k_trials} configs tried` },
    { k: "CAGR / vol", v: `${pct(v.cagr, 1, false)}`, s: `vol ${pct(v.vol, 1, false)} · β ${num(v.beta)}` },
    { k: "Max drawdown", v: pct(v.maxdd, 1), s: dlong(v.maxdd_date) },
    { k: "P(down year)", v: pct(v.p_neg_1yr, 0, false), s: `P(−20% DD in 1y) ${pct(v.p_dd20_1yr, 0, false)}` },
  ]).replace('class="kpis"', 'class="kpis" style="border:0;box-shadow:none;border-top:1px solid var(--line);border-radius:0;margin-top:12px;--n:6"'),
  { sub: `Backtest, not live. Graded by the verdict engine, ${esc(v.generated || "")}` });
}

// ───────────────────────────── Research ─────────────────────────────
const STATUSES = ["PASS", "FAIL", "INCONCLUSIVE", "MEASURED", "PRE-REGISTERED"];
async function renderResearch(view) {
  const d = await api("/api/research");
  setAsOf(null);
  if (!d.available) {
    view.innerHTML = `<div class="page-head"><div><h1>Research</h1><p>The pre-registered experiment ledger.</p></div></div>
      <div class="callout warn"><span class="bar"></span><div><b>Ledger not found.</b> ${esc(d.hint)}</div></div>`;
    return;
  }
  const ex = d.experiments;
  const count = (s) => ex.filter((e) => e.status === s).length;
  const premise = ex.filter((e) => e.premise_passed).length;
  let filter = "ALL", q = "";

  view.innerHTML = `
    <div class="page-head"><div><h1>Research</h1>
      <p>Pre-registered experiments: the bar is written before the data is touched, and kills are logged as carefully as wins.</p></div></div>
    <div class="callout" style="margin-bottom:16px"><span class="bar"></span><div>
      <b>${count("FAIL")} of ${ex.length} entries failed, ${count("PASS")} passed.</b> In ${premise} of the failures the premise held and the trade still lost: the signal was real, and execution or cost killed it.</div></div>
    <div class="toolbar">
      ${seg("st", [{ v: "ALL", label: "All", count: ex.length }].concat(STATUSES.map((s) => ({ v: s, label: s === "PRE-REGISTERED" ? "Pre-registered" : s[0] + s.slice(1).toLowerCase(), count: count(s) }))), "ALL")}
      <input class="search" type="search" placeholder="Search experiments" aria-label="Search experiments">
    </div>
    <section class="card" id="exlist"></section>
    <p class="muted" style="font-size:12px;margin-top:10px">Parsed from <span class="mono">${esc(d.source.split("/").slice(-2).join("/"))}</span>, modified ${ago(d.modified)}. Status is read from each entry's Status line and result headers; a kill anywhere in an entry counts as FAIL.</p>`;

  const list = $("#exlist", view);
  const draw = () => {
    const ql = q.toLowerCase();
    const rows = ex.filter((e) => (filter === "ALL" || e.status === filter) &&
      (!ql || (e.id + " " + e.title + " " + e.key + " " + e.status_text).toLowerCase().includes(ql)));
    list.innerHTML = rows.length ? rows.map(expRow).join("") : `<div class="empty">No experiments match</div>`;
  };
  draw();
  bindSeg(view, "st", (v) => { filter = v; draw(); });
  $(".search", view).addEventListener("input", (e) => { q = e.target.value; draw(); });
  list.addEventListener("click", (e) => {
    const b = e.target.closest(".exp > button");
    if (!b) return;
    const row = b.parentElement;
    row.classList.toggle("open");
    b.setAttribute("aria-expanded", row.classList.contains("open"));
  });
}

function expRow(e) {
  const label = e.status === "PRE-REGISTERED" ? "Pre-registered" : e.status[0] + e.status.slice(1).toLowerCase();
  return `<div class="exp"><button type="button" aria-expanded="false">
    <div class="id">${esc(e.id)}</div>
    <div class="body"><div class="t">${esc(e.title)}</div><div class="key">${esc(e.key)}</div></div>
    <div class="meta"><span class="pill ${e.status}"><span class="dot"></span>${label}</span>
      ${e.premise_passed ? `<span class="pill tag" title="A premise gate passed before the trade failed">premise held</span>` : ""}
      <span class="dt">${dshort(e.last_date || e.registered)}</span></div>
  </button>
  <div class="more"><dl>
    <dt>Status line</dt><dd>${esc(e.status_text) || "—"}</dd>
    <dt>Registered</dt><dd class="tnum">${dlong(e.registered)}</dd>
    ${e.k ? `<dt>Trials</dt><dd>${esc(e.k)}</dd>` : ""}
  </dl></div></div>`;
}

// ───────────────────────────── Health ─────────────────────────────
async function renderHealth(view) {
  const [h, d] = await Promise.all([api("/api/health"), api("/api/desk")]);
  setAsOf(d.generated);
  const runs = h.runs || [];
  const conclusionPill = (r) => {
    if (!r) return `<span class="pill"><span class="dot"></span>No runs</span>`;
    const c = r.status !== "completed" ? "scheduled" : r.conclusion === "success" ? "ran" : r.conclusion === "failure" ? "failed" : "missed";
    const lab = r.status !== "completed" ? r.status.replace("_", " ") : r.conclusion;
    return `<span class="pill ${c}"><span class="dot"></span>${esc(lab)}</span>`;
  };
  const tiles = d.books.map((b) => {
    const fails = b.status.fails_recent || 0;
    return { k: b.name, v: statusPill(b.status), s: `log ${dshort(b.status.last_log)} · Actions ${b.status.gh ? ago(b.status.gh.at) : "n/a"}${fails ? ` · ${fails} failed in last 40` : ""}` };
  });
  tiles.push({ k: "Alerts, last 30 days", v: String(d.alerts_30d), s: h.alerts.length ? `latest ${dshort(h.alerts[0].at)}` : "none logged" });

  const runRows = runs.slice(0, 18).map((r) => `<tr>
    <td>${conclusionPill(r)}</td>
    <td>${esc(r.workflowName)}</td>
    <td class="muted hide-sm">${esc(r.event)}</td>
    <td class="tnum" style="white-space:nowrap" title="${esc(r.createdAt)}">${ago(r.createdAt)}</td>
    <td class="r tnum hide-sm">${r.updatedAt && r.createdAt ? Math.max(0, Math.round((new Date(r.updatedAt) - new Date(r.createdAt)) / 1000)) + "s" : "—"}</td></tr>`).join("");
  const fresh = h.freshness.map((f) => `<tr><td>${esc(f.label)}<div class="muted mono" style="font-size:11px">${esc(f.path)}</div></td>
    <td class="r tnum">${f.exists ? f.rows : "—"}</td><td class="r tnum">${f.exists ? dshort(f.last) : '<span class="neg">missing</span>'}</td></tr>`).join("");
  const commits = h.commits.map((c) => `<div class="list-row"><div class="when" title="${esc(c.at)}">${ago(c.at)}</div>
    <div class="what"><div class="s">${esc(c.subject)}</div><div class="muted" style="font-size:12px"><span class="mono">${esc(c.sha)}</span> · ${esc(c.author)}</div></div></div>`).join("");
  const alerts = h.alerts.map((a) => `<div class="list-row"><span class="sev ${a.severity}" title="${a.severity}"></span>
    <div class="what"><div class="clamp2" title="${esc(a.msg)}"><b style="font-weight:600">${esc(a.category)}</b> <span class="ink2">${esc(a.msg)}</span></div></div>
    <div class="when" style="text-align:right">${dshort(a.at)} ${a.at.slice(11, 16)}</div></div>`).join("");

  view.innerHTML = `
    <div class="page-head"><div><h1>Health</h1><p>Did every job run, is every log current, and what did the bots complain about.</p></div></div>
    ${kpiStrip(tiles)}
    <div class="grid g-2-1 mt">
      ${card("Workflow runs", h.runs_error ? `<div class="empty">GitHub Actions unavailable: ${esc(h.runs_error)}</div>` :
        `<div class="tbl-wrap"><table><thead><tr><th>Result</th><th>Workflow</th><th class="hide-sm">Trigger</th><th>Started</th><th class="r hide-sm">Duration</th></tr></thead><tbody>${runRows}</tbody></table></div>`,
        { sub: "Most recent 18, via the local gh CLI" })}
      ${card("Data freshness", `<div class="tbl-wrap"><table><thead><tr><th>Log</th><th class="r">Rows</th><th class="r">Last row</th></tr></thead><tbody>${fresh}</tbody></table></div>`, { sub: "What this page is reading" })}
    </div>
    <div class="grid g-1-1 mt">
      ${card("Alerts", alerts || `<div class="empty">alerts.log not found</div>`, { sub: h.alerts_path ? "alerts.log, newest first" : "alerts.log is gitignored and absent here" })}
      ${card("Recent commits", commits, { sub: "Bot log commits and code changes" })}
    </div>`;
}

// ───────────────────────────── shell ─────────────────────────────
function setAsOf(iso) {
  const el = $("#asof");
  if (iso) el.textContent = `Updated ${new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
}
async function route() {
  const view = $("#view");
  const h = location.hash.replace(/^#\/?/, "") || "desk";
  const [page, arg] = h.split("/");
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === page));
  hideTip();
  view.innerHTML = loading();
  const titles = { desk: "Desk", book: "Book", research: "Research", health: "Health" };
  document.title = `${titles[page] || "Desk"} · Trading Desk`;
  try {
    if (page === "book") await renderBook(view, ["champion", "challenger", "volbot"].includes(arg) ? arg : "champion");
    else if (page === "research") await renderResearch(view);
    else if (page === "health") await renderHealth(view);
    else await renderDesk(view);
  } catch (e) {
    console.error(e);
    view.innerHTML = errorBox(e);
  }
}
window.addEventListener("hashchange", route);
$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh");
  b.classList.add("spin");
  cache.clear();
  await $("#theme").addEventListener("click", () => {
  const root = document.documentElement;
  const cur = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try { localStorage.setItem("desk-theme", next); } catch (e) {}
  route();  // charts read CSS vars at draw time only via var(), but redraw keeps hover state clean
});
route();
  b.classList.remove("spin");
});
$("#theme").addEventListener("click", () => {
  const root = document.documentElement;
  const cur = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try { localStorage.setItem("desk-theme", next); } catch (e) {}
  route();  // charts read CSS vars at draw time only via var(), but redraw keeps hover state clean
});
route();
