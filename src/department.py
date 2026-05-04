"""A single department agent.

A department is a Claude call with a role-specific system prompt and access
to the shared memory. It returns a string result back to the CEO. Anything
flagged `REQUIRES_APPROVAL:` is surfaced as a structured field so the CEO
(and the human approver) can act on it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .memory import Memory

AGENTS_DIR = Path(__file__).resolve().parent.parent / "company" / "agents"
APPROVAL_RE = re.compile(r"^REQUIRES_APPROVAL:\s*(.+)$", re.MULTILINE)


@dataclass
class DepartmentResult:
    text: str
    approval_requests: list[str]


class Department:
    def __init__(
        self,
        name: str,
        client: anthropic.Anthropic,
        memory: Memory,
        model: str | None = None,
    ) -> None:
        self.name = name
        self.client = client
        self.memory = memory
        self.model = model or os.environ.get("DEPT_MODEL", "claude-sonnet-4-6")
        self.system_prompt = (AGENTS_DIR / f"{name}.md").read_text()

    def handle(self, brief: str) -> DepartmentResult:
        recent = self.memory.recent_log(limit=10)
        memory_context = "\n".join(
            f"- [{actor}/{kind}] {content[:200]}" for _, actor, kind, content in recent
        ) or "(none)"

        user_message = (
            f"Brief from CEO:\n{brief}\n\n"
            f"Recent company log (most recent last):\n{memory_context}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = "".join(b.text for b in response.content if b.type == "text")
        approvals = [m.group(1).strip() for m in APPROVAL_RE.finditer(text)]

        self.memory.log(self.name, "report", text)
        return DepartmentResult(text=text, approval_requests=approvals)
