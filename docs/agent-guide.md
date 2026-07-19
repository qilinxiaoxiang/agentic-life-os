# Agent guide

Agentic Life OS is a state store and control surface, not an autonomous agent.
Use the HTTP API directly or call the JSON-only `lifeos` command. The Portal
has no direct-entry forms: a human expresses intent to the agent, the agent
writes structured state, and the Portal provides observation and confirmation.

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
- `time.consumption.views.categories.ranking` is the default semantic overview;
  `time.consumption.views.items.ranking` is its item-level drill-down. Both use
  the same one-copy physical clock. Use their neutral `pace_status` signals to
  investigate intent versus reality; do not treat protection values as
  consumption categories, performance scores, or reasons to resize silently.
- Do not fill a day to 24 hours or moralize unlogged time.

## Adaptive budget review

A personal operating system should adapt when its model repeatedly disagrees
with reality. Run this review on completed periods only: weekly for Time and
monthly for Money. Use a rolling four-week Time window and a rolling
three-month Money window when enough history exists.

The review is a human-governed adaptation loop:

1. **Monitor** — read budget items, actuals, and unbudgeted entries for each
   completed period.
2. **Analyze** — identify recurring mismatches and check whether they come from
   a missing category, wrong classification, exceptional event, unrealistic
   plan, or a behavior the user wants to change.
3. **Propose** — show the evidence, the proposed change, its effect on the
   total budget, and at least one alternative. Do not write yet.
4. **Confirm** — wait for explicit acceptance of each create, resize, merge, or
   retirement action.
5. **Adjust** — apply only accepted changes through the budget API, then read
   the overview again to verify the result.

Encode step 3 as a reviewable proposal rather than calling a budget mutation
endpoint directly:

```bash
lifeos budget propose examples/time-budget-adjustment.json
lifeos budget list
lifeos budget commit <proposal-id>   # or reject it
```

Every proposal must include a plain evidence summary, a positive count of
completed periods observed, and one alternative. The preview records the
before/after item and total-plan effect. Commit rechecks current state inside
the transaction; if the budget changed after preview, discard the stale
proposal and prepare a new one.

Use these as review signals, not automatic rules:

- **Missing item:** a coherent unbudgeted category appears in at least two
  completed periods. Propose a named item; never hide it inside “miscellaneous.”
- **Repeatedly over:** Money exceeds 110% in two of three months, or Time
  exceeds 110% in three of four weeks. Offer resize, reclassification, or a
  behavior guardrail as distinct explanations.
- **Repeatedly unused:** Money stays below 50% in three consecutive months, or
  Time stays below 50% in four consecutive weeks. Offer reduce, merge, retire,
  or deliberately keep as protected capacity.

For Time, preserve the 168-hour constraint when changing the plan. For Money,
do not manufacture spending to consume a budget and do not interpret
underspending as failure. A changed budget describes a better model of intent;
it is not a retroactive rewrite of actual history.

Suggested review prompt:

> Review the last four completed Time weeks and three completed Money months.
> Find recurring missing, overused, and unused budget items. For each signal,
> show the evidence, likely explanations, proposed change, and impact on the
> total plan. Do not modify any budget until I confirm that specific change.

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
