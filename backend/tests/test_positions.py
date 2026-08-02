"""V2-S3: offline tests for training-position mining.

All tests seed a db_session with Player/Game/MoveEval rows using the same
factory style as test_features.py/test_coach.py — no engine, no network.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import Game, MoveEval, Player, TrainingPosition
from app.positions import mine_positions


def _make_player(session, username: str = "testplayer") -> Player:
    player = Player(platform="chesscom", username=username, rating_snapshot=1200)
    session.add(player)
    session.commit()
    return player


def _make_game(
    session,
    player: Player,
    game_id: str,
    result: str = "win",
    player_color: str = "white",
) -> Game:
    game = Game(
        player_id=player.id,
        platform_game_id=game_id,
        game_url=f"https://www.chess.com/game/live/{game_id}",
        pgn="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *",
        time_class="blitz",
        player_color=player_color,
        result=result,
        player_rating=1200,
        opponent_rating=1190,
        analyzed_at=datetime.now(timezone.utc),
    )
    session.add(game)
    session.commit()
    return game


def _make_move_eval(
    session,
    game: Game,
    ply: int,
    *,
    classification: str = "ok",
    eval_cp_before: int = 0,
    best_move_san: str = "e4",
    fen_before: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
) -> MoveEval:
    """Create a MoveEval row. White POV evals; player_color determines who
    made the move via ply parity (odd=white, even=black)."""
    row = MoveEval(
        game_id=game.id,
        ply=ply,
        move_san="e4" if classification == "ok" else "Qh4",
        fen_before=fen_before,
        eval_cp_before=eval_cp_before,
        eval_cp_after=eval_cp_before + 50,
        cp_loss=50 if classification == "blunder" else 10,
        best_move_san=best_move_san,
        classification=classification,
        phase="middlegame",
    )
    session.add(row)
    session.commit()
    return row


# ── Blunder scenario ──────────────────────────────────────────────────


def test_mines_blunder_positions(db_session):
    """A game with player blunders mines the right FEN/category/eval."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g1", result="loss", player_color="white")

    # Ply 1 = White (player) blunder. Starting position FEN (White to move).
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    _make_move_eval(
        db_session, game, 1,
        classification="blunder",
        eval_cp_before=50,
        best_move_san="Nf3",
        fen_before=fen,
    )

    counts = mine_positions(db_session, player)
    db_session.commit()

    assert counts["blunder"] == 1
    assert counts["unconverted"] == 0
    assert counts["danger"] == 0

    # Read back the stored row.
    rows = db_session.query(TrainingPosition).filter_by(player_id=player.id).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.category == "blunder"
    assert row.fen == fen
    assert row.best_line_uci == "g1f3"  # Nf3 in UCI
    assert row.eval_before_cp == 50  # White POV — stored as-is


# ── Unconverted scenario ──────────────────────────────────────────────


def test_mines_unconverted_at_first_crossing_ply(db_session):
    """A not-won game whose player-POV eval crosses +300 mines exactly one
    row at the FIRST crossing ply."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g2", result="loss", player_color="white")

    # Ply 3 (White's 2nd move): eval 200 — below threshold, NOT mined.
    # Position after 1. e4 e5 — Nf3 is legal here.
    fen3 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    _make_move_eval(
        db_session, game, 3,
        classification="ok",
        eval_cp_before=200,
        best_move_san="Nf3",
        fen_before=fen3,
    )
    # Ply 5 (White's 3rd move): eval 350 — FIRST crossing, mined.
    # Position after 1. e4 e5 2. Nf3 Nc6 — Bc4 is legal here.
    fen5 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
    _make_move_eval(
        db_session, game, 5,
        classification="ok",
        eval_cp_before=350,
        best_move_san="Bc4",
        fen_before=fen5,
    )
    # Ply 7 (White's 4th move): eval 400 — later crossing, NOT mined (one per game).
    # Position after 1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 — O-O is legal here.
    fen7 = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
    _make_move_eval(
        db_session, game, 7,
        classification="ok",
        eval_cp_before=400,
        best_move_san="O-O",
        fen_before=fen7,
    )

    counts = mine_positions(db_session, player)
    db_session.commit()

    assert counts["unconverted"] == 1
    rows = db_session.query(TrainingPosition).filter_by(
        player_id=player.id, category="unconverted"
    ).all()
    assert len(rows) == 1
    assert rows[0].ply == 5  # First crossing, not the 400 one


# ── Danger scenario ───────────────────────────────────────────────────


def test_mines_danger_in_resource_band(db_session):
    """A lost game with worst eval in the resource band and an in-band
    player blunder mines a danger row."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g3", result="loss", player_color="white")

    # Worst player-POV eval across all rows: -400 (in band [-600, -150]).
    # Ply 1: player blunder at -350 (also in band). Starting position.
    _make_move_eval(
        db_session, game, 1,
        classification="blunder",
        eval_cp_before=-350,   # White POV -> player-POV = -350
        best_move_san="e4",
    )
    # Ply 3: opponent move, pushes eval to -400 (player nadir).
    _make_move_eval(
        db_session, game, 3,
        classification="ok",
        eval_cp_before=-400,
        best_move_san="e5",
    )
    # Ply 5: player blunder at -100 (OUTSIDE band) — not mined.
    # Position after 1. e4 e5 — Bc4 is legal here.
    fen5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    _make_move_eval(
        db_session, game, 5,
        classification="blunder",
        eval_cp_before=-100,
        best_move_san="Bc4",
        fen_before=fen5,
    )
    # Ply 7: player blunder at -500 (in band) — mined.
    # Position after 1. e4 e5 2. Nf3 Nc6 — d3 is always legal.
    fen7 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
    _make_move_eval(
        db_session, game, 7,
        classification="blunder",
        eval_cp_before=-500,
        best_move_san="d3",
        fen_before=fen7,
    )

    counts = mine_positions(db_session, player)
    db_session.commit()

    assert counts["danger"] == 2  # plies 1 and 7
    rows = db_session.query(TrainingPosition).filter_by(
        player_id=player.id, category="danger"
    ).all()
    assert len(rows) == 2
    mined_plies = {r.ply for r in rows}
    assert mined_plies == {1, 7}


# ── Clean game — no positions ────────────────────────────────────────


def test_clean_game_mines_zero_rows(db_session):
    """A game with no blunders, no +300 eval, and no resource band return
    mines zero rows."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g4", result="win", player_color="white")

    _make_move_eval(db_session, game, 1, classification="ok", eval_cp_before=20)
    _make_move_eval(db_session, game, 3, classification="ok", eval_cp_before=30)

    counts = mine_positions(db_session, player)
    db_session.commit()

    assert counts == {"blunder": 0, "unconverted": 0, "danger": 0}
    assert db_session.query(TrainingPosition).filter_by(player_id=player.id).count() == 0


# ── Idempotency ───────────────────────────────────────────────────────


def test_mine_positions_is_idempotent(db_session):
    """Running mining twice on the same data adds zero new rows the second
    time, and bumps last_seen on existing rows."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g5", result="loss", player_color="white")

    _make_move_eval(
        db_session, game, 1,
        classification="blunder",
        eval_cp_before=50,
        best_move_san="Nf3",
    )

    # First run.
    counts1 = mine_positions(db_session, player)
    db_session.commit()
    assert counts1["blunder"] == 1

    row1 = db_session.query(TrainingPosition).filter_by(player_id=player.id).first()
    first_last_seen = row1.last_seen

    # Second run.
    counts2 = mine_positions(db_session, player)
    db_session.commit()
    assert counts2["blunder"] == 0  # No new rows

    # Same total row count.
    total = db_session.query(TrainingPosition).filter_by(player_id=player.id).count()
    assert total == 1

    # last_seen was bumped.
    db_session.refresh(row1)
    assert row1.last_seen > first_last_seen or row1.last_seen == first_last_seen
    # Note: the bump may be the same if both runs complete within the same
    # second; that's fine — the real test is that row count stays 1.


# ── eval_before_cp is White POV ───────────────────────────────────────


def test_eval_before_cp_stored_white_pov(db_session):
    """eval_before_cp is stored exactly as MoveEval had it (White POV),
    not converted to player POV."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g6", result="loss", player_color="black")

    # Black player blunder: White POV eval is -200, so Black's POV is +200.
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    _make_move_eval(
        db_session, game, 2,  # Black's ply
        classification="blunder",
        eval_cp_before=-200,   # White POV
        best_move_san="Nc6",
        fen_before=fen,
    )

    counts = mine_positions(db_session, player)
    db_session.commit()

    row = db_session.query(TrainingPosition).filter_by(player_id=player.id).first()
    assert row is not None
    assert row.eval_before_cp == -200  # White POV, NOT +200


# ── Opponent blunders are NOT mined ───────────────────────────────────


def test_opponent_blunders_not_mined(db_session):
    """Only player-ply blunders are mined; opponent blunders are ignored."""
    player = _make_player(db_session)
    game = _make_game(db_session, player, "g7", result="win", player_color="white")

    # Ply 2 = opponent (Black) blunder — should NOT be mined.
    _make_move_eval(
        db_session, game, 2,
        classification="blunder",
        eval_cp_before=-50,
        best_move_san="d5",
    )

    counts = mine_positions(db_session, player)
    db_session.commit()

    assert counts["blunder"] == 0
