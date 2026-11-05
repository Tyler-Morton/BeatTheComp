# Data-quality audit — Databento vs Tiingo

*Window 2024-07-11 → 2026-07-08 · 15 tickers (the live bots' universe)*
*Databento dataset: `EQUS.SUMMARY` (consolidated daily OHLCV, unadjusted) vs Tiingo raw `close` · query cost $0.0117*

## Per-ticker agreement

| ticker   |   days |   median|bps| |   max|bps| |   %within5bps | worst day   |   db@worst |   ti@worst |
|:---------|-------:|--------------:|-----------:|--------------:|:------------|-----------:|-----------:|
| QQQ      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| TQQQ     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| UPRO     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| SOXL     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| TECL     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| VGT      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| MTUM     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| IWM      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| AVUV     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| BITO     |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| VEA      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| GLD      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| TLT      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |
| SHV      |    498 |             0 |       0.45 |           100 | 2024-11-29  | [removed: raw vendor price] | [removed: raw vendor price] |
| SPY      |    498 |             0 |       0    |           100 | 2024-07-11  | [removed: raw vendor price] | [removed: raw vendor price] |

**15/15 tickers agree within 5 bps on ≥99% of days.**

## Notes
- Raw close vs raw close: adjusted prices are excluded on purpose, so dividend/split adjustment policy differences cannot masquerade as errors.
- Residual small deviations usually trace to consolidated-tape vs primary-exchange closing print conventions, not data corruption.
- Conclusion feeds the bots directly: our backtests rest on Tiingo; this audit measures that foundation against an exchange-licensed source.