# Finding: Mira stated a fact that is not in our content (S09 "Is Yala open in September?")

## How it was found
On the first end-to-end run of the workflow (2026-11-20), the seed case S09 was answered:

> "Yala National Park is open in September. We offer two tours that visit Yala…"

None of the retrieved documents (D06 Yala, T13, T12) says anything about opening months or closures. The LLM judge
flagged it, and the trace shows the reason: `retrieval.search` returned the right chunks, but `respond_*` added a
sentence from general knowledge. This breaks requirement 4 (answer from content only). Raw note:
[2026-11-20-yala-hallucination-before.md](2026-11-20-yala-hallucination-before.md).

## Fix (`MIRA_GROUNDING_FIX=1`, now the default)
1. **Stricter grounding rule** in the responder prompt (`GROUNDING_RULE_V2` in `backend/mira/agents/prompts.py`):
   - every factual sentence must be stated in FACTS;
   - for opening months, closures, weather, visas, distances or availability, say "I don't have that in our tour details" and offer to ask the team;
   - Mira may still say which of our tours visit the place;
   - she must never say a booking or availability is confirmed, and never promise to arrange something not in FACTS.
2. **Model routing**: free-text factual answers go to the large route.

The flag keeps the old rule (`GROUNDING_RULE_V1`) so the before state can be reproduced:

```bash
cd backend && MIRA_GROUNDING_FIX=0 uv run python ../evals/run_evals.py --requirement R4 --report-name grounding-before-fix
```

```bash
cd backend && MIRA_GROUNDING_FIX=1 uv run python ../evals/run_evals.py --requirement R4 --report-name grounding-after-fix
```

## Before and after (same 15 grounding cases, same models)

Both runs used gemini-3.1-flash-lite for every role, because the free-tier daily caps on the other models were used up that day. So the difference comes from the prompt rule alone; the routing change had no effect here.

| | Grounding cases passed | S09 answer |
|---|---|---|
| Before (`MIRA_GROUNDING_FIX=0`) | **14/15** ([report](../reports/grounding-before-fix.md)) | "Yala National Park is open in September. It is a great place to see leopards, elephants, and sloth bears…" |
| After (`MIRA_GROUNDING_FIX=1`) | **15/15** ([report](../reports/grounding-after-fix.md)) | "I do not have information about park opening times in our tour details. I can ask our team for you. We have tours that visit Yala, such as the Wildlife Photography Tour and Treasures of Sri Lanka…" |

Traces:
- before: http://localhost:6006/redirects/traces/3c69ef908c25a4694d5ff4dd3f0586b9
- after: http://localhost:6006/redirects/traces/5ea1ea2e191afb244e9eaf93ba474b43

## Other problems the evals and traces surfaced (and fixes)
| Problem | Found by | Fix |
|---|---|---|
| "I have confirmed the availability…" in a quote reply | first run transcript | Rule 8: never claim availability or bookings are confirmed |
| Booking form attached to every quote | first run transcript | BookingForm only on a booking turn (code, `compose_ui`) |
| Mira offered to "arrange a custom trip to Jaffna" | judge on S10 | Rule: never promise to arrange what FACTS don't support; offer to pass to the team |
| "I want a day trip" answered in text with no tour cards | M33 `useful_by_turn` code check | `plan_turn` runs the tour ranker for trip-type and place answers; `compose_ui` attaches the top tour cards |
| A model's daily quota stalled turns for minutes (Gemini sent `retryDelay` = 84,000 s) | per-case timeout in the eval runner + log | Never wait on a per-day 429: mark the model exhausted and switch to the fallback; cap other waits at 20 s |
| Judge failed correct answers (S07 infants policy) | reading judge reasons | Judge rubric: statements supported by the documents are not violations unless the expectation forbids them |
