# Acme AI Co.

A starter scaffold for running a small "company" of AI agents under human
oversight. A CEO agent orchestrates department heads (engineering,
marketing, sales, finance, support) using the Claude API.

```
                 ┌────────────────────────┐
   human owner ──▶│  CEO (Opus)            │
                 │   tool-use loop        │
                 └─┬──┬──┬──┬──┬──────────┘
                   │  │  │  │  │
       ┌───────────┘  │  │  │  └─────────────┐
       ▼              ▼  ▼  ▼                ▼
  Engineering    Marketing  Sales        Finance     Support
  (Sonnet)       (Sonnet)   (Sonnet)     (Sonnet)    (Sonnet)
       │              │     │                │           │
       └──────────────┴─────┴────────┬───────┴───────────┘
                                     ▼
                            shared SQLite memory
                            human approval gate
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then set ANTHROPIC_API_KEY
python -m src.main "Draft a launch plan for our v1 developer product"
```

Or interactive:

```bash
python -m src.main
owner> What should we ship next quarter?
```

## Layout

```
company/
  charter.md            mission, principles, departments
  agents/
    ceo.md              role prompt for the orchestrator
    engineering.md
    marketing.md
    sales.md
    finance.md
    support.md
src/
  orchestrator.py       CEO tool-use loop, exposes departments as tools
  department.py         single-agent loop for a department head
  memory.py             SQLite kv + append-only log shared across agents
  approvals.py          human-in-the-loop gate (CLI by default)
  main.py               entry point
```

## How it works

1. `main.py` loads env vars and constructs a `CEO`.
2. `CEO.run(goal)` enters an Anthropic tool-use loop. The CEO sees one tool
   per department (`delegate_to_engineering`, etc.) plus `read_memory`,
   `write_memory`, and `request_human_approval`.
3. When the CEO calls `delegate_to_<dept>`, the matching `Department`
   makes its own Claude call with a role-specific system prompt. The
   department's reply goes back to the CEO as a tool result.
4. Any line a department emits matching `REQUIRES_APPROVAL: ...` triggers
   the human gate. By default that prompts on stdin; swap in your own
   `Approver` to route through Slack, a web UI, etc.
5. Decisions and reports are written to `company.db` so future turns have
   shared context.

## Extending

- **Add a department**: create `company/agents/<name>.md`, add the name to
  `DEPARTMENTS` in `src/orchestrator.py`. Done.
- **Custom approver**: implement the `Approver` protocol in
  `src/approvals.py` (a class with `ask(action, context) -> bool`) and pass
  it to `CEO(approver=...)`.
- **Sub-agents within a department**: the simplest pattern is to give a
  department its own `Department` instances and make `Department.handle`
  itself a tool-use loop. Pull from `src/orchestrator.py`.
- **Tools per department**: extend `Department.handle` to pass `tools=` to
  `messages.create` — for example, give engineering a `run_tests` tool, or
  give sales a CRM lookup tool.
- **Scheduling**: wrap `CEO.run` in a cron / queue worker for daily standups,
  weekly reports, hourly inbox checks.

## Safety defaults

- The human approval gate is **on** by default (`REQUIRE_APPROVAL=true`).
- No agent has live network access beyond the Claude API.
- No real money, email, or production systems are wired up — every
  external action lives behind a `REQUIRES_APPROVAL:` flag for now.

## Costs

Default model assignment: Opus 4.7 for the CEO, Sonnet 4.6 for departments.
Override via `CEO_MODEL` and `DEPT_MODEL` env vars. For high-volume work,
drop departments to `claude-haiku-4-5`.
