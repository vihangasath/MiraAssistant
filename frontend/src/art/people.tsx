// Original flat illustrations of Sri Lankan people and travellers (UI-DESIGN.md §4).
// Drawn in code (SVG), one shared style: faceless flat figures, brand-pack colours, a range of skin tones.
// Dress: saree, Kandyan osariya, sarong with shirt, national dress, veshti, hijab with modest dress,
// kurta with cap, and modern casual wear. See frontend/ATTRIBUTION.md.
import type { ReactElement } from "react";

const P = {
  orange: "#F26B1D", teal: "#14837B", sun: "#F5B700", leaf: "#4CA64C", sky: "#3A8DDE", coral: "#E5533D",
  white: "#F7F3EA", denim: "#3D5A80", khaki: "#C9A66B", ink: "#1E1410", shoe: "#3A2A22",
};
// Light to deep brown, varied within each scene.
export const SKIN = ["#E0B48A", "#C68B5E", "#A86F48", "#8A5A3B", "#6B4428"] as const;

type Dress = "saree" | "osariya" | "sarong" | "national" | "veshti" | "hijab" | "kurta" | "casual" | "casualDress";
interface FigureProps {
  x: number; y: number; s?: number;
  skin: string; dress: Dress; main: string; accent: string;
  hair?: "bun" | "short" | "long" | "none"; pack?: string;
}

// One figure, feet at (x, y), about 100 units tall before scaling.
export function Figure({ x, y, s = 1, skin, dress, main, accent, hair = "short", pack }: FigureProps): ReactElement {
  const longLower = dress !== "casual" && dress !== "kurta";
  const lower = dress === "national" ? P.white : dress === "veshti" ? P.white : dress === "kurta" ? P.white : main;
  const upper = dress === "national" ? P.white : dress === "sarong" || dress === "veshti" ? accent : main;
  const topLen = dress === "national" ? -36 : dress === "kurta" ? -28 : -45;
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      {pack && <rect x="2" y="-76" width="16" height="26" rx="5" fill={pack} />}
      {/* legs / lower garment */}
      {longLower ? (
        <path d="M-11 -46 L-13 0 H13 L11 -46 Z" fill={lower} />
      ) : (
        <g fill={dress === "kurta" ? P.white : accent}>
          <rect x="-10" y="-46" width="9" height="46" rx="2" />
          <rect x="1" y="-46" width="9" height="46" rx="2" />
        </g>
      )}
      {dress === "sarong" && <g stroke={main === P.white ? P.teal : P.white} strokeOpacity=".6" strokeWidth="1.5"><path d="M-12 -34 H12 M-12.5 -22 H12.5 M-13 -10 H13" /></g>}
      {dress === "veshti" && <rect x="-13" y="-6" width="26" height="3" fill={P.sun} />}
      {(dress === "saree" || dress === "osariya") && <rect x="-13" y="-5" width="26" height="3.5" fill={accent} />}
      <ellipse cx="-5" cy="0" rx="4.5" ry="2" fill={P.shoe} /><ellipse cx="5" cy="0" rx="4.5" ry="2" fill={P.shoe} />
      {/* arms */}
      <path d="M-11 -73 L-14.5 -47" stroke={skin} strokeWidth="4.5" strokeLinecap="round" />
      <path d="M11 -73 L14.5 -47" stroke={skin} strokeWidth="4.5" strokeLinecap="round" />
      {/* upper garment */}
      <path d={`M-11.5 -77 Q0 -80 11.5 -77 L12.5 ${topLen} H-12.5 Z`} fill={upper} />
      {(dress === "national" || dress === "kurta" || dress === "sarong" || dress === "veshti" || dress === "casual") && (
        <g stroke={upper} strokeWidth="5" strokeLinecap="round"><path d="M-11 -74 L-13 -63" /><path d="M11 -74 L13 -63" /></g>
      )}
      {dress === "hijab" && <g stroke={main} strokeWidth="5" strokeLinecap="round"><path d="M-11 -74 L-14 -50" /><path d="M11 -74 L14 -50" /></g>}
      {(dress === "saree" || dress === "osariya") && <path d="M-11.5 -77 L-4 -78.5 L12.5 -50 L12.5 -44 Z" fill={accent} />}
      {dress === "osariya" && <path d="M-12.5 -48 Q-6 -41 0 -48 Q6 -41 12.5 -48 L12.5 -44 H-12.5 Z" fill={accent} />}
      {/* head */}
      <rect x="-2.5" y="-83" width="5" height="6" fill={skin} />
      {dress === "hijab" ? (
        <>
          <path d="M-12 -76 C-14 -96 14 -96 12 -76 Z" fill={accent} />
          <circle cx="0" cy="-88" r="7" fill={skin} />
          <path d="M-9.5 -88 C-9.5 -101 9.5 -101 9.5 -88 C7 -94 -7 -94 -9.5 -88 Z" fill={accent} />
        </>
      ) : (
        <>
          {hair === "long" && <rect x="-9" y="-92" width="18" height="18" rx="6" fill={P.ink} />}
          {hair === "bun" && <circle cx="7" cy="-95" r="4.5" fill={P.ink} />}
          <circle cx="0" cy="-88.5" r="8.5" fill={skin} />
          {hair !== "none" && <path d="M-9 -88 C-9.5 -100 9.5 -100 9 -88 C6 -94 -6 -94 -9 -88 Z" fill={P.ink} />}
          {dress === "kurta" && <rect x="-7.5" y="-99" width="15" height="6" rx="3" fill={P.white} />}
        </>
      )}
    </g>
  );
}

// Traveller picker tiles: solo, couple, family, group.
const tile = (children: ReactElement) => (<svg viewBox="0 0 60 46" aria-hidden="true">{children}</svg>);
export const TravellerArt: Record<"solo" | "couple" | "family" | "group", () => ReactElement> = {
  solo: () => tile(<Figure x={30} y={45} s={0.43} skin={SKIN[3]} dress="saree" main={P.orange} accent={P.sun} hair="bun" />),
  couple: () => tile(<>
    <Figure x={20} y={45} s={0.43} skin={SKIN[1]} dress="national" main={P.white} accent={P.white} />
    <Figure x={40} y={45} s={0.41} skin={SKIN[0]} dress="casualDress" main={P.sky} accent={P.sky} hair="long" />
  </>),
  family: () => tile(<>
    <Figure x={14} y={45} s={0.43} skin={SKIN[2]} dress="kurta" main={P.teal} accent={P.teal} />
    <Figure x={46} y={45} s={0.41} skin={SKIN[2]} dress="hijab" main={P.coral} accent={P.sun} />
    <Figure x={30} y={45} s={0.27} skin={SKIN[2]} dress="casual" main={P.orange} accent={P.denim} />
  </>),
  group: () => tile(<>
    <Figure x={9} y={45} s={0.38} skin={SKIN[4]} dress="veshti" main={P.white} accent={P.leaf} />
    <Figure x={23} y={45} s={0.37} skin={SKIN[3]} dress="osariya" main={P.coral} accent={P.sun} hair="bun" />
    <Figure x={37} y={45} s={0.38} skin={SKIN[0]} dress="casual" main={P.sun} accent={P.denim} />
    <Figure x={51} y={45} s={0.38} skin={SKIN[1]} dress="sarong" main={P.teal} accent={P.orange} />
  </>),
};

// State illustrations (UI-DESIGN.md §4.3): no rates, payment failed, enquiry sent.
export const StateArt = {
  teaCup: () => (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path d="M26 10c-3 4 3 6 0 10M34 8c-3 4 3 6 0 10" stroke={P.teal} strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M12 26h34v6c0 11-7 18-17 18S12 43 12 32z" fill={P.orange} />
      <path d="M46 30c8 0 8 12-1 12" stroke={P.orange} strokeWidth="4" fill="none" />
      <rect x="12" y="29" width="34" height="3.5" fill={P.sun} />
      <ellipse cx="29" cy="54" rx="22" ry="4" fill={P.teal} />
    </svg>
  ),
  tukTuk: () => (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path d="M8 38c1-12 9-18 22-18h18c5 0 8 4 8 9v15H6v-6z" fill={P.teal} />
      <path d="M12 23h42" stroke={P.sun} strokeWidth="4" strokeLinecap="round" />
      <path d="M14 30h16v10H10z" fill="#DDF0EE" />
      <circle cx="42" cy="34" r="4" fill={SKIN[2]} />
      <circle cx="16" cy="46" r="6" fill="#2A2A2A" /><circle cx="48" cy="46" r="6" fill="#2A2A2A" />
      <path d="M54 12l4 6M58 10l-4 8" stroke={P.coral} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  ),
  envelope: () => (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <rect x="8" y="18" width="48" height="32" rx="4" fill={P.sun} />
      <path d="M8 22l24 16 24-16" stroke="#FFFFFF" strokeWidth="3" fill="none" strokeLinejoin="round" />
      <circle cx="50" cy="16" r="9" fill={P.teal} />
      <path d="M45.5 16l3 3 6-6" stroke="#FFFFFF" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};
