"""GmailExecutor — applies the pipeline's verdict to Gmail via labels.

This is the only place that mutates the mailbox, so every CLAUDE.md red line lives
here. Decision order (safety always wins):

  1. high-risk flag / require_human_check / safety override  → NeedsReview, KEEP in inbox
  2. move_to_junk (definite spam + high confidence)          → Quarantine, archive
                                                               (NEVER Gmail Spam/Trash — testing phase)
  3. pass                                                    → InboxSoul/<category>, archive

Every processed message also gets InboxSoul/Triaged so GmailSource skips it next poll.

DRY_RUN (EXECUTOR_DRY_RUN, default true): log the intended labels without calling the
Gmail API. Flip to false only after watching one poll's logged plan.
"""

from __future__ import annotations

import asyncio
import logging
import os

from src.pipeline.schemas import (
    HIGH_RISK_FLAGS,
    Category,
    ProcessResult,
    SpamDecision,
)

logger = logging.getLogger("inboxsoul.executor")

TRIAGED_LABEL = "InboxSoul/Triaged"
NEEDS_REVIEW_LABEL = "InboxSoul/NeedsReview"
QUARANTINE_LABEL = "InboxSoul/Quarantine"

CATEGORY_LABELS = {
    Category.WORK: "InboxSoul/Work",
    Category.SCHOOL: "InboxSoul/School",
    Category.PERSONAL: "InboxSoul/Personal",
    Category.FINANCE: "InboxSoul/Finance",
    Category.PROMOTION: "InboxSoul/Promotion",
    Category.SYSTEM: "InboxSoul/System",
    Category.SPAM: QUARANTINE_LABEL,
}


def _dry_run() -> bool:
    return os.getenv("EXECUTOR_DRY_RUN", "true").lower() != "false"


class GmailExecutor:
    def __init__(self, service) -> None:
        self._svc = service
        self._label_cache: dict[str, str] = {}

    async def apply(self, result: ProcessResult) -> None:
        labels, archive = self._decide(result)
        labels.append(TRIAGED_LABEL)
        msg_id = result.cleaned_email.message_id
        if _dry_run():
            logger.info(
                "[DRY_RUN] %s → labels=%s, %s",
                msg_id,
                labels,
                "archive" if archive else "keep-in-inbox",
            )
            return
        await asyncio.to_thread(self._apply_sync, msg_id, labels, archive)

    def _decide(self, r: ProcessResult) -> tuple[list[str], bool]:
        has_high_risk = any(f in HIGH_RISK_FLAGS for f in r.triage.risk_flags)
        if (
            has_high_risk
            or r.spam_decision.decision == SpamDecision.REQUIRE_HUMAN_CHECK
            or r.safety.overridden
        ):
            return [NEEDS_REVIEW_LABEL], False
        if r.spam_decision.decision == SpamDecision.MOVE_TO_JUNK:
            return [QUARANTINE_LABEL], True
        return [CATEGORY_LABELS[r.triage.category]], True

    def _apply_sync(self, msg_id: str, labels: list[str], archive: bool) -> None:
        body: dict[str, list[str]] = {"addLabelIds": [self._label_id(n) for n in labels]}
        if archive:
            body["removeLabelIds"] = ["INBOX"]
        self._svc.users().messages().modify(userId="me", id=msg_id, body=body).execute()

    def _label_id(self, name: str) -> str:
        if name in self._label_cache:
            return self._label_cache[name]
        existing = self._svc.users().labels().list(userId="me").execute().get("labels", [])
        for lbl in existing:
            self._label_cache[lbl["name"]] = lbl["id"]
        if name not in self._label_cache:
            created = (
                self._svc.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            self._label_cache[name] = created["id"]
        return self._label_cache[name]