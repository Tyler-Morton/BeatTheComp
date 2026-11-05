# Research log

This folder is the written record of Tyler Morton's trading research. It holds a ledger of pre-registered experiments (`experiments.md`) and the specs, audits and red-team notes that go with it. All accounts in it are paper accounts. "Live" in the log means a paper account running on market data.

The log was written with Claude Code at Tyler's direction. Apart from the marked removals described below, it is the record as written, errors included. Failed experiments, bugs, miscounts and disclosed flaws are left in. Role names such as strategist, tester, auditor, director and red team refer to Claude Code sessions, not outside people.

## How to read it

- Start with `experiments.md`. It is in the order things were written, not number order, and some results were appended far from their registration. The index below gives line numbers.
- Corrections sit next to the error. See line 1190 and the ledger audit at line 1337. Struck-through text is original text that was later retracted.
- The specs hold the frozen designs. Most of the numbered specs say that where a spec and the ledger disagree, the ledger wins.
- Specs show what was believed when they were written. For example, `volbot_spec.md` expects a Sharpe near 1.6, and EXP-010 later measured -1.54 on real quotes.
- Paths such as `research/exp024/` and `scratchpad` point to local working folders that are not published. This folder has no data, code or result files, so the numbers cannot be rerun from here.

## Data sources named in the log

- Tiingo: daily prices for most backtests, and the price source audited in `databento_audit.md`.
- Databento: OPRA option quotes for EXP-007, 007b, 010, 011 and 028, and the audit in `databento_audit.md`.
- Alpaca: minute and daily bars, plus the paper account records used in C2 and EXP-021.
- Yahoo Finance: prices for EXP-019, 020 and 022, and a rejected source in EXP-030.
- FRED: VIX and T-bill series.
- SEC EDGAR and XBRL: filings for EXP-007b, 008 and 030.
- Massive: 8-K event tags for EXP-004.
- CFTC: positioning data for EXP-013.
- Kalshi and Polymarket public APIs: EXP-015, 016, 017 and `kalshi_poly_notes.md`.
- NOAA NBM bulletins through Iowa State Mesonet and AWS: EXP-017.
- AQR data library: the TSMOM factor for EXP-020 and 025.
- Ken French data library: EXP-029 and 030.
- World Gold Council: gold prices for EXP-029.
- fja05680/sp500 on GitHub: index membership for EXP-030.
- WRDS and CRSP: accessed through the University of Utah. I used CRSP to cross-check the bots' cached prices and Fama-French factors for a descriptive attribution of the champion's backtest, outside the numbered experiments. EXP-030 may also use CRSP for delisted-name prices, under the rules in Amendment 2 at line 5552. The ledger has no results from them yet.
- Bloomberg: allowed in EXP-029 to spot-check about 10 dates, never as a data source. The log records no Bloomberg figures.

## Index

Line numbers refer to `experiments.md` unless another file is named.

| Experiment | Topic | Outcome as recorded | Line |
|---|---|---|---|
| EXP-001 | Scheduled-event de-risking, NFP part run | Killed at the premise gate. Vol ratios 1.000 and 1.090 against a 1.15 bar. FOMC and CPI parts not run. | 38 |
| EXP-002 | HAR-RV vol forecast, first run | Killed. Sharpe 0.524 against 0.552. | 130 |
| EXP-003 | Absorption-ratio de-risking | Killed at the premise gate. 0 of 3 terciles cleared the bar. | 175 |
| EXP-004 | 8-K event drift | Killed. F1 failed calibration. F2 passed calibration, then failed the holdout. | 243 |
| EXP-005 | VIX term-structure de-risk gate | Premise passed. Both trading variants killed. | 331 |
| EXP-006 | 12-1 momentum sleeve | Killed at the premise gate. +18 bps a month, P = 0.30. | 413 |
| EXP-007 | Earnings vol crush | Pilot only. 16 of 16 events had implied above realized. No formal gate was run. | 478 |
| EXP-007b | Earnings short-premium strategy | Killed. Mean -4.3%, median +6.1%. | 611 |
| EXP-008 | Lazy Prices with LLM diffs | Killed at the calibration gate. The sign came back opposite the published effect. | 540 |
| EXP-009 | Correlation-conditioned index variance premium | Part A passed (+1.93, P = 0.019). Part B not implemented. Survivorship not addressed. | 710 |
| EXP-010 | VolBot on real option quotes | Failed. Sharpe -1.54 and -1.24 against a 0.70 bar. | 870 |
| EXP-011 | Implied correlation premium | Part A passed (+0.034, P = 0.024). Cost gate failed (0.27x against 2.0x). Stopped. | 1004 |
| EXP-012 | Implied correlation as an exposure signal | Killed at the collinearity gate. The threshold named no estimator, recorded as a process error. | 1182 |
| EXP-013 | Positioning divergence and Treasury returns | Failed on the primary 4-week horizon (P = 0.200). The 13-week pass was not counted. | 1223 |
| EXP-014 | HAR-RV, second run | Recorded as a pass, with one condition rewritten after two others were known. A later audit disputed it and EXP-019 relabelled it unreplicated. It has no section in `experiments.md`. | `harrv_spec.md` 87 |
| EXP-015 | Kalshi maker side | Parts A and B passed. Part C failed on both arms. Part D failed. | 1374 |
| EXP-016 | Kalshi taker side | Phase 1 gave no verdicts. Phase 2 is registered. No Phase 2 score is in the ledger. | 2089 |
| EXP-017 | Weather forecast against Kalshi prices | Part A passed (beta 0.259). Holdout failed (-3.23c a contract, 0 of 7 cities). | 2213 |
| EXP-018 | Not used | The number was named for a candidate that was never registered. | 2253 |
| EXP-019 | HAR-RV against trailing estimators | Failed Part A. Part B not run. Found a production timing bug. | 2777 |
| EXP-020 | Managed-futures sleeve | Passed, with the proxy gate cleared by 0.004. Red team called it wounded. A replication with a disclosed blinding breach reached the same verdict. | 2414 |
| EXP-021 | Challenger paper book against its backtest | Inconsistent. Weekly tracking error 6.50% against 6.0%. | 2606 |
| EXP-022 | EWMA against trailing-40d | Failed. Part A passed, Part B worse. | 2941 |
| EXP-023 | HAR on intraday realized variance | Failed Part A. The 1-day horizon cleared, the 5-day did not. Part B not run. | 3129, 3968 |
| EXP-024 | Champion re-decision cadence and 3x cap | Failed. All three variants failed G2. Holdout left sealed. | 3210 |
| EXP-025 | Trend sleeve inside the overlay against T-bills | Failed. The edge depended on one crisis year per window. | 3723 |
| EXP-026 | No-trade band on the scaler | Failed. All three variants failed G1. | 3529 |
| EXP-027 | Monthly plus 30% cap against the champion, 2011 to 2018 | Passed after an audit tightened a gate. Not shown to beat the champion risk-adjusted. Red team: survives, with a smaller Sharpe effect. | 4047 |
| EXP-028 | Deep-ITM LEAPS against leveraged ETFs | H1 and H2 failed. Holdout not opened. | 4929, 5700 |
| EXP-029 | Correlation-gated duration | Inconclusive on data. Holdout not opened. | 4647, 5629 |
| EXP-030 | Long-only multi-factor S&P 500 | No result yet. The data build priced 94.1% against a 95% bar. Next step depends on CRSP or the declared fallback. | 5216 |

Two ledger entries have no experiment number. C2 at line 2304 is an execution audit of the paper books. The ledger audit at line 1337 corrects a miscount of why experiments failed.

## Counts

Counted from the entries above: 30 entries under 29 experiment numbers. EXP-018 was never used and EXP-007 has a second entry, EXP-007b.

- Failed or killed: 21 (001, 002, 003, 004, 005, 006, 007b, 008, 010, 011, 012, 013, 015, 017, 019, 022, 023, 024, 025, 026, 028).
- Passed, with limits stated in the entry: 2 (020, 027).
- Part A passed, no strategy built: 1 (009).
- Passed, then unreplicated: 1 (014).
- Inconsistent: 1 (021).
- Inconclusive on data: 1 (029).
- Pilot only: 1 (007).
- No final result yet: 2 (016, 030).

The ledger's own running counts, such as "16 experiments, 2 durable passes" at line 2050, were written at the time and are left as they are.

## What was removed and why

Removals are marked in place, for example `[removed: raw vendor data]`. Nothing else was changed.

- Licensed data. The University of Utah's license for WRDS, CRSP and Bloomberg is academic-only, so figures from them do not belong here. These sources stay named, along with what each was for. The current text has no such figures, so nothing had to be cut under this heading.
- Raw vendor data. Closing prices in `databento_audit.md` and two printed rows of an AQR file. Summary statistics and backtest results computed from vendor data stay.
- Unrelated private notes. References to an unrelated private project, career remarks, a person's name and an account identifier.

Key names such as `TIINGO_API_KEY` appear in the log. No key values do.
