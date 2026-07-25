# Chessania

A free "poor man's chess coach." Type your Chess.com or Lichess username and get a
personalized coaching report built from Stockfish analysis of your last 20 rapid/blitz
games. Aimed at sub-1800 players. No signup, no upload — just a username.

- **Strategy / what & why:** [PRD.md](PRD.md)
- **Execution / how (session-by-session, the plan of record):** [CHESSANIA_ROADMAP.md](CHESSANIA_ROADMAP.md)
- **Standing AI instructions:** [CLAUDE.md](CLAUDE.md)
- **Live state & honesty log:** [STATE.md](STATE.md)

> Work **one roadmap session at a time.** Read `CLAUDE.md` + `STATE.md` + the named
> session, plan, get approval, build the slice, verify with real commands, commit.

## Repo layout

```
backend/    FastAPI (Python 3.12), python-chess + Stockfish, SQLAlchemy + Alembic
frontend/   Next.js (App Router) + Tailwind
```

## Local dev

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload       # http://localhost:8000
curl localhost:8000/health          # {"status":"ok"}
pytest                              # offline unit suite
```

### Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

## Stockfish

Chess.com/Lichess evaluations are computed locally by a real Stockfish binary — install
one before running anything in `app/analysis.py` or `scripts/engine_hello.py`:

- **macOS:** `brew install stockfish` → binary lands at `/opt/homebrew/bin/stockfish`
  (Apple Silicon) or `/usr/local/bin/stockfish` (Intel)
- **Debian/Ubuntu:** `sudo apt install stockfish` → `/usr/games/stockfish`
- **Windows / other:** download the official binary from
  [stockfishchess.org](https://stockfishchess.org/download/) and note its path

Copy `backend/.env.example` to `backend/.env` and set `SF_PATH` to whatever `which
stockfish` (or the equivalent) printed for you. Then sanity-check the install:

```bash
cd backend && source venv/bin/activate
python scripts/engine_hello.py
```

Expect a small centipawn edge for White in the starting position, and a mate score
(`Qh4#` found instantly) in the second position — that's Fool's Mate, the fastest
checkmate in chess, used here because an engine that can't spot it in an instant isn't
installed correctly.

## Status

Session 4 complete (engine smoke test verified) — see `STATE.md` for the full session
log and what's next.
