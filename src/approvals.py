"""Human-in-the-loop approval gate.

Any action a department flags with `REQUIRES_APPROVAL:` runs through here
before the CEO returns a final answer. Default policy is to ask the human
synchronously on the terminal; replace with a Slack/web/etc. backend by
implementing the same `Approver` interface.
"""

from __future__ import annotations

import os
import sys
from typing import Protocol


class Approver(Protocol):
    def ask(self, action: str, context: str) -> bool: ...


class CLIApprover:
    """Synchronous terminal prompt. Good for local dev.

    Auto-denies in non-TTY contexts (Cloud Run Jobs, CI) to avoid hanging
    on input(). Replace with a Slack/web approver for production.
    """

    def ask(self, action: str, context: str) -> bool:
        if not sys.stdin.isatty():
            print(f"[approval auto-denied: no TTY] {action}", file=sys.stderr)
            return False
        print("\n" + "=" * 60)
        print("APPROVAL NEEDED")
        print("=" * 60)
        print(f"Action: {action}")
        if context:
            print(f"Context: {context}")
        print("=" * 60)
        answer = input("Approve? [y/N]: ").strip().lower()
        return answer in ("y", "yes")


class AlwaysApprover:
    """No-op approver — only for tests."""

    def ask(self, action: str, context: str) -> bool:  # noqa: ARG002
        return True


def default_approver() -> Approver:
    if os.environ.get("REQUIRE_APPROVAL", "true").lower() in ("0", "false", "no"):
        return AlwaysApprover()
    return CLIApprover()
