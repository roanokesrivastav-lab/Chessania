"""V2-S3: mine training positions from existing MoveEval data.

Pure Python/SQL over already-stored rows — never invokes an engine.
Three categories are mined:

  blunder    — every player-ply with classification == "blunder"
  unconverted — the first ply where player-POV eval crosses FEATURE_ADVANTAGE_CP
                in a game NOT won (one candidate per qualifying game)
  danger     — player-blunder plies inside a lost game whose worst player-POV
                eval falls in the resourcefulness band

Idempotent (M2): running twice over the same data adds zero duplicate rows.
The dedupe key is (player_id, source_game_id, ply, category); existing rows
get their last_seen bumped instead of being re-inserted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import is_player_ply, player_pov_eval
from app.config import settings
from app.models import Game, MoveEval, Player, TrainingPosition

logger = logging.getLogger(__name__)


def mine_positions(session: Session, player: Player) -> dict[str, int]:
    """Mine every analyzed game for this player and upsert training_positions
    rows. Returns per-category new-row counts: {"blunder": N, "unconverted": M,
    "danger": P}. Existing rows get last_seen bumped; duplicates add zero.

    Does NOT commit — the caller owns the transaction."""
    games = list(
        session.scalars(
            select(Game).where(
                Game.player_id == player.id, Game.analyzed_at.is_not(None)
            )
        ).all()
    )
    if not games:
        return {"blunder": 0, "unconverted": 0, "danger": 0}

    # Load all MoveEval rows for these games, keyed by game_id.
    evals_by_game: dict[str, list[MoveEval]] = {}
    for game in games:
        rows = sorted(
            session.scalars(
                select(MoveEval).where(MoveEval.game_id == game.id)
            ).all(),
            key=lambda r: r.ply,
        )
        evals_by_game[str(game.id)] = rows

    game_by_id = {str(g.id): g for g in games}
    candidates: list[tuple[str, int, str, str, str, int]] = []
    # Each candidate: (game_id_str, ply, category, fen, best_line_uci, eval_before_cp)

    # ── Category 1: blunder ───────────────────────────────────────────
    for game in games:
        rows = evals_by_game[str(game.id)]
        for row in rows:
            if (
                is_player_ply(row.ply, game.player_color)
                and row.classification == "blunder"
            ):
                uci = _san_to_uci(row.fen_before, row.best_move_san)
                if uci is None:
                    continue
                candidates.append(
                    (
                        str(game.id),
                        row.ply,
                        "blunder",
                        row.fen_before,
                        uci,
                        row.eval_cp_before,
                    )
                )

    # ── Category 2: unconverted ───────────────────────────────────────
    for game in games:
        if game.result == "win":
            continue
        rows = evals_by_game[str(game.id)]
        if not rows:
            continue
        # Find the FIRST ply (by ply order) where player-POV eval >= threshold.
        for row in sorted(rows, key=lambda r: r.ply):
            pov = player_pov_eval(row.eval_cp_before, game.player_color)
            if pov >= settings.FEATURE_ADVANTAGE_CP:
                uci = _san_to_uci(row.fen_before, row.best_move_san)
                if uci is None:
                    continue
                candidates.append(
                    (
                        str(game.id),
                        row.ply,
                        "unconverted",
                        row.fen_before,
                        uci,
                        row.eval_cp_before,
                    )
                )
                break  # One per qualifying game

    # ── Category 3: danger ────────────────────────────────────────────
    for game in games:
        if game.result != "loss":
            continue
        rows = evals_by_game[str(game.id)]
        if not rows:
            continue

        # The worst player-POV eval across all rows (the player's nadir).
        worst_pov = min(
            player_pov_eval(r.eval_cp_before, game.player_color) for r in rows
        )
        # Must fall in the resourcefulness band.
        if not (
            settings.FEATURE_RESOURCE_LOST_CP
            <= worst_pov
            <= settings.FEATURE_RESOURCE_TROUBLE_CP
        ):
            continue

        # Every player-ply blunder whose OWN player-POV eval is also in the band.
        for row in rows:
            if (
                is_player_ply(row.ply, game.player_color)
                and row.classification == "blunder"
            ):
                pov = player_pov_eval(row.eval_cp_before, game.player_color)
                if (
                    settings.FEATURE_RESOURCE_LOST_CP
                    <= pov
                    <= settings.FEATURE_RESOURCE_TROUBLE_CP
                ):
                    uci = _san_to_uci(row.fen_before, row.best_move_san)
                    if uci is None:
                        continue
                    candidates.append(
                        (
                            str(game.id),
                            row.ply,
                            "danger",
                            row.fen_before,
                            uci,
                            row.eval_cp_before,
                        )
                    )

    # ── Upsert into training_positions ────────────────────────────────
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new_counts: dict[str, int] = {"blunder": 0, "unconverted": 0, "danger": 0}

    for gid_str, ply, category, fen, uci, eval_before_cp in candidates:
        game_id = game_by_id[gid_str].id

        # SELECT existing row by the unique dedupe key.
        existing = session.scalars(
            select(TrainingPosition).where(
                TrainingPosition.player_id == player.id,
                TrainingPosition.source_game_id == game_id,
                TrainingPosition.ply == ply,
                TrainingPosition.category == category,
            )
        ).first()

        if existing is not None:
            existing.last_seen = now
        else:
            session.add(
                TrainingPosition(
                    player_id=player.id,
                    source_game_id=game_id,
                    ply=ply,
                    fen=fen,
                    category=category,
                    best_line_uci=uci,
                    eval_before_cp=eval_before_cp,
                    mined_at=now,
                    last_seen=now,
                )
            )
            new_counts[category] += 1

    return new_counts


def _san_to_uci(fen: str, san: str) -> str | None:
    """Convert a SAN move to UCI using the FEN for context. Returns None
    (and logs) on parse failure — never crashes the whole mining pass."""
    try:
        board = chess.Board(fen)
        move = board.parse_san(san)
        return move.uci()
    except Exception:
        logger.warning("Could not parse SAN %r from FEN %s", san, fen[:40])
        return None
