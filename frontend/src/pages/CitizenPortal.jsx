import { useEffect, useState } from "react";
import "./citizen-portal.css";
import { t, localeName } from "../services/i18n";

const API = "http://127.0.0.1:8000";
const services = [
  ["dashboard", "Citizen dashboard", "Weather, risk indicators, and local exposure information.", "▦"],
  ["help", "Report an incident", "Send a non-emergency incident report to your local response team.", "⌖"],
  ["sos", "Emergency / SOS response", "Send an urgent request with your location and household needs.", "SOS"],
  ["alerts", "Disaster alerts", "Read current official alerts published by administrators.", "◉"],
  ["shelter", "Find nearby shelter", "View locations, capacity, and request household shelter.", "⌂"],
  ["dashboard", "Disaster map", "Explore Kerala risk layers, constituencies, and shelter pins.", "◇"],
  ["information", "Disaster information", "Ask about safety, evacuation, SOS requests, and shelters.", "?"],
];

export default function CitizenPortal({ onNavigate, selectedLac, language = "en" }) {
  const [alerts, setAlerts] = useState([]);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { fetch(`${API}/api/alerts/published`).then(r => r.ok ? r.json() : []).then(setAlerts).catch(() => setAlerts([])); }, []);
  async function ask(event) {
    event.preventDefault(); if (!question.trim()) return;
    const prompt = question.trim(); setQuestion(""); setError(""); setMessages(v => [...v, { role: "citizen", text: prompt }]); setBusy(true);
    try {
      const response = await fetch(`${API}/api/citizen/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: prompt, language }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "The information service is unavailable.");
      setMessages(v => [...v, { role: "assistant", text: data.answer }]);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="citizen-portal"><header className="citizen-welcome"><div><span className="citizen-kicker">KAAVALAL · {t("Citizen Services",language)}</span><h1>{t("Citizen Portal",language)}</h1><p>{t("Report an incident, request help, check alerts, and find a shelter.",language)}</p></div><div className="citizen-location"><span>{t("Your starting area",language)}</span><b>{selectedLac?.name || t("Finding your nearest LAC…",language)}</b><small>{selectedLac?.district || "Kerala"}</small></div></header>
    <section className="citizen-service-grid" aria-label={t("Citizen Services",language)}>{services.map(([key,title,description,icon],i)=><button type="button" className={`citizen-service-card ${key === "sos" ? "citizen-sos-card" : ""}`} key={`${key}-${i}`} onClick={()=>key==="information"?onNavigate("information"):onNavigate(key)}><span className="citizen-service-icon">{icon}</span><span className="citizen-service-copy"><b>{t(title,language)}</b><small>{t(description,language)}</small></span><span className="citizen-arrow">→</span></button>)}</section>
    <section className="citizen-bottom-grid"><div className="citizen-panel"><div className="citizen-panel-head"><div><span className="citizen-kicker">{t("OFFICIAL UPDATES",language)}</span><h2>{t("Latest disaster alerts",language)}</h2></div><button type="button" onClick={()=>onNavigate("alerts")}>{t("All alerts",language)}</button></div>{alerts.slice(0,3).map(alert=><article className="citizen-alert-row" key={alert.id}><span className={`citizen-severity ${alert.severity}`}>{alert.severity}</span><div><b>{alert.title}</b><p>{alert.district || "Kerala-wide"} · {alert.message}</p></div></article>)}{!alerts.length&&<p className="citizen-muted">{t("No active alerts are published right now.",language)}</p>}</div>
    <div className="citizen-panel citizen-assistant"><span className="citizen-kicker">{t("PREPAREDNESS GUIDE",language)}</span><h2>{t("Disaster information",language)}</h2><p>{t("Ask a question about shelters, alerts, flood safety, landslides, or requesting help.",language)}</p><div className="citizen-chat-log" aria-live="polite">{messages.slice(-4).map((m,i)=><p className={`citizen-chat-message ${m.role}`} key={i}>{m.text}</p>)}</div><form onSubmit={ask}><input value={question} onChange={e=>setQuestion(e.target.value)} maxLength={1000} placeholder={language === "ml" ? "വെള്ളപ്പൊക്കത്തിൽ എന്ത് ചെയ്യണം?" : "What should I do during a flood?"}/><button disabled={busy}>{busy?"…":language === "ml" ? "ചോദിക്കുക" : "Ask"}</button></form>{error&&<small className="citizen-chat-error">{error}</small>}<small className="citizen-muted">{t("Guidance assistant. For urgent danger, contact emergency services.",language)}</small></div></section>
  </main>;
}

export function CitizenAlerts({ onBack, language = "en" }) {
  const [alerts,setAlerts]=useState([]); const [error,setError]=useState("");
  useEffect(()=>{fetch(`${API}/api/alerts/published`).then(async r=>{if(!r.ok)throw new Error("Unable to load published alerts.");return r.json();}).then(setAlerts).catch(e=>setError(e.message));},[]);
  return <main className="citizen-portal"><button className="citizen-back" onClick={onBack}>← {t("Citizen Portal",language)}</button><header className="citizen-welcome"><div><span className="citizen-kicker">{language === "ml" ? "അഡ്മിൻ പ്രസിദ്ധീകരിച്ചത്" : "ADMIN PUBLISHED"}</span><h1>{t("Disaster alerts",language)}</h1><p>{language === "ml" ? "കേരള ജില്ലകൾക്കായി നിലവിലുള്ള മുന്നറിയിപ്പുകൾ." : "Current alerts published for Kerala districts."}</p></div></header>{error&&<p role="alert">{error}</p>}<section className="citizen-alert-list">{alerts.map(a=><article className="citizen-panel" key={a.id}><span className={`citizen-severity ${a.severity}`}>{a.severity}</span><h2>{a.title}</h2><p>{a.message}</p><small>{a.district||"Kerala-wide"} · {language === "ml" ? "പ്രസിദ്ധീകരിച്ചത്" : "Published"} {a.published_at?new Date(a.published_at).toLocaleString(localeName(language)):"recently"}{a.expires_at?` · ${language === "ml" ? "കാലാവധി" : "Expires"} ${new Date(a.expires_at).toLocaleString(localeName(language))}`:""}</small></article>)}{!error&&!alerts.length&&<div className="citizen-panel citizen-muted">{t("No active alerts are published right now.",language)}</div>}</section></main>;
}

export function CitizenInformation({ onBack, language = "en" }) {
  const [question,setQuestion]=useState(""); const [answer,setAnswer]=useState(""); const [topic,setTopic]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  async function ask(e){e.preventDefault();setBusy(true);setError("");setAnswer("");try{const r=await fetch(`${API}/api/citizen/chat`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,language})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Could not get guidance.");setAnswer(d.answer);setTopic(d.topic);}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <main className="citizen-portal"><button className="citizen-back" onClick={onBack}>← {t("Citizen Portal",language)}</button><header className="citizen-welcome"><div><span className="citizen-kicker">{t("PREPAREDNESS GUIDE",language)}</span><h1>{t("Disaster information",language)}</h1><p>{language === "ml" ? "വെള്ളപ്പൊക്കം, മണ്ണിടിച്ചിൽ, SOS, മുന്നറിയിപ്പ്, ആരോഗ്യ ആവശ്യങ്ങൾ, അഭയകേന്ദ്രങ്ങൾ എന്നിവ ചോദിക്കുക." : "Ask about floods, landslides, SOS requests, alerts, medical needs, or shelters."}</p></div></header><section className="citizen-panel citizen-info-panel"><form onSubmit={ask}><label htmlFor="citizen-question">{language === "ml" ? "നിങ്ങളുടെ ചോദ്യം" : "Your question"}</label><textarea id="citizen-question" required minLength="2" maxLength="1000" rows="3" value={question} onChange={e=>setQuestion(e.target.value)} placeholder={language === "ml" ? "കുടുംബത്തിന് അഭയകേന്ദ്രം എങ്ങനെ അഭ്യർത്ഥിക്കാം?" : "How do I request shelter for my family?"}/><button disabled={busy}>{busy?(language === "ml"?"വിവരം തിരയുന്നു…":"Looking up guidance…"):(language === "ml"?"വിവരം നേടുക":"Get guidance")}</button></form>{error&&<p role="alert" className="citizen-chat-error">{error}</p>}{answer&&<article className="citizen-guidance-answer"><span className="citizen-kicker">{topic}</span><p>{answer}</p></article>}<p className="citizen-muted">{language === "ml" ? "പരിശോധിച്ച മുന്നൊരുക്ക നിർദ്ദേശങ്ങൾ. അടിയന്തര അപകടത്തിൽ അടിയന്തര സേവനങ്ങളെ ബന്ധപ്പെടുകയും SOS അയയ്ക്കുകയും ചെയ്യുക." : "This assistant uses reviewed preparedness guidance. For immediate danger, contact emergency services and submit an SOS request."}</p></section></main>;
}
