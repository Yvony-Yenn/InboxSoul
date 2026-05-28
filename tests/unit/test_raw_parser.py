"""Unit tests for src/ingestion/raw_parser.py — bytes → RawEmail only.

The parser produces structured fields; HTML and signatures are NOT stripped here
(that's clean_message's job). These tests verify only the parsing layer.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.raw_parser import RawEmail, parse_raw_message

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw_emails"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_plain_email_parsed() -> None:
    raw = parse_raw_message(_load("plain.eml"))
    assert isinstance(raw, RawEmail)
    assert raw.message_id == "plain-001@acme.com"
    assert raw.sender == "alice@acme.com"
    assert raw.subject == "Standup tomorrow"
    assert "move standup to 10am" in raw.body
    assert raw.body_content_type == "text"


def test_multipart_prefers_text_plain() -> None:
    raw = parse_raw_message(_load("multipart.eml"))
    assert raw.body_content_type == "text"
    assert "review PR #517" in raw.body
    assert "<b>" not in raw.body
    assert raw.sender == "bob@acme.com"


def test_html_only_keeps_html_tagged() -> None:
    """Parser does NOT strip HTML — cleaner does. Parser only flags content type."""
    raw = parse_raw_message(_load("html_only.eml"))
    assert raw.body_content_type == "html"
    assert "BIG SALE" in raw.body
    assert "<" in raw.body  # tags still present — cleaner will remove them


def test_rfc2047_subject_decoded() -> None:
    raw = parse_raw_message(_load("utf8_subject.eml"))
    assert raw.subject == "关于下周课程安排"
    assert raw.sender == "laoshi@example.cn"


def test_received_at_is_iso_string() -> None:
    raw = parse_raw_message(_load("plain.eml"))
    assert isinstance(raw.received_at, str)
    assert "2026-05-26" in raw.received_at  # cleaner parses this to datetime