import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./responder.css";
import "./responder-shelters.css";
import "./responder-map.css";
import ChatWidget from "../components/chatbot/ChatWidget";
import HelpRequestConversation from "../components/HelpRequestConversation";
import KeralaMap from "../dashboard-ui/KeralaMap";
import "../dashboard-ui/dashboard.css";
import "./responder-console.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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

function ShelterRequestPhoto({ requestId }) {
  const [photoUrl, setPhotoUrl] = useState("");
  const [photoError, setPhotoError] = useState("");
  async function togglePhoto() {
    if (photoUrl) { URL.revokeObjectURL(photoUrl); setPhotoUrl(""); return; }
    setPhotoError("");
    try {
      const response = await fetch(`${API_URL}/api/shelters/requests/${requestId}/id-photo`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(result.detail || "Could not open the ID photo."); }
      setPhotoUrl(URL.createObjectURL(await response.blob()));
    } catch (err) { setPhotoError(err.message); }
  }
  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);
  return <div className="shelter-id-photo"><button type="button" onClick={togglePhoto}>{photoUrl ? "Hide ID photo" : "View ID photo"}</button>{photoError && <small role="alert">{photoError}</small>}{photoUrl && <img src={photoUrl} alt={`Identification photo for shelter request ${requestId}`} />}</div>;
}
export default function ResponderFeed() {
  const navigate = useNavigate();
  const [coverage, setCoverage] = useState([]);
  const [items, setItems] = useState([]);
  const [resources, setResources] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [shelterRequests, setShelterRequests] = useState([]);
  const [shelterChoices, setShelterChoices] = useState({});
  const [occupancyAmounts, setOccupancyAmounts] = useState({});
  const [emergencyShelterChoices, setEmergencyShelterChoices] = useState({});
  const [user, setUser] = useState(null);
  const [notes, setNotes] = useState({});
  const [resourceDrafts, setResourceDrafts] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [issuingId, setIssuingId] = useState(null);
  const [activeView, setActiveView] = useState("overview");
  const [mapLayer, setMapLayer] = useState("people");
  const [openConversationId, setOpenConversationId] = useState(null);
  const [incidentQuery, setIncidentQuery] = useState("");
  const [incidentStatus, setIncidentStatus] = useState("");
  const [incidentUrgency, setIncidentUrgency] = useState("");

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
      Promise.all([request("/api/help-requests/responder/feed"), request("/api/shelters/responder/all"), request("/api/shelters/responder/requests")])
        .then(([feed, shelterList, shelterQueue]) => { setItems(feed); setShelters(shelterList); setShelterRequests(shelterQueue); })
        .catch(() => {});
    }, 15000);
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
    const params = new URLSearchParams({ status, responder_notes: notes[item.id] ?? item.responder_notes ?? "" });
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
    const shelter_id = Number(shelterChoices[item.id] || item.preferred_shelter?.id || 0);
    if (status === "Approved" && !shelter_id) { setError("Choose a shelter with enough capacity before accepting this request."); return; }
    setBusyId(`shelter-${item.id}`);
    try { await request(`/api/shelters/requests/${item.id}/decision`, { method: "POST", body: JSON.stringify({ status, ...(status === "Approved" ? { shelter_id } : {}) }) }); await load(); }
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

  async function adjustOccupancy(shelter, direction) {
    const quantity = Number(occupancyAmounts[shelter.id] || 1);
    const change = direction * quantity;
    if (!Number.isInteger(quantity) || quantity < 1 || (direction > 0 && quantity > shelter.available) || (direction < 0 && quantity > shelter.occupied)) { setError("Enter a valid headcount within the shelter's remaining capacity."); return; }
    const busyKey = `capacity-${shelter.id}`;
    setBusyId(busyKey);
    try { await request(`/api/shelters/${shelter.id}/occupancy?change=${change}`, { method: "POST" }); setOccupancyAmounts(v => ({ ...v, [shelter.id]: "1" })); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusyId(null); }
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

  const incidentRows = prioritizedItems.filter(item => {
    const query = incidentQuery.trim().toLowerCase();
    const searchable = `${item.id} ${item.emergency_type} ${item.district} ${item.lac} ${item.situation_description}`.toLowerCase();
    return (!incidentStatus || item.status === incidentStatus)
      && (!incidentUrgency || item.urgency === incidentUrgency)
      && (!query || searchable.includes(query));
  });
  const assignedActive = activeRequests.filter(item => item.assigned_responder_id === user?.id);
  const pendingShelters = shelterRequests.filter(item => item.status === "Pending").length;
  const lowStockCount = resources.filter(item => Number(item.quantity_available) <= Number(item.low_stock_threshold || 0)).length;

  function renderIncidentCard(item) {
    const owned = item.assigned_responder_id === user?.id;
    const closed = ["Resolved", "Rejected"].includes(item.status);
    return <article className="responder-card" id={`responder-request-${item.id}`} key={item.id}>
      <div className="responder-card-top"><div><span className="responder-loc">HELP-{item.id} · {item.lac} · {item.district}</span><h3>{item.emergency_type}</h3></div><span className={`responder-status ${item.urgency.toLowerCase()}`}>{item.urgency} · {item.status}</span></div>
      <p>{item.situation_description}</p>
      <div className="responder-meta"><span>People affected: <b>{item.people_affected}</b></span><span>Location: <b>{item.location_description}</b></span><span>Submitted: <b>{new Date(item.created_at).toLocaleString()}</b></span></div>
      {item.special_assistance&&<p className="responder-assistance"><b>Special assistance:</b> {item.special_assistance}</p>}
      {item.shelter_id&&<p className="responder-assistance"><b>Assigned shelter:</b> {shelters.find(s=>s.id===item.shelter_id)?.name||`Shelter #${item.shelter_id}`}</p>}
      {owned&&!closed&&<div className="responder-card-footer emergency-shelter-assignment"><select aria-label="Assign this emergency to a shelter" value={emergencyShelterChoices[item.id]||item.shelter_id||""} onChange={e=>setEmergencyShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Assign household to an in-coverage shelter</option>{shelters.filter(s=>s.is_active&&s.can_assign&&s.available+(s.id===item.shelter_id?item.people_affected:0)>=item.people_affected).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} spaces</option>)}</select><button disabled={busyId===item.id} onClick={()=>assignEmergencyShelter(item)}>{item.shelter_id?"Change shelter":"Assign shelter"}</button></div>}
      {owned&&!closed&&<div className="responder-actions"><label>Response notes<textarea value={notes[item.id]??item.responder_notes??""} onChange={e=>setNotes(prev=>({...prev,[item.id]:e.target.value}))} placeholder="Share an update with the citizen"/><small className="responder-note-hint">Saved notes appear in the citizen’s request tracker.</small><button className="responder-save-note" disabled={busyId===item.id||(notes[item.id]??item.responder_notes??"")===(item.responder_notes??"")} onClick={()=>update(item,item.status)}>{busyId===item.id?"Saving…":"Save update"}</button></label><label>Update status<select value={item.status} onChange={e=>update(item,e.target.value)} disabled={busyId===item.id}>{["Assigned","In Progress","Resolved","Rejected"].map(status=><option key={status}>{status}</option>)}</select></label></div>}
      {owned&&<><button className="responder-conversation-toggle" type="button" onClick={()=>setOpenConversationId(openConversationId===item.id?null:item.id)}>{openConversationId===item.id?"Close conversation":"Open citizen conversation"}</button>{openConversationId===item.id&&<HelpRequestConversation requestId={item.id} role="responder" closed={closed}/>}</>}
      {!closed&&<div className="responder-card-footer">{item.assigned_responder_id ? <span>{owned?"Assigned to you":"Assigned to another responder"}</span> : <button disabled={busyId===item.id} onClick={()=>claim(item)}>{busyId===item.id?"Claiming…":"Claim report"}</button>}</div>}
    </article>;
  }

  const renderShelterOperations = <>
    <section className="responder-resources shelter-ops">
      <div className="responder-feed-heading"><div><h2>Shelter requests</h2><p>Review requests and coordinate available beds in your coverage area.</p></div><span>{pendingShelters} awaiting review</span></div>
      {loading ? <p className="responder-empty">Loading shelter requests…</p> : !shelterRequests.length ? <p className="responder-empty">No shelter requests in your coverage areas.</p> : <div className="responder-cards">{shelterRequests.map(item=><article className="responder-card" key={`shelter-request-${item.id}`}><div className="responder-card-top"><div><span className="responder-loc">{item.lac} · {item.district}</span><h3>{item.household_name} · {item.people_count} people</h3></div><span className="responder-status">{item.status}</span></div><p>Preferred: <b>{item.preferred_shelter?.name}</b> · Contact {item.phone} · Aadhaar ending {item.aadhaar_last4}</p>{item.citizen_location&&<p><b>Request location:</b> {item.citizen_location}{item.latitude&&item.longitude&&<> · <a href={`https://www.google.com/maps?q=${item.latitude},${item.longitude}`} target="_blank" rel="noreferrer">Open citizen location ↗</a></>}</p>}{item.reason&&<p><b>Reason:</b> {item.reason}</p>}{item.id_photo_available&&<ShelterRequestPhoto requestId={item.id}/>}{item.special_needs&&<p><b>Needs:</b> {item.special_needs}</p>}{item.assigned_shelter&&<p>Assigned to <b>{item.assigned_shelter.name}</b> · Capacity {item.assigned_shelter.occupied}/{item.assigned_shelter.capacity} · <a href={`https://www.google.com/maps?q=${item.assigned_shelter.latitude},${item.assigned_shelter.longitude}`} target="_blank" rel="noreferrer">Open shelter map ↗</a></p>}{item.status==="Pending"&&<div className="responder-card-footer"><select aria-label="Choose a shelter for this household" value={shelterChoices[item.id]||item.preferred_shelter?.id||""} onChange={e=>setShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose an in-coverage shelter</option>{shelters.filter(s=>s.is_active&&s.can_assign&&s.available>=item.people_count).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available}/{s.capacity} spaces</option>)}</select><button disabled={busyId===`shelter-${item.id}`||!shelters.some(s=>s.id===Number(shelterChoices[item.id]||item.preferred_shelter?.id)&&s.is_active&&s.can_assign&&s.available>=item.people_count)} onClick={()=>shelterDecision(item,"Approved")}>Accept and assign</button><button className="shelter-reject" disabled={busyId===`shelter-${item.id}`} onClick={()=>shelterDecision(item,"Rejected")}>Reject</button></div>}{["Approved","Assigned"].includes(item.status)&&<div className="responder-card-footer"><select aria-label="Choose shelter in your jurisdiction" value={shelterChoices[item.id]||item.assigned_shelter?.id||""} onChange={e=>setShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose an in-coverage shelter</option>{shelters.filter(s=>s.is_active&&s.can_assign&&s.available+(s.id===item.assigned_shelter?.id?item.people_count:0)>=item.people_count).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} spaces</option>)}</select><button disabled={busyId===`shelter-${item.id}`} onClick={()=>assignShelter(item)}>{item.assigned_shelter?"Update assignment":"Assign shelter"}</button></div>}</article>)}</div>}
    </section>
    <section className="responder-resources shelter-ops"><div className="responder-feed-heading"><div><h2>Shelter directory</h2><p>Capacity and occupancy in your operational area.</p></div></div><div className="responder-resource-grid">{shelters.map(s=><article className="responder-resource-card" key={`shelter-${s.id}`}><div className="responder-card-top"><div><span className="responder-loc">{s.district} · {s.lac}</span><h3>{s.name}</h3></div><span className="responder-stock-count">{s.is_active?"Active":"Inactive"} · {s.occupied}/{s.capacity}</span></div><p>{s.building_type} · {s.address}<br/>{s.available} spaces available</p>{s.can_assign?<div className="shelter-counter"><label>People to update<input type="number" min="1" max={s.capacity} value={occupancyAmounts[s.id]??"1"} onChange={e=>setOccupancyAmounts(v=>({...v,[s.id]:e.target.value}))}/></label><button disabled={busyId===`capacity-${s.id}`||s.occupied<=0} onClick={()=>adjustOccupancy(s,-1)} aria-label={`Remove people from ${s.name}`}>Remove</button><button disabled={busyId===`capacity-${s.id}`||!s.is_active||s.occupied>=s.capacity} onClick={()=>adjustOccupancy(s,1)} aria-label={`Add people to ${s.name}`}>Add people</button></div>:<small>Outside your assigned jurisdiction</small>}</article>)}</div></section>
  </>;

  const renderResources = <section className="responder-resources responder-resource-module">
    <div className="responder-feed-heading"><div><h2>District relief resources</h2><p>Issue supplies for an operational need. Replenishment is managed by administrators.</p></div><button onClick={load}>Refresh</button></div>
    {loading ? <p className="responder-empty">Loading district inventory…</p> : !resources.length ? <p className="responder-empty">No relief supplies are currently available in your covered districts.</p> : <div className="responder-resource-grid">{resources.map(resource=>{
      const draft=resourceDrafts[resource.id]||{quantity:"",reason:"",help_request_id:""};
      const linkedRequests=items.filter(item=>item.assigned_responder_id===user?.id&&!['Resolved','Rejected'].includes(item.status)&&item.district?.toLowerCase()===resource.district?.toLowerCase());
      return <article className="responder-resource-card" key={resource.id}>
        <div className="responder-card-top"><div><span className="responder-loc">{resource.district} · {resource.category}</span><h3>{resource.name}</h3></div><span className="responder-stock-count">{resource.quantity_available} {resource.unit}</span></div>
        <p className="responder-stock-note">{Number(resource.quantity_available)<=Number(resource.low_stock_threshold||0)?"Low stock · Flag this item to an administrator.":"Available for response-team operations."}</p>
        <div className="responder-resource-form"><label>Quantity to issue<input type="number" min="1" max={resource.quantity_available} value={draft.quantity} onChange={e=>updateResourceDraft(resource.id,"quantity",e.target.value)} placeholder="Enter a quantity"/></label><label>Reason<input value={draft.reason} onChange={e=>updateResourceDraft(resource.id,"reason",e.target.value)} placeholder="Describe the operational need"/></label>{linkedRequests.length>0&&<label>Link to assigned report (optional)<select value={draft.help_request_id} onChange={e=>updateResourceDraft(resource.id,"help_request_id",e.target.value)}><option value="">No linked report</option>{linkedRequests.map(item=><option key={item.id} value={item.id}>HELP-{item.id} · {item.emergency_type}</option>)}</select></label>}<div className="responder-resource-controls"><button className="resource-issue" disabled={issuingId===resource.id||resource.quantity_available<1} onClick={()=>issueResource(resource)}>{issuingId===resource.id?"Saving…":"Issue supplies"}</button></div></div>
      </article>;
    })}</div>}
  </section>;

  const renderMap = <section className="responder-map-panel">
    <div className="responder-feed-heading"><div><h2>Response map</h2><p>Inspect active requests and shelters within your coverage areas.</p></div><button onClick={load}>Refresh</button></div>
    <div className="responder-map-toolbar" role="group" aria-label="Map layer">{[["people","Active reports"],["shelters","Shelters"],["constituencies","Constituencies"]].map(([value,label])=><button key={value} className={mapLayer===value?"active":""} aria-pressed={mapLayer===value} onClick={()=>setMapLayer(value)}>{label}</button>)}<span>{mapLayer==="people"?`${mapRequests.length} reports mapped`:mapLayer==="shelters"?`${shelters.length} shelters in view`:"Assembly constituencies"}</span></div>
    {mapLayer==="people"&&unpinnedRequestCount>0&&<p className="responder-map-note">{unpinnedRequestCount} active reports don’t have coordinates and can’t be pinned.</p>}
    <div className="responder-map-canvas dashboard-ui"><KeralaMap selectedDistrict={mapDistrict} districts={[]} selectedLayer="Overall Risk" showConstituencies={mapLayer==="constituencies"} lacs={[]} shelters={shelters} showShelters={mapLayer==="shelters"} helpRequests={mapRequests} showHelpRequests={mapLayer==="people"} onClaimHelpRequest={claim}/></div>
  </section>;

  const navItems = [
    ["overview", "Overview", "◫", null],
    ["incidents", "Incident reports", "⌖", activeRequests.length],
    ["shelters", "Shelter operations", "⌂", pendingShelters],
    ["resources", "Relief resources", "▤", resources.length],
    ["map", "Response map", "⌖", null],
  ];

  return <main className="responder-page responder-console">
    <aside className="responder-sidebar">
      <div className="responder-brand"><span className="responder-brand-mark">K</span><div><b>KAAVALAL</b><small>FIELD OPERATIONS</small></div></div>
      <div className="responder-sidebar-label">RESPONSE CONSOLE</div>
      <nav className="responder-console-nav" aria-label="Responder console">
        {navItems.map(([view,label,icon,count])=><button key={view} className={activeView===view?"active":""} aria-current={activeView===view?"page":undefined} onClick={()=>setActiveView(view)}><span className="responder-nav-icon">{icon}</span><span>{label}</span>{count>0&&<small>{count}</small>}</button>)}
      </nav>
      <div className="responder-sidebar-coverage"><span>YOUR COVERAGE</span>{coverageDistricts.length?coverageDistricts.map(district=><b key={district}>{district}</b>):<p>No district assigned</p>}</div>
      <div className="responder-sidebar-user"><span className="responder-user-avatar">{user?.full_name?.slice(0,1)?.toUpperCase()||"R"}</span><div><b>{user?.full_name||"Responder"}</b><small>{user?.role||"Field responder"}</small></div></div>
    </aside>
    <div className="responder-workspace">
      <header className="responder-header">
        <div><span className="responder-kicker">KAAVALAL · FIELD OPERATIONS</span><h1>Responder console</h1><p>Coordinate reports, shelters, and local resources.</p></div>
        <div className="responder-header-actions"><div className={`responder-availability ${user?.is_available?"is-available":""}`}><span className="availability-indicator"/>{user?.is_available?"Available":"Unavailable"}</div><button className="availability-toggle" onClick={toggleAvailability} disabled={!user||busyId==="availability"} aria-pressed={Boolean(user?.is_available)}>{busyId==="availability"?"Updating…":user?.is_available?"Set unavailable":"Set available"}</button><button className="responder-signout" onClick={signOut}>Sign out</button></div>
      </header>
      <section className="responder-content">
        {error&&<div className="responder-error" role="alert">{error}<button onClick={()=>setError("")}>Dismiss</button></div>}
        {notice&&<div className="responder-notice" role="status">{notice}<button onClick={()=>setNotice("")}>Dismiss</button></div>}
        {activeView==="overview"&&<>
          <div className="responder-page-heading"><div><span className="responder-kicker">LIVE OPERATIONS</span><h2>Good day{user?.full_name?`, ${user.full_name.split(" ")[0]}`:""}</h2><p>Here’s the current response picture for your districts.</p></div><button className="responder-refresh" onClick={load} disabled={loading}>{loading?"Refreshing…":"Refresh console"}</button></div>
          <div className="coverage-strip"><b>Coverage</b>{coverage.length?coverage.map((area,index)=><span key={`${area.district}-${area.lac}-${index}`}>{area.lac} · {area.district}</span>):<span>No coverage assigned. Ask an administrator to set your areas.</span>}</div>
          <div className="responder-stat-grid"><button onClick={()=>setActiveView("incidents")}><span>Open reports</span><b>{activeRequests.length}</b><small>in your covered districts</small></button><button className={urgentUnclaimed.length?"is-alert":""} onClick={()=>setActiveView("incidents")}><span>Urgent unclaimed</span><b>{urgentUnclaimed.length}</b><small>critical or high urgency</small></button><button onClick={()=>setActiveView("incidents")}><span>Assigned to you</span><b>{assignedActive.length}</b><small>active reports</small></button><button onClick={()=>setActiveView("shelters")}><span>Shelter reviews</span><b>{pendingShelters}</b><small>awaiting a decision</small></button><button onClick={()=>setActiveView("resources")}><span>Low-stock items</span><b>{lowStockCount}</b><small>at or below threshold</small></button></div>
          <div className="responder-overview-grid">
            <section className={`responder-urgent-notification ${urgentUnclaimed.length?"has-urgent":"is-clear"}`}><div className="urgent-notification-heading"><span className="urgent-notification-icon">{urgentUnclaimed.length?"!":"✓"}</span><div><strong>{urgentUnclaimed.length?`${urgentUnclaimed.length} urgent report${urgentUnclaimed.length===1?"":"s"} need attention`:"No urgent unclaimed reports"}</strong><p>Critical and high priority reports in your coverage.</p></div><button onClick={()=>setActiveView("incidents")}>Open queue</button></div>{urgentUnclaimed.slice(0,4).map(item=><article className="responder-urgent-row" key={item.id}><span>{item.urgency}</span><div><b>{item.emergency_type}</b><small>HELP-{item.id} · {item.lac}, {item.district}</small></div><button onClick={()=>setActiveView("incidents")}>Review</button></article>)}</section>
            <section className="responder-overview-panel"><div className="responder-panel-heading"><div><h3>My active assignments</h3><p>Reports currently assigned to you</p></div><button onClick={()=>setActiveView("incidents")}>View all</button></div>{assignedActive.slice(0,5).map(item=><button className="responder-assignment-row" key={item.id} onClick={()=>setActiveView("incidents")}><span className={`assignment-dot ${item.urgency.toLowerCase()}`}/><span><b>HELP-{item.id} · {item.emergency_type}</b><small>{item.lac} · {item.district}</small></span><strong>{item.status}</strong></button>)}{!assignedActive.length&&<p className="responder-empty-inline">No active reports assigned to you.</p>}</section>
          </div>
        </>}
        {activeView==="incidents"&&<>
          <div className="responder-page-heading"><div><span className="responder-kicker">CITIZEN REPORTS</span><h2>Incident response</h2><p>Claim a report to coordinate directly with the citizen and update progress.</p></div><button className="responder-refresh" onClick={load} disabled={loading}>{loading?"Refreshing…":"Refresh reports"}</button></div>
          <section className="responder-urgent-notification has-urgent"><div className="urgent-notification-heading"><span className="urgent-notification-icon">!</span><div><strong>{urgentUnclaimed.length?`${urgentUnclaimed.length} urgent unclaimed`:"No urgent unclaimed reports"}</strong><p>Reports are shared with responders assigned to the same district.</p></div></div></section>
          <div className="responder-list-toolbar"><label><span>Search reports</span><input value={incidentQuery} onChange={event=>setIncidentQuery(event.target.value)} placeholder="ID, incident, district or LAC"/></label><label><span>Status</span><select value={incidentStatus} onChange={event=>setIncidentStatus(event.target.value)}><option value="">All statuses</option>{["Submitted","Under Review","Assigned","In Progress","Resolved","Rejected"].map(status=><option key={status}>{status}</option>)}</select></label><label><span>Urgency</span><select value={incidentUrgency} onChange={event=>setIncidentUrgency(event.target.value)}><option value="">All urgency</option>{["Critical","High","Medium","Low"].map(value=><option key={value}>{value}</option>)}</select></label><strong>{incidentRows.length} reports</strong></div>
          {loading&&!items.length?<p className="responder-empty">Loading reports…</p>:incidentRows.length?<div className="responder-cards">{incidentRows.map(renderIncidentCard)}</div>:<p className="responder-empty">No reports match these filters.</p>}
        </>}
        {activeView==="shelters"&&<><div className="responder-page-heading"><div><span className="responder-kicker">LOCAL ACCOMMODATION</span><h2>Shelter operations</h2><p>Review household requests and coordinate available capacity.</p></div><button className="responder-refresh" onClick={load}>Refresh shelters</button></div>{renderShelterOperations}</>}
        {activeView==="resources"&&<><div className="responder-page-heading"><div><span className="responder-kicker">DISTRICT INVENTORY</span><h2>Relief resources</h2><p>Issue supplies with a recorded reason and optional report link.</p></div></div>{renderResources}</>}
        {activeView==="map"&&<><div className="responder-page-heading"><div><span className="responder-kicker">GEOGRAPHIC OPERATIONS</span><h2>Response map</h2><p>Review requests, shelters, and constituency boundaries.</p></div></div>{renderMap}</>}
      </section>
      <footer className="responder-console-footer"><span>KAAVALAL FIELD OPERATIONS</span><span>Updates automatically while this console is open</span></footer>
    </div>
    <ChatWidget district={coverage[0]?.district||null} page="responder" />
  </main>;
}
