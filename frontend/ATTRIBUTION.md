# Visual assets: where they come from

Destination pictures are openly licensed photos from Wikimedia Commons (listed below and in the site footer).
All other artwork is original SVG written as code in this repository. No stock images, third-party
illustrations or image models are used.

## Photos (Wikimedia Commons)
Listed with author, licence and source page in `src/photos.ts` and under "Photo credits" in the site footer.
Licences are CC BY-SA 3.0/4.0 or CC0; CC BY-SA requires the attribution shown in the footer. The images are
loaded from Wikimedia's thumbnail CDN at 960 px. If one fails to load (for example offline), the original
illustration for that place is shown instead.

## Original SVG

| Asset | File | Made with | Date |
|---|---|---|---|
| Mira avatar (woman in a saree, circular, orange ring added in CSS) | `public/mira-avatar.svg` | Hand-written SVG, Claude Code under my direction | 2026-11-20 |
| People figures: saree, Kandyan osariya, sarong with shirt, national dress, veshti, hijab with modest dress, kurta with cap, modern casual | `src/art/people.tsx` (`Figure`) | Hand-written SVG, Claude Code | 2026-11-20 |
| Traveller picker tiles (solo, couple, family, group) | `src/art/people.tsx` (`TravellerArt`) | Hand-written SVG, Claude Code | 2026-11-20 |
| State art: tea cup (specialist will confirm), tuk-tuk (payment failed), envelope (enquiry sent) | `src/art/people.tsx` (`StateArt`) | Hand-written SVG, Claude Code | 2026-11-20 |
| Destination illustrations, fallback when a photo fails (Sigiriya, Mirissa, Kandy, Nuwara Eliya, Ella, Galle, Colombo, Anuradhapura, Minneriya, Yala, Udawalawe, Polonnaruwa) | `src/destinations.tsx` | Hand-written SVG, Claude Code | 2026-11-20 |
| Category icons (fallback tour-card art) | `src/a2ui/icons.tsx` | Hand-written SVG, Claude Code | 2026-11-20 |
| Login scene (travellers, tuk-tuk, train) | `src/staff/LoginScene.tsx` | Hand-written SVG, Claude Code | 2026-11-20 |

## Style rules followed (UI-DESIGN.md §4)
- One flat style and the brand-pack palette only (orange, teal, sun, leaf, sky, coral).
- Skin tones from a range of light to deep brown (`SKIN` in `people.tsx`), varied within each scene.
- Faceless figures: no drawn features, so there is no caricature or exaggeration.
- Traditional dress is always mixed with modern casual wear; the guide is a local host, not a service role.
- No religious or sacred symbols used as decoration (the forehead dot was removed from the Mira avatar).
- Each image was reviewed by eye in light and dark themes on 2026-11-20.

