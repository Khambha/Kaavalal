const DB_NAME = "kaavalal-citizen-outbox";
const STORE = "requests";

function database() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) return reject(new Error("Offline request storage is unavailable in this browser."));
    const open = indexedDB.open(DB_NAME, 1);
    open.onupgradeneeded = () => open.result.createObjectStore(STORE, { keyPath: "id" });
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error || new Error("Could not open offline request storage."));
  });
}

async function withStore(mode, action) {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const store = tx.objectStore(STORE);
    const result = action(store);
    tx.oncomplete = () => { db.close(); resolve(result?.result); };
    tx.onerror = () => { db.close(); reject(tx.error || new Error("Offline request storage failed.")); };
    tx.onabort = () => { db.close(); reject(tx.error || new Error("Offline request storage was interrupted.")); };
  });
}

function signal(detail = {}) {
  window.dispatchEvent(new CustomEvent("kaavalal-outbox-changed", { detail }));
}

function tokenSubject(token) {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return String(JSON.parse(atob(payload)).sub || "");
  } catch { return ""; }
}

export async function listOfflineRequests() {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).getAll();
    request.onsuccess = () => { db.close(); resolve(request.result || []); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

export async function queueOfflineRequest(entry) {
  const token = localStorage.getItem("token") || sessionStorage.getItem("token");
  const owner_id = tokenSubject(token || "");
  if (!owner_id) throw new Error("Sign in again before saving this request offline.");
  await withStore("readwrite", store => store.put({ ...entry, owner_id }));
  signal({ queued: true });
}

export async function flushOfflineRequests() {
  if (!navigator.onLine) return { synced: 0 };
  const token = localStorage.getItem("token") || sessionStorage.getItem("token");
  if (!token) return { synced: 0 };
  const owner = tokenSubject(token);
  if (!owner) return { synced: 0 };
  const entries = (await listOfflineRequests()).filter(entry => entry.owner_id === owner);
  let synced = 0;
  const records = [];
  for (const entry of entries) {
    try {
      let response;
      if (entry.type === "incident") {
        const body = new FormData();
        Object.entries(entry.payload).forEach(([key, value]) => {
          if (value !== null && value !== undefined && value !== "") body.append(key, value);
        });
        response = await fetch("http://127.0.0.1:8000/api/help-requests/", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body });
      } else if (entry.type === "shelter") {
        response = await fetch("http://127.0.0.1:8000/api/shelters/requests", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(entry.payload) });
      } else continue;
      if (!response.ok) continue;
      const result = await response.json().catch(() => ({}));
      await withStore("readwrite", store => store.delete(entry.id));
      synced += 1;
      records.push({ type: entry.type, id: result.id, status: result.status });
    } catch {
      break;
    }
  }
  const pending = await listOfflineRequests();
  signal({ synced, pending: pending.length, records });
  return { synced, pending: pending.length };
}
