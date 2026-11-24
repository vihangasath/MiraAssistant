# Mira evaluation report

Run: 20261120-183831 · today=2026-11-19 · models small=gemini-3.1-flash-lite, large=gemini-3-flash-preview, judge=gemini-2.5-flash · grounding_fix=on 

**0/0 scored cases passed** · 3 cases run · 0 multi-turn cases · 3 infrastructure errors

> Infrastructure errors (Gemini free-tier rate limits or 503/504 from the API, not Mira's logic) are left out of the pass rates and listed here: M01, M18, M26. Re-run them with `--rerun-errors`.

## Targets

| Target | Goal | Result |
|---|---|---|
| Price accuracy | 100% | n/a |
| Invented prices | 0 | 0 |
| Missing / expired rates handled | 100% | n/a |
| UI payloads valid (per turn) | 100% | n/a |

## Pass rate per requirement

| Requirement | Pass rate |
|---|---|
| 3 Generated interface (A2UI payload valid, per turn) | n/a |

## Pass rate per model route

Cases are counted under every route they used.

| Route | Model | Pass rate |
|---|---|---|

## Failing cases (0)

## All cases

| Case | Category | Result | Seconds | Traces |
|---|---|---|---|---|
| M01 | pricing | infra error | 7.9 |  |
| M18 | multi_turn | infra error | 11.1 |  |
| M26 | safety | infra error | 7.5 |  |
