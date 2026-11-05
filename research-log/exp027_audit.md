### AUDIT — EXP-027 (research-integrity officer, 2026-10-13 23:06 PDT)

**Verdict: APPROVED WITH REQUIRED CHANGES.** R1–R10 below bind before any byte of
`prices_H.parquet` is parsed. The designer writes them into the entry with this audit's
reasons. The auditor did not design EXP-027. The auditor did not open, load, parse or md5
`prices_H.parquet`; `ls -la` shows 290,950 B, mtime 2026-10-13 22:50, which matches the
registration. Nothing was run.

Read: the EXP-027 entry (L4047–4258), `exp027_audit_request.md` (21 challenges), the EXP-024
pre-registration and RESULT (L3210–3526), `exp024/engine.py` (md5 c957b0a9…692f, verified),
`exp024/run_D.py`, `exp024_spec.md` §1–3, `audit_2026-10-13.md`. Worktree
`agent-a755d2182dda758ab` is at HEAD d6a6f812 with a clean `git status`.

#### Headline: is this an honest new test or a rescue?
On balance it is an honest new test, with **one D-shaped loosening that has to be reversed.**
Compare EXP-027 gate by gate with the H stage EXP-024 registered *before D existed* for this
same variant on this same window:

| EXP-024 H stage, V3 (blind to D) | EXP-027 | Direction |
|---|---|---|
| G1 TO ≤ 0.50× | G1 identical | same |
| — | G2 cost saved ≥ 1%/yr | **stricter** (added) |
| G3 MaxDD no worse by > 2 pts | G3 identical | same |
| G4 ES ≤ 1.10× and G6 ES ≤ 0.90× + worst day strictly better | G4 = G6 | same (1.10× is subsumed) |
| **G2 point ΔSR_net ≥ −0.03** (4.5% RF) | **G5 point ΔSR_net ≥ −0.10** (both RFs) | **looser by 0.07 Sharpe** |
| D-stage non-inferiority (Holm) | dropped | looser (justified, see F2) |

So the "all D values pass comfortably" red flag narrows to one gate. G1, G3 and G4 were set
blind to D. G2 is a materiality floor under the pre-D expectation (EXP-024 wrote "≈2–4%/yr" at
70–90×). G5 is the only gate that is both new and looser than the pre-D bar. Its stated
justification, "−0.10 is EXP-024's margin, kept for continuity", **is factually wrong.**
−0.10 was EXP-024's *bootstrap non-inferiority margin*, a bound on the lower tail of Δ*. EXP-024's
point-estimate guard was −0.03, and −0.03 is the statistic that EXP-027's G5 actually uses.
Moving a number from one statistic to a looser one, after the stricter gate killed the variant,
is the "amend a condition once the partial result is known" pattern (CLAUDE.md, EXP-014). A new
experiment number does not change that.

#### Findings (numbered to the audit request)

**1. V3 selection (Q1).** Acceptable. The cap was part of EXP-024's hypothesis *before* D:
"A hard cap on total 3x-ETF weight additionally shrinks the tail." C2 and the desk named both
problems before D. A mechanism-only rule that addresses both named problems picks V3, not V1.
V1 addresses only churn. Choosing a variant on D does not contaminate H, because H is
independent data. It only biases the *expectation* (winner's curse), and the entry states
that. One residual: the cap's motivating event (2026-06-05) is not reproduced by the engine
(26% vs 96% 3x). So on H the cap has to earn G4 on other days. That is what F4 is for.

**2. K (Q2).** K = 1 (family 15) is adequate. The 3 D looks are already inside the 14. A
re-test of an already-counted config on new data is not a new trial in the DSR sense, so
counting +1 is mildly conservative. The bp levels are not trials, because the gate is fixed
at 5 bp. The two RF conventions are not trials, because they enter as a conjunction (see
#12). Dropping the D non-inferiority gate is justified by the *nuisance* parameter σ ≈ 0.2,
not by V3's effect size. Under σ ≈ 0.2 that gate could not have passed a true Δ of +0.15
either. That is a property of the instrument, not of the result. No change.

**3. Spending H (Q3).** Acceptable. H is the only pre-2019 window with real 3x prices. A
synthetic-3x proxy is weaker evidence (EXP-022 B). A forward shadow cannot resolve Sharpe
either, and PASS here buys only that shadow. Spending H on one variant (K = 1) instead of
three is the cheaper use. The entry correctly declares H spent for the whole family.

**4. G2 at 1%/yr (Q4).** Accepted as a materiality floor: 1%/yr ≈ 0.055 Sharpe at 18% vol.
It sits well below the pre-D expectation, so it was not reverse-engineered from D's 2.87%.
State it as an absolute number, not as a fraction of A0's turnover: G1 already supplies the
relative test. Note for the RESULT: G1 and G2 are close to mechanically certain given monthly
cadence, so passing them confirms that the mechanism ran, not that V3 adds value.

**5. G1 vs G2 (Q5).** They are not redundant. G1 is relative and G2 is absolute. G2 binds only
if A0's H turnover is below about 24×/yr. Keep both.

**6. G4 worst-day strictness (Q6).** Do **not** score G4 on cap-binding days only. That
conditions the gate on where the mechanism happened to act, and it loosens the gate after D.
The strict inequality does have a real loophole, though. If both arms hold the same book on
their worst day (D shows that this happens: A0, V1 and V2 all returned exactly −6.33%), V3 can
be "strictly better" purely because A0 paid that day's trade cost. At 5 bp with Σ|ΔW| ≤ 2,
the cost difference can be up to 10 bp. → **R4.**

**7. G3 (Q7).** Keep it as a no-worse bound. A no-worse bound cannot be "carried" by a breaker
advantage. It only stops V3 failing. Its breaker confound is handled by reporting (R6).

**8. G5 harm guard (Q8).** See the headline. The −0.10 point guard is a post-D loosening of
the pre-D −0.03 guard, and the continuity claim is wrong. Moving it to −0.15/−0.18 (Q8) would
loosen it further, with the result already known in direction, so that is rejected. A gross
guard was considered. It isolates the uncertain timing component, but adding it now would be
another post-D gate design. Restoring the pre-registered bar is the clean option. Error rates
at −0.03 with σ_H = 0.214, normal approximation:

| true Δ | +0.11 | 0.00 | −0.10 | −0.30 | −0.45 |
|---|---|---|---|---|---|
| P(pass) at −0.03 (required) | 0.74 | 0.56 | 0.37 | 0.10 | 0.02 |
| P(pass) at −0.10 (as registered) | 0.84 | 0.68 | 0.50 | 0.18 | 0.05 |

The cost is a 44% false-kill rate if V3 and A0 are truly equal. That is the price of the bar
having been set before D, and it is stated openly. A clean FAIL that redirects is worth more
than a pass on a bar that was moved. → **R1.**

**9. No PARTIAL (Q9).** Agreed. The G5-only-failure wording already reports the resolution.

**10. σ_H scaling (Q10).** The direction is correct: SD ∝ 1/√N, so σ_H = 0.229 × √(1702/1950).
D's SD is probably inflated by A0's 136-day freeze (the arms decouple completely during it), so
σ_H may be optimistic or pessimistic. With R1, σ sets no threshold and only labels the error
rates, so no change is needed. Step 2's breaker-off SD on D should be ledgered beside it.

**11. Normal approximation (Q11).** Adequate as a *description*. It gates nothing.

**12. RF (Q12).** The direction claim checks out. ∂ΔSR/∂rf = 1/σ_A0 − 1/σ_V3 < 0 when
σ_V3 < σ_A0. With D's vols, 4.5% vs ≈0.6% moves ΔSR by about −0.03 against V3. The
conjunction is at least as strict as either convention alone, so it cannot be estimator
shopping. Keep it, but SHV-RF Sharpe is new code with a free formula choice. → **R3.**

**13. Warm-up ATH (Q13). The entry's disclosure is factually wrong.** The warm-up is not
"mostly SHV-flat". By `exp024_spec.md` §1, TECL (2008-12) and UPRO (2009-06) exist in the
warm-up, along with QQQ, VGT, IWM, VEA, GLD and TLT. The engine's column rule admits TECL about
20 rows after 2009-01-02. So the book trades a 3x-tech champion through Feb–Mar 2009, the 2009
rally, May 2010 and summer 2010. The breaker can fire *inside the warm-up*, and the ATH entering
2011-04-01 is path-set and differs by arm. This is live-faithful for an account opened
2009-01-02, and its direction is unknown before H, so keep the registered design for continuity
with D. But correct the text, and report the state. → **R5.**

**14. Breaker-off mechanism (Q14). Confirmed.** `engine.risk_gate` reads
`config.DRAWDOWN_CIRCUIT_BREAKER` at call time. With 1.0, `E/ath − 1 < −1` cannot be true for
E > 0. The vol (0.90), concentration (0.70), correlation (0.85) and 2% drift checks are
untouched. `risk.py` and `backtest.py` bind the constant at import, but the engine calls
neither of them for the breaker (it calls only `backtest._detect_regime_from_prices`). The
real risk is leakage: a runtime override that persists into a later breaker-on run in the
same process. → **R7.**

**15. Breaker-driven G3 (Q15).** See #7. The first-line flip rule should cover every gate, not
only the MaxDD sign. → **R6.**

**16. 06-05 gap (Q16).** It does not need explaining before H. H compares engine-A0 with
engine-V3, and F0 (87/100/104.7×) certifies that engine against live on 54 rows. The gap
blocks *replacement*, which the entry already requires. The RESULT has to say "engine replica
of the champion", not "the champion". → R9.

**17. F4 (Q17).** The thresholds are low but non-trivial: ≥ 5% ≈ ≥ 97 sessions with the cap
binding. Raising them now would itself be a post-D choice. The definition is under-specified,
though. "V3 decision-days" could mean monthly re-decision days (~93) or daily target days, and
`simulate` never records the pre-cap 3x target. That ambiguity is a lever the tester could
resolve after seeing outputs. → **R2.**

**18. Universe (Q18).** Both arms see the same reduced universe, so the comparison is fair.
External validity for the 2026 book (AVUV/BITO) is a caveat, not a validity failure. MTUM
enters around 2014-04, after ~235 rows, for both arms. No change.

**19. Cost (Q19).** Confirmed conservative against V3 at every gate. Understated cost raises
A0's net Sharpe more (A0 has 5–6× the turnover). It also shrinks G2's measured saving. Its
only other effect is on A0's breaker timing, which can go either way and is reported.

**20. Process leakage (Q20).** F2 shows prices only, which the designer already knows the
history of. Step 2 runs on spent D. Neither can show H strategy output. Step 2 can still move a
threshold indirectly if the H scoring code is written *after* step 2. → **R8** freezes the code
first.

**21. Contamination (Q21).** "Unseen for this book's outputs" is fair, and the regime-history
knowledge is disclosed. One consequence belongs in the RESULT: G4 passing is close to
predictable from known 2011/2015/2018 crash days plus a mechanical cap. G4 PASS confirms that
the mechanism ran on real prices. It is not a discovery.

**Additional finding A (not in the request): the decision cache is keyed by integer row
position.** `Decider` caches by `("reg", i)`, `("sel", i, regime)` and `("opt", i, …)`, and it
loads any existing pickle at `cache_path`. If `run_H.py` pointed at `decisions_D.pkl`, or at a
stale H cache, it would silently replay D's decisions onto H's dates. → **R7.**

**Additional finding B: the engine's library code lives in a mutable worktree.** F1 seals
`engine.py` but not the library code it imports from
`.claude/worktrees/agent-a755d2182dda758ab/`, and that worktree could be edited or cleaned up
before H runs. md5s at audit time: config.py `b5fca78139e601eac901f5f0200d5ea8`, optimizer.py
`43ea923f5827a330bfafaac1c17f43b4`, backtest.py `2832306c0724e27a866249e29f13b47b`,
risk_overlay.py `c8b57f813aa196d2896dea071b02ad9d`; HEAD d6a6f812, status clean. → **R8.**

**Additional finding C: the re-run clause is self-judged.** "Except an engine bug unrelated to
which arm wins" lets whoever has seen H decide what counts as unrelated. → **R10.**

#### Required changes (binding before H is parsed)

- **R1 (G5):** The point guard becomes **ΔSR_net(V3 − A0, 5 bp) ≥ −0.03 under both RF
  conventions**. This restores EXP-024's pre-D H-stage bar for this variant and window. Strike
  "−0.10 is EXP-024's margin, kept for continuity". Replace the error-rate table with the −0.03
  row above. The bootstrap p at margin 0.10 and the 90% CI stay reported only.
- **R2 (F4 definition):** In `run_H.py`, for every metrics-window session where V3 has a base
  target, compute `L_pre = Σ_LEV T_pre`, where `T_pre` comes from
  `engine.final_target(B, ret_win, cap=False)` on V3's base B for that day. Save it to the H
  daily output. The cap binds iff `L_pre > 0.30 + 1e-9`. F4 clause 2 = (binding sessions ÷
  metrics-window sessions with a V3 target) ≥ 0.05. Clause 1 = mean over metrics-window
  sessions of A0's `w3x` at 5 bp ≥ 0.05. If F4 fails, the verdict is INCONCLUSIVE, the kill
  rule applies exactly as for FAIL (H spent, re-entry on new data only), and every gate value
  is still computed and ledgered.
- **R3 (SHV-RF formula):** `SR_shv = (mean(net_t) − mean(r_SHV,t)) / std(net_t, ddof=1) × √252`
  over the metrics window, where `r_SHV,t` is SHV's adjClose close-to-close return on the same
  dates from `prices_H`. This mirrors the engine's constant-RF formula exactly. Any NaN in
  `r_SHV` inside the window ⇒ INVALID.
- **R4 (G4 worst day):** "Strictly better" means **worst_V3 − worst_A0 > 0.0010** (10 bp, net,
  5 bp run). That is the largest single-day cost difference possible at 5 bp, so a difference
  that small can be pure cost. ES clause unchanged.
- **R5 (warm-up disclosure):** Replace "The ATH is mostly SHV-flat during that stretch" with:
  "TECL and UPRO trade in the warm-up; the breaker can fire before 2011-04-01; ATH at window
  start is path-dependent per arm." The RESULT reports, for each arm and cost level: blocked
  days in the warm-up, E/ATH − 1 at 2011-04-01, and whether the breaker was active that day.
  The design is unchanged.
- **R6 (flip rule):** The RESULT's first line states any gate (G3, G4 or G5) whose pass/fail
  status differs between the breaker-on primary and the A0_nb/V3_nb pair. The pair stays
  ungated.
- **R7 (run hygiene):** `run_H.py` uses a new cache path (`decisions_H.pkl`) and asserts it
  does not exist before the run, with exclusive create on save. It asserts
  `px.index.max() <= 2018-12-31`. It runs the A0_nb/V3_nb pair in a separate process, or last
  with an assert, and asserts `config.DRAWDOWN_CIRCUIT_BREAKER == 0.30` at the start of every
  breaker-on sim.
- **R8 (code freeze):** Before F1, ledger the md5s of `run_H.py`, `score_027.py` and the four
  worktree library files above. F1 checks all of them and fails INVALID on any mismatch.
  Execution step 2 (D-only extras) must use the *frozen* `score_027.py` functions. As a dry run,
  `score_027.py` applied to the existing `daily_A0_D_5.parquet` and `daily_V3_D_5.parquet` must
  reproduce `results_D.json` (Sharpe, TO, MaxDD, ES1%, worst day) to 1e-9. If it does not,
  fix the code *before* H, re-freeze, and ledger the diff.
- **R9 (run by, and wording):** H is run and scored by a tester who did not design EXP-027, as
  in EXP-024. A PASS reads: "engine-replica V3 cuts turnover/cost and the cap shrinks the tail on
  2011–18, with no harm detected at σ ≈ 0.21. V3 is **not** shown to beat the champion
  risk-adjusted."
- **R10 (re-run):** A re-run is allowed only if the bug is first reproduced on D or on a
  synthetic fixture, before any H output is re-read. Both H results are ledgered, the original
  verdict is stated in the first line, and the auditor signs off before the re-run is scored.

Expected effect of R1–R10 on the designer's PASS prior: down. G5 goes from ~75% to about
60%, so PASS falls to roughly 20–25%. That is the intended direction. None of R1–R10 makes V3
easier to pass.
