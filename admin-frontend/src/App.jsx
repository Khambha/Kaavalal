import { Fragment, useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_PLATFORM_API_URL || "http://127.0.0.1:8000";
const tokenKey = "kaavalal_admin_token";

async function api(path, options = {}, token = sessionStorage.getItem(tokenKey)) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
  return data;
}

export default function App() {
  const [token, setToken] = useState(sessionStorage.getItem(tokenKey));
  const [admin, setAdmin] = useState(null);
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(sessionStorage.getItem(tokenKey)));
  const [mustChange, setMustChange] = useState(false);

  const verify = useCallback(async (jwt = token) => {
    if (!jwt) { setLoading(false); return; }
    try {
      const me = await api("/api/admin-auth/me", {}, jwt);
      setAdmin(me); setMustChange(me.must_change_password); setToken(jwt);
      sessionStorage.setItem(tokenKey, jwt);
    } catch {
      sessionStorage.removeItem(tokenKey); setToken(null); setAdmin(null);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { verify(); }, []);
  function logout() { sessionStorage.removeItem(tokenKey); setToken(null); setAdmin(null); setMustChange(false); }

  if (loading) return <div className="center"><div className="spinner"/><p>Checking admin session…</p></div>;
  if (!token || !admin) return <Login onLogin={async (jwt, user) => { sessionStorage.setItem(tokenKey, jwt); setToken(jwt); setAdmin(user); setMustChange(user.must_change_password); }} />;
  if (mustChange) return <ChangePassword onDone={() => { setMustChange(false); verify(token); }} />;

  return <div className="shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">K</div><div><b>KAAVALAL</b><small>ADMIN CONSOLE</small></div></div>
      <div className="nav-label">OPERATIONS</div>{["Overview", "People", "Organizations", "Help requests", "Alerts", "Resources", "Audit history", "Administrators"].map(name => <button key={name} className={`nav-item ${tab === name ? "selected" : ""}`} onClick={() => { setTab(name); setError(""); }}><span>{({Overview:"▦",People:"♙",Organizations:"▣", "Help requests":"⌖",Alerts:"◉",Resources:"▤", "Audit history":"◷",Administrators:"⚙"})[name]}</span>{name}</button>)}
      <div className="sidebar-bottom"><span className="secure-dot"/>Private administrator access</div>
    </aside>
    <main className="main"><header className="topbar"><div><p className="crumb">KAAVALAL / ADMIN</p><h1>{tab}</h1></div><div className="admin-menu"><div className="avatar">{admin.full_name?.[0]?.toUpperCase()}</div><div className="admin-ident"><b>{admin.full_name}</b><small>{admin.email}</small></div><button className="quiet" onClick={logout}>Sign out</button></div></header>
      {error && <div className="error-banner" role="alert">{error}<button onClick={() => setError("")}>×</button></div>}
      <section className="content"><Page tab={tab} setError={setError} token={token} /></section>
      <footer>Kaavalal Admin · Changes to accounts, requests, assignments, and alerts are recorded.</footer>
    </main>
  </div>;
}

function Login({ onLogin }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e) { e.preventDefault(); setBusy(true); setError(""); try { const data = await api("/api/admin-auth/login", { method:"POST", body:JSON.stringify({email,password}) }, null); onLogin(data.access_token, data.admin); } catch(err) { setError(err.message); } finally { setBusy(false); } }
  return <div className="login-page"><form className="login-card" onSubmit={submit}><div className="brand-mark large">K</div><p className="eyebrow">KAAVALAL · PRIVATE SITE</p><h1>Administrator sign in</h1><p className="muted">Use the credentials provided by your project administrator.</p><label>Email address<input type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} /></label>{error&&<p className="inline-error">{error}</p>}<button className="primary wide" disabled={busy}>{busy?"Signing in…":"Sign in securely"}</button><small className="muted">Admin accounts are created privately. There is no public admin signup.</small></form></div>;
}

function ChangePassword({ onDone }) {
  const [current, setCurrent] = useState(""); const [next, setNext] = useState(""); const [error, setError] = useState("");
  async function submit(e){e.preventDefault();try{await api("/api/admin-auth/change-password",{method:"POST",body:JSON.stringify({current_password:current,new_password:next})});onDone();}catch(err){setError(err.message);}}
  return <div className="login-page"><form className="login-card" onSubmit={submit}><p className="eyebrow">ACCOUNT SETUP</p><h1>Set your password</h1><p className="muted">Your account was created with a temporary password. Choose a new password with at least 12 characters.</p><label>Temporary password<input type="password" required value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>New password<input type="password" minLength="12" required value={next} onChange={e=>setNext(e.target.value)}/></label>{error&&<p className="inline-error">{error}</p>}<button className="primary wide">Update password</button></form></div>;
}

function Page({ tab, setError, token }) {
  if(tab==="Overview") return <Overview setError={setError}/>;
  if(tab==="People") return <People setError={setError}/>;
  if(tab==="Organizations") return <Organizations setError={setError}/>;
  if(tab==="Help requests") return <Requests setError={setError} token={token}/>;
  if(tab==="Alerts") return <Alerts setError={setError}/>;
  if(tab==="Resources") return <Resources setError={setError}/>;
  if(tab==="Audit history") return <Audit setError={setError}/>;
  return <Administrators setError={setError}/>;
}

function Resources({setError}) {
  const [items,setItems]=useState(null);
  const [transactions,setTransactions]=useState(null);
  const [districts,setDistricts]=useState([]);
  const [districtFilter,setDistrictFilter]=useState("");
  const [reload,setReload]=useState(0);
  const [includeInactive,setIncludeInactive]=useState(false);
  const [busy,setBusy]=useState(false);
  const [form,setForm]=useState({name:"",district:"",category:"Medical",unit:"units",quantity_available:"0",low_stock_threshold:"0"});
  const [adjustments,setAdjustments]=useState({});
  const [districtAssignments,setDistrictAssignments]=useState({});
  useEffect(()=>{let live=true;Promise.all([api(`/api/admin/resources${includeInactive?"?include_inactive=true":""}`),api("/api/admin/resource-transactions?limit=50")]).then(([resources,issues])=>{if(live){setItems(resources);setTransactions(issues);}}).catch(e=>setError(e.message));return()=>{live=false;};},[reload,includeInactive]);
  useEffect(()=>{let live=true;api("/api/help-requests/districts").then(d=>live&&setDistricts(d.districts||[])).catch(e=>setError(e.message));return()=>{live=false;};},[]);
  async function create(e){e.preventDefault();setBusy(true);try{await api("/api/admin/resources",{method:"POST",body:JSON.stringify({...form,quantity_available:Number(form.quantity_available),low_stock_threshold:Number(form.low_stock_threshold)})});setForm({name:"",district:"",category:"Medical",unit:"units",quantity_available:"0",low_stock_threshold:"0"});setReload(v=>v+1);}catch(e){setError(e.message);}finally{setBusy(false);}}
  function updateAdjustment(id,key,value){setAdjustments(v=>({...v,[id]:{direction:"add",quantity:"",reason:"",...v[id],[key]:value}}));}
  async function adjust(item){const draft=adjustments[item.id]||{};if(!draft.quantity||!draft.reason?.trim()){setError("Enter a quantity and reason for the stock change.");return;}try{await api(`/api/admin/resources/${item.id}/stock`,{method:"PATCH",body:JSON.stringify({direction:draft.direction||"add",quantity:Number(draft.quantity),reason:draft.reason.trim()})});setAdjustments(v=>({...v,[item.id]:{direction:"add",quantity:"",reason:""}}));setReload(v=>v+1);}catch(e){setError(e.message);}}
  async function toggle(item){try{await api(`/api/admin/resources/${item.id}/active?is_active=${!item.is_active}`,{method:"PATCH"});setReload(v=>v+1);}catch(e){setError(e.message);}}
  async function assignDistrict(item){const district=districtAssignments[item.id];if(!district){setError("Choose a district for this existing inventory item.");return;}try{await api(`/api/admin/resources/${item.id}/district`,{method:"PATCH",body:JSON.stringify({district})});setReload(v=>v+1);}catch(e){setError(e.message);}}
  const lowStock=(items||[]).filter(item=>item.is_active&&item.quantity_available<=item.low_stock_threshold).length;
  const visibleItems=(items||[]).filter(item=>!districtFilter||item.district===districtFilter);
  return <>
    <div className="toolbar"><div><h2>District relief inventory</h2><p>Stock is tracked separately for each district. Add the same item again to record its stock in another district.</p></div><div className="inventory-filters"><label>District<select value={districtFilter} onChange={e=>setDistrictFilter(e.target.value)}><option value="">All districts</option>{districts.map(name=><option key={name}>{name}</option>)}</select></label><label className="inventory-toggle"><input type="checkbox" checked={includeInactive} onChange={e=>setIncludeInactive(e.target.checked)}/> Show inactive items</label></div></div>
    <div className="stats-grid inventory-stats"><Stat label="Active items" value={(items||[]).filter(item=>item.is_active).length}/><Stat label="At or below low-stock threshold" value={lowStock}/></div>
    <div className="columns admin-layout"><form className="panel form-panel" onSubmit={create}><h3>Add item to district stock</h3><label>District<select required value={form.district} onChange={e=>setForm(v=>({...v,district:e.target.value}))}><option value="">Choose district</option>{districts.map(name=><option key={name}>{name}</option>)}</select></label><label>Item name<input required minLength="2" maxLength="120" value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))} placeholder="Drinking water"/></label><label>Category<input required minLength="2" maxLength="60" value={form.category} onChange={e=>setForm(v=>({...v,category:e.target.value}))} placeholder="Food, medical, shelter…"/></label><div className="two-fields"><label>Unit<input required maxLength="40" value={form.unit} onChange={e=>setForm(v=>({...v,unit:e.target.value}))} placeholder="bottles, kits, meals"/></label><label>Starting quantity<input type="number" min="0" required value={form.quantity_available} onChange={e=>setForm(v=>({...v,quantity_available:e.target.value}))}/></label></div><label>Low-stock warning at<input type="number" min="0" required value={form.low_stock_threshold} onChange={e=>setForm(v=>({...v,low_stock_threshold:e.target.value}))}/></label><button className="primary" disabled={busy}>{busy?"Saving…":"Add item"}</button></form>
      <div className="resource-list">{visibleItems.map(item=>{const draft=adjustments[item.id]||{direction:"add",quantity:"",reason:""};const low=item.quantity_available<=item.low_stock_threshold;return <article className="panel resource-card" key={item.id}><div className="resource-head"><div><span className="eyebrow">{item.district||"District not assigned"} · {item.category}</span><h3>{item.name}</h3></div><Pill value={!item.is_active?"inactive":low?"low stock":"in stock"}/></div>{!item.district&&<div className="resource-assign"><select aria-label={`Assign district for ${item.name}`} value={districtAssignments[item.id]||""} onChange={e=>setDistrictAssignments(v=>({...v,[item.id]:e.target.value}))}><option value="">Choose district</option>{districts.map(name=><option key={name}>{name}</option>)}</select><button className="secondary" onClick={()=>assignDistrict(item)}>Assign district</button></div>}<p className="resource-balance"><b>{item.quantity_available}</b> {item.unit} available <span>· alert below {item.low_stock_threshold}</span></p>{item.is_active&&<div className="resource-adjust"><select aria-label={`Stock adjustment for ${item.name} in ${item.district||"unassigned district"}`} value={draft.direction} onChange={e=>updateAdjustment(item.id,"direction",e.target.value)}><option value="add">Add stock</option><option value="remove">Remove stock</option></select><input aria-label="Quantity" type="number" min="1" value={draft.quantity} onChange={e=>updateAdjustment(item.id,"quantity",e.target.value)} placeholder="Quantity"/><input aria-label="Reason" value={draft.reason} onChange={e=>updateAdjustment(item.id,"reason",e.target.value)} placeholder="Reason for change"/><button className="secondary" onClick={()=>adjust(item)}>Update stock</button></div>}<button className="text-button" onClick={()=>toggle(item)}>{item.is_active?"Deactivate item":"Reactivate item"}</button></article>})}{items&&!visibleItems.length&&<div className="panel empty">No items in this district yet. Add one using the form.</div>}</div>
    </div><div className="panel resource-history"><div className="panel-head"><div><h3>Recent responder issues</h3><p>Most recent 50 stock issues recorded from the rescuer module</p></div></div><div className="table-scroll"><table><thead><tr><th>Issued</th><th>Responder</th><th>Item</th><th>District</th><th>Quantity</th><th>Help request</th><th>Reason</th></tr></thead><tbody>{transactions?.map(issue=><tr key={issue.id}><td>{new Date(issue.created_at).toLocaleString()}</td><td><b>{issue.responder_name}</b><small>{issue.responder_email}</small></td><td>{issue.resource_name}</td><td>{issue.district}</td><td>{issue.quantity} {issue.unit}</td><td>{issue.help_request_id?`#${issue.help_request_id}`:"—"}</td><td>{issue.reason}</td></tr>)}{transactions&&!transactions.length&&<tr><td colSpan="7" className="empty">No resources have been issued by responders yet.</td></tr>}</tbody></table></div></div><p className="note">Same-named items can exist in different districts and keep independent balances. Removing stock is limited to that district’s available amount. All stock changes and responder issues are recorded.</p>
  </>;
}

function Organizations({setError}) {
  const [organizations,refresh]=useLoad("/api/admin/organizations",setError);
  const [form,setForm]=useState({organization_name:"",organization_code:"",organization_type:"Rescue service",district:""});
  const [busy,setBusy]=useState(false);
  async function create(e){e.preventDefault();setError("");setBusy(true);try{await api("/api/admin/organizations",{method:"POST",body:JSON.stringify({...form,district:form.district||null})});setForm({organization_name:"",organization_code:"",organization_type:"Rescue service",district:""});refresh();}catch(err){setError(err.message);}finally{setBusy(false);}}
  async function toggle(item){try{await api(`/api/admin/organizations/${item.id}/active?is_active=${!item.is_active}`,{method:"PATCH"});refresh();}catch(err){setError(err.message);}}
  return <><div className="toolbar"><div><h2>Responder organizations</h2><p>Organizations identify response groups. Assign their responders to LACs separately under People.</p></div></div><div className="columns admin-layout"><form className="panel form-panel" onSubmit={create}><h3>Add an organization</h3><label>Organization name<input required minLength="2" value={form.organization_name} onChange={e=>setForm(v=>({...v,organization_name:e.target.value}))} placeholder="e.g. Palakkad Community Response Team"/></label><label>Organization code<input required minLength="3" pattern="[A-Za-z0-9][A-Za-z0-9_-]*" value={form.organization_code} onChange={e=>setForm(v=>({...v,organization_code:e.target.value.toUpperCase()}))} placeholder="e.g. PALAKKAD-CRT"/><small className="muted">Share this code with verified members who are registering as rescuers.</small></label><label>Organization type<select value={form.organization_type} onChange={e=>setForm(v=>({...v,organization_type:e.target.value}))}>{["Rescue service","Fire and rescue","Civil defence","Medical","NGO","Local government","Other"].map(type=><option key={type}>{type}</option>)}</select></label><label>Base district (optional)<input value={form.district} onChange={e=>setForm(v=>({...v,district:e.target.value}))} placeholder="Palakkad"/></label><button className="primary" disabled={busy}>{busy?"Creating…":"Create organization"}</button></form><div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>Organization</th><th>Code</th><th>Base district</th><th>Responders</th><th>Status</th><th></th></tr></thead><tbody>{organizations?.map(item=><tr key={item.id}><td><b>{item.organization_name}</b><small>{item.organization_type}</small></td><td><code>{item.organization_code}</code></td><td>{item.district||"—"}</td><td>{item.responder_count}</td><td><Pill value={item.is_active?"active":"inactive"}/></td><td><button className="text-button" onClick={()=>toggle(item)}>{item.is_active?"Deactivate":"Reactivate"}</button></td></tr>)}{organizations&&!organizations.length&&<tr><td colSpan="6" className="empty">No organizations created yet.</td></tr>}</tbody></table></div></div></div><p className="note">You do not need a separate organization for every LAC. Create actual responder groups here, then use People → Manage LACs to set each responder’s coverage.</p></>;
}

function useLoad(path, setError) {
  const [data,setData]=useState(null); const [reload,setReload]=useState(0);
  const refresh=()=>setReload(v=>v+1);
  useEffect(()=>{let live=true;api(path).then(d=>{if(live)setData(d);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[path,reload]);
  return [data,refresh];
}

function Overview({setError}) {
  const [stats]=useLoad("/api/admin/dashboard",setError);if(!stats)return <div className="loading-line">Loading current platform data…</div>;
  const responders=(stats.users.by_role.rescuer||0)+(stats.users.by_role.responder||0);
  return <><div className="welcome"><div><span className="eyebrow">SYSTEM OVERVIEW</span><h2>Kerala operations at a glance</h2><p>Live totals from the platform database.</p></div><span className="live"><i/>Connected</span></div>
    <div className="stats-grid"><Stat label="Registered users" value={stats.users.total}/><Stat label="Citizens" value={stats.users.by_role.citizen||0}/><Stat label="Response team" value={responders}/><Stat label="Administrators" value={stats.administrators.total}/><Stat label="Open help requests" value={stats.help_requests.active_or_unresolved}/><Stat label="Awaiting review" value={stats.help_requests.pending}/><Stat label="Published alerts" value={stats.alerts.published}/><Stat label="Active resource items" value={stats.resources?.active||0}/><Stat label="Low-stock items" value={stats.resources?.low_stock||0}/></div>
    <div className="columns"><div className="panel"><div className="panel-head"><div><h3>Help request statuses</h3><p>Current breakdown</p></div></div><div className="status-list">{Object.entries(stats.help_requests.by_status).map(([s,n])=><div key={s}><span>{s}</span><b>{n}</b></div>)}</div></div><div className="panel"><div className="panel-head"><div><h3>Recent administrator activity</h3><p>Most recent 10 recorded changes</p></div></div><Activity items={stats.recent_activity}/></div></div>
    {stats.not_yet_modeled?.length>0&&<p className="note">Data not yet available in the platform: {stats.not_yet_modeled.join(", ")}.</p>}
  </>;
}
function Stat({label,value}){return <article className="stat-card"><span>{label}</span><b>{value??0}</b></article>}
function Activity({items=[]}){return !items.length?<p className="empty">No administrator actions recorded yet.</p>:<ul className="activity">{items.map(item=><li key={item.id}><b>{item.action.replaceAll("_"," ")}</b><span>{item.details||item.target_type}</span><small>{new Date(item.created_at).toLocaleString()}</small></li>)}</ul>}

function People({setError}) {
  const [search,setSearch]=useState("");const [role,setRole]=useState("");const [status,setStatus]=useState("");const [reload,setReload]=useState(0);const [data,setData]=useState(null);const [coverageUser,setCoverageUser]=useState(null);
  useEffect(()=>{let live=true;const qs=new URLSearchParams({limit:"100"});if(search)qs.set("search",search);if(role)qs.set("role",role);if(status)qs.set("status",status);api(`/api/admin/users?${qs}`).then(d=>live&&setData(d)).catch(e=>setError(e.message));return()=>{live=false;};},[search,role,status,reload]);
  async function update(user,body){try{await api(`/api/admin/users/${user.id}`,{method:"PATCH",body:JSON.stringify(body)});setReload(x=>x+1);}catch(e){setError(e.message);}}
  return <><div className="toolbar"><div><h2>People and response teams</h2><p>Review signups and manage access to the main platform.</p></div><div className="filters"><input placeholder="Search name or email" value={search} onChange={e=>setSearch(e.target.value)}/><select value={role} onChange={e=>setRole(e.target.value)}><option value="">All roles</option><option value="citizen">Citizen</option><option value="responder">Responder</option></select><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{["active","pending","rejected","suspended","inactive"].map(v=><option key={v}>{v}</option>)}</select></div></div>
    <div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>Person</th><th>Role</th><th>District</th><th>Account</th><th>Role control</th><th>Access</th><th>LAC coverage</th></tr></thead><tbody>{data?.users.map(u=><Fragment key={u.id}><tr><td><b>{u.full_name}</b><small>{u.email}</small></td><td><Pill value={u.role}/></td><td>{u.district||"—"}</td><td><Pill value={u.status}/></td><td><select value={u.role==="rescuer"?"responder":u.role} onChange={e=>update(u,{role:e.target.value})}><option value="citizen">Citizen</option><option value="responder">Responder</option></select></td><td><button className="text-button" onClick={()=>update(u,{status:u.status==="active"?"suspended":"active"})}>{u.status==="active"?"Suspend":"Activate"}</button>{u.role==="rescuer"&&u.status==="pending"&&<button className="text-button approve" onClick={()=>update(u,{status:"active"})}>Approve</button>}</td><td>{["rescuer","responder"].includes(u.role)&&<button className="text-button" onClick={()=>setCoverageUser(coverageUser===u.id?null:u.id)}>{coverageUser===u.id?"Close":"Manage LACs"}</button>}</td></tr>{coverageUser===u.id&&<tr><td colSpan="7"><CoverageEditor user={u} onSaved={()=>{setCoverageUser(null);setReload(x=>x+1);}} onCancel={()=>setCoverageUser(null)} setError={setError}/></td></tr>}</Fragment>)}{data&&!data.users.length&&<tr><td colSpan="7" className="empty">No matching accounts.</td></tr>}</tbody></table></div></div>
    <p className="note">Administrator accounts are separate from platform user roles and are managed in the Administrators section.</p>
  </>;
}

function CoverageEditor({user,onSaved,onCancel,setError}) {
  const [districts,setDistricts]=useState([]);const [areas,setAreas]=useState(user.coverage?.length?user.coverage:[{district:user.district||"",lac:user.nearest_lac||""}]);const [options,setOptions]=useState({});const [busy,setBusy]=useState(false);
  useEffect(()=>{let live=true;api("/api/help-requests/districts").then(data=>live&&setDistricts(data.districts||[])).catch(e=>setError(e.message));return()=>{live=false;};},[setError]);
  useEffect(()=>{let live=true;areas.forEach((area,index)=>{if(!area.district)return;api(`/api/help-requests/lacs/${encodeURIComponent(area.district)}`).then(data=>{if(live)setOptions(prev=>({...prev,[index]:data.lacs||[]}));}).catch(()=>{});});return()=>{live=false;};},[areas]);
  function update(index,key,value){setAreas(prev=>prev.map((area,i)=>i===index?{...area,[key]:value,...(key==="district"?{lac:""}:{})}:area));}
  async function save(){if(areas.some(area=>!area.district||!area.lac)){setError("Choose a district and LAC for each coverage area.");return;}setBusy(true);try{await api(`/api/admin/users/${user.id}/coverage`,{method:"PUT",body:JSON.stringify({coverage:areas})});onSaved();}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <div className="coverage-editor"><b>Responder coverage · choose one or two LACs</b>{areas.map((area,index)=><div className="coverage-row" key={index}><select value={area.district} onChange={e=>update(index,"district",e.target.value)}><option value="">Choose district</option>{districts.map(d=><option key={d} value={d}>{d}</option>)}</select><select value={area.lac} onChange={e=>update(index,"lac",e.target.value)} disabled={!area.district}><option value="">Choose LAC</option>{(options[index]||[]).map(lac=><option key={lac} value={lac}>{lac}</option>)}</select>{areas.length>1&&<button className="text-button" onClick={()=>setAreas(prev=>prev.filter((_,i)=>i!==index))}>Remove</button>}</div>)}{areas.length<2&&<button className="text-button" onClick={()=>setAreas(prev=>[...prev,{district:"",lac:""}])}>+ Add another LAC</button>}<div className="button-row"><button className="primary small" disabled={busy} onClick={save}>{busy?"Saving…":"Save coverage"}</button><button className="secondary" onClick={onCancel}>Cancel</button></div></div>;
}
function Pill({value}){return <span className={`pill ${String(value).toLowerCase().replaceAll(" ","-")}`}>{value}</span>}

function Requests({setError,token}) {
  const [data,setData]=useState(null);const [users,setUsers]=useState([]);const [filter,setFilter]=useState("");const [reload,setReload]=useState(0);const [reasons,setReasons]=useState({});
  useEffect(()=>{let live=true;const qs=new URLSearchParams({limit:"100"});if(filter)qs.set("status",filter);Promise.all([api(`/api/admin/requests?${qs}`),api("/api/admin/users?role=responder&status=active&limit=100")]).then(([r,u])=>{if(live){setData(r);setUsers(u.users);}}).catch(e=>setError(e.message));return()=>{live=false;};},[filter,reload]);
  async function setStatus(item,status){const reason=reasons[item.id]||"";if(["Resolved","Rejected"].includes(status)&&reason.trim().length<3){setError("Enter a reason before resolving or rejecting a request.");return;}try{await api(`/api/admin/requests/${item.id}/status`,{method:"PATCH",body:JSON.stringify({status,reason:reason||null})});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function assign(item,responder_id){try{await api(`/api/admin/requests/${item.id}/assignment`,{method:"PATCH",body:JSON.stringify({responder_id:responder_id?Number(responder_id):null})});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function openAttachment(item){const tab=window.open("about:blank","_blank");try{const response=await fetch(`${API}/api/admin/requests/${item.id}/attachment`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||"Could not open attachment.");}const url=URL.createObjectURL(await response.blob());if(tab)tab.location.href=url;else window.location.href=url;}catch(e){tab?.close();setError(e.message);}}
  return <><div className="toolbar"><div><h2>Help requests</h2><p>Review reports, update status, and assign active responders.</p></div><select className="filter-select" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All statuses</option>{["Submitted","Under Review","Assigned","In Progress","Resolved","Rejected"].map(s=><option key={s}>{s}</option>)}</select></div>
    <div className="request-list">{data?.items.map(item=><article className="panel request-card" key={item.id}><div className="request-title"><div><span className="eyebrow">{item.district} · {item.lac} · #{item.id}</span><h3>{item.emergency_type}</h3></div><Pill value={item.status}/></div><p>{item.situation_description}</p><div className="request-meta"><span>Urgency: <b>{item.urgency}</b></span><span>People affected: <b>{item.people_affected}</b></span><span>Received: <b>{new Date(item.created_at).toLocaleString()}</b></span></div>{item.image_path&&<button className="text-button" onClick={()=>openAttachment(item)}>View attached evidence</button>}
      <div className="request-actions"><label>Assign responder<select value={item.assigned_responder_id||""} disabled={["Resolved","Rejected"].includes(item.status)} onChange={e=>assign(item,e.target.value)}><option value="">Unassigned</option>{users.filter(u=>(u.coverage||[]).some(area=>area.district.toLowerCase()===item.district.toLowerCase()&&area.lac.toLowerCase()===item.lac.toLowerCase())).map(u=><option key={u.id} value={u.id}>{u.full_name} · {u.district||""}</option>)}</select></label><label>Reason for rejection/resolution<input placeholder="Required for resolved or rejected" value={reasons[item.id]||""} onChange={e=>setReasons(v=>({...v,[item.id]:e.target.value}))}/></label><label>Update status<select value={item.status} onChange={e=>setStatus(item,e.target.value)}>{["Submitted","Under Review","Assigned","In Progress","Resolved","Rejected"].map(s=><option key={s}>{s}</option>)}</select></label></div>
    </article>)}{data&&!data.items.length&&<div className="panel empty">No requests found for this filter.</div>}</div>
  </>;
}

function Alerts({setError}) {
  const [alerts,setAlerts]=useState(null);const [reload,setReload]=useState(0);const [form,setForm]=useState({title:"",message:"",severity:"warning",district:"",expires_at:""});
  useEffect(()=>{let live=true;api("/api/admin/alerts").then(d=>live&&setAlerts(d)).catch(e=>setError(e.message));return()=>{live=false;};},[reload]);
  function change(e){setForm(v=>({...v,[e.target.name]:e.target.value}));}
  async function create(e){e.preventDefault();try{await api("/api/admin/alerts",{method:"POST",body:JSON.stringify({...form,district:form.district||null,expires_at:form.expires_at?new Date(form.expires_at).toISOString():null})});setForm({title:"",message:"",severity:"warning",district:"",expires_at:""});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function act(item,action){try{await api(`/api/admin/alerts/${item.id}/${action}`,{method:"POST"});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function edit(item){const title=window.prompt("Edit alert title",item.title);if(title===null)return;const message=window.prompt("Edit alert message",item.message);if(message===null)return;try{await api(`/api/admin/alerts/${item.id}`,{method:"PATCH",body:JSON.stringify({title,message})});setReload(x=>x+1);}catch(e){setError(e.message);}}
  return <><div className="toolbar"><div><h2>Disaster alerts</h2><p>Draft, submit for review, publish, withdraw, or expire platform alerts.</p></div></div><div className="columns alert-layout"><form className="panel form-panel" onSubmit={create}><h3>New alert draft</h3><label>Headline<input name="title" minLength="4" required value={form.title} onChange={change}/></label><label>Public message<textarea name="message" minLength="10" rows="5" required value={form.message} onChange={change}/></label><div className="two-fields"><label>Severity<select name="severity" value={form.severity} onChange={change}>{["info","advisory","warning","emergency"].map(v=><option key={v}>{v}</option>)}</select></label><label>District (optional)<input name="district" value={form.district} onChange={change} placeholder="All Kerala"/></label></div><label>Expires at (optional)<input type="datetime-local" name="expires_at" value={form.expires_at} onChange={change}/></label><button className="primary">Save draft</button></form><div className="alert-list">{alerts?.map(item=><article className="panel alert-card" key={item.id}><div className="request-title"><div><span className="eyebrow">{item.district||"ALL KERALA"} · {item.severity.toUpperCase()}</span><h3>{item.title}</h3></div><Pill value={item.status}/></div><p>{item.message}</p>{item.expires_at&&<small className="muted">Expires {new Date(item.expires_at).toLocaleString()}</small>}<div className="button-row">{["draft","review"].includes(item.status)&&<><button className="secondary" onClick={()=>edit(item)}>Edit</button>{item.status==="draft"?<button className="secondary" onClick={()=>act(item,"submit-review")}>Submit for review</button>:<button className="primary small" onClick={()=>act(item,"publish")}>Approve & publish</button>}</>}{item.status==="published"&&<><button className="secondary" onClick={()=>act(item,"withdraw")}>Withdraw</button>{item.expires_at&&new Date(item.expires_at)<=new Date()&&<button className="secondary" onClick={()=>act(item,"expire")}>Mark expired</button>}</>}</div></article>)}{alerts&&!alerts.length&&<div className="panel empty">No alerts yet.</div>}</div></div><p className="note">Publishing makes an alert available from the platform’s public alerts API. Verify the warning details and expiry before publishing.</p></>;
}

function Audit({setError}){const [data]=useLoad("/api/admin/audit-logs?limit=100",setError);return <><div className="toolbar"><div><h2>Audit history</h2><p>Actions by admin account, target, time, and outcome details.</p></div></div><div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>Time</th><th>Administrator</th><th>Action</th><th>Target</th><th>Details</th></tr></thead><tbody>{data?.items.map(item=><tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.admin_name||`Admin #${item.admin_user_id}`}</td><td>{item.action.replaceAll("_"," ")}</td><td>{item.target_type} #{item.target_id||"—"}</td><td>{item.details||"—"}</td></tr>)}</tbody></table></div></div></>}

function Administrators({setError}) {
  const [admins,setAdmins]=useState(null);const [reload,setReload]=useState(0);const [form,setForm]=useState({full_name:"",email:"",temporary_password:""});
  useEffect(()=>{let live=true;api("/api/admin/admins").then(d=>live&&setAdmins(d)).catch(e=>setError(e.message));return()=>{live=false;};},[reload]);
  async function create(e){e.preventDefault();try{await api("/api/admin/admins",{method:"POST",body:JSON.stringify(form)});setForm({full_name:"",email:"",temporary_password:""});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function toggle(admin){try{await api(`/api/admin/admins/${admin.id}/active?is_active=${!admin.is_active}`,{method:"PATCH"});setReload(x=>x+1);}catch(e){setError(e.message);}}
  return <><div className="toolbar"><div><h2>Administrator accounts</h2><p>Only existing administrators can create another admin account.</p></div></div><div className="columns admin-layout"><form className="panel form-panel" onSubmit={create}><h3>Add administrator</h3><label>Full name<input required minLength="2" value={form.full_name} onChange={e=>setForm(v=>({...v,full_name:e.target.value}))}/></label><label>Email<input required type="email" value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></label><label>Temporary password<input required minLength="12" type="password" value={form.temporary_password} onChange={e=>setForm(v=>({...v,temporary_password:e.target.value}))}/></label><p className="note">Share the temporary password privately. The new admin must change it on first sign-in.</p><button className="primary">Create admin</button></form><div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>Admin</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>{admins?.map(a=><tr key={a.id}><td><b>{a.full_name}</b><small>{a.email}</small></td><td><Pill value={a.is_active?"active":"inactive"}/></td><td>{new Date(a.created_at).toLocaleDateString()}</td><td><button className="text-button" onClick={()=>toggle(a)}>{a.is_active?"Deactivate":"Reactivate"}</button></td></tr>)}</tbody></table></div></div></div></>;
}
