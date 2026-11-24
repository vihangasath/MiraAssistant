// Apply brand_pack.json (served by the API) to CSS variables, so the pack is the source of truth.
export async function applyBrandPack(): Promise<void> {
  try {
    const res = await fetch("/api/brand");
    if (!res.ok) return;
    const b = await res.json();
    const root = document.documentElement.style;
    const set = (k: string, v: unknown) => typeof v === "string" || typeof v === "number" ? root.setProperty(k, String(v)) : undefined;
    set("--orange", b.colors?.orange);
    for (const [k, v] of Object.entries(b.colors?.accents ?? {})) set(`--${k}`, v);
    set("--black", b.colors?.black);
    set("--white", b.colors?.white);
    set("--surface", b.colors?.surface);
    set("--text-on-card", b.colors?.text);
    set("--muted-on-card", b.colors?.muted_text);
    set("--font", b.typography?.font_family);
    for (const [k, v] of Object.entries(b.typography?.scale_px ?? {})) set(`--fs-${k}`, `${v}px`);
    if (b.radius_px) {
      set("--r-card", `${b.radius_px.card}px`);
      set("--r-button", `${b.radius_px.button}px`);
      set("--r-input", `${b.radius_px.input}px`);
    }
    if (b.cards?.max_width_px) set("--card-max", `${b.cards.max_width_px}px`);
  } catch {
    /* CSS defaults already match the brand pack */
  }
}

export function storage() {
  return {
    get(key: string): string | null {
      try { return localStorage.getItem(key); } catch { return null; }
    },
    set(key: string, value: string) {
      try { localStorage.setItem(key, value); } catch { /* private mode */ }
    },
    remove(key: string) {
      try { localStorage.removeItem(key); } catch { /* ignore */ }
    },
  };
}
