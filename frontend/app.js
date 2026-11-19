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

function setSession(tokenValue, email) {
  sessionStorage.setItem(TOKEN_KEY, tokenValue);
  sessionStorage.setItem(EMAIL_KEY, email);
}

function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EMAIL_KEY);
}

function showApp() {
  document.getElementById("auth-card").hidden = true;
  [
    "profile-section",
    "air-panel",
    "plans",
    "impact",
    "ask",
    "documents",
  ].forEach(function (id) {
    document.getElementById(id).hidden = false;
  });
}

function hideApp() {
  document.getElementById("auth-card").hidden = false;
  [
    "profile-section",
    "air-panel",
    "plans",
    "impact",
    "ask",
    "documents",
  ].forEach(function (id) {
    document.getElementById(id).hidden = true;
  });
}

function handleRegister(event) {
  event.preventDefault();
  var payload = {
    email: document.getElementById("reg-email").value.trim(),
    password: document.getElementById("reg-password").value,
  };
  apiFetch("/auth/register", { method: "POST", body: payload })
    .then(function (data) {
      setSession(data.token, payload.email);
      showApp();
      showStatus("Welcome! Your account is ready.");
      loadProfile();
      loadPlans();
      loadDocuments();
    })
    .catch(function (error) {
      showError(error.message);
    });
}

function handleLogin(event) {
  event.preventDefault();
  var payload = {
    email: document.getElementById("login-email").value.trim(),
    password: document.getElementById("login-password").value,
  };
  apiFetch("/auth/login", { method: "POST", body: payload })
    .then(function (data) {
      setSession(data.token, payload.email);
      showApp();
      showStatus("Signed in.");
      loadProfile();
      loadPlans();
      loadDocuments();
    })
    .catch(function (error) {
      showError(error.message);
    });
}

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

function loadProfile() {
  return apiFetch("/profile")
    .then(function (profile) {
      fillProfileForm(profile);
      showStatus("Profile loaded.");
    })
    .catch(function () {
      showStatus("No profile yet - fill the form to personalize.");
    });
}

function saveProfile() {
  var payload = collectProfile();
  return apiFetch("/profile", { method: "PUT", body: payload })
    .then(function (profile) {
      fillProfileForm(profile);
      showStatus("Profile saved.");
      return profile;
    })
    .catch(function (error) {
      showError(error.message);
      return null;
    });
}

function renderAir(reading) {
  var text = reading.band || "No band";
  text += " (" + reading.source + ")";
  if (reading.fallback) {
    text += " - " + reading.fallback;
  }
  document.getElementById("aqi-readout").textContent = text;
}

function loadAir() {
  var city = document.getElementById("city").value.trim();
  if (!city) {
    showError("Enter your city first.");
    return Promise.resolve(null);
  }
  return apiFetch("/air?q=" + encodeURIComponent(city))
    .then(function (reading) {
      renderAir(reading);
      showStatus("Air quality updated.");
      return reading;
    })
    .catch(function (error) {
      showError(error.message);
      return null;
    });
}

function fetchLiveAqi() {
  return loadAir();
}

function saveAirContext() {
  var city = document.getElementById("city").value.trim();
  var band = document.getElementById("aqi-band").value;
  var season = document.getElementById("aqi-season").value;
  if (!city) {
    showError("Enter your city first.");
    return Promise.resolve(null);
  }
  return apiFetch("/air/context", {
    method: "POST",
    body: { city: city, band: band, season: season },
  })
    .then(function () {
      showStatus("Air-quality band saved.");
      return loadPlans();
    })
    .catch(function (error) {
      showError(error.message);
      return null;
    });
}

function formatNumber(value) {
  var numeric = Number(value);
  if (!isFinite(numeric)) {
    return "0";
  }
  return String(Math.round(numeric * 100) / 100);
}

function renderImpact(impact) {
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

function renderSection(elementId, items) {
  var container = document.getElementById(elementId);
  container.textContent = "";
  items.forEach(function (item) {
    var card = document.createElement("div");
    card.className = "plan-card";
    var title = document.createElement("h4");
    title.textContent = item.title;
    var detail = document.createElement("p");
    detail.textContent = item.detail;
    var impact = document.createElement("p");
    impact.textContent =
      "CO2e " +
      formatNumber(item.impact.co2e_kg_week) +
      " kg/week - exposure " +
      formatNumber(item.impact.exposure_reduction_pct) +
      "% - cost " +
      formatNumber(item.impact.cost_delta_inr_month) +
      " INR/month - sources: " +
      item.citations.join(", ");
    card.appendChild(title);
    card.appendChild(detail);
    card.appendChild(impact);
    container.appendChild(card);
  });
}

function renderPlans(data) {
  var routines = data.routines || [];
  renderSection("plans-routines", routines);
  renderSection("plans-hacks", data.hacks || []);
  renderSection("plans-alternatives", data.alternatives || []);
  if (routines.length) {
    renderImpact(routines[0].impact);
  }
  var note = data.profile_note;
  if (note) {
    showStatus(note);
  }
}

function loadPlans(area) {
  var suffix = area ? "?area=" + encodeURIComponent(area) : "";
  return apiFetch("/plans" + suffix)
    .then(function (data) {
      renderPlans(data);
      showStatus("Plan updated.");
    })
    .catch(function (error) {
      showError(error.message);
    });
}

function renderCitations(citations) {
  var list = document.getElementById("citations");
  list.textContent = "";
  citations.forEach(function (citation) {
    var item = document.createElement("li");
    item.textContent = citation;
    list.appendChild(item);
  });
}

function askQuestion(event) {
  if (event) {
    event.preventDefault();
  }
  var question = document.getElementById("q").value.trim();
  var plain = document.getElementById("plain").checked;
  if (!question) {
    showError("Enter a question first.");
    return Promise.resolve(null);
  }
  return apiFetch("/ask", {
    method: "POST",
    body: { "question": question, "plain_language": plain },
  })
    .then(function (data) {
      document.getElementById("answer-text").textContent = data.answer;
      document.getElementById("answerMode").textContent = "Mode: " + data.mode;
      renderCitations(data.citations || []);
      showStatus(
        data.grounded ? "Answered from the corpus." : "No corpus support found."
      );
      return data;
    })
    .catch(function (error) {
      showError(error.message);
      return null;
    });
}

function renderDocuments(documents) {
  var list = document.getElementById("docs-list");
  list.textContent = "";
  documents.forEach(function (doc) {
    var item = document.createElement("li");
    item.textContent = doc.title + " (" + doc.kind + ")";
    list.appendChild(item);
  });
}

function loadDocuments() {
  return apiFetch("/documents")
    .then(function (documents) {
      renderDocuments(documents);
      return documents;
    })
    .catch(function (error) {
      showError(error.message);
      return [];
    });
}

function uploadDocument(event) {
  if (event) {
    event.preventDefault();
  }
  var input = document.getElementById("docfile");
  if (!input.files || !input.files.length) {
    showError("Choose a PDF first.");
    return Promise.resolve(null);
  }
  var form = new FormData();
  form.append("file", input.files[0]);
  return apiFetch("/documents/upload", { method: "POST", body: form })
    .then(function () {
      document.getElementById("uploadStatus").textContent =
        "Upload complete.";
      showStatus("Document added to your corpus.");
      return loadDocuments();
    })
    .catch(function (error) {
      document.getElementById("uploadStatus").textContent = error.message;
      showError(error.message);
      return null;
    });
}

function exportPlan() {
  return apiFetch("/export?format=md")
    .then(function (markdown) {
      var blob = new Blob([markdown], { type: "text/markdown" });
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = "air-quality-plan.md";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      showStatus("Plan exported as Markdown.");
    })
    .catch(function (error) {
      showError(error.message);
    });
}

function init() {
  document
    .getElementById("register-form")
    .addEventListener("submit", handleRegister);
  document
    .getElementById("login-form")
    .addEventListener("submit", handleLogin);
  document
    .getElementById("profile-form")
    .addEventListener("submit", function (event) {
      event.preventDefault();
      saveProfile().then(function (profile) {
        if (profile) {
          loadPlans();
        }
      });
    });
  document.getElementById("fetch-live").addEventListener("click", fetchLiveAqi);
  document
    .getElementById("aqi-band")
    .addEventListener("change", saveAirContext);
  document
    .getElementById("aqi-season")
    .addEventListener("change", saveAirContext);
  document.getElementById("ask-form").addEventListener("submit", askQuestion);
  document
    .getElementById("upload-form")
    .addEventListener("submit", uploadDocument);
  document.getElementById("exportBtn").addEventListener("click", exportPlan);

  if (token()) {
    showApp();
    loadProfile();
    loadPlans();
    loadDocuments();
  } else {
    hideApp();
  }
}

document.addEventListener("DOMContentLoaded", init);
