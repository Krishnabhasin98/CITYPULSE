/**
 * Single API client for the whole app.
 *
 * Resolution order for the base URL:
 *  1. VITE_API_URL if set at build time,
 *  2. same origin, when the backend serves the built frontend (production),
 *  3. the dev Vite proxy (relative paths are proxied to 127.0.0.1:8000).
 *
 * Every response goes through one error normaliser so the UI can show a real
 * message instead of "[object Object]".
 */

const configured = import.meta.env.VITE_API_URL;
export const API_BASE = (configured || "").replace(/\/$/, "");

export function apiUrl(path) {
  if (!path) return API_BASE || "/";
  if (/^https?:\/\//i.test(path)) return path;
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${clean}`;
}

const TOKEN_KEY = "citypulse_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) — requests simply go anonymous */
  }
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function toError(response) {
  let payload = null;
  let message = `Request failed (${response.status})`;
  try {
    payload = await response.json();
    if (typeof payload?.detail === "string") message = payload.detail;
    else if (Array.isArray(payload?.detail)) {
      message = payload.detail
        .map((item) => item.msg?.replace(/^Value error, /, "") || "Invalid value")
        .join(", ");
    } else if (payload?.message) message = payload.message;
  } catch {
    /* body was not JSON */
  }
  if (response.status === 401) message = message || "Please sign in to continue.";
  return new ApiError(message, response.status, payload);
}

async function request(path, { method = "GET", body, form, signal } = {}) {
  const headers = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(apiUrl(path), { method, headers, body: payload, signal });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the CityPulse API. Is the backend running?", 0, null);
  }
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export const apiGet = (path, options) => request(path, options);
export const apiPost = (path, body, options) => request(path, { ...options, method: "POST", body });
export const apiPostForm = (path, form, options) => request(path, { ...options, method: "POST", form });

/** Build a query string, skipping empty values. */
export function qs(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

// ---------------------------------------------------------------------------
// Endpoint map — keeps paths in one place instead of scattered strings.
// ---------------------------------------------------------------------------
export const endpoints = {
  meta: () => "/api/meta",
  health: () => "/health",
  deepHealth: () => "/health/deep",
  liveHealth: () => "/health/live",

  register: () => "/api/auth/register",
  login: () => "/api/auth/login",
  demoSession: (role) => `/api/auth/demo-session${qs({ role })}`,
  me: () => "/api/auth/me",
  ledger: () => "/api/auth/ledger",
  scorecardAuth: () => "/api/auth/city-scorecard",

  report: () => "/api/posts/",
  reportJson: () => "/api/posts/json",
  myReports: () => "/api/posts/mine",

  incidents: (params) => `/api/incidents/${qs(params)}`,
  incident: (id) => `/api/incidents/${id}`,
  incidentGeojson: () => "/api/incidents/geojson",
  cityHealth: () => "/api/incidents/health",
  departments: () => "/api/incidents/departments",
  policy: () => "/api/incidents/policy",
  forecasts: () => "/api/incidents/forecasts",
  scorecard: () => "/api/incidents/scorecard",
  queue: (limit) => `/api/incidents/queue${qs({ limit })}`,
  actionsPending: (limit) => `/api/incidents/actions/pending${qs({ limit })}`,
  creditCatalog: () => "/api/incidents/credits/catalog",
  actions: (id) => `/api/incidents/${id}/actions`,
  verifyAction: (id, actionId) => `/api/incidents/${id}/actions/${actionId}/verify`,
  resolveIncident: (id) => `/api/incidents/${id}/resolve`,

  uploadEvidence: () => "/api/uploads/evidence",

  areaAnalyze: (params) => `/api/area/analyze${qs(params)}`,
  areaSearch: (q) => `/api/area/search${qs({ q })}`,
  areaSummary: () => "/api/area/summary",
  monsoon: () => "/api/area/monsoon",
  areaResolve: (params) => `/api/area/resolve${qs(params)}`,

  assistant: (q) => `/api/assistant/${qs({ q })}`,
  assistantAgentic: (q) => `/api/assistant/agentic${qs({ q })}`,
  assistantSuggestions: () => "/api/assistant/suggestions",
};
