# Project InboxSoul 3.0 — Email Agent

A stateful multi-agent email triage system with feedback-driven self-improvement.

**Design philosophy**: *Triage over Summarization*. Reject single-prompt shallow summaries; build a high-reliability, safety-first automation hub. Full design in `proposal_v3.docx`.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.




---

## Architecture Overview

```
[Fetch] → [Clean] → [Agent 1: Triage (LLM)]
                         ↓
                 [Safety Rule Check]
                         ↓
                 [Agent 2: Spam Decision (rules)]
                         ↓
                 [Agent 3: Reply Policy (rules)]
                         ↓
                 [Agent 4: Draft (LLM + RAG)]
                         ↓
                 [Human Review] → [Execution]
```

- **Only Agent 1 and Agent 4 call the LLM.** Agent 2 and 3 are pure rule engines (zero tokens, sub-second).
- **Hermes** is the feedback-driven self-evolution engine wrapping Agent 1 and Agent 4. Three stages: few-shot retrieval → periodic prompt rewriting → LoRA fine-tuning.

---

## Critical Safety Rules (NEVER violate)

1. **No auto-send.** AI never has outbound send authority. Drafts require explicit one-click by user.
2. **No auto-delete / auto-junk** when `risk_flags` contains any high-risk flag. The canonical list lives in `HIGH_RISK_FLAGS` in `src/pipeline/schemas.py` — that is the single source of truth. Current members: `money`, `account`, `deadline`, `legal`, `school`, `hr`. To add a new high-risk flag, update `schemas.py` only; do not duplicate the list here or in agent code.
3. **Agent 2 decision priority (hard-coded order — safety rules always evaluated first):**
   ```
   1. any(flag in HIGH_RISK_FLAGS for flag in triage.risk_flags)  → REQUIRE_HUMAN_CHECK
   2. spam_level == definite_spam and confidence >= 0.90           → MOVE_TO_JUNK
   3. spam_level == definite_spam (confidence < 0.90)              → REQUIRE_HUMAN_CHECK
   4. spam_level == suspicious                                     → REQUIRE_HUMAN_CHECK
   5. otherwise                                                    → PASS
   ```
   Rules are evaluated top-to-bottom and short-circuit. A `definite_spam` email with a `money` flag must go to human review, not junk. A `definite_spam` email with low confidence also goes to human review — auto-junk requires both a definite verdict and high confidence.
4. **Agent 1 must flag `risk_flags` conservatively.** If unsure whether a flag applies, include it rather than omit it. Risk flags are safety inputs for Agent 2 — optimizing for brevity here creates safety gaps. This principle must be reflected in `skills/triage.md`.
5. **Safety rules need 100% test coverage** in `tests/unit/test_safety.py`. Treat `src/safety/` as the project's red line — never relax these rules for convenience.
6. **Testing-phase Executor must not actually delete or auto-junk.** While the pipeline is in pre-production testing, the Executor (under `src/review/`) must route `SpamDecision.MOVE_TO_JUNK` to a dedicated **quarantine folder** rather than deleting messages or moving them to the IMAP/Gmail system Junk folder. The destination is gated behind a config flag and will be flipped to real Junk only after end-to-end verification. Agent 2's decision semantics are unchanged by this rule — the constraint lives at the execution layer.

---

## Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Local LLM | Ollama + `llama3.1:8b` | Default backend |
| Cloud LLM (optional) | Anthropic Claude / OpenAI | For Hermes Stage 2 meta-prompt rewriting |
| Embeddings | `nomic-embed-text` via Ollama | Keep everything local for privacy |
| Vector store | ChromaDB | Embedded, no ops |
| Agent orchestration | Hand-rolled + Pydantic | Do NOT introduce LangChain — explicit control is the point |
| API | FastAPI | |
| Review UI | Streamlit (MVP) → Next.js (later) | |
| Storage | SQLite + ChromaDB | |
| Scheduler | APScheduler | For Hermes periodic prompt rewrite |
| Package manager | uv | |
| Testing | pytest + pytest-asyncio | |

---

## Project Structure

```
src/
├── pipeline/        # Orchestrator, state machine, global schemas
├── ingestion/       # IMAP/Gmail fetch + HTML/signature cleanup
├── agents/          # 4 agents (triage, spam_decision, reply_policy, draft)
├── safety/          # Risk scanner + circuit breaker (RED LINE — 100% coverage)
├── llm/             # Provider-agnostic clients + Hermes routing layer
├── rag/             # ChromaDB, history retrieval, writing-style extraction
├── hermes/          # Feedback store, few-shot retriever, prompt rewriter, LoRA trainer
├── review/          # Human review queue + post-confirm executor
└── ui/              # FastAPI + Streamlit/Next.js
skills/              # Markdown agent specs (Claude Skill pattern: role + schema + few-shot + edges)
evaluation/          # Golden set + metrics + reports
tests/               # Mirrors src/ structure
```

---

## Agent 1 Output Schema (canonical)

Defined in `src/pipeline/schemas.py` as a Pydantic model:

```python
{
  "category": "work | school | personal | finance | promotion | system | spam",
  "summary": "single-sentence summary",
  "key_points": ["atomic fact 1", ...],
  "priority": "urgent | high | medium | low",
  "spam_level": "definite_spam | suspicious | not_spam",
  "reply_needed": bool,
  "reply_type": "must_review | draft_later | one_click | no_reply",
  "risk_flags": ["deadline", "money", "account", "external_link", ...],  # must use RiskFlag enum values
  "recommended_action": "move_to_junk | ask_user_check | generate_draft | no_action",
  "confidence": 0.0-1.0
}
```

`risk_flags` is typed as `list[RiskFlag]` — Agent 1's LLM output must use exact enum values or Pydantic validation will raise. Valid values are defined in `RiskFlag` in `schemas.py`.

Agent 2 / 3 consume this JSON only — they MUST NOT re-read the raw email.

## Agent 2 Output Schema (canonical)

Defined in `src/pipeline/schemas.py` as `SpamDecisionOutput`:

```python
{
  "decision": "move_to_junk | require_human_check | pass",
  "reason": "human-readable explanation shown in Streamlit review UI",
  "blocked_by_risk_flags": ["money", ...],  # populated when rule #1 fires
  "confidence": 0.0-1.0
}
```

Agent 2 is a pure rule engine — zero LLM calls. Decision logic and priority order are in Critical Safety Rule #3 above.

---

## How to Run

```bash
# One-time: install local LLM
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Start Ollama (or `brew services start ollama`)
ollama serve

# Install deps
uv sync

# Run the pipeline (offline mode with sample emails)
uv run python -m src.pipeline.orchestrator --source tests/fixtures/sample_emails

# Run the review UI
uv run streamlit run src/ui/streamlit_app.py

# Run evaluation against golden set
uv run python -m evaluation.run_eval

# Tests
uv run pytest                          # all
uv run pytest tests/unit/test_safety.py -v   # safety must always be green
```

---

## Code Conventions

- **Type hints everywhere.** Pydantic models for all cross-agent data.
- **No comments unless explaining WHY** (a non-obvious constraint, a workaround). Don't narrate WHAT the code does.
- **No backwards-compat shims.** This is a greenfield project; delete unused code rather than commenting it out.
- **Async by default** for I/O (IMAP, LLM calls, vector store).
- **Skills as markdown.** Each LLM-calling agent's prompt lives in `skills/<agent>.md` — never hardcode prompts in Python beyond a `load_skill()` call.
- **Tests mirror src/ layout.** `src/agents/triage.py` → `tests/unit/test_triage.py`.

---

## Development Order (avoid rework)

1. **Week 1** — Ollama + LLM abstraction + schemas + dummy E2E pipeline with mocks
2. **Week 2** — Agent 1 (Triage) + safety rules + Agent 2/3 (pure logic)
3. **Week 3** — RAG (history retrieval + style extraction) + Agent 4 (Draft)
4. **Week 4** — Evaluation framework + golden set + baseline numbers + Streamlit review UI
5. **Week 5** — Hermes Stage 1 (feedback store + few-shot retrieval) + re-run eval to show lift
6. **Week 6+** — Hermes Stage 2 (prompt auto-rewrite), then Stage 3 (LoRA, optional but resume-strong)

---

## Resume-Relevant Highlights

When generating docs/READMEs, surface these explicitly — they are the differentiators for US tech recruiters:

- Multi-agent system with LLM/rule-engine separation → ~50% token cost reduction
- Provider-agnostic LLM layer (local Ollama + cloud Claude/OpenAI) with privacy-aware routing
- Hermes: three-stage feedback-driven self-improvement (few-shot → prompt rewrite → LoRA)
- Safety-critical design: zero auto-send, mandatory human review for high-risk emails, 100% safety test coverage
- Evaluation framework with golden-set benchmarking

---

## User Preferences

- **Respond in Chinese** in chat, but keep code, comments, commit messages, and docs in English.
- **Show me the plan before destructive operations** (deleting files, large refactors, force-push).
- **Prefer editing existing files** over creating new ones unless structurally necessary.
- This project is targeted at **US tech company resumes** — prefer choices that are well-recognized in the US ecosystem (e.g., Llama over Qwen, even if Qwen is technically strong for Chinese).