import { Fragment, useCallback, useEffect, useState } from "react";
import "./shelter-workflow.css";

const API = import.meta.env.VITE_PLATFORM_API_URL || import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const tokenKey = "kaavalal_admin_token";

function formatApiError(detail, fallback) {
  if (Array.isArray(detail)) {
    return detail.map(item => {
      const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "Form";
      return `${field}: ${item.msg || "is invalid"}`;
    }).join(" · ");
  }
  if (detail && typeof detail === "object") return detail.message || JSON.stringify(detail);
  return detail || fallback;
}

async function api(path, options = {}, token = sessionStorage.getItem(tokenKey)) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(formatApiError(data.detail, `Request failed (${response.status}).`));
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
      <div className="nav-label">OPERATIONS</div>{["Overview", "People", "Organizations", "Help requests", "Shelters", "Alerts", "Resources", "Audit history", "Administrators"].map(name => <button key={name} className={`nav-item ${tab === name ? "selected" : ""}`} onClick={() => { setTab(name); setError(""); }}><span>{({Overview:"▦",People:"♙",Organizations:"▣", "Help requests":"⌖",Shelters:"⌂",Alerts:"◉",Resources:"▤", "Audit history":"◷",Administrators:"⚙"})[name]}</span>{name}</button>)}
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
  if(tab==="Shelters") return <Shelters setError={setError}/>;
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
    </div><div className="panel resource-history"><div className="panel-head"><div><h3>Recent responder issues</h3><p>Most recent 50 stock issues recorded from the rescuer module</p></div></div><div className="table-scroll"><table><thead><tr><th>Time</th><th>Responder</th><th>Item</th><th>District</th><th>Quantity</th><th>Help request</th><th>Reason</th></tr></thead><tbody>{transactions?.map(issue=><tr key={issue.id}><td>{new Date(issue.created_at).toLocaleString()}</td><td><b>{issue.responder_name}</b><small>{issue.responder_email}</small></td><td>{issue.resource_name}</td><td>{issue.district}</td><td>{issue.quantity} {issue.unit}</td><td>{issue.help_request_id?`#${issue.help_request_id}`:"—"}</td><td>{issue.reason}</td></tr>)}{transactions&&!transactions.length&&<tr><td colSpan="7" className="empty">No resources have been issued by responders yet.</td></tr>}</tbody></table></div></div><p className="note">Same-named items can exist in different districts and keep independent balances. Removing stock is limited to that district’s available amount. All stock changes and responder issues are recorded.</p>
  </>;
}

function Shelters({setError}) {
  const [items,refresh]=useLoad("/api/admin/shelters",setError);
  const [candidateItems,refreshCandidates]=useLoad("/api/admin/shelters/auditorium-candidates",setError);
  const [districts,setDistricts]=useState([]); const [lacs,setLacs]=useState([]); const [busy,setBusy]=useState(false);
  const [success,setSuccess]=useState(""); const [locationCheck,setLocationCheck]=useState(null);
  const [editingId,setEditingId]=useState(null); const [districtFilter,setDistrictFilter]=useState("");
  const [reviewOnly,setReviewOnly]=useState(false); const [currentPage,setCurrentPage]=useState(1); const [importing,setImporting]=useState(false);
  const [candidatePage,setCandidatePage]=useState(1); const [importingAuditoriums,setImportingAuditoriums]=useState(false);
  const pageSize=25;
  const [form,setForm]=useState({name:"",building_type:"School",district:"",lac:"",address:"",latitude:"",latitude_hemisphere:"N",longitude:"",longitude_hemisphere:"E",capacity:"",is_active:true});
  useEffect(()=>{const interval=window.setInterval(()=>{refresh();refreshCandidates();},15000);return()=>window.clearInterval(interval);},[refresh,refreshCandidates]);
  useEffect(()=>{api("/api/help-requests/districts").then(d=>setDistricts(d.districts||[])).catch(e=>setError(e.message));},[]);
  useEffect(()=>{let live=true;if(!form.district){setLacs([]);return()=>{live=false;};}api(`/api/help-requests/lacs/${encodeURIComponent(form.district)}`).then(d=>live&&setLacs(d.lacs||[])).catch(e=>live&&setError(e.message));return()=>{live=false;};},[form.district]);
  function locate(){if(!navigator.geolocation){setError("Location access is unavailable in this browser.");return;}navigator.geolocation.getCurrentPosition(p=>{setLocationCheck(null);setForm(v=>({...v,latitude:Math.abs(p.coords.latitude).toFixed(6),latitude_hemisphere:p.coords.latitude<0?"S":"N",longitude:Math.abs(p.coords.longitude).toFixed(6),longitude_hemisphere:p.coords.longitude<0?"W":"E"}));},()=>setError("Could not read location. Enter latitude and longitude manually."),{enableHighAccuracy:true,timeout:10000});}
  function signedCoordinates(){return {latitude:Number(form.latitude)*(form.latitude_hemisphere==="S"?-1:1),longitude:Number(form.longitude)*(form.longitude_hemisphere==="W"?-1:1)};}
  function resetForm(){setForm({name:"",building_type:"School",district:"",lac:"",address:"",latitude:"",latitude_hemisphere:"N",longitude:"",longitude_hemisphere:"E",capacity:"",is_active:true});setLocationCheck(null);setEditingId(null);}
  function editShelter(item){setEditingId(item.id);setLocationCheck(null);setForm({name:item.name,building_type:item.building_type,district:item.district,lac:item.lac,address:item.address,latitude:String(Math.abs(item.latitude)),latitude_hemisphere:item.latitude<0?"S":"N",longitude:String(Math.abs(item.longitude)),longitude_hemisphere:item.longitude<0?"W":"E",capacity:String(item.capacity),is_active:item.is_active});window.scrollTo({top:0,behavior:"smooth"});}
  async function checkLocation(){setError("");setLocationCheck({valid:null,message:"Checking the pin against the selected district…"});const point=signedCoordinates();if(form.latitude_hemisphere!=="N"||form.longitude_hemisphere!=="E"||point.latitude<8||point.latitude>13||point.longitude<74||point.longitude>78){const message="Shelter locations must be in Kerala (8–13° N, 74–78° E). Check the coordinate order and hemisphere.";setLocationCheck({valid:false,message});setError(message);return false;}try{await api("/api/admin/shelters/validate-location",{method:"POST",body:JSON.stringify({...point,district:form.district,lac:form.lac})});setLocationCheck({valid:true,message:`Pin is inside ${form.district} district and ${form.lac} LAC.`});return true;}catch(e){setLocationCheck({valid:false,message:e.message});setError(e.message);return false;}}
  async function create(e){e.preventDefault();setError("");setSuccess("");const valid=await checkLocation();if(!valid)return;const point=signedCoordinates();const wasEditing=Boolean(editingId);setBusy(true);try{const path=wasEditing?`/api/admin/shelters/${editingId}`:"/api/admin/shelters";const created=await api(path,{method:wasEditing?"PATCH":"POST",body:JSON.stringify({...form,name:form.name.trim(),address:form.address.trim(),...point,capacity:Number(form.capacity)})});resetForm();refresh();setSuccess(wasEditing?`${created.name} was updated.`:`${created.name} was added.`);}catch(e){setError(e.message);setLocationCheck({valid:false,message:e.message});}finally{setBusy(false);}}
  async function toggle(item){try{await api(`/api/admin/shelters/${item.id}/active?is_active=${!item.is_active}`,{method:"PATCH"});refresh();}catch(e){setError(e.message);}}
  async function importCamps(){
    if(!window.confirm("Import the prepared KSDMA camp records as inactive candidates? Every imported camp will require admin review before it can accept citizen requests."))return;
    setImporting(true);setError("");setSuccess("");
    try{const result=await api("/api/admin/shelters/import-ksdma-camps",{method:"POST"});refresh();setReviewOnly(true);setCurrentPage(1);setSuccess(`${result.imported} camp candidates imported; ${result.already_imported} were already present. ${result.message}`);}
    catch(e){setError(e.message);}finally{setImporting(false);}
  }
  async function importAuditoriumDemo(){
    if(!window.confirm("Add two high-confidence auditorium map suggestions from each district as review-only candidates? Capacity is unknown, so these will not be active shelters."))return;
    setImportingAuditoriums(true);setError("");setSuccess("");
    try{const result=await api("/api/admin/shelters/import-auditorium-demo",{method:"POST"});refreshCandidates();setCandidatePage(1);setSuccess(`${result.imported} auditorium demo candidates added; ${result.already_imported} were already present. ${result.message}`);}
    catch(e){setError(e.message);}finally{setImportingAuditoriums(false);}
  }
  async function markReviewed(item){
    if(!window.confirm(`Confirm that you reviewed the map pin, district, LAC, and capacity for “${item.name}”?`))return;
    try{await api(`/api/admin/shelters/${item.id}/review`,{method:"PATCH"});refresh();setSuccess(`${item.name} marked as reviewed. It remains inactive until you switch it on.`);}
    catch(e){setError(e.message);}
  }
  const visibleItems=(items||[]).filter(item=>(!districtFilter||item.district===districtFilter)&&(!reviewOnly||item.needs_review));
  const pageCount=Math.max(1,Math.ceil(visibleItems.length/pageSize));
  const pageItems=visibleItems.slice((currentPage-1)*pageSize,currentPage*pageSize);
  const auditoriumCandidates=(candidateItems||[]).filter(item=>!districtFilter||item.district===districtFilter);
  const candidatePageSize=10;
  const candidatePageCount=Math.max(1,Math.ceil(auditoriumCandidates.length/candidatePageSize));
  const visibleCandidates=auditoriumCandidates.slice((candidatePage-1)*candidatePageSize,candidatePage*candidatePageSize);
  const districtStats=[...new Set((items||[]).map(item=>item.district))].filter(district=>!districtFilter||district===districtFilter).sort().map(district=>{
    const shelters=(items||[]).filter(item=>item.district===district);
    const confirmed=shelters.filter(item=>!item.needs_review);
    return {district,shelterCount:confirmed.length,candidateCount:shelters.filter(item=>item.needs_review).length,activeCount:confirmed.filter(item=>item.is_active).length,occupied:confirmed.reduce((sum,item)=>sum+item.occupied,0),capacity:confirmed.reduce((sum,item)=>sum+item.capacity,0)};
  });
  return <>
    <div className="toolbar"><div><h2>Emergency shelters</h2><p>Manage shelter locations, capacity, and availability by district.</p></div><div className="shelter-toolbar-actions"><button className="secondary" disabled={importing} onClick={importCamps}>{importing?"Importing camps…":"Import KSDMA camps"}</button><button className="secondary" disabled={importingAuditoriums} onClick={importAuditoriumDemo}>{importingAuditoriums?"Adding demo…":"Add auditorium demo"}</button><span className="live"><i/>Admin controlled</span></div></div>
    {success&&<div className="shelter-success" role="status">{success}</div>}
    <section className="shelter-district-summary" aria-label="Shelter totals by district">{districtStats.length?districtStats.map(item=><article className="shelter-district-card" key={item.district}><div><span>District</span><h3>{item.district}</h3></div><strong>{item.occupied}<small> / {item.capacity} confirmed spaces</small></strong><footer><span>{item.activeCount} active</span><span>{item.shelterCount} confirmed</span><span>{item.candidateCount} to review</span></footer></article>):<p className="panel empty">No shelters have been added yet.</p>}</section>
    <div className="toolbar shelter-directory-toolbar"><div><h2>Shelter directory</h2><p>Choose a district to manage its shelters.</p></div><div className="inventory-filters"><label>District<select value={districtFilter} onChange={e=>{setDistrictFilter(e.target.value);setCurrentPage(1);setCandidatePage(1);}}><option value="">All districts</option>{districts.map(name=><option key={name}>{name}</option>)}</select></label><label className="inventory-toggle"><input type="checkbox" checked={reviewOnly} onChange={e=>{setReviewOnly(e.target.checked);setCurrentPage(1);}}/>Needs review only</label></div></div>
    <div className="columns admin-layout"><form className="panel form-panel shelter-form" onSubmit={create}><h3>{editingId?"Edit shelter details":"Add a shelter"}</h3>
      <label>Site name<input required minLength="2" value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))} placeholder="Municipal Stadium"/></label>
      <label>Building type<select value={form.building_type} onChange={e=>setForm(v=>({...v,building_type:e.target.value}))}>{["School","Relief camp","Stadium","Community hall","Religious building","Government building","College","Other"].map(x=><option key={x}>{x}</option>)}</select></label>
      <label>District<select required value={form.district} onChange={e=>{setLocationCheck(null);setForm(v=>({...v,district:e.target.value,lac:""}));}}><option value="">Choose district</option>{districts.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Assembly constituency (LAC)<select required value={form.lac} onChange={e=>setForm(v=>({...v,lac:e.target.value}))}><option value="">Choose LAC</option>{lacs.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Address<input required value={form.address} onChange={e=>setForm(v=>({...v,address:e.target.value}))} placeholder="Street, locality"/></label>
      <div className="two-fields"><label>Latitude<div className="coordinate-input"><input aria-label="Latitude degrees" required type="number" step="any" min="0" max="90" value={form.latitude} onChange={e=>{setLocationCheck(null);setForm(v=>({...v,latitude:e.target.value}));}}/><select aria-label="Latitude hemisphere" value={form.latitude_hemisphere} onChange={e=>setForm(v=>({...v,latitude_hemisphere:e.target.value}))}><option value="N">N</option><option value="S">S</option></select></div></label><label>Longitude<div className="coordinate-input"><input aria-label="Longitude degrees" required type="number" step="any" min="0" max="180" value={form.longitude} onChange={e=>{setLocationCheck(null);setForm(v=>({...v,longitude:e.target.value}));}}/><select aria-label="Longitude hemisphere" value={form.longitude_hemisphere} onChange={e=>setForm(v=>({...v,longitude_hemisphere:e.target.value}))}><option value="E">E</option><option value="W">W</option></select></div></label></div>
      <p className="coordinate-help">Use decimal degrees and validate that the pin falls inside the selected Kerala district.</p>
      <button type="button" className="secondary" disabled={!form.district||!form.lac||!form.latitude||!form.longitude||busy} onClick={checkLocation}>Check pin location</button>
      {locationCheck&&<div className={`location-check ${locationCheck.valid===true?"valid":locationCheck.valid===false?"invalid":"checking"}`} role="status">{locationCheck.message}{locationCheck.valid===true&&<a href={`https://www.google.com/maps?q=${signedCoordinates().latitude},${signedCoordinates().longitude}`} target="_blank" rel="noreferrer">Preview in Google Maps ↗</a>}</div>}
      <button type="button" className="secondary" onClick={locate}>Use this device’s location</button>
      <label>Capacity<input type="number" required min="1" max="100000" value={form.capacity} onChange={e=>setForm(v=>({...v,capacity:e.target.value}))}/></label>
      <label className="shelter-switch shelter-form-switch"><span>Available for citizen requests</span><input type="checkbox" role="switch" checked={form.is_active} onChange={e=>setForm(v=>({...v,is_active:e.target.checked}))}/><i/></label>
      <button type="submit" className="primary" disabled={busy}>{busy?"Saving…":editingId?"Save changes":"Add shelter"}</button>{editingId&&<button type="button" className="secondary" onClick={resetForm}>Cancel edit</button>}
    </form><div className="resource-list shelter-list">{pageItems.map(item=><article className="panel resource-card" key={item.id}>
      <div className="resource-head"><div><span className="eyebrow">{item.district} · {item.lac} · {item.building_type}</span><h3>{item.name}</h3></div><span className={`pill ${item.needs_review?"needs-review":item.is_active?"active":"inactive"}`}>{item.needs_review?"Review required":item.is_active?"Active":"Inactive"}</span></div>
      <p className="resource-balance">{item.address}<br/><b>{item.occupied}/{item.capacity}</b> people · {item.available} spaces available</p>
      <p className="note">{Math.abs(item.latitude).toFixed(5)}° {item.latitude<0?"S":"N"}, {Math.abs(item.longitude).toFixed(5)}° {item.longitude<0?"W":"E"}{item.needs_review&&<> · <a href={`https://www.google.com/maps?q=${item.latitude},${item.longitude}`} target="_blank" rel="noreferrer">Open map ↗</a></>}</p>
      {item.needs_review&&<p className="shelter-review-note">Nearest LAC center assignment · {item.lac_distance_km?.toFixed(1)} km from center · Source row {item.source_row}. Verify the pin, LAC, and capacity before activation.</p>}
      <div className="shelter-admin-actions"><div className="shelter-card-buttons"><button className="secondary" onClick={()=>editShelter(item)}>Edit details / capacity</button>{item.needs_review&&<button className="primary" onClick={()=>markReviewed(item)}>Confirm review</button>}</div><label className={`shelter-switch ${item.needs_review?"switch-disabled":""}`} title={item.needs_review?"Review this shelter before activation":"Toggle whether citizens can request this shelter"}><span>{item.needs_review?"Review before activation":item.is_active?"Accepting requests":"Not accepting requests"}</span><input type="checkbox" role="switch" aria-label={`${item.is_active?"Deactivate":"Activate"} ${item.name}`} disabled={item.needs_review} checked={item.is_active} onChange={()=>toggle(item)}/><i/></label></div>
    </article>)}{items&&!visibleItems.length&&<div className="panel empty">No shelters match these filters. Add one here or clear the review filter.</div>}
    {visibleItems.length>pageSize&&<div className="shelter-pagination"><span>{visibleItems.length} shelters · page {currentPage} of {pageCount}</span><div><button className="secondary" disabled={currentPage<=1} onClick={()=>setCurrentPage(page=>Math.max(1,page-1))}>Previous</button><button className="secondary" disabled={currentPage>=pageCount} onClick={()=>setCurrentPage(page=>Math.min(pageCount,page+1))}>Next</button></div></div>}
    </div></div>
    <section className="panel auditorium-candidate-panel">
      <div className="panel-head"><div><h3>Auditorium demo candidates</h3><p>Two suggested locations per district. These are review records, not active shelters; capacity is not provided by the source.</p></div><span className="pill needs-review">{auditoriumCandidates.length} candidates</span></div>
      {(!candidateItems||candidateItems.length===0)?<div className="candidate-empty"><p>No auditorium demo records have been added to this database yet.</p><button className="secondary" disabled={importingAuditoriums} onClick={importAuditoriumDemo}>{importingAuditoriums?"Adding demo…":"Add 28 demo candidates"}</button></div>:<>
        <div className="table-scroll"><table><thead><tr><th>District / facility</th><th>Workbook location</th><th>Suggested map match</th><th>Confidence</th><th>Coordinates</th><th>Capacity / review</th></tr></thead><tbody>{visibleCandidates.map(item=><tr key={item.source_key}><td><b>{item.district}</b><small>{item.name}</small><small>{item.source_sheet} · row {item.source_row}</small></td><td>{item.address||"—"}<small>{item.lsg||"Local body not listed"}</small></td><td><b>{item.geocode_result_name||"—"}</b><small>{item.geocode_result_address||"No map address returned"}</small></td><td><span className={`pill ${item.geocode_confidence==="high"?"active":"needs-review"}`}>{item.geocode_confidence}</span></td><td>{item.suggested_latitude?.toFixed(5)}, {item.suggested_longitude?.toFixed(5)}<small>{item.geocode_result_url&&<a href={item.geocode_result_url} target="_blank" rel="noreferrer">Open OSM result ↗</a>}</small></td><td><b>Unconfirmed</b><small>Capacity required</small><small>{item.review_status}</small></td></tr>)}</tbody></table></div>
        {auditoriumCandidates.length>candidatePageSize&&<div className="shelter-pagination"><span>{auditoriumCandidates.length} candidates · page {candidatePage} of {candidatePageCount}</span><div><button className="secondary" disabled={candidatePage<=1} onClick={()=>setCandidatePage(page=>Math.max(1,page-1))}>Previous</button><button className="secondary" disabled={candidatePage>=candidatePageCount} onClick={()=>setCandidatePage(page=>Math.min(candidatePageCount,page+1))}>Next</button></div></div>}
      </>}
    </section>
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
  const refresh=useCallback(()=>setReload(v=>v+1),[]);
  useEffect(()=>{let live=true;api(path).then(d=>{if(live)setData(d);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[path,reload]);
  return [data,refresh];
}

function Overview({setError}) {
  const [stats,refresh]=useLoad("/api/admin/dashboard",setError);
  useEffect(()=>{const interval=window.setInterval(refresh,30000);return()=>window.clearInterval(interval);},[refresh]);
  if(!stats)return <div className="loading-line">Loading current platform data…</div>;
  const responders=(stats.users.by_role.rescuer||0)+(stats.users.by_role.responder||0);
  return <><div className="welcome"><div><span className="eyebrow">SYSTEM OVERVIEW</span><h2>Kerala operations at a glance</h2><p>Live totals from the platform database.</p></div><span className="live"><i/>Connected</span></div>
    <div className="stats-grid"><Stat label="Registered users" value={stats.users.total}/><Stat label="Citizens" value={stats.users.by_role.citizen||0}/><Stat label="Response team" value={responders}/><Stat label="Available rescuers" value={stats.users.available_responders||0}/><Stat label="Administrators" value={stats.administrators.total}/><Stat label="Open help requests" value={stats.help_requests.active_or_unresolved}/><Stat label="Awaiting review" value={stats.help_requests.pending}/><Stat label="Published alerts" value={stats.alerts.published}/><Stat label="Active resource items" value={stats.resources?.active||0}/><Stat label="Low-stock items" value={stats.resources?.low_stock||0}/></div>
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
    <div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>Person</th><th>Role</th><th>District</th><th>Account</th><th>Availability</th><th>Role control</th><th>Access</th><th>LAC coverage</th></tr></thead><tbody>{data?.users.map(u=><Fragment key={u.id}><tr><td><b>{u.full_name}</b><small>{u.email}</small></td><td><Pill value={u.role}/></td><td>{u.district||"—"}</td><td><Pill value={u.status}/></td><td>{["rescuer","responder"].includes(u.role)?<Pill value={u.status==="active"&&u.is_available?"available":"unavailable"}/>:"—"}</td><td><select value={u.role==="rescuer"?"responder":u.role} onChange={e=>update(u,{role:e.target.value})}><option value="citizen">Citizen</option><option value="responder">Responder</option></select></td><td><button className="text-button" onClick={()=>update(u,{status:u.status==="active"?"suspended":"active"})}>{u.status==="active"?"Suspend":"Activate"}</button>{u.role==="rescuer"&&u.status==="pending"&&<button className="text-button approve" onClick={()=>update(u,{status:"active"})}>Approve</button>}</td><td>{["rescuer","responder"].includes(u.role)&&<button className="text-button" onClick={()=>setCoverageUser(coverageUser===u.id?null:u.id)}>{coverageUser===u.id?"Close":"Manage LACs"}</button>}</td></tr>{coverageUser===u.id&&<tr><td colSpan="8"><CoverageEditor user={u} onSaved={()=>{setCoverageUser(null);setReload(x=>x+1);}} onCancel={()=>setCoverageUser(null)} setError={setError}/></td></tr>}</Fragment>)}{data&&!data.users.length&&<tr><td colSpan="8" className="empty">No matching accounts.</td></tr>}</tbody></table></div></div>
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
  const [data,setData]=useState(null);const [users,setUsers]=useState([]);const [filter,setFilter]=useState("");const [reload,setReload]=useState(0);const [reasons,setReasons]=useState({});const [conversations,setConversations]=useState({});
  useEffect(()=>{let live=true;const refresh=()=>{const qs=new URLSearchParams({limit:"100"});if(filter)qs.set("status",filter);Promise.all([api(`/api/admin/requests?${qs}`),api("/api/admin/users?role=responder&status=active&limit=100")]).then(([r,u])=>{if(live){setData(r);setUsers(u.users);}}).catch(e=>live&&setError(e.message));};refresh();const interval=window.setInterval(()=>{if(document.visibilityState==="visible")refresh();},30000);return()=>{live=false;window.clearInterval(interval);};},[filter,reload,setError]);
  async function toggleConversation(item){if(conversations[item.id]){setConversations(v=>({...v,[item.id]:null}));return;}try{const rows=await api(`/api/admin/requests/${item.id}/messages`);setConversations(v=>({...v,[item.id]:rows}));}catch(e){setError(e.message);}}
  useEffect(()=>{const openIds=Object.entries(conversations).filter(([,rows])=>rows!==null).map(([id])=>id);if(!openIds.length)return;let live=true;const refresh=()=>{if(document.visibilityState!=="visible")return;openIds.forEach(id=>api(`/api/admin/requests/${id}/messages`).then(rows=>live&&setConversations(v=>({...v,[id]:rows}))).catch(e=>live&&setError(e.message)));};const interval=window.setInterval(refresh,15000);return()=>{live=false;window.clearInterval(interval);};},[Object.keys(conversations).filter(id=>conversations[id]!==null).join(","),setError]);
  async function setStatus(item,status){const reason=reasons[item.id]||"";if(["Resolved","Rejected"].includes(status)&&reason.trim().length<3){setError("Enter a reason before resolving or rejecting a request.");return;}try{await api(`/api/admin/requests/${item.id}/status`,{method:"PATCH",body:JSON.stringify({status,reason:reason||null})});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function assign(item,responder_id){try{await api(`/api/admin/requests/${item.id}/assignment`,{method:"PATCH",body:JSON.stringify({responder_id:responder_id?Number(responder_id):null})});setReload(x=>x+1);}catch(e){setError(e.message);}}
  async function openAttachment(item){const tab=window.open("about:blank","_blank");try{const response=await fetch(`${API}/api/admin/requests/${item.id}/attachment`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||"Could not open attachment.");}const url=URL.createObjectURL(await response.blob());if(tab)tab.location.href=url;else window.location.href=url;}catch(e){tab?.close();setError(e.message);}}
  return <><div className="toolbar"><div><h2>Help requests</h2><p>Review reports, update status, and assign active responders.</p></div><select className="filter-select" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All statuses</option>{["Submitted","Under Review","Assigned","In Progress","Resolved","Rejected"].map(s=><option key={s}>{s}</option>)}</select></div>
    <div className="request-list">{data?.items.map(item=><article className="panel request-card" key={item.id}><div className="request-title"><div><span className="eyebrow">{item.district} · {item.lac} · #{item.id}</span><h3>{item.emergency_type}</h3></div><Pill value={item.status}/></div><p>{item.situation_description}</p><div className="request-meta"><span>Urgency: <b>{item.urgency}</b></span><span>People affected: <b>{item.people_affected}</b></span><span>Received: <b>{new Date(item.created_at).toLocaleString()}</b></span></div>{item.image_path&&<button className="text-button" onClick={()=>openAttachment(item)}>View attached evidence</button>}
      <button className="text-button" onClick={()=>toggleConversation(item)}>{conversations[item.id] ? "Hide citizen conversation" : "Monitor citizen conversation"}</button>{Array.isArray(conversations[item.id])&&<div className="request-conversation-monitor">{conversations[item.id].length?conversations[item.id].map(message=><p key={message.id}><b>{message.sender_name} · {message.sender_role}</b><span>{message.message}</span><small>{new Date(message.created_at).toLocaleString()}</small></p>):<p>No messages yet. Admin monitoring is read-only.</p>}</div>}
      <div className="request-actions"><label>Assign responder<select value={item.assigned_responder_id||""} disabled={["Resolved","Rejected"].includes(item.status)} onChange={e=>assign(item,e.target.value)}><option value="">Unassigned</option>{users.filter(u=>(u.coverage||[]).some(area=>area.district.toLowerCase()===item.district.toLowerCase())).map(u=><option key={u.id} value={u.id}>{u.full_name} · {u.district||""}</option>)}</select></label><label>Reason for rejection/resolution<input placeholder="Required for resolved or rejected" value={reasons[item.id]||""} onChange={e=>setReasons(v=>({...v,[item.id]:e.target.value}))}/></label><label>Update status<select value={item.status} onChange={e=>setStatus(item,e.target.value)}>{["Submitted","Under Review","Assigned","In Progress","Resolved","Rejected"].map(s=><option key={s}>{s}</option>)}</select></label></div>
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
