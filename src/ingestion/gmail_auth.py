"""Gmail OAuth — InstalledAppFlow with a cached token.

scope = gmail.modify: read messages + add/remove labels + archive (remove the
INBOX label). Deliberately NOT https://mail.google.com/ — we never want
permanent-delete authority on the user's mailbox.

Files (gitignored, never commit):
    credentials.json  OAuth client secret downloaded from Google Cloud Console
    token.json        cached user token, written on first consent

Run once to grant consent and cache the token:
    uv run python -m src.ingestion.gmail_auth
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
):
    creds: Credentials | None = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


if __name__ == "__main__":
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authorized as {profile['emailAddress']} — token.json cached.")
