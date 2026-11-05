# EXP-020 — independent blind replication (EXP-020b), 2026-10-13

Replicator: independent agent, built from the pre-registration only (Status..Priors of
EXP-020 in research/experiments.md). Code + raw data + outputs:
scratchpad/replication/exp020b/ (code/exp020b.py, code/sens.py, code/chk.py, out_*.txt).
Did not open research/tradingroom_2026-10-13/exp020* or scratchpad tradingroom/exp020.

**Blinding breach, disclosed:** the grep used to find the section printed the Status line,
which reads "RESULT — PASS (holdout w=0.30; proxy gate 0.604 vs 0.60)". So I knew the
headline verdict, selected w and the proxy correlation before writing code. No RESULT
body numbers (Sharpes, MaxDDs, crisis means) were seen before VERDICT.md was written.

**Data:** AQR TSMOM monthly xlsx (aqr.com, 1985-01..2026-05), FRED TB3MS (fredgraph.csv),
SPY/VUSTX/DBMF/KMLM/CTA from Yahoo chart API adjclose — yfinance itself hit
YFRateLimitError, so I used the same Yahoo adjusted series directly (the original team
made the same substitution, it turns out).

## Interpretations (written before any return was computed)
1. Months: all series mapped to calendar month (period M). SPY monthly TR = pct change of
   yfinance auto-adjusted month-end close. 1993-02 is first full month (SPY listed 1993-01-29).
2. rf for month m = TB3MS(observation month m)/1200 (beginning-of-month rate, known ex ante).
3. Sleeve_m = TSMOM_m + rf_m - 0.02/12. Raw factor, unscaled.
4. Blend: target weights (1-w, w) at start of each month; returns accrue; end-of-month
   drifted weights; rebalance back to target at end of month. One-way turnover with 2 assets
   = |w_sleeve_drift - w|  (= 0.5*sum|dw|). Cost 5bp * turnover charged against that month's
   blend return. First month: no initial-purchase cost.
5. Base SPY carries no cost. Sharpe = sqrt(12)*mean(r-rf)/sd(r-rf) (ddof=1).
   dSharpe = Sharpe(blend) - Sharpe(SPY).
6. Bootstrap: circular moving block, block 12, 10,000 reps, numpy default_rng(20261013),
   resampling month indices jointly for (blend, SPY, rf) — blend returns pre-computed in
   original order. One index draw shared across all three w (paired). P = frac(stat* <= 0).
7. Crisis stat: worst decile = the k = round(0.10*n) lowest SPY months of the window
   (in-sample n=203 -> 20; holdout n=197 -> 20). Stat = mean(blend - SPY) over those months.
   In each bootstrap rep the decile is recomputed on the resampled SPY months.
8. MaxDD on compounded total-return wealth (not excess), starting at 1 before first month.
   IS3/H3 pass iff |MDD_blend| <= |MDD_SPY| - 2.0 pts.
9. Worst rolling-12m = min over compounded 12-consecutive-month total returns within window.
10. H1 CI lower bound = 5th percentile of bootstrap dSharpe (90% two-sided percentile CI).
11. Implementability: corr(DBMF_TR - rf, TSMOM) monthly, over DBMF's full months through
    2026-05 (AQR end). KMLM, CTA same. Tracking error = annualised sd(ETF_excess - TSMOM);
    shortfall = 12*mean(TSMOM - ETF_excess) (annualised arithmetic).
12. Selection ties: highest in-sample dSharpe among w passing IS1-IS4.
13. Data-source deviation: yfinance hit YFRateLimitError; SPY/VUSTX/DBMF/KMLM/CTA pulled
    instead from Yahoo's chart API (query2.finance.yahoo.com/v8/finance/chart, 'adjclose'),
    which is the same Yahoo adjusted-close series yfinance auto_adjust uses (div+split adj).

## In-sample 1993-02..2009-12 (n = 203, k = 20 worst-decile months)
SPY Sharpe 0.333, MaxDD −50.78%, worst-12m −43.42%. Sleeve Sharpe 1.181, corr(SPY, TSMOM) −0.146.

| w | blend Sharpe | ΔSh | P(Δ≤0) | crisis Δ (bp/mo) | P | MaxDD (gain) | worst-12m | IS1–4 |
|---|---|---|---|---|---|---|---|---|
| 0.10 | 0.441 | +0.1082 | 0.0000 | +122 | 0.0000 | −45.36% (+5.42) | −38.55% | PASS ×4 |
| 0.20 | 0.573 | +0.2400 | 0.0000 | +244 | 0.0000 | −39.46% (+11.32) | −33.37% | PASS ×4 |
| **0.30** | **0.730** | **+0.3963** | 0.0000 | +366 | 0.0000 | −33.06% (+17.72) | −27.89% | PASS ×4 |

Selected w = **0.30** (highest in-sample ΔSh). Haircut grid w=0.30: 0% +0.453, 1% +0.425,
2% +0.396, 3% +0.368, 4% +0.340.

## Holdout 2010-01..2026-05, w = 0.30 (n = 197, k = 20)
SPY Sharpe 0.906, MaxDD −23.93%, worst-12m −18.18%. Sleeve Sharpe 0.249.

| gate | value | result |
|---|---|---|
| H1 | Sharpe 0.906 → 0.987, ΔSh **+0.0806**, 90% CI [−0.0669, +0.2235], P(Δ≤0) 0.194 | PASS |
| H2 | crisis **+255 bp/mo**, P = 0.0000 | PASS |
| H3 | MaxDD −23.93% → −14.14%, **+9.79 pts** | PASS |
| H4 | worst-12m −18.18% → −6.32% | PASS |

Holdout haircut grid: 0% +0.139, 1% +0.110, 2% +0.081, 3% +0.051, 4% +0.022.

## Implementability
| ETF | overlap | corr(ETF excess, TSMOM) | TE/yr | TSMOM − ETF excess (arith/yr) |
|---|---|---|---|---|
| DBMF | 2019-06..2026-05 (84) | **0.604** (0.6035) | 11.33% | −2.97% |
| KMLM | 2021-01..2026-05 (65) | 0.664 | 10.71% | +3.47% |
| CTA | 2022-04..2026-05 (50) | 0.506 | 14.33% | −3.50% |

DBMF gate fragility (reported only, not used for the verdict): raw TR instead of excess
0.6065; drop first full month 0.6041; end 2026-04 0.6039; **include DBMF's partial first
month (May 2019 from listing day) 0.5997 → would trigger INCONCLUSIVE.** The gate outcome
depends on a month-boundary convention.

Reported-only 60/40 base (no cost): IS Sharpe 0.479 → 0.977, MaxDD −29.78% → −14.88%;
HO 0.891 → 0.928, MaxDD −25.71% → −11.32%.

## VERDICT (frozen rule): **PASS**
IS1–IS4 pass for all w; w=0.30 selected; H1–H4 pass; DBMF proxy corr 0.604 ≥ 0.60 so no
INCONCLUSIVE downgrade. Caveat: proxy gate cleared by 0.004 and flips under one plausible
data convention. (VERDICT.md in the scratchpad was written before the original RESULT was read.)

---
## Comparison with the original EXP-020 RESULT (read after the verdict above)

**Verdict: identical (PASS, w = 0.30).**

| quantity | original | replication | Δ | within tol? |
|---|---|---|---|---|
| IS SPY Sharpe | 0.333 | 0.333 | 0 | yes |
| IS ΔSh w=.10/.20/.30 | +0.108/+0.240/+0.396 | +0.108/+0.240/+0.396 | 0 | yes |
| IS MaxDD blend .10/.20/.30 | −45.4/−39.5/−33.1 | −45.36/−39.46/−33.06 | <0.1pt | yes |
| IS worst-12m | −38.5/−33.4/−27.9 | −38.55/−33.37/−27.89 | <0.1pt | yes |
| IS crisis bp/mo | +119/+237/+356 | +122/+244/+366 | +3/+7/+10 | not gated; see below |
| IS haircut grid | .453/.425/.396/.368/.340 | identical | 0 | yes |
| HO SPY Sharpe | 0.907 | 0.906 | 0.001 | yes |
| HO blend Sharpe / ΔSh | 0.987 / +0.081 | 0.987 / +0.0806 | 0 | yes |
| HO 90% CI | [−0.067, +0.223] | [−0.067, +0.224] | ≤0.001 | yes |
| HO P(Δ≤0) | 0.19 | 0.194 | — | yes |
| HO crisis | +255, P 0.000 | +255, P 0.000 | 0 | yes |
| HO MaxDD | −23.9 → −14.1 (+9.8) | −23.93 → −14.14 (+9.79) | 0 | yes |
| HO worst-12m | −18.2 → −6.3 | −18.18 → −6.32 | 0 | yes |
| HO haircut grid | .139/.110/.081/.051/.022 | .139/.110/.081/.051/.022 | 0 | yes |
| DBMF corr | 0.604 (n=84) | 0.604 (n=84) | 0 | yes |
| KMLM corr | 0.662 | 0.664 | 0.002 | yes (not gated) |
| CTA corr | 0.502 | 0.506 | 0.004 | yes (not gated) |
| KMLM / DBMF / CTA TE | 10.8/11.3/14.5 | 10.71/11.33/14.33 | ≤0.2 | yes |
| KMLM shortfall | +3.64 | +3.47 | 0.17 | approx |
| 60/40 HO Sharpe | 0.892 → 0.929 | 0.891 → 0.928 | 0.001 | yes (mine no cost) |
| 60/40 IS MaxDD | −29.8 → −14.9 | −29.78 → −14.88 | 0 | yes |

**Mismatches explained:**
1. *In-sample crisis mean* (+3 to +10 bp/mo): definition of "worst decile". I took the
   k = round(0.1·n) = 20 lowest months; the original evidently used SPY ≤ 10th-percentile
   (n = 21 in-sample). With k = 21 / quantile rule my numbers are +119/+237/+356 —
   exact match. In the holdout both rules give 20 months, hence the exact 255 match.
   Gate outcome unaffected (P = 0.000 either way). The registration should have pinned this.
2. *KMLM/CTA corr and shortfall* (0.002–0.004 corr, ~0.2%/yr): likely Yahoo snapshot /
   adjclose differences or how the original computed "AQR total − ETF" (theirs is
   arithmetic total-return difference; mine is TSMOM − (ETF − rf), which should be
   identical in principle). Ungated, immaterial.
3. *60/40*: I did not charge rebalance cost on the 60/40 line; ~0.001 Sharpe.

**Independent findings the original also reports:** proxy gate cleared by 0.004. My one
extra fragility point: counting DBMF's partial listing month (2019-05) as a return month
moves corr to 0.5997 and would flip the verdict to INCONCLUSIVE. The original's choice
(first full month) is the standard and pre-specified-in-spirit one ("monthly total
return"), so PASS stands, but the PASS is convention-sensitive on the implementability gate.
