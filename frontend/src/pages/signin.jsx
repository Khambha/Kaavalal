import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout, { Icon, RoleToggle } from "./AuthLayout";

const API_URL = "http://127.0.0.1:8000";

export default function Signin() {
  const navigate = useNavigate();
  const [role, setRole] = useState("citizen");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password, role }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
        throw new Error(detail || "Invalid email or password.");
      }

      const store = remember ? localStorage : sessionStorage;
      store.setItem("token", data.access_token);
      const profileResponse = await fetch(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const profile = await profileResponse.json().catch(() => ({}));
      if (!profileResponse.ok) throw new Error(profile.detail || "Could not load your account.");
      store.setItem("role", profile.role);
      navigate(["rescuer", "responder"].includes(profile.role) ? "/responder" : "/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout variant="login" role={role}>
      <form className="form" onSubmit={handleSubmit}>
        <h1>Welcome Back</h1>
        <p className="sub">Sign in to your KAAVALAL account.</p>

        <RoleToggle role={role} setRole={setRole} />

        <div className="field">
          <span className="field-icon"><Icon name="mail" /></span>
          <input type="email" placeholder="Email Address" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>

        <div className="field">
          <span className="field-icon"><Icon name="lock" /></span>
          <input type={showPw ? "text" : "password"} placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button type="button" className="eye" onClick={() => setShowPw(!showPw)} aria-label="Show or hide password">
            <Icon name={showPw ? "eye" : "eyeoff"} size={16} />
          </button>
        </div>

        <div className="options">
          <label className="remember">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember me
          </label>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>

        {error && <p className="msg error">{error}</p>}

        <button className="primary" disabled={loading}>{loading ? "Please wait..." : "Login"}</button>
        <p className="switch">
  Don't have an account? <Link to="/signup">Sign Up</Link>
</p>

      </form>
    </AuthLayout>
  );
}
