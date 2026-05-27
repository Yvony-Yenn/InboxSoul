"""Outlook fetcher via Microsoft Graph API.

OAuth2 uses the Device Code Flow: no redirect_uri, no client_secret, no local
HTTP server. First run prints a URL + code that the user opens in a browser
to log in; later runs reuse the refresh token silently from a local cache.

Setup (one-time, per user):
  1. Go to https://portal.azure.com → App registrations → New registration
       - Name: e.g. "InboxSoul Dev"
       - Supported account types: "Accounts in any organizational directory
         and personal Microsoft accounts"
       - Redirect URI: leave blank
  2. After creation, on the app's Overview page, copy
       "Application (client) ID"  →  this is OUTLOOK_CLIENT_ID
  3. Authentication → "Allow public client flows" → set to Yes → Save
  4. API permissions → Add a permission → Microsoft Graph → Delegated
       permissions → check `Mail.Read` and `offline_access` → Add
  5. Export the env var:
       export OUTLOOK_CLIENT_ID=<the GUID you copied in step 2>
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from msal import PublicClientApplication, SerializableTokenCache

_AUTHORITY = "https://login.microsoftonline.com/common"
_SCOPES = ["Mail.Read"]
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_CACHE_PATH = Path.home() / ".cache" / "inboxsoul" / "outlook_token.json"


@dataclass
class RawOutlookMessage:
    """One inbox message as returned by Graph, before cleaning."""

    message_id: str
    sender: str
    subject: str
    received_at: str
    body: str
    body_content_type: str


def _load_cache() -> SerializableTokenCache:
    cache = SerializableTokenCache()
    if _TOKEN_CACHE_PATH.exists():
        cache.deserialize(_TOKEN_CACHE_PATH.read_text())
    return cache


def _save_cache(cache: SerializableTokenCache) -> None:
    if not cache.has_state_changed:
        return
    _TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Refresh tokens are sensitive — restrict to the current user
    _TOKEN_CACHE_PATH.write_text(cache.serialize())
    _TOKEN_CACHE_PATH.chmod(0o600)


def _acquire_token(client_id: str) -> str:
    cache = _load_cache()
    app = PublicClientApplication(client_id, authority=_AUTHORITY, token_cache=cache)

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(_SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=_SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow init failed: {flow}")
        print(flow["message"], flush=True)
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache)

    if "access_token" not in result:
        raise RuntimeError(
            f"Token acquisition failed: {result.get('error_description', result)}"
        )
    return result["access_token"]


async def fetch_inbox(
    client_id: str | None = None,
    top: int = 25,
    folder: str = "inbox",
) -> list[RawOutlookMessage]:
    client_id = client_id or os.environ.get("OUTLOOK_CLIENT_ID")
    if not client_id:
        raise RuntimeError(
            "OUTLOOK_CLIENT_ID env var not set. "
            "Register an Azure AD app and set it — see module docstring."
        )

    # msal is sync; off-load to a thread so we don't block the event loop
    token = await asyncio.to_thread(_acquire_token, client_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_GRAPH_BASE}/me/mailFolders/{folder}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$top": top,
                "$orderby": "receivedDateTime desc",
                "$select": "id,from,subject,receivedDateTime,body",
            },
        )
        resp.raise_for_status()
        payload = resp.json()

    messages: list[RawOutlookMessage] = []
    for m in payload.get("value", []):
        sender = m.get("from", {}).get("emailAddress", {}).get("address", "")
        body = m.get("body", {}) or {}
        messages.append(
            RawOutlookMessage(
                message_id=m["id"],
                sender=sender,
                subject=m.get("subject", "") or "",
                received_at=m["receivedDateTime"],
                body=body.get("content", "") or "",
                body_content_type=body.get("contentType", "html"),
            )
        )
    return messages


if __name__ == "__main__":
    msgs = asyncio.run(fetch_inbox(top=10))
    print(f"\nFetched {len(msgs)} message(s):\n")
    for m in msgs:
        subject = (m.subject or "(no subject)")[:70]
        print(f"  [{m.received_at}] {m.sender}\n    {subject}\n")
