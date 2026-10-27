import "./Auth.css";

const PATHS = {
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></>,
  lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></>,
  eye: <><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" /><circle cx="12" cy="12" r="3" /></>,
  eyeoff: <path d="M17.9 17.9A10.9 10.9 0 0112 19C5 19 1 12 1 12a18 18 0 015-5.9M9.9 4.2A10.9 10.9 0 0112 4c7 0 11 8 11 8a18 18 0 01-2.2 3.2M1 1l22 22" />,
  pin: <><path d="M12 21s7-6 7-11a7 7 0 10-14 0c0 5 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></>,
  wave: <path d="M3 9c3-3 6 3 9 0s6 3 9 0M3 15c3-3 6 3 9 0s6 3 9 0" />,
  building: <><rect x="5" y="3" width="14" height="18" /><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2" /></>,
  id: <><rect x="4" y="4" width="16" height="16" rx="2" /><circle cx="12" cy="10" r="2.5" /><path d="M7.5 18c.7-2 2.5-3 4.5-3s3.8 1 4.5 3" /></>,
  shield: <path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z" />,
  people: <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.5" /><path d="M3 20c0-3 3-5 6-5s6 2 6 5M15 15c3 0 6 1.5 6 4.5" /></>,
  leaf: <path d="M5 19c0-8 5-14 15-14 0 10-6 15-14 15M5 19l8-8" />,
};

export function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}

function Logo() {
  return (
    <svg width="64" height="74" viewBox="0 0 60 70" aria-hidden="true">
      <path d="M30 2 L56 12 V34 C56 50 44 62 30 68 C16 62 4 50 4 34 V12 Z" fill="#fff" />
      <path d="M10 36 Q20 28 30 36 T50 36" fill="none" stroke="#1f5fbf" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M10 46 Q20 38 30 46 T50 46" fill="none" stroke="#1f5fbf" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M22 28 L30 14 L38 28" fill="none" stroke="#1f5fbf" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function RoleToggle({ role, setRole }) {
  return (
    <div className="role-toggle">
      <button type="button" className={role === "citizen" ? "active" : ""} onClick={() => setRole("citizen")}>
        <Icon name="user" /> Citizen
      </button>
      <button type="button" className={role === "rescuer" ? "active" : ""} onClick={() => setRole("rescuer")}>
        <Icon name="user" /> Rescuer
      </button>
    </div>
  );
}

// variant: "signup" | "login"   role: "citizen" | "rescuer"
export default function AuthLayout({ variant, role, children }) {
  const image =
  variant === "signup"
    ? "/auth-signup.jpg"
    : role === "rescuer"
      ? "/auth-login-rescuer.jpg"
      : "/auth-login-citizen.jpg";

  return (
    <div className="auth-shell" data-role={role}>
      <div className="auth-card2">
        <aside className={`panel panel-${variant}`} style={{ "--panel-img": `url(${image})` }}>
          <div className="panel-brand">
            <Logo />
            <h2>KAAVALAL</h2>
            <p>Safe Communities<br />Stronger Kerala</p>
          </div>

          {variant === "signup" ? (
            <div className="panel-foot">Report &nbsp;•&nbsp; Support &nbsp;•&nbsp; Save Lives</div>
          ) : (
            <div className="panel-features">
              <div><Icon name="shield" size={22} /><span>Real-time<br />alerts</span></div>
              <div><Icon name="people" size={22} /><span>Community<br />support</span></div>
              <div><Icon name="leaf" size={22} /><span>Safer<br />tomorrow</span></div>
            </div>
          )}
        </aside>

        <section className="form-side">{children}</section>
      </div>
    </div>
  );
}