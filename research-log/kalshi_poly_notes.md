# Kalshi ↔ Polymarket matcher: state and what has already been seen

Updated 2026-09-13. Any future cross-venue experiment (EXP-017 or later) must
disclose everything in this file, because it was looked at before registration.

## Matcher v9 (research/kalshi_poly_match.py), frozen

Text only. Prices and outcomes never choose a match. Rules: deadline read from
the question text (Polymarket's end-date field is unreliable), identical numbers,
direction, negation, action group and qualifiers (emergency, special, de facto…),
no unmatched rare name, no pair naming different places/people or rare specifics.
Two Kalshi series are excluded wholesale because their RULES differ from
Polymarket's same-titled markets for every member (see RULES_MISMATCH_SERIES).

Build history:
- v1: ~13 of 21 random pairs correct. Rare names swamped the verb.
- v2: 30 of 30 random pairs correct (action, negation, text deadlines).
- v3–v5: plurals, "no" as negation, year-only deadlines, threshold 0.40,
  two-sided rare specifics (MacBook cellular vs touchscreen).
- v6: two-sided different names (New York vs Texas). Noticed via a price gap;
  bias check: removed exactly that pair.
- v7: BUG FIX. "December 31, 2026" — the comma hid the year, so the deadline fell
  back to Polymarket's date field and matched a 2026 deadline to a 2028 one
  ([removed: person's name]). Removed 1 pair, added 5 correct ones.
- v8: RULES review. Series exclusions + qualifier rule. Removed 11; 5 of the 10
  with price data had gaps under 5c, so the exclusion did not select on
  disagreement.
- v9: "de facto" qualifier. Removed 1 (official vs de facto Venezuela leader).
  Possible recall loss in v8: an SC Senate special-primary pair ("special" on one
  side only), no price data.

## Rules review (research/kalshi_poly_rulings.csv)

Both venues' published resolution rules were fetched and compared.

    flagged by price gap (v6)     12   different 6, same with minor differences 6
    random, not flagged, price-   12   different 0, same 4, same-minor 8
      blind

Large gaps concentrate in genuinely different questions. The rulings on
flagged pairs were made with the gap visible; the random ones were not.

The [removed: person's name] "29c disagreement" was a deadline mismatch (Kalshi 2028 vs
Polymarket 2026), not a mispricing. On the matching 2027/2026 deadline the venues
agree. Remaining rules differences on that pair: Kalshi's death clause settles at
last fair price; Polymarket has no equivalent. Both count the announcement
regardless of the retirement's effective date.

## What v9 produces

    accepted one-to-one pairs            204   Elections 114, Politics 73,
                                               Sci/Tech 14, Companies 3
    tight quotes on both, same time      170
    price correlation                  0.977
    median per-pair gap                 1.0c
    pairs with median gap > 10c            0
    pairs ever >= 5c apart, tight          19
    flagged (median gap >= 5c)             6   all ruled same-question, minor
                                               rules differences
    resolved on BOTH venues                2   (2 of 2 same outcome)

## Conclusion so far

On questions that are actually the same, Kalshi and Polymarket agree to about a
penny. The biggest remaining gaps are 5–6c and sit on pairs with small rules
differences (> vs >= 60, a Gulf-time deadline, preliminary vs certified results)
that can plausibly explain them. Every gap over 10c turned out to be a different
question. Cross-venue mispricing looks arbitraged away.

## Limits

- Titles do not capture rules. A full rules review of all 204 pairs, blind to
  prices, is required before any registered study uses this set.
- Coverage is politics and long-dated. An outcome-based test has 2 resolved pairs.
- Acting on a gap needs orders on both venues; predmarket is read-only.
- Any outcome-based experiment needs its own holdout starting after its own
  registration, because EXP-016 scoring will expose September-onward outcomes.
