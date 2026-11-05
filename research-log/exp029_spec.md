# EXP-029 build spec: correlation-gated duration in the challenger book

**For:** an independent tester. **Written:** 2026-10-13 ~23:50 PDT, before any EXP-029 data was
downloaded or any EXP-029 number computed.
**Binding entry:** `research/experiments.md` § EXP-029. If this file and that entry disagree, the
entry wins, and the tester reports the disagreement. It is not resolved toward whichever reading passes.
**Do not edit tracked files.** `challenger/*.py` and `risk_overlay.py` are imported or copied, never
modified. Put all code and outputs in `research/exp029/`, which is gitignored. Never push.

---

## 0. Order of work (strict)

1. Write `research/exp029/INTERPRETATIONS.md` before any data is loaded. It holds every ambiguity
   you resolve and how you resolved it.
2. Build the data (§2) and run the integrity checks (§2.4). Write `integrity.txt`. Do not compute
   strategy returns yet.
3. Run the validity checks F0–F2 (§4). If any fails, the result is INVALID: stop and ledger it.
4. Run **Part A** (premise, §5) on window P. Append the Part A result to the ledger
   **before** running Part B. If Part A FAILS, stop. Spent K = 0.
5. Run **Part B**: all arms, both windows, both cost levels, in one run (§6–§7). Score the gates
   (§8). Append the result to the ledger, re-reading the ledger tail just before you write
   (other agents append to it).
6. Do not iterate. Do not re-run with a changed parameter. Bugs found after step 5 are
   reported as bugs. A fixed re-run is allowed only if the fix changes no spec choice, and both
   runs are reported.

---

## 1. What is being tested (one paragraph)

The challenger holds long duration in two places. Ballast holds TLT (inverse-vol against GLD,
inside a 27% budget). Core parks its de-risked slice in IEF (up to 45% when QQQ is ≥10% below
its 200d MA). Duration hedges equities only while the stock–bond correlation is negative. When
that correlation is positive (inflation-driven regimes: the 1970s–90s, and 2022–), duration
falls with stocks, and the "hedge" adds risk. The variants use the trailing 252-day stock–bond
correlation, measured at each monthly rebalance, to move that duration into T-bills (CASH) while
the correlation is positive. Nothing else in the book changes.

## 2. Data

### 2.1 Window D: ETF era (contaminated; guard only)
- Tiingo adjClose, same request as `challenger/backtest.load_data` (startDate 2005-01-01, ffill).
  Write a fresh pull to `research/exp029/px_D.parquet` and do not write the engine's cache
  (precedent: EXP-026).
- Tickers: `sleeves.ALL_TICKERS` (SPY, TLT, GLD, IEF, QQQ, QLD, XLP, XLU, XLV, SHV, …).
- Signal pair: EQ = SPY, LB = TLT.
- CASH accrual: SHV adjClose daily return. Before SHV's first valid return, use FRED DTB3
  (discount → simple daily ≈ rate/100/360, ffilled). Disclose how many days this covers.
- Monthly T-bill used for Sharpe: FRED TB3MS/1200 (EXP-025 convention).
- Scored: **2007-07-02 → 2026-10-09** (the sim runs from series start).

### 2.2 Window P: proxy era, 1987–2006 (the holdout; scored 1990-01-02 → 2006-12-29)
Column names map onto the challenger's tickers so `sleeves.py` runs unmodified.

| Ticker | Proxy (daily) | Source | Haircut |
|---|---|---|---|
| QQQ | ^NDX price index | yfinance, auto_adjust | −0.20%/yr |
| QLD | 2·r(^NDX) − 1·r_cash − 0.95%/yr, daily rebalanced | built | (in formula) |
| IEF | BOND10: synthetic 10y par bond from ^TNX | yfinance ^TNX | −0.15%/yr |
| TLT | BOND30: synthetic 30y par bond from ^TYX (EXP-022 construction) | yfinance ^TYX | −0.15%/yr |
| GLD | gold spot, daily USD (see 2.3) | §2.3 | −0.40%/yr |
| XLP | Ken French 12-industry daily VW **NoDur** | French library | −0.10%/yr |
| XLU | French 12-industry daily VW **Utils** | French library | −0.10%/yr |
| XLV | French 12-industry daily VW **Hlth** | French library | −0.10%/yr |
| SPY | French **Mkt** total return = (Mkt-RF)+RF, daily | French library | none (signal only) |
| SHV/CASH | French daily **RF** | French library | none |

- Haircuts are applied as a daily subtraction of fee/252.
- Bond construction (identical to EXP-022, BOND30):
  r_t = exact reprice of an N-year semiannual par bond with coupon y_{t−1} at yield y_t, minus 1,
  plus y_{t−1}/252 carry. Yields are ffilled onto the equity calendar. N = 30 (^TYX), N = 10 (^TNX).
  Reuse EXP-022's code if it is still in the scratchpad (`tradingroom/exp022/`); otherwise
  reimplement from that formula and unit-test it (a 1bp yield rise ⇒ r ≈ −DV01).
- **VUSTX is NOT used.** EXP-022 rejected it for unadjusted distribution artifacts (−5.7%
  1992-12-11, +6.8% 1992-12-31) and price quantisation (338 zero days).
- **^TYX 2002–2006:** the US Treasury did not issue 30y bonds from 2002-02 to 2006-02.
  - If ^TYX shows any run of more than 10 consecutive identical values in 1987–2006, then for
    2002-02-19 → 2006-02-08 build TLT from FRED DGS20 as a 20y par bond. Disclose this.
  - The signal's LB series then uses the same splice.
- Price indices (^NDX) exclude dividends. This lowers the core leg's level the same way in every
  arm. Disclose it; do not correct it.
- Monthly T-bill for Sharpe: French RF compounded within each month.
- The sim runs from the first date all series exist (expected 1987-01). The first base weights are
  computed at i = 260 (run_book's rule). Score 1990-01-02 → 2006-12-29.

### 2.3 Gold before GLD (pre-declared hierarchy; take the first that passes 2.4)
1. Stooq XAUUSD daily close.
2. World Gold Council daily USD gold price (LBMA PM).
3. If neither gives clean daily data from 1988-01 on:
   - P's scored start moves to the first month-start after gold has ≥ 260 clean daily
     observations.
   - The truncation is disclosed, and V0's power floor (§8) decides whether P can still deliver
     a verdict.
   - Do NOT substitute miners (^XAU, VGPMX, FSAGX), silver, or GC=F rolled futures before 2000-08.

Cross-checks (report them; failure = that source fails):
- Daily-return correlation with GLD over 2004-11-18 → 2006-12-29 ≥ 0.95.
- Correlation with GC=F over 2000-09 → 2004-10 ≥ 0.85 (fix vs futures-close timing explains
  some of the gap).
- Bloomberg (Tyler's Eccles login) may only be used to spot-check about 10 dates. It is never
  a data source.

Downloads need Tyler's OK in the tester's session. Every source above is free.

### 2.4 Integrity checks (write `integrity.txt` before any strategy number exists)
- For every P column, report:
  - row count and first/last date;
  - count of zero-return days;
  - the 5 largest |r| with their dates;
  - runs of more than 5 identical consecutive values;
  - gaps of more than 5 business days.
- Flag any |r| > 8% on a non-crash date for any proxy except QLD. Disclose it; do not delete it.
  (Known real crash dates include 1987-10-19 and 1989-10-13.)
- French files: confirm daily RF > 0 on more than 95% of days, and confirm units (percent → /100).
- Check that ρ is computable at every BME from 1990-01 on: the 252 paired returns need ≥ 240
  non-NaN pairs.

## 3. Engine

Copy `run_book` from `challenger/backtest.py` **at main** (the fixed engine: day i earns the
weights held coming into day i, and decisions are made at day-i close). Copy it into
`research/exp029/engine.py`, line-identical except for exactly these edits:

- **E1 (all arms): real cash.** `_held_return` credits CASH with that day's T-bill return series
  (§2.1 / §2.2) instead of `CASH_YIELD/TD`.
- **E2 (all arms):** TCOST is a parameter. Primary = **5 bp** × Σ|ΔW| per executed trade (both
  legs, CASH included). Sensitivity = 10 bp.
- **E3 (variants):** `base = combined_weights_029(px.iloc[:i+1], budgets, arm)`. This calls
  `sleeves.combined_weights` unchanged, then applies the arm's post-map (§6) if G_t = 1.

Unchanged and imported, not copied: `sleeves.py`, `risk_overlay.vol_target_scaler`,
`VOL_MODEL = "trailing"`, the 80-row returns slice, TV 0.16, DRIFT 0.02, BME base rebalance,
and the risky/CASH split (CASH is outside the scaler).
`SLEEVE_BUDGETS` = core .45 / trend 0 / lowvol .28 / ballast .27.

**Known engine property (disclose; do not "fix"):** `portfolio_vol` normalises the risky weights
to sum to 1. When TLT (or IEF) moves to CASH, the remaining risky book's normalised vol rises.
The scaler can then fall below 1, de-risking the rest of the book as well. This is exactly what
the live bot would do, so it stays in the test. Its size is measured by the attribution
diagnostic (§7).

## 4. Validity (failure ⇒ INVALID; nothing is scored)
- **F0** Reproduction on D: with E1 off (flat 2%), E3 = identity and TCOST = 10 bp, engine arm A
  must reproduce `backtest.run_book(px_D, SLEEVE_BUDGETS, 0.16)` to |Δ daily ret| < 1e-12 on
  every day.
- **F1** P sanity: at every arm-A base rebalance in P, the weights sum to 1 ± 1e-9, TLT > 0,
  and GLD > 0.
- **F2** Causality: for 20 random BMEs t, overwrite all rows after t with noise. ρ_t, G_t and
  the base weights at t must be unchanged.
- **F3** Mapping: in every variant, on every BME with G = 1, the variant's TLT weight
  (V1, V2) and IEF weight (V2) must be exactly 0, the CASH weight must have risen by exactly the
  removed amount, and every other weight must be identical to arm A's.

## 5. Part A: premise (measurement, K = 0), window P only

**Signal.** At each BME t: ρ_t = Pearson correlation of daily simple returns of EQ and LB over
the 252 trading rows ending at t, inclusive. Fewer than 240 valid pairs ⇒ ρ_t = NaN, which is
treated as G = 0. G_t = 1 iff ρ_t > 0.

**Outcomes for month m+1** (the calendar month after BME t):
- c_{m+1} = realised correlation of daily EQ and LB returns within month m+1;
- LB_{m+1}, EQ_{m+1} = monthly compounded returns.

**Gates:**
- **A1 (persistence):**
  - mean(c_{m+1} | G_t = 1) − mean(c_{m+1} | G_t = 0) ≥ **0.20**;
  - AND the circular block bootstrap of that difference (block 12 months, 10,000 reps,
    seed 29) has a 95% lower bound > 0.
- **A2 (hedge failure is what the signal flags):** over months with EQ_{m+1} < 0,
  mean(LB_{m+1} | G_t = 1) < mean(LB_{m+1} | G_t = 0) (point estimate).
- **A3 (power):** each G group has ≥ 24 month-ends, and each group has ≥ 6 months with
  EQ_{m+1} < 0.

Part A PASS = A1 ∧ A2 ∧ A3. Part A FAIL ⇒ stop; Part B is not run (not even as a diagnostic).

**Report as well:**
- the number of sign changes of G over P (month-end sampling), with dates;
- the same Part A statistics on D, reported only. D is contaminated: 2022 is the event that
  motivated this experiment.

## 6. Arms (Part B)

The post-map applies only on BMEs where G_t = 1. It is evaluated at every base rebalance (BME,
plus the first sim day).

| Arm | Role | Post-map when G_t = 1 |
|---|---|---|
| **A** | baseline (live config, E1 real cash) | none |
| **V1** | candidate | w[CASH] += w[TLT]; w[TLT] = 0 (ballast duration → T-bills; GLD weight unchanged) |
| **V2** | candidate | V1, plus w[CASH] += w[IEF]; w[IEF] = 0 (all book duration → T-bills) |
| **C1** | control, not deployable | V1's map applied on EVERY rebalance (G ≡ 1) |
| **C2** | control, not deployable | V2's map applied on EVERY rebalance (G ≡ 1) |

- In this config TLT appears only in ballast and IEF only in core, so these maps touch only
  those sleeves.
- GLD is not upsized, because that would be a different hypothesis (a gold-concentration bet).
- No hysteresis, no alternative lookback, no alternative threshold.

K = 2 (V1, V2). The controls exist only to answer one question: does *timing* add value over
simply holding less duration?

## 7. Metrics (per arm × window × cost level)

**Primary Sharpe (EXP-025 definition):**
- monthly total returns compounded from the daily book;
- excess over that window's monthly T-bill (§2);
- mean / sd(ddof = 1) · √12.

**Also report:**
- `backtest.metrics` daily Sharpe at a flat 4.5%, for continuity;
- CAGR and annualised daily vol;
- **MaxDD on daily equity**, rebased at the window start;
- ES1% (mean of the worst ceil(1%·T) days) and worst day;
- turnover per year (Σ|ΔW|);
- fraction of months with G = 1 and the number of G flips;
- mean scaler s for G = 1 months and G = 0 months, per arm;
- calendar-year returns;
- DSR (Bailey–López de Prado, `backtest.deflated_sharpe` on daily net returns) at
  **K_family = 10** (challenger configs 4 + EXP-026's 3 + EXP-025's 1 + EXP-029's 2).

**Stress sets** (defined on proxy/ETF asset returns, never on strategy returns; fixed now):
- **S+ ("2022-like"):** calendar months with EQ_m < 0 AND LB_m < 0.
- **S− ("flight to quality"):** calendar months with EQ_m < 0 AND LB_m > 0.
- For each set, report its count, its count with G = 1 at the prior BME, and
  mean(R_v − R_A) with the permutation p-value from §8.

**Named episodes (reported only, start-to-end compounded return per arm):**
- P:
  - 1990-07-16 → 1990-10-11 (Gulf oil shock);
  - 1994-02-01 → 1994-11-30 (bond massacre);
  - 1998-07-17 → 1998-10-08 (LTCM; the hedge was needed);
  - 2000-03-24 → 2002-10-09 (dot-com).
- D:
  - 2008-10-09 → 2009-03-09;
  - 2020-02-19 → 2020-03-23;
  - **2022-01-03 → 2022-10-12**;
  - 2023-07-31 → 2023-10-27.

**Attribution diagnostic (reported only):** V1′ and V2′ are the variants re-run with the scaler
path forced to equal arm A's day-by-day s. Report ΔSharpe and S+ improvement for V vs V′. This
splits the effect into "duration swap" and "induced scaler de-risk".

## 8. Gates (Part B)

Gates are evaluated per variant v ∈ {V1, V2} at 5 bp unless stated. All must hold.

- **V0 power floor (INCONCLUSIVE if it fails; not a PASS):** P has ≥ 12 S+ months, and ≥ 6 of
  them have G = 1 at the prior BME.
- **G1 Sharpe non-inferiority (P):**
  - ΔSh = Sh_v − Sh_A ≥ **−0.03** (point);
  - AND, under a paired circular block bootstrap (block 12 months, 10,000 reps,
    seed 20261029; the same resampled months for both arms), the one-sided lower **97.5%** bound
    (Bonferroni for K = 2) of ΔSh is > **−0.10**;
  - AND at 10 bp the point estimate is still ≥ −0.03.
- **G2 MaxDD (P):** MaxDD_v ≥ MaxDD_A − 0.010. The variant may be at most 1.0 pt deeper.
- **G3 2022-like stress (P):**
  - mean over S+ of (R_v − R_A) > 0, with a one-sided paired sign-flip permutation p
    (10,000 flips, seed 29) that is significant after **Holm across V1, V2 at α = 0.05**;
  - AND Σ over S+ of (R_v − R_A) ≥ **+1.0 pt** (arithmetic sum of monthly differences).
- **G4 hedge preserved (P):** mean over S− of (R_v − R_A) ≥ **−0.20 pt/month** (point). This
  checks that the gate is not dropping the hedge in exactly the months it pays (1998 is the
  live risk).
- **G5 timing beats static (P):** Sh_v ≥ Sh_Cv (V1 vs C1; V2 vs C2), point. If this fails, the
  finding is "hold less duration", which is an unregistered claim. It is logged as a lead and
  authorises nothing.
- **G6 ETF-era guard (D, contaminated):** ΔSh_D ≥ −0.05 (point) AND MaxDD_v,D ≥ MaxDD_A,D − 0.010.

**Verdict per variant:**
- **PASS** = Part A PASS ∧ F0–F3 ∧ V0 ∧ G1–G6.
- **FAIL** = any of G1–G6 fails.
- **INCONCLUSIVE** = V0 fails.

**EXP-029 verdict:** PASS if ≥ 1 variant passes. If both pass, both go to the shadow logger.
Do not pick one by Sharpe.

**What D's 2022 number means:** nothing evidential. It is printed because the desk report asked
"would this have helped in 2022". The strategist's prior is that a 252d window turned positive
part-way into 2022, after much of the bond loss. This was not computed; it is a prediction.

## 9. Outputs (`research/exp029/`)
- `INTERPRETATIONS.md`, `integrity.txt`
- `px_D.parquet`, `px_P.parquet`, `signal_P.csv` / `signal_D.csv` (BME, ρ, G)
- `partA.json`
- `daily_{arm}_{win}_{bp}.parquet`
- `monthly_{win}.csv`
- `results.json`, `verdict.json`
- `FROZEN_MD5.txt` (md5 of engine.py, data files and results, written at run time)

## 10. What a PASS authorises, and what a FAIL closes

**PASS authorises:**
- a read-only paper **shadow logger** of the passing variant(s) beside the live challenger,
  with Tyler's go-ahead;
- no change to `challenger/sleeves.py`, no orders, nothing live.

**Changing the live book requires:**
- a separate pre-registered live-vs-shadow check after ≥ 60 sessions;
- Tyler's go-ahead.

**A FAIL closes these, and P is then spent for the duration/ballast family:**
- no re-run with another lookback (63/126/504d);
- no non-zero threshold;
- no hysteresis;
- no other equity leg (QQQ instead of SPY);
- no other replacement asset (SHY, TIPS, gold, commodities).

Any of those is a new experiment. It must cite EXP-029 and use a holdout that EXP-029 did not
touch: forward data, or the **reserved pre-1987 window (1962–1986; FRED DGS10 from 1962,
French from 1926)**. That window holds the 1970s–80s positive-correlation regime. EXP-029 never
loads any series before 1987-01-01. The 1987–1989 rows are sim warm-up, and their strategy
returns are never scored or printed.

---

**AMENDMENT 1 (2026-10-13 23:59 PDT, pre-data):** see ledger § EXP-029 "AMENDMENT 1".
- P cash, QLD financing and the Sharpe T-bill all use French monthly RF spread evenly over each month's trading days.
- Gold before GLD comes from WGC daily, or from any Tyler-obtained daily LBMA USD fix that passes §2.3.
- §2.3 rule 3 does not apply to login-gated data. If no file is obtained, the run stays BLOCKED and P stays sealed.

**AMENDMENT 2 (2026-10-14 00:05 PDT, pre-data):** see ledger § EXP-029 "AMENDMENT 2".
- WGC fix-timed gold is not lagged.
- §2.3 daily ρ is replaced by weekly ρ (≥0.90 GLD / ≥0.85 GC=F, known to pass) plus month-end ρ (≥0.97 GLD / ≥0.95 GC=F, binding).
- A non-P sizing study (2007-07..2019-12, D-real vs D-fix GLD, arms A/V1/V2/C1/C2, 5 bp) has tolerances T1 |ΔSh| ≤ 0.05, T2 contrast |ΔΔSh| ≤ 0.015, T2b contrast |ΔΔMaxDD| ≤ 0.30 pt and T3 scaler mean |Δs| ≤ 0.01 (p99 ≤ 0.05).
- Any failure ⇒ INCONCLUSIVE-data, and P stays sealed.
