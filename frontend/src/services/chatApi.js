// Chat API client. Set VITE_API_URL (or REACT_APP_API_URL) to your FastAPI base, e.g. http://localhost:8000
const BASE =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL) ||
  (typeof process !== "undefined" && process.env && process.env.REACT_APP_API_URL) ||
  "http://127.0.0.1:8000";

// Reads your existing JWT so Thunai can show a logged-in citizen their own incident reports.
// Change the storage key to whatever your Login module uses.
function authHeaders() {
  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token") ||
      sessionStorage.getItem("token") || sessionStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
}

export async function sendMessage({ sessionId, message, language, context }) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId || null, message, language, context: context || null }),
  });
  if (res.status === 429) throw new Error("rate_limited");
  if (!res.ok) throw new Error("request_failed");
  return res.json();
}

export async function sendFeedback(messageId, helpful) {
  await fetch(`${BASE}/api/chat/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, helpful }),
  });
}
