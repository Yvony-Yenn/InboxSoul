"""IMAPSource — async IMAP/IMAPS implementation of IngestionSource.

fetch_unread is read-only: it does NOT mark messages as SEEN. Caller is
responsible for de-duplication across runs (e.g. by tracking processed
message_id values in pipeline state).
"""

from __future__ import annotations

from aioimaplib import IMAP4_SSL

from src.ingestion.base import IngestionSource
from src.ingestion.cleaner import clean_message
from src.ingestion.raw_parser import parse_raw_message
from src.pipeline.schemas import CleanedEmail


class IMAPSource(IngestionSource):
    def __init__(
        self,
        host: str,
        port: int = 993,
        username: str = "",
        password: str = "",
        mailbox: str = "INBOX",
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.timeout = timeout

    async def fetch_unread(self, limit: int = 50) -> list[CleanedEmail]:
        client = IMAP4_SSL(host=self.host, port=self.port, timeout=self.timeout)
        await client.wait_hello_from_server()
        try:
            login = await client.login(self.username, self.password)
            if login.result != "OK":
                raise RuntimeError(f"IMAP login failed: {login.result} {login.lines}")
            await client.select(self.mailbox)

            search = await client.search("UNSEEN")
            if search.result != "OK" or not search.lines:
                return []

            uids = _parse_uids(search.lines[0])
            if not uids:
                return []
            uids = uids[-limit:]

            results: list[CleanedEmail] = []
            for uid in uids:
                fetch = await client.fetch(uid, "(BODY.PEEK[])")
                if fetch.result != "OK":
                    continue
                raw = _extract_raw_bytes(fetch.lines)
                if raw:
                    results.append(clean_message(parse_raw_message(raw)))
            return results
        finally:
            await client.logout()


def _parse_uids(line: bytes | str) -> list[str]:
    text = line.decode() if isinstance(line, (bytes, bytearray)) else line
    return text.split()


def _extract_raw_bytes(lines: list) -> bytes | None:
    """aioimaplib FETCH response lines = [header_str, raw_email_bytes, trailer, ...].
    Pick the largest bytes payload — that's the RFC 822 message."""
    candidates = [ln for ln in lines if isinstance(ln, (bytes, bytearray)) and len(ln) > 50]
    if not candidates:
        return None
    return max(candidates, key=len)