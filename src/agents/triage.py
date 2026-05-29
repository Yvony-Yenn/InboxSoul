"""Agent 1: Email Triage. Single LLM call returning a validated TriageOutput."""

from __future__ import annotations

from src.llm.base import LLMClient
from src.pipeline.schemas import CleanedEmail, TriageOutput
from src.pipeline.skills import load_skill

_SKILL_NAME = "triage"
_PLACEHOLDER = "{{few_shot_examples}}"


async def run_triage(
    email: CleanedEmail,
    llm_client: LLMClient,
    few_shot_examples: str = "",
) -> TriageOutput:
    system = load_skill(_SKILL_NAME).replace(_PLACEHOLDER, few_shot_examples)
    user = (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n"
        f"Received: {email.received_at.isoformat()}\n\n"
        f"{email.body}"
    )
    return await llm_client.chat_json(
        system=system,
        user=user,
        schema=TriageOutput,
    )
