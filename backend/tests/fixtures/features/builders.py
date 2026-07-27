"""Session 17 — fixture builders for the three golden-report profiles.

Each builder seeds a Player, a set of Games, and the MoveEval rows that
`load_features()` turns into a `PlayerFeatures`.  The profiles are built to
fire different detectors and produce genuinely different reports, but they
do so without ever invoking Stockfish: every value is written directly into
the rows.

All times are deterministic, opponent ratings/game urls are realistic, and
`analyzed_at` is set so `load_features()` will pick the games up.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.features import PlayerFeatures, load_features
from app.models import Game, MoveEval, Player

_BASE_TIME = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

# Re-used FENs.  They are static because these tests only need the right
# values in the MoveEval columns, not a real position progression.
_QUEENLESS_FEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"
_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_HUNG_REPLY_FEN = "4k3/8/8/3N4/4b3/8/8/4K3 b - - 0 1"


def _make_player(session, *, username: str, rating: int) -> Player:
    player = Player(platform="chesscom", username=username, rating_snapshot=rating)
    session.add(player)
    session.commit()
    return player


def _make_game(
    session,
    player: Player,
    *,
    i: int,
    time_class: str,
    result: str,
    opening_eco: str | None,
    opponent_rating: int,
    game_url: str,
) -> Game:
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url=game_url,
        pgn="1. e4 e5",
        time_class=time_class,
        player_color="white",
        result=result,
        played_at=_BASE_TIME + dt.timedelta(hours=i),
        analyzed_at=_BASE_TIME,
        opening_eco=opening_eco,
        opponent_rating=opponent_rating,
    )
    session.add(game)
    session.commit()
    return game


def _insert_rows(session, game: Game, rows_spec: list[dict[str, object]]) -> None:
    """Insert MoveEval rows from a list of per-ply specs."""
    rows: list[MoveEval] = []
    for spec in rows_spec:
        rows.append(
            MoveEval(
                game_id=game.id,
                ply=spec["ply"],
                move_san=spec["move_san"],
                fen_before=spec.get("fen_before", _START_FEN),
                eval_cp_before=spec.get("eval_cp_before", 0),
                eval_cp_after=spec.get("eval_cp_after", 0),
                cp_loss=spec["cp_loss"],
                best_move_san=spec.get("best_move_san", spec["move_san"]),
                classification=spec["classification"],
                phase=spec.get("phase", "middlegame"),
            )
        )
    session.add_all(rows)
    session.commit()


def _build_rows(
    *,
    ply_count: int,
    cp_loss: int,
    classification: str,
    eval_amplitude: int,
    capture_san: str,
    quiet_san: str,
    include_castles: bool,
    fen: str = _START_FEN,
) -> list[dict]:
    """Build a deterministic list of move rows for one game.

    Player is white, so odd plies are the player's moves.
    """
    rows: list[dict] = []
    for ply in range(1, ply_count + 1):
        is_player = ply % 2 == 1
        # High-amplitude eval oscillation -> high eval_volatility.
        eval_val = eval_amplitude if ply % 2 == 0 else -eval_amplitude
        # Alternate captures and quiet moves to control capture_density.
        if is_player:
            if ply % 5 in (1, 3):
                move_san = capture_san if "x" in capture_san else quiet_san
            else:
                move_san = quiet_san
        else:
            move_san = quiet_san
        # Inject castling moves if requested (one kingside, one queenside).
        if include_castles and ply in (6, 7):
            if ply == 6:
                move_san = "O-O"
            else:
                move_san = "O-O-O"
        rows.append(
            {
                "ply": ply,
                "move_san": move_san,
                "fen_before": fen,
                "eval_cp_after": eval_val,
                "cp_loss": cp_loss if is_player else 0,
                "best_move_san": move_san,
                "classification": classification if is_player else "ok",
                "phase": "opening" if ply <= 20 else ("endgame" if ply >= 45 else "middlegame"),
            }
        )
    return rows


def build_tactical_blunderer(session) -> tuple[PlayerFeatures, Player]:
    """~900, blitz-heavy, short games, hung-piece blunders.

    Expected to fire: blunder_rate, hung_pieces, time_class_split.
    Playstyle should come out tactical.
    """
    player = _make_player(session, username="tactical_blunderer", rating=920)

    game_configs = []
    # 8 blitz games, most lost, a few won.
    for i in range(8):
        game_configs.append(
            {
                "time_class": "blitz",
                "result": "loss" if i < 6 else "win",
                "opening_eco": f"C{4 + i % 3}0",  # C40, C50, C60 — no single family dominates
                "opponent_rating": 1050 + i,
                "game_url": f"https://www.chess.com/game/live/{1000 + i}",
            }
        )
    # 5 rapid games, relatively clean, to make blitz look spiky.
    for i in range(5):
        game_configs.append(
            {
                "time_class": "rapid",
                "result": "draw" if i == 4 else "win",
                "opening_eco": f"B{1 + i % 2}0",
                "opponent_rating": 1100 + i,
                "game_url": f"https://www.chess.com/game/live/{2000 + i}",
            }
        )

    for i, cfg in enumerate(game_configs):
        game = _make_game(session, player, i=i, **cfg)
        is_blitz = cfg["time_class"] == "blitz"
        rows = _build_rows(
            ply_count=35,
            cp_loss=300 if is_blitz else 20,
            classification="blunder" if is_blitz else "ok",
            eval_amplitude=250,
            capture_san="Nxe4",
            quiet_san="Nf3",
            include_castles=True,
        )
        # Drive capture_density up: every non-castle player move is a capture.
        for row in rows:
            if row["ply"] % 2 == 1 and row["move_san"] not in ("O-O", "O-O-O"):
                row["move_san"] = "Nxe4"
        if is_blitz:
            # Make opponent replies on even plies look like hung-piece captures.
            for row in rows:
                if row["ply"] % 2 == 0:
                    row["best_move_san"] = "Bxd5"
                    row["fen_before"] = _HUNG_REPLY_FEN
        else:
            # Give rapid games a small blunder rate so time_class_split fires.
            for row in rows:
                if row["ply"] % 2 == 1 and row["ply"] <= 5:
                    row["classification"] = "blunder"
                    row["cp_loss"] = 20
        _insert_rows(session, game, rows)

    return load_features(session, "chesscom", player.username), player


def build_positional_leaker(session) -> tuple[PlayerFeatures, Player]:
    """~1400, longer games, leaking the same opening family, clean endgames.

    Expected to fire: opening_leak (and high endgame_conversion).
    Playstyle should come out positional.
    """
    player = _make_player(session, username="positional_leaker", rating=1420)

    game_configs = []
    for i in range(10):
        game_configs.append(
            {
                "time_class": "rapid",
                "result": "win" if i < 7 else "loss",
                "opening_eco": "B07",  # all same family "B0"
                "opponent_rating": 1500 + i,
                "game_url": f"https://www.chess.com/game/live/{3000 + i}",
            }
        )

    for i, cfg in enumerate(game_configs):
        game = _make_game(session, player, i=i, **cfg)
        rows = _build_rows(
            ply_count=100,
            cp_loss=10,
            classification="ok",
            eval_amplitude=20,
            capture_san="Nf3",  # no actual capture token -> low capture density
            quiet_san="d4",
            include_castles=False,
            fen=_QUEENLESS_FEN,
        )
        # Force a leak at ply 15 (detector) and ply 20 (feature).  The player is
        # white, so a negative White-POV eval means the player is worse.
        for row in rows:
            if row["ply"] in (15, 20):
                row["eval_cp_after"] = -200
        _insert_rows(session, game, rows)

    # Add two clean endgame conversions games so conversion is high.
    for j in range(2):
        game = _make_game(
            session,
            player,
            i=10 + j,
            time_class="rapid",
            result="win",
            opening_eco="B07",
            opponent_rating=1480 + j,
            game_url=f"https://www.chess.com/game/live/{3100 + j}",
        )
        rows = _build_rows(
            ply_count=100,
            cp_loss=10,
            classification="ok",
            eval_amplitude=20,
            capture_san="Nf3",
            quiet_san="d4",
            include_castles=False,
            fen=_QUEENLESS_FEN,
        )
        # Entry to endgame: white is ahead, so the white player converts.
        for row in rows:
            if row["ply"] == 45:
                row["phase"] = "endgame"
                row["eval_cp_before"] = 300
        _insert_rows(session, game, rows)

    return load_features(session, "chesscom", player.username), player


def build_endgame_loser(session) -> tuple[PlayerFeatures, Player]:
    """~1600, low blunder rate, reaches winning endgames but doesn't convert.

    Expected to fire: endgame_conversion (< 0.60).
    Playstyle should be balanced / mildly positional.
    """
    player = _make_player(session, username="endgame_loser", rating=1610)

    game_configs = []
    for i in range(12):
        game_configs.append(
            {
                "time_class": "rapid",
                "result": "loss" if i < 6 else "draw" if i < 9 else "win",
                "opening_eco": f"E{6 + i % 3}0",
                "opponent_rating": 1650 + i,
                "game_url": f"https://www.chess.com/game/live/{4000 + i}",
            }
        )

    for i, cfg in enumerate(game_configs):
        game = _make_game(session, player, i=i, **cfg)
        rows = _build_rows(
            ply_count=65,
            cp_loss=20,
            classification="ok",
            eval_amplitude=100,
            capture_san="Nf3",  # no capture token
            quiet_san="c4",
            include_castles=True,
            fen=_QUEENLESS_FEN,
        )
        # Winning endgame reached at ply 45.
        for row in rows:
            if row["ply"] == 45:
                row["phase"] = "endgame"
                row["eval_cp_before"] = 300
        _insert_rows(session, game, rows)

    return load_features(session, "chesscom", player.username), player
