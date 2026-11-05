# EXP-024 implementation spec: champion re-decision cadence and 3x cap

Written 2026-10-13 by the strategist, **before any EXP-024 backtest output existed**.
The pre-registration (hypothesis, gates, kill rule) is the EXP-024 entry in
`research/experiments.md`. If this spec and the ledger disagree, the ledger wins. Report the
disagreement; do not resolve it by picking the reading that passes.

This spec is meant to be built by an engineer who has not talked to the strategist. Every
number below is fixed. **Do not tune anything.** If something is ambiguous, pick the reading
closest to what live `main.py` does, write down the choice in `research/exp024/DECISIONS.md`
*before* running, and continue.

---

## 0. Ground rules for the tester

1. **Build on the FIXED code, not `main`.** The dev agent's branch
   `worktree-agent-a755d2182dda758ab` (worktree
   `/Users/tylermorton/Documents/IWillBeatS&P/.claude/worktrees/agent-a755d2182dda758ab`,
   commit `d6a6f81` at the time of writing) fixes several bugs:
   - same-day look-ahead in `challenger/backtest.py` (`run_book`, `run_champion_proxy`);
   - a drawdown breaker in `backtest.py` / `perf_report.py` that *deleted* losing days and
     so capped MaxDD at 30% by fiat;
   - `.bfill()` of pre-inception prices (BITO/AVUV);
   - misaligned HRP stats in `optimizer.optimize`.

   Import `optimizer`, `regime`, `risk_overlay`, `config`, `backtest` and `risk` **from that
   worktree** (put it first on `sys.path`). Record `git rev-parse HEAD` of the worktree in
   `results_D.json`. If the branch has moved past `d6a6f81`, use the new HEAD only if
   `git diff d6a6f81 HEAD -- optimizer.py regime.py risk_overlay.py risk.py config.py main.py`
   is empty. Otherwise pin `d6a6f81` and say so.
   - The optimizer fix changes only the *logged stats* (`expected_annual_return`,
     `annual_volatility`, `sharpe_ratio`), not the weights. `main.py`, `risk.py` and
     `regime.py` are byte-identical between `33c8745` and `d6a6f81` (verified 2026-10-13).
2. **Timing (non-negotiable).** A decision made from data through the close of day t is
   applied to the returns from t+1 onward. The weights held during day i are decided from
   prices with index ≤ i−1. Nothing computed from bar i may touch the return of bar i.
   - Live decides at ~09:30 ET on the prior close and fills near the open. The overnight gap
     between close(t) and open(t+1) is ignored. Disclose this as a limitation; do not model it.
3. **Do not edit tracked files.** All new code goes in `research/exp024/` (gitignored).
   Write the engine as `research/exp024/engine.py`, the runners as `run_D.py` and `run_H.py`,
   and the scoring as `score.py`. Never `git push`. Never place orders. No Alpaca trading calls.
4. **The holdout is sealed** (section 2). `run_D.py` must refuse to load any price dated
   before 2019-01-02. Only `run_H.py` reads the H file, and it runs only under the
   conditions in section 8.
5. **Result files are write-once.** Open them with `open(path, "x")` (exclusive create). A
   re-run that would overwrite a result is a bug, not a retry. If a genuine code bug is found
   after a result exists:
   - write `results_D.v2.json` alongside the original;
   - log the bug in `DECISIONS.md` with the diff;
   - report both, and gate on v2 only if the bug is unrelated to which arm wins.

---

## 1. Data

**Source:** Tiingo daily `adjClose`, using the loader pattern in `perf_report._load_tiingo`
(`TIINGO_API_KEY` from `.env`; never print it).
- Tickers: `config.ASSETS` (QQQ TQQQ UPRO SOXL TECL VGT MTUM IWM AVUV BITO VEA GLD TLT SHV)
  plus SPY.
- Range: 2009-01-02 → 2026-10-09 inclusive.
- **ffill only, never bfill.** Pre-inception dates stay NaN.
- Fallback if Tiingo fails for a ticker: yfinance `auto_adjust=True`, logged in `DECISIONS.md`.

Split once, at download time, into two files written with exclusive create:
- `research/exp024/prices_D.parquet`: rows with date ≥ 2019-01-02.
- `research/exp024/prices_H.parquet`: rows with date ≤ 2018-12-31.

**Integrity scan (allowed before results, like EXP-022):** row counts, first valid date per
ticker, number of zero-return days, max |daily return| and its date, per file. Write it to
`integrity.txt`. Compute **no strategy output** during the scan.

Expected inceptions:

| Ticker | Inception |
|---|---|
| TECL | 2008-12 |
| UPRO | 2009-06 |
| TQQQ | 2010-02 |
| SOXL | 2010-03 |
| MTUM | 2013-04 |
| AVUV | 2019-09 |
| BITO | 2021-10 |

**Data the H window cannot reproduce (disclosed):** H has no AVUV or BITO, and no MTUM
before mid-2014. That is the universe the champion would have had then.

---

## 2. Windows

| Window | Sim runs on | Metrics window | Role |
|---|---|---|---|
| **D** (development / primary gate) | prices_D only, 2019-01-02 → 2026-10-09 | **2020-01-02 → 2026-10-09** (≈6.8 y) | All gates. In-sample for the champion's regime map (tuned 2019–2026); out-of-sample for the variants, which have never been run. |
| **H** (sealed holdout / confirmation) | prices_H only, 2009-01-02 → 2018-12-31 | **2011-04-01 → 2018-12-31** (≈7.75 y) | Confirmation. No champion code has ever been run on pre-2019 data in this repo (backtest.py and perf_report.py both start 2019). |

The first year of each sim is warm-up. Trades and costs during warm-up are not scored.
Equity is re-based to 1.0 at the first metrics date.

---

## 3. The decision engine (shared by every arm)

One function, `decide(prices_upto, held, state, arm) -> (W_target or None, info)`, called
once per trading day i with `prices_upto = prices.iloc[:i]` (data through close i−1).

### 3.1 Lookback (replicates live `data.fetch_prices(lookback_days=252)`)
Live downloads `today − (252+90)` calendar days and keeps the last ≤252 rows. That is
≈235 trading rows (see the worktree's `risk_overlay.HAR_MIN_ROWS` comment).
- `px_win` = rows of `prices_upto` with date > (date of row i−1 − 342 calendar days), last
  252 at most.
- `ret_win = px_win[ASSETS].pct_change()`, drop the first row.
- **Column rule:** keep a ticker only if it has no NaN anywhere in `ret_win` and
  std > 1e-9. Live `get_returns().dropna()` drops rows; in the backtest we drop the
  incomplete *columns* instead, so pre-inception tickers are absent rather than truncating
  everyone's history. This is the worktree `backtest._simulate` rule.
- Then `ret_win = ret_win.dropna()`.
- If fewer than 20 rows remain, hold (no decision).

### 3.2 Base target (live steps 4–5, verbatim library calls)
- `regime = backtest._detect_regime_from_prices(px_win)`. It uses SPY/TLT from the same
  window, exactly like live `detect_regime`. **Do not** call `regime.detect_regime`, which
  writes to `regime_log.csv`.
- `strategy = optimizer.select_strategy(regime, returns=ret_win)`. Include the 0.5 floor; it
  is in the code.
- `B = optimizer.optimize(strategy=strategy, returns=ret_win, sentiment_modifiers={},
  regime=regime)["weights"]`.

  B is the **base target** (sums to 1, includes SHV as an optimizable asset).

### 3.3 Final target (live steps 5c–5d)
- `s = risk_overlay.vol_target_scaler(ret_win, B, target_vol=0.20, window=40,
  model="trailing")`. Pass `model` explicitly.
- `T = {k: s·B_k}`, then `T["SHV"] += (sum(B) − sum(T))` (this is `apply_overlay`; you may
  call `apply_overlay(B, ret_win, 0.20, use_ml=False, shadow_ml=False)` directly).
- **[Arm V3 only]** apply the 3x cap (section 4).
- Crumb fold: any non-SHV weight with 0 < w < 0.005 goes to SHV (`main.py:198-205`).

### 3.4 Risk gate (live step 6, `risk.run_all_checks`)
Re-implement without side effects. `risk._alert` writes `alerts.log`, and `check_drawdown`
reads `daily_log.csv`, so do not call them. Use identical arithmetic:
- **Drawdown:** E_{i−1} / max(E_0..E_{i−1}) − 1 < −0.30 → block. E is the simulated net
  equity (5 bp arm for the 5 bp run, etc.). Each cost level is a separate simulation.
- **Vol:** sqrt(wᵀ Σ₂₀ w) > 0.90, with Σ₂₀ = 252·cov of the last 20 rows of `ret_win` over
  the tickers in T (SHV included, as live) → block.
- **Concentration:** any non-SHV weight in T > 0.70 + 1e-6 → block.
- **Correlation:** mean upper-triangle pairwise corr of the last 20 rows of `ret_win` (all
  kept columns) > 0.85 → block.
- If blocked: no trade today. Holdings drift. Log the reason.

### 3.5 Drift gate (live step 7, `risk.should_rebalance`)
If max_k |T_k − H_{i−1,k}| < 0.02 → no trade. Otherwise trade fully to T.
- H_{i−1} = held weights after close i−1 (section 3.6).

### 3.6 Book accounting (all arms)
- If trading: W_i = T. Traded_i = Σ_k |T_k − H_{i−1,k}|, which **includes the SHV legs**.
  Otherwise W_i = H_{i−1}, Traded_i = 0.
- Gross day return: g_i = Σ_k W_{i,k} · r_{i,k}. Here r is the close(i−1)→close(i) return
  of the actual ticker, SHV included (live parks cash in real SHV, not at a constant
  RF_DAILY).
  - A held ticker with a NaN return that day contributes 0. This should not happen after
    inception; count it.
- Net day return: n_i = g_i − c · Traded_i, with c the cost in bp per $ traded (section 5).
- H_i = W_i ⊙ (1 + r_i) / (1 + g_i).
- Record each day: date, regime, strategy label, s, B, T, W, H, Traded, blocked reason,
  3x weight Σ_{TQQQ,UPRO,SOXL,TECL} W_i.

---

## 4. The arms

The baseline is not a variant. **K = 3 variants**, all parameters fixed here.

### Arm 0: AS-LIVE (baseline)
Section 3 run **every trading day**, exactly as live `main.py` at `d6a6f81`.

### V1: MONTHLY re-selection
- **Re-decision days:** the first trading day after each business-month-end (the decision
  uses data through the last trading day of the month; the trade happens the next session).
  This matches `simulate_deployed`'s BME + 1-day-lag timing. Also re-decide on the first
  trading day of the sim.
- **On re-decision days:** compute regime, strategy and B as in 3.2. Store B as the
  incumbent `B_inc`.
- **On every day (re-decision days included):** compute 3.3 → 3.6 using `B_inc`. The scaler
  is recomputed daily on the current `ret_win`. Risk gate and drift gate as live.
  - So V1 changes only how often the *selection and optimization* run. The overlay still
    rescales daily, exactly like the challenger after the C2 patch.
- **If the risk gate blocks on a re-decision day:** `B_inc` still updates. Only the trade is
  blocked. The next unblocked day trades to the scaled `B_inc`.

### V2: HYSTERESIS (daily, slow-changing target)
Every day, compute the live candidate (3.2) with two changes.

**(a) Label confirmation (N = 5).**
- Keep an incumbent regime `R_inc` and an incumbent strategy `S_inc`.
- Each day compute the raw regime `r_t = _detect_regime_from_prices(px_win)`.
- `R_inc` switches to a new value X only when r_t == X on 5 consecutive trading days (X ≠
  R_inc).
- **Exception:** a switch *to* RISK_OFF is immediate (safety asymmetry; declared now).
- Then compute the raw strategy `c_t = select_strategy(R_inc, ret_win)`. `S_inc` switches to
  Y only when c_t == Y on 5 consecutive trading days.
- Initial values: R_inc = r and S_inc = c on the first decision day.

**(b) Target smoothing (M = 10).**
- `B_t^raw = optimize(S_inc, ret_win, {}, R_inc)["weights"]`.
- `B_t = mean of B^raw over the last 10 decision days` (tickers missing on a day count as
  0), renormalised to sum 1. Fewer than 10 days available → mean of what exists.
- The bounds are not re-enforced after averaging. An average of feasible points is feasible
  for the box bounds. RISK_OFF floors could be violated across a regime switch; accept that
  and count the days.

Then 3.3 → 3.6 on B_t, daily. Risk gate and drift gate as live.
- *Why (b) exists:* on 2026-10-06 → 10-13 the book flipped TQQQ ↔ VGT four times with the
  label constant at HRP_MOMENTUM / RISK_ON (daily_log.csv). A label-only hysteresis cannot
  touch that churn.

### V3: MONTHLY + 3x CAP (30%)
V1 exactly, plus in 3.3 after the overlay and before the crumb fold:
- L = {TQQQ, UPRO, SOXL, TECL}.
- If Σ_{k∈L} T_k > 0.30, multiply each T_k (k ∈ L) by 0.30 / Σ_{k∈L} T_k, and add the
  removed mass to SHV.
- The cap applies to targets. Held weights may drift above 0.30 between trades. Report the
  max held 3x weight and the number of days held > 0.30.

### Reference arm R (reported only, never gated)
Worktree `perf_report.simulate_deployed` as-is on the same price files and metrics windows.
It is the monthly, constant-RF, zero-cost legacy sim, kept to show how far the live-faithful
replica (Arm 0) sits from the number the project has quoted until now.

---

## 5. Cost model
Cost is charged on every $ traded (both legs, SHV included), as a fraction of equity:
n_i = g_i − c · Traded_i.

| Level | c | Basis |
|---|---|---|
| Low | **3 bp** | C2 measured 1–3 bp/order arrival shortfall on paper fills |
| **Primary** | **5 bp** | Desk estimate: half-spread on TECL/TQQQ/BITO plus reg fees |
| High | **10 bp** | Stress; the challenger backtests' TCOST |

These are three separate simulations per arm, because the drawdown breaker depends on net
equity. Gross (c = 0) is also run and reported.

---

## 6. Metrics (per arm, per window, per cost level)
RF = `config.RISK_FREE_RATE`/252 constant (the `perf_report.metrics` convention; identical
across arms).

| Metric | Definition |
|---|---|
| **Sharpe_net** | (mean(n) − RF)/std(n)·√252 over the metrics window |
| CAGR, ann. vol | |
| **MaxDD** | min over the window of E/cummax(E) − 1, net |
| **Turnover** (TO) | Σ Traded_i · 252 / N_days. This is "× equity traded per year", the desk's 94× measure, two-sided |
| **Worst day** | min n_i, with its date |
| **ES1%** | mean of the worst ⌈1% · N_days⌉ net daily returns (negative number) |

Descriptive, not gated:
- beta to SPY;
- days traded (%);
- strategy-label switches/yr; regime switches/yr;
- TQQQ/VGT/each-3x in-or-out events/yr;
- mean and max 3x weight (W);
- days blocked by each risk check;
- 2026-06-05 net return and 3x weight that morning (D only).

**Turnover decomposition** (descriptive). Components may not sum, by the triangle
inequality. Over trade days:
- base component = Σ |s_i · (B_i − B_{prev})|;
- scaler component = Σ 2 · |s_i − s_{prev}| · Σ_{k≠SHV} B_{prev,k}. The non-SHV legs move
  by |Δs|·Σ_{k≠SHV}B, and the SHV leg moves by the same amount the other way;
- residual = Traded − base − scaler.

`prev` = values at the last trade.

---

## 7. Gates

All gates compare variant v to Arm 0 at the same cost level. Primary cost = 5 bp.

### F0: replica fidelity (Arm 0 only; checked first; failure ⇒ EXP-024 INVALID, nothing else is read)
On the dates in `daily_log.csv` from 2026-07-27 → 2026-10-09 (all rows with a log entry):

| Check | Requirement |
|---|---|
| (i) Strategy label | Arm 0's label equals the logged `strategy` on ≥ 85% of rows |
| (ii) Regime label | Arm 0's regime equals the logged `regime` on ≥ 85% of rows |
| (iii) Turnover | Arm 0's annualised TO over 2026-08-01 → 2026-10-09 within [0.5×, 2×] of live C2's 71×/yr, i.e. 35.5×–142× |

Mismatch sources to expect and disclose:
- Tiingo vs the yfinance/Alpaca closes live saw;
- the 0.5 floor and crumb fold were added 2026-10-13, so live rows before that ran without
  them;
- live row date = run date, which uses closes through the prior session. **Align: the log row
  dated D corresponds to the engine's decision for trading day D.**

### On window D (metrics 2020-01-02 → 2026-10-09)

| Gate | Requirement |
|---|---|
| **G1 turnover** | TO_v ≤ 0.50 × TO_0 at 5 bp |
| **G2 net Sharpe, non-inferior** | ΔSR = Sharpe_net,v − Sharpe_net,0 ≥ −0.03 at 5 bp (point estimate) **AND** paired block-bootstrap non-inferiority p_v below its Holm threshold (see test below) |
| **G3 drawdown** | MaxDD_v ≥ MaxDD_0 − 0.020 at 5 bp (not more than 2.0 pts deeper) |
| **G4 tail** | ES1%_v ≥ 1.10 × ES1%_0 at 5 bp (tail loss no more than 10% larger in magnitude) |
| **G5 cost robustness** | ΔSR ≥ −0.05 at 3 bp **and** ΔSR ≥ 0.00 at 10 bp |
| **G6 (V3 only)** | the cap's stated purpose. ES1%_V3 ≥ 0.90 × ES1%_0 at 5 bp (tail ≥ 10% smaller) **and** worst day_V3 > worst day_0 |

The G2 test:
- **Paired blocks:** resample the same indices for both arms' 5 bp net daily return series
  (moving blocks of 21 days, 10,000 reps, numpy `default_rng(24)`).
- Compute Δ* = Sharpe(v*) − Sharpe(0*) each rep.
- p_v = share of reps with Δ* ≤ −0.10. The non-inferiority margin is **0.10 Sharpe**.
- **Holm across the 3 variants at family α = 0.05.** Sort the p's ascending. Compare to
  0.05/3, 0.05/2, 0.05/1. Stop at the first failure; that one and all later ones fail G2.

### On window H (metrics 2011-04-01 → 2018-12-31), only if opened (section 8)
- **G1, G2 (point estimate only: ΔSR ≥ −0.03 at 5 bp), G3 and G4** must hold. G6 also holds
  for V3.
- The bootstrap p is reported, not gated.
- G5 is reported, not gated.

### Verdict
- A variant **PASSES** iff F0 passes, it passes every D gate, and it passes every H gate.
- **Promotion if more than one passes** (decided on D only; H never selects): highest D
  Sharpe_net at 5 bp. A tie within 0.02 goes to the shallower D MaxDD.
- No variant passes → **EXP-024 FAIL**. The champion is unchanged.

---

## 8. Execution order and sealing
1. Download and split (section 1). Integrity scan → `integrity.txt`.
2. Write `DECISIONS.md` (any ambiguity readings) and `engine.py`. Unit-check on D's warm-up
   year only (2019):
   - the timing assertion (weights used on day i were decided before i);
   - Σ W = 1 ± 1e-9 every day;
   - Arm 0 with c = 0 and the risk/drift gates disabled reproduces a direct
     `optimize`-per-day loop.
3. `run_D.py`: F0 first. Write `results_D_F0.json` (exclusive create).
   - If F0 fails, stop: EXP-024 INVALID (replication). Do not compute variant metrics.
4. `run_D.py`: all arms × {0, 3, 5, 10} bp on D. Write `results_D.json` (exclusive create)
   containing every metric, the gate table, the Holm table and the per-variant D verdict.
5. **Paste the D results into the ledger** (EXP-024 RESULT, "D" subsection) before H is
   loaded.
6. **H is opened only if ≥ 1 variant passed all D gates.** Otherwise H stays sealed and
   unspent; say so in the ledger.
   - If opened, `run_H.py` runs **all arms** (so H is spent exactly once) and writes
     `results_H.json` (exclusive create).
7. `score.py` produces the final verdict table from the two JSONs. Ledger it verbatim.

**Not allowed under EXP-024:**
- any other N, M, cap level, cadence or cost;
- an overlay no-trade band;
- dropping the drift gate;
- re-running H;
- substituting a different metric for a failed gate.

Each of those is a new experiment with a new number and a new K.

---

## 9. What PASS authorises
**Only a paper shadow.**
- A read-only logger runs the promoted variant's `decide()` daily in the champion workflow.
  It writes target weights, label and scaler to `research/exp024/shadow_log.csv` (or a new
  untracked CSV), with **no orders and no change to the champion book**.
- Building that logger is a separate dev task and needs Tyler's go-ahead.
- Replacing the champion's logic needs a *separate* pre-registered live-vs-shadow check after
  ≥ 60 sessions, plus Tyler's go-ahead.

FAIL or INVALID authorises nothing.

---

## 10. Deliverables checklist (`research/exp024/`)
- `prices_D.parquet`, `prices_H.parquet`, `integrity.txt`, `DECISIONS.md`
- `engine.py`, `run_D.py`, `run_H.py`, `score.py`
- `results_D_F0.json`, `results_D.json`, `results_H.json` (if opened); all exclusive-create
- `daily_<arm>_<window>_<bp>.parquet`: the per-day records from section 3.6
- A ledger RESULT block with:
  - the gate table;
  - the binding constraint in one line, with its number;
  - the pattern check against prior deaths (C2, 022);
  - the next structure.
