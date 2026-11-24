// Login gate: travellers continue to Mira; admin/staff accounts go to the staff page.
// Demo prototype: tokens only, no passwords.
import { useState } from "react";
import { storage } from "../brand";
import { LoginScene } from "./LoginScene";

const store = storage();
const DEMO_USERS = [
  { token: "demo-agent-token", label: "Nimal Perera", role: "Sales agent", initials: "NP" },
  { token: "demo-approver-token", label: "Ayesha Fernando", role: "Admin · content approver", initials: "AF" },
];

export function Login({ onSignIn }: { onSignIn: (kind: "traveller" | "staff") => void }) {
  const [admin, setAdmin] = useState(false);
  return (
    <main className="home" id="main">
      <section className={`hero hero--login${admin ? " hero--plain" : ""}`}>
        <h1>{admin ? <>Sign in to the <mark>staff</mark> desk.</> : <>Plan your Sri Lanka trip with <mark>Mira</mark>.</>}</h1>
        <div className="login-card">
          {admin ? (
            <>
              <p className="login-card__sub">Pick a demo staff account. This prototype has no passwords.</p>
              <div className="stack">
                {DEMO_USERS.map((u) => (
                  <button key={u.token} className="login-option" onClick={() => { store.set("mira.staff_token", u.token); onSignIn("staff"); }}>
                    <span className="login-option__avatar" aria-hidden="true">{u.initials}</span>
                    <span><strong>{u.label}</strong><span>{u.role}</span></span>
                  </button>
                ))}
              </div>
              <button className="text-button" onClick={() => setAdmin(false)}>Back to traveller sign-in</button>
            </>
          ) : (
            <>
              <p className="login-card__sub">Real itineraries and prices from our tours. Anything custom goes to our travel team.</p>
              <button className="btn btn--primary btn--block" onClick={() => onSignIn("traveller")}>
                Continue as traveller
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
              </button>
              <button className="btn btn--ghost btn--block" onClick={() => setAdmin(true)}>Admin login</button>
            </>
          )}
        </div>
        {!admin && <LoginScene />}
      </section>
    </main>
  );
}
