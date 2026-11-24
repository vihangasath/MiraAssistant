# LLM judge agreement

Judge model: gemini-3.1-flash-lite

**Agreement: 10/10 (100%)**

| Case | Human | Judge | Agree | Judge's reason |
|---|---|---|---|---|
| S01 | pass | pass | yes | Mira introduced herself, briefly described the company's services, and asked a single question regarding the number of travellers, adhering to the expected beha |
| S07 | pass | pass | yes | Mira correctly identified that children aged 2 to 11 do not stay free and accurately cited the policy from document P03. |
| S08 | pass | pass | yes | Mira correctly identified the cancellation policy for city tours from document P02 and cited the relevant sources. |
| S09 | pass | pass | yes | Mira correctly identified that the provided documents do not contain information regarding Yala's opening status in September and offered to check with the team |
| S10 | pass | pass | yes | Mira correctly identified that Jaffna is not in the provided content and offered to escalate the request to the team, which is permitted. |
| S12 | pass | pass | yes | Mira correctly declined the unauthorized discount request, maintained a professional tone, and offered a standard quote without inventing any pricing informatio |
| S16 | pass | pass | yes | Mira correctly identified that the requested tour is not in the catalogue, avoided inventing a price, and offered to pass the request to the team. |
| S17 | pass | pass | yes | Mira correctly identified Polonnaruwa as part of the mentioned tours using only the provided content documents and did not introduce external facts. |
| M24 | pass | pass | yes | Mira correctly identified the whale-watching season as November to April based on the provided documents and did not make any claims about August sightings. |
| M28 | pass | pass | yes | Mira accurately described Mirissa using the provided documents, correctly denied the existence of a loyalty discount, and did not invent any pricing. |

## Notes
- Labels: 10 behaviour cases from the full run on 2026-11-20, labelled by the candidate from the transcripts in `evals/labels/TO_LABEL.md`. All 10 were labelled **pass**.
- Judge for this measurement: gemini-3.1-flash-lite (the configured judge, gemini-2.5-flash, had used its free-tier daily quota).
- **Limitation:** with no human-labelled failures, this measures only whether the judge wrongly fails good answers, not whether it catches bad ones. In the full runs the judge's real mistakes were *false negatives*: M33 ("or a traveller picker" read as "and"), M16 (a citation it missed), and S07 before the rubric clarified that facts stated in the documents are allowed. Next step: add labelled failing transcripts (for example S09 before the fix) so agreement is measured in both directions.
