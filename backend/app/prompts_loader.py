from functools import lru_cache
from pathlib import Path

from .config import get_settings

BASE_PROMPTS = ["01-system.md", "10-guardrails.md"]


@lru_cache
def _read(name: str) -> str:
    path: Path = get_settings().prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def build_system_prompt(*agent_files: str) -> str:
    parts = [_read(name) for name in BASE_PROMPTS]
    parts.extend(_read(name) for name in agent_files)
    return "\n\n---\n\n".join(parts)
