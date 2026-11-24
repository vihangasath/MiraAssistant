# Ceylon Compass Holidays: UI Design (v0.3)

Status: decisions confirmed by the user on 2026-11-20. Built; v0.3 (2026-11-20) records what changed during the build.

## 1. Decisions

| Topic | Decision |
|---|---|
| Colours | Brand pack only. No maroon. Flag inspiration comes from orange, teal and sun-yellow |
| Flag motif | Thin three-colour frame (orange, teal, sun) on the top, left and right of the chat panel; static, once per page |
| People art | Original flat SVG illustrations written in code with Claude Code (no image model); disclosed in README and `frontend/ATTRIBUTION.md` |
| People shown | Saree and Kandyan osariya, sarong and national dress, Tamil, Muslim and Burgher Sri Lankans, plus modern casual wear |
| Mira | Simple illustrated woman in a saree (plain, no decorative border), circular avatar with orange ring |
| Language | English only |
| Theme | Light and dark; cards stay white in both |
| Mock-up | None; go straight to code (submission is 25 Nov) |
| Style reference | Mindtrip's clean, bold, spacious feel; chatbot-first product. Layout language from layla.ai: pill controls, one rounded hero panel, centred composer card |
| Sign-in | A login page comes first: "Continue as traveller" or "Admin login" (demo staff accounts) |
| Voice | Mic button (speech to text) and speaker toggle (Mira reads replies) in the input; starting with the mic makes the conversation hands-free. Browser Web Speech API, English |
| Home tour grid | A browsable grid of published tours under the hero; each card starts a chat. Never shows prices |

## 2. Intent
A warm, trustworthy Sri Lankan travel site where the conversation with Mira is the product. Colour and people make it unmistakably Sri Lankan; layout stays clean so prices and policies are easy to read.

## 3. Colour

### 3.1 Flag link
Flag values (commonly cited, verify before quoting): maroon `#8D153A`, saffron `#EB7400`, green `#00534E`, yellow `#FFBE29`. We deliberately skip maroon. The brand pack's own colours map to the rest:

| Brand pack | Hex | Flag echo |
|---|---|---|
| orange (primary) | `#F26B1D` | saffron stripe |
| teal | `#14837B` | green stripe |
| sun | `#F5B700` | yellow border and lion |

Other brand-pack accents (leaf `#4CA64C`, sky `#3A8DDE`, coral `#E5533D`) remain available for cards.

### 3.2 Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FFF8F0` (new warm off-white) | `#141414` | Page background |
| `--surface` | `#FFFFFF` | `#FFFFFF` | Cards (white in both themes, per brand pack) |
| `--surface-chrome` | `#FFFFFF` | `#1F1F1F` | Header, chat background, non-card areas |
| `--text` | `#111111` | `#F5F5F5` | Body on page background |
| `--text-on-card` | `#111111` | `#111111` | Text inside white cards, both themes |
| `--muted` | `#5F5F5F` | `#A8A8A8` | Secondary text |
| `--border` | `#E6E6E6` | `#333333` | Dividers, inputs |
| `--primary` | `#F26B1D` | `#F26B1D` | Buttons, Mira ring, links on dark |
| `--teal` | `#14837B` | `#2BB3A9` (lightened) | Confirmations, itinerary |
| `--sun` | `#F5B700` | `#F5B700` | Badges, highlights |
| `--leaf` `--sky` `--coral` | brand pack | same | Extra card accents |

Dark-mode tokens other than brand-pack values are my derivation; flag as such in the README. Decision: cards stay white in dark mode, as the brand pack says. They sit on a dark page, so give them a 1px `--border` edge and keep all text inside them `--text-on-card`.

### 3.3 Rules
- One accent colour per card.
- Prices and deposits are always `--text` on `--surface`, never coloured text.
- Orange `#F26B1D` on white is about 3:1, so use it for buttons with dark text (`#111111`), large text and icons, not small body text. Verify every pair for WCAG AA (4.5:1 body, 3:1 large) in both themes.
- Errors: coral plus icon plus words.
- Theme follows `prefers-color-scheme`, with a manual toggle (moon/sun button in the header, saved per browser).
- Links and focus rings use teal one step darker (`#0F6E67`) in light mode so small text passes AA on `--bg`; in dark mode they use `#2BB3A9`.

## 4. People and graphics

### 4.1 Direction
Places (tour cards, home tour grid) use real, openly licensed photos from Wikimedia Commons, credited in the footer and `frontend/ATTRIBUTION.md`; the flat illustration of each place is the fallback if a photo fails to load (user decision, 2026-11-20). People and states use original illustrations in one consistent flat style. Figures are faceless, which keeps them free of caricature.

### 4.2 Who and what they wear
- Skin tones: realistic range of brown, light to deep; vary within a scene.
- Sinhala: women in saree and Kandyan osariya; men in sarong and national dress (sarong with long shirt).
- Tamil: women in saree, men in veshti or sarong with shirt.
- Muslim: women in saree or modest dress with hijab where fitting, men in sarong or kurta, some with cap.
- Burgher: everyday Western or modern dress, to show the community without costume.
- Modern casual wear mixed into every scene so traditional dress doesn't read as a costume.
- Travellers of any background appear alongside locals; locals are hosts, guides and families, not only service roles.
- Patterns (batik, handloom stripes, Kandyan borders) use the palette.
- Avoid: caricature, exaggerated features, "exotic" framing, sacred or religious symbols used as decoration, any real person's likeness.

### 4.3 Asset list

| Place | Asset |
|---|---|
| Home hero | Family of four with a guide, landmark behind, palette-coloured sky |
| Mira avatar | Woman in a saree, circular crop, orange ring |
| Traveller picker | Solo, couple, family, group (4 small illustrations) |
| States | Enquiry sent, no rates ("specialist will confirm"), payment failed (tuk-tuk or tea cup), empty staff list |
| Tour cards | Photo header per destination (12 places), illustration as fallback |

### 4.4 Production plan (as built)
- SVG written in code (`frontend/src/art/people.tsx`, `frontend/src/destinations.tsx`) with one shared figure builder and the fixed palette, so the set is consistent and needs no network or image files.
- Alt text on meaningful images (hero, destinations); decorative art is `aria-hidden`.
- Each image reviewed by eye for skin tones, dress accuracy and stereotypes, in both themes.
- Tool and date per asset in `frontend/ATTRIBUTION.md`, and disclosed in the README.
- Empty staff list: plain text, because staff pages have no illustrations (§6).

## 5. Typography, spacing, shape
- Inter, then Helvetica/Arial (from the brand pack, applied at runtime). Sizes 12/14/16/20/28/36 px; weights 400/600/700.
- Spacing 4/8/12/16/24/32/48 px.
- Radius: card 12, button 999, input 8.
- Cards max 320 px wide; small, colourful.
- Motion: no scroll-triggered or parallax; transitions under 200 ms.
- English only; keep strings in one file so a language could be added later.

## 6. Layout: chatbot first

Reference: Mindtrip (screenshot `research/screenshots/04-mindtrip-home.png`). Borrow the feel only: a large, bold headline, generous white space, one clear call to action, and results shown as cards beside or under the chat. I only saw its landing page (its chat is behind login), so the chat layout below is my design, not a copy.

Principles
- The chat is the product. Every journey (quote, enquiry, itinerary, booking) happens in the conversation; there are no separate search, filter or booking pages.
- Mira's generated components appear inline in the message stream: traveller picker, tour card, itinerary day, price breakdown, booking form. Users can also answer by typing instead of using a component.
- Home = large headline, Mira's greeting, one big input, three quick-start chips (Day tour, Multi-day tour, Custom trip), no illustration (kept clean on purpose), flag frame around the chat panel, then the tour grid (no prices). No menu of other pages for travellers.
- Desktop (1100 px and wider): chat column in the centre-left; a sticky side panel shows the current trip (tour, dates, travellers, price, reference) and updates as the chat goes. Narrower: single column; the trip summary becomes a collapsible bar above the input that shows the price when collapsed.
- Returning visitors see their last quote as the first message.
- Every Mira message with facts shows its source; unknown answers offer an enquiry button.
- Failures (payment, rates missing) appear as a friendly Mira message with a next step, never an error page.
- Price breakdown shows price and deposit only, never costs or margins.
- Staff pages (enquiries, approvals) are separate, plain, same tokens, no illustrations.

## 7. Component catalog

| Component | Accent | Notes |
|---|---|---|
| Traveller picker | orange | Four illustrated tiles, counts for adults and children |
| Tour card | one per card | Illustrated header, duration, "from" price only if a rate exists, source link |
| Itinerary day | teal | Day number, place, activities, source |
| Price breakdown | sun | Line items, total, deposit; "specialist will confirm" state when rates are missing, expired or conflicting |
| Booking form | orange | Name, email, phone, dates; friendly failure state with a next step |

## 8. Accessibility and tone
- WCAG AA in both themes, visible focus rings, 44 px touch targets, alt text, respects reduced motion.
- Tone: short sentences, plain English, no exclamation marks in prices or policies; "we" for the company, "I" for Mira.

## 9. Open questions
None at the moment.
