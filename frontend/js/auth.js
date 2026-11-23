/**
 * Authentication flows: register, sign in, and sign out.
 *
 * Tokens live in sessionStorage through the API module, so a session never
 * outlives the tab. Sign-out always clears the local token and reports whether
 * the server also revoked it.
 */

import { apiFetch, clearToken, setToken } from "./api.js";
import { showError, showStatus } from "./ui.js";

/**
 * Build a submit handler that posts credentials to an auth endpoint.
 *
 * The returned handler prevents the native form submission, sends the trimmed
 * email and raw password, stores the returned token, and announces success. It
 * resolves to the response payload, or `null` after reporting an error.
 *
 * @param {string} endpoint - Auth path such as `/auth/register`.
 * @param {string} emailId - Id of the email input.
 * @param {string} passwordId - Id of the password input.
 * @param {string} successMessage - Status message announced on success.
 * @returns {(event: SubmitEvent) => Promise<{token: string} | null>} The form
 *   submit handler.
 */
export function submitAuth(endpoint, emailId, passwordId, successMessage) {
  return function handleAuthSubmit(event) {
    event.preventDefault();
    const payload = {
      email: document.getElementById(emailId).value.trim(),
      password: document.getElementById(passwordId).value,
    };
    return apiFetch(endpoint, { method: "POST", body: payload })
      .then((data) => {
        setToken(data.token);
        showStatus(successMessage);
        return data;
      })
      .catch((error) => {
        showError(error.message);
        return null;
      });
  };
}

/**
 * Revoke the session token when the server is reachable and always clear it
 * from this tab.
 *
 * @returns {Promise<boolean>} `true` when the server revoked the token,
 *   `false` when the call failed and the token was cleared locally only.
 */
export function handleLogout() {
  let revokedOnServer = false;
  return apiFetch("/auth/logout", { method: "POST" })
    .then(() => {
      revokedOnServer = true;
    })
    .catch(() => {
      revokedOnServer = false;
    })
    .then(() => {
      clearToken();
      return revokedOnServer;
    });
}
