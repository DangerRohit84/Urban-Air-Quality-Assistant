"use strict";

/* Urban Air Quality Assistant - front-end controller.
 *
 * Every dynamic write goes through textContent or createElement; the app never
 * parses a string as HTML. Status and error messages are announced through the
 * live regions in index.html.
 */

var TOKEN_KEY = "uqa_token";
var EMAIL_KEY = "uqa_email";

function token() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

function apiFetch(path, options) {
  var opts = options || {};
  opts.headers = Object.assign({}, opts.headers);
  var bearer = token();
  if (bearer) {
    opts.headers.Authorization = "Bearer " + bearer;
  }
  if (
    opts.body &&
    typeof opts.body !== "string" &&
    !(opts.body instanceof FormData)
  ) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  return fetch(path, opts).then(function (response) {
    if (!response.ok) {
      return response.json().catch(function () {
        return {};
      }).then(function (body) {
        throw new Error(body.detail || "request failed");
      });
    }
    if (response.status === 204) {
      return null;
    }
    var type = response.headers.get("content-type") || "";
    return type.indexOf("application/json") !== -1
      ? response.json()
      : response.text();
  });
}

function showStatus(message) {
  document.getElementById("status").textContent = message;
}

function showError(message) {
  document.getElementById("errors").textContent = message;
  focusErrors();
}

function focusErrors() {
  document.getElementById("errors").focus();
}
