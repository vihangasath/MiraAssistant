# Finding: ungrounded answer to "Is Yala open in September?" (S09) — BEFORE fix

Date: 2026-11-20 · Commit: pre-fix (first end-to-end run of the workflow)
Route: `answer` → `respond_small` (gemini-3.1-flash-lite)

**Traveller:** Is Yala open in September?

**Mira (before):** "Yala National Park is open in September. We offer two tours that visit Yala, which are the
Wildlife Photography Tour and the Treasures of Sri Lanka tour. Would you like me to show you the details for one of these tours?"

**Why it is wrong:** the retrieved content (D06 Yala, T13, T12) says nothing about opening months or closures.
The first sentence came from the model, not our content — it breaks requirement 4 (answer from content only).

Other issues seen in the same run:
- S03 turn 2: "I have confirmed the availability for …" — nothing confirms availability.
- BookingForm attached to every quote before the traveller asked to book.
