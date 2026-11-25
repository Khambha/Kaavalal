import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./shelter-requests.css";
import "./shelter-qr-modal.css";
import "./shelter-directory.css";
import { t, localeName } from "../services/i18n";
import { queueOfflineRequest } from "../services/offlineQueue";
import QRCode from "qrcode";
import { getToken } from "../services/auth";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

const API = `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"}/api/shelters`;
// `token` is the canonical key written by signin.jsx. Prefer it over the legacy
// access_token key so an old session cannot override the account just signed in.
const token = getToken;
const blankForm = () => ({ shelter_id: "", household_name: "", aadhaar_last4: "", phone: "", people_count: "1", citizen_location: "", latitude: "", longitude: "", reason: "", special_needs: "" });

function ShelterCheckinQr({ acceptanceId, name, peopleCount, shelterName }) {
  const [qrCode, setQrCode] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let active = true;
    const record = JSON.stringify({ acceptance_id: acceptanceId, name, people: peopleCount });
    QRCode.toDataURL(record, { width: 220, margin: 2, errorCorrectionLevel: "M" })
      .then(image => { if (active) setQrCode(image); })
      .catch(() => { if (active) setQrCode(""); });
    return () => { active = false; };
  }, [acceptanceId, name, peopleCount]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === "Escape") setOpen(false); };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return <>
    <button type="button" className="shelter-qr-trigger" onClick={() => setOpen(true)}>Ticketed QR</button>
    {open && createPortal(<div className="shelter-qr-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="shelter-qr-dialog" role="dialog" aria-modal="true" aria-labelledby={`shelter-qr-title-${acceptanceId}`}>
        <button type="button" className="shelter-qr-close" onClick={() => setOpen(false)} aria-label="Close ticketed QR">×</button>
        <span className="shelter-qr-eyebrow">SHELTER CHECK-IN</span>
        <h2 id={`shelter-qr-title-${acceptanceId}`}>Ticketed QR</h2>
        <p>Show this QR to the team at <b>{shelterName}</b>. Keep it private.</p>
        {qrCode ? <img className="shelter-qr-image" src={qrCode} alt={`Ticketed QR for acceptance ${acceptanceId}`} /> : <span className="shelter-qr-loading">Preparing QR code…</span>}
        <dl className="shelter-qr-details"><div><dt>Acceptance ID</dt><dd>{acceptanceId}</dd></div><div><dt>Name</dt><dd>{name}</dd></div><div><dt>People</dt><dd>{peopleCount}</dd></div></dl>
        <a className={`shelter-qr-download ${qrCode ? "" : "disabled"}`} href={qrCode || undefined} download={`${acceptanceId}.png`} aria-disabled={!qrCode}>Download QR code</a>
      </section>
    </div>, document.body)}
  </>;
}

export default function ShelterRequests({ shelters = [], language = "en" }) {
  const [requests, setRequests] = useState([]);
  const [referenceCamps, setReferenceCamps] = useState({ items: [], total: 0, page_size: 30 });
  const [referenceSearch, setReferenceSearch] = useState("");
  const [referenceQuery, setReferenceQuery] = useState("");
  const [referencePage, setReferencePage] = useState(1);
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceError, setReferenceError] = useState("");
  const [form, setForm] = useState(blankForm);
  const [idPhoto, setIdPhoto] = useState(null);
  const [districtFilter, setDistrictFilter] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [histories, setHistories] = useState({});
  const [directoryCategory, setDirectoryCategory] = useState("all");
  const [directoryView, setDirectoryView] = useState("list");
  const [requestFormOpen, setRequestFormOpen] = useState(false);
  const districts = [...new Set([...shelters, ...(referenceCamps.items || [])].map(s => s.district).filter(Boolean))].sort();
  const visibleShelters = shelters.filter(s => !districtFilter || s.district === districtFilter);
  const available = visibleShelters.filter(s => s.is_active && s.available > 0);
  const selectedShelter = shelters.find(s => Number(s.id) === Number(form.shelter_id));
  const managedCampKeys = new Set(shelters.map(s => s.source_key).filter(Boolean));
  const searchNeedle = referenceQuery.trim().toLocaleLowerCase();
  const directoryRows = [
    ...visibleShelters
      .filter(s => !searchNeedle || `${s.name} ${s.district} ${s.lac} ${s.address} ${s.building_type}`.toLocaleLowerCase().includes(searchNeedle))
      .filter(s => directoryCategory !== "camps")
      .filter(s => directoryCategory !== "available" || (s.is_active && s.available > 0))
      .map(s => ({ ...s, rowType: "managed", rowKey: `shelter-${s.id}` })),
    ...(referenceCamps.items || [])
      .filter(camp => !managedCampKeys.has(camp.source_key || `ksdma-camp:${camp.id}`))
      .filter(camp => !districtFilter || camp.district === districtFilter)
      .filter(camp => directoryCategory !== "available")
      .map(camp => ({
        ...camp,
        rowType: "camp",
        rowKey: `camp-${camp.id}`,
        address: [camp.village, camp.local_body, camp.district].filter(Boolean).join(", "),
        latitude: camp.latitude,
        longitude: camp.longitude,
        map_url: camp.map_url,
      })),
  ];
  const groupedDirectoryRows = directoryRows.reduce((groups, row) => {
    (groups[row.district || "Kerala"] ||= []).push(row);
    return groups;
  }, {});

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
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ page: String(referencePage), page_size: "30" });
    if (districtFilter) params.set("district", districtFilter);
    if (referenceQuery) params.set("search", referenceQuery);
    setReferenceLoading(true);
    setReferenceError("");
    fetch(`${API}/reference-camps?${params}`, { signal: controller.signal })
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "KSDMA camp locations are unavailable.");
        setReferenceCamps(data);
      })
      .catch(error => { if (error.name !== "AbortError") setReferenceError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setReferenceLoading(false); });
    return () => controller.abort();
  }, [districtFilter, referencePage, referenceQuery]);
  async function toggleHistory(id) {
    if (histories[id]) { setHistories(v => ({ ...v, [id]: null })); return; }
    try { const r = await fetch(`${API}/requests/my/${id}/history`, { headers: { Authorization: `Bearer ${token()}` } }); const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not load status history."); setHistories(v => ({ ...v, [id]: data })); }
    catch (e) { setError(e.message); }
  }
  function useLocation() {
    if (!navigator.geolocation) { setError("Location access is unavailable in this browser."); return; }
    navigator.geolocation.getCurrentPosition(p => { setForm(v => ({ ...v, latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) })); setNotice("Your current location was added to the request."); }, () => setError("Could not read your location. Enter your area below."), { enableHighAccuracy: true, timeout: 10000 });
  }
  function chooseShelter(shelter) {
    setForm(value => ({ ...value, shelter_id: String(shelter.id) }));
    setRequestFormOpen(true);
    setError("");
    setNotice("");
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
  return <main className="shelter-request-page"><header><div><span className="shelter-eyebrow">KAAVALAL · {language === "ml" ? "പൗര സേവനങ്ങൾ" : "CITIZEN SERVICES"}</span><h1>Find a shelter</h1><p>Search by district or camp name, check current space, and choose how to continue.</p></div></header>
    <section className="citizen-shelter-directory shelter-directory-workspace" aria-labelledby="shelter-directory-title">
      <div className="shelter-directory-heading"><div><h2 id="shelter-directory-title">Shelters and relief camps</h2><p>Live capacity and request options are shown for shelters managed by response teams.</p></div><span className="camp-directory-count">{referenceCamps.total.toLocaleString()} camp locations</span></div>
      <form className="shelter-directory-controls" onSubmit={event => { event.preventDefault(); setReferencePage(1); setReferenceQuery(referenceSearch.trim()); }}>
        <label className="shelter-search-field"><span>Search by name, village, or area</span><input value={referenceSearch} onChange={event => setReferenceSearch(event.target.value)} maxLength={160} placeholder="e.g. camp, panchayat, or district" aria-label="Search shelters and camps"/><button type="submit">Search</button></label>
        <label><span>District</span><select value={districtFilter} onChange={event => { setDistrictFilter(event.target.value); setReferencePage(1); setForm(blankForm()); setRequestFormOpen(false); }}><option value="">All districts</option>{districts.map(district => <option key={district}>{district}</option>)}</select></label>
      </form>
      <div className="shelter-directory-toolbar">
        <div className="shelter-filter-tabs" role="group" aria-label="Filter shelter locations">
          {[['all', 'All locations'], ['available', 'Accepting requests'], ['camps', 'Relief camps']].map(([value, label]) => <button type="button" key={value} className={directoryCategory === value ? 'selected' : ''} aria-pressed={directoryCategory === value} onClick={() => setDirectoryCategory(value)}>{label}</button>)}
        </div>
        <div className="shelter-view-toggle" role="group" aria-label="Directory view">
          <button type="button" className={directoryView === 'list' ? 'selected' : ''} aria-pressed={directoryView === 'list'} onClick={() => setDirectoryView('list')}>List</button>
          <button type="button" className={directoryView === 'map' ? 'selected' : ''} aria-pressed={directoryView === 'map'} onClick={() => setDirectoryView('map')}>Map</button>
        </div>
      </div>
      <p className="shelter-directory-note">KSDMA camp capacities are source-listed figures. Ask the district control room at <b>1077</b> about current opening and space before travelling.</p>
      {referenceError && <p className="shelter-empty" role="alert">{referenceError}</p>}
      {referenceLoading ? <p className="shelter-empty" role="status">Loading shelter locations…</p> : directoryView === 'map' ? <div className="shelter-directory-map" aria-label="Map of listed shelters and camps">
        <MapContainer center={[10.5, 76.2]} zoom={7} scrollWheelZoom={false}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {directoryRows.filter(row => row.latitude != null && row.longitude != null && Number.isFinite(Number(row.latitude)) && Number.isFinite(Number(row.longitude)) && Number(row.latitude) >= 8 && Number(row.latitude) <= 13 && Number(row.longitude) >= 74 && Number(row.longitude) <= 78).map(row => <CircleMarker key={row.rowKey} center={[Number(row.latitude), Number(row.longitude)]} radius={row.rowType === 'managed' ? 8 : 6} pathOptions={{ color: row.rowType === 'managed' ? '#155c45' : '#a87516', fillOpacity: .85 }}><Popup><b>{row.name}</b><br/>{row.district}{row.lac ? ` · ${row.lac}` : ''}<br/>{row.rowType === 'managed' ? `${row.available} spaces available` : 'KSDMA camp location'}<br/><a href={row.rowType === 'managed' ? `https://www.google.com/maps?q=${row.latitude},${row.longitude}` : row.map_url} target="_blank" rel="noreferrer">Open directions</a></Popup></CircleMarker>)}
        </MapContainer>
      </div> : !Object.keys(groupedDirectoryRows).length ? <p className="shelter-empty">No matching shelters or camps. Try another district or search term.</p> : <div className="shelter-district-groups">
        {Object.entries(groupedDirectoryRows).sort(([a], [b]) => a.localeCompare(b)).map(([district, rows]) => <section className="shelter-district-group" key={district}>
          <h3>{district}<span>{rows.length} location{rows.length === 1 ? '' : 's'}</span></h3>
          <div className="shelter-directory-rows">{rows.map(row => <article className="shelter-directory-row" key={row.rowKey}>
            <div className="shelter-row-main"><span className={`shelter-kind ${row.rowType}`}>{row.rowType === 'managed' ? row.building_type : 'KSDMA relief camp'}</span><h4>{row.name}</h4><p>{row.address || row.local_body || row.district}{row.lac ? ` · ${row.lac}` : ''}</p></div>
            <div className="shelter-row-capacity">{row.rowType === 'managed' ? <><b>{row.available}</b><span>spaces available</span><small>{row.occupied} of {row.capacity} occupied</small></> : <><b>{row.listed_capacity ?? '—'}</b><span>{row.listed_capacity == null ? 'capacity not listed' : 'source-listed capacity'}</span></>}</div>
            <div className="shelter-row-actions"><a href={row.rowType === 'managed' ? `https://www.google.com/maps?q=${row.latitude},${row.longitude}` : row.map_url} target="_blank" rel="noreferrer">Directions ↗</a>{row.rowType === 'managed' && <button type="button" disabled={!row.is_active || row.available <= 0} onClick={() => chooseShelter(row)}>{Number(form.shelter_id) === row.id && requestFormOpen ? 'Selected' : row.available > 0 ? 'Request a place' : 'Full'}</button>}</div>
          </article>)}</div>
        </section>)}
      </div>}
      {!referenceError && referenceCamps.total > referenceCamps.page_size && <div className="camp-directory-pagination"><span>Camp locations · page {referenceCamps.page} of {Math.ceil(referenceCamps.total / referenceCamps.page_size)}</span><div><button type="button" disabled={referencePage <= 1 || referenceLoading} onClick={() => setReferencePage(page => Math.max(1, page - 1))}>Previous</button><button type="button" disabled={referencePage >= Math.ceil(referenceCamps.total / referenceCamps.page_size) || referenceLoading} onClick={() => setReferencePage(page => page + 1)}>Next</button></div></div>}
    </section>
    {requestFormOpen && selectedShelter && <div className="shelter-request-workspace"><form onSubmit={submit} className="shelter-request-form"><div className="shelter-request-form-heading"><div><span className="shelter-kind managed">Selected shelter</span><h2>{selectedShelter.name}</h2><p>{selectedShelter.lac} · {selectedShelter.district} · {selectedShelter.available} places available</p></div><button type="button" className="shelter-close-form" onClick={() => { setRequestFormOpen(false); setForm(blankForm()); }}>Close</button></div>
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
    </form></div>}
    <details className="shelter-my-requests"><summary>My shelter requests <span>{requests.length}</span></summary>{requests.length ? requests.map(r => <article key={r.id}><div><b>{r.preferred_shelter?.name || `Shelter request #${r.id}`}</b><span>{r.lac} · {r.district}</span></div><strong className={`shelter-status ${r.status.toLowerCase()}`}>{t(r.status, language)}</strong><p>{r.people_count} people · Submitted {new Date(r.created_at).toLocaleString(localeName(language))}</p>{r.assigned_shelter && <div className="shelter-assignment-result"><b>Rescue team assigned: {r.assigned_shelter.name}</b><span>{r.assigned_shelter.address} · {r.assigned_shelter.lac}, {r.assigned_shelter.district}</span><span>Capacity: {r.assigned_shelter.occupied}/{r.assigned_shelter.capacity}</span><a href={`https://www.google.com/maps?q=${r.assigned_shelter.latitude},${r.assigned_shelter.longitude}`} target="_blank" rel="noreferrer">Open assigned shelter map ↗</a></div>}{r.acceptance_id && r.assigned_shelter && <ShelterCheckinQr acceptanceId={r.acceptance_id} name={r.household_name} peopleCount={r.people_count} shelterName={r.assigned_shelter.name}/>}{r.status === "Rejected" && <p className="shelter-rejected-note">The rescue team could not accept this request. You can submit another request for a different active shelter.</p>}<p>Status: {t(r.status, language)}{r.eta_estimate_minutes ? ` · Estimated review: about ${r.eta_estimate_minutes} minutes (estimate only)` : ""}</p><button type="button" className="shelter-history-toggle" onClick={() => toggleHistory(r.id)}>{histories[r.id] ? "Hide status history" : "View status history"}</button>{histories[r.id] && <ol className="request-status-history">{histories[r.id].map(e => <li key={e.id}><b>{t(e.status, language)}</b><span>{e.note}</span><small>{new Date(e.created_at).toLocaleString(localeName(language))}</small></li>)}</ol>}</article>) : <p>Requests you submit will appear here with their review status.</p>}</details>
  </main>;
}
