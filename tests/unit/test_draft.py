"""Agent 4 V0 unit tests. LLM is mocked — no network calls."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.draft import DraftAgent, DraftInput, DraftLLMOutput
from src.hermes.schemas import FewShotExample
from src.pipeline.schemas import Draft
from tests.fixtures.mock_data import (
    casual_email,
    chinese_email,
    work_email,
    work_triage,
)


@pytest.fixture
def mock_llm() -> AsyncMock:
    client = AsyncMock()
    client.chat_json = AsyncMock(
        return_value=DraftLLMOutput(
            subject="Re: Q2 roadmap review on Friday 3pm?",
            body="Friday 3pm works for me. I'll send a calendar invite shortly.",
        )
    )
    return client


@pytest.fixture
def agent(mock_llm: AsyncMock, tmp_path) -> DraftAgent:
    skill = tmp_path / "draft.md"
    skill.write_text("# Draft Agent\nGenerate an English reply.")
    return DraftAgent(llm=mock_llm, skill_path=skill)


async def test_draft_with_triage(agent: DraftAgent, mock_llm: AsyncMock) -> None:
    result = await agent.run(DraftInput(email=work_email(), triage=work_triage()))
    assert isinstance(result, Draft)
    assert result.subject
    assert result.body

    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Triage Context" in user_msg
    assert "work" in user_msg.lower()


async def test_draft_without_triage(agent: DraftAgent, mock_llm: AsyncMock) -> None:
    """User-triggered mode: Agent 4 must work on an email alone."""
    result = await agent.run(DraftInput(email=casual_email(), triage=None))
    assert isinstance(result, Draft)
    assert result.subject
    assert result.body

    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Triage Context" not in user_msg


async def test_draft_output_is_english(agent: DraftAgent) -> None:
    """Chinese in, English out. The mock returns English; we verify the agent
    does not error on non-ASCII input and the output contains no CJK characters."""
    result = await agent.run(DraftInput(email=chinese_email(), triage=None))
    text = result.subject + result.body
    has_cjk = any("一" <= c <= "鿿" for c in text)
    assert not has_cjk, f"Draft must be English-only, got: {text!r}"


async def test_draft_schema_valid(agent: DraftAgent) -> None:
    result = await agent.run(DraftInput(email=work_email(), triage=work_triage()))
    Draft.model_validate(result.model_dump())
    assert 0.0 <= result.confidence <= 1.0


async def test_style_anchors_render_in_prompt_and_pass_through(
    agent: DraftAgent, mock_llm: AsyncMock
) -> None:
    anchors = [
        "Will review tonight. Drop the diff link in Slack if it's urgent.",
        "10am works. I'll move the deploy review back 30 min.",
    ]
    result = await agent.run(
        DraftInput(email=work_email(), triage=work_triage(), style_anchors=anchors)
    )

    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Style References" in user_msg
    for a in anchors:
        assert a in user_msg

    assert result.style_references == anchors


async def test_no_style_anchors_means_no_section(
    agent: DraftAgent, mock_llm: AsyncMock
) -> None:
    await agent.run(DraftInput(email=work_email(), triage=None, style_anchors=None))
    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Style References" not in user_msg


async def test_few_shot_examples_render_in_prompt(
    agent: DraftAgent, mock_llm: AsyncMock
) -> None:
    examples = [
        FewShotExample(
            incoming="can you review PR #482?",
            reply="Will look tonight. Drop the diff in Slack if urgent.",
        ),
        FewShotExample(
            incoming="meeting moved to 10am — ok?",
            reply="10am works. Moving the deploy review back 30 min.",
        ),
    ]
    await agent.run(
        DraftInput(email=work_email(), triage=None, few_shot_examples=examples)
    )
    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Recent Successful Replies" in user_msg
    for ex in examples:
        assert ex.incoming in user_msg
        assert ex.reply in user_msg


async def test_no_few_shot_examples_means_no_section(
    agent: DraftAgent, mock_llm: AsyncMock
) -> None:
    await agent.run(DraftInput(email=work_email(), triage=None, few_shot_examples=None))
    user_msg = mock_llm.chat_json.await_args.kwargs["user"]
    assert "Recent Successful Replies" not in user_msg