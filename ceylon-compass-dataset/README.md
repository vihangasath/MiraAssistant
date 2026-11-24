# Ceylon Compass Holidays – starter dataset

Synthetic data for the take-home assignment, modelled on a real Sri Lankan tour operator's catalogue. The company, policies and every price are fictional; some hotel names are real, but their rates here are invented.

This data came out of a real-world-style handover from a sales team, so treat it the way you would treat real client data: read it carefully and don't assume it is clean or consistent.

## What's in here

| Path | What it is |
| --- | --- |
| `content/tours/` | 16 tour pages: day tours, city tours, round trips and stays (Markdown with YAML front matter) |
| `content/destinations/` | 10 destination pages |
| `content/policies/` | Booking and payment, cancellation, children, FAQ, about us, guest testimonials |
| `rates/rate_sheet_2026-27.xlsx` | The sales team's costing workbook. Start with the **READ ME** tab: it explains how a price is built. |
| `rates/sample_quotes.md` | Four quotes the sales team sent by email |
| `brand/brand_pack.json` | Colours, type, spacing and tone of voice for your UI |
| `evals/eval_seed.jsonl` | 15 starter test cases with expected outcomes. Extend these into your own suite. |

## Front matter fields

Every content file starts with front matter: `id`, `type`, `title`, `status` (`published` or `draft`) and `last_updated`. Tours also have `category`, `duration`, `start`, `destinations`, and sometimes `hotels` and `teaser_price`.

## Rules for using this data

- Prices shown to travellers must come from the rate workbook and the pricing rules on its READ ME tab.
- Make "today's date" configurable. **The expected outcomes in `eval_seed.jsonl` assume today is 19 November 2026.**
- Load the workbook as-is with code. Don't hand-edit it to make your loader work.
- You may add your own content and test cases, but keep ours unchanged so results are comparable.

## Eval seed format

Each line is one test case:

```json
{"id": "S02", "category": "pricing", "turns": ["user message 1", "user message 2"],
 "expected": {"type": "quote", "tour": "T01", "price_usd": 260, "deposit_usd": 260}}
```

`expected.type` is one of:

- `quote`: Mira shows this exact price and deposit (USD).
- `quote_sequence`: one expected quote per pricing turn, in order.
- `flag_no_price`: Mira must not show any price; it hands over to the team and raises a flag for staff.
- `behaviour`: judged against the `behaviour` description.
