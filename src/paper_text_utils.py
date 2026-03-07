from __future__ import annotations

from pathlib import Path
from typing import Any


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def paper_text(paper: dict[str, Any]) -> tuple[str, str]:
    title = str(paper.get("title") or "").strip()
    abstract = str(paper.get("abstract") or "").strip()
    full_text_path = str(paper.get("full_text_path") or "").strip()

    if full_text_path:
        full_text = _safe_read_text(Path(full_text_path))
        if full_text:
            return full_text, "pmc_full_text"

    if abstract:
        return f"{title}. {abstract}".strip(), "title_abstract"
    return title, "title"


__all__ = ["paper_text"]
