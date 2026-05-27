"""HTML / signature / quoted-reply cleaner.

Converts raw fetched messages (e.g. RawOutlookMessage) into the canonical
CleanedEmail consumed by Agent 1. Decoupled from the fetcher via a structural
Protocol so the same cleaner works for Outlook today, Gmail/IMAP later.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol

from bs4 import BeautifulSoup

from src.pipeline.schemas import CleanedEmail


class RawMessage(Protocol):
    """Structural type that any fetcher's raw output must satisfy."""

    message_id: str
    sender: str
    subject: str
    received_at: str
    body: str
    # "html" or "text" — case-insensitive, mirrors Microsoft Graph's contentType
    body_content_type: str


# Quoted-reply markers. Everything from the earliest match onward is discarded —
# replies in this codebase are downstream LLM input, and a quoted history both
# wastes tokens and confuses the triage signal.
_QUOTED_REPLY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\n-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE),
    re.compile(r"\nFrom:\s.+\nSent:\s.+\nTo:\s", re.IGNORECASE),
    re.compile(r"\nOn\s.+\swrote:\s*\n", re.IGNORECASE),
    re.compile(r"\n>{1,}\s"),
    re.compile(r"\n_{5,}\n"),
]

# Signature markers. Same truncate-at-earliest-match strategy.
_SIGNATURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\n-- ?\n"),
    re.compile(r"\nSent from my (iPhone|iPad|Android|mobile|Galaxy)", re.IGNORECASE),
    re.compile(r"\nGet Outlook for (iOS|Android)", re.IGNORECASE),
]

# HTML container classes that mail clients use to wrap quoted history.
_QUOTE_DIV_CLASSES = re.compile(r"gmail_quote|moz-cite-prefix|OutlookMessageHeader")


def clean_message(raw: RawMessage) -> CleanedEmail:
    body = (
        _html_to_text(raw.body)
        if raw.body_content_type.lower() == "html"
        else raw.body
    )
    body = _truncate_at_earliest_match(body, _QUOTED_REPLY_PATTERNS)
    body = _truncate_at_earliest_match(body, _SIGNATURE_PATTERNS)
    body = _normalize_whitespace(body)
    return CleanedEmail(
        message_id=raw.message_id,
        sender=raw.sender,
        subject=raw.subject,
        body=body,
        received_at=_parse_received_at(raw.received_at),
    )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for blockquote in soup.find_all("blockquote"):
        blockquote.decompose()
    for div in soup.find_all("div", class_=_QUOTE_DIV_CLASSES):
        div.decompose()
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _truncate_at_earliest_match(text: str, patterns: list[re.Pattern[str]]) -> str:
    earliest = len(text)
    for pat in patterns:
        m = pat.search(text)
        if m and m.start() < earliest:
            earliest = m.start()
    return text[:earliest]


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _parse_received_at(value: str) -> datetime:
    # Microsoft Graph returns "...Z"; Python 3.11+ accepts it via fromisoformat,
    # but normalize to +00:00 to stay portable across runtimes.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
