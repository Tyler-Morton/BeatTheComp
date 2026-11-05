# EXP-016: Where are Kalshi prices wrong, and can a taker collect it?

**Status:** PRE-REGISTERED 2026-09-13 in experiments.md. HOLDOUT SEALED. The
ledger entry is the binding version: where it is more specific than this file
(result-value rule, additive excess form, named estimator), the ledger wins.
Before registration no price-vs-outcome relationship was examined. Only schema,
counts, quote shapes and date ranges were checked (the `result` column was
never read).

## Why this, why now

EXP-015 killed the maker side on Kalshi twice (10 days, then 120 days / 300
markets). The binding constraint was queue position: a 60-second REST poller
is at the back of the line by construction, so the fills it gets are the
informed ones. That constraint only binds strategies that need passive fills.

The structure it does not reach: take a price once, hold to resolution. Speed
is irrelevant. Twice-daily snapshots plus resolutions (predmarket/) are the
wrong data for market making and the right data for this.

## What is already published

- Whelan, "Makers and Takers" (300,000+ Kalshi contracts): prices are
  informative but show a clear favorite-longshot bias. Low-price contracts
  win far less often than needed to break even.
- Unemployment markets (287 contracts, 2021-2026): contracts under $0.30
  overpriced by 7.7c on average, 4.0% win rate.
- Krause, CPI markets (95 contracts): no favorite-longshot bias.
- "Decomposing Crowd Wisdom" (arXiv 2602.19520): calibration varies by domain,
  horizon and trade size.

So the premise "a bias exists somewhere" is likely true, unlike most of this
ledger's deaths. The open question is narrower: does any of it survive a
taker's spread, fees and locked collateral, and in which domains.

## Crowding read

The bias comes from retail buying longshots. The people collecting it are
professional makers with better plumbing, which is EXP-015's wall. The naive
version, "always buy the near-certain side," is the obvious retail idea and
is rejected. What survives the crowding rule is a conditioned version
(domain x horizon x liquidity, collateral-adjusted, correlation-clustered) on
a dataset nobody sells. That barrier is capability, not secrecy.

## Data feasibility (checked 2026-09-13, outcomes not read)

    resolved markets that also appear in a snapshot        3,192
      every snapshot taken after close/settlement             379   (12%, would leak the answer)
      no snapshot at least 24h before close                  442
      usable: a snapshot at least 24h before close          2,750
      usable AND a real two-sided quote at that snapshot      944

Most common quote at the usable snapshot: bid $0.00 / ask $0.01 (907), then
bid $0.99 / ask $1.00 (357). Roughly half the usable markets were already
one-sided at the extremes a day before close. Where yes_bid is 0 there is no
one to fade: buying NO costs 1 - yes_bid = $1.00 and earns nothing. The
extremes, where published bias is largest, are mostly not executable.

The 944 two-sided contracts:

    spread at the snapshot     median 2.8c, p90 7.0c
    by category                Elections 355, Financials 328, Politics 172,
                               Sci/Tech 65, Companies 14, Economics 9, Weather 1
    by close month             Jul 273, Aug 539, Sep 132
    independent clusters       302 by ticker rule, 127 by (category, close date)

Effective sample is 127 to 302 independent events, not 944.

Known data weaknesses, all handled by the fixed rules below:
1. Post-close snapshots leak outcomes.
2. Sample is 38% Elections, mostly primaries. Not representative of Kalshi.
3. No event ID column. "Ticker minus last segment" under-clusters: the same
   race appears across KXVOTEPRIMARY, KXPRIMARYPLACE and KXPRIMARYMOV.
4. Snapshots run 0.4 to 7.9 hours late, so use `ts`, never the schedule.
5. Resolution sweeps only see recent settlements; one missed run (Aug 6).

## Design: explore, then confirm

Same split as EXP-004. Exploration is allowed, but only on data that can
never count as evidence.

### FROZEN AT REGISTRATION (before any exploration)

**Holdout.** Markets with close_time on or after 2026-09-01 are sealed. No
exploration, plotting, or summary statistic touches them until Phase 2 is
registered. Every future resolution from the running collector joins the
holdout automatically.

**Calibration window.** close_time before 2026-09-01. Explore freely.

**Mechanics that cannot depend on what exploration finds:**
- Snapshot: the last one with ts <= close_time - 24h AND ts < first_seen_settled.
  No qualifying snapshot, excluded.
- Tradeable: yes_bid > 0, yes_ask < 1, yes_bid < yes_ask. Otherwise excluded
  from P&L (still reported in calibration curves, flagged one-sided).
- Calibration uses mid. P&L uses the executable side only: yes_ask to buy
  YES, (1 - yes_bid) to buy NO.
- Fees: Kalshi taker formula ceil(M x 0.07 x C x P x (1 - P)) at C = 100
  contracts, M per series from Kalshi's published schedule (M = 1 if not
  found, flagged). C = 1 reported alongside, because rounding up to the cent
  dominates single-contract trades.
- Collateral: profit / capital locked, annualized over days from snapshot to
  close, minus 4.5% risk-free. A 5c edge over a week and over five months are
  not the same trade.
- Clustering: PRIMARY cluster = (category, close date). Conservative on
  purpose, and it makes election night one cluster, which it is. Ticker-rule
  clusters reported alongside as an upper bound.
- Inference: block bootstrap by cluster, 10,000 resamples.

### Phase 1: exploration (calibration window only, K = 0, no verdicts)

Anything is allowed. Every cut examined gets one line in
research/exp016_exploration_log.md, so K stays honest. Candidate cuts:

1. Calibration curve by price bucket (the favorite-longshot test)
2. By category. Published work says it varies by domain.
3. By time to close. Does mispricing grow or shrink near expiry?
4. By liquidity / open interest / spread. Is the bias only where you can't size?
5. Stale markets: price unchanged across many snapshots vs active ones
6. Round-number stickiness (5c, 10c, 25c, 50c)
7. Kalshi vs Polymarket on the same event, as analysis only. Matching markets
   across venues has no shared ID.
8. Primaries after the result is effectively known (careful: this is where
   look-ahead hides)

Output: at most 3 written hypotheses, each with an exact definition.

### Phase 2: confirmation (registered after Phase 1, before the holdout is touched)

K = number of hypotheses carried (3 or fewer). Each is tested once. A
hypothesis PASSES only if ALL hold on the holdout:
1. Mean collateral-adjusted excess return per cluster > 0, after fees at
   C = 100, block-bootstrap P < 0.05 / K.
2. Same sign in at least 60% of clusters.
3. Sample: at least 400 tradeable contracts and 60 primary clusters.
   Otherwise UNDERPOWERED (not FAIL): report and wait for more resolutions.

Primary result = full holdout. If one close date contributes more than 20% of
clusters' weight, the result excluding it is reported ALONGSIDE, never
substituted.

At the current pace (132 tradeable contracts in the first 13 days of
September) the holdout reaches the sample bar around late October to
November.

### Phase 3: shadow record (only after a Phase 2 PASS)

Register the strategy in predmarket/shadow.py STRATEGIES, log would-orders
on live snapshots, score against resolutions. Real money does not live in
predmarket/ and is a separate human decision.

## Already ruled out (do not repeat)

- Market making on Kalshi: EXP-015 KILL at 10 days and at 120 days / 300 markets.
- Ladder / overround arbitrage: 0 of 169 exhaustive events.
- Cross-venue arbitrage with real orders: violates predmarket's read-only rule.
- "Always buy the near-certain side": retail-crowded, and mostly one-sided anyway.

## Honest priors (written before any outcome was seen)

- A bias exists somewhere in this sample: likely.
- Any of it survives spread, fees and collateral on the holdout: unlikely.
  Base rate is 3 passes in 15.
- Most likely result: bias concentrated at extreme prices where markets are
  one-sided and nothing is executable, with the two-sided middle roughly
  calibrated. That would still be a finding: it locates the bias and says who
  can and cannot collect it.

## Decisions (resolved at registration, 2026-09-13)

Tyler accepted the proposed defaults:
1. Holdout cutoff: 2026-09-01.
2. Fee size C: 100 contracts.
3. Holdout sample bar: 400 tradeable contracts and 60 clusters.
4. Snapshot horizon: 24h before close.
5. Polymarket in Phase 1 exploration: yes, analysis only.

Found at registration: the `liquidity` column is 0.0000 in every row (Kalshi's
`liquidity_dollars` comes back empty). Use open_interest and volume instead.
