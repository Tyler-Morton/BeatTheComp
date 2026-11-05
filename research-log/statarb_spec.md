# Stat-Arb / Pairs-Trading Sleeve — Build Spec

## Why (the Sharpe thesis)
Add a **market-neutral, uncorrelated** return stream to lift the COMBINED book Sharpe
toward ~1.0. The current ETF book is ~0.56 (validated, 7.4yr). Combining uncorrelated
streams is the only real free lunch: combined Sharpe ≈ single Sharpe × √N. A market-neutral
stream that's genuinely uncorrelated to the equity book lifts the whole more than improving
any one strategy would.

**HONEST PRECONDITION:** this only helps if it has a real, validated, positive edge AFTER
COSTS. The simple version is largely competed away. If validation shows no edge, we KILL it
(a clean kill is a win). Capital in a zero-edge stream *hurts* combined Sharpe.

## The strategy
Cointegration-based pairs mean-reversion, market-neutral:
- Find two assets whose price SPREAD is mean-reverting (cointegrated, not just correlated).
- When the spread diverges abnormally: short the rich leg, long the cheap leg.
- Bet on convergence; exit when it reverts. You're hedged, so direction of the market barely matters.

## The math
1. **Cointegration test** — Augmented Dickey-Fuller (ADF) on the spread (or Engle-Granger /
   Johansen). Keep only pairs whose spread is stationary (p < 0.05). Correlation is NOT enough.
2. **Hedge ratio** — OLS to start (regress A on B); upgrade to a Kalman filter for a dynamic ratio.
3. **Spread + z-score** — spread = A − ratio·B; z = (spread − rolling_mean) / rolling_std.
4. **Half-life (Ornstein-Uhlenbeck)** — estimate how fast the spread reverts; sets max holding period.

## Entry / exit / stop
- ENTER when |z| > 2.0 (short spread if z>2, long spread if z<−2).
- EXIT when z crosses back toward 0 (or a small profit target).
- HARD STOP when |z| > 3.0–3.5 (the relationship likely broke — cut it).
- TIME STOP — exit if not reverted within ~2–3× the half-life.

## Universe (candidate pairs)
Start with ~10–20 economically-linked candidates:
- Same-sector ETF pairs (two semis, two energy, etc.).
- Related large-caps (Coke/Pepsi, two banks, two miners).
- An ETF vs a basket of its components.
Prefer less-obvious / less-liquid pairs (your small-size capacity edge); the obvious liquid
pairs are already arbitraged.

## Risk controls
- **Diversify across many pairs** — no single pair can sink the book (the main defense).
- **Vol-based position sizing** — constant risk per pair (same principle as the champion's overlay).
- Hard z-stop + time stop (above).
- **Event filter** — don't enter around earnings; exit if either name has pending M&A / major news.
  Corporate events are the #1 cause of a pair PERMANENTLY decoupling. (Reuse the EXP-001 calendar.)
- Re-check cointegration periodically; trim/exit if it weakens (rising ADF p-value).
- Position + gross-exposure caps.

## Costs (do NOT skip — this is what kills naive stat-arb)
- Model the bid-ask spread on BOTH legs (two instruments per trade).
- Model short-borrow cost on the short leg.
- An intraday/high-frequency version dies on costs; favor daily/hourly bars and low turnover.

## Validation plan (the whole point)
1. Backtest on clean daily/hourly data (Tiingo) WITH realistic costs.
2. Purged / walk-forward cross-validation (no lookahead).
3. Deflated Sharpe Ratio on the result (honest K = number of pair/param configs tried).
4. **Decision rule (pre-registered):**
   - DEPLOY-QUEUE only if net-of-cost Sharpe clears a real bar (e.g. > 0.4) AND DSR says the
     edge isn't a multiple-testing artifact AND it's genuinely low-correlation to the equity book.
   - Otherwise KILL. A zero-edge stream hurts the combined Sharpe.

## Integration into the book
- Run as a SEPARATE paper account (like the challenger) or a dedicated sleeve.
- Market-neutral → low correlation to the equity book → the diversification that lifts combined Sharpe.
- End-state: champion (growth) + challenger (diversified) + stat-arb (market-neutral) +
  (later) trend / vol-premium, all under one vol overlay = the ~1.0 Sharpe target.

## Phased plan
1. **Research** — build the cointegration screen, find pairs, eyeball the spreads.
2. **Backtest** — entry/exit/stops + costs; compute metrics.
3. **Validate** — purged CV + DSR; apply the decision rule (deploy-queue or kill).
4. **Paper** — if it survives, run live on a paper account and forward-track vs the equity book.
5. Only trust it after a forward window (the one thing that can't be overfit).

## Tech
- Python (`statsmodels` for ADF/cointegration, numpy/pandas, optional `pykalman`).
- Data: Tiingo daily (you have the key). Hourly later if needed.
- Reuse your DSR + purged-CV tools and your vol-sizing logic.
- C++ NOT needed (bar-level, not HFT); [removed: career note]

## Honest expectations
- Standalone Sharpe likely modest (the edge is competed); the value is being UNCORRELATED.
- It may not survive validation — that's fine, a clean kill saves you from a bad bet.
- [removed: career note]
