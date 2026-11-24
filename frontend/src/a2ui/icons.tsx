// Simple line icons and placeholder art (original SVG; no third-party assets).
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const Icon = {
  pin: () => (<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...base}><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>),
  clock: () => (<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...base}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>),
  info: () => (<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" {...base}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>),
  alert: () => (<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" {...base}><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17v.5" /></svg>),
  check: () => (<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" {...base}><path d="M5 12l5 5 9-10" /></svg>),
  doc: () => (<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" {...base}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /></svg>),
};

// Header art per tour category, used when a tour has no destination illustration.
export function CategoryArt({ category }: { category?: string | null }) {
  const c = (category ?? "").toLowerCase();
  if (c.includes("beach")) return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><circle cx="46" cy="18" r="7" /><path d="M4 44c8-4 16 4 24 0s16-4 24 0 8 2 8 2" /><path d="M20 44V22m0 0c-6 0-10 4-12 8m12-8c6 0 10 4 12 8m-12-8c0-5 4-9 9-10" /></svg>);
  if (c.includes("special")) return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><rect x="10" y="20" width="44" height="30" rx="4" /><circle cx="32" cy="35" r="9" /><path d="M24 20l4-6h8l4 6" /></svg>);
  if (c.includes("city")) return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><path d="M8 54V30h12v24M24 54V18h16v36M44 54V26h12v28" /><path d="M4 54h56" /></svg>);
  if (c.includes("stay")) return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><path d="M8 30 32 12l24 18" /><path d="M14 26v26h36V26" /><path d="M28 52V38h8v14" /></svg>);
  if (c.includes("day")) return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><path d="M6 52h52" /><path d="M14 52c0-10 4-16 10-20 2-6 8-10 14-8 6 2 8 8 8 14 4 4 6 9 6 14" /><circle cx="48" cy="14" r="5" /></svg>);
  return (<svg viewBox="0 0 64 64" aria-hidden="true" {...base}><path d="M6 50 22 26l10 14 8-10 18 20z" /><circle cx="46" cy="16" r="5" /></svg>);
}
