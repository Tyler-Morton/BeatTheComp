# Portfolio Bot - Showcase Page

A clean, public-facing web page for the trading bot. Light finance aesthetic
(Jane Street / Stripe vibe) with a flowing animated hero, live Alpaca portfolio
value, a real performance-vs-SPY chart, and the validated backtest numbers.

## Run it

```bash
python3 web/app.py
```

Then open **http://localhost:5050**

To stop it, press `Ctrl + C` in the terminal.

## What it shows

- **Hero** - animated gradient background, live portfolio value badge, today's change
- **Stats strip** - live equity, today %, Sharpe, max drawdown, regime
- **Strategy** - the 4 layers (3x ETFs, HRP momentum, vol-targeting, ML throttle)
- **Performance** - dual-line chart of the portfolio vs the S&P 500, with
  `1W / 1M / YTD / ALL` range buttons and a hover tooltip. Both lines are indexed
  to a $1,000 start per window, so the comparison is fair.
- **Since-inception metrics** - total return, vs S&P, best/worst day, win rate,
  days live, rebalances, current cash sleeve
- **Backtest results** - DSR 99.4%, Sharpe 0.89, vol reduction, max drawdown
- **Risk architecture** - the three guardrails
- **Footer** - contact email (GitHub + LinkedIn live in the top nav)

## Where the data comes from

- **Live portfolio value** - asked from Alpaca at page load (`broker.get_live_snapshot`)
- **Equity history** - `daily_log.csv`
- **SPY comparison** - the bot's own `prices_cache.parquet`
- **Backtest numbers** - the `BACKTEST` dict at the top of `web/app.py`

## Important: this is read-only

This page **only reads** the files the bot already writes and asks Alpaca for the
current account value. It **never** places trades, never runs `main.py`, and never
changes any bot state. The bot's normal GitHub Actions cron is completely unaffected.

## Editing

- Page content / sections -> `web/static/index.html`
- Styling -> `web/static/style.css`
- Animations, chart, live data -> `web/static/app.js`
- Backend / data API -> `web/app.py` (the `/api/stats` route)

The validated research numbers live in one place: the `BACKTEST` dict at the top
of `web/app.py`. Update them there.
