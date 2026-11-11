import { useEffect, useState } from "react";
import "./shelter-requests.css";
import "./shelter-directory.css";
import { t, localeName } from "../services/i18n";
import { queueOfflineRequest } from "../services/offlineQueue";

const API = `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"}/api/shelters`;
const token = () => localStorage.getItem("access_token") || localStorage.getItem("token") || sessionStorage.getItem("token") || "";
const blankForm = () => ({ shelter_id: "", household_name: "", aadhaar_last4: "", phone: "", people_count: "1", citizen_location: "", latitude: "", longitude: "", reason: "", special_needs: "" });

export default function ShelterRequests({ shelters = [], language = "en" }) {
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState(blankForm);
  const [idPhoto, setIdPhoto] = useState(null);
  const [districtFilter, setDistrictFilter] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [histories, setHistories] = useState({});
  const districts = [...new Set(shelters.map(s => s.district))].sort();
  const visibleShelters = shelters.filter(s => !districtFilter || s.district === districtFilter);
  const available = visibleShelters.filter(s => s.is_active && s.available > 0);
  const selectedShelter = shelters.find(s => Number(s.id) === Number(form.shelter_id));

  async function load() {
    if (!token()) return;
    const response = await fetch(`${API}/requests/my`, { headers: { Authorization: `Bearer ${token()}` } });
    if (response.ok) setRequests(await response.json());
  }
  useEffect(() => {
    load().catch(() => {});
    const interval = window.setInterval(() => load().catch(() => {}), 15000);
    window.addEventListener("focus", load);
    return () => { window.clearInterval(interval); window.removeEventListener("focus", load); };
  }, []);
  async function toggleHistory(id) {
    if (histories[id]) { setHistories(v => ({ ...v, [id]: null })); return; }
    try { const r = await fetch(`${API}/requests/my/${id}/history`, { headers: { Authorization: `Bearer ${token()}` } }); const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not load status history."); setHistories(v => ({ ...v, [id]: data })); }
    catch (e) { setError(e.message); }
  }
  function useLocation() {
    if (!navigator.geolocation) { setError("Location access is unavailable in this browser."); return; }
    navigator.geolocation.getCurrentPosition(p => { setForm(v => ({ ...v, latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) })); setNotice("Your current location was added to the request."); }, () => setError("Could not read your location. Enter your area below."), { enableHighAccuracy: true, timeout: 10000 });
  }
  function validate() {
    if (!form.shelter_id || form.household_name.trim().length < 2 || !/^\d{4}$/.test(form.aadhaar_last4) || form.phone.trim().length < 7 || Number(form.people_count) < 1 || form.citizen_location.trim().length < 3 || form.reason.trim().length < 5) {
      setError("Complete the required fields, including your location and reason."); return false;
    }
    return true;
  }
  async function saveOffline() {
    setError(""); setNotice("");
    if (!token()) { setError("Sign in before saving a shelter request."); return; }
    if (idPhoto) { setError("Identification photos need an internet connection. Submit the request when you are online."); return; }
    if (!validate()) return;
    const id = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload = { ...form, shelter_id: Number(form.shelter_id), people_count: Number(form.people_count), client_request_id: id };
    setBusy(true);
    try { await queueOfflineRequest({ id, type: "shelter", payload, queued_at: new Date().toISOString() }); setNotice("Saved on this device. It will sync when the connection returns."); setForm(blankForm()); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    if (!token()) { setError("Sign in to submit a shelter request."); setBusy(false); return; }
    if (!validate()) { setBusy(false); return; }
    if (idPhoto && !navigator.onLine) { setError("Identification photos need an internet connection. Submit the request when you are online."); setBusy(false); return; }
    const clientRequestId = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload = { ...form, shelter_id: Number(form.shelter_id), people_count: Number(form.people_count), client_request_id: clientRequestId };
    try {
      const response = await fetch(`${API}/requests`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` }, body: JSON.stringify(payload) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not submit shelter request.");
      let photoMessage = "";
      if (idPhoto) {
        const image = new FormData(); image.append("image", idPhoto);
        const upload = await fetch(`${API}/requests/${data.id}/id-photo`, { method: "POST", headers: { Authorization: `Bearer ${token()}` }, body: image });
        if (!upload.ok) { const details = await upload.json().catch(() => ({})); photoMessage = ` The request was received, but the ID photo could not be saved: ${details.detail || "upload failed"}.`; }
      }
      setNotice(`Shelter request #${data.id} sent to the local rescue team.${data.eta_estimate_minutes ? ` Estimated review window: about ${data.eta_estimate_minutes} minutes (estimate only).` : ""}${photoMessage}`);
      setForm(blankForm()); setIdPhoto(null); await load();
    } catch (err) {
      if ((err instanceof TypeError || !navigator.onLine) && !idPhoto) {
        try { await queueOfflineRequest({ id: clientRequestId, type: "shelter", payload, queued_at: new Date().toISOString() }); setNotice("Saved on this device. It will sync when the connection returns."); setForm(blankForm()); }
        catch (queueError) { setError(queueError.message); }
      } else setError(err.message);
    } finally { setBusy(false); }
  }
  return <main className="shelter-request-page"><header><div><span className="shelter-eyebrow">KAAVALAL · {language === "ml" ? "പൗര സേവനങ്ങൾ" : "CITIZEN SERVICES"}</span><h1>{t("Request emergency shelter", language)}</h1><p>Browse active shelters by district, then send your household details to the local rescue team.</p></div></header>
    <section className="citizen-shelter-directory"><div className="shelter-directory-heading"><div><h2>Available shelter options</h2><p>Live occupancy is shared with administrators and response teams.</p></div><label>District<select value={districtFilter} onChange={e => { setDistrictFilter(e.target.value); setForm(v => ({ ...v, shelter_id: "" })); }}><option value="">All districts</option>{districts.map(d => <option key={d}>{d}</option>)}</select></label></div>
      {!visibleShelters.length ? <p className="shelter-empty">No active shelters are listed yet.</p> : <div className="citizen-shelter-grid">{visibleShelters.map(s => <article className={`citizen-shelter-option ${!s.is_active || s.available <= 0 ? "unavailable" : ""}`} key={s.id}><div><span>{s.district} · {s.lac}</span><h3>{s.name}</h3><small>{s.building_type} · {s.address}</small></div><strong>{s.occupied}/{s.capacity}<small> people</small></strong><p>{s.is_active ? `${s.available} spaces available` : "Currently inactive"}</p>{s.latitude && s.longitude && <a href={`https://www.google.com/maps?q=${s.latitude},${s.longitude}`} target="_blank" rel="noreferrer">View location ↗</a>}<button type="button" disabled={!s.is_active || s.available <= 0} onClick={() => setForm(v => ({ ...v, shelter_id: String(s.id) }))}>{Number(form.shelter_id) === s.id ? "Selected" : s.is_active && s.available > 0 ? "Request this shelter" : "Unavailable"}</button></article>)}</div>}
    </section>
    <div className="shelter-request-grid"><form onSubmit={submit} className="shelter-request-form"><h2>Request shelter support</h2>
      <label>{t("Preferred shelter", language)}<select required value={form.shelter_id} onChange={e => setForm(v => ({ ...v, shelter_id: e.target.value }))}><option value="">Choose an available shelter</option>{available.map(s => <option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.occupied}/{s.capacity} · {s.available} spaces left</option>)}</select></label>
      {selectedShelter && <p className="shelter-selected-capacity">Current capacity: <b>{selectedShelter.occupied}/{selectedShelter.capacity}</b> · {selectedShelter.available} spaces available</p>}
      <label>{t("Household contact name", language)}<input required minLength="2" maxLength="150" value={form.household_name} onChange={e => setForm(v => ({ ...v, household_name: e.target.value }))}/></label>
      <div className="shelter-two"><label>{t("Aadhaar last 4 digits", language)}<input required inputMode="numeric" pattern="[0-9]{4}" maxLength="4" value={form.aadhaar_last4} onChange={e => setForm(v => ({ ...v, aadhaar_last4: e.target.value.replace(/\D/g, "").slice(0, 4) }))}/></label><label>{t("Phone number", language)}<input required type="tel" minLength="7" maxLength="20" value={form.phone} onChange={e => setForm(v => ({ ...v, phone: e.target.value }))}/></label></div>
      <label>{t("People in household", language)}<input type="number" min="1" max="1000" required value={form.people_count} onChange={e => setForm(v => ({ ...v, people_count: e.target.value }))}/></label>
      <label>Photo of identification card <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={e => setIdPhoto(e.target.files?.[0] || null)}/><small>Optional · JPEG, PNG, or WebP · up to 5 MB</small></label>
      <label>Your current location / area<input required maxLength="500" value={form.citizen_location} onChange={e => setForm(v => ({ ...v, citizen_location: e.target.value }))} placeholder="House, street, landmark, locality"/></label>
      <button type="button" className="shelter-secondary-action" onClick={useLocation}>Use my current location</button>
      {(form.latitude || form.longitude) && <p className="shelter-selected-capacity">GPS coordinates: {form.latitude}, {form.longitude}</p>}
      <label>Reason for shelter request<textarea required minLength="5" maxLength="2000" rows="3" value={form.reason} onChange={e => setForm(v => ({ ...v, reason: e.target.value }))} placeholder="Describe why your household needs shelter"/></label>
      <label>{t("Medical or accessibility needs", language)}<textarea maxLength="2000" rows="2" value={form.special_needs} onChange={e => setForm(v => ({ ...v, special_needs: e.target.value }))} placeholder="Optional"/></label>
      <p className="shelter-privacy">Only the last four Aadhaar digits are requested. Share an ID photo only if needed for verification. Request details are visible to the rescue team covering the selected shelter.</p>
      {error && <p className="shelter-error" role="alert">{error}</p>}{notice && <p className="shelter-notice" role="status">{notice}</p>}
      <button disabled={busy || !available.length}>{busy ? "Sending request…" : "Submit shelter request"}</button><button type="button" className="shelter-history-toggle" onClick={saveOffline} disabled={busy}>Save on this device</button>
      {!available.length && <p>No active shelter with available space is listed in this district.</p>}
    </form>
    <section className="shelter-my-requests"><h2>My shelter requests</h2>{requests.length ? requests.map(r => <article key={r.id}><div><b>{r.preferred_shelter?.name || `Shelter request #${r.id}`}</b><span>{r.lac} · {r.district}</span></div><strong className={`shelter-status ${r.status.toLowerCase()}`}>{t(r.status, language)}</strong><p>{r.people_count} people · Submitted {new Date(r.created_at).toLocaleString(localeName(language))}</p>{r.assigned_shelter && <div className="shelter-assignment-result"><b>Rescue team assigned: {r.assigned_shelter.name}</b><span>{r.assigned_shelter.address} · {r.assigned_shelter.lac}, {r.assigned_shelter.district}</span><span>Capacity: {r.assigned_shelter.occupied}/{r.assigned_shelter.capacity}</span><a href={`https://www.google.com/maps?q=${r.assigned_shelter.latitude},${r.assigned_shelter.longitude}`} target="_blank" rel="noreferrer">Open assigned shelter map ↗</a></div>}{r.status === "Rejected" && <p className="shelter-rejected-note">The rescue team could not accept this request. You can submit another request for a different active shelter.</p>}<p>Status: {t(r.status, language)}{r.eta_estimate_minutes ? ` · Estimated review: about ${r.eta_estimate_minutes} minutes (estimate only)` : ""}</p><button type="button" className="shelter-history-toggle" onClick={() => toggleHistory(r.id)}>{histories[r.id] ? "Hide status history" : "View status history"}</button>{histories[r.id] && <ol className="request-status-history">{histories[r.id].map(e => <li key={e.id}><b>{t(e.status, language)}</b><span>{e.note}</span><small>{new Date(e.created_at).toLocaleString(localeName(language))}</small></li>)}</ol>}</article>) : <p>Requests you submit will appear here with their review status.</p>}</section></div>
  </main>;
}