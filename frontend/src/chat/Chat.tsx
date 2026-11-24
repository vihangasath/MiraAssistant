import { useCallback, useEffect, useRef, useState } from "react";
import { runTurn, type UiAction } from "../agui";
import { Notice, SurfaceView } from "../a2ui/Renderer";
import { processMessages, resolve, type Surface } from "../a2ui/surface";
import { canListen, canSpeak, useVoice } from "./voice";
import { storage } from "../brand";
import { S } from "../strings";
import { TOURS, TOUR_FILTERS } from "../tours";
import { DestinationPhoto } from "../destinations";
import { PHOTOS } from "../photos";

interface ChatMessage {
  id: string;
  role: "user" | "mira";
  text: string;
  surface?: Surface | null;
  traceUrl?: string | null;
  error?: boolean;
}

interface TripSummary {
  tour?: string;
  dates?: string;
  travellers?: string;
  price?: string;
  reference?: string;
}

const store = storage();

// What Mira says aloud besides her reply text. Amounts come from the quote bound into the card
// (the same data the PriceBreakdown shows), never from model text.
function spokenSummary(surface: Surface | null): string {
  if (!surface) return "";
  const parts: string[] = [];
  for (const c of surface.components.values()) {
    if (c.component === "PriceBreakdown") {
      const price = resolve(surface, c.price_usd), deposit = resolve(surface, c.deposit_usd);
      if (typeof price === "number") parts.push(`The total for your group is ${price.toLocaleString("en-US")} US dollars.`);
      if (typeof deposit === "number" && !c.pay_in_full) parts.push(`The deposit to confirm is ${deposit.toLocaleString("en-US")} US dollars.`);
      if (c.pay_in_full) parts.push("This is paid in full when you book.");
    } else if (c.component === "SpecialistHandoff") {
      parts.push(`${c.title}. ${c.message}`);
    } else if (c.component === "TravellerPicker") {
      parts.push("Tell me who is travelling and when, or use the form on screen.");
    } else if (c.component === "BookingForm") {
      parts.push("The booking form is on screen. Please type your details there.");
    }
  }
  return parts.join(" ");
}

function getVisitorId(): string {
  let id = store.get("mira.visitor_id");
  if (!id) {
    id = `v-${crypto.randomUUID()}`;
    store.set("mira.visitor_id", id);
  }
  return id;
}

export function Chat() {
  const [visitorId, setVisitorId] = useState(getVisitorId);
  const [threadId, setThreadId] = useState(() => `t-${crypto.randomUUID()}`);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [trip, setTrip] = useState<TripSummary>({});
  const [tripOpen, setTripOpen] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const [tripPulse, setTripPulse] = useState(false);
  const voice = useVoice();
  const [readAloud, setReadAloud] = useState(() => canSpeak && store.get("mira.read_aloud") === "1");
  const readAloudRef = useRef(readAloud);
  readAloudRef.current = readAloud;
  const handsFree = useRef(false); // true while a conversation is being held by voice
  const listenRef = useRef<() => void>(() => undefined);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, busy]);

  const hasTrip = !!(trip.tour || trip.price);
  useEffect(() => {
    if (!hasTrip) return;
    setTripPulse(true); // the mobile bar stays collapsed and shows the price; the desktop panel is always open
    const t = setTimeout(() => setTripPulse(false), 1200);
    return () => clearTimeout(t);
  }, [trip.tour, trip.dates, trip.travellers, trip.price, trip.reference, hasTrip]);

  const updateTrip = (surface: Surface | null) => {
    if (!surface) return;
    for (const c of surface.components.values()) {
      if (c.component === "PriceBreakdown") {
        const q = surface.data.quotes?.[c.quote_ref];
        setTrip({ tour: c.tour_title, dates: c.start_date === c.end_date ? c.start_date : `${c.start_date} → ${c.end_date}`,
                  travellers: c.travellers, price: q ? `USD ${q.price_usd.toLocaleString("en-US")}` : undefined, reference: c.quote_ref });
      } else if (c.component === "SpecialistHandoff") {
        setTrip((t) => ({ ...t, price: "A specialist will confirm", reference: c.reference }));
      } else if (c.component === "TourCard") {
        setTrip((t) => (t.tour ? t : { ...t, tour: c.title }));
      }
    }
  };

  const send = useCallback(async (opts: { text?: string; action?: UiAction; hideUser?: boolean }) => {
    if (busy) return;
    setBusy(true);
    setStep(null);
    const pendingId = `u-${Date.now()}`;
    let reply = "";
    let extra = "";
    if (!opts.hideUser && opts.text) setMessages((m) => [...m, { id: pendingId, role: "user", text: opts.text! }]);
    await runTurn({
      threadId, visitorId, text: opts.text, action: opts.action,
      handlers: {
        onStep: (name) => setStep(name),
        onMeta: (meta) => {
          if (!opts.hideUser && !opts.text && meta.user_text) {
            setMessages((m) => [...m, { id: pendingId, role: "user", text: meta.user_text }]);
          }
          setMessages((m) => [...m, { id: meta.message_id, role: "mira", text: "", traceUrl: meta.trace_url }]);
        },
        onText: (id, text) => { reply = text; setMessages((m) => m.map((x) => (x.id === id ? { ...x, text } : x))); },
        onA2ui: (id, msgs) => {
          const surface = processMessages(msgs);
          extra = spokenSummary(surface);
          updateTrip(surface);
          setMessages((m) => m.map((x) => (x.id === id ? { ...x, surface } : x)));
        },
        onError: (message) => { reply = message; setMessages((m) => [...m, { id: `e-${Date.now()}`, role: "mira", text: message, error: true }]); },
      },
    });
    setBusy(false);
    setStep(null);
    if (readAloudRef.current && (reply || extra)) {
      // In a hands-free conversation, listen again once Mira has finished speaking.
      voice.speak(`${reply} ${extra}`, () => { if (handsFree.current) listenRef.current(); });
    } else if (handsFree.current) {
      handsFree.current = false;
    }
  }, [busy, threadId, visitorId, voice.speak]);

  // Returning visitors are greeted with their last quote.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    fetch(`/api/visitor/${visitorId}`).then((r) => r.json()).then((d) => {
      if (d?.profile?.last_quote || d?.profile?.trip?.adults) {
        send({ action: { name: "send_text", context: { text: "Hello again" } }, hideUser: true });
      }
    }).catch(() => undefined);
  }, [visitorId, send]);

  const onAction = (action: UiAction) => {
    if (action.name === "send_text") send({ text: String(action.context?.text ?? "") });
    else send({ action });
  };

  const forget = async () => {
    await fetch(`/api/visitor/${visitorId}`, { method: "DELETE" }).catch(() => undefined);
    store.remove("mira.visitor_id");
    setVisitorId(getVisitorId());
    setThreadId(`t-${crypto.randomUUID()}`);
    setMessages([]);
    setTrip({});
  };

  const empty = messages.length === 0;
  const submit = () => { if (input.trim() && !busy) { handsFree.current = false; voice.stopSpeaking(); send({ text: input.trim() }); setInput(""); } };

  // Voice: the mic starts a hands-free conversation (Mira answers aloud and listens again); tapping it again stops.
  const startListening = () => voice.listen({
    onInterim: (t) => setInput(t),
    onFinal: (t) => { setInput(""); send({ text: t }); },
    onNothing: () => { handsFree.current = false; setInput(""); },
  });
  listenRef.current = startListening;
  const toggleMic = () => {
    if (voice.listening) { handsFree.current = false; voice.stopListening(); return; }
    handsFree.current = true;
    if (!readAloud && canSpeak) { setReadAloud(true); store.set("mira.read_aloud", "1"); }
    startListening();
  };
  const toggleReadAloud = () => {
    const next = !readAloud;
    setReadAloud(next);
    store.set("mira.read_aloud", next ? "1" : "0");
    if (!next) { voice.stopSpeaking(); handsFree.current = false; }
  };
  const composer = (id: string, placeholder: string, cta: string) => (
    <form className="composer-card" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <label htmlFor={id} className="visually-hidden">{S.inputLabel}</label>
      <textarea id={id} rows={2} value={input} maxLength={1000} placeholder={voice.listening ? S.voiceListening : placeholder} readOnly={voice.listening}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
      <div className="composer-card__bar">
        <span className="composer-card__hint">
          {canListen && (
            <button type="button" className={`icon-button${voice.listening ? " icon-button--live" : ""}`} onClick={toggleMic} disabled={busy && !voice.listening}
              aria-pressed={voice.listening} aria-label={voice.listening ? S.voiceStop : S.voiceStart} title={voice.listening ? S.voiceStop : S.voiceStart}>
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
            </button>
          )}
          {canSpeak && (
            <button type="button" className="icon-button" onClick={toggleReadAloud} aria-pressed={readAloud}
              aria-label={readAloud ? S.readAloudOff : S.readAloudOn} title={readAloud ? S.readAloudOff : S.readAloudOn}>
              {readAloud ? (
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></svg>
              ) : (
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M17 9l5 6M22 9l-5 6" /></svg>
              )}
            </button>
          )}
          <span className="voice-status" role="status" aria-live="polite">
            {voice.error ?? (voice.listening ? S.voiceListening : voice.speaking ? S.voiceSpeaking : "")}
          </span>
        </span>
        <button className="btn btn--primary" type="submit" disabled={busy || !input.trim()}>
          {cta}<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </button>
      </div>
    </form>
  );
  const shown = TOURS.filter((t) => filter === "all" || t.group === filter);

  if (empty) {
    return (
      <main className="home" id="main">
        <section className="hero">
          <h1>Mira, your Sri Lanka travel assistant that plans and <mark>books</mark>.</h1>
          <div className="hero__greeting">
            <img className="avatar" src="/mira-avatar.svg" alt="" />
            <p className="bubble">Hi, I'm Mira. What kind of trip would you like?</p>
          </div>
          {composer("landing-input", S.inputPlaceholder, "Start planning")}
          <div className="quick-start" role="group" aria-label="Quick start">
            {S.quickStarts.map((q) => (
              <button key={q.label} className="chip" disabled={busy} onClick={() => send({ text: q.text })}>{q.label}</button>
            ))}
          </div>
          <p className="hero__proof">Prices come from our rate sheet. <strong>Our travel team</strong> confirms every custom trip.</p>
        </section>

        <section className="explore" aria-labelledby="explore-title">
          <h2 id="explore-title"><span className="warm">Not sure where to go</span> <mark>yet</mark>.</h2>
          <div className="filters" role="tablist" aria-label="Tour type">
            {TOUR_FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}</button>
            ))}
          </div>
          <ul className="trip-grid">
            {shown.map((t, i) => (
              <li key={t.title}>
                <button className={`trip-card tone-${i % 5}`} onClick={() => send({ text: `Tell me about the ${t.title}.` })} disabled={busy}>
                  <span className="trip-card__badge">{t.duration}</span>
                  <span className="trip-card__art"><DestinationPhoto name={t.art ?? t.places.split(" · ")[0]} /></span>
                  <span className="trip-card__body">
                    <strong>{t.title}</strong>
                    <span className="trip-card__meta">{t.places}</span>
                    <span className="trip-card__price">Ask Mira for a price</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <footer className="footer">
          <div className="footer__row">
            <span>© Ceylon Compass Holidays</span>
            <span>{S.heroBody}</span>
          </div>
          <details className="credits">
            <summary>Photo credits</summary>
            <ul>
              {Object.entries(PHOTOS).filter(([k]) => k !== "hikkaduwa").map(([k, p]) => (
                <li key={k}>
                  <a href={p.page} target="_blank" rel="noreferrer">{p.alt}</a> by {p.author}, {p.licenseUrl ? <a href={p.licenseUrl} target="_blank" rel="noreferrer">{p.license}</a> : p.license}, via Wikimedia Commons
                </li>
              ))}
            </ul>
          </details>
        </footer>
      </main>
    );
  }

  return (
    <div className="chat-layout">
      <main className="chat" id="main">
        <div className="messages" aria-live="polite">
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="msg msg--user"><div className="bubble bubble--user">{m.text}</div></div>
            ) : (
              <div key={m.id} className="msg">
                <img className="avatar" src="/mira-avatar.svg" alt="Mira" />
                <div className="msg__body">
                  {m.error ? (
                    <Notice tone="error" title="Something went wrong" message={m.text} />
                  ) : (
                    m.text && <p className="msg__text">{m.text}</p>
                  )}
                  {m.surface && <SurfaceView surface={m.surface} onAction={onAction} visitorId={visitorId} disabled={busy} />}
                  {m.traceUrl && <a className="trace-link" href={m.traceUrl} target="_blank" rel="noreferrer">View trace</a>}
                </div>
              </div>
            ),
          )}
          {busy && (
            <div className="msg">
              <img className="avatar" src="/mira-avatar.svg" alt="" />
              <p className="typing" role="status"><span className="typing__dots" aria-hidden="true"><i /><i /><i /></span>{S.thinking}</p>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div className="composer">
          <TripPanel variant="bar" trip={trip} hasTrip={hasTrip} pulse={tripPulse} open={tripOpen} onToggle={() => setTripOpen((o) => !o)} onForget={forget} />
          {composer("chat-input", "Reply to Mira…", S.send)}
        </div>
      </main>
      <TripPanel variant="side" trip={trip} hasTrip={hasTrip} pulse={tripPulse} open onToggle={() => undefined} onForget={forget} />
    </div>
  );
}

// Desktop: a side panel that is always open. Mobile: a collapsible bar above the input (UI-DESIGN.md §6).
function TripPanel({ variant, trip, hasTrip, pulse, open, onToggle, onForget }: {
  variant: "side" | "bar"; trip: TripSummary; hasTrip: boolean; pulse: boolean; open: boolean; onToggle: () => void; onForget: () => void;
}) {
  const title = <span className="trip-panel__title">{S.tripTitle}{hasTrip && <span className="trip-panel__dot" aria-hidden="true" />}</span>;
  return (
    <aside className={`trip-panel trip-panel--${variant}${pulse ? " trip-panel--pulse" : ""}`} aria-label={S.tripTitle}>
      {variant === "bar" ? (
        <button className="trip-panel__toggle" aria-expanded={open} onClick={onToggle}>
          {title}
          {!open && trip.price && <span className="trip-panel__peek">{trip.price}</span>}
          <svg className={`chev${open ? " chev--open" : ""}`} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 15l6-6 6 6" /></svg>
        </button>
      ) : (
        <h2 className="trip-panel__heading">{title}</h2>
      )}
      {open && (
        <div className="trip-panel__body">
          {hasTrip ? (
            <dl>
              {trip.tour && (<><dt>Tour</dt><dd>{trip.tour}</dd></>)}
              {trip.dates && (<><dt>Dates</dt><dd>{trip.dates}</dd></>)}
              {trip.travellers && (<><dt>Travellers</dt><dd>{trip.travellers}</dd></>)}
              {trip.price && (<><dt>Price</dt><dd>{trip.price}</dd></>)}
              {trip.reference && (<><dt>Reference</dt><dd>{trip.reference}</dd></>)}
            </dl>
          ) : (
            <p className="trip-panel__empty">{S.tripEmpty}</p>
          )}
          <button className="text-button" onClick={onForget}>{S.forget}</button>
        </div>
      )}
    </aside>
  );
}
