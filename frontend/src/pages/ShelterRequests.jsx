import { useEffect, useState } from "react";
import "./shelter-requests.css";
import { t, localeName } from "../services/i18n";
import { queueOfflineRequest } from "../services/offlineQueue";

const API = "http://127.0.0.1:8000/api/shelters";
const token = () => localStorage.getItem("access_token") || localStorage.getItem("token") || sessionStorage.getItem("token") || "";

export default function ShelterRequests({ shelters = [], language = "en" }) {
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({ shelter_id: "", household_name: "", aadhaar_last4: "", phone: "", people_count: "1", special_needs: "" });
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [histories,setHistories]=useState({});
  async function load() {
    if (!token()) return;
    const response = await fetch(`${API}/requests/my`, { headers: { Authorization: `Bearer ${token()}` } });
    if (response.ok) setRequests(await response.json());
  }
  useEffect(() => { load().catch(() => {}); }, []);
  async function toggleHistory(id){if(histories[id]){setHistories(v=>({...v,[id]:null}));return;}try{const r=await fetch(`${API}/requests/my/${id}/history`,{headers:{Authorization:`Bearer ${token()}`}});const data=await r.json();if(!r.ok)throw new Error(data.detail||"Could not load status history.");setHistories(v=>({...v,[id]:data}));}catch(e){setError(e.message);}}
  async function saveOffline(){
    setError("");setNotice("");
    if(!token()){setError(language==="ml"?"അഭ്യർത്ഥന സൂക്ഷിക്കാൻ ആദ്യം ലോഗിൻ ചെയ്യുക.":"Sign in before saving a shelter request.");return;}
    if(!form.shelter_id||form.household_name.trim().length<2||!/^\d{4}$/.test(form.aadhaar_last4)||form.phone.trim().length<7||Number(form.people_count)<1){setError(language==="ml"?"ഓഫ്‌ലൈൻ ആയി സൂക്ഷിക്കുന്നതിന് മുമ്പ് ആവശ്യമായ വിവരങ്ങൾ പൂരിപ്പിക്കുക.":"Complete the required fields before saving offline.");return;}
    const id=window.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload={...form,shelter_id:Number(form.shelter_id),people_count:Number(form.people_count),client_request_id:id};setBusy(true);
    try{await queueOfflineRequest({id,type:"shelter",payload,queued_at:new Date().toISOString()});setNotice(language==="ml"?"അഭ്യർത്ഥന ഈ ഉപകരണത്തിൽ സൂക്ഷിച്ചു. കണക്ഷൻ ലഭിക്കുമ്പോൾ അയയ്ക്കും.":"Saved on this device. It will sync when the connection returns.");setForm({shelter_id:"",household_name:"",aadhaar_last4:"",phone:"",people_count:"1",special_needs:""});}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    if (!token()) { setError("Sign in to submit a shelter request."); setBusy(false); return; }
    const clientRequestId = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload = { ...form, shelter_id: Number(form.shelter_id), people_count: Number(form.people_count), client_request_id: clientRequestId };
    try {
      const response = await fetch(`${API}/requests`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` }, body: JSON.stringify(payload) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not submit shelter request.");
      setNotice(language === "ml" ? `SHELTER-${data.id} ആയി സ്വീകരിച്ചു. പ്രാദേശിക രക്ഷാസംഘത്തിന് കൈമാറി.${data.eta_estimate_minutes ? ` കണക്കാക്കിയ പരിശോധനാ സമയം ഏകദേശം ${data.eta_estimate_minutes} മിനിറ്റ്.` : ""} ഇത് ഏകദേശ കണക്കാണ്; ഉറപ്പല്ല.` : `Acknowledged as SHELTER-${data.id}. Sent to the local rescue team.${data.eta_estimate_minutes ? ` Estimated review window: about ${data.eta_estimate_minutes} minutes.` : ""} This is an estimate, not a guarantee.`); setForm({ shelter_id: "", household_name: "", aadhaar_last4: "", phone: "", people_count: "1", special_needs: "" }); await load();
    } catch (err) {
      if (err instanceof TypeError || !navigator.onLine) {
        try { await queueOfflineRequest({ id: clientRequestId, type: "shelter", payload, queued_at: new Date().toISOString() }); setNotice("Saved on this device. It will sync when the connection returns."); setForm({ shelter_id: "", household_name: "", aadhaar_last4: "", phone: "", people_count: "1", special_needs: "" }); }
        catch (queueError) { setError(queueError.message); }
      } else setError(err.message);
    } finally { setBusy(false); }
  }
  const available = shelters.filter(s => s.available > 0);
  return <main className="shelter-request-page"><header><div><span className="shelter-eyebrow">KAAVALAL · {language === "ml" ? "പൗര സേവനങ്ങൾ" : "CITIZEN SERVICES"}</span><h1>{t("Request emergency shelter",language)}</h1><p>{language === "ml" ? "ലഭ്യമായ അഭയകേന്ദ്രം തിരഞ്ഞെടുക്കുക. പ്രദേശത്തെ രക്ഷാസംഘം അഭ്യർത്ഥന പരിശോധിക്കും." : "Choose an active shelter. The response team responsible for that area will review your request."}</p></div></header>
    <div className="shelter-request-grid"><form onSubmit={submit} className="shelter-request-form"><label>{t("Preferred shelter",language)}<select required value={form.shelter_id} onChange={e => setForm(v => ({ ...v, shelter_id: e.target.value }))}><option value="">{t("Choose an available shelter",language)}</option>{available.map(s => <option key={s.id} value={s.id}>{s.name} · {s.lac}, {s.district} · {s.available} {language === "ml" ? "ഒഴിവുകൾ" : "spaces"}</option>)}</select></label><label>{t("Household contact name",language)}<input required minLength="2" maxLength="150" value={form.household_name} onChange={e => setForm(v => ({ ...v, household_name: e.target.value }))}/></label><div className="shelter-two"><label>{t("Aadhaar last 4 digits",language)}<input required inputMode="numeric" pattern="[0-9]{4}" maxLength="4" value={form.aadhaar_last4} onChange={e => setForm(v => ({ ...v, aadhaar_last4: e.target.value.replace(/\D/g, "").slice(0, 4) }))}/></label><label>{t("Phone number",language)}<input required type="tel" minLength="7" maxLength="20" value={form.phone} onChange={e => setForm(v => ({ ...v, phone: e.target.value }))}/></label></div><label>{t("People in household",language)}<input type="number" min="1" max="1000" required value={form.people_count} onChange={e => setForm(v => ({ ...v, people_count: e.target.value }))}/></label><label>{t("Medical or accessibility needs",language)}<textarea maxLength="2000" rows="3" value={form.special_needs} onChange={e => setForm(v => ({ ...v, special_needs: e.target.value }))} placeholder={language === "ml" ? "ഐച്ഛികം" : "Optional"}/></label><p className="shelter-privacy">{language === "ml" ? "ആധാർ നമ്പറിന്റെ അവസാന നാല് അക്കങ്ങൾ മാത്രം ശേഖരിക്കുന്നു." : "Only the last four Aadhaar digits are collected for this request."}</p><p className="shelter-privacy">{language === "ml" ? "ഓഫ്‌ലൈൻ ആയാൽ അഭ്യർത്ഥന ഈ ഉപകരണത്തിൽ സൂക്ഷിക്കും. പങ്കിടുന്ന ഉപകരണത്തിൽ ഇത് ഉപയോഗിക്കുമ്പോൾ ശ്രദ്ധിക്കുക." : "If offline, request details are stored on this device until sync. Avoid using a shared device."}</p>{error && <p className="shelter-error" role="alert">{error}</p>}{notice && <p className="shelter-notice" role="status">{notice}</p>}<button disabled={busy || !available.length}>{busy ? (language === "ml" ? "അയയ്ക്കുന്നു…" : "Sending request…") : t("Submit shelter request",language)}</button><button type="button" className="shelter-history-toggle" onClick={saveOffline} disabled={busy}>{language==="ml"?"ഉപകരണത്തിൽ സൂക്ഷിക്കുക":"Save on this device"}</button>{!available.length && <p>{language === "ml" ? "ഒഴിവുള്ള അഭയകേന്ദ്രം ഇപ്പോൾ ലഭ്യമല്ല." : "No active shelter with available space is listed right now."}</p>}</form>
      <section className="shelter-my-requests"><h2>{t("My shelter requests",language)}</h2>{requests.length ? requests.map(r => <article key={r.id}><div><b>{r.preferred_shelter?.name || "Shelter request"}</b><span>{r.lac} · {r.district}</span></div><strong className={`shelter-status ${r.status.toLowerCase()}`}>{t(r.status,language)}</strong><p>{r.people_count} {language === "ml" ? "ആളുകൾ" : "people"} · {t("Phone number",language)} {r.phone}</p>{r.assigned_shelter && <p>{language === "ml" ? "നിയോഗിച്ച അഭയകേന്ദ്രം:" : "Assigned shelter:"} <b>{r.assigned_shelter.name}</b></p>}<p>{language === "ml" ? "നിലവാരം:" : "Status:"} {t(r.status,language)}{r.eta_estimate_minutes ? ` · ${language === "ml" ? "കണക്കാക്കിയ പ്രതികരണ സമയം" : "Estimated review window"}: ${r.eta_estimate_minutes} ${language === "ml" ? "മിനിറ്റ്" : "minutes"} · ${language === "ml" ? "ഉറപ്പല്ല, കണക്കുകൂട്ടൽ മാത്രം" : "estimate only"}` : ""}</p><small>{language === "ml" ? "അയച്ചത്" : "Submitted"} {new Date(r.created_at).toLocaleString(localeName(language))}</small><button type="button" className="shelter-history-toggle" onClick={()=>toggleHistory(r.id)}>{histories[r.id]?(language === "ml"?"ചരിത്രം മറയ്ക്കുക":"Hide status history"):(language === "ml"?"നിലവാര ചരിത്രം കാണുക":"View status history")}</button>{histories[r.id]&&<ol className="request-status-history">{histories[r.id].map(e=><li key={e.id}><b>{t(e.status,language)}</b><span>{e.note}</span><small>{new Date(e.created_at).toLocaleString(localeName(language))}</small></li>)}</ol>}</article>) : <p>{language === "ml" ? "അയച്ച അഭ്യർത്ഥനകൾ ഇവിടെ കാണാം." : "Requests you submit will appear here with their review status."}</p>}</section></div>
  </main>;
}
