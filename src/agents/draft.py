"""Agent 4 — Draft Generation.

Pure draft generator. Does not decide *whether* a reply should be sent — that
policy lives in the orchestrator (pipeline mode) or in the user clicking
"draft this anyway" (manual mode). Agent 4 answers "how to reply", not "whether".
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from src.hermes.schemas import FewShotExample
from src.llm.ollama_client import OllamaClient
from src.pipeline.schemas import CleanedEmail, Draft, TriageOutput


class DraftInput(BaseModel):
    email: CleanedEmail
    triage: TriageOutput | None = None
    style_anchors: list[str] | None = None
    few_shot_examples: list[FewShotExample] | None = None


class DraftLLMOutput(BaseModel):
    subject: str
    body: str


class DraftAgent:
    def __init__(
        self,
        llm: OllamaClient,
        skill_path: str | Path = "skills/draft_agent.md",
    ) -> None:
        self.llm = llm
        self.system_prompt = Path(skill_path).read_text()

    async def run(self, payload: DraftInput) -> Draft:
        user_msg = self._build_user_message(payload)
        result = await self.llm.chat_json(
            system=self.system_prompt,
            user=user_msg,
            schema=DraftLLMOutput,
        )
        return Draft(
            subject=result.subject,
            body=result.body,
            style_references=payload.style_anchors or [],
        )

    def _build_user_message(self, payload: DraftInput) -> str:
        e = payload.email
        sections = [
            "## Incoming Email",
            f"From: {e.sender}",
            f"Subject: {e.subject}",
            f"Body:\n{e.body}",
        ]
        if payload.triage is not None:
            t = payload.triage
            sections += [
                "",
                "## Triage Context",
                f"Category: {t.category}",
                f"Priority: {t.priority}",
                f"Summary: {t.summary}",
                f"Key points: {', '.join(t.key_points)}",
            ]
        if payload.style_anchors:
            sections += ["", "## Style References"]
            sections += [f"- {a}" for a in payload.style_anchors]
        if payload.few_shot_examples:
            sections += ["", "## Recent Successful Replies"]
            for ex in payload.few_shot_examples:
                sections += [
                    "",
                    f"Incoming: {ex.incoming}",
                    f"Reply:    {ex.reply}",
                ]
        return "\n".join(sections)