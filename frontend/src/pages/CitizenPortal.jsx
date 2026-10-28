import { useEffect, useState } from "react";
import "./citizen-portal.css";
import { t, localeName } from "../services/i18n";
import ChatWidget from "../components/chatbot/ChatWidget";

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

export default function CitizenPortal({ onNavigate, selectedLac, selectedDistrict, language = "en" }) {
  const [alerts, setAlerts] = useState([]);
  useEffect(() => { fetch(`${API}/api/alerts/published`).then(r => r.ok ? r.json() : []).then(setAlerts).catch(() => setAlerts([])); }, []);
  return <main className="citizen-portal"><header className="citizen-welcome"><div><span className="citizen-kicker">KAAVALAL · {t("Citizen Services",language)}</span><h1>{t("Citizen Portal",language)}</h1><p>{t("Report an incident, request help, check alerts, and find a shelter.",language)}</p></div><div className="citizen-location"><span>{t("Your starting area",language)}</span><b>{selectedLac?.name || t("Finding your nearest LAC…",language)}</b><small>{selectedLac?.district || "Kerala"}</small></div></header>
    <section className="citizen-service-grid" aria-label={t("Citizen Services",language)}>{services.map(([key,title,description,icon],i)=><button type="button" className={`citizen-service-card ${key === "sos" ? "citizen-sos-card" : ""}`} key={`${key}-${i}`} onClick={()=>key==="information"?onNavigate("information"):onNavigate(key)}><span className="citizen-service-icon">{icon}</span><span className="citizen-service-copy"><b>{t(title,language)}</b><small>{t(description,language)}</small></span><span className="citizen-arrow">→</span></button>)}</section>
    <section className="citizen-bottom-grid"><div className="citizen-panel"><div className="citizen-panel-head"><div><span className="citizen-kicker">{t("OFFICIAL UPDATES",language)}</span><h2>{t("Latest disaster alerts",language)}</h2></div><button type="button" onClick={()=>onNavigate("alerts")}>{t("All alerts",language)}</button></div>{alerts.slice(0,3).map(alert=><article className="citizen-alert-row" key={alert.id}><span className={`citizen-severity ${alert.severity}`}>{alert.severity}</span><div><b>{alert.title}</b><p>{alert.district || "Kerala-wide"} · {alert.message}</p></div></article>)}{!alerts.length&&<p className="citizen-muted">{t("No active alerts are published right now.",language)}</p>}</div>
    <div className="citizen-panel citizen-thunai-panel"><span className="citizen-kicker">{t("PREPAREDNESS GUIDE",language)}</span><h2>Thunai · {t("Disaster information",language)}</h2><ChatWidget variant="inline" district={selectedLac?.district || selectedDistrict?.name || null} page="citizen" language={language} /></div></section>
  </main>;
}

export function CitizenAlerts({ onBack, language = "en" }) {
  const [alerts,setAlerts]=useState([]); const [error,setError]=useState("");
  useEffect(()=>{fetch(`${API}/api/alerts/published`).then(async r=>{if(!r.ok)throw new Error("Unable to load published alerts.");return r.json();}).then(setAlerts).catch(e=>setError(e.message));},[]);
  return <main className="citizen-portal"><button className="citizen-back" onClick={onBack}>← {t("Citizen Portal",language)}</button><header className="citizen-welcome"><div><span className="citizen-kicker">{language === "ml" ? "അഡ്മിൻ പ്രസിദ്ധീകരിച്ചത്" : "ADMIN PUBLISHED"}</span><h1>{t("Disaster alerts",language)}</h1><p>{language === "ml" ? "കേരള ജില്ലകൾക്കായി നിലവിലുള്ള മുന്നറിയിപ്പുകൾ." : "Current alerts published for Kerala districts."}</p></div></header>{error&&<p role="alert">{error}</p>}<section className="citizen-alert-list">{alerts.map(a=><article className="citizen-panel" key={a.id}><span className={`citizen-severity ${a.severity}`}>{a.severity}</span><h2>{a.title}</h2><p>{a.message}</p><small>{a.district||"Kerala-wide"} · {language === "ml" ? "പ്രസിദ്ധീകരിച്ചത്" : "Published"} {a.published_at?new Date(a.published_at).toLocaleString(localeName(language)):"recently"}{a.expires_at?` · ${language === "ml" ? "കാലാവധി" : "Expires"} ${new Date(a.expires_at).toLocaleString(localeName(language))}`:""}</small></article>)}{!error&&!alerts.length&&<div className="citizen-panel citizen-muted">{t("No active alerts are published right now.",language)}</div>}</section></main>;
}

export function CitizenInformation({ onBack, selectedDistrict, language = "en" }) {
  return <main className="citizen-portal"><button className="citizen-back" onClick={onBack}>← {t("Citizen Portal",language)}</button><header className="citizen-welcome"><div><span className="citizen-kicker">{t("PREPAREDNESS GUIDE",language)}</span><h1>Thunai · {t("Disaster information",language)}</h1><p>{language === "ml" ? "വെള്ളപ്പൊക്കം, മണ്ണിടിച്ചിൽ, SOS, മുന്നറിയിപ്പ്, ആരോഗ്യ ആവശ്യങ്ങൾ, അഭയകേന്ദ്രങ്ങൾ എന്നിവ ചോദിക്കുക." : "Ask about floods, landslides, SOS requests, alerts, medical needs, or shelters."}</p></div></header><section className="citizen-info-panel"><ChatWidget variant="inline" district={selectedDistrict?.name || null} page="citizen" language={language} /></section></main>;
}
