# Defined-Risk Volatility-Premium Sleeve — Build Spec

## Why (the Sharpe thesis)
Add a **genuinely uncorrelated** return stream to lift the COMBINED book Sharpe toward ~1.0.
Combining uncorrelated streams is the only real free lunch: combined Sharpe ≈ single Sharpe × √N.
The current ETF book is ~0.56 (validated, 7.4yr). Of the five families we tested this cycle
(stat-arb, broad trend, niche trend, merger-arb, vol-premium) **this is the lone survivor** —
the one with a real, durable, *risk-premium* edge. So it earns the build.

## What we validated — and what we did NOT
Evidence (FRED 2016–2026, includes Feb-2018 Volmageddon + Q4-2018 + COVID-2020):
- Avg implied − realized = **+3.8 vol points**; implied > realized in **82% of months**.
- Short-vol proxy P&L: ann. Sharpe **~1.02**, skew **−0.33**.

**HONEST CAVEAT (read this twice):** that proxy *understates* the true tail. It used
start-of-month VIX and *net* monthly moves, so it misses intramonth gamma destruction. The
naked version of this trade is what blew up **XIV (went to ZERO on Feb 5, 2018)**. The premium
is real; the danger is that a naive implementation is "picking up pennies in front of a
steamroller." Everything below exists to make it **survivable**, not to juice the yield.

## The strategy: defined-risk short volatility
Sell **SPY put credit spreads** (and later, iron condors), 30–45 DTE. Collect premium up front;
keep it if SPY doesn't fall through your short strike. The long wing **caps your max loss on
every single trade** — that's the entire reason we can run this at all.

**Start with put credit spreads, not naked, not iron condors:**
- **Defined-risk** → known worst case per trade → you can size to survive it. Naked = unbounded
  loss = ruin = XIV. Off the table, permanently.
- **Put side first** → the VRP is *richest* on the downside: crash insurance is systematically
  over-priced (that's the durable risk premium — you're paid to insure others). The call side
  has thinner premium; add it (iron condor) only once the put sleeve is validated.

## Structure (concrete defaults — these are the knobs to test)
- **Underlying:** SPY to start (liquid, penny-wide near ATM). Consider XSP later (cash-settled,
  1/10 SPX, Section-1256 tax treatment, no early-assignment).
- **DTE:** 30–45 days at entry. Enough theta, avoids the brutal gamma of <21 DTE.
- **Short strike:** ~16-delta (≈1 SD OTM, ~84% prob. OTM). **Long strike:** 5–10 pts below short
  (this width *is* your defined risk).
- **Profit-take:** close at **50% of max credit** (don't be greedy for the last pennies).
- **Time stop:** close/roll at **21 DTE** regardless (gamma risk climbs after).
- **Loss stop:** close at **~2× credit** loss, or if the short strike is breached.

## Entry filters (the regime gates — this is where survival is won)
1. **VIX TERM-STRUCTURE FILTER (the key one).** Only open when the curve is in **contango**
   (front < back: VIX9D < VIX < VIX3M). When it **inverts to backwardation** (front > back),
   the market is stressed — **stop opening new positions.** This one filter sidesteps the worst
   of the vol spikes. (FRED gives VIXCLS; pull VIX9D / VIX3M from Cboe to build the ratio.)
2. **Don't sell into a spike.** Skip new entries when VIX is already extended (e.g. > 30, or
   above its trailing 80th percentile). You want to sell *elevated-but-calming*, not *exploding*.
3. **Event filter (optional).** Lighten or skip new entries into FOMC / CPI / major earnings
   clusters. (Reuse the bot's existing event calendar.)

## The tail hedge (NON-NEGOTIABLE)
Spend a **small slice** of collected premium on far-OTM long puts (or a long VIX call) — convex
protection for the genuine crash. This caps the *sleeve-level* tail beyond the per-trade spread
width and turns a −50% month into a −10% month. Net premium is lower; **survival > yield.**
This is the entire lesson of XIV in one line.

## ML crash-throttle (optional, LATER)
Reuse the existing crash classifier (`OVERLAY_ML_ENABLED` infra). In calm conditions, full size;
as crash-probability rises → cut new-position size / push the short strike further OTM / pause.
This is a **refinement on top of** the term-structure filter, not a replacement. Build and
validate the rules-based version FIRST; add ML only after the base proves out.

## Risk controls (summary)
- **Defined-risk on every position** (hard per-trade cap) — the primary defense.
- **Vol-based sizing:** scale total max-loss-at-risk to a target (e.g. risk ≤ X% of the sleeve
  per expiry cycle), same constant-risk principle as the champion's overlay.
- **Term-structure circuit breaker** + **don't-sell-into-spike** (above).
- **Tail hedge** (above).
- **Greeks caps:** limit net short vega and net short delta of the whole sleeve.
- **Defined kill:** if the sleeve draws down −X%, stand down and review before re-entering.

## Costs (do NOT skip — this is what kills naive option-selling)
- **Bid-ask:** model **half the spread per leg**, on entry AND exit. 2 legs for a credit spread,
  4 for a condor. Wings are wider than ATM — don't assume penny-wide everywhere.
- **Commissions/slippage:** Alpaca options are commission-free, but model slippage anyway
  (~$0.01–0.02/share equiv). A backtest with perfect fills WILL overstate the edge.
- **Pin/assignment risk:** close before expiry; never hold a short option into the close.

## The DATA problem (the honest hard part)
Backtesting options needs historical *option* prices, which are **not free or clean**. Paths:
- **(a) MODEL the premium from VIX via Black-Scholes** — set σ ≈ VIX/100 (× a put-skew
  multiplier ~1.1–1.3 for OTM puts), price each leg analytically every day, mark-to-model the
  spread, simulate P&L. Fast, free, approximate. **This is the buildable first-pass — do this.**
- **(b) Vendor data** (CBOE DataShop, ORATS, OptionMetrics) — accurate, costs money, out of scope.
- **(c) Proxy ETF** (PUTW put-write, or SVOL) — directional sanity check only, the way MNA was
  for merger-arb. Not a substitute for (a).

**Recommendation: build (a), cross-check direction against (b-free proxy) PUTW/SVOL, and be
LOUD in the output about every modeling assumption.** An approximate-but-honest backtest beats a
precise-but-overfit one.

## Math (for the model-based backtest)
- **VRP** = E[implied variance] − E[realized variance]; you capture it by *selling* options
  priced at implied vol and paying out *realized* moves.
- **Price each leg:** Black-Scholes with σ = VIX/100 × skew-multiplier; `scipy.stats.norm`.
- **Daily P&L** of a short spread = −Δ(spread mark) − costs.
- **Greeks intuition:** short **vega** (hurt by vol spikes), short **gamma** (hurt by big moves),
  long **theta** (helped by time passing). The filters exist to dodge the vega/gamma days.
- **Sizing:** risk-per-trade = width − net credit; choose N spreads so sleeve
  max-loss-at-risk = target.

## Validation plan (the whole point — same discipline as the stat-arb kill)
1. Model-based backtest 2016–2026, **must include Feb-2018, Q4-2018, COVID-2020**, WITH costs and
   the tail hedge.
2. **Filter A/B:** run term-structure filter ON vs OFF — quantify how much it saves in the spikes.
3. **Stress test:** what is the worst single month WITH defined-risk + tail hedge? It must be
   survivable. If the worst month still ruins the sleeve, the structure is wrong.
4. **Purged / walk-forward CV** + **Deflated Sharpe** (K = # of strike/DTE/filter configs tried —
   be honest about the multiple testing).
5. Cross-check direction vs PUTW/SVOL proxy.
6. **DECISION RULE (pre-registered):**
   - **DEPLOY-QUEUE** only if ALL hold: net-of-cost Sharpe > 0.5 · DSR clears (not a
     multiple-testing artifact) · worst-month is survivable WITH the hedge · correlation to the
     equity book is genuinely low.
   - Otherwise **KILL.** A short-vol stream that blows up in the one month that matters is *worse*
     than nothing — it correlates to your equity book exactly when you can't afford it.

## Integration into the book
- Run as a **separate paper account** (4th stream), Alpaca **Options Level 3**.
- Diversification value: low correlation in **normal** times. **Honest catch:** short vol is
  correlated to equities IN A CRASH (both lose together). The term-structure filter + tail hedge
  exist precisely to break that crash-correlation — **validation must confirm they do**, or the
  sleeve isn't actually diversifying when it counts.
- End-state: champion (growth) + challenger (diversified) + vol-premium (defined-risk short vol),
  viewed under one risk lens → the ~1.0 combined-Sharpe target.

## Phased plan
1. **Model** — build the Black-Scholes leg-pricer + spread simulator from VIX/SPY.
2. **Backtest** — put credit spreads with costs, filters, tail hedge; metrics across all spikes.
3. **Validate** — purged CV + DSR + worst-month stress; apply the decision rule (queue or kill).
4. **Paper** — if it survives, trade ONE small defined-risk spread per cycle on the Level-3 paper
   account; forward-track vs the equity book.
5. Only trust it after a forward window that includes at least one real vol bump.

## Tech
- Python: numpy / pandas, `scipy.stats.norm` (Black-Scholes), reuse the DSR + purged-CV tools.
- Data: **FRED** (VIXCLS, SP500 — free, has 2018 + COVID); **Cboe** for VIX9D / VIX3M term
  structure; **Alpaca** for SPY bars and (live) option chains/quotes + paper execution (Level 3).
- No C++ needed (daily marks, not HFT).

## Honest expectations
- This is a **risk premium**, not a free lunch: you're *paid to insure other people against
  crashes*, so by construction you lose in crashes. The edge is durable *because* it's
  uncomfortable to hold. Defined-risk + term-structure filter + tail hedge are what turn it from a
  blow-up into a sleeve. If validation shows the tail is still un-survivable → **KILL it**, same
  as we killed stat-arb.
- [removed: career note]
```
