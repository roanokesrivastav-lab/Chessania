"""Session 16 — playstyle-aware opening recommendations.

The recommendation table lives in app/data/openings.json (Appendix 4). This
module loads it once at import, then turns a playstyle bucket and the
player's current repertoire into exactly two OpeningRec objects: one for
White, one for Black.

The output is deterministic and template-based — no LLM, no ML, no invented
chess content. Every rec's why string contains digits (the line move order
and the player's own playstyle component numbers), satisfying the S17
banned-phrase guard before it even runs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app import schemas
from app.features import PlayerFeatures


# ---------------------------------------------------------------------------
# Load the committed recommendation table once at import time.
# ---------------------------------------------------------------------------


_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "openings.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _OPENINGS: list[dict[str, Any]] = json.load(_f)


# ---------------------------------------------------------------------------
# ECO matching
# ---------------------------------------------------------------------------


def _eco_in_family(code: str | None, family: str) -> bool:
    """Return whether a concrete ECO code (e.g. 'B12') belongs to a family
    description from openings.json.

    Supported family formats:
    * single code: "D02", "C50"
    * range: "C50–C54" (en-dash) or "C50-C54" (ASCII hyphen)
    * open-ended: "E60+", "D06+" (this letter, this number or higher)
    * None code -> False
    * wrong letter -> False
    """
    if code is None or not code.strip():
        return False

    code = code.strip().upper()
    family = family.strip()

    m = re.match(r"^([A-E])(\d+)$", code)
    if not m:
        return False

    code_letter = m.group(1)
    code_num = int(m.group(2))

    # Normalize en-dash to ASCII hyphen for uniform parsing.
    family_norm = family.replace("–", "-").strip()

    # Open-ended: E60+
    if family_norm.endswith("+"):
        base = family_norm[:-1].strip()
        mm = re.match(r"^([A-E])(\d+)$", base)
        if not mm:
            return False
        return code_letter == mm.group(1) and code_num >= int(mm.group(2))

    # Range: C50-C54
    if "-" in family_norm:
        start, end = family_norm.split("-", 1)
        start = start.strip()
        end = end.strip()
        ms = re.match(r"^([A-E])(\d+)$", start)
        me = re.match(r"^([A-E])(\d+)$", end)
        if not ms or not me:
            return False
        if code_letter != ms.group(1):
            return False
        if code_letter != me.group(1):
            return False
        return int(ms.group(2)) <= code_num <= int(me.group(2))

    # Single code.
    ms = re.match(r"^([A-E])(\d+)$", family_norm)
    if not ms:
        return False
    return code_letter == ms.group(1) and code_num == int(ms.group(2))


# ---------------------------------------------------------------------------
# Recommendation builder
# ---------------------------------------------------------------------------


def _primary_and_alt(bucket: str, color: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (primary, alt) entries for a (bucket, color) pair."""
    entries = [e for e in _OPENINGS if e["bucket"] == bucket and e["color"] == color]
    primary = next(e for e in entries if e["role"] == "primary")
    alt = next(e for e in entries if e["role"] == "alt")
    return primary, alt


def _top_two_components(components: dict[str, float]) -> list[tuple[str, float]]:
    """The two playstyle components with the largest absolute normalized
    values, or fewer if the dict is small."""
    sorted_components = sorted(components.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return sorted_components[:2]


def _component_label(name: str) -> str:
    """Human-readable name for a playstyle component."""
    return name.replace("_", " ")


def build_opening_recs(features: PlayerFeatures) -> list[schemas.OpeningRec]:
    """Return exactly two OpeningRecs (white, black) based on the player's
    playstyle bucket and current most-frequent ECO family per color.

    If the player already plays the primary recommendation, the copy switches
    to the deepen-don't-switch wording from Appendix 4 §Rules.
    """
    bucket = "balanced"
    components: dict[str, float] = {}
    if features.playstyle is not None:
        bucket = features.playstyle.label
        components = features.playstyle.components or {}

    top_two = _top_two_components(components)

    recs: list[schemas.OpeningRec] = []
    for color in ("white", "black"):
        primary, alt = _primary_and_alt(bucket, color)
        top_eco = features.top_eco_by_color.get(color) if features.top_eco_by_color else None
        already_plays = _eco_in_family(top_eco, primary["eco_family"])

        if already_plays:
            why = (
                f"You already play the {primary['name']} — and it fits you. "
                f"Don't switch; go one level deeper: {primary['line']}."
            )
            why += (
                f" If you want a second weapon, the {alt['name']} "
                f"({alt['line']}) is a natural companion."
            )
        else:
            why = primary["why_template"]
            if len(top_two) >= 2:
                (n1, v1), (n2, v2) = top_two[0], top_two[1]
                why += (
                    f" — your {_component_label(n1)} ({v1:.2f}) and "
                    f"{_component_label(n2)} ({v2:.2f}) point this way."
                )
            else:
                # Fallback that still satisfies the digit rule via the line.
                why += f" The move order {primary['line']} is a great fit."

        recs.append(
            schemas.OpeningRec(
                color=color,
                name=primary["name"],
                eco_family=primary["eco_family"],
                why=why,
                study_link=schemas.Link(
                    label=f"Study {primary['name']}",
                    url=primary["study_url"],
                ),
                already_plays=already_plays,
            )
        )

    return recs
