# Chessania — live state & decisions

## OPEN QUESTIONS (keep at top)

- [ ] Production depth: hold 12 or drop to 11 for Railway speed? (S24)
- [ ] Report retention: keep all reports forever, or cap per player? (beta)

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
- \_\_\_\_-\_\_: S17 report-quality gate → \_\_\_\_
- \_\_\_\_-\_\_: S23 pre-deploy gate → \_\_\_\_

## FIXTURE REGISTRY (P0-1)

- founder: (platform, username) = \_\_\_\_\_\_\_\_
- low-rated: \_\_\_\_\_\_\_\_   mid-rated: \_\_\_\_\_\_\_\_

## GROUND TRUTH (P0-3)

- game 1 (url): human-flagged bad moves = \_\_, \_\_ · worst phase = \_\_
- game 2: ...   game 3: ...
- S9 calibration verdict: \_\_\_\_\_\_\_\_   S13 detector verdict: \_\_\_\_\_\_\_\_

## SESSION CHECKLIST

Phase 0:  [ ] P0-1  [ ] P0-2  [ ] P0-3  [ ] P0-4
Phase 1:  [x] S1 [ ] S2* [x] S3 [x] S4 [ ] S5 [ ] S6 [ ] S7

  \* S2's docs/.gitignore are in place (folded into the 2026-07-24 rebuild), but the
    repo has not been pushed to origin yet — that DoD item is still open.
Phase 2:  [ ] S8 [ ] S9 [ ] S10 [ ] S11 [ ] S12 [ ] S13 [ ] S14 [ ] S15 [ ] S16 [ ] S17
Phase 3:  [ ] S18 [ ] S19 [ ] S20 [ ] S21 [ ] S22
Phase 4:  [ ] S23 [ ] S24 [ ] S25 [ ] weekly beta ×4–6

## SESSION LOG (newest first; honesty tags mandatory)

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
