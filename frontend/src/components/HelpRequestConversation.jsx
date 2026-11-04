import { useCallback, useEffect, useState } from "react";
import "./help-request-conversation.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("token") || sessionStorage.getItem("token") || localStorage.getItem("access_token") || "";
}

export default function HelpRequestConversation({ requestId, role, language = "en", closed = false }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const malayalam = language === "ml";

  const load = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/help-requests/${requestId}/messages`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const data = await response.json().catch(() => []);
    if (!response.ok) throw new Error(data.detail || "Could not load this conversation.");
    setMessages(data);
    setError("");
  }, [requestId]);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      load().catch(error => { if (active) setError(error.message); });
    };
    refresh();
    const interval = window.setInterval(refresh, 10000);
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
    };
  }, [load]);

  async function send(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || sending) return;
    setSending(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/help-requests/${requestId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ message }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not send your message.");
      setDraft("");
      await load();
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setSending(false);
    }
  }

  return <section className="help-conversation" aria-label={malayalam ? "സംഭാഷണം" : "Conversation with response team"}>
    <h4>{malayalam ? "പൗരനും രക്ഷാപ്രവർത്തക സംഘവും തമ്മിലുള്ള സംഭാഷണം" : "Conversation with response team"}</h4>
    {error && <p className="help-conversation-error" role="alert">{error}</p>}
    <div className="help-conversation-messages" aria-live="polite">
      {messages.map(item => <article className={`help-conversation-message ${item.sender_role === role ? "is-own" : ""}`} key={item.id}>
        <div><b>{item.sender_name}</b><span>{item.sender_role === "citizen" ? (malayalam ? "പൗരൻ" : "Citizen") : (malayalam ? "രക്ഷാപ്രവർത്തകൻ" : "Rescuer")}</span></div>
        <p>{item.message}</p>
        <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(malayalam ? "ml-IN" : "en-IN")}</time>
      </article>)}
      {!messages.length && !error && <p className="help-conversation-empty">{malayalam ? "ഇതുവരെ സന്ദേശങ്ങളില്ല." : "No messages yet. Send an update or ask a question."}</p>}
    </div>
    {closed ? <p className="help-conversation-closed">{malayalam ? "ഈ റിപ്പോർട്ട് അടച്ചതിനാൽ സംഭാഷണം അവസാനിച്ചു." : "This conversation is closed with the report."}</p> :
      <form onSubmit={send} className="help-conversation-compose">
        <textarea value={draft} onChange={event => setDraft(event.target.value)} maxLength={4000} rows={2} placeholder={malayalam ? "സന്ദേശം എഴുതുക…" : role === "responder" ? "Share advice or ask for more information…" : "Reply to the response team…"} aria-label={malayalam ? "സന്ദേശം" : "Message"} />
        <button type="submit" disabled={sending || !draft.trim()}>{sending ? (malayalam ? "അയയ്ക്കുന്നു…" : "Sending…") : (malayalam ? "അയയ്ക്കുക" : "Send")}</button>
      </form>}
  </section>;
}
