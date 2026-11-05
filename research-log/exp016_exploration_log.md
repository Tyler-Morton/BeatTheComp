# EXP-016 exploration log

Calibration window only. Every cut examined is recorded here. Nothing in this file is evidence.

## Run 2026-09-13 18:09 UTC

Holdout seal: asserted (no holdout `result` loaded; tickers disjoint).
Resolutions read: 6,122 rows (112 with unparseable dates dropped). Calibration window: 5,500 markets. Holdout: 510 markets.
Calibration markets with a snapshot >= 24h before close and a yes/no result: 2,255. Tradeable: 787. Non yes/no results excluded: 34 ({'no': 3852, 'yes': 1614, 'scalar': 34}).
`liquidity` > 0 in 0 of 2,182,656 snapshot rows (confirms the column is dead).
Fees computed at M = 1 for every series (per-series multipliers not yet looked up). Flagged.

### A. Calibration curve, all usable markets (mid at the 24h snapshot)

| mid bucket | n | clusters | mean mid | YES rate | gap | tradeable n | tradeable YES rate |
|---|---|---|---|---|---|---|---|
| 0.00–0.02 | 1139 | 76 | 0.006 | 0.4% | -0.3c | 95 | 1.1% |
| 0.02–0.05 | 180 | 52 | 0.029 | 2.2% | -0.7c | 110 | 2.7% |
| 0.05–0.10 | 90 | 39 | 0.069 | 6.7% | -0.2c | 83 | 7.2% |
| 0.10–0.20 | 72 | 31 | 0.144 | 16.7% | +2.3c | 70 | 17.1% |
| 0.20–0.30 | 29 | 19 | 0.242 | 27.6% | +3.4c | 28 | 28.6% |
| 0.30–0.50 | 66 | 32 | 0.405 | 39.4% | -1.1c | 49 | 36.7% |
| 0.50–0.70 | 55 | 29 | 0.594 | 80.0% | +20.6c | 55 | 80.0% |
| 0.70–0.80 | 41 | 30 | 0.755 | 70.7% | -4.8c | 41 | 70.7% |
| 0.80–0.90 | 62 | 29 | 0.856 | 93.5% | +8.0c | 61 | 93.4% |
| 0.90–0.95 | 69 | 38 | 0.925 | 94.2% | +1.7c | 67 | 94.0% |
| 0.95–0.98 | 80 | 37 | 0.966 | 96.2% | -0.3c | 71 | 95.8% |
| 0.98–1.00 | 372 | 54 | 0.993 | 99.7% | +0.4c | 57 | 100.0% |

### B. Buy the favorite, by favorite price (tradeable, C=100, after fees + collateral)

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| favorite 0.50–0.60 | 50 | 27 | +2.79c | [-12.00, +16.89] | 0.340 | 63% |
| favorite 0.60–0.70 | 52 | 27 | +10.08c | [-2.01, +20.75] | 0.047 | 74% |
| favorite 0.70–0.80 | 69 | 34 | -12.32c | [-26.20, +0.29] | 0.972 | 59% |
| favorite 0.80–0.90 | 129 | 41 | -3.75c | [-13.30, +4.54] | 0.792 | 76% |
| favorite 0.90–0.95 | 149 | 53 | -1.01c | [-7.05, +3.75] | 0.608 | 89% |
| favorite 0.95–1.00 | 338 | 74 | -0.73c | [-3.88, +1.13] | 0.657 | 92% |
| favorite >= 0.70 | 685 | 99 | -0.85c | [-4.28, +2.07] | 0.676 | 77% |
| favorite >= 0.70, fees at C=1 | 685 | 99 | -1.58c | [-5.12, +1.36] | 0.823 | 60% |
| ALL favorites | 787 | 103 | -0.03c | [-3.77, +3.20] | 0.483 | 79% |

### I. Buy the longshot, by favorite price (the mirror of B)

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| longshot vs favorite 0.50–0.70 | 102 | 40 | -25.18c | [-35.91, -13.65] | 1.000 | 18% |
| longshot vs favorite 0.70–0.90 | 198 | 50 | -5.60c | [-13.01, +2.44] | 0.917 | 28% |
| longshot vs favorite 0.90–1.00 | 487 | 89 | -2.91c | [-5.53, +0.62] | 0.950 | 8% |

### C. Buy the favorite >= 0.70, by category

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| Climate and Weather | 1 | 1 | — | — | — | — |
| Companies ⚠ under 10 clusters | 2 | 2 | +4.66c | [+0.92, +8.40] | 0.000 | 100% |
| Economics ⚠ under 10 clusters | 7 | 7 | +3.61c | [+1.05, +8.46] | 0.000 | 100% |
| Elections | 314 | 23 | -5.80c | [-15.19, +0.91] | 0.939 | 61% |
| Financials | 209 | 25 | +2.48c | [-1.50, +6.05] | 0.105 | 72% |
| Politics | 109 | 28 | +1.02c | [-2.77, +4.35] | 0.283 | 86% |
| Science and Technology | 43 | 13 | +1.54c | [-4.53, +7.08] | 0.282 | 85% |

### D. Buy the favorite >= 0.70, by snapshot horizon before close

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| 24h before close (frozen) | 685 | 99 | -0.85c | [-4.31, +2.09] | 0.669 | 77% |
| 72h before close | 787 | 101 | +1.39c | [-1.29, +3.61] | 0.131 | 82% |
| 168h before close | 826 | 89 | -0.85c | [-5.41, +3.06] | 0.630 | 75% |

### E. Buy the favorite >= 0.70, by spread at the snapshot

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| <= 1c | 251 | 51 | -2.33c | [-7.82, +2.00] | 0.823 | 84% |
| 1–3c | 152 | 47 | +1.48c | [-3.32, +5.07] | 0.236 | 89% |
| 3–7c | 230 | 61 | -0.57c | [-5.78, +3.70] | 0.575 | 82% |
| > 7c | 52 | 24 | -4.37c | [-16.91, +5.98] | 0.767 | 75% |

### F. Buy the favorite >= 0.70, by open-interest tercile

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| low OI | 228 | 47 | -0.86c | [-6.00, +3.19] | 0.604 | 77% |
| mid OI | 228 | 65 | -0.20c | [-3.88, +3.11] | 0.522 | 85% |
| high OI | 229 | 63 | -1.46c | [-7.03, +3.13] | 0.703 | 89% |

### G. Buy the favorite >= 0.70: stale vs active price history

| cut | n | clusters | mean excess | 95% CI | P(<=0) | clusters > 0 |
|---|---|---|---|---|---|---|
| stale (>= 6 snapshots, 1 distinct mid) ⚠ under 10 clusters | 13 | 9 | +2.07c | [+0.73, +3.74] | 0.000 | 100% |
| active (everything else) | 672 | 99 | -1.06c | [-4.62, +1.95] | 0.718 | 77% |

### H. Round-number stickiness (descriptive)

Tradeable asks on a multiple of 5c: 15.9% (uniform over 1–99c would be 19.2%).

### J. One-sided extremes (not tradeable, descriptive)

ask <= 1c, no bid: 900 markets, 54 clusters, YES rate 0.11%
bid >= 99c, no offer: 288 markets, 36 clusters, YES rate 99.65%

### K. Holdout progress toward the Phase 2 sample bar (NO outcomes read)

Tradeable holdout contracts so far: 132 of 400 needed. Primary clusters: 23 of 60 needed.

### Deferred (not examined this run)

- Kalshi vs Polymarket divergence: needs a validated cross-venue market matcher first.
- Primaries after the result is effectively known: look-ahead-prone, needs its own definition.

### Reviewer read of this run (2026-09-13), written before Phase 2 is registered

About 30 cuts were estimated. At that count, roughly one or two P < 0.05 results
are expected by chance alone, so single tempting numbers are treated as noise
unless there is a mechanism AND a realistic path to the sample bar.

Headline: pooled "buy the favorite >= 0.70" is -0.85c per contract after fees and
collateral (95% CI -4.28 to +2.07). The published bias is visible only where it
cannot be traded: 900 markets quoted ask <= 1c with no bid resolved YES 0.11% of the
time. The tradeable middle is roughly calibrated, minus the spread. This matches the
prior written at registration.

NOT carried, with reasons:
- Favorite 0.60-0.70 (+10.08c, P = 0.047): the adjacent band 0.70-0.80 is -12.32c.
  Neighbouring bands flipping sign by 22c is the signature of small-sample noise.
- Stale favorites (+2.07c, 9 clusters): 13 markets in seven weeks. The per-hypothesis
  sample bar (400 contracts, 60 clusters) would take years. Permanently underpowered.
- 72h horizon (+1.39c): switching away from the frozen 24h horizon to the one that
  looks best is the EXP-013 error. Not permitted.
- 0.95-1.00 favorites show 92% of clusters positive but a negative mean: rare large
  losses on near-certain contracts. The EXP-007b shape (wins often, loses money).

PROPOSED carry (NOT registered, awaiting Tyler):
- H1: buy the favorite at >= 0.70 in every category EXCEPT Elections.
  Calibration: Financials +2.48c (25 clusters), Politics +1.02c, Sci/Tech +1.54c,
  Elections -5.80c. Broad enough to reach the sample bar in a few months.
- H2: buy the favorite at >= 0.70 in Financials only. Strongest mechanism (company
  KPI brackets anchored to analyst consensus), nested inside H1.
- K = 2, each gated at P < 0.025. Before registering: look up Kalshi's fee multiplier
  M for the Financials and Politics series actually traded (currently M = 1, flagged).

### 2026-09-13: Phase 2 registered as proposed

H1 and H2 registered in experiments.md, K = 2. Fee multiplier M = 1 for every
series (Tyler's call; consistent with public fee schedules, where only Crypto
differs and Crypto is not collected). Phase 1 exploration is CLOSED. Nothing below
this line may feed EXP-016.
