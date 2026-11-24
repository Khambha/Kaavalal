import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./responder.css";
import "./responder-shelters.css";
import "./responder-map.css";
import ChatWidget from "../components/chatbot/ChatWidget";
import { clearToken, getToken } from "../services/auth";
import HelpRequestConversation from "../components/HelpRequestConversation";
import KeralaMap from "../dashboard-ui/KeralaMap";
import "../dashboard-ui/dashboard.css";
import "./responder-console.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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
  const [resourceRequests, setResourceRequests] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [otherShelterDistrict, setOtherShelterDistrict] = useState("");
  const [shelterRequests, setShelterRequests] = useState([]);
  const [shelterWorkspaceView, setShelterWorkspaceView] = useState("requests");
  const [shelterChoices, setShelterChoices] = useState({});
  const [occupancyAmounts, setOccupancyAmounts] = useState({});
  const [emergencyShelterChoices, setEmergencyShelterChoices] = useState({});
  const [user, setUser] = useState(null);
  const [notes, setNotes] = useState({});
  const [resourceRequestDraft, setResourceRequestDraft] = useState({ item_choice: "", custom_item_name: "", category: "Additional", unit: "units", district: "", quantity: "1", reason: "", priority: "Standard", help_request_id: "", latitude: "", longitude: "", lines: [] });
  const [returnAmounts, setReturnAmounts] = useState({});
  const [returnConditions, setReturnConditions] = useState({});
  const [returnAssetSelections, setReturnAssetSelections] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [resourceBusyId, setResourceBusyId] = useState(null);
  const [activeView, setActiveView] = useState("overview");
  const [mapLayer, setMapLayer] = useState("people");
  const [openConversationId, setOpenConversationId] = useState(null);
  const [incidentQuery, setIncidentQuery] = useState("");
  const [incidentStatus, setIncidentStatus] = useState("");
  const [incidentUrgency, setIncidentUrgency] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [profile, areas, feed, stock, stockRequests, shelterList, shelterQueue] = await Promise.all([
        request("/api/auth/me"),
        request("/api/help-requests/responder/coverage"),
        request("/api/help-requests/responder/feed"),
        request("/api/responder/resources"),
        request("/api/responder/resources/requests"),
        request("/api/shelters/responder/all"),
        request("/api/shelters/responder/requests"),
      ]);
      setUser(profile);
      setCoverage(areas);
      setItems(feed);
      setResources(stock);
      setResourceRequests(stockRequests);
      setShelters(shelterList);
      setShelterRequests(shelterQueue);
    } catch (err) {
      if (/token|credentials|authorized/i.test(err.message)) {
        clearToken();
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
      Promise.all([request("/api/help-requests/responder/feed"), request("/api/responder/resources"), request("/api/responder/resources/requests"), request("/api/shelters/responder/all"), request("/api/shelters/responder/requests")])
        .then(([feed, stock, stockRequests, shelterList, shelterQueue]) => { setItems(feed); setResources(stock); setResourceRequests(stockRequests); setShelters(shelterList); setShelterRequests(shelterQueue); })
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

  function addResourceRequestLine() {
    const draft = resourceRequestDraft;
    const custom = draft.item_choice === "custom";
    const item = custom ? null : resources.find(resource => String(resource.id) === draft.item_choice);
    const district = custom ? draft.district : item?.district;
    const quantity = Number(draft.quantity);
    if ((!custom && !item) || (custom && !draft.custom_item_name.trim())) { setError("Choose a catalog item or enter the name of an additional item."); return; }
    if (!district) { setError("Choose the district that needs this resource."); return; }
    if (draft.lines.length && draft.district.toLowerCase() !== district.toLowerCase()) { setError("All items in one transaction must be for the same district."); return; }
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 100000) { setError("Enter a valid requested quantity."); return; }
    const line = { resource_id: item?.id || null, custom_item_name: custom ? draft.custom_item_name.trim() : null,
      category: custom ? (draft.category.trim() || "Additional") : item.category,
      unit: custom ? draft.unit.trim() : item.unit, quantity,
      label: item?.name || draft.custom_item_name.trim(), district };
    const existingIndex = draft.lines.findIndex(existing => existing.resource_id ? existing.resource_id === line.resource_id : !line.resource_id && existing.label.trim().toLowerCase() === line.label.trim().toLowerCase());
    if (existingIndex >= 0 && draft.lines[existingIndex].quantity + quantity > 100000) { setError("Combined quantity for one item cannot exceed 100,000."); return; }
    const lines = existingIndex < 0 ? [...draft.lines, line] : draft.lines.map((existing, index) => index === existingIndex ? { ...existing, quantity: existing.quantity + quantity } : existing);
    setResourceRequestDraft(previous => ({ ...previous, district, lines, item_choice: "", custom_item_name: "", category: "Additional", unit: "units", quantity: "1", help_request_id: previous.help_request_id || "" }));
    setError("");
  }

  async function submitResourceRequest() {
    const draft = resourceRequestDraft;
    if (!draft.lines.length) { setError("Add at least one item to the transaction."); return; }
    if (!draft.reason.trim()) { setError("Describe the situation and why the response team needs these resources."); return; }
    if (!draft.help_request_id) { setError("Link this request to an active incident assigned to you."); return; }
    setResourceBusyId("new-resource-request");
    setError("");
    setNotice("");
    try {
      const incident = items.find(candidate => candidate.id === Number(draft.help_request_id));
      const result = await request("/api/responder/resources/request-batches", {
        method: "POST",
        body: JSON.stringify({
          items: draft.lines.map(({ label, district: lineDistrict, ...line }) => line),
          district: draft.district,
          description: draft.reason.trim(),
          latitude: resourceRequestDraft.latitude !== "" ? Number(resourceRequestDraft.latitude) : incident?.latitude ?? null,
          longitude: resourceRequestDraft.longitude !== "" ? Number(resourceRequestDraft.longitude) : incident?.longitude ?? null,
          priority: draft.priority,
          help_request_id: Number(draft.help_request_id),
        }),
      });
      setNotice(`Transaction ${result.transaction_id} submitted for ${draft.district}. District admins can review and approve it in Admin Console → Resources → Incoming resource requests. AI triage runs in the background.`);
      setResourceRequestDraft({ item_choice: "", custom_item_name: "", category: "Additional", unit: "units", district: "", quantity: "1", reason: "", priority: "Standard", help_request_id: "", latitude: "", longitude: "", lines: [] });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setResourceBusyId(null);
    }
  }

  async function returnResource(allocation) {
    const condition = returnConditions[allocation.id] || "Good";
    const assetIds = returnAssetSelections[allocation.id] || [];
    const quantity = Number(returnAmounts[allocation.id] || 1);
    if (allocation.inventory_mode === "Tracked Asset" ? assetIds.length < 1 : (!Number.isInteger(quantity) || quantity < 1 || quantity > allocation.quantity_in_use)) {
      setError(allocation.inventory_mode === "Tracked Asset" ? "Select at least one assigned asset to return." : `Choose a return quantity from 1 to ${allocation.quantity_in_use}.`);
      return;
    }
    if (condition === "Damaged" && !(returnAmounts[`note-${allocation.id}`] || "").trim()) { setError("Describe the damage or maintenance needed."); return; }
    setResourceBusyId(`return-${allocation.id}`);
    setError("");
    setNotice("");
    try {
      const result = await request(`/api/responder/resources/requests/${allocation.id}/return`, {
        method: "POST",
        body: JSON.stringify({ quantity, asset_ids: assetIds, condition, note: returnAmounts[`note-${allocation.id}`] || "" }),
      });
      setNotice(result.message);
      setReturnAmounts(previous => ({ ...previous, [allocation.id]: "1" }));
      setReturnAssetSelections(previous => ({ ...previous, [allocation.id]: [] }));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setResourceBusyId(null);
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
    clearToken();
    localStorage.removeItem("role");
    sessionStorage.removeItem("role");
    navigate("/login", { replace: true });
  }

  const activeRequests = items.filter(item => !["Resolved", "Rejected"].includes(item.status));
  const coverageDistricts = [...new Set(coverage.map(area => area.district).filter(Boolean))];
  const coverageDistrictKeys = new Set(coverageDistricts.map(district => district.trim().toLocaleLowerCase()));
  const coveredShelters = shelters.filter(s => coverageDistrictKeys.has((s.district || "").trim().toLocaleLowerCase()));
  const otherShelterDistricts = [...new Set(shelters.map(s => s.district).filter(district => district && !coverageDistrictKeys.has(district.trim().toLocaleLowerCase())))].sort();
  const otherDistrictShelters = otherShelterDistrict ? shelters.filter(s => (s.district || "").trim().toLocaleLowerCase() === otherShelterDistrict.toLocaleLowerCase()) : [];
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
  const lowStockCount = resources.filter(item => Number(item.quantity_available) > 0 && Number(item.quantity_available) <= Number(item.low_stock_threshold || 0)).length;

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
    <div className="responder-shelter-tabs" role="tablist" aria-label="Shelter workspace"><button type="button" role="tab" aria-selected={shelterWorkspaceView==="requests"} className={shelterWorkspaceView==="requests"?"selected":""} onClick={()=>setShelterWorkspaceView("requests")}>Requests <span>{pendingShelters}</span></button><button type="button" role="tab" aria-selected={shelterWorkspaceView==="capacity"} className={shelterWorkspaceView==="capacity"?"selected":""} onClick={()=>setShelterWorkspaceView("capacity")}>Shelter capacity <span>{coveredShelters.length}</span></button></div>
    {shelterWorkspaceView==="requests"&&<section className="responder-resources shelter-ops">
      <div className="responder-feed-heading"><div><h2>Shelter requests</h2><p>Review requests and coordinate available beds in your coverage area.</p></div><span>{pendingShelters} awaiting review</span></div>
      {loading ? <p className="responder-empty">Loading shelter requests…</p> : !shelterRequests.length ? <p className="responder-empty">No shelter requests in your coverage areas.</p> : <div className="responder-cards">{shelterRequests.map(item=><article className="responder-card" key={`shelter-request-${item.id}`}><div className="responder-card-top"><div><span className="responder-loc">{item.lac} · {item.district}</span><h3>{item.household_name} · {item.people_count} people</h3></div><span className="responder-status">{item.status}</span></div>{item.acceptance_id&&<p className="shelter-acceptance-reference"><b>Acceptance ID:</b> {item.acceptance_id}</p>}<p>Preferred: <b>{item.preferred_shelter?.name}</b> · Contact {item.phone} · Aadhaar ending {item.aadhaar_last4}</p>{item.citizen_location&&<p><b>Request location:</b> {item.citizen_location}{item.latitude&&item.longitude&&<> · <a href={`https://www.google.com/maps?q=${item.latitude},${item.longitude}`} target="_blank" rel="noreferrer">Open citizen location ↗</a></>}</p>}{item.reason&&<p><b>Reason:</b> {item.reason}</p>}{item.id_photo_available&&<ShelterRequestPhoto requestId={item.id}/>}{item.special_needs&&<p><b>Needs:</b> {item.special_needs}</p>}{item.assigned_shelter&&<p>Assigned to <b>{item.assigned_shelter.name}</b> · Capacity {item.assigned_shelter.occupied}/{item.assigned_shelter.capacity} · <a href={`https://www.google.com/maps?q=${item.assigned_shelter.latitude},${item.assigned_shelter.longitude}`} target="_blank" rel="noreferrer">Open shelter map ↗</a></p>}{item.status==="Pending"&&<div className="responder-card-footer"><select aria-label="Choose a shelter for this household" value={shelterChoices[item.id]||item.preferred_shelter?.id||""} onChange={e=>setShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose an in-coverage shelter</option>{shelters.filter(s=>s.is_active&&s.can_assign&&s.district?.trim().toLowerCase()===item.district?.trim().toLowerCase()&&s.available>=item.people_count).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available}/{s.capacity} spaces</option>)}</select><button disabled={busyId===`shelter-${item.id}`||!shelters.some(s=>s.id===Number(shelterChoices[item.id]||item.preferred_shelter?.id)&&s.is_active&&s.can_assign&&s.district?.trim().toLowerCase()===item.district?.trim().toLowerCase()&&s.available>=item.people_count)} onClick={()=>shelterDecision(item,"Approved")}>Accept and assign</button><button className="shelter-reject" disabled={busyId===`shelter-${item.id}`} onClick={()=>shelterDecision(item,"Rejected")}>Reject</button></div>}{["Approved","Assigned"].includes(item.status)&&<div className="responder-card-footer"><select aria-label="Choose shelter in your jurisdiction" value={shelterChoices[item.id]||item.assigned_shelter?.id||""} onChange={e=>setShelterChoices(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose an in-coverage shelter</option>{shelters.filter(s=>s.is_active&&s.can_assign&&s.district?.trim().toLowerCase()===item.district?.trim().toLowerCase()&&s.available+(s.id===item.assigned_shelter?.id?item.people_count:0)>=item.people_count).map(s=><option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} spaces</option>)}</select><button disabled={busyId===`shelter-${item.id}`} onClick={()=>assignShelter(item)}>{item.assigned_shelter?"Update assignment":"Assign shelter"}</button></div>}</article>)}</div>}
    </section>}
    {shelterWorkspaceView==="capacity"&&<section className="responder-resources shelter-ops"><div className="responder-feed-heading"><div><h2>Shelter capacity</h2><p>Update occupancy for shelters within your response coverage.</p></div></div>{coveredShelters.length ? <div className="responder-resource-grid">{coveredShelters.map(s=><article className="responder-resource-card" key={`shelter-${s.id}`}><div className="responder-card-top"><div><span className="responder-loc">{s.district} · {s.lac}</span><h3>{s.name}</h3></div><span className="responder-stock-count">{s.is_active?"Accepting requests":"Inactive"} · {s.occupied}/{s.capacity}</span></div><p>{s.building_type} · {s.address}<br/>{s.available} spaces available</p>{s.can_assign?<div className="shelter-counter"><label>People to update<input type="number" min="1" max={s.capacity} value={occupancyAmounts[s.id]??"1"} onChange={e=>setOccupancyAmounts(v=>({...v,[s.id]:e.target.value}))}/></label><button disabled={busyId===`capacity-${s.id}`||s.occupied<=0} onClick={()=>adjustOccupancy(s,-1)} aria-label={`Remove people from ${s.name}`}>Remove</button><button disabled={busyId===`capacity-${s.id}`||!s.is_active||s.occupied>=s.capacity} onClick={()=>adjustOccupancy(s,1)} aria-label={`Add people to ${s.name}`}>Add people</button></div>:<small>Outside your assigned jurisdiction</small>}</article>)}</div>:<p className="responder-empty">No shelters are listed in your assigned districts.</p>}{otherShelterDistricts.length>0&&<div className="shelter-other-districts"><label htmlFor="other-shelter-district">View shelters in another district</label><select id="other-shelter-district" value={otherShelterDistrict} onChange={e=>setOtherShelterDistrict(e.target.value)}><option value="">Choose a district</option>{otherShelterDistricts.map(district=><option key={district} value={district}>{district}</option>)}</select>{otherShelterDistrict&&<div className="responder-resource-grid">{otherDistrictShelters.map(s=><article className="responder-resource-card" key={`shelter-${s.id}`}><div className="responder-card-top"><div><span className="responder-loc">{s.district} · {s.lac}</span><h3>{s.name}</h3></div><span className="responder-stock-count">{s.is_active?"Accepting requests":"Inactive"} · {s.occupied}/{s.capacity}</span></div><p>{s.building_type} · {s.address}<br/>{s.available} spaces available</p><small>Outside your assigned jurisdiction · view only</small></article>)}</div>}</div>}</section>}
  </>;

  const selectedRequestResource=resources.find(resource=>String(resource.id)===resourceRequestDraft.item_choice);
  const resourceRequestDistrict=resourceRequestDraft.district||(resourceRequestDraft.item_choice==="custom"?"":selectedRequestResource?.district||"");
  const resourceRequestIncidents=items.filter(item=>item.assigned_responder_id===user?.id&&!['Resolved','Rejected'].includes(item.status)&&item.district?.trim().toLowerCase()===resourceRequestDistrict.trim().toLowerCase());
  const renderResources = <section className="responder-resources responder-resource-module">
    <div className="responder-feed-heading"><div><h2>District relief resources</h2><p>See available stock or send a request for items your team needs.</p></div><button onClick={load}>Refresh</button></div>
    <section className="responder-resource-request-panel">
      <div><span className="responder-kicker">RESOURCE REQUEST</span><h3>Request supplies or equipment</h3><p>Requests go to the admin for your chosen district. Stock changes only after approval.</p></div>
      <label>Resource<select value={resourceRequestDraft.item_choice} onChange={e=>{const value=e.target.value;const selected=resources.find(resource=>String(resource.id)===value);setResourceRequestDraft(previous=>({...previous,item_choice:value,district:value==="custom"?(previous.district||coverageDistricts[0]||""):selected?.district||previous.district,help_request_id:"",latitude:"",longitude:""}));}}><option value="">Choose a district resource</option>{resources.map(resource=><option key={resource.id} value={resource.id}>{resource.district} · {resource.name} · {resource.inventory_mode==="Tracked Asset"?(resource.available_assets||[]).length:resource.quantity_available} available</option>)}<option value="custom">Other · request an additional item</option></select></label>
      {resourceRequestDraft.item_choice==="custom"&&<>
        <label>New item name<input required maxLength="120" value={resourceRequestDraft.custom_item_name} onChange={e=>setResourceRequestDraft(v=>({...v,custom_item_name:e.target.value}))} placeholder="Describe the resource you need"/></label>
        <div className="two-fields"><label>Category<input maxLength="60" value={resourceRequestDraft.category} onChange={e=>setResourceRequestDraft(v=>({...v,category:e.target.value}))} placeholder="Additional"/></label><label>Unit<input required maxLength="40" value={resourceRequestDraft.unit} onChange={e=>setResourceRequestDraft(v=>({...v,unit:e.target.value}))} placeholder="units, kits, litres"/></label></div>
        <label>District<select required value={resourceRequestDraft.district} onChange={e=>setResourceRequestDraft(v=>({...v,district:e.target.value,help_request_id:"",latitude:"",longitude:""}))}><option value="">Choose district</option>{coverageDistricts.map(district=><option key={district}>{district}</option>)}</select></label>
      </>}
      {selectedRequestResource&&<p className="responder-resource-request-availability"><b>{selectedRequestResource.name}</b> · {selectedRequestResource.inventory_mode==="Tracked Asset"?(selectedRequestResource.available_assets||[]).length:selectedRequestResource.quantity_available} available in {selectedRequestResource.district}. You can still request more than the available amount; the admin will review what can be provided.</p>}
      <label>Quantity requested<div className="shelter-counter"><button type="button" disabled={Number(resourceRequestDraft.quantity)<=1} onClick={()=>setResourceRequestDraft(v=>({...v,quantity:String(Math.max(1,Number(v.quantity||1)-1))}))} aria-label="Decrease requested resource quantity">−</button><input type="number" min="1" max="100000" value={resourceRequestDraft.quantity} onChange={e=>setResourceRequestDraft(v=>({...v,quantity:e.target.value}))}/><button type="button" disabled={Number(resourceRequestDraft.quantity)>=100000} onClick={()=>setResourceRequestDraft(v=>({...v,quantity:String(Number(v.quantity||0)+1)}))} aria-label="Increase requested resource quantity">+</button></div></label>
      <button type="button" className="secondary" disabled={!resourceRequestDraft.item_choice} onClick={addResourceRequestLine}>Add item to transaction</button>
      {!!resourceRequestDraft.lines.length&&<div className="resource-request-lines"><b>Transaction items · {resourceRequestDraft.district}</b>{resourceRequestDraft.lines.map((line,index)=><div key={`${line.resource_id||line.label}-${index}`}><span>{line.label}</span><b>{line.quantity} {line.unit}</b><button type="button" aria-label={`Remove ${line.label}`} onClick={()=>setResourceRequestDraft(v=>{const lines=v.lines.filter((_,lineIndex)=>lineIndex!==index);return {...v,lines,district:lines.length?lines[0].district:"",help_request_id:lines.length?v.help_request_id:""};})}>Remove</button></div>)}</div>}
      <label>Priority<select value={resourceRequestDraft.priority} onChange={e=>setResourceRequestDraft(v=>({...v,priority:e.target.value}))}><option>Standard</option><option>Urgent</option><option>Critical</option></select></label>
      <label>Active incident<select required value={resourceRequestDraft.help_request_id} onChange={e=>{const linked=resourceRequestIncidents.find(item=>String(item.id)===e.target.value);setResourceRequestDraft(v=>({...v,help_request_id:e.target.value,latitude:linked?.latitude==null?"":String(linked.latitude),longitude:linked?.longitude==null?"":String(linked.longitude)}));}}><option value="">Choose an incident assigned to you</option>{resourceRequestIncidents.map(item=><option key={item.id} value={item.id}>HELP-{item.id} · {item.emergency_type} · {item.lac}</option>)}</select></label>
      <div className="two-fields"><label>Latitude<input type="number" step="any" min="-90" max="90" value={resourceRequestDraft.latitude} onChange={e=>setResourceRequestDraft(v=>({...v,latitude:e.target.value}))} placeholder="Copied from incident when available"/></label><label>Longitude<input type="number" step="any" min="-180" max="180" value={resourceRequestDraft.longitude} onChange={e=>setResourceRequestDraft(v=>({...v,longitude:e.target.value}))} placeholder="Copied from incident when available"/></label></div>
      {!resourceRequestIncidents.length&&resourceRequestDistrict&&<p className="responder-stock-note">No active incident assigned to you in {resourceRequestDistrict}. Assign or claim an incident in this district before submitting a resource request.</p>}
      <label>Situation and resource need<textarea required minLength="3" maxLength="2000" value={resourceRequestDraft.reason} onChange={e=>setResourceRequestDraft(v=>({...v,reason:e.target.value}))} placeholder="Describe what is happening and why these items are needed"/></label>
      <button className="resource-issue" disabled={resourceBusyId==="new-resource-request"||!resourceRequestDraft.lines.length||!resourceRequestDraft.help_request_id||!resourceRequestDraft.reason.trim()} onClick={submitResourceRequest}>{resourceBusyId==="new-resource-request"?"Submitting transaction…":"Submit resource transaction"}</button>
    </section>
    <div className="responder-feed-heading"><div><h3>Current district availability</h3><p>Inventory is shown for your assigned districts only.</p></div></div>
    {loading?<p className="responder-empty">Loading district inventory…</p>:!resources.length?<p className="responder-empty">No catalog inventory has been initialized for your assigned districts yet.</p>:<div className="responder-resource-grid">{resources.map(resource=>{const available=resource.inventory_mode==="Tracked Asset"?(resource.available_assets||[]).length:Number(resource.quantity_available||0);return <article className="responder-resource-card" key={resource.id}><div className="responder-card-top"><div><span className="responder-loc">{resource.district} · {resource.category} · {resource.inventory_mode}</span><h3>{resource.name}</h3></div><span className="responder-stock-count">{available} available</span></div><p className="responder-stock-note">{resource.is_returnable?"Reusable equipment · return after use":"Single-use supplies · consumed when issued"}{available<=0?" · Currently unavailable":available<=Number(resource.low_stock_threshold||0)?" · Limited availability":""}</p></article>})}</div>}
    <section className="responder-resource-requests"><div className="responder-feed-heading"><div><h2>My resource requests</h2><p>Track batch triage, approvals, asset assignments, and returns.</p></div></div>{!resourceRequests.length?<p className="responder-empty">You have not requested any resources yet.</p>:<div className="responder-cards">{resourceRequests.map(allocation=><article className="responder-card" key={`resource-request-${allocation.id}`}><div className="responder-card-top"><div><span className="responder-loc">{allocation.district} · {allocation.priority} priority</span><h3>{allocation.resource_name}</h3></div><span className="responder-status">{allocation.status}</span></div>{allocation.transaction_id&&<p><b>Transaction:</b> {allocation.transaction_id} · AI triage {allocation.triage_state||"Pending"}{allocation.ai_priority?` · ${allocation.ai_priority}`:""}</p>}<p>{allocation.quantity_requested} {allocation.unit} requested{allocation.quantity_granted!=null?` · ${allocation.quantity_granted} granted`:""} · {allocation.reason}</p>{allocation.ai_summary&&<p className="resource-ai-summary">{allocation.ai_summary}</p>}{allocation.help_request_id&&<p>Linked incident: <b>HELP-{allocation.help_request_id}</b></p>}{allocation.status==="Pending"&&<p>Pending admin review. This amount is shown as requested but remains available until a decision.</p>}{allocation.status==="Rejected"&&<p>Rejected: {allocation.rejection_reason||"No reason supplied."}</p>}{["Granted","Partially Granted","Partially Returned","Consumed"].includes(allocation.status)?<><p>{allocation.is_returnable?`${allocation.quantity_in_use} ${allocation.unit} assigned · ${allocation.quantity_returned} returned · ${allocation.quantity_quarantined||0} quarantined`: `${allocation.quantity_granted} ${allocation.unit} consumed`}{allocation.quantity_granted<allocation.quantity_requested&&<span> · Unapproved remainder canceled</span>}</p>{allocation.assets?.length>0&&<p><b>Assigned assets:</b> {allocation.assets.filter(asset=>asset.status==="Assigned").map(asset=>asset.identifier).join(", ")||"None currently assigned"}</p>}{allocation.is_returnable&&allocation.quantity_in_use>0&&<div className="responder-resource-form"><label>Return condition<select value={returnConditions[allocation.id]||"Good"} onChange={e=>setReturnConditions(v=>({...v,[allocation.id]:e.target.value}))}><option value="Good">Good · return to available stock</option><option value="Damaged">Damaged · quarantine for maintenance</option></select></label>{allocation.inventory_mode==="Tracked Asset"?<div className="resource-return-assets"><b>Select assets to return</b>{allocation.assets?.filter(asset=>asset.status==="Assigned").map(asset=><label key={asset.id}><input type="checkbox" checked={(returnAssetSelections[allocation.id]||[]).includes(asset.id)} onChange={e=>setReturnAssetSelections(v=>{const selected=v[allocation.id]||[];return {...v,[allocation.id]:e.target.checked?[...selected,asset.id]:selected.filter(id=>id!==asset.id)};})}/>{asset.identifier}</label>)}</div>:<label>Quantity returned<input type="number" min="1" max={allocation.quantity_in_use} value={returnAmounts[allocation.id]??"1"} onChange={e=>setReturnAmounts(v=>({...v,[allocation.id]:e.target.value}))}/></label>}{(returnConditions[allocation.id]||"Good")==="Damaged"&&<label>Damage / maintenance note<input value={returnAmounts[`note-${allocation.id}`]||""} onChange={e=>setReturnAmounts(v=>({...v,[`note-${allocation.id}`]:e.target.value}))} placeholder="Describe the condition"/></label>}<button disabled={resourceBusyId===`return-${allocation.id}`} onClick={()=>returnResource(allocation)}>{resourceBusyId===`return-${allocation.id}`?"Recording return…":"Record return"}</button></div>}</>:null}{allocation.quantity_quarantined>0&&<p>{allocation.quantity_quarantined} {allocation.unit} quarantined for maintenance; unavailable to other teams.</p>}{allocation.status==="Returned"&&<p>All reusable items in this allocation have been returned or quarantined.</p>}</article>)}</div>}</section>
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
        {activeView==="resources"&&<><div className="responder-page-heading"><div><span className="responder-kicker">DISTRICT INVENTORY</span><h2>Relief resources</h2><p>Request equipment and supplies from your district administrator.</p></div></div>{renderResources}</>}
        {activeView==="map"&&<><div className="responder-page-heading"><div><span className="responder-kicker">GEOGRAPHIC OPERATIONS</span><h2>Response map</h2><p>Review requests, shelters, and constituency boundaries.</p></div></div>{renderMap}</>}
      </section>
      <footer className="responder-console-footer"><span>KAAVALAL FIELD OPERATIONS</span><span>Updates automatically while this console is open</span></footer>
    </div>
    <ChatWidget district={coverage[0]?.district||null} page="responder" />
  </main>;
}
