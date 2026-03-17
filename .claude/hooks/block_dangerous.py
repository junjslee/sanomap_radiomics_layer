#!/usr/bin/env python3
import json
import re
import sys


PATTERNS = [
    (re.compile(r"\brm\s+-rf\b"), "Blocked destructive recursive delete."),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "Blocked hard reset."),
    (re.compile(r"\bgit\s+clean\s+-f[d|x]*\b"), "Blocked forced git clean."),
    (re.compile(r"\bgit\s+checkout\s+--\b"), "Blocked checkout overwrite."),
    (re.compile(r"\bgit\s+push\s+--force(?:-with-lease)?\b"), "Blocked force push."),
    (re.compile(r"\bfind\b.*\s-delete\b"), "Blocked find -delete."),
    (re.compile(r"\bsudo\b"), "Blocked sudo."),
]


def _extract_command(payload: dict) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        return (
            tool_input.get("command")
            or tool_input.get("cmd")
            or tool_input.get("bash_command")
            or ""
        )
    return ""


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    command = _extract_command(payload)
    for pattern, message in PATTERNS:
        if pattern.search(command):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": (
                                f"{message} Use a safer non-destructive alternative."
                            ),
                        }
                    }
                )
            )
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
