# EXP-028 implementation spec: deep-ITM QQQ LEAPS in place of leveraged ETFs

Written 2026-10-13 by the strategist, **before any EXP-028 option quote was downloaded and before
any EXP-028 number was computed.** The pre-registration (hypothesis, gates, kill rule) is the
EXP-028 entry in `research/experiments.md`. If this spec and the ledger disagree, the ledger wins.
Report the disagreement; do not resolve it toward PASS.

This spec is for an engineer who has not talked to the strategist. Every number is fixed. **Do
not tune anything.** If something is ambiguous, pick the reading closest to what a desk would
actually do, write the choice in `research/exp028/DECISIONS.md` *before* running, and continue.

---

## 0. Ground rules

1. **No tracked files are edited.** All code and output goes in `research/exp028/` (gitignored).
   Files: `fetch.py`, `engine.py`, `run_P.py`, `run_H.py`, `score.py`, `DECISIONS.md`,
   `integrity.txt`, `spend_log.csv`, `opra_cache/`. Import `challenger/sleeves.py` read-only and
   call `sleeves.core_sleeve` unmodified. Never `git push`. Never place orders, paper or
   otherwise. No Alpaca trading calls.
2. **Data budget: $9.50 hard stop** (Tyler authorised $10). Every OPRA request goes through one
   function that calls `metadata.get_cost` first, adds to a locked running total, and calls
   `sys.exit` *before* the request if the total would exceed $9.50. Append every paid request
   (UTC time, schema, n symbols, start, end, quoted cost, running total) to `spend_log.csv`.
   Copy the cached-access pattern in `research/exp010_real_quotes.py::opra()`: get_cost first,
   4 retries with backoff, **never cache an empty result**, atomic write via a temp file.
   Expected total: about $1.60 with lazy definition pulls, at most about $4 (see §9).
3. **Timing.** The ramp signal for decision date d uses prices through the close of d only.
   Trades execute at the close of the **next** trading day t = d+1: ETF legs at the Tiingo close,
   options at the closing NBBO of day t (§3.4). Positions set at the close of t earn returns from
   t+1 on. Nothing computed from bar i may touch the return of bar i.
4. **The holdout is sealed** (§2). `run_P.py` must refuse (raise) on any OPRA request whose end
   is after `2020-07-01T00:00Z` and on any price row dated after 2020-06-30. `run_H.py` is not
   written until the P verdict is in the ledger, and it runs only if every P gate passes.
5. **Result files are write-once** (`open(path, "x")`). If a genuine bug is found after a
   result exists: write `results_P.v2.json` beside it, log the diff in `DECISIONS.md`, report
   both, and gate on v2 only if the bug is unrelated to which arm wins.
6. **Secrets.** `DATABENTO_API_KEY` and `TIINGO_API_KEY` come from `.env`. Never print them.

---

## 1. Data

| What | Source | Notes |
|---|---|---|
| Option definitions | Databento `OPRA.PILLAR`, schema `definition`, `stype_in="parent"`, symbols `QQQ.OPT` / `SPY.OPT` | Pull **only on contract-selection days** (lazy, sim-driven, like EXP-010's COLLECT/drain pattern). Request `[day, day+1)`. |
| Option quotes | `OPRA.PILLAR`, schema `cbbo-1m` (consolidated NBBO, 1-minute), `stype_in="raw_symbol"` | Only schema with bid/ask back to 2013 (`cbbo-1s`, `tcbbo`, `cmbp-1` start 2023–2025). |
| Spot (strike moneyness, IV) | Tiingo daily **raw `close`** for QQQ, SPY | Must be raw (unadjusted). Strikes are raw. |
| Dividend yield q | Tiingo `divCash`, trailing 365 calendar days through t, divided by raw close at t | |
| Rate r | FRED `DTB3` (3-month T-bill, %), last value dated ≤ t, /100 | Use `fred()` from `exp010_real_quotes.py` (copy it). |
| ETF total returns | Tiingo `adjClose` for QQQ, QLD, IEF, SHV, TQQQ, UPRO, SPY | Same loader as `challenger/backtest.py::load_data`, but ffill only, never bfill. |

**Price file split, at download time, exclusive create:**
- `prices_P.parquet`: 2012-06-01 → 2020-06-30 (the ~13 months before P are warm-up for the
  200-day MA and the dividend trailing window).
- `prices_H.parquet`: 2019-06-01 → 2026-09-30. Written now, **not parsed** until H is unlocked.
  Record its md5 in `DECISIONS.md` at write time.

**Cache reuse.** `research/exp010_cache/` holds `definition` files for QQQ/SPY on EXP-010 entry
days 2020-08 → 2026-06. They are H-window files; P never touches them. In H you may reuse one
only if its first `ts_event` date equals the selection day exactly. Otherwise pull fresh.

**Integrity scan (allowed before results):** rows, first and last date, NaN count and max
|daily return| per ticker per file; count of DTB3 gaps. Write `integrity.txt`. No strategy output.

---

## 2. Windows

| Window | Decision dates (BME) | Metrics window | Status |
|---|---|---|---|
| **P (primary, gates)** | 2013-07-31 → 2020-05-29 | 2013-08-02 → 2020-06-30 | Opened by `run_P.py` |
| **H (holdout, one look)** | 2020-07-31 → 2026-08-31 | First trading day after the 2020-07-31 execution → 2026-09-30 | Sealed. Opens only if P passes every gate. |

- OPRA `cbbo-1m` starts 2013-04-01. The first P execution is 2013-08-01.
- P ends 2020-06-30 and includes the Feb–Mar 2020 crash. H includes the 2022 bear market.
- H starts **flat** for both arms (a fresh book at 2020-07-31). It does not inherit P positions.
- At each window's end, open positions are marked at mid (no forced liquidation). Also report,
  not gated, the cost of liquidating at bid on the last day.

---

## 3. The LEAPS chain (shared by every B arm on one underlying)

The "chain" is the single option contract the B arms hold at any time on an underlying. It is
defined on **every execution day t, whether or not an arm currently holds it.** This keeps H1
and H2 on the same contracts and makes the chain independent of the ramp.

### 3.1 Eligible expiries
Standard monthly expiries only: `instrument_class == "C"`, and the expiration is the third Friday
of its month. Before 2015-02 the OCC symbol carries the Saturday after; take the date from the
definition's `expiration` and accept a Friday on day 15–21 or a Saturday on day 16–22. Exclude
weeklies, quarterlies (end-of-quarter, e.g. 2021-09-30) and anything non-standard (e.g.
`contract_multiplier != 100`, adjusted or deliverable-changed contracts).

### 3.2 Selection (on a selection day t)
1. DTE = calendar days from t to expiration. T = DTE / 365.
2. Candidate expiries: eligible, DTE in **[270, 455]**. Try them in order of |DTE − 365|
   ascending; on a tie take the longer.
3. For the candidate expiry, take calls with strike in [0.50·S, 1.00·S]. Pull their `cbbo-1m`
   for day t (one request, 19:30–21:05 UTC, then filter in America/New_York time).
4. Closing quote per contract: the last 1-minute bar with NY time < 16:00 on day t whose
   `bid_px_00 > 0` and `ask_px_00 > bid_px_00`. Flag it if it is older than 15:30 (accept on
   the known half-days: day after Thanksgiving, Dec 24, Jul 3).
5. Valid for selection: closing quote exists and (ask − bid)/mid ≤ **0.10**.
6. IV: invert Black–Scholes–Merton (European, continuous q) on the mid with `brentq` on
   [0.01, 3.0]. If the mid is below the BSM price at IV = 0.01 (deep-ITM American calls can
   quote near intrinsic), set IV = 0.01 and note it.
7. Delta = e^(−qT)·N(d1).
8. Pick the call with delta closest to **0.80**. It must lie in **[0.70, 0.90]**. If none does,
   go to the next candidate expiry. If no candidate expiry has one, the chain is **EMPTY** on
   day t (§3.5).

### 3.3 Roll and re-strike (checked on every execution day t)
For the current chain contract, compute DTE and delta from its closing quote on t.
- **Roll** if DTE ≤ **180**.
- **Re-strike** if delta ∉ **[0.65, 0.93]**.
- Either one: run §3.2 on day t to get the new chain contract. Any arm that holds the old
  contract sells it at the bid and buys the new one at the ask, in the same execution.
- If the current contract has no valid closing quote on t, it cannot be checked. Keep it, carry
  its last valid mark, and retry on the next trading day (§3.5).

Expected: about 2 rolls a year, plus re-strikes after large moves.

### 3.4 Fills and marks
- **Buy at ask, sell at bid**, using the closing quote of §3.2 step 4. No mid fills, ever.
- Fees: $0.05 per contract per side (regulatory and clearing proxy; Alpaca charges no
  commission), pro rata for fractional contracts.
- **Daily mark: mid** of the closing quote. If there is no valid closing quote on a day, carry
  the previous mark and count the contract-day as **missing**.
- Flag, but do not alter, any day where mid < max(S − K, 0) − (ask − bid). Deep-ITM American
  calls should not trade below intrinsic, so this flags bad prints.
- Marks come from one continuous `cbbo-1m` request per contract, from its entry date
  13:00 UTC to its exit date + 1 day (about $0.015 per contract-year).
- Multiplier 100. QQQ and SPY options are American and PM-settled. We never exercise, and
  every contract is rolled at DTE ≤ 180, so expiry is never reached.

### 3.5 Missing data and fallbacks (all counted for G6)
- **Chain EMPTY on an execution day:** the B arm holds its LETF instead of options for that
  month (QLD for B1, TQQQ for B2, UPRO for B3), sized exactly as A. It is a "fallback month".
- **Trade needed but no valid quote on t:** defer the whole option trade to the next trading day
  with a valid quote, up to 5 trading days. After 5, it is a fallback month.

---

## 4. Arms

All arms are holdings-based: units of ETF shares and fractional option contracts, which drift
with prices between executions. **Not** the constant-weight `_held_return` of
`challenger/backtest.py`: options cannot be held at constant weight. Arm A is re-implemented in
the same holdings engine so A and B differ only in the instrument.

Notional start NAV: $1,000,000 for every arm. Fractional contracts for every gated arm.

### H1 — challenger core sleeve (gated, primary)
- **A1:** on each BME decision date d, `w = sleeves.core_sleeve(px_through_d, budget=1.0)`.
  Hold QQQ / QLD / IEF at those weights, executed at t = d+1.
- **B1:** identical QQQ and IEF. The QLD slice `w_QLD · NAV` is replaced by:
  - LEAPS on the chain, with target dollar delta **D\* = 2 · w_QLD · NAV_B(t)**;
    n\* = D\* / (Δ_t · 100 · S_t);
  - SHV with whatever is left of the slice: `w_QLD · NAV_B − premium paid`.
  - If premium > slice, cap n so premium = slice and log the dollar-delta shortfall.
  - If w_QLD = 0, B1 sells every contract at the bid.
- `core_sleeve` is called with `px` as a DataFrame that contains at least the QQQ `adjClose`
  column, through d, exactly as the backtest passes it.

### H2 — champion-style constant 3x (gated, secondary)
- **A2:** 100% TQQQ, held throughout. Bought on the first execution; never traded again unless
  a fallback forces it.
- **B2:** LEAPS on the QQQ chain with D\* = **3 · NAV_B(t)**, resized every execution day.
  The rest is in SHV. Premium is capped at 100% of NAV (log the shortfall).

### R1 — SPY / UPRO constant 3x (reported only, no verdict, cannot be promoted)
Same as H2, on the SPY chain, against 100% UPRO. Run R1 only after H1 and H2 P results are
written, and only if the running spend is under $6.

### R2 — implementability (reported only)
B1 with **whole contracts**, at core-sleeve NAV = $1,000,000 and also at the live challenger's
actual size. The live challenger's account equity was $1,014.82 on 2026-10-13, so its core
sleeve is about 45% of that. Round n\* to the nearest integer, using the same rules otherwise.
Report the tracking error to the fractional B1 and the share of months with n = 0.

### R3 — marking sensitivity (reported only)
B1 and B2 marked at the **bid** instead of the mid. Fills are unchanged.

---

## 5. Rebalancing mechanics (identical for A and B)

On execution day t:
1. Compute target weights (A) or target weights plus D\* (B) from the decision at d = t−1.
2. **ETF legs:** if any |w_held − w_target| > 0.02 (current market-value weights), trade every
   ETF leg to target. Cost: 10 bp of traded notional for QQQ, QLD, IEF, TQQQ and UPRO (the
   `TCOST` in `challenger/backtest.py`), and 1 bp for SHV.
3. **Option leg (B):**
   - A roll or re-strike always trades.
   - Otherwise resize to n\* only if |D_held − D\*| / NAV > **0.02**, with D_held = n·Δ_t·100·S_t.
   - After the option trade, set SHV to the slice remainder (H1) or the NAV remainder (H2/R1).
4. Roll and re-strike checks (§3.3) run on every execution day, and **only** on execution days
   (monthly). There is no intra-month option trading, and no intra-month ETF trading.

---

## 6. Outputs per arm (write-once JSON + daily parquet)

Daily: NAV, return, SHV return, QQQ (or SPY) return, option-leg market value, n, Δ, D_held,
D\*, chain symbol, missing-quote flag. Write `daily_{arm}_P.parquet`.

Statistics on the metrics window:
- **Sharpe (primary, SHV-RF):** mean(r − r_SHV) / std(r − r_SHV) · √252. Also report Sharpe with
  constant RF = 4.5% (the challenger's `metrics()` convention).
- CAGR, vol, MaxDD (daily NAV), worst day, worst 21-day.
- **β:** OLS slope of the arm's daily return on the underlying's `adjClose` return. Also report
  down-day β (underlying return < 0) and up-day β.
- **d = r_B − r_A** (daily). μ_d = 252·mean(d). TE = √252·std(d).
- **Bootstrap:** stationary (Politis–Romano) bootstrap of d, mean block length 21, 10,000 reps,
  `numpy.random.default_rng(28)`. One-sided p = share of resampled means of (d − mean(d)) that
  are ≥ mean(d). Report the 95% CI of μ_d.
- **Cost accounting for B, per year, as % of mean NAV:**
  - spread paid: Σ|Δn|·100·|fill − mid|;
  - fees;
  - option time-value decay, = Σ over holdings of (mark − intrinsic) change, excluding trades;
  - SHV interest earned.
- **Cost accounting for A, per year:** the LETF's all-in drag versus ideal daily leverage,
  = 252·mean(r_LETF − (L·r_und − (L−1)·r_SHV)), with L = 2 (QLD) or 3 (TQQQ, UPRO).
- **Same residual for B's levered leg:** option-leg plus SHV daily return against
  (L·r_und − (L−1)·r_SHV) on the same slice. This is the head-to-head the hypothesis is about.
- **Stress:** recompute μ_d with every option half-spread × **1.5** (fills only; marks
  unchanged).
- **Coverage:** % of held contract-days with a valid closing quote; # deferred trades;
  # fallback months; # intrinsic-violation flags.
- The roll/re-strike log: date, old symbol, new symbol, DTE, Δ, bid, ask.
- Per-year μ_d and ΔSR.

---

## 7. Validity checks (any failure ⇒ INVALID, not FAIL; fix, log, re-run as v2)

- **V1 (A2 identity):** A2's NAV path equals the TQQQ `adjClose` total return to within 1e-9
  per day, net of the single entry cost.
- **V2 (causality):** set every price and quote dated after a random day k (5 draws, seed 28)
  to NaN or garbage. Every arm's daily returns and positions through day k must be unchanged.
- **V3 (no mid fills):** assert that every option fill equals the bid or ask of its quote row.
- **V4 (sizing):** right after each option trade (outside cap/shortfall cases),
  |D_held/D\* − 1| ≤ 0.001 for fractional arms.
- **V5 (OCC sanity):** for 5 random selections, print the symbol, strike, expiry, bid, ask, S,
  IV and Δ into `DECISIONS.md` for eyeball review. IV must be in [0.05, 0.80] and DTE within
  [270, 455].

---

## 8. Gates (frozen; copied from the ledger; ledger wins)

Applied separately to H1 (B1 vs A1) and H2 (B2 vs A2) on **P**. K = 2, Bonferroni α = 0.025.

| Gate | Rule |
|---|---|
| G1 edge | μ_d > 0 **and** one-sided bootstrap p < **0.025** |
| G2 risk-adjusted | Sharpe_B − Sharpe_A (SHV-RF) ≥ **+0.05** |
| G3 drawdown | MaxDD_B ≥ MaxDD_A − **2.0 pts** (B no more than 2 points deeper) |
| G4 exposure tracking | β_B / β_A ∈ **[0.90, 1.10]** over the window, **and** fallback months ≤ **5%** of months with D\* > 0 |
| G5 cost | (B's spread + fees per year) / mean(D\*/NAV) ≤ **0.50%** per unit of target dollar delta, **and** μ_d > 0 under the ×1.5 spread stress |
| G6 coverage | ≥ **95%** of held contract-days have a valid closing quote, **and** ≥ 95% of required option trades execute on their scheduled day. Failure ⇒ **INCONCLUSIVE** (not PASS, not FAIL; K still spent; no tuning). |

**P PASS** for a hypothesis = G1 ∧ G2 ∧ G3 ∧ G4 ∧ G5 ∧ G6 ∧ V1–V5.

**H confirmation** (one look, only for hypotheses that passed P). Write `run_H.py` only after
the P verdict is ledgered. H uses the same code; the only change is the date constants.
- H PASS = μ_d > 0 (point estimate; no p-value) ∧ ΔSR ≥ 0 ∧ G3 ∧ G4 ∧ G6.
- H FAIL ⇒ "does not replicate", and no shadow is built.

---

## 9. Cost plan (quoted 2026-10-13 via `metadata.get_cost`; nothing downloaded)

| Item | Unit quote | Count | Est. |
|---|---|---|---|
| QQQ definitions, P (BME-date mean $0.0045) | lazy, selection days only, ~4/yr | ~28 | ~$0.13 (≤ $0.38 if all 84 BME dates) |
| QQQ definitions, H (mean $0.0131) | lazy | ~25 | ~$0.33 (≤ $0.95) |
| QQQ chain marks, cbbo-1m continuous | $0.0075 per contract per 6 mo (2014 and 2021 quotes agree); $0.0146 per contract-yr in 2025-26 | ~13 contract-years ×1.3 | ~$0.25 |
| Selection snapshots (band of one expiry, 19:30–21:05 UTC) | ~$0.001–0.003 | ~55 | ~$0.10 |
| SPY (R1), definitions + marks + snapshots, both windows | SPY definitions mean $0.0085 (P) / $0.0165 (H) | — | ~$0.80 lazy (≤ $2.3) |
| **Total** | | | **≈ $1.6 lazy; ≤ ≈ $4.0 if definitions are pulled on every BME date. Hard stop $9.50.** |

Snapshot upper bound: the whole QQQ chain for one closing window is $0.011 (2014) to $0.055
(2026). Do **not** pull whole chains. Filter to the band first, using the definition file.

---

## 10. Deliverables to the strategist

- `results_P.json` and `verdict_P.json` (gate table with numbers).
- `daily_*_P.parquet`.
- `DECISIONS.md` (every ambiguity resolved before running, every flag).
- `spend_log.csv` with the final total.
- A ledger-ready RESULT block, appended under the EXP-028 entry. Re-read the ledger before
  writing, because others append. Report FAIL as plainly as PASS. Include the per-year table and
  the A-vs-B residual decomposition whatever the verdict.
