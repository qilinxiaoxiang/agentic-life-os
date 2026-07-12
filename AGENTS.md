# Agent contract

Agentic Life OS is a local ledger and control surface. It does not contain an
AI model. Agents interact through the versioned HTTP API or the `lifeos` CLI.

## Required behavior

- Read `GET /api/v1/context/today` before proposing a daily plan.
- Tasks and the daily focus are reversible and may be written directly when
  they match the user's request.
- Money and time are durable ledgers. Always preview a batch, show the
  normalized proposal to the user, and wait for explicit confirmation before
  committing its `proposal_id`.
- Never guess an account, budget item, amount, duration, or category. Leave an
  item unbudgeted or ask for clarification.
- Supply stable `external_id` values. Retrying the same operation must not
  create a duplicate.
- A transfer moves balances but is not income or spending.
- Physical time counts once. Extra allocation credit must use
  `counts_toward_clock: false` and share an `overlap_group` with a clock-counted
  entry in the same proposal.

## Repository boundaries

- Keep the product limited to Today, Time, and Money.
- Do not add model credentials, bank integrations, calendars, journals,
  reports, habits, health tracking, investments, or marketplace workflows to
  the core application.
- Demo and test data must be synthetic. Never commit a runtime database,
  personal path, email address, API key, or real financial record.
- Run `pytest`, `ruff check .`, and `python scripts/privacy_check.py` before a
  public push.
