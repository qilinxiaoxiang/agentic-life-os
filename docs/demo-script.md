# YouTube launch video: 6–7 minute script

## Working title

**What If Software Had No Input Forms? Building an Agent-Mediated Personal OS**

Thumbnail line: **NO FORMS. ONLY INTENT.**

## Before recording

Start an isolated Compose project with disposable synthetic data, so the
recording reset cannot touch a normal Life OS volume:

```bash
docker compose -p lifeos-video-demo down -v
docker compose -p lifeos-video-demo up --build -d
alias lifeos-demo='docker compose -p lifeos-video-demo exec lifeos lifeos'
```

Open the Portal at `http://127.0.0.1:5050`, this README, and a terminal. Close
personal tabs, silence notifications, hide bookmarks, and increase terminal
text until it is legible at 1080p. Rehearse the two preview commands once after
a reset.

## Script

### 0:00–0:40 — Face to camera

> Most personal software begins with a form. The software decides what fields
> exist, and then we have to translate our lives into those fields.
>
> I think AI gives us a different model. What if a person never had to operate
> the software directly? You describe what happened or what you want, an agent
> translates that intent into structured actions, and the software becomes a
> place to inspect state and approve important changes.
>
> I’m using **Agent-Mediated Software** for a stricter design pattern: no forms,
> only intent. I built a small open-source personal operating system to test it.

Cut to the desktop on the GitHub README. Keep the repository URL visible.

### 0:40–1:30 — Define the idea

> The phrase agent-mediated has appeared before, and natural-language
> interfaces are not new. We already have ideas like No UI, Software 3.0, and
> agent-native applications.
>
> The narrower claim is about the division of labor. The human expresses
> intent and keeps authority. The agent is the normal write path. Deterministic
> software still owns the schema, validation, and durable state. And the visual
> interface becomes an observe-and-confirm surface.
>
> That last part matters. I do not want my financial history to be a pile of
> chat messages. I want a strict ledger. I just do not want to fill out the
> ledger by hand.

Scroll to “Design thesis,” then open the Portal.

### 1:30–2:30 — Today and the absence of forms

> This project has only three modules: Today, Time, and Money. Today holds one
> focus and a ranked list of concrete actions.
>
> Notice what is missing: there is no plus button, task form, or edit-focus
> dialog. If I say, “Make the walkthrough the focus and add a high-priority
> action to verify the demo,” the agent writes that through the typed API.

Run:

```bash
lifeos-demo context
lifeos-demo focus set "Explain Agent-Mediated Software clearly" --brief "Show the idea, the safety boundary, and the working demo."
lifeos-demo task add "Verify the live agent flow" --priority high --minutes 20
```

Refresh Today.

> The agent reads the current state before it writes. Today is reversible, so
> the agent can update it directly. If it misunderstood me, I correct it in the
> same language I used in the first place.

### 2:30–3:35 — Time and Money are budgets

Open Time.

> Time is a 168-hour weekly budget. It separates physical clock time from
> allocation credit. A commute can count once on the clock while also advancing
> a learning budget. That is difficult to express with a generic timer, but it
> is natural to explain to an agent.

Open Money.

> Money is also a budget plus an actual ledger. Amounts use integer minor units,
> transfers are not income or spending, refunds reverse spending, and stable
> external IDs prevent duplicate writes. The current release uses one primary
> currency, while the data model can keep currencies separate.

### 3:35–4:55 — Propose, confirm, commit

Place the terminal and Portal side by side. Run:

```bash
lifeos-demo money preview examples/money-batch.json
lifeos-demo time preview examples/time-batch.json
```

Refresh and show the pending cards without clicking yet.

> Here is the safety boundary. An agent can infer a task and write it because a
> task is easy to reverse. It cannot silently post Money or Time actuals.
>
> It first creates a normalized proposal. I can see the account, category,
> amount, duration, and totals. Until I confirm, balances and actuals have not
> changed. When I approve, the whole batch commits atomically. Retrying the same
> proposal or external ID does not double-count it.

Click one “Confirm & commit,” then show the updated overview.

> The agent is flexible at the edge. The ledger stays strict at the center.

### 4:55–5:55 — The system adapts

Show the adaptive review section in `docs/agent-guide.md`.

> A personal operating system should also learn where its own model is wrong.
> Every week for Time, and every month for Money, the agent can inspect completed
> periods.
>
> If the same unbudgeted category keeps appearing, it proposes a new budget
> item. If something is repeatedly over budget, it asks whether the plan is
> unrealistic, the classification is wrong, or the behavior should change. If
> a budget is consistently unused, it proposes reducing, merging, or retiring
> it.
>
> It does not silently move the goalposts. It shows the evidence and waits for
> confirmation. The goal is not to make every bar green. The goal is to make
> the model more truthful over time.

### 5:55–6:40 — Honest tradeoffs and close

Return to face to camera, or use picture-in-picture over the Portal.

> This interaction model is slower than clicking a form, and language models
> are not perfectly reliable. For high-frequency or safety-critical workflows,
> that can be the wrong trade.
>
> But a personal operating system needs to absorb messy reality, corrections,
> and changing priorities. Here, flexibility can matter more than shaving off a
> few seconds—if the structured core and confirmation boundaries are designed
> correctly.
>
> Agentic Life OS is local-first, model-independent, and open source. You can
> connect any agent that speaks HTTP or can run a CLI. The repository is linked
> below. I would love to know where you think Agent-Mediated Software works—and
> where a form is still better.

## Recording and edit recipe

1. Record the face-to-camera sections on a phone in landscape at eye level,
   using a window or soft light at roughly 45 degrees.
2. Record the desktop separately on macOS with `Shift-Command-5`. Choose the
   microphone under **Options** and enable visible mouse clicks.
3. Use 1920×1080, 30 fps, SDR. Keep key text away from the outer edges so the
   same export remains safe in LinkedIn's player.
4. For a dynamic USB microphone, place it about 10–15 cm away and slightly
   off-axis. If audio is recorded on the phone, transfer the original file and
   align it in the editor instead of routing a fragile live setup.
5. Edit in one 16:9 timeline. Remove pauses, add short section titles, normalize
   voice level, generate captions, and export MP4/H.264 with AAC audio.
6. Upload the same master natively to YouTube and LinkedIn. YouTube recommends
   matching the recorded frame rate; for 1080p SDR at 24–30 fps it lists 8 Mbps
   as the reference video bitrate.

Official references: [Apple screen recording](https://support.apple.com/en-us/102618),
[YouTube encoding guidance](https://support.google.com/youtube/answer/1722171),
and [LinkedIn video requirements](https://www.linkedin.com/help/linkedin/answer/a548372/video-sharing-troubleshooting-guide).
