// Destination pictures: openly licensed photos (photos.ts), with these original flat illustrations as the
// fallback when a photo is missing or fails to load.
// Brand-pack colours only. Each scene is drawn on a 400×240 canvas and crops to fill its frame.
import { useId, useState, type ReactElement } from "react";
import { PHOTOS } from "./photos";

const C = {
  orange: "#F26B1D", teal: "#14837B", tealDark: "#0E5F59", sun: "#F5B700", leaf: "#4CA64C", leafDark: "#2F7A3A",
  sky: "#3A8DDE", coral: "#E5533D", ink: "#111111", cream: "#FFF8F0", sand: "#F3D9A8", rock: "#C0602F", rockDark: "#8E4220", white: "#FFFFFF",
};

function Sky({ id, top, bottom }: { id: string; top: string; bottom: string }) {
  return (
    <>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={top} /><stop offset="1" stopColor={bottom} /></linearGradient></defs>
      <rect width="400" height="240" fill={`url(#${id})`} />
    </>
  );
}

const palm = (x: number, y: number, s = 1, lean = 0) => (
  <g transform={`translate(${x} ${y}) scale(${s}) rotate(${lean})`}>
    <path d="M0 0 C 2 -30, 6 -55, 4 -80" stroke={C.rockDark} strokeWidth="5" fill="none" strokeLinecap="round" />
    <g fill={C.leafDark}>
      <path d="M4 -80 C -20 -92, -40 -84, -48 -70 C -30 -80, -14 -80, 4 -78z" />
      <path d="M4 -80 C 26 -94, 46 -86, 54 -72 C 36 -82, 20 -80, 4 -78z" />
      <path d="M4 -80 C -8 -104, -28 -108, -38 -100 C -20 -100, -8 -92, 4 -79z" />
      <path d="M4 -80 C 18 -104, 38 -106, 46 -96 C 30 -98, 16 -92, 4 -79z" />
    </g>
  </g>
);

const elephant = (x: number, y: number, s = 1, fill = "#5E5A57") => (
  <g transform={`translate(${x} ${y}) scale(${s})`} fill={fill}>
    <path d="M0 0 C 0 -26, 14 -38, 40 -38 C 60 -38, 72 -30, 76 -18 C 82 -24, 92 -24, 96 -14 C 100 -4, 98 10, 94 26 L 88 26 C 90 12, 90 2, 86 -4 L 84 6 L 84 26 L 74 26 L 72 8 L 30 8 L 28 26 L 18 26 L 16 8 C 6 6, 0 4, 0 0 Z" />
    <circle cx="88" cy="-14" r="1.8" fill={C.cream} />
  </g>
);

const SCENES: Record<string, (id: string) => ReactElement> = {
  sigiriya: (id) => (
    <>
      <Sky id={id} top="#FFD3B0" bottom="#FFF1DF" />
      <circle cx="318" cy="62" r="26" fill={C.sun} />
      <path d="M0 170 C 80 150, 160 160, 240 150 S 360 140, 400 150 V240 H0Z" fill="#7FBF7A" />
      <path d="M112 170 C 124 150, 128 112, 142 90 C 158 66, 206 58, 240 64 C 264 70, 276 96, 282 128 C 286 148, 296 162, 304 170 Z" fill={C.rock} />
      <path d="M146 86 C 162 66, 206 58, 240 64 C 252 67, 260 74, 266 84 C 230 74, 186 74, 146 86 Z" fill={C.leafDark} />
      <path d="M244 72 C 262 90, 268 130, 276 170 L 304 170 C 296 162, 286 148, 282 128 C 276 96, 264 70, 244 72 Z" fill={C.rockDark} opacity=".55" />
      <path d="M0 200 C 40 176, 70 186, 100 178 C 130 170, 150 186, 190 180 C 230 174, 260 188, 300 178 C 340 170, 370 184, 400 176 V240 H0Z" fill={C.leaf} />
      <path d="M0 222 C 60 206, 120 218, 200 210 S 330 204, 400 214 V240 H0Z" fill={C.leafDark} />
    </>
  ),
  mirissa: (id) => (
    <>
      <Sky id={id} top="#BFE0F7" bottom="#E9F5FD" />
      <circle cx="90" cy="58" r="22" fill={C.sun} />
      <rect y="120" width="400" height="80" fill={C.sky} />
      <path d="M0 132 H400" stroke={C.white} strokeOpacity=".45" strokeWidth="3" strokeDasharray="24 18" />
      <path d="M0 160 H400" stroke={C.white} strokeOpacity=".35" strokeWidth="3" strokeDasharray="14 26" />
      <g fill="#2B5F86">
        <path d="M226 142 C 222 126, 214 112, 202 106 C 212 106, 224 112, 230 124 C 236 112, 248 106, 258 106 C 246 112, 238 126, 234 142 Z" />
      </g>
      <path d="M210 146 C 222 140, 238 140, 250 146" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M0 194 C 100 178, 220 186, 400 176 V240 H0Z" fill={C.sand} />
      {palm(330, 214, 1.05, 10)}
      {palm(372, 222, .8, -6)}
    </>
  ),
  kandy: (id) => (
    <>
      <Sky id={id} top="#CFEDE6" bottom="#F4FBF8" />
      <path d="M0 120 C 70 80, 130 96, 190 84 C 250 72, 320 100, 400 82 V170 H0Z" fill="#7FBF7A" />
      <path d="M0 140 C 90 118, 160 132, 240 118 S 360 120, 400 112 V170 H0Z" fill={C.leaf} />
      <g>
        <rect x="150" y="118" width="100" height="34" fill={C.white} />
        <path d="M144 120 L 200 98 L 256 120 Z" fill={C.orange} />
        <rect x="186" y="96" width="28" height="18" fill={C.white} />
        <path d="M180 98 L 200 84 L 220 98 Z" fill={C.orange} />
        <g fill={C.tealDark}>{[160, 176, 192, 208, 224, 240].map((x) => <rect key={x} x={x - 3} y="128" width="6" height="12" rx="3" />)}</g>
      </g>
      <rect y="152" width="400" height="88" fill={C.teal} />
      <path d="M150 158 H250" stroke={C.white} strokeOpacity=".5" strokeWidth="3" />
      <path d="M170 168 H230" stroke={C.white} strokeOpacity=".35" strokeWidth="3" />
      <path d="M0 152 H400" stroke={C.white} strokeWidth="3" strokeDasharray="2 6" />
      <path d="M0 214 C 120 204, 280 214, 400 206 V240 H0Z" fill={C.tealDark} />
    </>
  ),
  "nuwara-eliya": (id) => (
    <>
      <Sky id={id} top="#E4F1EA" bottom="#F8FCF9" />
      <path d="M0 110 C 60 80, 120 90, 170 74 C 230 56, 300 84, 400 70 V240 H0Z" fill="#9BCB93" />
      <path d="M0 150 C 80 112, 170 126, 250 108 C 320 92, 370 110, 400 104 V240 H0Z" fill={C.leaf} />
      <g stroke={C.leafDark} strokeWidth="5" strokeLinecap="round" fill="none" opacity=".8">
        <path d="M10 170 C 90 140, 180 150, 260 130 S 380 124, 400 122" />
        <path d="M0 192 C 90 166, 190 176, 270 156 S 380 150, 400 148" />
        <path d="M0 214 C 100 192, 200 200, 280 182 S 380 176, 400 174" />
      </g>
      <g transform="translate(286 74)">
        <rect width="46" height="28" fill={C.white} />
        <path d="M-6 2 L 23 -16 L 52 2 Z" fill={C.coral} />
        <rect x="18" y="12" width="10" height="16" fill={C.tealDark} />
      </g>
      <circle cx="80" cy="52" r="18" fill={C.sun} opacity=".9" />
    </>
  ),
  ella: (id) => (
    <>
      <Sky id={id} top="#D7ECF8" bottom="#F5FAFD" />
      <path d="M0 80 C 60 50, 110 70, 160 56 C 220 40, 300 70, 400 50 V240 H0Z" fill="#7FBF7A" />
      <path d="M0 240 V120 C 50 100, 90 120, 120 140 L 120 240Z" fill={C.leafDark} />
      <path d="M400 240 V110 C 360 100, 320 116, 290 136 L 290 240Z" fill={C.leafDark} />
      <g fill="#E8D7BE">
        <rect x="100" y="118" width="210" height="16" />
        {[0, 1, 2, 3, 4].map((i) => (
          <path key={i} d={`M${104 + i * 42} 134 h40 v106 h-6 v-62 a14 14 0 0 0 -28 0 v62 h-6z`} />
        ))}
      </g>
      <g transform="translate(140 98)">
        <rect width="120" height="20" rx="5" fill={C.sky} />
        <rect y="8" width="120" height="3" fill={C.sun} />
        {[10, 34, 58, 82, 104].map((x) => <rect key={x} x={x} y="2" width="12" height="5" rx="1" fill={C.white} />)}
      </g>
      <path d="M0 240 C 100 216, 300 226, 400 214 V240Z" fill={C.leaf} />
    </>
  ),
  galle: (id) => (
    <>
      <Sky id={id} top="#FFDCC4" bottom="#FFF4EA" />
      <circle cx="96" cy="66" r="24" fill={C.sun} />
      <rect y="150" width="400" height="90" fill={C.sky} />
      <path d="M0 164 H400" stroke={C.white} strokeOpacity=".4" strokeWidth="3" strokeDasharray="20 22" />
      <path d="M150 150 L 400 150 L 400 120 L 170 120 Z" fill="#D9C7A7" />
      <path d="M150 150 L 400 150 L 400 158 L 146 158 Z" fill="#BFA983" />
      <g fill="#BFA983">{[180, 214, 248, 282, 316, 350, 384].map((x) => <rect key={x} x={x} y="112" width="18" height="10" />)}</g>
      <g transform="translate(250 30)">
        <path d="M6 90 L 12 14 L 30 14 L 36 90 Z" fill={C.white} />
        <rect x="8" y="2" width="26" height="14" rx="2" fill={C.sun} />
        <path d="M6 2 L 21 -12 L 36 2 Z" fill={C.coral} />
        <rect x="10" y="44" width="22" height="6" fill={C.coral} />
      </g>
      {palm(176, 120, .7, -8)}
    </>
  ),
  colombo: (id) => (
    <>
      <Sky id={id} top="#FFE3CC" bottom="#FFF6EE" />
      <g fill="#E4C9B4">
        <rect x="40" y="110" width="34" height="70" /><rect x="80" y="92" width="28" height="88" /><rect x="114" y="122" width="40" height="58" />
        <rect x="258" y="100" width="36" height="80" /><rect x="300" y="120" width="30" height="60" /><rect x="336" y="86" width="40" height="94" />
      </g>
      <g transform="translate(200 20)">
        <rect x="-3" y="40" width="6" height="120" fill={C.teal} />
        <path d="M0 4 C 14 18, 16 34, 0 46 C -16 34, -14 18, 0 4 Z" fill={C.coral} />
        <path d="M0 18 C 8 26, 8 36, 0 44 C -8 36, -8 26, 0 18 Z" fill={C.orange} />
        <path d="M-10 46 H10 L 6 54 H-6 Z" fill={C.tealDark} />
      </g>
      <rect y="180" width="400" height="60" fill={C.sky} />
      <path d="M0 192 H400" stroke={C.white} strokeOpacity=".4" strokeWidth="3" strokeDasharray="18 20" />
      <path d="M0 176 H400 V184 H0Z" fill="#9BCB93" />
    </>
  ),
  anuradhapura: (id) => (
    <>
      <Sky id={id} top="#FFE8BF" bottom="#FFF8EC" />
      <path d="M0 180 C 100 168, 300 172, 400 166 V240 H0Z" fill="#9BCB93" />
      <g>
        <rect x="120" y="170" width="160" height="12" fill="#EFE6D8" />
        <path d="M130 172 C 130 112, 162 80, 200 80 C 238 80, 270 112, 270 172 Z" fill={C.white} />
        <rect x="186" y="58" width="28" height="22" fill={C.white} />
        <path d="M192 58 L 200 16 L 208 58 Z" fill={C.white} />
        <path d="M196 30 L 200 10 L 204 30 Z" fill={C.sun} />
        <path d="M238 92 C 258 112, 270 140, 270 172 L 252 172 C 252 140, 246 112, 232 96 Z" fill="#E9E1D4" />
      </g>
      <g fill={C.leafDark}>
        <circle cx="54" cy="150" r="30" /><circle cx="82" cy="160" r="22" /><rect x="50" y="160" width="8" height="26" fill={C.rockDark} />
        <circle cx="344" cy="148" r="32" /><circle cx="318" cy="162" r="20" /><rect x="340" y="160" width="8" height="26" fill={C.rockDark} />
      </g>
      <path d="M0 214 C 120 204, 280 212, 400 204 V240 H0Z" fill={C.leaf} />
    </>
  ),
  minneriya: (id) => (
    <>
      <Sky id={id} top="#FFD9B8" bottom="#FFF3E4" />
      <circle cx="300" cy="70" r="24" fill={C.sun} />
      <path d="M0 140 C 80 126, 160 134, 240 124 S 360 122, 400 128 V170 H0Z" fill="#7FBF7A" />
      <rect y="166" width="400" height="74" fill={C.teal} opacity=".9" />
      <path d="M0 166 C 100 158, 300 160, 400 156 V170 H0Z" fill="#B5D98F" />
      {elephant(60, 150, .9)}
      {elephant(170, 154, .7, "#6E6966")}
      {elephant(250, 148, 1)}
      <path d="M60 190 H140 M210 200 H300" stroke={C.white} strokeOpacity=".4" strokeWidth="3" />
    </>
  ),
  yala: (id) => (
    <>
      <Sky id={id} top="#FFC79E" bottom="#FFEBD6" />
      <circle cx="120" cy="96" r="34" fill={C.sun} />
      <path d="M0 170 C 100 156, 300 162, 400 152 V240 H0Z" fill="#D9B46A" />
      <path d="M0 200 C 120 186, 280 196, 400 186 V240 H0Z" fill="#C49A4E" />
      <g transform="translate(300 170)">
        <rect x="-3" y="-60" width="6" height="60" fill={C.rockDark} />
        <path d="M-50 -60 C -30 -76, 30 -76, 50 -60 C 30 -66, -30 -66, -50 -60 Z" fill={C.leafDark} />
        <path d="M0 -40 L -20 -58 M0 -46 L 18 -60" stroke={C.rockDark} strokeWidth="3" />
      </g>
      <path d="M150 176 C 150 156, 180 146, 220 150 C 240 152, 252 160, 254 176 Z" fill="#8E7D6B" />
      <g transform="translate(166 136)" fill="#E3A23C">
        <path d="M0 14 C 4 4, 16 0, 34 2 C 44 3, 50 8, 52 14 L 48 22 L 44 14 L 12 16 L 8 22 L 2 20 Z" />
        <circle cx="52" cy="6" r="8" />
        <path d="M0 14 C -10 10, -14 2, -10 -4" stroke="#E3A23C" strokeWidth="3" fill="none" />
        <g fill={C.ink} opacity=".75"><circle cx="14" cy="8" r="1.6" /><circle cx="22" cy="12" r="1.6" /><circle cx="30" cy="7" r="1.6" /><circle cx="38" cy="11" r="1.6" /></g>
      </g>
    </>
  ),
};
SCENES.udawalawe = (id) => (
  <>
    <Sky id={id} top="#DCEFD9" bottom="#F6FBF4" />
    <path d="M0 130 C 90 110, 200 124, 280 112 S 380 110, 400 114 V240 H0Z" fill="#9BCB93" />
    <path d="M0 176 C 110 160, 290 170, 400 160 V240 H0Z" fill={C.leaf} />
    {elephant(120, 168, 1.2)}
    {elephant(250, 176, .6, "#6E6966")}
    <path d="M0 220 C 120 206, 280 216, 400 208 V240 H0Z" fill={C.leafDark} />
  </>
);
SCENES.polonnaruwa = (id) => (
  <>
    <Sky id={id} top="#FFE0C2" bottom="#FFF6EC" />
    <circle cx="320" cy="64" r="22" fill={C.sun} />
    <path d="M0 170 C 100 160, 300 164, 400 158 V240 H0Z" fill="#9BCB93" />
    <g>
      <rect x="96" y="160" width="208" height="16" fill="#C9B79C" />
      <rect x="116" y="146" width="168" height="16" fill="#D8C8AE" />
      <rect x="136" y="134" width="128" height="14" fill="#E6D8C2" />
      <g fill="#E6D8C2">{[146, 166, 186, 206, 226, 246].map((x, i) => <rect key={x} x={x} y={i % 2 ? 92 : 100} width="9" height={i % 2 ? 42 : 34} />)}</g>
      <path d="M176 134 C 176 112, 188 102, 200 102 C 212 102, 224 112, 224 134 Z" fill="#CDBB9F" />
      <path d="M96 176 L 304 176 L 296 182 L 104 182 Z" fill="#B29F82" />
    </g>
    <g fill={C.leafDark}>
      <circle cx="44" cy="146" r="28" /><rect x="40" y="156" width="8" height="26" fill={C.rockDark} />
      <circle cx="362" cy="150" r="24" /><rect x="358" y="158" width="8" height="24" fill={C.rockDark} />
    </g>
    <path d="M0 214 C 120 204, 280 212, 400 204 V240 H0Z" fill={C.leaf} />
  </>
);
SCENES.hikkaduwa = SCENES.mirissa;

const slug = (name: string) => name.trim().toLowerCase().replace(/\s+/g, "-");

export function hasDestinationArt(name?: string | null): boolean {
  return !!name && slug(name) in SCENES;
}

export function DestinationArt({ name, className }: { name: string; className?: string }) {
  const id = `sky${useId().replace(/:/g, "")}`;
  const scene = SCENES[slug(name)];
  if (!scene) return null;
  return (
    <svg className={className} viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" role="img" aria-label={`Illustration of ${name.replace(/-/g, " ")}`}>
      {scene(id)}
    </svg>
  );
}

export function hasDestinationPhoto(name?: string | null): boolean {
  return !!name && (slug(name) in PHOTOS || slug(name) in SCENES);
}

// Real photo when we have one, illustration otherwise (or if the photo fails to load).
export function DestinationPhoto({ name }: { name: string }) {
  const photo = PHOTOS[slug(name)];
  const [failed, setFailed] = useState(false);
  if (!photo || failed) return <DestinationArt name={name} />;
  return <img className="dest-photo" src={photo.src} alt={photo.alt} loading="lazy" decoding="async" onError={() => setFailed(true)} />;
}
