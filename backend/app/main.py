"""Chessania backend — FastAPI application entrypoint.

Session 1 scope (roadmap Part C): the tightest possible feedback loop —
a single health endpoint the founder can hit with curl to prove the
server runs and reloads on save. Routes, CORS, ingestion, analysis, and
the coach are added in later sessions (S3+). Nothing here yet touches
the database or Stockfish.
"""

from fastapi import FastAPI

app = FastAPI(title="Chessania API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Returns 200 with a tiny JSON body.

    Verify with:  curl localhost:8000/health
    Edit the message, save, and re-curl — the --reload watcher restarts
    the server automatically, so the change shows without a manual restart.
    """
    return {"status": "ok"}
