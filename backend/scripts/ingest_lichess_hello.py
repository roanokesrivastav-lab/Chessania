"""Session 6 manual check: run the real Lichess fetcher against a live
account and print what came back, so a human can spot-check a few games
against what lichess.org itself shows for that account.

Run: python scripts/ingest_lichess_hello.py <username>
(defaults to a public account if no username is given)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest import (
    NoEligibleGames,
    PlayerNotFound,
    UpstreamError,
    UpstreamRateLimited,
    fetch_lichess,
)


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else "DrNykterstein"

    try:
        games = fetch_lichess(username)
    except PlayerNotFound:
        print(f"No such Lichess account: {username}")
        return
    except NoEligibleGames:
        print(f"{username} has no eligible (rapid/blitz) games.")
        return
    except UpstreamRateLimited:
        print("Lichess rate-limited us — try again in a minute.")
        return
    except UpstreamError as e:
        print(f"Lichess returned an unexpected error: {e}")
        return

    print(f"{len(games)} eligible game(s) for {username}:\n")
    header = (
        f"{'played_at':20} {'time_class':10} {'color':6} {'result':6} "
        f"{'rating':7} {'opp':7} {'eco':5}  url"
    )
    print(header)
    print("-" * len(header))
    for g in games:
        played = g.played_at.strftime("%Y-%m-%d %H:%M") if g.played_at else "?"
        print(
            f"{played:20} {g.time_class:10} {g.player_color:6} {g.result:6} "
            f"{str(g.player_rating):7} {str(g.opponent_rating):7} "
            f"{(g.opening_eco or '-'):5}  {g.game_url}"
        )


if __name__ == "__main__":
    main()
