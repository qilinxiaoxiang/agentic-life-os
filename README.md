# Agentic Life OS

**A local-first personal operating system where an AI agent helps you allocate
your two scarcest resources: time and money.**

![Agentic Life OS dashboard](docs/assets/dashboard.jpg)

Most personal productivity tools keep tasks, calendars, and budgets in
separate silos. Agentic Life OS gives an agent one small, explicit operating
surface:

- **Today** — one daily focus and a ranked list of actionable work.
- **Time** — a 168-hour weekly budget, category/item consumption views, and pace comparison.
- **Money** — accounts, monthly plans, and actual transactions.

The app contains no model and stores no AI credentials. Bring Codex, Claude,
OpenClaw, or any other agent that can call a local HTTP API or command-line
tool. Your data stays in a local SQLite database.

## Design thesis: Agent-Mediated Software

Agentic Life OS is an experiment in **Agent-Mediated Software**: the human
expresses intent, an agent translates that intent into structured operations,
and the application remains the deterministic state and policy layer.

**No forms, only intent.** The Portal is deliberately an observe-and-confirm
surface, not a data-entry surface. The agent is the only normal write path.
Humans inspect Today, Time, and Money and explicitly authorize durable ledger
commits. This keeps conversational input flexible without turning the database
into unstructured chat history.

This is a specific design pattern, not a claim that natural-language or
agent-driven interfaces began here. See the [concept brief](docs/concept-brief.md)
for the related ideas and the boundary this project is testing.

## Quick start

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) if
`docker compose` is not already available, then run:

```bash
git clone https://github.com/qilinxiaoxiang/agentic-life-os.git
cd agentic-life-os
docker compose up --build
```

Open [http://127.0.0.1:5050](http://127.0.0.1:5050). The default container
starts with synthetic demo data in USD. To start clean, copy `.env.example` to
`.env` and set `LIFEOS_DEMO=0`. Set `LIFEOS_CURRENCY` to another ISO 4217 code
before the first run if USD is not your primary currency.

### Open it on your phone (optional)

Keep the app bound to localhost and use a private Tailscale network instead of
opening port 5050 to the public internet:

1. Install [Tailscale](https://tailscale.com/download) on the computer running
   Life OS and on your phone. Sign in to the same tailnet on both devices.
2. With Life OS running, share the local service inside that tailnet:

   ```bash
   tailscale serve --bg localhost:5050
   ```

3. Open the private HTTPS URL printed by Tailscale on your phone. Use
   `tailscale serve status` to find it again.

This uses [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve),
which is tailnet-only. Do not use Tailscale Funnel for a personal ledger;
Funnel makes the service public. Life OS has no application-level login, so
the Tailscale access boundary is part of the setup.

If you want an agent to handle the computer-side setup, open the parent folder
in your coding agent and say:

> Clone Agentic Life OS, read AGENTS.md, start the synthetic Docker demo, and
> verify `/health`. Then help me make it reachable from my phone with Tailscale
> Serve. Keep it private to my tailnet and do not enable Funnel.

### Local Python setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
LIFEOS_DB_PATH=./data/lifeos.sqlite LIFEOS_DEMO=1 .venv/bin/python -m agentic_life_os
```

## How AI agents use it

The operating loop is deliberately small:

1. **Observe** — read `/api/v1/context/today` for the current focus, open
   actions, and the live time/money summaries.
2. **Propose** — update reversible tasks directly, but send money and time
   entries to a preview endpoint.
3. **Confirm** — show the normalized preview to the user. Unconfirmed proposals
   do not affect any balance or budget.
4. **Commit** — after explicit approval, commit the proposal atomically.

The same agent can periodically review completed periods and propose changes
to the model itself: add a missing budget category, resize a repeatedly missed
allocation, or retire an unused one. Adaptation is evidence-based and never
silent; budget changes still require explicit human confirmation. The full
policy is in the [agent guide](docs/agent-guide.md#adaptive-budget-review).

### Codex example

From this repository, ask Codex:

> Read AGENTS.md and the current Life OS context. Turn my notes into today's
> focus and actionable tasks. Then prepare, but do not commit, the time and
> money I report. Show me the normalized proposal first.

The CLI gives agents a model-independent interface:

```bash
lifeos context
lifeos task add "Review where the week went" --priority high --minutes 15
lifeos focus set "Plan a balanced week" --brief "Protect deep work, recovery, and visible spending."
lifeos money overview
lifeos money preview examples/money-batch.json
lifeos money commit <proposal-id>
lifeos time overview
lifeos time preview examples/time-batch.json
lifeos time commit <proposal-id>
```

All commands print JSON. The same operations are documented in
[`openapi.yaml`](openapi.yaml) and the [agent guide](docs/agent-guide.md).

### Useful prompts

- **Initialize budgets:** “Create a realistic monthly money plan and a
  168-hour weekly time budget. Ask about unknown amounts instead of guessing.”
- **Plan Today:** “Read today's context, choose one focus, and turn my notes
  into concrete actionables without deleting existing work.”
- **Evening reconciliation:** “Prepare time and money proposals from my raw
  notes. Preserve my wording and wait for confirmation before commit.”
- **Add a currency:** “Change the empty installation's primary currency to EUR.
  Do not convert existing amounts or blend currencies.”

## Data semantics

Money is stored in integer minor units. Expense, income, refund, and transfer
have distinct balance effects; transfers never count as spending or income.
Every agent-written ledger line can carry a stable `external_id`, so retries
are idempotent.

Time maintains two totals. `clock_minutes` answers where physical time went
and may not exceed 24 hours per day. `allocation_minutes` answers which budgets
that time advanced, so deliberate overlap can be larger than clock time.
The weekly overview ranks only clock-counted minutes. Its default category
view answers what the time was for (`Work`, `Learning`, `Wellbeing`), while the
item view exposes the underlying budget rows. Pace signals compare allocation
credit with the portion of the week already elapsed. Protection values such as
`committed` and `flexible` remain policy metadata, not consumption categories.

The schema includes a currency code on financial rows so another currency can
be added without a migration. Version 1 displays each currency separately and
does not provide exchange rates or cross-currency totals.

## Privacy and security

- The server binds to localhost by default and has no public hosting mode.
- No bank, calendar, model, or third-party account is connected.
- Runtime databases and `.env` files are ignored by Git.
- CI runs tests, linting, a repository privacy denylist, and secret scanning.
- The Portal contains no direct data-entry forms. Reversible task/focus writes
  go through the agent API; money and time actuals require preview plus an
  explicit commit.

This is a personal planning ledger, not financial, medical, or legal advice.

## Development

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python scripts/privacy_check.py
```

The project intentionally stops at Today, Time, and Money. Reports, journals,
habits, health metrics, investment analysis, bank sync, and external
automations belong in optional integrations rather than the core.

The repository also includes a [6–7 minute launch video script](docs/demo-script.md)
and a [LinkedIn launch package](docs/linkedin-launch.md) for explaining the
design pattern with the synthetic demo.

## License

MIT
