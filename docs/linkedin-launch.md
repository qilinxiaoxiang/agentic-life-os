# LinkedIn launch package

## Posting format

Upload the finished MP4 natively from desktop instead of posting only a YouTube
link. Use the same 1920×1080 landscape master, add captions, select a custom
thumbnail, and include the YouTube and GitHub links in the post text. LinkedIn
currently accepts desktop videos up to 15 minutes, so the 6–7 minute master
fits without a separate cut.

## Post copy

Most software asks us to translate our lives into forms.

I wanted to test the opposite model: the human expresses intent, an AI agent
translates it into structured operations, and the application becomes a place
to inspect state and approve durable changes.

I’m using **Agent-Mediated Software** for a stricter design pattern. The phrase
has prior history; the boundary I want to test is the contribution.

The principle is simple: **no forms, only intent.**

I built an open-source personal OS around that idea. It has only three modules:
Today, a 168-hour Time budget, and a Money budget plus ledger. Reversible Today
changes can move immediately. Time and Money follow an
Observe → Propose → Confirm → Commit boundary, so the agent cannot silently
change the durable ledgers.

The more interesting part is adaptation. The agent can review completed weeks
and months, detect missing or consistently mismatched budget items, and propose
a better model—while the human remains the authority.

This approach is slower and less deterministic than a form. But for a personal
operating system, flexibility and conversational correction may be worth that
trade.

Video: [add YouTube URL after upload]

Code: https://github.com/qilinxiaoxiang/agentic-life-os

Where would you trust Agent-Mediated Software, and where would you still want a
form?

#AgenticAI #OpenSource #PersonalProductivity

## First comment

The repository includes the REST API, JSON CLI, OpenAPI contract, privacy
checks, synthetic demo data, and the Agent Guide that defines confirmation and
self-adaptation boundaries. It runs locally with one Docker Compose command.

## Upload checklist

- Replace the YouTube placeholder with the public URL.
- Upload the MP4 directly and wait for processing before publishing.
- Add English captions and the “NO FORMS. ONLY INTENT.” thumbnail.
- Confirm the first frame, subtitles, and terminal text are legible on mobile.
- Check that the repository and video links open in a signed-out browser.
