# Vol-Premium Sleeve — AS-BUILT Spec (the validated, live version)

This is what the `volbot/` paper harness actually implements. It supersedes the research
spec (`volpremium_spec.md`) with the *validated* design and the live-trading adaptations.

## What we validated (and how)
Model-based backtest 2016–2026 (FRED VIX/VIX3M + S&P 500, Black-Scholes premium from VIX +
put-skew, daily marks, realistic costs). Refinement stack on a delta-neutral condor:

| config | Sharpe | worstMo | skew | corr-SPY |
|---|---|---|---|---|
| base (50% take-profit, SPY cost) | 0.59 | −1.3% | −1.31 | +0.35 |
| **+ expire-worthless** | **1.60** | −1.3% | −0.89 | +0.28 |
| + rich-vol timing (top tercile VRP) | 1.64 | −1.7% | +0.06 | +0.35 |
| + SPX cost (not available live) | 1.70 | −1.6% | +0.09 | +0.35 |

**Final (SPY-tradeable) expectation: ~1.6 net Sharpe, DSR ~0.99, worst month ~−1.6%, corr ~+0.35.**

Three findings that define the design:
1. **Expire-worthless did ~90% of the lift.** Closing winners early and paying round-trip cost
   every cycle was the killer. Riding OTM spreads to expiry (where they settle for *zero* cost)
   captures the full premium. → **No take-profit, no time-stop. Hold to expiry.**
2. **Rich-vol timing flips the tail positive** (skew −0.89 → +0.06). Selling only when vol is
   expensive sits out the complacent setups that precede spikes. → **VRP top-tercile gate.**
3. **Delta-neutral condor halves correlation** vs a put spread (+0.35 vs +0.67). → **Iron condor.**

## HONEST status
This is a **modeled** edge — the premium is priced from VIX, not real fills. The forward paper
test IS the validation gate. We are NOT deploying real conviction; we are gathering the one
piece of un-overfittable evidence: do real SPY option fills match the modeled premium?

## The live strategy (exactly what volbot does)
- **Underlying:** SPY (Alpaca has no SPX/XSP index options). Loses cash-settlement/1256-tax vs
  SPX, but the strategy logic and edge hold; backtest at SPY-level costs = ~1.6 Sharpe.
- **Structure:** iron condor — sell ~16Δ put + ~16Δ call, buy the $5-wide wings on each side.
  Defined risk: max loss = width − net credit, capped by the long wings.
- **DTE:** ~30 days at entry (accept 25–38 to hit a listed Friday).
- **Management — EXPIRE-WORTHLESS:** no profit-take, no time-stop. Hold to expiry; OTM legs
  expire worthless at zero cost. The ONLY active exit is the loss-stop. Close at DTE ≤ 1 to dodge
  assignment (SPY is American/physically-settled, unlike cash-settled SPX).
- **Loss-stop:** close the condor if cost-to-close ≥ 2× the credit received.
- **Entry filters (ALL must pass):**
  1. **Rich-vol:** VRP = VIX − 20d-realized-vol is in its top tercile (rolling 252d, 66th pct).
  2. **Contango:** VIX < VIX3M (term structure not inverted = no active stress).
  3. **No spike:** VIX < 30.
- **Sizing:** contracts = ⌊ RISK_FRAC(2%) × equity / (max-loss × 100) ⌋. Constant-risk, same
  principle as the champion overlay.
- **One position at a time** (matches the backtest; conservative on theta).

## Isolation & safety (non-negotiable — must not touch the other bots)
- **Own keys:** `VOLBOT_ALPACA_API_KEY` / `VOLBOT_ALPACA_SECRET_KEY` in `.env` — a SEPARATE paper
  account from champion ([removed: account identifier]) and challenger. The harness reads only these.
- **Hard paper guard:** `PAPER = True`, no code path flips it.
- **`DRY_RUN = True` by default:** computes and logs the intended trade, submits NOTHING. Flip to
  `False` only when you've watched a few dry runs and added the keys.
- **Own state/logs:** `volbot/volbot_state.json`, `volbot/volbot_log.csv`. Never reads/writes the
  champion or challenger logs.

## Data
- **VIX, VIX3M:** FRED (`VIXCLS`, `VXVCLS`) — free, ~1-day lag, fine for a daily-cadence bot.
- **SPY price + 20d realized vol + VRP history:** Alpaca stock bars.
- **Option chain + quotes:** Alpaca options API (`get_option_contracts`, `get_option_latest_quote`).
- **Delta:** computed via Black-Scholes (σ = VIX) to pick ~16Δ strikes — Alpaca doesn't return
  greeks on the contract endpoint (the official iron-condor example computes them the same way).

## Account settings you must set (paper)
1. Generate **paper** API keys on the new account → put in `.env` as the `VOLBOT_*` vars above.
2. **Level 3 options** — paper accounts have it automatically (no application).
3. **Margin account** (not cash) — spreads need ~$1,000 margin/spread; paper starts at $100k
   equity (> the $2k margin minimum). NOTE: defined-risk spreads do NOT borrow money — the
   "margin" is just collateral the broker reserves for the capped max loss. No loan, no interest,
   and it's paper. Nothing to fear here.
4. Options data: the default (free/indicative) feed is fine for a daily bot.

## Forward-test plan (the gate)
1. Run `DRY_RUN=True` for a few days — confirm it pulls the chain, picks ~16Δ strikes ~30 DTE,
   computes a sane credit, and the filters behave.
2. Flip `DRY_RUN=False` — it paper-trades one condor per cycle.
3. Track realized credit vs modeled credit, and the sleeve's Sharpe / worst month / corr to SPY
   over a forward window that includes at least one vol bump.
4. **Decision:** if real fills ≈ model and the sleeve holds ~1.5+ Sharpe forward with controlled
   tails → graduate it to a funded sleeve. If real premium is thinner → we'll see it bleed on
   paper, for free, and the kill is confirmed. Either way we learn the truth.

## Phased file map
- `volbot/config.py` — params, keys, the DRY_RUN/PAPER guards.
- `volbot/volbot.py` — data, filters, strike selection, sizing, order submission, management, run.
- `volbot/README.md` — how to run + settings.

## Modifications (registered changes to the as-built book)

### VB-2 — beta parking · registered 2026-07-20 · LIVE (armed)
**What changed.** The account's idle option collateral now buys SPY each run.
A cash reserve = `max(2× total-max-loss-at-risk, $10,000)` always stays behind
to collateralize the open condors; cash above it buys SPY, and if cash falls
below it (a loss-stop fired, or new rungs raised the reserve) SPY is trimmed to
refill. Drifts under $500 are ignored (no churn). Disabled under `DRY_RUN`,
wrapped in try/except so a parking failure can never break the condor pipeline.

**Why.** Before this, VolBot was a premium overlay sitting on ~$100k of dead
cash — it could only ever win or lose by the thin condor credit, so it could
not "compete with SPY," only tread water beside it. VB-2 makes the book own
beta and stack the premium edge on top (beta + uncorrelated overlay = the
overlay-fund construction). The condor logic, sizing, and entry filters are
**untouched**.

**Keeping the science clean (the one thing that matters).** Now that the book
holds SPY, the *account equity curve* is beta + premium and its correlation to
SPY goes to ~1.0. So the original validation gate — realized-vs-modeled credit,
the sleeve's Sharpe / worst-month / corr-to-SPY — must be read from the **condor
P&L stream alone** (rung credits and debits in `volbot_log.csv`), never from
account equity. Because VB-2 does not touch the condor engine, the premium
evidence is undisturbed *as long as it is measured separately*. If that
separation is ever lost, VB-2 has to come off — the whole point of this book is
the un-overfittable answer to "do real SPY fills match the modeled premium?",
and reading that off a SPY-dominated equity curve would answer nothing.
