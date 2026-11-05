# RED TEAM — EXP-020 (30% AQR TSMOM sleeve on a SPY book)

**Date:** 2026-10-13. **Status:** stress tests only. **The frozen EXP-020 verdict (PASS) is NOT re-adjudicated.**
Nothing here was pre-registered, so none of it is a test result. These are attacks on how robust the
PASS is and how much it means.
**Code/outputs:** `research/tradingroom_2026-10-13/redteam020/` — `rt.py` → `rt_output.txt`,
`relever.py` → `relever_output.txt`. Both `exec` the data/primitive block of the original
`exp020/run.py` unchanged: same files, same `blend()`, `maxdd()`, `worst12()`, `crisis()`, `boot_idx()`, seed.
Challenger and champion-proxy bases come from importing `challenger/backtest.py` (`run_book`,
`run_champion_proxy`) read-only on the cached Tiingo prices. No tracked file was edited and no API was called.

**Overall call: WOUNDED.** No bug and no look-ahead turned up, and the funds we can buy did deliver
in 2022. The damage is in what the PASS measures. Three of its four gates would also be passed by
putting the same 30% in T-bills. The part that is specific to trend comes almost entirely from
one year (2022). On the challenger's actual book, the Sharpe gain over 2007–2026 is zero.

---

## Attack 0 — the null EXP-020 never ran: 30% T-bills (most damaging)

EXP-020 compared the blend against 100% SPY. Any 30% non-equity sleeve lowers drawdown,
improves the worst 12 months, and does better in SPY's worst months, simply because there is
less equity in the book. So the correct control is **70% SPY / 30% T-bills**.

Holdout 2010-01..2026-05, w=0.30, h=2%:

| arm | CAGR | vol | Sharpe | MaxDD | worst 12m | Calmar |
|---|---|---|---|---|---|---|
| SPY | 14.38% | 14.5% | 0.907 | −23.9% | −18.2% | 0.60 |
| 70/30 TSMOM (EXP-020) | 11.64% | 10.3% | 0.987 | −14.1% | −6.3% | 0.82 |
| 70/30 T-bills | 10.58% | 10.1% | 0.906 | −16.8% | −12.1% | 0.63 |

How much of each gate's margin the T-bill arm also gets:
- **H2 crisis:** +255 bp/mo for the TSMOM blend vs **+211 bp/mo for T-bills**. TSMOM's own share is
  +43 bp/mo, bootstrap 90% CI [−6, +89], **P(≤0) = 0.072**. That share would not clear H2's α = 0.05.
- **H3 MaxDD:** +9.8 pts vs **+7.1 pts for T-bills**. TSMOM adds 2.7 pts.
- **H4 worst-12m:** T-bills pass it too (−12.1% vs −18.2%).
- **H1 Sharpe:** T-bills change Sharpe by 0.000. This is the only gate that separates trend from
  cash, and it passed as non-inferiority: P = 0.19, CI includes 0.

Credit where it's due: TSMOM does beat cash as the de-risking asset. Bootstrap CAGR edge
+1.05%/yr (P(≤0) = 0.14), and a CRRA certainty-equivalent edge of +0.85 to +0.95%/yr at γ = 2–10.
**Damage: high to the *meaning* of the PASS, not to its arithmetic.** H2–H4 mostly measure "less
equity". The trend-specific claim reduces to: ΔSh +0.08 (P = 0.19), +43 bp/mo crisis edge
(P = 0.07), and +2.7 pts MaxDD.

## Attack 1 — implementability: the funds we can actually buy

Each ETF used as the 30% sleeve on its real total-return history, net of its expense ratio,
with no extra haircut (`rt_output.txt` ATTACK 1):

| sleeve on SPY | window | ΔSh vs SPY | MaxDD SPY → blend (T-bill arm) | ΔCAGR (T-bill arm) | fund alone CAGR / Sh |
|---|---|---|---|---|---|
| DBMF | 2019-06..2026-09 (88) | **+0.184** | −23.9 → −14.0 (−16.8) | −163 bp (−401) | 9.6% / 0.63 |
| KMLM | 2021-01..2026-09 (69) | +0.168 | −23.9 → −8.7 (−16.8) | −192 bp (−328) | 6.5% / 0.29 |
| CTA | 2022-04..2026-09 (54) | +0.202 | −20.2 → −8.5 (−14.1) | −34 bp (−269) | 10.2% / 0.42 |
| AQR sleeve, DBMF window | 2019-06..2026-05 (84) | +0.087 | −23.9 → −11.2 | | 3.7% / 0.14 |

Crisis windows (sleeve-alone cumulative return):

| window | SPY | AQR+rf−2% | DBMF | KMLM | CTA |
|---|---|---|---|---|---|
| COVID 2020-02..03 | −19.4% | **+10.3%** | **−0.8%** | n/a | n/a |
| 2022 calendar | −18.2% | +24.8% | +21.6% | +24.2% | n/a |
| 2022-01..09 peak→trough | −23.9% | +33.6% | +31.6% | +44.8% | n/a |
| 2025-02..04 tariff shock | −7.6% | −4.7% | −3.9% | −4.3% | −1.1% |
| 2023 calendar | +26.2% | −5.3% | −8.9% | −5.7% | −2.2% |
| 2024 calendar | +24.9% | +6.6% | +7.2% | −1.7% | +24.1% |
| 2025 calendar | +17.7% | +3.9% | +13.8% | −3.0% | +0.9% |

In SPY's 9 worst-decile months since 2019-06, mean SPY −7.6%: DBMF +1.6%, AQR sleeve +3.2%,
T-bill +0.2%. DBMF lost money in 2020-02 (−2.1%), 2025-03 (−1.6%) and 2026-03 (−3.8%).

Regressing ETF excess returns on AQR excess (gross): DBMF α +4.8%/yr, β 0.51; KMLM α −1.6%/yr,
β 0.66; CTA α +4.3%/yr, β 0.75. Residual vol is 9–14%/yr.

**Damage: low on the headline, moderate on reliability.** The 2022 benefit is real in what we can
buy, and every fund improved the SPY book's Sharpe over its own (short) window by more than the
AQR proxy did. But:
- (a) In a fast crash (COVID), the replicator delivered about nothing while the index made +10%.
  Its slow-crash payoff is the only kind it has shown.
- (b) Dispersion across funds is enormous: 2024 runs from −1.7% to +24.1%, 2025 from −3.0% to +13.8%.
  The choice of fund is a bet of the same order as the sleeve's whole expected edge.
- (c) Every one of these windows contains 2022, so the ETF Sharpe gains are mostly a 2022 fact
  (see Attack 3).

## Attack 2 — code, look-ahead, fees, timing, dividends

| check | result |
|---|---|
| Look-ahead | None possible: fixed weights, no signal fitted. The AQR factor's own vol-scaling is ex-ante (t−1). |
| Month alignment (Yahoo month-start bar vs AQR month-end) | corr(SPY, AQR) at lags −1 / 0 / +1 = −0.04 / **−0.16** / −0.05. The peak at lag 0 means alignment is correct. SPY 2008-10 −16.5% and 2020-03 −12.5% match known values. |
| Dividends | SPY calendar 2022 −18.18% and 2008 −36.79% match published total returns (−18.2%, −36.8%), so adjclose includes dividends. DBMF 2022 +21.6% is consistent with its published TR. KMLM/CTA not independently checked. |
| Fee/turnover cost | `blend()` drift turnover `w(1+s)/(1+g) − w` is correct. 5 bp one-way is generous for liquid ETFs. |
| Haircut | The 2% haircut is applied to a gross index. The ETFs are net, which is why Attack 1 adds no haircut. |
| AQR holdout data | 197 months, 0 duplicates, 0 NaN. |
| Rebalance timing | Quarterly ΔSh +0.086, annual +0.096 (monthly +0.081). Not timing-sensitive. |

**Damage: none.** One clarification. The ledger's "sleeve Sharpe 0.25" is after the haircut. The
gross AQR TSMOM holdout Sharpe is 0.40 (0.46 for 2010–19, 0.32 for 2020–26). Side note, not about
EXP-020: on monthly data, my challenger `run_book` base gives Sharpe 0.98 for 2007-07..2026-05.
EXP-021 reports "Sharpe 0.65" for roughly the same replay. The definitions probably differ
(daily vs monthly, rf), but it's worth reconciling.

## Attack 3 — sensitivity (AQR sleeve, SPY base, w = 0.30)

| variant | ΔSh vs SPY | ΔMaxDD (T-bill arm) | ΔCAGR | sleeve-vs-cash ΔSh |
|---|---|---|---|---|
| holdout, h=2% (as registered) | +0.081 | +9.8 (+7.1) | −274 bp | +0.081 |
| h=3% | +0.051 | +9.7 | −307 bp | +0.052 |
| h=4% | +0.022 | +9.6 | −340 bp | +0.023 |
| h=5% | **−0.007** | +9.5 | −373 bp | −0.007 |
| 2010–2019 | +0.048 | +2.1 (**+4.7**) | −263 bp | +0.049 |
| 2020–2026-05 | +0.089 | +12.7 (+7.1) | −291 bp | +0.090 |
| 2023-01..2026-05 | **−0.026** | +1.6 (+2.8) | −527 bp | −0.025 |
| start 2016 → 2026-05 | +0.019 | +12.7 (+7.1) | −384 bp | +0.020 |
| **holdout ex-2022, h=2%** | **+0.014** | +5.3 (**+5.7**) | −400 bp | +0.015 |
| **holdout ex-2022, h=3%** | **−0.016** | +5.2 (+5.7) | −434 bp | −0.015 |

Per-year blend minus T-bill blend (pp), holdout: 2010 +3.2, 2011 −0.6, 2012 −0.2, 2013 +5.5,
2014 +5.3, 2015 +5.0, 2016 −4.1, 2017 +1.6, 2018 −3.3, 2019 +1.1, 2020 −2.2, 2021 −2.2,
**2022 +6.2**, 2023 −3.4, 2024 +0.5, 2025 0.0, 2026 YTD +4.4.

**Damage: moderate.**
- Remove calendar 2022 and the Sharpe gain goes to ~0 (+0.014). The drawdown benefit then becomes
  *smaller than cash's* (+5.3 vs +5.7 pts).
- In 2010–2019 cash also beat TSMOM on MaxDD (+4.7 vs +2.1).
- Since 2023 the sleeve has hurt on Sharpe.
- The result survives haircuts up to 4% and any rebalance frequency, but has essentially no
  margin left at 4%. KMLM's realized lag of 3.6%/yr vs AQR (ledger table) sits inside that zone.

## Attack 4 — the books Tyler actually runs

AQR sleeve (h=2%) blended monthly outside the overlay. Bases come from `challenger/backtest.py`:

| base | window | base Sh / CAGR / MaxDD | +30% TSMOM | +30% T-bills | ΔSh sleeve |
|---|---|---|---|---|---|
| **Challenger** (`run_book`, live budgets, TV 16%) | 2007-07..2026-05 | 0.983 / 12.52% / −23.4% | 0.983 / 10.26% / −14.2% | 0.982 / 9.23% / −16.4% | **0.000** |
| Challenger | 2010–2019 | 1.293 / 12.67% / −8.6% | 1.165 / 10.14% / −7.6% | 1.292 / 9.00% / −5.8% | **−0.128** |
| Challenger | 2020–2026-05 | 0.900 / 14.39% / −20.9% | 0.981 / 11.73% / −7.0% | 0.900 / 10.99% / −14.7% | +0.081 |
| Challenger + DBMF (actual) | 2019-06..2026-05 | 1.040 / 15.93% / −20.9% | 1.239 / 14.26% / −7.5% | 1.040 / 12.00% / −14.7% | +0.199 |
| **Champion proxy** (`run_champion_proxy`, 3x tech, TV 20%) | 2011-07..2026-05 | 1.058 / 20.39% / −28.6% | 1.120 / 15.72% / −16.2% | 1.058 / 14.80% / −20.5% | +0.062 |
| Champion proxy | 2011-07..2019-12 | 1.191 / 22.42% / −19.0% | 1.226 / 16.86% / −16.2% | 1.191 / 15.85% / −13.2% | +0.035 |
| Champion proxy + DBMF | 2019-06..2026-05 | 1.009 / 20.15% / −28.6% | 1.175 / 17.33% / −13.9% | 1.009 / 15.00% / −20.5% | +0.166 |
| Champion `quarterly_backtest.csv` HRP_MOMENTUM + DBMF | 2019Q3..2026Q2 (28q) | Sh 1.23 / 15.72% / −13.2%(q) | Sh 1.65 / 14.06% / −2.3%(q) | Sh 1.23 / 11.83% / −9.0%(q) | +0.42 |

corr(challenger base, AQR sleeve) = +0.02. corr(champion proxy, AQR sleeve) = −0.16.

**Damage: moderate for the challenger, low for the champion.**
- **Challenger:** the core sleeve is already trend-ramped (QQQ vs 200d MA) and the book holds
  TLT/GLD ballast. Over its full 19-year history the 30% sleeve buys **zero Sharpe**. In 2010–19 it
  *costs* 0.13 Sharpe while cutting MaxDD by only 0.9 pts (T-bills cut 2.8). The positive numbers
  all come from windows that contain 2022.
- **Champion:** shape is closer to SPY (concentrated, equity-heavy), and the sleeve helps it
  roughly as much as it helps SPY. The CAGR cost is larger (−467 bp/yr on the proxy) because the
  base returns more.
- Caveat on all rows: the live proposal puts DBMF *inside* the vol-target overlay. The overlay
  would re-lever a lower-vol book, so the fixed-blend CAGR cost here overstates what live would
  pay (see Attack 5).

## Attack 5 — is −274 bp/yr worth it?

Holdout, SPY base:

| arm | CAGR | Calmar | CRRA CE γ=2 | γ=4 | γ=6 | γ=10 | $10k → |
|---|---|---|---|---|---|---|---|
| SPY | 14.38% | 0.60 | **12.45%** | **10.31%** | 8.10% | 3.50% | $90,724 |
| 70/30 TSMOM | 11.64% | **0.82** | 10.53% | 9.47% | **8.38%** | **6.16%** | $60,970 |
| 70/30 T-bills | 10.58% | 0.63 | 9.59% | 8.55% | 7.49% | 5.31% | $52,153 |

- **Breakeven CRRA γ ≈ 5.5.** An investor with relative risk aversion below ~5.5 preferred plain SPY
  over the holdout. For [removed: personal detail] with a 40-year horizon, a paper account, and "get rich slow"
  as the goal, typical γ is 2–4, so **the static 70/30 sleeve was the wrong trade for his
  preferences in 2010–2026.** It cost $29.8k of terminal wealth per $10k.
- **Over the full 1993–2026 sample, CE(γ=4) is SPY 6.93% vs blend 9.19%.** That gap comes entirely
  from 2000–02 and 2008 (in-sample). Whether he wants it depends on whether he expects another
  slow crash in his horizon. Over 40 years, one probably happens.
- **Structure the CAGR wall doesn't reach: re-lever, don't de-risk.** The −274 bp cost is
  de-levering, not trend. Scale the blend back up to SPY's vol (L = 1.41, borrowing at rf+1%):
  - holdout CAGR **15.25% vs 14.38%** SPY, MaxDD −19.6% vs −23.9%, worst-12m −10.2% vs −18.2%.
  - **ex-2022 it is a wash** (Sh 1.107 vs 1.119, CAGR 16.69% vs 16.89%).
  - 2010–19 relevered MaxDD is *worse* than SPY's (−18.5% vs −16.2%).

  The challenger's vol-target overlay already does this re-levering mechanically, which is why
  the right test is the sleeve inside the overlay, not a fixed blend.

---

## Overall: **WOUNDED**

Survives:
- the code
- dividends and timing
- quarterly or annual rebalancing
- haircuts ≤ 4%
- the buyable funds in 2022
- the champion's shape
- beating T-bills as a de-risking asset (+~0.9%/yr CE)

Damaged by:
1. H2–H4 are mostly passed by T-bills. The trend-specific crisis edge is +43 bp/mo with P = 0.07.
2. Without 2022, the Sharpe gain is +0.014 and the drawdown benefit is worse than cash's.
3. On the challenger's own book: ΔSh 0.000 over 2007–2026 and −0.128 over 2010–19.
4. The replicators missed COVID (DBMF −0.8% vs index +10.3%) and disagree with each other by up
   to 25 pp in a calendar year.
5. At Tyler's plausible risk aversion, the static version is worth less than SPY.

Not KILLED: what's left is a real, institution-crowded, one-crisis-confirmed slow-crash hedge
that beats cash. Its value depends on structure (inside the overlay, re-levered), not on a static
70/30.

**Binding constraint:** the trend-specific benefit comes from one event in the holdout (2022:
+6.2 pp vs cash). Sixteen years with one slow crash cannot statistically separate trend from
"hold less equity".

## What the forward shadow book should look like (if pursued)

It is a **measurement instrument, not an edge test.** 60 days cannot test a crash hedge, and
pretending otherwise would be the rationalized-win failure mode.

1. **Three paper arms, logged daily, no orders:**
   - (A) challenger as-is;
   - (B) challenger with `MFUT_BUDGETS_PROPOSED` and DBMF *inside* `apply_overlay` (the patch as written);
   - (C) the same as B with SHV in place of DBMF.

   **B vs C is the real comparison.** B vs A mixes trend with de-risking.
2. **Pre-register before day 1:**
   - replication gap: DBMF monthly vs AQR TSMOM when AQR posts (β, residual vol);
   - the overlay's realized scale factor in B vs A, to see whether re-levering actually happens;
   - B−C tracking error;
   - DBMF's return on SPY's down weeks (the conditional hedge).
3. **Kill/escalate rules, frozen up front:**
   - after ≥ 6 months, if DBMF's β to SPY in SPY-down weeks is ≥ 0 (no hedge), or the B−C
     cumulative gap is below −3% with no SPY drawdown worse than −10% in the window, the sleeve
     is shelved;
   - if a ≥ 10% SPY drawdown happens during the shadow period, score B vs C on that episode
     alone, as a single pre-declared event.
4. **Run EXP-022-style backtest first (pre-registered):** challenger with the mfut sleeve inside
   `run_book` (AQR proxy pre-2019, DBMF after), against C. The fixed-blend numbers here suggest
   ΔSh ≈ 0 over 2007–26, so the honest prior is PARTIAL at best.
5. **Fund choice:** declare DBMF (as patched) and log KMLM/CTA alongside as reported-only. Do not
   switch to whichever one is winning later.
