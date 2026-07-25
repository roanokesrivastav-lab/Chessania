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
from dataclasses import dataclass

import httpx

from app.config import settings

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


def fetch_chesscom(username: str) -> list[NormalizedGame]:
    """Return up to settings.MAX_GAMES eligible games for a Chess.com
    username, newest first.

    Eligible = time_class in (rapid, blitz) and rules == "chess" — the
    rules check excludes variants (bughouse, chess960, king-of-the-hill,
    three-check, etc.). Those are a different game with a different skill
    set entirely, not just a different time control; mixing them into
    "your games" would corrupt every rate the pipeline computes downstream.
    """
    username = username.lower()  # Chess.com URLs require lowercase
    headers = {"User-Agent": f"Chessania/0.1 (+{settings.CONTACT_EMAIL})"}

    with httpx.Client(headers=headers, timeout=10.0) as client:
        archives_resp = client.get(f"https://api.chess.com/pub/player/{username}/games/archives")
        if archives_resp.status_code == 404:
            raise PlayerNotFound(username)
        if archives_resp.status_code == 429:
            raise UpstreamRateLimited("chess.com archives list")
        if archives_resp.status_code != 200:
            raise UpstreamError(f"chess.com archives list: {archives_resp.status_code}")

        archive_urls = archives_resp.json().get("archives", [])
        games: list[NormalizedGame] = []

        # Walk at most the last 3 months, newest first, stopping early once
        # we have enough games — fetched serially (never in parallel; a
        # polite client to a free public API, Appendix 9).
        for month_url in reversed(archive_urls[-3:]):
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
                if len(games) >= settings.MAX_GAMES:
                    break
            if len(games) >= settings.MAX_GAMES:
                break

    if not games:
        raise NoEligibleGames(username)

    return games[: settings.MAX_GAMES]
