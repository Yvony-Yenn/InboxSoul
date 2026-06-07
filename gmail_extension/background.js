// Service worker: the only place that talks to the localhost daemon.
// Running fetch here (not in content.js) uses the extension's host_permissions,
// which bypasses the page's CORS and Chrome's Private Network Access checks that
// would otherwise block a mail.google.com page from reaching http://localhost.

const DAEMON = "http://localhost:8000";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "process_email") return;

  fetch(`${DAEMON}/api/process_email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(msg.payload),
  })
    .then(async (resp) => {
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      return resp.json();
    })
    .then((result) => sendResponse({ ok: true, result }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));

  return true; // keep the channel open for the async sendResponse
});