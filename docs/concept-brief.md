# Agent-Mediated Software

## The claim

**The user stops operating software. The user states intent; an agent operates
the software.**

Agent-Mediated Software is a design pattern in which:

- natural language is the normal human input layer;
- an agent converts intent into typed, inspectable operations;
- deterministic application code remains the state, validation, and policy
  layer;
- the visual interface is primarily for observation and confirmation; and
- the agent periodically audits the model and proposes adaptations.

The short version is **No forms, only intent**. This does not mean “no UI.” It
means the UI no longer asks the person to translate life into the application's
schema. The agent does that translation, while the human retains authority over
durable or risky changes.

## Is it new?

The ingredients are not new. The stricter combination is the useful part.

| Related idea | What it contributes | Where this pattern is narrower |
| --- | --- | --- |
| Natural-language interfaces | Flexible expression and conversational clarification | Language is not an extra search box; it is the normal mutation path. |
| No UI | Remove avoidable screen interaction | A read/review UI remains valuable for legibility and consent. |
| Software 3.0 | Natural language becomes a programming surface | The focus here is end-user operation, not how developers create software. |
| Agent-native applications | Agents share real actions and state with the product | Agent-Mediated Software assigns normal writes to the agent and reserves the UI for observation/confirmation. |
| Self-adaptive systems | Monitor, analyze, plan, and execute against shared knowledge | Adaptation changes a person's model only after human review. |

The phrase “agent-mediated” also has prior use in electronic commerce and, more
recently, software consumption. So the responsible launch language is: **“I’m
using Agent-Mediated Software for this stricter design pattern,”** not “I
invented agent mediation or natural-language software.” The contribution is the
boundary—agent-only normal writes, structured state, observe/confirm UI, and
human-governed self-adaptation—not exclusive ownership of the words.

## Why it fits a personal operating system

Forms are fast and deterministic when the schema is stable. Personal life is
not. A sentence such as “the train was late, but I used the ride to study” may
need one physical Time entry, a second overlapping allocation, an updated
Today plan, and no new form fields. An agent can clarify and normalize that
intent against an explicit contract.

The trade is deliberate:

- **Gain:** tolerance for incomplete language, corrections through
  conversation, and a model that can evolve with the person.
- **Cost:** more latency, probabilistic interpretation, and dependence on a
  capable agent.
- **Control:** typed APIs, validation, previews, idempotency, confirmation
  gates, and a readable source of truth.

The agent is flexible at the edge. The ledger stays strict at the center.

## Self-adaptation without silent autonomy

The system treats budgets as hypotheses. It monitors completed periods,
analyzes recurring mismatches, proposes a revised model, waits for human
confirmation, and then executes the accepted change. This resembles the
Monitor–Analyze–Plan–Execute over Knowledge loop from self-adaptive systems,
with explicit human authority inserted before execution.

Examples:

- recurring unbudgeted activity suggests a missing Time or Money category;
- repeated overshoot may mean the budget is unrealistic, classification is
  wrong, or behavior should change;
- repeated non-use may mean an item should shrink, merge, disappear, or remain
  protected intentionally.

The goal is not to make every bar green. It is to make the model more truthful
and useful.

## Sources and lineage

- [Agent-Native: agent and UI as equal partners](https://www.agent-native.com/docs/what-is-agent-native)
- [Agent-mediated electronic commerce survey (1998)](https://doi.org/10.1017/S0269888998002082)
- [CLI-Anything: machine-readable interfaces for agent control](https://arxiv.org/abs/2606.03854)
- [The Best Interface Is No Interface, sample chapter](https://ptgmedia.pearsoncmg.com/images/9780133890334/samplepages/9780133890334.pdf)
- [Natural Language Interfaces for Tabular Data: A Survey](https://arxiv.org/abs/2212.13074)
- [Microsoft Research on the limits of unrestricted natural-language interfaces](https://www.microsoft.com/en-us/research/publication/do-we-need-natural-language-exploring-restricted-language-interfaces-for-complex-domains/)
- [MAPE-K applied to LLM-based multi-agent systems](https://arxiv.org/abs/2307.06187)
