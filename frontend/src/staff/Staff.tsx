// Staff page: plain, same tokens, no illustrations (UI-DESIGN.md §6).
import { Fragment, useEffect, useState } from "react";
import { storage } from "../brand";

const store = storage();
const DEMO_USERS = [
  { token: "demo-agent-token", label: "Nimal Perera – Sales agent" },
  { token: "demo-approver-token", label: "Ayesha Fernando – Content approver" },
];
const STATUSES = ["new", "needs_specialist", "contacted", "quoted", "booked", "payment_failed", "needs_follow_up", "closed"];

async function api(path: string, token: string, init: RequestInit = {}) {
  const res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", "X-Staff-Token": token, ...(init.headers ?? {}) } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? data.message ?? `Request failed (${res.status})`);
  return data;
}

export function Staff({ onSignOut }: { onSignOut?: () => void } = {}) {
  const [token, setToken] = useState<string>(() => store.get("mira.staff_token") ?? "");
  const [me, setMe] = useState<any>(null);
  const [tab, setTab] = useState<"enquiries" | "content" | "issues" | "pricing">("enquiries");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) { setMe(null); return; }
    api("/api/staff/me", token).then(setMe).catch((e) => { setError(e.message); setMe(null); });
  }, [token]);

  if (!me) {
    return (
      <div className="staff">
        <h1>Staff sign-in</h1>
        <div className="panel stack" style={{ maxWidth: 420 }}>
          <p>Demo accounts (no passwords in this prototype):</p>
          {DEMO_USERS.map((u) => (
            <button key={u.token} className="btn btn--ghost" style={{ color: "var(--text)" }} onClick={() => { store.set("mira.staff_token", u.token); setToken(u.token); }}>{u.label}</button>
          ))}
          {error && <p className="error-text">{error}</p>}
        </div>
      </div>
    );
  }
  return (
    <div className="staff">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Staff</h1>
        <div className="row">
          <span>{me.name} · <strong>{me.role}</strong></span>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {(["enquiries", "content", "issues", "pricing"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {{ enquiries: "Enquiries", content: "Content approvals", issues: "Data issues", pricing: "Pricing rules" }[t]}
          </button>
        ))}
      </div>
      {tab === "enquiries" && <Enquiries token={token} />}
      {tab === "content" && <Content token={token} me={me} />}
      {tab === "issues" && <Issues token={token} />}
      {tab === "pricing" && <Pricing token={token} me={me} />}
    </div>
  );
}

function Enquiries({ token }: { token: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const load = () => api("/api/staff/enquiries", token).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const update = async (id: string, body: Record<string, string>) => { await api(`/api/staff/enquiries/${id}`, token, { method: "PATCH", body: JSON.stringify(body) }); load(); };
  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <p style={{ margin: 0 }}>{rows.length} enquiries. Costs and margins are visible to staff only.</p>
        <button className="link-button" onClick={load}>Refresh</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Ref</th><th>Created</th><th>Kind</th><th>Tour / request</th><th>Price</th><th>Deposit</th><th>Cost</th><th>GP %</th><th>Status</th><th>Trace</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={11} className="empty-row">No enquiries yet. Quotes and specialist requests from the chat appear here.</td></tr>}
            {rows.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td>{r.id}</td>
                  <td>{new Date(r.created_at).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td>{r.kind}</td>
                  <td>{r.tour_name ?? "—"}<br /><span style={{ color: "var(--muted)" }}>{r.request?.start_date ?? ""} {r.request?.adults ? `· ${r.request.adults} ad` : ""}{r.request?.child_ages?.length ? ` · kids ${r.request.child_ages.join(",")}` : ""}</span></td>
                  <td>{r.price_usd != null ? `USD ${r.price_usd.toLocaleString()}` : "—"}</td>
                  <td>{r.deposit_usd != null ? `USD ${r.deposit_usd.toLocaleString()}` : "—"}</td>
                  <td>{r.cost_usd != null ? `USD ${r.cost_usd.toFixed(2)}` : "—"}</td>
                  <td>{r.gross_profit_pct != null ? `${r.gross_profit_pct}%` : "—"}</td>
                  <td>
                    <label className="visually-hidden" htmlFor={`st-${r.id}`}>Status</label>
                    <select id={`st-${r.id}`} value={r.status} onChange={(e) => update(r.id, { status: e.target.value })}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                    </select>
                  </td>
                  <td>{r.trace_url ? <a href={r.trace_url} target="_blank" rel="noreferrer">trace</a> : "—"}</td>
                  <td><button className="link-button" onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>{open === r.id ? "Hide" : "Details"}</button></td>
                </tr>
                {open === r.id && (
                  <tr>
                    <td colSpan={11}>
                      <div className="stack">
                        {r.flag_reasons && (<div><strong>Why no price:</strong><ul>{r.flag_reasons.map((f: any, i: number) => <li key={i}><code>{f.code}</code> {f.detail}</li>)}</ul></div>)}
                        {r.staff_quote && (<div><strong>Cost lines (LKR):</strong> {Object.entries(r.staff_quote.cost_lines_lkr).map(([k, v]) => `${k} ${Number(v).toLocaleString()}`).join(" · ")} · vehicle {r.staff_quote.vehicle} · margin {r.staff_quote.margin * 100}%</div>)}
                        {r.request?.summary && <div><strong>Request:</strong> {r.request.summary}</div>}
                        {r.contact && <div><strong>Contact:</strong> {r.contact.full_name} · {r.contact.email}{r.contact.phone ? ` · ${r.contact.phone}` : ""}</div>}
                        {r.booking_ref && <div><strong>Booking:</strong> {r.booking_ref}</div>}
                        <label className="field"><span>Notes</span>
                          <textarea value={notes[r.id] ?? r.notes ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} />
                        </label>
                        <div><button className="btn btn--primary" onClick={() => update(r.id, { notes: notes[r.id] ?? r.notes ?? "" })}>Save notes</button></div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Content({ token, me }: { token: string; me: any }) {
  const [rows, setRows] = useState<any[]>([]);
  const [command, setCommand] = useState("Add a 5-day Hill Country tour using the Ella photos");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const load = () => api("/api/staff/content", token).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const draft = async () => {
    setBusy(true); setMsg(null);
    try {
      const d = await api("/api/staff/content/command", token, { method: "POST", body: JSON.stringify({ command }) });
      setMsg(`Draft ${d.id} created. ${d.open_questions?.length ? `Open questions: ${d.open_questions.join(" ")}` : ""}`);
      setPreview(d.id); load();
    } catch (e: any) { setMsg(e.message); }
    setBusy(false);
  };
  const act = async (id: string, verb: "publish" | "reject") => {
    try { await api(`/api/staff/content/${id}/${verb}`, token, { method: "POST" }); setMsg(`${id} ${verb}ed.`); load(); }
    catch (e: any) { setMsg(e.message); }
  };
  return (
    <div className="stack">
      <div className="panel stack">
        <label className="field"><span>Ask the content agent</span>
          <textarea value={command} onChange={(e) => setCommand(e.target.value)} />
        </label>
        <div className="row"><button className="btn btn--primary" disabled={busy} onClick={draft}>{busy ? "Drafting…" : "Create draft"}</button>
          <span style={{ color: "var(--muted)" }}>Drafts are never shown to travellers until an Approver publishes them.</span></div>
        {msg && <p role="status">{msg}</p>}
      </div>
      <div className="panel table-wrap">
        <table>
          <thead><tr><th>Draft</th><th>Title</th><th>Status</th><th>By</th><th>Approved by</th><th>Trace</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td>{r.id}<br /><span style={{ color: "var(--muted)" }}>{r.doc_id}</span></td>
                  <td>{r.title}</td>
                  <td><span className={`status status--${r.status === "published" ? "booked" : r.status === "rejected" ? "payment_failed" : "new"}`}>{r.status}</span></td>
                  <td>{r.created_by}</td>
                  <td>{r.approved_by ?? "—"}</td>
                  <td>{r.trace_url ? <a href={r.trace_url} target="_blank" rel="noreferrer">trace</a> : "—"}</td>
                  <td className="row">
                    <button className="link-button" onClick={() => setPreview(preview === r.id ? null : r.id)}>{preview === r.id ? "Hide" : "Preview"}</button>
                    {r.status === "draft" && (
                      me.permissions.includes("publish_content")
                        ? (<><button className="btn btn--teal" onClick={() => act(r.id, "publish")}>Publish</button><button className="link-button" onClick={() => act(r.id, "reject")}>Reject</button></>)
                        : <span style={{ color: "var(--muted)" }} title="Only the Approver role can publish">Needs an Approver</span>
                    )}
                  </td>
                </tr>
                {preview === r.id && <tr><td colSpan={7}><div className="md-preview">{r.markdown}</div></td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Issues({ token }: { token: string }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { api("/api/staff/issues", token).then(setRows).catch(() => setRows([])); }, []);
  return (
    <div className="panel table-wrap">
      <p style={{ marginTop: 0 }}>What the loaders found in the dataset and how Mira handles it. The source files are never edited.</p>
      <table>
        <thead><tr><th>Source</th><th>Where</th><th>Kind</th><th>What we do</th></tr></thead>
        <tbody>{rows.map((r, i) => (<tr key={i}><td>{r.source}</td><td>{r.where}</td><td><code>{r.kind}</code></td><td>{r.message}</td></tr>))}</tbody>
      </table>
    </div>
  );
}

function Pricing({ token, me }: { token: string; me: any }) {
  const [data, setData] = useState<any>(null);
  const [form, setForm] = useState({ margin_day: "", margin_multi: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api("/api/staff/pricing-rules", token).then((d) => {
    setData(d);
    setForm({ margin_day: d.file.margin_day ?? "", margin_multi: d.file.margin_multi ?? "" });
  });
  useEffect(() => { load(); }, []);
  const save = async () => {
    try {
      const num = (v: string) => (v === "" ? null : Number(v));
      await api("/api/staff/pricing-rules", token, { method: "PUT", body: JSON.stringify({ margin_day: num(String(form.margin_day)), margin_multi: num(String(form.margin_multi)), margin_by_tour: data?.file?.margin_by_tour ?? {} }) });
      setMsg("Saved. New quotes use these margins."); load();
    } catch (e: any) { setMsg(e.message); }
  };
  if (!data) return null;
  const editable = me.permissions.includes("edit_pricing_rules");
  return (
    <div className="panel stack" style={{ maxWidth: 560 }}>
      <p style={{ margin: 0 }}>Workbook margins: day tours {data.workbook.margin_day * 100}%, multi-day {data.workbook.margin_multi * 100}%. FX {data.workbook.fx_lkr_per_usd} LKR per USD. Leave a box empty to use the workbook value.</p>
      <label className="field"><span>Override: day-tour margin (0–0.9)</span><input disabled={!editable} value={form.margin_day} onChange={(e) => setForm({ ...form, margin_day: e.target.value })} /></label>
      <label className="field"><span>Override: multi-day margin (0–0.9)</span><input disabled={!editable} value={form.margin_multi} onChange={(e) => setForm({ ...form, margin_multi: e.target.value })} /></label>
      {editable ? <div><button className="btn btn--primary" onClick={save}>Save rules</button></div> : <p style={{ color: "var(--muted)" }}>Only an Approver can change pricing rules.</p>}
      {msg && <p role="status">{msg}</p>}
    </div>
  );
}
