"""Ingestion — turns platform API responses into NormalizedGame objects.

Why normalize at the edge: everything downstream (analysis, features, coach)
speaks only NormalizedGame. Chess.com's per-month archive walk vs Lichess's
single NDJSON stream, their different result-code vocabularies, their
different field names — all of that platform weirdness is quarantined in
this one file. Adding a third platform someday means writing one more
fetch_* function; nothing else in the pipeline has to change.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Game, Player
from app.opening_book import classify_opening

ELIGIBLE_TIME_CLASSES = {"rapid", "blitz"}

# Chess.com's per-player result string -> our three-way outcome (Appendix 9).
# Everything not "win" and not one of these draw reasons is a loss
# (checkmated, timeout, resigned, abandoned, etc.) — there are more loss
# reasons than it's useful to enumerate, so loss is the default rather than
# an explicit set.
_CHESSCOM_DRAW_RESULTS = {
    "agreed",
    "repetition",
    "stalemate",
    "insufficient",
    "50move",
    "timevsinsufficient",
}


class PlayerNotFound(Exception):
    """The platform has no such username (Chess.com 404)."""


class NoEligibleGames(Exception):
    """The account exists but has no rapid/blitz standard-chess games in range."""


class UpstreamRateLimited(Exception):
    """429 from the platform. This fetcher does not retry-loop — it raises,
    and the caller (the S10 job) surfaces a friendly "try again in a minute"."""


class UpstreamError(Exception):
    """Any other non-2xx response from the platform."""


@dataclass
class NormalizedGame:
    """The common shape every platform's fetcher is forced into."""

    platform: str
    platform_game_id: str
    game_url: str
    pgn: str
    time_class: str
    player_color: str
    result: str  # win | loss | draw, from the analyzed player's perspective
    player_rating: int | None
    opponent_rating: int | None
    played_at: dt.datetime | None
    opening_eco: str | None
    opening_name: str | None


def _chesscom_result_to_outcome(result: str) -> str:
    if result == "win":
        return "win"
    if result in _CHESSCOM_DRAW_RESULTS:
        return "draw"
    return "loss"


def fetch_chesscom(username: str, max_games: int | None = None) -> list[NormalizedGame]:
    """Return up to max_games eligible games for a Chess.com username,
    newest first. Defaults to the fast 20-game cap; the S33 deep dive
    passes MAX_GAMES_DEEP (100). (Default resolved at call time, not def
    time, so tests can monkeypatch settings.MAX_GAMES and have it apply.)

    Eligible = time_class in (rapid, blitz) and rules == "chess" — the
    rules check excludes variants (bughouse, chess960, king-of-the-hill,
    three-check, etc.). Those are a different game with a different skill
    set entirely, not just a different time control; mixing them into
    "your games" would corrupt every rate the pipeline computes downstream.
    """
    max_games = settings.MAX_GAMES if max_games is None else max_games
    username = username.lower()  # Chess.com URLs require lowercase
    headers = {"User-Agent": f"Chessania/0.1 (+{settings.CONTACT_EMAIL})"}

    try:
        with httpx.Client(headers=headers, timeout=10.0) as client:
            archives_resp = client.get(
                f"https://api.chess.com/pub/player/{username}/games/archives"
            )
            if archives_resp.status_code == 404:
                raise PlayerNotFound(username)
            if archives_resp.status_code == 429:
                raise UpstreamRateLimited("chess.com archives list")
            if archives_resp.status_code != 200:
                raise UpstreamError(f"chess.com archives list: {archives_resp.status_code}")

            archive_urls = archives_resp.json().get("archives", [])
            games: list[NormalizedGame] = []

            # Walk the archives newest first, stopping early once we have
            # max_games — a standard run usually needs one month; the deep
            # dive walks back further until it fills its larger cap. Cap the
            # walk at a year of archives so a sparse account can't trigger a
            # dozen serial requests for a handful of games (Appendix 9
            # politeness) — the standard 20-game path is unaffected. Fetched
            # serially (never in parallel).
            for month_url in reversed(archive_urls[-12:]):
                month_resp = client.get(month_url)
                if month_resp.status_code == 429:
                    raise UpstreamRateLimited(month_url)
                if month_resp.status_code != 200:
                    raise UpstreamError(f"{month_url}: {month_resp.status_code}")

                # Chess.com lists each month's games oldest-first; reverse so
                # the newest games in the newest month are collected first too.
                for raw in reversed(month_resp.json().get("games", [])):
                    if raw.get("rules") != "chess":
                        continue
                    if raw.get("time_class") not in ELIGIBLE_TIME_CLASSES:
                        continue

                    white = raw.get("white", {})
                    black = raw.get("black", {})
                    if white.get("username", "").lower() == username:
                        player_color, player_side, opponent_side = "white", white, black
                    elif black.get("username", "").lower() == username:
                        player_color, player_side, opponent_side = "black", black, white
                    else:
                        continue  # shouldn't happen; skip rather than guess

                    games.append(
                        NormalizedGame(
                            platform="chesscom",
                            platform_game_id=raw["url"],  # unique per game, stable
                            game_url=raw["url"],
                            pgn=raw["pgn"],
                            time_class=raw["time_class"],
                            player_color=player_color,
                            result=_chesscom_result_to_outcome(player_side.get("result", "")),
                            player_rating=player_side.get("rating"),
                            opponent_rating=opponent_side.get("rating"),
                            played_at=(
                                dt.datetime.fromtimestamp(raw["end_time"], tz=dt.timezone.utc)
                                if "end_time" in raw
                                else None
                            ),
                            opening_eco=None,  # Chess.com's archive JSON has no ECO field
                            opening_name=None,
                        )
                    )
                    if len(games) >= max_games:
                        break
                if len(games) >= max_games:
                    break
    except httpx.RequestError as exc:
        # A real network failure (DNS, connection refused, timeout) rather
        # than an HTTP status code — the S10 job only knows how to translate
        # the four typed exceptions into a friendly message, so a bare httpx
        # exception here would otherwise crash the job with a raw traceback.
        raise UpstreamError(f"network error contacting chess.com: {exc}") from exc

    if not games:
        raise NoEligibleGames(username)

    return games[:max_games]


def fetch_lichess(username: str, max_games: int | None = None) -> list[NormalizedGame]:
    """Return up to max_games eligible games for a Lichess username,
    newest first. Defaults to the fast 20-game cap; the S33 deep dive
    passes MAX_GAMES_DEEP (100). (Default resolved at call time.)

    Unlike Chess.com's multi-request archive walk, this is a single
    request: Lichess streams NDJSON (one JSON object per line, newest
    first) and does the max/perfType filtering server-side (Appendix 9).
    """
    max_games = settings.MAX_GAMES if max_games is None else max_games

    headers = {
        "User-Agent": f"Chessania/0.1 (+{settings.CONTACT_EMAIL})",
        "Accept": "application/x-ndjson",
    }
    params = {
        "max": max_games,
        "perfType": "blitz,rapid",
        "pgnInJson": "true",
        # Lichess omits the "opening" object entirely unless this is set —
        # discovered by hitting the real API during review (its response
        # shape without this flag has no opening.eco/opening.name at all,
        # not just null values). Appendix 9 documents opening.{eco,name} as
        # part of the response shape, so this flag is required to actually
        # get what the appendix promises.
        "opening": "true",
        # Same story for clocks: without this flag the PGN has no [%clk] stamps.
        # We don't read per-move time in v1, but we capture the raw clocks now so
        # future v2 time-management coaching (roadmap Part G #11) never needs a
        # painful re-fetch. Chess.com includes clocks by default; this brings
        # Lichess to parity. (2026-07-25 amendment.)
        "clocks": "true",
    }

    try:
        with httpx.Client(headers=headers, timeout=15.0) as client:
            resp = client.get(f"https://lichess.org/api/games/user/{username}", params=params)
            if resp.status_code == 404:
                raise PlayerNotFound(username)
            if resp.status_code == 429:
                # Lichess convention: a rate limit means a full stop for
                # >= 60s, not a quick retry — raise immediately, same as
                # Chess.com, and let the caller surface friendly copy.
                raise UpstreamRateLimited("lichess games stream")
            if resp.status_code != 200:
                raise UpstreamError(f"lichess games stream: {resp.status_code}")

            games: list[NormalizedGame] = []
            for line in resp.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)

                # The perfType param already restricts the server-side
                # response to blitz/rapid, but this check is cheap and
                # keeps both fetchers' eligibility logic symmetric and
                # explicit rather than trusting the upstream filter blindly.
                if raw.get("speed") not in ELIGIBLE_TIME_CLASSES:
                    continue

                players = raw.get("players", {})
                white = players.get("white", {})
                black = players.get("black", {})
                white_name = (white.get("user") or {}).get("name", "")
                black_name = (black.get("user") or {}).get("name", "")

                if white_name.lower() == username.lower():
                    player_color, player_side, opponent_side = "white", white, black
                elif black_name.lower() == username.lower():
                    player_color, player_side, opponent_side = "black", black, white
                else:
                    continue  # shouldn't happen; skip rather than guess

                winner = raw.get("winner")  # "white" | "black" | absent = draw
                if winner is None:
                    result = "draw"
                elif winner == player_color:
                    result = "win"
                else:
                    result = "loss"

                opening = raw.get("opening") or {}
                game_id = raw["id"]

                games.append(
                    NormalizedGame(
                        platform="lichess",
                        platform_game_id=game_id,
                        game_url=f"https://lichess.org/{game_id}",
                        pgn=raw.get("pgn", ""),
                        time_class=raw["speed"],
                        player_color=player_color,
                        result=result,
                        player_rating=player_side.get("rating"),
                        opponent_rating=opponent_side.get("rating"),
                        played_at=(
                            dt.datetime.fromtimestamp(raw["createdAt"] / 1000, tz=dt.timezone.utc)
                            if "createdAt" in raw
                            else None
                        ),
                        opening_eco=opening.get("eco"),
                        opening_name=opening.get("name"),
                    )
                )
    except httpx.RequestError as exc:
        raise UpstreamError(f"network error contacting lichess: {exc}") from exc

    if not games:
        raise NoEligibleGames(username)

    return games[:max_games]


def fetch_games(
    platform: str, username: str, max_games: int | None = None
) -> list[NormalizedGame]:
    """Dispatch to the right platform fetcher. Adding a third platform
    someday means adding one more branch here and one more fetch_* function
    — nothing downstream of NormalizedGame has to change. max_games is
    threaded through so the S33 deep dive can request up to 100; None
    resolves to settings.MAX_GAMES inside the fetchers (call time)."""
    if platform == "chesscom":
        return fetch_chesscom(username, max_games=max_games)
    if platform == "lichess":
        return fetch_lichess(username, max_games=max_games)
    raise ValueError(f"unknown platform: {platform!r}")


def upsert_player(session: Session, platform: str, username: str, rating_snapshot: int | None) -> Player:
    """Insert the players row for (platform, username) if it doesn't exist
    yet, otherwise update its rating snapshot. Identity is this pair —
    there is no login anywhere in this product (Locked Decision 2)."""
    username = username.lower()
    player = session.execute(
        select(Player).where(Player.platform == platform, Player.username == username)
    ).scalar_one_or_none()

    if player is None:
        player = Player(platform=platform, username=username, rating_snapshot=rating_snapshot)
        session.add(player)
    elif rating_snapshot is not None:
        player.rating_snapshot = rating_snapshot

    session.commit()
    session.refresh(player)
    return player


def persist_games(session: Session, player: Player, games: list[NormalizedGame]) -> dict:
    """Insert games with insert-if-absent semantics on (player_id,
    platform_game_id) — the dedupe law from Appendix 1's unique constraint.

    Idempotency ("safe to run twice") is what makes a crashed ingest job
    restartable instead of a mess: running this twice for the same games
    adds zero duplicate rows, so a job that dies halfway through can simply
    be re-run from the top rather than needing to track exactly where it
    stopped.
    """
    fetched = len(games)
    new = 0

    for g in games:
        exists = session.execute(
            select(Game).where(
                Game.player_id == player.id,
                Game.platform_game_id == g.platform_game_id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue

        # Chess.com's archive JSON carries no opening data; derive it from
        # the moves so the rest of the pipeline (opening_leak, S16 recs)
        # works for both platforms. Lichess games already have ECO/name and
        # are never overwritten.
        opening_eco = g.opening_eco
        opening_name = g.opening_name
        if opening_eco is None or opening_name is None:
            book_eco, book_name = classify_opening(g.pgn)
            opening_eco = opening_eco or book_eco
            opening_name = opening_name or book_name

        session.add(
            Game(
                player_id=player.id,
                platform_game_id=g.platform_game_id,
                game_url=g.game_url,
                pgn=g.pgn,
                time_class=g.time_class,
                player_color=g.player_color,
                result=g.result,
                player_rating=g.player_rating,
                opponent_rating=g.opponent_rating,
                played_at=g.played_at,
                opening_eco=opening_eco,
                opening_name=opening_name,
            )
        )
        new += 1

    session.commit()
    return {"fetched": fetched, "new": new, "already_known": fetched - new}
