/*
 * InboxSoul taskpane — reads current Outlook email, calls localhost daemon,
 * renders multi-agent ProcessResult, and lets user open the draft in Outlook's
 * reply form. Safety red line: never auto-send; user always clicks Send themselves.
 */

/* global document, Office, fetch */

const DAEMON = "https://localhost:8000";

interface RawEmailPayload {
  message_id: string;
  sender: string;
  subject: string;
  body: string;
  body_content_type: "text" | "html";
  received_at: string;
}

interface ProcessResult {
  cleaned_email: { sender: string; subject: string; body: string; message_id: string };
  triage: {
    category: string;
    priority: string;
    spam_level: string;
    risk_flags: string[];
    summary: string;
    confidence: number;
  };
  safety: { override_action: string | null; reason: string | null };
  spam_decision: { decision: string; reason: string; blocked_by_risk_flags: string[] };
  reply_policy: { decision: string; reason: string };
  final_action: string;
  draft: { subject: string; body: string } | null;
}

let currentResult: ProcessResult | null = null;
let currentPayload: RawEmailPayload | null = null;

Office.onReady((info) => {
  if (info.host !== Office.HostType.Outlook) return;
  document.getElementById("sideload-msg")!.hidden = true;
  document.getElementById("btn-retry")!.addEventListener("click", () => void runPipeline());
  document.getElementById("btn-send")!.addEventListener("click", onSend);
  document.getElementById("btn-discard")!.addEventListener("click", onDiscard);
  document.getElementById("btn-acknowledge")!.addEventListener("click", onDiscard);
  void runPipeline();
});

async function runPipeline(): Promise<void> {
  showSection("loading");
  try {
    currentPayload = await readCurrentEmail();
    const resp = await fetch(`${DAEMON}/api/process_email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentPayload),
    });
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    currentResult = (await resp.json()) as ProcessResult;
    renderResult(currentResult);
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
  }
}

function readCurrentEmail(): Promise<RawEmailPayload> {
  return new Promise((resolve, reject) => {
    const item = Office.context.mailbox.item;
    if (!item) {
      reject(new Error("No email open"));
      return;
    }
    item.body.getAsync("text", (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) {
        reject(new Error(`Failed to read body: ${result.error?.message}`));
        return;
      }
      resolve({
        message_id: item.itemId || `unknown-${Date.now()}`,
        sender: (item as any).from?.emailAddress || "unknown@unknown",
        subject: item.subject || "(no subject)",
        body: result.value || "",
        body_content_type: "text",
        received_at: (item.dateTimeCreated || new Date()).toISOString(),
      });
    });
  });
}

function renderResult(r: ProcessResult): void {
  setText("email-sender", r.cleaned_email.sender);
  setText("email-subject", r.cleaned_email.subject);

  setText("triage-category", r.triage.category);
  setText("triage-summary-text", r.triage.summary);
  setText("triage-priority", r.triage.priority);
  setText("triage-spam", r.triage.spam_level);
  setText("triage-confidence", r.triage.confidence.toFixed(2));
  setText("triage-risks", r.triage.risk_flags.length ? r.triage.risk_flags.join(", ") : "(none)");

  setText(
    "safety-decision",
    r.safety.override_action
      ? `⚠️ ${r.safety.override_action} — ${r.safety.reason || ""}`
      : "no override",
  );
  setText("spam-decision", `${r.spam_decision.decision} — ${r.spam_decision.reason}`);
  setText("policy-decision", `${r.reply_policy.decision} — ${r.reply_policy.reason}`);
  setText("final-action", r.final_action);

  const draftSection = document.getElementById("draft-section")!;
  const noDraftSection = document.getElementById("no-draft-section")!;
  if (r.draft) {
    (document.getElementById("draft-subject") as HTMLInputElement).value = r.draft.subject;
    (document.getElementById("draft-body") as HTMLTextAreaElement).value = r.draft.body;
    draftSection.hidden = false;
    noDraftSection.hidden = true;
  } else {
    draftSection.hidden = true;
    noDraftSection.hidden = false;
  }

  showSection("result");
}

function onSend(): void {
  if (!currentResult || !currentPayload) return;
  const editedSubject = (document.getElementById("draft-subject") as HTMLInputElement).value;
  const editedBody = (document.getElementById("draft-body") as HTMLTextAreaElement).value;
  const original = currentResult.draft;
  const wasEdited = !original || editedBody !== original.body || editedSubject !== original.subject;

  Office.context.mailbox.item?.displayReplyFormAsync(editedBody);
  setText("action-status", "Reply form opened. Click Send in Outlook to actually send.");

  void recordFeedback(
    editedBody,
    wasEdited ? "edited_then_sent" : "sent",
    original?.body || "",
  );
}

function onDiscard(): void {
  if (!currentPayload) return;
  setText("action-status", "Discarded. Feedback recorded for Hermes.");
  void recordFeedback("", "discarded", currentResult?.draft?.body || "");
}

async function recordFeedback(
  finalSent: string,
  userAction: "sent" | "edited_then_sent" | "discarded",
  draftV0: string,
): Promise<void> {
  if (!currentPayload) return;
  try {
    await fetch(`${DAEMON}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: `fb-${currentPayload.message_id}-${Date.now()}`,
        incoming_email: {
          message_id: currentPayload.message_id,
          sender: currentPayload.sender,
          subject: currentPayload.subject,
          body: currentPayload.body,
          received_at: currentPayload.received_at,
        },
        draft_v0: draftV0,
        final_sent: finalSent,
        user_action: userAction,
        created_at: new Date().toISOString(),
      }),
    });
  } catch (err) {
    setText("action-status", `Feedback write failed: ${err}`);
  }
}

function showSection(which: "loading" | "result" | "error"): void {
  for (const id of ["loading", "result", "error"]) {
    document.getElementById(id)!.hidden = id !== which;
  }
}

function showError(msg: string): void {
  setText("error-detail", msg);
  showSection("error");
}

function setText(id: string, text: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}