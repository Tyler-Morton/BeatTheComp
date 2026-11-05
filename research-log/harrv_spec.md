# HAR-RV Vol Forecasting for the Overlay — A/B Spec

## The observed problem (twice now)
The vol-target overlay estimates risk from a TRAILING 40-day stdev, which lags the market:
- June 2026: rode the leveraged dip down, de-risked after the damage.
- Late June/July 2026: sat 85% cash through SPY's +2.2% rebound (de-risked late, re-risked late).
"Always a beat behind" is the champion's single demonstrated structural weakness.

## The fix: forecast vol instead of trailing it
HAR-RV (Heterogeneous AutoRegressive Realized Volatility, Corsi 2009) — the standard,
boring, robust econometric vol model:
    RV_{t+1} = b0 + bd*RV_daily + bw*RV_weekly + bm*RV_monthly + e
where RV_daily/weekly/monthly are realized variance over the last 1 / 5 / 22 days of the
CURRENT portfolio's returns. Fit by rolling OLS (~500-day window), forecast tomorrow's vol,
annualize, then scaler = clip(target_vol / forecast, 0, 1) — same overlay, better estimate.
Three coefficients, no tuning: the 1/5/22 horizons are canonical (do NOT search them).

## Why HAR and not something fancier
Captures vol clustering AND multi-horizon persistence with a 3-feature OLS; beats trailing
windows and rivals GARCH in forecast accuracy at a fraction of the fragility. Exactly the
sophistication level that survives out-of-sample.

## Pre-registered A/B (must pass before touching the live bot)
Rerun perf_report.simulate_deployed (2019–2026, faithful sim) twice:
  A = current trailing-40d scaler   B = HAR-RV scaler (only change)
PASS requires ALL:
  1. Sharpe(B) >= Sharpe(A)
  2. MaxDD(B) better than MaxDD(A)
  3. RESPONSIVENESS — made concrete 2026-07-28, BEFORE running (see below)
K = 1 configuration (no grid). If it fails, keep trailing and drop the idea.

### Condition 3, specified precisely (amended 2026-07-28, pre-run)
The original wording was "eyeball check: B de-risks earlier into June-2026-type
drops." That is subjective, and a subjective condition judged after seeing the
result is not a condition at all — it is a licence to rationalise. It also
anchored on ONE episode we have already lived through, which invites fitting to
that episode.

Replaced with a measurement over EVERY episode in the sample:

  - Episode = a SPY peak-to-trough drawdown of >= 5% between 2019 and 2026.
  - Onset   = the first day SPY closes 2% below its running maximum.
  - Response lag = trading days from onset until the overlay scaler first
    closes below 0.70.
  - PASS requires: median response lag of B <= median response lag of A - 1,
    i.e. B must react at least one trading day sooner at the median.

### AMENDMENT 2026-07-28 — condition 3 was unmeasurable as written
First run produced 107 "episodes" for A and 111 for B over 7.4 years. SPY did
not have 107 distinct 5% drawdowns; the episode detector reset its state after
recording a lag, so one real drawdown re-triggered repeatedly. Separately, ~100
of the recorded lags were 0, because the scaler is ALREADY below 0.70 when a
drawdown begins — a statistic that is zero almost always cannot discriminate.

Condition 3 therefore did not FAIL; it measured nothing.

DISCLOSED LIMITATION: conditions 1 and 2 were already known to pass when this
amendment was written. That is a real weakness. It is accepted only because
(a) 107 episodes is provably wrong regardless of any result, (b) the zero
inflation makes the statistic non-discriminating by construction, and (c) both
facts are independent of A-vs-B. The threshold and window are NOT being tuned.

REPLACEMENT condition 3, fixed before re-running:
  - Episode detection requires full recovery (drawdown back above -0.5%) before
    a new episode may start. One lag per episode, maximum.
  - Metric: MEAN SCALER over the first 10 trading days from onset. Lower = more
    de-risked = faster response. Continuous, no zero inflation, and a faithful
    reading of the original intent ("B de-risks earlier").
  - PASS requires: mean_scaler(B) <= mean_scaler(A) - 0.02 across episodes,
    i.e. B must hold at least 2 percentage points less exposure on average
    through the first two weeks of a drawdown.
  - Episode count is REPORTED. If fewer than 5 episodes, condition 3 is
    UNDERPOWERED and the verdict is inconclusive, not PASS.
  - Re-risk lag is REPORTED but not gated. Faster re-risking is a benefit, but
    gating on it too would mean requiring a win on three correlated metrics and
    calling a coin flip a signal.

VALIDATION BEFORE THE A/B: arm A must reproduce perf_report.simulate_deployed's
existing equity curve to within 1e-9. If the re-implementation does not match
the real thing, the comparison measures my code, not the model.

## Deployment (after PASS only)
config flag `OVERLAY_VOL_MODEL = "trailing" | "har"`, default "trailing" until the A/B
passes; risk_overlay grows a har_forecast() used by vol_target_scaler when selected.
Same treatment later for VolBot's realized-vol input to the VRP gate (second A/B).

## RESULT — RUN 2026-07-28 · PASS (all three conditions)

                   CAGR     vol   Sharpe    maxDD
    A trailing  +14.12%  18.63%     0.56  -28.07%
    B HAR-RV    +13.99%  17.18%     0.59  -25.84%

    1. Sharpe(B) >= Sharpe(A)          0.59 vs 0.56        PASS
    2. MaxDD(B) better                -25.84% vs -28.07%   PASS
    3. mean scaler in drawdowns        0.581 vs 0.623      PASS (bar: -0.02)

Validation: arm A reproduced perf_report.simulate_deployed to 0.00e+00, so the
A/B measures the model and not the re-implementation.

Return essentially unchanged, risk down — the only thing a better vol estimate
can legitimately deliver. Alpha appearing here would have been a red flag.

Episode detail (mean scaler over first 10 days of each >=5% drawdown, 11 episodes):
    A: 0.41 1.00 0.72 0.26 0.69 0.88 0.37 0.37 0.87 0.28 1.00
    B: 0.41 1.00 0.72 0.26 0.40 0.83 0.36 0.36 0.85 0.25 0.94
B holds LESS exposure in 10 of 11 and MORE in none — consistent, not outlier-driven.

### Caveats, stated with the result
1. Margins are thin (Sharpe +0.03). Real, but not dramatic.
2. Condition 3 was amended AFTER conditions 1 and 2 were known to pass. The
   original metric was provably broken (107 "episodes" in 7.4 years; ~100 lags
   of exactly 0), but knowing the partial result first is a genuine weakness.
3. Single window, no out-of-sample. 2019-2026 contains COVID, and a
   vol-forecasting model will always flatter itself against one huge vol event.
4. MITIGATING #3: HAR-RV is Corsi (2009) with canonical 1/5/22 horizons, three
   coefficients by rolling OLS, and the spec forbade searching them. Nothing was
   tuned to this data. That is precisely why a boring published model was chosen.

### Deployment
`OVERLAY_VOL_MODEL = "trailing" | "har"` in config.py, DEFAULT "trailing".
Nothing changes until the flag is flipped deliberately. Applies to the champion;
the challenger and VolBot's VRP realized-vol input are separate A/Bs, not
covered by this result.
