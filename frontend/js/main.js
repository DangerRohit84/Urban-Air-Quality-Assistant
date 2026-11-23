/**
 * Application entry point: profile form, visibility, and event wiring.
 *
 * The module is loaded with `type="module"`, so execution is deferred until
 * the document is parsed; `init` still waits for `DOMContentLoaded` to keep the
 * original startup contract.
 */

import { apiFetch, getToken } from "./api.js";
import { handleLogout, submitAuth } from "./auth.js";
import { fetchLiveAqi, saveAirContext } from "./air.js";
import { exportPlan, loadPlans } from "./plans.js";
import { loadDocuments, uploadDocument } from "./documents.js";
import { showError, showStatus } from "./ui.js";

/** Sections revealed only for an authenticated session. */
const APP_SECTION_IDS = [
  "profile-section",
  "air-panel",
  "plans",
  "impact",
  "ask",
  "documents",
];

const register = submitAuth(
  "/auth/register",
  "reg-email",
  "reg-password",
  "Welcome! Your account is ready."
);

const login = submitAuth("/auth/login", "login-email", "login-password", "Signed in.");

/**
 * Show or hide the authenticated application shell.
 *
 * @param {boolean} visible - `true` to reveal the app, `false` to show the auth
 *   card.
 * @returns {void}
 */
export function setAppVisible(visible) {
  document.getElementById("auth-card").hidden = visible;
  document.getElementById("session-bar").hidden = !visible;
  APP_SECTION_IDS.forEach((id) => {
    document.getElementById(id).hidden = !visible;
  });
}

/**
 * Clear per-session readouts so a new user never sees stale answers, uploads,
 * or air-quality context.
 *
 * @returns {void}
 */
function resetTransientState() {
  document.getElementById("errors").textContent = "";
  document.getElementById("answer-text").textContent = "";
  document.getElementById("answerMode").textContent = "Mode: standard";
  document.getElementById("citations").textContent = "";
  document.getElementById("docs-list").textContent = "";
  document.getElementById("uploadStatus").textContent = "";
  document.getElementById("aqi-readout").textContent = "No reading yet.";
}

/**
 * Sign out, clearing the shell and reporting whether the server revoked the
 * token.
 *
 * @returns {Promise<void>} Resolves after the UI reflects the signed-out state.
 */
function signOut() {
  return handleLogout().then((revokedOnServer) => {
    resetTransientState();
    setAppVisible(false);
    showStatus(revokedOnServer ? "Signed out." : "Signed out on this device.");
  });
}

/**
 * Load the authenticated data after a successful register or sign-in.
 *
 * @param {{token: string} | null} data - The auth response, or `null` after an
 *   error was announced.
 * @returns {void}
 */
function afterAuth(data) {
  if (!data) {
    return;
  }
  setAppVisible(true);
  loadProfile();
  loadPlans();
  loadDocuments();
}

/**
 * Fill the profile form from a saved profile payload.
 *
 * @param {object} profile - The profile returned by `/profile`.
 * @returns {void}
 */
function fillProfileForm(profile) {
  document.getElementById("city").value = profile.city || "";
  document.getElementById("climate_zone").value = profile.climate_zone;
  document.getElementById("children").checked = !!profile.children;
  document.getElementById("elderly").checked = !!profile.elderly;
  document.getElementById("respiratory").checked = !!profile.respiratory;
  document.getElementById("commute_mode").value = profile.commute_mode;
  document.getElementById("commute_km").value = profile.commute_km;
  document.getElementById("cooking_fuel").value = profile.cooking_fuel;
  document.getElementById("heating_type").value = profile.heating_type;
  document.getElementById("budget_level").value = profile.budget_level;
}

/**
 * Read the profile form into an API payload.
 *
 * @returns {object} The profile payload.
 */
function collectProfile() {
  return {
    city: document.getElementById("city").value.trim(),
    climate_zone: document.getElementById("climate_zone").value,
    children: document.getElementById("children").checked,
    elderly: document.getElementById("elderly").checked,
    respiratory: document.getElementById("respiratory").checked,
    commute_mode: document.getElementById("commute_mode").value,
    commute_km: parseFloat(document.getElementById("commute_km").value) || 0,
    cooking_fuel: document.getElementById("cooking_fuel").value,
    heating_type: document.getElementById("heating_type").value,
    budget_level: document.getElementById("budget_level").value,
  };
}

/**
 * Load the saved profile into the form.
 *
 * @returns {Promise<void>} Resolves after the form fills or the empty-state
 *   status is announced.
 */
function loadProfile() {
  return apiFetch("/profile")
    .then((profile) => {
      fillProfileForm(profile);
      showStatus("Profile loaded.");
    })
    .catch(() => {
      showStatus("No profile yet - fill the form to personalize.");
    });
}

/**
 * Save the profile form and refresh the plan.
 *
 * @returns {Promise<object | null>} The saved profile, or `null` on failure.
 */
function saveProfile() {
  const payload = collectProfile();
  return apiFetch("/profile", { method: "PUT", body: payload })
    .then((profile) => {
      fillProfileForm(profile);
      showStatus("Profile saved.");
      return profile;
    })
    .catch((error) => {
      showError(error.message);
      return null;
    });
}

/**
 * Render the answer citations into the list.
 *
 * @param {string[]} citations - Citation labels from the answer payload.
 * @returns {void}
 */
function renderCitations(citations) {
  const list = document.getElementById("citations");
  list.textContent = "";
  citations.forEach((citation) => {
    const item = document.createElement("li");
    item.textContent = citation;
    list.appendChild(item);
  });
}

/**
 * Post the question and render the grounded answer, mode, and citations.
 *
 * @param {SubmitEvent} [event] - The form submit event, when wired as a
 *   listener.
 * @returns {Promise<object | null>} The answer payload, or `null` on failure.
 */
function askQuestion(event) {
  if (event) {
    event.preventDefault();
  }
  const question = document.getElementById("q").value.trim();
  const plain = document.getElementById("plain").checked;
  if (!question) {
    showError("Enter a question first.");
    return Promise.resolve(null);
  }
  return apiFetch("/ask", {
    method: "POST",
    body: { question, plain_language: plain },
  })
    .then((data) => {
      document.getElementById("answer-text").textContent = data.answer;
      document.getElementById("answerMode").textContent = `Mode: ${data.mode}`;
      renderCitations(data.citations || []);
      showStatus(
        data.grounded ? "Answered from the corpus." : "No corpus support found."
      );
      return data;
    })
    .catch((error) => {
      showError(error.message);
      return null;
    });
}

/**
 * Wire the forms and buttons, then restore or hide the session shell.
 *
 * @returns {void}
 */
function init() {
  document.getElementById("register-form").addEventListener("submit", (event) => {
    register(event).then(afterAuth);
  });
  document.getElementById("login-form").addEventListener("submit", (event) => {
    login(event).then(afterAuth);
  });
  document.getElementById("profile-form").addEventListener("submit", (event) => {
    event.preventDefault();
    saveProfile().then((profile) => {
      if (profile) {
        loadPlans();
      }
    });
  });
  document.getElementById("fetch-live").addEventListener("click", fetchLiveAqi);
  document.getElementById("aqi-band").addEventListener("change", saveAirContext);
  document.getElementById("aqi-season").addEventListener("change", saveAirContext);
  document.getElementById("ask-form").addEventListener("submit", askQuestion);
  document.getElementById("upload-form").addEventListener("submit", uploadDocument);
  document.getElementById("exportBtn").addEventListener("click", exportPlan);
  document.getElementById("logoutBtn").addEventListener("click", signOut);

  if (getToken()) {
    setAppVisible(true);
    loadProfile();
    loadPlans();
    loadDocuments();
  } else {
    setAppVisible(false);
  }
}

document.addEventListener("DOMContentLoaded", init);
