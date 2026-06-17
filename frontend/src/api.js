// API base URL comes only from the environment, never hardcoded. Vite injects
// VITE_API_BASE_URL at build time.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export function isConfigured() {
  return Boolean(API_BASE_URL);
}

export function apiBaseUrl() {
  return API_BASE_URL;
}

export async function scoreSession(features) {
  if (!API_BASE_URL) {
    throw new Error(
      "VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env."
    );
  }

  const response = await fetch(`${API_BASE_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(features),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body; keep the status text
    }
    throw new Error(`Scoring failed (${response.status}): ${detail}`);
  }

  return response.json();
}

// The narrative is an optional layer: any failure degrades to "no card" rather than an
// error state, so the demo works identically with or without a model endpoint.
export async function narrateSession(features, { signal } = {}) {
  if (!API_BASE_URL) return { enabled: false, narrative: null };

  const response = await fetch(`${API_BASE_URL}/narrate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(features),
    signal,
  });

  if (!response.ok) return { enabled: false, narrative: null };
  return response.json();
}
