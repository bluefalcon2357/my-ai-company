"""Entry point. Run a goal through the CEO.

Usage:
    python -m src.main "Plan the launch of our v1 product"
    python -m src.main          # interactive REPL
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from .orchestrator import CEO


def main() -> None:
    load_dotenv()
    ceo = CEO()

    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
        print(ceo.run(goal))
        return

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
