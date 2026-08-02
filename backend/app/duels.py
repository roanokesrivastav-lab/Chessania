"""V2-S10: Position Duels — one POST to Lichess /api/challenge/open per duel.

The actual game lives entirely on Lichess. We store the returned share-links
(url, urlWhite, urlBlack) in a Duel row so the frontend can render copy-able
links. No realtime/websocket code on our side (A10/D4).
"""

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Duel

logger = logging.getLogger(__name__)

LICHESS_OPEN_CHALLENGE_URL = "https://lichess.org/api/challenge/open"

# ── Public helpers ────────────────────────────────────────────────────


def create_lichess_open_challenge(
    *,
    fen: str,
    clock_limit_s: int | None = None,
    clock_increment_s: int | None = None,
    days: int | None = None,
    name: str | None = None,
) -> dict:
    """POST to Lichess /api/challenge/open and return the parsed JSON response.

    Parameters (all optional except fen):
      - fen: the starting position (variant=fromPosition — MUST be a legal FEN)
      - clock_limit_s / clock_increment_s: realtime clock (defaults from config)
      - days: correspondence (mutually exclusive with clock_* — wins if both
        are set per Lichess convention; we prefer days when set)
      - name: optional display name for the challenge

    Returns the parsed JSON dict containing {id, url, urlWhite, urlBlack, ...}.

    Raises HTTPException(400) on an invalid FEN.
    Raises HTTPException(502) on a Lichess API failure.
    """
    import chess

    # Validate the FEN BEFORE calling Lichess (Hard Rule).
    try:
        chess.Board(fen)
    except (ValueError, Exception):
        raise HTTPException(
            status_code=400,
            detail="That position doesn't look valid — check the FEN and try again.",
        )

    # Build the form payload per the Lichess API spec.
    payload: dict = {
        "variant": "fromPosition",
        "fen": fen,
        "rated": "false",  # from-position + anonymous play requires unrated
    }

    if name is not None:
        payload["name"] = name

    if days is not None and days > 0:
        payload["days"] = str(days)
    else:
        limit = clock_limit_s if clock_limit_s is not None else settings.DUEL_CLOCK_LIMIT_S
        increment = clock_increment_s if clock_increment_s is not None else settings.DUEL_CLOCK_INCREMENT_S
        payload["clock.limit"] = str(limit)
        payload["clock.increment"] = str(increment)

    # Post to Lichess. No OAuth token is sent — open challenges need none
    # (Hard Rule, confirmed against the live API contract).
    try:
        resp = httpx.post(
            LICHESS_OPEN_CHALLENGE_URL,
            data=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception(
            "Lichess challenge creation failed (HTTP %s): %s",
            exc.response.status_code,
            exc.response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail="Lichess couldn't create the challenge — please try again.",
        )
    except Exception:
        logger.exception("Lichess challenge creation failed (network)")
        raise HTTPException(
            status_code=502,
            detail="Couldn't reach Lichess — please try again in a minute.",
        )

    return resp.json()


def store_duel(
    session: Session,
    *,
    fen: str,
    source: str,
    lichess_response: dict,
    creator_user_id: str | None,
) -> Duel:
    """Persist a Duel row with the Lichess response stored as JSON."""
    duel = Duel(
        fen=fen,
        source=source,
        lichess_urls_json=lichess_response,
        creator_user_id=creator_user_id,
    )
    session.add(duel)
    session.commit()
    return duel
