const namesEl = document.getElementById("names");
const checkBtn = document.getElementById("checkBtn");
const resultsEl = document.getElementById("results");

const STATUS_LABEL = {
  available: "Available",
  taken: "Taken",
  invalid: "Invalid",
  error: "Error",
  rate_limited: "Limited",
};

function parseNames(raw) {
  return [
    ...new Set(
      raw
        .split(/[\n,]+/)
        .map((n) => n.trim())
        .filter(Boolean)
    ),
  ];
}

function faceFor(result) {
  if (result.status === "taken" && (result.uuidRaw || result.name)) {
    const key = result.uuidRaw || result.name;
    return `<img class="result__face" src="https://mc-heads.net/avatar/${encodeURIComponent(key)}/40" alt="" width="40" height="40" loading="lazy" />`;
  }
  const mark =
    result.status === "available" ? "?" : result.status === "invalid" ? "!" : "·";
  return `<div class="result__face result__face--empty" aria-hidden="true">${mark}</div>`;
}

function detailFor(result) {
  if (result.status === "taken" && result.uuid) {
    return result.uuid;
  }
  if (result.message) return result.message;
  if (result.status === "available") return "Not registered on Mojang";
  return "";
}

function renderResults(results) {
  resultsEl.hidden = false;
  resultsEl.innerHTML = results
    .map((result, i) => {
      const status = result.status || "error";
      const label = STATUS_LABEL[status] || status;
      return `
        <article class="result result--${status}" style="animation-delay: ${i * 40}ms">
          ${faceFor(result)}
          <div class="result__meta">
            <p class="result__name">${escapeHtml(result.name || "(empty)")}</p>
            <p class="result__detail">${escapeHtml(detailFor(result))}</p>
          </div>
          <span class="result__badge">${label}</span>
        </article>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function runCheck() {
  const names = parseNames(namesEl.value);
  if (!names.length) {
    renderResults([
      {
        name: "",
        status: "invalid",
        message: "Enter at least one username.",
      },
    ]);
    return;
  }

  checkBtn.disabled = true;
  checkBtn.textContent = "Checking…";

  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ names }),
    });
    const data = await res.json();
    if (!res.ok) {
      renderResults([
        {
          name: names[0],
          status: "error",
          message: data.error || "Request failed.",
        },
      ]);
      return;
    }
    renderResults(data.results || []);
  } catch {
    renderResults([
      {
        name: names[0],
        status: "error",
        message: "Could not reach the local checker server.",
      },
    ]);
  } finally {
    checkBtn.disabled = false;
    checkBtn.textContent = "Check names";
  }
}

checkBtn.addEventListener("click", runCheck);

namesEl.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runCheck();
  }
});
