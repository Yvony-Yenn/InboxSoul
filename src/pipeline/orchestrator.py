"""Pipeline orchestrator — the daemon's single entry point.

  raw_email (bytes) → ProcessResult

Wires cleaner → Agent 1 → safety → Agent 2 → Agent 3 → (Agent 4). Agent 1 and
Agent 2 are owned by the teammate and injected at construction time, decoupling
this module from their concrete implementations. Wiring example:

    from functools import partial
    from src.agents.triage import run_triage
    from src.agents.spam_decision import run_spam_decision
    from src.llm.ollama_client import OllamaClient

    llm = OllamaClient()
    orch = Orchestrator(
        triage_runner=partial(run_triage, llm_client=llm),
        spam_decider=run_spam_decision,
        draft_agent=DraftAgent(llm=llm),
        ...
    )

Phase 2 Outlook Add-in / FastAPI will wrap process_email() 1:1.
"""

from __future__ import annotations

from src.agents.draft import DraftAgent, DraftInput
from src.agents.reply_policy import run_reply_policy
from src.hermes.schemas import FewShotExample
from src.ingestion.cleaner import clean_message
from src.ingestion.raw_parser import parse_raw_message
from src.pipeline.schemas import (
    CleanedEmail,
    Draft,
    ProcessResult,
    RecommendedAction,
    ReplyPolicy,
    SpamDecider,
    SpamDecision,
    TriageOutput,
    TriageRunner,
)
from src.safety.scanner import scan as safety_scan


class Orchestrator:
    def __init__(
        self,
        triage_runner: TriageRunner,
        spam_decider: SpamDecider,
        draft_agent: DraftAgent,
        style_retriever=None,
        few_shot_retriever=None,
    ) -> None:
        self.triage_runner = triage_runner
        self.spam_decider = spam_decider
        self.draft_agent = draft_agent
        self.style_retriever = style_retriever
        self.few_shot_retriever = few_shot_retriever

    async def process_email(self, raw_email: bytes) -> ProcessResult:
        """Entry for sources that provide RFC 5322 raw bytes (IMAP / .eml)."""
        return await self.process_cleaned(clean_message(parse_raw_message(raw_email)))

    async def process_cleaned(self, cleaned: CleanedEmail) -> ProcessResult:
        """Entry for sources that already provide structured data (Outlook plugin).
        Skip the bytes-parsing layer; still runs the full agent pipeline."""
        triage = await self.triage_runner(cleaned)
        safety = safety_scan(triage)
        spam = self.spam_decider(triage)
        policy = run_reply_policy(triage, spam)

        final_action = self._resolve_action(triage, safety, spam, policy)

        draft: Draft | None = None
        if policy.decision == ReplyPolicy.DRAFT_NOW:
            draft = await self.draft_agent.run(
                DraftInput(
                    email=cleaned,
                    triage=triage,
                    style_anchors=self._style_anchors(cleaned, triage),
                    few_shot_examples=self._few_shots(cleaned),
                )
            )

        return ProcessResult(
            cleaned_email=cleaned,
            triage=triage,
            safety=safety,
            spam_decision=spam,
            reply_policy=policy,
            final_action=final_action,
            draft=draft,
        )

    @staticmethod
    def _resolve_action(
        triage: TriageOutput, safety, spam, policy
    ) -> RecommendedAction:
        """Resolve final_action across all stages. Order: safety > Agent 2 > Agent 3.
        Once escalated to ASK_USER_CHECK, never deescalate."""
        action = safety.override_action or triage.recommended_action

        if spam.decision == SpamDecision.REQUIRE_HUMAN_CHECK:
            return RecommendedAction.ASK_USER_CHECK

        if spam.decision == SpamDecision.MOVE_TO_JUNK:
            if action == RecommendedAction.ASK_USER_CHECK:
                return action
            return RecommendedAction.MOVE_TO_JUNK

        # spam.decision == PASS — let Agent 3 have the final word.
        if policy.decision == ReplyPolicy.DRAFT_NOW:
            return RecommendedAction.GENERATE_DRAFT
        if policy.decision == ReplyPolicy.DEFER_TO_USER:
            return RecommendedAction.ASK_USER_CHECK
        # ReplyPolicy.NO_REPLY — preserve triage's action (NO_ACTION, etc.)
        if action == RecommendedAction.GENERATE_DRAFT:
            return RecommendedAction.NO_ACTION
        return action

    def _style_anchors(
        self, cleaned: CleanedEmail, triage: TriageOutput
    ) -> list[str] | None:
        if self.style_retriever is None:
            return None
        return self.style_retriever.retrieve(
            cleaned.body, category=triage.category.value, k=3
        )

    def _few_shots(self, cleaned: CleanedEmail) -> list[FewShotExample] | None:
        if self.few_shot_retriever is None:
            return None
        return self.few_shot_retriever.retrieve(cleaned.body, k=3)