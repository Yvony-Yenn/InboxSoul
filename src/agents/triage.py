"""Agent 1: Email Triage. Single LLM call returning a validated TriageOutput."""

from __future__ import annotations

import json

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
    skill = load_skill(_SKILL_NAME).replace(_PLACEHOLDER, few_shot_examples)
    email_block = (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n"
        f"Received: {email.received_at.isoformat()}\n\n"
        f"{email.body}"
    )
    prompt = f"{skill}\n\n---EMAIL---\n{email_block}\n---END EMAIL---"
    raw = await llm_client.complete(prompt)
    return TriageOutput.model_validate(_extract_json_object(raw))


def _extract_json_object(raw: str) -> dict:
    """Extract the first top-level JSON object from raw LLM output.

    Tolerates leading prose ("Here is the JSON:"), trailing commentary, and an
    optional ```json ... ``` markdown fence — all of which LLMs emit despite
    being told not to. Raises ValueError if no valid JSON object is found.
    """
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM output: {raw!r}")
    try:
        data, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from LLM output: {raw!r}") from e
    if not isinstance(data, dict):
        raise ValueError(f"LLM output JSON is not an object: {raw!r}")
    return data
