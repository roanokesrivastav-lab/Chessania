"""Session 9 offline tests for the pure analysis helpers — no engine, no network,
no DB. cp_loss / classify / tag_phase / extract_move_times are deliberately pure
so their math can be pinned down here with hand-computed numbers (roadmap S9:
"the one perspective helper, tested to death")."""

import chess

from app.analysis import classify, cp_loss, extract_move_times, tag_phase

# ---------------------------------------------------------------------------
# cp_loss — all four quadrants, hand-computed, White's-POV inputs
# ---------------------------------------------------------------------------


def test_cp_loss_white_worsening():
    # White was +120, after their move it's -180 (White POV) -> White lost 300.
    assert cp_loss(120, -180, chess.WHITE) == 300


def test_cp_loss_white_improving_is_floored_to_zero():
    # White was +50, after their move +200 (better) -> no loss.
    assert cp_loss(50, 200, chess.WHITE) == 0


def test_cp_loss_black_worsening():
    # Black to move: White POV goes -50 -> +250, i.e. Black got 300cp worse.
    assert cp_loss(-50, 250, chess.BLACK) == 300


def test_cp_loss_black_improving_is_floored_to_zero():
    # Black to move: White POV goes +100 -> -100 (Black improved) -> no loss.
    assert cp_loss(100, -100, chess.BLACK) == 0


# ---------------------------------------------------------------------------
# classify — exact threshold boundaries + the decided-position rule
# ---------------------------------------------------------------------------


def test_classify_threshold_boundaries():
    eb = 0  # not a decided position
    assert classify(0, eb) == "ok"
    assert classify(49, eb) == "ok"
    assert classify(50, eb) == "inaccuracy"
    assert classify(99, eb) == "inaccuracy"
    assert classify(100, eb) == "mistake"
    assert classify(199, eb) == "mistake"
    assert classify(200, eb) == "blunder"
    assert classify(999, eb) == "blunder"


def test_classify_decided_position_is_skipped_regardless_of_cp_loss():
    # |eval_before| > 800 -> skipped, even for a huge cp_loss, and for either sign.
    assert classify(500, 801) == "skipped"
    assert classify(500, -801) == "skipped"
    # exactly 800 is NOT decided (strictly greater than)
    assert classify(500, 800) == "blunder"


# ---------------------------------------------------------------------------
# tag_phase
# ---------------------------------------------------------------------------

_START_FEN = chess.STARTING_FEN


def test_tag_phase_opening_by_ply():
    assert tag_phase(_START_FEN, 1) == "opening"
    assert tag_phase(_START_FEN, 20) == "opening"


def test_tag_phase_middlegame_full_board_after_ply_20():
    assert tag_phase(_START_FEN, 21) == "middlegame"  # 30 non-K/P pieces, way over 6


def test_tag_phase_endgame_few_pieces():
    # White: K + R; Black: K + R  -> 2 non-king/pawn pieces (<= 6) -> endgame.
    fen = "4k3/8/8/8/8/8/4R3/4K2r w - - 0 40"
    assert tag_phase(fen, 40) == "endgame"


def test_tag_phase_opening_precedence_over_few_pieces():
    # A bare-ish position but ply <= 20 -> opening wins (matches spec ordering).
    fen = "4k3/8/8/8/8/8/8/4K2R w - - 0 8"
    assert tag_phase(fen, 8) == "opening"


def _heavy_count(fen: str) -> int:
    board = chess.Board(fen)
    return sum(
        1 for p in board.piece_map().values() if p.piece_type not in (chess.KING, chess.PAWN)
    )


def test_tag_phase_endgame_boundary_six_vs_seven():
    # Exactly 6 non-king/pawn pieces (each side Q+R+B) -> endgame (<= 6 inclusive).
    six = "r1bqk3/8/8/8/8/8/8/R1BQK3 w - - 0 40"
    assert _heavy_count(six) == 6
    assert tag_phase(six, 40) == "endgame"
    # One more piece (a black knight) -> 7 -> middlegame.
    seven = "r1bqk1n1/8/8/8/8/8/8/R1BQK3 w - - 0 40"
    assert _heavy_count(seven) == 7
    assert tag_phase(seven, 40) == "middlegame"


# ---------------------------------------------------------------------------
# extract_move_times — clock deltas, increment, and the clockless case
# ---------------------------------------------------------------------------


def test_extract_move_times_no_increment():
    # 180+0. White spends 0.4s then 3s; Black spends 1s then 2s (rounded).
    pgn = (
        '[TimeControl "180"]\n\n'
        "1. e4 {[%clk 0:02:59.6]} e5 {[%clk 0:02:59]} "
        "2. Nf3 {[%clk 0:02:56.6]} Nc6 {[%clk 0:02:57]} *\n"
    )
    times = extract_move_times(pgn)
    assert times[1] == 0   # 180 - 179.6 = 0.4 -> round -> 0
    assert times[2] == 1   # 180 - 179 = 1
    assert times[3] == 3   # 179.6 - 176.6 = 3.0
    assert times[4] == 2   # 179 - 177 = 2


def test_extract_move_times_with_increment():
    # 180+2: each move adds 2s back, so spent = prev - after + 2.
    pgn = (
        '[TimeControl "180+2"]\n\n'
        "1. e4 {[%clk 0:03:00]} e5 {[%clk 0:03:01]} *\n"
    )
    times = extract_move_times(pgn)
    # White: 180 - 180 + 2 = 2 ; Black: 180 - 181 + 2 = 1
    assert times[1] == 2
    assert times[2] == 1


def test_extract_move_times_clockless_returns_none():
    pgn = '[TimeControl "180"]\n\n1. e4 e5 2. Nf3 *\n'
    times = extract_move_times(pgn)
    assert times[1] is None
    assert times[2] is None
    assert times[3] is None


def test_extract_move_times_unparseable_time_control():
    pgn = '[TimeControl "-"]\n\n1. e4 {[%clk 0:02:59]} *\n'
    assert extract_move_times(pgn)[1] is None
