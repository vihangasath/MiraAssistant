// Slow, minimal animated vector scene for the login page: two travellers walking, a tuk-tuk passing,
// a distant train, birds. Transparent background so the hero colour shows through. Decorative only.
// Motion is CSS (theme.css "login scene") and stops under prefers-reduced-motion.

const SKIN_A = "#8A5A3B";
const SKIN_B = "#C68B5E";

function Walker({ shirt, pack, skin, hat }: { shirt: string; pack: string; skin: string; hat?: string }) {
  return (
    <g>
      <g className="ls-leg ls-leg--a"><path d="M0 0 V26" stroke="#3F3F3F" strokeWidth="5" strokeLinecap="round" /></g>
      <g className="ls-leg ls-leg--b"><path d="M0 0 V26" stroke="#2A2A2A" strokeWidth="5" strokeLinecap="round" /></g>
      <g className="ls-bob">
        <rect x="-10" y="-34" width="12" height="24" rx="5" fill={pack} />
        <rect x="-6" y="-38" width="14" height="40" rx="7" fill={shirt} />
        <g className="ls-arm"><path d="M2 -30 V-12" stroke={skin} strokeWidth="4" strokeLinecap="round" /></g>
        <circle cx="2" cy="-48" r="8" fill={skin} />
        {hat && <path d="M-9 -51 H13 M-5 -51 C -5 -60, 9 -60, 9 -51" stroke={hat} strokeWidth="3.5" strokeLinecap="round" fill={hat} />}
      </g>
    </g>
  );
}

export function LoginScene() {
  return (
    <svg className="login-scene" viewBox="0 0 1200 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
      {/* far landscape */}
      <path d="M0 150 C 140 128, 260 140, 380 130 C 470 122, 520 132, 600 128 C 720 120, 860 138, 1000 126 C 1080 120, 1150 128, 1200 124 V220 H0Z" fill="#F6C9AC" opacity=".45" />
      <path d="M760 132 C 762 112, 768 100, 780 94 C 794 88, 818 88, 826 96 C 834 104, 836 118, 840 132 Z" fill="#E7A983" opacity=".7" />
      {/* distant train on the hills */}
      <g transform="translate(0 116)"><g className="ls-train">
        <rect x="0" y="0" width="34" height="11" rx="3" fill="#3A8DDE" opacity=".55" />
        <rect x="37" y="0" width="34" height="11" rx="3" fill="#3A8DDE" opacity=".55" />
        <rect x="74" y="0" width="34" height="11" rx="3" fill="#3A8DDE" opacity=".55" />
      </g></g>
      {/* sun and birds */}
      <circle className="ls-sun" cx="1010" cy="58" r="22" fill="#F5B700" opacity=".8" />
      <g transform="translate(0 70)"><g className="ls-birds" fill="none" stroke="#5F5F5F" strokeWidth="2" strokeLinecap="round" opacity=".6">
        <path d="M0 0 q6 -6 12 0 q6 -6 12 0" />
        <path d="M34 12 q5 -5 10 0 q5 -5 10 0" />
      </g></g>
      {/* palms */}
      <g transform="translate(150 186)">
        <path d="M0 0 C 2 -40, 8 -70, 4 -100" stroke="#8E4220" strokeWidth="5" fill="none" strokeLinecap="round" />
        <g className="ls-fronds" fill="#2F7A3A">
          <path d="M4 -100 C -22 -112, -44 -104, -52 -88 C -32 -98, -14 -98, 4 -98z" />
          <path d="M4 -100 C 28 -114, 50 -106, 58 -90 C 38 -100, 22 -98, 4 -98z" />
          <path d="M4 -100 C -8 -124, -30 -128, -40 -118 C -22 -120, -8 -112, 4 -99z" />
          <path d="M4 -100 C 18 -124, 40 -126, 48 -116 C 32 -118, 16 -112, 4 -99z" />
        </g>
      </g>
      {/* road */}
      <path d="M0 196 H1200" stroke="#E7B996" strokeWidth="2" />
      <path d="M0 206 H1200" stroke="#E7B996" strokeWidth="2" strokeDasharray="18 22" opacity=".7" />
      {/* tuk-tuk, right to left */}
      <g transform="translate(0 198)"><g className="ls-tuk">
        <g className="ls-tuk-body">
          <path d="M8 -30 C 10 -46, 22 -52, 40 -52 H66 C 74 -52, 78 -46, 78 -38 V-10 H4 V-22 Z" fill="#14837B" />
          <path d="M14 -48 H76" stroke="#F5B700" strokeWidth="5" strokeLinecap="round" />
          <path d="M18 -40 H44 V-22 H12 Z" fill="#DDF0EE" />
          <circle cx="54" cy="-34" r="5" fill="#C68B5E" />
        </g>
        <g className="ls-wheel" transform="translate(16 -6)"><circle r="8" fill="#2A2A2A" /><path d="M-5 0 H5" stroke="#9A9A9A" strokeWidth="2" /></g>
        <g className="ls-wheel" transform="translate(68 -6)"><circle r="8" fill="#2A2A2A" /><path d="M-5 0 H5" stroke="#9A9A9A" strokeWidth="2" /></g>
      </g></g>
      {/* two travellers, left to right */}
      <g className="ls-walkers">
        <g transform="translate(0 170)"><Walker shirt="#F26B1D" pack="#14837B" skin={SKIN_A} /></g>
        <g transform="translate(40 172)"><Walker shirt="#3A8DDE" pack="#F5B700" skin={SKIN_B} hat="#F5B700" /></g>
      </g>
    </svg>
  );
}
