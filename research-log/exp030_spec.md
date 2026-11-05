# EXP-030 build spec — long-only multi-factor selection in the point-in-time S&P 500

Written 2026-10-14 by the strategist, BEFORE any return, factor value, or factor performance was
computed in this repo for this universe. Binding on the independent tester. If this file and the
EXP-030 ledger entry disagree, the ledger entry wins, and the disagreement is reported, not resolved
toward PASS.

Feasibility probe that preceded this spec: `research/exp030_probe.py` → `research/exp030/probe_*`.
It measured data coverage only (row counts, concept presence). It computed no return.

---

## 0. What the tester must not do

- No factor, lookback, weighting, threshold, cost, or window other than those below.
- No return of any kind dated after 2018-12-31 until the Part A result is written to the ledger
  (§6). The holdout seal is in code: `HOLDOUT_OPEN = False` in the run script, and the price loader
  truncates at 2018-12-31 while it is False. Flipping it is a ledgered act.
- No re-run after seeing a holdout number, except for a code bug. A bug re-run is allowed once per
  bug: the diff and the before/after numbers both go in the ledger.
- `predmarket/` is untouched. No orders, no broker writes. Nothing here touches a live bot.
- Never print a key from `.env`.

## 1. Universe (survivorship-free)

**Source:** `research/exp030/raw/sp500_hist.csv` (fja05680/sp500 "Historical Components & Changes
(Updated)". Clenow/Norgate base to 2019, then Wikipedia-maintained changes). The rows are snapshots
taken on change dates. **Membership on date d = the set in the latest snapshot dated ≤ d.** The last
snapshot containing a name is NOT its exit date. The exit is the next snapshot. (Example: SIVB's last
snapshot is 2023-01-04, and it leaves at 2023-03-15.)

Universe at rebalance t = members on t that have (a) a verified price series covering t and the 252
trading days before it, for momentum/vol (if this is missing, those two factors are missing), and (b)
a composite score (§3).

### 1.1 Ticker → price-series map (must be built and frozen BEFORE any return is computed)
The probe found that ticker matching alone is unsafe:
- The list-level exact-ticker match is wrong for reused tickers. The API spot check returned 0 rows
  for BEAM and CAM.
- The "X leaves, Y enters on the same day" rename heuristic was right for only about 26 of 61 pairs.
  It mapped SIVB→BG and FRC→AXON, which are wrong. The real series are SIVBQ and FRCB on Tiingo.

Procedure:
1. For every ticker that was ever a member in 2010-12-01..2026-09-30 and is not a current member:
   - Resolve the security by NAME. Use the Wikipedia changes table
     (`raw/wiki_1365256480.html`, table 1), plus the SEC entity name for the CIK (§1.2).
   - Find its Tiingo symbol, trying in order: the same ticker, the ticker + "Q", the successor
     ticker after a rename, and other Tiingo symbols with a matching name in the `/tiingo/daily/<sym>`
     meta endpoint.
   - Accept the match only if the meta `name` matches the company name, and the series has rows on
     ≥ 90% of business days in the membership interval.
2. Fallback, for 2016-01-04 onward only: Alpaca daily bars, `adjustment='all'`, same 90% rule.
3. Write `research/exp030/ticker_map.csv`. Columns: index ticker, interval, source, symbol, name
   evidence, row fraction. Then **write its SHA-256 into the ledger** before any return is
   computed. Anything unresolved stays unresolved. It is not dropped quietly.

**Price fields:**
- Returns use Tiingo `adjClose` (split- and dividend-adjusted total return).
- Market cap uses the unadjusted `close` × shares (§3.1).
- The Tiingo free tier caps unique symbols per month (EXP-004 stalled on this). The pull is about 830
  symbols plus SPY, so plan it across two calendar months at most 480 symbols each, and cache
  everything to `research/exp030/prices/`. Do NOT buy a paid tier without a quote to Tyler first.

### 1.2 Ticker → CIK map (frozen together with 1.1)
- Current members: the SEC `company_tickers.json` / Wikipedia CIK column.
- Departed members: the CIK must be verified by entity name **for every departed name**, including
  ones whose old ticker still resolves in `company_tickers.json`. Reused tickers (CEG, DELL, IR, DOW,
  SNDK…) would otherwise attach another company's fundamentals.
- The probe left 27 unmapped and 23 matched only by top search hit. Resolve them by hand on EDGAR.
- Record everything in `ticker_map.csv`.

### 1.3 Delisting returns (rule fixed now, list enumerated before returns)
A held name whose verified series ends inside a holding month gets one of these:
- **Acquisition / merger** (reason per the Wikipedia changes table, or the 8-K): the last available
  close. This is approximately the deal value.
- **Failure / bankruptcy / regulatory seizure:** the post-failure OTC series if one is verified
  (e.g. SIVBQ, FRCB). Otherwise −100% from the last close.
- **Unknown reason:** −30% from the last close (Shumway 1997, performance-delist average).

The tester lists every series that ends while the name is still a member, with its class, in
`research/exp030/delist_classes.csv`. This happens **before** any portfolio return is computed.

## 2. Windows

- **Prices loaded from** 2010-12-01, for the 252-day lookback at the first rebalance.
- **Rebalance dates** t = last NYSE trading day of each month.
- **Calibration window C:** rebalances 2012-01-31 → 2018-11-30. That is 83 monthly holding
  periods, Feb 2012 – Dec 2018. The last period is truncated at the 2018-12-31 close, so nothing in C
  reads a 2019 price.
- **Sealed holdout H:** rebalances 2018-12-31 → 2026-08-31. That is 93 monthly holding periods,
  Jan 2019 – Sep 2026. The last period ends at the 2026-10-01 close.
- **Membership after the last snapshot (2026-08-18)** is carried forward. Any index change after it
  is missed. This is disclosed, and it affects at most 2 rebalances.
- **Benchmarks:** the same dates and the same return convention.

## 3. Factors (fixed, equal-weighted, no mining)

All cross-sectional ranks are percentile ranks in [0, 1] across the universe at t (within FF-12
sector for V2), with ties averaged. Higher = better.

**Point-in-time rule for fundamentals:**
- Use SEC XBRL companyfacts, from the bulk `companyfacts.zip` (free), for the mapped CIKs.
- For each (concept, period), take the **first-filed** entry: `min(filed)`. [removed: reference to an unrelated private project]
- A value is usable at t only if `filed < t` (strictly earlier calendar date).
- A period whose end is more than 200 days before t is stale, and that input is missing.

From the probe: first-filed lag (period end → filed) had a median of 33 days and a p90 of 54 days.
First-filed and latest-filed values differ on 3.5% of period-ends (Assets, 15-CIK sample).

**TTM flows:**
- Sum the latest 4 quarterly values.
- Quarterly values are 80–100-day durations. Q4 = annual (330–380 days) − the three prior quarters,
  [removed: reference to an unrelated private project]. All are first-filed.
- If any of the four quarters is missing, the TTM is missing.

### 3.1 VALUE
VALUE = mean(pct(E/P), pct(B/P)), using whichever of the two is available.
- E = TTM `NetIncomeLoss`. B = latest `StockholdersEquity` (instant).
- P = market cap = shares × unadjusted close at t.
- Shares:
  - Take `dei:EntityCommonStockSharesOutstanding` from the latest filing with filed < t, summed over
    share classes reported at the same date.
  - Multiply by Tiingo's cumulative `splitFactor` between that as-of date and t.
  - Fallback: the latest quarterly `WeightedAverageNumberOfSharesOutstandingBasic`.
  - Report the share of each source.
- Negative E or B values are kept (they rank low).

### 3.2 MOMENTUM (12-1)
adjClose[t−21] / adjClose[t−252] − 1, in trading days. It needs ≥ 240 valid closes in the window.

### 3.3 QUALITY (gross profitability, Novy-Marx)
- **Route G:** TTM gross profit / latest `Assets`.
  - GP = `GrossProfit`.
  - Else revenue − cost, using revenue from {`Revenues`,
    `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`} and cost from
    {`CostOfRevenue`, `CostOfGoodsAndServicesSold`, `CostOfGoodsSold`}, first available in that order.
- **Route R** (no GP route, e.g. banks, insurers, many utilities and REITs): TTM `NetIncomeLoss` /
  latest `Assets`.
- Percentiles are computed **separately within route G and within route R**, then pooled. Report the
  route-R share by year.

The probe saw a GP route for only about 41–60% of members in the frames API. Frames undercount
non-calendar fiscal years, so companyfacts coverage will be higher, but route R will be large. It
is a fixed rule, not a choice made later.

### 3.4 LOW VOLATILITY
LOWVOL = −stdev of daily log adjClose returns over the last 252 trading days (≥ 240 obs).

### 3.5 Composite
COMPOSITE = the mean of the available factor percentiles. A name is eligible only if ≥ 3 of the 4
are available. No re-ranking, no factor weights other than equal.

**Sector:** Fama-French 12-industry classification from the SEC SIC code (Ken French's
`Siccodes12` definitions; SIC from EDGAR submissions). This is the current SIC, not point-in-time.
That is a small, disclosed look-ahead.

## 4. Variants (K = 3; declared now, all three run, none picked by result)

All are long-only, fully invested, monthly, and trade at the **close of t+1** (the next trading day
after the signal date t). Weights drift between rebalances.

- **V1 — top quintile, EW, sector cap.**
  - Hold the top 20% by COMPOSITE (round to the nearest integer), equal-weighted.
  - Cap: no FF-12 sector above 25% of names. If it is breached, drop that sector's lowest-ranked
    holdings and add the next-best names from other sectors until the cap holds.
- **V2 — sector-neutral.**
  - Factor percentiles are computed within FF-12 sector, then averaged into COMPOSITE.
  - Hold the top 20% within each sector (round, minimum 1 if the sector has ≥ 5 eligible names),
    equal-weighted.
- **V3 — V1 with a turnover buffer.**
  - Buy names entering the top 20%. Keep a holding until it falls out of the top 40%.
  - Equal-weight whatever is held, with the 25% sector cap applied at entry.
  - At the first rebalance the book equals V1.

**Benchmarks:**
- **EW:** the equal-weighted eligible universe, rebalanced monthly on the same schedule, net of the
  same costs.
- **SPY:** buy and hold, adjClose.
- **RF:** the Ken French daily risk-free rate.

## 5. Costs

- 10 bp one-way per $ traded is primary; 20 bp one-way is the stress case.
- Basis: Alpaca commission = 0. S&P 500 quoted half-spreads are typically 1–3 bp at the close, and
  impact is negligible at paper size. So 10 bp is a deliberately conservative allowance of about 3–5×
  the half-spread.
- Costs apply to all turnover, including EW's. Turnover = ½ Σ|w_new − w_drifted| per rebalance,
  annualised.

## 6. Part A — premise gate on window C (K = 0). FAIL ⇒ STOP.

- **A0 (data; failure ⇒ INCONCLUSIVE, not a premise FAIL):**
  - ≥ 95% of member-months in C are priced via the frozen map.
  - ≥ 90% of priced member-months have a COMPOSITE.
  - Report this by year. Probe estimate: 92.6% priced in 2012, rising to 98.4% in 2018, before
    manual mapping. The manual pass is expected to close the gap.
- **A1:**
  - The monthly Spearman IC of COMPOSITE (whole universe, V1 ranking) with the next month's total
    return (t+1 close → next t+1 close) has a mean ≥ 0.015.
  - AND a stationary block bootstrap (mean block 6, 10,000 reps, seed 30) gives one-sided
    P(mean IC ≤ 0) < 0.05.
- **A2:** the mean gross monthly return of the top-quintile EW portfolio (V1, no cap) minus EW is > 0,
  as a point estimate.

Part A is written to the ledger (numbers plus the `ticker_map.csv` SHA) before `HOLDOUT_OPEN` is
flipped.

## 7. Part B — holdout H, per variant, net of 10 bp. All must hold.

- **B0 validity (else INVALID, not FAIL):**
  - ≥ 98% of member-months in H priced; ≥ 90% with a COMPOSITE.
  - **Causality test:** shift every `filed` date by +1 day and perturb all prices after t by ×(1+ε),
    then confirm that weights at t are unchanged.
  - V1 at its first rebalance equals an independent recomputation for 5 random dates (seed 30).
- **G1 premium vs EW:**
  - ΔSh = Sharpe(V − RF) − Sharpe(EW − RF), on monthly returns, annualised by √12, is ≥ +0.10.
  - AND the paired stationary block bootstrap (mean block 6, 10,000, seed 30) gives one-sided
    P(ΔSh ≤ 0) < 0.05/3 = 0.0167 (Bonferroni, K = 3).
  - AND the annualised net active return vs EW is > 0.
- **G2 non-inferiority vs SPY:** ΔSh(V vs SPY) ≥ −0.05 as a point estimate. The bootstrap CI is
  reported.
- **G3 drawdown:** the net MaxDD (daily NAV) is no more than 5.0 pts deeper than EW's AND no more than
  5.0 pts deeper than SPY's.
- **G4 turnover and cost:**
  - Mean annualised one-way turnover ≤ 150% for V1/V2 and ≤ 100% for V3.
  - AND at 20 bp the G1 point estimate is still ΔSh ≥ +0.05.
- **G5 is-it-what-it-claims:**
  - Regress monthly active return (V − EW) on Fama-French 5 + UMD (Ken French, free), with
    Newey-West (3 lags).
  - Of the four intended tilts — HML > 0, UMD > 0, RMW > 0, and market beta of V below market beta of
    EW — at least 3 must have the intended sign.
  - A failure here is FAIL-with-diagnosis. It becomes a re-run only if a code bug is found and
    disclosed.

**Reported, not gated:**
- calendar-year active returns;
- the C-window backtest of all variants (descriptive: it is the calibration period);
- SMB loading (an EW universe vs SPY is a size tilt; say so);
- DSR at K_family = 3;
- holdings count and route-R share;
- per-factor ICs (descriptive only; they may not be used to re-weight anything);
- the delisting-class P&L contribution.

## 8. Verdict

- **PASS per variant** = Part A ∧ B0 ∧ G1–G5. If several pass, all are shadowed; there is no pick by
  Sharpe.
- **PASS authorises only** a read-only paper shadow logger that computes the variant's target book
  monthly beside the live bots, with Tyler's go-ahead. No orders, no change to any live bot, no
  allocation. Adoption needs a separate pre-registered forward check (≥ 12 monthly rebalances of
  shadow vs EW and SPY) plus Tyler.
- **FAIL:** the 2019-01..2026-09 holdout is spent for long-only S&P 500 cross-sectional factor
  selection. Not authorised without a new pre-registration on forward data:
  - other factor definitions;
  - factor weights;
  - top-N/decile cut-offs;
  - rebalance frequencies;
  - adding a size or short leg;
  - a different universe (Russell 1000, S&P 400).
- A positive-but-insignificant G1 is FAIL. It is written up as such and authorises nothing.

## 9. Outputs

`research/exp030/`:
- `ticker_map.csv`, `delist_classes.csv`;
- `partA.json`, `partB_<variant>.json`;
- `nav_<arm>.parquet`, `weights_<variant>.parquet`;
- `factor_regression.json`.

The script is `research/exp030_run.py`. Results are appended to the ledger under the EXP-030 entry.
