# Agent guide

Agentic Life OS is a state store and control surface, not an autonomous agent.
Use the HTTP API directly or call the JSON-only `lifeos` command.

## Operating loop

### 1. Observe

Start each session with:

```bash
lifeos context
```

Read the existing focus and tasks before adding anything. Use the current money
and time summaries as constraints, not as a score of the user.

### 2. Propose reversible work

Tasks and the daily focus can be changed directly. Keep task titles concrete,
retain the user's wording in notes, and do not silently delete existing work.

```bash
lifeos task add "Draft the release note" --priority high --minutes 30
lifeos focus set "Publish a trustworthy release" --brief "Verify first, then explain it simply."
```

### 3. Preview durable ledgers

Money and time always use a two-step write. Put normalized entries in a JSON
file and preview it:

```bash
lifeos money preview examples/money-batch.json
lifeos time preview examples/time-batch.json
```

Preview validates all lines and stores a pending proposal. It does not alter
balances or actuals. Show the returned entries, totals, classifications, and
`proposal.id` to the user. If a category, amount, duration, account, or budget
item is unclear, stop and ask; do not use a miscellaneous category as a guess.

### 4. Confirm and commit

Only after the user explicitly accepts the displayed proposal:

```bash
lifeos money commit <proposal-id>
lifeos time commit <proposal-id>
```

A commit is atomic. If one entry is invalid, none are written. Repeating a
committed proposal returns its original result. Stable `external_id` values
also prevent duplicates across different proposals.

## Money rules

- Use decimal strings in requests; the service converts them to integer minor
  units.
- `expense` decreases an asset or increases a liability.
- `income` enters an asset account.
- `refund` reverses spending against the selected account and category.
- `transfer` moves balances between accounts and never affects income or
  spending totals.
- Version 1 has no exchange-rate engine. Keep currencies separate.

## Time rules

- A time line needs one concrete weekly budget item or `unbudgeted: true`.
- Clock-counted minutes may not exceed 1,440 on one date.
- Additional budget allocation uses `counts_toward_clock: false` and must share
  an `overlap_group` with a clock-counted line in the same proposal.
- Do not fill a day to 24 hours or moralize unlogged time.

## Suggested agent prompts

### Morning

> Read the current context. Propose one daily focus and rank the open tasks. Do
> not change money or time. Preserve existing tasks unless I ask to remove one.

### Evening

> Turn my raw notes into a time proposal and a money proposal. Keep uncertainty
> visible, use stable external IDs, and show both previews. Do not commit until
> I explicitly confirm each one.

### Empty installation

> Ask me for my timezone, primary currency, accounts, monthly income and expense
> envelopes, and a realistic 168-hour weekly allocation. Create only confirmed
> rows; leave unknowns empty.
