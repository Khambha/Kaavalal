import { useState } from "react";
import { Link } from "react-router-dom";
import AuthLayout, { Icon } from "./AuthLayout";

const API_URL = "http://127.0.0.1:8000";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not request a password reset.");
      setMessage(data.message);
    } catch (err) {
      setError(err.message || "Unable to contact the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return <AuthLayout variant="login" role="citizen">
    <form className="form" onSubmit={submit}>
      <h1>Reset your password</h1>
      <p className="sub">Enter the email address on your Kaavalal account. This works for citizen and rescuer accounts.</p>
      <div className="field"><span className="field-icon"><Icon name="mail" /></span><input type="email" autoComplete="email" placeholder="Email address" value={email} onChange={event=>setEmail(event.target.value)} required /></div>
      {message&&<p className="msg success" role="status">{message}</p>}
      {error&&<p className="msg error" role="alert">{error}</p>}
      <button className="primary" disabled={loading}>{loading?"Sending…":"Send reset link"}</button>
      <p className="switch"><Link to="/login">Back to login</Link></p>
    </form>
  </AuthLayout>;
}
