/**
 * HTTP transport for the Urban Air Quality Assistant.
 *
 * The wrapper clones the caller's options instead of mutating them, injects the
 * session bearer token, encodes plain-object bodies as JSON, and normalises
 * FastAPI's `{"detail": ...}` error envelope into an `Error`.
 */

/** sessionStorage key holding the bearer token. */
export const TOKEN_KEY = "uqa_token";

/**
 * Read the bearer token for the current tab.
 *
 * @returns {string} The stored token, or an empty string when signed out.
 */
export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

/**
 * Persist the bearer token for the current tab.
 *
 * @param {string} value - The token returned by the auth endpoint.
 * @returns {void}
 */
export function setToken(value) {
  sessionStorage.setItem(TOKEN_KEY, value);
}

/**
 * Remove the bearer token from the current tab.
 *
 * @returns {void}
 */
export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

/**
 * Fetch a JSON API resource with authentication and error normalisation.
 *
 * Plain-object bodies are serialised as JSON; `FormData` and string bodies are
 * sent untouched. A 204 response resolves to `null`, JSON responses resolve to
 * the parsed body, and anything else resolves to text. Non-2xx responses reject
 * with the server's `detail` message when present.
 *
 * @param {string} path - Absolute API path such as `/plans`.
 * @param {RequestInit} [options] - Fetch options; the object is not mutated.
 * @returns {Promise<unknown>} The parsed response body, text, or `null`.
 * @throws {Error} When the response status is not ok.
 */
export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const bearer = getToken();
  if (bearer) {
    headers.set("Authorization", `Bearer ${bearer}`);
  }

  let body = options.body;
  if (body && typeof body !== "string" && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  const response = await fetch(path, { ...options, headers, body });
  if (!response.ok) {
    let detail = "request failed";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}
