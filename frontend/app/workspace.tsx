"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import PilotMap, { type Locality, type MapFeature } from "./pilot-map";

type Incident = { id: string; locality: string; category: string; status: string; source: string; households: number };
type Timeline = { action: string; date: string; note?: string }[];
type Evidence = { id: string; title: string; excerpt: string; url?: string; simulated?: boolean; measurements?: { label: string; value: number; unit: string }[]; source_url?: string; page?: number;
  date?: string; period?: string; limitation: string };
type Run = { id: string; status: string; model: string; stage?: string; error?: string; evidence?: Evidence[]; selected?: string[];
  scenario_analysis?: string; checks?: string[]; unknowns?: string[]; observations?: string[]; draft?: { id: string; message: string; status: string } };
type Alert = { id: string; locality: string; message: string; why: string; sent_at: string; category: string; status: string };
type Report = { resolution_update?: string | null; incident_id: string | null; id: string; description: string; category: string; status: string; observed_at: string };
type RiverDevice = { locality_id: string; station: string; river: string; flagged: boolean;
  samples: { time: string; ph: number; turbidity: number; oxygen: number }[] };
type View = "Map" | "My reports" | "Alerts" | "Review";

const categories = ["discolouration", "odour", "particles", "low pressure", "other"];
const sources = ["municipal", "borewell", "tanker", "unknown"];
const displayText = (value: string) => value.replace(/Demo fixture: /g, "Simulated report: ")
  .replace(/Demo update\./g, "Simulation update.").replace(/demo households/g, "participating households")
  .replace(/demo complaints/g, "household reports");
const readable = (value: string) => value.toLowerCase().replaceAll("_", " ");
const dateLabel = (value: string) => new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata",
}).format(new Date(value));
const initialTime = () => {
  const local = new Date();
  return new Date(local.getTime() - local.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

async function api<T>(path: string, token = "", body?: FormData | object): Promise<T> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (body && !(body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    headers, method: body ? "POST" : "GET",
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join(". ") : data.detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json();
}

export default function Workspace() {
  const [view, setView] = useState<View>("Map");
  const [resident, setResident] = useState("resident-1");
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [localities, setLocalities] = useState<Locality[]>([]);
  const [features, setFeatures] = useState<MapFeature[]>([]);
  const [devices, setDevices] = useState<RiverDevice[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState("");
  const [timeline, setTimeline] = useState<Timeline>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [subscription, setSubscription] = useState({ locality_id: "demo-east", opt_in: false });
  const [showForm, setShowForm] = useState(false);
  const [area, setArea] = useState("demo-east");
  const [category, setCategory] = useState(categories[0]);
  const [position, setPosition] = useState<[number, number]>();
  const [filter, setFilter] = useState("all");
  const [note, setNote] = useState("");
  const [resolutionUpdate, setResolutionUpdate] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Evidence[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const active = incidents.find((item) => item.id === selected);
  const locality = localities.find((item) => item.id === area);
  const focus: [number, number] | undefined = position ?? (locality ? [locality.latitude, locality.longitude] : undefined);

  const refresh = useCallback(async () => {
    const [areas, map, items, riverDevices] = await Promise.all([
      api<Locality[]>("/localities"), api<{ features: MapFeature[] }>("/map"), api<Incident[]>("/incidents"), api<RiverDevice[]>("/river-watch"),
    ]);
    setLocalities(areas);
    setFeatures(map.features);
    setIncidents(items);
    setDevices(riverDevices);
    setSelected((value) => value || items.find((item) => item.status !== "RESOLVED")?.id || items[0]?.id || "");
  }, []);

  const loadReview = useCallback(async (id: string, key: string) => {
    const [investigation, events] = await Promise.all([
      api<Run | null>(`/incidents/${id}/investigation`, key),
      api<Timeline>(`/admin/incidents/${id}/events`, key),
    ]);
    setRun(investigation);
    setTimeline(events);
  }, []);

  useEffect(() => { refresh().catch((err) => setError(err.message)); }, [refresh]);
  useEffect(() => {
    let current = true;
    if (view === "Review" && selected && token) {
      loadReview(selected, token).catch((err) => { if (current) setError(err.message); });
    } else if (view === "Map" && selected) {
      api<{ timeline: Timeline }>(`/incidents/${selected}`).then((item) => {
        if (current) setTimeline(item.timeline);
      }).catch((err) => { if (current) setError(err.message); });
    }
    return () => { current = false; };
  }, [view, selected, token, loadReview]);

  useEffect(() => {
    if (!running || !selected || !token) return;
    let current = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api<Run | null>(`/incidents/${selected}/investigation`, token);
        if (current && next?.status === "RUNNING") setRun(next);
      } catch {
        // The final request reports errors. Keep polling transient failures.
      }
      if (current) timer = setTimeout(poll, 750);
    }
    timer = setTimeout(poll, 200);
    return () => { current = false; clearTimeout(timer); };
  }, [running, selected, token]);

  const loadResident = useCallback(async () => {
    const [items, updates, settings] = await Promise.all([
      api<Report[]>("/reports/mine", resident), api<Alert[]>("/alerts/mine", resident),
      api<typeof subscription>("/alerts/subscription", resident),
    ]);
    setReports(items);
    setAlerts(updates);
    setSubscription(settings);
  }, [resident]);
  useEffect(() => { loadResident().catch((err) => setError(err.message)); }, [loadResident]);

  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try { await work(); }
    catch (err) { setError(err instanceof Error ? err.message : "Request failed"); }
    finally { setBusy(false); }
  }

  function selectIncident(id: string) {
    setTimeline([]);
    setRun(null);
    setNote("");
    setResolutionUpdate("");
    setSelected(id);
  }

  function openReport(issue?: string) {
    setCategory(issue ?? categories[0]);
    setPosition(undefined);
    setArea(subscription.locality_id);
    setView("Map");
    setShowForm(true);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    void act(async () => {
      if (!focus) throw new Error("Choose a pilot locality.");
      const data = new FormData();
      data.set("payload", JSON.stringify({
        locality_id: area, category, source: values.get("source"), description: String(values.get("description")).trim(),
        observed_at: new Date(String(values.get("observed"))).toISOString(),
        latitude: focus[0], longitude: focus[1], zone: String(values.get("zone")).trim().toLowerCase() || null,
        alert_opt_in: values.get("opt") === "on",
      }));
      const file = values.get("photo");
      if (file instanceof File && file.size) data.set("photo", file);
      const result = await api<{ id: string; status: string; incident_id: string | null }>("/reports", resident, data);
      setShowForm(false);
      setNotice(`Report received · ${readable(result.status)} · ${result.id.slice(0, 8)}`);
      if (result.incident_id) selectIncident(result.incident_id);
      await Promise.all([refresh(), loadResident()]);
    });
  }

  function reviewAction(path: string, body: object, message: string | ((result: { recipients: number }) => string)) {
    void act(async () => {
      let result: { recipients: number };
      try { result = await api(path, token, body); }
      finally { await Promise.all([refresh(), loadReview(selected, token), loadResident()]); }
      setNotice(typeof message === "function" ? message(result) : message);
      setNote("");
      setResolutionUpdate("");
    });
  }

  function investigate() {
    setRunning(true);
    setRun(null);
    void act(async () => {
      try {
        await api(`/incidents/${selected}/investigate`, token, {});
        setNotice("Investigation ready for review.");
      } finally {
        setRunning(false);
        await Promise.all([refresh(), loadReview(selected, token)]);
      }
    });
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><h1>Community Water Intelligence</h1></div>
        <div className="header-actions">
          <label className="account">Pilot account
            <select value={resident} onChange={(event) => { setReports([]); setAlerts([]); setResident(event.target.value); }}>
              {[1, 2, 3].map((index) => <option key={index} value={`resident-${index}`}>Resident {index}</option>)}
            </select>
          </label>
          <button className="primary" onClick={() => openReport()}><span aria-hidden="true">＋</span> Report a water issue</button>
        </div>
      </header>
      <nav aria-label="Workspace">
        {(["Map", "My reports", "Alerts", "Review"] as const).map((item) =>
          <button key={item} aria-current={view === item ? "page" : undefined}
            onClick={() => {
              setView(item); setShowForm(false); setError(""); setNotice("");
              if (item === "My reports") Promise.all([refresh(), loadResident()]).catch((err) => setError(err.message));
            }}>
            {item}{item === "Alerts" && alerts.length > 0 ? ` (${alerts.length})` : ""}
          </button>)}
      </nav>
      {error && <p className="message error" role="alert">{error}</p>}
      {notice && <p className="message" role="status">{notice}</p>}
      {view === "Map" && <>
        <section className="map-overview" aria-labelledby="overview-title">
          <div>
            <p className="eyebrow">Uttar Pradesh · Simulation</p>
            <h2 id="overview-title">Prayagraj water monitor</h2>
          </div>
          <dl className="map-totals">
            <div><dt>Active incidents</dt><dd>{incidents.filter((item) => !["RESOLVED", "DISMISSED"].includes(item.status)).length}</dd></div>
            <div><dt>Unverified reports</dt><dd>{features.reduce((count, item) => count + (item.properties.reports ?? 0), 0)}</dd></div>
            <div><dt>Resolved incidents</dt><dd>{incidents.filter((item) => item.status === "RESOLVED").length}</dd></div>
          </dl>
        </section>
        <div className="map-layout">
        <section className="panel map-panel" aria-label="Prayagraj pilot map">
          <div className="panel-heading"><h2>Locality map</h2>
            <label className="inline">Layer
              <select value={filter} onChange={(event) => setFilter(event.target.value)}>
                <option value="all">All reports</option><option value="active">Active incidents</option>
                <option value="unverified">Unverified reports</option>
              </select>
            </label>
          </div>
          <PilotMap localities={localities} features={features.filter(({ properties }) =>
            filter === "all" || (filter === "active" ? properties.id && properties.status !== "RESOLVED" : !properties.id))}
            onSelect={selectIncident} onLocate={showForm ? (lat, lon) => setPosition([lat, lon]) : undefined}
            location={showForm ? focus : undefined} />
          <div className="legend"><span><i className="river" />CPCB river station</span><span><i className="active" />Active incident</span>
            <span><i className="reviewed" />Resolved incident</span><span><i className="unverified" />Unverified report or pilot locality</span></div>
        </section>
        <aside className="panel side incident-panel">
          {showForm ? <form onSubmit={submit} className="fields">
            <div className="panel-heading"><h2>Report an issue</h2><button type="button" onClick={() => setShowForm(false)}>Close</button></div>
            <label>Locality<select value={area} onChange={(event) => { setArea(event.target.value); setPosition(undefined); }} required>
              {localities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <p className="small">Click the map to set an approximate location. The public pin stays at the locality centre.</p>
            {position && <button type="button" onClick={() => setPosition(undefined)}>Use locality centre</button>}
            <div className="two">
              <label>Issue<select value={category} onChange={(event) => setCategory(event.target.value)}>
                {categories.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Supply<select name="source" defaultValue="unknown">{sources.map((item) => <option key={item}>{item}</option>)}</select></label>
            </div>
            <label>Description<textarea name="description" required minLength={5} maxLength={1000} rows={3} /></label>
            <label>Observed at (your device time)<input type="datetime-local" name="observed" required defaultValue={initialTime()} /></label>
            <label>Supply zone (optional)<input name="zone" maxLength={48} /></label>
            <label>Photo (optional)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp" /></label>
            <label className="check"><input name="opt" type="checkbox" /> Subscribe to alerts for this locality</label>
            <button type="submit" className="primary" disabled={busy}>Submit report</button>
          </form> : <>
            <h2>Incidents</h2>
            <IncidentList incidents={incidents} selected={selected} onSelect={selectIncident} />
            {active && <section className="detail">
              <h3>{active.locality}</h3>
              <p>{active.source === "river sensor" ? "Simulated surface-water monitoring signal" : `${active.households} independent households · ${active.source} supply`}</p>
              <p className="small">Cause and affected supply area are unknown.</p>
              <TimelineList events={timeline} />
            </section>}
            <section className="detail river-devices"><h3>River and lake watch</h3><p className="small">Simulated devices</p>
              {devices.map((device) => {
                const sample = device.samples.at(-1)!;
                return <article key={device.locality_id} className="entry">
                  <strong>{device.station} · {device.river}</strong>
                  <p className="small">{device.flagged ? "Flagged for review" : "No trigger"} · pH {sample.ph} · {sample.turbidity} NTU · {sample.oxygen} mg/L oxygen</p>
                </article>;
              })}
            </section>
          </>}
        </aside>
      </div></>}
      {view === "My reports" && <section className="panel content">
        <h2>My reports</h2>
        {reports.length === 0 && <p>No reports for this pilot resident.</p>}
        {reports.map((report) => {
          const incident = incidents.find((item) => item.id === report.incident_id);
          const others = incident ? Math.max(0, incident.households - 1) : null;
          return <article key={report.id} className="entry"><strong>{report.category}</strong>
            <span className="tag">{readable(report.status)}</span><p>{displayText(report.description)}</p>
            <p className="small">{dateLabel(report.observed_at)} IST · {report.id.slice(0, 8)}</p>
            {report.status === "RESOLVED" && <div className="report-community">
              <strong>Reviewer update</strong>
              <p>{report.resolution_update || "The reviewer closed this incident. No public update was recorded."}</p>
            </div>}
            <div className="report-community">
              {others !== null ? <p><strong>{others} other {others === 1 ? "household" : "households"}</strong> reported a matching issue in {incident?.locality}. The cause is unconfirmed.</p>
                : <p>{report.incident_id ? "This report is linked to a community incident." : "This report hasn’t been grouped into a community incident yet."}</p>}
              {report.incident_id && <button onClick={() => { selectIncident(report.incident_id!); setShowForm(false); setView("Map"); }}>
                View incident timeline
              </button>}
            </div>
          </article>;
        })}
      </section>}
      {view === "Alerts" && <section className="panel content">
        <h2>My alerts</h2>
        <form className="subscription" onSubmit={(event) => {
          event.preventDefault();
          void act(async () => { await api("/alerts/subscription", resident, subscription); await loadResident(); setNotice("Subscription saved."); });
        }}>
          <label>Locality<select value={subscription.locality_id}
            onChange={(event) => setSubscription({ ...subscription, locality_id: event.target.value })}>
            {localities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="check"><input type="checkbox" checked={subscription.opt_in}
            onChange={(event) => setSubscription({ ...subscription, opt_in: event.target.checked })} /> Opt in to locality alerts</label>
          <button disabled={busy}>Save</button>
        </form>
        {alerts.length === 0 && <p>No approved alerts for this pilot resident.</p>}
        {alerts.map((alert) => <article key={alert.id} className="entry"><strong>{alert.locality}</strong>
          <span className="tag">{readable(alert.status)}</span><p>{displayText(alert.message)}</p><p className="small">{alert.why}</p>
          <p className="small">{dateLabel(alert.sent_at)} IST</p>
          <button onClick={() => openReport(alert.category)}>Report a similar issue</button></article>)}
      </section>}
      {view === "Review" && (!token ? <section className="panel content">
        <h2>Reviewer sign-in</h2>
        <p>Enter the local pilot reviewer token.</p>
        <form className="subscription" onSubmit={(event) => {
          event.preventDefault();
          void act(async () => { await api("/admin/documents", tokenInput); setToken(tokenInput); setTokenInput(""); });
        }}>
          <label>Reviewer token<input type="password" value={tokenInput} required onChange={(event) => setTokenInput(event.target.value)} /></label>
          <button className="primary" disabled={busy}>Sign in</button>
        </form>
      </section> : <div className="review-layout">
        <aside className="panel side"><div className="panel-heading"><h2>Review queue</h2>
          <button onClick={() => { setToken(""); setRun(null); setTimeline([]); }}>Sign out</button></div>
          <IncidentList incidents={incidents} selected={selected} onSelect={selectIncident} />
          <button className="detail" disabled={busy} onClick={() => void act(async () => {
            const result = await api<{ created: string[]; news_checked: boolean }>("/admin/river-watch/scan", token, {});
            await refresh();
            if (result.created.length) selectIncident(result.created[0]);
            if (!result.created.length && selected && active?.source === "river sensor") await loadReview(selected, token);
            setNotice(result.created.length ? "River watch draft is ready for review."
              : result.news_checked ? "River watch news check completed. See the investigation for results." : "No new river watch signals.");
          })}>Check river watch</button>
          <form className="fields detail" onSubmit={(event) => {
            event.preventDefault();
            void act(async () => setResults(await api<Evidence[]>(`/documents/search?q=${encodeURIComponent(query)}`)));
          }}>
            <label>Search source PDFs<input value={query} minLength={2} required onChange={(event) => setQuery(event.target.value)} /></label>
            <button disabled={busy}>Search</button>
          </form>
          {results.map((item) => <EvidenceCard key={item.id} item={item} />)}
        </aside>
        <section className="panel content review">
          {active && <>
            <div className="panel-heading"><div><h2>{active.locality}</h2>
              <p>{active.category} · {active.source === "river sensor" ? "Simulated monitoring signal" : `${active.households} participating households`} · {readable(active.status)}</p></div>
              {active.source !== "river sensor" && <button className="primary" disabled={busy || ["RESOLVED", "DISMISSED"].includes(active.status)}
                onClick={investigate}>
                {busy ? "Working…" : "Run Groq investigation"}
              </button>}
            </div>
            {active.source !== "river sensor" && <InvestigationFlow run={run} running={running} />}
            {run && run.status !== "RUNNING" && <section className="detail investigation-result">
              <div className="panel-heading"><h3>Investigation findings</h3>
                <span className="small">{readable(run.status)}{run.error ? ` · ${run.error}` : ""}</span></div>
              <div className="findings-grid">
                <section><h4>What was reported</h4>{run.observations?.map((line) => <p key={line}>{displayText(line)}</p>)}</section>
                <section><h4>What remains unknown</h4>{run.unknowns?.map((line) => <p key={line}>{line}</p>)}</section>
              </div>
              {run.scenario_analysis && <section className="scenario-analysis"><h4>Scenario interpretation</h4><p>{run.scenario_analysis}</p></section>}
              {!!run.checks?.length && <section className="next-checks"><h4>Recommended checks</h4>
                <ol>{run.checks.map((line) => <li key={line}>{line}</li>)}</ol></section>}
              {!!run.evidence?.length && <section className="evidence-section"><h4>Evidence record</h4>
                <div className="evidence-grid">{[...run.evidence].sort((a, b) => Number(!!b.simulated) - Number(!!a.simulated)).map((item) =>
                  <EvidenceCard key={item.id} item={item} selected={run.selected?.includes(item.id)} />)}</div>
              </section>}
              {run.draft && <article className="entry"><strong>Locality alert</strong><span className="tag">{readable(run.draft.status)}</span>
                <p>{displayText(run.draft.message)}</p><p className="small">Audience: opted-in pilot residents in {active.locality}.</p>
                {run.draft.status === "DRAFT" && <div className="actions">
                  <button className="primary" disabled={busy} onClick={() => reviewAction(
                    `/admin/alerts/${run.draft!.id}/approve`, {}, ({ recipients }) => recipients === 0 ? "Alert approved. Nobody is subscribed to this locality yet."
                      : `Alert delivered to ${recipients} opted-in ${recipients === 1 ? "resident" : "residents"}.`)}>Approve and deliver</button>
                  <button disabled={busy || note.trim().length < 5} onClick={() => reviewAction(
                    `/admin/alerts/${run.draft!.id}/reject`, { note }, "Draft rejected.")}>Reject with reason below</button>
                </div>}
              </article>}
            </section>}
            <section className="detail fields">
              <h3>Follow-up</h3><label>Private finding or reason<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} /></label>
              {active.status === "INVESTIGATING" && <label>Resolution update for residents
                <textarea value={resolutionUpdate} maxLength={280} rows={2}
                  onChange={(event) => setResolutionUpdate(event.target.value)} />
                <span className="small">Shown in My reports when you resolve the incident.</span>
              </label>}
              <div className="actions">
                {["FINDING", ...(active.status === "INVESTIGATING" ? ["RESOLVED", "DISMISSED"] :
                  active.status === "RESOLVED" ? ["REOPENED"] :
                  active.status === "DISMISSED" ? [] : ["INVESTIGATING", "DISMISSED"])].map((action) =>
                  <button key={action} disabled={busy || note.trim().length < 5 || (action === "RESOLVED" && resolutionUpdate.trim().length < 5)} onClick={() => reviewAction(
                    `/admin/incidents/${selected}/events`, { action, note, ...(action === "RESOLVED" ? { resolution_update: resolutionUpdate } : {}) }, "Follow-up saved.")}>
                    {{ FINDING: "Record finding", INVESTIGATING: "Start investigation", RESOLVED: "Resolve",
                      REOPENED: "Reopen", DISMISSED: "Dismiss" }[action]}
                  </button>)}
              </div>
              <TimelineList events={timeline} />
            </section>
          </>}
        </section>
      </div>)}
      <footer>Household reports are fictional. Simulated measurements are labelled in each investigation.</footer>
    </main>
  );
}

const workflow = [
  { id: "evidence", title: "Gather evidence", detail: "Local records & weather" },
  { id: "research", title: "Research agent", detail: "Selects relevant sources" },
  { id: "reasoning", title: "Reasoning agent", detail: "Chooses follow-up checks" },
  { id: "alert_writer", title: "Alert writer", detail: "Prepares the draft" },
  { id: "review", title: "Reviewer", detail: "Approves or rejects" },
];

function InvestigationFlow({ run, running }: { run: Run | null; running: boolean }) {
  const failed = run?.status === "FAILED";
  const finished = ["APPROVED", "REJECTED", "SUPERSEDED"].includes(run?.draft?.status ?? "");
  const index = finished || run?.status === "AWAITING_REVIEW" ? 4
    : run?.stage ? workflow.findIndex((step) => step.id === run.stage)
    : running ? 0 : -1;
  const status = finished ? readable(run!.draft!.status)
    : failed ? "Run failed" : index === 4 ? "Awaiting reviewer"
    : index >= 0 ? workflow[index].title : "Ready to run";

  return <section className="workflow" aria-labelledby="workflow-title">
    <div className="panel-heading">
      <h3 id="workflow-title">Alert workflow</h3>
      <span className="workflow-status" role="status">{status}</span>
    </div>
    <ol>
      {workflow.map((step, position) => {
        const state = position < index || (finished && position === index) ? "done"
          : position === index ? failed ? "failed" : "current" : "pending";
        return <li key={step.id} data-state={state} aria-current={state === "current" ? "step" : undefined}>
          <span className="workflow-node" aria-hidden="true">{state === "done" ? "✓" : state === "failed" ? "!" : position + 1}</span>
          <strong>{step.title}</strong>
          <small>{step.detail}</small>
        </li>;
      })}
    </ol>
  </section>;
}

function IncidentList({ incidents, selected, onSelect }: {
  incidents: Incident[]; selected: string; onSelect: (id: string) => void;
}) {
  return <div className="incident-list">{incidents.length === 0 && <p>No clustered incidents.</p>}
    {incidents.map((item) => <button key={item.id} aria-pressed={item.id === selected} onClick={() => onSelect(item.id)}>
      <strong>{item.category}</strong><small data-status={item.status}>{readable(item.status)}</small>
      <span>{item.locality} · {item.source === "river sensor" ? "River watch" : `${item.households} households`}</span>
    </button>)}</div>;
}

function TimelineList({ events }: { events: Timeline }) {
  return <ol className="timeline">{events.map((item, index) =>
    <li key={index}><strong>{readable(item.action)}</strong> <time>{dateLabel(item.date)} IST</time>
      {item.note && <p>{displayText(item.note)}</p>}</li>)}</ol>;
}

function EvidenceCard({ item, selected }: { item: Evidence; selected?: boolean }) {
  return <article className="evidence" data-simulated={item.simulated || undefined}>
    <div className="evidence-heading"><strong>{displayText(item.title)}</strong>
      {item.simulated && <span>Simulated</span>}</div>
    <p className="small">{item.period || (item.date?.length === 10 ? item.date : item.date ? dateLabel(item.date) : "")}
      {item.page ? ` · Page ${item.page}` : ""}{selected ? " · Cited" : ""}</p>
    {item.measurements?.length ? <MeasurementChart readings={item.measurements} />
      : <p>{displayText(item.excerpt)}</p>}
    <p className="small">{item.limitation}</p>
    <div className="actions">{item.url && <a href={item.url} target="_blank" rel="noreferrer">Open evidence</a>}
      {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Original source</a>}</div>
  </article>;
}

function MeasurementChart({ readings }: { readings: NonNullable<Evidence["measurements"]> }) {
  const unit = readings[0].unit;
  const isRain = unit === "mm";
  const step = isRain ? 10 : unit === "NTU" ? 8 : 2;
  const maximum = Math.max(step * 5, Math.ceil(Math.max(...readings.map(({ value }) => value)) / (step * 5)) * step * 5);
  const points = readings.map(({ value }, index) => ({
    x: ((index + 0.5) / readings.length) * 100,
    y: 100 - (value / maximum) * 100,
  }));
  const labels = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });

  return <figure className="measurement-chart">
    <figcaption>{isRain ? "Daily rainfall" : unit === "NTU" ? "Turbidity" : unit === "pH" ? "pH" : "Dissolved oxygen"} <span>({unit})</span></figcaption>
    <div className="chart-body" aria-hidden="true">
      <div className="chart-scale">{[maximum, maximum / 2, 0].map((tick) => <span key={tick}>{tick}</span>)}</div>
      <div className="chart-plot">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" focusable="false">
          {isRain ? points.map(({ x, y }, index) => <rect key={readings[index].label}
            x={x - 7} y={Math.min(y, 99)} width={14} height={Math.max(1, 100 - y)} />)
            : <polyline points={points.map(({ x, y }) => `${x},${y}`).join(" ")} vectorEffect="non-scaling-stroke" />}
        </svg>
        {!isRain && points.map(({ x, y }, index) =>
          <span className="chart-point" key={readings[index].label} style={{ left: `${x}%`, top: `${y}%` }} />)}
      </div>
    </div>
    <dl className="chart-readings">
      {readings.map(({ label, value }) => <div key={label}>
        <dt>{/^\d{4}-\d{2}-\d{2}$/.test(label) ? labels.format(new Date(label)) : label.includes("T") ? new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(label)) : label}</dt>
        <dd>{value} {unit}</dd>
      </div>)}
    </dl>
  </figure>;
}
