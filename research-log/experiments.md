# Research Journal

The law: hypothesis BEFORE data. Every variant tried increments K. DSR computed
with honest K. Kills get logged with the same care as wins — a clean kill is a
result, not a failure. Nothing deploys mid-A/B; survivors queue for the merge.

Cumulative K ledger (all experiments, for honest DSR penalties):
- Champion-era configs (pre-journal): K = 11 (DSR 99.4% on best)
- Challenger sleeve configs: K = 4 (DSR ~100% on shipped config)
- EXP-001: K = 0 SPENT (Part A premise gate failed 2026-07-11 — the two planned
  variants never ran; descriptive gate work does not count toward strategy-K)
- EXP-002: K = 1 (single HAR-RV config, as pre-registered — no grid was run)
- EXP-003: K = 2 planned (AR de-risk ×0.5 @ p80, ×0.5 @ p90)
- EXP-004: K = 0 planned (measurement only, families pre-named; strategy-K
  starts at EXP-004b if measurement confirms)
- EXP-005: K = 2 SPENT (inversion ×0.5, inversion ×0.0 — both killed by the
  frozen bar; premise itself confirmed real)
- EXP-007b: K = 1 SPENT (iron fly wings @ 2× — killed, mean −4.3%; V2 @ 1.5×
  not run, strictly-worse prior)
- EXP-006: K = 0 SPENT (Part A premise gate failed — variants never ran)
- EXP-009: K = 0 SPENT for Part A (PASSED, effect concentrated in top decile);
  K = 2 unlocked for Part B but NOT SPENT — Part B deliberately not implemented
- EXP-010: K = 0 SPENT (measurement — real OPRA quotes vs modeled prices).
  FAILED: ARM A Sharpe −1.54, ARM B −1.24 vs a 0.70 bar. Sleeve not extended;
  no tuning attempted, per the pre-registered FAIL rule.
- EXP-011: K = 0 for Part A (premium measurement) and Part A2 (cost
  feasibility); K = 1 planned for Part B — ONE pre-specified implementation,
  spent only if A and A2 both pass. No second implementation is authorised.
- EXP-016: K = 0 for Phase 1 (exploration on the calibration window, markets
  closing before 2026-09-01; no verdicts). Phase 2 REGISTERED 2026-09-13:
  K = 2 (H1, H2), each gated at P < 0.025. EXP-016 is closed to new hypotheses.
- EXP-017: K = 2 SPENT 2026-09-13. Part A PASS (beta 0.259); Part B FAIL on the
  holdout (-3.23c/contract, 0/7 cities). No second trade rule is authorised, and the
  holdout (2025-06-01..2026-08-13, 7 series) is spent for any weather hypothesis.

---

## EXP-001 — Scheduled-event de-risking (FOMC / CPI / NFP)

**Status:** PRE-REGISTERED 2026-06-10 · EXP-001a (NFP) run 2026-07-11 — **KILLED
AT THE PART A GATE** (premise false). EXP-001b (FOMC) remains open, pending the
hand-filled 2006-2022 Fed calendar — its premise is untested and plausibly
different (2pm ET intraday decision vs pre-open release).
**Origin:** June 5 2026 crash was a jobs-report day; the book took its worst
single-day hit with no signal from the vol overlay (trailing vol is blind to
known future events).

### Hypothesis (written before touching data)
Daily returns on scheduled macro-event days (FOMC decision, CPI release,
NFP/jobs report) have materially higher volatility and fatter left tails than
ordinary days. Therefore halving the challenger book's risky exposure on those
days improves Sharpe and max drawdown at negligible CAGR cost.

### Why it could be real (mechanism, not data-mining)
These are the only days when a large repricing is SCHEDULED. Realized-vol
models can't see them coming (the spike hasn't happened yet), so a calendar
adds information the overlay structurally lacks. Defensive use only.

### Data
- Prices: challenger/prices_cache.parquet (2005-2026, already clean Tiingo)
- Event dates (2006-2026), saved to research/event_dates.csv via build_calendar.py:
  - NFP: pd.date_range freq=WOM-1FRI. DONE (246 dates; 16 dropped as market
    holidays). Limitation: first-Friday approx, a few real releases shift.
  - FOMC decision days: hand-verified list. 2023-2026 entered; 2006-2022 still
    TODO from federalreserve.gov historical pages (incl. emergency 2008/2020).
  - CPI: ABANDONED as a scrape (2026-06-10) - BLS schedule + archive pages have
    NO html <table>, so pd.read_html finds nothing. Decision per the "stop after
    ~15 min" rule: do NOT build a JS scraper. Add CPI later by hand-copy IF the
    NFP/FOMC result warrants it.

### Decision: run incrementally by event (more informative anyway)
- EXP-001a: NFP only - runnable NOW, zero manual entry, and NFP is the exact
  event behind the June 5 crash. Get the first real answer, learn the analysis.
- EXP-001b: + FOMC once 2006-2022 is hand-filled.
- EXP-001c: + CPI only if a/b look promising (hand-copy then).
- Reporting per-event is description, not strategy selection, so it does not
  inflate strategy-K. Each strategy VARIANT still counts toward K as planned.

### Method
**Part A — descriptive (does the premise hold?)**
For QQQ and SPY daily returns, compare event days vs all other days:
mean, stdev, worst 1%, skew. Significance: bootstrap the vol ratio
(10k resamples). PASS GATE: event-day vol must be >1.15x normal-day vol with
bootstrap p < 0.05, else the experiment STOPS here (premise false, kill).

**Part B — strategy variant (only if Part A passes)**
Rerun challenger/backtest.py run_book with an event-day multiplier on the
risky sleeve weights:
  - Variant 1: x0.5 on event days (K += 1)
  - Variant 2: x0.0 on event days (K += 1)
Costs and drift rules identical to the shipped backtest. No other changes.

### Decision rule (pre-registered, no moving the goalposts)
- DEPLOY-QUEUE if: Sharpe improves >= +0.03 AND MaxDD no worse, on the full
  2007-2026 window AND the 2018+ subwindow (both, not either).
- PARTIAL if: Sharpe flat (within +/-0.03) but MaxDD improves >= 2pts ->
  re-test as a conditional rule (event-day de-risk only when vol already
  elevated), which costs one more K.
- KILL otherwise. Expected effect is small (~32 event days/yr = ~13% of days),
  so a null result is the likely outcome and that is fine.

### Result — EXP-001a (NFP), 2026-07-11, research/exp001a_nfp.py
Part A premise gate, 230 NFP trading days vs 5,161 ordinary days (2006-2026):

| | SPY event | SPY other | QQQ event | QQQ other |
|---|---|---|---|---|
| daily vol (bps) | 119.4 | 119.4 | 147.7 | 135.5 |
| mean (bps) | +8.0 | +4.7 | +0.3 | +6.9 |
| worst 1% | −3.07% | −3.49% | −4.22% | −3.86% |
| skew | −0.73 | +0.03 | −0.59 | −0.03 |

Vol ratios: SPY 1.000 (bootstrap P(ratio≤1.15)=0.97), QQQ 1.090 (P=0.81).
Gate required >1.15 at p<0.05 on both. **FAIL → STOP, KILL.** Part B never ran.

**What's actually in the data:** NFP days have the SAME vol as ordinary days,
a HIGHER mean on SPY (+8.0 vs +4.7 bps — consistent with the announcement-
premium literature: you get PAID for holding through scheduled news), and the
one real anomaly is skew (−0.73 vs +0.03): same-size moves, slightly more
left-tailed shape. De-risking every NFP day would forfeit an above-average
return stream AND pay ~2%/yr in round-trip costs to dodge a tail that 20 years
of data says is not big enough to matter.

**One-line lesson:** June 5 2026 was the tail realizing once, not a pattern —
the market prices scheduled macro days efficiently, and hedging them
systematically is a negative-edge trade. Sample-of-one pattern-matching is
exactly what the premise gate exists to catch.

---

## EXP-002 — HAR-RV vol forecast for the overlay

**Status:** PRE-REGISTERED 2026-07-02 (research/harrv_spec.md) · run 2026-07-08 · **KILLED**
**Origin:** the champion's twice-observed structural weakness — the trailing-40d
overlay de-risked late into the June 2026 drop, then sat 85% cash through the
late-June rebound ("always a beat behind").

### Hypothesis
Replacing the trailing-40d vol estimate with a HAR-RV one-day-ahead forecast
(Corsi 2009, canonical 1/5/22 horizons, rolling 500d OLS) makes the overlay
react earlier in both directions, improving Sharpe and MaxDD.

### Method
research/harrv_ab.py — perf_report.simulate_deployed run twice, the vol
estimate feeding the scaler being the ONLY difference. Data: Tiingo
2019-01-02 → 2026-07-08 (1,888 days); HAR active 1,614 days (rest fell back
to trailing = identical to A). K = 1, no grid, per spec.

### Decision rule (frozen in the spec before any code)
PASS requires ALL: (1) Sharpe(B) ≥ Sharpe(A); (2) MaxDD(B) better;
(3) eyeball — B de-risks earlier into June-2026-type drops, re-risks earlier after.

### Result
| arm | CAGR | Vol | Sharpe | MaxDD |
|---|---|---|---|---|
| A trailing-40d | 13.89% | 18.65% | 0.55 | −28.07% |
| B HAR-RV | 12.52% | 16.65% | **0.52** | −27.21% |

1. Sharpe: **FAIL** (0.524 < 0.552). 2. MaxDD: pass (−27.2% vs −28.1%).
3. Timing: pass — B held lower exposure through the Jun 1–15 drop (0.20 vs
0.24) and equal-or-higher through the rebound.

**VERDICT: KILL.** HAR-RV did exactly what it promised — reacted faster,
cut vol 2 points, trimmed the drawdown — but the faster reaction also
trimmed exposure during ordinary noisy up-moves, costing 1.4 pts of CAGR
for 0.9 pts of drawdown. Sharpe net-net worse. The timing problem is real
but forecasting realized vol better isn't the fix; the June-2026 failure
was event-driven (jobs-report gap), which no realized-vol model sees coming
→ EXP-001 (scheduled-event calendar) is the right attack on this weakness.

**One-line lesson:** faster vol reaction ≠ better risk-adjusted returns
when the underlying loss came from a scheduled event, not vol clustering.

---

## EXP-003 — Absorption-ratio de-risking (challenger overlay)

**Status:** PRE-REGISTERED 2026-07-12 · run 2026-07-12 — **KILLED AT THE
PART A GATE** (premise false)
**Origin:** Vol-targeting scales on trailing vol MAGNITUDE and reacts late to
correlation crashes — the regime where the challenger's whole diversification
premise temporarily dies (June 2026 tape). García-Medina (arXiv 2607.06908)
shows market factor structure breathes over time; Kritzman's absorption-ratio
literature says concentration spikes precede fragility. Right-sized for our
~dozen-asset book: AR = share of rolling-covariance variance in eigenvector 1.

### Hypothesis
When the challenger book's 60d absorption ratio is historically elevated,
forward book risk is elevated BEYOND what trailing vol already captures, and
scaling risky exposure down in those states improves Sharpe and MaxDD at
small CAGR cost.

### Why it could be real
AR measures co-movement SHAPE, not size — it can rise while measured vol is
still calm (herding before the storm). The overlay currently has no view of
correlation structure, only variance level, so the information is genuinely
additive if it exists.

### Data
challenger/prices_cache.parquet (2005–2026), risky-universe daily returns.
No new data.

### Method
**Part A — premise gate (descriptive, K=0).** AR_t = λ1/Σλ of the 60d rolling
covariance of risky-universe returns. The sharp question: does AR add signal
BEYOND trailing vol? Double-sort: within each tercile of trailing 40d book
vol, compare forward 5d baseline-book vol on high-AR (top quintile,
trailing-252d rank) vs low-AR (bottom quintile) days.
GATE: high-AR forward vol ≥ 1.15× low-AR in at least 2 of 3 vol terciles,
pooled bootstrap p < 0.05 (10k resamples). Fail → STOP, premise false, kill.

**Part B — variants (only if A passes).** run_book with AR-conditional
multiplier on held risky weights, costs/drift identical to shipped backtest:
  - Variant 1: ×0.5 when AR_t > trailing-252d 80th percentile   (K += 1)
  - Variant 2: ×0.5 when AR_t > trailing-252d 90th percentile   (K += 1)

### Decision rule (frozen)
Windows: since 2007-07-01 AND since 2018-01-01 (both must agree).
- DEPLOY-QUEUE: Sharpe ≥ baseline + 0.03 AND MaxDD no worse, both windows.
- PARTIAL: Sharpe within ±0.03 AND MaxDD improves ≥ 2 pts, both windows →
  one conditional refinement allowed later (costs K += 1).
- KILL otherwise. Turnover drag reported either way.

### Result — 2026-07-12, research/exp003_absorption.py
Part A double-sort, 977 stride-5 days (2007–2026). Forward 5d book vol,
high-AR vs low-AR within trailing-vol terciles:
tercile ratios 0.984 / 0.876 / 0.944 — pooled 0.934, bootstrap P(≤1) = 0.87.
Gate needed ≥1.15 in 2 of 3 terciles at p<0.05. **0 of 3, wrong direction.
FAIL → STOP, KILL. Zero strategy-K spent.**

**What's actually in the data:** in this ~dozen-asset multi-asset book, AR is
essentially collinear with trailing vol — conditioned on vol, high
correlation-concentration days carried NO extra forward risk (if anything
slightly less). The published signal lives in 500-stock universes where
factor structure has room to breathe; a small diversified book's top
eigenvector is already the equity factor, and its share co-moves with vol.

**One-line lesson:** a signal validated at index scale is not a signal at
book scale — premise gates must test the signal ON OUR OBJECT, not trust
the literature's object.

---

## EXP-004 — 8-K fine-grained event drift (Massive taxonomy)

**Status:** PRE-REGISTERED 2026-07-12 · run 2026-07-12 — **KILLED. F1 failed
the calibration gate; F2 passed calibration decisively (p=0.0001) then FAILED
the one-shot holdout (mean flipped sign). The holdout did exactly its job.**
**Origin:** Dolphin et al. (arXiv 2607.08346) released 601,088 quote-grounded
event tags on 292,984 8-K filings (2022–2026, 119 event types, quality scores
1–5). Taxonomy is days old — fine-grained event classes inside catch-all item
codes are plausibly under-harvested at daily horizon. Their own event study
shows unsigned reactions differ by event type; we test SIGNED drift.

### Hypothesis
Stocks filing 8-Ks tagged with severe-negative event families exhibit
NEGATIVE post-filing drift over the next 20 trading days (underreaction),
economically meaningful at daily-close granularity. Pre-named families,
chosen BEFORE looking at any returns (from the paper's taxonomy only):
  F1 financial distress (going concern, covenant violation, payment default,
     bankruptcy, restructuring)
  F2 listing deficiency / delisting determinations
No other families may be promoted to the hypothesis after seeing results —
any additional family tested counts K += 1 and is exploratory only.

### Why it could be real
Distress news in catch-all Item 8.01 is exactly what coarse item-code
screens miss (the paper: only 48 of 309 cyber incidents carried the dedicated
code). Limited attention + no dedicated code = slow diffusion. Retail-usable
edge: an avoid/exit filter (and hypothetical short-side measurement).

### Data
- Event tags: served via Massive.com's REST API (located 2026-07-12):
  massive.com/docs/rest/stocks/filings/8-k-disclosures — "included in all
  Stocks plans", filterable by ticker/date/category, updated daily.
  BLOCKER: Tyler creates a (free-tier) Massive account + API key, then we
  pull the two pre-named families 2022–2026. Filter: quality score ≥ 4 only.
- Prices: Tiingo daily closes for tagged tickers + SPY benchmark. If API
  limits force sampling, sample randomly by event with seed 11, minimum 300
  events per family.

### Method (measurement first — strategy gets its own spec later)
**Part A — calibration window (2022-01-01 to 2024-12-31 ONLY).** For each
family: CAR(+1,+20) vs SPY from the first close after filing timestamp.
GATE: mean CAR ≤ −1.5% with bootstrap p < 0.05 for the family. Fail on both
families → kill. (Holdout stays untouched regardless.)
**Part B — holdout confirmation (2025-01-01 to 2026-06-30).** Passing
families re-measured once: PASS = same sign, ≥ 50% of calibration magnitude,
p < 0.05. No re-runs, no window tweaks — one shot.
**Part C — only after B passes:** the tradeable rule (exit/avoid overlay or
short sleeve) gets its own pre-registration (EXP-004b) before any strategy
backtest; strategy-K accounting starts there.

### Decision rule (frozen)
K = 0 for A/B (pure measurement with a held-out confirmation; the two
families were named in advance). Verdicts: KILL (gate fails), MEASURED-REAL
(A+B pass → proceed to EXP-004b spec), or INCONCLUSIVE (sample too thin:
< 300 usable events per family → park, do not tweak thresholds).

### Result — 2026-07-12 (exp004_8k_drift/finish/topup/holdout.py)
**Deviations, all documented pre-results:** API exposes no quality scores
(filter dropped); Massive free plan blocks price bars → prices via Tiingo
(stalled at 123 series on free-tier caps) → Alpaca bars, adjustment='all';
usable-count shortfall repaired by outcome-blind top-up sampling (drawn twice
due to a crash-rerun: +80 F1, +50 F2 — selection never saw returns).

**Calibration 2022-2024:**
| family | n | mean CAR | median | %neg | P(mean≥0) | gate |
|---|---|---|---|---|---|---|
| F1 distress | 366 | −3.59% | −7.34% | 63% | 0.088 | **FAIL** (not significant — bankruptcy short-squeeze right tail) |
| F2 listing | 343 | −6.36% | −4.77% | 70% | 0.0001 | **PASS** |

**F2 one-shot holdout 2025-01..2026-06 (n=286, 95% full windows):**
mean CAR **+3.87%** (sign flipped!), median −7.52%, 63% negative, P(mean≥0)=0.80.
Confirm bar was mean ≤ −3.18% & p<0.05. **HOLDOUT FAIL → KILL.**

**What the data actually says:** the MEDIAN event still bleeds out of sample
(−7.5%, worse than calibration) — most deficiency-notice names keep falling.
But the equal-weight MEAN — what a real short book would earn — was destroyed
by a handful of +several-hundred-percent microcap squeezes in the 2025-26
tape. The typical outcome and the portfolio outcome are different objects;
shorting this pond means collecting pennies in front of moonshots.

**One-line lesson:** a p=0.0001 calibration result died in a held-out year —
watching that happen once is worth a thousand warnings about overfitting.
No median-based or winsorized rescue attempts: that would be a new hypothesis
shaped by this data — if ever pursued, it needs a fresh pre-registration on
fresh data, and the prior is now poor.

---

## EXP-005 — VIX term-structure de-risk gate (challenger overlay)

**Status:** PRE-REGISTERED 2026-07-12 · run 2026-07-12 — **PART A PASSED
(the premise is REAL) · PART B: BOTH VARIANTS KILLED. First true-signal /
failed-trade result in the journal.**
**Origin:** EXP-002 (HAR) proved realized-vol models can't lead the market —
but the options market prices FORWARD vol all day. VIX ≥ VIX3M (inversion) =
the market itself pricing imminent stress. VolBot already uses contango as an
options ENTRY gate; never tested as an equity-book DE-RISK signal. Published
lineage: VIX futures basis / term-structure literature.

### Hypothesis
On days following a term-structure inversion (VIXCLS ≥ VIX3M at prior close),
the challenger book's forward risk is elevated BEYOND what trailing vol
already captures, and scaling risky exposure down during inversion improves
Sharpe and MaxDD.

### Why it could be real
The overlay's input (trailing realized vol) is backward-looking by
construction; implied term structure is a market-priced FORECAST. If the two
disagree (calm realized, inverted implied), the overlay is blind exactly when
options traders are paying up for near-term protection.

### Data
- FRED daily closes: VIXCLS and VIX3M (fallback series id VXVCLS); no key
  needed. VIX3M history starts Dec 2007 → test windows 2008-07-01 and
  2018-01-01.
- Books: challenger/prices_cache.parquet, shipped 3-sleeve VT16 baseline.
- Signal strictly lagged: inversion state at close t−1 applies to day t.

### Method
**Part A — premise gate (K=0), same design as EXP-003 for comparability.**
Stride-5 sampled days; within terciles of trailing 40d book vol, forward 5d
baseline-book vol on INVERTED vs NORMAL days.
GATE: ratio ≥ 1.15 in ≥2 of 3 terciles AND pooled bootstrap p < 0.05.
Pre-registered fallback (inversion clusters in high-vol states, so low-vol
cells may be empty): terciles with < 15 inverted samples are untestable; if
fewer than 2 terciles are testable, the gate runs on the highest-vol tercile
alone at the same 1.15 / p<0.05 bar. Forward 5d MEAN return difference is
reported descriptively (not gated).

**Part B — variants (only if A passes), engine = EXP-003's state-multiplier
run_book (already verified to reproduce the shipped backtest exactly):**
  - V1: ×0.5 on held risky weights while inverted   (K += 1)
  - V2: ×0.0 (full de-risk) while inverted           (K += 1)
Transition turnover charged on state flips, costs otherwise identical.

### Decision rule (frozen)
Windows: since 2008-07-01 AND since 2018-01-01 (both must agree).
DEPLOY-QUEUE: Sharpe ≥ baseline + 0.03 AND MaxDD no worse, both windows.
PARTIAL: Sharpe within ±0.03 AND MaxDD improves ≥ 2 pts, both windows.
KILL otherwise.

### Result — 2026-07-12, research/exp005_vix_ts.py
Inversion: 478 of 4,656 days (10.3%) since Dec 2007.

**Part A — GATE PASS (first premise to survive this week).** Low-vol tercile
untestable (13 inverted samples, as the fallback anticipated); ratios in the
two testable terciles 1.419 / 1.324, pooled 1.371, bootstrap P(≤1) = 0.0001.
Inversion days carry ~35% more forward book vol EVEN AFTER controlling for
trailing vol. The options market genuinely knows something the overlay can't
see.

**Part B — BOTH KILLED (K = 2 spent).**
| variant | ΔSharpe 2008+ | ΔSharpe 2018+ | ΔMaxDD |
|---|---|---|---|
| ×0.5 while inverted | −0.039 | −0.045 | −0.3 pts (worse) |
| ×0.0 while inverted | −0.126 | −0.136 | −0.7 pts (worse) |
De-risking cut vol (12.1%→11.0%/10.6%) and softened worst days, but cost more
CAGR than the risk it saved — and MaxDD got WORSE, because inversion peaks at
capitulation lows and the de-risked book misses the violent snap-backs while
re-entering late.

**One-line lesson:** a TRUE signal is not a TRADEABLE signal — inversion days
carry extra vol AND extra compensation for bearing it (same shape as the NFP
announcement premium). The market prices its own fear correctly; being paid
for holding through it IS the deal. No ×0.75 / delayed-entry / early-exit
refinements without fresh pre-registration — the PARTIAL clause did not
trigger and tinkering from here is curve-fitting.

---

## EXP-006 — Trend sleeve re-audition: 12-1 momentum, vol-weighted

**Status:** PRE-REGISTERED 2026-07-12 · run 2026-07-12 — **KILLED AT THE
PART A GATE** (premise not established in our universe)
**Origin:** The challenger's trend seat is benched (budget 0) because the
10-month-MA version lost to its own absence. The classic academic spec was
never auditioned: 12-1 momentum (12-month return SKIPPING the most recent
month — the documented short-term-reversal guard) with inverse-vol weighting.
Different signal, same crisis-alpha mandate.

### Hypothesis
In the sleeve's own universe (SPY, EFA, TLT, GLD, DBC), assets with positive
12-1 momentum earn materially higher forward 1-month returns than assets with
negative 12-1 momentum, and a sleeve built on that signal earns its budget
back at the book level.

### Why it could be real
12-1 momentum is the most replicated cross-asset anomaly in the literature;
the skip-month specifically avoids the 1-month reversal that poisons naive
momentum. The benched sleeve failed with a DIFFERENT signal (price vs 10mo
MA, no skip, equal weight); this is not a re-run of a failed idea with new
clothes — it is the canonical spec, tested once.

### Data
challenger/prices_cache.parquet. Signal strictly from data through t−1.

### Method
**Part A — premise gate (K=0).** Monthly-sampled (21d stride) pooled panel
over TREND_ASSETS, 2007+: mean forward-21d return of positive-12-1 assets
minus negative-12-1 assets.
GATE: spread ≥ +20 bps/month AND bootstrap P(spread ≤ 0) < 0.05 (10k).

**Part B — variants (only if A passes), K=2.** New builder: qualifiers =
assets with 12-1 > 0; weights ∝ 1/vol60 over qualifiers, scaled to
budget × (n_qualified / 5); unfilled slice parks in SHV (keeps the sleeve's
cash-parking crisis behavior). Baseline = shipped 3-sleeve VT16. Engine must
reproduce the shipped backtest exactly at trend budget 0 before variants run.
  - V1: trend 20% — budgets {core .36, trend .20, lowvol .224, ballast .216}
  - V2: trend 10% — budgets {core .405, trend .10, lowvol .252, ballast .243}

### Decision rule (frozen)
Windows since 2007-07-01 AND 2018-01-01, both must agree.
DEPLOY-QUEUE: Sharpe ≥ baseline + 0.03 AND MaxDD no worse.
PARTIAL: Sharpe within ±0.03 AND MaxDD improves ≥ 2 pts.
KILL otherwise. No third budget, no signal-lookback grid.

### Result — 2026-07-12, research/exp006_trend121.py
Pooled monthly panel 2007–2026: 758 positive-mom vs 400 negative-mom
asset-months. Forward 21d means: +0.69% vs +0.51% — spread **+18 bps/mo**
(under the +20 bps bar) with **P(spread≤0) = 0.30** (nowhere near 0.05).
**FAIL → STOP, KILL. Zero strategy-K spent.**

**What's actually in the data:** the sign agrees with the literature, but a
5-ETF universe gives ~40 observations/decade of independent cross-sectional
information — the most-replicated anomaly in finance cannot be STATISTICALLY
ESTABLISHED at this scale, let alone earn a 20% budget slice. Consistent with
the original benching: it's not that trend is fake, it's that this book's
format is too small to harvest it reliably.

**One-line lesson (rhymes with EXP-003):** anomalies documented on hundreds
of assets do not automatically survive in a five-asset sleeve — cross-
sectional breadth IS the strategy, and we don't have it.

---

## EXP-007 — Earnings vol-crush premium (single-name VolBot sibling)

**Status:** PRE-REGISTERED 2026-07-12 · data feasibility probe pending
**Origin:** The one confirmed edge family (variance risk premium) applied to
its most capacity-constrained corner: single-name options around earnings.
Funds can't deploy size in weekly mid-cap options; the premium plausibly
persists. Hypothesis shape identical to volbot_spec's: implied > realized,
harvest defined-risk.

### Hypothesis
For liquid optionable names, the earnings-implied move (ATM straddle price at
the last close before announcement ÷ spot) systematically EXCEEDS the realized
next-session absolute move, by enough to clear defined-risk selling costs.

### Data (feasibility gates the experiment)
- Earnings dates + timing (BMO/AMC): yfinance PROBED 2026-07-12 — 40 events
  back to 2015 per ticker, depth sufficient; verify per-ticker at build.
- Options: Databento OPRA.PILLAR PROBED 2026-07-12 — full AAPL chain daily
  bars = $0.95/3 days (worst-case name). Build must pull definitions first,
  then bars for ONLY the 2-4 ATM contracts per event. HARD COST CAP $30,
  cost-checked before every pull.
- Underlyings: existing Tiingo/Alpaca sources.
- Universe pre-named: the ~40 most-liquid optionable single names by option
  volume (list frozen at probe time, before any premium measurement).

### Method
**Part A — premise (K=0), calibration = 2023-01-01..2025-06-30:** ≥200 events.
Per event: implied_move = ATM straddle close / spot; realized = |next close
return|. GATE: mean(implied/realized) ≥ 1.15 AND win rate (implied>realized)
≥ 60% AND bootstrap P(mean ratio ≤ 1) < 0.05.
**Part B — one-shot holdout 2025-07-01..2026-06-30:** same bars at 50%
magnitude tolerance, p < 0.05, single look.
**Part C — strategy (short iron-fly/condor variants) only after A+B pass,**
under a fresh EXP-007b registration; strategy-K starts there.

### Result — PILOT ONLY, 2026-07-13 (research/exp007_pilot.py)
16 events across AAPL/MSFT/MSFT before a transient Databento read-timeout.
Implied move (ATM straddle/spot) vs realized (|next-close return|): **16/16
had implied > realized**, ratios 1.1×–34×, median ~4×. Pipeline validated
(near-free definitions → targeted 2-contract bar pulls, pennies). Earnings
dates came from a HARDCODED pilot fallback (yfinance rate-limited).

**CRITICAL REFRAME (honest, pre-strategy):** ratio > 1 is the EXPECTED,
textbook result — the earnings variance risk premium is one of the most
robust known features of options markets. The premise gate (mean ratio ≥
1.15) is therefore near-trivially passable and proves the premium EXISTS,
not that it is HARVESTABLE. Selling that premium exposes you to the full
earnings gap; the tail quarter (a name gaps 15% when 4% was priced) can erase
many quarters of collected premium — which is exactly how retail earnings-
straddle sellers blow up. VolBot survives on INDEXES partly because index
moves are diversified and less gappy than single names.

**Therefore the real, uncertain, edge-or-not question is the STRATEGY P&L
with honest tail accounting** (defined-risk short iron-fly/condor, held
through earnings, with a selection filter for when the premium is unusually
fat), i.e. EXP-007b — NOT the premise gate. Do not over-invest in formalizing
a premise the pilot already confirmed. Also unresolved: a scalable earnings-
date-with-timing source (yfinance rate-limits; Massive/Polygon or a paid
source needed for a real universe).

---

## EXP-008 — "Lazy Prices" with LLM semantic diffs (10-K/Q risk factors)

**Status:** PRE-REGISTERED 2026-07-12 · Part A PASSED (instrument validated,
Spearman 1.00) · **Part B RAN 2026-07-12 — KILLED, and the signal INVERTED
vs the published anomaly.** Holdout never touched.
**Origin:** Cohen–Malloy (J. Finance): firms that substantively CHANGE filing
language (esp. Item 1A risk factors) underperform over subsequent months. The
original instrument was bag-of-words similarity; an LLM semantic diff is a
genuine instrument upgrade nobody retail runs. Monthly horizon (outside our
daily-frequency graveyard). Data free (SEC EDGAR); scoring pennies (Haiku).

### Hypothesis
Firms whose consecutive 10-K/10-Q risk-factor sections show HIGH semantic
change (LLM-scored 0–5, prompt versioned + fingerprinted before scoring any
calibration filing) underperform low-change peers over the following 63
trading days.

### Data
- Filings: SEC EDGAR (free). Universe pre-named: 150 mid-caps sampled seed-11
  from the S&P 400 list as of probe date. Calibration filings 2022-2024;
  holdout 2025-2026 untouched.
- Returns: Alpaca adjusted bars (validated in EXP-004). Benchmark MDY.
- LLM: claude-haiku, temperature 0, fixed prompt; ShadowHarness-style
  fingerprint of prompt+model recorded BEFORE calibration scoring; changing
  either stales the evidence.

### Method
**Part A — instrument validation (K=0):** score a 40-pair pilot twice; require
rank agreement (Spearman ≥ 0.8 between runs) and total pilot cost ≤ $2, else
fix instrument BEFORE any return is examined.
**Part B — calibration measurement:** top-quintile change vs bottom-quintile
change, forward 63d return vs MDY. GATE: spread ≤ −1.5% with bootstrap
p < 0.05.
**Part C — one-shot holdout 2025-2026:** same sign, ≥50% magnitude, p < 0.05.
Strategy (avoid/underweight filter) only via fresh EXP-008b registration.

### Result — 2026-07-12, research/exp008_partb.py
150-name S&P 400 sample (seed 11), 396 usable 10-K pairs (2022–2024),
23 extraction failures dropped, LLM scoring cost $2.41.
| group | n | fwd 63d vs MDY |
|---|---|---|
| HIGH change (score ≥3) | 202 | **+2.81%** |
| LOW change (score ≤1) | 95 | +0.09% |
Spread HIGH−LOW = **+2.72%**, P(spread ≥ 0) = 0.925. Gate wanted ≤ −1.5% at
p<0.05. **GATE FAIL — and the sign is OPPOSITE the published Lazy Prices
effect** (which predicts high-change firms UNDERperform). Holdout untouched.
K = 0 spent (pure measurement, no strategy built).

**Why the inversion (all pre-declared or mechanical, none data-mined into a
new hypothesis):**
1. *Survivorship (pre-registered limitation):* universe = CURRENT S&P 400,
   so high-change firms that then blew up already left the index. This biases
   high-change survivors UP — but it would need to explain ~4.3 pts to flip a
   true −1.5% into +2.7%; implausible as the whole story.
2. *Post-publication decay/reversal:* Lazy Prices published 2020 on 1990s-2010s
   data; heavily arbitraged since. Reversal is a common post-publication fate.
3. *Instrument gap:* original used bag-of-words cosine on the whole 10-K; our
   LLM scores SUBSTANTIVE business change on Item 1A. In the 2023-24 bull tape,
   "meaningfully rewrote its risk factors" likely proxies for transformation/
   growth (→ outperformance), not buried distress. Different instrument,
   different construct.

**One-line lesson:** an anomaly can fail to replicate by INVERTING, not just
fading — and a validated instrument measuring a slightly different construct
than the original is a prime way that happens. NOT flipping this into "go long
high-change firms": that's a new hypothesis born from this data AND it's
survivorship-contaminated; it would need fresh pre-registration on fresh,
delisting-inclusive data with a stated mechanism.

---

## EXP-007b — Earnings short-premium STRATEGY simulation (defined risk)

**Status:** PRE-REGISTERED 2026-07-13 · run 2026-07-13 — **KILLED. The
median trade wins (+6.1%) but the mean LOSES (−4.3%): the flood signature.**
**Origin:** EXP-007 pilot confirmed the premium EXISTS (16/16 events implied >
realized, median 4×). Untested and uncertain: does a DEFINED-RISK harvest net
positive after earnings-gap tails and costs? (The reason retail earnings
sellers blow up.) This is the actual edge test.

### Hypothesis
A short ATM iron fly, sold at the close before earnings and held to the
nearest post-earnings expiration, over a frozen universe of liquid optionable
large caps, earns positive mean return-on-risk that survives the tail losses
and transaction costs.

### Universe (FROZEN before any P&L)
18 names: AAPL MSFT NVDA AMZN GOOGL META TSLA AMD NFLX JPM BAC WMT DIS CRM
INTC QCOM ORCL MU. Calibration events 2023-01-01..2025-06-30; holdout
2025-07-01..2026-06-30 (UNTOUCHED until calibration passes).

### Structure (FROZEN; K counts variants)
- Entry: close before earnings (AMC → close(E); BMO → close(E−1)).
- Short legs: 1 call + 1 put at the listed strike nearest spot (ATM).
- Long wings: 1 call + 1 put at nearest listed strikes ≥ 2× the implied move
  from spot (implied move = ATM straddle ÷ spot). → iron fly, defined risk.
- Expiry: nearest listed expiration strictly after the earnings date; HELD to
  expiry, settled at intrinsic from the underlying close (no exit pull). No
  early management in v1.
- V1 = wings @ 2× implied move (K=1). V2 = wings @ 1.5× implied move (K=2).
- Costs (frozen, conservative): each of 4 legs at entry filled 3% worse than
  its daily close (shorts collect less, longs pay more) + $0.65/contract
  commission. Expiry settlement free.
- Metric: per-trade return-on-risk = net P&L ÷ |defined max loss|.

### Decision rule (FROZEN)
Calibration GATE (all): mean return-on-risk ≥ +5% AND bootstrap P(mean ≤ 0)
< 0.05 AND win rate ≥ 55%. (Bootstrap is the real test — if a few gap-losses
dominate, the mean's CI blows out and p fails, which is the point.)
One-shot HOLDOUT: mean ≥ 0 AND bootstrap p < 0.05, same sign. No re-runs.
KILL if calibration fails. No structure/cost tuning post-hoc.

### Result — 2026-07-13, research/exp007b_sim.py (V1, wings @ 2× implied move)
168 trades (of 180 events; 12 lost to Databento timeouts), earnings dates from
SEC 8-K Item 2.02 filings, held-to-expiry, frozen 3%-slippage + $0.65/leg costs.
Total Databento spend $1.03.

| metric | value |
|---|---|
| **mean return-on-risk** | **−4.3%** (account loses) |
| median return-on-risk | **+6.1%** (typical trade wins) |
| win rate | 54% |
| worst trade | −100% (full max loss — a gap through the wings) |
| P(mean ≤ 0) | 0.836 |
| total P&L (1 unit risk/trade) | **−11.8 units** |

**GATE FAIL → KILL** (needed mean ≥ +5%, p<0.05, win ≥ 55%). V2 (1.5× wings)
NOT run: it collects LESS premium against the SAME gap tail → strictly worse
prior; K = 1 spent.

**What the data says — the flood, quantified.** The median trade makes +6%
and you win 54% of the time, so it *feels* like a winner. But the mean is
−4.3%: the occasional −100% earnings gap (a name blows through the wings)
wipes out many small wins. This is the exact mechanism behind EXP-007's pilot
(premium EXISTS, 16/16 overpriced) NOT being harvestable: the premium is real
but smaller than fair compensation for the single-name gap risk. It is why
retail earnings-straddle sellers blow up — they see the 54% win rate and miss
that the rare disasters dominate the average.

**Vindicates VolBot's design with data.** VolBot sells this SAME premium but
on INDEXES (SPY/QQQ/IWM), which diversify away single-name gaps — indexes
almost never move 15% on one event. Single names flood constantly; indexes
rarely do. Same trade, survivable on one object and not the other.

**One-line lesson:** median ≠ mean, and the account earns the mean — a
high-win-rate strategy can be a guaranteed loser when the losses are rare and
total. (Twin of EXP-005: a true premium is not a tradeable premium.)

---

## Template for future experiments

## EXP-NNN — Name
**Status:** PRE-REGISTERED date · running · KILLED · DEPLOY-QUEUED
**Origin:** what loss/paper/observation produced the idea
### Hypothesis
One falsifiable sentence, written before touching data.
### Why it could be real
Mechanism. If you cannot state one, do not run the experiment.
### Data
Sources, date range, file paths.
### Method
Exact procedure. Name every variant you intend to try (that is your K).
### Decision rule
Numeric pass/fail thresholds, chosen in advance.
### Result
Numbers, verdict, one-line lesson. Kills documented like wins.

---

## EXP-009 — Correlation-conditioned index variance premium

**Status:** PRE-REGISTERED 2026-07-24 · RUN 2026-07-26 — **PART A PASSED** (P = 0.019, effect in the top decile). Part B authorised but deliberately NOT SPENT.
**Origin:** A 2026-07-24 measurement of research/statarb_prices.parquet (172
large caps) found average pairwise correlation at **0.156 — the 8th percentile
of 5.5 years** — while cross-sectional dispersion hit a 6-year high (39.5%).
Rolling 126d windows show this pinned at 0.14–0.18 for nine straight months
(Oct 2025 → Jun 2026), so it is a regime, not a blip. In the same window,
VolBot's own logged IV vs trailing realized vol gave SPY VRP **+0.6**, QQQ VRP
**−4.2**, IWM **+3.6** vol points. VolBot sells index premium. If index VRP is
conditional on the correlation regime, the bot is currently selling into the
worst possible one and does not know it.

### Hypothesis (written before touching data)
Realized cross-sectional correlation among S&P components predicts forward
21-day index variance risk premium (VIX minus subsequent SPY realized vol).
Specifically: **periods of HIGH realized correlation are followed by HIGHER
index VRP than periods of LOW realized correlation.**

### Why it could be real (mechanism, not data-mining)
Index variance is component variance times a correlation term. Index options
are the market's hedging vehicle, so demand for index protection scales with
systemic — i.e. correlated — risk, while single-name vol supply is comparatively
steady. When correlation collapses, index realized vol falls mechanically and
the premium embedded in index options should compress. This is the same
structural fact that dispersion desks monetise; the claim here is only that
its *sign is predictable from realized correlation*, which is free to compute.

**Competing story that would falsify it:** if index IV is sticky and re-prices
correlation slowly, low correlation → RV falls faster than IV → VRP goes UP,
the opposite sign. The recent 19-day reading is directionally consistent with
the compression story, but 19 days is nothing. Both stories are live; that is
why this is a gate and not a strategy.

### Crowding read (new selection criterion, 2026-07-24)
Institution-crowded is acceptable; retail-crowded is not. Bank exotics desks
have traded implied vs realized correlation for decades — fine, they make money
and the barrier is capability. Retail premium sellers (tastytrade cohort,
JEPI/QYLD/XYLD complex) sell index premium **unconditionally**, on a calendar,
with no correlation conditioning whatsoever. That gap is the whole thesis.
Explicitly rejected as retail-crowded: long-short 12-1 momentum on large caps,
pairs/stat-arb tutorials, VIX-contango roll, earnings straddles (already killed
in EXP-007/008).

### Data
- **Correlation panel:** research/statarb_prices.parquet is only 2021+ (172
  names, 5.5y). At a 21-day stride that is ~65 OVERLAPPING observations, and
  correlation regimes persist for months — call it 10–15 independent episodes.
  **This is the exact trap that killed EXP-006** (5-ETF universe, ~40
  observations/decade, could not resolve the most-replicated anomaly in
  finance). So Part A MUST first extend the panel to 2005+ via yfinance on the
  same 172 tickers, accepting survivorship bias and documenting it.
  If the extended fetch fails, STOP and log the block — do not run on 5.5y.
- **Implied vol:** FRED VIXCLS (verified live 2026-07-24, 9,538 rows).
  Confirmed absent: COR1M, COR3M, ICJ, KCJ all 404 on FRED — there is no free
  implied-correlation series, which is why this tests realized correlation as
  the conditioner rather than the correlation premium directly.
- **Realized vol:** SPY from the same fetch. Signal strictly from data ≤ t−1;
  forward RV strictly from t+1..t+21.

### Method
**Part A — premise gate (K=0).** On the extended panel, at 21-day stride:
compute 126d average pairwise correlation at t, and forward index VRP =
VIX(t) − realized SPY vol over t+1..t+21. Split observations at the median
correlation. Statistic = mean forward VRP in the high-correlation half minus
the low-correlation half.
**GATE: spread ≥ +1.5 vol points AND bootstrap P(spread ≤ 0) < 0.05 (10k
resamples, block bootstrap with 126d blocks to respect the overlap).**
A plain IID bootstrap here would be a lie — the windows overlap by design.

**Part B — variants (only if A passes), K=2.** Both are conditioners on the
EXISTING VolBot gate, not a new book. Baseline = VolBot as shipped.
  - V1: hard gate — no new rungs when 126d correlation is below its own 252d
    median, regardless of the existing VRP tercile test.
  - V2: soft gate — half size below the median instead of no trade.
No third variant, no correlation-lookback grid, no threshold grid.

### Decision rule (frozen)
Evaluated on the CONDOR P&L STREAM ONLY (per volbot_spec.md VB-2 note — never
account equity). Windows 2005+ and 2015+, both must agree.
- DEPLOY-QUEUE: mean credit-capture ≥ baseline + 10% relative AND worst rung
  loss no worse.
- PARTIAL: capture within ±10% AND worst rung loss improves ≥ 20%.
- KILL otherwise.

### Known ways this dies (write them down now, not after)
1. Extended fetch fails or is too survivorship-poisoned to trust → blocked, K=0.
2. ~15 independent regime episodes cannot resolve a 1.5-vol-point effect →
   honest "underpowered," K=0, same lesson as EXP-006.
3. Premise true but the effect is already inside the existing VRP tercile gate
   (correlation and VRP may be near-collinear) → PARTIAL at best; must report
   the correlation between the two gates before claiming independent value.

### Result
**RUN 2026-07-26 · Part A PASSES the pre-registered gate — with a caveat that
changes how it may be used.**

Spec correction made BEFORE the gate was computed (order is auditable in the
script): the origin universe was **not** "172 large caps." 26 of the 175 tickers
in statarb_prices.parquet are FUNDS — seven bond funds (TLT IEF IEI LQD HYG JNK
VCIT), metals (GLD SLV), sector baskets (XLE XLK SMH SOXX XBI IBB ITB XHB KBE
KRE OIH GDX GDXJ) and regional equity funds (EEM EFA VEA VWO). Bond funds drag
a pairwise-correlation mean down; sector baskets are near-duplicates of their
own constituents and drag it up. Universe amended to **149 single-name
equities**. Panel: Tiingo, 2005-01-03 → 2026-07-24, 100% coverage, 250
observations, ~41 independent blocks.

Also fixed pre-gate: a zero-variance column made np.corrcoef emit NaN and
silently DISCARD the whole 126-day window — biased against stressed periods,
where halted/flat names cluster. Cost one observation before it was caught.

Gate:
- median 126d correlation 0.284; HIGH half fwd VRP **+4.39**, LOW half **+2.46**
- SPREAD **+1.93** vol pts (gate ≥ +1.5) · block-bootstrap P(spread ≤ 0) =
  **0.019** (gate < 0.05) → **PASS**, K=2 unlocked for Part B
- collinearity vs VolBot's trailing-VRP gate: **r = −0.118**. Well under the 0.6
  ceiling, so this is genuinely new information, not a repackaging of the
  existing tercile gate. This is the strongest part of the result.

**The origin anomaly survived the cleanup.** On the corrected equities-only
universe the latest reading is **0.154, 7th percentile** (vs 0.156/8th on the
contaminated one) — pinned 0.128–0.160 for eight straight months. Removing the
bond funds moved it by 0.002. The low-correlation regime is real.

**Not crisis-driven:** high-correlation observations spread across 16 different
years; 2008+2020 together are only 22 of 125 (18%).

**THE CAVEAT — the effect is not monotonic.** Forward VRP by correlation decile:

    decile   0     1     2     3     4     5     6     7     8     9
    corr   .143  .204  .231  .253  .271  .298  .324  .354  .398  .527
    fwdVRP +1.06 +3.50 -0.62 +3.63 +4.73 +2.65 +3.71 +4.36 +3.02 +8.20

Deciles 0–8 are noise between −0.6 and +4.7 with no ordering. **The median split
passes essentially because decile 9 (+8.20) is extreme.** The honest statement
is "very high correlation predicts rich forward VRP," NOT "correlation predicts
VRP."

**Operationally this says nothing about where we are now.** Current regime is
the BOTTOM decile: n=25 overlapping obs (~4 independent episodes), mean fwd VRP
+1.06 but median +4.37 — mean and median disagree by 3.3 vol points, so the mean
is not a robust summary and the bucket is uninformative. Bottom-decile dates:
2007, 2017, 2018, 2024, 2025, 2026.

**Decision: do NOT implement Part B as pre-registered, and do NOT change VolBot.**
The pre-registered Part B (median-split hard gate / half-size) is weakly
motivated now that the effect is known to live in one tail, and we are sitting
in the opposite tail where the data is silent. Re-specifying it as a top-decile
size-UP rule after seeing this table would be fitting the rule to the answer —
the exact multiple-looks failure this ledger exists to prevent. That belongs in
a new pre-registration tested forward, out of sample.

Survivorship remains unaddressed (today's names extended backwards); per the
spec's own instruction, a marginal PASS stays unproven until a point-in-time
constituent list is used. +1.93 vs a +1.5 gate and p=0.019 vs 0.05 is marginal.

K spent: 2. Artifacts: research/exp009_corrvrp.py, exp009_observations.csv.

---

## EXP-010 — VolBot on REAL option quotes (no pricing model at all)

**Status:** PRE-REGISTERED 2026-07-27 · RUN 2026-07-28 — **FAILED.** On real OPRA quotes: Sharpe −1.54 (ARM A) and −1.24 (ARM B) against a 0.70 bar. No tuning attempted, per the pre-registered FAIL rule.
**K:** 0 (measurement, not a variant search — see ledger note)

### Origin
On 2026-07-27, live fills were checked against the backtest for the first time.
The backtest (`volbot_ladder_backtest.py`, "v2") priced the SPY 2026-08-21
condor at **2.44**; real consolidated OPRA NBBO on the entry date was **0.95**.
Alpaca paper quotes were 0.82 — i.e. the broker was roughly right and the MODEL
was 2.6x high. Two causes found:

1. **Duration mismatch.** `p["d"]` decrements once per TRADING day, so DTE=30
   modeled a 30-trading-day (~43 calendar) option. The bot targets 30 CALENDAR
   days. ~45% too much time value.
2. **No call skew.** v2 applied skew to puts, priced calls at flat VIX. Measured
   SPY 2026-07-20: real IV 19.7% at the 710 put (model said 20.0% — the put
   skew is excellent) but **11.1% at the 793 call** where the model used 18.8%.
   Modeled call spread ~1.1 vs real 0.10.

`volbot_backtest_v3.py` fixes both and lands at 1.38 — still 45% high, because
`SKEW=1.5` on the put side was never validated either. Each fix has revealed
another uncalibrated parameter. That is the treadmill this experiment exits.

**Live consequence already established (not in dispute):** the bot selects call
strikes with flat VIX, so its "16-delta" short call is really **2.7-delta**
(SPY 793 on 2026-07-20). VolBot is trading a ~20-delta put credit spread with a
near-worthless call spread attached, not the iron condor it was validated as.

### Hypothesis (written before touching the data)
VolBot's edge survives realistic pricing. Specifically: on real OPRA quotes,
with real bid/ask paid at entry and exit, the sleeve clears **Sharpe ≥ 0.7**
over 2020-07 → 2026-07, the same window v2 and v3 ran on.

0.7 is chosen because it is roughly SPY's own Sharpe in this window (0.65) plus
a small margin. A vol-selling sleeve that cannot beat buy-and-hold on
risk-adjusted terms has no reason to exist inside this book, whatever its
absolute return.

### Method
- **No Black-Scholes anywhere in the P&L path.** Entry credit, daily marks, and
  exit cost all come from OPRA `cbbo-1m` NBBO. BS is used ONLY to invert quotes
  into IV for delta-based strike selection, which is what a desk would do.
- Entry gates unchanged from v2/v3 (VRP top tercile per underlying, VIX<VIX3M
  contango, IV<30, ENTRY_GAP, MAX_RUNGS, RISK_PER, TOTAL_RISK_CAP).
- Strikes: nearest listed to 16-delta computed from REAL IV, wings ~1% of spot.
- Costs: pay the real spread — sell at bid, buy at ask on entry; reverse on exit.
  No COST_LEG fudge factor.
- Management unchanged: expire-worthless, 2x-credit loss stop, close at ≤1 DTE.

### Two arms, both reported (this is not a variant search)
- **ARM A — as-built:** call strikes chosen with flat VIX, reproducing what the
  live bot actually does today.
- **ARM B — as-designed:** call strikes chosen with real (skew-aware) IV, a true
  16-delta condor.

Both are reported whatever they show. A is the honest picture of the deployed
system; B says whether the strike-selection bug is worth fixing. Reporting only
the better one would be the failure this ledger exists to prevent.

### Decision rule (fixed now)
- **PASS** (Sharpe ≥ 0.7 on ARM A): keep the sleeve, continue to the Nov 2026
  live evaluation with ARM A as the benchmark instead of v2's Sharpe 1.27.
- **PARTIAL** (ARM A < 0.7 but ARM B ≥ 0.7): the strategy is sound and the
  implementation is broken. Fix strike selection as its own pre-registered
  change, re-run, and do NOT count pre-fix live trades toward the Nov sample.
- **FAIL** (both < 0.7): size the sleeve down or retire it. Do not go looking
  for a parameter set that passes — every one of DTE, delta, wing width, loss
  stop and tercile is then a free variable and anything can be made to pass.

### Known ways this dies (written down now)
1. OPRA coverage gaps or illiquid strikes leave holes in the daily marks →
   report coverage honestly; if >10% of contract-days are missing, the result
   is "inconclusive", not a number.
2. Survivorship-free but LOOK-AHEAD prone: strike selection must use only data
   available at the entry timestamp. Any accidental use of the day's later
   quotes inflates results. Guard: select from the FIRST quote of the session.
3. The 2020-2026 window contains one enormous vol event (2020 COVID tail) and
   an otherwise historically calm regime. A pass here is not a pass everywhere;
   extending to 2013 is cheap and should follow a PASS, not precede it.

### Result
**RUN 2026-07-28 · FAIL. On real OPRA quotes VolBot loses money.**

                         ann ret    vol   Sharpe    maxDD   worstMo
    SPY                   +14.8%  16.9%    0.64    -25.4%    -9.6%
    ARM A (as-built)       -8.0%   8.1%   -1.54    -40.6%   -11.0%
    ARM B (as-designed)   -10.4%  11.9%   -1.24    -49.0%   -14.8%

334 condors, 2020-07→2026-07. Expectancy **−$118/trade**. Losing in 6 of 7
years — systematic, not one bad episode. Mark coverage 90.9% (ARM A) / 93.5%
(ARM B), inside the 10% threshold for "inconclusive" but worth remembering.

**Bug caught before believing the good version.** The first run printed Sharpe
1.76 and PASS. Disbelieved on principle: real prices CANNOT beat an inflated
model. Cause — credit counted twice (added at entry, added again inside the
exit P&L), so every trade booked a premium it never received. Fixed; the result
inverted from +19.8% to −8.0%. Sixth silent bug in two days; none crashed.

### Why it loses (mechanism, not a fishing expedition)
- **The premise is CORRECT.** Of condors reaching expiry, **92% win**, avg +$237.
  Selling 16-delta index premium does work.
- **46% never reach expiry.** They hit the 2× loss stop. Stops win 0% by
  definition, avg −$532.
- **Stops don't execute at 2×.** Median 2.25×, mean 2.58×, 90th 3.17×, 95th
  4.17×, max **14.03×**. The bot checks daily; by the time it sees the breach
  the position has gapped past it. The stop is a suggestion, not a floor.
- **Robustness:** if every stop executed perfectly at 2.0×, total P&L would be
  −$10,775 instead of −$39,314. **Still negative.** Slippage explains ~3/4 of
  the damage but the conclusion does not depend on it.
- **More premium made it worse.** ARM B sold closer strikes (20.9% of width vs
  ARM A's 14.3%) and lost MORE. The loss tail dominates the extra income.

### Decision taken
Per the pre-registered rule for FAIL: **do not tune.** The data points straight
at the loss stop, and removing it is the obvious response — obvious post-hoc
responses are usually wrong, and every one of DTE/delta/wing/stop/tercile is a
free variable the moment we start. Sleeve is not to be extended; open rungs ride
to their Aug 13/20 settlement so volbot_trades.csv yields a live-vs-backtest
comparison. K spent: 0 (measurement experiment; no variant auditioned).

### What this bought
- The premium-selling franchise is dead as configured. VolBot was the lone
  survivor of a 9-strategy gauntlet; it is now 0 for 10 on real prices.
- **Real credits are 14–21% of width, not the 29–37% Black-Scholes claims.**
  That gap is information about the whole family, not just this sleeve.
- **OPRA 2013-04 → 2020-07 remains UNTOUCHED** — ~7 years of genuine
  out-of-sample data for anything proposed from here.

Artifacts: research/exp010_real_quotes.py, exp010_trades_{A,B}.csv,
exp010_curve_{A,B}.csv, exp010_cache/ (~1,500 files, $12.82 total spend).

---

## EXP-011 — Implied correlation premium (dispersion)

**Status:** PRE-REGISTERED 2026-07-28 · RUN 2026-07-28 — **PART A PASSED** (+0.034, P = 0.024) · **PART A2 FAILED** on cost feasibility → STOPPED. K spent: 0.
**K:** Part A = 0 (measurement). Part A2 = 0 (cost feasibility). Part B = 1 —
ONE fully pre-specified implementation. Not two, not "vega-weighted vs
equal-weighted, whichever works." One.

### Origin
Chosen BEFORE EXP-010's result was known, precisely so the choice could not be
contaminated by it (stated in-session 2026-07-27). Dispersion is long
single-name vol against short index vol — a different bet from VolBot's short
index premium, so it does not inherit that failure.

Crowding read: **institution-crowded** (bank exotics desks), retail-absent.
Passes the criterion in [[strategy-crowding-criterion]] — the barrier is
capability (many legs, real options data, symbology), not secrecy.

Supporting measurement, not evidence: the scanner has cross-sectional
correlation at the **1st percentile, extreme for 39 consecutive readings**.

### Hypothesis (written before touching data)
Index implied volatility is systematically rich relative to the cap-weighted
implied volatility of its components — i.e. **implied correlation exceeds
subsequently realized correlation** — and the gap is large enough to survive
real bid-ask on every leg.

### Windows — fixed now, and this is the main overfitting control
- **PRIMARY: 2013-04 → 2019-12.** Never examined by any experiment in this
  ledger. All development, all gates, all decisions happen here.
- **CONFIRMATION: 2020-07 → 2026-07.** ONE look, only if Part B passes, never
  revisited. Treated as SECONDARY evidence because EXP-009 and the scanner have
  already touched realized correlation in this period — partial contamination,
  stated up front rather than discovered later.
- 2020-01 → 2020-06 excluded entirely (COVID; a regime that would dominate any
  correlation study and is not representative).

### Parameters — fixed a priori, NOT searched
Copied in spirit from the v2 VolBot spec, which listed its structural params as
"NOT searched". Any change to these after seeing a result voids the experiment.

    N_COMPONENTS = 25        # top 25 SPY weights, the tradeable subset
    TENOR        = 30 days   # nearest listed expiry to 30 calendar days
    MONEYNESS    = ATM       # nearest strike to spot, both legs
    SAMPLE       = monthly   # one observation per month, no overlap games
    MIN_EPISODES = 25        # below this the answer is "underpowered", not "no"

### Part A — does the premium exist? (K=0)
Implied correlation from real OPRA quotes:

    rho_imp = (var_index - SUM w_i^2 var_i) / (SUM_i SUM_{j!=i} w_i w_j sig_i sig_j)

Realized correlation over the FOLLOWING 30 days from prices.

- **GATE:** mean(rho_imp − rho_real) > 0 with block-bootstrap P(spread ≤ 0) <
  0.05 over the primary window.
- **Underfitting guard:** run a power check FIRST (same `--power` pattern as
  EXP-009 — report episode count and coverage, compute NO gate statistic). If
  fewer than MIN_EPISODES independent episodes, the verdict is **underpowered**,
  not FAIL. Killing a real edge with a bad measurement is the failure mode that
  EXP-006 taught us.

### Part A2 — can it survive costs? (K=0, and it runs BEFORE any strategy work)
Ten strategies in this ledger have now died on costs — the 9-strategy gauntlet,
then VolBot on real quotes. So costs get measured before anything is built.

Using real OPRA bid/ask, compute the round-trip spread cost of the full
structure (1 short index straddle + 25 long component straddles = 52 legs).

- **GATE:** measured premium from Part A must exceed **2×** the round-trip cost.
- Fail here and the answer is **STOP** — do not proceed to Part B, do not look
  for a cheaper variant, do not reduce N to make it fit. Reducing N after seeing
  the cost is parameter search.

### Part B — one implementation, net of costs (K=1)
Only if A and A2 both pass. Vega-weighted: size component legs so total
component vega matches index vega. Monthly roll, hold to expiry, no stop.

**No stop is a deliberate design choice, decided now and for a stated reason:**
EXP-010 established that daily-checked stops on options exit at 2.58× not 2.0×
and turned a working premise into a losing strategy. This is not "removing the
stop because it failed last time" applied to the same strategy — it is a
different structure, and the choice is being fixed before any result is seen.

- **GATE:** Sharpe ≥ 0.70 net of all bid-ask, on the PRIMARY window.
  Same bar as EXP-010, deliberately, so results are comparable.
- **PASS →** one confirmation run on 2020-2026. If confirmation Sharpe < 0.35
  (half the bar), report as "does not replicate" and stop.
- **FAIL →** retire the idea. Do not adjust N, tenor, moneyness, or weighting.

### Known ways this dies (written down now, not after)
1. Fewer than 25 of the top names have liquid 30-day ATM options across the
   window → underpowered, STOP, K=0 spent.
2. 52 legs of bid-ask exceed the premium → the answer that killed ten
   strategies. Most likely outcome; Part A2 exists to find it cheaply.
3. The premium is real but concentrated in a handful of crisis months → not
   harvestable, and a Sharpe computed across it would be a lie about a tail bet.
4. Implied correlation > 1 or < 0 in the computation → a formula or weighting
   bug, not a finding. Sanity-bound every observation and report the rate.

### Feasibility probe — 2026-07-28, BEFORE any gate statistic exists
Kill condition #1 tested first, for ~$0.25 of definitions. **PASSES:** >=25 of
the 26 names have a shared ~30-day expiry on every probe date spanning the
primary window (2013-06 25/26, 2014-09 26/26, 2016-06 26/26, 2019-06 26/26).

Three spec corrections, all made before any statistic was computed:

1. **Sampling must be anchored to the listed expiry, not the calendar.** A fixed
   25-38 CALENDAR-day window found only 4/26 names in 2013, because weekly
   options were not yet widely listed and the monthly expiry fell outside the
   band. This is a property of the instrument calendar, not a tuning knob.
2. **Do not COMPUTE the expiry — DISCOVER it.** Before 2015, US equity options
   expired on the SATURDAY after the third Friday; the OCC later moved it to the
   Friday. Computing "third Friday" silently returned zero contracts for 2013.
   The rule is now: among expiries 25-45 days out, take the one the most names
   share, tie-broken by closeness to 30 days. Convention changes then cost
   nothing and no cutover date has to be looked up and gotten wrong.
3. **Ticker history is time-aware.** FB -> META (2022-06), GOOG -> GOOGL
   (2014-04). Using today's symbol for 2013 silently drops the name — the same
   class of error as the FUNDS contamination in EXP-009.

None of these change a threshold, a window boundary, or a decision rule. They
fix which contracts get read. Documented so the ordering is auditable.

### Result
**RUN 2026-07-28 · Part A PASSES · Part A2 FAILS → STOP. K spent: 0.**

Coverage was perfect: 81/81 monthly observation dates usable, 23-24 components
each, **0/81 implied correlations outside [0,1]** (formula clean), 80 clean
observations = ~26 independent episodes vs the 25 required. Spend $4.03.

**PART A — the premium is REAL.**

    mean implied correlation    0.352
    mean realized correlation   0.318
    SPREAD (implied - realized) +0.034
    block-bootstrap P(<=0)       0.024      (gate < 0.05)   PASS

Index options ARE systematically rich relative to their components, on this
book's own data, 2013-2019, out of sample to everything else in this ledger.

**PART A2 — and it is unreachable from here.**

    mean relative bid-ask per option leg   6.3%
    premium (vol-equivalent)             +0.0043
    round-trip cost (52 legs, in + out)   0.0158
    premium / cost                          0.27x   (gate >= 2.0x)   FAIL

**Costs are 3.7x the entire edge.** Not close, not fixable by trimming legs.

### Interpretation — the most useful result in this ledger
The hypothesis was right AND the trade is impossible at retail execution. Those
two facts together are more informative than either alone:

- A real, statistically significant premium exists and we measured it.
- It is invisible to us not because it is hidden but because capturing 3.4
  correlation points requires paying less than 6.3% per leg.
- That is precisely WHY it stays institution-crowded. Bank exotics desks trade
  this at spreads retail cannot see. The barrier is capability, exactly as
  [[strategy-crowding-criterion]] predicts — and here the capability is
  execution, not insight.

This is the eleventh strategy in this ledger, and the eleventh to die on costs.
That is no longer a coincidence; it is the finding. **For an account this size,
per-leg transaction cost is the binding constraint on the entire options
strategy space, and any future options idea must clear a cost gate BEFORE any
other work.** Part A2 running before Part B is what made this cost $4 and one
evening instead of a month.

### Decision
STOP, per the pre-registered rule. Part B not built. N not reduced to make the
numbers fit — reducing N after seeing the cost is parameter search. K = 0 spent
because no strategy variant was ever auditioned.

Artifacts: research/exp011_dispersion.py, exp011_observations.csv,
exp011_cache/, exp011_spot_raw.parquet. Total spend $4.03 (+$0.25 probe).

---

## EXP-012 — Implied correlation as an equity exposure signal

**Status:** KILLED 2026-07-28 at the collinearity gate, before any strategy work.

**Idea:** implied correlation prices *systemic* risk. Trade it as a risk-on /
risk-off signal in SPY vs cash (~1bp) rather than in options (6.3%/leg) — the
"institutional DATA, cheap EXECUTION" frame that the eleven cost deaths point to.

> **CORRECTION 2026-07-29 (see LEDGER AUDIT below):** "the eleven cost deaths" is
> false and was never checked. At the time this was written there were **three**
> cost deaths (005, 007b, 010); the majority of kills were absent-signal failures
> at Part A gates. The "institutional DATA, cheap EXECUTION" frame is still a
> reasonable motivation for EXP-012 — it just wasn't supported by the count I
> attached to it. Left in place with the correction rather than edited away.

**Gate 1 (cheapest kill, run first):** if implied correlation is just VIX in a
costume there is no independent signal, and VIX-timing is retail-crowded.

    corr(implied_corr, VIX)      pearson +0.670   spearman +0.717
    corr(implied_corr, SPY IV)   pearson +0.763   spearman +0.788
    threshold |r| > 0.70

**KILLED.** Two of three measures fail; the one that passes does so by 0.03.
Part of the collinearity is definitional — index IV sits in the numerator of the
implied-correlation formula.

**PROCESS ERROR, recorded deliberately:** the threshold was written as "|r| >
0.7" without naming the estimator or the benchmark. That left three numbers and
a free choice among them — exactly the degree of freedom pre-registration
exists to remove. Every future gate must name the statistic, the comparison
series, and the window BEFORE it is computed. This is the lesson of EXP-012,
and it is worth more than the experiment was.

Residual idea NOT pursued: ~55% of implied-correlation variation is not VIX, so
an orthogonalised version is a genuinely different construction. Rejected for
now because it was proposed AFTER seeing the collinearity, and a hypothesis that
survives because we went looking for the surviving piece is the weakest kind.
K spent: 0.

---

## EXP-013 — Does institutional positioning divergence predict Treasury returns?

**Status:** PRE-REGISTERED 2026-07-28 · RUN 2026-07-28 — **FAILED** at Part A on the pre-specified primary horizon. K spent: 0.
**K:** 0 for Part A (measurement gate). K = 1 for Part B, one pre-specified
implementation, spent only if Part A passes.

### Origin
CFTC Traders-in-Financial-Futures scanner, 2026-07-28. On UST 10Y NOTE:

    assetmgr_net   +0.481   100th percentile   z +2.14   run 73 weeks
    levmoney_net   -0.392     4th percentile   z -1.86   run 71 weeks

Asset managers at their most-long in the entire record, leveraged funds near
their most-short, both holding those tails for ~72 consecutive weeks. Seven of
24 scanned measures were extreme (1-2 is the chance expectation), but every
other extreme has run <= 8. **Persistence, not extremity, is why this one is
here** — chance produces isolated extremes, not two opposing tails on one
contract held for seventeen months.

Corroborating but NOT independent: the market-state scanner has real 10Y yields
at the 96th percentile, run 17.

Execution: TLT / IEF at ~1bp round trip. This is the "institutional data, cheap
execution" frame — the only frame in which uncrowded and affordable can both
hold, after eleven strategies died on transaction costs.

### The leading explanation says this predicts NOTHING
The Treasury **basis trade**: hedge funds short futures against long cash
Treasuries (a spread arbitrage), asset managers long futures for capital-
efficient duration. Under that reading, "leveraged money maximally short" is the
footprint of an arbitrage and carries **zero directional information**. The
72-week persistence actively supports it — a directional bet does not sit
unchanged for seventeen months; a structural arb does.

Writing this down first, because it is the most likely outcome and the result
must not be allowed to look surprising afterwards.

### Hypothesis (written before touching returns data)
Sustained extreme divergence between asset-manager and leveraged-money net
positioning in UST 10Y futures predicts forward IEF returns.

### Estimator, named in advance (the EXP-012 lesson)
- **Signal:** `DIV_t = assetmgr_net_t - levmoney_net_t`, each as a share of open
  interest, from the TFF futures-only report, contract `UST 10Y NOTE`.
- **State:** `EXTREME_t = 1` when `DIV_t` is in the top decile of its own
  trailing 260-week distribution, computed with data through t only.
- **Outcome:** forward 4-week and 13-week total return of **IEF** (chosen over
  TLT: shorter duration, closer to the 10Y contract being measured). Both
  horizons reported; the 4-week horizon is the pre-specified primary.
- **Statistic:** difference in mean forward return, EXTREME vs all other weeks.
- **Significance:** block bootstrap, block = 13 weeks (positioning is
  autocorrelated), P(spread <= 0) two-sided, 5000 draws, seed 0.
- **Alignment:** COT is published Friday for the PRIOR Tuesday. Signal at week t
  may only use the report RELEASED on or before t, and forward returns start the
  following Monday. No same-week look-ahead.

### Gates
- **Part A PASS:** |mean forward-return difference| >= 0.50% at the 4-week
  horizon AND bootstrap P < 0.05 AND at least 25 non-overlapping extreme
  episodes.
- **UNDERPOWERED** (not FAIL) if fewer than 25 episodes — report and stop.
- **Part B** only on a Part A pass: one implementation, IEF long/flat, weekly
  rebalance, 1bp per switch, gate Sharpe >= 0.70 net of costs on 2010-2026.

### Known ways this dies
1. **It's the basis trade** — divergence is structural, predicts nothing. Most
   likely outcome.
2. Extreme episodes cluster in 2-3 macro regimes (2020, 2022 hiking cycle,
   2025-26) -> not 25 independent episodes, verdict UNDERPOWERED.
3. It works but only via the level of yields, not positioning. **Guard:**
   report corr(DIV, real 10Y yield) and corr(DIV, 10Y level). If |r| > 0.70
   against either, the signal is a rates proxy and is KILLED — same rule that
   killed EXP-012, with the estimator named this time.
4. Signal predicts direction only in-sample because 2010-2026 contains one
   enormous bond bear market.

### Result
**RUN 2026-07-28 · Part A FAILS on the pre-specified primary horizon. K spent: 0.**

Power was fine: 1,037 weekly obs 2006-2026, 36 non-overlapping episodes vs 25
required, spread across 13 distinct years (2008-10, 2015-19, 2022-26) — so kill
condition #2 (regime clustering) did NOT bind.

    4-week (PRIMARY)  extreme +0.384%  other +0.227%  diff +0.157%  P = 0.200
                      gate |diff| >= 0.5% and P < 0.05          ->  FAIL
    13-week           extreme +1.277%  other +0.736%  diff +0.541%  P = 0.021

**The secondary horizon passes. The primary fails on BOTH criteria — a third of
the required magnitude at P = 0.20. Recorded as FAIL.** Switching to the 13-week
because it came back significant is the multiple-looks failure the primary
designation exists to prevent; the spec named 4-week before any data was seen.

**The 13-week result also has a mundane explanation**, and would be discounted
even without the discipline argument: corr(DIV, real 10Y) = +0.324, so EXTREME
periods coincide with higher-yield periods, which earn more carry. Over 13 weeks
carry dominates; over 4 weeks it barely registers. That asymmetry is consistent
with the longer-horizon "effect" being arithmetic rather than signal — and it is
part of why the 4-week horizon was chosen as primary.

**Kill condition #3 (rates proxy) was cleared BEFORE the gate:** worst |r| = 0.340
across pearson/spearman vs nominal and real 10Y, well inside the 0.70 threshold.
So the signal is genuinely not a yield proxy — it simply doesn't predict.

**This supports the explanation written down in advance:** the Treasury basis
trade. Positioning divergence is the footprint of a structural arbitrage (hedge
funds short futures against long cash, asset managers long futures for capital-
efficient duration), not a directional view. Structural footprints do not predict
returns. The pre-registered "most likely outcome" is what happened.

Artifacts: research/cot.py, exp013_positioning.py, exp013_observations.csv,
cot_cache/, cot_latest.csv. Cost: $0 — CFTC data is free.

---

## LEDGER AUDIT 2026-07-29 — I had been miscounting the cause of death

Before EXP-015, a claim I had repeated for three experiments turned out to be
false, so it is corrected here in the ledger itself.

**What I kept saying:** "eleven/twelve consecutive deaths on transaction costs."
It is written into EXP-012's own header. **What the ledger actually says:**

| cause of death | experiments | n |
|---|---|---|
| Premise false — the signal isn't there | 001, 003, 004, 006, 008, 012, 013 | 7 |
| Premise TRUE, the trade still lost money | 005, 007b, 010, 011 | 4 |
| Model spec failed its own gate | 002 (HAR-RV v1) | 1 |
| PASS | 009 Part A, 014 (HAR-RV v2) | 2 |

The dominant failure mode is **absent signal**, not cost. Cost is the SECOND
wall — it can only appear in the four cases that cleared the premise gate. The
slogan inflated one real pattern into a general law, and it was about to become
the foundation of a research direction.

**The pattern that survives correct counting is narrower and more useful:** all
four premise-clearing experiments were the SAME edge family — variance risk
premium.

- EXP-005 VIX term-structure inversion — Part A premise REAL
- EXP-007  earnings vol crush — 16/16 events implied > realized, median 4x
- EXP-009  correlation-conditioned index VRP — Part A gate P = 0.019
- EXP-011  dispersion / implied-correlation premium — +0.034, P = 0.024

Four independent confirmations of one edge, and all four died in execution. The
honest state of this research programme is therefore: **we own exactly one
repeatedly confirmed edge family, and the only thing between it and profit is the
spread we pay to get on.** That is a solvable-sounding problem in a way that
"costs kill everything" is not.

---

## EXP-015 — Collect the spread instead of paying it (Kalshi maker side)

**Status:** PRE-REGISTERED 2026-07-29 · RUN 2026-07-30 — **BOTH GATES PASS** (A2 only barely).
**K:** Part A = 0 (pure measurement). Part B = 1 — one pre-specified simulation.

**Origin — two facts that only matter together:**
1. The ledger audit above: every experiment that ever cleared a premise gate then
   lost in execution, paying a spread to take liquidity.
2. Kalshi's fee schedule, measured across its full series census (12,261 series):
   `quadratic` = 12,129, `quadratic_with_maker_fees` = 132. **Resting a limit
   order is fee-free on 98.9% of the exchange.** (Sports 108 of 3,056 charge maker
   fees; Politics, Elections, Companies, Health, World, Weather: zero.)

Every prior idea asked "can I find a mispricing big enough to pay the spread?"
This asks the inverted question: "can I be the one collecting it?" The Kalshi
arbitrage scan that closed 2026-07-29 measured buy-all costs of 1.26-1.47 against
a $1.00 payout across 169 exhaustive events — a 26-47 point round trip. Fatal as a
taker. That same number is the gross revenue line for a maker.

**Crowding read (standing criterion):** institution-crowded, which per the
criterion is acceptable rather than disqualifying — Susquehanna and other
professional shops quote on Kalshi, and retail is structurally the taker side.
But it implies the spread is competitive exactly where the professionals are, and
wide only where they are absent. Part A is partly a map of where they aren't.

### Part A — is the spread collectable at all? (gate, K=0)
A resting quote in a market with no takers never fills. So:

- **Gate A1 (venue exists):** >= 200 non-provisional markets with lifetime volume
  >= 1,000 contracts AND a live two-sided quote (0 < bid < ask < 1).
- **Gate A2 (spread exists where volume is):** median spread among those markets
  >= 0.03. If liquid Kalshi markets are already 1-2 cents wide, there is nothing
  left to collect once adverse selection is subtracted, and this dies at Part A.

**BOTH must pass.** Failing either closes the direction; no reformulating the
volume threshold or the spread bar after seeing the distribution.

Provisional markets are excluded by the `is_provisional` flag — the auto-generated
MVE parlay products (54,255 of ~60,000 open markets) fill against a computed price
and have no order book. Quoting against a parlay engine is not market making.

### PART A RESULT — RUN 2026-07-30 · BOTH GATES PASS (A2 only barely)

Scanned 548,236 open markets (549 cursor pages); 427,155 provisional parlays
excluded, leaving **121,081 real markets** — 89,697 ever traded, 44,906 two-sided,
**29,952 both**.

    TWO-SIDED markets bucketed by lifetime volume
    bucket             n     medSpr  medMid  spr/mid    medOI  medBidSz
    0 never traded  14954    0.0800   0.435     0.18        0       100
    1-100            7647    0.0600   0.315     0.19       12       100
    101-1k           9052    0.0500   0.310     0.16      238       100
    1k-10k           9030    0.0400   0.255     0.16     1472       100
    10k-100k         3089    0.0200   0.145     0.14    11216       185
    >100k            1134    0.0100   0.060     0.17   180582      1002

    Gate A1  >=200 liquid two-sided markets    13,264      PASS (66x the bar)
    Gate A2  median spread >= 0.03             0.0300      PASS (exactly at bar)

**A2 passed on the threshold itself.** Under the pre-registered rule (`>= 0.03`)
that is a pass and the bar is not being moved — but it is the weakest possible
pass and is recorded as such. At volume >= 10,000 the median spread is 0.0140 and
58% of markets are <= 2 cents.

**The spread collapses monotonically with volume, 8c -> 1c.** Wide spreads sit
exactly where the takers aren't, which is what the pre-registered crowding read
predicted: professionals quote where the flow is.

**The one genuinely unexpected number: `spr/mid` is 0.14-0.19 in EVERY bucket.**
Relative spread is ~16% of mid regardless of liquidity, because the high-volume
markets are also low-priced longshots (median mid 6c at >100k). There is no
liquidity tier where the spread is structurally cheap to collect. Whether ~16%
of mid is enough to survive adverse selection is precisely Part B's question,
and Part A deliberately does not answer it.

**Maker-fee premise independently verified** (it was an inference from the
`fee_type` census, and the whole experiment rests on it): Kalshi's published
schedule charges takers `0.07 * P * (1-P)` and **0% maker fee on standard
markets**, with a maker fee only on selected major-event series — matching the
132-of-12,261 census exactly. Sources:
[pm.wiki](https://pm.wiki/learn/kalshi-fees-explained) ·
[Market Math](https://marketmath.io/blog/kalshi-fees-guide-2026) ·
[Maker/Taker Math on Kalshi](https://whirligigbear.substack.com/p/makertaker-math-on-kalshi)

Artifacts: `research/exp015_cohort.py`, `exp015_logger.py`, `exp015/`. Cost: $0.

### Part B — adverse selection, the thing that actually kills market making (K=1)
Fees are not why makers lose. Makers lose because **they fill precisely when they
are wrong**: the taker crossing the spread is often the person who just watched the
touchdown. Pre-specified before any data:

- Poll top-of-book + trades on the Part-A-qualifying markets for >= 10 sessions.
  **SUPERSEDED 2026-07-30 (method only — metric, horizon and gate unchanged):**
  the 10 sessions do not have to be waited for. `/markets/trades` paginates weeks
  back (12,000 trades to 2026-06-07 on one market), and
  `/series/{s}/markets/{t}/candlesticks` returns **1-MINUTE bars carrying
  yes_bid + yes_ask OHLC** — i.e. historical top-of-book. The 1-min endpoint caps
  the WINDOW at ~24h, not the history depth, so walking back in 1-day windows
  reconstructs weeks of book at 1-minute grain (verified: 10 consecutive days,
  186-582 bars each). Part B therefore runs retrospectively over >= 10 real
  sessions **today**. The live logger is kept as an independent forward check,
  since retrospective and forward-collected tapes can differ.
- Simulate a passive two-sided quote resting AT the prevailing bid and ask.
- **Metric: post-fill markout** — mid price 10 minutes after each simulated fill,
  signed in the direction of the fill. 10 minutes is fixed now; it is NOT searched.
- **PASS:** mean markout across fills > 0, i.e. captured spread exceeds adverse
  selection. Maker fee is 0 on the qualifying series, so no fee term is subtracted;
  if a series with `quadratic_with_maker_fees` qualifies it is EXCLUDED rather than
  fee-adjusted, to keep one clean cost model.
- **KILL:** mean markout <= 0. Market making these markets is a losing trade and
  the direction closes.

### COHORT DESIGN FLAW found and handled 2026-07-30, before any markout data

The first cohort rule ranked qualifying markets by 24h volume and took the top
300. Part A had *just* established that spread narrows monotonically with volume —
so ranking by volume selected the TIGHTEST markets available. Result:

    cohort median spread   0.0100   (vs 0.0300 for the whole qualifying set)
    cohort median spr/mid  0.095    (vs ~0.16 in every Part A bucket)

By construction I had built the hardest possible case for a maker: the markets
where professionals are already quoting. That is *conservative*, not wrong — but it
mostly answers "can a retail maker beat Susquehanna at its own game," which is a
worse question than "is the maker side viable at all."

**Handled by declaring a second arm NOW, before any markout number exists** —
not by swapping the cohort later, which is the EXP-013 failure mode:

- **ARM 1 (primary, frozen):** top 300 by 24h volume. Unchanged. The conservative
  case. 4,979 qualified; cohort spans golf (117 of 300), ITF tennis (18),
  2028 presidential nomination (14).
- **ARM 2 (declared 2026-07-30, pre-data):** same qualifying universe, same N=300,
  **one added filter — spread >= 0.05 before ranking by 24h volume.** This is the
  actual opportunity set: takers demonstrably present AND a spread worth
  collecting. `ARM2_MIN_SPREAD = 0.05` is fixed now and is NOT searched.

Both arms are reported. **Neither is designated the "real" one after the fact:**
arm 1 answers viability in competitive markets, arm 2 in wide ones. A split result
(arm 2 passes, arm 1 fails) is the *expected* outcome if the maker edge is real but
competed away where the professionals are — and if that is what happens, it is
reported as a split, not as a pass.

Noted in passing, worth its own look later: the in-play sports markets break Part
A's monotonic volume/spread relationship. `KXITFMATCH-26JUL30ZHASOR` showed a
**21-cent spread on 253,719 contracts of 24h volume** — high volume AND a wide
spread simultaneously. That combination is exactly where a maker wants to be and
exactly where adverse selection should be worst (the taker just watched the point).
Arm 2 will contain these; the per-series breakdown will be informative.

### PART B RESULT — ARM 2 RUN 2026-07-30 · PASS as specified, but the gate was weak

23,033 fills · 60 markets · 11 distinct sessions · 10-min horizon (as pre-registered).

    mean markout (per contract)  +0.00696
    mean markout (vol-weighted)  +0.00359
    median                       +0.00500
    profitable share              58.0%
    maker SOLD    n=18416  mean  +0.00852
    maker BOUGHT  n= 4617  mean  +0.00071
    pre-registered gate (mean markout > 0)  ->  PASS

**SIGN CONVENTION — established from data, and it was the opposite of my code.**
The guard fired on the first run and refused to print a verdict. A 662-trade
cross-tab of `taker_book_side` x `taker_outcome_side` against contemporaneous
quotes settled it: `taker_book_side` names the side the TAKER'S OWN ORDER sat on,
and execution happens on the OPPOSITE side.

    book_side  outcome  prints    n    yes_px-bid   ask-yes_px
    bid        yes      AT_ASK   428     +0.0100      -0.0000
    ask        no       AT_BID   234     +0.0011      +0.0091

    => book_side="bid" -> taker BOUGHT at the ask -> MAKER SOLD
       book_side="ask" -> taker SOLD  at the bid -> MAKER BOUGHT

Not the yes/no complement artifact that was the competing explanation: NO-takers
print at the yes-BID, which is the correct yes-equivalent of buying NO, so
`yes_price` is usable uniformly. `book_side` and `outcome_side` are perfectly
correlated (bid<->yes, ask<->no) because buying YES *is* selling NO. Confirmed at
scale on the corrected run (4291 vs 876, and 16969 vs 3939).

Without the guard this experiment would have printed a confident mean markout with
PASS and KILL transposed. Same error class as EXP-010's double-counted credit —
except EXP-010 took three hours and a hunch to catch, and this took a
pre-committed check that ran automatically. **The guard was worth more than the
result.**

#### THE GATE WAS THE WRONG QUESTION (recorded, not retroactively changed)

~~mean half-spread at entry +0.08813 · captured 7.9% · adverse selection ate 92.1%~~

**WRONG BY 7x — CORRECTED SAME DAY 2026-07-30.** That first pass divided per-fill
markout by the **cohort-snapshot** spread (0.088), not the spread standing when
each trade actually printed. Recomputed against contemporaneous quotes:

                                    ARM 2      ARM 1
    mean half-spread AT FILL      +0.01297   +0.00801
    mean 10-min markout           +0.00696   +0.00443
    share of half-spread captured    53.6%      55.2%
    mean(markout / half-spread)     +0.786     +0.617
    fills                           23,033     77,716
    sessions                            11         11

**Adverse selection eats ~45%, not 92%. A passive fill keeps roughly half the
spread** — an ordinary, healthy market-making number, not a wall.

**WHY THE DENOMINATOR WAS 7x TOO BIG — the real lesson.** Arm 2 selected markets
showing spread >= 0.05 *in one snapshot*. Spread is mean-reverting, so that filter
did not select persistently-wide markets; it selected markets that were
**momentarily** wide at freeze time. By the time trades printed they had reverted
to ~1.3c. That is selection on noise — the same error as ranking stocks by a single
day's volatility. Any future cohort rule must select on a spread measured over a
WINDOW, never a point-in-time snapshot.

**Consequence: the two arms did not separate.** 53.6% vs 55.2% capture is a null
result on the arm-1/arm-2 distinction, which was the whole point of declaring arm 2.
The pre-registration was sound and is left standing; the instrument simply failed
to discriminate, because both cohorts faced ~1c spreads at fill time regardless of
how they were chosen. Recorded as a design failure, not reinterpreted as a finding.

**Also invalidated: the favorite-longshot test.** The price-bucket table (SOLD
positive at high prices, BOUGHT positive at low prices) was computed against the
same stale denominator and is not interpretable. The competing explanation —
directional longshot premium vs genuine spread capture — is therefore still OPEN,
and Part C must settle it with per-fill normalisation. A resolution-censoring
artifact was separately considered and RULED OUT: all sampled cohort markets were
`active` with trades inside the prior 1.6h, so nothing was settling mid-sample.

A maker filled at the bid instantly holds a position worth ~half the spread more
than they paid. So the no-adverse-selection benchmark is **+0.088, not 0.** The
pre-registered bar of "mean > 0" is satisfied by keeping 8% of the spread, which
is a far weaker claim than the PASS label suggests.

The gate is NOT being rewritten after the fact — PASS as specified stands. But the
substantive finding is 7.9%, and Part C's gate is benchmarked against half-spread
from the start.

#### Robustness

    clustered by series (G=22):  mean +0.01169  SE 0.00327  t = 3.58
    naive (n=23033):             mean +0.00696  SE 0.00070  t = 9.99
    series with positive mean markout: 20 of 22

14,402 of 23,033 fills are one series (KXITFMATCH), and trades within a single
tennis match are heavily autocorrelated, so the naive t of 10.0 is inflated.
Clustering on series drops it to 3.58 — still significant, and 20-of-22 positive
means no single series carries the result. Negative series: KXPGAROUNDSCORE
(-0.004), KXLAUNCHES (-0.012).

#### Two things that argue against reading this as market-making alpha
1. **The edge is 92% one-sided.** Selling earns +0.00852, buying +0.00071 — near
   zero. Genuine spread capture should be roughly symmetric. An 80/20 fill
   imbalance skewed to the sell side looks more like a directional risk premium
   than a maker edge, and "paid to sell longshots" already has a name
   (favorite-longshot bias). Part C must test the two sides separately.
2. **Markout is not realized P&L.** It measures the mid 10 minutes out. Exiting
   requires crossing a spread again, or holding to settlement. Positive markout
   means the position gained value, not that the gain is collectable.

**This is nonetheless the first experiment in 15 where the premise cleared AND the
execution wall did not immediately close it.** The residual is thin (8% of spread)
and Part C applies two further taxes — queue position and full collateral — but
this is the first live door in the ledger rather than another wall.

### Part C — PRE-REGISTERED 2026-07-30, BEFORE ANY SIMULATOR CODE EXISTED (K=1)

Part B says a passive fill keeps ~54% of the contemporaneous half-spread. Part C
asks the only question that decides tradeability: **of the fills you would actually
GET, sitting at the back of a real queue, does the residual survive?**

Part B measured fills that went to whoever was at the FRONT. That is not a random
sample. Orders at the back fill preferentially when a large order sweeps several
levels, which is disproportionately informed flow. The fills you receive are
selected to be worse than the fills Part B measured.

#### Strategy — fully specified, ONE configuration, no variants
- At each 1-minute bar, rest `Q = 1` contract at the current best bid AND best ask.
- **NEVER improve the price.** Only ever JOIN the existing best bid/ask. Joining
  does not change the market; improving would, and the counterfactual would be
  invalid. This is a hard constraint, not a parameter.
- **Queue model:** an order joining price level P sits behind the size already
  resting at P (from `/orderbook` depth). It fills only once cumulative taker
  volume executing at P exceeds the size ahead of it.
- **Requote:** if best bid/ask moves, cancel and rejoin the new best — **queue
  position resets to the back.** Losing priority on every requote is the dominant
  realism cost and is modelled, not waived.
- **Inventory limit:** `|position| <= MAX_POS = 10`. At the limit, stop quoting the
  side that would increase exposure.
- **Fees:** maker = 0 (cohort excludes all `quadratic_with_maker_fees` series).
  Taker fee `0.07*P*(1-P)` charged ONLY on terminal liquidation.
- **Terminal:** liquidate remaining inventory by CROSSING (long -> sell at bid,
  short -> buy at ask) and pay the taker fee. No settlement data required, so the
  sim does not select on "markets that resolved quickly," and the marking
  assumption errs pessimistic rather than assuming an exit at mid.

#### AMENDMENT 2026-07-30 — queue depth is not observable historically (pre-result)
Found while writing the simulator, BEFORE any P&L was computed. `/orderbook`
returns only a LIVE snapshot and candlesticks carry no size, so the size resting
ahead of my order at a historical minute cannot be observed. Substituting today's
live depth for every past minute would be a fabricated queue model.

Handled by treating `size_ahead` as an unobservable nuisance parameter and
reporting the result ACROSS a grid fixed now: **S in {0, 25, 100, 400}**.

- **S = 100 is PRIMARY**, and it is justified by an INDEPENDENT measurement, not by
  outcome: Part A's `medBidSz` was exactly 100 in four of six volume buckets.
- S = 0 is the no-queue upper bound (what Part B effectively assumed).
- The gate below applies to the PRIMARY S = 100 only. The others are sensitivity.

This is a grid over a nuisance parameter, not a strategy search: the strategy stays
K = 1. Reporting sensitivity to an unmeasurable input is disclosure; picking the S
that passes would be the EXP-013 error and is forbidden.

#### Gate 0 — tradeability, checked before P&L is even interpreted
If **fill rate < 1% of quote-minutes**, the strategy is untradeable at any P&L
sign and Part C reports UNTRADEABLE. A large edge on fills you never get is not
an edge.

#### PASS requires ALL
1. **Total P&L > 0** after terminal liquidation costs and fees.
2. **>= 60% of series** with positive P&L (not carried by one series — Part B was
   62% one series by fill count, so this matters).
3. **>= 60% of sessions** with positive P&L.

REPORTED BUT NOT GATED: Sharpe of the daily P&L series. With 11 sessions a Sharpe
estimate is badly underpowered, and gating on three correlated metrics would mean
calling a coin flip a signal. Also reported: fill rate, P&L per fill, peak
collateral, and P&L per dollar of collateral against the 4.5% risk-free drag.

#### Pre-committed interpretation limits
- A PASS means "the maker side survives a conservative simulation on one venue over
  11 sessions." It is NOT a reason to fund an account. Everything stays paper.
- The **longshot-premium vs spread-capture** question is still OPEN (Part B's test
  used the stale denominator and proved nothing). Part C reports P&L split by entry
  price bucket with per-fill normalisation. If the P&L concentrates in one price
  region, this is a directional premium and NOT market making.
- 11 sessions of one venue in one week. No regime variation whatsoever.

#### Known limitations, stated before the result
1. **Cohort selection is compromised** and is not being re-cut to flatter the
   result. Arm 2's spread filter selected momentarily-wide markets (selection on
   noise, see above). Part C runs on BOTH existing arms as-is. A future experiment
   should select on a windowed spread; changing the cohort now, after seeing Part
   B, would be exactly the EXP-013 error.
2. **1-minute bars, not tick data.** Within-minute sequencing is invisible, so the
   fill model cannot know whether the sweep happened before or after a requote.
   Resolved conservatively: a requote in a minute forfeits that minute's fills.
3. No hidden/iceberg size, and no modelling of cancellations ahead in the queue
   (which would HELP, so omitting them is conservative).

#### PART C RESULT — ARM 2 RUN 2026-07-30 · **KILL** (both gates fail, decisively)

60 markets · 10 days · 36,691 quote-minutes · Q=1 · MAX_POS=10

        S  fills  fill rate     P&L $   $/fill   liq cost$
        0    909     2.48%    -36.58   -0.0402      3.79
       25    634     1.73%    -31.03   -0.0489      3.36
      100    424     1.16%    -23.20   -0.0547      2.70   <== PRIMARY
      400    219     0.60%    -12.10   -0.0552      1.57

    Gate 0  fill rate >= 1%          1.156%          OK (tradeable)
    1.      total P&L > 0            -$23.20         FAIL
    2.      >=60% series positive    2/22 (9%)       FAIL

**THE DECISIVE FEATURE IS THE MONOTONICITY, NOT THE SIGN.** P&L gets worse as
queue position IMPROVES: front of queue (S=0) loses $36.58, deep in queue (S=400)
loses $12.10, and `$/fill` is pinned near -$0.05 across the whole grid. If the
strategy had an edge, a better queue position would earn MORE. Instead the only
way to lose less is to be filled less. **Every fill is bad on average**, and the
result holds at all four values of the unobservable queue depth — so it is not an
artifact of the S assumption.

**This is exactly the selection effect Part C was pre-registered to catch.**
Part B measured fills that went to whoever was at the FRONT of the queue: mostly
small, uninformed flow, keeping ~54% of a 1.3c half-spread. Part C measures the
fills *you* would receive from the back — which arrive when a large order sweeps
your price level, i.e. informed flow. Losing 5.5c per fill against a 1.3c
half-spread means adverse selection of ~6.8c on the fills you actually get, about
5x the spread being collected.

So Part B's PASS and Part C's KILL do not conflict. Part B answered "is there
spread left after adverse selection, on average, across all fills?" (yes). Part C
answered "is there spread left on the fills a back-of-queue retail maker gets?"
(emphatically no). The second question is the one that determines tradeability,
which is why the gate structure put it last and gave it the deciding vote.

Per-series: 2 of 22 positive. Worst: KXITFMATCH -$5.66, KXPGAROUNDSCORE -$3.41,
KXATPCHALLENGERMATCH -$2.96. The two positives (KXCLUBFTOTAL +$0.24,
KXLAUNCHES +$0.13) are small-n.

**PROCESS ERROR, self-caught:** the first printout multiplied P&L by 100, reporting
-$2,319.68 and -$5.47/fill. `yes_bid_dollars` is already denominated in dollars, so
the cents-to-dollars conversion was spurious. The tell was arithmetic: a 1-contract
position at price p costs $p and pays $0 or $1, so |P&L per fill| can never exceed
$1 and -$5.47 was impossible on its face. Every gate is scale-invariant (P&L sign,
share of positive series, monotonicity in S), so the KILL is unaffected — but the
magnitudes were wrong by 100x for one report and the bug is fixed in
`exp015_partc.py`.

**RETRACTED 2026-07-30, same day: "the direction is CLOSED" was written on ARM 2
ALONE, before arm 1 finished running.** Arm 1 contradicts it — see the arm 1 result
below. Calling a direction closed on one of two pre-registered cohorts, while the
second was still computing, is exactly the kind of premature conclusion this
ledger exists to prevent. The original text is struck through, not deleted:

~~VERDICT: the Kalshi maker direction is CLOSED for a retail back-of-queue quoter.~~

Also OVERSTATED in the arm 2 write-up above: "every fill is bad on average, the
monotonicity proves it." The per-fill numbers say fill QUALITY improves toward the
front (-$0.055 deep vs -$0.040 at front), exactly as market-making theory predicts.
Total P&L is worse at the front only because it is more fills times a still-negative
per-fill figure. The monotonicity in TOTAL P&L is arithmetic, not evidence about
fill quality.
Recorded against the pre-registered gates, with no re-cutting of the cohort, no
switching to arm 1 hoping for a different answer, and no reinterpretation of the
grid. Arm 1 is still worth running for completeness and will be reported whatever
it says, but a monotonic loss across every queue depth is not a result that a
second cohort overturns.

#### PART C · ARM 1 RESULT + P&L DECOMPOSITION — RUN 2026-07-30

60 markets · 10 days · 87,375 quote-minutes.

        S  fills  fill rate    P&L $   $/fill
        0    7158     8.19%   +16.95   +0.002    front of queue: PROFITABLE
       25    4483     5.13%    +2.43   +0.001
      100    2807     3.21%    -2.45   -0.001    PRIMARY: essentially breakeven
      400    1562     1.79%    -7.05   -0.005

    Gate 0  fill rate >= 1%        3.213%        OK
    1.      total P&L > 0          -$2.45        FAIL
    2.      >=60% series positive  11/23 (48%)   FAIL

**ARM 1 FAILS the pre-registered gates and is recorded as FAIL.** But it fails by
$2.45 across 2,807 fills and is PROFITABLE with queue priority — a completely
different result from arm 2's rout, and the arm distinction finally earning its
keep (though not in the direction it was designed for: tight liquid markets have
benign flow; transiently-wide sports markets are wide *because* informed traders
are there).

#### THE DECOMPOSITION — the loss is INVENTORY RISK, not adverse selection

        S      spread earned   inventory/trend   liq cost      NET   peak|pos|
        0            +$40.90           -$21.30     -$2.65   +$16.95        10
       25            +$25.56           -$20.75     -$2.38    +$2.43        10
      100            +$16.47           -$16.43     -$2.49    -$2.45        10
      400             +$8.70           -$13.42     -$2.32    -$7.05        10

**Spread earned is POSITIVE at every queue depth.** The fills are good; the
strategy really does capture spread. Adverse selection is NOT the binding problem
on arm 1 (it clearly was on arm 2).

**Inventory loss is roughly CONSTANT** (-$13 to -$21) while spread income scales
with queue position. That single asymmetry explains the whole P&L curve: at the
front $40.90 of spread beats $21.30 of inventory bleed; deep in the queue $8.70
does not beat $13.42.

**`peak |pos| = 10` at EVERY depth** — the position is pinned against its own cap.
The simulated strategy accumulates one-sided inventory and eats the trend, because
it was given no inventory management beyond a hard limit. That is a flaw in the
naive implementation, not evidence against market making.

#### NEXT STEP, and the anti-overfitting reasoning for it
The named failure is inventory risk, and the canonical published fix is
**Avellaneda-Stoikov (2008), "High-frequency trading in a limit order book"** —
inventory-aware quote skewing: when long, shift BOTH quotes down to encourage
selling and discourage further buying. Parameters derive from observables
(volatility, order arrival rate), not from fitting P&L.

This qualifies as a legitimate K=1 addition by the same test that justified HAR-RV
(EXP-014, the only durable PASS in this ledger): a boring published model, applied
to a pre-identified failure, with nothing tuned to our data. Same discipline —
Corsi's 1/5/22 horizons were forbidden from being searched, and A-S's parameters
must be too.

EXPLICITLY FORBIDDEN as "improvements": tuning MAX_POS until P&L turns positive;
selecting series after seeing per-series P&L; searching the requote threshold;
choosing the S that passes. Test for any proposed change: *could it have been
written down before seeing this data?* If not, it is overfitting.

**Free and legitimate before any strategy change:** extend 10 -> ~120 days (the
1-min candle history exists that far back; the 429s at day -45/-90 were rate
limits, not missing data) and 60 -> 300 markets. More evidence is not a new choice.

#### The structural caveat that survives all of this
Arm 1's profitability depends on QUEUE POSITION (+$16.95 front vs -$7.05 deep).
Queue priority is won with speed, colocation and exchange rebates. A Python script
polling REST endpoints at 60s is at the back of the queue BY CONSTRUCTION, and no
amount of inventory skewing changes that. So the realistic ceiling here is
"breakeven at S=100," and the honest read is that the edge is real and belongs to
whoever has better plumbing. That is the same wall as the other fifteen
experiments, wearing different clothes.

#### SAMPLE EXTENSION 2026-07-30 — more evidence, SPEC UNCHANGED

Part C ran on 10 days / 60 markets. That was my under-use of the data, not a limit
of it: the probe showed 1-minute candles available at least 120 days back (the
429s at day -45/-90 were RATE LIMITS, not missing history), and trades paginate
back weeks.

Extending to **120 days / 300 markets per arm**. This changes ONLY the sample.
The strategy, queue model, S-grid, primary S=100, Gate 0 and both PASS conditions
are all untouched. More data on a frozen spec is additional evidence, not a new
choice — it is the one improvement that cannot be an overfit, which is exactly why
it comes BEFORE any strategy change (e.g. Avellaneda-Stoikov skewing).

Implementation: `research/exp015_fetch.py` caches candles+trades per market to
`research/exp015/cache/`, resumable and rate-limited, so the expensive fetch
happens once and every later analysis (S-grids, A-S variants, decompositions)
reads from disk for free. `exp015_partc.py --cached` runs the identical simulator
against the cache — the cache changes where bytes come from, never what is
computed.

PRE-COMMITTED: the 10-day results already recorded above STAND as the
pre-registered Part C outcome. The 120-day run is reported ALONGSIDE them, not as
a replacement. If the two disagree, both are shown and the disagreement is the
finding — silently promoting whichever looks better would be the EXP-013 error.

#### 120-DAY RESULT — ARM 1, FULL 300 MARKETS · **KILL CONFIRMED**

300 markets · 120 days · 2,059,754 quote-minutes · 62MB cached tape.

        S  fills  fill rate     P&L $   $/fill
        0  67047     3.26%    +165.08   +0.002
       25  40827     1.98%     +41.81   +0.001
      100  25095     1.22%      -7.17   -0.000   <== PRIMARY
      400  12925     0.63%     -26.11   -0.002

    Gate 0  fill rate >= 1%        1.218%        OK
    1.      total P&L > 0          -$7.17        FAIL
    2.      >=60% series positive  33/77 (43%)   FAIL

**Robustness (pre-committed BEFORE this number was seen):**

    all 77 series                -$7.17
    excluding KXMAYORLA          -$46.06   positive 32/76 (42%)
    median series P&L            -$0.24
    series losing money          44/77

**A single market moves the total from -$46 to -$7.** KXMAYORLA (+$38.89) is 5.4x
the next largest contributor. Gate 2 exists to catch exactly this and did.

**THE PARTIAL READ WAS MISLEADING — and the caveat was right.** A preliminary run
on the first 105 cached markets showed +$33.47 and a gate-1 PASS. Those 105 were
the MOST LIQUID THIRD (the cohort is sorted by 24h volume), and it was flagged at
the time that the remaining 195 would likely drag it down. Full 300: -$7.17, FAIL.
Recorded because it is a clean example of why a non-random subset is not a preview.

**Both windows now agree, as pre-committed to report:**

    10 days  /  60 markets   arm 1   -$2.45   FAIL
    120 days / 300 markets   arm 1   -$7.17   FAIL
    10 days  /  60 markets   arm 2  -$23.20   FAIL

20x more data, same verdict. No window is being promoted over another.

**THE DIAGNOSIS IS STABLE ACROSS EVERY SAMPLE SIZE AND QUEUE DEPTH:**

    S=100, 120d:  spread earned +$139.12 | inventory/trend -$133.60 | peak|pos| 10

Spread capture is POSITIVE everywhere. Inventory bleed cancels it almost exactly.
`peak |pos| = 10` at every S in every run — the position is permanently pinned at
its own cap. The fills are good; there is no inventory management.

**That gap is why the A-S step is worth running rather than abandoning:** at S=100
the strategy earns $139 of spread and gives back $134 to inventory. Removing even
half the inventory bleed would flip -$7 to roughly +$60. The failure is named,
localised, and has a canonical published fix.

#### INVENTORY-SKEW RUN 2026-07-30 — real effect, but NOT Avellaneda-Stoikov

Pre-registered as an A-S inventory skew with gamma normalised to one tick.
**The implementation degenerated and the label was wrong.** Reported as found.

        S    skew   fills     P&L $  spread$  invent$  series+
      100    none   25095     -7.17   139.12  -133.60   33/77
      100   0.005   18056    +37.89    97.53   -58.29   42/77
      100   0.010   18056    +37.89    97.53   -58.29   42/77   <== "PRIMARY"
      100   0.020   18056    +37.89    97.53   -58.29   42/77

**THE PARAMETER IS INERT.** All three skew magnitudes give byte-identical output
across a 4x range. The algebra shows why:

    r - half = (bid+ask)/2 - skew_term - (ask-bid)/2 = bid - skew_term
    want_bid <=> bid - skew_term >= bid <=> skew_term <= 0 <=> pos <= 0

The magnitude cancels exactly. Only the SIGN of inventory survives, so the rule
actually tested was **"quote the bid only when flat-or-short, the ask only when
flat-or-long."** That is a crude one-sided-quoting rule, NOT A-S.

Root cause: genuine A-S posts at a SHIFTED PRICE — the model is entirely about
where to quote, continuously. Part C's hard "never improve the price" constraint
(which exists to keep the counterfactual valid) makes a shifted quote
inexpressible, so the model collapsed. The constraint and the model are
incompatible as specified; that is a design conflict, not a coding slip.

**What the result does and does not show:**
- REAL: inventory control cuts the bleed 56% (-$133.60 -> -$58.29) and flips P&L
  from -$7.17 to +$37.89. The decomposition's diagnosis is confirmed — inventory
  risk, not adverse selection, was the binding failure.
- ALSO REAL: fills drop 25,095 -> 18,056. Roughly a third of the improvement is
  simply trading less, which is not the same as trading better.
- **GATE 2 STILL FAILS: 42/77 series positive (55% < 60%).** So even with the
  inventory rule, Part C is a FAIL. Gate 1 alone is not a pass.
- NOT SHOWN: anything about Avellaneda-Stoikov. The model was never actually
  tested. Any future claim that "A-S was tried" would be false.

**Not being fixed by relaxing the constraint.** Letting the sim post inside the
spread would require modelling how my own quote changes other participants'
behaviour — a counterfactual this data cannot support. Better to record that A-S
is untestable under this design than to fake it with a fabricated market response.

NAMING CORRECTION: `SKEW_GRID`/`SKEW_PRIMARY` in exp015_partc.py should be read as
a one-sided-quoting switch, not as A-S gamma. The grid is meaningless and is kept
only to document the degeneracy.

#### PART D — AVELLANEDA-STOIKOV, PROPERLY IMPLEMENTED · **FAIL** (2026-07-30)

294 of 300 markets · 120 days · gamma grid [0.05 0.1 0.5 1.0 2.0] · S grid [0 25 100 400]

        S   gamma   fills     P&L $   $/fill  series+
      100    0.05     929    -21.07  -0.0227    3/77
      100    0.10    1043    -21.27  -0.0204    3/77
      100    0.50     927    -19.07  -0.0206    2/77
      100    1.00     652     -8.56  -0.0131    2/77
      100    2.00     594     -8.87  -0.0149    1/77

Negative in 19 of 20 cells. **Gate 2 fails in ALL 20** — best is 3/77 series
positive (4%) vs 33/77 for the no-skew baseline. The lone positive cell
(S=400, gamma=2.0, +$1.83, 391 fills, 2/77 series) is noise.

**WHY IT FAILS — the informative part.** Fills collapsed 25,095 -> ~900, a 96%
drop. A-S's optimal half-spread is

    d = [ gamma*sigma^2*(T-t) + (2/gamma)*ln(1 + gamma/k) ] / 2

where k is the ORDER ARRIVAL RATE. Kalshi markets are slow — a few trades per
minute. Small k makes gamma/k large, blowing up ln(1+gamma/k), so d comes out far
WIDER than the market's own spread. The model therefore posts well off the touch
and essentially stops trading.

**A-S was derived for continuous-time, high-arrival-rate markets. In a
low-arrival-rate venue its optimal spread exceeds the market spread and the
strategy degenerates into not quoting.** That is a property of applying the model
outside its regime, not a coding error, and it is the substantive result of Part D.

**Pre-registered limitation, honored:** only the PULL-BACK half of A-S was tested.
Quotes were clamped at the touch and never improved it, because quoting inside the
spread creates a new best price and simulating the market's reaction would require
inventing data. A-S's lean-in behaviour remains untested, and this result makes no
claim about it. Note the failure mode observed (quoting too WIDE) is in the
pull-back direction, so the untested half would not obviously rescue it — but that
is reasoning, not evidence.

gamma is A-S's one free parameter. The grid is DISCLOSURE, not selection: every
cell is reported and no gamma is designated primary after the fact. sigma and k
were MEASURED per market from its own mid-returns and trade counts.

#### EXP-015 FINAL STATE

    Part A  is there a spread to collect?                 PASS
    Part B  does it survive adverse selection on average? PASS  (~54% of half-spread)
    Part C  does it survive the fills YOU get?            FAIL  (both arms, 10d and 120d)
    Part C' one-sided quoting rule                        gate 1 pass, GATE 2 FAIL (55%)
    Part D  Avellaneda-Stoikov                            FAIL  (19/20 cells, gate 2 all 20)

**VERDICT: Kalshi market making does not survive at retail queue position.** The
edge is real (spread capture positive in every configuration) and the binding
constraints are two, both structural rather than strategic:
1. **Queue priority** — profitable at the front, breakeven at S=100, losing deeper.
   Won with speed, colocation and rebates; not with better strategy code.
2. **Capacity** — peak capital $724 at Q=1 across 300 markets. Best observed P&L
   +$37.89/120d = 15.9% annualised on that capital. Scaling Q to 100 makes you the
   entire book, at which point the queue model and the no-impact assumption both
   fail. The strategy cannot absorb meaningful size.

16 experiments, 2 durable passes. This one closes on capacity and market
microstructure, not on absence of edge — a materially different failure from the
seven that died because the signal was never there.

### Caveats stated in advance, not after
1. ~~**Simulated fills are OPTIMISTIC and Part B is an UPPER BOUND.** Public data
   shows top-of-book price and size but not my position in the queue.~~
   **REVISED 2026-07-30, same day, before any Part B data:** this caveat was too
   pessimistic and I wrote it before checking the endpoints. `/markets/{t}/orderbook`
   returns **full depth per price level**, and `/markets/trades` returns
   `taker_book_side` per trade — which resting side actually got hit. So queue
   position IS modellable from free public data: an order joining price level P
   rests behind exactly the size already resting at P, and fills only once that
   much volume trades through P on the taker side. Part B therefore uses a
   **conservative queue model**, not an optimistic top-of-book fill.
   Residual optimism that remains: I cannot see hidden/iceberg size, order
   cancellations ahead of me (which would help), or the sub-poll-interval sequence
   of events at 60s cadence. So a Part B pass is still necessary rather than
   sufficient — just far less loosely so than this caveat originally claimed.
2. **Capital efficiency is poor by design.** Kalshi requires full collateral and
   offers no leverage: $1 of exposure locks $1 of cash. Even a positive markout has
   to clear that opportunity cost, which at ~4.5% risk-free is a real hurdle.
3. **Paper study only.** Read-only public API, no account, no keys, no orders — the
   same standing rule as `predmarket/`.
4. This tests one venue. A pass says "the maker side is viable on Kalshi," NOT
   "market making works" — and specifically does not transfer to the options VRP
   without its own A/B, where spreads are wider but so is the competition.

### Process note carried forward
Part A's first run was invalid: I used `volume` and `open_interest`, which do not
exist on Kalshi's market object (`volume_fp`, `open_interest_fp`,
`liquidity_dollars`). A permissive float coercion turned every missing key into
0.0, so all 10,612 two-sided markets were classified "never traded" — a clean-
looking table that measured nothing. Third field-name error on this API in one
session. The v2 script asserts the required keys exist on the first page and fails
loudly if the schema moves.

---

## EXP-016 — Where are Kalshi prices wrong, and can a taker collect it?

**Status:** PRE-REGISTERED 2026-09-13 (full spec: research/exp016_spec.md) ·
HOLDOUT SEALED · Phase 1 exploration authorised on the calibration window only.

**Why:** EXP-015 died on queue position — a 60s REST poller is at the back of the
line by construction, so its fills are the informed ones. That constraint binds
passive fills only. A taker who takes a price once and holds to resolution does
not need speed, and predmarket/'s twice-daily snapshots + resolutions are built
for exactly that. Published work (Whelan, 300k+ Kalshi contracts) finds a
favorite-longshot bias; unemployment markets show it (−7.7c on contracts under
$0.30), CPI markets do not. The premise is likely TRUE, unlike most deaths in this
ledger. The live question is narrower: does any of it survive a taker's spread,
fees and locked collateral, and in which domains.

**Crowding read:** the bias is created by retail longshot buyers and collected by
professional makers with better plumbing (EXP-015's wall). "Always buy the
near-certain side" is the retail version — REJECTED. A conditioned version on a
dataset nobody sells is a capability barrier — allowed.

**Feasibility, checked before registration (the `result` column was NOT read):**

    resolved markets that also appear in a snapshot        3,192
      only snapshotted after close/settlement (leak)          379
      a snapshot >= 24h before close                        2,750
      two-sided quote at that snapshot                        944
    most common quote at that snapshot: bid 0 / ask 1c (907), bid 99c / ask $1 (357)
    independent clusters among the 944: 127 (category, close date) to 302 (ticker rule)

Data defects found: `liquidity` (Kalshi `liquidity_dollars`) is 0.0000 in every
row — never valid, do not use. Only markets above the collector's open-interest
floor are snapshotted (a selection, not a bug). 38% of the tradeable sample is
Elections, mostly primaries.

**FROZEN — cannot change based on anything exploration shows:**
- **HOLDOUT:** markets with close_time >= 2026-09-01. Their outcomes are not read,
  plotted or summarised until Phase 2 is registered. Every future resolution from
  the running collector joins the holdout automatically.
- **Snapshot:** the last one with ts <= close_time − 24h AND ts < first_seen_settled.
  None qualifying → excluded.
- **Tradeable:** yes_bid > 0, yes_ask < 1, yes_bid < yes_ask.
- **Prices:** calibration uses mid; P&L uses the executable side only — yes_ask to
  buy YES, 1 − yes_bid to buy NO.
- **Result values:** only `yes` / `no` count; anything else (voided, cancelled) is
  excluded and counted.
- **Fees:** ceil(M × 0.07 × C × P × (1 − P)) to the cent at C = 100, divided by C;
  C = 1 reported alongside. M from Kalshi's schedule per series, M = 1 if unknown
  (flagged).
- **Excess per contract, in dollars:** payoff − cost − fee − cost × 0.045 ×
  days_held / 365. (Additive form of "return minus risk-free", chosen now because
  the annualised ratio explodes on one-day holds. Same sign.)
- **Cluster:** (category, close date) PRIMARY; ticker-rule clusters reported alongside.
- **Estimator (named in advance, the EXP-012 lesson):** equal-weighted mean across
  clusters of each cluster's mean excess per contract. Inference: block bootstrap
  resampling clusters, 10,000 resamples.

**Phase 2 gates — for each hypothesis carried, ALL required, on the holdout:**
1. Estimator > 0 with bootstrap P(<= 0) < 0.05 / K.
2. Same sign in >= 60% of clusters.
3. Sample >= 400 tradeable contracts AND >= 60 primary clusters. Otherwise
   UNDERPOWERED — not FAIL; report and wait for resolutions.

The full holdout is primary. If one close date holds more than 20% of clusters,
the result excluding that date is shown ALONGSIDE, never substituted.

**Priors, written before any outcome was seen:** a bias exists somewhere in the
sample — likely. Any of it survives costs on the holdout — unlikely (base rate 3
passes in 15). Most likely result: the bias sits in one-sided extremes where
nothing is executable, and the two-sided middle is roughly calibrated.

**Already ruled out — do not repeat:** Kalshi market making (EXP-015, twice);
ladder/overround arbitrage (0 of 169 exhaustive events); cross-venue arbitrage
with orders (read-only rule); naive near-certain buying (crowding).

### PHASE 1 RESULT — 2026-09-13 (calibration window, ~30 cuts, no verdicts)

Full record: research/exp016_exploration_log.md. Pooled "buy the favorite >= 0.70"
was −0.85c per contract after fees and collateral (95% CI −4.28 to +2.07). The
published bias appears only where it cannot be traded: 900 markets quoted ask
<= 1c with no bid resolved YES 0.11% of the time. The tradeable middle is roughly
calibrated, minus the spread — as the prior predicted. Rejected candidates and the
reason for each (neighbouring-band sign flips, a permanently underpowered subset,
a forbidden horizon switch) are in the log, written before this registration.

### PHASE 2 — REGISTERED 2026-09-13, before any holdout outcome was read. K = 2.

All Phase-1 frozen mechanics apply unchanged. Common to both hypotheses:
- **Universe:** holdout markets, 24h snapshot rule, tradeable rule, result yes/no.
- **Trade rule:** at the snapshot, fav = max(mid, 1 − mid). Trade only if fav >= 0.70.
  If mid >= 0.50 buy YES at yes_ask, else buy NO at 1 − yes_bid. One unit per market.
- **Category:** the `category` field of kalshi_resolutions.csv.
- **Fees:** M = 1 for every series (Tyler, 2026-09-13; consistent with public fee
  schedules, where only Crypto differs and Crypto is not collected). C = 100.
- **Gates, each hypothesis, ALL required:** estimator > 0 with bootstrap P(<= 0)
  < 0.025; cluster means > 0 in >= 60% of clusters; the hypothesis's OWN trade set
  has >= 400 contracts and >= 60 primary clusters, else UNDERPOWERED.

**H1 — buy favorites >= 0.70 in every category except `Elections`.** Calibration:
371 trades, 76 clusters. Honest note: Elections was excluded after seeing it lose
(−5.80c). That is allowed only because the holdout judges it; expectation is low.

**H2 — buy favorites >= 0.70 in `Financials` only.** Calibration: 209 trades, 25
clusters, +2.48c. Mechanism: company-metric brackets anchored to analyst consensus,
with retail overpaying for surprise outcomes.

**Scoring discipline (no optional stopping):**
- The sample-bar check reads NO outcomes. It may read only whether a market's
  result is binary, never which side won.
- Each hypothesis is scored EXACTLY ONCE, automatically, on the first run after its
  bar is met. The score is written to research/exp016_phase2_result_H{n}.json and
  the scorer refuses to overwrite it. Markets later found non-binary at scoring are
  excluded and counted; the verdict stands on the remainder.
- Deadline: a hypothesis whose bar is not met by 2027-03-01 is final UNDERPOWERED.
- Expected timing from calibration-window rates: H1 around early November 2026;
  H2 around January 2027 (60 Financials close dates at ~3.5 a week).
- **EXP-016 is closed to new hypotheses.** Anything from the Kalshi–Polymarket
  matcher goes to a new experiment with its own later holdout, because scoring H1
  and H2 will expose September-onward outcomes.
- Scorer: research/exp016_phase2.py. Its `--selftest` runs the identical code on
  the calibration window and must reproduce Phase 1's trade counts before it may
  score the holdout.

---

## EXP-017 — Does a public weather forecast know something Kalshi's price doesn't?

**Status:** PRE-REGISTERED 2026-09-13 (full frozen spec: research/exp017_spec.md) ·
HOLDOUT SEALED · no outcome or price value from these series read before registration.
**K:** Part A = 1, Part B = 1 (only if A passes).

**Why — the pattern across all deaths, recounted from this ledger on 2026-09-13:**
seven premise-false deaths (001, 003, 004, 006, 008, 012, 013), at least six of them
sourced from published papers or textbook anomalies; five real-but-untradeable
(005, 007b, 010, 011, 015), every one a PREMIUM for supplying risk or liquidity
that goes to the cheapest supplier, which a slow retail taker never is. EXP-016
Phase 1 and the Kalshi–Polymarket matcher hit the same wall (bias only at 1c; venue
gaps ~1c). Every idea so far searched inside prices everyone sees. This is the
first INFORMATION-edge test: a public non-price forecast of the settlement number,
used hours before close and held to settlement, so speed is irrelevant and the
spread is paid once.

**Correction logged with this entry:** research/SUMMARY.md had counted EXP-015 as a
PASS. Its final state above is FAIL at Part C (queue position). Corrected to 2
passes in 15.

**Design in one paragraph.** Seven Kalshi daily-high-temperature series
(NY, CHI, MIA, AUS, DEN, LAX, PHIL), NWS-settled era only (close <= 2026-08-14; the
settlement source switched to The Weather Company from 2026-08-15). At 15:00Z on
day D, compare the Kalshi mid with the probability implied by the NBM 07Z text
bulletin's max-temperature forecast and its own standard deviation (txn, xnd), with
nothing fitted. Calibration: day D <= 2025-05-31. Holdout: 2025-06-01 .. 2026-08-13.
- **Part A (calibration):** slope beta of (outcome - mid) on (forecast - mid);
  PASS needs beta > 0 at P < 0.05 by week-cluster bootstrap AND beta >= 0.20.
- **Part B (holdout, once):** buy the side where forecast minus executable price
  minus fee >= 0.05; hold to settlement. PASS needs a positive week-clustered mean
  at P < 0.05, >= 60% of cities positive, still positive without the best week,
  >= 400 trades and >= 60 weeks (else final UNDERPOWERED).

**Crowding read:** RETAIL-crowded (hobbyist weather bots use these same NOAA
forecasts). Registered as a measurement of the direction, with the pre-commitment
that a PASS authorises nothing: it returns to Tyler as a crowding decision.

**Not registered, on structure:** CPI/Fed/payrolls (monthly, cannot reach 60
independent clusters); S&P ranges vs SPX options (feasible, ~$45-60 of OPRA data,
needs spend approval and its own spec; EXP-018 candidate).

**Priors:** Part A pass ~60%; beta decays by year; Part B holdout pass ~15%.

### RESULT — 2026-09-13 · Part A PASS · Part B holdout **FAIL** (decisive)

Data: 44,094 markets; usable (fresh two-sided quote + forecast) calibration 15,995
over 200 weeks, holdout 12,990 over 64 weeks. Result files: exp017_partA.json,
exp017_partB_calibration.json, exp017_partB_holdout.json (exclusive-create).

    PART A  (calibration)   beta 0.259   CI 0.21-0.31   P(<=0) 0.000   PASS
            alongside: beta by year 2021 .31 | 2022 .16 | 2023 .33 | 2024 .39 | 2025(Jan-May) .05
                       Brier market 0.159 vs forecast 0.177 (the price beat the forecast even here)
    PART B  calibration     -0.84c/contract  CI -2.25..+0.59   7,809 trades   (recorded, not a verdict)
    PART B  HOLDOUT         -3.23c/contract  CI -4.06..-2.36   7,316 trades   0 of 7 cities positive   FAIL
            alongside: NBM v4 days -3.43c · NBM v5 days -2.02c (both negative)

Verification before the holdout was opened: beta recomputed by covariance, lstsq and
pure Python (identical, 0.25912); bootstrap recomputed without BLAS matmul (identical
CI and P). The numpy "divide by zero / overflow in matmul" warnings are the known
spurious Apple Accelerate FP-flag issue. Part B trade logic re-implemented row by row
in pure Python on calibration: same 7,809 tickers, total |excess| difference 0.0.

**Post-hoc, descriptive only — the holdout was already scored once:**
holdout beta **-0.014** (CI ~ -0.05..+0.03), 2025H2 -0.011, 2026 -0.017. Brier market
0.131 vs forecast 0.161. The market is calibrated bucket by bucket; raw NBM is
overconfident at the tails (says 1.3% where 5.9% happen). Losses in every edge bucket,
worst where the forecast disagreed most (>40c edge: -7.5c).

**Binding constraint, one line:** the free NBM forecast carried beta ~0.3-0.4 of
information Kalshi's price lacked through 2024, and ~0 from mid-2025; by then the
price was better calibrated than the forecast (Brier 0.131 vs 0.161), so a taker
trading raw disagreement lost 3.2c/contract on 7,316 holdout trades.

**Pattern across all deaths (recounted from this ledger):** premise false 7
(001 003 004 006 008 012 013); real but untradeable on execution 5 (005 007b 010 011
015); spec failed gate 1 (002); **real, then decayed before the test period 1 (017)**;
pass 2 (009A, 014). Every public-information signal tested out of sample was already
in the price when tested (008 filings, 004 8-K tags, 013 COT, 017 NBM). 017 is the
first to show the decay itself on a clock: the edge existed while the venue was young.

Checked before proposing a "new-series launch window" idea, calibration data only:
the three series that launched in the calibration period (DEN, PHIL, LAX, Nov 2024 -
Jan 2025) did NOT show high beta (-0.12, 0.13, 0.31). The decay looks venue-wide
(bots arriving), not per-series age. That idea is not supported.

**Research value kept:** a clean, pre-registered measurement of a prediction-market
category becoming efficient between 2024 and mid-2025.

---

## C2 — Execution audit (champion + challenger, live paper books)
**Status:** PRE-REGISTERED 2026-10-13 (before any order/fill data was pulled) · measurement, K = 0
**Origin:** tradingroom review. The research ledger's main finding is that the one
confirmed edge family died in *execution*. Nobody has measured what execution costs
the two equity books that are actually running. Branch `tradingroom-fixes` (1e94b61)
just changed: split-adjusted bars, close_position on exits, sell-order polling,
logging held weights, risk blocks exiting non-zero.

**Disclosed before data:** while reading code to write this I saw that
`challenger/backtest.py::run_book` and `strategy_lab.py::backtest` compute weights
from `px.iloc[:i+1]` (close of day i) and then credit `dr.iloc[i]` (the return INTO
close i) to those weights — a same-bar look-ahead. Live decides on close(i-1) and
fills near open(i). Component G measures it; I have not run it yet.

### What is measured, and the estimator for each (per book)
- **A. Arrival shortfall** per filled order: `IS_arr = side × (fill_px − arr_px)/arr_px`
  in bp, side = +1 buy / −1 sell; `arr_px` = open of the Alpaca IEX 1-min bar
  containing `submitted_at` (fallback: last 1-min close before it). Aggregate
  notional-weighted mean; $ = Σ side×(fill−arr)×qty.
- **A'. Signal-to-fill (delay)** vs prior close (the price the signal used). Reported,
  NOT counted as cost (dominated by the overnight gap, mean ≈ drift).
- **B. VWAP/close benchmark**: same formula with the day's IEX daily-bar VWAP and
  close. Counterfactual for timing (F).
- **C. Cash drag**: positions reconstructed from fill history, valued at daily close
  (Alpaca daily bars, Adjustment.ALL); idle cash = equity (portfolio history) −
  positions MV; drag = Σ max(cash,0) × T-bill/252, T-bill = 4.0%/yr flat (stated
  assumption). SHV holdings are deliberate cash, not drag; SHV's 0.15% ER reported
  as a separate small line.
- **D. Fees**: Alpaca is commission-free; regulatory fees (SEC §31 on sells, FINRA
  TAF) computed from the published schedule as an UPPER bound ($27.80/M sells +
  $0.000166/share, capped $8.30/trade). Paper accounts charge none.
- **E. Dust**: positions < 0.5% of equity or not in the logged target, $ and days held.
- **F. Open-auction timing**: for each order, `side × (fill − P_later)/P_later` with
  P_later = 1-min bar open at 10:30 ET and at 15:30 ET same day. Positive = trading
  later would have been cheaper. Notional-weighted mean, t-stat over orders.
- **G. Backtest timing assumption**: re-run `challenger/backtest.py::run_book` on its
  cache as-written vs with a 1-day lag (weights decided on i-1 earn day i);
  ΔCAGR, ΔSharpe. Also: measured all-in cost per unit turnover vs the backtests'
  TCOST = 10 bp (challenger/backtest.py, strategy_lab.py; backtest.py charges 0).
- **H. Missed / blocked days**: NYSE trading days since each book's first log row
  with no log row; risk-block rows; rows with `unfilled=` notes; days with orders in
  Alpaca but no log row (the 2026-07-07 log-commit bug).

Annualization: $ drag ÷ mean equity ÷ (calendar days/365), reported in bp/yr.

### Caveat fixed in advance
These are PAPER fills. Alpaca paper fills market orders against the quote with no
impact model, so A/F are a *lower bound* on live cost (spread only, no impact,
no queue). Small ETF tickets in liquid names → impact ~0 anyway; the bound is tight
for the 3× ETFs less so.

### Decision rule (fixed now)
1. **Order type / timing change** if A notional-weighted IS_arr > 10 bp AND the
   annualized A drag > 25 bp/yr of equity, for a book.
2. **Move trade time later (≥10:00 ET)** if F(10:30) mean > 5 bp with |t| ≥ 2 AND
   annualized benefit > 15 bp/yr. If |t| < 2, NO timing change (noise).
3. **Cash sweep / cushion change** if C > 10 bp/yr for a book.
4. **Dust / missed-run fix** if any dust > 0.5% equity persists > 5 trading days, or
   missed+blocked days > 5% of trading days.
5. **Backtest fix** if measured all-in cost/turnover > 10 bp (TCOST understated), or
   G changes Sharpe by > 0.05 (look-ahead material). Backtest fixes change what we
   *believe*, not what trades.
No result here justifies a live-strategy change; all changes are execution plumbing,
delivered as a patch, applied only on Tyler's go-ahead.

### Result
**Run 2026-10-13. Data:** 446 champion orders (05-22..10-13) and 194 challenger orders (06-10..09-22), all market/day, all filled. IEX 1-min + daily bars. Read-only. Full report: scratchpad `tradingroom/c2_execution_audit.md`.

| bp/yr of mean equity | champion full | champion since 08-01 | challenger |
|---|---|---|---|
| turnover (x/yr) | 93 | 71 | 12.5 (backtest: 2.9) |
| A arrival IS | 494 (6.1bp/order, t=2.5) | 102 (1.4bp/order) | -35 (noise) |
| D reg fees (upper bound) | 14 | ~11 | 1.4 |
| C idle cash @4% | 10.3 | | 0.4 |
| F open vs 10:30 | +13bp/order, t=0.28 (n.s.) | | -14bp/order, t=-1.7 (n.s.) |
| G look-ahead | n/a | | dSharpe -0.025, dCAGR -25bp |

**Verdicts by rule:**
1. NOT triggered: per-order cost < 10bp in both books.
2. NOT triggered: |t| < 2.
3. Champion TRIGGERED, marginally (10.3 bp/yr). Driven mostly by one event: on 09-25, $579 sat idle for 2 days. That likely came from the old settle heuristic, which the tradingroom-fixes branch replaces.
4. Missed days TRIGGERED historically: 21/99, all inside the 06-24..07-24 log-commit bug, 10 of them with real orders. 0 missing since 07-27. Dust is not triggered as written (no lot > 0.5%), but the aggregate is 1.5% across 28 lots.
5. NOT triggered: cost per $ traded < 10bp, and G < 0.05. Separately, backtest.py charges 0 cost.

**Outside the pre-registered rules (disclosed):**
- The dominant loss is TURNOVER, not fill quality.
- Challenger live recomputes `combined_weights` daily. Its backtest recomputes monthly. I re-ran the backtest with the live behavior (lag 1): 9.9x/yr turnover (live since Aug: 9.1x), CAGR 12.12% -> 11.39% at 3bp, and 11.89% -> 10.62% at 10bp. Live does not equal the tested spec.
- Champion: SHV is 40% of traded $, and HRP<->HRP_MOMENTUM flips account for 37%.

**Binding constraint:** fills cost 1-3bp each, but the books re-decide too often. The champion turns over 71x/yr, and the challenger runs 4x the turnover of its validated spec.

**Next testable structure:** C2b, pre-register a selection-hysteresis / monthly-reselect backtest for the champion. Separately, patch the challenger so its live re-decision frequency matches its backtest (monthly base, daily vol-scale). The patch is in the scratchpad and not applied.

---

## Idea queue (not yet pre-registered, in priority order)
0. Metabook contest allocator (ContestTrade mechanism, arXiv 2508.00554:
   score books on realized outcomes only, predict forward utility, allocate
   to positive-predicted-utility books). WANTS ≥60d of live 3-book history —
   spec around Sep 2026 when the shadow log has enough rows.
1. Skew/kurtosis features for the ML crash throttle (Phase 2 prerequisite)
2. Better trend sleeve: 12-1 momentum w/ vol scaling vs the failed 10-mo MA
   version (re-audition for the benched sleeve)
3. Hurst regime gate on the challenger core ramp
4. Google Trends fear index as a throttle feature (pytrends, free)
5. Put/call ratio + vol skew as throttle features
6. Numerai: seed ensembling, auxiliary targets (separate track)

---

## EXP-020 — Managed-futures / time-series-trend sleeve on the champion's equity book

**Status:** RESULT 2026-10-13 — **PASS** (holdout w=0.30; proxy gate 0.604 vs 0.60, see RESULT).
Originally **Status:** PRE-REGISTERED 2026-10-13 16:30 UTC (before any return, Sharpe or drawdown
was computed on any window). Only the AQR file's schema/date range (1985-01..2026-05)
was inspected, which printed the first four 1985 rows (in-sample, pre-base-start).
**Numbering note:** EXP-018 and EXP-019 do not exist in this ledger (019 is a director
draft only); 020 is used because the desk assigned it.
**Origin:** director draft 2026-10-13. EXP-006 died on breadth (5 ETFs, P = 0.30).
Trend is a breadth strategy; a managed-futures fund buys 50+ futures markets of breadth
we cannot build. This tests buying it instead of building it.
**Crowding read:** INSTITUTION-crowded (CTAs, ~$300bn+ managed-futures AUM, AQR/Man/
Winton), not retail-crowded → acceptable under Tyler's criterion.

### Hypothesis
Replacing w of a SPY book with a fee-haircut time-series-momentum sleeve (monthly
rebalanced) raises the book's Sharpe AND improves its crisis behaviour (max drawdown,
worst 12 months, returns in SPY's worst-decile months), out of sample.

### Why it could be real
TSMOM is long-vol-like: it shorts assets in sustained declines, and equity crises
are usually sustained (2000-02, 2008, 2022) — so its payoff is convex to slow crashes,
and its correlation to equities is ~0 unconditionally. Diversifying a ~0-correlated,
positive-mean asset into an equity book raises Sharpe mechanically IF the mean
survives fees. The open question is exactly that last clause.

### Data (free only)
- Sleeve: AQR "Time Series Momentum: Factors, Monthly", column TSMOM (all assets),
  excess returns, gross of fees. scratchpad tradingroom/exp020_dl/tsmom.xlsx.
- rf: FRED TB3MS (3m T-bill, monthly, % p.a. → /1200).
- Base: SPY monthly total return from yfinance auto-adjusted closes.
- Reported-only secondary base: 60/40 SPY / VUSTX (Vanguard long Treasury fund,
  TLT stand-in since 1986) — the champion's equity + long-bond ballast shape.
  The champion's own live curve (2026-06-23+, 58 rows) is too short to use.
- Implementability: DBMF (2019-05+), KMLM (2020-12+), CTA (2022-03+) monthly total
  return from yfinance.
- No paid data, no Anthropic API.

### Construction
- Sleeve return = TSMOM_excess + rf − h/12, h = **2.0%/yr primary haircut**
  (≈0.85–0.90% ETF expense ratio + ~1.1% replication/implementation drag).
  Raw factor, NOT rescaled (no vol estimate fitted). Haircut grid {0,1,2,3,4}%
  REPORTED only; the verdict uses 2%.
- Blend = (1−w)·SPY + w·sleeve, rebalanced monthly to target, cost 5 bp × one-way
  turnover at each rebalance (drift-based).
- Sharpe = annualised mean(blend − rf)/sd, monthly.
- Block bootstrap: circular moving block, block = 12 months, 10,000 reps, paired
  (same resampled months for blend and base), seed 20261013.

### Sample split
- **In-sample (selection):** 1993-02 .. 2009-12 (203 months; SPY start, includes
  2000-02 and 2008).
- **Holdout (sealed until in-sample verdict is written):** 2010-01 .. 2026-05
  (197 months; includes 2020 and 2022).
- **Honesty about the holdout:** it is unseen by THIS code, not by me. The published
  record (post-2012 trend weakness, strong 2022) is in my priors and the literature.
  Treat holdout P-values as softer than their nominal level.

### Variants: K = 3, pre-declared
w ∈ {0.10, 0.20, 0.30}. No other weight, no lookback grid, no vol-rescaling variant,
no sub-factor (EQ/FI/FX/CM) variant. Trend family running K (journal-era): EXP-006 spent
0; this spends 3 in-sample + 1 holdout test.
**Multiple-testing adjustment:** Bonferroni over K = 3 in-sample → one-sided α = 0.0167
per test. Exactly ONE w goes to the holdout (single test, α = 0.05).

### Decision rule (frozen)
Per w, IN-SAMPLE gates (all four):
- IS1 ΔSharpe (blend − SPY) > 0 with bootstrap P(Δ ≤ 0) < 0.0167
- IS2 crisis: mean(blend − SPY) over SPY's worst-decile months (decile of the window)
  > 0 with bootstrap P(≤ 0) < 0.0167
- IS3 MaxDD(blend) less severe than SPY's by ≥ 2.0 pts
- IS4 worst rolling-12-month return(blend) ≥ SPY's
Selection: among w passing IS1–IS4, the one with the highest in-sample ΔSharpe goes to
the holdout. None pass → FAIL at in-sample; holdout still scored ONCE descriptively
for the record (stated now, so it isn't a later choice), no verdict from it.
HOLDOUT, selected w only:
- H1 ΔSharpe ≥ 0.00 (point) AND 90% bootstrap CI lower bound ≥ −0.10 (non-inferiority;
  disclosed: a ~0.05 Sharpe delta is not statistically resolvable in 16 years)
- H2 worst-decile crisis mean > 0 with P(≤ 0) < 0.05
- H3 MaxDD less severe by ≥ 2.0 pts
- H4 worst rolling-12m ≥ SPY's
**PASS** = H1–H4. **PARTIAL** = H2 + H3 pass but H1 fails (crisis insurance bought
at a Sharpe cost — authorises nothing but a report to Tyler). **FAIL** otherwise.
Implementability (Part b) gate: monthly corr(DBMF excess, TSMOM excess) over the
overlap < 0.60 → the AQR series is not a valid proxy for what we can buy → verdict
downgraded to INCONCLUSIVE regardless of the above. Also reported: KMLM/CTA corr,
tracking error, realised annual shortfall vs the AQR index (vs the assumed 2%).
**Kill:** FAIL → no trend sleeve for the champion from the AQR-index route; idea queue
item #2 closed. PASS → a patch is WRITTEN (not applied), proposal only; deployment is a
separate decision, and it goes to the challenger's A/B process, not straight to live.

### Priors (stated before running)
In-sample pass ~65% (1993–2009 was trend's best era). Holdout PASS ~30%; PARTIAL ~35%.

### RESULT — Part 1: IN-SAMPLE (written 2026-10-13 BEFORE the holdout was unsealed)
Code: scratchpad tradingroom/exp020/run.py (`is` stage loads no holdout month into any
statistic); output is_output.txt, is_results.json. Data checks: SPY 2008-10 −16.5%,
2020-03 −12.5% (match known), no missing SPY months 1993-01..2026-05.

| w | Sharpe SPY | Sharpe blend | ΔSh | P(Δ≤0) | crisis Δ (bp/mo) | P(≤0) | MaxDD SPY → blend | worst-12m SPY → blend | IS1–4 |
|---|---|---|---|---|---|---|---|---|---|
| 0.10 | 0.333 | 0.441 | +0.108 | 0.0000 | +119 | 0.0000 | −50.8% → −45.4% (+5.4) | −43.4% → −38.5% | PASS ×4 |
| 0.20 | 0.333 | 0.573 | +0.240 | 0.0000 | +237 | 0.0000 | −50.8% → −39.5% (+11.3) | −43.4% → −33.4% | PASS ×4 |
| **0.30** | 0.333 | **0.730** | **+0.396** | 0.0000 | +356 | 0.0000 | −50.8% → −33.1% (+17.7) | −43.4% → −27.9% | PASS ×4 |

Sleeve (TSMOM + rf − 2%) in-sample: CAGR 18.3%, vol 12.0%, Sharpe 1.18, corr to SPY −0.14.
90% CI of ΔSh at w=0.30: [+0.273, +0.503]. Haircut grid (point ΔSh, w=0.30): 0% +0.453,
1% +0.425, 2% +0.396, 3% +0.368, 4% +0.340 — the in-sample result does not depend on h.
Reported-only 60/40 base, w=0.30: ΔSh +0.497, MaxDD −29.8% → −14.9%.

**In-sample verdict: all three w pass IS1–IS4. Selected for holdout by the frozen rule
(highest in-sample ΔSharpe): w = 0.30.** Prior (pass ~65%) — passed, and by a wide margin,
which is exactly what 1993–2009 should do for trend (this is trend's famous era; the
in-sample result is close to a reproduction of the literature, not a discovery). Note the
selection rule mechanically favours the largest w whenever the sleeve's standalone Sharpe
beats SPY's — so the holdout is effectively a test of "max trend weight", disclosed here.

### RESULT — Part 2: HOLDOUT (unsealed after Part 1 was written) + implementability
Output: ho_output.txt, ho_results.json, impl_output.txt, impl_sens_output.txt.

**Holdout 2010-01..2026-05, w = 0.30, h = 2% (n = 197)**

| gate | statistic | value | threshold | result |
|---|---|---|---|---|
| H1 | ΔSharpe (0.907 → 0.987) | **+0.081**, 90% CI [−0.067, +0.223] (P(Δ≤0) = 0.19) | point ≥ 0 AND CI low ≥ −0.10 | PASS |
| H2 | crisis Δ, SPY worst-decile months | **+255 bp/mo**, P(≤0) = 0.0000 | > 0, P < 0.05 | PASS |
| H3 | MaxDD SPY −23.9% → blend −14.1% | **+9.8 pts** | ≥ 2.0 | PASS |
| H4 | worst 12m SPY −18.2% → blend −6.3% | blend ≥ SPY | | PASS |

**Implementability gate:** corr(DBMF excess, TSMOM excess), 2019-06..2026-05, n = 84:
**0.604** vs the < 0.60 INCONCLUSIVE trigger → **gate passes, by 0.004.**

| ETF | overlap | corr (excess) | β to AQR | TE vs AQR | AQR total − ETF (arith/yr) | CAGR ETF / AQR |
|---|---|---|---|---|---|---|
| DBMF | 2019-06..2026-05 (84) | 0.604 | 0.51 | 11.3% | −2.95% (ETF beat it) | +9.26% / +5.80% |
| KMLM | 2021-01..2026-05 (65) | 0.662 | 0.66 | 10.8% | +3.64% | +5.02% / +8.87% |
| CTA | 2022-04..2026-05 (50) | 0.502 | 0.75 | 14.5% | −3.31% | +10.71% / +7.91% |

**VERDICT: PASS** (H1–H4 pass; implementability gate not triggered). Prior was PASS ~30%.

What the PASS does and does not say — read before acting on it:
1. **It's crisis insurance that costs return.** Holdout CAGR SPY 14.38% → blend
   **11.64% (−274 bp/yr)**. The sleeve itself earned 3.92%/yr (Sharpe 0.25) after the
   haircut in 2010–2026. Sharpe rose only because the volatility and drawdown fell more
   than the return did. H1 passed as *non-inferiority*; the Sharpe gain itself is not
   statistically resolved (P = 0.19), as the pre-registration said it wouldn't be.
2. **The haircut matters in the holdout, not in-sample.** Holdout ΔSh at w=0.30 by h:
   0% +0.139, 1% +0.110, 2% +0.081, 3% +0.051, 4% +0.022 — stays ≥ 0 across the grid
   but the margin is mostly fee-sensitivity.
3. **The proxy gate is a coin flip.** 0.604 vs 0.60. Reported-only fragility checks:
   block-bootstrap 90% CI [0.459, 0.715], P(corr < 0.60) = 0.49; leave-one-year-out
   range 0.525 (drop 2022) .. 0.651; Spearman 0.597. DBMF's β to the AQR index is only
   0.51 — it's a lagged replicator (corr with AQR one month earlier 0.22). The rule says
   PASS; the honest reading is "the AQR backtest is a loose, not a tight, description of
   what DBMF delivers." The realised-shortfall check against the assumed 2% is not
   cleanly measurable — the betas are < 1, so a raw return difference mixes scale with
   fees (DBMF beat the index; KMLM lagged it by 3.6%/yr).
4. Holdout is unseen by the code, not by me (post-2012 trend weakness, strong 2022 were
   in my priors). Treat it as softer than nominal.
Reported-only 60/40 base, holdout: ΔSh +0.036 at w=0.30 (0.892 → 0.929), CAGR 10.08% →
8.51%, MaxDD −25.7% → −11.3%. Full 1993-02..2026-05, w=0.30: ΔSh +0.246, CAGR 10.88% →
11.41%.

**Deviations / choices not spelled out in the registration (disclosed):**
- Bootstrap P-values are the uncentred fraction of resampled Δ ≤ 0. For the crisis
  statistic, the worst-decile months are re-identified inside each resample.
- SPY/VUSTX/DBMF/KMLM/CTA monthly adjusted closes came from Yahoo's chart API
  (adjclose, parsed by exp020/parse_yahoo.py), i.e. the same Yahoo adjusted series
  yfinance returns, not via the yfinance library itself.
- No cost charged on the initial purchase (1 bp-scale, both arms affected).
- KMLM's first full monthly return is 2021-01 (registration said "2020-12+"); CTA's is
  2022-04.
None of these were chosen after seeing a result.

**Binding constraint (for the PASS):** proxy validity — the AQR index the gates were
run on correlates 0.604 with the ETF we'd actually buy (threshold 0.60, β 0.51), and the
holdout economics are a −274 bp/yr CAGR trade for +9.8 pts of drawdown protection.

**Next testable structure:** (a) per the kill rule, a patch is WRITTEN, not applied:
scratchpad tradingroom/exp020/exp020_mfut_sleeve_PROPOSAL.patch adds a dormant
`mfut_sleeve` (DBMF) and `MFUT_BUDGETS_PROPOSED` (existing sleeves ×0.7 + 30% mfut) to
challenger/sleeves.py; SLEEVE_BUDGETS and ALL_TICKERS are untouched, so it changes
nothing live (`git apply --check` passes). (b) Before any A/B: EXP-022 (to pre-register)
— does the 30% TSMOM sleeve still help on the CHALLENGER's base, which already owns TLT
and GLD ballast? The 60/40 reported line (ΔSh only +0.036) suggests much of the benefit
is already captured by bond ballast, so this is a real question, not a formality. Use
the AQR series as the pre-2019 proxy and DBMF after, with the proxy-gap disclosed.
(c) Shadow book on DBMF for ≥ 60 live days to measure the actual replication gap.
Idea queue item #2 stays OPEN (route: buy breadth, not build it).

---

## EXP-021 — Does the challenger's live paper book behave like its validated backtest?

**Status:** RESULT 2026-10-13 — **INCONSISTENT (replication leg, R2 6.50% > 6.0%)**.
Originally **Status:** PRE-REGISTERED 2026-10-13 16:32 UTC, before any replay, rolling-window
distribution or percentile was computed by me. **K = 1** (one verdict; everything else
below is labelled reported-only).
**Numbering note:** 020 was taken by the managed-futures entry minutes earlier; this is 021.
**What I had already seen (disclosed):** the analyst's report (performance_2026-10-13.md):
live +1.48% (06-10 → 10-13 log equity), SPY +6.10% (close 06-09 → close 10-12),
and a frictionless replay of the LOGGED target weights of +2.1% to +3.9% depending on
trade-timing convention. I have read backtest.py, sleeves.py, main.py, risk_overlay.py
and broker.rebalance, and noticed before running anything that backtest.run_book (i)
recomputes sleeve weights only at business-month-end while live recomputes daily,
(ii) holds CONSTANT weights between trades (implicit daily rebalance) while live
positions drift, (iii) applies weights set from close(i) to the return ending at
close(i) on trade days, (iv) charges 10 bp/turnover and credits 2%/yr on SHV.
Those are hypotheses for the decomposition, not results.

### Objects
- **L (live):** challenger/daily_log.csv `equity`, 87 rows 06-10 .. 10-13 = 86 intervals,
  snapped ~09:31 ET (≈ open(t)). Total = 1014.82/1000.02 − 1 = +1.48%.
- **P (primary replay = "the strategy the backtest validated"):** backtest.run_book
  logic exactly as written, config A (SLEEVE_BUDGETS 0.45/0/0.28/0.27, TARGET_VOL 0.16,
  trailing-40d vol, TCOST 10 bp, DRIFT 2%, CASH_YIELD 2%), run over the full spliced
  history (challenger/prices_cache.parquet through 2026-06-09, then the RETURNS of
  challenger/live_prices.parquet from 2026-06-10 to 2026-10-12; Tiingo adjClose both;
  no API calls). Code copied to the scratchpad; no tracked file edited.
  Live-window P = compounded P returns dated 06-10 .. 10-12 (close 06-09 → close 10-12,
  86 returns).
- Alignment: live row t ↔ replay return dated t−1 (live interval open(t−1)→open(t)
  shares its intraday leg with close(t−2)→close(t−1)).

### Gate 1 — replication (both must hold)
- **R1** cumulative gap |L − P| over the window ≤ **150 bp**.
- **R2** weekly tracking error: non-overlapping 5-interval blocks (17 blocks, last
  partial block dropped), SD(L_block − P_block) × √52 ≤ **6.0% annualized**.
  (Weekly, not daily, because the open-vs-close snapshot makes daily TE meaningless;
  6% allows ≈ two endpoint overnight gaps per block at ~0.5% book overnight σ.)
REPLICATES iff R1 and R2.

### Gate 2 — is the live relative return unusual?
- Statistic: (P compounded return − SPY compounded return) over every rolling
  86-trading-day window whose first return is ≥ 2007-07-01 and last return ≤ 2026-06-09
  (the backtest's own pre-live history; overlapping windows, step 1 day).
- Live value: L − SPY(close 06-09 → close 10-12) = 1.48% − 6.10% ≈ −4.62 pp
  (recomputed from files, the recomputed figure is the one used).
- **UNUSUAL** iff the live value is below the **5th percentile** of that distribution
  (one-sided; overlapping windows → descriptive percentile, not a p-value).

### Verdict
**CONSISTENT** = REPLICATES and not UNUSUAL. **INCONSISTENT** otherwise, labelled by which
leg failed (replication / tail / both). If INCONSISTENT on replication: identify the
cause and draft a patch file in the scratchpad (no tracked-file edit, no commit).
Reported-only (no verdict weight): a live-faithful frictionless replay F (daily
recompute from prices through t−1, 2% drift rule vs drifted holdings, no cost, 0% cash),
a replay of the logged weights W, the gap decomposition (signal/weights,
execution/costs, timing, cash/rounding), percentile under F, daily diagnostics.

### Prior (stated before running)
R1 pass ~60% (the analyst's W already sits 0.6–2.4 pp above L). Not UNUSUAL ~85%
(−4.6 pp in 4 months for a ~13%-vol book that is ~0.45 QQQ-heavy is a ~1σ draw by eye).

### RESULT (written 2026-10-13; numbers re-verified by a fresh re-run of replay.py — output byte-identical)

**Verdict: INCONSISTENT — replication leg (R2).** R1 passed, R2 failed by 0.50 pts, Gate 2
not unusual. The bar is NOT moved; the reasons R2 failed are reported below, and they do
not change the verdict.

| gate | statistic | value | threshold | result |
|---|---|---|---|---|
| R1 | cumulative gap L − P | **−110 bp** (L +1.48%, P +2.58%) | \|·\| ≤ 150 bp | PASS |
| R2 | weekly TE, 17 non-overlapping 5-interval blocks | **6.50%** | ≤ 6.0% | **FAIL** |
| Gate 2 | live L − SPY vs rolling-86d (P − SPY), 4,680 windows 2007-10..2026-06 | **−4.62 pp → 14.9th pctile** | UNUSUAL if < 5th | not unusual |

Gate 2 distribution: 1% −13.56%, 5% −8.14%, 10% −5.82%, median −0.07%, 95% +8.96%.
Reported: P − SPY over the live window itself −3.52% (20.5th pctile); non-overlapping
windows (n=55) live below 12.7%; 2018+ windows 11.9th pctile; under F's own history 15.4th.
Sanity: P 2007-07..2026-06 CAGR 12.3%, vol 12.1%, Sharpe 0.65, MaxDD −24.4% (SPY 0.39 / −55.2%).
Priors: R1 pass (60%) — yes. Not UNUSUAL (85%) — yes. The prior didn't anticipate R2 at all.

**Decomposition ladder (reported-only; live-window compounded return, 86 returns)**

| step | change vs previous | window return | Δ |
|---|---|---|---|
| V0 P | backtest.run_book as written | +2.579% | — |
| V1 | no same-day lookahead (weights from close t act from t+1) | +2.795% | +22 bp |
| V2 | zero transaction cost | +2.912% | +12 bp |
| V3 | SHV earns SHV (not flat 2%) | +2.946% | +3 bp |
| V4 | holdings drift between trades | +2.961% | +1 bp |
| **V5** | **daily signal recompute (what live did)** | **+1.901%** | **−106 bp** |
| V6 = F | 4dp rounding / 0.5% min weight | +1.899% | −0 bp |

F reproduces the LOGGED target weights exactly (max \|Δw\| = 0.0000 on all 86 days; 30 of
31 logged trade days, the missing one is the 06-10 initial buy). So the strategy code is
faithful; the gap between "what was validated" and "what ran" is almost entirely V5:
**the backtest recomputes sleeve weights at month-end, live recomputed them every day**
(30 trades in window vs 10–11). Commit 33c8745 (already on main) changes live to a
monthly base, which removes V5 going forward.

Full-history check of V5 (extras_fixed.py, 2007-07..2026-06): monthly vs daily signal,
frictionless, CAGR 12.32% vs 11.72%, Sharpe 0.645 vs 0.624, trades/yr 19 vs 93;
daily-minus-monthly mean −59 bp/yr, **t = −0.90** (not a significant signal difference).
At 10 bp/turnover: Sharpe 0.619 vs **0.536**, CAGR 11.96% vs 10.59%. So the case for
33c8745 is turnover cost, not signal quality. The live-window daily-vs-monthly gap
(−1.06%) sits at the 15.1th pctile of its own rolling-86d distribution (5% −1.90%,
median −0.17%, 95% +1.58%) — an unlucky draw of a mildly negative, mostly cost-driven
difference.

**From F to L (the remainder of the −110 bp):**

| step | value | Δ | what it is |
|---|---|---|---|
| F (Tiingo adj. close, trade @ close t−1) | +1.899% | | |
| W_close: logged weights, same convention | +1.907% | +1 bp | F ≡ logged targets |
| W_openC: logged weights traded @ IEX open t, valued @ close 10-12, adjusted bars | +2.519% | +61 bp | open-vs-close trade timing / data source |
| same, RAW (unadjusted) bars | +1.789% | **−73 bp** | **dividends not credited** |
| C: actual Alpaca close equity 10-12 | +1.829% | +4 bp | execution (fills median 67 s after open; slippage −$0.85 on $4,336 notional) |
| L: daily_log `equity`, 10-13 ~09:31 snapshot | +1.480% | −35 bp | endpoint snapshot timing |

Sum: −68 (P→F) +1 +61 −73 +4 −35 = −110 bp. ✓

**New finding — the paper account does not appear to receive dividends.** Actual close
equity C ends within **4 bp** of a replay on RAW (no-dividend) IEX prices, and 73 bp
below the same replay on adjusted prices (ex-div events in window across IEF, TLT, SHV,
XLU, XLP, XLV, QQQ, QLD; account cash is $1.36, so no dividend cash is sitting there).
Every backtest in this repo uses adjusted (total-return) prices, so **every paper-vs-
backtest comparison is biased against paper by roughly the book's dividend yield**
(~73 bp in 4 months here ≈ 2%/yr for this bond/defensive-heavy mix). This is a paper-
broker artifact — a real account would be paid — but it contaminates every live-vs-
backtest gate, including the champion's and Gate 2 above (L excludes dividends; SPY
+6.10% includes them). Not used to adjust the verdict.
Bug disclosure: extras.py printed this as "+0.7 bp" — a units bug ((wa−wr)/10 is
percent, not bp). It is 73 bp. extras.py also crashed on an index mismatch (C starts
06-08, ladder 06-10); fixed copy is extras_fixed.py, output in extras_output.txt.

**Why R2 failed — the open-vs-close snapshot.** daily_log `equity` is taken ~09:31 ET,
i.e. ≈ open(t); the replay is close-to-close. The pre-registration budgeted ~0.5% book
overnight σ for this; the realized sd(daily L − P_lagged) is **0.96%**. Decisive check
(reported-only): weekly TE of L vs the SAME book's own close equity C is **6.06%** — the
measurement instrument alone uses the whole 6.0% budget. Measured close-aligned, the book
tracks tightly: weekly TE C vs F **1.40%**, C vs P **1.86%**; daily corr C vs F 0.967.
The pre-registered R2 design was flawed (I under-budgeted overnight variance by ~2×).
That's my error in the gate, and it stays a FAIL.

**Binding constraint:** R2 died on the measurement, not the strategy — open-snapshot
equity contributes 6.06% weekly TE by itself against a 6.0% budget, while the strategy
measured at the close tracks its replay at 1.40–1.86%.

**Pattern across deaths:** this is the second time in two days a live-vs-backtest gap
traced to a *convention mismatch* rather than the signal (C2 audit: split-unadjusted
Alpaca bars; here: daily-vs-monthly recompute, open snapshot, uncredited dividends). The
live books have never been compared to the backtest on a like-for-like basis.

**Patch (drafted, NOT applied):** scratchpad tradingroom/exp021/patch/exp021_close_equity_log.patch
— challenger/main.py logs the broker's prior-close equity (`acct.last_equity`) once per
run day to a separate challenger/close_equity.csv (daily_log.csv column layout untouched;
placed after the duplicate-run and market-open guards), and the workflow `git add`s it.
`git apply --check` passes. Needs Tyler's go-ahead; the signal-recompute fix is already
in 33c8745.

**Next testable structure (to pre-register before the data exists, not now-and-adjust):**
EXP-021b — re-run Gate 1 on the PATCHED challenger (33c8745 monthly base + close-equity
log) after ≥ 60 live trading days from the patch date (≈ early Jan 2027), comparing
close equity to a replay on RAW (no-dividend) prices with the same monthly base. Draft
thresholds: R1 \|gap\| ≤ 100 bp, R2 weekly TE ≤ 3.0%. Disclosure for that entry: these
thresholds are informed by the 1.40–1.86% close-aligned TE seen here, so 021b is a
confirmation on new data, not a fresh discovery. Separately: a one-shot audit of the
champion book for the same dividend bias (cheap; same raw-vs-adjusted replay).

---

## EXP-019 — HAR-RV vs simple trailing estimators on forecast loss (clean replication of 014)

**Status:** PRE-REGISTERED 2026-10-13 (written before any forecast or loss was computed;
the only data step run before this entry was the download + an integrity scan of max|r|
and zero-return counts, which contains no estimator output) · running
**Origin:** director audit 2026-10-13 flagged EXP-014's PASS as DISPUTED: it re-ran the
killed EXP-002 under the same spec with an undisclosed longer warm-up (250 → 527 obs,
which took COVID out of the HAR arm), and condition 3 was rewritten after 1 and 2 were
known. HAR family is therefore K=2 and unreplicated. EXP-019 asks the estimator question
directly — forecast accuracy, not a Sharpe proxy — on a window no HAR run has touched.

### Hypothesis
Part A: the frozen EXP-014 HAR-RV forecast has lower QLIKE loss than each of trailing-40d,
trailing-20d and EWMA(0.94) for next-day and next-week daily variance of the champion's
ETFs, 2008-01-01..2018-12-31.
Part B (only if A clears the incumbent gate): swapping the champion overlay's estimator
from trailing-40d to HAR improves the overlay on the same window.

### Why it could be real
Vol clustering at multiple horizons is the best-documented regularity in finance (Corsi
2009; Andersen-Bollerslev). A trailing window weights day 1 and day 40 equally and drops
day 41 to zero; HAR weights recent variance more and mean-reverts toward the monthly level.
Why it could fail here: inputs are squared daily close-to-close returns (no intraday RV),
which makes every HAR regressor noisy; EWMA 0.94 is already a recency-weighted estimator.

### Data
yfinance `Ticker.history(auto_adjust=True)`, daily, 2005-01-03..2026-10-09, fetched
2026-10-13 to scratchpad tradingroom/exp019/ohlc_yf.parquet. $0, no API keys.
Integrity scan done pre-registration: no gaps; largest |r| per ticker all on real crash
days (2008-10-13, 2020-03-16, BITO 2022-06-13, GLD 2026-01-30); no split artifacts.
Assets: champion universe (config.ASSETS) ∪ {SPY} minus SHV = SPY QQQ IWM TLT TQQQ UPRO
SOXL TECL VGT MTUM AVUV BITO VEA GLD. SHV EXCLUDED (cash stand-in; 1,343 of 4,967 days
are exactly zero return, so its "variance" is tick quantisation, not risk). AVUV and BITO
have no data in the primary window → secondary only. Primary panel = 12 assets,
unbalanced: each asset enters once its own warm-up completes.

### Method (exact)
- r_t = simple close-to-close return (pct_change, as risk_overlay uses). Variance proxy =
  r_t². Range estimators (Parkinson/GK) NOT used: they omit the overnight gap and are not
  conditionally unbiased for close-to-close variance, which Patton (2011) robustness needs.
- Forecast origin = close of day t, using r_1..r_t only. Horizons h=1 (target r²_{t+1})
  and h=5 (target mean(r²_{t+1..t+5}), per-day variance).
- Estimators (per asset):
  - **T40** sample variance (ddof=1, demeaned) of last 40 returns — the incumbent, same
    as portfolio_vol(window=40). Flat across horizons.
  - **T20** same with 20.
  - **EWMA** σ²_{t+1} = 0.94 σ²_t + 0.06 r_t², seeded with mean r² of first 22 returns,
    no demeaning (RiskMetrics). Flat across horizons.
  - **HAR** frozen from exp014_harrv.py / risk_overlay.har_forecast: regressors
    [1, r²_s, mean r²_{s-4..s}, mean r²_{s-21..s}]; OLS on the last 500 (X_s, y_s) pairs
    whose target is fully observed by t; active only when ≥ 527 returns exist
    (HAR_WINDOW+22+5, the 014 warm-up — kept so that 019 tests 014's model). h=5 uses
    the direct Corsi projection (y_s = mean r²_{s+1..s+5}); same regressors, same window.
    Non-finite or ≤ 0 forecast → replaced by T40 (production fallback); count reported.
- All four evaluated on the identical asset-dates (HAR active). Asset-days with r_{t+1}=0
  dropped at h=1 (normalised QLIKE undefined); count reported.
- Losses: QLIKE L = y/f − ln(y/f) − 1 (Patton normalisation, ≥ 0); MSE L = (y − f)²,
  divided per asset by (mean y in window)² so 3x ETFs don't dominate.
- Panel: per evaluation date, equal-weight mean loss across available assets.
  d_t = L_comp − L_HAR (positive = HAR better).
- DM: t = mean(d)/sqrt(NW-Bartlett long-run var / T), NW lag 22 for both horizons
  (≥ h−1 = 4 required for h=5), normal reference, one-sided (HAR better).
- Loss ratio = mean L_HAR / mean L_comp, 95% CI by moving-block bootstrap on dates
  (block 22, 2,000 reps, seed 19).
- Windows: PRIMARY targets dated 2008-01-01..2018-12-31 (verdict). SECONDARY
  2019-01-01..2026-10-09 (reported only — contaminated by 002/014).

### K and multiple testing
Part A family = 3 comparators × 2 horizons × 2 losses = **12 DM tests**, Holm-adjusted at
family α = 0.05. Per-asset DMs, secondary window, yearly splits: descriptive, no K.
Part B = 1 gated comparison (HAR vs T40). T20/EWMA overlay rows reported, authorise nothing.
HAR family K after this = 002 (1) + 014 (1) + 019A (1 hypothesis, 12 Holm'd tests) +
019B (1) = 4.

### Decision rule — Part A (all on PRIMARY)
- **C1** QLIKE: HAR beats T40, T20 and EWMA at h=1 and h=5 — all 6 Holm-adjusted p < 0.05.
- **C2** MSE guard: in none of the 6 MSE comparisons is HAR worse at one-sided p < 0.05
  (unadjusted — strict).
- **C3** stability: panel QLIKE(h=1) HAR < T40 in ≥ 7 of 11 calendar years 2008–2018.
- **C4** breadth: per-asset QLIKE(h=1) HAR < T40 in ≥ 9 of 12 assets.
- **FULL PASS** = C1–C4. **INCUMBENT PASS** = C1 holds for the two T40 tests only, plus
  C2–C4 → "beats the overlay's estimator, not the best simple one". **FAIL** otherwise.
- **UNSTABLE** overrides a pass if SECONDARY mean d (QLIKE, h=1, vs T40) < 0.
- Relation to 014: FULL/INCUMBENT PASS (not unstable) → "014's direction replicated
  on forecast loss"; FAIL or UNSTABLE → 014 relabelled UNREPLICATED.

### Decision rule — Part B (runs only on FULL or INCUMBENT PASS)
perf_report.simulate_deployed logic copied to scratchpad, estimator the only switch, on
yfinance closes 2008-01-02..2018-12-31 (assets join as they list, per the sim's own
filter). Turnover = Σ_assets |s_t w_t − s_{t−1} w_{t−1}|, annualised. Sharpe reported
gross and net of 5 bp × turnover.
- **GAIN** = turnover ≤ 1.25× T40 AND [(ΔSharpe_net ≥ +0.03 AND MaxDD not worse by > 1 pt)
  OR (MaxDD better by ≥ 2 pts AND ΔSharpe_net ≥ −0.02)].
- **NON-INFERIOR** = ΔSharpe_net ≥ −0.02, MaxDD not worse by > 1 pt, turnover ≤ 1.25×.
- **WORSE** otherwise. Patch drafted (scratchpad, not applied) only on GAIN.
- Disclosed: a 0.03 Sharpe delta over 11 years is not statistically resolvable; Part B is a
  sanity/non-inferiority check, the evidence is Part A.

### Differences from EXP-014's spec, and why
1. Metric: forecast loss + DM, not Sharpe/MaxDD/condition-3. 014's question was answered
   through a book Sharpe that mixes estimator accuracy with what the overlay does with it.
2. Window: 2008–2018 primary, untouched by 002/014; 014's 2019–2026 demoted to secondary.
3. Warm-up stated, not discovered: 527 obs (014's), named here and kept identical for
   every asset. 002's 250 is not re-tested.
4. Comparators: T20 and EWMA added — "beats a 40d window" is a low bar.
5. Data: yfinance auto-adjusted instead of Tiingo (Tiingo key not used; free source asked).
6. No subjective/episode condition. Every gate is a number computed by code.
7. Multiple-testing correction (Holm over 12) — 014 had none.

### Prior (stated before running)
C1 vs T40/T20 ~70% (trailing boxcars are weak at h=1). C1 vs EWMA at h=1 ~40% with
daily-return inputs — the most likely failure point. FULL PASS ~30%; INCUMBENT PASS ~55%.

### RESULT — run 2026-10-13 · **FAIL** (Part A). Part B not run (gate). EXP-014 → UNREPLICATED.

Ran exactly as registered (scratchpad tradingroom/exp019/partA.py). PRIMARY 2008–2018,
2,769 panel dates, 12 assets. QLIKE ratio = L_HAR / L_comp (<1 = HAR better), 95% block-bootstrap CI.

| h | loss | vs | ratio [95% CI] | DM | p one-sided | p Holm(12) |
|---|---|---|---|---|---|---|
| 1 | QLIKE | T40 | 0.976 [0.951, 0.997] | 1.98 | 0.024 | 0.240 |
| 1 | QLIKE | T20 | 0.966 [0.940, 0.988] | 2.79 | 0.003 | 0.029 |
| 1 | QLIKE | EWMA | 1.008 [0.992, 1.024] | −1.00 | 0.84 | 1 |
| 5 | QLIKE | T40 | 0.908 [0.830, 0.988] | 1.89 | 0.029 | 0.262 |
| 5 | QLIKE | T20 | 0.866 [0.795, 0.943] | 2.88 | 0.002 | 0.024 |
| 5 | QLIKE | EWMA | 1.012 [0.948, 1.075] | −0.35 | 0.64 | 1 |
| 1 | MSE | T40/T20/EWMA | 1.05 / 1.06 / 1.09 | −0.75/−0.96/−1.31 | — | 1 |
| 5 | MSE | T40/T20/EWMA | 1.39 / 1.46 / 1.61 (CIs to 2.3–2.6) | −0.87/−0.96/−1.11 | — | 1 |

- C1 FAIL — only the 2 T20 tests clear Holm. vs incumbent T40 raw p 0.024/0.029 → Holm 0.24/0.26
  (INCUMBENT PASS also fails). vs EWMA HAR is WORSE on point estimate at both horizons.
- C2 PASS (no MSE comparison significantly worse; smallest p_worse 0.095 vs EWMA h=1).
- C3 PASS, exactly at the bar: 7/11 years (lost 2009, 2013, 2015, 2017).
- C4 PASS: 11/12 assets (TLT the exception).
- Secondary 2019–2026 (reported only): h=1 vs T40 ratio 0.979, DM 0.84; h=5 vs T40 0.844, DM 2.13;
  vs EWMA h=1 1.023 (EWMA better again). Not unstable — same sign, just not significant.
- Panel mean QLIKE h=1 primary: EWMA 1.502 < HAR 1.514 < T40 1.551 < T20 1.567. EWMA is the best
  of the four on QLIKE h=1 and on MSE at both horizons, in both windows. (Descriptive — EWMA vs T40
  was NOT a registered hypothesis and is not claimed here.)
- Diagnostics: zero-return drops 8–41/asset; HAR ≤0 fallbacks 0–12/asset.

**BUG FOUND (production + EXP-014):** risk_overlay.har_forecast and exp014_harrv.har_scaler drop the
unlabeled last row and then forecast from X.iloc[-1] — i.e. from day t−1 regressors, not day t.
Verified on SPY at 4 dates (production equals the X_{t−1} forecast to machine precision). EXP-019
tested the correctly-timed HAR, as registered. Reported-only diagnostic of the stale version
(primary, QLIKE h=1): ratio vs T40 0.989 (DM 0.90), vs EWMA 1.021 (DM −1.78), vs correct HAR 1.013.
So the model EXP-014 passed is the worse of the two HARs, and it has no detectable forecast edge
over the incumbent. EXP-014 Sharpe/MaxDD gains were not driven by forecast accuracy.

**Binding constraint:** HAR built from squared DAILY returns buys only a 2.4% QLIKE gain over T40
(p_Holm 0.24) and loses 0.8% to EWMA(0.94), a zero-parameter recency weight. The edge HAR is known
for comes from intraday RV inputs; with r² inputs the three regressors are mostly noise and the
OLS fit is dominated by outliers (h=5 MSE ratio 1.39–1.61).
**Structures this does not bind:** (1) EWMA(0.94) vs T40 as the overlay estimator — needs its own
pre-registration on data no one has looked at (pre-2005 index history e.g. ^GSPC/^IXIC/^RUT
1990–2004, plus a forward shadow log) and its own overlay non-inferiority test; it is faster than
T40, and EXP-002 showed faster ≠ better Sharpe. (2) HAR on true intraday RV (Alpaca IEX minute
bars, free, 2016+) — HAR in its home setting.
**K:** HAR family now 4 (002, 014, 019A; 019B unspent). OVERLAY_VOL_MODEL stays "trailing".
The production HAR timing bug should be fixed or the "har" option removed before anyone flips it.


---

## EXP-022 — EWMA(0.94) vs trailing-40d as the champion overlay's vol estimator (1990–2004 holdout)

**Status:** PRE-REGISTERED 2026-10-13 (written before any forecast, loss or simulation was
computed. Data steps run before this entry: yfinance download of closes/yields 1987–2004 and an
integrity scan — row counts, zero-return counts, max |r| and its date. No estimator output.)
· run 2026-10-13 · **FAIL** (A PASS, B WORSE — see RESULT)
**Origin:** EXP-019 found EWMA(0.94) had the lowest QLIKE(h=1) and MSE of four estimators on
2008–2026 ETF data — descriptive only, not a registered claim. Production overlay uses T40
(OVERLAY_VOL_MODEL "trailing"). This tests the switch on data no prior run touched.

### Hypothesis
Part A: EWMA(0.94) has lower QLIKE loss than trailing-40d sample variance for next-day and
next-week daily variance of US index-level assets, targets dated 1990-01-02..2004-12-31.
Part B (only if A passes): swapping the champion overlay's portfolio-vol estimator from T40 to
EWMA(0.94) is at least non-inferior on net Sharpe / MaxDD / turnover in a proxy-universe
replay of perf_report.simulate_deployed over the same window.

### Why it could be real
Vol clusters and decays; a boxcar weights day 1 and day 40 equally and drops day 41 to zero,
so it reacts late and then "ghosts" (a shock leaves the window 40 days later, causing a step).
EWMA reacts with half-life ~11 days and never ghosts. RiskMetrics (1996) chose 0.94 on exactly
this kind of daily data. Why it could fail: faster = more noise into the scaler (EXP-002:
faster ≠ better Sharpe); EWMA is not demeaned; 1990–2004 includes a calm 1993–1996 where a
40d boxcar may be just as good.

### Data (all yfinance auto_adjust=True, $0, no keys; scratchpad tradingroom/exp022/)
close_yf.parquet: ^GSPC ^IXIC ^RUT ^NDX ^SOX(1994-05+) VUSTX VWIGX VGPMX ^IRX ^DJI, 1987–2004.
yields_yf.parquet: ^TYX ^TNX.
Integrity scan findings (pre-registration): equity indices clean (0–7 zero returns, max |r|
on real days: 1997-10-27, 2000-04-14, 2001-01-03). **VUSTX REJECTED**: unadjusted distribution
artifacts (−5.7% on 1992-12-11, +6.8% on 1992-12-31) and price quantisation (338 zero-return
days). Long bond is instead **BOND30** = synthetic 30y par bond from ^TYX: r_t = exact reprice
of a 30y semiannual par bond with coupon y_{t−1} at yield y_t, minus 1, plus y_{t−1}/252
carry (^TYX ffilled onto the equity calendar; 171 zero Δy days disclosed). VWIGX/VGPMX
(fund NAVs, 184/172 zero days, quantised) used in Part B only, not in Part A.

### Method — Part A (frozen; code = exp019/partA.py estimators, T40 and EWMA only)
- Assets (PRIMARY panel, 5): ^GSPC ^IXIC ^RUT ^SOX BOND30. ^SOX joins when its warm-up
  completes (unbalanced panel, as 019).
- r_t simple close-to-close; variance proxy r_t². Origin = close of t, info r_1..r_t.
- T40 = sample var (ddof=1, demeaned) of last 40 returns. EWMA s_{t+1} = 0.94 s_t + 0.06 r_t²,
  seeded with mean r² of first 22 returns (exactly 019's code). Both flat across horizons.
- Warm-up: an asset's forecast enters only once it has ≥ 250 returns (seed weight 0.94^228 ≈ 0).
  Data begins 1987/1994 so all non-SOX assets are warm by 1990-01-02.
- h=1 target r²_{t+1}; h=5 target mean r²_{t+1..t+5}. h=1 asset-days with r_{t+1}=0 dropped.
- QLIKE L = y/f − ln(y/f) − 1; MSE = (y−f)² / (asset's mean y in window)².
- Panel: equal-weight mean loss across available assets per date; d_t = L_T40 − L_EWMA
  (positive = EWMA better). DM with NW-Bartlett lag 22, normal, one-sided. Ratio
  L_EWMA/L_T40 with moving-block bootstrap CI (block 22, 2,000 reps, seed 22).
- Window: targets 1990-01-02..2004-12-31 (15 calendar years). Reported-only secondary:
  2005–2026 ETF panel from 019 (contaminated — 019 already showed EWMA < T40 there).

### Decision rule — Part A
- **A1** QLIKE: EWMA beats T40 at h=1 AND h=5, Holm-adjusted (m=2) one-sided p < 0.05 each.
- **A2** MSE guard: neither MSE comparison (h=1, h=5) has EWMA worse at one-sided p < 0.05.
- **A3** stability: panel QLIKE(h=1) EWMA < T40 in ≥ 10 of 15 calendar years.
- **A4** breadth: per-asset QLIKE(h=1) EWMA < T40 in ≥ 4 of 5 assets.
- **PASS** = A1–A4. Otherwise FAIL; Part B then not gated (run only as labelled diagnostics).

### Method — Part B (proxy-universe replay; estimator is the ONLY switch)
perf_report.simulate_deployed copied verbatim to scratchpad (regime detector, select_strategy,
optimizer, monthly BME rebalance, 30% circuit breaker, constant RF_DAILY on the de-risked slice).
Proxy universe mapped onto the champion's tickers so the optimizer's ticker rules apply:
SPY←^GSPC, QQQ←^NDX, IWM←^RUT, TLT←BOND30, VEA←VWIGX, SHV←cash (^IRX_{t−1}/100/252, ffill),
TQQQ←3×^NDX−2×cash−0.95%/yr, UPRO←3×^GSPC−2×cash−0.91%/yr, SOXL←3×^SOX−2×cash−0.95%/yr
(from 1994-05). No proxy: TECL VGT MTUM AVUV BITO GLD (VGPMX is miners, not gold — excluded).
Price indices exclude dividends (same in both arms; disclosed).
Sim runs 1989-01-03..2004-12-31; metrics on 1990-01-02..2004-12-31.
- Arm T40: vol_target_scaler(..., window=40, model="trailing") — production.
- Arm EWMA: portfolio returns p_s = Σ w_i r_{i,s} (weights normalised to sum 1, NaN→0) over
  the last 250 rows of returns.iloc[:i]; s seeded with mean p² of the first 22, recursed
  through the last row; vol = sqrt(252·s). Fewer than 60 rows → falls back to T40.
  scaler = clip(0.20 / vol, 0, 1) — unchanged.
- Turnover = Σ_assets |s_t w_t − s_{t−1} w_{t−1}|, annualised. Sharpe gross and net of
  5 bp × turnover (daily). Also reported (descriptive): realised-vol targeting error =
  RMSE of rolling-63d realised annualised vol of the book vs the 20% target, and % of days
  the book's next-21d realised vol exceeded 25%.
- **GAIN** = turnover ≤ 1.25× T40 AND [(ΔSharpe_net ≥ +0.03 AND MaxDD not worse by > 1 pt)
  OR (MaxDD better by ≥ 2 pts AND ΔSharpe_net ≥ −0.02)].
- **NON-INFERIOR** = ΔSharpe_net ≥ −0.02, MaxDD not worse by > 1 pt, turnover ≤ 1.25×.
- **WORSE** otherwise.
- Reported only (contaminated): same two arms on 019's real ETF closes 2008–2018 and 2019–2026.

### Overall verdict
- A PASS + B GAIN → **PASS (switch)**: patch drafted in scratchpad, not applied.
- A PASS + B NON-INFERIOR → **PASS (non-inferior)**: patch drafted; recommendation is a
  forward shadow log of the EWMA scaler alongside T40 before any flip (better forecast, same
  book — the case for switching is risk-measurement accuracy, not return).
- A FAIL, or B WORSE → **FAIL**, no patch.
Either way deploy is Tyler's call; the champion is not changed by this experiment.

### K
New family (overlay estimator: EWMA). Part A = 1 hypothesis (2 Holm'd QLIKE tests, 2 MSE
guards). Part B = 1 comparison. EWMA family K = 2 after this. Overlay-estimator meta-family
(002, 014, 019, 022) = 6. Any other λ (0.97, 0.90...) would be a new K — none is authorised.

### Prior (stated before running)
A1 h=1 ~75% (019: EWMA 3.2% below T40 on QLIKE h=1); A1 h=5 ~55% (flat forecast, decay
matters less at 5d). A3 ~60%. Part A PASS ~40%. Given A, Part B NON-INFERIOR-or-better ~55%
(EXP-002 precedent: the faster estimator cost Sharpe). PASS overall ~25%.

### RESULT — run 2026-10-13 · Part A **PASS** · Part B **WORSE** · EXP-022 **FAIL** (no patch)

Ran exactly as registered (scratchpad tradingroom/exp022/partA.py, partB.py, outputs *_output.txt).

**Part A (1990–2004, 5 assets, 3,784 panel dates) — PASS on all four gates.**

| h | loss | ratio EWMA/T40 [95% CI] | DM | p Holm(2) |
|---|---|---|---|---|
| 1 | QLIKE | 0.981 [0.972, 0.990] | 4.00 | 0.0001 |
| 5 | QLIKE | 0.923 [0.895, 0.961] | 3.92 | 0.0001 |
| 1 | MSE | 0.966 [0.951, 0.979] | 4.11 | (guard: EWMA better) |
| 5 | MSE | 0.895 [0.848, 0.937] | 4.02 | (guard: EWMA better) |

A1 pass; A2 pass; A3 11/15 years (lost 1991, 1999, 2003, 2004); A4 5/5 assets (^RUT DM 4.40,
^IXIC 3.98, ^GSPC 2.79, BOND30 0.88, ^SOX 0.63). Reported-only, same code on 019's ETF panel:
2008–18 QLIKE h1 0.968 (DM 4.2), h5 0.895; 2019–26 h1 0.957 (DM 3.4), h5 0.864. EWMA(0.94) is a
better variance forecaster than T40 in every window and at both horizons. That claim now stands
on untouched data.

**Part B (proxy-universe replay 1990–2004) — WORSE.** Arm T40 reproduces
perf_report.simulate_deployed to 2e-16 (checked on 1989–1993).

| arm | Sharpe gross | Sharpe net | CAGR net | MaxDD net | vol | turnover/yr | 63d vol-track RMSE | days fwd-21d vol > 25% |
|---|---|---|---|---|---|---|---|---|
| T40 | 0.560 | 0.526 | 12.07% | −22.13% | 15.3% | 10.2× | 7.85 pts | 5.2% |
| EWMA | 0.533 | 0.497 | 11.53% | −20.87% | 15.2% | 10.9× | 7.74 pts | 3.9% |

ΔSharpe_net −0.029 (bar −0.02) → fails NON-INFERIOR; MaxDD +1.26 pts better (not ≥ 2 for the
drawdown route); turnover 1.06×. Reported-only ETF windows: 2008–18 ΔSharpe_net +0.014 (NON-INFERIOR),
2019–26 −0.036 (WORSE). Across all three windows: ΔSharpe_net −0.029 / +0.014 / −0.036, every
one inside the ±0.03 the spec said is not statistically resolvable; EWMA's MaxDD better in 2/3;
vol tracking and >25%-vol days better in 3/3.

**Verdict: FAIL. OVERLAY_VOL_MODEL stays "trailing". No patch drafted** (the pre-registered
patch condition was A PASS + B ≥ NON-INFERIOR). No other λ was run.

**Binding constraint (one line):** the better forecaster (QLIKE −1.9%, −7.7%; p 1e-4) did not buy
book Sharpe (−0.029 net) — forecast accuracy and overlay Sharpe are close to decoupled in a
capped-at-1, daily-rescaled vol target.
**Pattern across the estimator deaths (checked against the ledger, not memory):** 002 HAR (faster)
→ Sharpe −0.03, MaxDD better; 014 stale HAR → Sharpe +0.03 (now UNREPLICATED); 019 HAR → no
forecast edge; 022 EWMA (faster, better forecast) → Sharpe −0.03, MaxDD better, tail-vol days
fewer. Both overlay replays of a faster estimator (002, 022) improved the risk side and cost ~0.03 Sharpe; 014 is the only Sharpe gain and it did not replicate. That is
one finding: estimator choice moves the overlay's *risk* numbers, and the overlay's Sharpe is not
an instrument that can see a 2–8% forecast improvement.
**Structures this does not bind:** (1) use the accuracy where accuracy *is* the objective — a
risk *limit* rather than a return driver: e.g. the realised-vol leg of VolBot's VRP sizing or the
challenger's vol-target, scored on a pre-registered risk objective (vol-breach rate / CVaR), on
data no one has used (^GSPC 1950–1989 is still untouched). The objective must be chosen in that
pre-registration — re-scoring 022 on tracking error after the Sharpe gate failed would be exactly
the amended-condition move CLAUDE.md forbids. (2) The overlay's 10×/yr turnover is driven by
daily rescaling under either estimator (gross→net costs ~0.03 Sharpe for both); a no-trade band
on the scaler is an estimator-independent structure. (3) HAR on true intraday RV → EXP-023.
**K:** EWMA family 2 SPENT (022A, 022B). Overlay-estimator meta-family (002, 014, 019, 022) = 6.

### EXP-022 audit note (added 2026-10-13 after an in-progress auditor review)
1. **Pre-registration location and timing.** The spec above (from "## EXP-022" through
   "### Prior") was drafted in scratchpad exp022/prereg.md (file mtime 22:38:32 PDT) and appended
   to this ledger at 22:38:36 PDT (shell `date` printed in the same command). The first estimator
   output (partA_output.txt) is 22:39:10; Part B output 22:40:27. So the spec was in this file
   before any result existed; nothing in it was edited afterwards except the Status line
   ("· running" → "· run · FAIL"). The auditor appears to have looked before the append landed.
2. **Code edits around the run (all pre-result, none touched logic or parameters).**
   - `data.py` → `x22data.py` (22:39:05): the first `python3 -I partA.py` failed with
     ImportError before computing anything (`-I` drops the script dir; a bare `data` would also
     shadow the project's data.py). partA.py's only edit was its import line
     (`from data import load` → `from x22data import load`).
   - partB.py first run crashed in `stats()` (`D.eq` resolved to DataFrame.eq, a method) after
     both sims finished but before any metric was computed or printed; fixed to `D["eq"]`,
     `D["to"]`, `D["s"]` and re-run. No other change.
   - Spurious Accelerate BLAS matmul RuntimeWarnings (same ones risk_overlay.py documents) appear
     in partA_output.txt; all reported statistics are finite.
3. **Part B is a SYNTHETIC PROXY UNIVERSE, not the champion's assets.** SPY/QQQ/IWM are price
   indices (no dividends); TQQQ/UPRO/SOXL are constructed 3× daily returns minus 2× T-bill minus
   fee (no tracking error, no path frictions beyond that); TLT is a synthetic 30y par bond priced
   from ^TYX; VEA is a mutual-fund NAV (VWIGX); SHV is T-bill accrual from ^IRX; TECL VGT MTUM
   AVUV BITO GLD are absent. Part B therefore tests the estimator inside the champion's logic on
   a book shaped like the champion's, not the champion's own history; the two ETF windows are the
   only real-asset rows and are contaminated (reported only).
4. **No patch.** EXP-022 FAILED, so per the spec no patch was drafted. If a future experiment
   passes, the change must target the champion only: challenger/main.py and challenger/backtest.py
   inherit config.OVERLAY_VOL_MODEL, so a patch should add a champion-specific setting (or pass
   `model=` explicitly from main.py) rather than flip the shared config value.


---

## EXP-023 — HAR on true intraday realized variance (HAR in its home setting)

**Status:** PRE-REGISTERED 2026-10-13 (spec only — NOT run. No minute bars downloaded beyond a
coverage probe: bar COUNTS for SPY/TQQQ/TLT on 6 dates, no prices inspected, no RV computed.)
**Origin:** EXP-019's binding constraint — HAR on squared DAILY returns has no forecast edge
(QLIKE 0.976 vs T40, p_Holm 0.24; loses to EWMA). HAR's documented edge (Corsi 2009; ABDL 2003)
comes from intraday RV inputs, which no run here has used. EXP-022 then established EWMA(0.94)
on daily r² as the best simple forecaster (QLIKE beats T40 on 1990–2004 and both ETF windows),
so the bar HAR must now clear is EWMA, not T40.

### Data availability (probe, 2026-10-13, scratchpad tradingroom/exp023/probe.py)
Alpaca market data, read-only, paper key names ALPACA_API_KEY/ALPACA_SECRET_KEY (values never
printed). 1-min bars, 13:30–20:00 UTC:
- feed=IEX: EMPTY on 2015-06-01, 2016-01-04, 2018-02-05, 2020-03-16; sparse on 2024-06-03
  (SPY 330/391 bars, TQQQ 244). **IEX is unusable for RV** — sparse prints bias RV down.
- feed=SIP (historical > 15 min old, free tier): 2016-01-04 SPY 391 / TLT 353 / TQQQ 371;
  2020-03-16 377 each (correct — 15-min market-wide halt); 2024+ 391. 2015: empty.
→ Source = **Alpaca SIP 1-min bars, adjustment=all, 2016-01-04..2026-10-09**. $0.

### Hypothesis
A HAR model fit on 5-minute realized variance (plus overnight return²) forecasts next-day and
next-week close-to-close variance of the champion's ETFs with lower QLIKE loss than (i) T40,
(ii) EWMA(0.94) on daily r², and (iii) EWMA(0.94) on the same intraday RV series.

### Method (frozen)
- Assets: SPY QQQ IWM TLT TQQQ UPRO SOXL TECL VGT MTUM VEA GLD (12; AVUV, BITO secondary only;
  SHV excluded as in 019).
- RV_t = Σ (5-min log returns, 09:30–16:00 ET, last 1-min close in each 5-min bucket, missing
  minutes forward-filled within session) + (ln open_t − ln close_{t−1})². This is the
  close-to-close variance proxy and the TARGET for every estimator (Patton 2011: RV is a far less
  noisy conditionally-unbiased proxy than r²). Days with < 300 of 390 1-min bars flagged and
  counted; kept (half-days included as they come).
- Estimators at origin = close of t:
  - **HAR-RV**: RV_{t+1} = b0 + bd RV_t + bw mean(RV_{t−4..t}) + bm mean(RV_{t−21..t}), OLS on
    the last 500 pairs whose target is observed by t, forecast from DAY-t regressors (the 019
    timing bug is the reason this line exists). h=5: direct projection on mean RV_{t+1..t+5}.
    Forecast ≤ 0 or non-finite → EWMA-RV; count reported.
  - **T40**: sample variance of last 40 daily close-to-close returns (incumbent).
  - **EWMA-r²**: 0.94 recursion on daily r² (EXP-022's estimator).
  - **EWMA-RV**: 0.94 recursion on RV_t (input-matched control: isolates model from data).
- Losses QLIKE (primary) and MSE normalised per asset by (mean target)² (guard), panel = equal
  weight per date, DM NW lag 22 one-sided, block bootstrap CI (22, 2,000, seed 23).
- Windows: training/warm-up 2016-01-04..2017-12-29 (≈500 days; HAR needs 500 pairs + 22).
  PRIMARY targets 2018-01-02..2026-10-09. Disclosed contamination: 019/022 already scored
  T40 and EWMA-r² against r² on 2019–2026; no run has touched intraday RV or this target.

### K and multiple testing
Part A family = 3 comparators × 2 horizons on QLIKE = **6 DM tests, Holm at 0.05**. MSE = guard.
HAR family K after this = 5 (002, 014, 019A, 023A, 023B).

### Decision rule — Part A
- **C1** HAR beats T40, EWMA-r² and EWMA-RV at h=1 and h=5 — all 6 Holm p < 0.05.
- **C2** no MSE comparison has HAR worse at one-sided p < 0.05.
- **C3** panel QLIKE(h=1) HAR < EWMA-r² in ≥ 6 of 9 calendar years 2018–2026.
- **C4** per-asset QLIKE(h=1) HAR < EWMA-r² in ≥ 9 of 12 assets.
- **FULL PASS** = C1–C4. **DATA PASS** = C1 holds vs T40 and EWMA-r² (4 tests) but not vs EWMA-RV,
  plus C2–C4 → "the gain is the intraday data, not the HAR model" — the deployable candidate is
  then EWMA-RV (simpler), and Part B runs with EWMA-RV instead of HAR. **FAIL** otherwise.

### Decision rule — Part B (only on FULL or DATA PASS)
Overlay replay (perf_report.simulate_deployed copy, estimator the only switch) on real closes
2018-01-02..2026-10-09; portfolio RV built from asset 5-min returns with the day's weights.
Arms: T40 (production), EWMA-r² (022), winner of Part A.
- Pre-declared objectives (EXP-022 showed Sharpe alone cannot see a forecast improvement; this
  is declared HERE, before any 023 data, not retro-fitted to 022):
  - **R1 risk**: share of days with next-21d realised book vol > 25% reduced by ≥ 20% vs T40.
  - **R2 Sharpe non-inferiority**: ΔSharpe_net (5 bp × turnover) ≥ −0.02 vs T40, MaxDD not worse
    by > 1 pt, turnover ≤ 1.25×.
- **PASS** = R1 AND R2 → patch drafted (scratchpad, not applied) + 60-trading-day forward
  shadow log before any flip. Otherwise FAIL.
- Operational gate, also binding: the live bot would need ~22 days of minute bars each morning
  from Alpaca SIP (allowed > 15 min old); a fetch failure must fall back to T40. If the daily
  fetch is not reliable in a 20-day dry run, PASS is downgraded to SHADOW-ONLY.

### Prior (stated before running)
C1 vs T40 and EWMA-r² ~70% (RV inputs are where HAR's literature edge lives). C1 vs EWMA-RV ~35%
(EWMA on RV is a strong, often-unbeaten benchmark). FULL PASS ~25%, DATA PASS ~35%. R1 given A
~50%; R2 ~50% (022 precedent).

---

## EXP-024 — Champion re-decision cadence: monthly reselect, hysteresis, 3x cap

**Status:** PRE-REGISTERED 2026-10-13. Written before any EXP-024 simulation, metric or
backtest output existed. The only data read beforehand: `daily_log.csv` and `regime_log.csv`
(live rows 2026-07-27..10-13), the desk report, C2, the audit, and code at 33c8745 / d6a6f81.
Measurement plus strategy test. K = 3.

**Full build spec:** `research/exp024_spec.md`. It is binding. If the spec and this entry
disagree, this entry wins, and the disagreement is reported.

**Origin:** C2 found the champion turns over 71–93×/yr; HRP↔HRP_MOMENTUM flips account for
37% of traded $. The desk found that the book alternates between a ~16% TQQQ book and a ~20%
VGT book almost daily. It also found that on 2026-06-05 the book held ~96% in 3x ETFs and
lost 19.0% in a day. Audit #5 says the champion's selection logic was never pre-registered.
C2's "next testable structure" was C2b; this is C2b.

### Observation that shaped the design (from the live log, before any backtest)
From 2026-10-01 to 10-13, the label was HRP_MOMENTUM / RISK_ON on every row. Holdings still
flipped TQQQ ↔ VGT four times (10-06, 10-08, 10-12, 10-13). So **a label-only hysteresis
cannot fix the current churn.** Part of it is inside HRP_MOMENTUM (the 63-day
absolute-momentum hurdle and top-3/bottom-3 rank; mechanism not verified). The label flips
(08-20, 09-23, 09-25, 09-28) are a second source. So every variant below acts on the *target*,
not only on the label.

Side note: the 0.75 ↔ 0.06 `expected_return` swing was partly a logging bug. The HRP stats
were misaligned, which the dev branch fixes; the fix changes no weights. The holdings flip is
real; the "10× forecast swing" number is not.

### Hypothesis
Re-deciding the champion's selection and optimization less often cuts turnover by at least
half, with net Sharpe non-inferior and drawdown/tail no worse. A hard cap on total 3x-ETF
weight additionally shrinks the tail.

Mechanism: a 60-day Sharpe score, majority-vote regime labels near their thresholds, and
63-day momentum ranks are all noisy daily. Re-deciding on noise pays the spread for nothing.
The 3x sleeve is where a −2.6% SPY day becomes a −19% book day.

Why it could fail:
- slower re-decision is late into crashes (RISK_OFF arrives up to a month late in V1/V3);
- the daily overlay rescale, which none of these touch, may dominate turnover;
- at 3–5 bp the cost saved (≈2–4%/yr gross at 70–90×) may be smaller than the timing value
  of daily momentum, if that value exists.

### Variants (K = 3, all parameters fixed; baseline = Arm 0 AS-LIVE, the daily `main.py` replica)

| Variant | What it does |
|---|---|
| **V1 MONTHLY** | Regime, select_strategy and optimize run only on the first session after each business month-end. The base weights are held in between. The vol-overlay scaler, risk checks and 2% drift gate still run daily, exactly as live. |
| **V2 HYSTERESIS** | Daily. (a) The regime and strategy labels switch only after 5 consecutive days of the same new label; a switch *to* RISK_OFF is immediate. (b) The base target is the mean of the last 10 daily base targets. Overlay, risk and drift as live. |
| **V3 MONTHLY + CAP30** | V1, plus Σ(TQQQ, UPRO, SOXL, TECL) ≤ 30% of the final target. Excess goes to SHV, applied after the overlay. |

Reference arm R (`perf_report.simulate_deployed`, monthly, zero-cost legacy sim) is reported
only, never gated.

**Engine:** the FIXED code on branch `worktree-agent-a755d2182dda758ab` (d6a6f81). That code
has no same-day look-ahead, a breaker that blocks rebalancing instead of deleting losing days,
no bfill, and aligned HRP stats.
- Decisions use data through close t and earn returns from t+1.
- SHV is held as a real asset (not a constant RF).
- The live lookback is about 235 rows.

### Data and windows (Tiingo adjClose, 14 ASSETS + SPY, ffill only)

| Window | Role | Metrics period | Notes |
|---|---|---|---|
| **D** | Primary gate | 2020-01-02 → 2026-10-09 | The sim uses only ≥ 2019-01-02 data; 2019 is warm-up. In-sample for the champion's regime map; new for every variant. |
| **H** | Sealed holdout | 2011-04-01 → 2018-12-31 | The sim uses only ≤ 2018-12-31 data. No champion code has ever been run pre-2019 in this repo. No AVUV/BITO; MTUM from 2014. The D runner refuses to load pre-2019 prices. |

H is opened **once**, for all arms, and only if at least one variant passes every D gate. The
D results are ledgered first. If nothing passes D, H stays sealed and unspent.

### Cost model
Cost is c × Σ|ΔW|, both legs, SHV included, as a fraction of equity.
- Primary **c = 5 bp** per $ traded (desk: half-spread on TECL/TQQQ/BITO plus reg fees).
- Sensitivity at 3 bp (C2's measured 1–3 bp/order) and 10 bp (stress).
- Each cost level is its own sim, because the breaker sees net equity.

### Metrics
Net Sharpe (RF 4.5% constant), CAGR, vol, MaxDD, turnover (× equity traded/yr, two-sided:
the desk's 94× measure), worst day, ES1% (mean of the worst 1% of days).
Descriptive only:
- label/regime switches per year;
- 3x in/out events;
- mean and max 3x weight;
- days blocked;
- a turnover decomposition into base / scaler / residual;
- each arm's 2026-06-05 return.

### Gates (variant vs Arm 0, 5 bp unless stated)
- **F0 replica fidelity** (checked first; failure ⇒ **INVALID**, no variant read). On the live
  log rows 2026-07-27..10-09:
  - Arm 0's strategy label matches on ≥ 85% of rows;
  - Arm 0's regime label matches on ≥ 85% of rows;
  - Arm 0's turnover over 08-01..10-09 is within 35.5–142×/yr (0.5–2× C2's 71×).
- **D window:**
  - **G1** TO_v ≤ 0.50 × TO_0.
  - **G2** ΔSharpe_net ≥ −0.03 (point estimate) AND non-inferiority at margin 0.10 Sharpe.
    The test is a paired 21-day moving-block bootstrap (10,000 reps, seed 24), with
    p = P(Δ* ≤ −0.10), **Holm-adjusted across the 3 variants at α = 0.05.**
  - **G3** MaxDD_v not deeper than MaxDD_0 by > 2.0 pts.
  - **G4** |ES1%_v| ≤ 1.10 × |ES1%_0|.
  - **G5** ΔSharpe ≥ −0.05 at 3 bp, and ≥ 0.00 at 10 bp.
  - **G6 (V3 only, the cap's purpose)** |ES1%| ≥ 10% smaller than Arm 0's, AND worst day
    strictly better.
- **H window:** G1, G2 (point estimate only), G3, G4, plus G6 for V3. The bootstrap p and G5
  are reported, not gated.
- **Variant PASS** = F0 + all D gates + all H gates.
- If more than one variant passes: promote the highest D Sharpe_net at 5 bp. A tie within
  0.02 goes to the shallower D MaxDD. H never selects.

### Kill rule
- No variant passes ⇒ **EXP-024 FAIL**. The champion is unchanged.
- No other N, M, cap level, cadence or cost may be tried under this number. Each would be a
  new K and a new experiment number.
- A variant that passes D and fails H is FAIL, with no re-test.
- A failed gate may not be re-scored on a different metric.

### What PASS authorises
**Only a paper shadow.** A read-only daily logger of the promoted variant's targets, label and
scaler runs alongside the champion. It places no orders and makes no change to the champion
book; building it needs Tyler's go-ahead. Replacing the champion requires a separate
pre-registered live-vs-shadow check after ≥ 60 sessions, plus Tyler's go-ahead. FAIL or
INVALID authorises nothing.

### Why the overlay-scaler no-trade band is NOT in this experiment (orchestrator's question)
EXP-022 found that the overlay's daily rescale turns over ~10×/yr under either estimator and
costs ~0.03 Sharpe. A no-trade band on the scaler is a real candidate. I am keeping it out of
EXP-024, for four reasons:
1. **Attribution.** If the band went in all arms, the baseline would stop being live. If it
   went in one arm, that arm's result would be cadence and band confounded.
2. **K budget.** All three slots test the selection-cadence question C2 and the audit
   actually raised.
3. **Scope.** The band is estimator-independent and book-independent; the challenger rescales
   daily too. Its natural test spans both books.
4. **Data.** EXP-024 *reports* a turnover decomposition (base / scaler / residual). That is
   the input a band experiment needs, but once it is read it contaminates D for the band. So
   the band gets its **own number**, and it must be registered either **before EXP-024's D
   results are read** or on data neither experiment touches (pre-2009 proxies, as in 022).

### K
Champion-configs family: 11 (back-filled, pre-journal) + 3 = **14**. EXP-024 spends 3
(V1, V2, V3).

### Prior (stated before running)
- F0 passes: ~70% (Tiingo vs live closes; the 0.5 floor and crumb fold post-date most of the
  live rows).
- G1: V1 ~80%, V3 ~80%, V2 ~65%. Turnover risk: the overlay plus the 2% drift gate may keep
  every arm above half.
- G2 (Holm, margin 0.10): ~50% each. The bootstrap SE on ΔSharpe over 6.8 y is probably close
  to the margin.
- G6 for V3: ~60%.
- Any variant passes D: ~50%. Passes D and H: ~35%.

### RESULT — run 2026-10-13 · F0 **PASS** · V1/V2/V3 all **FAIL G2** on D · EXP-024 **FAIL** · H **sealed, unspent**

Run by an independent tester who did not design the experiment. Code and outputs are in
`research/exp024/`: engine.py, run_D.py, score.py, results_D_F0.json, results_D.json,
verdict.json, daily_<arm>_D_<bp>.parquet, INTERPRETATIONS.md (28 ambiguity readings, written
before any output), integrity.txt, unit_checks.txt. Engine: worktree HEAD d6a6f812 (= d6a6f81;
branch unmoved). Library code was imported from there, and no tracked file was edited.
Data: Tiingo adjClose for all 15 tickers (no fallback), ffill only.

**EXP-026 timing (asked by the orchestrator).** EXP-026 was *not* in the ledger at my first
check, 22:48:59 PDT (0 matches). It *was* there at my re-check at 22:53:09 (header
self-reports "ledger write 22:50:03"). Both checks came before any EXP-024 output:
results_D_F0.json was written 22:53:55 and results_D.json 22:55:00. So EXP-026 was registered
before EXP-024's D results existed. Note that it is on the challenger book.

#### D — F0 replica fidelity: PASS
On the 54 live rows dated 2026-07-27..10-09:

| check | result | bar |
|---|---|---|
| strategy label match | 47/54 = 87.0% | ≥ 85% |
| regime label match | 54/54 = 100% | ≥ 85% |
| Arm 0 turnover, 08-01..10-09 | 104.7×/yr (49 days) | 35.5–142× |

The 7 strategy mismatches:
- 07-29 and 07-30: the engine chose MAX_SHARPE, live chose HRP_MOMENTUM.
- 09-11, 09-16, 09-17 and 09-22: the engine chose HRP_MOMENTUM, live chose HRP.
- 09-25: the engine chose HRP_MOMENTUM, live chose HRP.

All are adaptive-override flips. The live rows predate the 0.5 floor, and live used
yfinance closes while the engine used Tiingo.

#### D — metrics, 5 bp (2020-01-02..2026-10-09, N = 1,702)

| arm | Sharpe net | CAGR | vol | MaxDD | TO ×/yr | worst day | ES1% | mean 3x | days blocked |
|---|---|---|---|---|---|---|---|---|---|
| A0 as-live | 0.333 | 9.46% | 19.2% | −39.7% | 68.7 | −6.33% (2025-10-10) | −4.42% | 20.3% | 136 |
| V1 monthly | 0.390 | 10.55% | 18.7% | −23.2% | 12.3 | −6.33% | −4.51% | 19.3% | 0 |
| V2 hysteresis | 0.436 | 11.83% | 19.9% | −32.4% | 17.3 | −6.33% | −4.53% | 21.5% | 24 |
| V3 monthly+cap30 | 0.445 | 11.07% | 16.6% | −22.2% | 11.3 | −5.65% (2026-06-05) | −3.73% | 16.1% | 0 |
| R (legacy sim; 0 cost, constant RF; not gated) | 0.603 | 15.13% | 18.9% | −23.5% | – | −6.37% | – | – | – |

Sharpe net at each cost level (A0 / V1 / V2 / V3):

| cost | A0 | V1 | V2 | V3 |
|---|---|---|---|---|
| 0 bp | 0.472 | 0.423 | 0.476 | 0.479 |
| 3 bp | 0.399 | 0.403 | 0.453 | 0.459 |
| 5 bp | 0.333 | 0.390 | 0.436 | 0.445 |
| 10 bp | 0.121 | 0.358 | 0.394 | 0.411 |

#### D — gate table (vs A0, 5 bp unless stated)

| gate | V1 | V2 | V3 |
|---|---|---|---|
| G1 TO ratio ≤ 0.50 | 0.178 ✔ | 0.252 ✔ | 0.164 ✔ |
| G2 ΔSR ≥ −0.03 | +0.057 ✔ | +0.103 ✔ | +0.112 ✔ |
| G2 p = P(Δ* ≤ −0.10) | 0.230 | 0.111 | 0.155 |
| G2 Holm threshold | 0.05 ✘ | 0.0167 ✘ | 0.025 ✘ |
| G3 MaxDD Δ (pts) ≥ −2.0 | +16.5 ✔ | +7.2 ✔ | +17.4 ✔ |
| G4 ES1% ratio ≤ 1.10 | 1.020 ✔ | 1.024 ✔ | 0.844 ✔ |
| G5 ΔSR @3bp ≥ −0.05 | +0.005 ✔ | +0.054 ✔ | +0.060 ✔ |
| G5 ΔSR @10bp ≥ 0 | +0.237 ✔ | +0.273 ✔ | +0.290 ✔ |
| G6 (V3) ES ≤ 0.90× and worst day better | – | – | 0.844, −5.65% > −6.33% ✔ |
| **D verdict** | **FAIL (G2)** | **FAIL (G2)** | **FAIL (G2)** |

How G2 failed under Holm: V2 had the smallest p, 0.1114, against a threshold of 0.0167. It
failed, so the procedure stopped there, and V3 (0.155) and V1 (0.230) failed with it.

The bootstrap used 10,000 paired 21-day moving blocks from `default_rng(24)`, one index matrix
for all three variants. The SD of Δ* was 0.217 for V1, 0.169 for V2 and 0.229 for V3.

**Verdict (frozen rule): no variant passes D ⇒ EXP-024 FAIL. The champion is unchanged.**
H stays sealed and unspent:
- `prices_H.parquet` was written once, at download, by the split.
- It was never parsed or loaded.
- Its bytes were read once, by an `md5`, which I disclose.
- `run_H.py` was not built.

Nothing is authorised.

#### Turnover breakdown (5 bp, × equity/yr; descriptive; the components overlap)

| arm | total | base | scaler | residual | strategy switches/yr | regime switches/yr | TQQQ in/out /yr | cost drag @5bp |
|---|---|---|---|---|---|---|---|---|
| A0 | 68.7 | 59.2 | 32.5 | −23.0 | 35.1 | 28.3 | 26.8 | 3.44%/yr |
| V1 | 12.3 | 9.3 | 7.2 | −4.2 | 5.0 | 4.7 | 3.4 | 0.61%/yr |
| V2 | 17.3 | 13.5 | 7.8 | −4.0 | 6.5 | 7.7 | 7.4 | 0.87%/yr |
| V3 | 11.3 | 9.3 | 6.8 | −4.8 | 5.0 | 4.7 | 3.4 | 0.56%/yr |

The residual is negative because the base and scaler formulas double-count on days when both
B and s move. A0's scaler component (~32×) is about 3× EXP-022's whole-book ~10×. That comparison is
loose: EXP-022 tested a different book on a proxy universe. The daily
re-selection moves B under the scaler, and the scaler then re-moves it.

#### Other findings (descriptive, not gated)

**1. A0's drawdown breaker froze the daily book for 136 sessions (2022-06-15..2023-05-15).**
At 5 bp, A0 crossed −30% net. From then on, its drawdown check blocked every trade, and the
book drifted until it reached a −39.7% trough on 2022-10-14. V1 and V3 never reached −30%, so
they were never blocked.
- Most of the +16 to +17 pt MaxDD gap is this freeze, not cadence alone.
- The breaker as live implements it freezes risk at the bottom rather than removing it.

**2. The 2026-06-05 day is not reproduced.** Every arm held 26.2% in 3x on that day, with the
scaler at 0.28, and returned −5.65%. Live held ~96% in 3x and lost 19.0%. The d6a6f81 replica
would not have held the book live held. F0 only covers rows from 07-27, so this gap is
unexplained here.

**3. The vol, concentration and correlation checks never fired in any arm.** V2's averaging broke RISK_OFF floors on 79 days, which were counted.

**4. Gross timing value is small.** At 0 bp:
- V1 is −0.049 Sharpe vs A0, so daily re-selection has a little gross value against monthly.
- V2 and V3 are +0.004 and +0.007.

The whole net gain is cost.

#### Disclosures
- The overnight close(t)→open(t+1) gap is ignored, as the spec says.
- The engine uses Tiingo closes, while live used yfinance/Alpaca.
- Regime, select and optimize are cached per (date, args). This is safe because they are pure
  functions of prices. The breaker, risk gate, drift gate and accounting are run per cost
  level.
- Unit checks on 2019 all passed:
  - timing: perturbing bars ≥ i leaves decision i unchanged;
  - ΣW = 1 to within 1e-14;
  - c = 0 with gates off equals a direct optimize loop to 0.0.

**Binding constraint (one line):** G2's non-inferiority test cannot resolve the effect size.
Over 6.8 y, the bootstrap SD of ΔSharpe is 0.17–0.23. To clear its Holm threshold at margin
0.10, a variant needs a point ΔSR of about +0.26 to +0.35; the observed values were
+0.06/+0.10/+0.11. Each variant passed every other gate, including:
- a 75–84% turnover cut;
- 2.6–2.9%/yr of cost saved at 5 bp;
- a MaxDD 7–17 pts shallower;
- a 16% smaller ES for V3.

The prior's "SE probably close to the margin" was wrong: the SE is about 2× the margin.

**Pattern check (against the ledger, not memory):**
- EXP-022 Part B died at ΔSharpe_net −0.029 against a bar of −0.02, inside the ±0.03 that its
  own spec called "not statistically resolvable".
- EXP-024 dies at ΔSR +0.06..+0.11 against a bootstrap SD of about 0.2.

Twice in a row, a champion/overlay structural change produced large, deterministic changes in
turnover, cost and drawdown, and was judged on a Sharpe difference that one ~7-year daily window
cannot resolve. The second time, the gate statistic itself had little power: even a true
ΔSR of +0.15 would usually fail it. That is one finding: **in this family, the Sharpe-difference
gate, not the strategy, is what binds.**

**Next structure (what this constraint does not bind; new number, new K — not a re-score of
EXP-024):**
- Pre-register cadence as a *cost* question:
  - primary statistic: deterministic turnover and cost saved (no sampling error given the
    trade log);
  - non-inferiority on *gross* Sharpe, where the true Δ is about 0 for V2/V3, with a margin
    sized to the measured resolution (SD ≈ 0.17–0.23 per 6.8 y, written down beforehand);
  - the still-unspent 2011–2018 H window as confirmation.
- Separately, two engineering items surfaced here deserve their own measurement entries:
  - the breaker-freeze behaviour (A0, 136 blocked days in 2022–23);
  - the unexplained live-vs-replica gap on 2026-06-05 (96% vs 26% 3x).

None of these is authorised by this result.

---

## EXP-026 — No-trade band on the daily vol-target scaler (challenger book)

**Status:** PRE-REGISTERED 2026-10-13 (ledger write 22:50:03 PDT). Written BEFORE any EXP-026
simulation and BEFORE any EXP-024 D-window result was in this ledger. Read beforehand: the
EXP-022 and EXP-024 entries, `risk_overlay.vol_target_scaler`, `challenger/backtest.py`
(`run_book`, `run_champion_proxy`) and `challenger/sleeves.py` at d6a6f81. No prices loaded,
no scaler path computed. K = 3. Build spec: `research/exp026_spec.md` (binding; if it and this
entry disagree, this entry wins and the disagreement is reported).

**Origin:** EXP-022: the overlay rescales ~10×/yr under either estimator; both faster-estimator
replays (002, 022) gave back ~0.03 Sharpe to costs. EXP-024 §"Why the band is NOT in this
experiment" split the band out and required it be registered before 024's D results. This is it.

### Hypothesis
Holding the scaler fixed until the newly computed scaler moves past a band cuts the book's
turnover to ≤ 0.6× of the live rule, with net Sharpe non-inferior and drawdown/tail/vol
not materially worse. Mechanism: day-to-day changes in a 40d trailing vol estimate are mostly
noise (one day in, one day out); re-scaling on them pays the spread for no risk change.
Why it could fail: (a) the existing 2% per-name DRIFT gate already suppresses most small
rescales, so the band saves little; (b) monthly base rebalances dominate turnover, making
0.6× unreachable from the scaler alone; (c) a band delays de-risking into vol spikes
(2008, 2020-03), deepening MaxDD/ES.

### Book and engine
Primary and ONLY gated book: challenger `run_book(px, SLEEVE_BUDGETS, 0.16)` — the live config
(core .45 / trend 0 / lowvol .28 / ballast .27, VT 16%, VOL_MODEL "trailing", 80-row window,
DRIFT 0.02, monthly BME base rebalance, SHV cash at 2%/yr, RF 4.5%). Code: the FIXED engine on
branch `worktree-agent-a755d2182dda758ab` (d6a6f81: no same-bar look-ahead). The variant
changes only which scaler value feeds `desired`; nothing else in run_book changes.
Champion proxy (`run_champion_proxy`, VT 20%) is run with the same bands and REPORTED ONLY —
any champion adoption needs its own experiment on the EXP-024 main.py replica.

### Variants (K = 3; baseline Arm 0 = live rule, s_held = s_new every day)
s_new = vol_target_scaler(...) as live. s_held initialised to s_new on the first sim day.
| Variant | Update rule (on trigger, s_held jumps fully to s_new; else s_held kept) |
|---|---|
| **B1 ABS05** | update iff \|s_new − s_held\| > 0.05 |
| **B2 ABS10** | update iff \|s_new − s_held\| > 0.10 |
| **B3 REL10** | update iff \|s_new / s_held − 1\| > 0.10 (s_held ≤ 1e-6 ⇒ update) |
Symmetric (no "cut immediately" override). desired uses s_held; DRIFT gate, base rebal, cost
accounting unchanged. Monthly base rebalances use s_held too (band is on the scaler only).

### Data and windows (Tiingo adjClose via challenger `load_data`, startDate 2005-01-01, ffill)
| Window | Role | Metrics period |
|---|---|---|
| **D** | Primary gate | 2007-01-03 → 2018-12-31 (sim runs from series start; metrics sliced) |
| **H** | Sealed holdout | 2019-01-02 → 2026-10-09 (sim runs on full history; only these dates scored) |
The sim always runs on the full history (so the warm-up and s_held state are continuous); D/H
only slice the scored returns. H is opened ONCE, all arms, only if ≥ 1 variant passes every D gate.
**Contamination, declared:** (1) the challenger *config* was chosen on 2005–2026 (EXP-021 era
work), so neither window is fresh for the BOOK; both are fresh for the BAND (no band has ever been
run). (2) H overlaps EXP-024's D window (2020–2026, Tiingo). EXP-024 is a champion-book cadence
test; its scaler-turnover decomposition will be read before H opens. That can inform priors on
scaler share of champion turnover, not the sign of the challenger band's ΔSharpe; disclosed, not
cured. (3) The 1990–2004 proxy set is spent (EXP-022) and lacks the sleeve ETFs; not used.

### Cost model
cost = c × Σ\|ΔW\| on each executed trade, both legs, SHV included. Primary c = 5 bp; sensitivity
3 bp and 10 bp (each its own sim — run_book's TCOST is the only change). run_book's default 10 bp
is NOT the primary.

### Metrics (each window)
Net Sharpe (RF 4.5%), CAGR, ann. vol, MaxDD, turnover (×/yr, two-sided Σ\|ΔW\|), ES1% (mean of
worst 1% days), worst day, scaler-update days/yr, trade days/yr, mean \|s_held − s_new\|,
turnover on non-rebalance days vs BME days (descriptive decomposition).

### Gates (variant vs Arm 0, c = 5 bp unless stated)
- **F0 sanity (INVALID if fails):** Arm 0 reproduces `run_book(px, SLEEVE_BUDGETS, 0.16)` with
  TCOST=10bp to |Δ daily ret| < 1e-12 on every day; a band of 0 reproduces Arm 0 exactly.
- **D window:**
  - **G1** TO_v ≤ 0.60 × TO_0 (total turnover).
  - **G2** ΔSharpe_net ≥ −0.02 (point) AND non-inferiority at margin 0.05: paired 21-day
    moving-block bootstrap of daily return pairs, 10,000 reps, seed 26,
    p = P(ΔSharpe* ≤ −0.05); **Holm-adjusted across the 3 variants, α = 0.05.**
  - **G3** MaxDD_v not deeper than MaxDD_0 by > 1.0 pt.
  - **G4** |ES1%_v| ≤ 1.05 × |ES1%_0| AND ann. vol_v ≤ 1.05 × vol_0.
  - **G5** ΔSharpe ≥ −0.03 at 3 bp; ΔSharpe ≥ 0.00 at 10 bp.
- **H window:** G1, G2 (point estimate only; bootstrap p reported), G3, G4. G5 reported only.
- **PASS** = F0 + all D gates + all H gates. Multiple passers: highest D Sharpe_net at 5 bp;
  tie within 0.01 → lower D turnover. H never selects.

### Kill rule
No variant passes ⇒ **EXP-026 FAIL**; overlay unchanged. No other band width, asymmetric
override, book, window or cost may be tried under this number (each is a new K and number).
Passes D, fails H ⇒ FAIL, no re-test. No gate re-scored on another metric. Do not report the
champion-proxy result as a pass/fail for anything.

### What PASS authorises
**Paper shadow only:** a read-only logger computing the promoted band's s_held and hypothetical
target next to the live challenger each day. No orders, no change to `challenger/main.py`,
`risk_overlay.py` or `sleeves.py`; building it needs Tyler's go-ahead. Changing the live overlay
needs a separate pre-registered shadow-vs-live check (≥ 60 sessions) plus Tyler's go-ahead.
FAIL/INVALID authorise nothing.

### K
New family "overlay execution rule": 3 (B1, B2, B3). Overlay-estimator family (002, 014, 022)
is separate and untouched. Deflated Sharpe reported with K = 3.

### Prior (stated before running)
F0 ~95%. G1 (≤ 0.6× total): B1 ~35%, B2 ~55%, B3 ~40% — risk (b) is the main threat; the 2%
DRIFT gate already absorbs small rescales. G2 ~70% each (variants are near-identical paths, so
paired SE is small). G3/G4 ~70% (2008/2020 lag risk, larger for B2). Any variant passes D ~35%;
passes D and H ~25%.

### RESULT (independent tester, 2026-10-13) — **FAIL** (all three variants fail D-G1; H NOT opened)

**Setup as run.** Engine imported by path from worktree `agent-a755d2182dda758ab` @ d6a6f81 (not
edited). Code/output: `research/exp026/` (`fetch.py`, `run.py` = `run_book_band` /
`run_champion_proxy_band` copies, `score.py`, `INTERPRETATIONS.md` written before any sim,
`F0.json`, `results_D.json`, `daily_series.parquet`, `px.parquet`). Data: fresh Tiingo adjClose
pull replicating `load_data` (the existing `challenger/prices_cache.parquet` was dated 2026-06-09
and could not cover H), 15 tickers, 5,477 rows, 2005-01-03 → 2026-10-09 (truncated there),
SHA-256 `08ee707e1dcbf2ef6ae0e03f4cab39c9d190a6e2030e0a1b58f269870e12b577`.

**F0 PASS.** A0 @10 bp vs unmodified `backtest.run_book(px, SLEEVE_BUDGETS, 0.16)`: max |Δ| = 0.0.
Band abs 0.0 vs A0: max |Δ| = 0.0 at 3, 5 and 10 bp.

**D window 2007-01-03 → 2018-12-31 (3,020 days, 11.99 yr).** TO = two-sided Σ|ΔW|/yr;
split = BME-day / other-day; upd = scaler-update days/yr; trd = trade days/yr.

| arm | bp | Sharpe | CAGR | vol | MaxDD | ES1% | worst | TO/yr | TO split | upd | trd | mean\|s_h−s_n\| | DSR K=3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 5 | 0.5789 | 11.08% | 11.55% | −23.02% | −2.556% | −3.69% | 2.615 | 2.174 / 0.442 | 23.3 | 14.8 | 0.0000 | 0.993 |
| B1 | 5 | 0.5808 | 11.10% | 11.55% | −22.98% | −2.553% | −3.69% | 2.469 | 2.153 / 0.316 | 3.2 | 10.9 | 0.0033 | 0.993 |
| B2 | 5 | 0.5820 | 11.13% | 11.57% | −22.73% | −2.553% | −3.69% | 2.378 | 2.137 / 0.241 | 1.6 | 9.6 | 0.0052 | 0.993 |
| B3 | 5 | 0.5890 | 11.22% | 11.56% | −22.73% | −2.548% | −3.69% | 2.376 | 2.140 / 0.236 | 1.7 | 9.7 | 0.0049 | 0.994 |
| A0 | 3 | 0.5835 | 11.14% | 11.55% | −22.95% | −2.556% | −3.69% | 2.615 | | | | | 0.994 |
| B1 | 3 | 0.5851 | 11.16% | 11.55% | −22.91% | −2.553% | −3.69% | 2.469 | | | | | 0.994 |
| B2 | 3 | 0.5861 | 11.19% | 11.57% | −22.66% | −2.553% | −3.69% | 2.378 | | | | | 0.994 |
| B3 | 3 | 0.5931 | 11.27% | 11.56% | −22.66% | −2.548% | −3.69% | 2.376 | | | | | 0.994 |
| A0 | 10 | 0.5676 | 10.94% | 11.55% | −23.20% | −2.557% | −3.69% | 2.615 | | | | | 0.992 |
| B1 | 10 | 0.5701 | 10.97% | 11.55% | −23.15% | −2.554% | −3.69% | 2.469 | | | | | 0.993 |
| B2 | 10 | 0.5717 | 11.00% | 11.57% | −22.89% | −2.554% | −3.69% | 2.378 | | | | | 0.993 |
| B3 | 10 | 0.5787 | 11.09% | 11.56% | −22.89% | −2.548% | −3.69% | 2.376 | | | | | 0.993 |
(Turnover/updates are cost-independent; shown once.)

**D gates (5 bp unless stated).**

| gate | threshold | B1 ABS05 | B2 ABS10 | B3 REL10 |
|---|---|---|---|---|
| G1 TO_v/TO_0 | ≤ 0.60 | 0.944 **FAIL** | 0.909 **FAIL** | 0.908 **FAIL** |
| G2 ΔSharpe (point) | ≥ −0.02 | +0.0019 ✓ | +0.0031 ✓ | +0.0100 ✓ |
| G2 boot p = P(ΔS* ≤ −0.05), sd(ΔS*) | Holm α .05 | 0.0000 (sd .0040) ✓ | 0.0000 (sd .0075) ✓ | 0.0000 (sd .0061) ✓ |
| G3 ΔMaxDD | ≥ −1.0 pt | +0.04 pt ✓ | +0.29 pt ✓ | +0.29 pt ✓ |
| G4 ES ratio / vol ratio | ≤ 1.05 / ≤ 1.05 | 0.999 / 1.000 ✓ | 0.999 / 1.002 ✓ | 0.997 / 1.001 ✓ |
| G5 ΔS @3bp / @10bp | ≥ −0.03 / ≥ 0 | +0.0016 / +0.0025 ✓ | +0.0027 / +0.0041 ✓ | +0.0096 / +0.0111 ✓ |
| **all D gates** | | **FAIL (G1)** | **FAIL (G1)** | **FAIL (G1)** |

Holm: all three p = 0 (ties, order B1, B2, B3), each < 0.05/3, 0.05/2, 0.05 — G2 passes for all.
No variant passes D ⇒ **H (2019-01-02 → 2026-10-09) never scored**, per the pre-reg. The H returns
exist in `daily_series.parquet` only because the sim runs on full history; no H metric was computed.

**Verdict: EXP-026 FAIL.** Overlay unchanged. Prior had G1 at 35–55% per variant; failure mode (b)
from the hypothesis ("monthly base rebalances dominate turnover, making 0.6× unreachable from the
scaler alone") is what happened.

**Binding constraint (with the number).** G1 was unreachable by construction: A0's BME-day turnover
is 2.174 of 2.615 /yr = **83.1%**. Even a band that deleted ALL non-BME turnover (0.442/yr) leaves
TO_v/TO_0 ≥ 0.831 > 0.60. The bands did what they were built to do — scaler-update days 23.3 → 1.6–3.2
/yr, non-BME turnover cut 29–47% — on the minority slice. Second number that matters more: the whole
book's cost drag is tiny. A0 trades 2.6×/yr; at 5 bp that is ~13 bp/yr, and A0's Sharpe moves only
0.016 between 3 bp and 10 bp. The band's cost saving is (2.615 − 2.376) × 5 bp ≈ 1.2 bp/yr ≈ 0.001
Sharpe; B3's +0.010 ΔSharpe is therefore ~90% path/timing noise, not cost savings — do not read it as
an edge.

**Pattern across deaths.** EXP-022's "~0.03 Sharpe given back to costs" was on the CHAMPION
(VT20, 3x ETFs; proxy A0 turnover here 5.98/yr). On the challenger the scaler is a minor turnover
source and turnover is a minor cost. The constraint "costs eat overlay changes" does not transfer
across books; the turnover lives where the base weights move.

**Next testable structure (constraint does not bind it).** Two, ranked:
1. *Champion book, not challenger.* The descriptive proxy below shows the band biting harder there
   (B2 turnover 5.98 → 4.55/yr, 0.76×) — but the proxy isn't the live champion. A new number,
   registered on the EXP-024 `main.py` replica, with its own G1 sized to that book's measured
   scaler share of turnover (read EXP-024's decomposition first).
2. *Challenger base-rebalance tolerance band* (skip the BME rebalance unless sleeve weights have
   drifted > x). It attacks the 83% slice — but the maximum prize is bounded by ~13 bp/yr total
   cost at 5 bp (≤ ~0.011 Sharpe), so it should only be registered if the turnover itself, not
   cost, is the objective (e.g. tax lots / live slippage on SHV-heavy rebalances). Recommend #1.

**Champion proxy — descriptive, not gated** (5 bp, 2011-07-01 → 2018-12-31; reported only, no
pass/fail for anything): A0 Sharpe 0.702, vol 21.2%, MaxDD −23.4%, TO 5.98/yr · B1 0.697, 21.4%,
−23.7%, 5.17 · B2 0.714, 21.9%, −24.9%, 4.55 · B3 0.712, 21.3%, −23.7%, 5.10.

**Deviations / interpretations / bugs.** No spec–ledger disagreement. Interpretations (data source,
bootstrap mechanics incl. re-seeding rng(26) per variant, ES count = ceil(1%·T), update-day
definition, window-rebased MaxDD) are in `research/exp026/INTERPRETATIONS.md`, written before any
sim. Deviation: px came from a fresh Tiingo pull written to `research/exp026/px.parquet` rather than
`load_data()`'s cache (stale; and writing the cache would touch the engine tree) — same request,
same transforms. No engine bug found. F0a is trivially exact because the copy is line-identical
apart from the two permitted edits.

---

## EXP-025 — Trend sleeve INSIDE the challenger's overlay, against a T-bill control (B vs C)

**Status:** PRE-REGISTERED 2026-10-13 (ledger write 22:53:06 PDT). Written BEFORE any EXP-025 arm
was simulated. No B or C return, Sharpe, drawdown or crisis number exists under the fixed engine.
K = 1. Build spec: `research/exp025_spec.md` (binding; if it and this entry disagree, this entry
wins and the disagreement is reported, not resolved toward the reading that passes).
**Read beforehand:** EXP-020 (entry + RESULT), `research/redteam_exp020.md`,
`research/replication_exp020.md`, EXP-021, EXP-024/026 headers, `challenger/backtest.py` and
`challenger/sleeves.py` at d6a6f81 (fixed branch) and at main, `risk_overlay.vol_target_scaler`
and `portfolio_vol`, `exp020/run.py`, `redteam020/rt.py`, `exp021/replay.py`, the EXP-020
mfut PROPOSAL patch.
**Computed beforehand (disclosed):** only the Sharpe-definition reconciliation below, on the
PRE-FIX `run_book` arm-A series that was already published twice (EXP-021, red team), over the
already-published window. Code/output: `research/exp025/recon_sharpe_defs/`. To confirm the AQR
file's end date I printed its last two rows [removed: raw vendor data]; both are inside
EXP-020's already-unsealed holdout.
**Origin:** red team on EXP-020 rated it WOUNDED: three of four gates are passed by T-bills at the
same weight; the trend-specific part is mostly 2022; on the challenger's book (fixed blend,
outside the overlay) ΔSharpe = 0.000. The red team asked for exactly this: the sleeve inside
`run_book` with the overlay active, against the same weight in SHV.
**Crowding read:** institution-crowded (CTAs, managed-futures ETFs). Acceptable.

### The 0.98 vs 0.65 side note — reconciled (affects how this entry is scored)
Both numbers are the SAME daily series: pre-fix `bt.run_book(px, SLEEVE_BUDGETS, 0.16)` from
2007-07. They differ only in the Sharpe definition:
| definition | Sharpe |
|---|---|
| EXP-021: `bt.metrics` — daily returns, √252, **flat 4.5%/yr hurdle** (`RF = 0.045`), to 2026-06-09 | **0.651** |
| same, ending 2026-05-31 | 0.667 |
| daily, √252, rf = mean TB3MS over window (1.43%/yr) | 0.905 |
| monthly, √12, flat 4.5% | 0.710 |
| red team: **monthly** compounded returns, √12, **excess over monthly TB3MS**, to 2026-05 | **0.983** |
Decomposition: hurdle 4.5% → realised T-bill (≈1.4%/yr) **+0.25**; daily → monthly sampling
**+0.08** (annualised vol 12.1% daily vs 11.25% monthly, i.e. daily returns are negatively
autocorrelated at the monthly horizon); end date +0.02 the other way. Neither number is a bug.
`bt.metrics`'s "Sharpe" is a hurdle ratio against a fixed 4.5% — three times the window's mean T-bill
(1.43%) — and it penalises low-vol arms more than high-vol ones, which would bias any
de-risked arm (B, C) against A. Both numbers also come from the pre-fix (look-ahead) engine, so
neither is the EXP-025 baseline.
**EXP-025 uses the red-team/EXP-020 definition for every gate:** monthly total returns compounded
from the daily book, excess over FRED TB3MS/1200 for that month, mean/sd(ddof=1)·√12.
`bt.metrics` daily-4.5% Sharpe is reported alongside for continuity with backtest.py/EXP-026.

### Hypothesis
Inside the live vol-target overlay, replacing 30% of the challenger's sleeve budgets with a
fee-haircut TSMOM sleeve (arm B) beats replacing the same 30% with T-bills (arm C): higher
monthly excess Sharpe, better returns in SPY's worst-decile months, shallower MaxDD — and the
result does not rest on a single calendar year.
Why it could be real: TSMOM's excess return is ≥ 0 on average with convex payoff to slow crashes;
cash's excess is 0 by construction. Inside the overlay, B's sleeve lowers estimated book vol, so
the scaler can keep more of the rest of the book on (C's SHV is cash, outside the scaler, so C
cannot be re-levered at all).
Why it could fail: (a) the red team's fixed-blend numbers already show B−C ≈ 0 Sharpe 2007–26 and
−0.13 in 2010–19; (b) the scaler is **capped at 1.0 — it never levers up** — and the book's
realised vol (~12%) sits below TV 16%, so on most days there is nothing to re-lever; the red
team's "the overlay re-levers" may be mostly false here. (b) is a reported prediction, below.

### Arms (all on the FIXED engine, d6a6f81; one engine, only budgets/sleeve asset differ)
- **A (challenger as-is):** `SLEEVE_BUDGETS` = core .45 / trend 0 / lowvol .28 / ballast .27, TV 0.16,
  VOL_MODEL "trailing", DRIFT 2%, BME base rebalance. Reported only (not gated).
- **B (trend sleeve inside run_book):** `MFUT_BUDGETS_PROPOSED` = core .315 / lowvol .196 /
  ballast .189 / **mfut .30** (existing ×0.7 + 30%). mfut asset = synthetic "MFUT":
  monthly return R_m = AQR TSMOM (all assets, excess) + rf_m − **0.02/12** where rf_m = SHV's
  monthly total return (so B's and C's T-bill legs are identical and B−C isolates TSMOM excess
  minus haircut). Credited daily as (1+R_m)^(1/n_m) − 1. MFUT is RISKY (inside the scaler).
- **C (T-bill control):** same budgets as B, mfut asset = SHV, which merges into CASH (outside the
  scaler) — exactly what the live patch would do with SHV in place of DBMF.
- **B_dbmf (reported-only + downgrade check):** B with MFUT = AQR proxy through 2019-05, actual
  DBMF daily (Tiingo adjClose) from 2019-06-03, using DBMF's real daily returns in the 40d cov.
- **Cash convention (all arms):** every CASH/SHV weight earns SHV's actual daily total return
  (Tiingo adjClose), not run_book's flat 2%. Reason: flat 2% understates T-bills by ~2–3 pts/yr
  in 2023–26 and would hand B a fake edge over C. A on run_book's flat 2% (`A_asis`) is reported
  as the reproduction anchor.
- **Vol estimate with a monthly sleeve (B only):** the smoothed daily MFUT series would look
  ~zero-vol to a 40d estimator and fake a re-lever. So MFUT is EXCLUDED from the 40d daily
  sample cov; its variance and covariances with each risky ticker come from monthly returns over
  months m−37..m−2 (36 months, skipping m−1 for AQR's publication lag; min 12 overlapping months,
  else that covariance = 0), annualised ×12, inserted into the same normalised-weight quadratic
  form `portfolio_vol` uses; if the augmented matrix is not PSD, the sleeve covariances are
  halved until it is (logged). s = clip(0.16/pv, 0, 1), as live. A and C use the live
  `vol_target_scaler` unchanged.
- **All gate metrics are computed on month-end equity** (monthly compounding of the daily book),
  for every arm. The smoothed sleeve has no intra-month path, so daily MaxDD/vol would flatter B.

### Cost model
10 bp × one-way turnover on every executed trade, all assets incl. MFUT/DBMF/SHV (run_book's
TCOST, the challenger-as-is convention). DRIFT 2%. AQR sleeve: 2%/yr haircut (ETF fee + replication
drag, EXP-020's primary). DBMF and SHV: expense ratios already in adjClose, no extra haircut.
Reported-only: 5 bp; haircut grid {0,1,3,4}%.

### Sample split and contamination (honest)
Window: 2007-07 .. 2026-05 (challenger history start; AQR's last month). Sim runs on full history
(warm-up continuous); windows only slice scored months.
- **IS:** 2007-07 .. 2019-05 (143 months; 2008, 2011, 2015–16, 2018Q4).
- **HO (sealed until the IS result is written in this ledger):** 2019-06 .. 2026-05 (84 months;
  COVID, 2022, 2025 tariff shock). Starts at DBMF's first full month so the buyable fund covers
  the whole holdout.
- **What prior runs touched — NO historical month here is unseen by me:**
  - EXP-020: AQR TSMOM 1985–2026-05 and SPY 1993–2026-05 (IS and HO both unsealed); DBMF/KMLM/CTA
    monthly to 2026-09.
  - Red team: the outside-overlay analogue of B vs C on the challenger (pre-fix run_book), all of
    2007-07..2026-05 and 2010–19 / 2020–26 sub-windows: ΔSh sleeve 0.000 vs cash −0.000; crisis
    +189 vs +159 bp/mo; MaxDD −14.2% vs −16.4%; 2010–19 ΔSh −0.128 vs 0.000; DBMF window
    (2019-06..2026-05) ΔSh +0.199 vs 0.000, crisis +217 vs +172 bp/mo.
  - EXP-021, the challenger's 2026-06-09 validation, EXP-026 (registered): arm A only, 2007–26.
  - **Genuinely unseen:** the inside-overlay interaction (scale paths, re-levering) under the fixed
    engine — never computed; AQR months after 2026-05 (not yet downloaded); the forward shadow.
  So the HO is sealed to the code, not to the strategist. The only clean holdout is forward.

### Gates (B vs C; monthly TB3MS-excess Sharpe; each evaluated on IS and on HO; all must pass on both)
- **G1 Sharpe:** ΔSh(B−C) > 0.00 (point) AND 90% bootstrap CI lower bound ≥ −0.10.
- **G2 crisis:** mean(B−C) over SPY's worst-decile months of that window (SPY monthly from the same
  Tiingo cache) > 0 with bootstrap P(≤0) < **0.025**.
- **G3 drawdown:** MaxDD(B) less severe than MaxDD(C) by ≥ **2.0 pts** (month-end equity).
- **G4 single-year dependence (the 2022 question — PRIMARY, decided now):** min over
  leave-one-calendar-year-out of ΔSh(B−C) ≥ **−0.10** (drop that year's months from both series,
  no re-simulation; partial edge years count as years).
  Why primary and why this form: the red team's binding constraint is that the trend-specific
  benefit is one event (2022: +6.2 pp vs cash; ex-2022 ΔSh +0.014). Reported-only would let the
  verdict rest on that one event again. But demanding superiority with the crisis removed tests
  the wrong hypothesis — insurance is supposed to cost in normal years. So G4 bounds the COST of
  the insurance outside any single year (non-inferiority, same −0.10 margin as EXP-020 H1), and
  it is "drop ANY one year, worst case", not "drop 2022", so the year isn't named after seeing
  it — it binds 2008 in IS the same way it binds 2022 in HO. Literal ex-2022 and ex-2008 are
  reported.
- **Bootstrap:** paired circular moving-block bootstrap on the monthly (B, C, SPY, rf) rows,
  block 12, 10,000 reps, seed 20261013; worst-decile months re-identified inside each resample;
  P = uncentred fraction of Δ* ≤ 0 (EXP-020's disclosed method).
- **Multiple testing:** K = 1 (one comparison, w = 0.30 fixed by EXP-020, h = 2% fixed, one fund,
  one split). Gates are conjunctive (intersection-union), so no adjustment across gates. G2 is the
  only P-value gate; α = 0.025 = Bonferroni over the trend family's two holdout tests on
  overlapping 2010–2026 data (EXP-020 H2, this). Trend family running K: EXP-006 0, EXP-020 3+1,
  EXP-025 1 → DSR of B reported with K = 5.
- **Implementability downgrade (cannot upgrade):** on HO, if B_dbmf vs C has ΔSh < −0.10 OR crisis
  mean ≤ 0 (points), a PASS is downgraded to INCONCLUSIVE (the AQR proxy does not describe the fund).
- **Validity (INVALID if fails):** F0 — the research engine with flat-2% cash and A's budgets
  reproduces fixed `bt.run_book(px, SLEEVE_BUDGETS, 0.16)` to < 1e-12 per day; F1 — C with
  mfut = 0 and SHV-actual cash equals A on SHV-actual cash exactly.

### Verdict
**PASS** = F0–F1 + G1–G4 on IS + G1–G4 on HO (+ no downgrade). **PARTIAL** = G2 and G3 pass on both
windows but G1 or G4 fails somewhere (crisis insurance that beats cash, bought at a Sharpe/
single-year cost) — authorises a report to Tyler only. **FAIL** otherwise. IS fails → HO is still
scored ONCE, descriptively, verdict FAIL (stated now).

### Reported-only (no verdict weight)
A vs B, A vs C (CAGR, vol, Sharpe both definitions, MaxDD, worst-12m, Calmar); B−C CAGR; per-year
B−C; **the re-lever test:** mean scaler s and % of days s < 1 for A, B, C, plus B's mean gross
risky exposure vs C's — prediction stated now: s = 1 on most days in all arms, so B's re-lever
gain over C is < 1 pt/yr of CAGR; smoothing calibration on HO (B_dbmf vs B with DBMF
monthly-smoothed + structured cov); haircut grid; 5 bp costs; B_dbmf full HO table; A_asis.

### Priors (stated before running)
F0–F1 ~95%. IS: G2 ~70% (2008 is in it), G3 ~70%, G1 ~40%, G4 ~35% (drop 2008 leaves the
2010–19 stretch where the red team saw −0.13). HO: G2 at P < 0.025 with ~9 crisis months ~30%,
G3 ~65%, G1 ~55%, G4 ~35% (drop 2022). **PASS ~8%. PARTIAL ~25%. FAIL ~65%.** Re-lever
prediction (s=1 most days) ~75%.

### Kill rule
FAIL → the "buy breadth inside the challenger" route is closed for this weight/proxy:
`MFUT_BUDGETS_PROPOSED` stays unapplied and is marked dead; no re-test under this number at
w = 0.10/0.20, another haircut, fund (KMLM/CTA), split, crisis definition, Sharpe definition or
cost. Each would be a new K and a new number. Re-entry only on NEW data: ≥ 36 AQR months after
2026-05, or a ≥ 10% SPY drawdown, registered fresh before it is scored. Idea queue item #2 then
records the constraint, not "trend doesn't work".

### What PASS authorises
A **3-arm paper shadow**, per the red team's design, as a measurement instrument — not an edge
test, not a live change: A as-is, B = challenger with `MFUT_BUDGETS_PROPOSED` + DBMF inside the
overlay, C = same with SHV. Logged daily from adjusted prices (NOT paper equity: the paper account
doesn't credit dividends, EXP-021, and SHV's return is nearly all distributions). No orders.
Building it needs Tyler's go-ahead. Shadow rules frozen in the spec (§7): ≥ 126 sessions;
shelve if DBMF's β to SPY in SPY-down weeks ≥ 0, or B−C cumulative < −3% with no SPY drawdown
worse than −10%; a ≥ 10% SPY drawdown during the shadow is scored B vs C as one pre-declared
event. KMLM/CTA logged reported-only; the fund is not switched later. Any change to the live
challenger needs a separate pre-registration plus Tyler's go-ahead. PARTIAL/FAIL/INVALID
authorise no shadow.

### RESULT (part 1 of 2: IN-SAMPLE) — tester run 2026-10-13, ledger write 23:00:33 PDT · **IS FAIL (G1, G2, G4 fail; G3 passes)** · HO still sealed at this write
Independent tester. Engine worktree d6a6f81 (import paths asserted). Code/outputs `research/exp025/`
(`INTERPRETATIONS.md` written before any B/C statistic; items 17–19 added after two pre-scoring
crashes in the first B sim, disclosed there). **Validity:** F0 max|Δ| = 0.0, F1 max|Δ| = 0.0,
DBMF 2022 = +21.53% (check passes). IS = 2007-07..2019-05, 143 months, monthly TB3MS-excess Sharpe.
| arm | CAGR | vol | Sharpe | MaxDD(m) | hurdle Sh |
|---|---|---|---|---|---|
| A (SHV cash) | 10.66% | 10.4% | 0.958 | −22.2% | 0.550 |
| **B** (AQR h=2%) | 9.05% | 9.0% | **0.930** | **−12.9%** | 0.545 |
| **C** (SHV) | 7.76% | 7.3% | **0.969** | **−15.1%** | 0.413 |
- **G1 FAIL:** ΔSh(B−C) = **−0.039**, 90% CI [−0.257, +0.160] (point ≤ 0).
- **G2 FAIL:** crisis mean(B−C) = **+46.8 bp/mo** over 15 SPY-worst-decile months, P(≤0) = **0.210** (need < 0.025).
- **G3 PASS:** MaxDD B −12.91% vs C −15.15% → **+2.24 pts** (need ≥ 2.0).
- **G4 FAIL:** min LOYO ΔSh = **−0.138 (drop 2008)** (need ≥ −0.10). Every other year −0.073..+0.017.
- Per-year B−C (pp): 2008 +6.06, 2013 +5.12, 2014 +5.48, 2015 +4.52 vs 2009 −2.93, 2016 −4.19, 2018 −3.64.
- **Re-lever test (prediction HELD):** mean s A 0.989 / B 1.000 / C 0.989; % days s<1 A 8.7 / B 0.6 / C 8.7.
  B−C non-sleeve gross exposure +0.007. Re-lever CAGR gain (B vs B replayed on C's s-path) = **+0.17 pt/yr** (< 1).
  B−C CAGR +1.29 pt/yr is almost all the sleeve's own excess return, not re-levering.
- Reported-only: haircut grid ΔSh h0 +0.028 / h1 −0.005 / h3 −0.072 / h4 −0.105; 5 bp ΔSh −0.043;
  DSR(B, K=5) 0.994; A vs B ΔSh −0.028, MaxDD +9.3 pts. Structured scaler: PSD shrink needed on
  1,368 sim days (all fixed within 10 halvings); NaN-cov days 94 (all ≤ 2006-05, warm-up).
- Priors check: IS G2 ~70% → failed (point positive, P 0.21); G1 ~40% → failed; G4 ~35% → failed; G3 ~70% → passed.
**IS verdict FAIL ⇒ EXP-025 verdict is FAIL** (stated in the pre-reg). HO is scored once, descriptively, next.

### RESULT (part 2 of 2: HOLDOUT, descriptive — unsealed after the IS write above) — ledger write 23:01:52 PDT · **EXP-025 FAIL**
HO = 2019-06..2026-05, 84 months, scored once.
| arm | CAGR | vol | Sharpe | MaxDD(m) | hurdle Sh |
|---|---|---|---|---|---|
| A (SHV cash) | 14.98% | 12.4% | 0.973 | −21.3% | 0.773 |
| **B** (AQR h=2%) | 12.70% | 9.2% | **1.060** | **−9.1%** | 0.790 |
| **C** (SHV) | 11.32% | 8.7% | **0.969** | **−15.4%** | 0.710 |
| B_dbmf (real DBMF from 2019-06-03) | 14.52% | 9.3% | 1.217 | −8.8% | 0.866 |
- G1 FAIL: ΔSh +0.091, CI90 [−0.166, +0.324]. G2 PASS (barely): +59.6 bp/mo over 9 months, P(≤0) = **0.0248** vs 0.025.
  G3 PASS: +6.26 pts (−9.1% vs −15.4%). G4 FAIL: min LOYO **−0.118 (drop 2022)**; every other year +0.03..+0.18.
- Downgrade check (moot): B_dbmf vs C ΔSh +0.248 (CI90 −0.034..+0.478), crisis +31.1 bp P 0.228, MaxDD +6.6 pts,
  LOYO min +0.066 → no downgrade. Smoothing calibration (DBMF monthly-smoothed + struct cov − DBMF daily + live
  scaler): ΔSh −0.019, MaxDD −0.40 pts, mean |Δs| 0.007 — the smoothing/structured-cov machinery is not what drives B.
- **Re-lever test:** mean s A 0.952 / B 0.987 / C 0.952; % days s<1 A 20.6 / B 5.9 / C 20.6; B−C non-sleeve gross
  +0.024. Re-lever CAGR gain (B − B on C's s-path) = **+0.97 pt/yr** — prediction (< 1 pt) **held in both windows,
  but only just in HO** (IS +0.17). In HO the re-lever is ~70% of B−C CAGR (+1.38): the sleeve's own carry after the
  2% haircut was ~+0.4 pt/yr; the "overlay re-levers" mechanism the red team named is real in high-vol regimes and
  ~nil in calm ones (s=1 on 91% of IS days in A/C).
- Reported-only: haircut grid ΔSh h0 +0.156 / h1 +0.124 / h3 +0.059 / h4 +0.026; 5 bp ΔSh +0.088; DSR(B,K=5) 0.978.
- Priors: HO G2 ~30% → passed at P 0.0248; G3 ~65% passed; G1 ~55% failed; G4 ~35% failed. Overall FAIL (~65% prior).

**Verdict: EXP-025 FAIL** (IS: G1, G2, G4 fail; HO descriptive: G1, G4 fail). Not PARTIAL: G2 failed IS (P 0.21).
Kill rule applies: `MFUT_BUDGETS_PROPOSED` stays unapplied and is marked dead at w=0.30/AQR/h=2%; no shadow.
B_dbmf's better HO numbers cannot upgrade (downgrade-only check; fund switches are a new K).

**Binding constraint:** single-year dependence — B's Sharpe edge over T-bills exists only through one crisis year per
window: drop 2008 → ΔSh **−0.138** (IS), drop 2022 → **−0.118** (HO), against the −0.10 bound; the full-IS ΔSh is
−0.039. The crisis payoff is real in sign in both windows (+47, +60 bp/mo; MaxDD 2.2 and 6.3 pts better) but it is
paid for by ~−0.03..−0.07 ΔSh of carry in every other year, roughly the 2% haircut (IS h0 ΔSh +0.028 vs h2 −0.039).
**Pattern across the trend family (ledger-checked):** EXP-006 FAIL (premise); EXP-020 PASS vs SPY but red-team
WOUNDED because T-bills pass three of its four gates; EXP-025 FAIL vs T-bills inside the overlay. Same finding three
times: against cash, trend is once-a-decade insurance with a steady premium, and 7–12-year windows contain one
claim each. The one mechanism that is NOT single-event is the re-lever (+0.97 pt/yr in 2019–26, +0.17 in 2007–19):
it pays whenever book vol is above target, not only in a crash.
**Next structure (constraint it does not bind; new K, registered fresh):** stop holding the insurance unconditionally.
Route the scaler's own de-risked fraction (1−s)·risky into the trend fund instead of SHV — B ≡ A whenever s = 1
(no carry in calm years, so no LOYO bleed), trend held only while vol is above target (when TSMOM's convexity
pays). Honest prior: small — mean 1−s was 1.1% (IS) / 4.8% (HO), so the effect is bounded; and under this entry's kill
rule it may only be scored on NEW data (the pre-declared ≥10% SPY drawdown event or ≥36 new AQR months), so it is
a forward-logged arm, not a backtest. Code/outputs: `research/exp025/` (is_/ho_ results.json, monthly_IS/HO.csv).

---

## EXP-023 — RESULT (appended at ledger end; spec is the EXP-023 entry above, line ~3129)

### RESULT — run 2026-10-13 · Part A **FAIL** (h=1 clears all 3 comparators; h=5 does not) · Part B **not run** (gate) · no patch

Ran as registered. Code + cache: scratchpad tradingroom/exp023/ (dryrun.py, fetch.py, build_rv.py,
partA.py, partA_output.txt, partA_verdict.json; partB.py was written BEFORE Part A ran and was not
executed). Data: Alpaca SIP 1-min + daily bars, adjustment=all, 15 symbols, 2016-01-04..2026-10-09,
2,708 sessions, $0. Read-only market-data key; no orders, no tracked files edited.

**Deviations, written to tradingroom/exp023/deviations.md BEFORE any RV or loss was computed:**
- D1 (forced): the 2018-01-02 primary start is unreachable — SIP has no 2015 data, so 500 HAR pairs
  + 22-day regressor first exist at origin index 521. Scored window = first date HAR has its full
  500-pair window: **h=1 from 2018-01-31 (2,185 panel dates), h=5 from 2018-02-06 (2,177)**, same
  common sample for every estimator. No shorter-window HAR substituted.
- D2 (forced): a true 20-trading-day forward dry run does not fit in one session. Done instead: 20
  replayed mornings (sessions 2026-09-15..2026-10-12), each a LIVE SIP fetch made now of the
  trailing 22 sessions × 15 symbols. **20/20 succeeded, 0 retries, 5.7–7.0 s each, 22/22 sessions
  and 15/15 symbols every time.** Tests API completeness/latency, NOT forward-morning reliability.
- Interpretation choices I1–I10 (bucket construction, official open/close for the overnight leg,
  log daily returns for T40/EWMA-r², Holm-within-6 for the DATA-PASS branch, etc.) are in that file.
- Data QA (pre-Part-A, not cleaned — spec has no cleaning rule): GLD 2017-11-24 half-day has a
  +8.5%/−8.5% adjacent-bucket bad print (RV 0.0146). Thin prints: days < 300 of 390 bars — TECL 1,112,
  MTUM 661, VGT 618, SOXL 419, others ≤ 23 (kept, as specified). Mean RV / mean r² = 0.94–1.09 per
  asset (the proxy is unbiased in level). HAR fallbacks to EWMA-RV: 46 (h=1) / 65 (h=5) of ~26k origins.

**Part A (12 assets, equal-weight panel, QLIKE primary, DM NW lag 22, Holm over 6):**

| h | comparator | ratio HAR/comp [95% block CI] | DM | p Holm |
|---|---|---|---|---|
| 1 | T40 | 0.745 [0.658, 0.840] | 3.70 | **0.0007** |
| 1 | EWMA-r² | 0.892 [0.823, 0.963] | 2.73 | **0.013** |
| 1 | EWMA-RV | 0.896 [0.842, 0.961] | 2.90 | **0.009** |
| 5 | T40 | 0.713 [0.573, 0.880] | 2.28 | **0.034** |
| 5 | EWMA-r² | 0.899 [0.768, 1.046] | 1.27 | 0.206 ✗ |
| 5 | EWMA-RV | 0.946 [0.836, 1.075] | 0.81 | 0.210 ✗ |

- **C1 FAIL** (4/6; both h=5 EWMA tests fail). DATA-PASS branch also fails (it needs h=5 vs EWMA-r²).
- C2 pass, but only on significance: HAR's normalised MSE is WORSE on every comparison — h=1 ratio
  1.18–1.40, **h=5 ratio 3.1–3.9** (one-sided p_worse 0.16–0.28). The 10 worst asset-days, all
  2020-03-17..20 (VEA, UPRO, SPY), are **45.5% of HAR's entire h=5 MSE**: the level-OLS direct
  projection extrapolates the crash spike forward five days.
- C3 pass 8/9 years (lost 2021). C4 pass 11/12 assets (lost GLD).
- Reported-only: EWMA-RV vs EWMA-r² is a wash (better in 6/9 years, 6/12 assets; h=1 panel QLIKE
  0.3856 vs 0.3872) — **the intraday data alone buys nothing inside an EWMA; the gain at h=1 is the
  HAR structure on RV.** Secondary AVUV/BITO (from 2023-11): HAR best for AVUV h=1 only; worse than both
  EWMAs on both assets at h=5.
- DM statistics re-verified in pure Python (Accelerate BLAS emitted the known spurious matmul
  warnings; numbers identical to 4 dp).

**Verdict: FAIL.** Part B not run. OVERLAY_VOL_MODEL stays "trailing"; **no patch drafted**.
HAR family K = 4 run (002 FAIL, 014 PASS→UNREPLICATED, 019A FAIL, 023A FAIL; 023B never reached).
Prior check: I gave C1-vs-EWMA-RV ~35% and FULL PASS ~25%; the h=1 half came in, the h=5 half did not.

**Binding constraint:** the 5-day horizon — HAR vs EWMA-r² at h=5 has QLIKE ratio 0.899 but Holm
p = 0.21 (CI 0.77–1.05), and the variance of that difference is dominated by one week (March 2020
= 45.5% of HAR's h=5 MSE). At h=1 the same model wins all three comparisons at Holm p ≤ 0.013.

**Pattern across the HAR deaths (checked against the ledger, not memory):** 002 and 019 died because
the INPUT was daily r² (no edge to find). 023 is the first run with the right input, and the edge
appeared exactly where the literature puts it (1-day) and dissolved where a level-OLS projection is
known to be fragile (multi-day, crash weeks). This is no longer "HAR has no edge here"; it is "HAR-RV
has a 1-day edge whose multi-day form is outlier-fragile."

**Next testable structure (needs its own pre-registration; NOT a re-score of 023):**
The constraint is level-OLS fragility at h=5, which a **log-HAR** (Corsi's own robust form: OLS on
ln RV, forecast exp(ŷ + ½σ̂²)) does not reach, and the overlay recomputes its scaler DAILY, so h=1
is the decision horizon on ex-ante grounds. But the 2016–2026 panel for these 12 tickers is now
spent — choosing h=1 after seeing it pass is the EXP-013 move. So the evidence must come from
untouched series: **EXP-0xx = HAR-RV and log-HAR vs EWMA-r² on a HOLD-OUT ETF panel** (tickers not
in the 12 and not in config.ASSETS, e.g. DIA, XLK, XLF, XLE, XLV, EFA, EEM, HYG, LQD, IEF, SLV, USO;
same SIP window, same code), h=1 primary and h=5 secondary declared before fetching, plus the
original Part B overlay replay (R1/R2 unchanged) on the champion book if A passes. Cost $0; the
fetch path is proven (dry run 20/20). Power check from 023: h=1 DM t ≈ 2.7–2.9 on 2,185 dates,
so a 12-asset holdout of the same length is adequately powered; a 60-day forward log alone is not
(expected t ≈ 0.5).


---

## EXP-027 — V3 (monthly re-decision + 30% 3x cap) vs the as-live champion on the sealed 2011–2018 window

**Status:** PRE-REGISTERED 2026-10-13 23:02:04 PDT (ledger write). **PENDING AUDIT. Do not build `run_H.py`
and do not open H until an audit is ledgered under this entry.** The audit request is
`research/exp027_audit_request.md`. Written after EXP-024's D results were ledgered and
before any byte of `prices_H.parquet` was parsed by anyone. Measurement plus strategy test.
K = 1 (champion-configs family running total 14 → **15**).

### Disclosure: this is a D-informed follow-up, not a fresh idea
I have read EXP-024's full D RESULT: every arm's metrics at 0/3/5/10 bp, the gate table, the
bootstrap SDs, the turnover breakdown and the breaker-freeze finding. **The variant choice,
the gate set and the thresholds below were all chosen knowing D.** The protections against
that are:
1. D decides nothing here. D values are shown for transparency only.
2. H has never been run through any champion code. The window is pre-2019, the champion's
   regime map was tuned on 2019–2026, and the EXP-024 tester never parsed the H file. md5 at
   registration time: `prices_H.parquet` = `468a0727e2443bfcefae2fd2e4ba6e64` (290,950 bytes,
   written 2026-10-13 22:50). I computed that md5 myself and did not parse the file.
3. Every number is frozen here, and the margins come from a power argument written below.

Two further disclosures:
- **The market history is not unknown to the designer.** I know 2011–2018 had sharp
  down-days and that 3x ETFs suffered on them (Aug 2011, Aug 2015, Feb 2018, Q4 2018).
  EXP-020/025 ran challenger-book tests over 2007/2010–2026. So H is unseen *for this book's
  outputs* but not *for its regime history*. Knowing that a 3x cap helps on big down-days is
  the mechanism the test is built on. It is not a peek at an output.
- **H gets spent here.** After EXP-027, H is spent for the whole champion-cadence/cap family.
  V1 and V2 are never run on H. No future champion experiment may call 2011–2018 a holdout.

This is not a re-score of EXP-024. EXP-024 stays FAIL under its frozen rule, and nothing in
EXP-027 changes that verdict.

### Why ONE variant, and why V3
- **Mechanism, which was stated before EXP-024's D results existed:** C2 and the desk named
  two problems, (a) churn (71–93×/yr) and (b) 3x tail concentration (2026-06-05). V3 is the
  only variant that acts on both. Monthly cadence targets (a); the cap targets (b). V1 is V3
  without the cap. V2 addresses (a) only.
- **D evidence (seen, so it is selection):** on D, V3 had the lowest turnover (11.3×), the
  shallowest MaxDD (−22.2%), the only ES cut (0.844×), a better worst day, zero breaker days
  and the highest ΔSR (+0.112). V2's averaging broke RISK_OFF floors on 79 days, which is an
  implementation flaw, not noise. V1's gross ΔSR was −0.049 at 0 bp, so monthly cadence
  without the cap lost a little gross timing value.
- **Selection-bias statement:** V3 was also D's best on ΔSR among 3 tries. Its expected H
  ΔSR is lower than D's +0.112 (regression to the mean). The gates below do not rely on
  D's ΔSR size.

### Arms (engine and parameters identical to EXP-024; nothing re-tuned)
- **A0 AS-LIVE:** the daily `main.py` replica from EXP-024.
- **V3 MONTHLY + CAP30:** exactly as in `exp024_spec.md` §4 V3. Re-decision on the first
  session after each business month-end; overlay, risk gates and 2% drift gate run daily;
  Σ(TQQQ, UPRO, SOXL, TECL) ≤ 0.30 of the final target after the overlay, with the excess
  going to SHV.
- **Engine:** `research/exp024/engine.py`, unmodified (md5 `c957b0a917245a86d8e76ff59f10692f`),
  with library code from worktree HEAD d6a6f812. `git diff d6a6f81 HEAD` outside `web/`
  touches only README.md, so no champion logic has changed since D.
- **New code:** `research/exp027/run_H.py` and `score_027.py`. These import the engine.
  Result files are exclusive-create.

### The −30% drawdown breaker (the 136-session freeze in D)
- **The breaker stays ON in both arms**, as live: `config.DRAWDOWN_CIRCUIT_BREAKER = 0.30`
  on simulated net equity per cost level, blocking trades and letting holdings drift. That
  is live behaviour (`risk.check_drawdown`). Removing it from the primary comparison would
  test a book nobody runs.
- **Equity and ATH run from the first sim row (2009-01-02), as in EXP-024.** H's warm-up is
  about 2.25 y, longer than D's 1 y because the 3x ETFs have later inceptions (TQQQ 2010-02,
  SOXL 2010-03). The ATH is mostly SHV-flat during that stretch. This is disclosed, not
  changed.
- **The asymmetry cuts both ways and is accepted.** If A0 trips the breaker and V3 does not,
  G3 rewards V3 partly for avoiding a freeze. That is a real live consequence of A0's churn
  and 3x path, so it counts. If V3 trips the breaker and A0 does not, it counts against V3.
- **Attribution pair (reported, never gated):** A0_nb and V3_nb at 5 bp, with the breaker
  disabled by setting `config.DRAWDOWN_CIRCUIT_BREAKER = 1.0` at runtime. The engine file is
  not edited. All other gates stay on. The ledger must report G3's Δ both with and without
  the breaker, plus blocked days per arm. If the sign of the MaxDD advantage flips without
  the breaker, the RESULT must say so in its first line, whatever the verdict.
- Whether the breaker *should* freeze risk at the bottom is a separate engineering entry. It
  is not tested here.

### Window, data, costs, RF
- **H:** the sim runs on `prices_H` only (2009-01-02 → 2018-12-31). Metrics run 2011-04-01 →
  2018-12-31, about 1,950 sessions (≈7.75 y). The universe is the one the champion would have
  had then: no AVUV or BITO, and MTUM only once it has a full lookback. Columns with
  incomplete history drop out of the window, as in the engine.
- **Cost:** c × Σ|ΔW|. The primary rate is **5 bp**, with 0/3/10 bp as separate sims.
  Disclosed: 3x-ETF spreads in 2011–13 were probably wider than 5 bp. Understating cost
  favours A0, the high-turnover arm, so this is conservative against V3.
- **RF, a change from EXP-024 (disclosed and handled by conjunction):** EXP-024 used a
  constant 4.5%. Actual 2011–18 bill yields averaged under 1%. With unequal vols, too high an
  RF penalises the lower-vol arm, so a constant 4.5% biases ΔSR against V3. Picking one
  convention after this reasoning would be estimator-shopping. So **G5 must pass under BOTH**
  conventions: (i) constant 4.5% (EXP-024 continuity) and (ii) the realised SHV daily total
  return from `prices_H`.

### Power argument (written before H; this sets the Sharpe gate's form)
- D measured a bootstrap SD of the V3−A0 net ΔSharpe of **0.229** over N = 1,702.
- Scaled by √(N_D/N_H) = √(1702/1950) = 0.934, that gives **σ_H ≈ 0.214**. This is frozen.
  The tester's measured H SD is reported and does not move any threshold.
- **Formal non-inferiority at margin 0.10, one-sided α = 0.05:** the point ΔSR must be at
  least −0.10 + 1.645·0.214 = **+0.252**.
  - Power if the true Δ = 0 is about 12%.
  - Power if the true Δ = +0.11 (D's value) is about 25%.
- **Margin needed for 80% power:** about 0.42 at true Δ = +0.11, and 0.53 at Δ = 0. Either is
  larger than A0's whole D Sharpe (0.33). A gate at that margin would assert nothing.
- **Conclusion:** H, like D, cannot confirm Sharpe non-inferiority at any margin that matters.
  So Sharpe enters as a **harm guard** with its error rates stated below, not as the claim.
  The confirmatory claims are the ones H can resolve: turnover and cost, which are mechanical
  given the trade log, and the tail, which is partly mechanical through the cap.

The G5 guard is "point ΔSR_net ≥ −0.10". The −0.10 is EXP-024's margin, kept for continuity
and not re-tuned. Under the normal approximation, P(pass | true Δ) = Φ((Δ + 0.10)/0.214):

| true Δ | +0.11 | 0.00 | −0.10 | −0.30 | −0.45 |
|---|---|---|---|---|---|
| P(G5 passes) | 0.84 | 0.68 | 0.50 | 0.18 | 0.05 |

What this means: a V3 that is truly equal to A0 net is wrongly killed about 32% of the time.
A V3 that is truly worse by 0.30 Sharpe slips through about 18% of the time. That is the
resolution of 7.75 years. The ledger states it rather than hiding it inside a p-value.

### Gates (H only; V3 vs A0, 5 bp, breaker on; all must pass)

| Gate | Requirement | Why resolvable | What it said on D (transparency only) |
|---|---|---|---|
| **G1 turnover** | TO_V3 ≤ 0.50 × TO_A0 | Deterministic given the trade log | 11.29/68.72 = 0.164 ✔ |
| **G2 cost saved** | 5 bp × (TO_A0 − TO_V3) ≥ **1.00%/yr**, i.e. ≥ 20×/yr less turnover | Deterministic. 1%/yr ≈ 0.05–0.06 Sharpe at 17–19% vol, the smallest saving worth a code change | 0.0005 × 57.43 = 2.87%/yr ✔ |
| **G3 drawdown** | MaxDD_V3 ≥ MaxDD_A0 − 2.0 pts (no worse) | Single path, so a no-worse bound only, never a better-than | +17.4 pts ✔ (mostly the A0 breaker freeze) |
| **G4 tail (the cap's purpose)** | ES1%_V3 ≥ 0.90 × ES1%_A0 (≥ 10% smaller), **and** worst day V3 > worst day A0 | Partly mechanical: on worst days with >30% 3x targeted, the cap cuts exposure. N_H ≈ 1,950 → k = 20 days | 0.844 and −5.65% > −6.33% ✔ |
| **G5 Sharpe harm guard** | ΔSR_net ≥ −0.10 (point) under **both** RF conventions | Not resolvable as non-inferiority (see power); error rates in the table above | +0.112 (4.5% RF) ✔; the SHV-RF value was not computed on D (see the execution order) |

Reported, never gated:
- the bootstrap p of the 0.10 non-inferiority test and the 90% CI of ΔSR (21-day paired
  moving blocks, 10,000 reps, seed 27);
- the measured σ_H;
- gross ΔSR at 0 bp (on D it was +0.007, so D says cap-plus-monthly gave up no gross timing);
- ΔSR at 3 and 10 bp;
- CAGR, vol and beta;
- blocked days per reason;
- mean and max 3x weight and the days held above 30%;
- the turnover decomposition;
- the breaker-off pair;
- per-year ΔSR;
- the DSR of V3 with K = 15.

### Validity (checked before any gate; failure ⇒ INVALID or INCONCLUSIVE; H still counts as spent)
- **F1 seal:** the md5 of `prices_H.parquet` equals `468a0727…6e64`, and the md5 of
  `engine.py` equals `c957b0a9…692f`. Mismatch ⇒ INVALID, and nothing is run.
- **F2 integrity scan (no strategy output):** first-valid dates within ±1 month of the
  `exp024_spec.md` §1 inceptions. Every |daily r| > 50% is listed with its date and checked
  against a known split or reverse split. Unexplained ⇒ INVALID.
- **F3 unit checks on H's warm-up (2009–2010 rows):** the timing assertion, ΣW = 1 ± 1e-9,
  and nan_held_days = 0 in both arms over the metrics window. Failure ⇒ INVALID.
- **F4 mechanism exercised:** A0's mean 3x weight over H ≥ 5%, **and** V3's pre-cap 3x target
  exceeds 0.30 on ≥ 5% of V3 decision-days. If this fails ⇒ **INCONCLUSIVE**: the cap never
  bound, so G4 tests nothing. This authorises nothing and H is spent.

There is no live-log fidelity check on H, because no live rows exist before 2026. EXP-024's
F0 (87% strategy / 100% regime / 104.7× turnover) stands for this engine, which is
byte-identical. One open caveat: the engine does **not** reproduce live's 96% 3x book on
2026-06-05 (EXP-024 finding 2).

### Execution order
1. The audit is ledgered under this entry. Any change the audit forces is written here
   **before** step 2, with the reason, and H is still unparsed.
2. On D only (already spent, so harmless), compute and ledger the values H will not use as
   gates: ΔSR under SHV-RF, gross-Δ bootstrap SD, and the breaker-off pair. They are reported
   only. They may **not** change any threshold above.
3. F1 → F2 → F3 on H. Then run `run_H.py`: A0 and V3 at {0, 3, 5, 10} bp, plus A0_nb and V3_nb
   at 5 bp. Write `results_H_027.json` (exclusive create). Next F4, then the gates.
   `score_027.py` writes `verdict_027.json`.
4. Ledger the verdict verbatim. H is opened exactly once. No re-run is allowed for any
   reason except an engine bug unrelated to which arm wins. Such a bug is logged with its
   diff, and both runs are reported.

### Verdict
- **PASS** = F1–F4 + G1–G5.
- **FAIL** = any of G1–G5 fails. There is no PARTIAL.
- A G5-only failure is still FAIL. It is reported as "harm guard tripped at Δ = x; resolution
  is σ ≈ 0.21", not as "V3 is worse".

### Kill rule
- FAIL means the monthly+cap30 champion configuration is dead on 2011–2026 history. No other
  cap level, cadence, cost, RF convention, window split, breaker setting or metric may be
  tried under this number. A failed gate is never re-scored on another metric.
- V1 and V2 do not get H.
- Re-entry is only on **new data**: a forward paper shadow, or a pre-2009 synthetic-3x proxy
  test (as in EXP-022). Either one must be registered fresh, with a new number and a new K,
  before it is scored.

### What PASS authorises
**Only a paper shadow**, as in EXP-024 §9:
- a read-only daily logger of V3's targets, label and scaler beside the live champion;
- no orders, and no change to the champion book;
- building it needs Tyler's go-ahead.

Replacing the champion's logic needs all of the following:
- a separate pre-registered live-vs-shadow check after ≥ 60 sessions;
- **an explanation of the 2026-06-05 live-vs-replica gap (96% vs 26% 3x)**, because a replica
  that does not hold live's book cannot certify a change to live;
- Tyler's go-ahead.

FAIL, INVALID or INCONCLUSIVE authorise nothing. All accounts stay PAPER.

### Prior (stated before H)
- F1–F3: ~90%.
- F4: ~80%. Low-vol 2012–17 should keep the overlay scaler high and 3x targets large.
- G1: ~85%.
- G2: ~70%. Calm years may cut A0's label flips and scaler churn, and A0 needs ≥ ~32×/yr.
- G3: ~70%.
- G4: ~55%. The worst-day strictness fails if A0's worst H day held ≤ 30% 3x.
- G5: ~75%.
- **PASS ~25–30%.**

### AUDIT — EXP-027 (research-integrity officer, 2026-10-13 23:06 PDT)

**Verdict: APPROVED WITH REQUIRED CHANGES.** R1–R10 below bind before any byte of
`prices_H.parquet` is parsed. The designer writes them into the entry with this audit's
reasons. The auditor did not design EXP-027. The auditor did not open, load, parse or md5
`prices_H.parquet`; `ls -la` shows 290,950 B, mtime 2026-10-13 22:50, which matches the
registration. Nothing was run.

Read: the EXP-027 entry (L4047–4258), `exp027_audit_request.md` (21 challenges), the EXP-024
pre-registration and RESULT (L3210–3526), `exp024/engine.py` (md5 c957b0a9…692f, verified),
`exp024/run_D.py`, `exp024_spec.md` §1–3, `audit_2026-10-13.md`. Worktree
`agent-a755d2182dda758ab` is at HEAD d6a6f812 with a clean `git status`.

#### Headline: is this an honest new test or a rescue?
On balance it is an honest new test, with **one D-shaped loosening that has to be reversed.**
Compare EXP-027 gate by gate with the H stage EXP-024 registered *before D existed* for this
same variant on this same window:

| EXP-024 H stage, V3 (blind to D) | EXP-027 | Direction |
|---|---|---|
| G1 TO ≤ 0.50× | G1 identical | same |
| — | G2 cost saved ≥ 1%/yr | **stricter** (added) |
| G3 MaxDD no worse by > 2 pts | G3 identical | same |
| G4 ES ≤ 1.10× and G6 ES ≤ 0.90× + worst day strictly better | G4 = G6 | same (1.10× is subsumed) |
| **G2 point ΔSR_net ≥ −0.03** (4.5% RF) | **G5 point ΔSR_net ≥ −0.10** (both RFs) | **looser by 0.07 Sharpe** |
| D-stage non-inferiority (Holm) | dropped | looser (justified, see F2) |

So the "all D values pass comfortably" red flag narrows to one gate. G1, G3 and G4 were set
blind to D. G2 is a materiality floor under the pre-D expectation (EXP-024 wrote "≈2–4%/yr" at
70–90×). G5 is the only gate that is both new and looser than the pre-D bar. Its stated
justification, "−0.10 is EXP-024's margin, kept for continuity", **is factually wrong.**
−0.10 was EXP-024's *bootstrap non-inferiority margin*, a bound on the lower tail of Δ*. EXP-024's
point-estimate guard was −0.03, and −0.03 is the statistic that EXP-027's G5 actually uses.
Moving a number from one statistic to a looser one, after the stricter gate killed the variant,
is the "amend a condition once the partial result is known" pattern (CLAUDE.md, EXP-014). A new
experiment number does not change that.

#### Findings (numbered to the audit request)

**1. V3 selection (Q1).** Acceptable. The cap was part of EXP-024's hypothesis *before* D:
"A hard cap on total 3x-ETF weight additionally shrinks the tail." C2 and the desk named both
problems before D. A mechanism-only rule that addresses both named problems picks V3, not V1.
V1 addresses only churn. Choosing a variant on D does not contaminate H, because H is
independent data. It only biases the *expectation* (winner's curse), and the entry states
that. One residual: the cap's motivating event (2026-06-05) is not reproduced by the engine
(26% vs 96% 3x). So on H the cap has to earn G4 on other days. That is what F4 is for.

**2. K (Q2).** K = 1 (family 15) is adequate. The 3 D looks are already inside the 14. A
re-test of an already-counted config on new data is not a new trial in the DSR sense, so
counting +1 is mildly conservative. The bp levels are not trials, because the gate is fixed
at 5 bp. The two RF conventions are not trials, because they enter as a conjunction (see
#12). Dropping the D non-inferiority gate is justified by the *nuisance* parameter σ ≈ 0.2,
not by V3's effect size. Under σ ≈ 0.2 that gate could not have passed a true Δ of +0.15
either. That is a property of the instrument, not of the result. No change.

**3. Spending H (Q3).** Acceptable. H is the only pre-2019 window with real 3x prices. A
synthetic-3x proxy is weaker evidence (EXP-022 B). A forward shadow cannot resolve Sharpe
either, and PASS here buys only that shadow. Spending H on one variant (K = 1) instead of
three is the cheaper use. The entry correctly declares H spent for the whole family.

**4. G2 at 1%/yr (Q4).** Accepted as a materiality floor: 1%/yr ≈ 0.055 Sharpe at 18% vol.
It sits well below the pre-D expectation, so it was not reverse-engineered from D's 2.87%.
State it as an absolute number, not as a fraction of A0's turnover: G1 already supplies the
relative test. Note for the RESULT: G1 and G2 are close to mechanically certain given monthly
cadence, so passing them confirms that the mechanism ran, not that V3 adds value.

**5. G1 vs G2 (Q5).** They are not redundant. G1 is relative and G2 is absolute. G2 binds only
if A0's H turnover is below about 24×/yr. Keep both.

**6. G4 worst-day strictness (Q6).** Do **not** score G4 on cap-binding days only. That
conditions the gate on where the mechanism happened to act, and it loosens the gate after D.
The strict inequality does have a real loophole, though. If both arms hold the same book on
their worst day (D shows that this happens: A0, V1 and V2 all returned exactly −6.33%), V3 can
be "strictly better" purely because A0 paid that day's trade cost. At 5 bp with Σ|ΔW| ≤ 2,
the cost difference can be up to 10 bp. → **R4.**

**7. G3 (Q7).** Keep it as a no-worse bound. A no-worse bound cannot be "carried" by a breaker
advantage. It only stops V3 failing. Its breaker confound is handled by reporting (R6).

**8. G5 harm guard (Q8).** See the headline. The −0.10 point guard is a post-D loosening of
the pre-D −0.03 guard, and the continuity claim is wrong. Moving it to −0.15/−0.18 (Q8) would
loosen it further, with the result already known in direction, so that is rejected. A gross
guard was considered. It isolates the uncertain timing component, but adding it now would be
another post-D gate design. Restoring the pre-registered bar is the clean option. Error rates
at −0.03 with σ_H = 0.214, normal approximation:

| true Δ | +0.11 | 0.00 | −0.10 | −0.30 | −0.45 |
|---|---|---|---|---|---|
| P(pass) at −0.03 (required) | 0.74 | 0.56 | 0.37 | 0.10 | 0.02 |
| P(pass) at −0.10 (as registered) | 0.84 | 0.68 | 0.50 | 0.18 | 0.05 |

The cost is a 44% false-kill rate if V3 and A0 are truly equal. That is the price of the bar
having been set before D, and it is stated openly. A clean FAIL that redirects is worth more
than a pass on a bar that was moved. → **R1.**

**9. No PARTIAL (Q9).** Agreed. The G5-only-failure wording already reports the resolution.

**10. σ_H scaling (Q10).** The direction is correct: SD ∝ 1/√N, so σ_H = 0.229 × √(1702/1950).
D's SD is probably inflated by A0's 136-day freeze (the arms decouple completely during it), so
σ_H may be optimistic or pessimistic. With R1, σ sets no threshold and only labels the error
rates, so no change is needed. Step 2's breaker-off SD on D should be ledgered beside it.

**11. Normal approximation (Q11).** Adequate as a *description*. It gates nothing.

**12. RF (Q12).** The direction claim checks out. ∂ΔSR/∂rf = 1/σ_A0 − 1/σ_V3 < 0 when
σ_V3 < σ_A0. With D's vols, 4.5% vs ≈0.6% moves ΔSR by about −0.03 against V3. The
conjunction is at least as strict as either convention alone, so it cannot be estimator
shopping. Keep it, but SHV-RF Sharpe is new code with a free formula choice. → **R3.**

**13. Warm-up ATH (Q13). The entry's disclosure is factually wrong.** The warm-up is not
"mostly SHV-flat". By `exp024_spec.md` §1, TECL (2008-12) and UPRO (2009-06) exist in the
warm-up, along with QQQ, VGT, IWM, VEA, GLD and TLT. The engine's column rule admits TECL about
20 rows after 2009-01-02. So the book trades a 3x-tech champion through Feb–Mar 2009, the 2009
rally, May 2010 and summer 2010. The breaker can fire *inside the warm-up*, and the ATH entering
2011-04-01 is path-set and differs by arm. This is live-faithful for an account opened
2009-01-02, and its direction is unknown before H, so keep the registered design for continuity
with D. But correct the text, and report the state. → **R5.**

**14. Breaker-off mechanism (Q14). Confirmed.** `engine.risk_gate` reads
`config.DRAWDOWN_CIRCUIT_BREAKER` at call time. With 1.0, `E/ath − 1 < −1` cannot be true for
E > 0. The vol (0.90), concentration (0.70), correlation (0.85) and 2% drift checks are
untouched. `risk.py` and `backtest.py` bind the constant at import, but the engine calls
neither of them for the breaker (it calls only `backtest._detect_regime_from_prices`). The
real risk is leakage: a runtime override that persists into a later breaker-on run in the
same process. → **R7.**

**15. Breaker-driven G3 (Q15).** See #7. The first-line flip rule should cover every gate, not
only the MaxDD sign. → **R6.**

**16. 06-05 gap (Q16).** It does not need explaining before H. H compares engine-A0 with
engine-V3, and F0 (87/100/104.7×) certifies that engine against live on 54 rows. The gap
blocks *replacement*, which the entry already requires. The RESULT has to say "engine replica
of the champion", not "the champion". → R9.

**17. F4 (Q17).** The thresholds are low but non-trivial: ≥ 5% ≈ ≥ 97 sessions with the cap
binding. Raising them now would itself be a post-D choice. The definition is under-specified,
though. "V3 decision-days" could mean monthly re-decision days (~93) or daily target days, and
`simulate` never records the pre-cap 3x target. That ambiguity is a lever the tester could
resolve after seeing outputs. → **R2.**

**18. Universe (Q18).** Both arms see the same reduced universe, so the comparison is fair.
External validity for the 2026 book (AVUV/BITO) is a caveat, not a validity failure. MTUM
enters around 2014-04, after ~235 rows, for both arms. No change.

**19. Cost (Q19).** Confirmed conservative against V3 at every gate. Understated cost raises
A0's net Sharpe more (A0 has 5–6× the turnover). It also shrinks G2's measured saving. Its
only other effect is on A0's breaker timing, which can go either way and is reported.

**20. Process leakage (Q20).** F2 shows prices only, which the designer already knows the
history of. Step 2 runs on spent D. Neither can show H strategy output. Step 2 can still move a
threshold indirectly if the H scoring code is written *after* step 2. → **R8** freezes the code
first.

**21. Contamination (Q21).** "Unseen for this book's outputs" is fair, and the regime-history
knowledge is disclosed. One consequence belongs in the RESULT: G4 passing is close to
predictable from known 2011/2015/2018 crash days plus a mechanical cap. G4 PASS confirms that
the mechanism ran on real prices. It is not a discovery.

**Additional finding A (not in the request): the decision cache is keyed by integer row
position.** `Decider` caches by `("reg", i)`, `("sel", i, regime)` and `("opt", i, …)`, and it
loads any existing pickle at `cache_path`. If `run_H.py` pointed at `decisions_D.pkl`, or at a
stale H cache, it would silently replay D's decisions onto H's dates. → **R7.**

**Additional finding B: the engine's library code lives in a mutable worktree.** F1 seals
`engine.py` but not the library code it imports from
`.claude/worktrees/agent-a755d2182dda758ab/`, and that worktree could be edited or cleaned up
before H runs. md5s at audit time: config.py `b5fca78139e601eac901f5f0200d5ea8`, optimizer.py
`43ea923f5827a330bfafaac1c17f43b4`, backtest.py `2832306c0724e27a866249e29f13b47b`,
risk_overlay.py `c8b57f813aa196d2896dea071b02ad9d`; HEAD d6a6f812, status clean. → **R8.**

**Additional finding C: the re-run clause is self-judged.** "Except an engine bug unrelated to
which arm wins" lets whoever has seen H decide what counts as unrelated. → **R10.**

#### Required changes (binding before H is parsed)

- **R1 (G5):** The point guard becomes **ΔSR_net(V3 − A0, 5 bp) ≥ −0.03 under both RF
  conventions**. This restores EXP-024's pre-D H-stage bar for this variant and window. Strike
  "−0.10 is EXP-024's margin, kept for continuity". Replace the error-rate table with the −0.03
  row above. The bootstrap p at margin 0.10 and the 90% CI stay reported only.
- **R2 (F4 definition):** In `run_H.py`, for every metrics-window session where V3 has a base
  target, compute `L_pre = Σ_LEV T_pre`, where `T_pre` comes from
  `engine.final_target(B, ret_win, cap=False)` on V3's base B for that day. Save it to the H
  daily output. The cap binds iff `L_pre > 0.30 + 1e-9`. F4 clause 2 = (binding sessions ÷
  metrics-window sessions with a V3 target) ≥ 0.05. Clause 1 = mean over metrics-window
  sessions of A0's `w3x` at 5 bp ≥ 0.05. If F4 fails, the verdict is INCONCLUSIVE, the kill
  rule applies exactly as for FAIL (H spent, re-entry on new data only), and every gate value
  is still computed and ledgered.
- **R3 (SHV-RF formula):** `SR_shv = (mean(net_t) − mean(r_SHV,t)) / std(net_t, ddof=1) × √252`
  over the metrics window, where `r_SHV,t` is SHV's adjClose close-to-close return on the same
  dates from `prices_H`. This mirrors the engine's constant-RF formula exactly. Any NaN in
  `r_SHV` inside the window ⇒ INVALID.
- **R4 (G4 worst day):** "Strictly better" means **worst_V3 − worst_A0 > 0.0010** (10 bp, net,
  5 bp run). That is the largest single-day cost difference possible at 5 bp, so a difference
  that small can be pure cost. ES clause unchanged.
- **R5 (warm-up disclosure):** Replace "The ATH is mostly SHV-flat during that stretch" with:
  "TECL and UPRO trade in the warm-up; the breaker can fire before 2011-04-01; ATH at window
  start is path-dependent per arm." The RESULT reports, for each arm and cost level: blocked
  days in the warm-up, E/ATH − 1 at 2011-04-01, and whether the breaker was active that day.
  The design is unchanged.
- **R6 (flip rule):** The RESULT's first line states any gate (G3, G4 or G5) whose pass/fail
  status differs between the breaker-on primary and the A0_nb/V3_nb pair. The pair stays
  ungated.
- **R7 (run hygiene):** `run_H.py` uses a new cache path (`decisions_H.pkl`) and asserts it
  does not exist before the run, with exclusive create on save. It asserts
  `px.index.max() <= 2018-12-31`. It runs the A0_nb/V3_nb pair in a separate process, or last
  with an assert, and asserts `config.DRAWDOWN_CIRCUIT_BREAKER == 0.30` at the start of every
  breaker-on sim.
- **R8 (code freeze):** Before F1, ledger the md5s of `run_H.py`, `score_027.py` and the four
  worktree library files above. F1 checks all of them and fails INVALID on any mismatch.
  Execution step 2 (D-only extras) must use the *frozen* `score_027.py` functions. As a dry run,
  `score_027.py` applied to the existing `daily_A0_D_5.parquet` and `daily_V3_D_5.parquet` must
  reproduce `results_D.json` (Sharpe, TO, MaxDD, ES1%, worst day) to 1e-9. If it does not,
  fix the code *before* H, re-freeze, and ledger the diff.
- **R9 (run by, and wording):** H is run and scored by a tester who did not design EXP-027, as
  in EXP-024. A PASS reads: "engine-replica V3 cuts turnover/cost and the cap shrinks the tail on
  2011–18, with no harm detected at σ ≈ 0.21. V3 is **not** shown to beat the champion
  risk-adjusted."
- **R10 (re-run):** A re-run is allowed only if the bug is first reproduced on D or on a
  synthetic fixture, before any H output is re-read. Both H results are ledgered, the original
  verdict is stated in the first line, and the auditor signs off before the re-run is scored.

Expected effect of R1–R10 on the designer's PASS prior: down. G5 goes from ~75% to about
60%, so PASS falls to roughly 20–25%. That is the intended direction. None of R1–R10 makes V3
easier to pass.

*(Also saved as `research/exp027_audit.md`.)*

### RESULT — EXP-027 (independent tester, scored 2026-10-13 23:14 PDT)

**PASS. No gate flips between breaker-on and breaker-off (R6: G3, G4, G5 pass in both).** In R9's
words: the engine-replica V3 cuts turnover and cost, and the cap shrinks the tail on 2011–18,
with no harm detected at σ ≈ 0.21. **V3 is not shown to beat the champion risk-adjusted.**

The tester did not design EXP-027 or its audit. The run applied the audit's R1–R10 wherever
they conflict with the original entry: G5 at −0.03 under both RFs, F4 per R2, SHV-RF per R3,
the worst-day margin per R4. Note that the ledger entry itself has not been rewritten with
R1–R10. The tester applied them from the AUDIT block.

#### Process (in order, with file times)
1. Wrote `exp027/INTERPRETATIONS.md` (J1–J19) before any code ran.
2. Built `run_H.py` and `score_027.py`.
   - Ran the whole pipeline end-to-end on a synthetic fixture (prices_D 2019–2020 in the
     scratchpad, not H) to catch crashes.
   - Fixed one fixture-found crash before the freeze: the timing-check row 400 was out of
     range for a 1-year warm-up, so positions are now filtered to the warm-up length.
3. **R8 dry run:** frozen `score_027.py` reproduced `results_D.json` for A0 and V3 at 5 bp
   (Sharpe, TO, MaxDD, ES1%, worst day) with max |diff| = **0.0**.
4. `FROZEN_MD5.txt` written 23:12:46. It holds:
   - run_H.py `ce58d1c10e14f78bd42952027b9e0f27`;
   - score_027.py `4b5f40441651ffd5b1ee33654ac54adc`;
   - config / optimizer / backtest / risk_overlay `b5fca781… / 43ea923f… / 2832306c… /
     c8b57f81…`, which equal the audit's values;
   - worktree HEAD d6a6f812, status clean.
5. Step 2 (D extras): `d_extras_027.json` written 23:12:57, before H was parsed (H check
   ran at 23:13:08). These are ledgered below rather than in a separate pre-H block, which
   is a disclosed deviation.
6. **R7 run hygiene:**
   - `decisions_H.pkl` was asserted absent, then written with exclusive create.
   - The Decider was built with `cache_path=None`, so no pickle could be auto-loaded.
   - px range was asserted to be 2009-01-02..2018-12-31.
   - Every breaker-on sim asserted the breaker was 0.30.
   - The breaker-off pair ran in a separate process, with 1.0 asserted.
7. H was opened once. Nothing was re-run. No engine bug was found.

#### Validity
- **F1 PASS.** All 8 frozen md5s match, including prices_H `468a0727…6e64` and engine
  `c957b0a9…692f`. Re-verified in every phase and again at scoring.
- **F2 PASS.**
  - First-valid dates: TECL 2009-01-02 (the file's first row), UPRO 2009-06-25,
    TQQQ 2010-02-11, SOXL 2010-03-11, MTUM 2013-04-18. AVUV and BITO are absent.
  - No |daily r| > 50% anywhere. Max: SOXL 20.7% (2014-10-10), TECL 20.6% (2009-03-10).
  - No interior NaNs. SHV has no NaN in the window (R3 OK).
- **F3 PASS.**
  - Timing assertion holds at warm-up rows 40, 120, 200, 400 and 503.
  - ΣW error is ≤ 1.1e-11 on every row of every sim.
  - nan_held = 0 in-window for all 10 sims.
- **F4 PASS.**
  - Clause 1: A0 mean 3x weight = **35.1%** (threshold 5%).
  - Clause 2: the cap binds on **1,219 of 1,950** V3 target sessions = **62.5%** (threshold
    5%). Pre-cap 3x averaged 35.8%, max 93.1%.

#### Gates (H, 2011-04-01 → 2018-12-31, N = 1,950, 5 bp, breaker ON)

| Gate | A0 | V3 | Value | Pass |
|---|---|---|---|---|
| G1 TO ≤ 0.50× | 71.51×/yr | 11.05×/yr | ratio 0.154 | ✔ |
| G2 saved ≥ 1.00%/yr | | | 0.0005 × 60.47 = **3.02%/yr** | ✔ |
| G3 MaxDD ≥ A0 − 2 pts | −34.96% | −27.70% | **+7.25 pts** | ✔ |
| G4 ES1% ≤ 0.90× | −5.00% | −3.24% | ratio **0.649** | ✔ |
| G4 worst day > A0 + 10 bp (R4) | −9.04% (2018-10-10) | −4.71% (2015-08-24) | **+433 bp** | ✔ |
| G5 ΔSR ≥ −0.03, const 4.5% RF | 0.093 | 0.399 | **+0.306** | ✔ |
| G5 ΔSR ≥ −0.03, SHV-RF (R3) | 0.322 | 0.713 | **+0.391** | ✔ |

**Breaker-off pair** (5 bp, reported only; R6 flips: none):
- G1: 0.150.
- G2: 3.13%/yr.
- G3: +9.34 pts (A0_nb MaxDD −37.04%, V3_nb −27.70%).
- G4: ES ratio 0.649, worst day +433 bp.
- G5: +0.339 const / +0.421 SHV.

The breaker *helped* A0 on H. A0_nb's Sharpe is 0.060, against 0.093 with the breaker on.

**R5 state at the window start** (5 bp; the other cost levels are in `results_H_027.json`):
- No breaker blocks in the warm-up for any arm at any cost level.
- E/ATH − 1 on 2011-04-01: A0 −7.8%, V3 −3.7%. The breaker was inactive in both.
- In-window drawdown-blocked days: A0 = 5 / 35 / 63 / 129 at 0 / 3 / 5 / 10 bp. At 5 bp the
  first was 2016-05-02 and the last 2016-12-06. V3 = 0 at every cost level.

#### Reported only
- **Bootstrap** (seed 27, 21-day paired blocks, 10k reps):
  - p(Δ* ≤ −0.10) = 0.025.
  - 90% CI of ΔSR is [−0.034, +0.652].
  - Measured σ_H = **0.209** (frozen 0.214).
  - The CI's lower end is below zero. That is why no superiority claim is made.
- **ΔSR by cost** (const RF / SHV-RF):

  | cost | const RF | SHV-RF |
  |---|---|---|
  | 0 bp (gross) | +0.178 | +0.260 |
  | 3 bp | +0.245 | +0.328 |
  | 5 bp | +0.306 | +0.391 |
  | 10 bp | +0.380 | +0.468 |

- **Sharpe** (const RF), A0 / V3: 0.263 / 0.440 at 0 bp, 0.170 / 0.415 at 3 bp, −0.023 / 0.357
  at 10 bp.
- **CAGR / vol / β(SPY), 5 bp:** A0 4.64% / 17.98% / 0.63; V3 9.28% / 13.13% / 0.57.
- **Per-year ΔSR** (const, 5 bp): 2011 +0.81, 2012 +0.11, 2013 +0.84, 2014 +0.57, 2015 −0.07,
  2016 +1.07, 2017 +0.55, 2018 +0.35.
- **DSR of V3** (K = 15, the verdict.py formula on raw net returns): **0.613**.
- **3x exposure:**
  - A0: mean 35.1%, max 95.8%.
  - V3: mean 21.5%, max held **32.3%**.
  - V3 held more than 30% on 670 days. The cap applies to the *target*. Between monthly
    trades, holdings drift under the 2% drift gate, so held 3x can exceed 0.30. This is the
    specified mechanics, not a bug.
- **Turnover decomposition** (5 bp, ×/yr, components overlap):
  - A0: base 59.1, scaler 26.8, residual −14.4.
  - V3: base 9.5, scaler 6.5, residual −5.0.
- **Label churn:**
  - Strategy switches: A0 29.6/yr, V3 5.3/yr.
  - Regime switches: A0 26.6/yr, V3 4.4/yr.
- **Worst days:**
  - On A0's worst day (2018-10-10) A0 held 64.1% 3x. V3 held 28.3% and lost −3.41%.
  - On V3's worst day (2015-08-24) A0 held 0% 3x.
  - So G4's worst-day margin compares different dates, and partly reflects A0 being out of
    3x on 2015-08-24.
- **D extras** (step 2, spent D, reported only; `d_extras_027.json`):
  - ΔSR (5 bp) = +0.112 const and **+0.127 SHV-RF**.
  - Net Δ* SD = 0.229 (reproduces EXP-024).
  - Gross ΔSR (0 bp) = +0.007, with gross Δ* SD **0.229**.
  - D breaker-off pair:
    - A0_nb Sharpe 0.232 (A0 with breaker 0.333). V3 is unchanged at 0.445.
    - ΔSR +0.214 const / +0.225 SHV.
    - MaxDD Δ +18.4 pts.
    - ES ratio 0.848.
    - Net Δ* SD 0.237.
    - Zero blocked days in both arms.

#### Caveats that bind the reading
- G1 and G2 are close to mechanically certain under monthly cadence (audit #4). They confirm
  that the mechanism ran, not that V3 adds value.
- G4 passing was largely predictable from the known 2011/2015/2018 crash days plus a
  mechanical cap (audit #21). It confirms the cap acted on real prices. It is not a discovery.
- The comparison is engine-replica A0 against engine-replica V3. The engine does not
  reproduce live's 96% 3x book on 2026-06-05 (EXP-024 finding 2).
- H is spent for the entire champion-cadence/cap family. V1 and V2 never get H.
- **What this authorises:** only a read-only paper shadow logger of V3 beside the live
  champion, and only with Tyler's go-ahead. It authorises no orders and no change to the
  champion book.
- **Replacing the champion requires all three:**
  - a separate pre-registered live-vs-shadow check after ≥ 60 sessions;
  - an explanation of the 06-05 replica gap;
  - Tyler's go-ahead.
- All accounts remain PAPER.

Files are in `research/exp027/`:
- `results_H_027.json` (md5 f7b33d03…11c8)
- `verdict_027.json` (ce1acd86…743d)
- `checks_H_027.json`
- `d_extras_027.json`
- `run_main_H.json`
- `run_nb_H.json`
- the daily parquet files
- `FROZEN_MD5.txt`
- `INTERPRETATIONS.md`

---

## EXP-029 — Correlation-gated duration: move the challenger's TLT/IEF to T-bills while the 1y stock–bond correlation is positive

**Status:** PRE-REGISTERED 2026-10-13 (ledger write ~23:55 PDT). Written BEFORE any EXP-029 data was
downloaded or any number computed. K = 2. Build spec: `research/exp029_spec.md` (binding; if it and
this entry disagree, this entry wins and the disagreement is reported, not resolved toward PASS).
**Read beforehand:** `challenger/sleeves.py`, `challenger/backtest.py` (main, fixed engine),
`risk_overlay.vol_target_scaler`/`portfolio_vol`, `research/desk_report_2026-10-13.md` §2, the
EXP-020/022/025/026/027 entries. Not read: EXP-020's reported-only 60/40 SPY/VUSTX numbers (they exist
in this ledger; I avoided them).
**Origin:** desk report 2026-10-13: the challenger lost about 31% in the 2022 replay. TLT fell about
29% alongside QLD, because the stock–bond correlation turned positive with inflation, and the book's
duration hedge became a second long-risk position. Its correlation with the champion is 0.80.
**Crowding read:** institution-crowded (risk-parity, multi-asset desks, AQR/Man research on the
stock–bond correlation). This is a slow macro signal, not a retail one. Acceptable.

### Why this candidate, not the other two
- **Inflation/commodity hedge in ballast (rejected).**
  - It is unconditional, so it pays commodity roll/contango carry in every regime to insure one.
  - It is equity-correlated in deflationary crashes (DBC fell with stocks in 2008 and 2020).
  - Clean daily history before 2006 is a futures-roll reconstruction, which adds a second
    modelling layer.
- **Duration-neutral ballast (rejected as the primary).** It removes the hedge in the regime where
  the hedge works (TLT +14% in COVID; 2008), to fix the regime where it fails. It is the
  static-cash control here (C1/C2), not the candidate.
- **Correlation-adaptive ballast (chosen).**
  - It is the only one of the three whose mechanism names *when* duration hedges and when it
    doesn't. The sign of the stock–bond correlation is set by whether inflation or growth news
    dominates (Campbell–Sunderam–Viceira; Ilmanen 2003; AQR 2023), and those regimes last years.
  - It is testable as a premise (does trailing sign predict next-month sign?) before any strategy
    is built, which is where seven of this ledger's deaths happened.
  - One parameter pair (252d, threshold 0), fixed now, not gridded.

### Hypothesis
Part A (premise, K = 0): the trailing 252d correlation of daily equity and long-bond returns, measured
at month-end, predicts the next month's realised stock–bond correlation, and flags the months when long
bonds fail to hedge equity drawdowns.
Part B: in the challenger book (live config, fixed engine), moving TLT (V1), or TLT and the core IEF
cushion (V2), to T-bills on month-ends when that correlation is > 0:
- loses less in "2022-like" months (stocks and bonds both down);
- keeps the hedge in flight-to-quality months;
- costs no more than 0.03 net Sharpe;
- beats simply holding less duration all the time.

### Why it could fail (stated before data)
- **Lag.** A 252d window is slow. My prior is that it turned positive part-way into 2022, after much
  of the bond loss. Not computed.
- **Forgone rallies.** Positive-correlation regimes include bond rallies *with* stocks (1995 long
  bonds roughly +30%). The variant sits in T-bills through them, and G1 bites there.
- **Missed flight to quality.** Correlation can be positive going into a flight-to-quality shock
  (1998 LTCM?), which is when the hedge was needed (G4).
- **Engine quirk.** `portfolio_vol` normalises risky weights, so removing duration raises
  normalised vol, and the scaler de-risks the rest of the book. That makes part of any S+
  improvement just "less exposure". It stays in the test because the live bot would behave the
  same way. Its size is measured by the V′ attribution diagnostic.

### Arms (one engine; only the post-map differs)
- **A (baseline):** live config (core .45 / lowvol .28 / ballast .27, TV 16%, trailing, DRIFT 2%,
  BME), on a copy of main's `run_book` with three permitted edits:
  - E1: CASH earns the actual T-bill (SHV; French RF in P), not a flat 2%. All arms.
  - E2: TCOST 5 bp primary, 10 bp sensitivity.
  - E3: the variant post-map.
- **V1:** when G = 1 at a base rebalance, w[TLT] → CASH (GLD unchanged).
- **V2:** V1, plus w[IEF] → CASH.
- **C1, C2 (controls, never deployable):** the V1 / V2 map applied at every rebalance.

Signal:
- ρ_t = Pearson correlation of daily EQ and LB returns over the 252 rows ending at BME close t.
- G_t = 1 iff ρ_t > 0. NaN (fewer than 240 pairs) ⇒ 0.
- EQ/LB = SPY/TLT in D, and French Mkt / BOND30 in P.
- Decisions are made at day-t close and earn from t+1 (fixed engine).
- No hysteresis, no other lookback or threshold.

### Windows and contamination (honest)
- **P, the holdout: 1990-01-02 → 2006-12-29**, scored on proxies.
  - QQQ ← ^NDX; QLD ← 2×^NDX − cash − 0.95%.
  - IEF/TLT ← synthetic 10y/30y par bonds from ^TNX/^TYX (EXP-022 construction).
  - XLP/XLU/XLV ← French daily industries NoDur/Utils/Hlth.
  - GLD ← daily gold spot (source hierarchy in spec §2.3).
  - CASH ← French RF.
  - VUSTX is NOT used (EXP-022 rejected it for distribution artifacts). This overrides the brief's
    suggestion, with that reason.
  - The sim warms up on 1987–1989 data; those strategy returns are never scored.
- **D, the guard: 2007-07-02 → 2026-10-09**, Tiingo ETFs.
- **What has seen what:**
  - The challenger config was chosen on 2005–2026 data (EXP-021 era, plus EXP-025/026 on 2007–26),
    so D is contaminated for the BOOK. 2022 is the event that motivated this experiment, so D
    carries no evidential weight on the stress question and is a no-harm guard only.
  - No challenger-book or ballast result has ever been computed before 2005 in this repo.
  - EXP-026 called "the 1990–2004 proxy set" spent. It was spent by EXP-022 for the
    overlay-estimator family, on the champion proxy. It is unspent for this family.
  - EXP-020 did print a reported-only 60/40 SPY/VUSTX monthly series over 1993–2026. A
    stock-plus-long-bond aggregate for P exists in the ledger (unread by me). The gated book does
    not exist anywhere.
  - **P is sealed to the code, not to the strategist.** Public history is in my priors: the
    positive correlation in the 1990s, the 1994 bond crash, the 1995 bond rally, the 1998 flight to
    quality. So G3 (stress) on P is partly predictable from 1994, and should be read as softer than
    its nominal p. **G1 (does the 1995–97 rally cost too much Sharpe) and G4 (1998) are the
    genuinely uncertain gates.**
  - Expected regime count in P is low: positive through about 1997–98, negative 2000–06. Part A
    may effectively compare two eras. The tester reports the G sign-change count, with dates.
- **Reserved, untouched:** everything before 1987. EXP-029 loads nothing earlier. 1962–1986 holds
  the 1970s–80s positive-correlation regime and is kept as the confirmatory holdout for any
  successor.

### Decision rule
**Part A (window P; FAIL ⇒ STOP, K = 0 spent).**
- A1: mean next-month realised correlation | G = 1 minus | G = 0 is ≥ 0.20, and its 95% block-bootstrap
  lower bound is > 0.
- A2: in equity-down months, mean LB return | G = 1 < mean | G = 0.
- A3: ≥ 24 month-ends per group, and ≥ 6 equity-down months per group.

Part A is ledgered before Part B runs.

**Part B gates** (per variant, window P, 5 bp; all must hold):
- **V0 (power, else INCONCLUSIVE):** ≥ 12 S+ months in P, ≥ 6 of them with G = 1.
- **G1 Sharpe non-inferiority:** ΔSh (monthly, excess over T-bill) ≥ −0.03, AND the paired
  block-bootstrap one-sided 97.5% lower bound > −0.10 (Bonferroni K = 2), AND the point estimate
  is ≥ −0.03 at 10 bp.
- **G2 MaxDD:** no more than 1.0 pt deeper than A (daily equity).
- **G3 2022-like stress:**
  - S+ = calendar months with equity < 0 AND long bond < 0 (defined on asset returns, now).
  - mean(R_v − R_A) over S+ > 0, sign-flip permutation p significant under Holm (K = 2,
    α = 0.05);
  - AND Σ(R_v − R_A) over S+ ≥ +1.0 pt.
- **G4 hedge preserved:** S− = equity < 0 AND long bond > 0. mean(R_v − R_A) over S− ≥ −0.20
  pt/month.
- **G5 timing beats static:** Sh_V1 ≥ Sh_C1 and Sh_V2 ≥ Sh_C2 (point). If this fails, the finding
  is "hold less duration", which is unregistered: logged as a lead, authorising nothing.
- **G6 ETF-era guard (D):** ΔSh ≥ −0.05 AND MaxDD not deeper by more than 1.0 pt.

**Validity (spec §4; failure ⇒ INVALID):**
- F0: reproduces `backtest.run_book` exactly with the edits off.
- F1: P weights are sane.
- F2: causality perturbation test.
- F3: the post-map is exact.

**Reported, not gated:**
- the named episodes, including D's 2022-01-03 → 2022-10-12;
- the V′ attribution (scaler held at A's path);
- DSR at K_family = 10 (challenger 4 + EXP-026's 3 + EXP-025's 1 + EXP-029's 2);
- turnover, G flips, mean scaler by regime, and calendar years.

**Verdict:**
- PASS per variant = Part A ∧ F0–F3 ∧ V0 ∧ G1–G6. If both pass, both are shadowed (no pick by
  Sharpe).
- **PASS authorises only** a read-only paper shadow logger beside the live challenger, with
  Tyler's go-ahead. It authorises no change to `sleeves.py` and no orders. Adoption needs a
  separate pre-registered live-vs-shadow check after ≥ 60 sessions, plus Tyler.
- **Kill rule (FAIL):** P is spent for the duration/ballast family. None of these may be re-tested
  on P or D:
  - another lookback (63/126/504d);
  - a non-zero threshold or hysteresis;
  - QQQ as the equity leg;
  - another replacement asset (SHY, TIPS, gold, commodities).

  Each is a new experiment that cites EXP-029 and uses forward data or the reserved pre-1987
  window.

### Predictions (written before data)
- Part A PASS: about 70%. The correlation regimes are persistent; the risk is A3 power or a
  two-era-only comparison.
- Part B: V1 PASS about 25%, V2 PASS about 20%.
- Most likely V1 failure: G3's Σ ≥ 1.0 pt, because TLT is only about 13% of the book.
- Most likely V2 failure: G1, because IEF is in cash through the 1995 rally whenever core is
  de-risked; and because the core is rarely de-risked during G = 1 periods in the 1990s, V2 may
  add little over V1.
- G5 should pass in P (long duration earned a large premium in 1990–2006, so static cash is a
  weak control). D's 2022 improvement: modest, because of the lag.

### AMENDMENT 1 — pre-data (strategist, system clock 2026-10-13 23:59 PDT)
Written after the tester's BLOCKED status entry (ledger end; INTERPRETATIONS #29–31). What existed
when I wrote this: D-window validity output (F0, F2, F3) and the P non-gold integrity scan.
`research/exp029/` holds no P return, ρ-conditioned statistic, Part A value or arm result. I did
not open `integrity_nogold.txt` beyond the status summary. Neither ruling depends on any outcome.

1. **P T-bill: approved, applied to every P day.**
   - Use French **monthly** RF, spread evenly over that month's trading days as a daily simple
     rate: (1+RF_m)^(1/n_m) − 1.
   - It replaces daily RF everywhere it is used in P: CASH accrual, the QLD financing leg, and the
     Sharpe T-bill. The Sharpe leg was already monthly RF, so P is now internally consistent.
   - The §2.4 RF check becomes: monthly RF > 0 in ≥ 95% of P months. Report the count.
   - Reason: the daily file's 0.01% rounding is a units artifact, not a rate. The monthly file has
     12× the relative resolution.
   - D is unchanged (SHV / TB3MS).
2. **Gold.**
   - **(a)** Preferred: Tyler downloads the WGC daily file manually. It is clean; the login is only
     an access gate.
   - **(b)** Also acceptable, as an equal alternative and not a fallback ranking: any other
     **daily LBMA gold PM (or AM) fix in USD** file that Tyler obtains himself (for example from
     LBMA's own site), provided it passes §2.3's cross-checks (GLD ρ ≥ 0.95, GC=F ρ ≥ 0.85).
     These sources are still excluded:
     - Bloomberg (validation only);
     - miners and silver;
     - GC=F before 2000-08;
     - monthly series interpolated to daily (they would fake the 60-day vol that drives ballast's
       inverse-vol weights).
   - **(c)** If no such file is obtained, §2.3 rule 3 does **not** apply. I agree with the
     tester's reading: rule 3 was written for data that does not exist, not for data that exists
     behind a login.
     - Truncating to about 2001+ would spend the sealed window on a stretch that is almost all
       G = 0, where V0 is very likely to fail. That trade is not worth making.
     - Status stays **BLOCKED**. P stays sealed and unspent, Part A is not run, and nothing on D
       is scored or ledgered as a verdict.
     - No substitute gold proxy may be introduced later without a new pre-data amendment written
       before any P statistic exists.
3. **Unchanged:** every gate, arm, window, threshold, seed and K = 2. The amendment touches only
   data plumbing.

### AMENDMENT 2 — pre-data (strategist, system clock 2026-10-14 00:05 PDT)
**What I had read when I wrote this:**
- tester status 2 (ledger end);
- its quoted cross-check numbers: daily ρ 0.600 / 0.566, weekly ρ 0.92 / 0.87, lag+1 ρ 0.36 / 0.42.

No P statistic exists, and I have computed nothing. The failure is fix-time asynchrony: the London
fix vs the NY close. It is not dirty data. My §2.3 daily-ρ threshold assumed a close-timed source.
That was a design error; it is mine, and it is disclosed.

1. **No lagging.** Using fix_{t+1} as the close-t proxy is a look-ahead and is rejected. Gold enters
   P as the fix on day t.
   - That carries no look-ahead, because the fix is struck before the NY close on t.
   - It is timing-asynchronous with the other P series. That is disclosed as a known property of
     the GLD proxy.
2. **Replacement identity check** (it replaces §2.3's daily ρ; data-identity only, not a strategy
   gate):
   - **(a)** weekly Fri→Fri return ρ ≥ 0.90 vs GLD (2004-11-19 → 2006-12-29), and ≥ 0.85 vs GC=F
     (2000-09 → 2004-10).
     - Disclosed: these were set **after seeing** 0.92 / 0.87, so (a) is known to pass.
     - It is kept only as a floor against a gross data error.
   - **(b)** Not yet computed, and binding: month-end return ρ ≥ 0.97 vs GLD and ≥ 0.95 vs GC=F,
     over the same spans.
     - Reasoning: timing noise of about a third of a day's move is small against a month's move.
       Two clean series of the same metal should agree almost perfectly at monthly frequency.
   - Fail (b) ⇒ EXP-029 **INCONCLUSIVE-data** (see 4).
3. **Sizing study, before P opens** (non-P data only).
   - **Data.** Each arm is simulated twice, at 5 bp: D-real (Tiingo GLD) and D-fix (the GLD column
     replaced by WGC fix-timed gold, minus 0.40%/yr, ffilled to the D calendar).
     - The sim runs from 2005-01-03, and the scored span is 2007-07-02 → 2019-12-31. That span
       avoids 2022, which motivated the experiment.
     - If Tyler's file stops at 2006, the same WGC file is needed through 2019-12-31.
   - **Arms:** A, V1, V2, C1, C2, with engine, arms and seeds exactly as registered.
   - **Write only substitution deltas** (fix − real) to `research/exp029/sizing.json`. Arm-level
     Sharpe and MaxDD are not ledgered.
   - **Tolerances.** All must hold. They are set from the gate margins, not from data:
     - **T1** Arm level: |ΔSh| ≤ 0.05 for each arm (monthly excess-Sharpe definition).
     - **T2** Gated contrasts, the binding check: |Δ(Sh_x − Sh_y)| ≤ **0.015** for each pair
       V1−A, V2−A, C1−A, C2−A, V1−C1 and V2−C2. That is half of G1's −0.03 point margin.
       - V−A pairs will be near 0 by construction, because G is mostly 0 over 2007–19.
       - **C−A is the real probe.** The always-mapped arms exercise exactly the duration-to-cash
         swap under fix-timed gold.
     - **T2b** |Δ(MaxDD_x − MaxDD_y)| ≤ 0.30 pt for the same pairs (G2 tolerance 1.0 pt).
     - **T3** Scaler path: for each arm, mean_t |s_fix − s_real| ≤ 0.01, and the 99th percentile
       ≤ 0.05.
   - **Reported, not gated:**
     - 40-day gold–SPY and gold–QQQ correlation, fix vs real (mean and the ratio of means);
     - mean |Δ gold weight| in ballast;
     - per-arm ΔMaxDD;
     - share of scored months with G = 1.
4. **Decision.**
   - **(b) and T1–T3 all pass** ⇒ WGC fix-timed gold is accepted on P, and the run resumes at F1
     on P exactly as registered.
   - **Any of them fails** ⇒ **EXP-029 INCONCLUSIVE-data**:
     - P stays sealed and unspent;
     - no P statistic is computed;
     - K spent = 0;
     - there is no second sizing run, no relaxed tolerance, and no alternative gold construction
       for P.
   - **Successor:** this family moves to forward data, via the shadow logger only if Tyler wants
     it. The pre-1987 window has the same gold-timing problem, and any use of it needs its own
     registration that cites this amendment.
5. **Contamination, disclosed.**
   - The sizing run shows the tester (not me) arm-level D results for 2007–2019, which overlaps
     G6's guard window.
   - G6 already carries no evidential weight, so it stays as registered. The tester notes in the
     result that G6 was partly previewed.
6. **Unchanged:** every gate, arm, window, threshold, seed and K = 2, apart from the §2.3
   cross-check replaced in item 2.

### Result
(pending: independent tester per `research/exp029_spec.md`)

---

## EXP-028 — Deep-ITM QQQ LEAPS in place of leveraged ETFs (QLD in the challenger core; TQQQ champion-style)

**Status:** PRE-REGISTERED 2026-10-13 ~23:55 PDT (ledger write; appended after EXP-029 because
others append). Written BEFORE any EXP-028 option quote was downloaded or any EXP-028 number was
computed. The only Databento calls made were `metadata.get_cost` (free); $0.00 spent.
Build spec: `research/exp028_spec.md` (binding; if it and this entry disagree, this entry wins
and the disagreement is reported, not resolved toward PASS).
**K = 2** (H1, H2). Bonferroni α = 0.025 each. Challenger family 10 → **11** (H1). Champion
family 15 → **16** (H2). R1–R3 are reported only: no verdict, no promotion, so no K.
**Read beforehand:** `challenger/sleeves.py`, `challenger/backtest.py`, EXP-010 and EXP-011
(real OPRA quotes via Databento `cbbo-1m`), `research/databento_audit.md`.

### Origin
Tyler's idea, 2026-10-13: replace leveraged-ETF exposure with long-dated deep-ITM calls of the
same target dollar delta. The claim is that this avoids daily-reset volatility drag and caps
the loss at the premium paid.

### Hypothesis (one sentence, before data)
Holding QQQ calls ~12 months out at Δ ≈ 0.80, sized monthly to the LETF's dollar delta, with
the freed cash in T-bills, beats the leveraged ETF (QLD at 2x, TQQQ at 3x) net of real OPRA
bid/ask, on the same exposure schedule.

### Mechanism, and the prior against it (stated honestly)
- **For.** The LETF pays a 0.95% expense ratio plus swap financing above T-bills, and it is
  short gamma at *realized* variance through its daily reset. That loses money in choppy,
  mean-reverting markets. The LEAPS arm earns T-bill interest on the ~60–80% of the slice not
  spent on premium. Its own leverage resets only monthly, and its loss in a gap is capped at the
  premium.
- **Against.** A long call is long gamma paid for at *implied* variance. This ledger has
  confirmed the variance risk premium four separate times (EXP-005, 007/007b, 009, 011), so
  the buyer of convexity pays that premium on average. Deep ITM (Δ 0.8) keeps vega per dollar of
  delta small, but not zero.
- **"Avoiding vol drag" is partly a misconception.** For iid returns, a monthly-resized levered
  position and a daily-reset one have similar expected drag. The real difference is
  intra-month autocorrelation (mean reversion favors monthly) plus explicit costs. So this is a
  financing-cost race: LETF fees + swap spread + daily-reset path cost against VRP on a small
  gamma + option bid/ask + roll turnover.
- **Prior:** a near-wash, with a small expected effect.
- **Structural risk for H1.** The ramp switches the QLD slice on and off as QQQ crosses +3.3%
  above its 200-day MA. Every switch costs B a full option round trip, while A pays only 10 bp.

### Feasibility findings already established (no data bought)
1. **Data.** Databento `OPRA.PILLAR` `cbbo-1m` is the only bid/ask schema covering 2013-04 →
   today; `cbbo-1s`, `tcbbo` and `cmbp-1` start 2023–2025. Quoted via `metadata.get_cost`:
   - one LEAPS contract, continuous cbbo-1m: **$0.0075 per 6 months** (2014 and 2021) and $0.0146
     per year (2025–26);
   - QQQ parent definitions: mean **$0.0045**/day in P and $0.0131/day in H;
   - SPY parent definitions: mean $0.0085/day in P and $0.0165/day in H.

   **Full plan: ≈ $1.6** with lazy definition pulls, **≤ ≈ $4.0** if definitions are pulled on
   every month-end. Hard stop is $9.50 against Tyler's $10. Nothing usable is cached:
   `exp010_cache` holds short-dated quotes, plus QQQ/SPY definitions only for 2020-08 → 2026-06
   (H-window, reusable only on an exact date match).
2. **Implementability, the binding constraint even if the backtest passes.** The challenger's
   equity is **$1,014.82** (`challenger/daily_log.csv`, 2026-10-13), so its QLD slice is about
   $228 and carries about $457 of QQQ dollar delta. One QQQ Δ 0.8 LEAPS carries about **$38k of
   delta and costs about $8k**. Listed options cannot be fractional, so this is about 80× the
   slice's delta and 8× the whole account. The champion is the same ($915.65). A whole-contract
   book that tracks the ramp within ±10% needs a core sleeve of roughly $0.85M+.

### Instrument rules (frozen; detail in spec §3–5)
- **Underlying:** QQQ for H1 and H2; SPY for R1. Standard monthly third-Friday expiries only.
- **Tenor:** the eligible expiry with DTE closest to 365, inside [270, 455].
- **Strike:** delta closest to **0.80**, which must lie in [0.70, 0.90]. Delta comes from
  BSM-inverted IV on the closing mid, with r = DTB3 and q = trailing dividend yield. The quote
  must have (ask − bid)/mid ≤ 10%.
- **Roll** at DTE ≤ 180 (≈ 2 per year). **Re-strike** if Δ leaves [0.65, 0.93].
- One shared "chain" contract per underlying, defined on every execution day.
- **Sizing:** target dollar delta D\* = 2·w_QLD·NAV for H1 (w_QLD from the unmodified
  `sleeves.core_sleeve`) and 3·NAV for H2. Contracts n = D\*/(Δ·100·S), fractional.
  Resize at monthly executions only if |D_held − D\*|/NAV > 0.02.
- **Freed cash:** SHV (actual total return). Premium is capped at the slice; shortfall is logged.
- **Fills:** buy at ask, sell at bid, at the last valid 1-minute NBBO before 16:00 ET. Fees
  $0.05 per contract. Daily marks at mid (R3 marks at bid).
- **ETF legs:** 10 bp, the backtest's TCOST; 1 bp on SHV.
- **Timing:** signal from close d (BME), execution at close d+1.
- Both arms use the same holdings-based engine. A differs from B only in the levered instrument.

### What is compared
| Label | Arm A | Arm B | Status |
|---|---|---|---|
| **H1** | challenger core sleeve standalone (budget 1.0, same ramp): QQQ + QLD + IEF | same, with QLD → LEAPS + SHV | gated, primary |
| **H2** | 100% TQQQ | QQQ LEAPS at 3x dollar delta + SHV | gated, secondary |
| R1 | 100% UPRO | SPY LEAPS at 3x | reported only; runs only if spend < $6 |
| R2 | — | H1 with whole contracts at $1M and at live size | reported only (implementability) |
| R3 | — | H1/H2 marked at bid | reported only |

The full challenger book (vol overlay) is not run. The overlay rescales daily, which would force
daily option trades. Its book-level effect is roughly 0.45 × the sleeve's μ_d × the mean
scaler, and is reported only as that arithmetic.

### Windows
- **P (gates):** decision dates 2013-07-31 → 2020-05-29, metrics 2013-08-02 → 2020-06-30.
  Includes the 2015–16 chop, Q4 2018 and the COVID crash.
- **H (sealed holdout, one look):** 2020-07-31 → 2026-09-30, including the 2022 bear. Opened
  only for a hypothesis that passes every P gate. Starts flat.
- **Disclosure:**
  - QQQ LEAPS quotes in both windows have never been touched by this ledger. EXP-010 used
    short-dated QQQ quotes 2020-07+; EXP-011 used 30-day SPY and single-name quotes 2013–19.
  - The QQQ/QLD/TQQQ **price paths** are not unseen: challenger and champion backtests have run
    2007–2026. H is sealed for this comparison's outputs, not for market history. I know 2020-03
    and 2022 were bad for 2x/3x ETFs.

### Gates (P; each of H1 and H2 separately; frozen)
- **G1 edge:** μ_d = 252·mean(r_B − r_A) > 0 **and** a one-sided stationary block bootstrap
  (mean block 21, 10k reps, seed 28) gives p < **0.025**.
- **G2:** ΔSharpe (B − A, excess over SHV) ≥ **+0.05**.
- **G3:** MaxDD_B no more than **2.0 pts** deeper than MaxDD_A.
- **G4 tracking:** daily β to QQQ, β_B/β_A ∈ **[0.90, 1.10]**, **and** fallback months (chain
  empty or untradeable for 5 days, so B holds the LETF) ≤ **5%** of months with exposure.
  This stops B from "winning" by simply being under-exposed.
- **G5 cost:** option spread + fees ≤ **0.50% per year per unit of target dollar delta /
  NAV**, **and** μ_d > 0 when every option half-spread is multiplied by 1.5.
- **G6 coverage:** ≥ 95% of held contract-days have a valid close quote, and ≥ 95% of option
  trades execute on schedule. Failure ⇒ **INCONCLUSIVE**: K is still spent and nothing is tuned.
- **Validity V1–V5** (spec §7): TQQQ identity, a causality perturbation, no mid fills, sizing
  exactness, OCC sanity. Failure ⇒ INVALID, then a fix logged as v2.
- **H confirmation:** μ_d > 0 (point estimate) ∧ ΔSR ≥ 0 ∧ G3 ∧ G4 ∧ G6. Failure ⇒ "does not
  replicate".

**Power note (written before data).**
- The tracking error of d is unknown. The minimum detectable μ_d at one-sided 2.5% over 7 years
  is ≈ 2·TE/√7 ≈ 0.76·TE.
- If TE ≈ 2%/yr at the sleeve level, only effects of about 1.5%/yr or more can pass G1. The
  plausible effect (well under 1%/yr) would most likely FAIL G1 while being slightly positive.
- That is accepted: this design prefers a false negative.
- The pre-registered reading of such a result is **"no detectable difference; QLD retained"**.
  It is not "LEAPS lose". Either way, QLD is implementable at this account size and LEAPS are not.

### Crowding read
- **The strategy itself is retail-crowded.** "Stock replacement with deep-ITM LEAPS" and the
  PMCC are staples of r/options. Under Tyler's criterion this would be a reject *as an alpha
  idea*.
- **It is not one.** It is a choice of financing and implementation for exposure we already
  hold. Crowding does not decay a financing spread the way it decays a signal.
- **Where crowding does bite:** retail call-buying lifts call IV (2020–21). That raises the
  price the B arm pays, and it sits in the "against" mechanism above.
- **Institutional analogue:** a delta-one desk choosing between swap, futures and listed-option
  leverage. That is an acceptable framing, [removed: career note].

### What PASS authorizes
- **H1 PASS (P and H):**
  - a **read-only, virtual paper shadow logger** of B1 beside the live challenger: fractional
    contracts, marks from option quotes, **no orders of any kind**;
  - only with Tyler's go-ahead.
- **Why no paper orders:**
  - Alpaca paper does support options, including long calls at level 1–2.
  - But the account cannot hold even one contract against a $228 slice (feasibility 2).
  - Real paper option orders need a separately pre-registered resize of the paper account (core
    sleeve ≳ $0.85M), plus a pre-shadow check that Alpaca lists QQQ expiries ≥ 270 DTE.
  - No change to `sleeves.py`.
- **H2 PASS:**
  - a ledger note to the champion queue only;
  - the champion's SOXL/TECL have no comparably liquid long-dated option;
  - no champion change.
- All accounts remain PAPER.

### Kill rule
- **FAIL of a hypothesis on P:** the LEAPS-for-LETF family is killed for that comparison.
- None of the following may be re-tested on P or H:
  - another delta (0.70/0.90);
  - another tenor (6/18/24 months);
  - another roll DTE or re-strike band;
  - the spread filter;
  - mid fills;
  - SPY in place of QQQ for the core;
  - a hysteresis on the ramp to cut round trips.
- H is **not opened** on a P fail, so it stays sealed for a structurally different future idea
  (e.g. options on the *signal*, not the leverage), which must cite EXP-028.
- Do not go looking for the parameter set that passes. Every one of the above is a free
  variable, and anything can be made to pass.

### Predictions (written before data)
- **H1 P-PASS:** ~12%.
  - Most likely failure: G1, from low power plus the ramp-toggle round trips.
  - Next most likely: G5 in 2013–15, when deep-ITM QQQ LEAPS spreads were wider.
- **H2 P-PASS:** ~25%.
  - The 3x daily-reset path cost in 2015–16 and Q4 2018, and B2's capped loss in March 2020,
    favor B.
  - VRP paid on 3x dollar delta works against it.
  - A G3 pass is likely; the G1 p-value is the risk.
- **G6 INCONCLUSIVE on QQQ:** ~10% (2013–14 deep-ITM LEAPS quote gaps).
- **R2:** the live-size challenger rounds to **0 contracts in 100% of months**. This is
  certain, and is recorded so nobody rediscovers it as a surprise.

### Result
(pending: independent tester per `research/exp028_spec.md`)

---

## EXP-029 — tester status (2026-10-14 ~00:30 PDT): BLOCKED on the gold source. No P number computed; P unspent.

Independent tester, per `research/exp029_spec.md`. Interpretations written first:
`research/exp029/INTERPRETATIONS.md` (#29–31 cover this block).

**Done (no Part A or Part B statistic exists on P):**
- D pulled fresh (Tiingo, 2005-01-03 → 2026-10-13, `research/exp029/px_D.parquet`).
- Engine copy `research/exp029/engine.py` (E1/E2/E3 only, plus off-by-default logging and the §7 V′
  `force_s` hook). **F0 PASS:** max |Δ daily ret| vs main's `backtest.run_book` = 0.0 over 5,479 rows.
- F2 (20 BMEs, seed 29) and F3 (244 BMEs, all four mapped arms) PASS on D at the weight level.
  F1–F3 on P need GLD and are not run.
- P non-gold proxies built from 1987-01-02 (`integrity_nogold.txt`). ^TYX max identical run = 4
  ⇒ no DGS20 splice. Bond builder unit test: 1 bp rise ⇒ −0.1382% vs −DV01 −0.1384%. ρ computable
  at 205/205 month-ends 1989-12 → 2006-12. Five BME weekdays are market holidays (1991-03-29,
  1993-05-31, 1999-05-31, 2002-03-29, 2004-05-31); the engine skips those months' rebalances.

**Binding constraint: gold before 2004-11.**
- Source 1, Stooq XAUUSD, now serves a JavaScript proof-of-work bot check, not a CSV. Not bypassed.
- Source 2, the WGC daily file: 403, "You must be logged in to download this file". The tester
  may not create accounts or log in, and did not scrape the page's internal chart API to get
  around the gate.
- Rule 3 (truncate P's scored start to about 2001-09 on GC=F-era gold) was NOT applied.
  - Its trigger is "neither source gives clean daily data". WGC's data is clean; only the tester's
    access is blocked.
  - Rule 3 is irreversible. It would spend 2001–2006 of the sealed holdout on a window that is
    mostly G = 0, where V0 (≥ 6 S+ months with G = 1) very likely fails.

**Second integrity finding (needs a pre-declared fix before the run):**
- French daily RF is 0.00 on all 397 days from 2003-01 to 2004-07. The file is rounded to 0.01%,
  and the true rate was about 1%/yr, or 0.004%/day.
- RF > 0 on 92.1% of days, which fails spec §2.4's > 95% check.
- This under-credits CASH, the QLD financing leg and the Sharpe T-bill for 19 months.
- **Suggested fix** (for the strategist to pre-declare; the tester has not applied it): use French
  *monthly* RF, spread evenly over the month's trading days, for every P day.

**Next testable step (unblocks in about 5 minutes):**
1. Tyler, with a free gold.org login, saves "Gold price averages in a range of currencies since
   1978" (.xlsx) to `research/exp029/raw/wgc_gold.xlsx`.
2. The strategist rules on the RF fix.
3. The tester resumes at the gold cross-checks (GLD ρ ≥ 0.95; GC=F ρ ≥ 0.85), then runs
   F1 → F3 on P, Part A (ledgered), Part B and G6, exactly as pre-registered.

Alternatively, Tyler rules that rule 3 applies, and it is applied as written.

## EXP-029 — tester status 2 (2026-10-14): still BLOCKED. The WGC daily gold failed the pre-registered cross-checks. P unspent.

Resumed per Amendment 1:
- Tyler's `raw/wgc_gold_daily.xls` is in use: 5,217 USD rows from 1987-01-01 to 2006-12-29, none
  dropped.
- French monthly RF is spread geometrically over each month's trading days.

**Cross-checks** (§2.3: daily simple returns, ffilled to the P calendar; `research/exp029/gold_xcheck.json`):

| check | ρ measured | n | required | result |
|---|---|---|---|---|
| vs GLD, 2004-11-19 → 2006-12-29 | 0.600 | 532 | ≥ 0.95 | FAIL |
| vs GC=F, 2000-09 → 2004-10 | 0.566 | 1,044 | ≥ 0.85 | FAIL |

Under §2.3 the source fails, and under Amendment 1(c) the status stays BLOCKED:
- no F1–F3 on P;
- no Part A;
- no Part B;
- no ρ/G statistic on P computed.

**Binding constraint: fix-time asynchrony, not dirty data.**
- Data-quality diagnostics only:
  - lag-1 ρ (gold leads by a day) ≈ −0.03, so the dates are aligned;
  - lag+1 ρ is 0.36 (GLD) and 0.42 (GC=F);
  - weekly ρ is 0.92 and 0.87;
  - spot rows such as 2005-03-01 → 03-10 track GLD closely.
- The LBMA fix is struck in the London afternoon and GLD/GC=F settle at the NY close. About a third
  of each day's move falls into the next fix's return.
- So **any** daily LBMA fix, AM or PM, from any vendor fails a ≥ 0.95 daily-return check against
  NY-close GLD.
- The thresholds in §2.3 were set for a close-timed source, and no free close-timed pre-2000 daily
  gold source passed (Stooq is behind a bot check).
- This asynchrony also matters inside the engine:
  - gold's 40-day covariance with NY-close equities would be understated, which feeds the vol
    scaler;
  - ballast's 60-day own-vol, which sets the inverse-vol weight, is unaffected.

**Next testable structure (needs a strategist pre-data Amendment 2 before any P statistic):**
- Option 1, keep the fix: accept WGC with a timing-robust check pre-declared, such as a weekly
  (Fri→Fri) ρ ≥ 0.90 or a lag-0 plus lag+1 summed-ρ test.
- Option 2, also handle the engine effect: lag gold by one day (use fix_{t+1} as the close-t proxy).
  That is a look-ahead of about 6 hours and is probably unacceptable.
  - The clean alternative is to state that the GLD proxy is timing-asynchronous.
  - Then report a D-window bracket: GLD vs WGC-fix gold over 2005–2019, Part B at 5 bp, A arm only.
    This sizes the distortion before P is opened.
- If neither is acceptable, P is unusable for this book. The family moves to forward data, or to
  the pre-1987 window, which has the same gold problem.

Disclosure: while checking the .xls layout, three 1978–79 gold rows were printed to screen. They
were unused and filtered out at load.

---

## EXP-030 — Long-only multi-factor selection (value, 12-1 momentum, gross profitability, low vol) in the point-in-time S&P 500

**Status:** PRE-REGISTERED 2026-10-14. This was written BEFORE any return, factor value or factor
performance for this universe was computed in this repo. K = 3 (new family: long-only S&P 500
cross-sectional factor selection).

Build spec: `research/exp030_spec.md`. It is binding; if it and this entry disagree, this entry wins,
and the disagreement is reported rather than resolved toward PASS. Tyler approved the start in chat.
Free data only; paid data needs a quote to Tyler first.

**Origin:** this is the structure that EXP-006's binding constraint does not reach. EXP-006 died
because a 5-ETF universe gives about 40 independent cross-sectional observations per decade. Its
lesson was "cross-sectional breadth IS the strategy". The point-in-time S&P 500 has about 500 names
per month.

EXP-008's unfixed flaw was survivorship (a current-constituent universe). EXP-004 showed what a few
squeezes do to an equal-weight mean. Both are handled explicitly in spec §1.

**Crowding read:** institution-crowded. AQR, DFA and the MTUM/QUAL/USMV/VLUE factor ETFs, with
smart-beta AUM in the trillions, all trade these factors. That is acceptable under the crowding
criterion, but expect decayed premia:
- McLean–Pontiff find about a third smaller premia out of sample and roughly half post-publication.
- Value and momentum premia are weaker in large caps than all-cap.
- Large-cap value had a lost decade after 2007.

The prior for net alpha against EW is small and positive at best.

### Feasibility probe (2026-10-14, `research/exp030_probe.py`; coverage counts only, no returns)

**Membership:** fja05680/sp500 PIT snapshots (Clenow/Norgate base, Wikipedia-maintained since 2019).
- 2012-01-01..2026-08-18: 917 snapshots, 496–507 names each.
- 815 distinct tickers; 503 are still members and 312 are not.

**Tiingo list level** (supported_tickers.csv; 30 API calls used in total):
- 729 exact ticker+date matches, 61 rename-heuristic matches, 25 unmatched.
- The heuristic is unreliable: about 26 of 61 pairs were true renames. SIVB→BG and FRC→AXON were
  wrong; the real series are SIVBQ and FRCB.

**API spot check:** 30 departed names (seed 30).
- 26/30 had ≥ 90% of business days present.
- Exact matches: 23/25. The failures were BEAM and CAM, both reused tickers with 0 rows.
- Renames: 3/5 (INFO→MOH wrong; VIAC→PARA only partial).

**Alpaca fallback (2016+):** 11 of the 25 Tiingo-unmatched names are covered. 8 left the index before
2016. Some apparent misses are re-entering tickers whose merged interval spans a gap: CEG, DELL,
SNDK, IR.

**Departed-name price coverage after removing known-bad matches:** 270/312 = 87%. The remaining
roughly 42 names need a by-name manual mapping. They are mostly acquired names from before 2016.

**Member-month price coverage, same basis:** 97.5% overall.

| 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020–2026 |
|---|---|---|---|---|---|---|---|---|
| 92.6% | 94.3% | 95.6% | 96.2% | 97.6% | 98.2% | 98.4% | 98.6% | 98.9–99.3% |

Departures cluster early, so the calibration window carries the gap and the holdout does not.

**CIK mapping:**
- 622 by current SEC ticker. These include reused-ticker hazards (DELL, CEG, IR…), so every
  departed CIK must be name-verified.
- 47 by rename (unverified, given the heuristic's precision).
- 96 by exact Wikipedia name to an EDGAR entity.
- 23 by top search hit only, unverified.
- 27 unmapped.
- That leaves about 50 departed names for manual EDGAR lookup, outcome-blind.

**XBRL coverage** (frames API, year-end members, 2011 → 2025). Frames undercount non-calendar fiscal
years, so these are lower bounds; the test uses companyfacts.

| fact | 2011 | 2025 |
|---|---|---|
| Assets | 86% | 99.8% |
| StockholdersEquity | 80% | 94% |
| NetIncomeLoss (annual) | 78% | 93% |
| any gross-profit route | 41% | 58% |
| dei shares outstanding | 59% | 72% |

The dei shares figure is low because the cover-page date rarely equals the period end. The
gross-profit route is thin because financials, utilities and many service firms report no COGS.
That is why the spec fixes a within-route fallback (NI/Assets) now.

**First-filed lag** (Assets, 15-CIK sample, 713 period-ends 2011+):
- Median 33 days, p90 54, p99 60, max 431.
- First-filed ≠ latest-filed on 3.5% of period-ends. Restatements are real but rare.

**Data cost:** none required. The Tiingo free tier's monthly unique-symbol cap means the pull of
about 830 symbols spans two calendar months, at most 480 per month. A paid month would be faster, but
needs a quote to Tyler first; I have not verified the price.

### Hypothesis

**Part A (premise, K = 0):** in the survivorship-free S&P 500, 2012–2018:
- The equal-weight composite of four textbook factors has a positive monthly rank IC with
  next-month return. The factors are: VALUE = E/P and B/P; MOM = 12-1; QUALITY = gross profits/assets
  (NI/assets where there is no GP); LOWVOL = −252d vol.
- Its top quintile beats the equal-weight universe, gross.

**Part B (holdout 2019-01..2026-09):** a long-only, monthly, net-of-cost top-quintile book:
- beats the equal-weight universe on Sharpe, significantly after K = 3;
- is not worse than SPY on Sharpe;
- has a comparable drawdown;
- has bounded turnover;
- carries the factor tilts it claims.

### Why it could be real
- These are among the most replicated cross-sectional premia: Fama–French, Jegadeesh–Titman,
  Novy-Marx, Frazzini–Pedersen/Ang et al.
- Combining them diversifies their individually long drawdowns. Value and momentum are negatively
  correlated.
- Long-only large-cap is the implementable, cheap end of the trade: about 1–3 bp half-spreads and
  no short borrow.

### Why it could fail (stated before data)
- **Decay and crowding** (above).
- **Large-cap dilution.**
- **Mega-cap concentration, 2019–2026.** I know in broad strokes that cap-weighted SPY beat
  equal-weight over much of this period. An EW-style factor book carries an anti-size tilt against
  SPY, so G2 is the gate I expect to fail.
- **Known factor events in H.** The 2020 value crash, the November 2020 momentum crash, the 2022
  value rebound, and low-vol's lag in the 2023–24 rallies are all in my priors. **H is sealed to the
  code, not to the strategist.** The factor set is the textbook one, fixed before any number. It was
  not chosen with these episodes in view, but a reader should weigh G1/G2 knowing they are not
  surprises to me.
- **Power.** EW and the book are highly correlated, so SE(ΔSh) is about 0.11 over 93 months. G1's
  Bonferroni bar therefore needs a realised ΔSh of roughly +0.25. A true premium of +0.10 would
  usually come back as FAIL. I accept that rather than loosening the bar.

### Design (summary; details are in the spec)
**Data and honesty rules:**
- **Survivorship:** the PIT universe, and departed-name prices mapped by NAME with row-count
  verification. The ticker map is frozen and its SHA ledgered before any return.
- **Delisting rule:**
  - acquisition → last close;
  - failure → post-failure OTC series, or −100%;
  - unknown → −30%.
  - The list is enumerated before returns.
- **Look-ahead:**
  - XBRL first-filed values, usable only if `filed < t`, stale after 200 days, with TTM built from
    quarters.
  - Trades at the close of t+1.
  - Sector = FF-12 from current SIC (a disclosed small look-ahead).
- **Costs:** 10 bp one-way primary, 20 bp stress. Alpaca commission is $0 and S&P 500 half-spreads
  are about 1–3 bp, so this is a conservative 3–5×.

**Variants (K = 3, declared, all run, none picked):**
- **V1:** top quintile, EW, FF-12 sector cap of 25%.
- **V2:** sector-neutral (ranks within sector, top quintile per sector).
- **V3:** V1 with a 20%-in / 40%-out turnover buffer.

There are no factor weights other than equal, and no other cut-offs, lookbacks or factors.

**Windows:**
- Prices from 2010-12.
- Calibration C: rebalances 2012-01..2018-11, returns through 2018-12-31.
- Sealed holdout H: rebalances 2018-12-31..2026-08-31, returns 2019-01..2026-09 (93 months).
- The seal is in code: `HOLDOUT_OPEN = False` truncates prices at 2018-12-31 until Part A is
  ledgered.

### Decision rule (frozen)
**Part A (window C; FAIL ⇒ STOP, K = 0 spent):**
- A0 data:
  - ≥ 95% of member-months priced, and ≥ 90% scored.
  - A failure is INCONCLUSIVE, not a premise death.
- A1: mean monthly Spearman IC ≥ 0.015, AND block-bootstrap one-sided P(≤ 0) < 0.05.
- A2: top-quintile EW gross minus universe EW > 0 (point).

**Part B (window H, per variant, net 10 bp; all must hold):**
- **B0 validity (else INVALID):**
  - ≥ 98% of member-months priced, ≥ 90% scored;
  - the causality perturbation test (filed+1d, post-t prices) leaves the weights unchanged;
  - 5-date independent recomputation.
- **G1:**
  - ΔSh(V − EW) ≥ +0.10;
  - AND paired stationary block bootstrap (block 6, 10k, seed 30) P(ΔSh ≤ 0) < 0.0167
    (Bonferroni K = 3);
  - AND net active return > 0.
- **G2:** ΔSh(V − SPY) ≥ −0.05 (point).
- **G3:** MaxDD no more than 5.0 pts deeper than EW's AND than SPY's.
- **G4:**
  - one-way turnover ≤ 150%/yr (V1, V2) or ≤ 100%/yr (V3);
  - AND G1's point estimate ≥ +0.05 at 20 bp.
- **G5:** active return on FF5+UMD (NW-3). At least 3 of {HML > 0, UMD > 0, RMW > 0, β_V < β_EW}
  have the intended sign. A failure is FAIL-with-diagnosis.

**Reported, not gated:**
- C-window backtests;
- calendar years;
- SMB loading (EW vs SPY is a size bet);
- DSR at K_family = 3;
- per-factor ICs (descriptive only; never used to re-weight);
- the route-R share;
- the delisting-class P&L.

**Verdict:**
- PASS per variant = A ∧ B0 ∧ G1–G5. All passers are shadowed; none is picked by Sharpe.
- **PASS authorises only** a read-only monthly paper shadow logger of the target book, with Tyler's
  go-ahead. That means no orders, no live-bot change, and no allocation. Adoption needs a separate
  pre-registered forward check (≥ 12 shadow rebalances vs EW and SPY) plus Tyler.
- A positive-but-insignificant G1 is a FAIL and authorises nothing.
- **Kill rule:** on FAIL, H (2019-01..2026-09) is spent for long-only S&P 500 factor selection.
  Each of the following is a new experiment on forward data:
  - other factor definitions or weights;
  - other cut-offs or rebalance frequency;
  - a short or size leg;
  - another universe (R1000, S&P 400).

### Predictions (written before data)
- **Part A PASS:** about 55%. Momentum, low vol and quality were broadly positive in large caps
  2012–16, and value was weak. A1's IC bar is modest, but 83 months is not a lot.
- **Part B, each variant:**
  - G1 about 15% (power is the main reason);
  - G2 about 15% (mega-cap concentration);
  - G5 about 80%.
- **Any variant full PASS:** about 7%.
- **Most likely outcome:**
  - Part A passes.
  - G1 has a positive point estimate but is insignificant, so FAIL.
  - G2 fails with ΔSh vs SPY around −0.2 to −0.4.
  - V3 has the lowest turnover and V2 the lowest active risk.

### AMENDMENT 1 — pre-data (2026-10-14 09:12 PDT; strategist, on Tyler's in-chat choice)

**Why.** Tiingo's free tier is 50 requests/hr and 500 unique symbols/month. In about 12 hours it has
consumed 140 unique symbols, mostly on name-verification meta calls, and written only 17 price
series. It cannot finish about 830 symbols this month.

**Pre-data status, checked in `research/exp030/` at the timestamp:**
- No return, rank, factor-value, IC, NAV or weights file exists.
- No `exp030_*.py` script computes returns or ranks (grep for pct_change / rank / spearman / cumprod /
  log: no hits).
- On disk: 17 Tiingo price files (including SPY), all ending ≤ 2018-12-31, and 154 meta files.
- `symbol_map.csv` is still `draft`, and no SHA has been ledgered.
- XBRL companyfacts were pulled; no factor has been built from them.

**Price sourcing (plumbing only):**
1. Symbols whose index-stint issuer is still listed under that symbol take daily closes from Yahoo
   Finance, either yfinance `auto_adjust=True` or the chart API.
   - The issuer must be CIK- and name-verified, exactly as for Tiingo. Yahoo serves only the
     current holder of a ticker, so reused tickers (DELL, CEG, IR, …) do not qualify.
   - The market-cap close in spec §3.1 is Yahoo's split-adjusted `Close`, un-adjusted using Yahoo's
     split events.
2. Delisted or renamed symbols that Yahoo lacks stay on Tiingo `adjClose`, with Alpaca as the
   existing 2016+ fallback.
3. Symbols already pulled from Tiingo keep Tiingo.
4. **Cross-source consistency check (pre-declared).**
   - **Scope:** this is a data-validation computation on individual-symbol daily returns, window C
     only. It produces per-symbol statistics and no rank, factor or portfolio number.
   - **Sample:** at least 30 symbols with both sources over 2010-12-01..2018-12-31. Use every
     already-pulled Tiingo symbol that Yahoo also serves, then top up with a seed-30 random draw of
     Yahoo-sourced names, fetched from Tiingo within quota.
   - **Per-symbol pass:** all of these must hold:
     - common-date coverage ≥ 95%;
     - Pearson correlation of daily total returns ≥ 0.99;
     - |annualised total-return difference| ≤ 0.5%/yr.
   - **A failing symbol** uses Tiingo, or is flagged unresolved if Tiingo lacks it.
   - **Source-level rule:** if fewer than 90% of the sample pass, Yahoo is rejected wholesale, and
     the build reverts to the slow Tiingo path across months.
   - **Screens on every Yahoo series:** no non-positive prices, and no |daily return| > 50% without a
     split event. Hits are listed.
5. `symbol_map.csv` gains a final `price_source` column (`tiingo` / `yahoo` / `alpaca`).
   - The map is frozen after step 4.
   - Its SHA-256 is written in this ledger before any factor, rank or portfolio return is computed.

**Holdout:** it stays sealed. With `HOLDOUT_OPEN = False`, every Yahoo request ends at 2018-12-31
(yfinance `end="2019-01-01"`, which is exclusive). Back-adjustment factors from later corporate
actions are scale constants that do not alter returns inside C; this is the same as Tiingo.

**Unchanged:** factors, variants (K = 3), windows, gates, costs, delisting rule, verdict and kill
rule. This amendment changes data plumbing only.

### Result
(pending: independent tester per `research/exp030_spec.md` + Amendment 1. The first step is the frozen
ticker/CIK map, with `price_source`, and its SHA.)

#### Data build — tester (2026-10-14, ~20:35 UTC). MAP FROZEN before any factor, rank or portfolio return.

No factor value, rank, IC, NAV or portfolio return has been computed. The only return-type numbers
are the per-symbol Tiingo-vs-Yahoo checks in window C, which Amendment 1 item 4 requires. Every
price request ended on or before 2018-12-31; `HOLDOUT_OPEN = False`. Full report:
`research/exp030/DATA_BUILD.md`.

**Frozen SHA-256:**
- `research/exp030/symbol_map.csv` (map v1; `ticker_map.csv` is byte-identical):
  **`0b92c4e1816ce43184e632ea26ff4ea69aaac9b5d3acf07da5cf5cf614f7251d`**
- `research/exp030/delist_classes.csv`:
  **`def08959091bdd1a33c4e3cbb14663050c3f9a815fb458af1d15627d64eda23f`**
- `research/exp030/identity_overrides.csv` (the by-name input):
  `055acd9be09a117fe266b402372c0b70654f680000eb23fbb627f4c2b6b521a3`

**Amendment 1 item 4 — Yahoo REJECTED.**
- 29 of 33 sample symbols pass (87.9%, against the 90% bar).
- Failures: ANF ρ = 0.9889; EVRG coverage 7%; HLT +0.61 pp/yr; GRMN −1.09 pp/yr.
- So `price_source` is `tiingo` (802 segments) or `none` (76).
- Tyler's mid-run move to a paid Tiingo plan allowed the full pull: 607 series, 2010-12-01..2018-12-31.
- The Alpaca 2016+ fallback was considered, but no unresolved segment qualifies.

**Map:** 836 tickers, 854 stints, 878 identity segments (673 of them in C).
- **CIK:** 877/878 mapped and name-verified. Signature Bank is the exception: it files with the
  FDIC.
- **Window C:** 612 segments VERIFIED, 11 of them flagged (label collisions AGN/CB/JCI; spliced
  DD/FTI; Norgate labels). 61 are **UNRESOLVED**. All are departed names:
  - 25 reused tickers;
  - 24 with no reachable Tiingo listing;
  - 12 with 0 rows.

**Delisting list:** 151 events (148 A, 3 F, 0 U); 97 of them fall in C.

**XBRL:** companyfacts are cached for 822 of 823 CIKs. The missing one is FRC, an FDIC filer.

**Pre-registered consequence for A0 (reported, not decided here).** Priced member-months in C are
**94.1%**:

| | priced |
|---|---|
| 2012 | 90.1% |
| 2013 | 91.3% |
| 2014 | 93.0% |
| 2015 | 93.6% |
| 2016 | 95.6% |
| 2017 | 97.5% |
| 2018 | 98.0% |

That is below the ≥ 95% A0 bar. As registered, Part A on this map is INCONCLUSIVE-data, not a premise
FAIL.

The binding constraint is pre-2016 delisted names that **no Tiingo tier** can serve: the listing is
absent, or the ticker has been reused by another issuer. The map cannot be widened without a
different delisted-name price source and a new pre-data amendment. That decision belongs to the
strategist or Tyler, not the tester.

Disclosures (DATA_BUILD.md):
- The probe's row-only spot check accepted wrong securities: PCL, HAR→DISH, ATGE→PNR.
- The fja membership file has label collisions (Actavis, ACE and Tyco are missing pre-merger) and
  double-counts two stretches (CCE/CCEP and KORS/CPRI).

### AMENDMENT 2 — pre-data (2026-10-14 16:21 PDT; strategist)

**Why.** Map v1 prices 94.1% of member-months in C, short of A0's ≥ 95%. The 61 unresolved segments
are departed names, mostly delisted before 2016: 25 reused tickers, 24 not on Tiingo, and 12 with
zero rows. No Tiingo tier can serve them. Tyler has requested WRDS access through the University of
Utah, which would provide the CRSP daily stock file with delisting returns. Approval takes about
5 business days.

**Pre-data status, checked at the timestamp:**
- `research/exp030/` contains no factor, rank, IC, NAV, weights or portfolio-return file.
- The only return-type computation so far is Amendment 1's per-symbol Tiingo-vs-Yahoo check
  (`exp030_xsource_check.py`, window C).
- Map v1 (SHA `0b92c4e1…7251d`, above) stays in this ledger as the v1 record.

**Rules:**
1. **Scope.** CRSP is a price source ONLY for the 61 segments marked UNRESOLVED in map v1, and ONLY
   in window C. Every v1-priced segment keeps Tiingo, whatever CRSP shows. CRSP is not authorised
   for H.
   - Query end date: 2018-12-31. No CRSP row dated 2019 or later is requested or loaded.
   - CRSP data stays local and gitignored, under the university licence terms.
2. **Linking.** A segment is linked to a PERMNO only if all of the following hold:
   - The CRSP stocknames ticker and/or CUSIP has a name-date range that overlaps the index stint.
   - The CRSP company name matches the verified SEC entity name or CIK, checked by name.
   - It is common stock (SHRCD 10/11).
   - The PERMNO has rows on ≥ 90% of the stint's trading days.

   Anything that fails stays UNRESOLVED.
3. **Price fields.**
   - Returns use CRSP `RET`, the total return.
   - The market-cap close uses |`PRC`| (which is unadjusted), with `CFACPR`/`CFACSHR` standing in for
     Tiingo's split factor.
   - The spec §3.1 shares rule is unchanged.
4. **Delisting.** The existing classes (A/F/U) and reason sources are unchanged. For CRSP-sourced
   segments, CRSP `DLRET` is the delisting return when it is non-missing:
   - A: the last CRSP price, then `DLRET`.
   - F: `DLRET`, else −100%.
   - U: `DLRET`, else −30%.

   Tiingo-sourced events are untouched.
5. **Cross-source check, before CRSP is admitted.** This uses the same bar that rejected Yahoo; no
   loosening.
   - **Sample:** at least 30 v1-VERIFIED Tiingo segments in C that also exist in CRSP.
     - Every verified departed segment that links to CRSP is included, up to 15.
     - The rest is a seed-30 random draw.
   - **Per-symbol pass:** all of the following must hold:
     - common-date coverage ≥ 95%;
     - daily total-return Pearson ρ ≥ 0.99;
     - |annualised total-return difference| ≤ 0.5 pp/yr.
   - **Admission:** if ≥ 90% of the sample pass, CRSP is admitted. Otherwise CRSP is not admitted,
     even if the disagreements look like Tiingo's fault.
   - Per-symbol statistics only; no rank, factor or portfolio number.
6. **Map v2.**
   - `symbol_map.csv` v2 = v1 + the CRSP-linked segments (`price_source = crsp`, plus a `permno`
     column).
   - `delist_classes.csv` v2 includes any `DLRET`.
   - The SHA-256 of both is written here BEFORE any factor, rank or portfolio return is computed.
   - A0 is then re-measured on v2 against the unchanged 95% bar.
7. **Fallback (pre-declared).** EXP-030 is recorded as **INCONCLUSIVE-data** if any of these
   happens:
   - WRDS is denied, or not granted by 2026-11-30;
   - the item 5 check fails;
   - CRSP links too few segments to bring C to ≥ 95%.

   In that case K spent = 0, and H (2019-01..2026-09) stays sealed and unspent. Specifically
   excluded as rescues:
   - lowering A0;
   - shortening C (e.g. dropping 2012–2015);
   - dropping unresolved names from the universe definition;
   - mixing in another source not named here.

   Any of those is a new pre-registration.

**Unchanged:** factors, variants (K = 3), windows, gates, costs, the A/F/U delisting classes, the
verdict and kill rules, and the holdout seal. This amendment changes data plumbing only.

---

## EXP-029 — RESULT (tester, 2026-10-14): **INCONCLUSIVE-data.** P stays sealed and unspent; K spent = 0.

Run under Amendments 1 and 2. Interpretations #32–42 in `research/exp029/INTERPRETATIONS.md` were
written before each computation. Files: `identity_check.json`, `sizing.json`, `verdict.json`,
`FROZEN_MD5.txt`.

**Data and validity:**
- F0 PASS: exact reproduction of `run_book`, max diff 0.0.
- F2 and F3 PASS on D at the weight level.
- Amendment 1 RF is in place.

**Identity checks (WGC fix vs other gold), Amendment 2 item 2 — PASS:**

| vs | weekly ρ | n | weekly min | month-end ρ | n | month-end min |
|---|---|---|---|---|---|---|
| GLD | 0.923 | 110 | 0.90 | 0.977 | 25 | 0.97 |
| GC=F | 0.878 | 217 | 0.85 | 0.984 | 49 | 0.95 |

**Sizing study** (D-real vs D-fix gold, 5 bp, sim from 2005-01-03, scored 2007-07-02 → 2019-11-15):
- **Truncation, disclosed beforehand (#39):** Tyler's WGC file ends 2019-11-15, so scoring stops
  there, not at 2019-12-31. No extra gold was fetched.
- Before SHV, 510 days of cash used DTB3.

| check | measured (fix − real) | tolerance | result |
|---|---|---|---|
| T1, arm ΔSh | A +0.006, V1 +0.006, V2 +0.006, C1 +0.001, C2 −0.004 | ≤ 0.05 | PASS |
| T2, contrast ΔSh (largest) | V2−C2 +0.0099, C2−A −0.0097 | ≤ 0.015 | PASS |
| T2b, contrast ΔMaxDD | C1−A −0.45 pt, V1−C1 +0.45 pt (V−A 0.00, C2−A +0.11) | ≤ 0.30 pt | **FAIL** |
| T3, p99 \|Δs\| | C1 0.082, C2 0.097 (A/V1/V2 0.033) | ≤ 0.05 | **FAIL** |
| T3, mean \|Δs\| | all ≤ 0.0064 | ≤ 0.01 | pass |

Reported only:
- Mean 40d ρ(gold, SPY): real +0.013, fix −0.005. ρ(gold, QQQ): real +0.004, fix −0.008.
- Mean |Δ GLD base weight| = 0.006.
- G = 1 in 0.7% of scored months, so the V−A contrasts barely exercised the map. The C arms did.

**Decision (Amendment 2 §4):** T2b and T3 failed ⇒ INCONCLUSIVE-data.
- F1 and F3 on P were not run. No Part A, no Part B, no ρ/G statistic on P exists.
- There is no second sizing run, no relaxed tolerance, and no other gold construction for P.

**Contamination note:** the sizing run showed the tester arm-level D results for 2007-07 →
2019-11, which overlaps G6's guard window. G6 was partly previewed. It carries no evidential
weight, so nothing changes.

**Binding constraint:**
- Fix-timed gold changes the vol scaler on tail days by up to 0.097 (p99 |Δs|, C2; limit 0.05).
- It moves the duration-to-cash contrast's MaxDD by 0.45 pt (limit 0.30).
- The cause is the duration removal itself. Once TLT/IEF go to cash, gold is a larger share of the
  risky book. Its asynchronous fix-timed returns then feed the 40d covariance that sets s, which
  is exactly the mechanism EXP-029 tests.
- The proxy perturbs most strongly in the arms that exercise the hypothesis. A, V1 and V2 sit well
  inside tolerance only because G was almost never 1 in 2007–19.

**Pattern across deaths:** this is the first death in this family on *proxy fidelity*, not on
premise or cost. The ballast inverse-vol and scaler machinery is sensitive to timing in the
hedge leg. Any pre-ETF test of a ballast-heavy book inherits that problem: the 1962–86 window has
the same London-fix issue, and before 1968 there is no free gold price.

**Next testable structure** (needs Tyler and a new registration):
1. **Forward test:** a read-only V1/V2 shadow logger beside the live challenger, if Tyler wants
   it, per Amendment 2's successor clause.
2. **Gold-free premise test:** Part A (the SPY/TLT correlation-regime persistence measurement)
   uses no gold.
   - A separate K = 0 registration could run it on 1987–2006, or on the reserved 1962–86 window
     (DGS10 and French).
   - Whether P may be opened for a gold-free measurement is a strategist call. P is sealed now.
3. **Sidestep gold in the book:** test the duration gate on a book whose ballast holds no
   fix-timed asset (for example a TLT-only ballast variant) on forward data.

---

## EXP-028 — RESULT (tester, 2026-10-14): **H1 FAIL, H2 FAIL on P.** H sealed and unopened; K = 2 spent (challenger family 11, champion family 16).

Independent tester; did not design EXP-028.

**Verdict on P (2013-08-02 → 2020-06-30): H1 FAIL. H2 FAIL.** Validity V1–V5 all pass; G6 coverage
passes (100% of held contract-days quoted, 100% of option trades on schedule), so neither is
INCONCLUSIVE. **H was not opened** (no hypothesis passed P): `run_H.py` was never written,
`prices_H.parquet` was written at download time and never parsed (md5 25f8820b…), and no OPRA
request ended after 2020-07-01. Kill rule applies to both comparisons.

Files: `research/exp028/` — `verdict_P.json`, `results_P.json`, `daily_{H1,H2}_{A,B,Bstress,Bbid}_P.parquet`,
`INTERPRETATIONS.md` (written before data), `DECISIONS.md` (every amendment, with timing),
`chain_log_P.txt`, `spend_log.csv`.

| Gate | H1 (core sleeve: QLD → LEAPS) | H2 (TQQQ → 3x LEAPS) |
|---|---|---|
| G1 μ_d, p (one-sided, block 21) | **−0.46%/yr, p = 0.904** (95% CI −1.18% … +0.23%) ✗ | **−2.70%/yr, p = 0.806** (CI −8.55% … +3.95%) ✗ |
| G2 ΔSharpe (SHV-RF) ≥ +0.05 | **−0.008** (0.775 vs 0.783) ✗ | **+0.004** (0.948 vs 0.945) ✗ |
| G3 MaxDD_B ≥ MaxDD_A − 2 pts | −32.3% vs −33.0% ✓ | −59.6% vs −69.9% ✓ |
| G4 β ratio ∈ [0.90,1.10]; fallback ≤ 5% | 0.983 ✓; **fallback 9/66 = 13.6%** ✗ | 0.931 ✓; **fallback 10/83 = 12.0%** ✗ |
| G5 spread+fees ≤ 0.50%/yr per unit D\*/NAV; μ_d>0 at ×1.5 | **2.31%/yr per unit** ✗; stressed μ_d −1.05% ✗ | **1.94%/yr per unit** ✗; stressed μ_d −4.92% ✗ |
| G6 coverage | 100% / 100% ✓ | 100% / 100% ✓ |

Arm stats (P metrics window): A1 CAGR 17.5%, vol 22.8%, β 1.088; B1 CAGR 17.0%, vol 22.4%, β 1.070.
A2 (TQQQ) CAGR 47.0%, vol 58.2%, MaxDD −69.9%, worst day −34.5%; B2 CAGR 46.0%, vol 55.1%,
MaxDD −59.6%, worst day −21.0%; B2 down-day β 2.57 vs A2 2.95 (the convexity is real and shows
up as drawdown protection, which is why G3 passes).

**Residual decomposition (the head-to-head the hypothesis is about), per year:**
| | H1 | H2 |
|---|---|---|
| A's LETF all-in drag vs ideal L·r_QQQ − (L−1)·r_SHV | QLD **−1.33%** of the QLD position | TQQQ **−2.46%** of NAV |
| B's levered leg (options+SHV, mark-to-mark) vs the same ideal | **+1.61%** of the slice | **+0.01%** of NAV |
| B option spread paid | **1.36% of NAV** | **5.81% of NAV** |
| B fees / time-value change / SHV interest (% NAV) | 0.002% / −0.53% / +0.14% | 0.006% / −4.79% / +0.34% |
| A ETF trading cost (% NAV) — B's in parentheses | — (B 0.33%) | — (B 0.11%) |

Read: the premise was right. QLD and TQQQ really did lag ideal daily leverage (−1.3%/yr and
−2.5%/yr), and the deep-ITM option leg, marked mid-to-mid, tracked ideal leverage as well as or
better than the ETF. The variance-risk-premium cost the pre-registration feared did not show
up as a mid-to-mid loss on Δ 0.8 calls in 2013–20 (convexity gains ≈ theta). The trade
died on **crossing the option spread every month**. Monthly resizing under the 2% band, plus
the ramp toggling the H1 slice on and off, made B pay 1.36% (H1) / 5.81% (H2) of NAV a year in
half-spreads. That is larger than the whole LETF drag it was meant to save.

Per-year μ_d (%/yr) — H1: 2013 +0.62, 2014 −0.49, 2015 −1.01, 2016 −0.82, 2017 −0.80,
2018 +1.07, 2019 −0.59, 2020H1 −1.64. H2: 2013 +2.08, 2014 −1.04, 2015 −6.82, 2016 −10.83,
2017 −3.69, 2018 +7.40, 2019 −5.28, 2020H1 +1.52. B wins only in the high-vol years (2018, and
2020 for H2), where convexity and the capped loss pay. It loses in the calm trending years.

**Reported-only arms.**
- R2 implementability: at the live challenger size (core ≈ $456.67) whole contracts round to
  **0 in 100% of months with w_QLD > 0** (66/66), as predicted. At $1M, TE vs fractional 0.06%/yr;
  the 13.6% of months with n = 0 are exactly the fallback months.
- R3 bid marks: H1 μ_d −0.48%, ΔSR −0.012; H2 μ_d −2.78%, ΔSR −0.005. Liquidation at bid on the
  last day would cost 0.12% (B1) / 0.26% (B2) of NAV.
- R1 (SPY options vs UPRO, P only, reported only, no K): μ_d −0.97%/yr (p = 0.62), ΔSR +0.015, MaxDD −72.2% vs UPRO −76.8%, β ratio 0.925, **0 fallback months** (SPY always had an eligible LEAPS expiry; QQQ missed 10 of 83), spread+fees **0.495%/yr per unit of D\*/NAV** (about 4× cheaper than QQQ's 1.94%, right at the 0.50% line), stressed μ_d −1.71%. UPRO drag vs ideal 3x −1.92%/yr; B's leg −1.39%/yr. Premium cap bound Apr–Jun 2020 (shortfall 56–88% of NAV). File `results_R1_P.json`.
- H2 premium cap bound in Apr–Jun 2020 (dollar-delta shortfall 30% / 58% / 74% of NAV, logged).
  It is pre-registered behavior. It cut B2's exposure in the rebound and is inside H2's 2020H1
  +1.52% anyway.

**Predictions vs outcome.** H1 P-PASS predicted ~12% → FAIL, on G1 as predicted, but also on G4
and G5. H2 P-PASS ~25% → FAIL (G3 passed as predicted; G1 failed as predicted). G6 INCONCLUSIVE
~10% → did not happen: coverage was 100% once the 2014 strike adjustment was followed. R2 "0
contracts in 100% of months" → confirmed exactly. **Not predicted:** G4 fallback failing on
*listing structure*. QQQ's LEAPS calendar often has no standard monthly expiry inside 270–455
DTE (e.g. 2015-08-03: only 228 and 536 DTE exist). In four 2014 months the only candidate
expiry carried only strikes adjusted by the Feb-2014 special dividend, which the spec excludes.

**Amendments and incidents (all in DECISIONS.md, all made before any arm number existed unless
noted):**
1. `contract_multiplier` is Databento's null sentinel on 2013 rows, so the rule became
   multiplier ∈ {100, null}, root exactly `QQQ`. Expiry = UTC date of `expiration` (2013 rows sit
   on the Saturday), matching spec §3.1 wording.
2. QQQ paid a $0.37313 special dividend ex 2014-02-27. OCC re-struck the held
   `QQQ 141220C00075000` to `…C00074630`; the old symbol has no quotes after 02-26. The sim
   follows the adjusted contract (same position, no trade). Selection excludes adjusted
   (non-$0.50) strikes per §3.1.
3. §3.3's "keep it, retry next day" never terminates if quotes end for good. Replaced by:
   abandon at last valid bid after 5 days, fallback month. **It never triggered.**
4. Transport only, no sim logic: the Databento Python client hung repeatedly. Root cause was
   the Mac entering system sleep on battery (confirmed in `pmset -g log`), plus transient
   504/read timeouts. Downloads moved to plain HTTP in a killable child process, verified
   against the client on a cached contract (identical closing quotes, max difference 0.00). Every interrupted attempt is logged as
   paid. Each stuck process of mine (8 PIDs: the chain builds and two test probes) was killed by verified PID. **No other process was
   touched.**

**Spend: $0.54 total ($0.5429, 219 logged requests) of Tyler's $10** (hard stop $9.50), every request in
`research/exp028/spend_log.csv`. $0.124 of that (34 requests) is re-paid attempts after the sleep/timeout incidents,
logged conservatively even where the server returned nothing.

**Binding constraint (one line, with the number):** option half-spreads from monthly resizing:
**1.94–2.31%/yr per unit of target dollar delta against a 0.50% gate**, i.e. 5.8%/yr of NAV at 3x
against a TQQQ drag of 2.5%/yr. Secondary: **12–14% of months with no eligible LEAPS** (listing
calendar) against a 5% gate.

**Pattern across deaths (checked against what this entry measured; the cross-ledger count is
not re-derived here):** this belongs with the CLAUDE.md group "premise TRUE, the trade still
lost". The LETF financing drag is real and measured (−1.3%/yr QLD, −2.5%/yr TQQQ). The option
leg's economics were fine mid-to-mid. Execution (spread × turnover) ate it. Same wall as the
VRP deaths, from the opposite side: here we were the convexity *buyer* and the VRP did not
bite. The spread did.

**Next testable structure (one the binding constraint does not reach; must cite EXP-028):**
capture the same measured LETF drag with an instrument whose round-trip cost per unit of delta
is ~100× smaller and that never needs monthly re-striking: **Micro E-mini Nasdaq-100 futures
(MNQ) as the leverage leg** in place of QLD/TQQQ. Same holdings engine, same ramp, same gates,
fills at 1 tick + exchange fees, quarterly roll, financing implicit in the basis (≈ T-bill),
no daily reset. Testable cheaply on Databento `GLBX.MDP3` (front-month MNQ/NQ, 2019+ for MNQ,
NQ before). This is a different instrument, not one of the option parameters the kill rule
freezes. **Stated up front:** it hits the same implementability wall as LEAPS. One MNQ is about
$40–50k of NDX delta, versus a $457 core sleeve, so it would be research-only until a sleeve
carries ≥ 1 contract of delta. For the live $1k account, QLD remains the only implementable
leverage instrument, and EXP-028 says it is not leaving money on the table relative to listed
options.
