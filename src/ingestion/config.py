"""IMAP credentials — loaded from .env or process environment.

Expected .env keys (defined in .env.example):
    IMAP_HOST=outlook.office365.com
    IMAP_PORT=993
    IMAP_USER=you@northeastern.edu
    IMAP_PASSWORD=<app-password>        # Microsoft 365 requires an App Password,
                                        # not your account password
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.ingestion.imap_source import IMAPSource


class IMAPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="IMAP_",
    )

    host: str = "outlook.office365.com"
    port: int = 993
    user: str = ""
    password: str = ""

    def build_source(self) -> IMAPSource:
        return IMAPSource(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
        )