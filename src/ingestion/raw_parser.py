"""RFC 5322 bytes → RawEmail dataclass.

Stays narrowly focused on **parsing** (MIME walking, charset decoding, header
decoding). All content cleanup — HTML → text, signature truncation, quoted-
reply removal, whitespace normalization — lives in `cleaner.clean_message`.

For structured sources that already provide message metadata (Microsoft Graph,
Gmail API), skip this module and construct RawEmail directly.
"""

from __future__ import annotations

import email
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime


@dataclass
class RawEmail:
    """Concrete dataclass satisfying cleaner.RawMessage Protocol."""

    message_id: str
    sender: str
    subject: str
    body: str
    body_content_type: str  # "text" or "html"
    received_at: str  # ISO 8601 string — cleaner parses this to datetime


def parse_raw_message(raw: bytes) -> RawEmail:
    msg = email.message_from_bytes(raw)
    body, ctype = _extract_body(msg)
    return RawEmail(
        message_id=_message_id(msg),
        sender=_sender(msg),
        subject=_decoded_header(msg.get("Subject", "")),
        body=body,
        body_content_type=ctype,
        received_at=_received_at_iso(msg),
    )


def _message_id(msg: Message) -> str:
    mid = (msg.get("Message-ID") or "").strip()
    return mid.strip("<>") or "unknown"


def _sender(msg: Message) -> str:
    raw_from = _decoded_header(msg.get("From", ""))
    _, addr = parseaddr(raw_from)
    return addr or "unknown@unknown"


def _decoded_header(value: str) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _received_at_iso(msg: Message) -> str:
    raw_date = msg.get("Date")
    if raw_date:
        try:
            return parsedate_to_datetime(raw_date).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(tz=timezone.utc).isoformat()


def _extract_body(msg: Message) -> tuple[str, str]:
    """Returns (body_text, content_type) where content_type is 'text' or 'html'."""
    if not msg.is_multipart():
        text = _decode_payload(msg)
        ctype = "html" if msg.get_content_type() == "text/html" else "text"
        return text, ctype

    plain: str | None = None
    html: str | None = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        ptype = part.get_content_type()
        if ptype == "text/plain" and plain is None:
            plain = _decode_payload(part)
        elif ptype == "text/html" and html is None:
            html = _decode_payload(part)

    if plain is not None:
        return plain, "text"
    if html is not None:
        return html, "html"
    return "", "text"


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")