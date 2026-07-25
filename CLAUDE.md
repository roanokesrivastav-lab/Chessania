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
