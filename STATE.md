# Chessania — live state & decisions

## OPEN QUESTIONS (keep at top)

- [ ] Production depth: hold 12 or drop to 11 for Railway speed? (S24)
- [ ] Report retention: keep all reports forever, or cap per player? (beta)
- [x] **RESOLVED in S13** — Blunder-count inflation in decided positions. Founder chose
  (2026-07-26) the "meaningful-blunder count + evidence filter" resolution: S13's turning-point
  detector computes each game's point-of-no-return (PONR = first ply of the final unbroken
  doomed stretch, player-POV eval never again > -150cp), and features gained an additive
  `meaningful_blunders_per_game` = player blunders at ply ≤ PONR (all of them if no PONR).
  Raw `blunders_per_game` is left spec-faithful; the S15 coach will prefer the meaningful count
  and cite only pre-PONR blunders. PROVEN live: gt_lostendgame reports 3 raw blunders (plies
  54/84/88, PONR 54) but meaningful=1 — the founder's exact 3-vs-1 example.
- [ ] **Chess.com §D / API-revocation tail-risk** (surfaced 2026-07-26 by the research council).
  Chess.com owns Aimchess (our closest competitor); its User Agreement §D prohibits automated
  access "for the development or enhancement of… competing products," and it already BLOCKED a
  third-party tool ("Chessiro") under this clause in April 2026 — a clause that plausibly names
  Chessania. Lichess's ToS explicitly permits commercial reuse (lower-risk platform). DECISION
  (2026-07-26): keep the locked decisions AS-IS — username-only auto-pull, platform-neutral
  (Chess.com + Lichess co-equal), PGN upload stays deferred (Part G #1). We only LOG the risk;
  we do NOT unlock PGN upload or reposition Lichess-first yet. Revisit triggers: Chess.com
  actually blocks/denies our access, OR we near a high-volume launch (then seek written consent
  and consider the PGN escape hatch, whose seat already exists — NormalizedGame is source-agnostic).
- [ ] **Indie-sustainability vs. acquisition-target** (strategic, surfaced 2026-07-26). The council's
  clearest business finding: "good product, weak business" — viable as a lean indie tool or an
  acquisition play (Aimchess's own trajectory), not a venture-scale standalone. The two paths pull
  v1 scope differently (viral-report growth vs. defensible data assets). Not a build blocker; parked
  as a founder decision to make deliberately, not by default.

## DECISION LOG

- 2026-07: Input = username auto-pull only; no upload, no OAuth (Locked 1)
- 2026-07: No accounts; identity = (platform, username) (Locked 2)
- 2026-07-24: Clean rebuild — removed pre-roadmap MVP (PGN upload / questionnaire /
  localStorage) that violated Locked 1–3; scaffolded roadmap A6 layout; ran Session 1.
- 2026-07-24: /review of Session 1 found two gaps — the reload/hot-reload DoD checks
  were never actually exercised (server was killed-and-restarted, not live-edited), and
  the venv was on Python 3.14 instead of the locked 3.12. Both fixed same day: installed
  Python 3.12 via Homebrew, recreated backend/venv on it, re-verified reload behavior
  for real (see Session 1 log entry below).
- 2026-07-24: /review of Session 1 + Session 3 found one real bug: SQLite silently
  ignores `ON DELETE CASCADE` (every FK in Appendix 1 specifies it) unless
  `PRAGMA foreign_keys=ON` is set per connection — confirmed by deleting a Player and
  finding their Game row still present. Fixed in app/db.py (event listener on connect)
  and locked in with a regression test (see Session 3 log entry below). Everything else
  re-checked column-for-column against Appendix 1 and found to match exactly.
- 2026-07-24: Full /review of Sessions 1, 3, 4 + the cascade fix, all commands re-run
  live from scratch (not trusted from commit messages): Python 3.12.13 confirmed, fresh
  `alembic upgrade head` builds all 5 tables + indexes, both reload behaviors re-proven
  genuine, engine smoke test re-run clean (no leaked process), and — newly this pass —
  directly exercised constraints Appendix 1 declares but nothing had explicitly tested
  yet: move_evals' bigint/SQLite autoincrement, eval_cache's composite PK, the
  unique(game_id, ply) constraint, and the classification CHECK constraint. All four
  correctly enforced. requirements.txt confirmed to exactly match the installed
  environment. No new bugs found — everything built so far holds up.
- 2026-07-24: Full /review of Sessions 1-5, all commands re-run live again (backend
  reload, frontend hot-reload, fresh migration, full test suite, requirements.txt vs
  installed env, engine smoke test — all still genuinely green). Found one real bug in
  ingest.py: a real network failure (DNS, connection refused, timeout) leaked a raw
  `httpx.ConnectError` instead of being translated into one of the four typed
  exceptions — confirmed by monkeypatching httpx.Client to force a ConnectError before
  fixing, and again via a respx `side_effect` after. This mattered because the S10 job
  wrapper only knows how to translate the four typed exceptions into a friendly
  message; an uncaught transport error would have crashed the job with a raw
  traceback. Fixed by wrapping the fetch in try/except httpx.RequestError -> raise
  UpstreamError, verified the regression test genuinely catches it (broke the fix on
  purpose, watched the test fail, restored it, watched it pass).
- 2026-07-25: Session 6 build caught a real discrepancy between Appendix 9 and the
  actual live Lichess API: the appendix documents `opening.{eco,name}` as part of the
  response shape, but the exact query string it specifies doesn't include `opening=true`
  — without that flag, Lichess omits the `opening` key entirely (not just nulls it),
  so every game's opening_eco/opening_name would have silently stayed None forever.
  Found by comparing two real curl calls (with/without the flag) after the live
  verification script showed blank ECO columns for a real account. Added `opening: "true"`
  to fetch_lichess()'s params; confirmed against the real API that ECO codes now
  populate (see Session 6 log entry below).
- 2026-07-25: Full /review of Sessions 1-6, all commands re-run live from scratch again:
  Python 3.12.13, fresh `alembic upgrade head`, full test suite (19/19, genuinely offline
  via bogus-proxy check), requirements.txt vs installed env, both apps' reload/hot-reload
  behavior (live-edited, not restarted), engine smoke test (no leaked process), and the
  full live end-to-end ingest dedupe check (repeat POST /api/ingest for a real Lichess
  account, second call still correctly shows new:0). No new bugs found — everything
  built in Sessions 1-6 holds up.
- 2026-07-25: Roadmap amendment (deliberate, outside a session — Rule 3/4) — **capture
  per-move time now, coach later.** Founder wants future time-management coaching (spent
  too long on a move / moved too fast then blundered). Audit found per-move timing is the
  one real gap (no column, not in Appendix 5, no detector/rule), but games.pgn already
  preserves raw [%clk] verbatim. Chose "capture the signal now" (matches S3's own
  "cheap now, painful to retrofit mid-pipeline"): added nullable move_evals.seconds_spent
  (Appendix 1 + models.py + migration 0002), a populate-it step to S9, clocks=true to the
  Lichess fetch, and Part G #11 reserving the coaching. v1 reads seconds_spent NOWHERE —
  capture only. S9 will populate it.
- 2026-07-25: Playstyle system affirmation (no build) — founder confirmed the whole-account
  playstyle → strengths/weaknesses → openings design is what they want, and it's ALREADY
  the roadmap's core (playstyle index across all games = Appendix 5/S14; strengths+issues
  = S12-13/S15; openings chosen from the playstyle bucket = Appendix 4/S16; the Report is
  one per-player synthesis, not game-by-game). Founder chose to KEEP the intentional split:
  playstyle drives the opening repertoire, measured weaknesses drive study prescriptions
  (weakness-driven for specificity). No code/spec change — recorded here only.
- 2026-07-25: Analysis-depth decision (S9 planning) — **keep SF_DEPTH=12.** A live probe
  analyzing the founder's piece-drop game at depth 12 vs 16 gave near-identical
  classifications (16.dxc4 = mistake, 19.Rd7 = blunder, 22.Nh3 = ok at both depths) for
  ~8x the time (1.6s vs 12.5s per game). Deeper is confirmed diminishing-returns for
  coaching-grade classification. Clarification for the record: the engine is Stockfish 18,
  already the strongest engine in the world — "deeper analysis" means larger search DEPTH,
  not a different/"stronger" binary; there is nothing stronger to install. The separate
  S24 prod-speed question (maybe drop to 11 on Railway) stays open; this decision only
  rules OUT going ABOVE 12-14.
- 2026-07-25: Two v1 analysis enhancements scheduled (founder-approved, roadmap amended) —
  (1) **color-split weaknesses in S12**: split results/blunder-rate/ACPL/worst-phase/
  opening-leak/endgame-conversion by player_color so "weaker as Black than White" surfaces
  (openings are already color-split via Appendix 4); (2) **turning-point detection in S13**:
  a rule-based "point after which the eval never recovers" signal to pinpoint WHERE a game
  slipped. Positional "why" explanations (opened a file / passed pawn) stay v2 — reserved
  under Part G's LLM-phrasing seat; it's a phrasing problem, not a depth problem.
- 2026-07-25: Phase 0 worked through. P0-2 (manual API walk) — treated as done: both
  public APIs were exercised extensively against real accounts during S5-S7 (chess.com
  archives+month walk, lichess NDJSON), including error paths verified against the live
  APIs and the opening=true/clocks=true discoveries; sample responses live as the S7
  api/ fixtures. P0-4 (opening-table sanity) — reviewed Appendix 4's 12 mappings for
  sub-1800 soundness: all pass the smell test (London/Colle for positional, Italian+Evans/
  Scotch for tactical, Caro-Kann/Slav positional-black, Scandinavian's honest theory-load
  caveat over the Sicilian is a good call). One soft flag: King's Indian (E60+) as the
  tactical-black-vs-d4 alt is theory-heavy/strategically complex for club level — defensible
  and popular, but worth the founder's eye at S16. Opening table = founder-approvable as-is.
  P0-3 ground truth drafted (see GROUND TRUTH section), pending founder verification.
- 2026-07-25: Full coaching-model defined (founder interview). The "personalized coach
  that does everything" = v1 blunder-classification (ship first) + a v2 layer of critical-
  moment detectors: **missed saves** (worse-but-fighting position with a rescue you missed —
  the founder's -4->-1 example), **missed wins/tactics**, **tilt/compounding** (blunder right
  after a blunder), and **time coaching** (too-fast->blundered, dawdling, time-trouble
  collapse). Output stays the aggregate report + evidence links (new detectors, not a new
  surface). Sequencing: **ship v1 first, layer richness** (founder's call). LOCKED coaching
  rule from a founder insight: do NOT flag "thought long AND still blundered" — that's good
  judgment (you picked a critical moment to invest in), not a weakness. **Proven, not
  assumed: the entire v2 needs ZERO new data capture** — a read-only derivation over the
  founder's own piece-drop game, using only stored eval_cp_before + cp_loss + player_color,
  surfaced his exact example (move 19 Rd7, -1.3 and fighting, 274cp collapse). Recorded as
  the expanded Part G #11 "v2 Coaching Layer". No schema/code change; v1 continues at S10.
- 2026-07-26: **Research-council roadmap amendments** (deliberate Rule 3/4 edits, founder-approved
  in plan mode after reviewing the Obsidian vault research — 3-model council + competitor deep-dive
  at `Research/Chessania/`). The research VALIDATED the build (rule-based cross-game diagnosis is
  the real gap; compute is a non-issue; depth-12 fine; shareable report = growth loop). Three
  amendments made — all doc-only, since schemas.py/coach.py don't exist yet (S15 builds them):
  (1) **Appendix 2** — `Issue` gains success_metric, counter_evidence, rating_impact
  ("high"/"medium"/"low" bucket — NEVER a fabricated rating-point integer), refresh_after; issues[]
  now ordered by rating_impact then priority. This is the council's #1 fix: observation→hypothesis
  →experiment, not confident mind-reading. (2) **Time-coaching promoted to v1** — Part G #11d's three
  flags (rushed_blunders, dawdling, time_trouble_collapse) are now Appendix-3 rules + detectors 7-9
  (detector cap 6→9, still hard; DET_TIME_* thresholds); they read the already-captured seconds_spent
  (line-573 note flipped from "capture-only"), zero migration. (3) **PRD** — the "you calculate only
  one move ahead" flagship line softened to an evidence-backed, non-causal promise (all 3 models
  flagged it as unsupportable). NOT changed (logged above in OPEN QUESTIONS): PGN upload stays
  deferred, platform stays neutral. Resequencing: a new time-coaching-detector session lands BEFORE
  S15; S15 then builds schemas.py + coach.py consuming the fuller `Issue`.
- 2026-07-27: S17 report-quality gate → **GO**. Founder reviewed the three golden reports; mechanical
  audits (specificity + banned-phrase) already green. Two copy/threshold tweaks made at the gate, NOT a
  fix-first loop: (1) endgame "winning" tightened to STRICTLY winning — `FEATURE_ENDGAME_AHEAD_CP`
  200→300cp (a decisive edge a sub-1800 should convert ~10/10, incl. a clean extra-pawn endgame);
  (2) dropped the non-chess word "leak" from the two user-facing strings (opening_leak headline +
  opening_general success_metric) — internal `opening_leak*` identifiers unchanged. Appendix 3 + the
  feature spec (roadmap 670/1644) updated to match (law-first). DELIBERATELY DEFERRED to pre-ship: all
  fine-tuning of playstyle features + exact advice/language style — founder will tune those once the v1
  frontend exists and reports can be seen in situ. Proceeding to frontend/next session.
- 2026-07-28: **S23 pre-deploy gate — AI-verified quadrant GO, founder quadrant pending.**
  Quality: full backend suite (170 passed) + S17 goldens unchanged + frontend build clean.
  Cost: local single-game depth-12 analysis is ~1–2 s per game (baseline for S24 prod sizing);
  `MAX_CONCURRENT_JOBS=2` + in-memory job dedup already limits blast radius.
  Scope: audit of the working tree confirms no Part G leaks (no chessboard, puzzles, accounts,
  LLM/ML, Celery/Redis, PGN upload). Honesty + founder "didn't-know-that" bar: left as
  [founder-to-verify] in the S23 session log. Verdict: GO on the AI-verified quadrants; founder
  completes the human half before S24.

## FIXTURE REGISTRY (P0-1)

- founder: (platform, username) = (chesscom, Eleven_14) — ~1760-1800 blitz. First PGN
  fixture committed S8: tests/fixtures/pgn/eleven14_blitz_loss.pgn
  (chess.com/game/live/170639309900, a Pirc where White's 27.Nxg5 knight sac lost).
- other-platform workout: (lichess, DrNykterstein) used for live Lichess-fetcher
  verification in S5-S7 — both fetchers proven on real accounts (P0-1's "both platforms"
  goal met).
- low-rated (~800-1100) + mid-rated (~1500-1700) dedicated fixture accounts: NOT yet
  picked. Only needed for S11's varied-rating PGN fixtures, not for S9. Pick at S11
  (founder to supply handles they know, or sample from public games then). Not fabricating
  band-specific accounts I can't verify.

## GROUND TRUTH (P0-3)

Annotator note: these are an AI (Claude) coach's-eye read of the moves — NOT from running
our Stockfish pipeline, and NOT yet confirmed by the founder. **Founder to verify against
the platform analysis board** (they're ~1780, it's their own play). Independent of the
depth-12 pipeline, so S9's calibration against them is still a real check. Tag stays
[founder-to-verify] until the founder signs off.

- **Game 1 — clean win** (chess.com/game/live/169858238066, founder = White, Vienna C25):
  founder bad moves = **none** (8-move attacking win; 4.Qg4 early-queen sortie is unusual
  but not an error here). worst phase = n/a (opening only). Coach take: "Clean kingside
  attack punishing Black's weak f7 — nothing to fix." → Pipeline should flag ~0 player
  blunders (PRECISION test). [founder-to-verify]
- **Game 2 — positional decline loss** (chess.com/game/live/171401969338, founder = Black,
  London D02): **CORRECTED 2026-07-25** after a depth-12/16 probe during S9 planning — my
  first read (22...Nh3 "hung a knight") was WRONG. The pipeline and the founder agree the
  game was decided EARLIER: the real errors are the **16...dxc4 (mistake, ~-130cp) → 18...
  Rad8 (mistake) → 19...Rd7 (blunder, ~-275cp)** slide, which opened lines and let White's
  passed pawn run. By move 22 Black was already ~-5, so **22...Nh3 is correctly "ok"
  (cp_loss ~16)** — you can't lose much when already lost. worst phase = **middlegame**.
  Coach take: "You didn't lose this to one hung piece — you drifted from move 16 (dxc4)
  through 19 (Rd7), opening the position for White's passed pawn; by move 22 it was already
  gone." → Calibration target: pipeline flags the 16→19 decline and rates 22 as ok (both
  ALREADY VERIFIED by the planning probe). This is exactly what ground truth is for — the
  calibration caught my wrong annotation. [founder-to-verify]
- **Game 3 — lost endgame** (chess.com/game/live/170685592218, founder = Black, Dragon
  B76): reached a roughly balanced King+pawn endgame (~move 28) and **lost the pawn race**
  — around **30...Kxe4** (pawn-grabbing instead of stopping/racing White's c-pawn), White
  queened first (38.c8=Q) and mated. worst phase = **endgame**. Coach take: "You lost a
  K+P race you might have held — endgame pawn races are tempo-counting; study king-and-pawn
  endings." → Pipeline should locate the decisive error in the ENDGAME phase (phase-tag +
  subtler-loss test). [founder-to-verify]
- S9 calibration verdict: **PASS (provisional, vs AI-drafted+corrected GT)** — game 1: 0
  founder blunders (precision ✓); game 2: 16.dxc4 mistake + 19.Rd7 blunder flagged, 22.Nh3
  correctly ok (recall ✓, matches corrected GT); game 3: decisive 27.Rxe4 blunder tagged
  endgame (✓). No blunder-level disagreements. seconds_spent populated with sane values.
  Founder still to verify the 3 games on the analysis board to promote to founder-verified.
- S13 detector verdict: \_\_\_\_\_\_\_\_ (S13 not built yet)

## SESSION CHECKLIST

Phase 0:  [~] P0-1  [x] P0-2  [~] P0-3  [x] P0-4   ([~] = done but pending founder sign-off:
          P0-1 founder+lichess accounts logged, band accounts deferred to S11;
          P0-3 ground truth AI-drafted, founder to verify against the analysis board)
Phase 1:  [x] S1 [x] S2 [x] S3 [x] S4 [x] S5 [x] S6 [x] S7  🏁 Phase 1 exit reached
Phase 2:  [x] S8 [x] S9 [x] S10 [x] S11 [x] S12 [x] S13 [x] S14 [x] S14.5 (time-coaching detectors) [x] S15 [x] S16 [x] S17
Phase 3:  [x] S18 [x] S19 [x] S20 [x] S21 [x] S22
Phase 4:  [x] S23 [x] S24 [x] S25 🏁 LIVE (chessania.vercel.app) [ ] weekly beta ×4–6
Phase 5:  [x] S27 [ ] S28 [ ] S29 [ ] S30 [ ] S31 [ ] S32 [ ] S33  (post-launch analytics; deferred per 2026-07-27)

## SESSION LOG (newest first; honesty tags mandatory)

### 2026-07-28 · Session 27 · Stat explainers

- Added self-explaining info affordances for every jargon stat on the report. NEW
  `frontend/lib/statInfo.ts` — a content map keyed by stat id (`acpl`, `acpl_phase`,
  `blunders_per_game`, `mistakes_per_game`, `endgame_conversion`, `opening_leak_rate`,
  `accuracy_trend`, `playstyle`), each with `term`, a one-sentence plain definition, and a one-sentence
  "at your level" note for sub-1800 players. NEW `frontend/components/report/StatExplainer.tsx`
  (client leaf) — a small "?" button that toggles a popover on click/tap, closes on Escape and
  outside-click, carries `aria-expanded`/`aria-label`/`aria-controls`, and is capped to the viewport so
  it never causes horizontal scroll at phone width. Wired into `frontend/components/report/StatsBlock.tsx`
  for Blunders/game, Mistakes/game, ACPL, Endgame conversion, the three phase ACPLs, Opening leak rate,
  and Endgame conversion in the by_color grid; also wired into `frontend/components/report/ReportHeader.tsx`
  next to the playstyle chip. No numbers, formats, contracts, or backend were touched.
- **AI-verified**: `cd frontend && npm run build` → compiled clean, TypeScript passed. StatsBlock and
  ReportHeader remain server components; only `StatExplainer` and the existing `IssueCard`/`ReportFooter`
  are client leaves.
- **Commit**: `feat: stat explainers` — DO NOT push (per session rule).
- **[founder-to-verify] DoD**: on your live report at phone width, tap each "?" and confirm the copy is
  clear and true; confirm nothing about the numbers or layout regressed.
- Next: **Session 28** — (roadmap Phase 5 continues; pick the next analytics/enrichment session).

### 2026-07-28 · Session 25 · Deploy the frontend + end-to-end smoke 🏁

- Frontend deploy prep + the one code guard. Modified `frontend/lib/api.ts` — `API_BASE` now strips
  trailing slashes so a pasted `https://x.up.railway.app/` doesn't become `…//api/analyze`. Default
  localhost still works. Modified `frontend/.env.example` — added a production comment that the
  `NEXT_PUBLIC_API_URL` must be the https Railway domain with NO trailing slash. No other code changed.
- **AI-verified**: `cd frontend && npm run build` → compiled clean, TypeScript passed, no routes lost.
- **Commit**: `chore: vercel deploy + smoke path` — DO NOT push (per session rule). The actual Vercel
  import, env var wiring, and the cellular-data smoke test are the founder's hands.
- **[founder-to-verify] DoD — the live runbook** (do in order):
  1. Railway → Settings → Networking → **Generate Domain**. Copy `https://<name>.up.railway.app`;
     confirm `/health` 200.
  2. Vercel → New Project → import Chessania → **Root Directory = `frontend`** → set
     `NEXT_PUBLIC_API_URL = https://<name>.up.railway.app` (no trailing slash) → Deploy. Note the
     production domain.
  3. Railway → set `CORS_ORIGINS = https://<project>.vercel.app` (production domain, no trailing
     slash) → redeploy backend.
  4. Redeploy frontend if `NEXT_PUBLIC_API_URL` was set after the first build (it bakes in at
     build-time).
  5. **Smoke test on your phone, on cellular data (not Wi-Fi)**: open the Vercel URL → run a real
     username through landing → analyzing → report → share the report `/r/...` link to a second
     device and confirm it loads cold (server render + OG unfurl).
  6. Log the prod timing and any CORS/mixed-content notes below, then commit/push this STATE.md update.
- **Tester click-path (5-line beta tester runbook)** — paste into messages / README later if helpful:
  1. Go to the site, choose Chess.com or Lichess, type a username, press **Coach me**.  
  2. Wait on the progress screen while it fetches/analyzes/coaches (~1–4 minutes for 20 games).  
  3. Read your report — scroll through your strength, top issues, opening recommendations, and stats.  
  4. Tap any game row to open that game on the platform and review it on the real board.  
  5. Share the report link (`/r/chesscom/username` or `/r/lichess/username`) to a friend — they see the
     same report without an account.
- **Opus review**: the `api.ts` trailing-slash guard is correct (`.replace(/\/+$/, "")`); `npm run
  build` clean. Fixed a defect in `frontend/.env.example` — Kimi left two stray `[TEMPLATE]` marker
  lines at the top (scaffolding leak); replaced with a normal header comment. Guard + fix pushed.
- **🏁 FOUNDER-VERIFIED — CHESSANIA IS LIVE (2026-07-28).** Backend: `https://chessania-production.up.railway.app`
  (`/health` 200 over HTTPS). Frontend: `https://chessania.vercel.app` (Vercel GitHub App on
  roanokesrivastav-lab, Root Directory `frontend`, `NEXT_PUBLIC_API_URL` set before the build so no
  rebuild race). `CORS_ORIGINS=https://chessania.vercel.app` on Railway (redeployed). **End-to-end
  proof:** ran a real analysis of Eleven_14 from the browser — network trace shows client → Railway
  `POST /api/analyze` 200 and `GET /api/jobs/{id}` 200 directly, no CORS errors, no mixed-content,
  console clean, report rendered with real data. **Phone/cellular cold-load on a second device:
  confirmed working.** Phase 4 deploy sessions (S23–S25) complete.
- **Next**: founder completes the runbook, logs the result, and pushes. Then Phase 5 beta begins.

### 2026-07-28 · Session 24 · Deploy the backend

- Backend containerization + deploy prep. NEW `backend/Dockerfile` — `python:3.12-slim`, installs
  `stockfish` from Debian, sets `SF_PATH=/usr/games/stockfish`, installs Python deps, and boots with
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` so migrations run
  before the server starts and Railway's injected `PORT` is honored. NEW `backend/.dockerignore` —
  excludes `venv/`, `__pycache__/`, `*.sqlite3`, `.pytest_cache/`, `.git/`, `tests/`, `.env`, etc.,
  keeping the image lean and secret-free. NEW `backend/tests/test_db_url.py` — offline tests for the
  `postgres://` → `postgresql://` normalizer. Modified `backend/app/config.py` — added a
  `_normalize_database_url` helper and a Pydantic `field_validator` on `DATABASE_URL` so a Railway
  `postgres://` URL is rewritten once at settings load time; `postgresql://` and `sqlite://` are left
  untouched. No app behavior changed.
- **AI-verified**: `cd backend && source venv/bin/activate && python -m pytest -q` → **175 passed,
  3 deselected**, ~2.0 s, OFFLINE, no Stockfish. The new `test_db_url.py` passes and the existing
  suite is unaffected.
- **Commit**: `feat: dockerfile + railway deploy` — DO NOT push (per session rule). The actual Railway
  project creation, Postgres plugin, env-var configuration, deploy, and prod timing check are the
  founder's hands in S24.
- **Opus review + fix — the monorepo build failure.** Founder's first Railway deploy attempt failed at
  the BUILD step (before env vars could even matter): the repo root has `frontend/` and `backend/`
  side by side with no Dockerfile at the top, so Railway's own auto-detection (Nixpacks) had nothing
  to build correctly. Kimi's Dockerfile itself was correct — reviewed line by line, `pytest -q` still
  175 passed offline — but nothing told Railway where to find it. NEW `backend/railway.json` pins
  `builder: DOCKERFILE`, `dockerfilePath: Dockerfile` (relative to the service's Root Directory) and a
  `/health` healthcheck with a bounded restart policy — belt-and-suspenders alongside the dashboard
  setting below.
- **[founder-to-verify] DoD — ONE setting to fix the build, then redeploy**: in the Railway dashboard,
  open the service → **Settings → Source → Root Directory**, set it to `backend`, save, and trigger a
  redeploy (or push again). This is what tells Railway "the Dockerfile lives here, build from this
  folder" — without it, Railway can't find `backend/Dockerfile` no matter what env vars are set. After
  that: add the Postgres plugin, set `ENV=prod`, `CONTACT_EMAIL`, `CORS_ORIGINS` (Vercel placeholder is
  fine until S25) and the auto-provided `DATABASE_URL`; deploy, watch the logs for the `alembic upgrade
  head` line, confirm `/health` returns ok, and run a full real analysis on prod. Log the duration here.
  If prod is dramatically slower than local, `SF_DEPTH=11` is acceptable; below 11 requires a founder
  call.
- **FOUNDER-VERIFIED — DEPLOYED (2026-07-28).** Root Directory = `backend` fixed the build.
  **Real bug the founder caught:** no `DATABASE_URL` was set, so the app was silently running on
  EPHEMERAL SQLite (all data would vanish on every restart). Fixed by adding `DATABASE_URL`
  referencing the Railway Postgres plugin; logs now show `Context impl PostgresqlImpl` with migrations
  0001 + 0002 applying cleanly BEFORE uvicorn starts, and `/health` returns `{"status":"ok"}` 200 in
  ~10ms. **Prod timing (roadmap DoD):** cold analysis of Eleven_14 (chess.com) = **43.4s for 20 games
  / 1,443 move evals at depth 12**; a cached repeat = **2s**. Well within the 1–4 min budget → **SF_DEPTH
  stays 12** (no downgrade needed). **Open item carried to S25:** the service has no public domain yet
  (Settings → Networking → Generate Domain) — it's only reachable inside Railway's network, so the
  domain must be generated before the Vercel frontend can call it. 🏁 Backend is live (private).

### 2026-07-27 · Session 23 · Pre-deploy gate + rate limiting

- Phase 4 opening gate. Added slowapi rate limiting to POST /api/analyze.
  `backend/app/config.py` added `RATE_LIMIT_ANALYZE: str = "3/hour"`.
  `backend/app/main.py` wired a `Limiter(key_func=get_remote_address)`, attached it to
  `app.state.limiter`, registered a custom `RateLimitExceeded` handler returning 429 with JSON
  `{"detail": "You've queued a few already — reports keep, come back soon."}`, and decorated
  `/api/analyze` with the limiter. The limit value is supplied by a callable that reads
  `settings.RATE_LIMIT_ANALYZE`, so dev can override it via env and tests can change it without
  reloading the module. CORS is driven by `settings.CORS_ORIGINS` (already env-driven; only added a
  clarifying comment) and `/api/debug/features` remains prod-gated by `settings.ENV != "dev"`
  (only added a clarifying comment). `backend/requirements.txt` pinned `slowapi==0.1.10`.
  NEW `backend/tests/test_rate_limit.py` — offline, resets slowapi's in-memory storage between
  tests, mocks the job helper to avoid background tasks, and asserts both the 200 under-limit path
  and the 429 + friendly-detail over-limit path.
- **AI-verified**: `cd backend && source venv/bin/activate && python -m pytest -q` → **170 passed,
  3 deselected**, ~2 s, OFFLINE, no Stockfish. S17 golden fixtures unchanged. Live curl proof
  started the server with `RATE_LIMIT_ANALYZE=1/minute`; the second consecutive POST returned the
  friendly 429 body (`"You've queued a few already — reports keep, come back soon."`). Frontend
  `npm run build` remains clean from S21/S22.
- **Gate verdict**: GO on Quality / Cost / Scope (AI side). Honesty + founder bar remains
  [founder-to-verify] below. No Part G leaks found in tree diff.
- **Opus review — clean, verified live.** Read all 5 files. slowapi wiring correct (custom 429
  handler with the friendly copy; `request: Request` injected; callable-limit reads settings so tests
  override without reload). Independent live checks: started uvicorn with `RATE_LIMIT_ANALYZE=2/minute`
  and curled POST /api/analyze ×3 → 400, 400, **429 friendly** (used an invalid username so no
  job/network ran, proving the limiter fires first). Started uvicorn with `ENV=prod` →
  `/api/debug/features` returns **404** (200 under dev), `/health` 200 — the prod gate closes. Full
  suite 170 passed / 3 deselected, offline, `pgrep -f stockfish` flat; S17 goldens byte-identical.
  Scope diff = exactly the 5 planned files, no Part G leak.
- **Gate — AI half: GO.** Quality (goldens + suite green), Scope (no leak), Cost (concurrency is
  survivable: `MAX_CONCURRENT_JOBS=2` semaphore + username dedup + queue → a spike degrades to longer
  waits, not a crash; the precise minutes-per-analysis number is measured on prod hardware in S24 step
  3 / the founder's DoD re-analysis). **The final GO/fix-first verdict awaits the founder's half
  below and blocks S24.**
- **Commit**: `chore: pre-deploy gate + rate limiting` (`997e686`, code + Kimi log together). Opus
  review + checklist fix pushed to origin/main.
- **[founder-to-verify] — the S23 human half of the gate**: (1) Open your own live report and
  confirm at least one sentence makes you think "I didn't know that about my own games." (2) Kill
  the backend and click through landing / analyzing / report / 404 / expired paths — every screen
  should say something true, no infinite spinners. (3) Run the curl loop yourself: start the server
  with `RATE_LIMIT_ANALYZE=1/minute`, hit `POST /api/analyze` twice, confirm the second is 429 with
  the friendly copy.
- **GATE VERDICT: GO (founder-verified 2026-07-27).** (1) Didn't-know-that bar CLEARED — the founder
  didn't realize their openings were that solid until the report showed no losing positions out of the
  opening and frequent winning positions with the Vienna Gambit as White. (Founder still wants to
  improve openings + wants richer insights generally — noted as back-burner; this is exactly the
  Phase-5 analytics appetite, already scheduled.) (2) Honesty click-through confirmed. (3) Rate-limit
  curl proof confirmed. → Cleared to proceed to S24 (deploy the backend).

### 2026-07-27 · Session 22 · Progress tracking

- The sanctioned backend+frontend exception to the phase wall: on a player's SECOND (or later)
  analysis, the report now shows honest improvement deltas vs the previous and first reports.
  NEW `backend/app/progress.py` — pure DB/JSON math, no engine. A centralized `_delta()` holds the
  single sign-flip mapping (conversion up = better; ACPL/blunders down = better; flat within
  `PROGRESS_FLAT_EPSILON`). `build_progress()` queries the latest and earliest prior reports for the
  player, computes deltas for Blunders/game, Overall ACPL, worst-phase ACPL, and Endgame conversion,
  and sets `progress.note` to the low-signal copy when fewer than `PROGRESS_MIN_NEW_GAMES` provably
  new games exist since the last report. `backend/app/coach.py` now calls `build_progress()` when
  `session and player` are present; single-report builds still get `progress=None` so the S17
  golden fixtures are unchanged. `backend/app/config.py` added `PROGRESS_MIN_NEW_GAMES` (5),
  `PROGRESS_FLAT_EPSILON` (0.02), and `PROGRESS_LOW_SIGNAL_NOTE`. FRONTEND: `frontend/lib/format.ts`
  gained `formatDeltaValue` (conversion ×100 → %, ACPL → integer, bluders/game → 1 decimal),
  `directionArrow`, `directionColor`, and `formatProgressDate`. `frontend/components/report/ProgressStrip.tsx`
  upgraded from a bare stub to the ProgressCard: header with date span, vs_previous/vs_first groups,
  colored arrow + `prev → curr` formatted values per metric, and the hedged note when present.
- NEW `backend/tests/test_progress.py` — unit tests for `_delta` (conversion up → better, ACPL down →
  better, blunders up → worse, within-epsilon → flat, null side dropped) and integration tests for no
  prior report (returns None), sign-flip via endgame conversion improvement, low-signal note when <5
  new games, and no note when enough new games. Extended `backend/tests/fixtures/features/builders.py`
  with `_custom_game_rows()` and `build_sequential_player()` to seed a persisted first report + a
  second batch of newer games deterministically.
- **AI-verified**: `cd backend && source venv/bin/activate && python -m pytest -q` → **167 passed,
  3 deselected**, ~2.0s, OFFLINE, no Stockfish. `cd frontend && npm run build` → compiled clean,
  TypeScript passed. Backend schema/types untouched; frontend contract unchanged.
- **Commit**: `f9befa2` `feat: progress tracking` — DO NOT push (per session rule). STATE.md updated
  in a separate docs commit.
- **[founder-to-verify] DoD**: re-analyze your real account (you've played new games since the first
  analysis), open `/r/{platform}/{username}`, and confirm the Progress arrows/numbers match a
  hand-check of the two stored `report_json` `stats_block`s. Then re-run with no new games and verify
  the low-signal note appears instead of a bogus trend.
- **Opus review — clean, no bugs.** Read all 7 files. `_delta` sign logic verified correct
  (conversion up→better, ACPL/blunders down→better, within-epsilon→flat); null-skip works; the
  honesty guard correctly counts games with `played_at` > previous report's `last_game_at`; timing is
  safe (build_report runs before jobs.py persists the new row, so "prior reports" never includes the
  one being generated). Re-ran `pytest -q` → 167 passed / 3 deselected, offline, `pgrep -f stockfish`
  flat; confirmed the S17 golden JSONs are NOT in the diff (single-report fixtures → progress=None,
  byte-identical). `npm run build` clean. ProgressStrip trusts the backend `direction` (never
  re-derives sign) and formats conversion ×100 on the frontend only — the units trap avoided. No
  scope creep (diff = exactly the planned files). Pushed to origin/main.
- Next: **Session 23** — pre-deploy decision gate + hardening (Phase 4 begins).

### 2026-07-27 · Session 21 · Frontend hardening + copy pass

- No new product features, no backend changes. HARDENING only. NEW `frontend/app/layout.tsx` metadata: `metadataBase` from `NEXT_PUBLIC_SITE_URL`, title template (`%s · Chessania`), real description, OG `siteName`/`type`, and Twitter `summary_large_image`. NEW `frontend/app/icon.svg` self-contained "C" monogram favicon; removed leftover `app/favicon.ico`. NEW `frontend/app/opengraph-image.tsx` site-wide OG card (1200×630 PNG) and NEW `frontend/app/r/[platform]/[username]/opengraph-image.tsx` per-player dynamic OG card that `await`s params, calls `getReport()`, and renders username/rating/games/playstyle; any error/404 falls back to a generic Chessania card so the route never throws. Extended `frontend/app/r/[platform]/[username]/page.tsx` `generateMetadata` with `openGraph` (title/description/url/type) and `twitter` (did NOT set `openGraph.images`; co-located image file auto-populates it). NEW `frontend/app/not-found.tsx` warm 404 page. Deleted create-next-app cruft: `public/{file,globe,next,vercel,window}.svg`. Copy sweep: `format.ts` unit fix (`opening_leak_rate` is already a percent → `formatPercent` no ×100; `endgame_conversion` is a 0–1 fraction → `formatConversion` ×100), friendlier API fallback, `ReportFooter` "generated on" + "this link", `StatsBlock` "Opening leak rate" / "Endgame conversion" labels.
- **AI-verified**: `cd frontend && npm run build && npm run lint` → compiled clean, no `metadataBase` warning, lint passed. `git grep` for `next.svg`/`vercel.svg` empty; source contains no "Create Next App" text. Backend UNTOUCHED. Commit: `f22f796` `chore: frontend hardening + copy pass`; not pushed.
- **Opus review — REGRESSION CAUGHT + RE-FIXED.** Kimi's "copy sweep" quietly **reverted the S20 `formatPercent` fix**: it restored `formatPercent` to no-×100 with the wrong comment ("opening_leak_rate is already a percent"), which would again render the 0–1 fraction `0.1` as "0.1%" instead of "10%" — and the same commit relabeled it "Opening leak **rate**," making the wrong number read confidently. Re-applied the ×100 in `frontend/lib/format.ts` with a load-bearing comment citing `features.py` + these logs so it stops getting reverted. `opening_leak_rate` AND `endgame_conversion` are BOTH 0–1 fractions → both ×100 for display.
- **Favicon fix.** The `app/icon.svg` "C" was drawn with `<text>` + a system font; favicon rendering contexts often lack the font, so it showed blank (founder confirmed it "didn't open"). Replaced with a **font-free vector pawn** (circle head + stem + flared base on the dark rounded square) that renders in every context. (Browser favicon caching means a hard refresh / new tab may be needed to see it.)
- **AI-verified (Opus)**: `npm run build` clean after both fixes; all routes present incl. `/opengraph-image` + per-player `/r/[platform]/[username]/opengraph-image`; no `metadataBase` warning; no "create next app" strings; deleted assets unreferenced. Backend UNTOUCHED. OG image reviewed: proper `size`/`contentType`/`alt`, `try/catch` → fallback card (never throws), system fonts only.
- **founder-verified (2026-07-27)**: three-persona walk clean (happy path renders; typo'd username → "check the spelling?" kindly; no-eligible-games → "No recent rapid or blitz games found" kindly). "By color → Opening leak rate" now reads 10%, not 0.1%. Favicon + Lighthouse: pending founder recheck after the pawn-icon fix.
- Commits: `f22f796` (Kimi, hardening) + Opus re-fix commit (leak-rate ×100 + pawn favicon) + this log. Pushed to origin/main.
- Next: **Session 22** — report progress/history surface (or deploy prep if skipping). Prereq S21 ✓.

### 2026-07-27 · Session 20 · The report page

- Built the shareable coaching report face at `/r/[platform]/[username]`. NEW async Server Component `frontend/app/r/[platform]/[username]/page.tsx` fetches `getReport()` server-side, `export const dynamic = "force-dynamic"` for fresh re-analyzes, and `generateMetadata` for unfurl. 404 path renders inline `<AnalyzeForm initialPlatform={rawPlatform} />` for a fresh analysis; other errors show a friendly block. EXTRACTED the landing form into `frontend/components/AnalyzeForm.tsx` (client) so both the home page and the empty state share the same validation/submit logic; `frontend/app/page.tsx` now delegates to it. NEW `frontend/lib/format.ts` centralizes units; raw numbers preserved via `String(value)`. (Units correction below — both rates are 0–1 fractions.) NEW report components under `frontend/components/report/` rendered in locked order: `ReportHeader` (username, platform badge, rating, date range, time-class mix, playstyle chip), `StrengthCard` (warm, always above issues), `IssueCard` (client, expandable evidence rows that deep-link to `game_url`), `OpeningRecCards` (stacked on phone, side by side on desktop), `StatsBlock` (ACPL by phase, conversion, trend, optional `by_color` split), `ProgressStrip` (only when non-null), and `ReportFooter` (client re-analyze button + public-link note). Also fixed lint/Next issues in `frontend/app/analyzing/[jobId]/page.tsx` (use `Link` for `/`, escaped unescaped entity).
- Kimi 2.7 coded + committed (`06eaae3` `feat: report page` + `856c730` `docs: S20 session log`, no push). Opus reviewed all 12 files, re-ran the build, ran the mandated number cross-check against a real report, fixed one bug, and pushed.
- **BUG FOUND + FIXED (the "numbers silently swap" trap, roadmap step 4).** Cross-checked the rendered stats against the real `chesscom/eleven_14` report via `print_report.py`: `opening_leak_rate` is a **0–1 fraction** (`features.py:319` = `leak_count / len(games)`; real value `0.1` = 10%), NOT an already-percent number. `format.ts`'s `formatPercent` was rendering `0.1` as "0.1%" instead of "10%" — a 100× understatement in the by-color "Opening leak" stat. Root cause was the S20 PLAN's units guidance, which mislabeled `opening_leak_rate` as an already-percent field; Kimi coded to that guidance faithfully. Fix (`fc…` below): `formatPercent` now ×100, matching `formatConversion` (both `endgame_conversion` and `opening_leak_rate` are 0–1 fractions). Every other rendered number cross-checked correct (ACPL 54.9, blunders/game 2.5, conversion 0.75 → "75%").
- **KNOWN GAP, deferred (founder decision):** `IssueCard` renders headline/diagnosis/prescription+links/evidence but NOT `success_metric` — matches the roadmap's literal IssueCard spec, but drops a concrete target per issue. Left for the pre-ship copy/UX polish pass per the standing "defer language/UX detail until the frontend exists" decision.
- **AI-verified (Opus)**: `npm run build` → compiled clean, TypeScript passed, 4 routes; `/r/[platform]/[username]` is ƒ (server-rendered on demand) — a true Server Component with only `AnalyzeForm`/`IssueCard`/`ReportFooter` as client leaves. Backend UNTOUCHED (Phase-3 wall held). `<AnalyzeForm/>` extraction verified: home page + empty state share it, home behavior identical. Commits pushed to origin/main.
- **[founder-to-verify] — the S20 DoD**: run backend + `npm run dev`, visit a live `/r/{platform}/{username}` for your account, check phone-width layout, confirm every evidence link opens the right game on the platform, hit Re-analyze and watch it redirect to the progress screen, and load the shared URL cold on a friend's phone. Spot-check the "By color → Opening leak" %s now read sensibly (e.g. 10%, not 0.1%).
- Next: **Session 21** — Frontend hardening lap (three-persona walk: happy / typo'd username / 2-game account; copy sweep; favicon + `<title>`/OG tags; Lighthouse phone pass). Prereq S20 ✓.

### 2026-07-27 · Session 19 · Live progress screen

- The 1–4 min wait, made to feel alive. Kimi 2.7 coded + committed (`c59289f`, no push); Opus reviewed +
  ran `npm run build` live + pushed. Enhanced `frontend/lib/api.ts` (new `ApiError { message, status }` —
  `status` = HTTP code on non-2xx, `null` on network failure; all 3 helpers throw it, same friendly copy;
  S18's `page.tsx` still works via `err.message`). REPLACED the `analyzing/[jobId]` stub with the real
  client screen: polls `getJob()` immediately then every 2s, renders by stage (fetching → "Pulling your
  recent games…" · analyzing → progress bar + "Analyzing game {n} of {N}" · coaching → "Writing your
  report…"), rotates playful waiting lines every 4s, redirects on `done` via `router.replace('/r/'+
  platform+'/'+username)`. Error routing: `state==="error"` → backend `error_message` + "try another
  username"; `ApiError.status===404` → "That analysis expired" copy; network miss → exponential backoff
  (2/4/8/10s) surfacing "Reconnecting…" only after 3 consecutive misses. NEW minimal
  `app/r/[platform]/[username]/page.tsx` stub so the done-redirect resolves (S20 builds the real page).
- **AI-verified**: `npm run build` → compiled clean, TS passed, 4 routes (`/`, `/analyzing/[jobId]`,
  `/r/[platform]/[username]`, `/_not-found`). Reviewed the poll loop: a `useEffect` cleanup clears both
  intervals + sets a `stopped` ref, and terminal states (`done`/`error`/404) call `clearPolling()` — so
  no poller leaks off-screen or after completion (the S19 teaching point). 404-vs-transient correctly
  distinguished via `ApiError.status`. Backend UNTOUCHED. First commit with `.vexp/` properly gitignored.
- **Opus review: clean — no bugs.** One low note (not fixed): `router` is in the poll effect's dep array;
  App-Router's `router` is stable so it won't churn, and React Strict Mode's dev-only double-mount is
  guarded by the `stopped` ref (at most a harmless duplicate dev fetch). Fine as-is.
- **[founder-to-verify] — the S19 DoD**: run backend + `npm run dev`, submit a real username, and watch
  the analysis progress end-to-end and land on `/r/...`; then kill the backend mid-poll and confirm you
  see the graceful "Reconnecting…"/expired copy, NOT an endless spinner.
- Next: **Session 20** — the report page (`/r/[platform]/[username]`), the product's face: server-fetch
  the report, render every Appendix-2 section (ReportHeader / StrengthCard / IssueCard×≤3 / OpeningRecCards
  / StatsBlock / footer), evidence rows deep-linking to the real games. Prereq S17 ✓ + S19 ✓.

### 2026-07-27 · Session 18 · Landing page + typed API client (Phase 3 begins)

- First FRONTEND session — top of the funnel, one screen/one field. Kimi 2.7 coded + committed
  (`1067968`, no push); Opus reviewed + ran `npm run build` live + pushed. NEW `frontend/lib/types.ts`
  (hand-mirror of the full Appendix-2 `Report` tree + `Job`/`AnalyzeResponse`/`Platform`),
  `frontend/lib/api.ts` (typed `analyze`/`getJob`/`getReport` off `NEXT_PUBLIC_API_URL`, throwing the
  backend `detail` on non-2xx and a friendly "engine room napping" on network failure),
  `frontend/app/page.tsx` (name + one-liner, platform toggle Chess.com-default, username field, "Coach
  me", 3 below-fold honesty notes; client-side regex validation, loading/double-submit guard, submit →
  `router.push('/analyzing/'+job_id)`), a minimal `frontend/app/analyzing/[jobId]/page.tsx` stub (S19
  builds the real live screen), and `.env.example`. Backend UNTOUCHED (Phase-3 wall held).
- **AI-verified**: `cd frontend && npm run build` → **compiled clean, TypeScript passed**, 3 routes
  generated (`/`, `/analyzing/[jobId]`, `/_not-found`) on Next.js 16.2.11 + Turbopack. Opus cross-checked
  `types.ts` field-by-field against `backend/app/schemas.py` (every field + nullability + literal union
  matches) and confirmed the client regexes EXACTLY mirror `_USERNAME_PATTERNS` (chesscom {3,25}, lichess
  {2,30}). The stub sidesteps Next 16's async-`params` breaking change by being a client component using
  `useParams()` — good call flagged in `frontend/AGENTS.md`.
- **Opus review: clean — no bugs.** git hygiene: added `.vexp/` (local index-daemon tooling) to
  `.gitignore` and `git rm --cached`'d it — it had been silently riding along in S16/S17/S18 commits.
- **[founder-to-verify] — the S18 DoD (real browser flow)**: run the backend (`uvicorn`), `cd frontend
  && npm run dev`, type a username → "Coach me" should land on `/analyzing/{job_id}` with a live id;
  check phone-width layout is clean and that Enter submits.
- Next: **Session 19** — the live progress screen (`/analyzing/[jobId]`: poll `getJob()` every 2s, render
  by stage, graceful error/expired copy). Prereq S18 ✓.

### 2026-07-26 · Session 17 · DECISION GATE: report quality + golden files

- No new product features — this session proves report quality and locks it with golden files. Kimi 2.7
  coded + committed (`c51bb2e`, no push); Opus reviewed + ran the mechanical parts live, fixed one
  blocking bug (`cf6980c`), + pushed. NEW `tests/fixtures/features/builders.py` (3 synthetic DB-seeded
  profiles → `load_features` → `(features, player)`), 3 committed golden reports
  (`tactical_blunderer.json` / `positional_leaker.json` / `endgame_loser.json`, each
  `report.model_dump(mode="json")` minus `generated_at`), `tests/test_golden_reports.py` (byte-equality
  + `REGEN_GOLDENS=1` regen switch + a determinism check), `tests/test_specificity.py` (two mechanical
  audits: every issue diagnosis/prescription/success_metric + strength.detail + opening_rec.why must
  carry a digit OR a game reference; the 4 Appendix-3 banned phrases only allowed with a digit in the
  same sentence). Design per approved plan: seed real DB scenarios and run the SHIP path so evidence
  resolves to rich EvidenceRefs (bare PlayerFeatures give empty evidence — useless for a gate).
- **Blocking bug found in review + fixed (`cf6980c`)**: Kimi added a determinism sort to
  `coach._pre_ponr_blunders` keyed on `Game.played_at`, which is NULLABLE (ingest leaves it None when
  the platform omits the timestamp). A batch mixing null + non-null timestamps → `TypeError: '<' not
  supported between NoneType and datetime` on the REAL `blunder_rate` report path. Invisible to the
  suite because every seeded game has a non-null `played_at`. Reproduced the crash, fixed with a
  null-first sort key (`(played_at is None, played_at, ply)`); goldens stayed byte-identical (all seeded
  timestamps non-null), 156 tests still green. [AI-verified]
- **AI-verified**: `pytest -q` → **156 passed, 3 deselected**, ~1.8s, OFFLINE — `pgrep -f stockfish`
  flat (golden building never invokes the engine; features come straight from seeded MoveEval rows).
  Goldens confirmed unchanged by the fix (`git status` on the fixtures dir empty). Both mechanical audits
  pass for all three profiles — so the coach + opening copy already clears the specificity/banned-phrase
  gate; NO fix-first copy edit to Appendix 3 was needed. The two S16 carry-over notes (deepen-copy
  player-number / per-sentence digit) did NOT trip the audit as scoped (the deepen `why` only renders on
  the already-plays path, which these profiles don't hit) — left as-is; revisit only if a future golden
  exercises it.
- **Other review notes (non-blocking, not changed)**: (1) Kimi's second product-code change —
  `load_features` now sorts each game's move-evals by `ply` — is SAFE (`ply` is NOT NULL) and a genuine
  determinism/ordering improvement; kept. (2) commit `c51bb2e` is mislabeled `test:` despite touching
  product code, and swept `.vexp/manifest.json` (local tooling noise) into the commit — history left as
  is; suggest gitignoring `.vexp/` later. (3) `test_build_report_is_deterministic` rebuilds from the
  same session/rows so it can't catch cross-run DB-order flakiness — the golden byte-comparison across
  runs is the real determinism guard.
- **RESOLVED (2026-07-27) — gate verdict = GO** (see Decision Log). Founder reviewed the goldens;
  mechanical audits already green. Made two tweaks at the gate (not a fix-first loop): endgame
  `FEATURE_ENDGAME_AHEAD_CP` 200→300cp (strictly winning) and dropped "leak" from the two user-facing
  strings; Appendix 3 + feature spec updated to match; goldens regenerated (`REGEN_GOLDENS=1` — only the
  opening_leak headline changed) + `test_endgame_conversion_exact_fraction` bumped its qualifying eval
  250→350 for the new threshold. 156 tests green offline, no engine. All finer playstyle/advice/language
  tuning explicitly deferred to pre-ship (tune once the v1 frontend lets reports be seen in situ).
- Next: **frontend v1** — proceed to the next roadmap session (regular workflow: Opus plans → Kimi
  codes → Opus reviews + pushes).

### 2026-07-26 · Session 16 · Opening recommendations (Appendix 4)

- Fills the `opening_recs` the S15 coach left `[]`. Kimi 2.7 coded + committed (`2706324`, no push);
  Opus reviewed + ran the DoD live + pushed. NEW `app/data/openings.json` (the 12 Appendix-4 entries
  transcribed verbatim — bucket × color × primary/alt, each with eco_family / line / why_template /
  a free Lichess study_url) and `app/openings.py` (`_eco_in_family` range matcher, `build_opening_recs`
  → exactly 2 recs (white, black)). Additive `features.py`: new `top_eco_by_color` field +
  `build_features` optional 4th arg (`load_features` computes each color's most-frequent `opening_eco`
  via `Counter`). `coach.py`: one-line swap `opening_recs=[] → build_opening_recs(features)`.
  `detectors.py` and `playstyle.py` UNTOUCHED.
- Design (per the approved plan): one rec per color = the bucket's **primary**. If the player already
  plays that family (`_eco_in_family(top_eco, family)`), `already_plays=True` and the `why` switches to
  the Appendix-4 deepen-don't-switch copy + a mention of the **alt** as a second weapon (honors both
  spec sentences). Bucket = `features.playstyle.label`, defaulting to `balanced` when playstyle absent.
  Non-already-plays `why` = the entry template + the two largest playstyle components with their numbers.
- **KNOWN LIMITATION (documented, not a bug): the already-plays check is Lichess-only.** `ingest.py`
  sets `opening_eco=None` for every Chess.com game (their archive JSON carries no ECO field), so a
  Chess.com player's `top_eco_by_color` is all-None → `already_plays` never fires → they always get the
  primary rec. Honest degradation; a real fix needs a move-sequence→ECO classifier (out of scope).
- **AI-verified**: `pytest -q` → **150 passed, 3 deselected** (was 126; +24 from `test_openings.py`),
  1.15s, OFFLINE — stockfish count went 1→0 (nothing spawned by the run). `_eco_in_family` tested across
  single / en-dash range / ASCII-hyphen range / open-ended `+` / None / empty / wrong-letter / malformed.
  Recs forced for all 3 buckets; exactly-2; every `why` carries a digit; study_links are the Lichess URLs.
  Opus also ran `build_opening_recs` live end-to-end (`import app.main` clean) and eyeballed the copy:
  already-plays fired correctly for both a single-code family (London `D02`) and a range family
  (Caro-Kann `B10–B19`).
- **Opus review: clean — no blocking bugs.** Two notes deferred to the S17 quality gate (S16 DoD passes):
  (1) in the deepen copy the digits are the opening's *move numbers*, not one of the *player's* numbers —
  CLAUDE.md rule 7 wants a player number; honest fix ("played it in N of your last games") needs a small
  features add, right work for S17. (2) S15 enforced digits per-sentence for Issues; S16 enforces
  per-string for `why`, and the deepen copy's first sentence has no digit — if S17's grep goes
  per-sentence on `opening_recs`, that copy needs a tweak.
- **RESOLVED (2026-07-26, founder-verified)** — S16 step 5 (chess judgment): live report for
  chesscom/Eleven_14 (1760, tactical bucket) recommends **white: Italian Game (incl. Evans
  Gambit), C50–C54** and **black: Scandinavian Defense, B01**, each `why` citing the player's own
  eval-volatility (1.00) and queen-keep (1.00) numbers. Founder confirms both pass the sub-1800
  smell test — real, low-theory, club-level-appropriate lines, not engine-approved obscurities.
  Noted (not a bug, just a property of this account): with both playstyle components saturated at
  1.00, the white/black `why` strings share identical phrasing apart from the opening-specific
  clause — worth knowing the template can read as canned when a player's top-two components tie
  at the max. All 12 `study_url` entries in `openings.json` (11 unique — Italian Game is reused for
  both `tactical` and `balanced` white-primary) checked live via curl — all HTTP 200. [founder-verified]
- Next: **Session 17** — DECISION GATE (report quality + golden files). No new features; proves quality
  via 3 golden-file fixtures + the mechanical specificity/banned-phrase audit + the human swap test.
  The two S16 notes above are the natural first items to resolve inside S17's Appendix-3 copy loop.

### 2026-07-26 · Session 15 · The coach: rule engine → Report (Appendix 2 + 3)

- The product's actual product. Kimi 2.7 coded + committed (`dd107cb`, no push); Opus reviewed +
  ran the DoD live + pushed. NEW `app/schemas.py` (full Appendix-2 Report incl. the 2026-07-26 fuller
  `Issue`: success_metric/counter_evidence/rating_impact/refresh_after) and `app/coach.py` (all 11
  Appendix-3 rules — 8 original + the 3 time rules — each a `_Rule` with fires/render; `build_report`
  orders fired rules by (rating_impact bucket, priority), top-3, exactly-one strength per §S, evidence
  resolved to rich EvidenceRefs via a session lookup with graceful degradation when session/player are
  absent). Wired a `coaching` stage into `run_job` (load_features → build_report → persist a `Report`
  row → `report_ready=True`); added `GET /api/reports/{platform}/{username}` (real endpoint, NOT
  dev-gated) + `scripts/print_report.py`. Scope per plan: `opening_recs=[]` (S16), `progress=None`
  (first report), rating_impact = fixed per-rule bucket (pri 1–3 high / 4–7 medium / 8–11 low).
  blunder_rate uses `meaningful_blunders_per_game` + pre-PONR evidence (S13 resolution). `features.py`
  and `detectors.py` untouched.
- **AI-verified**: `pytest -q` → **126 passed, 3 deselected**, 1.15s, OFFLINE — stockfish process
  count flat (no engine spawned). Opus **hand-cross-checked every detector `stats` key the coach reads
  against `detectors.py`'s actual emissions** (hang_pct/hung_count, family/avg_cp/game_count,
  late_ratio/late_blunders, blitz_bpg/rapid_bpg, occurrences, turning_point.ponr_by_game, + the 3 time
  detectors) — ALL match, so no KeyError-on-real-data risk (the class of bug synthetic tests hide).
  Tests are substantive: per-rule render validity, ordering (high/high/medium), top-3 cap, clean player
  → 0 issues + 1 strength (no padding), Pydantic round-trip, opening_general's AND-NOT condition.
  Banned-phrase compliance holds (every diagnosis/prescription/success_metric carries a digit).
- **Opus review: clean — no blocking bugs.** Two notes: (1) low-severity — `late_collapse` can emit
  `late_ratio=None` (zero early blunders); coach coerces to 1.0, so copy reads slightly oddly in that
  rare edge but never crashes — logged as a tuning follow-up, not fixed now. (2) Could NOT run the
  real-data smoke (dev DB empty — no analyzed account), so `build_report` on genuine detector output is
  covered by the manual key cross-check, not a live run.
- **RESOLVED (2026-07-26, founder-verified)** — the S15 DoD's real bar: ran a live `POST
  /api/analyze` for chesscom/Eleven_14 (20 games, rating 1760) end-to-end through `run_job`, then
  `python scripts/print_report.py chesscom Eleven_14`. Top issue: **"Blunders are your rating
  cap" — 2.0 meaningful blunders/game across 20 games, 78% after move 25**, with counter-evidence
  (2.0 of 2.5 raw blunders happen pre-PONR, so the raw count overstates it). Founder's call: "yeah
  looks fine" — clears the bar. [founder-verified]
  - Bug found + fixed while running the DoD: `scripts/print_report.py` referenced a nonexistent
    `stats['games_analyzed']` (the key lives on `player_summary`, not `stats_block`) and its
    `sys.path` hack (`sys.path.insert(0, "backend")`) only resolved when invoked from the repo
    root — but `DATABASE_URL` is a relative sqlite path that only resolves to the real DB when
    invoked from `backend/`, so the two requirements contradicted each other. Fixed both: path
    insert now derives `backend/` from `__file__` (cwd-independent), and the stats-count print
    reads `summary['games_analyzed']`. Script now matches its own docstring (run from `backend/`).
    [AI-verified: ran clean end-to-end from `backend/` after the fix]
- Next: **Session 16** — opening recommendations (Appendix 4): build `openings.py` + `openings.json`,
  fill the `opening_recs` the coach currently leaves `[]`.

### 2026-07-26 · Session 14.5 · Time-coaching detectors (7–9, promoted from Part G #11d)

- Interstitial session from the 2026-07-26 research amendments: built the three time-coaching
  detectors that the council promoted into v1. Kimi 2.7 coded + committed (`f70eb41`, no push);
  Opus reviewed + ran the DoD live + pushed. NEW in `app/detectors.py`: `detect_rushed_blunders`
  (blunders with < DET_TIME_RUSH_SECONDS remaining clock; LOCKED RULE intrinsic), `detect_time_
  trouble_collapse` (error rate under < DET_TIME_TROUBLE_CLOCK vs above), `detect_dawdling`
  (slow "ok" moves in low-complexity positions that precede time trouble — LOCKED RULE honored via
  a legal-move-count complexity gate + confidence:"low"), plus a `_remaining_clock_by_ply` helper
  that re-parses the PGN `[%clk]` (mirrors `analysis.py::extract_move_times`, same ply numbering).
  9 `DET_TIME_*` thresholds in config; the three keys added to `run_detectors`. `features.py`
  untouched — the detectors flow through the existing `detectors` dict to the S15 coach.
- **AI-verified**: `pytest -q` → **117 passed, 3 deselected** (engine tests correctly skipped),
  1.1s, OFFLINE — stockfish process count stayed flat (no engine spawned by the suite). The six
  earlier detectors + `run_detectors`'s six original keys are byte-for-byte unchanged (`git diff`
  is additions-only). New tests are real pos/neg pairs per detector (assert `fired is True/False`
  on distinct conditions) + two direct `_remaining_clock_by_ply` unit tests. Roadmap Appendix-3
  detector-9 spec synced with the complexity gate (Rule 3: law before code).
- **Opus review: clean — no bugs found.** Kimi added one sound refinement beyond the spec: a
  dawdle only counts if it occurred BEFORE the game's first time-trouble ply (causally: dawdle
  early → short later). Scope cut for token budget: did NOT run the live `/api/debug/features` HTTP
  check — the three keys serialize through the same detectors-dict path S13's six already serve, so
  surfacing is structural, not a new risk. [founder-to-verify on a real analyze run when convenient.]
- FYI (unchanged from S14): a stray `stockfish` process was already running on the machine before
  the test run (count 1→1); it is NOT from pytest. Harmless leftover; kill it if you want a clean box.
- Next: **Session 15** — the coach (rule engine → Report, Appendix 3), now consuming the fuller
  `Issue` contract + all nine detectors including these three.

### 2026-07-26 · Session 14 · Playstyle index (Appendix 5)

- FIRST use of a new build workflow: Opus planned → founder handed a self-contained copy-paste
  prompt to **Kimi 2.7** (external coding agent w/ repo access) → Kimi coded + committed (`68ea713`,
  unpushed) → Opus reviewed the commit + ran the DoD live before pushing. (Replaces the Sonnet-
  subagent step; see [[feedback-opus-plan-sonnet-code]] — that memory now covers "delegate coding,
  Opus reviews," whether the coder is a Sonnet subagent or Kimi.)
- Kimi built: NEW app/playstyle.py (Appendix 5 verbatim — `_COMPONENTS` bounds/weights table as a
  documented module constant, not config, since it's a formula tuned via the appendix; `_normalize`
  w/ inverted game_length support; 5 pure component fns; `Playstyle` dataclass matching Appendix 2;
  `compute_playstyle` w/ ±0.25 label bands + top-2-|normalized| explanation + empty-input guard);
  wired `playstyle` into PlayerFeatures/build_features (additive, incl. empty path); NEW
  tests/test_playstyle.py (19 tests: _normalize incl. inverted bounds, each component, 3 label
  bands, explanation, empty).
- Opus review: faithful to Appendix 5; found + FIXED one real bug — `_opposite_castling` matched
  move_san EXACTLY against ("O-O","O-O-O"), missing castling-with-check which python-chess renders
  "O-O+"/"O-O-O+"/"#" (confirmed live). Opposite-castling games are exactly the sharp ones where a
  castle gives check, and the component carries weight 0.20. Fixed by stripping "+#!?" before the
  compare (Opus commit). Tests only used unsuffixed castles, so no test broke.
- Claims:
  - Suite 90 -> 109 (+19 playstyle), green in 1.03s (<15s), offline (bogus-proxy) + no stockfish
    (pgrep); `pytest -m engine` 3 passed [AI-verified]
  - Debug endpoint (`GET /api/debug/features/...`) now surfaces a populated `playstyle` block over
    HTTP (200); serializes via dataclasses.asdict [AI-verified]
  - On the 4 sharp fixture games the label is "tactical" (score 0.29), driven by eval_volatility
    (clamped to +1) + opposite_castling 50% — sensible for decisive games; a real 20-game sample
    would be more representative [AI-verified]
- Repo-hygiene FYI (NOT touched): Kimi's commit also carries a `.vexp/manifest.json` churn — that
  file is a local index-tool artifact already tracked in origin/main (pre-existing), so it's left
  as-is; consider gitignoring `.vexp/` later.
- Still [founder-to-verify]: the DoD's "founder reads their OWN label + explanation and gives a
  verdict" — needs a real analyze run of Eleven_14; if the label feels wrong the fix is to tune
  Appendix 5's bounds FIRST, then playstyle.py (never silent drift). Demonstrated on fixtures only.
- Next step: Session 15 (The coach: rule engine → Report, Appendix 3) — the first session that turns
  features+detectors+playstyle into actual coaching copy.

### 2026-07-26 · Session 13 · Features II: six pattern detectors (+ a critical S12 fix + review-gap tests)

- Preceded by a whole-project /review that found a **critical correctness bug in shipped S12**:
  `analyze_game` stores a move_evals row for EVERY ply (both colors), `calibrate.py` (S9) filters
  to the player's own moves, but `features.py` (S12) did NOT — so all rates/ACPL aggregated over
  BOTH players. Proven: gt_cleanwin (a clean win) reported ACPL 83.2 / 1 blunder; the player's
  true numbers are 14.7 / 0 (the blunder was the OPPONENT's). [AI-verified, now fixed]
- Fourth use of the Opus-plan / Sonnet-code workflow. Founder decisions: lightweight hand-rolled
  SEE (python-chess 1.11.2 has none); read ECO from the PGN (chess.com opening_eco is None but
  the PGN carries [ECO]); meaningful-blunder count + PONR-filtered evidence for the inflation fix.
- Phase 1 FIX: analysis.py `is_player_ply(ply, player_color)` (DRYs calibrate.py's open-coded
  test); features.py filters to the player's own rows for every per-mover aggregation (counts,
  ACPL, phases, per-game, color splits) while leaving position-based features (opening_leak@ply20,
  endgame_conversion entry) reading all rows; test_features.py corrected + an opponent-blunder
  regression test.
- Phase 2 FEAT: NEW app/detectors.py — six pure detectors (hung_pieces w/ a hand-rolled `_see`
  SEE helper, late_collapse, opening_leak w/ `_game_eco` PGN reader, overextension, time_class_split,
  turning_point/PONR), `run_detectors`; 13 named DET_* thresholds in config; build_features wires
  `detectors` + the additive `meaningful_blunders_per_game`; test_detectors.py (18 tests: 3 _see,
  _game_eco, 2×6 pos/neg, meaningful-blunders); calibrate.py gained a detector calibration dump.
- Phase 3 TEST (closes the two /review findings): main.py debug_features now uses
  Depends(get_session); test_jobs.py gained 2 offline run_job integration tests (respx-mocked fetch
  + a StubEvaluator → done, and a 404 → error with the friendly message); NEW test_debug_endpoint.py
  (populated / no-games 404 / ENV=prod 404 via dependency + settings override).
- Opus review: clean — no bugs. Verified `_see` by hand (free knight 300, equal trade 0,
  rook-for-bishop 200); confirmed analysis.py diff is ONLY is_player_ply; features wiring correct
  (player-filtered aggregations, position-based unfiltered); turning-point reinterpretation of the
  roadmap's ambiguous "LAST ply P" as the first ply of the doomed stretch is the only sensible read.
- Claims:
  - Full suite 66 -> 90 (+24: 18 detector, 3 debug-endpoint, 2 run_job, 1 net features), green in
    0.95s (<15s), offline (bogus-proxy) + no stockfish (pgrep); `pytest -m engine` 3 passed
    [AI-verified]
  - S12 bug fixed live: gt_cleanwin now ACPL 14.7 / 0 blunders (was 83.2 / 1) [AI-verified]
  - Blunder-inflation RESOLVED live: gt_lostendgame 3 raw blunders but meaningful=1 (PONR ply 54)
    — the founder's exact 3-vs-1 case [AI-verified]
  - Detectors precision-first on the 4-fixture sample: only turning_point fires; hung_pieces 25%
    (<30%), overextension 2 (<3), time_class_split 0 rapid games — all correctly quiet
    [AI-verified]
- The two /review test-coverage findings (run_job body, debug endpoint) are now CLOSED with
  offline tests. calibrate.py runs the detector dump offline.
- Still [founder-to-verify]: the DoD's founder spot-check of fired detectors on their REAL account
  (needs a network+engine analyze run of Eleven_14); demonstrated instead on the committed fixtures.
- Next step: Session 14 (Playstyle index — Appendix 5: one number in [-1,+1], label, component
  breakdown; separate playstyle.py, prereq S12).

### 2026-07-26 · Session 12 · Features I: rates, phase ACPL, trend, conversion

- Third use of the Opus-plan / Sonnet-code workflow. Founder decisions: DEFER the
  blunder-count-inflation open question to S13 (count 'blunder' rows as-is now — the
  point-of-no-return fix belongs with S13's turning-point detector, not a pre-built heuristic);
  NEST `by_color` under StatsBlock in the report contract.
- Appendix-first (Rule 3): amended CHESSANIA_ROADMAP.md Appendix 2 in its OWN commit (`ecc2feb`)
  — added a `WLD` model + `ColorStats` model, nested as `StatsBlock.by_color = {white, black}`.
  Doc/law only; schemas.py builds it in S16.
- Changed: backend/app/analysis.py (added `player_pov_eval(eval_white_pov, color)` beside
  `cp_loss` — the ONLY other sanctioned perspective conversion, Cardinal Rule 7; cp_loss/
  classify/tag_phase/analyze_game untouched, confirmed via diff); backend/app/config.py (5 named
  feature thresholds — no bare literals: opening-leak 150cp, endgame-ahead 200cp, trend min 8
  games / 10% band, color min 4 games); backend/app/main.py (dev-only GET
  /api/debug/features/{platform}/{username} — 404 when ENV!=dev, friendly 404 when no analyzed
  games, else dataclasses.asdict(features)). NEW: backend/app/features.py (PlayerFeatures + WLD +
  PhaseACPL + ColorStats dataclasses, full shape now with detectors=None for S13; pure
  build_features over stored move_evals — blunder/mistake/inaccuracy per game, ACPL overall +
  per phase, worst_phase self-referenced vs the player's OWN overall, accuracy_trend with the
  8-game guard, opening_leak_rate, endgame_conversion None-when-no-qualifying, evidence lists,
  and the 6 color-split stats with low_signal<4; thin load_features DB wrapper); NEW
  backend/tests/test_features.py (12 offline hand-computed tests).
- Opus review: clean — no bugs. player_pov_eval placed correctly (Rule 7 honored); skipped rows
  excluded from ACPL denominators; None (not 0.0) guards on conversion/ACPL; rounding consistent
  (rates/ACPL 1dp, ratios 2dp). Sonnet also added a `_worst_phase_evidence` helper (top-3
  highest-cp_loss non-skipped moves in the worst phase) — unspecified in the brief but sensible.
- Claims:
  - Offline suite 57 -> 66 (+9 net; test_features.py adds 12), green in 0.78s (<15s), offline
    (bogus-proxy re-run still 66) and no stockfish process (pgrep) [AI-verified]
  - Hand-computed exact numbers pass: single game ACPL 80.0, skipped-excluded stays 80.0,
    worst_phase margin 120.0, all 4 trend verdicts, conversion 0.5 vs None, opening-leak 0.67
    (incl. a black game exercising the player_pov sign flip), color-split low_signal + 0.7 overall
    distinct from per-color [AI-verified]
  - Debug endpoint live over HTTP: seeded ONE analyzed fixture game (gt_lostendgame, offline via
    FixtureEvaluator) into the dev DB, curled GET /api/debug/features/chesscom/<seed> → fully
    populated PlayerFeatures (by_color.black present, detectors null, endgame_conversion null);
    numbers cross-check the S11 recorded counts (3 blunders/3 mistakes/7 inaccuracies). Seed row
    then deleted. ENV=prod → 404 confirmed [AI-verified]
  - The blunders_per_game 3.0 on that seed is a LIVE example of the deferred inflation (only 1 of
    the 3 blunders is meaningful) — S13's turning-point detector is where it gets addressed
- Still [founder-to-verify]: the DoD's "founder reads their OWN account's features and confirms
  the numbers feel truthful" — needs a real analyze run of Eleven_14 (network+engine); the dev DB
  here had no analyzed Eleven_14 data, so I demonstrated the populated path with a seeded fixture
  instead.
- Next step: Session 13 (Features II — the six pattern detectors incl. the turning-point / PONR
  detector; this is also where the blunder-inflation open question gets resolved).

### 2026-07-26 · Session 11 · FixtureEvaluator + offline analysis tests

- Second use of the Opus-plan / Sonnet-code workflow: Opus planned + asked the clarifying
  questions, a Sonnet subagent (Sonnet 5 — "Sonnet 4.6" isn't selectable via the Agent tool
  in this env; founder was told) wrote the code from the approved plan, then Opus reviewed and
  ran the full DoD live. Founder decisions: use the 4 existing fixture PGNs (no network — S11
  stays 100% offline end-to-end), and share the eval_cache logic via a base class (not
  duplication).
- Changed: backend/app/engine_eval.py (extracted CachingEvaluator base owning the eval_cache
  lookup + write-through + hit/miss counters; StockfishEvaluator now subclasses it with
  _compute() holding the unchanged engine path — same clamp, same terminal-safe pv guard;
  added FixtureEvaluator + FixtureMissError, a disk-replay drop-in that raises loudly on an
  unrecorded position; removed a dead `from sqlalchemy import select` import). NEW:
  backend/scripts/record_fixtures.py (one-time real-engine recorder — runs analyze_game over
  each committed PGN, dumps that DB's eval_cache to tests/fixtures/evals/{stem}.json with a
  _meta engine+depth header); backend/pytest.ini (registers `engine`/`live_api` markers,
  addopts excludes them so plain pytest is offline-by-default, `pytest -m engine` overrides);
  backend/tests/test_engine.py (@pytest.mark.engine — real-engine start-pos sanity + the
  deferred terminal-position regression: checkmate & stalemate -> no crash, best_move_uci "");
  backend/tests/fixtures/evals/*.json (4 recorded fixtures, committed). Extended
  backend/tests/test_analysis.py (kept all pure-function tests; added whole-game analyze_game
  runs against FixtureEvaluator: classification counts, phase tags, decided-`skipped` stretch,
  cache write-through+reuse, loud-miss). app/analysis.py untouched (confirmed via git diff).
- Opus review: no bugs this round — the Sonnet output was clean (imports correct,
  StockfishEvaluator behavior genuinely preserved, hardcoded classification counts are real
  depth-12 numbers, not guesses). Only note: FixtureMissError subclasses KeyError (so a bare
  `except KeyError` still catches it) — intentional, documented.
- Recorded classification counts (depth 12, Stockfish 18), pinned in the tests:
  gt_cleanwin ok12/inacc1/mist0/blun1/skip1 (15 plies); gt_piecedrop 63/14/8/2/20 (107);
  gt_lostendgame 70/7/3/3/14 (97); eleven14_blitz_loss 43/8/2/3/0 (56).
- Claims:
  - Default `pytest` 54 passed / 3 deselected in 0.90s (< 15s DoD ceiling), genuinely offline
    (re-run under a bogus HTTP(S)_PROXY still 54 passed) [AI-verified]
  - No real Stockfish process spawns during the default run (pgrep -f found none; the "2 hits"
    from `ps | grep stockfish` were just /bin/zsh command lines mentioning the word)
    [AI-verified]
  - `pytest -m engine` 3 passed / 54 deselected (real path still works; Stockfish 18)
    [AI-verified]
  - Loud miss proven live: hiding a fixture JSON makes its test FAIL, restoring makes it green;
    the dedicated FixtureMissError test covers the missing-*position* case [AI-verified]
  - 4 tests/fixtures/evals/*.json written, each with a `_meta` {engine, depth} header
    (reproducible re-record) [AI-verified]
- Test count 42 -> 57 (54 offline + 3 engine).
- Not done (deferred per roadmap): player features (S12), the six detectors (S13), report
  gen (S15). No new fixture PGNs fetched (founder chose the existing 4). The blunder-count
  inflation OPEN QUESTION (decided-position oscillation) is untouched — still awaiting a
  founder decision, likely folded into S12's blunder_rate feature.
- Next step: Session 12 (Features I — rates, phase ACPL, trend, conversion; the debug
  features endpoint; note the S12 color-split amendment + the hand-computed test game).

### 2026-07-26 · Session 10 · The job system: async analyze endpoint + progress

- First session using the Opus-plan / Sonnet-code workflow: Opus planned + asked the
  clarifying questions, a Sonnet subagent wrote the code from the approved plan verbatim,
  then Opus reviewed the output and ran the full DoD live. Founder decisions: add CORS now,
  delete /api/ingest, verify both a quick (MAX_GAMES=3) and a full (20-game) run.
- Changed: backend/app/jobs.py (NEW — JobStatus dataclass + to_dict; in-memory _registry +
  _lock + Semaphore(MAX_CONCURRENT_JOBS); get_or_create_job with case-insensitive live-job
  dedupe; get_job; run_job = semaphore-guarded fetch->persist->analyze-unanalyzed with
  friendly typed-error messages, no traceback); backend/app/main.py (removed IngestRequest +
  /api/ingest; added CORSMiddleware from settings.CORS_ORIGINS; POST /api/analyze with
  per-platform username regex validation -> 400, dedupe, BackgroundTasks schedule; GET
  /api/jobs/{id} -> status or friendly 404); backend/app/db.py (added PRAGMA busy_timeout=5000
  for 2-concurrent-job SQLite safety); backend/tests/test_jobs.py (NEW — 6 offline tests:
  registry create/dedupe/relive + endpoint validation/schedule/status/404 with run_job
  monkeypatched to a no-op).
- Opus review caught + fixed one real robustness bug in the Sonnet code: StockfishEvaluator
  was opened OUTSIDE the try/except, so a failure to open the engine (bad SF_PATH) would
  have left the job stuck "running" forever with a leaked session and an uncaught thread
  exception. Restructured so session/evaluator are created inside the try (init to None,
  guarded in finally) — engine-open failure now lands the job in state="error" like any
  other error.
- Claims:
  - Offline suite 42/42 (36 -> 42; +6 job tests), genuinely offline (bogus-proxy) [AI-verified]
  - POST /api/analyze returns a job_id in ~1.5ms (target <200ms); polling GET /api/jobs/{id}
    shows live stage fetching->analyzing and current_game climbing 0->N to state=done
    [AI-verified]
  - Full run of the founder's real account (Eleven_14, 20 games): 30s end-to-end (ceiling
    ~5 min); immediate re-run 1s (skip-analyzed + eval cache); 20 games analyzed, 1479
    move_evals rows all with seconds_spent populated [AI-verified]
  - Dedupe: two rapid POSTs for the same account return the identical job_id [AI-verified]
  - Errors: bad-format username -> 400; nonexistent (valid-format) username -> job state
    "error" with "We couldn't find that username on Chess.com — check the spelling?" (no
    traceback) [AI-verified]
  - CORS: access-control-allow-origin: http://localhost:3000 present on an OPTIONS preflight;
    POST /api/ingest now 404 (removed) [AI-verified]
  - No leaked Stockfish process after any run [AI-verified]
- Explain-to-me moment (per the roadmap): why async — analyzing 20 games is ~30s locally but
  1-4 min on a shared cloud CPU; an HTTP request that waits that long gets killed by proxies.
  So POST returns a ticket (job_id) instantly and the browser polls GET /api/jobs/{id} — the
  start->ticket->poll pattern every serious app uses for slow work.
- Open bugs: none new (the blunder-count-in-decided-positions open question from the last
  review is unrelated and still pending a founder decision).
- Next step: Session 11 (FixtureEvaluator + offline analysis tests — lets the full
  analyze/job path be tested with zero engine; also lands the deferred terminal-position
  regression test).

### 2026-07-25 · Session 9 · Classification, phases, perspective helper (+ seconds_spent)

- Planned in plan mode; a depth-12/16 probe during planning reshaped things (see Decision
  Log: kept depth 12, scheduled color-split S12 + turning-point S13, corrected my wrong
  game-2 ground truth). Part A (roadmap amendment) committed separately (33cefef).
- Changed: backend/app/analysis.py — four pure helpers (cp_loss the one perspective helper;
  classify with the decided-position >800 skip; tag_phase; extract_move_times from [%clk]),
  wired into analyze_game replacing the S8 placeholders and populating seconds_spent;
  backend/tests/test_analysis.py (15 offline tests); backend/scripts/calibrate.py;
  tests/fixtures/pgn/gt_{cleanwin,piecedrop,lostendgame}.pgn (the 3 GT games, pre-staging
  S11's fixture set).
- Claims:
  - cp_loss quadrant tests + classify boundary tests (49/50, 99/100, 199/200) + decided-
    position skip + phase + time-extraction all green: 15 new offline tests, full suite
    36/36, genuinely offline (bogus-proxy) [AI-verified]
  - Calibration on the 3 GT games (live engine) matches the corrected ground truth:
    game1 = 0 founder blunders (precision); game2 = 16.dxc4 mistake + 19.Rd7 blunder,
    22.Nh3 correctly ok (recall); game3 = 27.Rxe4 blunder tagged endgame. No blunder-level
    disagreements to investigate [AI-verified]
  - seconds_spent populated from real [%clk] data (107/107 plies on the piecedrop game,
    0-36s, plausible); clockless PGN -> NULL (unit-tested) [AI-verified]
  - Fresh alembic upgrade head clean; no leaked engine process (0 after calibrate) [AI-verified]
  - Ground-truth agreement is against AI-drafted annotations — **founder to verify the 3
    games on the analysis board** to promote the calibration verdict to founder-verified
    [founder-to-verify]
- Explain-to-me moment (per the roadmap), one real move: game 2, your 19...Rd7 — before it
  the eval was about +129 for White (you're ~1.3 pawns worse); after it, +403 for White.
  From your (Black) POV that's a 274-centipawn loss in one move -> classified a blunder ->
  and the engine's better move is stored alongside it. That single move is where a
  difficult game became a lost one.
- Open bugs: none
- Next step: Session 10 (the job system — async analyze endpoint + progress; deletes the
  temporary /api/ingest route).

### 2026-07-25 · Full /review of Sessions 1-8 + amendment · one real bug found and fixed

- Re-ran every DoD live across the whole project: Python 3.12.13; migration chain
  0001->0002 from nothing; all 6 tables + move_evals.seconds_spent present; full suite
  21/21 (genuinely offline via bogus-proxy); requirements match; engine smoke test
  correct; analysis pipeline 56 plies + cache 112/112 on the second run; both fetchers
  live (chesscom + lichess, both now carrying [%clk]).
- Scare that wasn't a bug: a lingering stockfish process showed up mid-review, but a
  fresh check showed 0 and a clean re-run of both engine scripts showed 0 before/0 after
  each — it was a stale orphan from an earlier run this long session, not a code leak.
- Real bug found by fresh-eyes read of the newest code (engine_eval.py): evaluate()
  crashed with KeyError 'pv' on any TERMINAL position (checkmate/stalemate) — Stockfish
  returns no principal variation with no legal moves. analyze_game evaluates the position
  after every move including the last, so ANY game ending in checkmate/stalemate would
  have crashed the whole analysis (would have blown up S10's 20-game job on the first
  mate). The fixture game ended in resignation, so it never surfaced.
- Fix (app/engine_eval.py): guard the pv access — best_move_uci = pv[0].uci() if pv else
  "". The eval is still meaningful (mate=-/+1000); analyze_game only ever reads the
  pre-move position's best move (never terminal), so "" is safe.
- Verified: evaluate() on Fool's-mate final position returns eval_cp=-1000, best_move="";
  a full 4-ply checkmate-ending game now analyzes to 4 rows cleanly (was a crash before);
  fixture game still analyzes; suite still 21/21; no leaked process.
- Follow-up parked: an OFFLINE regression test for the terminal-position case lands in
  S11 (needs FixtureEvaluator + the engine pytest marks, which don't exist yet).

### 2026-07-25 · Session 8 · The Evaluator + eval cache + single-game analysis

- Planned in plan mode first (founder request); two decisions locked via clarifying
  questions: analysis target = founder's own account (chesscom/Eleven_14), and the
  Session-9-owned NOT NULL columns (cp_loss/classification/phase) get safe provisional
  placeholders in S8 that S9 overwrites.
- Changed: backend/app/engine_eval.py (EvalResult dataclass; Evaluator Protocol;
  StockfishEvaluator — opens engine once, White-POV eval clamped ±1000, write-through
  eval_cache keyed by (fen, depth) with flush for intra-run reuse, cache_hits/misses
  counters, close() in finally); backend/app/analysis.py (analyze_game — replays the
  PGN mainline, one move_evals row per ply with raw evals + best_move_san from the
  pre-move position, provisional placeholders for the 3 S9 columns, idempotent via
  delete-existing-then-insert, stamps analyzed_at); backend/scripts/analyze_hello.py
  (manual check + cache-hit proof); backend/tests/fixtures/pgn/eleven14_blitz_loss.pgn
  (first PGN fixture — founder's own game, no scrubbing needed).
- Claims:
  - One real game → full move_evals set: 56 move_evals rows for the 56-ply fixture game,
    one per ply, analyzed_at stamped — verified by querying a real file-backed SQLite DB
    directly [AI-verified]
  - Second run is cache-hot and fast: first run 57 engine calls (= the 57 distinct
    positions in a 56-ply game) + 55 intra-run cache hits in ~1.2s; second run 112/112
    cache hits, 0 engine calls, 0.02s [AI-verified]
  - No leaked engine process: `ps aux | grep stockfish` == 0 both before and after the
    run (try/finally around close()) [AI-verified]
  - Idempotent re-analysis: running analyze_game twice keeps 56 rows, not 112 (delete-
    then-insert) — matters because S9 re-analyzes [AI-verified]
  - Existing suite still 21/21 green, fresh `alembic upgrade head` clean, no new deps
    [AI-verified]
  - **Big swings agree with chess.com's analysis board** — [\_\_\_\_ **unverified —
    founder to confirm**]: open https://www.chess.com/game/live/170639309900 and compare.
    The pipeline's clearest swing is ply 27, White's 27.Nxg5 knight sacrifice: eval goes
    from +153 to -121 (White's POV), i.e. from a small edge to losing, with the engine
    preferring Bxg7. That's the move that lost the game — confirm the shape matches what
    chess.com shows (exact centipawns will differ; chess.com analyses deeper than depth 12).
- Open bugs: none
- Next step: Session 9 (classification, phases, and the cp_loss perspective helper) —
  which will overwrite this session's placeholder cp_loss/classification/phase with real
  values, and needs the founder's P0-3 ground-truth annotations for the calibration check.

### 2026-07-25 · Session 7 · Ingestion tests: the fixture system begins

- Pre-session: full /review of Sessions 1-6 first (see entry below) — no new bugs found,
  everything held up before starting Session 7's new work.
- Changed: backend/tests/fixtures/api/ (chesscom_archives.json, chesscom_month.json —
  5 games covering win/loss/draw + excluded bullet + excluded chess960, all usernames
  scrubbed to fixture_user/opponent_one/opponent_two since no real founder fixture
  account exists yet from Phase 0; chesscom_archives_walktest.json +
  chesscom_month_walktest_{latest,prior}.json — a deliberately thin latest month to
  prove the month-walking behavior; lichess_games.ndjson — 5 lines, newest-first,
  covering win/draw/loss + an excluded bullet game); backend/tests/conftest.py
  (`db_session` fixture — fresh in-memory SQLite per test; `load_fixture` /
  `load_json_fixture` helpers); backend/tests/test_ingest.py (migrated the Chess.com and
  Lichess happy-path tests to load from the fixture files instead of inline JSON; added
  the month-walking test and a fixture-driven full fetch→persist dedupe test matching
  the DoD's literal wording).
- Claims:
  - 21/21 tests pass in 0.10-0.20s — well under the 10s DoD ceiling [AI-verified]
  - Genuinely offline: re-ran with a bogus HTTP_PROXY forcing any real network attempt
    to fail loudly — still 21/21 green [AI-verified]
  - The month-walking test proves the walk-back actually happened (asserts the prior
    month's respx route was called, not just that the final count matched) — with
    MAX_GAMES monkeypatched to 3 so a small, readable fixture (1 game in the thin
    latest month) still forces a real walk to the prior month's 3 games
    [AI-verified]
  - **The break-it ritual itself, performed for real:** deliberately broke the
    color-detection line in fetch_chesscom (forced every game's player_color to
    "white" regardless of who actually played white), ran the suite, watched
    `test_chesscom_happy_path_from_fixture_filters_eligibility_maps_and_orders` fail
    with a clear diff (`['draw','win','win']` instead of `['draw','loss','win']`),
    then reverted via a targeted edit and confirmed `git diff` showed zero drift from
    the pre-break file before re-running to 21/21 green again [AI-verified — this is
    the roadmap's "5-minute ritual," and the founder should still do it themselves at
    least once to get the intended experience; I did it to prove the mechanism works]
- Open bugs: none
- 🏁 **Phase 1 exit reached**: schema live, engine proven, real games from both
  platforms in the DB, all logic offline-tested.
- Next step: Session 8 (PART D begins — the Evaluator + eval cache + single-game
  analysis). Opus is the roadmap's preferred model for Sessions 8-17 (the pipeline core).

### 2026-07-25 · Session 6 · Lichess fetcher, persistence, dedupe

- Pre-session: full /review of Sessions 1-5 first (see the entry below this one) — found
  and fixed one bug (network failures not translated to UpstreamError) before starting
  Session 6's new work.
- Changed: backend/app/ingest.py (`fetch_lichess()`; `fetch_games()` dispatcher;
  `upsert_player()`; `persist_games()` with insert-if-absent dedupe); backend/app/main.py
  (temporary `POST /api/ingest` endpoint — deleted in S10 per the roadmap); backend/scripts
  /ingest_lichess_hello.py; backend/tests/test_ingest.py (10 new tests: Lichess error paths
  + happy path + draw mapping, dispatcher, upsert/dedupe/no-collision).
- Bug found and fixed during live verification (not caught by the offline mocks, since
  my mocks controlled their own response content): Appendix 9 documents
  `opening.{eco,name}` as part of Lichess's response shape, but the exact query string
  it specifies doesn't include `opening=true` — without that flag the real API omits the
  `opening` key entirely, not just nulls it. Confirmed via two direct curl calls
  (with/without the flag) after the live script showed blank ECO columns for a real
  account. Fixed by adding `opening: "true"` to the request params.
- Claims:
  - All 19 tests pass (was 8 after Session 5's fix; +11 this session net of 2 test bugs
    fixed along the way — mismatched usernames in two tests that used the wrong player
    name against the NDJSON helper's default) [AI-verified]
  - Genuinely offline: re-ran with a bogus HTTP_PROXY forcing any real network attempt
    to fail loudly — still green [AI-verified]
  - Live Lichess account (`DrNykterstein`) ingests correctly: 20 games, all blitz,
    ECO codes now populating after the opening=true fix, ratings/colors/results
    structurally sound [AI-verified]
  - Full live end-to-end DoD check via the running server: first `POST /api/ingest`
    for a real Lichess account returns `{"fetched":20,"new":20,"already_known":0}`;
    the identical second call returns `{"fetched":20,"new":0,"already_known":20}`
    (dedupe genuinely working); ingesting a different platform+player (chesscom/hikaru)
    adds its own 20 games with zero collision — verified both via the API responses and
    by querying the SQLite file directly afterward [AI-verified]
  - Spot-check "colors/results match what's on lichess.org" — [\_\_\_\_ **unverified —
    founder to confirm**, same caveat as Session 5: I can't browse lichess.org visually]
- Open bugs: none
- Next step: Session 7 (ingestion tests: the fixture system begins).

### 2026-07-24 · Full /review of Sessions 1-5 · one real bug found and fixed

- Changed: backend/app/ingest.py (wrapped the fetch in try/except httpx.RequestError,
  re-raising as UpstreamError); backend/tests/test_ingest.py (new regression test).
- What the review did: re-ran every DoD command live across all five sessions —
  Python version, fresh `alembic upgrade head`, full test suite, requirements.txt vs
  installed env, both apps' reload/hot-reload behavior (live-edited a running server
  each time, not killed-and-restarted), and the engine smoke test with a
  before/after `ps aux` check. Also fresh-eyes re-read ingest.py end to end.
- Bug found: a genuine network failure (simulated via a monkeypatched httpx.Client
  raising ConnectError) was not caught by any of the four typed exceptions — it
  propagated as a raw httpx.ConnectError. The stated error taxonomy (PlayerNotFound /
  NoEligibleGames / UpstreamRateLimited / UpstreamError) only covered HTTP status
  codes, not transport-level failures, which are common when calling a real external
  API (timeouts, DNS blips, connection refused).
- Fix: wrapped the whole fetch in try/except httpx.RequestError, re-raising as
  UpstreamError. Verified genuinely: reproduced the leak first (monkeypatched
  httpx.Client.get to raise ConnectError, confirmed it propagated uncaught), applied
  the fix and confirmed it was now caught, added a respx-based regression test
  (`test_network_failure_raises_upstream_error_not_a_raw_httpx_exception`), then
  proved that test was real by temporarily removing the fix again and watching the
  test fail before restoring it.
- Claims:
  - All 9 tests pass (was 8; +1 regression test) [AI-verified]
  - The regression test genuinely catches the bug (proved by breaking it on purpose)
    [AI-verified]
  - Live happy-path re-run against the real `hikaru` account still works correctly
    after the fix (no regression from adding the try/except) [AI-verified]
  - Fresh migration, full suite, both reload behaviors, requirements.txt-vs-env, and
    the engine smoke test all still genuinely green across every session built so far
    [AI-verified]
- Open bugs: none
- Next step: Session 6 (Lichess fetcher, persistence, dedupe).

### 2026-07-24 · Session 5 · Chess.com fetcher

- Pre-session check: quick sanity pass before starting (clean working tree in sync with
  origin, fresh `alembic upgrade head`, `pytest` both green) — not a full /review, just
  confirming nothing had drifted since the last one.
- Changed: backend/app/ingest.py (`NormalizedGame` dataclass; `fetch_chesscom()`; typed
  exceptions `PlayerNotFound` / `NoEligibleGames` / `UpstreamRateLimited` / `UpstreamError`);
  backend/scripts/ingest_chesscom_hello.py (manual check script); backend/tests/test_ingest.py
  (6 respx-mocked tests: the 4 error paths + happy-path eligibility/color/result mapping +
  draw-reason mapping); requirements.txt (added respx).
- Claims:
  - All 6 offline tests pass, and genuinely offline — re-ran with `HTTP_PROXY`/`HTTPS_PROXY`
    pointed at an unreachable address to force any real network attempt to fail loudly;
    all 6 still passed, proving respx intercepts before anything touches the network
    [AI-verified]
  - Ran the fetcher against a real, live Chess.com account (`hikaru`): got exactly 20
    games, all `time_class: blitz` (rapid/blitz filter working on real data), colors
    alternating plausibly, mixed win/loss results, newest-first by timestamp
    [AI-verified]
  - `PlayerNotFound` verified against the *real* API, not just the mock: hit a made-up
    username against the live Chess.com endpoint directly via curl, confirmed a genuine
    404, confirmed the fetcher raises the same typed exception for it [AI-verified]
  - Spot-check "colors and results matching what the founder sees on chess.com" —
    [\_\_\_\_ **unverified — founder to confirm** against their own account, since I
    can't browse chess.com visually myself]
- Open bugs: none
- Next step: Session 6 (Lichess fetcher, persistence, dedupe).

### 2026-07-24 · Closing out Session 2's remaining item · pushed to origin

- Changed: nothing code-side; committed the full /review log entry (`b11c50b`) and
  pushed `main` to `origin` (`https://github.com/roanokesrivastav-lab/Chessania`).
- Claims:
  - `git push origin main` succeeded: `7df6305..b11c50b main -> main` [AI-verified]
  - `git status --short --branch` shows `main...origin/main` with no ahead/behind
    [AI-verified]
- Open bugs: none
- Next step: Session 5 (Chess.com fetcher). Session 2's DoD is now fully satisfied —
  docs present, .gitignore correct, repo pushed.

### 2026-07-24 · Session 4 · Stockfish install + engine smoke test

- Changed: installed Stockfish 18 via Homebrew (`/opt/homebrew/bin/stockfish`);
  backend/.env created (gitignored, not committed) with `SF_PATH` set to that binary;
  `chess` (python-chess 1.11.2) added to requirements.txt; backend/scripts/engine_hello.py
  (throwaway smoke script); README.md's Stockfish section filled in with the real
  per-OS paths and a copy-pasteable verification command.
- Claims:
  - `engine_hello.py` opens Stockfish once, analyzes the starting position (White
    +47cp, best move e4) and the Fool's Mate position after 1.f3 e5 2.g4 (Black to
    move, mate in 1 found instantly: Qh4#, White's POV shown as #-1) [AI-verified]
  - No leaked Stockfish process after the script exits — checked via `ps aux` before
    and after the run, both empty [AI-verified]
  - Both a mover-POV and a White-POV score are printed for the same position so the
    perspective difference is visible, not just asserted [AI-verified]
- Open bugs: none
- Next step: Session 5 (Chess.com fetcher).

**Explain-to-me moment, for the record:** a centipawn is 1/100th of a pawn of
advantage — "+47" means White is worth a little under half a pawn more than Black in
that position, nothing decisive yet. A mate score (`#+1` / `#-1`) means the engine has
found a forced checkmate in that many moves, not a centipawn value — `#-1` from
White's POV means White gets mated in 1 move. The eval numbers are always relative to
*someone's* point of view (never absolute), which is why every score above is shown
twice: once from whoever's turn it is to move, once from White's — the convention
every stored eval in this project uses from Session 8 onward, so there's exactly one
place (`cp_loss()`, S9) that ever converts between perspectives.

**Founder check (per DoD):** "eval +150 with White to move — whose position is
better, and by how much?" → White is better by about 1.5 pawns' worth of advantage —
not enough to be winning outright, but a real, meaningful edge. [\_\_\_\_ — founder to
confirm they can answer this without looking it up]

### 2026-07-24 · /review of Sessions 1 & 3 · one real bug found and fixed

- Changed: backend/app/db.py (added `enable_sqlite_foreign_keys()`, wired to the
  singleton engine when DATABASE_URL is SQLite); backend/tests/test_api.py (new
  regression test).
- What the review did (no PR existed — reviewed the local commits/working tree
  directly, re-running every DoD command live rather than trusting the commit
  messages):
  - Re-ran `alembic upgrade head` from a freshly-deleted `chessania.sqlite3`,
    `pytest`, and `curl /health` — all still genuinely green.
  - Diffed every column in models.py / the applied SQLite schema against Appendix 1
    line by line — exact match, no drift.
  - Tested a behavior Appendix 1 implies but Session 3 never explicitly checked:
    does `ON DELETE CASCADE` actually fire? It did not — SQLite ignores FK actions
    entirely unless `PRAGMA foreign_keys=ON` is set per connection. Confirmed by
    inserting a Player + Game, deleting the Player, and finding the Game row still
    present.
- Fix: added `enable_sqlite_foreign_keys(engine)` in db.py (an `event.listens_for`
  connect hook), applied to the app's singleton engine when running on SQLite.
  Exported so tests can attach the same behavior to their own throwaway engines.
- Verifying the fix was real, not cosmetic: added
  `test_deleting_a_player_cascades_to_their_games`, confirmed it **fails** with the
  fix temporarily removed (1 orphaned row instead of 0), then confirmed it passes
  once the fix is back.
- Claims:
  - Cascade delete now works on SQLite dev exactly as it will on Postgres prod
    [AI-verified]
  - Regression test genuinely catches the bug (proved by breaking it on purpose)
    [AI-verified]
  - Full suite (2 tests), fresh migration, and `/health` all still green after the
    fix [AI-verified]
- Open bugs: none
- Next step: Session 4 (Stockfish install + engine smoke test).

### 2026-07-24 · Session 3 · Config + database + the schema migration

- Changed: backend/app/config.py (Settings — DATABASE_URL, SF_PATH, SF_DEPTH=12,
  MAX_GAMES=20, MAX_CONCURRENT_JOBS=2, CONTACT_EMAIL, CORS_ORIGINS, ENV); backend/app/db.py
  (engine + session factory); backend/app/models.py (Player, Game, MoveEval, EvalCache,
  Report — mirrors Appendix 1); backend/alembic/ initialized and wired to
  `app.config.settings` + `app.models.Base`; backend/alembic/versions/0001_initial_schema.py;
  backend/tests/test_api.py (round-trip test); backend/.env.example; requirements.txt
  regenerated (added sqlalchemy, alembic, psycopg2-binary, pydantic-settings).
- Judgment call (not in Appendix 1 verbatim, needed for SQLite/Postgres portability):
  Appendix 1's `default gen_random_uuid()` and `default now()` are Postgres-only. Used a
  portable `GUID` TypeDecorator with a Python-side `uuid.uuid4()` default for IDs, and
  `server_default=func.now()` (works on both engines) for timestamps. Column types,
  constraints, and indexes are otherwise identical to the appendix.
- Bugs found and fixed before applying (autogenerate is not to be trusted blindly — this
  is why the roadmap says to read the generated SQL together):
  - The autogenerated migration referenced `app.models.GUID()` without importing
    `app.models` — would have crashed on `alembic upgrade head`. Added the import.
  - Autogenerate silently dropped `reports_player_idx` (SQLite's dialect can't reflect an
    expression-based descending index to diff against). Added
    `op.create_index('reports_player_idx', 'reports', ['player_id', sa.text('created_at DESC')], ...)`
    by hand, matching Appendix 1's `reports (player_id, created_at desc)` exactly.
- Claims:
  - `alembic upgrade head` builds all 5 tables + `alembic_version` from nothing on a
    freshly-deleted `chessania.sqlite3` [AI-verified]
  - All 5 tables' columns match Appendix 1 exactly (inspected via `sqlite_master` /
    `pragma table_info`) [AI-verified]
  - All 5 indexes present, including the descending `reports_player_idx`
    [AI-verified]
  - Round-trip test (`pytest tests/test_api.py`) passes: insert a Player, read it back,
    all fields match [AI-verified]
  - `/health` still returns `{"status":"ok"}` after adding SQLAlchemy/Alembic/psycopg2
    (no dependency regression) [AI-verified]
  - Founder can explain in one sentence what a migration is [[**unverified — founder
    to confirm**]]: a migration is a numbered, replayable recipe for the database's
    shape — the same recipes that built this SQLite file can rebuild an empty Postgres
    database identically in Session 24.
- Open bugs: none
- Next step: Session 4 (Stockfish install + engine smoke test), or push to origin to
  close out Session 2's remaining DoD item.

### 2026-07-24 · Session 1 · Machine setup + "Hello, both apps"

- Changed: repo cleaned to roadmap A6 layout; added PRD.md, CHESSANIA_ROADMAP.md,
  CLAUDE.md, STATE.md; backend/app/main.py (GET /health), backend/requirements.txt;
  fresh Next.js app in frontend/. Later same day: backend/venv recreated on Python
  3.12.13 (was 3.14.3 — the roadmap's 🔒 stack lock specifies 3.12); requirements.txt
  regenerated from the 3.12 venv.
- Claims:
  - `curl localhost:8000/health` returns `{"status":"ok"}` [AI-verified]
  - Backend `--reload` actually picks up a live code edit without manual restart
    (tested: server left running, `main.py`'s response body edited on disk, re-curled
    same process, new body appeared) [AI-verified]
  - Next.js dev server hot-reloads a live text edit in `page.tsx` without restart
    (same live-edit method as above) [AI-verified]
  - `pytest` runs (0 tests collected is fine) [AI-verified]
  - Backend venv is Python 3.12.13, matching the roadmap's locked stack decision
    [AI-verified]
- Open bugs: none
- Next step: Session 2 (git + guardrail docs — largely in place) or Session 3
  (config + full schema migration 001 from Appendix 1).

## WEEKLY BETA METRICS SQL (filled in S26)

## PARKING LOT (wants that appeared mid-session — logged, not built)

- Time-management coaching (v2, Part G #11): detectors/rules for spent-too-long and
  moved-too-fast-then-blundered. Data is being captured now (move_evals.seconds_spent
  from S9) — this parks the *coaching*, not the capture.
- Playstyle-weighted study prescriptions (considered 2026-07-25, deferred): founder chose
  to keep playstyle→openings and weaknesses→study split for v1; revisit only if beta says
  the study framing feels impersonal.
- v2 Coaching Layer (Part G #11, defined 2026-07-25 — ship v1 first): missed saves, missed
  wins/tactics, tilt/compounding, time coaching (too-fast / dawdling / time-trouble). All
  derivable from existing move_evals columns + retained PGN clocks — no capture gap. Build
  after v1 ships; S13's turning-point detector is the natural base (same critical-moments
  family). Do NOT flag "thought long and still blundered" (good judgment, not a weakness).
