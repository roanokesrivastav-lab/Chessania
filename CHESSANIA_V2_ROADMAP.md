CHESSANIA V2 ROADMAP — THE PROVING GROUND
==========================================

Status: SCOPE FINALIZED 2026-08-01 (founder). v2 is the FRIENDS BETA of the
training layer. Fine detail still refined in plan mode before each session,
same as v1; [REFINE] marks the few spots needing live research.

This document governs v2 ONLY. CHESSANIA_ROADMAP.md remains the law for v1
(the coaching-report product, now including its post-launch Phase 5 "Deeper
Analytics"). Where the two conflict about v2, this file wins; where silent,
v1's rules carry over.

________________


PART 0 — WHAT V2 IS (AND ISN'T)
================================

v1 = the mirror. Type a username, get a brutally specific coaching report
from your own games. Read-only, no signup, rule-based.

v2 = the proving ground. **Self-evaluation + self-testing.** Test yourself
on your own mistakes, and on set positions (mate it, hold it, win it —
against the engine or a friend). NOT an instructor: v2 does not teach opening
theory or run a generic puzzle grind — other apps (Lichess, Chess.com,
Aimchess) do that better. Chessania's wedge is showing you the truth about
your own game, then letting you prove you can fix it.

v3 = broaden reach (LATER, after the v2 friends beta). Everything deliberately
deferred lives in the v3 backlog (Part D) — native live play, generic
trainers, the puzzle DB, intuition calibration, public launch, monetization,
accessibility polish.

FOUNDER DECISIONS (locked 2026-07-27 → finalized 2026-08-01; change only by
editing this Part):

D1. v2 identity = SELF-EVALUATION + SELF-TESTING. No opening teaching, no
    generic puzzle trainers. Every trainer is either (a) seeded from the
    user's OWN analyzed games, or (b) a set-position challenge you test
    yourself on (mate / endgame / duel).
D2. Deeper-analytics work (advantage capitalization, per-variation openings,
    resourcefulness, tilt, stat explainers, category dashboard, tiered deep
    dives) is v1 Phase 5 (CHESSANIA_ROADMAP.md), DONE — v2 CONSUMES those
    metrics, does not build them.
D3. Unlocked for v2 (banned in v1): chessboard renderer (open-source library,
    never from scratch), user accounts, client-side engine (stockfish.wasm).
    STILL LOCKED: LLM coaching, ML models, hand-authored puzzles, and — new —
    NO server-side realtime infra in v2 (native live play is v3; v2's "play a
    friend" uses Lichess challenge links, zero realtime code).
D4. Live person-vs-person practice in v2 = **Lichess challenge links from a
    custom FEN only** (no matchmaking, no websockets). Native in-app live play
    → v3, built only if the link-duels show real pull.
D5. NO Lichess puzzle-DB import and NO generic trainers (Tactics, Defender,
    Visualization/Blindfold, Time) in v2 — all → v3. Checkmate and endgame
    self-tests run off small CURATED position sets, not a puzzle pool.
D6. Audience = friends + self ONLY for v2 (mostly Chess.com accounts). No
    public launch, no monetization in v2 — those are v3.
D7. Prerequisite gate: v2 Phase T0 may not start until v1 has shipped (S25 ✓)
    and Phase 5 analytics is founder-verified. Never two in-flight sessions at
    once.

MECHANICS (locked 2026-07-27):
M1. Trainer scoring = TWO-TIER. A move "passes" if it didn't blunder (within a
    safe cp band of best); "Perfect" if it matched the engine's top move.
    Never a single harsh best-move-only gate. One shared grade() helper.
M2. Position bank = CONTINUOUS + GROWING. Every v1 analysis (standard OR deep)
    mines positions into a PERSISTENT personal bank that accumulates across
    reports. Drills pull from the whole bank.
M3. Auth = EMAIL MAGIC-LINK primary (works for Chess.com friends with no
    OAuth), Lichess OAuth as a one-tap bonus. Guest mode always works for
    every trainer (progress just doesn't persist). No passwords, ever.

WORKFLOW (unchanged from v1): Opus plans one session → founder approves → Kimi
codes + commits (never pushes) → Opus reviews, verifies live, fixes with
permission, logs STATE.md → pushes. One vertical slice per session.

________________


PART A — CARDINAL RULES FOR V2
===============================

A1. Everything in v1 Part A still applies except where D3 unlocks it.
A2. Board = library, never bespoke. chessground (MIT, Lichess's board) +
    chessops for legality. Writing piece-movement math = the session is wrong.
A3. Own-games first. Every trainer that CAN be seeded from the user's analyzed
    games MUST be (T1). Set-position challenges (T2/T3) use small CURATED FEN
    sets committed in the repo — never a scraped or generic puzzle pool.
A4. Engine in the browser. Trainer play/validation uses stockfish.wasm
    client-side (free, private, zero server load). The v1 server engine stays
    reserved for report analysis.
A5. Accounts are thin (M3). Auth persists progress/streaks and addresses duels
    to a person — nothing else. Guest mode always works.
A6. The v1 report stays free and signup-less FOREVER. v2 must never gate a v1
    report behind an account.
A7. Own numbers everywhere (v1 Locked 8 carries over): "You converted 53% of
    your +3 games — these drills are those 8 unconverted positions."
A8. Tests offline: fixture FENs + canned engine lines; stockfish.wasm mocked in
    unit tests.
A9. Schema changes live in Appendix V2-1; appendix-first discipline.
A10. NO server realtime in v2 (D3/D4). If a v2 session finds itself wanting a
    websocket, it's a v3 feature — stop and flag it.
A11. UI follows DESIGN.md (adopted 2026-08-01) — the dark-first navy + gold/coral
    "performance terminal" system: its palette tokens, type roles (serif
    headings / sans body / mono data), component vocabulary, and DO/DON'T (no
    composite grade, no opening TEACHING in the UI, both themes, mobile-first).
    Every v2 screen is built to it; V2-S1 establishes the tokens in code.

________________


PART B — ARCHITECTURE DELTAS (v1 → v2)
=======================================

Frontend (Vercel, Next.js — unchanged host):
  + components/board/Board.tsx — chessground wrapped ONCE (FEN in, legal moves
    via chessops, onMove out, flip, phone-first, a11y). Every trainer reuses
    this wrapper.
  + lib/engine.ts — stockfish.wasm in a Web Worker behind a seam mirroring v1's
    Evaluator (real engine in prod, FixtureEngine in tests). One shared
    grade(move, bestLine, band) → "perfect|pass|fail" (M1).
  + /train/* and /duel/* route trees; v1 report issue-cards deep-link in.

Backend (Railway, FastAPI — unchanged host):
  + auth: email magic-link primary + Lichess OAuth bonus; httpOnly session
    cookie; users table. No passwords (M3).
  + new tables (Appendix V2-1): users, training_positions, attempts, streaks,
    duels.
  + mining service: turns a player's existing v1 MoveEval rows into
    training_positions, run after every analysis, ACCUMULATING (M2). Pure
    SQL/python over data v1 already stores — no new engine work.
  + NO websocket/queue/broker in v2 (D3/A10).

Data sources:
  + The player's own analyzed games (v1) → the position bank.
  + Small CURATED FEN sets committed in the repo for mate/endgame self-tests
    (Appendix V2-4). NO external puzzle DB (D5).

________________


PART C — PHASES AND SESSIONS
=============================

Numbering V2-S1… Each session: Goal · Steps · Definition of Done. [REFINE] =
Opus researches the exact detail in that session's plan.


PHASE T0 — FOUNDATIONS (board, accounts, position bank)
--------------------------------------------------------
Exit: a signed-in (or guest) user sees a board rendering any FEN on their
phone, and the DB holds an accumulating bank of positions mined from their own
analyzed games.

V2-S1 — The board component
  Est: 3h · Prereq: v1 shipped + Phase 5 verified (D7)
  Goal: ONE reusable Board wrapper on chessground + chessops: FEN in, legal
  moves enforced, onMove callback, flip, promotion picker, last-move + check
  highlight, phone-width perfect, keyboard-accessible.
  Steps: FIRST establish the DESIGN.md tokens in code (globals.css custom
  properties + type roles, both themes, killing the Arial override) so every
  later v2 screen inherits them; add chessground + chessops themed to the
  system; build components/board/Board.tsx; a /train/board-demo dev page proves
  both sides + flip + illegal-move rejection.
  DoD: founder plays both sides of a Philidor position on their phone, styled to
  DESIGN.md; no trainer logic yet; illegal moves impossible.

V2-S2 — Accounts (thin, magic-link primary)  [REFINE: email provider]
  Est: 4h · Prereq: V2-S1
  Goal: passwordless auth that works for every friend (M3), guest mode default.
  Steps: users table; httpOnly signed session cookie; email magic-link
  (signed single-use short-TTL token, hashed at rest; default provider Resend,
  confirm in-session); Lichess OAuth as a second button upserting the same
  row; header shows "Sign in to save progress" / display name; guest sessions
  carry an anon id so a later sign-in adopts their progress.
  DoD: founder signs in via email link on phone; a friend signs in with
  Lichess; sign-out works; the v1 report flow is provably unchanged as guest.

V2-S3 — Position mining (the growing bank)  (M2)
  Est: 4h · Prereq: V2-S2
  Goal: extract training_positions from existing v1 MoveEval data, per player,
  ACCUMULATING across every analysis (idempotent). Categories: (a) blunder
  positions (ply before each classified blunder + the best line), (b)
  unconverted advantages (first ply the player's POV crossed +winning in a game
  NOT won), (c) danger positions (a missed opponent threat).
  Steps: training_positions schema with a dedupe key; pure python/SQL over
  MoveEval; hook it to run after each v1 analysis (standard AND deep) + a
  backfill entrypoint; offline tests on fixture evals (idempotent).
  DoD: founder's account shows N accumulated positions across ≥2 analyses,
  spot-checked against 3 real games; tests green, idempotent.


PHASE T1 — YOUR MISTAKES (own-games self-eval — the core wedge)
---------------------------------------------------------------
Exit: each v1 report issue-card links to a trainer seeded from that user's own
bank, graded two-tier (M1), with attempts + streaks persisting.

V2-S4 — Retry Your Mistakes
  Est: 4h · Prereq: V2-S3
  Goal: /train/retry replays the user's blunder positions; two-tier grading;
  progress persists.
  Steps: a reusable trainer shell (pull a set from the bank → Board → submit
  move → lib/engine.ts grade() → perfect/pass/fail → show best line → next);
  grade band in config; attempts rows + streaks; guest = no persist; empty
  state for a thin bank.
  DoD: founder retries 5 of their own real blunders on phone; a perfect and a
  pass both register; guest works without persistence.

V2-S5 — Blunder Preventer
  Est: 3h · Prereq: V2-S4
  Goal: /train/preventer on danger positions: "opponent just played X — what's
  the threat, and how do you meet it?" Same shell, same two-tier grading.
  DoD: founder completes a 10-position defensive set from their own games; kind
  wrong-answer UX.

V2-S6 — Advantage Capitalization Trainer
  Est: 4h · Prereq: V2-S4; v1 advantage-capitalization metric (S28 ✓)
  Goal: /train/convert — the user's unconverted winning positions PLAYED OUT
  against stockfish.wasm (capped strength) until mate/draw/resign. Win =
  converted.
  Steps: playout mode in the shell (user vs wasm from the bank FEN; adjudicate
  terminal); intro copy ties to the v1 metric ("you converted 53% — convert
  these 8 now"), numbers interpolated (A7); record converted/failed.
  DoD: founder wins (or honestly loses) a full playout from one of their own
  real unconverted games on phone.

V2-S7 — Report ↔ trainer deep links
  Est: 2h · Prereq: V2-S4..S6
  Goal: every v1 issue-card (and the category dashboard) gains a "Train this"
  button routing to the right trainer pre-filtered by the cited games.
  Steps: a mapping (issue key → trainer + filter); the trainer accepts a
  filter so the drill is the exact positions the card cited.
  DoD: founder taps from their live report into a drill seeded by the exact
  games the card referenced.


PHASE T2 — SET-POSITION SELF-TESTS (curated challenges)
-------------------------------------------------------
Exit: the user can test themselves on "can I mate this?" and "can I win/hold
this endgame?" from small curated position sets — no generic puzzle pool.

V2-S8 — Checkmate challenges  [REFINE: curated set]
  Est: 3h · Prereq: V2-S4 (trainer shell)
  Goal: /train/mate — mate-in-N from a committed curated set (basic mates →
  common patterns), on the Board, validated move-by-move (opponent auto-replies
  via stockfish.wasm), two-tier: found the mate / found it fastest.
  Steps: curated mate FEN set (Appendix V2-4); puzzle-solve mode in the shell;
  attempts recorded.
  DoD: founder solves a set of basic + pattern mates on phone; wrong-move UX
  reads kindly.

V2-S9 — Endgame self-tests
  Est: 3h · Prereq: V2-S8
  Goal: /train/endgame — win-or-hold a curated endgame FEN vs stockfish.wasm
  (K+P conversions, Lucena, Philidor, R+P, opposite bishops …). Result adjudged
  (held the draw / converted the win = pass).
  Steps: curated endgame FEN library (Appendix V2-4) with a one-line "why this
  matters at your level"; reuse the V2-S6 playout mode; attempts/streaks.
  DoD: founder holds a drawn rook endgame and converts a K+P vs K on phone.


PHASE T3 — PLAY A FRIEND FROM A POSITION (the cheap live path)  (D4)
--------------------------------------------------------------------
Exit: two friends practice a set position against each other tonight, with ZERO
realtime code written.

V2-S10 — Position Duels via Lichess challenge links  [REFINE: exact API]
  Est: 3h · Prereq: V2-S2
  Goal: pick any position (bank / curated / pasted FEN) → create a Lichess
  challenge FROM that FEN → two share-links (one per color) → "swap & replay"
  regenerates with colors flipped. Duel recorded.
  Steps: research the Lichess custom-FEN open-challenge endpoint (variant
  fromPosition + fen); prefer a path that lets a Chess.com friend create
  without a Lichess account if possible; store a duels row with the two URLs.
  DoD: founder + a friend play the SAME won-pawn endgame from both sides via
  shared links on their phones; duel stored.

V2-S11 — The duel library
  Est: 2h · Prereq: V2-S10
  Goal: /duel — browsable library ("your unconverted positions", "classic
  endgames", "from your last report") + per-user duel history.
  DoD: the friends-beta group runs 3 library duels in a week.


PHASE T4 — DASHBOARD + PROGRESS (retention)
-------------------------------------------
Exit: the training home shows what to drill and whether it's working.

V2-S12 — Training dashboard
  Est: 4h · Prereq: T1 done
  Goal: /train home — streaks, per-trainer progress, weakness categories from
  the latest v1 report (reusing the S32 category read) with "Train" buttons,
  and a "what to drill today" queue ordered by the report's rating_impact.
  DoD: founder's dashboard honestly reflects a week of their own use;
  phone-first; zero console errors.

V2-S13 — Progress feedback loop
  Est: 3h · Prereq: V2-S12
  Goal: close the loop — after ≥N drills + a re-analysis, show "trained
  endgames 40×; conversion 53% → 61%", with v1's honest low-signal hedges.
  DoD: at least one real metric visibly moves for one beta user (or the hedge
  copy shows honestly).

--- v2 friends-beta loop: recruit the friend group, watch these 13 sessions in
real use, fix what breaks, and decide (from real use) what graduates from the
v3 backlog. ---

________________


PART D — v3 BACKLOG (broaden reach — deferred, NOT built in v2)
================================================================

Captured so nothing is lost; sequenced later, after the v2 friends beta reads.

1. **Native in-app live play** — matchmaking, private rooms, server-authoritative
   clocks + move validation, spectate (websockets + a real queue). Build ONLY if
   the v2 Lichess-link duels (T3) show real pull. The single biggest v3 lift.
2. **Generic skill trainers** — Tactics, Defender, Visualization / Blindfold,
   Time Trainer. Requires the Lichess puzzle-DB (CC0) import. Deferred because
   Lichess/Chess.com do these better; revisit only if beta friends ask by name.
3. **Intuition calibration** (founder idea) — curated positions where the point
   is a JUDGMENT, not a forced line (right plan / which side is better / attack
   or hold?), then reveal the verdict and score how calibrated the player's read
   was. Fits the self-eval identity; needs design work on grading a judgment and
   sourcing positions (curated vs mined from the player's own decision points).
4. **Public launch, lichess-first** — onboarding polish, ToS/privacy, OG, a
   launch decision gate, public beta loop.
5. **Monetization** — out of scope until v3, if ever.
6. **Accessibility / broader-audience polish** — the v3 theme ("more accessible
   to more users"): stronger onboarding, 2000+ considerations, etc.
7. **Native mobile apps** — PWA polish only until proven demand.

________________


PART E — DO-NOT-BUILD (v2 edition)
===================================

1. LLM coaching or LLM anything (locked until real scale).
2. ML models of any kind.
3. A bespoke board renderer, move generator, or engine (A2/A4 — library + wasm).
4. Hand-authored or scraped puzzle pools / a generic tactics grind (D5).
5. Opening theory teaching / lessons / repertoire builder (D1 — v2 evaluates
   openings via the v1 report; it never teaches them).
6. Server realtime infra — websockets, matchmaking, a queue/broker (D3/D4/A10;
   native live play is v3).
7. Public launch, ratings/ladders/leaderboards, monetization (D6 — v3).
8. Anything gating a v1 report behind an account (A6).
9. Native mobile apps — PWA polish only.

________________


PART F — COST CEILINGS
=======================

Engine: all trainer engine work is client-side wasm — server engine budget
stays v1's. NO puzzle DB (D5) → no large data import. NO realtime service (D6)
→ the existing Railway instance suffices. Auth email: free-tier magic-link
provider (V2-S2). The hosting bill must not change order-of-magnitude in v2.

________________


APPENDICES (LAW — tune here first, then code)
==============================================

Appendix V2-1 — Schema deltas  [REFINE exact types before V2-S2/S3]
  users(id, created_at, email?, email_verified_at?, lichess_id?, display_name,
    anon_id?)   -- anon_id lets a guest's progress be adopted at first sign-in
  training_positions(id, player_id, source_game_id, ply, fen,
    category[blunder|unconverted|danger], best_line_uci, eval_before_cp,
    mined_at, last_seen)
    UNIQUE(player_id, source_game_id, ply, category)   -- M2 idempotent
  attempts(id, user_id, ref_type[position|curated|duel], ref_id, trainer,
    grade[perfect|pass|fail], seconds, created_at)      -- M1 two-tier
  streaks(user_id, trainer, current, best, last_active_date)
  duels(id, creator_user_id?, fen, source, lichess_urls_json, result?,
    created_at)

Appendix V2-2 — Trainer specs (shipped)  [V2-S4 / V2-S5]

  ── Retry Your Mistakes ──
  route:         /train/retry?platform=&username=
  seed source:   player's own training_positions, category "blunder"
  mode:          solve — one move at a time
  GRADE:         two-tier via lib/engine.ts gradeMove(): perfect (match best_line_uci),
                 pass (cp_loss < 200), fail (cp_loss ≥ 200). Exactly one engine
                 call per non-perfect move; StockfishWasmEngine at depth 12.
  attempt:       Attempt(ref_type="position", trainer="retry", grade, seconds)
  streak:        Streak(trainer="retry", current, best, last_active_date)
  empty-state:   "Run a v1 analysis first to mine positions from your games."
  guest:         full grading + tally live in browser; no attempt/streak persisted.
  layout:        mobile-first, 560px max-width Board; top bar (progress + tally +
                 streak); optional prompt slot above board (unused); feedback panel
                 below board (Perfect gold / Pass green / Fail coral); source-game
                 deep-link; inline form when ?platform=&username= are absent.

  ── Blunder Preventer ──
  route:         /train/preventer?platform=&username=
  seed source:   player's own training_positions, category "danger"
  mode:          solve — one defensive move at a time
  GRADE:         same two-tier gradeMove() as retry (perfect/pass/fail, BLUNDER_CP=200).
                 Softer wrong-answer UX: fail label = "Missed it" with a hint
                 ("Here's the idea — see the best line below…") — grading math unchanged.
  attempt:       Attempt(ref_type="position", trainer="preventer", grade, seconds)
  streak:        Streak(trainer="preventer", …) — DISTINCT streak counter from retry.
  opponent_move: derived server-side from the source game's PGN (ply-1), cached
                 per game_id in the request. null when ply == 1. Displayed above the
                 board + as lastMove highlight on chessground.
  empty-state:   "No danger positions yet. Run a fresh v1 analysis first to mine
                 defensive positions, then come back."
  guest:         same as retry — full live grading, no persist.
  layout:        same TrainerShell layout as retry; adds the opponent-move prompt
                 (coral-highlighted SAN) above the board.

  shared shell:  components/train/TrainerShell.tsx — TrainerShellProps { trainer,
                 category, title, description, emptyStateText?, failCopy?,
                 renderPrompt? }. Extracted from retry/page.tsx (V2-S4 → V2-S5),
                 no behavior change to retry. All future solve-mode trainers reuse
                 this shell.

Appendix V2-3 — Report → trainer mapping  [complete before V2-S7]
  hung_pieces / blunder_rate / tilt → retry + preventer
  advantage_capitalization → convert trainer
  missed_saves (resourcefulness) → preventer
  endgame_conversion → endgame self-tests
  (opening issues → no trainer in v2; v1 report is the opening surface)

Appendix V2-4 — Curated FEN sets (committed in the repo)  [REFINE at V2-S8/S9/S10]
  Mate set: basic mates (K+Q vs K, K+R vs K, two rooks) → common patterns
    (back-rank, smothered, Anastasia, Arabian …), each mate-in-N tagged.
  Endgame set: K+P conversions, Lucena, Philidor, R+4v3, opposite bishops, Q vs
    R — each with a one-line "why this matters at your level" + color to move.
  Duel seed set: the endgame set + the player's own unconverted positions.

________________


PROGRESS CHECKLIST
==================

T0: [ ] V2-S1 board  [ ] V2-S2 accounts  [ ] V2-S3 mining
T1: [ ] V2-S4 retry  [ ] V2-S5 preventer  [ ] V2-S6 convert  [ ] V2-S7 links
T2: [ ] V2-S8 mate  [ ] V2-S9 endgame
T3: [ ] V2-S10 duels  [ ] V2-S11 duel library
T4: [ ] V2-S12 dashboard  [ ] V2-S13 progress loop
→ v2 friends-beta loop → read results → pull from the v3 backlog (Part D)
