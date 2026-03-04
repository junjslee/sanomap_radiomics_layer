from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.types import to_dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: str | Path, records: Iterable[Any]) -> int:
    ensure_parent(path)
    count = 0
    with Path(path).open("w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(to_dict(rec), ensure_ascii=True) + "\n")
            count += 1
    return count


def append_jsonl(path: str | Path, records: Iterable[Any]) -> int:
    ensure_parent(path)
    count = 0
    with Path(path).open("a", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(to_dict(rec), ensure_ascii=True) + "\n")
            count += 1
    return count


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_manifest(
    *,
    manifest_dir: str | Path,
    stage: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
    outputs: dict[str, str],
    command: str,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    target = manifest_dir / f"{stage}_{timestamp}.json"
    payload = {
        "stage": stage,
        "timestamp": utc_now_iso(),
        "params": params,
        "metrics": metrics,
        "outputs": outputs,
        "command": command,
    }
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
    return target


__all__ = [
    "utc_now_iso",
    "ensure_parent",
    "write_jsonl",
    "append_jsonl",
    "read_jsonl",
    "write_manifest",
]
