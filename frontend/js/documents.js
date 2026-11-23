/**
 * Document library rendering, upload, and list refresh.
 *
 * The upload uses `FormData` so the API wrapper leaves the multipart body
 * untouched, and every rendered value is written with `textContent`.
 */

import { apiFetch } from "./api.js";
import { showError, showStatus } from "./ui.js";

/**
 * Render the document titles and kinds into the library list.
 *
 * @param {Array<{title: string, kind: string}>} documents - Document
 *   summaries.
 * @returns {void}
 */
export function renderDocuments(documents) {
  const list = document.getElementById("docs-list");
  list.textContent = "";
  documents.forEach((doc) => {
    const item = document.createElement("li");
    item.textContent = `${doc.title} (${doc.kind})`;
    list.appendChild(item);
  });
}

/**
 * Load the current user's documents.
 *
 * @returns {Promise<Array<object>>} The documents, or an empty array after an
 *   error is announced.
 */
export function loadDocuments() {
  return apiFetch("/documents")
    .then((documents) => {
      renderDocuments(documents);
      return documents;
    })
    .catch((error) => {
      showError(error.message);
      return [];
    });
}

/**
 * Upload the selected PDF and refresh the document list.
 *
 * @param {SubmitEvent} [event] - The form submit event, when wired as a
 *   listener.
 * @returns {Promise<Array<object> | null>} The refreshed documents, or `null`
 *   when no file was chosen or the upload failed.
 */
export function uploadDocument(event) {
  if (event) {
    event.preventDefault();
  }
  const input = document.getElementById("docfile");
  if (!input.files || !input.files.length) {
    showError("Choose a PDF first.");
    return Promise.resolve(null);
  }
  const form = new FormData();
  form.append("file", input.files[0]);
  return apiFetch("/documents/upload", { method: "POST", body: form })
    .then(() => {
      document.getElementById("uploadStatus").textContent = "Upload complete.";
      showStatus("Document added to your corpus.");
      return loadDocuments();
    })
    .catch((error) => {
      document.getElementById("uploadStatus").textContent = error.message;
      showError(error.message);
      return null;
    });
}
