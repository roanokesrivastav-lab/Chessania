"""Chessania backend — FastAPI application entrypoint."""

import dataclasses
import re
import secrets
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.features import load_features
from app.jobs import get_job, get_or_create_job, run_job
from app.models import Report as ReportModel

# In-memory rate limiter (correct for the single Railway instance v1; scaling
# horizontally would move this to shared storage — Part G #9).
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Chessania API", version="0.1.0")
app.state.limiter = limiter

# CORS is intentionally driven by the CORS_ORIGINS env/config. S24/S25 sets this
# to the Vercel domain; dev uses the default http://localhost:3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "You've queued a few already — reports keep, come back soon."},
    )

_USERNAME_PATTERNS = {
    "chesscom": r"[a-zA-Z0-9_-]{3,25}",
    "lichess": r"[a-zA-Z0-9_-]{2,30}",
}


def _platform_label(platform: str) -> str:
    return "Chess.com" if platform == "chesscom" else "Lichess"


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Returns 200 with a tiny JSON body.

    Verify with:  curl localhost:8000/health
    Edit the message, save, and re-curl — the --reload watcher restarts
    the server automatically, so the change shows without a manual restart.
    """
    return {"status": "ok"}


class AnalyzeRequest(BaseModel):
    platform: Literal["chesscom", "lichess"]
    username: str
    # Session 33: "standard" (fast 20-game default) | "deep" (opt-in ~100).
    mode: Literal["standard", "deep"] = "standard"


def _analyze_rate_limit() -> str:
    """Callable limit so the rate can be overridden in tests without reloading the module."""
    return settings.RATE_LIMIT_ANALYZE


def _magic_link_rate_limit() -> str:
    """Callable limit (see _analyze_rate_limit) for the magic-link send endpoint."""
    return settings.RATE_LIMIT_MAGIC_LINK


@app.post("/api/analyze")
@limiter.limit(_analyze_rate_limit)
def analyze(request: Request, payload: AnalyzeRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Kick off (or join) an analysis job for (platform, username) and
    return its job_id immediately. Progress is then polled via
    GET /api/jobs/{job_id} — this route never blocks on the fetch/analyze
    work itself."""
    platform_label = _platform_label(payload.platform)
    if not re.fullmatch(_USERNAME_PATTERNS[payload.platform], payload.username):
        raise HTTPException(
            status_code=400,
            detail=f"That doesn't look like a valid {platform_label} username.",
        )

    job, deduped = get_or_create_job(payload.platform, payload.username, mode=payload.mode)
    if not deduped:
        background_tasks.add_task(run_job, job.job_id)

    return {"job_id": job.job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="That analysis expired or was never started — start a fresh one.",
        )
    return job.to_dict()


@app.get("/api/debug/features/{platform}/{username}")
def debug_features(
    platform: str, username: str, session: Session = Depends(get_session)
) -> dict:
    """Dev-only peek at Session 12's aggregated PlayerFeatures for an already-
    analyzed account — lets the founder eyeball the numbers a coaching report
    will eventually speak in, before there's a report endpoint to read them
    from. Formal prod gating (returning 404 whenever ENV != "dev") lands for
    real in Session 23; until then this plain check keeps the route from
    ever answering in production.

    Session via `Depends(get_session)` (S13) rather than calling
    SessionLocal() directly — same DB session plumbing every other route
    dependency uses, and what lets a test override it with
    `app.dependency_overrides[get_session]` instead of touching the real
    dev database."""
    if settings.ENV != "dev":
        raise HTTPException(status_code=404, detail="Not found.")
    # Debug endpoint is intentionally prod-gated: it only answers when ENV == "dev".
    if platform not in _USERNAME_PATTERNS:
        raise HTTPException(status_code=404, detail="Not found.")

    features = load_features(session, platform, username)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No analyzed games for that account yet — run POST /api/analyze first.",
        )
    return dataclasses.asdict(features)


# ── V2-S2: Auth routes ────────────────────────────────────────────────


class MagicLinkRequest(BaseModel):
    email: str


@app.post("/api/auth/magic-link")
@limiter.limit(_magic_link_rate_limit)
def request_magic_link(
    request: Request,
    payload: MagicLinkRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Send (or log) a magic link for the given email.

    Always returns 200 — the same shape whether or not the email has an
    account, so an attacker can't enumerate users by probing this endpoint.
    Rate-limited (RATE_LIMIT_MAGIC_LINK) so it can't email-bomb a third party."""
    from app.auth import send_magic_link

    email = payload.email.strip().lower()
    send_magic_link(session, email)
    return {"ok": True, "message": "If that email has an account, a sign-in link has been sent."}


@app.get("/api/auth/magic-link/verify")
def verify_magic_link(
    token: str,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Verify a magic-link token. On success: set the session cookie and
    redirect to the frontend. On failure: redirect to the frontend with an
    error query param so the login page can show a message."""
    from app.auth import create_session_cookie, verify_magic_link as _verify

    frontend = settings.FRONTEND_BASE_URL
    try:
        user = _verify(session, token)
    except HTTPException:
        return RedirectResponse(
            url=f"{frontend}/login?error=invalid_link", status_code=302
        )

    response = RedirectResponse(url=f"{frontend}/train", status_code=302)
    create_session_cookie(response, user_id=str(user.id))
    return response


@app.get("/api/auth/lichess/start")
def lichess_start() -> dict[str, str]:
    """Return the Lichess OAuth authorize URL. The code_verifier is stashed
    in a short-lived signed cookie so the callback can recover it."""
    from app.auth import lichess_authorize_url

    state = secrets.token_urlsafe(16)
    url, code_verifier = lichess_authorize_url(state)

    # We need to pass both state and code_verifier through to the callback.
    # A simple approach: sign them into a short-lived cookie.
    from itsdangerous import URLSafeTimedSerializer

    verifier_serializer = URLSafeTimedSerializer(
        secret_key=settings.SECRET_KEY, salt="lichess_oauth"
    )
    verifier_token = verifier_serializer.dumps(
        {"state": state, "code_verifier": code_verifier}
    )

    from fastapi.responses import JSONResponse

    resp = JSONResponse(content={"url": url})
    resp.set_cookie(
        key="chessania_lichess_oauth",
        value=verifier_token,
        max_age=600,  # 10 min to complete the flow
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/auth/lichess",
    )
    return resp


@app.get("/api/auth/lichess/callback")
def lichess_callback(
    code: str,
    state: str,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle the Lichess OAuth callback: verify the state param, exchange
    the code, upsert the user, set the session cookie, redirect home."""
    from itsdangerous import URLSafeTimedSerializer

    from app.auth import create_session_cookie, exchange_lichess_code

    frontend = settings.FRONTEND_BASE_URL

    # Recover the code_verifier from the short-lived cookie.
    verifier_cookie = request.cookies.get("chessania_lichess_oauth")
    if not verifier_cookie:
        return RedirectResponse(
            url=f"{frontend}/login?error=oauth_expired", status_code=302
        )

    verifier_serializer = URLSafeTimedSerializer(
        secret_key=settings.SECRET_KEY, salt="lichess_oauth"
    )
    try:
        verifier_data = verifier_serializer.loads(verifier_cookie, max_age=600)
    except Exception:
        return RedirectResponse(
            url=f"{frontend}/login?error=oauth_expired", status_code=302
        )

    if verifier_data.get("state") != state:
        return RedirectResponse(
            url=f"{frontend}/login?error=oauth_mismatch", status_code=302
        )

    try:
        user = exchange_lichess_code(
            session, code, verifier_data["code_verifier"]
        )
    except HTTPException:
        return RedirectResponse(
            url=f"{frontend}/login?error=oauth_failed", status_code=302
        )

    response = RedirectResponse(url=f"{frontend}/train", status_code=302)
    create_session_cookie(response, user_id=str(user.id))
    # Clear the verifier cookie.
    response.delete_cookie(
        key="chessania_lichess_oauth",
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/auth/lichess",
    )
    return response


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    from app.auth import clear_session_cookie

    clear_session_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request, session: Session = Depends(get_session)) -> dict:
    """Return the signed-in user (or guest=null)."""
    from app.auth import read_session

    user_id = read_session(request)
    if user_id is None:
        return {"user": None}

    from app.models import User

    user = session.get(User, user_id)
    if user is None:
        return {"user": None}

    return {
        "user": {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
            "lichess_id": user.lichess_id,
        }
    }


@app.get("/api/reports/{platform}/{username}")
def get_report(platform: str, username: str, session: Session = Depends(get_session)) -> dict:
    """Return the latest stored report for (platform, username). The report is
    generated by the coaching stage in run_job and persisted as JSON, so this
    route is fast and deterministic."""
    if platform not in _USERNAME_PATTERNS:
        raise HTTPException(status_code=404, detail="Not found.")

    from app.models import Player

    player = session.scalars(
        select(Player).where(Player.platform == platform, Player.username == username.lower())
    ).first()
    if player is None:
        raise HTTPException(
            status_code=404,
            detail="No report yet — run POST /api/analyze first.",
        )

    report = session.scalars(
        select(ReportModel).where(ReportModel.player_id == player.id).order_by(desc(ReportModel.created_at))
    ).first()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report yet — run POST /api/analyze first.",
        )

    return report.report_json


# ── V2-S4: Trainer routes ────────────────────────────────────────────


@app.get("/api/train/positions")
def get_training_positions(
    platform: str,
    username: str,
    category: str = "blunder",
    limit: int = 10,
    game_urls: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return up to `limit` training positions for the given player+category.
    Empty list (not 404) if the player exists but has zero positions — the
    frontend renders the empty-state UI.

    V2-S5: derives opponent_move_san / opponent_move_uci by replaying the
    source game's PGN up to ply-1. null when ply == 1 (no prior move).

    V2-S7: optional game_urls (comma-separated) filters positions to those
    whose source game's URL is in the given list. Matches against
    Game.game_url for the resolved player. No match → empty list (same
    "empty, not 404" contract as the unfiltered path)."""
    import io

    import chess.pgn

    from app.models import Game, Player, TrainingPosition

    player = session.scalars(
        select(Player).where(
            Player.platform == platform, Player.username == username.lower()
        )
    ).first()
    if player is None:
        raise HTTPException(status_code=404, detail="No analyzed games found for that account.")

    # V2-S7: optional game_urls filter — narrow to positions from specific games.
    filtered_game_ids: set | None = None
    if game_urls is not None:
        parsed_urls = [u.strip() for u in game_urls.split(",") if u.strip()]
        if parsed_urls:
            matching_games = session.scalars(
                select(Game.id).where(
                    Game.player_id == player.id,
                    Game.game_url.in_(parsed_urls),
                )
            ).all()
            filtered_game_ids = set(matching_games)
            if not filtered_game_ids:
                # No games matched — short-circuit to empty list.
                return []

    query = select(TrainingPosition).where(
        TrainingPosition.player_id == player.id,
        TrainingPosition.category == category,
    )
    if filtered_game_ids is not None:
        query = query.where(TrainingPosition.source_game_id.in_(filtered_game_ids))
    rows = session.scalars(
        query.order_by(TrainingPosition.ply).limit(limit)
    ).all()

    # Join Game for game_url/played_at + PGN for opponent_move derivation.
    game_ids = {r.source_game_id for r in rows}
    games = {
        str(g.id): g
        for g in session.scalars(
            select(Game).where(Game.id.in_(game_ids))
        ).all()
    }

    # Per-request PGN parse cache so positions from the same game don't re-parse.
    _pgn_cache: dict[str, chess.pgn.GameNode | None] = {}

    def _prior_move(game_id: str, ply: int) -> tuple[str | None, str | None]:
        """Return (san, uci) of the move immediately before `ply`, or (None, None).
        Mirrors analysis.py's replay pattern: san(move) BEFORE push(move)."""
        if ply <= 1:
            return None, None
        game = games.get(game_id)
        if game is None or not game.pgn:
            return None, None
        if game_id not in _pgn_cache:
            try:
                _pgn_cache[game_id] = chess.pgn.read_game(io.StringIO(game.pgn))
            except Exception:
                _pgn_cache[game_id] = None
        parsed = _pgn_cache[game_id]
        if parsed is None:
            return None, None
        board = parsed.board()
        target = ply - 1
        idx = 0
        for move in parsed.mainline_moves():
            idx += 1
            if idx == target:
                try:
                    san = board.san(move)  # BEFORE push (mirrors analysis.py)
                except Exception:
                    san = move.uci()
                return san, move.uci()
            board.push(move)
        return None, None

    return [
        {
            "id": str(r.id),
            "fen": r.fen,
            "best_line_uci": r.best_line_uci,
            "ply": r.ply,
            "eval_before_cp": r.eval_before_cp,
            "game_url": games[str(r.source_game_id)].game_url if str(r.source_game_id) in games else "",
            "played_at": (
                games[str(r.source_game_id)].played_at.isoformat()
                if str(r.source_game_id) in games and games[str(r.source_game_id)].played_at
                else None
            ),
            "opponent_move_san": _prior_move(str(r.source_game_id), r.ply)[0],
            "opponent_move_uci": _prior_move(str(r.source_game_id), r.ply)[1],
        }
        for r in rows
    ]


class SubmitAttemptRequest(BaseModel):
    ref_id: str
    ref_type: str = "position"
    trainer: str
    grade: Literal["perfect", "pass", "fail"]
    seconds: int


@app.post("/api/train/attempts")
def submit_attempt(
    payload: SubmitAttemptRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Record a graded training attempt. 401 for guests."""
    from app.auth import read_session
    from app.models import Attempt, Streak, User

    user_id = read_session(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to save your progress.")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to save your progress.")

    # Insert the attempt.
    attempt = Attempt(
        user_id=user.id,
        ref_type=payload.ref_type,
        ref_id=payload.ref_id,
        trainer=payload.trainer,
        grade=payload.grade,
        seconds=payload.seconds,
    )
    session.add(attempt)

    # Upsert the streak (daily practice, not per-answer).
    streak = _upsert_streak(session, user.id, payload.trainer)
    session.commit()

    return {"current": streak.current, "best": streak.best}


@app.get("/api/train/streak")
def get_streak(
    trainer: str,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Return the signed-in user's streak for a trainer, or zeros for guest."""
    from app.auth import read_session
    from app.models import Streak

    user_id = read_session(request)
    if user_id is None:
        return {"current": 0, "best": 0}

    streak = session.scalars(
        select(Streak).where(Streak.user_id == user_id, Streak.trainer == trainer)
    ).first()
    if streak is None:
        return {"current": 0, "best": 0}
    return {"current": streak.current, "best": streak.best}


def _upsert_streak(session: Session, user_id, trainer: str):
    """Daily-practice streak upsert algorithm.

    - First attempt ever: create current=1, best=1, today.
    - Same day: no change.
    - Consecutive day: current += 1 (bump best if exceeded).
    - Gap: reset current = 1.
    Always sets last_active_date = today when it changes."""
    from datetime import date, datetime, timedelta

    from app.models import Streak

    today = date.today()

    streak = session.scalars(
        select(Streak).where(Streak.user_id == user_id, Streak.trainer == trainer)
    ).first()

    if streak is None:
        streak = Streak(
            user_id=user_id,
            trainer=trainer,
            current=1,
            best=1,
            last_active_date=today,
        )
        session.add(streak)
        return streak

    # Extract date from last_active_date.
    if isinstance(streak.last_active_date, datetime):
        last_date = streak.last_active_date.date()
    elif isinstance(streak.last_active_date, date):
        last_date = streak.last_active_date
    else:
        last_date = today

    if last_date == today:
        # Same day — no change.
        pass
    else:
        delta_days = (today - last_date).days
        if delta_days == 1:
            # Consecutive day — bump.
            streak.current += 1
            if streak.current > streak.best:
                streak.best = streak.current
        else:
            # Gap — reset.
            streak.current = 1
        streak.last_active_date = today

    return streak


# ── V2-S10: Position Duels ────────────────────────────────────────────


def _duel_rate_limit() -> str:
    """Callable limit so the rate can be overridden in tests."""
    return settings.RATE_LIMIT_DUELS


class CreateDuelRequest(BaseModel):
    fen: str
    source: Literal["paste", "curated-mate", "curated-endgame"]
    mode: Literal["realtime", "correspondence"] = "realtime"
    clock_limit_s: int | None = None  # overrides DUEL_CLOCK_LIMIT_S when set
    clock_increment_s: int | None = None
    days: int | None = None  # for correspondence mode
    name: str | None = None


@app.post("/api/duels")
@limiter.limit(_duel_rate_limit)
def create_duel(
    request: Request,
    payload: CreateDuelRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Create a Lichess open challenge from a FEN and return per-color
    share-links. Rate-limited (RATE_LIMIT_DUELS) to prevent Lichess spam.

    FEN validation happens BEFORE the Lichess call — invalid positions
    return 400 and never hit the external API.

    Guests can create duels (creator_user_id = null)."""
    from app.auth import read_session
    from app.duels import create_lichess_open_challenge, store_duel

    user_id = read_session(request)

    # Create the challenge on Lichess (validates the FEN internally).
    lichess_response = create_lichess_open_challenge(
        fen=payload.fen,
        clock_limit_s=payload.clock_limit_s,
        clock_increment_s=payload.clock_increment_s,
        days=payload.days if payload.mode == "correspondence" else None,
        name=payload.name,
    )

    # Persist the duel in our DB.
    duel = store_duel(
        session,
        fen=payload.fen,
        source=payload.source,
        lichess_response=lichess_response,
        creator_user_id=user_id,
    )

    return {
        "id": str(duel.id),
        "challenge_id": lichess_response.get("id") or lichess_response.get("challenge", {}).get("id", ""),
        "url": lichess_response.get("url") or lichess_response.get("challenge", {}).get("url", ""),
        "urlWhite": lichess_response.get("urlWhite", ""),
        "urlBlack": lichess_response.get("urlBlack", ""),
    }
