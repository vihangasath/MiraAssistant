import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { applyBrandPack, storage } from "./brand";
import { Chat } from "./chat/Chat";
import { Staff } from "./staff/Staff";
import { Login } from "./staff/Login";
import "./theme.css";

const store = storage();

// Theme: follows prefers-color-scheme until the visitor picks one with the toggle (UI-DESIGN.md §3.3).
type Theme = "light" | "dark";
const darkQuery = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function useTheme(): [Theme, () => void] {
  const [chosen, setChosen] = useState<Theme | null>(() => {
    const t = store.get("mira.theme");
    return t === "light" || t === "dark" ? t : null;
  });
  const [systemDark, setSystemDark] = useState(() => !!darkQuery?.matches);
  useEffect(() => {
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    darkQuery?.addEventListener("change", onChange);
    return () => darkQuery?.removeEventListener("change", onChange);
  }, []);
  useEffect(() => {
    if (chosen) document.documentElement.dataset.theme = chosen;
    else delete document.documentElement.dataset.theme;
  }, [chosen]);
  const theme: Theme = chosen ?? (systemDark ? "dark" : "light");
  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    store.set("mira.theme", next);
    setChosen(next);
  };
  return [theme, toggle];
}

function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [session, setSession] = useState<string | null>(() => store.get("mira.session"));
  const [theme, toggleTheme] = useTheme();
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const navigate = (to: string) => { window.history.pushState({}, "", to); setPath(to); };
  const isStaffSession = session === "staff" && !!store.get("mira.staff_token");
  // Everyone goes through the login page first.
  const page = !session ? "login" : path.startsWith("/staff") ? (isStaffSession ? "staff" : "chat") : path.startsWith("/login") ? "login" : "chat";
  useEffect(() => {
    const want = page === "login" ? "/login" : page === "staff" ? "/staff" : "/";
    if (window.location.pathname !== want) window.history.replaceState({}, "", want);
  }, [page]);
  const signIn = (kind: "traveller" | "staff") => { store.set("mira.session", kind); setSession(kind); navigate(kind === "staff" ? "/staff" : "/"); };
  const signOut = () => { store.remove("mira.session"); store.remove("mira.staff_token"); setSession(null); navigate("/login"); };
  return (
    <div className={`app app--${page}`}>
      <nav className="nav" aria-label="Main">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); if (session) navigate(isStaffSession ? "/staff" : "/"); }}>
          <svg className="brand__mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5l2.6 6.9 6.9 2.6-6.9 2.6L12 21.5l-2.6-6.9L2.5 12l6.9-2.6z" fill="currentColor" /></svg>
          <span>Ceylon Compass</span>
        </a>
        <span className="nav__spacer" />
        <button className="pill-button pill-button--icon" onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} title={theme === "dark" ? "Light theme" : "Dark theme"}>
          {theme === "dark" ? (
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
          )}
        </button>
        {session && (
          <button className="pill-button" onClick={signOut}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
            <span className="pill-button__role">{session === "staff" ? "Staff" : "Traveller"} · </span>Sign out
          </button>
        )}
      </nav>
      {page === "login" ? <Login onSignIn={signIn} /> : page === "staff" ? <Staff onSignOut={signOut} /> : <Chat />}
    </div>
  );
}

applyBrandPack();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
