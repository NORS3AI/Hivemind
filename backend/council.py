"""The Hivemind council: five distinct advisors plus a Chair that synthesizes.

Each advisor is a separate Claude persona that answers the user's question from
its own lens only. The Chair then receives all five views, surfaces where they
agree and disagree, and delivers one final, practical answer with next steps.
"""

import asyncio
import json
import os

from anthropic import AsyncAnthropic

# Default to the most capable model; override with HIVEMIND_MODEL if desired.
MODEL = os.environ.get("HIVEMIND_MODEL", "claude-opus-4-8")

# The five members of the Hivemind. Each one is deliberately narrow — it speaks
# only from its own angle and never tries to give the final answer.
ADVISORS = [
    {
        "key": "strategist",
        "name": "Strategist",
        "tagline": "long-term goals and smart direction",
        "lens": (
            "the long game: where this should end up, the smartest direction to "
            "take, leverage, sequencing, and what compounds over time"
        ),
    },
    {
        "key": "skeptic",
        "name": "Skeptic",
        "tagline": "risks, weak assumptions, blind spots",
        "lens": (
            "what could go wrong: shaky assumptions, hidden risks, blind spots, "
            "and the parts of the plan most likely to break"
        ),
    },
    {
        "key": "creative",
        "name": "Creative",
        "tagline": "fresh ideas and better angles",
        "lens": (
            "fresh ideas and better angles: unconventional approaches, reframes, "
            "and options the obvious answer would miss"
        ),
    },
    {
        "key": "operator",
        "name": "Operator",
        "tagline": "practical steps and execution",
        "lens": (
            "execution: the concrete steps to actually do this, what to do first, "
            "and how to make it real without overcomplicating it"
        ),
    },
    {
        "key": "audience",
        "name": "Audience Advocate",
        "tagline": "what the user / customer / viewer needs",
        "lens": (
            "the audience: what the end user, customer, or viewer actually needs, "
            "feels, and will respond to"
        ),
    },
]

ADVISOR_BY_KEY = {a["key"]: a for a in ADVISORS}


def _advisor_system(advisor: dict) -> str:
    return (
        f"You are the {advisor['name']}, one of five advisors on the Hivemind "
        f"council. Your lens is {advisor['lens']}.\n\n"
        "Give a short, sharp view on the user's request from YOUR perspective "
        "only — 2 to 4 sentences or a few tight bullet points. Be specific and "
        "opinionated; surface the one or two things someone with your lens would "
        "insist on. Do not cover the other advisors' angles, and do not give a "
        "final overall recommendation — that is the Chair's job."
    )


CHAIR_SYSTEM = (
    "You are the Chair of the Hivemind — a council of five advisors "
    "(Strategist, Skeptic, Creative, Operator, and Audience Advocate). You "
    "receive the user's question and each advisor's short view.\n\n"
    "Your job: synthesize them into one answer. First, in a couple of lines, "
    "note where the advisors agree and where they genuinely disagree. Then "
    "deliver ONE final, practical answer with clear, concrete next steps. Be "
    "decisive — pick a direction rather than listing every option. Use short "
    "markdown sections and keep it tight."
)


_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Lazily build the client so a missing API key is a runtime error we can
    report to the user, not an import-time crash."""
    global _client
    if _client is None:
        _client = AsyncAnthropic()
    return _client


def _text_of(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text").strip()


async def _advisor_view(client: AsyncAnthropic, advisor: dict, question: str):
    """Get one advisor's view. Returns (advisor, text)."""
    message = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_advisor_system(advisor),
        messages=[{"role": "user", "content": question}],
    )
    return advisor, _text_of(message)


def _chair_prompt(question: str, views: dict[str, str]) -> str:
    parts = [
        "The user asked the Hivemind council:\n",
        f'"""\n{question}\n"""\n',
        "Here are the five advisors' views:\n",
    ]
    for advisor in ADVISORS:
        view = views.get(advisor["key"], "(no response)")
        parts.append(f"## {advisor['name']} ({advisor['tagline']})\n{view}\n")
    parts.append(
        "Now, as Chair, synthesize these into the council's answer: briefly "
        "highlight the key agreements and disagreements, then give one final "
        "practical answer with clear next steps."
    )
    return "\n".join(parts)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_council(question: str):
    """Async generator yielding Server-Sent Events for the full council run."""
    question = (question or "").strip()
    if not question:
        yield _sse("error", {"message": "Please enter a question for the council."})
        return

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        yield _sse(
            "error",
            {
                "message": (
                    "ANTHROPIC_API_KEY is not set. Add it to your environment "
                    "or a .env file and restart the server."
                )
            },
        )
        return

    try:
        client = get_client()
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": f"Could not initialize the client: {exc}"})
        return

    # Announce all advisors up front so the UI can render their cards.
    for advisor in ADVISORS:
        yield _sse(
            "advisor_start",
            {
                "key": advisor["key"],
                "name": advisor["name"],
                "tagline": advisor["tagline"],
            },
        )

    # Fan out to all five advisors concurrently; stream each as it finishes.
    tasks = [
        asyncio.create_task(_advisor_view(client, advisor, question))
        for advisor in ADVISORS
    ]
    views: dict[str, str] = {}
    try:
        for future in asyncio.as_completed(tasks):
            advisor, text = await future
            views[advisor["key"]] = text
            yield _sse("advisor_done", {"key": advisor["key"], "view": text})
    except Exception as exc:  # noqa: BLE001 - surface any API error to the client
        for task in tasks:
            task.cancel()
        yield _sse("error", {"message": f"An advisor failed: {exc}"})
        return

    # The Chair synthesizes, streamed token by token.
    yield _sse("synthesis_start", {})
    try:
        async with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=CHAIR_SYSTEM,
            messages=[{"role": "user", "content": _chair_prompt(question, views)}],
        ) as stream:
            async for text in stream.text_stream:
                yield _sse("synthesis_delta", {"text": text})
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": f"The Chair failed to synthesize: {exc}"})
        return

    yield _sse("done", {})
