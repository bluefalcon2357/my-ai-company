"""Entry point. Run a goal through the CEO.

Usage:
    python -m src.main "Plan the launch of our v1 product"   # CLI arg
    GOAL="..." python -m src.main                            # env var (Cloud Run Jobs)
    python -m src.main                                       # interactive REPL
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .orchestrator import CEO


def main() -> None:
    load_dotenv()
    ceo = CEO()

    goal_arg = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ""
    goal_env = os.environ.get("GOAL", "").strip()
    goal = goal_arg or goal_env

    if goal:
        print(ceo.run(goal))
        return

    if not sys.stdin.isatty():
        # Non-interactive (e.g. Cloud Run Job) with no goal set — fail loudly.
        print("[error] no goal provided. Set GOAL env var or pass as argv.", file=sys.stderr)
        sys.exit(1)

    print("Acme AI Co. — type a goal, or 'quit' to exit.")
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
        print("\n" + ceo.run(goal))


if __name__ == "__main__":
    main()
