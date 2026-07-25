"""Session 5 tests: the four typed error paths, plus a happy-path check of
eligibility filtering, color detection, and result mapping.

respx intercepts httpx's outgoing requests and hands back a canned response
— no real network call happens, so these tests are offline and deterministic
(Rule 5) despite exercising real HTTP-calling code. Session 7 moves these
canned responses into committed fixture files under tests/fixtures/api/ and
formalizes this pattern for the whole ingestion suite; here they're kept
inline since that's this session's scope, not this one's.
"""

import httpx
import pytest
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import enable_sqlite_foreign_keys
from app.ingest import (
    NoEligibleGames,
    NormalizedGame,
    PlayerNotFound,
    UpstreamError,
    UpstreamRateLimited,
    fetch_chesscom,
    fetch_games,
    fetch_lichess,
    persist_games,
    upsert_player,
)
from app.models import Base, Game


@respx.mock
def test_player_not_found_raises_typed_exception():
    respx.get("https://api.chess.com/pub/player/ghostplayer/games/archives").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(PlayerNotFound):
        fetch_chesscom("ghostplayer")


@respx.mock
def test_rate_limit_raises_typed_exception_without_retrying():
    respx.get("https://api.chess.com/pub/player/limiteduser/games/archives").mock(
        return_value=httpx.Response(429)
    )
    with pytest.raises(UpstreamRateLimited):
        fetch_chesscom("limiteduser")


@respx.mock
def test_unexpected_status_raises_upstream_error():
    respx.get("https://api.chess.com/pub/player/erroruser/games/archives").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(UpstreamError):
        fetch_chesscom("erroruser")


@respx.mock
def test_network_failure_raises_upstream_error_not_a_raw_httpx_exception():
    """Regression test found in review: a genuine connection failure (DNS,
    refused connection, timeout) previously leaked a raw httpx.ConnectError
    instead of being translated into one of the four typed exceptions —
    which would have crashed the S10 job with an ugly traceback instead of
    the friendly message it's designed to show."""
    respx.get("https://api.chess.com/pub/player/networkfail/games/archives").mock(
        side_effect=httpx.ConnectError("simulated network failure")
    )
    with pytest.raises(UpstreamError):
        fetch_chesscom("networkfail")


@respx.mock
def test_no_eligible_games_when_everything_is_filtered_out():
    username = "onlybullet"
    respx.get(f"https://api.chess.com/pub/player/{username}/games/archives").mock(
        return_value=httpx.Response(
            200,
            json={"archives": [f"https://api.chess.com/pub/player/{username}/games/2026/06"]},
        )
    )
    respx.get(f"https://api.chess.com/pub/player/{username}/games/2026/06").mock(
        return_value=httpx.Response(
            200,
            json={
                "games": [
                    {
                        "url": "https://www.chess.com/game/live/1",
                        "pgn": "1. e4 e5",
                        "time_class": "bullet",  # ineligible — not rapid/blitz
                        "rules": "chess",
                        "end_time": 1717200000,
                        "white": {"username": username, "rating": 1000, "result": "win"},
                        "black": {"username": "opponent", "rating": 990, "result": "checkmated"},
                    }
                ]
            },
        )
    )
    with pytest.raises(NoEligibleGames):
        fetch_chesscom(username)


@respx.mock
def test_happy_path_filters_eligibility_and_maps_color_and_result():
    username = "testplayer"
    respx.get(f"https://api.chess.com/pub/player/{username}/games/archives").mock(
        return_value=httpx.Response(
            200,
            json={"archives": [f"https://api.chess.com/pub/player/{username}/games/2026/06"]},
        )
    )
    respx.get(f"https://api.chess.com/pub/player/{username}/games/2026/06").mock(
        return_value=httpx.Response(
            200,
            json={
                "games": [
                    {
                        # eligible: rapid, standard chess, player is Black, wins
                        "url": "https://www.chess.com/game/live/1",
                        "pgn": "1. e4 e5",
                        "time_class": "rapid",
                        "rules": "chess",
                        "end_time": 1717200000,
                        "white": {"username": "opponent", "rating": 1100, "result": "checkmated"},
                        "black": {"username": username, "rating": 1050, "result": "win"},
                    },
                    {
                        # excluded: bullet
                        "url": "https://www.chess.com/game/live/2",
                        "pgn": "1. d4 d5",
                        "time_class": "bullet",
                        "rules": "chess",
                        "end_time": 1717200100,
                        "white": {"username": username, "rating": 1050, "result": "win"},
                        "black": {"username": "opponent", "rating": 1100, "result": "resigned"},
                    },
                    {
                        # excluded: variant, not standard chess
                        "url": "https://www.chess.com/game/live/3",
                        "pgn": "1. e4",
                        "time_class": "rapid",
                        "rules": "chess960",
                        "end_time": 1717200200,
                        "white": {"username": username, "rating": 1050, "result": "win"},
                        "black": {"username": "opponent", "rating": 1100, "result": "resigned"},
                    },
                ]
            },
        )
    )

    games = fetch_chesscom(username)

    assert len(games) == 1
    game = games[0]
    assert game.platform == "chesscom"
    assert game.platform_game_id == "https://www.chess.com/game/live/1"
    assert game.time_class == "rapid"
    assert game.player_color == "black"
    assert game.result == "win"
    assert game.player_rating == 1050
    assert game.opponent_rating == 1100


@respx.mock
def test_chesscom_draw_reasons_map_to_draw():
    username = "drawplayer"
    respx.get(f"https://api.chess.com/pub/player/{username}/games/archives").mock(
        return_value=httpx.Response(
            200,
            json={"archives": [f"https://api.chess.com/pub/player/{username}/games/2026/06"]},
        )
    )
    respx.get(f"https://api.chess.com/pub/player/{username}/games/2026/06").mock(
        return_value=httpx.Response(
            200,
            json={
                "games": [
                    {
                        "url": "https://www.chess.com/game/live/1",
                        "pgn": "1. e4 e5",
                        "time_class": "blitz",
                        "rules": "chess",
                        "end_time": 1717200000,
                        "white": {"username": username, "rating": 1050, "result": "repetition"},
                        "black": {"username": "opponent", "rating": 1050, "result": "repetition"},
                    }
                ]
            },
        )
    )

    games = fetch_chesscom(username)
    assert games[0].result == "draw"


# ---------------------------------------------------------------------------
# Session 6: Lichess fetcher
# ---------------------------------------------------------------------------


def _lichess_ndjson_line(**overrides) -> str:
    import json as _json

    base = {
        "id": "abcd1234",
        "speed": "rapid",
        "winner": "black",
        "players": {
            "white": {"user": {"name": "opponent"}, "rating": 1100},
            "black": {"user": {"name": "testplayer"}, "rating": 1050},
        },
        "pgn": "1. e4 e5",
        "opening": {"eco": "C20", "name": "King's Pawn Game"},
        "createdAt": 1717200000000,
    }
    base.update(overrides)
    return _json.dumps(base)


@respx.mock
def test_lichess_player_not_found():
    respx.get("https://lichess.org/api/games/user/ghostplayer").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(PlayerNotFound):
        fetch_lichess("ghostplayer")


@respx.mock
def test_lichess_rate_limited():
    respx.get("https://lichess.org/api/games/user/limiteduser").mock(
        return_value=httpx.Response(429)
    )
    with pytest.raises(UpstreamRateLimited):
        fetch_lichess("limiteduser")


@respx.mock
def test_lichess_happy_path_maps_color_result_opening_and_ndjson_parsing():
    ndjson_body = "\n".join(
        [
            _lichess_ndjson_line(id="game1", winner="black"),  # player (black) wins
            _lichess_ndjson_line(  # excluded: not rapid/blitz
                id="game2", speed="bullet", winner="white"
            ),
        ]
    )
    respx.get("https://lichess.org/api/games/user/testplayer").mock(
        return_value=httpx.Response(200, text=ndjson_body)
    )

    games = fetch_lichess("testplayer")

    assert len(games) == 1
    g = games[0]
    assert g.platform == "lichess"
    assert g.platform_game_id == "game1"
    assert g.game_url == "https://lichess.org/game1"
    assert g.time_class == "rapid"
    assert g.player_color == "black"
    assert g.result == "win"
    assert g.player_rating == 1050
    assert g.opponent_rating == 1100
    assert g.opening_eco == "C20"
    assert g.opening_name == "King's Pawn Game"


@respx.mock
def test_lichess_absent_winner_is_a_draw():
    ndjson_body = _lichess_ndjson_line(id="drawgame", winner=None)
    # Absent winner key entirely (not just null) is how Lichess represents a draw.
    import json as _json

    payload = _json.loads(ndjson_body)
    del payload["winner"]
    respx.get("https://lichess.org/api/games/user/testplayer").mock(
        return_value=httpx.Response(200, text=_json.dumps(payload))
    )

    games = fetch_lichess("testplayer")  # matches _lichess_ndjson_line()'s default black name
    assert games[0].result == "draw"


# ---------------------------------------------------------------------------
# Session 6: fetch_games dispatcher
# ---------------------------------------------------------------------------


@respx.mock
def test_fetch_games_dispatches_to_chesscom():
    username = "dispatchtest"
    respx.get(f"https://api.chess.com/pub/player/{username}/games/archives").mock(
        return_value=httpx.Response(200, json={"archives": []})
    )
    with pytest.raises(NoEligibleGames):
        fetch_games("chesscom", username)


@respx.mock
def test_fetch_games_dispatches_to_lichess():
    username = "testplayer"  # matches _lichess_ndjson_line()'s default black name
    respx.get(f"https://lichess.org/api/games/user/{username}").mock(
        return_value=httpx.Response(200, text=_lichess_ndjson_line())
    )
    games = fetch_games("lichess", username)
    assert games[0].platform == "lichess"


def test_fetch_games_rejects_unknown_platform():
    with pytest.raises(ValueError):
        fetch_games("carrierpigeon", "someone")


# ---------------------------------------------------------------------------
# Session 6: persistence + dedupe
# ---------------------------------------------------------------------------


def _make_normalized_game(platform_game_id: str) -> NormalizedGame:
    return NormalizedGame(
        platform="lichess",
        platform_game_id=platform_game_id,
        game_url=f"https://lichess.org/{platform_game_id}",
        pgn="1. e4 e5",
        time_class="rapid",
        player_color="white",
        result="win",
        player_rating=1500,
        opponent_rating=1490,
        played_at=None,
        opening_eco="C20",
        opening_name="King's Pawn Game",
    )


def test_upsert_player_creates_then_updates_rating():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        p1 = upsert_player(session, "lichess", "TestPlayer", 1500)
        assert p1.username == "testplayer"  # stored lowercased
        assert p1.rating_snapshot == 1500

        p2 = upsert_player(session, "lichess", "TestPlayer", 1550)
        assert p2.id == p1.id  # same row, not a duplicate
        assert p2.rating_snapshot == 1550


def test_persist_games_is_idempotent_running_twice_adds_zero_new_rows():
    """The dedupe law: running ingestion twice must add zero duplicate rows."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    games = [_make_normalized_game("g1"), _make_normalized_game("g2")]

    with Session(engine) as session:
        player = upsert_player(session, "lichess", "dedupeplayer", 1500)

        first = persist_games(session, player, games)
        assert first == {"fetched": 2, "new": 2, "already_known": 0}

        second = persist_games(session, player, games)
        assert second == {"fetched": 2, "new": 0, "already_known": 2}

        total_rows = session.query(Game).filter_by(player_id=player.id).count()
        assert total_rows == 2  # not 4 — no duplicates from the second run


def test_persist_games_for_different_players_do_not_collide():
    """Both platforms' games coexist for different players without collision."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        chesscom_player = upsert_player(session, "chesscom", "alice", 1200)
        lichess_player = upsert_player(session, "lichess", "bob", 1400)

        persist_games(session, chesscom_player, [_make_normalized_game("shared_id")])
        persist_games(session, lichess_player, [_make_normalized_game("shared_id")])

        assert session.query(Game).filter_by(player_id=chesscom_player.id).count() == 1
        assert session.query(Game).filter_by(player_id=lichess_player.id).count() == 1
        assert session.query(Game).count() == 2
