"""FastAPI app for the Hivemind: serves the web UI and the council SSE stream."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .council import run_council

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Hivemind")


class Question(BaseModel):
    question: str


@app.post("/api/council")
async def council(payload: Question):
    """Stream the council's deliberation as Server-Sent Events."""
    return StreamingResponse(
        run_council(payload.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering for SSE
        },
    )


# Serve the single-page frontend at the root. Mounted last so /api/* wins.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
