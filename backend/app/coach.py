"""Session 15 — the rule-based coach.

Turns a `PlayerFeatures` aggregation (Session 12 + detectors from Session
13/14) into a structured `Report` (Appendix 2). Every rule is deterministic,
template-based, and number-driven. No LLM, no ML, no invented copy.

Rule table (priority / rating_impact) and copy templates are taken verbatim
from CHESSANIA_ROADMAP.md Appendix 3. If a coaching sentence ever feels
wrong, the fix is to amend Appendix 3 first, then mirror that change here;
never silently drift from the appendix.

Every Issue diagnosis, prescription, and success_metric must contain at
least one digit — the banned-phrase guard in S17 will grep-enforce this;
we comply now by construction.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app import schemas
from app.analysis import is_player_ply
from app.config import settings
from app.models import Game, MoveEval, Player
from app.features import PlayerFeatures
from app.openings import build_opening_recs


# ---------------------------------------------------------------------------
# Internal rule representation
# ---------------------------------------------------------------------------


@dataclass
class _Rule:
    key: str
    priority: int
    rating_impact: str
    fires: callable
    render: callable


# ---------------------------------------------------------------------------
# Evidence resolution: (game_id, ply) -> EvidenceRef
# ---------------------------------------------------------------------------


def _resolve_evidence(
    session,
    player: Player | None,
    evidence: list[tuple[str, int]],
    detail_fn: callable,
) -> list[schemas.EvidenceRef]:
    """Turn up to 3 (game_id, ply) tuples into rich EvidenceRef objects by
    looking up the actual Game and MoveEval rows. If session/player are
    absent (synthetic tests) or a citation can't be resolved, that citation
    is simply skipped — the caller is responsible for keeping at least one."""
    if not session or not player or not evidence:
        return []

    try:
        game_ids = [uuid.UUID(gid) for gid, _ply in evidence]
    except ValueError:
        return []

    games = session.scalars(select(Game).where(Game.id.in_(game_ids))).all()
    game_map = {str(g.id): g for g in games}

    refs: list[schemas.EvidenceRef] = []
    for gid_str, ply in evidence[:3]:
        game = game_map.get(gid_str)
        if game is None:
            continue
        row = session.scalars(
            select(MoveEval).where(MoveEval.game_id == game.id, MoveEval.ply == ply)
        ).first()
        if row is None:
            continue
        detail = detail_fn(game, row)
        refs.append(
            schemas.EvidenceRef(
                game_url=game.game_url,
                played_at=game.played_at,
                opponent_rating=game.opponent_rating,
                ply=row.ply,
                move_san=row.move_san,
                detail=detail,
            )
        )
    return refs


def _blunder_detail(game: Game, row: MoveEval) -> str:
    return f"blundered {row.move_san} for {row.cp_loss} centipawns lost"


def _generic_error_detail(game: Game, row: MoveEval) -> str:
    return f"{row.classification} with {row.move_san} at move {row.ply}"


# ---------------------------------------------------------------------------
# Pre-PONR blunders (used by the blunder_rate rule for both its headline
# number and its evidence)
# ---------------------------------------------------------------------------


def _pre_ponr_blunders(
    session,
    player: Player,
    features: PlayerFeatures,
) -> list[tuple[Game, MoveEval]]:
    """All player blunders that happened at or before that game's PONR,
    sorted by cp_loss descending. If a game has no PONR, every player
    blunder in that game counts."""
    ponr_by_game = (
        features.detectors.get("turning_point", {}).get("stats", {}).get("ponr_by_game", {})
    )

    games = session.scalars(select(Game).where(Game.player_id == player.id)).all()
    if not games:
        return []

    game_map = {str(g.id): g for g in games}
    rows = session.scalars(
        select(MoveEval).where(MoveEval.game_id.in_([g.id for g in games]))
    ).all()

    result: list[tuple[Game, MoveEval]] = []
    for row in rows:
        game = game_map.get(str(row.game_id))
        if game is None:
            continue
        if not is_player_ply(row.ply, game.player_color):
            continue
        if row.classification != "blunder":
            continue
        ponr = ponr_by_game.get(str(game.id))
        if ponr is not None and row.ply > ponr:
            continue
        result.append((game, row))

    result.sort(key=lambda gr: gr[1].cp_loss, reverse=True)
    return result


# ---------------------------------------------------------------------------
# Count qualifying endgame conversion games (winning endgame reached)
# ---------------------------------------------------------------------------


def _count_winning_endgames(session, player: Player) -> int:
    """Number of games where the player reached a winning endgame
    (player-POV eval >= FEATURE_ENDGAME_AHEAD_CP at endgame-entry ply)."""
    from app.analysis import player_pov_eval

    games = session.scalars(select(Game).where(Game.player_id == player.id)).all()
    if not games:
        return 0
    game_map = {str(g.id): g for g in games}
    rows = session.scalars(
        select(MoveEval).where(MoveEval.game_id.in_([g.id for g in games]))
    ).all()

    count = 0
    for row in rows:
        if row.phase != "endgame":
            continue
        game = game_map[str(row.game_id)]
        pov = player_pov_eval(row.eval_cp_before, game.player_color)
        if pov >= settings.FEATURE_ENDGAME_AHEAD_CP:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Per-time-class blunder rate (for the strength fallback)
# ---------------------------------------------------------------------------


def _time_class_blunder_rates(
    session, player: Player
) -> dict[str, float]:
    """Returns {time_class: blunders_per_game} for the player's games."""
    games = session.scalars(select(Game).where(Game.player_id == player.id)).all()
    if not games:
        return {}

    game_map = {str(g.id): g for g in games}
    rows = session.scalars(
        select(MoveEval).where(MoveEval.game_id.in_([g.id for g in games]))
    ).all()

    blunders: dict[str, int] = {}
    game_counts: dict[str, int] = {}
    for game in games:
        game_counts[game.time_class] = game_counts.get(game.time_class, 0) + 1

    for row in rows:
        game = game_map[str(row.game_id)]
        if not is_player_ply(row.ply, game.player_color):
            continue
        if row.classification == "blunder":
            blunders[game.time_class] = blunders.get(game.time_class, 0) + 1

    return {
        tc: round(blunders.get(tc, 0) / game_counts[tc], 2)
        for tc in game_counts
        if game_counts[tc] > 0
    }


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------


def _rule_blunder_rate() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return f.meaningful_blunders_per_game > settings.COACH_BLUNDER_RATE

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        bpg = round(f.meaningful_blunders_per_game, 1)
        n = f.games_analyzed

        # Evidence: the 3 worst pre-PONR blunders.
        pre_ponr: list[tuple[Game, MoveEval]] = []
        if session and player:
            pre_ponr = _pre_ponr_blunders(session, player, f)
        evidence = [(str(g.id), row.ply) for g, row in pre_ponr[:3]]

        # % of those pre-PONR blunders that happened after move 25.
        after_move_25 = sum(1 for _g, row in pre_ponr if row.ply > 25)
        pct_late = round(100 * after_move_25 / len(pre_ponr), 1) if pre_ponr else 0.0

        # "at your rating" would be a digit-less sentence when rating_snapshot is
        # None; keeping the game count in the clause guarantees a number.
        rating_text = f"rating {f.rating_snapshot}" if f.rating_snapshot is not None else "your current rating"
        diagnosis = (
            f"You averaged {bpg} meaningful blunders per game across {n} games "
            f"— at {rating_text}, that's the difference-maker in a {n}-game sample; "
            f"{pct_late}% came after move 25."
        )

        if bpg <= 2.5:
            prescription = (
                "Do 20 Lichess puzzles a day for 30 days, and before every move ask one question: "
                "what did their last move threaten?"
            )
        else:
            prescription = (
                "Do 40 Lichess puzzles a day for 30 days, and before every move ask one question: "
                "what did their last move threaten?"
            )

        target = max(round(bpg - 1.0, 1), 0.5)
        success_metric = (
            f"Get your meaningful blunder rate from {bpg} to under {target} per game "
            f"over your next 20 games."
        )

        counter = None
        if f.blunders_per_game > f.meaningful_blunders_per_game:
            counter = (
                f"but only {bpg} of your {f.blunders_per_game} blunders per game "
                f"came before the position was already lost — the raw count overstates it."
            )

        links = [
            schemas.Link(label="Lichess puzzles", url="https://lichess.org/training/tactics"),
        ]

        return schemas.Issue(
            key="blunder_rate",
            headline="Blunders are your rating cap.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="high",
            refresh_after="re-check after 20 new games",
            links=links,
            evidence=_resolve_evidence(session, player, evidence, _blunder_detail),
        )

    return _Rule("blunder_rate", 1, "high", fires, render)


def _rule_hung_pieces() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("hung_pieces", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["hung_pieces"]["stats"]
        hang_pct = stats["hang_pct"]
        hung_count = stats["hung_count"]
        evidence = f.detectors["hung_pieces"]["evidence"]

        diagnosis = (
            f"{hang_pct}% of your blunders left a piece where it could simply be taken — "
            f"{hung_count} hung-piece blunders in this batch."
        )
        prescription = (
            "Board-vision drill: before moving, scan every undefended piece of yours; "
            "train the Lichess 'hanging pieces' theme for 15 minutes a day."
        )
        target = max(round(hang_pct * 0.5, 1), 10.0)
        success_metric = (
            f"Cut hung-piece blunders from {hang_pct}% to under {target}% over your next 20 games."
        )
        counter = "This counts only positions where the opponent's best reply actually wins material."

        return schemas.Issue(
            key="hung_pieces",
            headline="Free pieces are walking away.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="high",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess hanging pieces",
                    url="https://lichess.org/practice/intermediate-tactics/hanging-piece/",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("hung_pieces", 2, "high", fires, render)


def _rule_opening_leak() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("opening_leak", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["opening_leak"]["stats"]
        family = stats["family"]
        avg_cp = abs(stats["avg_cp"])
        k = stats["game_count"]
        evidence = f.detectors["opening_leak"]["evidence"]

        diagnosis = (
            f"You reached move 15 of your {family} games down an average of {avg_cp} centipawns "
            f"across {k} games — you're losing these games before they start."
        )
        prescription = (
            f"Learn ONE reply properly: pick a single line in the {family} family and spend "
            f"20 minutes a day on it for 2 weeks."
        )
        success_metric = (
            f"Improve your {family} score by 50 centipawns at move 15 over your next 10 games."
        )
        counter = f"This is based on {k} games — if you switch lines, the sample resets."

        return schemas.Issue(
            key="opening_leak",
            headline=f"Your {family} is leaking.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="high",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label=f"Lichess {family} explorer",
                    url=f"https://lichess.org/opening/{family}",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("opening_leak", 3, "high", fires, render)


def _rule_endgame_conversion() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return f.endgame_conversion is not None and f.endgame_conversion < settings.COACH_ENDGAME_CONVERSION

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        conv = round(f.endgame_conversion * 100, 1)

        # Count qualifying winning endgames from the DB for the copy.
        q = 0
        if session and player:
            q = _count_winning_endgames(session, player)

        diagnosis = f"You reached a winning endgame in {q} games and converted {conv}%."
        prescription = (
            "Drill king + pawn fundamentals on Lichess Practice for 15 minutes, 2 times a week."
        )
        success_metric = (
            f"Convert at least 75% of winning endgames over your next 10 games (you are at {conv}%)."
        )
        counter = "Only positions where you entered the endgame ahead by 2 pawns or more are counted."

        return schemas.Issue(
            key="endgame_conversion",
            headline="Winning positions aren't becoming wins.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="medium",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess endgame practice",
                    url="https://lichess.org/practice/basic-endgames/",
                )
            ],
            evidence=_resolve_evidence(
                session,
                player,
                f.endgame_conversion_evidence,
                lambda g, r: f"reached a winning endgame at move {r.ply} but did not win",
            ),
        )

    return _Rule("endgame_conversion", 4, "medium", fires, render)


def _rule_late_collapse() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("late_collapse", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["late_collapse"]["stats"]
        late_ratio = stats["late_ratio"] or 1.0
        late_blunders = stats["late_blunders"]
        evidence = f.detectors["late_collapse"]["evidence"]

        diagnosis = (
            f"Past move 30 you blunder {late_ratio} times as often as before it — "
            f"{late_blunders} late blunders in this batch."
        )
        prescription = (
            "Use a 5-second blunder check before every move, and keep at least 25% of your clock "
            "for the last 15 moves."
        )
        target = max(round(late_ratio * 0.5, 1), 1.2)
        success_metric = (
            f"Halve your late-blunder ratio from {late_ratio} to under {target} over your next 20 games."
        )
        counter = "This compares late blunders to early ones, so a quiet opening can inflate the ratio."

        return schemas.Issue(
            key="late_collapse",
            headline="Your games are decided after move 30 — against you.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="medium",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess practice",
                    url="https://lichess.org/training/",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("late_collapse", 5, "medium", fires, render)


def _rule_blitz_gap() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("time_class_split", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["time_class_split"]["stats"]
        blitz_bpg = stats["blitz_bpg"]
        rapid_bpg = stats["rapid_bpg"]
        evidence = f.detectors["time_class_split"]["evidence"]

        diagnosis = (
            f"You don't have a chess problem — you have a blitz problem: "
            f"{blitz_bpg} blunders per game in blitz vs {rapid_bpg} in rapid."
        )
        prescription = (
            "Shift the ratio toward rapid for 30 days: play 3 rapid games for every 1 blitz game; "
            "blitz is testing, rapid is training."
        )
        success_metric = (
            f"Get your blitz blunder rate within 0.5 of your rapid rate over your next 20 games."
        )
        counter = "This only matters if you care about your rapid rating; in pure bullet practice the gap is expected."

        return schemas.Issue(
            key="blitz_gap",
            headline="You don't have a chess problem — you have a blitz problem.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="medium",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess rapid pool",
                    url="https://lichess.org/?time=10&increment=0#/",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("blitz_gap", 6, "medium", fires, render)


def _rule_opening_general() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        opening_leak_fired = bool(
            f.detectors and f.detectors.get("opening_leak", {}).get("fired")
        )
        return f.opening_leak_rate >= settings.COACH_OPENING_GENERAL and not opening_leak_fired

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        leak_rate = round(f.opening_leak_rate * 100, 1)
        evidence = f.opening_leak_evidence

        diagnosis = (
            f"{leak_rate}% of your games you are already worse by move 20, but no single opening "
            f"family is the culprit — this is a general opening-principles problem."
        )
        prescription = (
            "Spend 20 minutes a day on opening fundamentals: develop every piece before moving the same one twice, "
            "castle within the first 10 moves, and don't grab pawns you can't keep."
        )
        success_metric = (
            f"Drop your move-20 leak rate from {leak_rate}% to under 20% over your next 20 games."
        )
        counter = None

        return schemas.Issue(
            key="opening_general",
            headline="Your opening fundamentals are costing you.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="medium",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess opening principles",
                    url="https://lichess.org/practice/coordinate/piece-checks/",
                )
            ],
            evidence=_resolve_evidence(
                session,
                player,
                evidence,
                lambda g, r: f"position was already worse by move {r.ply}",
            ),
        )

    return _Rule("opening_general", 7, "medium", fires, render)


def _rule_overextension() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("overextension", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["overextension"]["stats"]
        k = stats["occurrences"]
        evidence = f.detectors["overextension"]["evidence"]

        diagnosis = (
            f"There are signs you push pawns past their support — {k} times a deep pawn advance "
            f"was followed by a 150+ centipawn swing against you within 6 plies."
        )
        prescription = (
            "Before any pawn push past the 5th rank, ask who guards the square it leaves behind — "
            "spend 10 minutes on pawn-structure videos."
        )
        success_metric = (
            f"Reduce these overextension signals from {k} to under {max(k // 2, 1)} over your next 20 games."
        )
        counter = "This is a soft correlation, not proof the pawn push caused the swing."

        return schemas.Issue(
            key="overextension",
            headline="Your pawn pushes are running ahead of your pieces.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="low",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess pawn structure",
                    url="https://lichess.org/video/pawn-structure",
                )
            ],
            evidence=_resolve_evidence(
                session,
                player,
                evidence,
                lambda g, r: f"advanced {r.move_san} deep before the eval swung",
            ),
        )

    return _Rule("overextension", 8, "low", fires, render)


def _rule_rushed_blunders() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("rushed_blunders", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["rushed_blunders"]["stats"]
        rushed_pct = round(stats["share"] * 100, 1)
        rush_seconds = stats["rush_seconds"]
        evidence = f.detectors["rushed_blunders"]["evidence"]

        diagnosis = (
            f"{rushed_pct}% of your blunders came with under {rush_seconds} seconds on your clock — "
            f"you're moving before you've finished looking."
        )
        prescription = (
            "On every move where you still have time, before you touch a piece, spend at least 5 seconds "
            "naming every check and capture your opponent has."
        )
        target = max(round(rushed_pct * 0.5, 1), 15.0)
        success_metric = (
            f"Cut rushed blunders from {rushed_pct}% to under {target}% over your next 10 games."
        )
        counter = "This counts only blunders made with very little clock — slow blunders are a different issue."

        return schemas.Issue(
            key="rushed_blunders",
            headline="You don't have a blunder problem — you have a rushing problem.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="low",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess time management",
                    url="https://lichess.org/page/tips",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("rushed_blunders", 9, "low", fires, render)


def _rule_time_trouble_collapse() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("time_trouble_collapse", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["time_trouble_collapse"]["stats"]
        rate_low = stats["rate_low"]
        rate_normal = stats["rate_normal"]
        low_clock = stats["low_clock"]
        evidence = f.detectors["time_trouble_collapse"]["evidence"]

        diagnosis = (
            f"Your error rate climbs from {rate_normal} per move to {rate_low} per move once you drop "
            f"under {low_clock} seconds — the mistakes cluster in time trouble, not across the whole game."
        )
        prescription = (
            "Budget the clock: keep 20% of your time for the last 15 moves, and play known opening lines faster "
            "to bank time for the moves that decide the game."
        )
        success_metric = (
            f"Keep your under-{low_clock}s error rate within 2x your normal rate over your next 10 games."
        )
        counter = "If you almost never reach time trouble, this signal is based on a small sample."

        return schemas.Issue(
            key="time_trouble_collapse",
            headline="Your clock, not the board, is losing these.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="low",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess clock tips",
                    url="https://lichess.org/page/tips",
                )
            ],
            evidence=_resolve_evidence(session, player, evidence, _generic_error_detail),
        )

    return _Rule("time_trouble_collapse", 10, "low", fires, render)


def _rule_dawdling() -> _Rule:
    def fires(f: PlayerFeatures) -> bool:
        return bool(f.detectors and f.detectors.get("dawdling", {}).get("fired"))

    def render(f: PlayerFeatures, session, player: Player | None) -> schemas.Issue:
        stats = f.detectors["dawdling"]["stats"]
        avg_seconds = stats["avg_dawdle_seconds"]
        k = stats["game_count"]
        evidence = f.detectors["dawdling"]["evidence"]

        diagnosis = (
            f"You burned an average of {avg_seconds} seconds on moves that didn't need it — "
            f"low-loss, low-complexity positions across {k} games, then landed in time trouble."
        )
        prescription = (
            "Spend your think time where the position is genuinely unclear; play forced recaptures and obvious "
            "moves in under 5 seconds."
        )
        success_metric = (
            f"Reach move 30 with at least 30 seconds left over your next 10 games."
        )
        counter = "This only counts simple positions — time spent on genuinely hard moves is good judgment."

        return schemas.Issue(
            key="dawdling",
            headline="You're spending your time in the wrong places.",
            diagnosis=diagnosis,
            prescription=prescription,
            success_metric=success_metric,
            counter_evidence=counter,
            rating_impact="low",
            refresh_after="re-check after 20 new games",
            links=[
                schemas.Link(
                    label="Lichess clock tips",
                    url="https://lichess.org/page/tips",
                )
            ],
            evidence=_resolve_evidence(
                session,
                player,
                evidence,
                lambda g, r: f"spent {r.seconds_spent} seconds on the simple ok move {r.move_san}",
            ),
        )

    return _Rule("dawdling", 11, "low", fires, render)


# ---------------------------------------------------------------------------
# Strength selection (Appendix 3 §S)
# ---------------------------------------------------------------------------


def _best_phase(features: PlayerFeatures) -> tuple[str, float, float] | None:
    """Return (phase_name, acpl, margin) for the player's best phase,
    or None if no phase is clearly best."""
    if features.acpl_overall is None:
        return None

    candidates: list[tuple[str, float]] = []
    for phase in ("opening", "middlegame", "endgame"):
        value = getattr(features.acpl_by_phase, phase)
        if value is not None:
            candidates.append((phase, value))

    if not candidates:
        return None

    best_phase, best_acpl = min(candidates, key=lambda x: x[1])
    margin = round(features.acpl_overall - best_acpl, 1)
    if margin <= 0:
        return None
    return best_phase, best_acpl, margin


def _strength_for(
    features: PlayerFeatures, session, player: Player | None
) -> schemas.Strength:
    """Exactly one strength, with a real number that earns it."""
    best = _best_phase(features)
    if best:
        phase, acpl, margin = best
        return schemas.Strength(
            headline=f"Your {phase} is genuinely solid.",
            detail=(
                f"Your {phase} ACPL is {acpl}, better than your other phases by {margin} "
                "average centipawns."
            ),
        )

    if features.endgame_conversion is not None and features.endgame_conversion >= settings.COACH_ENDGAME_CONVERSION:
        return schemas.Strength(
            headline="You convert winning endgames.",
            detail=(
                f"You converted {features.endgame_conversion * 100:.0f}% of your winning endgames — "
                "that is the skill that lets you turn advantages into points."
            ),
        )

    if features.accuracy_trend == "improving":
        return schemas.Strength(
            headline="Your accuracy is trending up.",
            detail=(
                f"Your average centipawn loss improved across the second half of your {features.games_analyzed} games."
            ),
        )

    # Fallback: the time class with the lowest blunder rate.
    cleanest_tc = None
    cleanest_bpg = None
    if session and player:
        rates = _time_class_blunder_rates(session, player)
        if rates:
            cleanest_tc, cleanest_bpg = min(rates.items(), key=lambda x: x[1])

    if cleanest_tc is None:
        cleanest_tc = "games"
        cleanest_bpg = features.blunders_per_game

    return schemas.Strength(
        headline=f"Your {cleanest_tc} games are your cleanest time control.",
        detail=f"You make {cleanest_bpg} blunders per game in {cleanest_tc}.",
    )


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _all_rules() -> list[_Rule]:
    return [
        _rule_blunder_rate(),
        _rule_hung_pieces(),
        _rule_opening_leak(),
        _rule_endgame_conversion(),
        _rule_late_collapse(),
        _rule_blitz_gap(),
        _rule_opening_general(),
        _rule_overextension(),
        _rule_rushed_blunders(),
        _rule_time_trouble_collapse(),
        _rule_dawdling(),
    ]


def _stats_block(features: PlayerFeatures) -> schemas.StatsBlock:
    return schemas.StatsBlock(
        blunders_per_game=features.blunders_per_game,
        mistakes_per_game=features.mistakes_per_game,
        acpl_overall=features.acpl_overall if features.acpl_overall is not None else 0.0,
        acpl_by_phase=schemas.PhaseStats(
            opening=features.acpl_by_phase.opening or 0.0,
            middlegame=features.acpl_by_phase.middlegame or 0.0,
            endgame=features.acpl_by_phase.endgame or 0.0,
        ),
        endgame_conversion=features.endgame_conversion,
        accuracy_trend=features.accuracy_trend,
        per_game_acpl=features.per_game_acpl,
        by_color={
            color: schemas.ColorStats(
                games=cs.games,
                results=schemas.WLD(
                    win=cs.results.win,
                    loss=cs.results.loss,
                    draw=cs.results.draw,
                ),
                blunders_per_game=cs.blunders_per_game,
                acpl_overall=cs.acpl_overall,
                acpl_by_phase=schemas.PhaseStats(
                    opening=cs.acpl_by_phase.opening or 0.0,
                    middlegame=cs.acpl_by_phase.middlegame or 0.0,
                    endgame=cs.acpl_by_phase.endgame or 0.0,
                ),
                worst_phase=cs.worst_phase,
                opening_leak_rate=cs.opening_leak_rate,
                endgame_conversion=cs.endgame_conversion,
                low_signal=cs.low_signal,
            )
            for color, cs in features.by_color.items()
        }
        if features.by_color
        else None,
    )


def _playstyle(features: PlayerFeatures) -> schemas.Playstyle:
    p = features.playstyle
    if p is None:
        return schemas.Playstyle(
            label="balanced",
            score=0.0,
            explanation="Not enough games yet to pin down a playstyle.",
            components={},
        )
    return schemas.Playstyle(
        label=p.label,
        score=p.score,
        explanation=p.explanation,
        components=p.components,
    )


def _player_summary(features: PlayerFeatures, player: Player | None, games: list[Game]) -> schemas.PlayerSummary:
    if not player:
        return schemas.PlayerSummary(
            platform="chesscom",
            username="",
            rating=None,
            games_analyzed=features.games_analyzed,
            date_range="—",
            time_class_mix="",
        )

    time_class_mix = " · ".join(f"{count} {tc}" for tc, count in features.time_class_mix.items())

    dates = sorted(g.played_at for g in games if g.played_at is not None)
    if not dates:
        date_range = "—"
    elif len(dates) == 1:
        date_range = dates[0].strftime("%b %d")
    else:
        date_range = f"{dates[0].strftime('%b %d')} – {dates[-1].strftime('%b %d')}"

    return schemas.PlayerSummary(
        platform=player.platform,
        username=player.username,
        rating=player.rating_snapshot,
        games_analyzed=features.games_analyzed,
        date_range=date_range,
        time_class_mix=time_class_mix,
    )


def build_report(
    features: PlayerFeatures, session=None, player: Player | None = None
) -> schemas.Report:
    """Evaluate every Appendix 3 rule, keep the fired ones, and return a
    Report ordered by (rating_impact bucket, priority). Top 3 issues are
    kept; fewer is correct, never padded.

    `session` and `player` are optional. When provided they let the coach
    resolve (game_id, ply) evidence tuples into rich EvidenceRef objects
    and compute DB-backed numbers (pre-PONR blunders, winning-endgame
    counts, time-class blunder rates). When absent, those pieces degrade
    gracefully.
    """
    rules = _all_rules()
    fired = [rule for rule in rules if rule.fires(features)]

    impact_order = {"high": 0, "medium": 1, "low": 2}
    fired.sort(key=lambda rule: (impact_order[rule.rating_impact], rule.priority))
    top_issues = fired[:3]

    issues = [rule.render(features, session, player) for rule in top_issues]
    strength = _strength_for(features, session, player)

    games: list[Game] = []
    if session and player:
        games = list(session.scalars(select(Game).where(Game.player_id == player.id)).all())

    return schemas.Report(
        schema_version=1,
        player_summary=_player_summary(features, player, games),
        playstyle=_playstyle(features),
        strengths=[strength],
        issues=issues,
        opening_recs=build_opening_recs(features),
        stats_block=_stats_block(features),
        progress=None,
        generated_at=dt.datetime.now(dt.timezone.utc),
        engine_depth=settings.SF_DEPTH,
    )
