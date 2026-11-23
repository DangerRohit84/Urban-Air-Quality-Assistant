/**
 * Live-region helpers shared by every feature module.
 *
 * Messages are written with `textContent` so user input is never parsed as
 * HTML, and errors move focus so keyboard and screen-reader users land on the
 * failure immediately.
 */

/**
 * Announce a non-critical message through the polite status region.
 *
 * @param {string} message - The message to announce.
 * @returns {void}
 */
export function showStatus(message) {
  document.getElementById("status").textContent = message;
}

/**
 * Announce an error through the assertive alert region and move focus to it.
 *
 * @param {string} message - The error message to announce.
 * @returns {void}
 */
export function showError(message) {
  document.getElementById("errors").textContent = message;
  focusErrors();
}

/**
 * Move focus to the error region so assistive technology reaches it at once.
 *
 * @returns {void}
 */
export function focusErrors() {
  document.getElementById("errors").focus();
}
