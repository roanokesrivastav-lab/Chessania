"""Session 17 — specificity and banned-phrase quality gate.

Every coaching sentence must contain a digit or a concrete game reference,
and the four Appendix-3 banned phrases are only allowed if the same sentence
also contains a digit.  These tests audit the rendered Report for all three
golden-report profiles.
"""

from __future__ import annotations

import re

import pytest

from app.coach import build_report
from tests.fixtures.features.builders import (
    build_endgame_loser,
    build_positional_leaker,
    build_tactical_blunderer,
)

_BANNED_PHRASES = [
    "study tactics",
    "practice more",
    "improve your endgame",
    "work on openings",
]

_BUILDERS = [
    build_tactical_blunderer,
    build_positional_leaker,
    build_endgame_loser,
]


# ---------------------------------------------------------------------------
# Collect the strings that the audit cares about.
# ---------------------------------------------------------------------------


def _coaching_strings(report) -> list[str]:
    """Return every issue diagnosis/prescription/success_metric, plus every
    strength detail and every opening recommendation "why".

    counter_evidence is intentionally excluded: the Session 17 audit only
    covers diagnosis, prescription, success_metric, strength.detail, and
    opening_rec.why.
    """
    strings: list[str] = []
    for issue in report.issues:
        strings.append(issue.diagnosis)
        strings.append(issue.prescription)
        strings.append(issue.success_metric)
    for strength in report.strengths:
        strings.append(strength.detail)
    for rec in report.opening_recs:
        strings.append(rec.why)
    return strings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contains_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


_URL_RE = re.compile(r"https?://\S+")
_SAN_RE = re.compile(r"\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8]|O-O(?:-O)?)\b")
_GAME_N_RE = re.compile(r"\bgame\s+\d+", re.IGNORECASE)


def _contains_game_reference(text: str) -> bool:
    """A URL, a move-SAN token, or an explicit ``game N`` citation counts as a
    game reference for the specificity audit."""
    if _URL_RE.search(text):
        return True
    if _SAN_RE.search(text):
        return True
    if _GAME_N_RE.search(text):
        return True
    return False


def _sentences(text: str) -> list[str]:
    """Naive sentence split that is sufficient for the short coaching strings."""
    return [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]


# ---------------------------------------------------------------------------
# Audits
# ---------------------------------------------------------------------------


def test_coaching_strings_are_specific_or_reference_a_game(db_session):
    """Every coaching string has a digit or a URL/move-SAN/game-N reference."""
    failures: list[tuple[str, str]] = []

    for builder in _BUILDERS:
        features, player = builder(db_session)
        report = build_report(features, db_session, player)
        for text in _coaching_strings(report):
            if not _contains_digit(text) and not _contains_game_reference(text):
                failures.append((builder.__name__, text))

    if failures:
        formatted = "\n".join(f"  [{name}] {text!r}" for name, text in failures)
        raise AssertionError(f"Digit-less, game-reference-less coaching strings:\n{formatted}")


def test_banned_phrases_appear_only_with_digits(db_session):
    """The four Appendix-3 banned phrases are only allowed in sentences that
    also contain a digit."""
    failures: list[tuple[str, str, str]] = []

    for builder in _BUILDERS:
        features, player = builder(db_session)
        report = build_report(features, db_session, player)
        for text in _coaching_strings(report):
            lower_text = text.lower()
            for phrase in _BANNED_PHRASES:
                if phrase in lower_text:
                    for sentence in _sentences(text):
                        if phrase in sentence.lower() and not _contains_digit(sentence):
                            failures.append((builder.__name__, phrase, sentence))

    if failures:
        formatted = "\n".join(
            f"  [{builder}] banned phrase {phrase!r} in digit-less sentence: {sentence!r}"
            for builder, phrase, sentence in failures
        )
        raise AssertionError(f"Banned phrase violations:\n{formatted}")
