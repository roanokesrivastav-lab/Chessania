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

from app.ingest import (
    NoEligibleGames,
    PlayerNotFound,
    UpstreamError,
    UpstreamRateLimited,
    fetch_chesscom,
)


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
