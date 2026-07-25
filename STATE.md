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
Phase 1:  [x] S1 [x] S2 [x] S3 [x] S4 [x] S5 [x] S6 [x] S7  🏁 Phase 1 exit reached
Phase 2:  [ ] S8 [ ] S9 [ ] S10 [ ] S11 [ ] S12 [ ] S13 [ ] S14 [ ] S15 [ ] S16 [ ] S17
Phase 3:  [ ] S18 [ ] S19 [ ] S20 [ ] S21 [ ] S22
Phase 4:  [ ] S23 [ ] S24 [ ] S25 [ ] weekly beta ×4–6

## SESSION LOG (newest first; honesty tags mandatory)

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
