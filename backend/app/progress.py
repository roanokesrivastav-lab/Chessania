"""Session 22 — progress tracking.

Pure DB/JSON math: compare the current report's numbers to the player's
previous and first stored reports. No engine, no network.
"""

from __future__ import annotations

from sqlalchemy import select

from app import schemas
from app.config import settings
from app.features import PlayerFeatures
from app.models import Game, Report as ReportModel


def _delta(
    label: str,
    prev: float | None,
    curr: float | None,
    higher_is_better: bool,
) -> schemas.Delta | None:
    """Return a Delta if both sides are present; None otherwise.

    Direction is "flat" when the change is within PROGRESS_FLAT_EPSILON
    (relative to max(|prev|, 1)). Otherwise it follows higher_is_better:
    up = better for conversion, down = better for ACPL/blunders.
    """
    if prev is None or curr is None:
        return None

    threshold = settings.PROGRESS_FLAT_EPSILON * max(abs(prev), 1)
    if abs(curr - prev) <= threshold:
        direction = "flat"
    elif curr > prev:
        direction = "better" if higher_is_better else "worse"
    else:
        direction = "worse" if higher_is_better else "better"

    return schemas.Delta(metric=label, previous=prev, current=curr, direction=direction)


def _build_deltas(
    current: PlayerFeatures,
    prior_stats: dict,
) -> list[schemas.Delta]:
    """Compute the four metric deltas between the current features and a
    prior report's stats_block."""
    deltas: list[schemas.Delta] = []

    delta = _delta(
        "Blunders/game",
        prior_stats.get("blunders_per_game"),
        current.blunders_per_game,
        higher_is_better=False,
    )
    if delta:
        deltas.append(delta)

    delta = _delta(
        "Overall ACPL",
        prior_stats.get("acpl_overall"),
        current.acpl_overall,
        higher_is_better=False,
    )
    if delta:
        deltas.append(delta)

    worst_phase = current.worst_phase
    if worst_phase is not None:
        prior_phase_acpl: float | None = None
        acpl_by_phase = prior_stats.get("acpl_by_phase")
        if isinstance(acpl_by_phase, dict):
            prior_phase_acpl = acpl_by_phase.get(worst_phase)
        current_phase_acpl = getattr(current.acpl_by_phase, worst_phase)
        delta = _delta(
            f"{worst_phase.capitalize()} ACPL",
            prior_phase_acpl,
            current_phase_acpl,
            higher_is_better=False,
        )
        if delta:
            deltas.append(delta)

    delta = _delta(
        "Endgame conversion",
        prior_stats.get("endgame_conversion"),
        current.endgame_conversion,
        higher_is_better=True,
    )
    if delta:
        deltas.append(delta)

    return deltas


def build_progress(
    session,
    player,
    current_features: PlayerFeatures,
    current_games: list[Game],
) -> schemas.Progress | None:
    """If prior reports exist, build a Progress comparing current_features
    against the latest (vs_previous) and earliest (vs_first) stored reports.

    The honesty guard sets `note` when fewer than PROGRESS_MIN_NEW_GAMES have
    been played since the previous report's last_game_at.
    """
    previous_report = session.scalars(
        select(ReportModel)
        .where(ReportModel.player_id == player.id)
        .order_by(ReportModel.created_at.desc())
        .limit(1)
    ).first()
    if previous_report is None:
        return None

    first_report = session.scalars(
        select(ReportModel)
        .where(ReportModel.player_id == player.id)
        .order_by(ReportModel.created_at.asc())
        .limit(1)
    ).first()
    # previous_report is non-None, so first_report must also be non-None.

    previous_stats = previous_report.report_json.get("stats_block", {})
    first_stats = first_report.report_json.get("stats_block", {})

    vs_previous = _build_deltas(current_features, previous_stats)
    vs_first = _build_deltas(current_features, first_stats)

    # Honesty guard: count games that are provably newer than the last report.
    last_game_at = previous_report.last_game_at
    if last_game_at is not None:
        new_games = sum(
            1 for g in current_games if g.played_at is not None and g.played_at > last_game_at
        )
    else:
        # Without a cutoff, every dated game counts as "new".
        new_games = sum(1 for g in current_games if g.played_at is not None)

    note = None
    if new_games < settings.PROGRESS_MIN_NEW_GAMES:
        note = settings.PROGRESS_LOW_SIGNAL_NOTE

    return schemas.Progress(
        vs_previous=vs_previous,
        vs_first=vs_first,
        previous_report_at=previous_report.created_at,
        note=note,
    )
