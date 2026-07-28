CHESSANIA V2 ROADMAP — THE TRAINING PLATFORM
=============================================

Status: v1.0 structure + full session specs (founder-approved decisions
2026-07-27). Fine detail still refined in plan mode before each session,
same as v1; [REFINE] marks the few spots needing live research (exact
external-API shapes, provider pick, dataset sizing) — everything else is
specced to build.

This document governs v2 ONLY. CHESSANIA_ROADMAP.md remains the law for
v1 (the coaching-report product, now including its post-launch Phase 5
"Deeper Analytics"). Where the two conflict about v2, this file wins;
where silent, v1's rules carry over.

________________


PART 0 — WHAT V2 IS (AND ISN'T)
================================

v1 = the mirror. Type a username, get a brutally specific coaching
report from your own games. Read-only, no signup, rule-based.

v2 = the gym. Every weakness the report finds becomes something you can
DRILL — starting from your own real positions, not generic exercises.
The wedge over Aimchess: their trainers are generic; ours start from
the user's own games ("here is the exact position where YOU threw away
+3 last Tuesday — convert it this time"), and every number stays
transparent and clickable back to the real game.

FOUNDER DECISIONS (locked 2026-07-27; change only by editing this Part):

D1. v2 scope = trainers + live practice ONLY. Deeper analytics (advantage
    capitalization, per-variation openings, resourcefulness, tilt, time,
    stat explainers, category dashboard, tiered 100-game deep dives) is
    v1 Phase 5 in CHESSANIA_ROADMAP.md, NOT here. v2 CONSUMES those
    metrics; it does not build them.
D2. Unlocked for v2 (banned in v1): chessboard renderer (via an
    open-source library, never from scratch), user accounts, realtime
    infra. STILL LOCKED: LLM-phrased coaching (revisit only at real
    scale — founder will decide then), ML models, hand-authored puzzles.
D3. Live person-vs-person practice ships TWICE: first the cheap way
    (Lichess challenge-links from a custom FEN — no board, no sockets),
    then natively in the final phases IF the cheap version shows pull.
D4. Audience sequencing: friends + self beta FIRST (mostly chess.com
    accounts), THEN public launch aimed lichess-first. Monetization is
    out of scope for this entire roadmap.
D5. Prerequisite gate: v2 Phase T0 may not start until v1 has shipped
    through S25 AND the friends beta (S26+) is live. Near-term priority
    after that is v1 Phase 5 analytics ("finish v1"); v2 follows, though
    T0 foundations may begin in parallel once the gate opens. Never two
    in-flight sessions at once.

FOUNDER DECISIONS — v2 mechanics (locked 2026-07-27):

M1. Trainer scoring = TWO-TIER. A move "passes" if it didn't blunder
    (stayed within a safe cp band of best, band in config); it's
    "Perfect" if it matched the engine's top move. Never a single harsh
    best-move-only gate — sub-1800 players need the good-enough win
    acknowledged, with precision still rewarded.
M2. Position bank = CONTINUOUS + GROWING. Every v1 analysis (standard OR
    deep-dive) mines positions into a PERSISTENT personal bank that
    accumulates across reports over time. Drills pull from the whole
    bank, not just the latest report. This is what makes "retry
    mistakes from PAST games" real.
M3. Auth = EMAIL MAGIC-LINK primary (works for chess.com friends who
    have no OAuth), Lichess OAuth as a one-tap bonus. Guest mode always
    works for every trainer (progress just doesn't persist). No
    passwords, ever.

WORKFLOW (unchanged from v1): Opus researches + plans one session →
founder approves → Kimi codes + commits (never pushes) → Opus reviews,
verifies live, fixes with permission, logs STATE.md (honesty tags),
pushes. One vertical slice per session. Plain language throughout.

________________


PART A — CARDINAL RULES FOR V2
===============================

A1. Everything in v1 Part A still applies except where D2 unlocks it.
A2. Board = library, never bespoke. chessground (MIT, Lichess's board) +
    chessops for legality. Writing piece-movement math = the session is
    wrong.
A3. Own-games first. Every trainer that CAN be seeded from the user's
    analyzed games MUST be, before any generic content is added. Generic
    tactics come ONLY from the Lichess puzzle DB (CC0) — never
    hand-authored, never scraped.
A4. Engine in the browser. Trainer play/validation uses stockfish.wasm
    client-side (free, private, zero server load). The server engine
    (depth 12) stays reserved for report analysis; a trainer adding
    server engine load must justify it in its plan.
A5. Accounts are thin (M3). Auth persists progress/streaks and addresses
    duels to a person — nothing else. Guest mode always works.
A6. The report stays free and signup-less FOREVER. v2 must never gate a
    v1 report behind an account.
A7. Own numbers everywhere (v1 Locked 8 carries over): "You converted
    53% of your +3 games — these drills are those 8 unconverted
    positions."
A8. Tests offline: fixture FENs + canned engine lines; stockfish.wasm
    and websockets mocked in unit tests. Realtime gets its own opt-in
    integration harness in T6 (like v1's `pytest -m engine`).
A9. Schema changes live in Appendix V2-1; appendix-first discipline
    (tune appendix, then code).
A10. Cuttable-by-design: Phase T4 and everything after are explicitly
    cuttable if beta says the core loop matters more. A cuttable session
    never blocks a core one.
A11. Two-tier scoring (M1) is uniform across every trainer — one shared
    grading helper, not per-trainer reinvention.

________________


PART B — ARCHITECTURE DELTAS (v1 → v2)
=======================================

Frontend (Vercel, Next.js — unchanged host):
  + components/board/Board.tsx — chessground wrapped ONCE (FEN in, legal
    moves via chessops, onMove out, flip, phone-first, a11y). Every
    trainer reuses this wrapper; no trainer imports chessground directly.
  + lib/engine.ts — stockfish.wasm in a Web Worker behind a seam
    mirroring v1's Evaluator (real engine in prod, FixtureEngine in
    tests). One shared grade(move, bestLine, band) → "perfect|pass|fail"
    (M1/A11).
  + /train/* and /duel/* route trees; v1 report issue-cards deep-link in.

Backend (Railway, FastAPI — unchanged host):
  + auth: email magic-link primary + Lichess OAuth (PKCE) bonus;
    httpOnly session cookie; users table. No passwords (M3).
  + new tables (Appendix V2-1): users, training_positions, attempts,
    duels, streaks.
  + mining service: turns a player's existing MoveEval rows into
    training_positions, run after every analysis, ACCUMULATING (M2).
    Pure SQL/python over data v1 already stores — no new engine work.
  + Phase T6 only: FastAPI-native websocket endpoint + in-memory room
    registry. A broker/queue (Redis/Celery) is added ONLY if native
    measurably fails — never pre-built.

Data sources:
  + Lichess puzzle DB (CC0 dump): a rating-banded subset imported once
    into Postgres, themed. Weakness→theme mapping is Appendix V2-3, LAW
    like v1's openings.json.

________________


PART C — PHASES AND SESSIONS
=============================

Numbering V2-S1… Estimates assume the Kimi/Opus workflow. Each session:
Goal · Steps · Definition of Done. [REFINE] = Opus researches the exact
detail in that session's plan.


PHASE T0 — FOUNDATIONS (board, accounts, position bank)
--------------------------------------------------------
Exit: a signed-in (or guest) user sees a board rendering any FEN on
their phone, and the DB holds an accumulating bank of training positions
mined from their own analyzed games.

V2-S1 — The board component
  Est: 3h · Prereq: v1 S25 + beta (D5)
  Goal: ONE reusable Board wrapper on chessground + chessops: FEN in,
  legal moves enforced, onMove callback, flip, promotion picker,
  last-move + check highlight, phone-width perfect, keyboard-accessible.
  Steps:
  1. Add chessground + chessops; build components/board/Board.tsx with a
     typed props contract (fen, orientation, onMove, highlights,
     interactable?).
  2. A /train/board-demo dev page: render a fixed FEN, play both sides,
     flip, confirm illegal moves are rejected by chessops (not by us).
  3. Mobile pass: piece drag + tap-tap move both work at iPhone width.
  DoD: founder plays both sides of a Philidor position on their phone;
  NO trainer logic anywhere yet; illegal moves impossible.

V2-S2 — Accounts (thin, magic-link primary)  [REFINE: email provider]
  Est: 4h · Prereq: V2-S1
  Goal: passwordless auth that works for every friend (M3), guest mode
  default, nothing else gated.
  Steps:
  1. users table (Appendix V2-1); httpOnly signed session cookie.
  2. Email magic-link: request → signed single-use short-TTL token
     (stored hashed) → email → verify → session. Provider = a free-tier
     transactional email service (default Resend; confirm in-session).
  3. Lichess OAuth (PKCE) as a second "Sign in with Lichess" button that
     upserts the same users row (links lichess_id).
  4. Header shows "Sign in to save progress" / the display name;
     sign-out; guest sessions carry an anonymous id so a later sign-in
     can adopt their progress.
  5. Prove the v1 report flow is byte-identical when signed out (A6).
  DoD: founder signs in via email link on phone; a friend signs in with
  Lichess; sign-out works; report flow provably unchanged as guest.

V2-S3 — Position mining (the growing bank)  (M2)
  Est: 4h · Prereq: V2-S2
  Goal: extract training_positions from existing MoveEval data, per
  player, ACCUMULATING across every analysis — never wiping the bank.
  Categories: (a) blunder positions (the ply BEFORE each classified
  blunder + the game's best line), (b) unconverted advantages (first ply
  the player's POV crossed +winning in a game NOT won), (c) danger
  positions (a missed opponent threat), (d) endgame entries from
  lost/drawn winning endgames.
  Steps:
  1. training_positions schema (Appendix V2-1) with a dedupe key
     (player_id + source_game_id + ply + category) so re-analysis
     doesn't duplicate; mined_at + last_seen for freshness ordering.
  2. mining service: pure python/SQL over MoveEval
     (eval_cp_before/after, cp_loss, classification, phase, best_move,
     player_color, ply, fen_before) → rows per category.
  3. Hook it to run after each v1 analysis job (standard AND deep-dive)
     and a backfill entrypoint for existing players.
  4. Offline tests on fixture evals: each category extracts the expected
     plies; re-running is idempotent (no dupes, bank grows only with new
     games).
  DoD: founder's account shows N accumulated positions across ≥2
  analyses in a dev endpoint, spot-checked against 3 real games; tests
  green, idempotent.


PHASE T1 — THE MISTAKE LOOP (own-games trainers — the wedge)
-------------------------------------------------------------
Exit: each v1 report issue-card links to a trainer seeded from that
user's own bank, graded two-tier (M1), with attempts + streaks
persisting.

V2-S4 — Retry Your Mistakes
  Est: 4h · Prereq: V2-S3
  Goal: /train/retry replays the user's blunder positions; two-tier
  grading; progress persists.
  Steps:
  1. Trainer shell (reused by later trainers): pull a set from the bank,
     Board wrapper, submit-move → lib/engine.ts grade() → perfect/pass/
     fail feedback → show best line → next.
  2. Grade band + "winning-enough" thresholds in config (M1/A11).
  3. attempts rows (grade, seconds); streaks updated; guest = no persist.
  4. Empty state for new accounts with an empty bank ("play + analyze a
     few games and your misses will appear here").
  DoD: founder retries 5 of their own real blunders on phone; a perfect
  and a pass both register correctly; guest mode works sans persistence.

V2-S5 — Blunder Preventer
  Est: 3h · Prereq: V2-S4
  Goal: /train/preventer on danger positions (category c): "opponent
  just played X — what's the threat, and how do you meet it?" Same
  shell, same two-tier grading.
  Steps:
  1. Feed category-c positions into the trainer shell; frame the prompt
     around the threat rather than "best move".
  2. Grade the defensive resource two-tier; explain the threat on fail.
  3. Attempts/streaks reuse V2-S4 plumbing.
  DoD: founder completes a 10-position defensive set from their own
  games; kind wrong-answer UX.

V2-S6 — Advantage Capitalization Trainer
  Est: 4h · Prereq: V2-S4; v1 S28 (capitalization metric)
  Goal: /train/convert — the user's unconverted winning positions,
  PLAYED OUT against stockfish.wasm (limited, configurable strength)
  until mate/draw/resign. Win = converted.
  Steps:
  1. Playout mode in the shell: user vs wasm from the bank FEN; wasm at
     a capped level; detect terminal + adjudicate (winning eval held to
     mate = converted; blundered back to equal = not).
  2. Intro copy ties to the v1 metric ("you converted 53% — convert
     these 8 now"), numbers interpolated (A7).
  3. Record converted/failed as an attempt; streak on conversions.
  DoD: founder wins (or honestly loses) a full playout from one of their
  own real unconverted games on phone.

V2-S7 — Report ↔ trainer deep links
  Est: 2h · Prereq: V2-S4..S6
  Goal: every v1 issue-card gains a "Train this" button routing to the
  right trainer pre-filtered by the cited games.
  Steps:
  1. Mapping (Appendix V2-3): issue key → trainer route + filter.
  2. Buttons on the report; the trainer accepts a filter (game ids /
     category) so the drill is the exact positions the card cited.
  DoD: founder taps from their live report into a drill seeded by the
  exact games the card referenced.


PHASE T2 — GENERIC SKILLS (Lichess puzzle DB)
----------------------------------------------
Exit: weakness-themed tactics work even for users with a thin bank.

V2-S8 — Puzzle DB import + theme mapping  [REFINE: subset size/storage]
  Est: 3h · Prereq: V2-S3
  Goal: import a rating-banded subset of the CC0 Lichess puzzle CSV,
  themed; map report weaknesses → themes; serve puzzles near the user's
  rating.
  Steps:
  1. Import script: filter the dump to a sane band (default rating
     ~600–2000) and needed columns; store themed. Target footprint
     <500MB (confirm exact subset in-session).
  2. Appendix V2-3 weakness→theme table completed (LAW).
  3. Selection API: themes + rating window → puzzle set.
  4. Offline tests on a small fixture CSV slice.
  DoD: dev endpoint returns sane themed, rating-appropriate sets; tests
  green on the fixture slice.

V2-S9 — Tactics + Checkmate Patterns trainers
  Est: 3h · Prereq: V2-S8
  Goal: /train/tactics and /train/mates — classic multi-move puzzle solve
  on the Board wrapper, validated move-by-move, themed by the user's
  report weaknesses, rating-adaptive.
  Steps:
  1. Puzzle mode in the shell: play the solution line, validate each
     ply, opponent auto-replies, wrong move = kind retry.
  2. Theme selection defaults to the user's top weakness themes; manual
     theme picker too.
  3. Rating steps up/down with the two-tier result; attempts recorded.
  DoD: founder solves a themed set matched to their report; wrong-move
  UX reads kindly; rating adapts.

V2-S10 — Endgame + Defender trainers
  Est: 3h · Prereq: V2-S9
  Goal: /train/endgames (endgame-theme puzzles + playouts of curated
  won/drawn endgame FENs vs wasm) and /train/defender (defensive themes).
  Steps:
  1. Curated FEN library (Appendix V2-4): K+P, Lucena, Philidor, R+4v3,
     opposite bishops, each with a one-line "why this matters at your
     level".
  2. Endgame playouts reuse the V2-S6 playout mode; Defender reuses the
     puzzle mode filtered to defensive themes.
  3. Attempts/streaks reused.
  DoD: founder holds a drawn rook endgame vs the engine on phone;
  defender set completes.


PHASE T3 — LIVE PRACTICE v0 (the clever path)  (D3)
----------------------------------------------------
Exit: two friends practice a set position against each other tonight,
with ZERO realtime code written.

V2-S11 — Position Duels via Lichess challenge links  [REFINE: exact API]
  Est: 3h · Prereq: V2-S2
  Goal: pick any position (bank / curated / pasted FEN) → create a
  Lichess challenge FROM that FEN → two share-links (one per color) →
  "swap & replay" regenerates with colors flipped. Duel recorded.
  Steps:
  1. Research the Lichess challenge API path for a custom-FEN open
     challenge (variant fromPosition + fen); decide unauth open-challenge
     vs OAuth-created challenge — spec both, pick the one that lets a
     chess.com friend create without a Lichess account if possible.
  2. Backend endpoint: FEN → challenge → store a duels row with the two
     URLs; return them.
  3. UI: position picker → "Duel a friend" → share the two links; a
     swap-colors button.
  DoD: founder + a friend play the SAME won-pawn endgame from both sides
  via shared links on their phones; duel stored.

V2-S12 — The duel library
  Est: 2h · Prereq: V2-S11
  Goal: /duel browsable library — "your unconverted positions", "classic
  endgames", "from your last report" — plus per-user duel history.
  Steps:
  1. Library views sourcing from the bank, Appendix V2-4, and the latest
     report.
  2. History list of created duels with quick "replay/swap".
  DoD: the friends-beta group runs 3 library duels in a week.


PHASE T4 — TIME + EXOTIC TRAINERS (cuttable per A10)
-----------------------------------------------------
V2-S13 — Time Trainer
  Est: 3h · Prereq: V2-S9; v1 time-coaching (Appendix 3)
  Goal: /train/time — the user's own time-trouble profile (from v1 clock
  data) fronts a countdown drill mirroring THEIR failure zone.
  Steps:
  1. Read the v1 time-coaching signals to identify the user's failure
     mode (too-fast-then-blundered / time-trouble collapse).
  2. Puzzle sets on a clock tuned to that mode; two-tier grade + a time
     component.
  3. Attempts record time + grade.
  DoD: founder runs a timed set that reflects their real time weakness.
  [REFINE: exact clock mechanics]

V2-S14 — Visualization + Blindfold Tactics
  Est: 4h · Prereq: V2-S9
  Goal: /train/visualize — show a position, announce/animate K moves,
  ask for the tactic in the FINAL position without showing it; Blindfold
  = pieces at opacity 0.
  Steps:
  1. Move-sequence renderer (progressive ghosting / hidden board).
  2. Answer + two-tier grade against the engine line.
  3. Difficulty ramp on move count / piece count.
  DoD: founder solves a 3-move visualization from a hidden final
  position. [REFINE: ramp]

V2-S15 — 360 / Intuition Trainer  (EXPLICITLY CUTTABLE)
  Est: 3h · Prereq: V2-S9
  Goal: rapid-fire "best square for this piece" / rotated-board pattern
  drills. Cut without ceremony if T5 needs the time.
  DoD (if built): founder runs an intuition set. [REFINE or CUT]


PHASE T5 — THE TRAINING DASHBOARD (retention)
----------------------------------------------
V2-S16 — Dashboard
  Est: 4h · Prereq: T1 done + ≥2 of T2
  Goal: /train home — streaks, per-trainer progress, weakness categories
  from the latest v1 report with "Train" buttons, and "what to drill
  today" ordered by the report's rating_impact. The click-through hub.
  Steps:
  1. Aggregate streaks + attempt stats per trainer for the user.
  2. Pull the latest report's weaknesses; order drills by rating_impact.
  3. "Today" queue + resume-where-you-left-off.
  DoD: founder's dashboard honestly reflects a week of their own use;
  phone-first; zero console errors.

V2-S17 — Progress feedback loop
  Est: 3h · Prereq: V2-S16
  Goal: close the loop — after ≥N drills + a re-analysis, show "trained
  endgames 40×; conversion 53% → 61%", with v1's honest low-signal
  hedges.
  Steps:
  1. Join attempt history against report deltas over time.
  2. Show movement per trained category; hedge small samples (v1 trend
     rules).
  DoD: at least one real metric visibly moves for one beta user (or the
  hedge copy shows honestly).


PHASE T6 — NATIVE LIVE PLAY (the endgame; build ONLY if T3 duels showed
real pull)  [REFINE all of T6 before starting — gated]
------------------------------------------------------------------------
V2-S18 — Websocket foundation
  Est: 4h — FastAPI-native websockets, in-memory room registry,
  presence, reconnect; opt-in integration-test harness (A8). No broker
  unless native measurably fails (B).
V2-S19 — Private rooms + clocks
  Est: 4h — create/join by code, chosen FEN, server-authoritative clocks
  + move validation (chessops server-side), spectate.
V2-S20 — Native position duels
  Est: 3h — both-sides swap, rematch, result → duels table; the
  Lichess-link path stays as fallback.
V2-S21 — Hardening for strangers
  Est: 3h — rate limits, abuse killswitches, idle-room reaping, load
  sanity check. GATE: T6 exits only if this passes.


PHASE T7 — PUBLIC, LICHESS-FIRST  (D4)
---------------------------------------
V2-S22 — Public onboarding polish
  Est: 3h — lichess-first landing copy, "how it works", ToS/privacy
  pages, OG polish for /train and /duel.
V2-S23 — DECISION GATE: public launch review
  Est: 2h — v1-S23-style honesty gate: cost ceilings (Part E) checked,
  abuse posture checked, founder walk of every surface. GO → announce on
  lichess community channels; FIX-FIRST loops back.
V2-S24+ — Public beta loop (weekly, like v1 S26+): watch, fix, decide
  what graduates from cuttable.

________________


PART D — DO-NOT-BUILD (v2 edition)
===================================

1. LLM-phrased coaching or LLM anything (D2 — locked until scale).
2. ML models of any kind (carryover).
3. A bespoke board renderer, move generator, or engine (A2/A4 —
   library + wasm only).
4. Hand-authored puzzles or scraped third-party content (A3).
5. Native mobile apps — PWA polish only.
6. Ratings, ladders, leaderboards, or strength-matchmaking for duels
   (friends/codes first; revisit only post-T7).
7. Opening-explorer clone, video lessons, coach marketplace, forums,
   chat beyond what a duel strictly needs.
8. Redis/Celery/broker BEFORE native websockets measurably need it (B).
9. Monetization of any kind (D4).
10. Anything gating a v1 report behind an account (A6).

________________


PART E — COST CEILINGS
=======================

Engine: all trainer engine work is client-side wasm — server engine
budget stays v1's. Puzzle DB: rating-banded subset, target <500MB in
Postgres (V2-S8). Realtime: FastAPI-native on the existing Railway
service until T6 hardening proves otherwise. Auth email: free-tier
magic-link provider (V2-S2). The hosting bill must not change
order-of-magnitude before T7.

________________


APPENDICES (LAW — tune here first, then code)
==============================================

Appendix V2-1 — Schema deltas  [REFINE exact types before V2-S2/S3]
  users(id, created_at, email?, email_verified_at?, lichess_id?,
    display_name, anon_id?)   -- anon_id lets a guest's progress be
                                 adopted at first sign-in
  training_positions(id, player_id, source_game_id, ply, fen,
    category[blunder|unconverted|danger|endgame], best_line_uci,
    eval_before_cp, mined_at, last_seen)
    UNIQUE(player_id, source_game_id, ply, category)   -- M2 idempotent
  attempts(id, user_id, ref_type[position|puzzle|duel], ref_id, trainer,
    grade[perfect|pass|fail], seconds, created_at)      -- M1 two-tier
  duels(id, creator_user_id?, fen, source, lichess_urls_json, result?,
    created_at)
  streaks(user_id, trainer, current, best, last_active_date)

Appendix V2-2 — Trainer spec template  [Opus fills per session]
  name · route · seed source (bank category / puzzle themes / curated
  FEN) · mode (solve | playout-vs-wasm) · GRADE (two-tier band from M1;
  the shared grade() helper) · attempt record · empty-state copy (thin
  bank / new account) · guest behavior · phone-first layout notes.

Appendix V2-3 — Weakness → training mapping  [complete before T2]
  hung_pieces         → retry + preventer + themes[hangingPiece]
  blunder_rate        → retry + themes[advantage, crushing]
  endgame_conversion  → convert + endgames + themes[rookEndgame, pawnEndgame,...]
  opening_leak        → v1 rec cards + duels from move-20 positions
  advantage_capitalization (v1 S28) → convert trainer
  resourcefulness / missed_saves (v1 S29) → preventer + themes[defensiveMove]
  tilt (v1 S30)       → (dashboard nudge; no drill — behavioral)
  time_trouble (v1 Appendix 3) → time trainer
  ... (finish the table before V2-S8 ships)

Appendix V2-4 — Curated duel/endgame FEN library  [REFINE at V2-S10/S11]
  Seed: K+P conversions, Lucena, Philidor, R+4v3, Q vs R, opposite
  bishops — each with a one-line "why this matters at your level" and a
  color-to-move note.

________________


PROGRESS CHECKLIST
==================

T0: [ ] V2-S1 [ ] V2-S2 [ ] V2-S3
T1: [ ] V2-S4 [ ] V2-S5 [ ] V2-S6 [ ] V2-S7
T2: [ ] V2-S8 [ ] V2-S9 [ ] V2-S10
T3: [ ] V2-S11 [ ] V2-S12
T4: [ ] V2-S13 [ ] V2-S14 [ ] V2-S15 (cuttable)
T5: [ ] V2-S16 [ ] V2-S17
T6: [ ] V2-S18 [ ] V2-S19 [ ] V2-S20 [ ] V2-S21 (gated on T3 pull)
T7: [ ] V2-S22 [ ] V2-S23 gate [ ] public beta loop
