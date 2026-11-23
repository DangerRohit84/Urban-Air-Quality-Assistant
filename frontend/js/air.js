/**
 * Air-quality readout and saved AQI context.
 *
 * The readout is rendered with `textContent`; the city comes from the profile
 * form so the live request always matches what the user is editing.
 */

import { apiFetch } from "./api.js";
import { loadPlans } from "./plans.js";
import { showError, showStatus } from "./ui.js";

/**
 * Render the band, source, and optional fallback explanation.
 *
 * @param {{band?: string, source: string, fallback?: string}} reading - The
 *   air-quality reading.
 * @returns {void}
 */
export function renderAir(reading) {
  let text = reading.band || "No band";
  text += ` (${reading.source})`;
  if (reading.fallback) {
    text += ` - ${reading.fallback}`;
  }
  document.getElementById("aqi-readout").textContent = text;
}

/**
 * Fetch the live reading for the city in the profile form.
 *
 * @returns {Promise<object | null>} The reading, or `null` when the city is
 *   missing or the request fails.
 */
export function loadAir() {
  const city = document.getElementById("city").value.trim();
  if (!city) {
    showError("Enter your city first.");
    return Promise.resolve(null);
  }
  return apiFetch(`/air?q=${encodeURIComponent(city)}`)
    .then((reading) => {
      renderAir(reading);
      showStatus("Air quality updated.");
      return reading;
    })
    .catch((error) => {
      showError(error.message);
      return null;
    });
}

/**
 * Fetch the live AQI reading; wired to the "Fetch live AQI" button.
 *
 * @returns {Promise<object | null>} The reading, or `null` on failure.
 */
export function fetchLiveAqi() {
  return loadAir();
}

/**
 * Save the selected CPCB band and season, then refresh the plan.
 *
 * @returns {Promise<unknown>} The plan refresh, or `null` when the city is
 *   missing or the save fails.
 */
export function saveAirContext() {
  const city = document.getElementById("city").value.trim();
  const band = document.getElementById("aqi-band").value;
  const season = document.getElementById("aqi-season").value;
  if (!city) {
    showError("Enter your city first.");
    return Promise.resolve(null);
  }
  return apiFetch("/air/context", {
    method: "POST",
    body: { city, band, season },
  })
    .then(() => {
      showStatus("Air-quality band saved.");
      return loadPlans();
    })
    .catch((error) => {
      showError(error.message);
      return null;
    });
}
