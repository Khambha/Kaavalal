const TOKEN_KEYS = ["token", "access_token"];

function storages() {
  if (typeof window === "undefined") return [];
  return [window.localStorage, window.sessionStorage];
}

function decodePayload(token) {
  try {
    const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function getToken() {
  for (const storage of storages()) {
    try {
      for (const key of TOKEN_KEYS) {
        const token = storage.getItem(key);
        if (token) return token;
      }
    } catch {
      // Storage can be unavailable in hardened/private browsing contexts.
    }
  }
  return "";
}

export function setToken(token, { persist = true } = {}) {
  if (!token) throw new Error("A non-empty authentication token is required.");
  clearToken();
  const storage = persist ? window.localStorage : window.sessionStorage;
  storage.setItem("token", token);
}

export function clearToken() {
  for (const storage of storages()) {
    try {
      for (const key of TOKEN_KEYS) storage.removeItem(key);
    } catch {
      // Continue clearing other storage even if one is unavailable.
    }
  }
}

export function getUserIdFromToken(token = getToken()) {
  const payload = token ? decodePayload(token) : null;
  const id = payload?.sub ?? payload?.user_id ?? payload?.id;
  return id == null ? "" : String(id);
}

export function getRoleFromToken(token = getToken()) {
  const payload = token ? decodePayload(token) : null;
  return typeof payload?.role === "string" ? payload.role : "";
}
