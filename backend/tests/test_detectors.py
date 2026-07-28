"""Session 13 offline tests for app/detectors.py — six pattern detectors +
the SEE helper they share, all pure aggregation over hand-built move_evals
rows in the in-memory test database (no engine, no network: same discipline
as test_features.py, whose insert helpers this module reuses directly).

Every detector gets at least one POSITIVE (fired=True) and one NEGATIVE
(fired=False) case, chosen to sit right at the detector's own threshold
guard so the test actually exercises the boundary, not just "obviously yes"
vs "obviously no".
"""

import datetime as dt
import uuid

import chess
import pytest

from app.config import settings
from app.detectors import (
    _game_eco,
    _remaining_clock_by_ply,
    _see,
    detect_dawdling,
    detect_hung_pieces,
    detect_late_collapse,
    detect_opening_leak,
    detect_overextension,
    detect_rushed_blunders,
    detect_tilt,
    detect_time_class_split,
    detect_time_trouble_collapse,
    detect_turning_point,
    run_detectors,
)
from app.features import build_features
from app.models import Game, MoveEval, Player
from tests.test_features import _evals_for, _insert_player_and_game, _insert_rows

_BASE_TIME = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# _see — direct unit tests, explicit FENs (values pinned down by hand)
# ---------------------------------------------------------------------------


def test_see_free_undefended_piece_returns_its_full_value():
    # White bishop e4 captures an undefended black knight on d5.
    board = chess.Board("4k3/8/8/3n4/4B3/8/8/4K3 w - - 0 1")
    move = board.parse_san("Bxd5")
    assert _see(board, move) == 300  # knight's value, nothing recaptures


def test_see_equal_trade_nets_zero():
    # White pawn e4 takes black pawn d5; black pawn c6 recaptures. A clean
    # 1-for-1 trade nets 0 regardless of which piece values were exchanged.
    board = chess.Board("4k3/8/2p5/3p4/4P3/8/8/4K3 w - - 0 1")
    move = board.parse_san("exd5")
    assert _see(board, move) == 0


def test_see_winning_the_exchange_rook_for_bishop():
    # White bishop c3 captures a rook on d4 that's defended only by a pawn
    # on c5. Net: +500 (rook) - 300 (bishop lost to the recapture) = +200.
    board = chess.Board("4k3/8/8/2p5/3r4/2B5/8/4K3 w - - 0 1")
    move = board.parse_san("Bxd4")
    assert _see(board, move) == 200


# ---------------------------------------------------------------------------
# _remaining_clock_by_ply
# ---------------------------------------------------------------------------


def _fmt_hms(seconds: int) -> str:
    """Format seconds as H:MM:SS for PGN [%clk] comments."""
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _build_pgn_with_clocks(moves: list[str], clocks: list[int | None]) -> str:
    """A legal PGN whose mainline is `moves` and whose clock comments are
    taken from `clocks` (remaining seconds after each move)."""
    parts: list[str] = []
    for i, (san, clk) in enumerate(zip(moves, clocks), start=1):
        clk_str = _fmt_hms(clk) if clk is not None else "0:00:00"
        if i % 2 == 1:
            parts.append(f"{(i + 1) // 2}. {san} {{[%clk {clk_str}]}}")
        else:
            parts.append(f"{san} {{[%clk {clk_str}]}}")
    return (
        '[Event "Test"]\n'
        '[Site "?"]\n'
        '[Date "2026.07.26"]\n'
        '[Round "?"]\n'
        '[White "White"]\n'
        '[Black "Black"]\n'
        '[Result "*"]\n\n'
        f'{" ".join(parts)} *'
    )


def _make_clocked_game(
    db_session,
    player,
    *,
    moves: list[str],
    clocks: list[int | None],
    row_specs: list[dict] | None = None,
    time_class: str = "blitz",
    player_color: str = "white",
    played_at=None,
    i: int = 0,
) -> Game:
    """Insert a Game with a real PGN carrying [%clk] comments, plus matching
    MoveEval rows. `row_specs` controls classification, seconds_spent, and any
    per-row overrides (fen_before, move_san, cp_loss)."""
    pgn = _build_pgn_with_clocks(moves, clocks)
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn=pgn,
        time_class=time_class,
        player_color=player_color,
        result="loss",
        played_at=played_at or (_BASE_TIME + dt.timedelta(minutes=i)),
    )
    db_session.add(game)
    db_session.commit()

    # Replay the moves to get the real fen_before for each ply.
    board = chess.Board()
    computed_fens: list[str] = []
    for san in moves:
        computed_fens.append(board.fen())
        board.push_san(san)

    if row_specs is None:
        row_specs = [{"classification": "ok", "seconds_spent": 0} for _ in moves]

    for idx, spec in enumerate(row_specs):
        ply = spec.get("ply", idx + 1)
        move_san = spec.get("move_san", moves[idx])
        fen_before = spec.get("fen_before", computed_fens[idx])
        classification = spec["classification"]
        cp_loss_val = spec.get(
            "cp_loss",
            300 if classification == "blunder" else (100 if classification == "mistake" else 0),
        )
        db_session.add(
            MoveEval(
                game_id=game.id,
                ply=ply,
                move_san=move_san,
                fen_before=fen_before,
                eval_cp_before=spec.get("eval_cp_before", 0),
                eval_cp_after=spec.get("eval_cp_after", 0),
                cp_loss=cp_loss_val,
                best_move_san=spec.get("best_move_san", move_san),
                classification=classification,
                phase=spec.get("phase", "opening"),
                seconds_spent=spec.get("seconds_spent"),
            )
        )
    db_session.commit()
    return game


# ---------------------------------------------------------------------------
# _game_eco
# ---------------------------------------------------------------------------


def test_game_eco_reads_from_pgn_tag_when_opening_eco_column_is_none():
    game = Game(
        pgn='[ECO "B07"]\n\n1. e4 d6 *\n',
        opening_eco=None,
        player_color="white",
        result="loss",
        time_class="blitz",
        platform_game_id="x",
        game_url="u",
    )
    assert _game_eco(game) == "B07"


# ---------------------------------------------------------------------------
# run_detectors — shape sanity (all nine keys, safe on zero games)
# ---------------------------------------------------------------------------


def test_run_detectors_returns_all_ten_keys_and_is_safe_on_empty_input():
    result = run_detectors([], {})
    assert set(result) == {
        "hung_pieces",
        "late_collapse",
        "opening_leak",
        "overextension",
        "time_class_split",
        "turning_point",
        "rushed_blunders",
        "time_trouble_collapse",
        "dawdling",
        "tilt",
    }
    for detector in result.values():
        assert detector["fired"] is False


# ---------------------------------------------------------------------------
# 1. hung_pieces
# ---------------------------------------------------------------------------


def _make_hung_pieces_game(db_session, player, *, reply_fen, reply_best_move, i=0):
    """One game: a single player blunder at ply 1, followed by an opponent
    reply row at ply 2 whose fen_before/best_move_san the test controls
    directly (hung_pieces is the one detector that actually replays a real
    chess position, so it needs a real board, unlike the others below)."""
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class="blitz",
        player_color="white",
        result="loss",
        played_at=_BASE_TIME + dt.timedelta(minutes=i),
    )
    db_session.add(game)
    db_session.commit()
    rows = [
        MoveEval(
            game_id=game.id,
            ply=1,
            move_san="e4",
            fen_before=chess.STARTING_FEN,
            eval_cp_before=0,
            eval_cp_after=0,
            cp_loss=300,
            best_move_san="e4",
            classification="blunder",
            phase="opening",
        ),
        MoveEval(
            game_id=game.id,
            ply=2,
            move_san="e5",
            fen_before=reply_fen,
            eval_cp_before=0,
            eval_cp_after=-300,
            cp_loss=300,
            best_move_san=reply_best_move,
            classification="blunder",
            phase="opening",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return game


def test_detect_hung_pieces_fires_when_blunder_immediately_hangs_material(db_session):
    player = Player(platform="chesscom", username="hung_pos")
    db_session.add(player)
    db_session.commit()

    # Black to move, best reply Bxd5 captures an undefended white knight —
    # SEE = 300 >= DET_SEE_MINOR_CP, so the player's only blunder "hung" it.
    game = _make_hung_pieces_game(
        db_session,
        player,
        reply_fen="4k3/8/8/3N4/4b3/8/8/4K3 b - - 0 1",
        reply_best_move="Bxd5",
    )
    result = detect_hung_pieces([game], _evals_for(db_session, game))

    assert result["fired"] is True
    assert result["stats"]["player_blunders"] == 1
    assert result["stats"]["hung_count"] == 1
    assert result["stats"]["hang_pct"] == 100.0
    assert result["evidence"] == [(str(game.id), 1)]


def test_detect_hung_pieces_does_not_fire_when_reply_is_not_a_capture(db_session):
    player = Player(platform="chesscom", username="hung_neg")
    db_session.add(player)
    db_session.commit()

    # Same shape, but the opponent's best reply is a quiet bishop move — not
    # a capture at all, so nothing counts as "hung".
    game = _make_hung_pieces_game(
        db_session,
        player,
        reply_fen="4k3/8/8/8/4b3/8/8/4K3 b - - 0 1",
        reply_best_move="Bd5",
    )
    result = detect_hung_pieces([game], _evals_for(db_session, game))

    assert result["fired"] is False
    assert result["stats"]["player_blunders"] == 1
    assert result["stats"]["hung_count"] == 0
    assert result["evidence"] == []


# ---------------------------------------------------------------------------
# 2. late_collapse
# ---------------------------------------------------------------------------


def test_detect_late_collapse_fires_when_late_rate_far_exceeds_early_rate(db_session):
    # 5 early player moves (plies 1-9), 1 blunder -> early_rate = 0.2.
    # 5 late player moves (plies 31-39, all > DET_LATE_PLY=30), all
    # blunders -> late_rate = 1.0 = 5x early_rate (>= DET_LATE_RATIO=2.0),
    # and late_blunders (5) >= DET_LATE_MIN_BLUNDERS (4).
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME, username="late_pos")
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok"},
            {"ply": 3, "cp_loss": 0, "classification": "ok"},
            {"ply": 5, "cp_loss": 300, "classification": "blunder"},
            {"ply": 7, "cp_loss": 0, "classification": "ok"},
            {"ply": 9, "cp_loss": 0, "classification": "ok"},
            {"ply": 31, "cp_loss": 300, "classification": "blunder"},
            {"ply": 33, "cp_loss": 300, "classification": "blunder"},
            {"ply": 35, "cp_loss": 300, "classification": "blunder"},
            {"ply": 37, "cp_loss": 300, "classification": "blunder"},
            {"ply": 39, "cp_loss": 300, "classification": "blunder"},
        ],
    )
    result = detect_late_collapse([game], _evals_for(db_session, game))

    assert result["fired"] is True
    assert result["stats"]["late_blunders"] == 5
    assert result["stats"]["late_ratio"] == 5.0


def test_detect_late_collapse_does_not_fire_below_min_blunder_count(db_session):
    # Same rate shape (late_rate = 5x early_rate) but only 2 late blunders,
    # below DET_LATE_MIN_BLUNDERS (4) -> the count guard blocks firing even
    # though the ratio alone would qualify.
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME, username="late_neg")
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok"},
            {"ply": 3, "cp_loss": 0, "classification": "ok"},
            {"ply": 5, "cp_loss": 300, "classification": "blunder"},
            {"ply": 7, "cp_loss": 0, "classification": "ok"},
            {"ply": 9, "cp_loss": 0, "classification": "ok"},
            {"ply": 31, "cp_loss": 300, "classification": "blunder"},
            {"ply": 33, "cp_loss": 300, "classification": "blunder"},
        ],
    )
    result = detect_late_collapse([game], _evals_for(db_session, game))

    assert result["fired"] is False
    assert result["stats"]["late_blunders"] == 2


# ---------------------------------------------------------------------------
# 3. opening_leak
# ---------------------------------------------------------------------------


def _make_eco_game(db_session, player, eco, ply15_eval, i):
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn=f'[ECO "{eco}"]\n\n1. e4 e5 *\n',
        time_class="blitz",
        player_color="white",
        result="loss",
        played_at=_BASE_TIME + dt.timedelta(minutes=i),
    )
    db_session.add(game)
    db_session.commit()
    db_session.add(
        MoveEval(
            game_id=game.id,
            ply=15,
            move_san="e4",
            fen_before=chess.STARTING_FEN,
            eval_cp_before=0,
            eval_cp_after=ply15_eval,
            cp_loss=0,
            best_move_san="e4",
            classification="ok",
            phase="opening",
        )
    )
    db_session.commit()
    return game


def test_detect_opening_leak_fires_for_a_consistently_leaking_eco_family(db_session):
    player = Player(platform="chesscom", username="leak_pos")
    db_session.add(player)
    db_session.commit()

    # 5 games (== DET_OPENING_FAMILY_MIN_GAMES), all family "B0" (B01/B02/
    # .../B05), each already -100 (white POV) by ply 15 -> avg -100, well
    # past -DET_OPENING_LEAK_CP (-40).
    games = [
        _make_eco_game(db_session, player, f"B0{n}", -100, i=n) for n in range(1, 6)
    ]
    evals = _evals_for(db_session, *games)
    result = detect_opening_leak(games, evals)

    assert result["fired"] is True
    assert result["stats"]["family"] == "B0"
    assert result["stats"]["avg_cp"] == -100.0
    assert result["stats"]["game_count"] == 5  # full family size, for the coach's "{k} games"
    assert len(result["evidence"]) == 3  # but evidence honors the up-to-3 contract


def test_detect_opening_leak_does_not_fire_when_family_is_only_mildly_worse(db_session):
    player = Player(platform="chesscom", username="leak_neg")
    db_session.add(player)
    db_session.commit()

    # Same family size, but only -10 on average by ply 15 -> above the
    # -40 threshold, not a real leak.
    games = [
        _make_eco_game(db_session, player, f"B0{n}", -10, i=n) for n in range(1, 6)
    ]
    evals = _evals_for(db_session, *games)
    result = detect_opening_leak(games, evals)

    assert result["fired"] is False
    assert result["stats"] == {}
    assert result["evidence"] == []


# ---------------------------------------------------------------------------
# 4. overextension
# ---------------------------------------------------------------------------


def _make_overextension_game(db_session, player, i):
    """A player pawn push to e6 (White's 6th rank) at ply 5, followed one
    ply later by a 200cp drop in the player's own POV eval — within
    DET_OVEREXT_WINDOW (6) and past DET_OVEREXT_DROP_CP (150)."""
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class="blitz",
        player_color="white",
        result="loss",
        played_at=_BASE_TIME + dt.timedelta(minutes=i),
    )
    db_session.add(game)
    db_session.commit()
    rows = [
        MoveEval(
            game_id=game.id,
            ply=5,
            move_san="e6",
            fen_before=chess.STARTING_FEN,
            eval_cp_before=0,
            eval_cp_after=0,
            cp_loss=0,
            best_move_san="e6",
            classification="ok",
            phase="middlegame",
        ),
        MoveEval(
            game_id=game.id,
            ply=6,
            move_san="Nf3",
            fen_before=chess.STARTING_FEN,
            eval_cp_before=0,
            eval_cp_after=-200,
            cp_loss=0,
            best_move_san="Nf3",
            classification="ok",
            phase="middlegame",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return game


def test_detect_overextension_fires_at_the_minimum_occurrence_count(db_session):
    player = Player(platform="chesscom", username="overext_pos")
    db_session.add(player)
    db_session.commit()

    # 3 games, each with one qualifying occurrence == DET_OVEREXT_MIN (3).
    games = [_make_overextension_game(db_session, player, i) for i in range(3)]
    evals = _evals_for(db_session, *games)
    result = detect_overextension(games, evals)

    assert result["fired"] is True
    assert result["stats"]["confidence"] == "low"
    assert result["stats"]["occurrences"] == 3


def test_detect_overextension_does_not_fire_below_minimum_occurrence_count(db_session):
    player = Player(platform="chesscom", username="overext_neg")
    db_session.add(player)
    db_session.commit()

    # Only 2 games (occurrences) — below DET_OVEREXT_MIN (3).
    games = [_make_overextension_game(db_session, player, i) for i in range(2)]
    evals = _evals_for(db_session, *games)
    result = detect_overextension(games, evals)

    assert result["fired"] is False
    assert result["stats"]["occurrences"] == 2


# ---------------------------------------------------------------------------
# 5. time_class_split
# ---------------------------------------------------------------------------


def _make_tc_game(db_session, player, i, time_class, blunder):
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class=time_class,
        player_color="white",
        result="loss",
        played_at=_BASE_TIME + dt.timedelta(minutes=i),
    )
    db_session.add(game)
    db_session.commit()
    cls = "blunder" if blunder else "ok"
    db_session.add(
        MoveEval(
            game_id=game.id,
            ply=1,
            move_san="e4",
            fen_before=chess.STARTING_FEN,
            eval_cp_before=0,
            eval_cp_after=0,
            cp_loss=300 if blunder else 0,
            best_move_san="e4",
            classification=cls,
            phase="opening",
        )
    )
    db_session.commit()
    return game


def test_detect_time_class_split_fires_when_blitz_blunders_far_more_than_rapid(db_session):
    player = Player(platform="chesscom", username="tc_pos")
    db_session.add(player)
    db_session.commit()

    # 5 blitz games, every one a player blunder -> blitz_bpg = 1.0.
    # 5 rapid games, only 1 blunders -> rapid_bpg = 0.2. Ratio 5x >= 1.8.
    blitz = [_make_tc_game(db_session, player, i, "blitz", True) for i in range(5)]
    rapid = [_make_tc_game(db_session, player, 10 + i, "rapid", i == 0) for i in range(5)]
    games = blitz + rapid
    result = detect_time_class_split(games, _evals_for(db_session, *games))

    assert result["fired"] is True
    assert result["stats"]["blitz_bpg"] == 1.0
    assert result["stats"]["rapid_bpg"] == 0.2
    assert result["stats"]["blitz_games"] == 5
    assert result["stats"]["rapid_games"] == 5


def test_detect_time_class_split_does_not_fire_when_rates_are_comparable(db_session):
    player = Player(platform="chesscom", username="tc_neg")
    db_session.add(player)
    db_session.commit()

    # Both classes blunder at the same rate (1.0) -> ratio 1x < 1.8.
    blitz = [_make_tc_game(db_session, player, i, "blitz", True) for i in range(5)]
    rapid = [_make_tc_game(db_session, player, 10 + i, "rapid", True) for i in range(5)]
    games = blitz + rapid
    result = detect_time_class_split(games, _evals_for(db_session, *games))

    assert result["fired"] is False


# ---------------------------------------------------------------------------
# 6. turning_point
# ---------------------------------------------------------------------------


def test_detect_turning_point_fires_for_a_slide_not_a_single_blunder(db_session):
    """The eval trajectory (player-POV, white) crosses permanently below
    -DET_PLAYABLE_CP (-150) at ply 6 (an OPPONENT ply, since player_color
    is white and 6 is even) — so the PONR can never coincide with the
    player's own worst blunder (necessarily an odd ply), guaranteeing this
    game 'qualifies' as a slide rather than a single-blunder loss."""
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME, username="ponr_pos")
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok", "eval_cp_after": 50},
            {"ply": 2, "cp_loss": 0, "classification": "ok", "eval_cp_after": 30},
            {"ply": 3, "cp_loss": 0, "classification": "ok", "eval_cp_after": 20},
            {"ply": 4, "cp_loss": 0, "classification": "ok", "eval_cp_after": -20},
            {"ply": 5, "cp_loss": 100, "classification": "mistake", "eval_cp_after": -100},
            {"ply": 6, "cp_loss": 0, "classification": "ok", "eval_cp_after": -160},
            {"ply": 7, "cp_loss": 0, "classification": "ok", "eval_cp_after": -200},
            {"ply": 8, "cp_loss": 0, "classification": "ok", "eval_cp_after": -170},
            {"ply": 9, "cp_loss": 250, "classification": "blunder", "eval_cp_after": -300},
            {"ply": 10, "cp_loss": 0, "classification": "ok", "eval_cp_after": -400},
        ],
    )
    evals = _evals_for(db_session, game)
    result = detect_turning_point([game], evals)

    assert result["stats"]["ponr_by_game"][str(game.id)] == 6
    assert result["fired"] is True
    assert result["stats"]["qualifying_games"] == 1
    assert (str(game.id), 6) in result["evidence"]


def test_detect_turning_point_does_not_qualify_when_ponr_is_the_single_blunder(db_session):
    """The single player blunder at ply 5 IS the PONR (the eval only drops
    for good on that exact move) and is also the player's largest cp_loss —
    a one-move loss, not a slide, so this game must NOT count toward
    'fired'/evidence even though it still gets a PONR in ponr_by_game."""
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME, username="ponr_neg")
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok", "eval_cp_after": 50},
            {"ply": 2, "cp_loss": 0, "classification": "ok", "eval_cp_after": 40},
            {"ply": 3, "cp_loss": 0, "classification": "ok", "eval_cp_after": 30},
            {"ply": 4, "cp_loss": 0, "classification": "ok", "eval_cp_after": 20},
            {"ply": 5, "cp_loss": 700, "classification": "blunder", "eval_cp_after": -300},
            {"ply": 6, "cp_loss": 0, "classification": "ok", "eval_cp_after": -350},
        ],
    )
    evals = _evals_for(db_session, game)
    result = detect_turning_point([game], evals)

    assert result["stats"]["ponr_by_game"][str(game.id)] == 5
    assert result["fired"] is False
    assert result["stats"]["qualifying_games"] == 0
    assert result["evidence"] == []


# ---------------------------------------------------------------------------
# meaningful_blunders_per_game — the blunder-inflation fix, end to end
# ---------------------------------------------------------------------------


def test_meaningful_blunders_per_game_excludes_blunders_after_the_ponr(db_session):
    """A lost game with one player blunder BEFORE the PONR and one AFTER it:
    blunders_per_game counts both (2/game); meaningful_blunders_per_game
    must exclude the post-PONR one (1/game)."""
    game = _insert_player_and_game(db_session, played_at=_BASE_TIME, username="meaningful")
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 0, "classification": "ok", "eval_cp_after": 50},
            {"ply": 2, "cp_loss": 0, "classification": "ok", "eval_cp_after": 40},
            # Pre-PONR player blunder — eval after it (-100) is still
            # "playable" (> -150), so the game isn't decided yet.
            {"ply": 3, "cp_loss": 300, "classification": "blunder", "eval_cp_after": -100},
            # Opponent's move tips it permanently past -150 -> PONR = ply 4.
            {"ply": 4, "cp_loss": 0, "classification": "ok", "eval_cp_after": -200},
            # Post-PONR player blunder — already-lost noise.
            {"ply": 5, "cp_loss": 250, "classification": "blunder", "eval_cp_after": -300},
            {"ply": 6, "cp_loss": 0, "classification": "ok", "eval_cp_after": -320},
        ],
    )
    features = build_features([game], _evals_for(db_session, game), rating_snapshot=None)

    assert features.detectors["turning_point"]["stats"]["ponr_by_game"][str(game.id)] == 4
    assert features.blunders_per_game == 2.0
    assert features.meaningful_blunders_per_game == 1.0


# ---------------------------------------------------------------------------
# 7. rushed_blunders
# ---------------------------------------------------------------------------


def test_detect_rushed_blunders_fires_when_most_blunders_are_low_clock(db_session):
    player = Player(platform="chesscom", username="rushed_pos")
    db_session.add(player)
    db_session.commit()

    # 5 games, each with one player blunder at a low remaining clock.
    # clocked_blunders = 5 (>= DET_TIME_RUSH_MIN_BLUNDERS=4) and share = 1.0.
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[10, 180, 170, 160],  # ply 1 is the player's blunder, 10s left
            row_specs=[
                {"classification": "blunder", "seconds_spent": 2},
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_rushed_blunders(games, _evals_for(db_session, *games))
    assert result["fired"] is True
    assert result["stats"]["clocked_blunders"] == 5
    assert result["stats"]["rushed"] == 5
    assert result["stats"]["share"] == 1.0
    assert len(result["evidence"]) == 3


def test_detect_rushed_blunders_does_not_fire_when_share_below_threshold(db_session):
    player = Player(platform="chesscom", username="rushed_neg")
    db_session.add(player)
    db_session.commit()

    # 5 blunders, all with plenty of time — share 0 < DET_TIME_RUSH_MIN_SHARE (0.40).
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[60, 180, 170, 160],
            row_specs=[
                {"classification": "blunder", "seconds_spent": 20},
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_rushed_blunders(games, _evals_for(db_session, *games))
    assert result["fired"] is False
    assert result["stats"]["clocked_blunders"] == 5
    assert result["stats"]["rushed"] == 0
    assert result["stats"]["share"] == 0.0


# ---------------------------------------------------------------------------
# 8. time_trouble_collapse
# ---------------------------------------------------------------------------


def test_detect_time_trouble_collapse_fires_when_low_clock_errors_spike(db_session):
    player = Player(platform="chesscom", username="trouble_pos")
    db_session.add(player)
    db_session.commit()

    # 5 games: normal player ply is clean (120s), low-clock player ply is a blunder (10s).
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[120, 180, 10, 160],
            row_specs=[
                {"classification": "ok", "seconds_spent": 5},        # ply 1: normal, clean
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "blunder", "seconds_spent": 2},   # ply 3: low-clock, error
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_time_trouble_collapse(games, _evals_for(db_session, *games))
    assert result["fired"] is True
    assert result["stats"]["games_in_trouble"] == 5
    assert result["stats"]["rate_low"] == 1.0
    assert result["stats"]["rate_normal"] == 0.0
    assert len(result["evidence"]) == 3


def test_detect_time_trouble_collapse_does_not_fire_when_rates_are_equal(db_session):
    player = Player(platform="chesscom", username="trouble_neg")
    db_session.add(player)
    db_session.commit()

    # 5 games: an error at both normal and low clock, so rates are equal (1.0 each).
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[120, 180, 10, 160],
            row_specs=[
                {"classification": "mistake", "seconds_spent": 5},    # normal, error
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "mistake", "seconds_spent": 2},   # low, error
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_time_trouble_collapse(games, _evals_for(db_session, *games))
    assert result["fired"] is False
    assert result["stats"]["rate_low"] == 1.0
    assert result["stats"]["rate_normal"] == 1.0


# ---------------------------------------------------------------------------
# 9. dawdling
# ---------------------------------------------------------------------------

# A position with only one legal king move — well under the complexity gate.
_DAWDLE_FEN = "8/8/8/8/8/8/5k2/7K w - - 0 1"


def test_detect_dawdling_fires_when_ok_moves_waste_time_before_trouble(db_session):
    player = Player(platform="chesscom", username="dawdle_pos")
    db_session.add(player)
    db_session.commit()

    # 5 games: a long think on a simple position (20 legal moves gate not needed,
    # this position has 1), then later the player drops under 30s.
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[120, 180, 20, 160],  # ply 3 is the low-clock player ply
            row_specs=[
                {
                    "classification": "ok",
                    "seconds_spent": 25,  # dawdled
                    "move_san": "Kh2",
                    "fen_before": _DAWDLE_FEN,
                },
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 2},  # time-trouble ply
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_dawdling(games, _evals_for(db_session, *games))
    assert result["fired"] is True
    assert result["stats"]["game_count"] == 5
    assert result["stats"]["avg_dawdle_seconds"] == 25.0
    assert len(result["evidence"]) == 3


def test_detect_dawdling_does_not_fire_without_later_time_trouble(db_session):
    player = Player(platform="chesscom", username="dawdle_neg")
    db_session.add(player)
    db_session.commit()

    # 5 games with a long think on a simple position, but the clock never drops low.
    games = []
    for i in range(5):
        g = _make_clocked_game(
            db_session,
            player,
            moves=["e4", "e5", "Nf3", "Nc6"],
            clocks=[120, 180, 120, 160],  # every ply stays above 30s
            row_specs=[
                {
                    "classification": "ok",
                    "seconds_spent": 25,
                    "move_san": "Kh2",
                    "fen_before": _DAWDLE_FEN,
                },
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
                {"classification": "ok", "seconds_spent": 3},
            ],
            i=i,
        )
        games.append(g)

    result = detect_dawdling(games, _evals_for(db_session, *games))
    assert result["fired"] is False
    assert result["stats"]["game_count"] == 0


# ---------------------------------------------------------------------------
# _remaining_clock_by_ply direct tests
# ---------------------------------------------------------------------------


def test_remaining_clock_by_ply_reads_pgn_clock_comments():
    player = Player(platform="chesscom", username="clock_reader")
    # No DB needed for this pure helper.
    game = Game(
        player_id=player.id,
        platform_game_id="x",
        game_url="u",
        pgn='[Event "Test"]\n\n1. e4 {[%clk 0:02:00]} e5 {[%clk 0:02:00]}',
        time_class="blitz",
        player_color="white",
        result="loss",
    )
    assert _remaining_clock_by_ply(game) == {1: 120, 2: 120}


def test_remaining_clock_by_ply_returns_none_when_no_clocks():
    player = Player(platform="chesscom", username="clockless")
    game = Game(
        player_id=player.id,
        platform_game_id="x",
        game_url="u",
        pgn="1. e4 e5",
        time_class="blitz",
        player_color="white",
        result="loss",
    )
    assert _remaining_clock_by_ply(game) == {1: None, 2: None}


# ---------------------------------------------------------------------------
# 10. tilt
# ---------------------------------------------------------------------------


def _make_tilt_game(db_session, *, username, i=0, classifications=None):
    """A white game with three player plies whose classifications are
    controlled by the caller. Defaults to a classic tilt sequence:
    mistake -> blunder (the compounding blunder)."""
    game = _insert_player_and_game(
        db_session, color="white", result="loss", played_at=_BASE_TIME + dt.timedelta(minutes=i), username=username
    )
    rows = classifications or ["mistake", "blunder", "ok"]
    _insert_rows(
        db_session,
        game,
        [
            {"ply": 1, "cp_loss": 100, "classification": rows[0]},
            {"ply": 3, "cp_loss": 300, "classification": rows[1]},
            {"ply": 5, "cp_loss": 0, "classification": rows[2] if len(rows) > 2 else "ok"},
        ],
    )
    return game


def test_detect_tilt_fires_at_minimum_game_count(db_session):
    games = [
        _make_tilt_game(db_session, username="tilt_pos", i=0),
        _make_tilt_game(db_session, username="tilt_pos", i=1),
        _make_tilt_game(db_session, username="tilt_pos", i=2),
    ]
    result = detect_tilt(games, _evals_for(db_session, *games))

    assert result["fired"] is True
    assert result["stats"]["tilt_games"] == 3
    assert result["stats"]["tilt_events"] == 3
    assert result["stats"]["games_analyzed"] == 3
    # Evidence cites the compounding (second) blunder, up to 3.
    assert len(result["evidence"]) == 3
    assert all(ply % 2 == 1 for _gid, ply in result["evidence"])


def test_detect_tilt_does_not_fire_below_min_games(db_session):
    games = [
        _make_tilt_game(db_session, username="tilt_min", i=0),
        _make_tilt_game(db_session, username="tilt_min", i=1),
    ]
    result = detect_tilt(games, _evals_for(db_session, *games))

    assert result["fired"] is False
    assert result["stats"]["tilt_games"] == 2
    assert result["stats"]["tilt_events"] == 2


def test_detect_tilt_ignores_non_consecutive_player_errors(db_session):
    """A lone blunder, or a mistake followed by a good move then a blunder,
    should not count as tilt — only back-to-back player moves."""
    game = _make_tilt_game(db_session, username="tilt_neg", classifications=["mistake", "ok", "blunder"])
    result = detect_tilt([game], _evals_for(db_session, game))

    assert result["fired"] is False
    assert result["stats"]["tilt_games"] == 0
    assert result["stats"]["tilt_events"] == 0
    assert result["evidence"] == []


def test_detect_tilt_ignores_blunders_separated_by_a_good_move(db_session):
    """Two player blunders with a good move in between are not a tilt event."""
    game = _make_tilt_game(db_session, username="tilt_sep", classifications=["blunder", "ok", "blunder"])
    result = detect_tilt([game], _evals_for(db_session, game))

    assert result["fired"] is False
    assert result["stats"]["tilt_games"] == 0
    assert result["stats"]["tilt_events"] == 0
    assert result["evidence"] == []
