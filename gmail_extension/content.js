// Injected into Gmail. Adds a floating button; on click it reads the open email
// from Gmail's DOM, asks background.js to run the pipeline, and shows a panel.

const PANEL_ID = "inboxsoul-panel";

// Gmail's class names are obfuscated but these three have been stable for years.
// If reading ever returns null, these are the selectors to re-check first.
function readOpenEmail() {
  const subjectEl = document.querySelector("h2.hP");
  const senderEl = document.querySelector("span.gD");
  const bodyEl = document.querySelector("div.a3s");
  if (!subjectEl || !bodyEl) return null;
  return {
    message_id: "gmail-" + Date.now(),
    sender: senderEl?.getAttribute("email") || senderEl?.textContent || "unknown@unknown",
    subject: subjectEl.textContent || "(no subject)",
    body: bodyEl.innerText || "",
    body_content_type: "text",
    received_at: new Date().toISOString(),
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]),
  );
}

function panel() {
  let p = document.getElementById(PANEL_ID);
  if (!p) {
    p = document.createElement("div");
    p.id = PANEL_ID;
    document.body.appendChild(p);
  }
  return p;
}

function render(html) {
  panel().innerHTML = html;
}

function renderResult(r) {
  const t = r.triage;
  const draft = r.draft
    ? `<h4>Draft</h4><div class="is-sub">${escapeHtml(r.draft.subject)}</div>
       <textarea readonly>${escapeHtml(r.draft.body)}</textarea>`
    : `<div class="is-muted">No draft — ${escapeHtml(r.reply_policy.decision)}</div>`;
  render(`
    <div class="is-head"><span>🧠 InboxSoul</span><span class="is-x">×</span></div>
    <div class="is-row"><b>${escapeHtml(t.category)}</b> · ${escapeHtml(t.priority)} · ${escapeHtml(t.spam_level)} · conf ${t.confidence.toFixed(2)}</div>
    <div class="is-sum">${escapeHtml(t.summary)}</div>
    <div class="is-row">risks: ${t.risk_flags.length ? escapeHtml(t.risk_flags.join(", ")) : "(none)"}</div>
    <div class="is-row">spam: ${escapeHtml(r.spam_decision.decision)}</div>
    <div class="is-row">safety: ${r.safety.override_action ? "⚠️ " + escapeHtml(r.safety.override_action) : "ok"}</div>
    <div class="is-row"><b>final: ${escapeHtml(r.final_action)}</b></div>
    ${draft}
  `);
  panel().querySelector(".is-x")?.addEventListener("click", () => panel().remove());
}

function run() {
  const payload = readOpenEmail();
  if (!payload) {
    render(`<div class="is-head">🧠 InboxSoul</div><div class="is-muted">Open an email first.</div>`);
    return;
  }
  render(`<div class="is-head">🧠 InboxSoul</div><div class="is-muted">Analyzing… (first run is slow — model cold start)</div>`);
  chrome.runtime.sendMessage({ type: "process_email", payload }, (resp) => {
    if (!resp) return render(`<div class="is-err">No response — is the daemon running on :8000?</div>`);
    if (!resp.ok) return render(`<div class="is-head">🧠 InboxSoul</div><div class="is-err">${escapeHtml(resp.error)}</div>`);
    renderResult(resp.result);
  });
}

function injectStyles() {
  if (document.getElementById("inboxsoul-style")) return;
  const s = document.createElement("style");
  s.id = "inboxsoul-style";
  s.textContent = `
    #inboxsoul-btn{position:fixed;right:20px;bottom:20px;z-index:99999;padding:8px 14px;border:none;border-radius:20px;background:#1a73e8;color:#fff;font-size:13px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.3)}
    #inboxsoul-panel{position:fixed;right:20px;bottom:64px;z-index:99999;width:320px;max-height:70vh;overflow:auto;background:#fff;border:1px solid #dadce0;border-radius:10px;padding:12px;font:13px/1.4 Arial,sans-serif;color:#202124;box-shadow:0 4px 16px rgba(0,0,0,.25)}
    #inboxsoul-panel .is-head{font-weight:bold;margin-bottom:8px;display:flex;justify-content:space-between}
    #inboxsoul-panel .is-x{cursor:pointer;color:#5f6368}
    #inboxsoul-panel .is-row{margin:4px 0}
    #inboxsoul-panel .is-sum{color:#5f6368;margin:6px 0}
    #inboxsoul-panel .is-muted{color:#5f6368}
    #inboxsoul-panel .is-err{color:#d93025;white-space:pre-wrap}
    #inboxsoul-panel textarea{width:100%;height:120px;margin-top:4px}
  `;
  document.head.appendChild(s);
}

function addButton() {
  if (document.getElementById("inboxsoul-btn")) return;
  const btn = document.createElement("button");
  btn.id = "inboxsoul-btn";
  btn.textContent = "🧠 Triage";
  btn.addEventListener("click", run);
  document.body.appendChild(btn);
}

injectStyles();
addButton();