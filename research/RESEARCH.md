# Existing solutions: AI travel booking assistant (Ceylon Compass "Mira")

Researched 2026-11-20. Vendor claims are marketing, not independent evaluation. Screenshots in `screenshots/`.

| # | Solution | Type | Screenshot | What it does | Gap vs. the brief |
|---|----------|------|-----------|--------------|-------------------|
| 1 | TourConnect Itinerary Assist AI | B2B quoting copilot for DMCs | 01 | Reads agent quote emails, drafts priced itineraries from operator inventory; chat keeps itinerary context | Staff-facing, not a traveller chat; no evidence of an approval/evals story |
| 2 | Layla (layla.ai) | Consumer planner + human advisor | 02, 03 | Chat prompt box -> itinerary with "from" prices; a human advisor checks and books. **Chat requires sign-in (Google/Apple/email) after the first prompt**, so I did not go further | Generic marketplace; no own-rates pricing function, no enquiry/staff page visible |
| 3 | Mindtrip | Consumer planner | 04 | "Personal travel assistant" that learns preferences (Stays/Flights/Eats/Experiences) | Login-gated; personalisation resembles the brief's bonus, but no operator rate control |
| 4 | Wonderchat tour-operator template | No-code RAG chatbot | 05 (template URL redirected to homepage) | Qualifies leads, group details, 40+ languages | Text-only FAQ/lead capture; no generated UI, no deterministic pricing |
| 5 | Hyperleap / BotPenguin / Hellotars / Denser | Chatbot vendors | 09 | Ask 2-3 qualifying questions, pass enquiry on | Same as above; claims (e.g. 40-60% cost cut) unverified |
| 6 | CopilotKit a2a-travel (MIT) | Open-source reference | 06 | Orchestrator + LangGraph itinerary/restaurant agents + Google ADK weather/budget agents, Next.js + AG-UI | Budget agent *estimates* costs with an LLM: exactly what the brief forbids; no tracing/evals/approvals |
| 7 | Google A2UI | Generative-UI standard | 07 | Agents stream declarative JSON UI; renderers for React/Angular/Lit/Flutter etc.; ADK restaurant-finder sample | A protocol, not a product: you must add the catalog validation, pricing, RAG and enquiry flow |
| 8 | Booking.com AI Trip Planner, Expedia Romie | Big OTA assistants | none (not captured) | Chat-guided search into normal checkout; Romie for group trips | Inventory is OTA's own; not applicable to a single operator |

## Takeaways for Mira
- **The market splits in two**: staff quoting copilots (TourConnect) and customer chatbots for FAQ/lead capture. Few do traveller chat + provably correct price + staff enquiry + human-approved content together. That combination is the brief's differentiator.
- **Closest code to build from**: CopilotKit a2a-travel (ADK + AG-UI structure) and Google A2UI's ADK sample. Your stack choice (ADK + A2UI) matches. Treat both as references; the brief says to mark any code you did not write.
- **Anti-pattern to avoid**: LLM-estimated budgets (a2a-travel). Keep prices in a code function.
- **Login walls** (Layla, Mindtrip): Mira's quick-booker path should price without sign-in.
- Flow pattern worth copying: ask 2-3 qualifying questions -> show options -> hand custom requests to a human advisor (Layla's "real advisor books every trip" mirrors Mira's enquiry handoff).

## Limits of this research
- Chats for Layla, Mindtrip, Booking.com and Romie are login-gated; I did not sign in or create accounts, so the "whole process" is only captured for Layla's first prompt and sign-in wall (02 -> 03). Screenshots 04, 05, 06, 07, 09 are landing/repo pages, not live conversations.
- Run the open-source repos locally (a2a-travel, A2UI restaurant sample) if you want true end-to-end UI screenshots; say the word and I'll do it.
