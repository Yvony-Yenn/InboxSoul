# Project InboxSoul 3.0

A stateful multi-agent email triage system with feedback-driven self-improvement.

> **Design philosophy**: *Triage over Summarization*. Reject single-prompt shallow summaries; build a high-reliability, safety-first automation hub.

## Highlights

- **Multi-agent system with LLM/rule-engine separation** — only 2 of 4 agents call the LLM, cutting token cost ~50%.
- **Provider-agnostic LLM layer** — local Ollama by default, with optional Claude/OpenAI fallback for complex meta-tasks.
- **Hermes self-improvement engine** — three-stage feedback loop: few-shot retrieval → periodic prompt rewriting → LoRA fine-tuning.
- **Safety-critical design** — zero auto-send, mandatory human review for high-risk emails, 100% test coverage on safety rules.

## Architecture

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

## Quick Start

```bash
# 1. Install local LLM
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama serve  # or: brew services start ollama

# 2. Install dependencies
uv sync

# 3. Copy environment template
cp .env.example .env

# 4. Run the pipeline against sample emails
uv run python -m src.pipeline.orchestrator --source tests/fixtures/sample_emails

# 5. Launch the human review UI
uv run streamlit run src/ui/streamlit_app.py
```

## Project Structure

See `CLAUDE.md` for the full architecture, conventions, and development roadmap.

## License

MIT