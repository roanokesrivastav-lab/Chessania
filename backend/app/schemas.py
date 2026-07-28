"""Appendix 2 — the Report contract.

Every model below mirrors the contract in CHESSANIA_ROADMAP.md line for
line. Changing any field here requires a matching change to Appendix 2
(and eventually the frontend types mirror), so this file is the
single source of truth for what a Chessania report looks like once it
leaves the backend.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field
from typing import Literal


class EvidenceRef(BaseModel):
    """A concrete (game, ply) citation so every Issue can point at an actual
    move instead of asserting a vibe."""

    game_url: str
    played_at: dt.datetime | None
    opponent_rating: int | None
    ply: int
    move_san: str
    detail: str


class Link(BaseModel):
    """A labelled external resource the player can follow."""

    label: str
    url: str


class Issue(BaseModel):
    """One coaching finding. The 2026-07-26 amendment adds four fields:
    success_metric, counter_evidence, rating_impact, and refresh_after."""

    key: str
    headline: str
    diagnosis: str
    prescription: str
    success_metric: str
    counter_evidence: str | None
    rating_impact: Literal["high", "medium", "low"]
    refresh_after: str
    links: list[Link]
    evidence: list[EvidenceRef]


class Strength(BaseModel):
    """Exactly one positive signal, with the number that earns it."""

    headline: str
    detail: str


class OpeningRec(BaseModel):
    """An opening recommendation. Built in S16; left empty in S15."""

    color: Literal["white", "black"]
    name: str
    eco_family: str
    why: str
    study_link: Link
    already_plays: bool


class Playstyle(BaseModel):
    """The tactical/positional/balanced index from Session 14."""

    label: Literal["tactical", "positional", "balanced"]
    score: float
    explanation: str
    components: dict[str, float]


class PhaseStats(BaseModel):
    """ACPL per phase."""

    opening: float
    middlegame: float
    endgame: float


class WLD(BaseModel):
    """Win/loss/draw tally."""

    win: int
    loss: int
    draw: int


class ColorStats(BaseModel):
    """Per-color weakness breakdown."""

    games: int
    results: WLD
    blunders_per_game: float
    acpl_overall: float | None
    acpl_by_phase: PhaseStats
    worst_phase: Literal["opening", "middlegame", "endgame"] | None
    opening_leak_rate: float
    endgame_conversion: float | None
    low_signal: bool


class StatsBlock(BaseModel):
    """The raw numbers block that appears in every report."""

    blunders_per_game: float
    mistakes_per_game: float
    acpl_overall: float
    acpl_by_phase: PhaseStats
    endgame_conversion: float | None
    advantage_capitalization: float | None
    accuracy_trend: Literal["improving", "flat", "declining", "insufficient_data"]
    per_game_acpl: list[float]
    by_color: dict[str, ColorStats] | None


class Delta(BaseModel):
    """A progress delta against a previous report. Left empty in S15."""

    metric: str
    previous: float
    current: float
    direction: Literal["better", "worse", "flat"]


class Progress(BaseModel):
    """Progress tracking. Left None in S15."""

    vs_previous: list[Delta]
    vs_first: list[Delta]
    previous_report_at: dt.datetime
    note: str | None


class PlayerSummary(BaseModel):
    """Header information about the player and the analyzed batch."""

    platform: Literal["chesscom", "lichess"]
    username: str
    rating: int | None
    games_analyzed: int
    date_range: str
    time_class_mix: str


class Report(BaseModel):
    """The full coaching report, exactly as stored in reports.report_json."""

    schema_version: int = 1
    player_summary: PlayerSummary
    playstyle: Playstyle
    strengths: list[Strength]
    issues: list[Issue]
    opening_recs: list[OpeningRec] = Field(default_factory=list)
    stats_block: StatsBlock
    progress: Progress | None
    generated_at: dt.datetime
    engine_depth: int
