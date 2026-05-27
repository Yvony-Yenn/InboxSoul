"""Load markdown skill prompts from the project's skills/ directory."""

from __future__ import annotations

from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def load_skill(name: str) -> str:
    return (_SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8")
