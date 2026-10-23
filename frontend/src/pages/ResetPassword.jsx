import { useState } from "react";
import { Link } from "react-router-dom";
import AuthLayout, { Icon } from "./AuthLayout";

const API_URL = "http://127.0.0.1:8000";

export default function ResetPassword() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not reset the password.");
      setMessage(data.message);
      setPassword("");
      setConfirmation("");
    } catch (err) {
      setError(err.message || "Unable to contact the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return <AuthLayout variant="login" role="citizen">
    <form className="form" onSubmit={submit}>
      <h1>Choose a new password</h1>
      <p className="sub">The reset link works once and expires after 30 minutes.</p>
      {!token&&<p className="msg error" role="alert">This reset link is missing its token. Request a new link.</p>}
      <div className="field"><span className="field-icon"><Icon name="lock" /></span><input type="password" autoComplete="new-password" placeholder="New password (at least 8 characters)" minLength={8} maxLength={128} value={password} onChange={event=>setPassword(event.target.value)} required /></div>
      <div className="field"><span className="field-icon"><Icon name="lock" /></span><input type="password" autoComplete="new-password" placeholder="Confirm new password" minLength={8} maxLength={128} value={confirmation} onChange={event=>setConfirmation(event.target.value)} required /></div>
      {message&&<p className="msg success" role="status">{message}</p>}
      {error&&<p className="msg error" role="alert">{error}</p>}
      <button className="primary" disabled={loading||!token}>{loading?"Updating…":"Update password"}</button>
      <p className="switch"><Link to="/login">Back to login</Link></p>
    </form>
  </AuthLayout>;
}
