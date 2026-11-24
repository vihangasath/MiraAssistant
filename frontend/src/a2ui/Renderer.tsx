// Renders one A2UI surface with Mira's component catalog.
import { useState, type ReactNode } from "react";
import type { UiAction } from "../agui";
import { CategoryArt, Icon } from "./icons";
import { StateArt, TravellerArt } from "../art/people";
import { DestinationPhoto, hasDestinationPhoto } from "../destinations";
import { resolve, type ComponentNode, type Surface } from "./surface";

export interface RenderCtx {
  surface: Surface;
  onAction: (action: UiAction) => void;
  visitorId: string;
  disabled: boolean;
}

const usd = (n: unknown) =>
  typeof n === "number" ? `USD ${n.toLocaleString("en-US")}` : "—";
const niceDate = (iso?: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "";

export function SurfaceView(ctx: RenderCtx) {
  const root = ctx.surface.components.get("root");
  if (!root) return null;
  const kids: ComponentNode[] = (root.children as string[])
    .map((id) => ctx.surface.components.get(id))
    .filter(Boolean) as ComponentNode[];
  // Group consecutive cards so they flow side by side; itinerary days stack.
  const blocks: ReactNode[] = [];
  let cardRun: ComponentNode[] = [];
  let dayRun: ComponentNode[] = [];
  const flush = () => {
    if (cardRun.length) blocks.push(<div className="cards" key={`cards-${cardRun[0].id}`}>{cardRun.map((c) => <Node key={c.id} node={c} ctx={ctx} />)}</div>);
    if (dayRun.length) blocks.push(<ol className="itinerary" aria-label="Itinerary" key={`days-${dayRun[0].id}`} style={{ listStyle: "none", padding: 0, margin: 0 }}>{dayRun.map((c) => <li key={c.id}><Node node={c} ctx={ctx} /></li>)}</ol>);
    cardRun = [];
    dayRun = [];
  };
  for (const c of kids) {
    if (c.component === "TourCard") { if (dayRun.length) flush(); cardRun.push(c); continue; }
    if (c.component === "ItineraryDay") { if (cardRun.length) flush(); dayRun.push(c); continue; }
    flush();
    blocks.push(<Node key={c.id} node={c} ctx={ctx} />);
  }
  flush();
  return <div className="surface">{blocks}</div>;
}

function Node({ node, ctx }: { node: ComponentNode; ctx: RenderCtx }) {
  switch (node.component) {
    case "Text":
      return null; // the reply text is shown as the chat bubble
    case "TourCard":
      return <TourCard n={node} ctx={ctx} />;
    case "ItineraryDay":
      return <ItineraryDay n={node} />;
    case "PriceBreakdown":
      return <PriceBreakdown n={node} ctx={ctx} />;
    case "TravellerPicker":
      return <TravellerPicker n={node} ctx={ctx} />;
    case "SpecialistHandoff":
      return <Handoff n={node} />;
    case "BookingForm":
      return <BookingForm n={node} ctx={ctx} />;
    case "EnquiryForm":
      return <EnquiryForm n={node} ctx={ctx} />;
    case "SourceList":
      return <Sources n={node} />;
    case "QuickReplies":
      return (
        <div className="quick-replies" role="group" aria-label="Suggested replies">
          {(node.options as string[]).map((o) => (
            <button key={o} className="chip" disabled={ctx.disabled} onClick={() => ctx.onAction({ name: "send_text", context: { text: o } })}>{o}</button>
          ))}
        </div>
      );
    case "Notice":
      return <Notice tone={node.tone} title={node.title} message={node.message} />;
    default:
      return null;
  }
}

function actionLabel(a: UiAction): string {
  return { get_quote: "Get a price", show_itinerary: "See itinerary", send_enquiry: "Ask a specialist", start_booking: "Book now" }[a.name] ?? a.name;
}

function TourCard({ n, ctx }: { n: ComponentNode; ctx: RenderCtx }) {
  return (
    <article className={`card accent-${n.accent}`} aria-label={n.title}>
      <div className={`card__art${hasDestinationPhoto((n.destinations as string[])?.[0]) ? " card__art--scene" : ""}`}>
        {hasDestinationPhoto((n.destinations as string[])?.[0]) ? <DestinationPhoto name={(n.destinations as string[])[0]} /> : <CategoryArt category={n.category} />}
      </div>
      <h3>{n.title}</h3>
      <div className="meta">
        {n.category && <span className="badge">{n.category}</span>}
        {n.duration && <span className="badge"><Icon.clock /> {n.duration}</span>}
      </div>
      <p className="muted"><Icon.pin /> {(n.destinations as string[]).map((d) => d.replace(/-/g, " ")).join(" · ")}</p>
      <p>{n.summary}</p>
      {!n.bookable_online && <p className="muted">A specialist prices this tour for you.</p>}
      <div className="actions">
        {(n.actions as UiAction[]).map((a, i) => (
          <button key={a.name} className={`btn ${i === 0 ? "btn--primary" : "btn--ghost"}`} disabled={ctx.disabled} onClick={() => ctx.onAction(a)}>{actionLabel(a)}</button>
        ))}
      </div>
      <span className="source"><Icon.doc /> Source: {n.source.title}</span>
    </article>
  );
}

function ItineraryDay({ n }: { n: ComponentNode }) {
  return (
    <div className="day">
      <span className="day__num" aria-label={`Day ${n.day}`}>{n.day}</span>
      <div>
        <h4>{n.title}</h4>
        <p>{n.description}</p>
        {n.meals && <p className="muted" style={{ color: "var(--muted-on-card)" }}>Meals: {n.meals}</p>}
        {n.accommodation && <p className="muted" style={{ color: "var(--muted-on-card)" }}>Stay: {n.accommodation}</p>}
      </div>
    </div>
  );
}

function PriceBreakdown({ n, ctx }: { n: ComponentNode; ctx: RenderCtx }) {
  const price = resolve(ctx.surface, n.price_usd);
  const deposit = resolve(ctx.surface, n.deposit_usd);
  const balance = resolve(ctx.surface, n.balance_usd);
  return (
    <section className="card card--wide accent-sun" aria-label={`Price for ${n.tour_title}`}>
      <h3>{n.tour_title}</h3>
      <p className="muted">{niceDate(n.start_date)}{n.end_date !== n.start_date ? ` – ${niceDate(n.end_date)}` : ""} · {n.travellers}</p>
      <div>
        <span className="muted">Total for your group</span>
        <div className="price-total">{usd(price)}</div>
      </div>
      <dl className="price-rows">
        <dt>{n.pay_in_full ? "Pay in full now" : "Deposit to confirm (25%)"}</dt><dd>{usd(deposit)}</dd>
        {!n.pay_in_full && (<><dt>Balance due {niceDate(n.balance_due)}</dt><dd>{usd(balance)}</dd></>)}
      </dl>
      <p className="muted">Private tour, includes everything listed on the tour page. Quote reference {n.quote_ref}.</p>
      <div className="actions">
        {(n.actions as UiAction[]).map((a) => (
          <button key={a.name} className="btn btn--primary" disabled={ctx.disabled} onClick={() => ctx.onAction(a)}>{actionLabel(a)}</button>
        ))}
      </div>
    </section>
  );
}

function TravellerPicker({ n, ctx }: { n: ComponentNode; ctx: RenderCtx }) {
  const [adults, setAdults] = useState<number>(n.adults || 2);
  const [kids, setKids] = useState<number[]>(n.child_ages ?? []);
  const [date, setDate] = useState<string>(n.start_date ?? "");
  const [tripType, setTripType] = useState<string>(n.trip_type ?? "");
  const total = adults + kids.length;
  const kind = adults === 1 && kids.length === 0 ? "solo" : adults === 2 && kids.length === 0 ? "couple" : kids.length > 0 ? "family" : "group";
  const preset = (k: string) => {
    if (k === "solo") { setAdults(1); setKids([]); }
    if (k === "couple") { setAdults(2); setKids([]); }
    if (k === "family") { setAdults(2); setKids(kids.length ? kids : [8]); }
    if (k === "group") { setAdults(Math.max(adults, 4)); setKids([]); }
  };
  const submit = () =>
    ctx.onAction({ name: "set_travellers", context: { adults, child_ages: kids, start_date: date || null, trip_type: tripType || null } });
  return (
    <section className="card card--wide accent-orange" aria-label="Who is travelling">
      <h3>Who is travelling?</h3>
      <div className="tiles" role="group" aria-label="Traveller type">
        {(["solo", "couple", "family", "group"] as const).map((k) => {
          const Art = TravellerArt[k];
          return (
            <button key={k} type="button" className="tile" aria-pressed={kind === k} onClick={() => preset(k)}>
              <Art />{k[0].toUpperCase() + k.slice(1)}
            </button>
          );
        })}
      </div>
      <div className="form-grid">
        <div className="field">
          <span id={`${n.id}-adults`}>Adults (12+)</span>
          <div className="stepper" role="group" aria-labelledby={`${n.id}-adults`}>
            <button type="button" aria-label="Fewer adults" onClick={() => setAdults(Math.max(1, adults - 1))}>−</button>
            <output aria-live="polite">{adults}</output>
            <button type="button" aria-label="More adults" onClick={() => setAdults(Math.min(20, adults + 1))}>+</button>
          </div>
        </div>
        <div className="field">
          <span>Children (ages 0–11)</span>
          <div className="row">
            {kids.map((age, i) => (
              <label key={i} className="row" style={{ gap: 4 }}>
                <span className="visually-hidden">Age of child {i + 1}</span>
                <select value={age} onChange={(e) => setKids(kids.map((a, j) => (j === i ? Number(e.target.value) : a)))}>
                  {Array.from({ length: 12 }, (_, a) => <option key={a} value={a}>{a < 1 ? "under 1" : `${a} yr`}</option>)}
                </select>
                <button type="button" className="link-button" aria-label={`Remove child ${i + 1}`} onClick={() => setKids(kids.filter((_, j) => j !== i))}>×</button>
              </label>
            ))}
            {total < 20 && <button type="button" className="link-button" onClick={() => setKids([...kids, 8])}>+ Add child</button>}
          </div>
          <span className="hint">Under 2s travel free. Ages 2–11 pay child rates.</span>
        </div>
        <label className="field">
          <span>Start date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Kind of trip</span>
          <select value={tripType} onChange={(e) => setTripType(e.target.value)}>
            <option value="">Not sure yet</option>
            <option value="day_tour">Day tour</option>
            <option value="multi_day">Multi-day tour</option>
            <option value="custom">Custom trip</option>
          </select>
        </label>
        <button className="btn btn--primary" disabled={ctx.disabled} onClick={submit}>Continue</button>
      </div>
    </section>
  );
}

function Handoff({ n }: { n: ComponentNode }) {
  return (
    <section className="notice notice--warning notice--art" aria-label={n.title}>
      <span className="notice__art"><StateArt.teaCup /></span>
      <div>
        <h4><Icon.info /> {n.title}</h4>
        <p style={{ margin: 0 }}>{n.message}</p>
        <p className="muted" style={{ margin: "6px 0 0", fontSize: 12 }}>Reference {n.reference}</p>
      </div>
    </section>
  );
}

export function Notice({ tone, title, message, art, children }: { tone: string; title: string; message: string; art?: ReactNode; children?: ReactNode }) {
  const body = (
    <>
      <h4>{tone === "error" ? <Icon.alert /> : tone === "info" ? <Icon.check /> : <Icon.info />} {title}</h4>
      <p style={{ margin: 0 }}>{message}</p>
      {children}
    </>
  );
  return (
    <section className={`notice notice--${tone}${art ? " notice--art" : ""}`} role={tone === "error" ? "alert" : "status"}>
      {art ? <><span className="notice__art">{art}</span><div>{body}</div></> : body}
    </section>
  );
}

function BookingForm({ n, ctx }: { n: ComponentNode; ctx: RenderCtx }) {
  const deposit = resolve(ctx.surface, n.deposit_usd);
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [result, setResult] = useState<any>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const payload = {
      visitor_id: ctx.visitorId, quote_ref: n.quote_ref,
      full_name: String(f.get("full_name") || ""), email: String(f.get("email") || ""),
      phone: String(f.get("phone") || "") || null,
      card_number: String(f.get("card_number") || ""), card_expiry: String(f.get("card_expiry") || ""),
    };
    const errs: Record<string, string> = {};
    if (payload.full_name.trim().length < 2) errs.full_name = "Please enter your name.";
    if (!/^\S+@\S+\.\S+$/.test(payload.email)) errs.email = "Please enter a valid email.";
    if (payload.card_number.replace(/\D/g, "").length < 12) errs.card_number = "Please enter the card number.";
    if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(payload.card_expiry)) errs.card_expiry = "Use MM/YY.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setState("sending");
    try {
      const res = await fetch("/api/booking", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await res.json().catch(() => null);
      setResult(data && typeof data.ok === "boolean" ? data : { ok: false, title: "We couldn't finish your booking", message: "Nothing has been charged. Please try again, or ask our team for a payment link.", next_steps: ["Try again"] });
    } catch {
      setResult({ ok: false, title: "We couldn't reach our booking system", message: "Nothing has been charged. Please check your connection and try again.", next_steps: ["Try again"] });
    }
    setState("done");
  };
  if (state === "done" && result) {
    return (
      <Notice tone={result.ok ? "info" : "error"} title={result.title} message={result.message} art={result.ok ? undefined : <StateArt.tukTuk />}>
        {!result.ok && (
          <div className="actions" style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn--primary" onClick={() => { setState("idle"); setResult(null); }}>Try again</button>
            <button className="btn btn--ghost" onClick={() => ctx.onAction({ name: "send_enquiry", context: { quote_ref: n.quote_ref } })}>Ask the team for a payment link</button>
          </div>
        )}
      </Notice>
    );
  }
  const field = (name: string, label: string, props: Record<string, unknown> = {}) => (
    <label className="field">
      <span>{label}</span>
      <input name={name} aria-invalid={!!errors[name]} {...props} />
      {errors[name] && <span className="field-error">{errors[name]}</span>}
    </label>
  );
  return (
    <form className="card card--wide accent-orange" onSubmit={onSubmit} noValidate aria-label="Booking form">
      <h3>Book {n.tour_title}</h3>
      <p className="muted">{n.pay_in_full ? "You pay in full today" : "You pay the deposit today"}: <strong>{usd(deposit)}</strong>. Payment is a demo – no real card is charged.</p>
      <div className="form-grid">
        {field("full_name", "Full name", { autoComplete: "name" })}
        {field("email", "Email", { type: "email", autoComplete: "email" })}
        {field("phone", "Phone (optional)", { type: "tel", autoComplete: "tel" })}
        {field("card_number", "Card number (demo)", { inputMode: "numeric", placeholder: "4242 4242 4242 4242" })}
        {field("card_expiry", "Expiry (MM/YY)", { placeholder: "12/28" })}
        <p className="muted" style={{ fontSize: 12 }}>Your details go only to our booking team. They are never shared with the AI assistant.</p>
        <button className="btn btn--primary" type="submit" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Confirm booking"}</button>
      </div>
    </form>
  );
}

function EnquiryForm({ n, ctx }: { n: ComponentNode; ctx: RenderCtx }) {
  const [msg, setMsg] = useState<string | null>(null);
  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const res = await fetch(`/api/enquiry/${n.reference}/contact`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_id: ctx.visitorId, full_name: f.get("full_name"), email: f.get("email"), message: f.get("message") || null }),
      });
      const data = await res.json().catch(() => null);
      setMsg(data?.message ?? "Thank you. Our team will reply by email.");
    } catch {
      setMsg("We couldn't send that just now. Please try again.");
    }
  };
  if (msg) return <Notice tone="info" title="Request sent" message={msg} art={<StateArt.envelope />} />;
  return (
    <form className="card card--wide accent-teal" onSubmit={onSubmit} aria-label="Send your request to our team">
      <h3>Send your request to our team</h3>
      <p className="muted">{n.summary}</p>
      <div className="form-grid">
        <label className="field"><span>Full name</span><input name="full_name" required minLength={2} autoComplete="name" /></label>
        <label className="field"><span>Email</span><input name="email" type="email" required autoComplete="email" /></label>
        <label className="field"><span>Anything else? (optional)</span><textarea name="message" rows={3} /></label>
        <button className="btn btn--teal" type="submit">Send to our team</button>
      </div>
    </form>
  );
}

function Sources({ n }: { n: ComponentNode }) {
  return (
    <div className="sources" aria-label="Sources">
      <span>Sources:</span>
      {(n.sources as any[]).map((s) => (
        <span className="src" key={s.doc_id} title={s.source}><Icon.doc /> {s.title}</span>
      ))}
    </div>
  );
}
