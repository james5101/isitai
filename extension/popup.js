// ── Config ───────────────────────────────────────────────────────────────────
const DEFAULT_API = "https://isitai-nkib.onrender.com";

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(score) {
  if (score >= 81) return "#ef4444";   // red       Very likely AI
  if (score >= 61) return "#f97316";   // orange    Likely AI
  if (score >= 41) return "#fbbf24";   // yellow    Uncertain
  if (score >= 21) return "#86efac";   // lt green  Probably human
  return "#22c55e";                    // green     Human-built
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Collect the top N evidence items across all analyzers, ordered by score.
// This surfaces the strongest signals without overwhelming the compact UI.
function topEvidence(breakdown, max = 5) {
  return Object.values(breakdown)
    .filter(r => r.score > 0 && r.evidence.length > 0)
    .sort((a, b) => b.score - a.score)
    .flatMap(r => r.evidence)
    .slice(0, max);
}

function getApiUrl() {
  // chrome.storage is callback-based — wrap it in a Promise so we can await it.
  // This is the same idea as promisifying a Node callback with util.promisify.
  return new Promise(resolve => {
    chrome.storage.local.get("apiUrl", ({ apiUrl }) => {
      resolve(apiUrl || DEFAULT_API);
    });
  });
}

// ── API call ─────────────────────────────────────────────────────────────────

async function analyze(pageUrl, apiUrl) {
  const res = await fetch(`${apiUrl}/analyze/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: pageUrl }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    throw new Error(`API error ${res.status}: ${msg}`);
  }

  return res.json();
}

// ── Render ────────────────────────────────────────────────────────────────────

function showError(msg) {
  document.getElementById("spinner").style.display = "none";
  const box = document.getElementById("error-box");
  box.textContent = msg;
  box.style.display = "block";
}

function renderResults(data, pageUrl, apiUrl) {
  const color = scoreColor(data.score);

  // Score number + label
  const numEl = document.getElementById("score-num");
  numEl.textContent = data.score;
  numEl.style.color = color;

  const labelEl = document.getElementById("score-label");
  labelEl.textContent = data.label;
  labelEl.style.color = color;

  // Animated progress bar — same requestAnimationFrame trick as the main app
  const bar = document.getElementById("score-bar");
  bar.style.background = color;
  bar.style.width = "0%";
  requestAnimationFrame(() => { bar.style.width = data.score + "%"; });

  // Stack pills
  const stackSection = document.getElementById("stack-section");
  if (data.stack && data.stack.length > 0) {
    stackSection.innerHTML = `
      <div class="section-label">Detected stack</div>
      <div class="pills">
        ${data.stack.map(t => `<span class="pill">${escHtml(t)}</span>`).join("")}
      </div>`;
  }

  // Top evidence
  const items = topEvidence(data.breakdown);
  const listEl = document.getElementById("evidence-list");
  if (items.length > 0) {
    listEl.innerHTML = items.map(e => `<li>${escHtml(e)}</li>`).join("");
  } else {
    listEl.outerHTML = `<p class="no-signals">No signals detected</p>`;
  }

  // "View full report" — opens the web app with ?url= pre-filled so it
  // auto-runs the analysis there with the full breakdown accordion.
  const base = apiUrl.replace(/\/+$/, "");
  document.getElementById("full-report-link").href =
    `${base}/?url=${encodeURIComponent(pageUrl)}`;

  document.getElementById("spinner").style.display = "none";
  document.getElementById("results").style.display = "block";
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function run() {
  const apiUrl = await getApiUrl();

  // Restore saved API URL into settings input if it differs from default
  if (apiUrl !== DEFAULT_API) {
    document.getElementById("api-url-input").value = apiUrl;
  }

  // Get the active tab's URL.
  // chrome.tabs.query is the MV3 way — no background script needed.
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const pageUrl = tab.url;

  // Show the hostname in the header
  try {
    document.getElementById("current-url").textContent = new URL(pageUrl).hostname;
  } catch {
    document.getElementById("current-url").textContent = pageUrl;
  }

  // Bail on non-HTTP pages (chrome://, about:, file://, etc.)
  if (!pageUrl.startsWith("http")) {
    showError("Can only analyze http/https pages.");
    return;
  }

  try {
    const data = await analyze(pageUrl, apiUrl);
    renderResults(data, pageUrl, apiUrl);
  } catch (e) {
    showError(e.message);
  }
}

// ── Settings ─────────────────────────────────────────────────────────────────

document.getElementById("settings-toggle").addEventListener("click", () => {
  document.getElementById("settings-row").classList.toggle("open");
});

document.getElementById("save-btn").addEventListener("click", async () => {
  const val = document.getElementById("api-url-input").value.trim();
  await chrome.storage.local.set({ apiUrl: val || DEFAULT_API });

  // Close settings and re-run with the new URL
  document.getElementById("settings-row").classList.remove("open");
  document.getElementById("results").style.display = "none";
  document.getElementById("error-box").style.display = "none";
  document.getElementById("spinner").style.display = "flex";
  run();
});

// Kick off on popup open
run();
