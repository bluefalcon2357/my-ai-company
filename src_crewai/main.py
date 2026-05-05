"""CrewAI entry point. Parallel to src/main.py for side-by-side comparison.

Usage:
    python -m src_crewai.main "Plan the launch of our v1 product"   # CLI arg
    GOAL="..." python -m src_crewai.main                            # env var
    python -m src_crewai.main                                       # interactive REPL
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .crew import build_crew


def main() -> None:
    load_dotenv()

    goal_arg = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ""
    goal_env = os.environ.get("GOAL", "").strip()
    goal = goal_arg or goal_env

    crew = build_crew()

    if goal:
        print(crew.kickoff(inputs={"goal": goal}))
        return

    if not sys.stdin.isatty():
        print("[error] no goal provided. Set GOAL env var or pass as argv.", file=sys.stderr)
        sys.exit(1)

    print("Acme AI Co. (CrewAI) — type a goal, or 'quit' to exit.")
    while True:
        try:
            goal = input("\nowner> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if goal.lower() in ("quit", "exit"):
            return
        if not goal:
            continue
        print("\n" + str(crew.kickoff(inputs={"goal": goal})))


if __name__ == "__main__":
    main()
