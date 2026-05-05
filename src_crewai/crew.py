"""CrewAI port of the AI company.

Same topology as the hand-built scaffold (src/orchestrator.py): a CEO
manager agent delegates to five department heads. The role prompts are
loaded from `company/agents/*.md`, identical to the hand-built version,
so the two implementations can be compared on the same inputs.

Phase 1 scope: orchestration only. Memory, approval gates, and real
tools come in subsequent phases — see the CrewAI section of README.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task

AGENTS_DIR = Path(__file__).resolve().parent.parent / "company" / "agents"

DEPARTMENTS: dict[str, str] = {
    "engineering": "Head of Engineering",
    "marketing": "Head of Marketing",
    "sales": "Head of Sales",
    "finance": "Head of Finance",
    "support": "Head of Customer Support",
}


def _load_role_prompt(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text()


def build_crew(verbose: bool = True) -> Crew:
    """Construct the CEO + departments crew. Reads model IDs from env."""
    ceo_llm = LLM(model=f"anthropic/{os.environ.get('CEO_MODEL', 'claude-opus-4-7')}")
    dept_llm = LLM(model=f"anthropic/{os.environ.get('DEPT_MODEL', 'claude-sonnet-4-6')}")

    ceo = Agent(
        role="CEO",
        goal=(
            "Take goals from the human owner and orchestrate the company to "
            "deliver them. Decompose, delegate to the right department(s), "
            "integrate the results, and present a single coherent answer."
        ),
        backstory=_load_role_prompt("ceo"),
        llm=ceo_llm,
        allow_delegation=True,
        verbose=verbose,
    )

    departments = [
        Agent(
            role=role,
            goal=f"Deliver {name} work to the standard set in the role brief.",
            backstory=_load_role_prompt(name),
            llm=dept_llm,
            allow_delegation=False,
            verbose=verbose,
        )
        for name, role in DEPARTMENTS.items()
    ]

    task = Task(
        description="{goal}",
        expected_output=(
            "A coherent answer for the human owner. Show: (1) what you "
            "delegated and to whom, (2) the substance each department "
            "returned, (3) your synthesis and recommended next step."
        ),
        agent=ceo,
    )

    return Crew(
        agents=departments,
        tasks=[task],
        process=Process.hierarchical,
        manager_agent=ceo,
        verbose=verbose,
    )
