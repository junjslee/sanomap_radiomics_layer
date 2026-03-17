#!/usr/bin/env python3
import json
import sys


def main() -> int:
    _ = sys.stdin.read()
    print(
        json.dumps(
            {
                "systemMessage": (
                    "Before ending unfinished work, update docs/PROGRESS.md and "
                    "docs/NEXT_STEPS.md if priorities, blockers, validated outputs, "
                    "worktree ownership, or next actions changed."
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
