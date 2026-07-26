Chessania — Vibecoding Roadmap (v1.0)
What this document is: The session-by-session execution plan for building the Chessania MVP with Claude (Opus/Sonnet) as the coding partner. It is the operational companion to PRD.md. The PRD explains what and why; this roadmap explains exactly what to build, in what order, in which session, with what guardrails, and how to know each piece is done. The lead engineer who wrote this will not be available afterward — this document IS the lead engineer.


Who reads it:


* The founder — to pace the work: pick the next session, paste the session prompt, approve the plan, verify with real commands and their real chess account, commit, repeat.
* The AI (Claude Opus/Sonnet, in Claude Code) — to know its exact scope for this session and the rules it must not break. If you are an AI reading this cold: read Part A in full, then jump to the single session the founder names. Build nothing outside it.


Companion docs (live in the repo root):


* PRD.md — the condensed product brief (founder supplies; the strategy source)
* CHESSANIA_ROADMAP.md — this file
* CLAUDE.md — short standing instructions loaded into every AI session (template in Appendix 6)
* STATE.md — the living session log and honesty ledger (template in Appendix 7)


________________


PART A — Operating Manual (read before every session)
A1. The working loop
Every unit of work is a session: one sitting (1–4 hours), one vertical slice, one commit (or a few). The loop:


1. Founder opens the repo and picks the next unchecked session in this roadmap.
2. Founder pastes the Session Start Prompt (Appendix 8) into Claude, naming the session number.
3. Claude reads CLAUDE.md + STATE.md + the named session, then restates the goal in plain language and lists the files it plans to create or change — and stops.
4. Founder approves (or adjusts). Only then does Claude write anything.
5. Build in small steps. Verify with the real commands in the session's Definition of Done, using the founder's real chess username where the session says so.
6. When the Definition of Done passes: commit with a clear message, update STATE.md (session entry + checkbox), log any new open questions.
7. Stop. Resist starting the next session "while we're here." One slice per sitting protects momentum and comprehension.
A2. Ten non-negotiable rules for every AI session
1. Plan before files. Show the plan (goal restated + file list + approach) and wait for explicit approval before creating or editing anything. Every session, no exceptions.
2. Plain language always. The founder is learning to code. Explain what each piece does and why, like explaining to a smart friend, not a senior engineer. Every session has at least one designated "Explain-to-me moment" — deliver it unprompted.
3. The schema is law. All database work must match Appendix 1 exactly. Do not invent, rename, or drop fields. If a session seems to need a schema change, stop and raise it as an open question in STATE.md instead.
4. The Do-Not-Build list is absolute. The features in Part G must not be built, stubbed, or "just quickly prototyped" during MVP sessions — even if they seem easy, even if the founder is tempted mid-session. Cite Part G and decline. The founder can override only by editing this roadmap deliberately, outside a coding session.
5. Tests never require the internet or Stockfish. The unit test suite runs offline, deterministic, in under 15 seconds, against committed fixtures (Appendix 10 explains the fixture system). Real-API and real-engine tests exist but are opt-in pytest marks. If a test you're writing needs the network or the engine, you are writing the wrong kind of test — stop and use a fixture.
6. One slice, end to end. Data → pipeline → endpoint (→ screen, once the frontend exists) → verified by the founder running a real command. A half-built slice across three layers is worse than one thin slice that works.
7. Definition of Done means the founder ran it. Every session ends with Claude walking the founder through the exact commands (curl calls, pytest runs, browser steps) to verify each DoD item themselves. STATE.md records each claim as founder-verified, AI-verified, or written-but-unverified — never inflate a claim's status.
8. Commit the moment it works. Claude provides the exact git commands and a clear commit message at session end. Small commits, always pushable.
9. Errors are lessons first, fixes second. When an error appears, Claude explains what it means and why it happened before proposing the fix. No blind paste-and-pray.
10. The specificity bar is a functional requirement. A recommendation that could be copy-pasted to a different player unchanged is a bug, exactly like a crash is a bug (Locked Decision 8). When writing any coaching copy, interpolate the player's actual numbers and cite specific games.
A3. Locked decisions 🔒
🔒 marks decisions only the founder can reopen. Difficulty implementing something is not permission to change a locked decision — if a lock is blocking you, stop, explain the block in plain language, and ask.


1. 🔒 Game input is username-based auto-pull only. The user picks Chess.com or Lichess and types their username; games are fetched from the platforms' public APIs. No manual PGN upload. No OAuth. Neither platform requires authentication to read public games — "connect your account" is literally one text field. This is the entire onboarding and the product's biggest UX advantage; protect it.
2. 🔒 No user accounts, login, or signup in v1. Identity = the pair (platform, username). Reports and history are stored keyed by that pair. Progress tracking works by comparing new analyses to stored past analyses for the same pair. There is no password anywhere in this product.
3. 🔒 No questionnaire. Playstyle is derived from the games themselves (Appendix 5). Nothing stands between the username field and the report.
4. 🔒 The coaching engine is rule-based. No ML, no LLM calls anywhere in the v1 pipeline. Report text is produced by string templates interpolating computed numbers (Appendix 3).
5. 🔒 Target user is sub-1800. No features aimed at 2000+ players (deep prep, opponent scouting, novelty detection).
6. 🔒 Stack: Next.js (App Router) + Tailwind on Vercel · FastAPI (Python 3.12) on Railway · python-chess driving a Stockfish binary · Postgres in production, SQLite in local dev · SQLAlchemy + Alembic for schema.
7. 🔒 Analysis scope: the player's last 20 rapid + blitz games (MAX_GAMES=20, env-configurable). Bullet and daily/correspondence games are excluded — bullet is too noisy to coach from; daily games distort time-pressure patterns.
8. 🔒 Specificity bar. Every issue in a report must cite the player's own numbers and at least one specific game/move. Grep-test enforced in Session 17.
9. 🔒 Async jobs via FastAPI BackgroundTasks + an in-memory job registry. No Celery, no Redis, no external queue in v1.
10. 🔒 Engine settings: depth-based analysis (SF_DEPTH=12, ceiling 14), one engine process at a time per job, evals cached by (fen, depth).
11. 🔒 Reports are shareable URLs with no privacy layer in v1: /r/{platform}/{username} shows the latest stored report to anyone. This is honest (the games are already public on the platforms) and it is the growth loop. State it plainly in the UI footer.
A4. Decision protocol
* Mechanical questions (syntax, a single error, "which import"): straight answer, no ceremony.
* Strategic forks (a scope tradeoff, a copy-tone question, a launch call): present 2–3 options with a plain-language tradeoff table and a recommendation. The founder decides; log it in STATE.md → Decision Log.
* Two decision gates are built into this roadmap (Session 17: report quality gate; Session 23: pre-deploy gate). Do not blow past them.
A5. Tooling for the AI sessions
* Best fit: Claude Code (it reads CLAUDE.md automatically, edits files, runs pytest/uvicorn/curl directly).
* Model: strongest available (Opus preferred for Sessions 8–17, the pipeline core; Sonnet is fine everywhere else). The session structure is designed so any capable model with CLAUDE.md + STATE.md + one session's text has everything it needs — no memory of prior sessions is assumed.
* Two repos-in-one (monorepo): backend sessions never touch /frontend, frontend sessions never touch /backend except to read the report contract (Appendix 2).
A6. Repo layout (target state)
chessania/


├── PRD.md


├── CHESSANIA_ROADMAP.md


├── CLAUDE.md


├── STATE.md


├── backend/


│   ├── app/


│   │   ├── main.py            # FastAPI app, routes, CORS


│   │   ├── config.py          # every env var, with defaults


│   │   ├── db.py              # engine/session factory (SQLite dev, PG prod)


│   │   ├── models.py          # SQLAlchemy ORM mirroring Appendix 1


│   │   ├── schemas.py         # Pydantic: request bodies + the Report contract (Appendix 2)


│   │   ├── ingest.py          # chesscom + lichess fetchers → NormalizedGame


│   │   ├── engine_eval.py     # Evaluator interface, StockfishEvaluator, FixtureEvaluator


│   │   ├── analysis.py        # per-game eval loop, classification, phase tagging, caching


│   │   ├── features.py        # PlayerFeatures extraction + pattern detectors


│   │   ├── playstyle.py       # tactical/positional index (Appendix 5)


│   │   ├── coach.py           # rule engine (Appendix 3) → Report


│   │   ├── openings.py        # recommendation lookup over openings.json (Appendix 4)


│   │   ├── jobs.py            # in-memory job registry + background task runner


│   │   └── data/


│   │       └── openings.json  # the committed recommendation table


│   ├── tests/


│   │   ├── fixtures/


│   │   │   ├── api/           # recorded Chess.com + Lichess HTTP responses


│   │   │   ├── pgn/           # ~6 committed real games (varied ratings/phases)


│   │   │   ├── evals/         # recorded eval JSONs keyed by fixture game


│   │   │   └── features/      # 3 synthetic PlayerFeatures JSONs for coach tests


│   │   ├── conftest.py


│   │   ├── test_ingest.py


│   │   ├── test_analysis.py


│   │   ├── test_features.py


│   │   ├── test_playstyle.py


│   │   ├── test_coach.py


│   │   └── test_api.py


│   ├── scripts/


│   │   ├── record_fixtures.py # one-shot: hit real APIs/engine, write fixtures


│   │   └── print_report.py    # CLI: pretty-print a stored report


│   ├── alembic/               # migrations (001 = full schema)


│   ├── requirements.txt


│   └── Dockerfile


└── frontend/


    ├── app/


    │   ├── page.tsx           # landing: platform toggle + username + button


    │   ├── analyzing/[jobId]/page.tsx   # progress screen (polls)


    │   └── r/[platform]/[username]/page.tsx  # the report


    ├── components/            # ReportHeader, IssueCard, OpeningRecCard, ...


    ├── lib/


    │   ├── api.ts             # typed fetch helpers to the backend


    │   └── types.ts           # TS mirror of the Report contract


    └── ...
A7. Timeline reality check
At nights-and-weekends pace (1–3 sessions/week), Phase 0 through deploy is roughly 8–12 weeks. Weeks are elastic; the sequence is not. Never skip a session's prerequisites. It is completely fine for a session to take two sittings — split it, commit the working half, note the split point in STATE.md, resume.


The dependency spine, so nobody re-derives it: schema (S3) → engine smoke (S4) → ingestion (S5–S7) → analysis (S8–S11) → features (S12–S14) → coach (S15–S17) → UI (S18–S21) → progress (S22) → deploy (S23–S25) → beta (S26+). Sessions 12–14 can interleave with 18–19 if the founder wants a UI morale boost mid-pipeline — nothing in the frontend before S20 needs real reports.


________________


PART B — Phase 0: Fixtures & Ground Truth (zero code, ~1 week)
No code is written in this phase, but its outputs are hard dependencies: the fixture accounts feed every test in the project, and the hand-annotated ground truth is how we'll know the analysis pipeline tells the truth. AI sessions here are research/curation help only.
P0-1. Pick 3 fixture accounts
* The founder's own account (Chess.com or Lichess — whichever has ≥20 recent rapid/blitz games).
* One public account around ~800–1100 and one around ~1500–1700 (find candidates via the platforms' public games; any active public player works — their games are public data). One of the three must be on the other platform from the founder's, so both fetchers get a real-account workout.
* Record all three (platform, username) pairs in STATE.md → Fixture Registry.
P0-2. Manual API walk (curl only, no code)
Prove both public APIs behave as Appendix 9 describes before any code depends on them:


* Chess.com: fetch the archives list for one fixture account, then fetch the latest month, and eyeball the JSON: find pgn, time_class, end_time, white.username, white.rating, white.result. Confirm the request fails or degrades without a User-Agent header and works with one.
* Lichess: fetch max=5 games as NDJSON and eyeball one line: find players.white.user.name, players.white.rating, speed, winner, pgn, opening.eco.
* Save both sample responses somewhere safe — they become the recorded test fixtures in S7.
P0-3. Hand-annotate ground truth (the calibration set)
Pick 3 games from the fixture accounts (one clean win, one blunder-fest, one lost endgame). For each, the founder — with Claude's help in chat, using the platforms' own analysis boards — writes down: the 2–3 genuinely bad moves (move numbers), which phase went worst, and a one-sentence "what a coach would say." Save as STATE.md → Ground Truth. Sessions 9 and 13 must reproduce these findings; if the pipeline disagrees with the human eye on these three games, the pipeline is wrong.
P0-4. Sanity-check the opening table
Read Appendix 4's twelve entries aloud. The founder (a chess player) confirms each mapping passes the smell test at sub-1800 level and adjusts names/lines in the appendix before it's committed as openings.json in S16. This is a chess-judgment task, not a code task — do it while it's cheap.


Phase 0 exit criteria: 3 fixture accounts logged · both APIs manually verified with saved sample responses · 3 ground-truth games annotated · opening table founder-approved.


________________


PART C — Phase 1: Environment & Foundations (Sessions 1–7)
Goal of the phase: a running FastAPI backend with the full schema, a proven Stockfish install, and real games from real accounts landing in the database — all tested offline.


________________


Session 1 — Machine setup + "Hello, both apps"
Est: 1–2 h · Prereq: none


Goal: The tightest possible feedback loops on both halves: edit backend code → server reloads; edit frontend code → page hot-reloads.


Steps:


1. Install: Python 3.12, Node.js LTS, Git, VS Code (safe default).
2. Backend: create backend/, then python -m venv venv && source venv/bin/activate, pip install fastapi "uvicorn[standard]" pytest httpx. Create a minimal app/main.py with a GET /health returning {"status":"ok"}. Run uvicorn app.main:app --reload, hit it with curl.
3. Frontend: npx create-next-app@latest frontend (TypeScript, Tailwind, App Router — accept defaults). npm run dev, see the starter page, change one string, watch it hot-reload.
4. Write backend/requirements.txt (pip freeze > requirements.txt is fine for now; it gets curated in S23).


Explain-to-me moment: what a virtual environment is (a project-private toolbox so this project's Python packages can't collide with any other project's) and what --reload does (a watcher restarts the server on every file save — the backend's version of hot reload).


Definition of Done:


* curl localhost:8000/health returns ok; editing the message and re-curling shows the change without restarting anything.
* localhost:3000 renders; a text edit hot-reloads.
* pytest runs (zero tests collected is fine today).


Commit: (git arrives next session — just don't delete anything)


________________


Session 2 — Repo + guardrail documents
Est: 1 h · Prereq: S1


Goal: Version control and the standing instructions that make every future AI session consistent.


Steps:


1. git init at the monorepo root; create .gitignore before anything else: venv/, node_modules/, .env, __pycache__/, .next/, *.sqlite3, .pytest_cache/.
2. Create the private GitHub repo and push.
3. Add the four companion docs to the root: PRD.md (founder pastes the condensed brief), this roadmap, CLAUDE.md from Appendix 6, STATE.md from Appendix 7.
4. First commit: chore: scaffold backend + frontend + project docs.


Guardrails: CLAUDE.md stays under ~60 lines — it's the always-loaded context, not the encyclopedia. Depth lives in PRD.md and here.


Definition of Done:


* Repo pushed; git status clean; all four docs present.
* .env pattern verified ignored (create an empty backend/.env, confirm git status doesn't show it, keep it).


________________


Session 3 — Config + database + the schema migration (the most important session in the project)
Est: 2–3 h · Prereq: S2


Goal: Create the entire data model from Appendix 1 — every table, column, index, and constraint — via Alembic migration 001, run against local SQLite. Some columns sit unused for weeks (e.g. reports.report_json until S15); they exist from day one because they're cheap now and painful to retrofit mid-pipeline. This session is run once, correctly, with understanding.


Steps:


1. pip install sqlalchemy alembic psycopg2-binary pydantic-settings.
2. app/config.py: a Settings class (pydantic-settings) reading every env var with defaults — DATABASE_URL (default sqlite:///./chessania.sqlite3), SF_PATH, SF_DEPTH=12, MAX_GAMES=20, MAX_CONCURRENT_JOBS=2, CONTACT_EMAIL (goes in the Chess.com User-Agent), CORS_ORIGINS, ENV=dev. No tunable number is ever hardcoded at a call site — everything routes through config.
3. app/db.py: engine + session factory from DATABASE_URL. One plain-language note in comments: SQLite locally, Postgres in prod, and SQLAlchemy makes the code identical.
4. app/models.py: ORM classes mirroring Appendix 1 exactly — Claude walks the founder through the appendix table by table in plain language before writing any code: what each table stores, why eval_cache exists (never pay Stockfish twice for the same position), why move_evals.classification includes skipped (decided positions don't count against you), what an index is (a phone book so lookups don't read every row).
5. alembic init, wire it to the models, autogenerate migration 001, read the generated SQL together, apply it.
6. A trivial round-trip test in test_api.py: insert a Player, read it back.


Explain-to-me moment: what a migration is — a numbered, replayable recipe for the database's shape, so production Postgres in S24 can be built by replaying the same recipes the SQLite dev DB grew from. The migration folder is the database's birth certificate.


Guardrails: zero schema improvisation (Rule 3). If anything in Appendix 1 can't be expressed, fix it in the appendix too so the repo copy stays true.


Definition of Done:


* alembic upgrade head builds a fresh DB from nothing; all tables visible (inspect with any SQLite viewer or a python -c snippet Claude provides).
* Round-trip test passes. Founder can explain in one sentence what a migration is.
* Commit: feat: config, db wiring, full schema migration 001.


________________


Session 4 — Stockfish install + engine smoke test
Est: 1–2 h · Prereq: S3


Goal: A working engine the code can talk to, and the founder's first look at what an eval actually is — before building anything on top of it.


Steps:


1. Install Stockfish locally (macOS: brew install stockfish; Linux: apt install stockfish; or the official binary). Put the path in .env as SF_PATH; document per-OS install in the README.
2. pip install chess (the python-chess package). Do not install the separate stockfish pip wrapper — python-chess's chess.engine module is the maintained way and everything here uses it.
3. A throwaway script (scripts/engine_hello.py): open the engine with chess.engine.SimpleEngine.popen_uci(settings.SF_PATH), analyze two positions at depth 12 — the starting position, and the position after 1.f3 e5 2.g4 (where Black has Qh4#, so the engine should scream mate) — print the score and best move for each, quit the engine cleanly.
4. Read the output together: what a centipawn is (1/100 of a pawn of advantage), what a mate score means, and the perspective trap: python-chess returns scores relative to a point of view you must choose — always call .pov(color) explicitly, never assume.


Explain-to-me moment: the engine is a separate program the code converses with over a pipe (the UCI protocol) — which is why it must be opened once and reused, not reopened per move (each open pays a startup cost).


Definition of Done:


* The smoke script prints sensible evals for both positions and exits without a hung process (check with ps).
* Founder can answer: "eval +150 with White to move — whose position is better and by how much?"
* Commit: feat: engine smoke test + SF_PATH config.


________________


Session 5 — Ingestion I: the Chess.com fetcher
Est: 2–3 h · Prereq: S3


Goal: Given a Chess.com username, return the last MAX_GAMES eligible games as clean, normalized Python objects.


Steps:


1. pip install respx (httpx is already in).
2. In ingest.py, define the NormalizedGame dataclass — the common shape both platforms are forced into: platform, platform_game_id, game_url, pgn, time_class, player_color, result (win/loss/draw from the analyzed player's perspective), player_rating, opponent_rating, played_at, opening_eco, opening_name.
3. fetch_chesscom(username) -> list[NormalizedGame]:
   * Lowercase the username (Chess.com URLs require it).
   * GET the archives list (Appendix 9), walk archive months newest → oldest, fetching serially, until MAX_GAMES eligible games are collected or 3 months are exhausted.
   * Eligible = time_class in (rapid, blitz) and rules == "chess" (this excludes bughouse/960 variants — state why in a comment).
   * Determine which color the user played by case-insensitive username match on white.username / black.username; map their result string to win/loss/draw per Appendix 9's table.
   * platform_game_id = the game's url (unique per game, stable).
   * Always send the User-Agent header built from CONTACT_EMAIL (P0-2 proved why).
4. Error taxonomy, mapped to typed exceptions the API layer translates later: PlayerNotFound (404), NoEligibleGames, UpstreamRateLimited (429 → this fetcher does not retry-loop; it raises, and the job reports a friendly "try again in a minute"), UpstreamError (anything else).
5. A scripts/-level manual check: run the fetcher against the founder's fixture account, print a table of the games.


Explain-to-me moment: why normalize at the edge — the entire rest of the pipeline (analysis, features, coach) speaks only NormalizedGame, so platform weirdness is quarantined in one file, and adding a third platform someday touches one function.


Definition of Done:


* Manual run against a real account prints ≤20 games, all rapid/blitz, colors and results matching what the founder sees on chess.com (spot-check 3).
* The four error paths raise the right typed exceptions (force each: fake username; a filter that excludes everything; simulated 429 via respx in a quick test).
* Commit: feat: chess.com fetcher + NormalizedGame.


________________


Session 6 — Ingestion II: Lichess fetcher, persistence, dedupe
Est: 2–3 h · Prereq: S5


Goal: The second fetcher, plus games durably in the database with re-run safety.


Steps:


1. fetch_lichess(username) -> list[NormalizedGame]: single GET with NDJSON accept header, max=MAX_GAMES, perfType=blitz,rapid, pgnInJson=true (Appendix 9 for the exact call). Parse line-by-line (each line is one JSON game). Map fields into NormalizedGame; platform_game_id = the Lichess game id; game_url = https://lichess.org/{id}.
2. fetch_games(platform, username) dispatcher.
3. Persistence (ingest.py): upsert the players row on (platform, username); snapshot the rating. Insert games with insert-if-absent semantics on (player_id, platform_game_id) — running ingestion twice must add zero duplicate rows. Return counts: fetched / new / already-known.
4. Temporary test endpoint POST /api/ingest {platform, username} returning those counts (S10 folds this into the analyze job; delete the route then).


Explain-to-me moment: idempotency — "safe to run twice." It shows up at three layers in this project (game upsert here, skip-analyzed in S10, eval cache in S8), and it's what makes a crashed job restartable instead of a mess.


Definition of Done:


* Real Lichess fixture account ingests correctly (spot-check colors/results on lichess.org).
* Running POST /api/ingest twice for the same user: second response shows new: 0.
* Both platforms' games coexist for different players in the DB without collision.
* Commit: feat: lichess fetcher + persistence + dedupe.


________________


Session 7 — Ingestion tests: the fixture system begins
Est: 2 h · Prereq: S6


Goal: The ingestion layer fully tested offline — the founder's first taste of the fixture-first discipline every later layer copies.


Steps:


1. Move the P0-2 saved API responses into tests/fixtures/api/ (one Chess.com archives-list + one month JSON; one Lichess NDJSON of ~5 games). Trim to ≤5 games each so fixtures stay readable; hand-edit usernames in the fixtures to fixture_user so no real stranger's handle is baked into the repo (the founder's own is fine to keep).
2. Tests with respx mocking httpx: happy path per platform (correct count, colors, results, ordering newest-first) · bullet/variant filtering · 404 → PlayerNotFound · 429 → UpstreamRateLimited · dedupe (ingest same fixture twice against a fresh in-memory SQLite, assert new: 0) · Chess.com month-walking (fixture with a thin latest month forces the fetcher to walk back one archive).
3. conftest.py: a fresh in-memory SQLite per test (create tables via the models' metadata — fast and isolated), plus a fixture-loading helper.
4. Confirm the whole suite runs offline: turn off Wi-Fi, pytest, green.


Explain-to-me moment: what mocking is — respx intercepts the code's outgoing HTTP and hands back the recorded file, so tests check our logic, not Chess.com's uptime — and why that makes tests fast, free, and honest.


Definition of Done:


* pytest green, offline, < 10 s.
* Founder deliberately breaks the color-detection line, watches the right test fail, reverts. (This 5-minute ritual — break it, watch it catch you — is the point of the whole session.)
* Commit: test: offline ingestion suite + recorded API fixtures.


🏁 Phase 1 exit: schema live, engine proven, real games from both platforms in the DB, all logic offline-tested.


________________


PART D — Phase 2: The Analysis & Coaching Pipeline (Sessions 8–17)
The heart of the product. Order matters tightly here: evals → classification → jobs → tests → features → playstyle → coach → openings → quality gate. Opus is preferred for this phase. Standing guardrail: Part G is in force — in particular, no ML scaffolding, no LLM report phrasing, no "while we're here" extra detectors beyond the six specified (was five; a sixth, turning-point, added by the 2026-07-25 founder-approved amendment — still a hard cap, Rule 4).


________________


Session 8 — The Evaluator + eval cache + single-game analysis
Est: 3–4 h (two sittings is normal) · Prereq: S4, S7


Goal: One game in → per-move evals out, with the two design moves that make everything after this testable and fast: the Evaluator interface and the eval cache.


Steps:


1. engine_eval.py — define the seam:


class Evaluator(Protocol):


    def evaluate(self, board: chess.Board) -> EvalResult: ...


    # EvalResult: eval_cp (int, White's perspective, mate clamped to ±1000),


    #             best_move_uci (str)


    def close(self) -> None: ...


   * StockfishEvaluator: opens the engine once (S4 pattern), analyse at Limit(depth=SF_DEPTH), converts score with .pov(chess.WHITE).score(mate_score=1000), clamps to ±1000. The convention, stated in a docstring in capital letters: EVERY EVAL STORED ANYWHERE IN THIS SYSTEM IS FROM WHITE'S PERSPECTIVE; conversion to the mover's perspective happens in exactly one helper (S9). Two perspectives floating around is the classic chess-engine bug factory.
   * Constructor takes an optional cache session; on each call, check eval_cache by (fen, depth) first, write-through on miss.
2. analysis.py — analyze_game(game, evaluator) -> list[MoveEvalRow]: replay the PGN mainline with chess.Board; for each ply record fen_before, eval before, push the move, eval after, and the engine's best move (SAN-ified from the position before it was played). No classification yet — raw numbers only this session. Persist rows; stamp games.analyzed_at.
3. Manual run on one fixture game; print a ply-by-ply eval table next to the same game open on the platform's analysis board. Eyeball agreement on the big swings (exact numbers will differ — platforms use different depths; the shape must match).
4. Second run of the same game: near-instant (every position cache-hits). Print the cache hit count to prove it.


Explain-to-me moment: why the interface exists before the second implementation does — S11's FixtureEvaluator will slot into the same socket, which is the whole trick that lets 90% of the project's tests never touch the engine.


Definition of Done:


* One real game produces a full move_evals set; big swings agree with the platform's analysis; second run is cache-hot and fast.
* Engine process count on the machine returns to zero after the run (no leaks — try/finally around close()).
* Commit: feat: evaluator interface, stockfish impl, eval cache, raw game analysis.


________________


Session 9 — Classification, phases, and the perspective helper
Est: 2–3 h · Prereq: S8


Goal: Raw evals become coaching-grade labels, matching the Phase-0 ground truth.


Steps:


1. The one perspective helper, used everywhere, tested to death:


def cp_loss(eval_before_white_pov: int, eval_after_white_pov: int,


            mover: chess.Color) -> int


From the mover's perspective: loss = (before − after) if mover is White, (after − before) if Black; floor at 0 (an improvement is 0 loss). Unit-test all four quadrants with hand-computed numbers.


2. Classification per Locked thresholds: 0–49 ok · 50–99 inaccuracy · 100–199 mistake · ≥200 blunder. Decided-position rule: if |eval_before| > 800 (from the mover's POV), classification = skipped — a "blunder" in a dead-lost position is noise, not signal, and counting it would poison every downstream rate.
3. Phase tagging: opening = ply ≤ 20 · endgame = ≤ 6 non-king, non-pawn pieces remain on the board · middlegame = the rest. (Deliberately simple; a smarter boundary is a logged v2 nicety, not a v1 blocker.)
4. Wire both into analyze_game; re-analyze the three ground-truth games (cache makes this cheap).
5. Populate move_evals.seconds_spent (added by the 2026-07-25 amendment): for each of the player's moves, derive the clock time spent from the PGN's [%clk] comments — python-chess exposes the remaining clock per node via node.clock(); time_spent = (this player's previous remaining clock − current remaining clock) + increment (parsed from the TimeControl header, e.g. "180" = no increment, "180+2" = 2s), with the first move measured from the starting clock. Leave it null when the PGN has no clock data. This is CAPTURE ONLY — no v1 feature, detector, or rule reads it (Part G reserves the time-management coaching that will).
6. The calibration check: compare the pipeline's blunder list per game against the founder's P0-3 annotations. Target: every human-flagged bad move is caught (recall), and nothing the founder considers fine is labeled a blunder (precision on the big label). Threshold disagreements at the inaccuracy/mistake border are acceptable; blunder-level disagreements are bugs — investigate, don't rationalize.


Explain-to-me moment: walk one real move through the math out loud: "eval was +120 for you, after your move it's −180 for you, that's a 300-centipawn loss, that's a blunder, and here's the better move the engine saw."


Definition of Done:


* Ground-truth agreement achieved on all three games; result recorded in STATE.md → Ground Truth (founder-verified).
* cp_loss quadrant tests + threshold boundary tests (49/50, 99/100, 199/200) green.
* Commit: feat: classification, phase tagging, perspective helper + calibration.


________________


Session 10 — The job system: analyze endpoint + progress
Est: 3 h · Prereq: S9, S6


Goal: The public API shape the frontend will live on: kick off a full ingest-and-analyze as a background job, watch it progress, never block.


Steps:


1. jobs.py: an in-memory registry dict[job_id, JobStatus] where JobStatus = {state: queued|running|done|error, stage: fetching|analyzing|coaching, current_game, total_games, error_message, report_ready}. A module-level semaphore caps concurrent jobs at MAX_CONCURRENT_JOBS=2; jobs beyond the cap sit in queued. Plain-language comment: this registry dies on restart, and that's an accepted v1 tradeoff (Part G #9 holds the durable-queue seat).
2. POST /api/analyze {platform, username} → validate (username regex per platform: Chess.com [a-zA-Z0-9_-]{3,25}, Lichess [a-zA-Z0-9_-]{2,30}), create job, schedule via BackgroundTasks, return {job_id} immediately (measure: < 200 ms).
3. The job body: ingest (S6) → for each game without analyzed_at, analyze (S9), updating current_game/total_games as it goes → (report generation attaches here in S15; until then the job ends after analysis) → done. Wrap everything in try/except: any typed ingestion error or engine failure lands in error_message as a human sentence ("We couldn't find that username on Chess.com — check the spelling?"), never a traceback.
4. GET /api/jobs/{job_id} → the status object; 404 for unknown ids (with a note that a restarted server forgets jobs — the frontend copy in S19 handles this: "That analysis expired — start a fresh one").
5. Dedupe guard: a second POST for a (platform, username) that already has a live job returns the existing job_id instead of double-analyzing.
6. Manual end-to-end: analyze the founder's account with curl, poll in a watch loop, watch current_game climb, time the whole run.


Explain-to-me moment: why async — 20 games ≈ 800–1200 engine calls ≈ 1–4 minutes on a cloud CPU; an HTTP request that waits that long gets killed by every proxy on the internet. The job pattern (start → ticket → poll) is how every serious app does slow work.


Definition of Done:


* Founder-run curl flow: POST returns instantly; polling shows live progress; full first run ≤ ~5 min locally; immediate re-run completes in seconds (skip-analyzed + cache).
* Bad username → job ends in error with a friendly sentence. Two rapid POSTs → one job.
* Commit: feat: async analyze jobs + progress endpoint.


________________


Session 11 — FixtureEvaluator + offline analysis tests
Est: 2 h · Prereq: S10


Goal: The pipeline's test harness: the full analysis path tested with zero engine.


Steps:


1. scripts/record_fixtures.py: for each PGN in tests/fixtures/pgn/ (commit ~6 now: the 3 ground-truth games + 3 more covering a short miniature, a long endgame grind, and a wild tactical game), run the real StockfishEvaluator at SF_DEPTH and write tests/fixtures/evals/{game}.json mapping fen → {eval_cp, best_move_uci}. Run it once; commit the outputs. Header comment in each JSON: engine version + depth, so a future re-record is reproducible.
2. FixtureEvaluator in engine_eval.py: loads those JSONs; evaluate() is a dict lookup; raises loudly on a miss (a miss means the test is analyzing a position that was never recorded — a real bug, not something to paper over with a default).
3. Rewrite/extend test_analysis.py to run whole games through analyze_game with the FixtureEvaluator: assert classification counts per fixture game, phase tags at known plies, the decided-position skipped behavior (one fixture game must actually contain a decided stretch — the endgame grind does), and cache write-through.
4. Mark the S4-style real-engine test @pytest.mark.engine and exclude that mark by default in pytest config; same for any @pytest.mark.live_api tests.


Explain-to-me moment: deterministic tests — the recorded evals never change between runs, so a failing test always means the code changed behavior, never "the engine felt different today." That certainty is what makes refactoring safe for a beginner.


Definition of Done:


* Full suite green, offline, no engine required, < 15 s.
* pytest -m engine separately green on this machine (proves the real path still works).
* Commit: test: fixture evaluator + recorded evals + offline pipeline suite.


________________


Session 12 — Features I: rates, phase ACPL, trend
Est: 2–3 h · Prereq: S11


Goal: The first half of PlayerFeatures — the aggregate numbers the coach speaks in.


Steps:


1. features.py: PlayerFeatures dataclass (it will grow across S12–S14; define the full shape now with None for not-yet-computed sections, so the contract is visible early). This session computes:
   * games_analyzed, results (W/L/D), rating snapshot, time-class mix.
   * Per-game and aggregate: blunders/mistakes/inaccuracies per game (excluding skipped plies from denominators — say why in a comment).
   * ACPL overall and per phase (average centipawn loss — the single best "how well do you actually play" number).
   * worst_phase: the phase whose ACPL most exceeds the player's own overall ACPL (relative, not absolute — an 900-rated player's "good" phase would be a 1700's disaster; we always compare the player to themself).
   * accuracy_trend: per-game ACPL in chronological order + a simple direction verdict (improving/flat/declining via first-half vs second-half means; guard the tiny-sample case — fewer than 8 games → verdict insufficient_data, and the coach copy handles it honestly).
   * opening_leak_rate: % of games where the player's eval (their POV) dropped ≥150cp by ply 20.
   * endgame_conversion: of games that reached an endgame while the player was ahead ≥200cp, the % actually won. Guard division by zero (no such games → None, not 0 — "no data" and "converts nothing" are very different coaching facts).
2. Evidence discipline starts here (Locked 8): every feature that can cite a moment carries evidence: list[(game_id, ply)] — e.g. opening_leak_rate keeps the 3 worst offending games; worst_phase keeps the 3 worst plies in that phase. Downstream copy is only as specific as the evidence collected now.
2b. Color-split the weakness features (added 2026-07-25 amendment): compute results (W/L/D), blunder rate, ACPL, worst_phase, opening_leak_rate, and endgame_conversion BOTH overall AND split by games.player_color (white vs black), so a real color gap ("you leak far more as Black than White") is a first-class, reportable weakness rather than being averaged away. Sub-1800 win rates often differ sharply by color; games.player_color is already stored per game. Guard small per-color samples the same way as the trend guard (fewer than ~4 games of a color → the per-color number is low-signal; carry it but let the coach copy hedge). Appendix 2's report contract gains a per-color stats breakdown — spec the exact fields when this session is built. (Openings are already color-split — Appendix 4 recommends per color.)
3. Debug endpoint GET /api/debug/features/{platform}/{username} dumping the object (dev-only; gated off in prod via ENV in S23).
4. Tests against fixture evals with hand-computed expected numbers for at least one small game (yes, by hand with a calculator — the one time hand-checking the math pays for itself forever).


Definition of Done:


* Debug endpoint returns a fully populated part-one PlayerFeatures for the founder's real account; the founder reads it and confirms the numbers feel truthful.
* Hand-computed test game passes. Commit: feat: core player features (rates, phase ACPL, trend, conversion).


________________


Session 13 — Features II: the six pattern detectors (5 original + turning-point)
Est: 3–4 h · Prereq: S12


Goal: The distinctive-insight layer — each detector returns {fired: bool, stats: dict, evidence: list}, and exactly these six, no more (Rule 4; was five, +turning-point per the 2026-07-25 amendment):


Steps:


1. Hung pieces — of the player's blunders, the share where the position after their move allows an immediate winning capture: detect by checking whether the engine's best reply is a capture that wins material ≥ a minor piece (use python-chess's static-exchange-evaluation helpers on the reply move). Fires at ≥ 30% of blunders. Evidence: the 3 clearest hangs.
2. Late-game collapse — blunder rate in plies > 30 ≥ 2× the rate in plies ≤ 30 (min 4 late blunders to fire — small-sample guard). Evidence: 3 late collapses.
3. Opening repetition leak — group the player's games by ECO family (letter + first digit, e.g. B1x = Caro-Kann territory); any family with ≥ 5 games and average player-POV eval at ply 15 ≤ −40cp fires, carrying the family's name and per-game evidence. This powers the coach's best line: "your most-played opening is quietly losing you the opening."
4. Overextension (explicitly heuristic — labeled confidence: low in its stats, and the coach copy hedges accordingly): a player pawn move to their 6th rank or beyond, followed within 6 plies by a player eval drop ≥ 150cp; fires at ≥ 3 occurrences.
5. Time-class split — free and useful for prescriptions: compute blunder rate separately for blitz vs rapid; fires if blitz ≥ 1.8× rapid with ≥ 5 games of each (the "you don't have a chess problem, you have a clock problem" insight).
6. Turning-point / point-of-no-return (added 2026-07-25 amendment) — per game, find the ply after which the player's own-POV eval never again recovers above a "still playable" threshold (e.g. -150cp): the move the game actually slipped away, which is often EARLIER than the biggest single cp_loss (a live probe confirmed this — a player's game was decided by a move-16 mistake + move-19 blunder that opened lines for a passed pawn, while the eye-catching "hung piece" at move 22 was already-lost noise, correctly scored ok). Reports the turning-point ply + the move there as evidence, distinct from "your single worst move." Pure function over stored move_evals; rule-based, no ML. Fires when a decisive turning point exists that is NOT the same move as the largest cp_loss (i.e. when the game was lost by a slide, not one blunder) — this is where it adds insight over the plain blunder list. NOTE this stays "which move" — the "WHY it was bad" (opened a file, allowed a passed pawn) is v2 phrasing (Part G).
7. Each detector is a pure function over stored move_evals + games — no engine calls (everything needed was stored in S8–S9; if a detector seems to need a new engine call, its design is wrong — raise it, don't call).
8. Calibration: run against the ground-truth games and the founder's account; founder sanity-reads every fired detector's evidence (open the cited moves on the platform and confirm the story is real).


Explain-to-me moment: precision beats recall throughout — a detector that stays quiet is mildly unhelpful; a detector that fires wrongly makes the whole product feel like a horoscope. Every threshold above was chosen to under-fire.


Definition of Done:


* All six tested against fixtures (construct at least one positive and one negative case per detector).
* Founder-verified evidence spot-check on their own account logged in STATE.md.
* Commit: feat: six pattern detectors with evidence.


________________


Session 14 — Playstyle index
Est: 2 h · Prereq: S12


Goal: Implement Appendix 5 exactly: one number in [−1, +1] (positional ↔ tactical), a label, and the component breakdown that makes it explainable.


Steps:


1. playstyle.py: compute the five raw components (capture density, game length, eval volatility, opposite-castling rate, queen-keep rate) per Appendix 5's definitions, normalize each through the appendix's fixed bounds, combine with the fixed weights. The formula lives in one function whose docstring restates Appendix 5 in plain language — the appendix is law; the docstring is the translation.
2. Label mapping: score ≤ −0.25 → "positional"; ≥ +0.25 → "tactical"; between → "balanced". The explanation string cites the two strongest components with their numbers ("you castle opposite sides in 31% of games and your positions swing hard — you thrive in sharp play").
3. Attach to PlayerFeatures. Tests: three synthetic move-eval sets hand-built to score clearly tactical, clearly positional, and balanced.
4. Founder reads their own label + explanation and gives a verdict: does it match how they'd describe their chess? Log the verdict; if it's badly wrong, the fix is tuning bounds in Appendix 5 first, then re-implementing — never silent drift between doc and code.


Definition of Done:


* Three synthetic tests green; founder verdict on their own label logged.
* Commit: feat: playstyle index per Appendix 5.


________________


Session 15 — The coach: rule engine → Report
Est: 3–4 h · Prereq: S13, S14


Goal: PlayerFeatures in → a stored, contract-conforming Report out — the product's actual product.


Steps:


1. schemas.py: the full Pydantic Report model exactly per Appendix 2 — this is the frontend contract and changes only by changing the appendix + both sides in one session.
2. coach.py: implement the rule table exactly per Appendix 3 — each rule = condition over features, priority, and a render(features) producing headline/diagnosis/prescription/links/evidence from the appendix's copy templates with real numbers interpolated. No rule beyond the table; no freelance copy.
3. Selection: evaluate all rules → keep fired ones → sort by priority → top 3 become issues. The strength is chosen per Appendix 3 §S (best phase or best stat, with its number). If fewer than 3 rules fire (a clean player), 1–2 issues is correct — never pad with filler.
4. Wire report generation into the S10 job as the final stage (stage: coaching); store the JSON in reports; job's report_ready flips true.
5. GET /api/reports/{platform}/{username} → the latest stored report (404 with friendly copy if none). scripts/print_report.py for terminal reading.
6. Generate the founder's real report; read it together, out loud.


Explain-to-me moment: why templates, not an LLM (Locked 4) — the numbers are the credibility; a template cannot hallucinate a stat it wasn't handed, and determinism means the same games always produce the same advice, which is what "engine-backed" should mean.


Definition of Done:


* Founder's real report exists, conforms to the contract (Pydantic guarantees it), and contains at least one line that makes the founder think "…that's true and I hadn't seen it put that way." If it doesn't clear that bar, the session isn't done — tune via Appendix 3, not ad hoc.
* Commit: feat: rule-based coach + report storage + endpoints.


________________


Session 16 — Opening recommendations
Est: 2 h · Prereq: S15


Goal: The playstyle-aware opening module per Appendix 4.


Steps:


1. Commit the founder-approved (P0-4) table as app/data/openings.json; openings.py loads it once at startup and looks up (playstyle_bucket, color).
2. The already-plays check: if the player's most-frequent ECO family for that color matches a recommended opening's family, set already_plays: true and the why switches to the deepen-don't-switch copy (Appendix 4 §Rules) — telling a Caro-Kann player to "learn the Caro-Kann" is the exact genericness this product exists to avoid.
3. The why must interpolate playstyle evidence (the S14 explanation components). Every rec carries a free study_link (Lichess opening explorer/study URLs — the JSON holds them; verify each is live).
4. Attach opening_recs (white + black) to the report; extend the S15 expectations.
5. Founder reads their own recs for both colors; chess-judgment verdict logged.


Definition of Done:


* Recs render for all three playstyle buckets (force each via a synthetic features object in tests); already-plays path proven with a synthetic repertoire.
* Commit: feat: playstyle-aware opening recommendations.


________________


Session 17 — DECISION GATE: report quality + golden files
Est: 2–3 h · Prereq: S16 · Blocks: all frontend report work


The gate (no new features — this session only proves quality):


1. Golden-file tests: three synthetic PlayerFeatures fixtures in tests/fixtures/features/ — the tactical blunderer (~900, hangs pieces, blitz-heavy), the positional opening-leaker (~1400, one leaking ECO family, fine endgames), the endgame loser (~1600, low blunders, terrible conversion) — each produce a full report asserted verbatim against a committed golden JSON. Any future copy or logic change shows up as a diff a human reads and re-approves. (Plain-language aside: golden files are how you code-review words.)
2. The specificity audit (Locked 8), mechanical: a test that walks every diagnosis/prescription string in all three golden reports and fails if any contains no digits and no game reference. Plus the grep-test: Appendix 3's banned-phrase list may not appear unless immediately adjacent to a number.
3. The swap test, human: founder reads the three golden reports side by side and confirms no paragraph could be moved to a different player unchanged. Verdict logged.
4. Gate output: go / fix-first, logged in STATE.md → Decision Log. Fix-first loops back through Appendix 3 edits + golden re-approval. Do not proceed to S20 on a fix-first verdict.


Definition of Done:


* Goldens committed; specificity tests green; swap-test verdict logged; gate verdict logged.
* Commit: test: golden reports + specificity gate.


🏁 Phase 2 exit: the entire product works headless — a curl away from any username to a coach-grade report.


________________


PART E — Phase 3: The Face (Sessions 18–22)
Frontend sessions. The backend is finished and off-limits except lib/types.ts mirroring Appendix 2. Standing guardrails: mobile-first (test at iPhone-width first, desktop second) · no component library beyond Tailwind · no chessboard renderer (Part G #6 — link out to the platforms; a board component is a two-week scope trap wearing a one-hour costume).


________________


Session 18 — Landing page
Est: 2 h · Prereq: S1 (backend running locally)


Goal: The entire top of the funnel: one screen, one decision, one field.


Steps:


1. lib/types.ts (hand-mirror of Appendix 2) and lib/api.ts (analyze(), getJob(), getReport() — typed fetch helpers reading the backend URL from NEXT_PUBLIC_API_URL).
2. The page: product name, one sentence ("Free coaching report from your last 20 games — no signup."), platform toggle (two big buttons, Chess.com default), username field, "Coach me" button. Below the fold: three one-line honesty notes — what it does, sub-1800 focus, reports are shareable-public.
3. Submit → POST /api/analyze → router.push('/analyzing/' + job_id). Client-side username validation mirrors the S10 regexes with friendly inline messages.
4. Loading state on the button (double-submit guard); backend-down state ("Chessania's engine room is napping — try again in a minute.").


Definition of Done:


* Real flow from the browser reaches the progress route with a live job id; phone-width layout clean; keyboard "enter" submits.
* Commit: feat: landing page + typed api client.


________________


Session 19 — Progress screen
Est: 2 h · Prereq: S18


Goal: 1–4 minutes of waiting that feels alive, not broken.


Steps:


1. /analyzing/[jobId]: poll getJob() every 2 s. Render by stage: fetching → "Pulling your recent games…" · analyzing → progress bar + "Analyzing game {current} of {total}" · coaching → "Writing your report…" · done → auto-redirect to the report URL.
2. Rotating one-liners under the bar (a small array of chess-flavored waiting copy — playful, calm, no jargon).
3. Error states, each with its own copy path: job error (show the backend's human sentence + a "try another username" link) · 404/unknown job (server restarted: "That analysis expired — start a fresh one") · poll network failure (retry with backoff, only surface after 3 consecutive misses).
4. Stop polling on unmount and on terminal states (explain the cleanup function — the beginner's first useEffect teardown, worth two minutes).


Definition of Done:


* Founder watches a real analysis progress end-to-end and land on the report route; kill the backend mid-poll and see the graceful copy, not a spinner of lies.
* Commit: feat: live progress screen.


________________


Session 20 — The report page (the product's face)
Est: 4 h (two sittings is normal) · Prereq: S17, S19


Goal: Render Appendix 2 beautifully at phone width.


Steps:


1. /r/[platform]/[username]: fetch the latest report server-side (fast first paint, and shared links unfurl with real content).
2. Component per contract section:
   * ReportHeader — username, platform badge, rating, games analyzed, date range, playstyle label as a colored chip.
   * StrengthCard — one card, visually warm, always above the issues (sub-1800 players quit tools that only criticize — the order is a product decision, not a style one).
   * IssueCard ×≤3 — headline large; diagnosis with the interpolated numbers visually emphasized (the numbers ARE the credibility — style them like evidence, not like body text); prescription with its links as buttons; evidence as an expandable list, each row = game date/opponent rating/move + a deep link straight to that game on chess.com/lichess (the platforms' game URLs from ingestion — this outsources the chessboard, which is why we don't build one).
   * OpeningRecCards — white and black side by side (stacked on phone), the why, the study link, and the deepen-vs-switch framing when already_plays.
   * StatsBlock — compact grid: ACPL by phase, blunders/game, conversion rate, trend arrow.
   * Footer: "Analyzed {n} games at depth {d} · Reports are public at this link · Re-analyze" (button → POST /api/analyze → progress screen).
3. Empty/404 path: "No report for this player yet — want one?" with the landing form inline.
4. Cross-check every rendered number against the raw JSON (print_report.py side by side) — rendering is where numbers silently swap.


Definition of Done:


* Founder's real report, phone-width, zero console errors; every evidence deep-link opens the right game at the platform; a friend's phone loads the shared URL cold.
* Commit: feat: report page.


________________


Session 21 — Frontend hardening lap
Est: 2 h · Prereq: S20


Goal: Every screen honest in its three states (loading/error/empty) and the copy pass.


Steps:


1. Walk the full flow as three personas: happy path · typo'd username · a username with 2 total games (NoEligibleGames and the small-sample insufficient_data trend copy must both read kindly).
2. Copy sweep: every string sounds like a friendly strong player, not a database ("No rapid or blitz games found for that account" not "0 eligible rows").
3. Favicon + <title>/OG tags (shared report links should unfurl with the player's name — it's the growth loop's clothing).
4. Lighthouse quick pass at phone emulation; fix anything egregious, log the rest.


Definition of Done:


* Three-persona walk clean; commit: chore: frontend hardening + copy pass.


________________


Session 22 — Progress tracking (the return visit)
Est: 2–3 h · Prereq: S20 (a backend + frontend session — the one exception to the phase wall, by design)


Goal: The second analysis tells the player whether they're improving — honestly.


Steps:


1. Backend: at report generation, if prior reports exist for the player, compute progress per Appendix 2: deltas vs the previous report and vs the first report for blunders/game, overall ACPL, worst-phase ACPL, conversion. Each delta carries its direction (better/worse/flat — mind the sign flips: lower ACPL is better; centralize that mapping in one function) plus both raw values. Honesty guard: if the two reports' game sets overlap heavily (< 5 new games since last time), set progress.note to the low-signal copy ("mostly the same games as last time — play a few more for a real read") rather than proclaiming trends from noise.
2. Frontend: a ProgressCard on the report (renders only when progress exists): arrows + both numbers + the date span ("2.4 → 1.7 blunders/game since July 2"). Sparkline optional; arrows with numbers are the requirement — plain and true beats pretty and vague.
3. Golden test: two synthetic sequential reports → asserted deltas including a sign-flip case and the low-signal case.


Definition of Done:


* Founder re-analyzes their real account (having played new games since S15) and the deltas match a hand-check of the two stored report_jsons.
* Commit: feat: progress tracking.


________________


PART F — Phase 4: Deploy & Beta (Sessions 23–26+)
Session 23 — DECISION GATE: pre-deploy review + hardening
Est: 2 h · Prereq: S22


Gate (30 min): walk four questions, log verdicts: Quality — do the S17 goldens still pass, and does the founder's own report still clear the "didn't-know-that" bar? Cost — depth-12 × 20 games per user on a shared Railway CPU: what does one analysis cost in minutes, and does MAX_CONCURRENT_JOBS=2 + queueing keep a small viral moment survivable? Honesty — does every screen say true things in every failure mode (kill the backend and click everything)? Scope — has anything from Part G leaked in? Output: go / fix-first.


Then the hardening minimums:


1. pip install slowapi; rate-limit POST /api/analyze to 3/hour/IP with friendly 429 copy ("You've queued a few already — reports keep, come back soon.").
2. CORS locked to the (future) Vercel domain via CORS_ORIGINS; debug endpoints gated off when ENV=prod.
3. Curate requirements.txt (pin versions, drop strays).


Definition of Done:


* Gate verdict logged · rate limit proven with a curl loop · commit: chore: pre-deploy gate + rate limiting.


________________


Session 24 — Deploy the backend
Est: 3 h + waiting on builds · Prereq: S23


Steps:


1. Dockerfile: python:3.12-slim base, apt-get install -y stockfish, copy app, install requirements, run alembic upgrade head on boot then uvicorn. SF_PATH=/usr/games/stockfish (the apt location — verify locally with docker run ... which stockfish before deploying).
2. Railway: new project from the repo, add the Postgres plugin, set every S3 env var (DATABASE_URL from the plugin, ENV=prod, CONTACT_EMAIL, CORS_ORIGINS placeholder). Deploy; watch logs; migrations apply on first boot.
3. Timing reality check: analyze the founder's account on production hardware and time it. If it's dramatically slower than local (shared CPUs are), the knob is SF_DEPTH — 11 is acceptable, document the change in STATE.md if turned. Depth below 11 requires a founder decision (analysis quality is the product).
4. Money note (Appendix 9): Railway's hobby tier is ~$5/mo after trial credit — the project's only recurring cost.


Definition of Done:


* Production /health ok · a full real analysis completes on prod with timing logged · commit: feat: dockerfile + railway deploy.


________________


Session 25 — Deploy the frontend + end-to-end smoke
Est: 1–2 h · Prereq: S24


Steps: Vercel import of /frontend · NEXT_PUBLIC_API_URL → the Railway URL · backend CORS_ORIGINS → the Vercel domain (redeploy) · then the smoke test that matters: founder, phone, cellular data (not Wi-Fi), full flow, share the report link to a second device. Write the tester click-path (5 lines) into STATE.md.


Definition of Done:


* Cellular-data full flow clean · commit: chore: vercel deploy + smoke path. 🏁 Chessania is live.


________________


Session 26+ — The beta loop (weekly, ~4–6 weeks)
The single question this phase answers: does the report make players feel seen? Everything serves getting a clean read on that.


1. Recruit 15–30 sub-1800 players: chess club friends, beginner-improver communities on Reddit/Discord (follow each community's self-promo rules). The pitch is the product: "free coaching report from your last 20 games, no signup — 3 minutes."
2. The one interview question after someone reads their report: "Which line felt most true, and which felt most generic?" The second answer is the work queue for Appendix 3 tuning.
3. Weekly metrics (saved SQL in STATE.md; the database already knows — no analytics SDK): reports generated · distinct players · re-analysis rate (the retention signal: did anyone come back?) · error-job rate by error type · p50/p95 analysis duration · eval-cache hit rate (should climb weekly as common openings accumulate).
4. Weekly ritual: ship at least one visible improvement from feedback. Copy/threshold tuning → the Appendix 3 → code → goldens loop; bugs → fix; v2 cravings → Part G, log, do not build.
5. Exit reading: players share their report links unprompted and re-analyze after playing more → the loop is real; consider Part G #1–2 next. Reports read as generic despite the numbers → the problem is rule copy and detector precision — fix there; more features will not save advice that doesn't land.


________________


PART G — v2 Horizon: the Do-Not-Build list (and why each is safe to defer)
During MVP sessions this list is a hard fence (Rule 4). Each entry notes the seat already reserved for it — proof that deferring costs nothing. Rough later-order with triggers:


1. Manual PGN upload + OTB games — seat: NormalizedGame is source-agnostic; a PGN parser slots in beside the fetchers. Trigger: beta users who play over-the-board ask for it by name.
2. User accounts + private reports — seat: players is already the identity spine; auth would hang off it. Trigger: someone actually objects to public reports (Locked 11 states the policy plainly meanwhile).
3. LLM-phrased reports — templates stay the source of truth; an LLM could rephrase a generated report, never generate facts. Trigger: beta says the numbers land but the prose feels robotic. (This is also the seat for positional "WHY" explanations — "16.dxc4 opened the c-file and let the passed pawn run" rather than just "16.dxc4, -130cp, best was X". v1 says WHICH move and HOW MUCH, and S13's turning-point detector says WHERE it slipped; explaining WHY in prose is this LLM layer, NOT a depth problem — a 2026-07-25 planning probe confirmed depth 12 already locates the right moves.)
4. ML recommender — seat: every report + subsequent re-analysis delta is training data quietly accruing in reports. Trigger: hundreds of players with return visits — not before.
5. 2000+ mode — a different product (prep, novelties, calculation depth). Trigger: a real cohort of strong users asks, and sub-1800 is already well served.
6. In-app chessboard / move replay — the evidence deep-links outsource this to the platforms. Trigger: users demonstrably don't click through. (It will be tempting every single frontend session. The links are the feature.)
7. Puzzle integration — generating puzzles from the player's own blunders is the killer version. Seat: move_evals.fen_before of every blunder is literally a puzzle set waiting. Trigger: the coaching loop is trusted first.
8. Coach-mode chat ("ask about your report") — trigger: only after #3, and only with the report as grounding.
9. Durable job queue (Celery/Redis) + horizontal engine workers — seat: the Evaluator seam and job registry isolate exactly what would change. Trigger: real queue-depth pain in the weekly metrics, not imagined scale.
10. Openings deep-dive product (repertoire builder, line trainer) — seat: the ECO-family stats from detector #3. Trigger: opening recs are the most-clicked report section for weeks running.
11. THE v2 COACHING LAYER — "the coach that does everything" (defined 2026-07-25 from a full founder interview). v1 ships blunder-classification first (founder's call: ship v1, layer richness); these are the layered-on detectors, all in the SAME aggregate-report surface (new sections/issues + evidence links — NOT a new per-game review), all rule-based (no ML; the positional "WHY" prose stays the LLM seat, #3). CRITICAL FINDING, proven not assumed: every one needs ZERO new data capture or migration — each derives from move_evals as it already exists (eval_cp_before/after, cp_loss, best_move_san, classification, phase, seconds_spent, player_color, ply, fen_before) plus games.pgn's retained [%clk]. A read-only derivation over the founder's own piece-drop game, using only eval_cp_before + cp_loss + player_color, surfaced his exact example (move 19 Rd7: he was -1.3 and fighting, a 274cp drop collapsed it). The "capture now, coach later" discipline already bought this whole layer. These are the same "critical moments" family as the v1 turning-point detector (S13 #6), so S13's machinery is the natural base. The pieces:
    - a. Missed saves — a worse-but-still-tenable position (your-POV eval_before ~ -50..-350) where a high cp_loss means a fighting move existed and you let it collapse. Teaches defense/resilience. Seat: move_evals (eval_cp_before + cp_loss + player_color).
    - b. Missed wins / tactics — a winning eval_before + high cp_loss = you were winning and let it go. Seat: same columns.
    - c. Tilt / compounding — a mistake/blunder immediately followed by another (the emotional spiral). Seat: consecutive move_evals.classification ordered by ply.
    - d. Time coaching — three flags: (i) too-fast-then-blundered (low seconds_spent + blunder), (ii) dawdling/indecision (high seconds_spent burned on low-cp_loss moves, leaving you short), (iii) time-trouble collapse (error rate rising as the remaining clock falls — remaining clock reconstructable from seconds_spent + [%clk]). Seat: move_evals.seconds_spent + games.pgn. LOCKED RULE (founder insight): do NOT flag "thought long AND still blundered" as a weakness — spending time on a genuinely critical move is GOOD judgment (you picked the right place to invest), not a flaw; if anything it's a positive signal.
    Trigger for the whole layer: the v1 eval-based coaching loop is shipped and trusted first. (Note: v1 reads NONE of this — capture/derivability only.)


________________


APPENDIX 1 — The Complete Database Schema (Session 3, exactly as written)
This is the law referenced by Rule 3. Expressed as Postgres DDL; the SQLAlchemy models in models.py mirror it 1:1 and Alembic migration 001 realizes it (SQLite accepts this shape for dev; jsonb maps to JSON, timestamptz to datetime).


-- =====================================================================


-- Chessania — initial schema (001)


-- =====================================================================


-- Players: identity = (platform, username). No auth anywhere (Locked 2).


create table players (


  id              uuid primary key default gen_random_uuid(),


  platform        text not null check (platform in ('chesscom','lichess')),


  username        text not null,           -- stored lowercased, always


  rating_snapshot int,                     -- best-known rating at last ingest


  created_at      timestamptz not null default now(),


  unique (platform, username)


);


-- Games: one row per fetched game, PGN retained verbatim.


create table games (


  id               uuid primary key default gen_random_uuid(),


  player_id        uuid not null references players(id) on delete cascade,


  platform_game_id text not null,          -- chess.com game URL / lichess game id


  game_url         text not null,          -- deep link used in report evidence


  pgn              text not null,


  time_class       text not null check (time_class in ('rapid','blitz')),


  player_color     text not null check (player_color in ('white','black')),


  result           text not null check (result in ('win','loss','draw')),


  player_rating    int,


  opponent_rating  int,


  played_at        timestamptz,


  opening_eco      text,                   -- e.g. 'B12'


  opening_name     text,


  analyzed_at      timestamptz,            -- null = not yet analyzed (job skip-key)


  created_at       timestamptz not null default now(),


  unique (player_id, platform_game_id)     -- the dedupe law (S6)


);


create index games_player_idx   on games (player_id);


create index games_analyzed_idx on games (player_id, analyzed_at);


-- Move evals: the pipeline's ground truth. ALL evals White-POV (S8 law).


create table move_evals (


  id             bigint generated always as identity primary key,


  game_id        uuid not null references games(id) on delete cascade,


  ply            int  not null,             -- 1-based half-move number


  move_san       text not null,


  fen_before     text not null,


  eval_cp_before int  not null,             -- White POV, clamped ±1000, mate=±1000


  eval_cp_after  int  not null,


  cp_loss        int  not null,             -- mover's POV, floored at 0 (S9 helper)


  best_move_san  text not null,


  classification text not null check (classification in


                   ('ok','inaccuracy','mistake','blunder','skipped')),


  phase          text not null check (phase in


                   ('opening','middlegame','endgame')),


  seconds_spent  int,                       -- player's clock time on this move (sec);


                                            -- null when the PGN carries no clock data.


                                            -- Populated S9 from [%clk] deltas; captured


                                            -- for v2 time-management coaching (Part G),


                                            -- NOT used by any v1 feature/rule.


  unique (game_id, ply)


);


create index move_evals_game_idx  on move_evals (game_id);


create index move_evals_class_idx on move_evals (game_id, classification);


-- Eval cache: never pay Stockfish twice for one position (S8).


create table eval_cache (


  fen           text not null,


  depth         int  not null,


  eval_cp       int  not null,              -- White POV, clamped


  best_move_uci text not null,


  created_at    timestamptz not null default now(),


  primary key (fen, depth)


);


-- Reports: the product's output, whole, as JSON conforming to Appendix 2.


create table reports (


  id             uuid primary key default gen_random_uuid(),


  player_id      uuid not null references players(id) on delete cascade,


  games_analyzed int  not null,


  first_game_at  timestamptz,               -- date range shown in the header


  last_game_at   timestamptz,


  report_json    jsonb not null,


  created_at     timestamptz not null default now()


);


create index reports_player_idx on reports (player_id, created_at desc);
What deliberately does NOT exist (so nobody "helpfully" adds it)
No users/auth tables (Locked 2) · no jobs table (the registry is in-memory, Locked 9; Part G #9 holds the seat) · no puzzles/chat/social tables (Part G) · no per-rule config table (Appendix 3 is code + doc, and that's correct at this scale).


________________


APPENDIX 2 — The Report Contract (Pydantic in schemas.py; TS mirror in lib/types.ts)
schema_version: 1. Changing this contract = editing this appendix + schemas.py + types.ts + goldens, in one session, deliberately.


class EvidenceRef(BaseModel):


    game_url: str            # deep link to the game on its platform


    played_at: datetime | None


    opponent_rating: int | None


    ply: int                 # half-move where it happened


    move_san: str            # what was played


    detail: str              # one line: "hung the knight; Nxe5 wins it (–310)"


class Link(BaseModel):


    label: str               # "Lichess pawn-endgame practice"


    url: str


class Issue(BaseModel):


    key: str                 # rule id from Appendix 3, e.g. "blunder_rate"


    headline: str            # short, direct: "Blunders are your rating cap"


    diagnosis: str           # MUST contain the player's numbers


    prescription: str        # MUST be concrete and sized (counts, days, links)


    links: list[Link]


    evidence: list[EvidenceRef]          # 1–3 items, never empty


class Strength(BaseModel):


    headline: str


    detail: str              # with the number that earns it


class OpeningRec(BaseModel):


    color: Literal["white","black"]


    name: str                # "Caro-Kann Defence"


    eco_family: str          # "B10–B19"


    why: str                 # interpolates playstyle evidence


    study_link: Link


    already_plays: bool      # flips copy to deepen-don't-switch


class Playstyle(BaseModel):


    label: Literal["tactical","positional","balanced"]


    score: float             # [-1, +1]


    explanation: str         # cites the two strongest components with numbers


    components: dict[str, float]         # raw normalized components (debug/UI)


class PhaseStats(BaseModel):


    opening: float; middlegame: float; endgame: float   # ACPL per phase


class WLD(BaseModel):                  # win/loss/draw tally (2026-07-25 amendment)


    win: int; loss: int; draw: int


class ColorStats(BaseModel):          # per-color weakness breakdown (2026-07-25 amendment)


    games: int


    results: WLD                      # {win, loss, draw} for this color


    blunders_per_game: float


    acpl_overall: float | None        # None = no non-skipped moves of this color


    acpl_by_phase: PhaseStats


    worst_phase: Literal["opening","middlegame","endgame"] | None


    opening_leak_rate: float


    endgame_conversion: float | None  # None = no qualifying games of this color


    low_signal: bool                  # < 4 games of this color → coach copy must hedge


class StatsBlock(BaseModel):


    blunders_per_game: float


    mistakes_per_game: float


    acpl_overall: float


    acpl_by_phase: PhaseStats


    endgame_conversion: float | None     # None = no qualifying games (say so in UI)


    accuracy_trend: Literal["improving","flat","declining","insufficient_data"]


    per_game_acpl: list[float]           # chronological, for any future sparkline


    by_color: dict[str, ColorStats] | None   # keys "white"/"black" (2026-07-25 amendment); only
                                             # colors actually played appear; None = not computed.
                                             # Surfaces a real white-vs-black gap as a first-class
                                             # weakness instead of averaging it away.


class Delta(BaseModel):


    metric: str              # "blunders_per_game", "acpl_overall", ...


    previous: float


    current: float


    direction: Literal["better","worse","flat"]   # sign-aware (lower ACPL = better)


class Progress(BaseModel):


    vs_previous: list[Delta]


    vs_first: list[Delta]


    previous_report_at: datetime


    note: str | None         # low-signal honesty copy when game overlap is high


class PlayerSummary(BaseModel):


    platform: Literal["chesscom","lichess"]


    username: str


    rating: int | None


    games_analyzed: int


    date_range: str          # "Jun 28 – Jul 18"


    time_class_mix: str      # "14 blitz · 6 rapid"


class Report(BaseModel):


    schema_version: int = 1


    player_summary: PlayerSummary


    playstyle: Playstyle


    strengths: list[Strength]            # exactly 1 in v1


    issues: list[Issue]                  # 1–3, priority-ordered


    opening_recs: list[OpeningRec]       # exactly 2 (white, black)


    stats_block: StatsBlock


    progress: Progress | None


    generated_at: datetime


    engine_depth: int


________________


APPENDIX 3 — The Rule Engine (implemented verbatim in coach.py)
Each rule: key · fires when · priority (lower = more important). {braces} interpolate from PlayerFeatures. No rule, threshold, or copy exists in code that isn't in this table; tuning happens here first, then code, then golden re-approval (S17).


key
	fires when
	pri
	blunder_rate
	blunders/game > 1.5
	1
	hung_pieces
	detector 1 fired
	2
	opening_leak
	detector 3 fired
	3
	endgame_conversion
	conversion is not None and < 0.60
	4
	late_collapse
	detector 2 fired
	5
	blitz_gap
	detector 5 fired
	6
	opening_general
	opening_leak_rate ≥ 0.35 AND opening_leak did not fire
	7
	overextension
	detector 4 fired
	8
	

Copy templates (structural shapes — full strings live in code, matching these exactly in structure):


* blunder_rate — H: "Blunders are your rating cap." D: "You averaged {bpg} blunders per game across {n} games — at {rating}, that's the difference-maker; {pct_late}% came after move 25." P: severity-sized — bpg 1.5–2.5 → "20 puzzles a day for 30 days"; > 2.5 → "40 a day, and before every move ask one question: what did their last move threaten?" Links: Lichess puzzle themes matching the player's worst phase. Evidence: the 3 worst blunders.
* hung_pieces — H: "Free pieces are walking away." D: "{hang_pct}% of your blunders left a piece where it could simply be taken — like {example_move} against {example_opp} ({example_detail})." P: board-vision drill — before moving, scan every undefended piece of yours; puzzle theme "hanging pieces."
* opening_leak — H: "Your {family_name} is leaking." D: "You reached move 15 of your {family_name} games down an average of {avg_cp} centipawns across {k} games — you're losing these games before they start." P: "Learn ONE reply properly: {concrete_line_from_openings_json}." Link: the family's Lichess study/explorer.
* endgame_conversion — H: "Winning positions aren't becoming wins." D: "You reached a winning endgame in {q} games and converted {conv_pct}%." P: king+pawn fundamentals; Lichess Practice endgame drills; 15 min × 2/week.
* late_collapse — H: "Your games are decided after move 30 — against you." D: "Past move 30 you blunder {late_ratio}× as often as before it." P: the 5-second blunder-check habit + clock framing (keep 25% of your clock for the last 15 moves).
* blitz_gap — H: "You don't have a chess problem — you have a blitz problem." D: "{blitz_bpg} blunders/game in blitz vs {rapid_bpg} in rapid." P: shift the ratio toward rapid for a month; blitz is testing, rapid is training.
* opening_general — the softer variant when no single family is guilty: D cites {leak_rate}% of games worse by move 20; P: opening principles (development, king safety) — not lines — with one link.
* overextension — hedged (low-confidence detector): "There are signs you push pawns past their support — in {k} spots a big advance preceded a slide within 3 moves…" P: before any pawn push past the 5th, ask who guards the square it leaves behind?


§S Strength selection (exactly one): best phase by ACPL margin → "Your {phase} is genuinely solid — {acpl} average loss, better than your other phases by {margin}"; else conversion ≥ 0.75 → the closer strength; else trend improving → the trajectory strength; else lowest-blunder time class. Never omit; never fake a number.


Banned-phrase list (S17 grep-test): "study tactics", "practice more", "improve your endgame", "work on openings" — each banned unless a digit appears within the same sentence.


________________


APPENDIX 4 — openings.json (founder-approved in P0-4, committed in S16)
Shape per entry: {bucket, color, name, eco_family, line, why_template, study_url}. The twelve mappings:


bucket
	color
	recommendation (eco family)
	tactical
	white
	Italian Game, aggressive lines incl. Evans (C50–C54)
	tactical
	white (alt)
	Scotch Game (C44–C45)
	positional
	white
	London System (D02)
	positional
	white (alt)
	Colle / quiet queen's-pawn structures (D04–D05)
	balanced
	white
	Italian Game, quiet lines (C50)
	balanced
	white (alt)
	Queen's Gambit intro (D06+)
	tactical
	black
	Scandinavian (B01) vs e4 — sharp but learnable sub-1800 (honest caveat over the Sicilian: theory load)
	tactical
	black (alt)
	King's Indian setups (E60+) vs d4
	positional
	black
	Caro-Kann (B10–B19) vs e4
	positional
	black (alt)
	Slav (D10+) vs d4
	balanced
	black
	1...e5 classical (C20+) vs e4
	balanced
	black (alt)
	Queen's Gambit Declined (D30+) vs d4
	

Rules (in openings.py): pick the primary entry for the bucket; surface the alt only when already_plays matches the primary. why_template interpolates two playstyle components. Deepen-don't-switch copy when already_plays: "You already play the {name} — and it fits you. Don't switch; go one level deeper: {line}." Every study_url is a free Lichess study/explorer link, verified live in S16.


________________


APPENDIX 5 — The Playstyle Formula (implemented verbatim in playstyle.py)
Five components, each mapped to [−1, +1] via fixed bounds (no population z-scores — we have no population; fixed bounds keep the score stable and explainable). Per component: clamp(raw, lo, hi) then linear-rescale so lo → −1 and hi → +1.


component
	raw metric
	bounds (lo → hi)
	weight
	capture_density
	captures by player ÷ player moves
	0.15 → 0.40
	0.25
	game_length
	mean plies, inverted (shorter = tactical)
	90 → 40
	0.15
	eval_volatility
	stddev of player-POV eval across all plies
	60 → 250
	0.25
	opposite_castling
	share of games castled opposite sides
	0.00 → 0.30
	0.20
	queen_keep
	share of games where queens survived past ply 30
	0.35 → 0.75
	0.15
	

score = Σ weight × normalized · label: ≤ −0.25 positional · ≥ +0.25 tactical · else balanced. The explanation cites the two components with the largest |normalized| values, with their raw numbers. Bounds are founder-tunable here first (S14 verdict loop), then code, then tests.


________________


APPENDIX 6 — CLAUDE.md starter template (keep under ~60 lines)
# Chessania — standing instructions for AI sessions


One-liner: free "poor man's chess coach" website — type your


Chess.com/Lichess username, get a personalized coaching report from


Stockfish analysis of your last 20 games. Sub-1800 players only.


Strategy: PRD.md. Execution: CHESSANIA_ROADMAP.md (work ONE session


at a time). Live log: STATE.md.


## Stack


Next.js + Tailwind (frontend, Vercel) · FastAPI Python 3.12 (backend,


Railway) · python-chess + Stockfish binary · Postgres prod / SQLite


dev · SQLAlchemy + Alembic.


## Cardinal rules (full versions: roadmap Part A)


1. Show the plan (goal + file list) and WAIT for approval before


   creating or editing any file.


2. Plain language — the founder is learning to code. Explain errors


   before fixing them.


3. Schema = roadmap Appendix 1. Report contract = Appendix 2. Rule


   engine = Appendix 3. Openings = Appendix 4. Playstyle = Appendix 5.


   These are law — tune the appendix first, then the code.


4. NEVER build the Part G Do-Not-Build list: PGN upload, accounts,


   LLM phrasing, ML, chessboard renderer, puzzles, chat, Celery/Redis,


   2000+ features. Not even stubs.


5. Locked: username-only input · no auth · no questionnaire ·


   rule-based coach · depth 12 (ceiling 14) · 20 games · BackgroundTasks.


6. Tests run OFFLINE: fixtures for HTTP (respx) and evals


   (FixtureEvaluator). Needing network/engine in a unit test = wrong test.


7. Every stored eval is WHITE-POV; mover conversion happens only in


   cp_loss(). Every coaching string must contain the player's numbers.


8. One vertical slice per session; founder verifies with real commands;


   update STATE.md (honesty tags: founder-verified / AI-verified /


   unverified) before ending ANY session that changed code.


## Commands


cd backend && source venv/bin/activate && uvicorn app.main:app --reload


pytest                     # offline suite (fast)


pytest -m engine           # real-Stockfish tests (opt-in)


cd frontend && npm run dev


## Key paths


app/config.py (all tunables) · app/engine_eval.py (Evaluator seam) ·


app/coach.py + app/data/openings.json · tests/fixtures/ · alembic/


________________


APPENDIX 7 — STATE.md starter template
# Chessania — live state & decisions


## OPEN QUESTIONS (keep at top)


- [ ] Production depth: hold 12 or drop to 11 for Railway speed? (S24)


- [ ] Report retention: keep all reports forever, or cap per player? (beta)


## DECISION LOG


- 2026-07: Input = username auto-pull only; no upload, no OAuth (Locked 1)


- 2026-07: No accounts; identity = (platform, username) (Locked 2)


- ____-__: S17 report-quality gate → ____


- ____-__: S23 pre-deploy gate → ____


## FIXTURE REGISTRY (P0-1)


- founder: (platform, username) = ________


- low-rated: ________   mid-rated: ________


## GROUND TRUTH (P0-3)


- game 1 (url): human-flagged bad moves = __, __ · worst phase = __


- game 2: ...   game 3: ...


- S9 calibration verdict: ________   S13 detector verdict: ________


## SESSION CHECKLIST


Phase 0:  [ ] P0-1  [ ] P0-2  [ ] P0-3  [ ] P0-4


Phase 1:  [ ] S1 [ ] S2 [ ] S3 [ ] S4 [ ] S5 [ ] S6 [ ] S7


Phase 2:  [ ] S8 [ ] S9 [ ] S10 [ ] S11 [ ] S12 [ ] S13 [ ] S14 [ ] S15 [ ] S16 [ ] S17


Phase 3:  [ ] S18 [ ] S19 [ ] S20 [ ] S21 [ ] S22


Phase 4:  [ ] S23 [ ] S24 [ ] S25 [ ] weekly beta ×4–6


## SESSION LOG (newest first; honesty tags mandatory)


### YYYY-MM-DD · Session N · <title>


- Changed: <files>


- Claims: <thing> [founder-verified | AI-verified | unverified]


- Open bugs: ...


- Next step: <exact resumption point>


## WEEKLY BETA METRICS SQL (filled in S26)


## PARKING LOT (wants that appeared mid-session — logged, not built)


________________


APPENDIX 8 — Session prompt templates (copy-paste these)
Session start:


You're working on Chessania. Read CLAUDE.md, then STATE.md, then Session N in CHESSANIA_ROADMAP.md (and only that session). Restate the session goal in 2–3 plain sentences, list every file you plan to create or change with a one-line reason each, name which appendices this session is bound by, flag anything you're tempted to build that touches Part G, then STOP and wait for my approval before writing anything.


On any error:


Here's the full error output: [paste everything]. Before proposing any fix: explain in plain language what this error means and why it happened.


Session end:


The Definition of Done items look met. Walk me through verifying each one myself with real commands, step by step. Then give me the exact git commands and a clear commit message. Then dictate the STATE.md session entry — with honest verification tags — and any new open questions or parking-lot items.


Copy/threshold tuning (the Appendix 3 loop):


I want to change [rule/threshold/copy]. Show me the current Appendix 3 entry, the proposed new entry, and which golden files will change, then wait for my approval. Then update appendix → code → goldens together, in that order.


________________


APPENDIX 9 — External APIs, money & accounts
Chess.com public API (no key, no auth)
* Archives list: GET https://api.chess.com/pub/player/{username}/games/archives → {"archives":[url,...]} (chronological; walk from the end).
* One month: GET .../games/{YYYY}/{MM} → {"games":[...]}; per game: url (= our platform_game_id), pgn, time_class (bullet|blitz|rapid|daily), rules (keep only chess), end_time (unix), white/black: {username, rating, result}.
* Result mapping: win → win · agreed|repetition|stalemate|insufficient|50move|timevsinsufficient → draw · everything else (checkmated|timeout|resigned|abandoned, etc.) → loss.
* Requires a real User-Agent (Chessania/0.1 (+{CONTACT_EMAIL})) or requests get blocked. Usernames lowercase in URLs. Fetch serially; on 429 raise UpstreamRateLimited (no retry loops).
Lichess public API (no key for public games)
* GET https://lichess.org/api/games/user/{username}?max=20&perfType=blitz,rapid&pgnInJson=true&opening=true&clocks=true with header Accept: application/x-ndjson. (opening=true is required or the opening object is omitted entirely — discovered S6. clocks=true is required or the PGN has no [%clk] stamps — added by the 2026-07-25 amendment so per-move time can be captured on both platforms; Chess.com includes clocks by default.)
* Each line = one JSON game: id, speed, winner (white|black; absent = draw), players.{color}.{user.name, rating}, pgn (with [%clk] when clocks=true), opening.{eco,name}, createdAt (ms).
* On 429: Lichess convention is a full stop for ≥ 60 s — raise, surface friendly copy, do not hammer.
Money & accounts checklist
Item
	Cost
	When
	Notes
	Python / Node / FastAPI / Next.js
	$0
	—
	

	Stockfish
	$0
	S4
	Open-source engine; runs on our own server
	GitHub private repo
	$0
	S2
	

	Chess.com / Lichess APIs
	$0
	S5–S6
	Public data; be a polite client (UA header, serial fetches)
	Vercel (frontend)
	$0 hobby
	S25
	

	Railway (backend + Postgres)
	~$5/mo after trial credit
	S24
	The project's only recurring cost; usage-based
	Domain
	~$12/yr, optional
	whenever
	The free Vercel/Railway URLs are fine for beta
	The real cost
	founder hours
	always
	Copy tuning + beta interviews don't automate
	

________________


APPENDIX 10 — Fixture recording + vibecoding hygiene
The fixture system in one page
Three recorded layers, all committed to the repo, all created once:


1. API fixtures (tests/fixtures/api/) — saved real HTTP responses (P0-2, installed S7), replayed by respx. Trimmed to ≤5 games, stranger usernames scrubbed.
2. PGN fixtures (tests/fixtures/pgn/) — ~6 real games chosen for coverage (miniature, endgame grind, wild tactical, + the 3 ground-truth games).
3. Eval fixtures (tests/fixtures/evals/) — record_fixtures.py output: the real Stockfish's answers for every position in the PGN fixtures, replayed by FixtureEvaluator (S11).


Re-record only deliberately (engine upgrade, depth change): rerun the script, review the diff, expect golden-report diffs, re-approve everything. Record the engine version in STATE.md when you do.
Hygiene (when things go sideways)
1. Paste whole errors, not fragments — the useful line is usually the cropped one.
2. Explain-then-fix, always (Rule 9). Understanding compounds; blind patches don't.
3. The 30-minute rule: stuck past 30 min on one bug → commit any working state, start a fresh AI session, describe the problem from scratch. Fresh context regularly beats a long polluted one.
4. Git is the undo button: git status → git diff to see what changed; git checkout -- <file> discards a bad file; a committed working state means nothing is ever truly broken.
5. Isolate the layer: DB weirdness → query it raw (sqlite3 locally / Railway's data tab). Pipeline weirdness → run one game through one function in a REPL with the FixtureEvaluator. API weirdness → curl the endpoint directly. UI weirdness → hard-code a report JSON into the page. Find which layer is lying before touching code.
6. Engine weirdness → run the S4 smoke script first; if it fails, the problem is the install/path, not your pipeline.
7. A hung port (address already in use) → a previous uvicorn survived; find and kill it (lsof -i :8000), don't change ports and forget why.
8. Beware helpful scope creep — the AI's and your own. "While we're in here…" is how MVPs die. Parking-lot it (STATE.md), stay on the session.
9. When the AI seems confused about the project, it lost context: point it back to CLAUDE.md + STATE.md + the current session. That reset is cheap and usually total.


________________




End of roadmap v1.0 — maintained alongside PRD.md and STATE.md. When reality and this document disagree, update the document; it only works if it stays true.