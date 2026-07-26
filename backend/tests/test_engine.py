"""Session 11 real-engine tests — the opt-in slice that actually launches
Stockfish. Everything else in the suite runs offline against FixtureEvaluator
(app/engine_eval.py); these tests exist to catch the real binary drifting
away from what the fixtures assume, and to regression-test the terminal-
position handling (checkmate/stalemate) that a normal game replay never
exercises, since analyze_game only ever evaluates non-terminal positions.

Opt-in via the `engine` marker (pytest.ini): a plain `pytest` run skips this
whole module; `pytest -m engine` runs it.
"""

import chess
import pytest

from app.engine_eval import StockfishEvaluator

pytestmark = pytest.mark.engine


def test_start_position_is_near_equal_with_legal_best_move():
    evaluator = StockfishEvaluator()
    try:
        board = chess.Board()
        result = evaluator.evaluate(board)
    finally:
        evaluator.close()

    assert -100 <= result.eval_cp <= 100
    assert chess.Move.from_uci(result.best_move_uci) in board.legal_moves


def test_checkmate_position_does_not_crash_and_has_no_best_move():
    # 1.f3 e5 2.g4 Qh4# — Fool's Mate, White to move, checkmated.
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert board.is_checkmate()

    evaluator = StockfishEvaluator()
    try:
        result = evaluator.evaluate(board)
    finally:
        evaluator.close()

    assert result.best_move_uci == ""


def test_stalemate_position_does_not_crash_and_has_no_best_move():
    # Black to move, stalemated: no legal moves, not in check.
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()

    evaluator = StockfishEvaluator()
    try:
        result = evaluator.evaluate(board)
    finally:
        evaluator.close()

    assert result.best_move_uci == ""
