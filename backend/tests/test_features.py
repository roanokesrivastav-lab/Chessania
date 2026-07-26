"""Session 12 offline tests for app/features.py — pure aggregation over
move_evals rows built directly in the in-memory test database (no engine,
no network: this session is aggregation-only). Every expected number below
is hand-computed, not "approximately" — see each test's comment for the
arithmetic.

Building blocks: `_insert_player_and_game` inserts a throwaway Player (once
per test, reused across that test's games) and one Game row; `_insert_rows`
inserts a list of MoveEval rows for it. Both go through db_session directly,
same pattern test_api.py and test_analysis.py already use.
"""

import datetime as dt
import io
import uuid

import chess.pgn
import pytest

from app.analysis import analyze_game
from app.config import settings
from app.engine_eval import FixtureEvaluator
from app.features import build_features
from app.models import Game, MoveEval, Player
from tests.conftest import load_fixture

_BASE_TIME = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def _insert_player_and_game(
    db_session,
    *,
    color: str = "white",
    result: str = "win",
    time_class: str = "blitz",
    played_at: dt.datetime | None = None,
    username: str = "tester",
) -> Game:
    """Insert (or reuse) a throwaway Player for `username`, then insert one
    Game row for it with the given color/result. `platform_game_id` is a
    fresh uuid each call so multiple games for the same test never collide
    with the (player_id, platform_game_id) unique constraint."""
    player = (
        db_session.query(Player)
        .filter_by(platform="chesscom", username=username)
        .first()
    )
    if player is None:
        player = Player(platform="chesscom", username=username)
        db_session.add(player)
        db_session.commit()

    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class=time_class,
        player_color=color,
        result=result,
        played_at=played_at,
        analyzed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(game)
    db_session.commit()
    return game


def _insert_rows(db_session, game: Game, rows_spec: list[dict]) -> list[MoveEval]:
    """rows_spec: a list of dicts, one per move, each with at least
    `cp_loss` and `classification`. `ply`, `phase`, `eval_cp_before`, and
    `eval_cp_after` fall back to sane defaults when not given."""
    rows = []
    for i, spec in enumerate(rows_spec, start=1):
        rows.append(
            MoveEval(
                game_id=game.id,
                ply=spec.get("ply", i),
                move_san="e4",
                fen_before=chess.STARTING_FEN,
                eval_cp_before=spec.get("eval_cp_before", 0),
                eval_cp_after=spec.get("eval_cp_after", 0),
                cp_loss=spec["cp_loss"],
                best_move_san="e4",
                classification=spec["classification"],
                phase=spec.get("phase", "middlegame"),
            )
        )
    db_session.add_all(rows)
    db_session.commit()
    return rows


def _evals_for(db_session, *games: Game) -> dict[str, list[MoveEval]]:
    return {
        str(g.id): db_session.query(MoveEval).filter_by(game_id=g.id).all() for g in games
    }


# ---------------------------------------------------------------------------
# 1. Hand-computed single game
# ---------------------------------------------------------------------------


def test_single_game_hand_computed_rates(db_session):
    """S13: move_evals stores a row for EVERY ply (both colors) — a
    player_color='white' game has the PLAYER on odd plies (1,3,5,7) and the
    OPPONENT on even plies (2,4,6). Every number below is hand-computed over
    the PLAYER's rows only; the three opponent 'blunder' rows (cp_loss 999,
    on even plies) are a built-in regression check that they contribute
    ZERO — the S12 bug this session fixes counted both colors."""
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME)
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok"},  # player
            {"ply": 2, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 3, "cp_loss": 60, "classification": "inaccuracy"},  # player
            {"ply": 4, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 5, "cp_loss": 250, "classification": "blunder"},  # player
            {"ply": 6, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 7, "cp_loss": 10, "classification": "ok"},  # player
        ],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=1500)

    assert features.games_analyzed == 1
    assert features.blunders_per_game == 1.0  # 1 PLAYER blunder (ply 5) / 1 game
    assert features.mistakes_per_game == 0.0
    assert features.inaccuracies_per_game == 1.0  # 1 PLAYER inaccuracy (ply 3) / 1 game
    assert features.acpl_overall == 80.0  # PLAYER rows only: (0 + 60 + 250 + 10) / 4 = 80.0


# ---------------------------------------------------------------------------
# 2. 'skipped' excluded from ACPL
# ---------------------------------------------------------------------------


def test_skipped_rows_excluded_from_acpl(db_session):
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME)
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok"},  # player
            {"ply": 2, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 3, "cp_loss": 60, "classification": "inaccuracy"},  # player
            {"ply": 4, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 5, "cp_loss": 250, "classification": "blunder"},  # player
            {"ply": 6, "cp_loss": 999, "classification": "blunder"},  # opponent — must NOT count
            {"ply": 7, "cp_loss": 10, "classification": "ok"},  # player
            # A huge cp_loss in an already-decided position, on a PLAYER ply —
            # must NOT move acpl_overall at all (denominator excludes
            # 'skipped' rows regardless of whose move it was).
            {"ply": 9, "cp_loss": 900, "classification": "skipped"},  # player
        ],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=None)

    assert features.acpl_overall == 80.0  # unchanged from the player-only test above


def test_opponent_blunder_does_not_count_toward_player_blunders(db_session):
    """Dedicated regression test for the S12 bug S13 fixes: move_evals
    stores a row for EVERY ply (both colors) — an opponent 'blunder' row
    must contribute ZERO to the player's blunders_per_game, even though it
    lives in the very same game's rows."""
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME)  # white
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok"},  # player — no blunders at all
            {"ply": 2, "cp_loss": 500, "classification": "blunder"},  # OPPONENT blunder
        ],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=None)
    assert features.blunders_per_game == 0.0


# ---------------------------------------------------------------------------
# 3. worst_phase
# ---------------------------------------------------------------------------


def test_worst_phase_exceeds_overall_by_exact_margin(db_session):
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME)
    _insert_rows(
        db_session,
        game,
        [
            {"cp_loss": 10, "classification": "ok", "phase": "opening"},
            {"cp_loss": 10, "classification": "ok", "phase": "opening"},
            {"cp_loss": 30, "classification": "inaccuracy", "phase": "middlegame"},
            {"cp_loss": 30, "classification": "inaccuracy", "phase": "middlegame"},
            {"cp_loss": 200, "classification": "blunder", "phase": "endgame"},
            {"cp_loss": 200, "classification": "blunder", "phase": "endgame"},
        ],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=None)

    # overall = (10+10+30+30+200+200)/6 = 480/6 = 80.0
    assert features.acpl_overall == 80.0
    assert features.acpl_by_phase.opening == 10.0
    assert features.acpl_by_phase.middlegame == 30.0
    assert features.acpl_by_phase.endgame == 200.0
    assert features.worst_phase == "endgame"
    assert features.worst_phase_margin == 120.0  # 200.0 - 80.0


# ---------------------------------------------------------------------------
# 4. accuracy_trend
# ---------------------------------------------------------------------------


def _games_with_per_game_acpl(db_session, values: list[float], username: str) -> list[Game]:
    games = []
    for i, value in enumerate(values):
        game = _insert_player_and_game(
            db_session,
            played_at=_BASE_TIME + dt.timedelta(minutes=i),
            username=username,
        )
        _insert_rows(db_session, game, [{"cp_loss": value, "classification": "ok"}])
        games.append(game)
    return games


def test_accuracy_trend_insufficient_data_below_min_games(db_session):
    games = _games_with_per_game_acpl(db_session, [20, 20, 20], username="trend_a")
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)
    assert len(games) < settings.FEATURE_TREND_MIN_GAMES
    assert features.accuracy_trend == "insufficient_data"


def test_accuracy_trend_declining(db_session):
    # First half ACPL 20, second half ACPL 100 -> s (100) > f (20) * 1.10 (22) -> declining.
    values = [20, 20, 20, 20, 100, 100, 100, 100]
    games = _games_with_per_game_acpl(db_session, values, username="trend_b")
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)
    assert features.accuracy_trend == "declining"


def test_accuracy_trend_improving(db_session):
    # First half ACPL 100, second half ACPL 20 -> s (20) < f (100) * 0.90 (90) -> improving.
    values = [100, 100, 100, 100, 20, 20, 20, 20]
    games = _games_with_per_game_acpl(db_session, values, username="trend_c")
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)
    assert features.accuracy_trend == "improving"


def test_accuracy_trend_flat(db_session):
    # First half ACPL 50, second half ACPL 52: 52 is within [45, 55] (10% band) -> flat.
    values = [50, 50, 50, 50, 52, 52, 52, 52]
    games = _games_with_per_game_acpl(db_session, values, username="trend_d")
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)
    assert features.accuracy_trend == "flat"


# ---------------------------------------------------------------------------
# 5. endgame_conversion
# ---------------------------------------------------------------------------


def test_endgame_conversion_exact_fraction_of_qualifying_games(db_session):
    won = _insert_player_and_game(
        db_session, color="white", result="win", played_at=_BASE_TIME, username="endgame_a"
    )
    _insert_rows(
        db_session,
        won,
        [{"ply": 30, "cp_loss": 0, "classification": "ok", "phase": "endgame", "eval_cp_before": 250}],
    )

    lost = _insert_player_and_game(
        db_session,
        color="white",
        result="loss",
        played_at=_BASE_TIME + dt.timedelta(minutes=1),
        username="endgame_a",
    )
    _insert_rows(
        db_session,
        lost,
        [{"ply": 32, "cp_loss": 0, "classification": "ok", "phase": "endgame", "eval_cp_before": 300}],
    )

    games = [won, lost]
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)

    assert features.endgame_conversion == 0.5  # 1 win / 2 qualifying games
    assert features.endgame_conversion_evidence == [(str(lost.id), 32)]


def test_endgame_conversion_none_when_zero_qualifying_games(db_session):
    game = _insert_player_and_game(
        db_session, color="white", result="win", played_at=_BASE_TIME, username="endgame_b"
    )
    # Reaches an endgame, but only barely ahead (< FEATURE_ENDGAME_AHEAD_CP) -> not qualifying.
    _insert_rows(
        db_session,
        game,
        [{"ply": 30, "cp_loss": 0, "classification": "ok", "phase": "endgame", "eval_cp_before": 50}],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=None)
    assert features.endgame_conversion is None
    assert features.endgame_conversion_evidence == []


# ---------------------------------------------------------------------------
# 6. opening_leak_rate (including a black game, to exercise player_pov_eval)
# ---------------------------------------------------------------------------


def test_opening_leak_rate_and_evidence(db_session):
    leaking_white = _insert_player_and_game(
        db_session, color="white", played_at=_BASE_TIME, username="leak"
    )
    _insert_rows(
        db_session,
        leaking_white,
        [{"ply": 20, "cp_loss": 0, "classification": "ok", "eval_cp_after": -200}],
    )

    fine_white = _insert_player_and_game(
        db_session, color="white", played_at=_BASE_TIME + dt.timedelta(minutes=1), username="leak"
    )
    _insert_rows(
        db_session,
        fine_white,
        [{"ply": 20, "cp_loss": 0, "classification": "ok", "eval_cp_after": -50}],
    )

    # Black game: White-POV eval of +180 means the BLACK player is down 180 ->
    # player_pov_eval flips the sign, so this counts as a leak too.
    leaking_black = _insert_player_and_game(
        db_session,
        color="black",
        played_at=_BASE_TIME + dt.timedelta(minutes=2),
        username="leak",
    )
    _insert_rows(
        db_session,
        leaking_black,
        [{"ply": 20, "cp_loss": 0, "classification": "ok", "eval_cp_after": 180}],
    )

    games = [leaking_white, fine_white, leaking_black]
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)

    assert features.opening_leak_rate == 0.67  # round(2/3, 2)
    # Sorted most-negative-first: leaking_white (-200) then leaking_black (-180).
    assert features.opening_leak_evidence == [
        (str(leaking_white.id), 20),
        (str(leaking_black.id), 20),
    ]


# ---------------------------------------------------------------------------
# 7. color split
# ---------------------------------------------------------------------------


def test_color_split_low_signal_and_differs_from_overall(db_session):
    white_games = []
    for i in range(4):
        g = _insert_player_and_game(
            db_session,
            color="white",
            played_at=_BASE_TIME + dt.timedelta(minutes=i),
            username="colorsplit",
        )
        _insert_rows(db_session, g, [{"cp_loss": 300, "classification": "blunder"}])
        white_games.append(g)

    black_games = []
    for i in range(2):
        g = _insert_player_and_game(
            db_session,
            color="black",
            played_at=_BASE_TIME + dt.timedelta(minutes=10 + i),
            username="colorsplit",
        )
        _insert_rows(db_session, g, [{"cp_loss": 20, "classification": "ok"}])
        black_games.append(g)

    games = white_games + black_games
    features = build_features(games, _evals_for(db_session, *games), rating_snapshot=None)

    assert set(features.by_color) == {"white", "black"}
    assert features.by_color["white"].low_signal is False  # 4 games, not < FEATURE_COLOR_MIN_GAMES (4)
    assert features.by_color["black"].low_signal is True  # 2 games < 4
    assert features.by_color["white"].blunders_per_game == 1.0  # 4 blunders / 4 white games
    assert features.by_color["black"].blunders_per_game == 0.0  # 0 blunders / 2 black games
    # Overall = 4 blunders / 6 games = 0.6667 -> 0.7, distinct from both per-color numbers.
    assert features.blunders_per_game == 0.7
    assert features.blunders_per_game not in (
        features.by_color["white"].blunders_per_game,
        features.by_color["black"].blunders_per_game,
    )


# ---------------------------------------------------------------------------
# 8. Real-fixture sanity test (still offline, via FixtureEvaluator)
# ---------------------------------------------------------------------------


def _build_fixture_game(db_session, stem: str) -> Game:
    pgn = load_fixture("pgn", f"{stem}.pgn")
    headers = chess.pgn.read_game(io.StringIO(pgn)).headers
    player = Player(platform="chesscom", username=headers.get("White", "u").lower())
    db_session.add(player)
    db_session.commit()
    game = Game(
        player_id=player.id,
        platform_game_id=headers.get("Link", stem),
        game_url=headers.get("Link", ""),
        pgn=pgn,
        time_class="blitz",
        player_color="white",
        result="win",
    )
    db_session.add(game)
    db_session.commit()
    return game


def test_build_features_over_real_fixture_is_structurally_sane(db_session):
    stem = "gt_lostendgame"
    game = _build_fixture_game(db_session, stem)
    rows = analyze_game(game, FixtureEvaluator(stem, cache_session=db_session), db_session)

    features = build_features([game], {str(game.id): rows}, rating_snapshot=1500)

    assert features.games_analyzed == 1
    assert "white" in features.by_color
    assert features.endgame_conversion is None or isinstance(features.endgame_conversion, float)
    assert features.acpl_overall is not None and features.acpl_overall > 0
    assert features.accuracy_trend == "insufficient_data"  # only 1 game, well under the min
