# Red team + independent rebuild: EXP-027 (V3 monthly + cap30 vs A0 as-live)

Written 2026-10-13 by the red-team rebuilder. This is **reported only**. It does not
re-adjudicate the EXP-027 verdict, which stays PASS under its frozen rule.

**Call: SURVIVES.** The rebuild matches the RESULT on every quantity I compared. All the
EXP-027 gates still pass under each attack I ran: 11 decision-day shifts, cap 25% and 35%,
3x-wide costs and flat costs up to 20 bp, 3 lookback variants, and 2 execution models.

That does not mean every headline number holds. The Sharpe *size* is weaker than reported:
- About half of H's +0.30 ΔSR is gross timing luck, and its sign flips on D.
- The cap does not produce the Sharpe gain. The cap makes the tail smaller, and the monthly
  cadence saves the cost.
- In a fast crash that starts mid-month (Feb–Mar 2020), V3 is late and does worse.

Code and outputs are in `research/redteam027/`:
- `INTERPRETATIONS.md`: I1–I15 and attacks A1–A7, written before any sim ran.
- `rt_engine.py`, `core.py`, `attacks.py`, `livepath.py`, `subper.py`.
- `*.json` and `peryear_*.csv` hold every number below.

Nothing tracked was edited. No orders were placed. `.env` was not read.

---

## Part 1: independent rebuild

### How it was built
- **Not read:** `research/exp024/engine.py`, `run_D.py`, any `research/exp027/*.py`, and the
  tester's INTERPRETATIONS/DECISIONS files.
- **Reused:** the champion's pure library functions only: `optimizer.select_strategy`,
  `optimizer.optimize`, `risk_overlay.vol_target_scaler` and the `regime` signal and vote
  functions. The main-repo copies are byte-identical to worktree d6a6f81.
- **Written from scratch:**
  - the lookback window, the column rule and the decision loop;
  - the overlay application, the cap and the crumb fold;
  - the risk gate (without side effects) and the drift gate;
  - accounting, costs, the breaker, the monthly schedule, the metrics and the bootstrap.
- **Data:** a different vendor on purpose. I used Yahoo chart-API adjclose; the original
  used Tiingo.
  - Row index on H is identical to `prices_H.parquet`: 2,516 rows.
  - Daily-return differences are mostly under 1 bp.
  - Some single-print disagreements: TECL 2010-03-23 (Tiingo +12.5% vs Yahoo +3.1%), SOXL
    Oct 2011 and VGT 2014-12-18.

### Interpretations that could matter
- **I3:** the lookback is "date > date(i−1) − 342d, last 252", the spec's wording. Live
  actually anchors on the run date, so I ran that as attack A7.
- **I11:** before the first decision the book is 100% SHV. Warm-up costs feed the breaker.
- **I13:** V3 re-decides on the first session of each month, plus the first possible
  decision day.

### Match table (H, 5 bp, breaker on unless stated)

Tolerances: turnover ±20%, MaxDD ±2 pts, ΔSR ±0.10.

| Quantity | RESULT | Rebuild | Match |
|---|---|---|---|
| A0 turnover ×/yr | 71.51 | 71.1 | ✔ (−0.6%) |
| V3 turnover ×/yr | 11.05 | 11.1 | ✔ |
| Cost saved @5 bp | 3.02%/yr | 3.00%/yr | ✔ |
| A0 MaxDD | −34.96% | −34.66% | ✔ (0.3 pt) |
| V3 MaxDD | −27.70% | −28.62% | ✔ (0.9 pt) |
| G3 Δ MaxDD | +7.25 pts | +6.04 pts | ✔ |
| A0 / V3 Sharpe (4.5% RF) | 0.093 / 0.399 | 0.092 / 0.386 | ✔ |
| **ΔSR, constant RF** | **+0.306** | **+0.295** | ✔ (0.011) |
| ΔSR, SHV-RF | +0.391 | +0.380 | ✔ |
| ΔSR at 0 / 3 / 10 bp | +0.178 / +0.245 / +0.380 | +0.163 / +0.254 / +0.366 | ✔ |
| ES1% A0 / V3 (ratio) | −5.00 / −3.24 (0.649) | −5.00 / −3.26 (0.652) | ✔ |
| Worst day A0 | −9.04% on 2018-10-10 | −9.04% on 2018-10-10 | ✔ exact |
| Worst day V3 | −4.71% on 2015-08-24 | −4.79% on 2015-08-21 | value ✔, **date differs** (vendor; my 08-24 is −4.66%) |
| A0 breaker blocks | 63 days, 2016-05-02..12-06 | 61 days, 2016-05-02..12-06 | ✔ (same dates) |
| Breaker-off A0_nb Sharpe / MaxDD | 0.060 / −37.04% | 0.063 / −36.75% | ✔ |
| F4: A0 mean 3x; cap-binding share; pre-cap mean/max | 35.1%; 62.5%; 35.8% / 93.1% | 35.2%; 62.5%; 36.0% / 93.1% | ✔ |
| V3 days held >30%; max held | 670; 32.3% | 743; 32.7% | ~ (definition of "held") |
| Bootstrap σ; 90% CI; p(Δ* ≤ −0.10) | 0.209; [−0.034, +0.652]; 0.025 | 0.211; [−0.047, +0.644]; 0.029 | ✔ |
| Warm-up E/ATH at 2011-04-01, A0 / V3 | −7.8% / −3.7% | −7.76% / −3.73% | ✔ |
| A0 strategy switches/yr | 29.6 | 29.2 | ✔ |
| CAGR A0 / V3 | 4.64% / 9.28% | 4.62% / 9.10% | ✔ |
| Per-year ΔSR, 2011–18 | .81 .11 .84 .57 **−.07** 1.07 .55 .35 | .81 .11 .84 .58 **−.19** 1.10 .55 .35 | ✔ except 2015 (Aug-2015 vendor prints) |
| *D bonus:* A0 / V3 Sharpe @5 bp | 0.333 / 0.445 | 0.312 / 0.445 | ✔ |
| *D bonus:* turnover; MaxDD | 68.7 / 11.3; −39.7 / −22.2 | 67.3 / 11.3; −39.76 / −22.24 | ✔ |
| *D bonus:* A0 blocked days | 136 | 156 | ~ (path-dependent breaker timing) |

**Verdict on the rebuild:** every gated quantity reproduces well inside tolerance. I found
no engine bug.

The remaining differences come from three things:
- the data vendor: Aug-2015 prints move V3's worst-day date and 2015's per-year ΔSR;
- path-dependent breaker timing: D blocked days;
- my "days held >30%" counting the end-of-day drifted weight.

None changes any gate.

---

## Part 2: attacks (H unless stated; all at 5 bp unless stated)

### A1. Cost-assumption sensitivity
| Cost model | A0 Sharpe, H | V3 Sharpe, H | ΔSR, H (same cost) | ΔSR, D (same cost) |
|---|---|---|---|---|
| 0 bp (gross) | 0.265 | 0.428 | +0.163 | +0.021 |
| 5 bp | 0.092 | 0.386 | +0.295 | +0.133 |
| 3x at 15 bp, others 5, SHV 1 | 0.029 | 0.380 | +0.351 | +0.241 |
| 20 bp | −0.417 | 0.260 | +0.677 | +0.468 |
| 40 bp | −0.400 | 0.082 | +0.482 | +0.478 |

- V3's edge grows with cost at every level tested.
- Cost cannot flip the verdict, because V3 is also ahead gross (+0.16 H, +0.02 D).
- Above about 15–20 bp, A0's comparison stops being meaningful. A0's net equity crosses
  −30%, and the breaker then freezes it: 916 blocked sessions on H at 20 bp, with turnover
  falling to 35×. V3 itself starts tripping the breaker at 40 bp (88 days on H).
- Wider 3x spreads, which are plausible for 2011–13, help V3 further.

### A2. Month-end timing luck: decision-day shift k ∈ [−5, +5] sessions

ΔSR at each shift:

| k | −5 | −4 | −3 | −2 | −1 | **0** | +1 | +2 | +3 | +4 | +5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ΔSR, H | +.42 | +.15 | +.27 | +.28 | +.21 | **+.30** | +.21 | +.39 | +.26 | +.27 | +.33 |
| ΔSR, D | +.06 | +.08 | +.28 | +.29 | +.30 | **+.13** | +.05 | +.09 | +.18 | +.22 | +.16 |

Ranges across the 11 shifts:

| Metric | H | D |
|---|---|---|
| V3 Sharpe | 0.243–0.513 (k = 0 ranks 4th of 11) | 0.356–0.613 (k = 0 is below the median) |
| V3 MaxDD | −16.4% to −28.6% (k = 0 is the *worst*) | not tabulated |

- **The registered day was not lucky.** k = 0 is mid-pack on Sharpe and the worst of 11 on H
  MaxDD.
- ΔSR is positive at all 22 window × shift points.
- Every H gate passes at every shift:
  - worst day between −4.05% and −5.35%, against A0's −9.04%;
  - ES ratio between 0.58 and 0.68;
  - MaxDD better by 6 to 18 pts.
- Timing noise is still large: ±0.13 Sharpe from the day of the month alone. That is the
  same order as the effect being claimed on D.

### A3. Cap-level sensitivity (report only)
| Cap | Sharpe, H | ΔSR, H | MaxDD, H | ES1%, H | Worst, H | ΔSR, D |
|---|---|---|---|---|---|---|
| 25% | 0.343 | +0.251 | −27.1% | −2.95% | −4.79% | +0.131 |
| **30%** | 0.386 | +0.295 | −28.6% | −3.26% | −4.79% | +0.133 |
| 35% | 0.407 | +0.316 | −30.3% | −3.64% | −5.24% | +0.114 |

The trade-off is smooth and monotone. Nothing suggests 30% is a lucky knife-edge.

### A4. Subperiods
- **H halves:**

  | Half | A0 Sharpe | V3 Sharpe | ΔSR |
  |---|---|---|---|
  | 2011-04..2014 | 0.395 | 0.830 | +0.435 |
  | 2015..2018 | −0.162 | 0.044 | +0.206 |

- **Per-year ΔSR:**
  - H: positive in 7 of 8 years. 2015 is −0.19, the August 2015 crash.
  - **D: positive in only 3 of 7 years.**
    - 2020: −0.14
    - 2021: +0.14
    - 2022: +0.68
    - 2023: −0.44
    - 2024: −0.13
    - 2025: −0.25
    - 2026: +1.12
- **D's advantage is concentrated.** It comes mostly from 2022 (A0's breaker froze it from
  2022-06-14 to 2023-05-25) and 2026 YTD. In the "normal" years 2023–25, A0 beat V3.

### A5. 2020 and 2022 behaviour in D
- **2020: V3 loses.**

  | Metric | A0 | V3 |
  |---|---|---|
  | Year return | +13.5% | +10.0% |
  | In-year MaxDD | −13.5% | −19.2% |
  | Trough, 2020-02-19..04-30 | −10.8% | −18.1% |

  - The cause is the monthly lag. A0's daily regime went CHOPPY on 02-25, and A0 was out of
    3x by 02-27.
  - V3 kept its February base (about 28–30% 3x after the cap) until the 03-02 re-decision.
    It lost −4.2% on 02-27, then −2.7% on 03-12 and −3.9% on 03-18 on its RISK_OFF book.
  - This is the "late into crashes" failure the EXP-024 entry pre-named, and it happened.
  - The cap limited the damage. V1, with no cap, had about 36% 3x.
- **2022: V3 wins big.**

  | Metric | A0 | V3 |
  |---|---|---|
  | Year return | −28.2% | −13.6% |
  | In-year MaxDD | −34.1% | −21.9% |

  - Both books held almost no 3x: 6.4% for A0 and 5.2% for V3.
  - The gap is A0's churn costs, plus A0 crossing −30% and freezing near the bottom. In
    2023, A0's frozen book then recovered +35.6% against V3's +20.9%.
  - So D's ΔSR leans heavily on the breaker-freeze dynamics.

### A6. Does the gain come from just holding less 3x? (2×2: cadence × cap)
| Arm (5 bp) | Sharpe, H | ΔSR, H | ΔSR, D | ES ratio vs A0, H | Worst day, H | MaxDD, H |
|---|---|---|---|---|---|---|
| A0 (daily, no cap) | 0.092 | 0 | 0 | 1.00 | −9.04% | −34.7% |
| A0cap30 (daily + cap) | 0.085 | **−0.006** | **−0.034** | 0.62 | −5.23% | −28.0% |
| V1 (monthly, no cap) | 0.409 | **+0.317** | +0.078 | **1.08** | −8.47% | −34.2% |
| V3 (monthly + cap) | 0.386 | +0.295 | +0.133 | 0.65 | −4.79% | −28.6% |

Gross Sharpe at 0 bp, H:

| A0 | A0cap30 | V1 | V3 |
|---|---|---|---|
| 0.265 | 0.362 | 0.453 | 0.428 |

- **The Sharpe gain is the cadence, not the cap.**
  - Capping the daily book does nothing net. A0cap30 is ≈ 0 on H and −0.03 on D: the cost
    of 66×/yr turnover eats the gross benefit.
  - On H, the monthly book without a cap (V1) has a slightly *higher* Sharpe than V3.
- **The tail gain is the cap, not the cadence.**
  - V1 alone would *fail* G4 on H: its ES ratio is 1.08, against a bar of ≤ 0.90.
  - Daily + cap gets almost all of V3's tail cut: ES 0.62, worst day −5.23%.
- This matches V3's stated design: cadence aimed at churn, cap aimed at the tail. **So V3
  needs both parts, and neither part alone passes.**
- **Gross timing changes sign between windows.** V1 − A0 at 0 bp is +0.19 on H and −0.035 on
  D. So about half of H's +0.30 net ΔSR is window-specific gross timing.
- The *durable* piece is the cost saving: 2.8–3.0%/yr, worth about +0.11 to +0.13 Sharpe
  on both windows.

### A7. Live code-path differences
| Variant (H, 5 bp) | A0 Sharpe | V3 Sharpe | ΔSR | MaxDD A0 / V3 | A0 breaker days |
|---|---|---|---|---|---|
| Spec lookback (registered) | 0.092 | 0.386 | +0.295 | −34.7 / −28.6 | 61 |
| Lookback anchored on run date (what live does) | 0.136 | 0.383 | **+0.247** | −31.3 / −28.9 (**Δ only +2.3**) | 14 |
| Full 252 rows (no 342-day filter) | 0.147 | 0.393 | +0.246 | −31.0 / −26.2 | 7 |
| broker.py rules, $930 book: $1 minimum order, 99.5% sell cap, 2% buy cushion, $2 cash | 0.090 | 0.387 | +0.297 | −34.5 / −28.6 | 61 |
| Same broker.py rules, $100k book | 0.090 | 0.383 | +0.293 | −34.5 / −28.6 | 61 |
| Whole shares at nominal prices, $930 (stress; live is fractional) | −0.067 | 0.136 | +0.203 | −36.0 / −26.3 | 38 |
| Whole shares, $100k | 0.092 | 0.386 | +0.294 | −34.6 / −28.6 | 61 |

- **The lookback detail matters for A0, not for V3.**
  - A tiny window-anchoring change, the kind of thing the spec explicitly called a ≤3-day
    difference, moves A0's Sharpe by +0.05.
  - It also cuts A0's breaker days from 61 to 14 and shrinks G3's MaxDD advantage from
    +6.0 to +2.3 pts. G3 still passes, because its bar is −2.0.
  - So A0's H numbers are fragile through the breaker. V3's are stable within ±0.01 Sharpe.
- Live fractional execution changes nothing.
- Whole shares on a $930 book would cripple both arms through idle cash. Live does not use
  whole shares.

---

## Overall: SURVIVES

**What holds up under every attack:**
- the turnover cut (6.4×);
- about 3%/yr of cost saved;
- the ES cut (about 35%) and the worst-day cut (about −9% → −5%) from the cap;
- a positive ΔSR at every shift, cap level, lookback, execution model and cost level
  tested (0–40 bp).

**What is weaker than the RESULT reads:**
1. **The H ΔSR of +0.30 overstates the durable edge.** About +0.13 of it is cost, which is
   mechanical. The rest is gross timing, which reverses on D. The honest forward expectation
   is ΔSR ≈ +0.1. That cannot be resolved at σ ≈ 0.21. (R9's wording already says "not shown
   to beat"; this agrees.)
2. **D's advantage depends on the breaker.** It is concentrated in 2022–23, when A0 froze. In
   2023–25, A0 beat V3 every year.
3. **Fast crashes that start mid-month are V3's known weak spot.**
   - 2020: trough −18.1% vs A0's −10.8%.
   - H, August 2015: V3's worst H year relative to A0.
   - Monthly cadence holds the last base target for up to about 21 sessions after the
     daily regime has gone RISK_OFF.
4. **Neither component passes alone.** The cap is a tail tool with no net Sharpe value when
   used daily. Monthly cadence is a cost tool that leaves the tail at A0's level.

## What the forward shadow should watch
1. **Realised turnover and cost per $ traded vs ~11×/yr.**
   - The cost saving is the durable claim.
   - If shadow-implied turnover exceeds ~20×/yr, the claim is broken.
   - Measure actual bp per $ on the live champion's fills (C2 says 1–3 bp).
2. **Regime-lag exposure.** Count the sessions where the *daily* regime is RISK_OFF but V3
   still holds more than 10% in 3x, and record the P&L on those days. H had 25 such days
   and D had 6. Pre-register a kill threshold on this.
3. **Held 3x drift above the cap.** The max held was 32.7% on H. Flag any session above 35%.
4. **Live-vs-replica 3x gap** (the 2026-06-05 issue: 96% vs 26%).
   - The shadow must log live's *actual* 3x weight next to replica-A0 and V3 every session.
   - The cap's value is far larger if live really runs 60–96% 3x books.
   - If replica-A0 does not track live, the comparison certifies nothing.
5. **A0's drawdown-breaker state.** A large share of both H's and D's advantage passes through
   A0 freezing at −30%. Log E/ATH for both books daily.
6. **Lookback anchoring.** The shadow should use live's exact `fetch_prices` window (anchored
   on the run date), not the spec's i−1 anchoring. A0 is sensitive to it.
