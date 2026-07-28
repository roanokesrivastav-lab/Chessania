"""The ingestion layer, fully tested offline.

respx intercepts the code's outgoing HTTP and hands back a recorded
response — no real network call ever happens, so these tests check our
logic, not Chess.com's or Lichess's uptime. That's what makes the whole
suite fast, free, and honest: green here means the parsing/filtering/
mapping code is right, not that some external server happened to be up
when the test ran.

Happy-path tests load real (scrubbed) recorded responses from
tests/fixtures/api/ (Appendix 10's fixture system, formalized this
session) — the error-path tests below don't need real fixture content,
only a status code to react to, so they stay inline.
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
from tests.conftest import load_fixture, load_json_fixture

# ---------------------------------------------------------------------------
# Chess.com: error paths (no fixture content needed — just a status code)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Chess.com: happy path, from recorded fixtures (tests/fixtures/api/)
# ---------------------------------------------------------------------------


@respx.mock
def test_chesscom_happy_path_from_fixture_filters_eligibility_maps_and_orders():
    """Uses the recorded chesscom_archives.json / chesscom_month.json fixtures
    (5 games: 3 eligible — win, loss, draw — plus a bullet and a chess960
    game, both excluded). Also proves newest-first ordering: the month
    fixture lists games oldest-first (as Chess.com really does), so a
    correct result here means the reversal logic is right, not coincidental."""
    archives = load_json_fixture("api", "chesscom_archives.json")
    month = load_json_fixture("api", "chesscom_month.json")

    respx.get("https://api.chess.com/pub/player/fixture_user/games/archives").mock(
        return_value=httpx.Response(200, json=archives)
    )
    respx.get("https://api.chess.com/pub/player/fixture_user/games/2026/06").mock(
        return_value=httpx.Response(200, json=month)
    )

    games = fetch_chesscom("fixture_user")

    assert len(games) == 3  # bullet and chess960 games excluded
    assert [g.result for g in games] == ["draw", "loss", "win"]  # newest-first
    assert [g.player_color for g in games] == ["white", "black", "white"]
    assert games[0].platform == "chesscom"
    assert games[0].platform_game_id == "https://www.chess.com/game/live/1000000005"


@respx.mock
def test_chesscom_month_walking_reaches_back_when_latest_month_is_thin(monkeypatch):
    """Fixture with a thin latest month (1 eligible game) forces the fetcher
    to walk back to the prior month to reach the requested count."""
    monkeypatch.setattr("app.config.settings.MAX_GAMES", 3)

    archives = load_json_fixture("api", "chesscom_archives_walktest.json")
    latest_month = load_json_fixture("api", "chesscom_month_walktest_latest.json")
    prior_month = load_json_fixture("api", "chesscom_month_walktest_prior.json")

    respx.get("https://api.chess.com/pub/player/fixture_walker/games/archives").mock(
        return_value=httpx.Response(200, json=archives)
    )
    prior_route = respx.get(
        "https://api.chess.com/pub/player/fixture_walker/games/2026/05"
    ).mock(return_value=httpx.Response(200, json=prior_month))
    respx.get("https://api.chess.com/pub/player/fixture_walker/games/2026/06").mock(
        return_value=httpx.Response(200, json=latest_month)
    )

    games = fetch_chesscom("fixture_walker")

    assert prior_route.called  # proves the walk-back actually happened
    assert len(games) == 3  # 1 from the thin latest month + 2 from the prior, capped at MAX_GAMES=3


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
# Lichess: error paths
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Lichess: happy path, from the recorded NDJSON fixture
# ---------------------------------------------------------------------------


@respx.mock
def test_lichess_happy_path_from_fixture_filters_orders_and_maps_opening():
    """Uses the recorded lichess_games.ndjson fixture (5 lines, newest-first
    as Lichess really streams them: win, draw, an excluded bullet game,
    loss, win). Proves eligibility filtering, color/result mapping,
    opening.eco/name mapping, and that fetch_lichess preserves the API's
    own newest-first order rather than needing to re-sort anything."""
    ndjson_body = load_fixture("api", "lichess_games.ndjson")
    respx.get("https://lichess.org/api/games/user/fixture_user").mock(
        return_value=httpx.Response(200, text=ndjson_body)
    )

    games = fetch_lichess("fixture_user")

    assert len(games) == 4  # the bullet line excluded
    assert [g.result for g in games] == ["win", "draw", "loss", "win"]
    assert [g.opening_eco for g in games] == ["C50", "B01", "A45", "C00"]
    assert games[0].platform == "lichess"
    assert games[0].platform_game_id == "fixture_game_5"
    assert games[0].game_url == "https://lichess.org/fixture_game_5"


@respx.mock
def test_lichess_absent_winner_is_a_draw():
    ndjson_body = load_fixture("api", "lichess_games.ndjson")
    respx.get("https://lichess.org/api/games/user/fixture_user").mock(
        return_value=httpx.Response(200, text=ndjson_body)
    )
    games = fetch_lichess("fixture_user")
    draw_games = [g for g in games if g.result == "draw"]
    assert len(draw_games) == 1
    assert draw_games[0].platform_game_id == "fixture_game_4"


# ---------------------------------------------------------------------------
# fetch_games dispatcher
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
    respx.get("https://lichess.org/api/games/user/fixture_user").mock(
        return_value=httpx.Response(200, text=load_fixture("api", "lichess_games.ndjson"))
    )
    games = fetch_games("lichess", "fixture_user")
    assert games[0].platform == "lichess"


def test_fetch_games_rejects_unknown_platform():
    with pytest.raises(ValueError):
        fetch_games("carrierpigeon", "someone")


# ---------------------------------------------------------------------------
# Persistence + dedupe
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


def test_persist_games_preserves_existing_opening_data():
    """Regression guard: Chess.com games get their opening derived from the
    PGN, but Lichess games already carry authoritative opening_eco/name and
    must never be overwritten by the opening book."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = upsert_player(session, "lichess", "lichess_opening_preserve", 1500)
        game = NormalizedGame(
            platform="lichess",
            platform_game_id="preserve_opening_1",
            game_url="https://lichess.org/preserve_opening_1",
            pgn="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O *",
            time_class="rapid",
            player_color="white",
            result="win",
            player_rating=1500,
            opponent_rating=1490,
            played_at=None,
            opening_eco="C78",  # supplied by Lichess
            opening_name="Ruy Lopez: Morphy Defense, Closed Center",
        )

        persist_games(session, player, [game])
        persisted = session.query(Game).filter_by(platform_game_id="preserve_opening_1").one()

        assert persisted.opening_eco == "C78"
        assert persisted.opening_name == "Ruy Lopez: Morphy Defense, Closed Center"


def test_persist_games_derives_opening_for_chesscom_games():
    """Chess.com games arrive with null openings; persist_games fills them
    from the stored PGN using the opening book."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = upsert_player(session, "chesscom", "chesscom_opening_derive", 1500)
        game = NormalizedGame(
            platform="chesscom",
            platform_game_id="derive_opening_1",
            game_url="https://www.chess.com/game/live/derive_opening_1",
            pgn="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O *",
            time_class="blitz",
            player_color="white",
            result="win",
            player_rating=1500,
            opponent_rating=1490,
            played_at=None,
            opening_eco=None,  # Chess.com supplies no opening
            opening_name=None,
        )

        persist_games(session, player, [game])
        persisted = session.query(Game).filter_by(platform_game_id="derive_opening_1").one()

        assert persisted.opening_eco is not None
        assert persisted.opening_eco.startswith("C")
        assert persisted.opening_name is not None
        assert "Ruy Lopez" in persisted.opening_name or "Spanish" in persisted.opening_name


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


@respx.mock
def test_ingest_same_fixture_twice_against_fresh_db_adds_zero_duplicates(db_session):
    """The literal Session 7 DoD wording: 'dedupe (ingest same fixture twice
    against a fresh in-memory SQLite, assert new: 0)' — this is the full
    fetch -> persist pipeline, not just persist_games in isolation."""
    archives = load_json_fixture("api", "chesscom_archives.json")
    month = load_json_fixture("api", "chesscom_month.json")
    respx.get("https://api.chess.com/pub/player/fixture_user/games/archives").mock(
        return_value=httpx.Response(200, json=archives)
    )
    respx.get("https://api.chess.com/pub/player/fixture_user/games/2026/06").mock(
        return_value=httpx.Response(200, json=month)
    )

    games = fetch_chesscom("fixture_user")
    player = upsert_player(db_session, "chesscom", "fixture_user", games[0].player_rating)

    first = persist_games(db_session, player, games)
    assert first["new"] == 3

    second = persist_games(db_session, player, games)
    assert second["new"] == 0
    assert second["already_known"] == 3
