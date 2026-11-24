# Live demo script (30 min) and 5-minute video outline

Before you start: `docker compose up --build`, open http://localhost:8080, http://localhost:8080/staff
(sign in as Ayesha) and http://localhost:6006. Use a fresh browser profile, or click **Forget me**, so the
first visit is not "returning".

## 1. Architecture (3 min)
Use the diagram in README §2. Points to make:
- The ADK `Workflow` has 3 LLM nodes (understand, respond_small, respond_large) and 7 code nodes, over a typed `MiraState`.
- The LLM proposes, code decides. Slots are validated in `plan_turn`; prices come only from `Catalog.quote()`; the UI is validated against the A2UI catalog; publishing needs the Approver role in code.
- Prices reach the screen only as A2UI data bindings filled from the stored quote. The model never writes a number (the price guard strips any it does).

## 2. Quick booker, then planner (6 min)
**Quick booker:** "How much is the Sigiriya and Minneriya day tour from Kandy for 2 adults on 10 January 2027?"
→ USD 315, pay in full. Point at the quote reference, then show the same row on the staff page with cost USD 220 and GP 30.16%.

**Planner (S13):**
1. "We want to see the ancient cities, about a week." → a Cultural Triangle card and the traveller picker.
2. Use the picker: 2 adults, 3 May 2027 → USD 2,125, deposit USD 532, balance due 3 April.
3. "Actually there will be 4 adults, can you update the price?" → USD 3,640 / 910 (van, two doubles).

**Custom trip:** "10 days across Kandy, Ella and the south coast for a family of four" → the closest tours plus an enquiry to the team, and no price.

**Never guess:** "Solo, Treasures of Sri Lanka from 10 April 2027?" → specialist handoff. Show the flag reason on the staff page (Heritance Tea Factory has no single rate).

## 3. Their inputs (8 min)
Likely probes and what happens:
- **Discount / injection:** declined. `plan_turn`'s regex and the model both flag it, and there is no code path that changes a price.
- **Unknown facts** (visa, weather, Yala in September): "I don't have that in our tour details", plus an offer to ask the team.
- **Dates after Oct 2027, groups over 20, the Hotel Suisse overlap in Jan–Mar 2027:** flagged with a reason code.
- **Booking:** card ending `0002` → friendly decline with next steps; `0003` → booking system busy.

## 4. One trace (4 min)
Open "View trace" under a quote, then walk down the tree:
1. `mira.turn`: scrubbed input.
2. `understand` LLM call: prompt and structured JSON output.
3. `plan_turn`: route and model route.
4. `pricing.price_tour`: inputs, cost lines, price, GP%.
5. `retrieval.search`: query and chunks.
6. `respond_small` LLM call.
7. `ui.compose_and_validate`: components, valid, price guard.

## 5. Evaluation report and the fixed problem (4 min)
Open `evals/reports/latest.md` and show the targets table, then the per-requirement and per-route tables.
Then show the finding in `evals/findings/`. To show the before numbers live:
`MIRA_GROUNDING_FIX=0 uv run python ../evals/run_evals.py --requirement R4 --label "before fix"`.

## 6. Live change (5 min)
Change the day-tour margin:
- **Option 1:** staff page → Pricing rules (as Ayesha) → day-tour margin `0.35`.
- **Option 2:** edit `config/pricing_rules.json` → `"margin_day": 0.35` (the staff page save reloads the catalog; for a file edit restart the API or save from the staff page).

Then re-run the pricing evals:
```bash
cd backend && uv run pytest tests/test_pricing.py -q
```
```bash
cd backend && uv run python ../evals/run_evals.py --requirement R5 --no-judge
```
Expected: S02 now fails with 340 instead of 315 (220 / 0.65 = 338.46 → 340), which shows the evals catch a price change. Set it back to `null` and re-run to show green again.

## 5-minute video outline
| Time | What |
|---|---|
| 0:00–0:40 | Problem and architecture diagram |
| 0:40–1:40 | Quick booker quote, then the staff row with cost and GP |
| 1:40–2:50 | Planner with picker, party change, custom trip handoff |
| 2:50–3:30 | No-rate flag and injection refusal |
| 3:30–4:20 | Trace walk-through |
| 4:20–5:00 | Eval report and the Yala grounding fix before/after |
