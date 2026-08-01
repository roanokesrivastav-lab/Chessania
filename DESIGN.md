CHESSANIA — UI DESIGN SYSTEM
=============================

Status: adopted 2026-08-01 (founder). This is the canonical visual direction
for ALL Chessania frontend — the v1 report/landing (restyle whenever the
founder wants; not urgent) AND every v2 session, which is built to this system
from session one. "I might change the website design later" — so treat this as
the current law, not a permanent lock; when it changes, edit this file first.

Reference mockup (the agreed look, applied to real honest content):
https://claude.ai/code/artifact/dbc69c9e-b892-49f9-bdb7-1297d0c6d8f4

Direction in one line: **a dark-first, editorial "performance terminal" for
chess** — deep navy ground, warm gold + coral accents, serif headings over a
sans body over mono data. Premium and data-forward, not playful. It reads as a
serious self-evaluation instrument.


PRINCIPLES (information design — a report/dashboard is scanned, not read)
------------------------------------------------------------------------
1. Summary first, detail on demand. Lead with the at-a-glance category
   scorecard + the single biggest leak ("the red thread"); the full numbers
   and evidence come below / behind an expander.
2. Encode state in FORM, not just number — a severity stripe, a verdict chip,
   a colored dot. What needs attention must read in one scan.
3. Semantic color ≠ accent. The warm accents (gold, coral) are the brand;
   green/gold/coral as GOOD/WARN/CRIT verdicts are semantic and separate.
   Color always means something — never decoration.
4. NO composite black-box scores (founder decision, S32 + 2026-08-01). No
   single letter grade, no "84% overall". Every number shown is a real,
   transparent metric traceable to the games. The honest per-category
   scorecard replaces the grade.
5. The numbers ARE the credibility. Style interpolated numbers in a diagnosis
   like evidence — mono, tabular, chipped/highlighted — not like body text.
6. Mobile-first. Design at phone width first; nothing may cause horizontal
   page scroll (wide content scrolls inside its own container).
7. Both themes, real. Dark is primary/default; light is a warm-paper
   complement, given equal care via tokens (never a naive invert).


PALETTE (token values — define once, theme via tokens)
------------------------------------------------------
Neutrals are navy-biased (chosen toward the accents), not pure grey/black.

DARK (default):
  --bg #0e1523   --bg-2 #0a0f1a
  --surface #151d2e   --surface-2 #1b2436   --surface-3 #222d43
  --border #27324b   --border-soft #1d2637
  --text #eaedf4   --text-mid #a4aec1   --text-dim #737f97
  --gold #d9a441 (primary warm accent: strengths, streaks, positive, primary buttons)
  --gold-2 #e6b559 (hover)   --gold-bg rgba(217,164,65,0.12)
  --coral #e37c6b (critical leak / negative)   --coral-2 #ec8b79   --coral-bg rgba(227,124,107,0.13)
  --green #52ab7c (semantic GOOD: wins, converts, "strong")   --green-bg rgba(82,171,124,0.13)

LIGHT (warm paper):
  --bg #f3f0e9   --surface #fffdf8   --surface-2 #f6f2ea   --surface-3 #efe9dd
  --border #e0d8c8   --text #1c2233   --text-mid #545d70   --text-dim #7a8093
  --gold #b07d18   --coral #c8543f   --green #2f8f5c   (backgrounds at ~0.10–0.12 alpha)

Semantic mapping (verdicts & severity): GOOD=green, WARN=gold, CRIT=coral.


TYPOGRAPHY (system stacks — CSP blocks webfont CDNs; no linked webfonts)
-----------------------------------------------------------------------
  --serif: ui-serif, Georgia, "Iowan Old Style", "Palatino Linotype", "Times New Roman", serif
  --sans:  system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif
  --mono:  ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace

Roles:
  • SERIF — all headings, the hero username, big display headlines (editorial).
    text-wrap: balance on headings.
  • SANS — body copy, buttons, UI text.
  • MONO — every label/eyebrow (UPPERCASE, letter-spacing ~.1–.16em) AND every
    number/stat (font-variant-numeric: tabular-nums). This mono-for-data
    treatment is the "instrument" personality.

⚠ FIX FIRST when restyling v1: `frontend/app/globals.css` currently hard-codes
`body { font-family: Arial, ... }`, which OVERRIDES the loaded Geist fonts —
the app renders in Arial today. Replace with the stacks above.


COMPONENT TREATMENTS (the vocabulary — reuse, don't reinvent per screen)
------------------------------------------------------------------------
• Card — rounded (~14px), 1px --border, --surface, soft shadow. Elevate on hover.
• Category scorecard tile — a left severity stripe (crit/warn/good), category
  name, big serif/mono number + unit, and a verdict chip (colored dot + label).
  The at-a-glance summary; replaces any grade.
• "The red thread" hero issue card — the #1 leak. Coral left border + faint
  8×8 board-grid motif bleeding from a corner; a "⚑ Critical bottleneck"
  eyebrow, a "High impact" severity tag, a big serif headline, a diagnosis with
  the numbers chipped, a gold primary action ("Train …") + secondary link, and
  an expandable evidence list (date · opponent · move ↗ that deep-links out).
• Secondary issue card — same, lighter (gold left border, smaller headline).
• Signal card — a stat + a trend tag (↑/↓) + a mini canvas sparkline (area
  fill, emphasized endpoint). Green for improving, coral for a leak.
• Opening-performance panel — the player's repeated lines: name · ECO · color ·
  W-L-D · avg eval; a gold "⚑ fine out of book but losing" flag where it fires.
  (This is the self-eval replacement for the reference's cut "repertoire" slot.)
• Strength card — green-tinted, warm; always present, celebrates a real number.
• Result/quality timeline — a 20-cell heatmap (green win / coral loss / neutral
  draw; brighter = cleaner game). The "last 20 games" glance.
• Buttons — mono label; primary = gold fill (dark ink text); secondary =
  bordered ghost. Evidence/game links carry a ↗.

Motion: restrained. A gentle staggered rise on load; hover elevate; respect
prefers-reduced-motion. No gratuitous animation (it reads as AI-generated).


DO / DON'T (product decisions baked into the UI)
------------------------------------------------
DO: honest per-category verdicts · numbers traceable to games · evidence links
OUT to the real game on the platform · both themes · mobile-first.
DON'T: a single letter grade / composite score (#4) · opening-repertoire
TEACHING in the UI (v2 is self-eval, not instruction — show opening PERFORMANCE
instead) · "upload your games" (username-only, Part G #1) · an in-app board
render in the v1 report (evidence links out; the board arrives in v2 trainers).


APPLICATION
-----------
• v1 restyle (landing, /analyzing, the report + its S32 category dashboard):
  a later polish session — reskin to these tokens/type/components, no data-logic
  change. Fixes the Arial bug and the "mid" look at the root. Not urgent per the
  founder; do when ready.
• v2 (all of it): built to this system from V2-S1. The board wrapper, trainers,
  dashboard, and duel screens use these tokens, type roles, and card vocabulary.
  V2-S1 establishes the tokens in code (globals.css + a shared theme) so every
  later v2 session inherits them.
