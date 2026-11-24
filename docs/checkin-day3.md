# Day 3 check-in (draft – edit before sending)

1. Core is working end to end: ADK workflow (3 LLM agents + 7 code nodes, typed state) → A2UI v0.9 over AG-UI → React renderer; staff page; Phoenix tracing (1 trace per turn).
2. Pricing is a pure function over the workbook as-is; all 6 expected prices in the seed/sample quotes reproduce exactly; 48 unit tests pass. 19 data problems found (text numbers, USD hotel, overlapping Hotel Suisse rates, injected HTML comment, sample quote Q-1043 missing child beds …) are handled in code and listed for staff.
3. Eval suite (54 cases, code checks + LLM judge) runs with one command; first real problem found and fixed: an ungrounded answer to "Is Yala open in September?".
4. Blockers: Gemini Pro models are not available on my key and Flash models sometimes return 503/504, so I added a fallback model and keep latency in view (5–20 s per turn).
5. Next: human-label 10 cases for judge agreement, before/after numbers for the fix, docker compose verification, demo video.
