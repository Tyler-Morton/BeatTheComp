# EXP-026 build spec — no-trade band on the vol-target scaler (for an independent tester)

Binding companion to `research/experiments.md` § EXP-026 (pre-registered 2026-10-13 22:50:03 PDT).
If this spec and the ledger entry disagree, the ledger wins; report the disagreement.
Do not edit tracked files. Do not git push. Put all code/output under `research/exp026/`.

## 0. Engine
- Use the code at branch `worktree-agent-a755d2182dda758ab` (commit d6a6f81), worktree
  `.claude/worktrees/agent-a755d2182dda758ab/`. Import `challenger/backtest.py`,
  `challenger/sleeves.py`, `risk_overlay.py` from there (sys.path), never edit them.
- Write `research/exp026/run.py` containing a COPY of `run_book` named `run_book_band(px, budgets,
  target_vol, tcost, band)` that differs from `run_book` in exactly two places:
  1. `TCOST` → the `tcost` argument.
  2. After `s = vol_target_scaler(...)`, apply the band (below) and use `s_held` in `desired`.
  Keep everything else identical: day-i return accrues to `held` before the decision; 80-row
  window `dr.iloc[max(0,i-79):i+1]`; `VOL_MODEL`; BME base rebalance; `DRIFT = 0.02` max-abs
  gate; cost = tcost × Σ|ΔW| (incl. SHV) on executed trades; `CASH_YIELD` 2%.

## 1. Band rule (state `s_held`, init None)
```
s_new = vol_target_scaler(...)            # unchanged live call
if s_held is None: s_held = s_new
elif band.kind == "none": s_held = s_new                       # Arm 0
elif band.kind == "abs" and abs(s_new - s_held) > band.x: s_held = s_new
elif band.kind == "rel" and (s_held <= 1e-6 or abs(s_new/s_held - 1) > band.x): s_held = s_new
desired = {t: v * s_held ...}; desired[CASH] = base.get(CASH,0) + (1 - s_held) * sum(risky)
```
Arms: A0 none · B1 abs 0.05 · B2 abs 0.10 · B3 rel 0.10. Jump fully to s_new on trigger.
No asymmetric override. No other widths — ever, under this number.

## 2. Data
`challenger/backtest.load_data()` (Tiingo adjClose, startDate 2005-01-01, ffill; needs
`TIINGO_API_KEY` from `.env` — do not print its value) or an existing `prices_cache.parquet` with
all `ALL_TICKERS`. Record row count, first/last date, last date used ≤ 2026-10-09 (truncate px
there). Save a SHA-256 of the px parquet used into the output.

## 3. Runs
Book: `budgets = sleeves.SLEEVE_BUDGETS`, `target_vol = 0.16`. For each arm × tcost ∈
{0.0005 (primary), 0.0003, 0.0010}: one full-history sim → daily net returns. Also record per day:
s_new, s_held, traded flag, turnover, is_BME.
Descriptive only: `run_champion_proxy` with the same 4 bands at 5 bp (copy it the same way).

## 4. Windows (slice the full-history series; never re-run per window)
- D = 2007-01-03 … 2018-12-31. Score D first; write D results to the ledger (§7) BEFORE H.
- H = 2019-01-02 … 2026-10-09. Sealed. Compute only if ≥ 1 variant passes all D gates.

## 5. Metrics per arm/window
Sharpe_net = mean(r − 0.045/252)/std(r)·√252; CAGR; vol·√252; MaxDD on cumulative net equity;
turnover/yr = Σ two-sided |ΔW| / years; ES1% = mean of worst 1% of days (ceil count); worst day;
scaler-update days/yr; trade days/yr; mean |s_held − s_new|; turnover split BME-day vs other days;
deflated Sharpe with K = 3.

## 6. Gates (variant v vs A0, 5 bp unless noted) — exact
- F0 (else INVALID, stop): A0 at tcost=0.0010 equals the unmodified `backtest.run_book(px,
  SLEEVE_BUDGETS, 0.16)` to max |Δ| < 1e-12 on every day; band abs 0.0 equals A0 exactly.
- G1 TO_v ≤ 0.60·TO_0.
- G2 ΔS = S_v − S_0 ≥ −0.02 AND Holm-adjusted p < 0.05, where p = P(ΔS* ≤ −0.05) from a paired
  21-day moving-block bootstrap (resample block starts uniformly, circular wrap off, concatenate
  to window length, same indices for both arms), 10,000 reps, `np.random.default_rng(26)`.
  Holm across B1–B3: sort p ascending, compare p_(k) to 0.05/(4−k), stop at first failure.
- G3 MaxDD_v ≥ MaxDD_0 − 0.010 (drawdowns negative).
- G4 |ES1%_v| ≤ 1.05·|ES1%_0| AND vol_v ≤ 1.05·vol_0.
- G5 ΔS ≥ −0.03 at 3 bp; ΔS ≥ 0.00 at 10 bp.
- H: G1, G2 point only (report p), G3, G4. G5 reported.
- PASS = F0 + all D + all H. Several passers → highest D Sharpe_net @5bp; tie ≤ 0.01 → lower D TO.

## 7. Reporting
Append a `RESULT` block under EXP-026 in the ledger (append, don't rewrite the pre-registration):
D table (all arms × 3 costs), gate table with each number vs threshold, Holm p's, then H (if
opened) the same way, verdict PASS/FAIL/INVALID, any deviation from this spec, any bug found.
Save `research/exp026/results_D.json`, `results_H.json`, daily series parquet.
Champion-proxy numbers go under a "descriptive, not gated" heading.

## 8. Prohibitions
No band widths, books, windows, costs or metrics beyond these. No re-scoring after seeing results.
No orders, no account calls, no edits to tracked files, no git push. PASS authorises only a
proposal for a read-only paper shadow logger (Tyler's go-ahead required to build it).
