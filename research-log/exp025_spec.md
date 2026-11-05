# EXP-025 implementation spec: trend sleeve inside the challenger overlay vs a T-bill control

Written 2026-10-13 by the strategist, **before any EXP-025 arm was simulated**. The
pre-registration (hypothesis, gates, kill rule, priors) is the EXP-025 entry in
`research/experiments.md`. If this spec and the ledger disagree, the ledger wins. Report the
disagreement; do not resolve it by picking the reading that passes.

This is written for an engineer who has not talked to the strategist. Every number is fixed.
**Do not tune anything.** If something is ambiguous, pick the reading closest to what live
`challenger/main.py` + `risk_overlay.apply_overlay` do, write the choice in
`research/exp025/DECISIONS.md` *before* running, and continue.

---

## 0. Ground rules

1. **Fixed engine only.** Import `challenger/backtest.py`, `challenger/sleeves.py` and
   `risk_overlay.py` from the worktree
   `/Users/tylermorton/Documents/IWillBeatS&P/.claude/worktrees/agent-a755d2182dda758ab`
   (branch `worktree-agent-a755d2182dda758ab`, commit `d6a6f81`). Put the worktree root and its
   `challenger/` first on `sys.path`. Record `git rev-parse HEAD` in every results JSON. If HEAD
   has moved, use it only if `git diff d6a6f81 HEAD -- challenger/backtest.py challenger/sleeves.py risk_overlay.py`
   is empty; otherwise pin d6a6f81 and say so.
   The main checkout's `challenger/backtest.py` still has the same-bar look-ahead (rebalance
   then earn day i). Do **not** import from main.
2. **Timing.** Day i's return accrues to the weights held coming into day i (fixed run_book
   convention). Nothing computed from bar i touches bar i's return.
3. **Do not edit tracked files.** All code in `research/exp025/` (gitignored). No commits, no push.
4. **No API calls except one Tiingo fetch** (§2.3), key read from `.env` by name
   (`TIINGO_API_KEY`); never print it. No Alpaca, no Anthropic, no orders.
5. **Stages are sealed.** `python3 -I run.py is` computes and prints only IS-window statistics.
   `run.py ho` refuses to run unless `research/exp025/IS_WRITTEN` exists, which the strategist
   creates after writing the IS result into the ledger. The sim itself runs on full history in
   both stages (warm-up continuous); only the scored months are sliced.

## 1. Files to produce (`research/exp025/`)

| file | content |
|---|---|
| `DECISIONS.md` | ambiguity calls, written before running |
| `data.py` | loads/assembles every input of §2; writes `inputs_manifest.json` (row counts, first/last date, NaN counts, sha256 of each source file) |
| `engine.py` | `run_book_x(...)` (§3) |
| `run.py` | stages `sanity`, `is`, `ho` |
| `sanity_output.txt`, `is_output.txt`, `is_results.json`, `ho_output.txt`, `ho_results.json` | outputs |
| `monthly_IS.csv`, `monthly_HO.csv` | month, A, B, C, B_dbmf (HO only), A_asis, SPY, rf, sB, sC, sA (mean scaler that month) |

## 2. Data

### 2.1 Daily prices
`challenger/prices_cache.parquet` (Tiingo adjClose, 2005-01-03..2026-06-09; columns include
SHV from 2007-01-11). Use it as `px`. The scored window ends 2026-05 so `live_prices.parquet`
is **not** needed for gates. (Optional, reported-only: nothing.)

### 2.2 Monthly series (already on disk; do not re-download)
`research/tradingroom_2026-10-13/exp020_dl/`:
- `tsmom.xlsx`, sheet "TSMOM Factors", column `TSMOM` (all-asset, excess, gross). Parse exactly
  as `exp020/run.py` does. Index = month period. Last month 2026-05.
- `tb3ms.csv`: TB3MS/1200 = monthly rf (used for Sharpe excess and as fallback only).

### 2.3 DBMF daily (one fetch)
Tiingo `daily/DBMF/prices`, startDate 2019-05-01, endDate 2026-06-09, adjClose. Save to
`research/exp025/dbmf_daily.parquet`. Check: monthly compounded 2022 calendar return within
±1.5 pts of +21.6% (red team's Yahoo number). If outside, stop and report; do not proceed.

### 2.4 Derived series
- `dr = px.pct_change(fill_method=None)` (as run_book).
- `shv_d` = SHV daily return. Before SHV's first valid day (warm-up only, never scored),
  use TB3MS_m/21 for that month.
- `shv_m` = SHV monthly total return = compounded `shv_d` by calendar month.
- **AQR sleeve monthly:** `R_m = TSMOM_m + shv_m − 0.02/12`. (Haircut h = 0.02 primary; grid
  {0, 0.01, 0.03, 0.04} reported-only, each its own sim.)
- **AQR sleeve daily (smoothed):** for each trading day d in month m with n_m trading days in
  `px.index` for that month: `r_d = (1 + R_m)^(1/n_m) − 1`. Build a synthetic price column
  `MFUT = cumprod(1 + r_d)` on `px.index`, appended to `px` as `px_aug`. For the partial month
  2026-06 (no AQR value), MFUT returns are NaN → treated as 0 by `_held_return`; this month is
  never scored.
- **B_dbmf daily:** MFUT_dbmf = AQR smoothed through 2019-05-31, then DBMF daily returns from
  2019-06-03. (First DBMF day must exist in the fetched file; DBMF's first price is 2019-05-08,
  so the 40d window has ≥ 15 real DBMF rows by 2019-06-03.)
- **SPY monthly** for crisis months and reported comparisons: compounded `dr["SPY"]` from the same
  cache (not Yahoo).

## 3. Engine: `run_book_x`

Copy the FIXED `run_book` body verbatim and add exactly these hooks (defaults reproduce it):

```python
def run_book_x(px, budgets, target_vol, *, mfut_asset=None, cash_ret=None,
               scaler=None, tcost=bt.TCOST, log=None) -> pd.Series
```
- `combined_weights` is called with a builders dict that adds
  `"mfut": lambda px, b: {mfut_asset: b}` (if `mfut_asset == "SHV"` this merges into CASH,
  exactly like sleeves' CASH handling). Build it locally; do NOT apply the EXP-020 patch to
  `sleeves.py`.
- `cash_ret`: if None, CASH earns `bt.CASH_YIELD/252` (as-is). If a Series, CASH earns
  `cash_ret.loc[day]`. Write a local `_held_return_x`; keep NaN→0 for risky assets as in
  `_held_return`.
- `scaler`: if None, `vol_target_scaler(dr.iloc[max(0,i-79):i+1], risky, target_vol, model=VOL_MODEL)`
  (live). Otherwise call `scaler(i, dr, risky, target_vol)`.
- `log`: if a dict is passed, append per day: date, s, sum(risky weights)·s (gross risky),
  turnover on trade days.
- Start index 260, BME rebalance set, DRIFT 0.02, TCOST 10 bp — unchanged.

### 3.1 Structured scaler for arm B (MFUT is monthly-smoothed)
Smoothed MFUT has ~zero daily variance and would fake a re-lever. For arm B (AQR primary and
the h-grid) use `scaler_struct`:
1. `cols` = risky tickers with |w| > 1e-9, excluding `MFUT`; normalise ALL risky weights
   (incl. MFUT) by their sum, as `portfolio_vol` does → w_r (vector over cols), w_s (MFUT).
2. Σ_rr = `dr[cols].iloc[max(0,i-79):i+1].tail(40).dropna(how="all").cov() × 252` (identical to
   `portfolio_vol` with window 40; if < 10 rows → s = 1.0 as live).
3. Let m = month of day i. Monthly window = months m−37 .. m−2 inclusive (36 months; m−1 is
   skipped for AQR's publication lag). Monthly ticker returns = compounded `dr` by month;
   sleeve monthly = `R_m`. σ_s² = var(R) × 12; Σ_rs[t] = cov(ticker t, R) × 12, each over the
   months where both exist, requiring ≥ 12 overlapping months, else that entry = 0 and log it.
   σ_s² requires ≥ 12 months (always true; AQR starts 1985).
4. Augmented Σ = [[Σ_rr, Σ_rs],[Σ_rsᵀ, σ_s²]]. If min eigenvalue < 0: multiply Σ_rs by 0.5,
   repeat up to 10 times; log count of days this happened.
5. pv = sqrt(wᵀ Σ w); s = clip(0.16 / pv, 0, 1); pv ≤ 1e-6 → s = 1.0.
For B_dbmf: live `vol_target_scaler` for days ≥ 2019-06-03 (DBMF is a real daily ticker in
the 40d cov — exactly what live would do); `scaler_struct` before that.
A and C: live `vol_target_scaler`, unchanged (C's SHV is CASH and never enters the scaler).

## 4. Arms

| arm | budgets | mfut_asset | cash_ret | scaler | gated |
|---|---|---|---|---|---|
| A_asis | SLEEVE_BUDGETS | — | None (flat 2%) | live | no (anchor) |
| A | SLEEVE_BUDGETS | — | shv_d | live | no (reported) |
| **B** | MFUT_BUDGETS (below) | "MFUT" (AQR, h=2%) | shv_d | scaler_struct | **yes** |
| **C** | MFUT_BUDGETS | "SHV" | shv_d | live | **yes** |
| B_dbmf | MFUT_BUDGETS | "MFUT" (AQR→DBMF spliced) | shv_d | struct → live | downgrade check |
| B_h{0,1,3,4} | MFUT_BUDGETS | "MFUT" (AQR, h grid) | shv_d | scaler_struct | no |
| B_5bp, C_5bp | as B, C | | | | tcost 5 bp; no |
| B_dbmf_smooth | MFUT_BUDGETS | DBMF monthly, smoothed like AQR, HO only | shv_d | scaler_struct (with DBMF monthly as R) | no (calibration) |

`MFUT_BUDGETS = {"core": 0.315, "trend": 0.0, "lowvol": 0.196, "ballast": 0.189, "mfut": 0.30}`
(= EXP-020 patch's `MFUT_BUDGETS_PROPOSED`). Define it locally.

## 5. Stage `sanity` (must pass before `is`; INVALID otherwise)
- **F0:** `run_book_x(px, SLEEVE_BUDGETS, 0.16)` with all hooks default equals fixed
  `bt.run_book(px, SLEEVE_BUDGETS, 0.16)` with max |Δ daily| < 1e-12.
- **F1:** `run_book_x(px, {..., "mfut": 0.0}, 0.16, cash_ret=shv_d)` equals arm A (SHV cash)
  to < 1e-12.
- Print data manifest checks (§2.3 DBMF 2022, no NaN in TSMOM 2004-06..2026-05, SHV first date).
- Prints NO arm-B or arm-C statistic of any window.

## 6. Scoring (identical code for IS and HO)

Windows: **IS 2007-07..2019-05**, **HO 2019-06..2026-05** (month periods). Monthly series:
`m_X = (1+daily_X).groupby(period M).prod() − 1`, sliced to the window. rf = TB3MS/1200.

- **Sharpe (the EXP-025 definition):** `e = m − rf; mean(e)/std(e, ddof=1)·√12`.
  Also report `bt.metrics(daily)['sharpe']` (daily, flat 4.5% hurdle) labelled "hurdle Sharpe".
- **MaxDD:** on month-end equity `cumprod(1+m)` with a leading 1.0 (EXP-020's `maxdd`).
- **Worst rolling 12m, CAGR, vol (monthly √12), Calmar.**
- **Crisis mean:** SPY's worst-decile months of the window: `thr = quantile(spy_m, 0.10)`,
  mask `spy_m ≤ thr`; statistic = mean(m_B − m_C) over the mask.
- **Bootstrap:** paired circular moving-block, block 12, 10,000 reps, `np.random.default_rng(20261013)`,
  index generator identical to `exp020/run.py: boot_idx`. Resample rows of (B, C, SPY, rf)
  jointly; recompute ΔSh and the crisis mean (decile mask re-identified in each resample).
  P = fraction of Δ* ≤ 0 (uncentred). 90% CI = 5th/95th percentiles of ΔSh*.
- **LOYO (G4):** for each calendar year Y with ≥ 1 month in the window, drop Y's months from
  both B and C (and rf), recompute ΔSh(B−C). G4 statistic = min over Y; print every Y's value,
  and label ex-2008 / ex-2022.

### Gates (both windows; all must pass)
| gate | rule |
|---|---|
| G1 | ΔSh(B−C) > 0.00 AND 90% CI low ≥ −0.10 |
| G2 | crisis mean(B−C) > 0 AND P(≤0) < 0.025 |
| G3 | MaxDD(B) − MaxDD(C) ≥ +2.0 pts (B less severe) |
| G4 | min LOYO ΔSh(B−C) ≥ −0.10 |
| downgrade (HO only) | B_dbmf vs C: ΔSh < −0.10 OR crisis mean ≤ 0 → PASS becomes INCONCLUSIVE |

Verdict logic exactly as the ledger: PASS / PARTIAL (G2 & G3 pass both windows; G1 or G4
fails) / FAIL / INVALID / INCONCLUSIVE. If IS fails, `ho` still runs once (after IS_WRITTEN)
and prints "descriptive only — verdict FAIL".

### Reported-only (print, no verdict weight)
- Full metric table for A_asis, A, B, C (and B_dbmf in HO); B−C per calendar year (pp).
- **Re-lever diagnostics:** per arm, mean s, % days s < 1, mean gross risky exposure
  (Σ risky × s), and B−C difference in mean gross exposure of the NON-sleeve risky part.
  Strategist's stated prediction: s = 1 on most days in every arm; B's re-lever CAGR gain over
  C < 1 pt/yr. Print the number of days `scaler_struct` needed PSD shrinkage.
- Haircut grid, 5 bp costs, DSR of B (`bt.deflated_sharpe(daily_B, 5)`).
- HO calibration: B_dbmf_smooth vs B_dbmf on 2019-06..2026-05 — ΔSh, ΔMaxDD, crisis mean,
  mean |Δs| — this measures what smoothing + structured cov get wrong.
- 2026-06+ AQR months are NOT used; if AQR has published them by run time, do not download.

## 7. If PASS: the 3-arm paper shadow (design frozen now; building needs Tyler's go-ahead)

Measurement instrument, not an edge test. Read-only logger; no orders; no change to
`challenger/main.py`, `sleeves.py`, `risk_overlay.py`, or any workflow without Tyler's go-ahead.
- Arms: A = live challenger targets; B = `MFUT_BUDGETS_PROPOSED` with **DBMF** inside the live
  overlay (live `vol_target_scaler`); C = same with SHV (cash). Same monthly base, DRIFT, TV.
- **Valuation from adjusted closes (Tiingo adjClose), not paper equity.** EXP-021 found the paper
  account does not credit dividends; SHV's return is almost all distributions and DBMF pays a
  large annual distribution, so paper equity would bias C and B.
- Log daily: targets per arm, s per arm, arm returns, DBMF/KMLM/CTA/SPY/SHV returns. KMLM and
  CTA are reported-only; the fund is DBMF and is not switched later.
- Frozen before day 1 (written into the ledger when the shadow starts): replication gap
  (DBMF monthly vs AQR TSMOM when AQR posts: β, residual vol); realised s(B) vs s(A); B−C
  tracking error; DBMF β to SPY on SPY-down weeks.
- **Shelve rules** (after ≥ 126 sessions): DBMF's β to SPY in SPY-down weeks ≥ 0, OR cumulative
  B−C < −3% with no SPY drawdown worse than −10% in the window → sleeve shelved.
  **Event rule:** if SPY draws down ≥ 10% from a high during the shadow, B vs C on that episode
  (peak → trough → recovery to the prior high or 63 sessions, whichever first) is scored once
  as a single pre-declared event.
- Any live allocation change needs its own pre-registration plus Tyler's go-ahead.

## 8. Things that are easy to get wrong
- Importing `backtest` from the main checkout (look-ahead version). Check F0 against the
  worktree's `bt.run_book`.
- Letting the smoothed MFUT column into the 40d cov (fakes a re-lever for B).
- Crediting cash at flat 2% in B/C (hands B a fake 2023–26 edge over T-bills).
- Scoring MaxDD on the daily path (B's sleeve has no intra-month path).
- Using `bt.metrics` Sharpe for gates (it is a 4.5%-hurdle ratio; see ledger reconciliation:
  same series reads 0.65 there and 0.98 under the monthly-TB3MS definition).
- Printing any HO number during `is`.
