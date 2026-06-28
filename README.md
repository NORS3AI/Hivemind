# Hivemind

A system of five entirely different but stupid-smart AI advisors you can
question to get complete answers from.

Ask the Hivemind anything and a council of five distinct personas each weighs in
from its own lens. A Chair then surfaces where they agree and disagree and
delivers **one** final, practical answer with clear next steps.

## The council

| Advisor | Lens |
| --- | --- |
| **Strategist** | long-term goals and smart direction |
| **Skeptic** | risks, weak assumptions, blind spots |
| **Creative** | fresh ideas and better angles |
| **Operator** | practical steps and execution |
| **Audience Advocate** | what the user / customer / viewer needs |

Each advisor is a separate Claude call run in parallel; the Chair is a final
synthesis pass that streams its answer back token by token.

## How it works

```
                ┌─ Strategist ─┐
   question ──▶ ├─ Skeptic ────┤ ──▶ Chair (synthesis) ──▶ final answer
   (fan-out)    ├─ Creative ───┤      • agreements
                ├─ Operator ───┤      • disagreements
                └─ Audience ───┘      • next steps
```

- **Backend** — FastAPI (`backend/`). `POST /api/council` streams the whole run
  as Server-Sent Events: each advisor's view as it lands, then the Chair's
  answer streamed live.
- **Frontend** — a dependency-free single page (`frontend/`) that renders the
  five advisor cards and the final verdict.
- **Model** — defaults to `claude-opus-4-8`; advisors answer directly, the Chair
  uses adaptive thinking at high effort. Override with `HIVEMIND_MODEL`.

## Run it inside Claude (plugin)

Prefer no app and no API key? Install the Hivemind as a **Claude Code plugin** and
run the council directly inside any Claude session:

```bash
/plugin marketplace add nors3ai/hivemind
/plugin install hivemind@nors3ai
```

Then ask the council:

```bash
/council Should we launch on Friday or wait a week?
```

Claude itself plays all five advisors and the Chair — Strategist, Skeptic, Creative,
Operator, and Audience Advocate weigh in, then you get one final answer with next
steps. The bundled `council` skill also lets Claude convene the council on its own
when you ask for "multiple perspectives" or to "ask the hivemind" about a decision.

## Run it as a web app

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env      # then add your ANTHROPIC_API_KEY
./run.sh                  # serves on http://127.0.0.1:8000
```

Or run it directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn backend.main:app --reload
```

Open <http://127.0.0.1:8000>, type a question, and convene the council.
(`⌘/Ctrl + Enter` submits.)
