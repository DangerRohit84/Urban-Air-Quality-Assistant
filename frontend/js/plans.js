/**
 * Personalised plan rendering and the Markdown export.
 *
 * Every value is written with `textContent`; plan titles, details, and
 * citations are never interpolated into markup.
 */

import { apiFetch } from "./api.js";
import { showError, showStatus } from "./ui.js";

/**
 * Format a numeric metric with at most two decimal places.
 *
 * @param {unknown} value - The raw metric value.
 * @returns {string} The rounded value, or `"0"` when not finite.
 */
export function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "0";
  }
  return String(Math.round(numeric * 100) / 100);
}

/**
 * Write the three aggregate impact metrics into the impact panel.
 *
 * @param {{co2e_kg_week: number, exposure_reduction_pct: number,
 *   cost_delta_inr_month: number}} impact - The impact payload.
 * @returns {void}
 */
export function renderImpact(impact) {
  document.getElementById("impact-co2e").textContent = formatNumber(
    impact.co2e_kg_week
  );
  document.getElementById("impact-exposure").textContent = formatNumber(
    impact.exposure_reduction_pct
  );
  document.getElementById("impact-cost").textContent = formatNumber(
    impact.cost_delta_inr_month
  );
}

/**
 * Replace a plan section with cards built from the supplied items.
 *
 * @param {string} elementId - Container id such as `plans-routines`.
 * @param {Array<{title: string, detail: string, impact: object,
 *   citations: string[]}>} items - The plan items.
 * @returns {void}
 */
export function renderSection(elementId, items) {
  const container = document.getElementById(elementId);
  container.textContent = "";
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "plan-card";
    const title = document.createElement("h4");
    title.textContent = item.title;
    const detail = document.createElement("p");
    detail.textContent = item.detail;
    const impact = document.createElement("p");
    impact.textContent =
      `CO2e ${formatNumber(item.impact.co2e_kg_week)}` +
      ` kg/week - exposure ${formatNumber(item.impact.exposure_reduction_pct)}` +
      `% - cost ${formatNumber(item.impact.cost_delta_inr_month)}` +
      ` INR/month - sources: ${item.citations.join(", ")}`;
    card.appendChild(title);
    card.appendChild(detail);
    card.appendChild(impact);
    container.appendChild(card);
  });
}

/**
 * Render the three plan sections, the headline impact, and the profile note.
 *
 * @param {{routines?: Array<object>, hacks?: Array<object>,
 *   alternatives?: Array<object>, profile_note?: string}} data - Plan payload.
 * @returns {void}
 */
export function renderPlans(data) {
  const routines = data.routines || [];
  renderSection("plans-routines", routines);
  renderSection("plans-hacks", data.hacks || []);
  renderSection("plans-alternatives", data.alternatives || []);
  if (routines.length) {
    renderImpact(routines[0].impact);
  }
  if (data.profile_note) {
    showStatus(data.profile_note);
  }
}

/**
 * Load the plan for an optional area filter.
 *
 * @param {string} [area] - Optional area name appended as `?area=`.
 * @returns {Promise<void>} Resolves after the plan renders or the error shows.
 */
export function loadPlans(area) {
  const suffix = area ? `?area=${encodeURIComponent(area)}` : "";
  return apiFetch(`/plans${suffix}`)
    .then((data) => {
      renderPlans(data);
      showStatus("Plan updated.");
    })
    .catch((error) => {
      showError(error.message);
    });
}

/**
 * Download the current plan as Markdown.
 *
 * @returns {Promise<void>} Resolves after the download starts or the error
 *   shows.
 */
export function exportPlan() {
  return apiFetch("/export?format=md")
    .then((markdown) => {
      const blob = new Blob([markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "air-quality-plan.md";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      showStatus("Plan exported as Markdown.");
    })
    .catch((error) => {
      showError(error.message);
    });
}
