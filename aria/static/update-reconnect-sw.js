const ARIA_UPDATE_SW_VERSION = "2026-05-16-alpha269";
const ARIA_RECONNECT_LABELS = __ARIA_RECONNECT_LABELS__;

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function labelsForBrowser() {
  const language = String(navigator.language || "").toLowerCase().startsWith("en") ? "en" : "de";
  return ARIA_RECONNECT_LABELS[language] || ARIA_RECONNECT_LABELS.en || ARIA_RECONNECT_LABELS.de || {};
}

function reconnectShell(targetUrl) {
  const labels = labelsForBrowser();
  const safeTarget = escapeHtml(targetUrl || "/");
  const targetJson = JSON.stringify(targetUrl || "/");
  const labelsJson = JSON.stringify(labels);
  const html = `<!DOCTYPE html>
<html lang="${escapeHtml(labels.language || "de")}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>${escapeHtml(labels.title || "ARIA")}</title>
  <style>
    :root { color-scheme: dark; }
    body {
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at 20% 20%, rgba(71, 146, 255, 0.22), transparent 30rem),
        radial-gradient(circle at 80% 70%, rgba(18, 255, 180, 0.14), transparent 28rem),
        #08100f;
      color: #edf7f2;
      font: 16px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(720px, calc(100vw - 32px));
      border: 1px solid rgba(237, 247, 242, 0.2);
      border-radius: 24px;
      padding: 28px;
      background: rgba(8, 16, 15, 0.86);
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
    }
    .kicker {
      margin: 0 0 8px;
      color: #93f5cc;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0 0 12px;
      font-size: clamp(2rem, 5vw, 3.4rem);
      line-height: 0.95;
    }
    p { margin: 0 0 14px; color: rgba(237, 247, 242, 0.82); }
    code {
      display: inline-block;
      max-width: 100%;
      overflow-wrap: anywhere;
      padding: 3px 7px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.08);
      color: #b8ffd9;
    }
    .status {
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(147, 245, 204, 0.1);
      border: 1px solid rgba(147, 245, 204, 0.22);
      color: #dffced;
    }
    button {
      margin-top: 16px;
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      background: #93f5cc;
      color: #07100d;
      font-weight: 800;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <main>
    <p class="kicker">${escapeHtml(labels.kicker || "Update")}</p>
    <h1>${escapeHtml(labels.title || "ARIA")}</h1>
    <p>${escapeHtml(labels.body || "ARIA is restarting.")}</p>
    <p><span>${escapeHtml(labels.target || "Target page:")}</span> <code>${safeTarget}</code></p>
    <div class="status" id="status">${escapeHtml(labels.status || "Waiting for /health ...")}</div>
    <button type="button" id="retry">${escapeHtml(labels.retry || "Retry")}</button>
  </main>
  <script>
    (function () {
      const targetUrl = ${targetJson};
      const labels = ${labelsJson};
      const status = document.getElementById("status");
      const retry = document.getElementById("retry");
      async function probe() {
        try {
          const response = await fetch("/health?reconnect=" + Date.now(), { cache: "no-store" });
          const text = await response.text();
          if (response.ok && text.toLowerCase().includes("ok")) {
            status.textContent = labels.online || "ARIA is reachable again. Reloading ...";
            window.setTimeout(() => window.location.replace(targetUrl), 650);
            return;
          }
        } catch (_error) {
          // Main container is still unavailable; keep the waiting shell visible.
        }
        status.textContent = labels.waiting || "Still waiting for ARIA to come back ...";
      }
      retry.addEventListener("click", probe);
      window.setInterval(probe, 2000);
      window.setTimeout(probe, 250);
    })();
  </script>
</body>
</html>`;
  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-ARIA-Reconnect-Shell": ARIA_UPDATE_SW_VERSION,
    },
  });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.mode !== "navigate") {
    return;
  }
  event.respondWith(fetch(request).catch(() => reconnectShell(request.url)));
});
