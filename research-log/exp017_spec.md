# EXP-017 — Does a public weather forecast know something Kalshi's price doesn't?

**Status:** PRE-REGISTERED 2026-09-13. No outcome and no price value from the series
below has been read by anyone working on this experiment. HOLDOUT SEALED.
**K:** Part A = 1 (one named test). Part B = 1 (one frozen trade rule), spent only if A passes.

## Why this experiment

The ledger through EXP-016 has two kinds of death. Seven premise-false deaths,
at least six of them published anomalies. Five real-but-untradeable deaths, all of
them *premia* (variance risk premium x4, the Kalshi maker spread) that go to
whoever supplies risk or liquidity most cheaply — never a slow retail taker.
EXP-016 Phase 1 and the Kalshi–Polymarket matcher hit the same wall (bias only at
untradeable 1c quotes; cross-venue gaps ~1c).

Every idea so far looked for an edge *inside prices everyone sees*. This is the
first test of an **information edge**: an outside, public, non-price forecast of
the number a market settles on, used hours before close, held to settlement so
the spread is paid once. Speed does not matter at this horizon, so the binding
constraint of EXP-015 does not reach it.

## Crowding read (standing criterion) — stated before any data

**Retail-crowded.** Hobbyist bots pricing Kalshi weather markets off NOAA models
are common. Under Tyler's criterion that is disqualifying *for building a
strategy*. It is registered anyway as the cheapest, best-powered measurement of
the direction (7 cities x 5 years of daily events, free forecasts), with this
pre-commitment: **a PASS does not authorise building anything.** It goes back to
Tyler as an explicit crowding decision, and the institution-crowded version of the
same idea (Kalshi S&P ranges vs SPX options) is the natural follow-up.

## Feasibility, checked before registration (counts and rules text only)

    Kalshi archive (/historical/markets, pre-2026-07-15) + live endpoint after
      KXHIGHNY   9,184 mkts  1,799 events  2021-08 ..      KXHIGHCHI  9,181 / 1,787
      KXHIGHMIA  6,952 / 1,159  2023-05 ..                KXHIGHAUS  6,933 / 1,156
      KXHIGHDEN  3,606 /   601  2024-11 ..                KXHIGHPHIL 3,606 /   601
      KXHIGHLAX  3,330 /   555  2025-01 ..
    hourly candlesticks with yes_bid / yes_ask exist back to 2021
    fresh (<=3h) two-sided quote at 15:00Z on day D, 1,200-market sample: 27%-96%
      by city-year, most 55-85% (Miami lowest)
    fee_type quadratic, fee_multiplier 1 on all seven series
    NBM text bulletin (NBS): Iowa State Mesonet archive 2021-09 .. 2026-05-05;
      AWS noaa-nbm-grib2-pds blend_nbstx files cover the whole period incl. after
    NBS contains txn (forecast max) AND xnd (its standard deviation) per station

Found during feasibility, all from rules text or metadata, none from outcomes:
- **Settlement source changed.** Markets closing on or before 2026-08-14 settle on
  the NWS Daily Climatological Report; from 2026-08-15, on The Weather Company.
  EXP-017 uses only the NWS era.
- 1,418 NYC and 1,407 Chicago markets (2021-22) have no `strike_type`; their
  bracket is stated in the rules text ("between 51-52°", ">N°").
- Settlement stations from rules text: Central Park (KNYC), Chicago Midway (KMDW),
  Miami Intl (KMIA), Austin Bergstrom (KAUS), Denver (KDEN), Los Angeles Airport
  (KLAX), Philadelphia Intl (KPHL).
- No KXHIGH city market appears in predmarket/ data, so EXP-016 exposed none of
  these outcomes (its one "Climate and Weather" row is KXHIGHINFLATION).

## Considered and NOT registered (decided on structure, not data)

- **CPI / Fed / payrolls:** monthly. At most 61, 39 and 40 events since 2021 before
  any tradeable filter, so a 60-independent-cluster bar is unreachable. Would be
  permanently UNDERPOWERED.
- **S&P 500 ranges vs SPX options:** feasible, ~1,000 daily events. Needs OPRA data,
  estimated ~$0.045/day (SPXW cbbo-1m 5-min window + definitions) = roughly $45-60,
  above the previous $30 cap. Needs Tyler's spend approval and its own spec.
  Queued as the EXP-018 candidate.

## FROZEN — cannot change based on anything the data shows

**Universe.** Series KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHAUS, KXHIGHDEN, KXHIGHLAX,
KXHIGHPHIL. Event day D from the event ticker. Only markets with close_time
<= 2026-08-14T23:59Z (NWS era). The other ~40 KXHIGH* series were not examined and
are out of scope.

**Windows.**
- CALIBRATION: day D <= 2025-05-31.
- HOLDOUT: 2025-06-01 <= day D <= 2026-08-13. SEALED: its outcomes are not read,
  plotted or summarised unless Part A has passed and Part B's calibration result has
  been written. If Part A fails, the holdout stays unread and remains available.
- Nothing with close_time >= 2026-09-01 is ever read (EXP-016's holdout).

**Decision time.** tau = 15:00 UTC on day D (11am ET, 10am CT, 9am MT, 8am PT).

**Kalshi quote.** The market's last hourly candlestick with
tau - 3h <= end_period_ts <= tau. Quote = yes_bid close, yes_ask close, in dollars
(the loader asserts every value lies in [0, 1]). Tradeable: 0 < bid < ask < 1.
Mid m = (bid + ask) / 2. No qualifying candle, or not tradeable -> excluded, counted.

**Bracket.** From strike fields when present; otherwise parsed from rules text
("greater than N" / ">N", "less than N" / "<N", "between A-B" / "A to B").
Where both exist they must agree on 100% of markets or the run stops.
Unparseable -> excluded, counted. Temperatures are whole degrees:
- greater than k:  P = 1 - Phi((k + 0.5 - mu) / sigma)
- less than k:     P = Phi((k - 0.5 - mu) / sigma)
- between a-b:     P = Phi((b + 0.5 - mu) / sigma) - Phi((a - 0.5 - mu) / sigma)

**Forecast f.** NBM text bulletin NBS, **07Z cycle of day D**, for the settlement
station. mu = txn at ftime (D+1) 00:00 UTC (the day-D daytime max); sigma =
max(xnd at the same row, 1.0). Missing txn -> excluded, counted. No parameter is
fitted to anything. The 07Z cycle is ~8h older than tau, so the market has seen
newer model runs and the morning's temperatures: this handicaps the forecast
and is deliberate.
Source: Iowa State Mesonet for days <= 2026-05-05; AWS blend_nbstx.t07z after.
Consistency check before any scoring: parse both sources on 10 fixed dates
(the 1st and 15th of 2025-12..2026-04, all inside both archives) x 7 stations. txn and xnd must match in
>= 95% of pairs, or holdout days after 2026-05-05 are excluded and counted.

**Outcome.** Kalshi `result`; only yes/no count, anything else excluded and counted.

**Cluster.** Calendar week of day D (ISO week, all cities together), because
neighbouring cities share weather systems and one city's days share regimes.
(city, week) reported alongside.

## Part A — does the forecast carry information the price lacks? (CALIBRATION, K = 1)

Named estimator: pooled OLS slope beta in

    (y - m) = alpha + beta * (f - m)

over all tradeable markets in the calibration window. beta > 0 means that when the
forecast disagrees with the price, outcomes move toward the forecast.
Inference: bootstrap over week clusters, 10,000 resamples, seed 17.

**PASS requires ALL:**
1. beta > 0 with bootstrap P(beta <= 0) < 0.05.
2. Point estimate beta >= 0.20. Below that, even a 25c disagreement is worth <5c,
   which the spread and fee absorb. Fixed now, not searched.
3. >= 2,000 tradeable markets and >= 60 week clusters.

Reported alongside, never gating: beta by year and by city; Brier score of m and of
f; share of markets with |f - m| >= 0.10.

FAIL -> the direction is recorded as "public forecast already in the price" for
Kalshi weather, Part B is not run, and the holdout is left unread.

## Part B — does it survive a taker's costs? (K = 1, scored once on the HOLDOUT)

**Trade rule**, one contract per market at tau, at most one side:
- buy YES at yes_ask if  f - yes_ask - fee(yes_ask) >= 0.05
- buy NO at 1 - yes_bid  if  (1 - f) - (1 - yes_bid) - fee(1 - yes_bid) >= 0.05

theta = 0.05 is fixed now and is not searched.
fee(P) = ceil(0.07 x C x P x (1 - P) x 100) / 100 / C at C = 100 (M = 1, verified).
excess = payoff - cost - fee - cost x 0.045 x days_to_close / 365.
Estimator (the EXP-016 form): equal-weighted mean over week clusters of each
cluster's mean excess per contract; week-cluster bootstrap, 10,000 resamples.

Order: Part B is computed on CALIBRATION first and written to
exp017_partB_calibration.json (recorded, not a verdict). Only then does the holdout
loader unlock.

**HOLDOUT PASS requires ALL:**
1. Estimator > 0 with bootstrap P(<= 0) < 0.05.
2. Among cities with >= 30 holdout trades, >= 60% have a positive mean.
3. Estimator still > 0 after dropping the single best week.
4. >= 400 trades and >= 60 week clusters; otherwise UNDERPOWERED. This is final:
   the holdout is closed past data, so there is nothing to wait for.

Written once, with exclusive create, to exp017_partB_holdout.json.

## Build log — after registration, before any outcome was read

- Census: 44,094 NWS-era markets (calibration 25,656 · holdout 18,438).
- Bracket parser vs strike fields: 0 disagreements. It first missed sub-zero
  Chicago brackets ("less than -3°"); fixed, then re-verified. 1 market unparseable
  ("greater than 83-NA°"), so it is excluded. 308 events from 2021-22 are ladders
  ("> 52", "> 54") rather than a partition; each market is still its own yes/no
  question and is scored as one.
- NBM: 12,855 station-days (Mesonet 12,155 · AWS 700), 1,836-1,837 of 1,839 days per
  station, xnd never missing (14 values of 0, floored to 1.0 as registered).
  Consistency check: **70/70 pairs identical -> OK**, so holdout days after
  2026-05-05 stay in.
- Kalshi throttles above ~5 requests/s sustained; the quote fetch is paced.

## Priors, written before any data

- Part A passes on calibration: likely (~60%). 2021-23 markets were thin and early.
- beta shrinks year over year: likely, as bots arrived. Reported, not gated.
- Part B passes on the holdout: unlikely (~15%). NBM is free and bots use it, and
  NBM's xnd may be overconfident, which makes f too extreme and trades too eager.

## Known limitations, stated before the result

1. NBM's daytime max (roughly 7am-7pm local) is not exactly the Climate Report's
   midnight-to-midnight max. The mismatch hurts the forecast, so it is conservative.
2. Hourly candles, not tick data: the quote is the last close up to 3h before tau.
3. Today's fee formula is applied to 2021-24 markets, when fees differed.
4. No depth: one contract per market, no size or impact modelled.
5. Paper only. predmarket/ stays read-only; nothing here places an order.
6. (Added 2026-09-13 while building the fetcher, before any quote or outcome was
   read.) NBM itself changed version: bulletins after ~2026-05-05 are "NBM V5.0",
   earlier ones V4.x, which is likely why the Mesonet archive stops there. The
   holdout therefore spans two forecast versions. No rule changes; beta and Part B
   are reported alongside for days before and after 2026-05-06.
   Parser sanity check on 2024-07-01: Mesonet and AWS gave identical txn/xnd for
   KNYC (80, 2) and KLAX (76, 2).
