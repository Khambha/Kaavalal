import { useEffect, useRef, useState } from "react";
import { sendMessage, sendFeedback } from "../../services/chatApi";
import "./chat.css";

/**
 * Thunai (തുണ), the Kaavalal citizen assistant.
 *
 * Props
 *   variant   "floating" (default: round button bottom-right, on every page)
 *             "inline"   (fills its parent, e.g. a card on the dashboard)
 *   district  Kerala district the dashboard is showing, e.g. "Wayanad" (optional)
 *   page      name of the current dashboard page (optional)
 *
 * Other dashboard components can open Thunai with a question, e.g. from an alert card:
 *   window.dispatchEvent(new CustomEvent("thunai:ask", { detail: { message: "What should I do?" } }));
 */
const T = {
  en: {
    title: "Thunai · Kaavalal Assistant",
    placeholder: "Ask about alerts, shelters, safety...",
    welcome: "Hi, I'm Thunai. I can help with flood and landslide risk, rainfall, alerts, shelters with free places, your incident reports and safety guidance across Kerala.",
    emergency: "Emergency? Call 112",
    disclaimer: "Informational only. Not a replacement for emergency services.",
    error: "Something went wrong. For emergencies call 112.",
    limited: "Too many messages. Please wait a minute.",
    viewing: (d) => `Showing help for ${d}`,
    locate: "📍 Use my location",
    located: "📍 Location shared (not stored)",
    locDenied: "Location not available. You can type your district or panchayat instead.",
    quick: ["Nearest relief camp", "Water kiosk near me", "Hospitals in my district", "Flood risk today"],
  },
  ml: {
    title: "തുണ · കാവലാൾ സഹായി",
    placeholder: "മുന്നറിയിപ്പുകൾ, ക്യാമ്പുകൾ, സുരക്ഷ...",
    welcome: "നമസ്കാരം, ഞാൻ തുണ. കേരളത്തിലെ വെള്ളപ്പൊക്ക/ഉരുൾപൊട്ടൽ സാധ്യത, മഴ, മുന്നറിയിപ്പുകൾ, ക്യാമ്പുകളിലെ ഒഴിവുകൾ, നിങ്ങളുടെ റിപ്പോർട്ടുകളുടെ നില, സുരക്ഷാ മാർഗ്ഗനിർദേശം എന്നിവയിൽ സഹായിക്കാം.",
    emergency: "അടിയന്തരം? 112 വിളിക്കുക",
    disclaimer: "വിവരങ്ങൾക്ക് മാത്രം. അടിയന്തര സേവനങ്ങൾക്ക് പകരമല്ല.",
    error: "എന്തോ പിഴവുണ്ടായി. അടിയന്തരമെങ്കിൽ 112 വിളിക്കുക.",
    limited: "വളരെയധികം സന്ദേശങ്ങൾ. ഒരു മിനിറ്റ് കാത്തിരിക്കുക.",
    viewing: (d) => `${d} ജില്ലയ്ക്കുള്ള സഹായം`,
    locate: "📍 എന്റെ സ്ഥലം ഉപയോഗിക്കുക",
    located: "📍 സ്ഥലം പങ്കിട്ടു (സൂക്ഷിക്കില്ല)",
    locDenied: "സ്ഥലം ലഭ്യമല്ല. ജില്ലയോ പഞ്ചായത്തോ ടൈപ്പ് ചെയ്യാം.",
    quick: ["അടുത്തുള്ള ദുരിതാശ്വാസ ക്യാമ്പ്", "അടുത്തുള്ള കുടിവെള്ള കിയോസ്ക്", "ജില്ലയിലെ ആശുപത്രികൾ", "ഇന്നത്തെ വെള്ളപ്പൊക്ക സാധ്യത"],
  },
};

// Shows **bold** and makes http(s) links clickable. Built from React elements only (no HTML injection possible).
function renderLine(line) {
  return line.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s'")\]}]+)/g).map((part, i) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (/^https?:\/\//.test(part)) {
      const url = part.replace(/[.,;:!?]+$/, "");
      const label = url.includes("google.com/maps") ? "Open map" : url;
      return (
        <span key={i}>
          <a href={url} target="_blank" rel="noopener noreferrer">{label}</a>{part.slice(url.length)}
        </span>
      );
    }
    return part;
  });
}

function RichText({ text }) {
  return text.split("\n").map((line, i) => (
    <div key={i} className="kc-line">{line === "" ? "\u00a0" : renderLine(line)}</div>
  ));
}

export default function ChatWidget({ variant = "floating", district = null, page = null, language = "en" }) {
  const inline = variant === "inline";
  const [open, setOpen] = useState(inline);
  const [languageOverride, setLanguageOverride] = useState(null);
  const lang = languageOverride ?? (language === "ml" ? "ml" : "en");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [quick, setQuick] = useState(null);
  const [coords, setCoords] = useState(null); // only kept in memory, sent with messages, never saved
  const [sessionId, setSessionId] = useState(() => {
    try { return localStorage.getItem("kaavalal_chat_session"); } catch { return null; }
  });
  const endRef = useRef(null);
  const sendRef = useRef(null);
  const t = T[lang];

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  async function send(text) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    setQuick([]);
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const data = await sendMessage({
        sessionId, message: msg, language: lang,
        context: { district, page, lat: coords ? coords.lat : null, lng: coords ? coords.lng : null },
      });
      setSessionId(data.session_id);
      try { localStorage.setItem("kaavalal_chat_session", data.session_id); } catch {}
      setMessages((m) => [...m, {
        role: "bot", content: data.reply, id: data.message_id,
        emergency: data.emergency, layer: data.layer,
      }]);
      setQuick(data.quick_replies);
    } catch (e) {
      setMessages((m) => [...m, { role: "bot", content: e.message === "rate_limited" ? t.limited : t.error }]);
    } finally {
      setLoading(false);
    }
  }
  sendRef.current = send; // always the latest closure, for the event listener below

  // Let other dashboard components open Thunai with a question (e.g. "Ask Thunai" on a dashboard card).
  useEffect(() => {
    function onAsk(e) {
      const message = e.detail && e.detail.message;
      if (!message) return;
      setOpen(true);
      setTimeout(() => sendRef.current && sendRef.current(message), 0);
    }
    window.addEventListener("thunai:ask", onAsk);
    return () => window.removeEventListener("thunai:ask", onAsk);
  }, []);

  function locate() {
    if (!navigator.geolocation) {
      setMessages((m) => [...m, { role: "bot", content: t.locDenied }]);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setMessages((m) => [...m, { role: "bot", content: t.locDenied }]),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }

  async function rate(index, helpful) {
    const msg = messages[index];
    if (!msg.id || msg.rated) return;
    setMessages((m) => m.map((x, i) => (i === index ? { ...x, rated: helpful ? "up" : "down" } : x)));
    try { await sendFeedback(msg.id, helpful); } catch {}
  }

  const chips = quick && quick.length ? quick : (messages.length === 0 ? t.quick : []);

  return (
    <>
      {!inline && !open && (
        <button className="kc-fab" onClick={() => setOpen(true)} aria-label="Open Thunai chat">💬</button>
      )}
      {open && (
        <div className={`kc-panel ${inline ? "kc-inline" : ""}`} role="dialog" aria-label={t.title}>
          <div className="kc-header">
            <span>{t.title}</span>
            <div className="kc-header-actions">
              <button onClick={() => setLanguageOverride(lang === "en" ? "ml" : "en")} className="kc-lang">
                {lang === "en" ? "മലയാളം" : "English"}
              </button>
              {!inline && <button onClick={() => setOpen(false)} aria-label="Close">✕</button>}
            </div>
          </div>

          <div className="kc-sos">{t.emergency}</div>
          {district && <div className="kc-ctx">{t.viewing(district)}</div>}

          <div className="kc-body">
            <div className="kc-msg kc-bot">{t.welcome}</div>
            {messages.map((m, i) => (
              <div key={i} className={`kc-msg ${m.role === "user" ? "kc-user" : "kc-bot"} ${m.emergency ? "kc-emergency" : ""}`}>
                <RichText text={m.content} />
                {m.role === "bot" && m.id && (
                  <div className="kc-rate">
                    <button disabled={!!m.rated} className={m.rated === "up" ? "on" : ""} onClick={() => rate(i, true)} aria-label="Helpful">👍</button>
                    <button disabled={!!m.rated} className={m.rated === "down" ? "on" : ""} onClick={() => rate(i, false)} aria-label="Not helpful">👎</button>
                  </div>
                )}
              </div>
            ))}
            {loading && <div className="kc-msg kc-bot kc-typing"><span /><span /><span /></div>}
            <div ref={endRef} />
          </div>

          <div className="kc-loc">
            {coords
              ? <span>{t.located} <button onClick={() => setCoords(null)} aria-label="Stop sharing location">✕</button></span>
              : <button onClick={locate}>{t.locate}</button>}
          </div>

          {chips.length > 0 && (
            <div className="kc-chips">
              {chips.map((c) => <button key={c} onClick={() => send(c)}>{c}</button>)}
            </div>
          )}

          <form className="kc-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)}
              placeholder={t.placeholder} maxLength={1000} />
            <button type="submit" disabled={loading || !input.trim()}>➤</button>
          </form>
          <div className="kc-disclaimer">{t.disclaimer}</div>
        </div>
      )}
    </>
  );
}
