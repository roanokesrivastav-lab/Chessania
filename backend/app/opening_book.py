"""Derive ECO code and opening name from a game's PGN.

Session 31a: Chess.com's archive API returns no opening data, so we fill
`games.opening_eco` / `games.opening_name` from the stored PGN using a
public-domain opening book. Lichess games already arrive with authoritative
opening data and are never overridden.

The book is the lichess-org/chess-openings dataset (CC0), vendored in
app/data/openings_book/ as five TSV files (a.tsv..e.tsv). Each row gives an
ECO code, opening name, and SAN move sequence. At import time we parse each
sequence into a UCI move tuple and build a lookup table. classify_opening()
replays a game's mainline, checks every prefix against the book, and returns
the (eco, name) of the longest matching prefix — the most specific named
variation that the game reached.
"""

from __future__ import annotations

import csv
import io
import os
from typing import TYPE_CHECKING

import chess.pgn

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Load the public-domain opening book once at import time.
# ---------------------------------------------------------------------------

_BOOK: dict[tuple[str, ...], tuple[str, str]] = {}
_MAX_DEPTH = 0


def _load_book() -> None:
    global _MAX_DEPTH

    base_dir = os.path.join(os.path.dirname(__file__), "data", "openings_book")
    for file_name in ("a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv"):
        path = os.path.join(base_dir, file_name)
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                pgn_text = row.get("pgn", "").strip()
                if not pgn_text:
                    continue

                # The TSV move sequences are bare SAN (e.g. "1. e4 e5 ...");
                # python-chess parses them fine without headers.
                parsed = chess.pgn.read_game(io.StringIO(pgn_text))
                if parsed is None:
                    continue

                uci_moves = tuple(m.uci() for m in parsed.mainline_moves())
                if not uci_moves:
                    continue

                _BOOK[uci_moves] = (row["eco"].strip(), row["name"].strip())
                _MAX_DEPTH = max(_MAX_DEPTH, len(uci_moves))


_load_book()


def classify_opening(pgn: str) -> tuple[str | None, str | None]:
    """Return the (eco, name) of the deepest opening-book prefix reached by
    the given PGN, or (None, None) when no prefix matches.

    The lookup uses UCI move tuples so transpositions inside the book are not
    followed — we match the exact move order recorded in the book. This is
    deterministic, offline, and good enough for populating missing ECO data.
    """
    if not pgn:
        return None, None

    parsed = chess.pgn.read_game(io.StringIO(pgn))
    if parsed is None:
        return None, None

    uci_moves = [m.uci() for m in parsed.mainline_moves()]
    if not uci_moves:
        return None, None

    # Cap at the deepest line the book knows about; longer prefixes cannot
    # possibly match.
    capped = uci_moves[:_MAX_DEPTH]

    # Longest-prefix match: check from full depth down to the first move.
    for depth in range(len(capped), 0, -1):
        prefix = tuple(capped[:depth])
        if prefix in _BOOK:
            return _BOOK[prefix]

    return None, None


def book_size() -> int:
    """Return the number of distinct move-sequence entries loaded from the
    opening book. Exposed mainly for tests and diagnostics."""
    return len(_BOOK)
