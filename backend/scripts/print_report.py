#!/usr/bin/env python3
"""Pretty-print the latest stored coaching report for a player.

Usage (from the backend directory with the virtualenv activated):

    python scripts/print_report.py chesscom <username>
    python scripts/print_report.py lichess <username>
"""

from __future__ import annotations

import argparse
import sys

# Make app/ importable when running from the repo root.
sys.path.insert(0, "backend")

from app.db import SessionLocal
from app.models import Player, Report as ReportModel
from sqlalchemy import desc, select


def _fmt_date_range(value: str) -> str:
    return value if value else "—"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the latest coaching report for a player.")
    parser.add_argument("platform", choices=["chesscom", "lichess"], help="Platform the account is on.")
    parser.add_argument("username", help="Username on that platform.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        player = session.scalars(
            select(Player).where(
                Player.platform == args.platform,
                Player.username == args.username.lower(),
            )
        ).first()
        if player is None:
            print(f"No player found for {args.platform}/{args.username}.", file=sys.stderr)
            return 1

        report = session.scalars(
            select(ReportModel)
            .where(ReportModel.player_id == player.id)
            .order_by(desc(ReportModel.created_at))
        ).first()
        if report is None:
            print(f"No report yet for {args.platform}/{args.username} — run an analysis first.", file=sys.stderr)
            return 1

        data = report.report_json
        summary = data["player_summary"]
        playstyle = data["playstyle"]
        stats = data["stats_block"]

        print("=" * 60)
        print(f"Chessania report for {summary['username']} ({summary['platform']})")
        print(f"Rating: {summary['rating'] or 'not set'} | Games: {summary['games_analyzed']}")
        print(f"Date range: {_fmt_date_range(summary['date_range'])}")
        print(f"Time class mix: {summary['time_class_mix']}")
        print(f"Engine depth: {data['engine_depth']}")
        print("=" * 60)

        print(f"\nPlaystyle: {playstyle['label']} (score {playstyle['score']})")
        print(f"  {playstyle['explanation']}")

        print("\n--- Strengths ---")
        for strength in data["strengths"]:
            print(f"• {strength['headline']}")
            print(f"  {strength['detail']}")

        print(f"\n--- Stats ({stats['games_analyzed']} games) ---")
        print(f"Blunders/game: {stats['blunders_per_game']}")
        print(f"Mistakes/game: {stats['mistakes_per_game']}")
        print(f"ACPL: {stats['acpl_overall']}")
        print(
            f"  opening={stats['acpl_by_phase']['opening']} "
            f"middlegame={stats['acpl_by_phase']['middlegame']} "
            f"endgame={stats['acpl_by_phase']['endgame']}"
        )
        print(f"Accuracy trend: {stats['accuracy_trend']}")
        if stats.get("by_color"):
            print("\nBy color:")
            for color, cs in stats["by_color"].items():
                print(
                    f"  {color}: {cs['games']} games, {cs['blunders_per_game']} blunders/game, "
                    f"ACPL={cs['acpl_overall']}"
                )

        print(f"\n--- Issues ({len(data['issues'])}) ---")
        for issue in data["issues"]:
            print(f"\n[{issue['rating_impact'].upper()}] {issue['headline']}")
            print(f"Diagnosis: {issue['diagnosis']}")
            print(f"Prescription: {issue['prescription']}")
            print(f"Success metric: {issue['success_metric']}")
            if issue.get("counter_evidence"):
                print(f"Counter-evidence: {issue['counter_evidence']}")
            print(f"Refresh: {issue['refresh_after']}")
            for ev in issue["evidence"][:3]:
                print(f"  • move {ev['ply']} ({ev['move_san']}) — {ev['detail']}")

        print("\n" + "=" * 60)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
