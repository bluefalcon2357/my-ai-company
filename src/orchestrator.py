"""CEO orchestrator.

The CEO is a Claude tool-use loop. Each department is exposed as a tool;
calling that tool runs the department agent and feeds its result back to
the CEO. Memory and human approval are also tools, so the model itself
decides when to use them.
"""

from __future__ import annotations

import os
from pathlib import Path

import anthropic

from .approvals import Approver, default_approver
from .department import Department
from .memory import Memory

AGENTS_DIR = Path(__file__).resolve().parent.parent / "company" / "agents"
CHARTER = (Path(__file__).resolve().parent.parent / "company" / "charter.md").read_text()

DEPARTMENTS = ["engineering", "marketing", "sales", "finance", "support"]


def _delegate_tool(name: str) -> dict:
    return {
        "name": f"delegate_to_{name}",
        "description": f"Delegate a task to the head of {name}. "
        f"Provide a clear brief: goal, constraints, deliverable, deadline.",
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string", "description": "What you want them to produce."}},
            "required": ["brief"],
        },
    }


TOOLS: list[dict] = [_delegate_tool(d) for d in DEPARTMENTS] + [
    {
        "name": "read_memory",
        "description": "Read a value from shared company memory by key. Returns null if missing.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "write_memory",
        "description": "Write a key/value into shared company memory for future turns.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"],
        },
    },
    {
        "name": "request_human_approval",
        "description": "Ask the human owner to approve an irreversible action before it happens. "
        "Returns 'approved' or 'denied'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "One-line description of the action."},
                "context": {"type": "string", "description": "Why and what's at stake."},
            },
            "required": ["action"],
        },
    },
]


class CEO:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        memory: Memory | None = None,
        approver: Approver | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.memory = memory or Memory()
        self.approver = approver or default_approver()
        self.model = model or os.environ.get("CEO_MODEL", "claude-opus-4-7")
        self.departments = {
            name: Department(name, self.client, self.memory) for name in DEPARTMENTS
        }
        self.system_prompt = (
            (AGENTS_DIR / "ceo.md").read_text()
            + "\n\n# Company Charter\n\n"
            + CHARTER
        )

    def run(self, goal: str, max_turns: int = 12) -> str:
        self.memory.log("human", "goal", goal)
        messages: list[dict] = [{"role": "user", "content": goal}]

        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return _final_text(response)

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._run_tool(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )

            if not tool_results:
                return _final_text(response)

            messages.append({"role": "user", "content": tool_results})

        return "[CEO] Hit max turns without producing a final answer."

    def _run_tool(self, name: str, payload: dict) -> str:
        if name.startswith("delegate_to_"):
            dept = name.removeprefix("delegate_to_")
            result = self.departments[dept].handle(payload["brief"])
            blocks = [f"[{dept}] {result.text}"]
            for req in result.approval_requests:
                approved = self.approver.ask(req, context=f"requested by {dept}")
                self.memory.log(dept, "approval", f"{req} -> {'APPROVED' if approved else 'DENIED'}")
                blocks.append(f"\n[approval:{dept}] {req} -> {'APPROVED' if approved else 'DENIED'}")
            return "\n".join(blocks)

        if name == "read_memory":
            value = self.memory.read(payload["key"])
            return value if value is not None else "null"

        if name == "write_memory":
            self.memory.write(payload["key"], payload["value"])
            return "ok"

        if name == "request_human_approval":
            approved = self.approver.ask(payload["action"], payload.get("context", ""))
            self.memory.log("ceo", "approval", f"{payload['action']} -> {'APPROVED' if approved else 'DENIED'}")
            return "approved" if approved else "denied"

        return f"[error] unknown tool {name}"


def _final_text(response: anthropic.types.Message) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()
