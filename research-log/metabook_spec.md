# Meta-Book: Sleeve Combination Engine + ML Roadmap — Build Spec

## Why (the Sharpe thesis, final form)
We now run three live sleeves:
- **Champion** — aggressive leveraged equity momentum (high beta, high vol)
- **Challenger** — diversified vol-targeted book (defensive)
- **VolBot** — defined-risk vol-premium condors (~uncorrelated, +0.35 to SPY)

Multi-strat shops (Citadel/Millennium) don't win with one magic strategy — they win with a
**ruthless allocation engine over many okay strategies**. Combined Sharpe ≈ single Sharpe × √N
when streams are uncorrelated. The meta-book is that engine for our three sleeves. Realistic
target: **combined book Sharpe ~1.0 with roughly half of SPY's drawdown** — which beats the
~85–90% of active PMs who trail SPY over 10 years (SPIVA).

## HONEST PRECONDITION
The combiner cannot conjure edge. It amplifies what the sleeves already have by (a) sizing
their *risk* correctly relative to each other, (b) cutting gross when they start moving
together, and (c) producing evidence (attribution) so we make decisions on data, not vibes.
If a sleeve has no edge, the combiner's job is to *shrink it* — same kill-discipline as DSR.

## Architecture (three layers)

### Layer 1 — Measurement (build first; pure win, zero risk)
Daily job that pulls each sleeve's equity curve (Alpaca portfolio-history API, all 3 accounts):
- Per sleeve: rolling vol, Sharpe, max drawdown, hit rate, contribution to book P&L.
- **Pairwise rolling correlations** between sleeves (the diversification is only real if these
  stay low — measure it, don't assume it).
- Combined book: equal-weight and risk-weighted curves vs SPY benchmark.
- Output: one CSV log + one console/PNG report ("the tape"). This is the attribution layer —
  which sleeve is earning its capital, which is dead weight.

### Layer 2 — Allocation engine (shadow mode first)
Computes what each sleeve's **risk budget** *should* be:
1. **ERC (Equal Risk Contribution)** across sleeves — inverse-vol weights adjusted by the full
   covariance so each sleeve contributes equal risk to the book. (Risk parity at the meta
   level; same philosophy as HRP inside the champion, one level up.)
2. **Book-level vol target** (~12%) — the combined book, not just each sleeve, holds constant
   risk. Same overlay math we already trust, applied at the top.
3. **Correlation circuit-breaker** — if rolling sleeve correlations spike (e.g. short-vol and
   equities converging in a selloff), cut gross across the board. This is the crash defense
   that no single sleeve can see on its own.
4. **Slow performance gating** — a sleeve in sustained drawdown beyond its backtested envelope
   gets its budget trimmed (meta circuit-breaker). Deliberately SLOW (quarterly-ish, wide
   bands) — fast performance-chasing is noise-chasing; our own adaptive selector uses a 15%
   override margin for the same reason.
5. **Kelly guard** — cap total book risk at a conservative fraction (≤ ~0.25×) of the
   Kelly-implied optimum from realized stats. Protects against overbetting a lucky streak.

### Layer 3 — Implementation via risk dials (no cash transfers needed)
The sleeves live in separate paper accounts, so we can't move capital between them. We don't
need to: **every sleeve already has a risk knob.**
- Champion/Challenger: `OVERLAY_TARGET_VOL`
- VolBot: `RISK_FRAC`
The meta-layer implements its allocation by *setting each sleeve's dial*, not by wiring money.
v1 runs **advisory/shadow**: it logs what the dials *should* be and tracks the hypothetical
combined curve vs naive equal-weight. Only after the shadow record proves value do we let it
actually write the dials (and even then, bounded: dials move max ±20%/week).

## ML & quant upgrades — the honest map

### Where ML legitimately helps us (defensive / structural — the survivable kind)
1. **Crash throttle (BUILT, off)** — gradient-boosted P(drawdown) classifier scaling exposure.
   Next step: run in **shadow mode** (log crash-prob + intended multiplier daily, act on
   nothing) for 2–3 weeks of calm market, then enable. Already coded in `risk_overlay.py`.
2. **HAR-RV vol forecasting (highest value-per-effort)** — replace trailing-window realized vol
   with the HAR model (Corsi 2009): tomorrow's vol regressed on daily + weekly + monthly
   realized vol components. Simple OLS, 3 features, robust, standard — and demonstrably better
   than a 40-day trailing window. Directly improves BOTH the vol-target overlay (less lag =
   the June problem) and VolBot's VRP calc (better realized-vol estimate = better rich-vol
   timing). Econometrics, not deep learning — exactly the sophistication level that survives.
3. **Meta-labeling for VolBot (López de Prado)** — ML that does NOT generate signals; it sizes
   signals the rules already produced. Train a classifier on historical condor entries
   (features: VRP level, term-structure slope, realized-vol trend, days-since-spike) →
   P(this condor ends profitable) → scale contracts 0.5×–1.5×. The respectable "ML on top of a
   strategy" pattern: the edge stays rules-based and explainable; ML only modulates size.
   Needs a season of forward trades to train on — queue for after the forward test.
4. **HMM regime detection (shadow)** — a 3-state Hidden Markov Model on SPY vol/trend features
   as a challenger to the rule-based regime vote. The June RISK_ON↔CHOPPY whipsaw cost the
   champion real money; HMMs give sticky, probabilistic regimes (fewer flip-flops). Run in
   shadow next to `regime.py`, compare regime-call quality for a quarter, promote only if it
   demonstrably whipsaws less.

### What we will NOT do (our own base rates: 1 of 9 ideas survived)
- ❌ ML/NN **return prediction** — the retail graveyard; unfalsifiable overfitting machine.
- ❌ LLM stock-picking — already tried, already killed (alpha sleeve).
- ❌ Fast adaptive allocation — reacting to weeks of performance = chasing noise.
- ❌ New exotic anomalies without the full DSR gauntlet.

## Validation plan
1. **Backtest the allocator** on the sleeves' historical curves (champion/challenger live logs
   + VolBot's validated backtest curve): ERC + vol-target + corr-breaker vs naive equal-weight.
   Metric: combined Sharpe, maxDD, worst month. The combiner must beat equal-weight on
   risk-adjusted terms or it doesn't ship.
2. **Shadow-run live** ≥ 1 month: log intended dials daily; compare shadow book vs actual.
3. Only then wire the dials (bounded moves). Every stage logged, reversible, kill-switchable.

## Build order
1. `metabook/measure.py` — account pulls, per-sleeve stats, correlations, combined curve, report. **(build now)**
2. `metabook/allocate.py` — ERC + book vol-target + corr-breaker + Kelly guard, shadow log. **(build now, shadow)**
3. HAR-RV module + A/B vs trailing vol in the overlay backtest. **(next)**
4. Crash-throttle shadow mode switch. **(next, calm market)**
5. Meta-labeling + HMM. **(after VolBot forward season)**

[removed: career note]
