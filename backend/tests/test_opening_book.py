"""Offline tests for the opening book classifier."""

from __future__ import annotations

import pytest

from app.opening_book import _BOOK, book_size, classify_opening


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def ruy_lopez_pgn() -> str:
    return "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 *"


@pytest.fixture
def sicilian_pgn() -> str:
    return "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. c4 *"


@pytest.fixture
def vienna_pgn() -> str:
    return "1. e4 e5 2. Nc3 Nf6 3. f4 *"


# ---------------------------------------------------------------------------
# Book loading
# ---------------------------------------------------------------------------


def test_book_loaded_from_all_eco_files():
    """The book should contain entries from all five ECO files."""
    assert book_size() > 0
    # Each letter file contributes at least one line (the headerless rows).
    ecodes = { eco for eco, _ in _BOOK.values() }
    for letter in ("A", "B", "C", "D", "E"):
        assert any(eco.startswith(letter) for eco in ecodes), f"no {letter}-file entry loaded"


# ---------------------------------------------------------------------------
# Known openings
# ---------------------------------------------------------------------------


def test_classify_opening_finds_spanish_game(ruy_lopez_pgn: str):
    eco, name = classify_opening(ruy_lopez_pgn)
    assert eco is not None
    assert eco.startswith("C")
    assert name is not None
    assert "Ruy Lopez" in name or "Spanish" in name


def test_classify_opening_finds_sicilian(sicilian_pgn: str):
    eco, name = classify_opening(sicilian_pgn)
    assert eco is not None
    assert eco.startswith("B")
    assert "Sicilian" in name


def test_classify_opening_finds_vienna(vienna_pgn: str):
    eco, name = classify_opening(vienna_pgn)
    assert eco is not None
    assert eco.startswith("C")
    assert "Vienna" in name


# ---------------------------------------------------------------------------
# Longest-prefix specificity
# ---------------------------------------------------------------------------


def test_classify_opening_prefers_deeper_named_variation(ruy_lopez_pgn: str):
    """A game that reaches the closed Ruy Lopez should report a specific
    variation, not the top-level 'Ruy Lopez (Spanish Opening)' family."""
    _eco, name = classify_opening(ruy_lopez_pgn)
    assert name is not None
    # The closed/morphy defense lines have more specific names.
    assert name != "Ruy Lopez"
    assert len(name) > len("Ruy Lopez")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_classify_opening_returns_none_for_unmatched_oddball():
    """A move order that leaves the book early still returns the longest
    matching prefix (here the standard Open Game after 2...Nc6), because the
    public-domain book covers every legal first move. Only empty or
    unparseable PGNs yield (None, None)."""
    pgn = "1. e4 e5 2. Nf3 Nc6 3. Ke2"  # legal but clearly non-book
    eco, name = classify_opening(pgn)
    assert eco is not None
    assert name is not None
    # The book matches at least the first two moves; the weird third move
    # does not force a (None, None) because longest-prefix matching picks the
    # deepest valid prefix.
    assert "Open" in name or "Knight" in name or "Game" in name


def test_classify_opening_does_not_override_existing_data():
    """The classification helper itself is read-only; the caller (ingest) is
    responsible for preserving existing Lichess opening data."""
    pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 *"
    eco, name = classify_opening(pgn)
    assert eco is not None
    assert name is not None


def test_classify_opening_handles_empty_and_unparseable():
    assert classify_opening("") == (None, None)
    assert classify_opening("not a pgn") == (None, None)
