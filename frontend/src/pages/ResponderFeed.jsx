import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./responder.css";
import "./responder-shelters.css";
import "./responder-map.css";
import ChatWidget from "../components/chatbot/ChatWidget";
import KeralaMap from "../dashboard-ui/KeralaMap";
import "../dashboard-ui/dashboard.css";

const API_URL = "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("token") || sessionStorage.getItem("token");
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${getToken()}`,
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
  return data;
}

export default function ResponderFeed() {
  const navigate = useNavigate();
  const [coverage, setCoverage] = useState([]);
  const [items, setItems] = useState([]);
  const [resources, setResources] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [shelterRequests, setShelterRequests] = useState([]);
  const [shelterChoices, setShelterChoices] = useState({});
  const [emergencyShelterChoices, setEmergencyShelterChoices] = useState({});
  const [user, setUser] = useState(null);
  const [notes, setNotes] = useState({});
  const [resourceDrafts, setResourceDrafts] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [issuingId, setIssuingId] = useState(null);
  const [activeView, setActiveView] = useState("operations");
  const [mapLayer, setMapLayer] = useState("people");

  const load = useCallback(async () => {
    setError("");
    try {
      const [profile, areas, feed, stock, shelterList, shelterQueue] = await Promise.all([
        request("/api/auth/me"),
        request("/api/help-requests/responder/coverage"),
        request("/api/help-requests/responder/feed"),
        request("/api/responder/resources"),
        request("/api/shelters/responder/all"),
        request("/api/shelters/responder/requests"),
      ]);
      setUser(profile);
      setCoverage(areas);
      setItems(feed);
      setResources(stock);
      setShelters(shelterList);
      setShelterRequests(shelterQueue);
    } catch (err) {
      if (/token|credentials|authorized/i.test(err.message)) {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        navigate("/login", { replace: true });
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  async function toggleAvailability() {
    if (!user) return;
    setBusyId("availability");
    setError("");
    setNotice("");
    try {
      const result = await request("/api/auth/me/availability", {
        method: "PATCH",
        body: JSON.stringify({ is_available: !user.is_available }),
      });
      setUser(current => ({ ...current, is_available: result.is_available }));
      setNotice(result.is_available ? "You are now marked available to admins." : "You are now marked unavailable to admins.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  useEffect(() => {
    load();
    const interval = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      request("/api/help-requests/responder/feed").then(setItems).catch(() => {});
    }, 30000);
    return () => window.clearInterval(interval);
  }, [load]);

  async function claim(item) {
    setBusyId(item.id);
    try { await request(`/api/help-requests/${item.id}/claim`, { method: "POST" }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  }

  async function update(item, status) {
    setBusyId(item.id);
    const params = new URLSearchParams({ status, responder_notes: notes[item.id] || "" });
    try { await request(`/api/help-requests/${item.id}/status?${params}`, { method: "PATCH" }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  }

  function updateResourceDraft(resourceId, key, value) {
    setResourceDrafts(previous => ({
      ...previous,
      [resourceId]: { quantity: "", reason: "", help_request_id: "", ...previous[resourceId], [key]: value },
    }));
  }

  async function issueResource(resource) {
    const draft = resourceDrafts[resource.id] || {};
    if (!draft.quantity || Number(draft.quantity) < 1 || !draft.reason?.trim()) {
      setError("Enter a quantity and reason before changing stock.");
      return;
    }
    setError("");
    setNotice("");
    setIssuingId(resource.id);
    try {
      const result = await request(`/api/responder/resources/${resource.id}/issue`, {
        method: "POST",
        body: JSON.stringify({
          quantity: Number(draft.quantity),
          reason: draft.reason.trim(),
          help_request_id: draft.help_request_id ? Number(draft.help_request_id) : null,
        }),
      });
      setNotice(result.message);
      setResourceDrafts(previous => ({ ...previous, [resource.id]: { quantity: "", reason: "", help_request_id: "" } }));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setIssuingId(null);
    }
  }

  async function shelterDecision(item, status) {
    setBusyId(`shelter-${item.id}`);
    try { await request(`/api/shelters/requests/${item.id}/decision`, { method: "POST", body: JSON.stringify({ status }) }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  }

  async function assignShelter(item) {
    const shelter_id = Number(shelterChoices[item.id]);
    if (!shelter_id) { setError("Choose an in-coverage shelter for this household."); return; }
    setBusyId(`shelter-${item.id}`);
    try { await request(`/api/shelters/requests/${item.id}/assign`, { method: "POST", body: JSON.stringify({ shelter_id }) }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  }

  async function adjustOccupancy(shelter, change) {
    try { await request(`/api/shelters/${shelter.id}/occupancy?change=${change}`, { method: "POST" }); await load(); }
    catch (err) { setError(err.message); }
  }

  async function assignEmergencyShelter(item) {
    const shelter_id = Number(emergencyShelterChoices[item.id]);
    if (!shelter_id) { setError("Choose an in-coverage shelter for this emergency."); return; }
    setBusyId(item.id);
    try { await request(`/api/shelters/help-requests/${item.id}/assign`, { method: "POST", body: JSON.stringify({ shelter_id }) }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  }

  function signOut() {
    localStorage.removeItem("token");
    sessionStorage.removeItem("token");
    localStorage.removeItem("role");
    sessionStorage.removeItem("role");
    navigate("/login", { replace: true });
  }

  const activeRequests = items.filter(item => !["Resolved", "Rejected"].includes(item.status));
  const coverageDistricts = [...new Set(coverage.map(area => area.district).filter(Boolean))];
  const mapDistrict = coverageDistricts[0] || "ALL";
  const mapRequests = activeRequests.filter(item => item.latitude != null && item.longitude != null && item.latitude !== "" && item.longitude !== "" && Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)));
  const unpinnedRequestCount = activeRequests.length - mapRequests.length;
  const urgentUnclaimed = items
    .filter(item => ["Critical", "High"].includes(item.urgency) && !item.assigned_responder_id && !["Resolved", "Rejected"].includes(item.status))
    .sort((a, b) => (a.urgency === b.urgency ? new Date(b.created_at) - new Date(a.created_at) : a.urgency === "Critical" ? -1 : 1));
  const prioritizedItems = [...items].sort((a, b) => {
    const aUrgentUnclaimed = !a.assigned_responder_id && ["Critical", "High"].includes(a.urgency) && !["Resolved", "Rejected"].includes(a.status);
    const bUrgentUnclaimed = !b.assigned_responder_id && ["Critical", "High"].includes(b.urgency) && !["Resolved", "Rejected"].includes(b.status);
    if (aUrgentUnclaimed !== bUrgentUnclaimed) return aUrgentUnclaimed ? -1 : 1;
    const urgencyRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
    if (urgencyRank[a.urgency] !== urgencyRank[b.urgency]) return (urgencyRank[a.urgency] ?? 4) - (urgencyRank[b.urgency] ?? 4);
    return new Date(b.created_at) - new Date(a.created_at);
  });

  return <main className="responder-page">
    <header className="responder-header"><div><span className="responder-kicker">KAAVALAL · FIELD OPERATIONS</span><h1>Responder dashboard</h1><p>Citizen requests in your assigned coverage areas.</p><div className={`responder-availability ${user?.is_available ? "is-available" : ""}`}><span className="availability-indicator"/>{user?.is_available ? "Available to respond" : "Unavailable"}</div></div><div className="responder-header-actions"><button className="availability-toggle" onClick={toggleAvailability} disabled={!user || busyId === "availability"} aria-pressed={Boolean(user?.is_available)}>{busyId === "availability" ? "Updating…" : user?.is_available ? "Set unavailable" : "Set available"}</button><Link to="/dashboard">Public dashboard</Link><button onClick={signOut}>Sign out</button></div></header>
    <section className="coverage-strip"><b>District coverage</b>{coverageDistricts.length ? <>{coverageDistricts.map(district=><span key={district}>All LACs · {district}</span>)}<small>Citizen requests from every constituency in these districts appear here.</small></> : <span>No district coverage is assigned yet. Ask an administrator to set your coverage.</span>}</section>
    {error && <div className="responder-error" role="alert">{error}<button onClick={()=>setError("")}>Dismiss</button></div>}
    {notice && <div className="responder-notice" role="status">{notice}<button onClick={()=>setNotice("")}>Dismiss</button></div>}
    <section className={`responder-urgent-notification ${urgentUnclaimed.length ? "has-urgent" : "is-clear"}`} role="status" aria-live="polite">
      <div className="urgent-notification-heading"><span className="urgent-notification-icon" aria-hidden="true">{urgentUnclaimed.length ? "!" : "✓"}</span><div><strong>{loading ? "Checking urgent requests…" : urgentUnclaimed.length ? `${urgentUnclaimed.length} urgent unclaimed request${urgentUnclaimed.length === 1 ? "" : "s"}` : "No urgent unclaimed requests"}</strong><p>{urgentUnclaimed.length ? "Critical and high urgency reports in your assigned coverage." : "New urgent requests will appear here while this dashboard is open."}</p></div><button onClick={load}>Refresh</button></div>
      {urgentUnclaimed.length > 0 && <div className="urgent-notification-list">{urgentUnclaimed.slice(0, 3).map(item => <article key={`urgent-notice-${item.id}`}><div><span className="urgent-level">{item.urgency}</span><b>{item.emergency_type}</b><small>{item.lac} · {item.district} · {item.people_affected} affected</small></div><button onClick={() => document.getElementById(`responder-request-${item.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}>Review request</button></article>)}</div>}
    </section>
    <nav className="responder-view-tabs" aria-label="Responder dashboard views">
      <button className={activeView === "operations" ? "active" : ""} aria-pressed={activeView === "operations"} onClick={() => setActiveView("operations")}>Operations</button>
      <button className={activeView === "map" ? "active" : ""} aria-pressed={activeView === "map"} onClick={() => setActiveView("map")}>Dashboard map</button>
      <button className={activeView === "resources" ? "active" : ""} aria-pressed={activeView === "resources"} onClick={() => setActiveView("resources")}>Resources</button>
    </nav>
    {activeView === "map" ? <section className="responder-map-panel">
      <div className="responder-feed-heading"><div><h2>Kerala response map</h2><p>District risk overview with operational layers for your coverage areas.</p></div><button onClick={load}>Refresh</button></div>
      <div className="responder-map-toolbar" role="group" aria-label="Map layer">
        {[ ["people", "People"], ["shelters", "Shelters"], ["constituencies", "Constituencies"] ].map(([value, label]) => <button key={value} className={mapLayer === value ? "active" : ""} aria-pressed={mapLayer === value} onClick={() => setMapLayer(value)}>{label}</button>)}
        <span>{mapLayer === "people" ? `${mapRequests.length} active request${mapRequests.length === 1 ? "" : "s"} pinned` : mapLayer === "shelters" ? `${shelters.length} shelter${shelters.length === 1 ? "" : "s"} in view` : "Assembly constituencies"}</span>
      </div>
      {mapLayer === "people" && unpinnedRequestCount > 0 && <p className="responder-map-note">{unpinnedRequestCount} active request{unpinnedRequestCount === 1 ? "" : "s"} {unpinnedRequestCount === 1 ? "has" : "have"} no coordinates and cannot be pinned.</p>}
      <div className="responder-map-canvas dashboard-ui">
        <KeralaMap selectedDistrict={mapDistrict} districts={[]} selectedLayer="Overall Risk" showConstituencies={mapLayer === "constituencies"} lacs={[]} shelters={shelters} showShelters={mapLayer === "shelters"} helpRequests={mapRequests} showHelpRequests={mapLayer === "people"} onClaimHelpRequest={claim} />
      </div>
    </section> : activeView === "resources" ? <section className="responder-resources responder-resource-module">
      <div className="responder-feed-heading"><div><h2>District relief resources</h2><p>Stock allocated by admins for your assigned districts. Use − to issue supplies; only admins can replenish stock.</p></div><button onClick={load}>Refresh</button></div>
      {loading ? <p className="responder-empty">Loading district inventory…</p> : !resources.length ? <p className="responder-empty">No relief supplies are currently available in your covered districts.</p> : <div className="responder-resource-grid">{resources.map(resource=>{
        const draft=resourceDrafts[resource.id]||{quantity:"",reason:"",help_request_id:""};
        const linkedRequests=items.filter(item=>item.assigned_responder_id===user?.id&&!['Resolved','Rejected'].includes(item.status)&&item.district?.toLowerCase()===resource.district?.toLowerCase());
        return <article className="responder-resource-card" key={resource.id}>
          <div className="responder-card-top"><div><span className="responder-loc">{resource.district} · {resource.category}</span><h3>{resource.name}</h3></div><span className="responder-stock-count">{resource.quantity_available} {resource.unit}</span></div>
          <p className="responder-stock-note">Current shared district balance · Admin-managed allocation.</p>
          <div className="responder-resource-form">
            <label>Quantity change<input type="number" min="1" value={draft.quantity} onChange={e=>updateResourceDraft(resource.id,"quantity",e.target.value)} placeholder="Enter a quantity"/></label>
            <label>Reason<input value={draft.reason} onChange={e=>updateResourceDraft(resource.id,"reason",e.target.value)} placeholder="Describe the operational need"/></label>
            {linkedRequests.length>0&&<label>Link to assigned help request (optional)<select value={draft.help_request_id} onChange={e=>updateResourceDraft(resource.id,"help_request_id",e.target.value)}><option value="">No linked request</option>{linkedRequests.map(item=><option key={item.id} value={item.id}>Request #{item.id} · {item.emergency_type}</option>)}</select></label>}
            <div className="responder-resource-controls"><button className="resource-issue" disabled={issuingId===resource.id||resource.quantity_available<1} onClick={()=>issueResource(resource)}>{issuingId===resource.id?"Saving…":"− Issue supplies"}</button></div>
          </div>
        </article>;
      })}</div>}
    </section> : <>
    <section className="responder-resources shelter-ops">
      <div className="responder-feed-heading"><div><h2>Shelter requests</h2><p>Requests are routed by the preferred shelter’s LAC. Approve before assigning a bed.</p></div><span>{shelterRequests.filter(r=>r.status==="Pending").length} awaiting review</span></div>
      {loading ? <p className="responder-empty">Loading shelter requests…</p> : !shelterRequests.length ? <p className="responder-empty">No shelter requests in your coverage areas.</p> : <div className="responder-cards">{shelterRequests.map(item=><article className="responder-card" key={`shelter-request-${item.id}`}><div className="responder-card-top"><div><span className="responder-loc">{item.lac} · {item.district}</span><h3>{item.household_name} · {item.people_count} people</h3></div><span className="responder-status">{item.status}</span></div><p>Preferred: <b>{item.preferred_shelter?.name}</b> · Contact {item.phone} · Aadhaar ending {item.aadhaar_last4}</p>{item.special_needs&&<p><b>Needs:</b> {item.special_needs}</p>}{item.assigned_shelter&&<p>Assigned to <b>{item.assigned_shelter.name}</b></p>}{item.status==="Pending"&&<div className="responder-card-footer"><button disabled={busyId===`shelter-${item.id}`} onClick={()=>shelterDecision(item,"Approved")}>Approve request</button><button className="shelter-reject" disabled={busyId===`shelter-${item.id}`} onClick={()=>shelterDecision(item,"Rejected")}>Reject</button></div>}{["Approved","Assigned"].includes(item.status)&&<div className="responder-card-footer"><select aria-label="Choose shelter in your jurisdiction" value={shelterChoices[item.id]||item.assigned_shelter?.id||""} onChange={e=>setShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose an in-coverage shelter</option>{shelters.filter(s=>s.can_assign&&s.available+(s.id===item.assigned_shelter?.id?item.people_count:0)>=item.people_count).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} spaces</option>)}</select><button disabled={busyId===`shelter-${item.id}`} onClick={()=>assignShelter(item)}>{item.assigned_shelter?"Update assignment":"Assign shelter"}</button></div>}</article>)}</div>}
    </section>
    <section className="responder-resources shelter-ops"><div className="responder-feed-heading"><div><h2>Shelter directory</h2><p>All active shelters are visible. Occupancy can only be changed in your assigned areas.</p></div></div><div className="responder-resource-grid">{shelters.map(s=><article className="responder-resource-card" key={`shelter-${s.id}`}><div className="responder-card-top"><div><span className="responder-loc">{s.district} · {s.lac}</span><h3>{s.name}</h3></div><span className="responder-stock-count">{s.occupied}/{s.capacity}</span></div><p>{s.building_type} · {s.address}<br/>{s.available} spaces available</p>{s.can_assign?<div className="shelter-counter"><button disabled={s.occupied<=0} onClick={()=>adjustOccupancy(s,-1)} aria-label={`Remove one person from ${s.name}`}>−</button><span>Update headcount</span><button disabled={s.occupied>=s.capacity} onClick={()=>adjustOccupancy(s,1)} aria-label={`Add one person to ${s.name}`}>+</button></div>:<small>Outside your assigned jurisdiction</small>}</article>)}</div></section>
    <div className="responder-feed-heading"><div><h2>Help requests</h2><p>{items.length} request{items.length===1?"":"s"} in your area</p></div><button onClick={load}>Refresh</button></div>
    {loading ? <p className="responder-empty">Loading requests…</p> : !prioritizedItems.length ? <p className="responder-empty">There are no citizen requests in your coverage areas.</p> : <div className="responder-cards">{prioritizedItems.map(item=>{
      const owned = item.assigned_responder_id === user?.id;
      const closed = ["Resolved", "Rejected"].includes(item.status);
      return <article className="responder-card" id={`responder-request-${item.id}`} key={item.id}>
        <div className="responder-card-top"><div><span className="responder-loc">{item.lac} · {item.district}</span><h3>{item.emergency_type}</h3></div><span className={`responder-status ${item.urgency.toLowerCase()}`}>{item.urgency} · {item.status}</span></div>
        <p>{item.situation_description}</p>
        <div className="responder-meta"><span>People affected: <b>{item.people_affected}</b></span><span>Location: <b>{item.location_description}</b></span><span>Submitted: <b>{new Date(item.created_at).toLocaleString()}</b></span></div>
        {item.special_assistance&&<p className="responder-assistance"><b>Special assistance:</b> {item.special_assistance}</p>}
        {item.shelter_id&&<p className="responder-assistance"><b>Assigned shelter:</b> {shelters.find(s=>s.id===item.shelter_id)?.name||`Shelter #${item.shelter_id}`}</p>}
        {owned&&!closed&&<div className="responder-card-footer emergency-shelter-assignment"><select aria-label="Assign this emergency to a shelter" value={emergencyShelterChoices[item.id]||item.shelter_id||""} onChange={e=>setEmergencyShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Assign household to an in-coverage shelter</option>{shelters.filter(s=>s.can_assign&&s.available+(s.id===item.shelter_id?item.people_affected:0)>=item.people_affected).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} spaces</option>)}</select><button disabled={busyId===item.id} onClick={()=>assignEmergencyShelter(item)}>{item.shelter_id?"Change shelter":"Assign shelter"}</button></div>}
        {owned&&!closed&&<div className="responder-actions"><label>Response notes<textarea value={notes[item.id]??item.responder_notes??""} onChange={e=>setNotes(prev=>({...prev,[item.id]:e.target.value}))} placeholder="Share an update with the citizen"/><small className="responder-note-hint">Saved notes appear in the citizen’s request tracker.</small><button className="responder-save-note" disabled={busyId===item.id||(notes[item.id]??item.responder_notes??"")===(item.responder_notes??"")} onClick={()=>update(item,item.status)}>{busyId===item.id?"Saving…":"Save update"}</button></label><label>Update status<select value={item.status} onChange={e=>update(item,e.target.value)} disabled={busyId===item.id}>{["Assigned","In Progress","Resolved","Rejected"].map(status=><option key={status}>{status}</option>)}</select></label></div>}
        {!closed&&<div className="responder-card-footer">{item.assigned_responder_id ? <span>{owned?"Assigned to you":"Already assigned to another responder"}</span> : <button disabled={busyId===item.id} onClick={()=>claim(item)}>{busyId===item.id?"Claiming…":"Claim request"}</button>}</div>}
      </article>;
    })}</div>}
    </>}
    <ChatWidget district={coverage[0]?.district || null} page="responder" />
  </main>;
}
