"""Tests for the HTML / signature / quoted-reply cleaner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.ingestion.cleaner import clean_message
from src.pipeline.schemas import CleanedEmail


@dataclass
class _Raw:
    body: str = ""
    body_content_type: str = "text"
    message_id: str = "msg-1"
    sender: str = "alice@example.com"
    subject: str = "test"
    received_at: str = "2024-05-26T12:34:56Z"


def test_plain_text_passes_through_with_whitespace_normalized():
    raw = _Raw(body="Hello\n   world  \n\n\n\nGoodbye")
    out = clean_message(raw)
    assert isinstance(out, CleanedEmail)
    assert out.body == "Hello\nworld\n\nGoodbye"


def test_html_is_stripped_to_text():
    raw = _Raw(
        body="<p>Hello <b>world</b></p><p>Second paragraph.</p>",
        body_content_type="html",
    )
    out = clean_message(raw)
    assert "Hello" in out.body
    assert "world" in out.body
    assert "Second paragraph" in out.body
    assert "<" not in out.body and ">" not in out.body


def test_html_blockquote_dropped():
    raw = _Raw(
        body=(
            "<p>Sure, here is my reply.</p>"
            "<blockquote>Original message from Alice</blockquote>"
        ),
        body_content_type="html",
    )
    out = clean_message(raw)
    assert "reply" in out.body
    assert "Alice" not in out.body


def test_html_script_and_style_dropped():
    raw = _Raw(
        body="<style>p{color:red}</style><p>Body</p><script>alert(1)</script>",
        body_content_type="html",
    )
    out = clean_message(raw)
    assert out.body == "Body"


def test_gmail_quoted_reply_dropped():
    raw = _Raw(
        body=(
            "My answer is here.\n\n"
            "On Mon, May 1, 2024 at 9:00 AM Alice wrote:\n"
            "> previous email content\n"
            "> more quoted lines\n"
        ),
    )
    out = clean_message(raw)
    assert "My answer is here." in out.body
    assert "previous email content" not in out.body
    assert "Alice wrote" not in out.body


def test_outlook_quoted_header_dropped():
    raw = _Raw(
        body=(
            "Quick reply.\n\n"
            "From: Bob <bob@example.com>\n"
            "Sent: Monday, May 13, 2024 9:00 AM\n"
            "To: Me\n"
            "Subject: Old subject\n\n"
            "Bob's previous content"
        ),
    )
    out = clean_message(raw)
    assert "Quick reply" in out.body
    assert "Bob's previous content" not in out.body


def test_original_message_divider_dropped():
    raw = _Raw(
        body=(
            "New content here.\n"
            "-------- Original Message --------\n"
            "Old content here."
        ),
    )
    out = clean_message(raw)
    assert "New content here." in out.body
    assert "Old content here." not in out.body


def test_signature_dash_dash_delimiter_dropped():
    raw = _Raw(body="Real content.\n-- \nAlice Anderson\nCEO, ExampleCo")
    out = clean_message(raw)
    assert "Real content." in out.body
    assert "Alice Anderson" not in out.body
    assert "ExampleCo" not in out.body


def test_signature_sent_from_iphone_dropped():
    raw = _Raw(body="Quick note.\nSent from my iPhone")
    out = clean_message(raw)
    assert out.body == "Quick note."


def test_signature_get_outlook_for_ios_dropped():
    raw = _Raw(body="Body text.\nGet Outlook for iOS")
    out = clean_message(raw)
    assert out.body == "Body text."


def test_received_at_zulu_iso8601_parsed_to_utc_datetime():
    raw = _Raw(received_at="2024-05-26T12:34:56Z", body="hi")
    out = clean_message(raw)
    assert isinstance(out.received_at, datetime)
    assert out.received_at.year == 2024
    assert out.received_at.month == 5
    assert out.received_at.day == 26
    assert out.received_at.tzinfo is not None


def test_content_type_case_insensitive():
    raw = _Raw(body="<p>Hi</p>", body_content_type="HTML")
    out = clean_message(raw)
    assert out.body == "Hi"


def test_quoted_reply_then_signature_takes_earliest_cut():
    raw = _Raw(
        body=(
            "Live content.\n"
            "-- \nMy Signature\n"
            "On Mon, May 1, 2024 at 9:00 AM Alice wrote:\n"
            "> old"
        ),
    )
    out = clean_message(raw)
    assert "Live content." in out.body
    assert "My Signature" not in out.body
    assert "Alice wrote" not in out.body
