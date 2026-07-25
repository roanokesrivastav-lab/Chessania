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

## Stockfish (needed from Session 4 on)

- macOS: `brew install stockfish`
- Debian/Ubuntu: `sudo apt install stockfish`
- Or the official binary from stockfishchess.org

Set its path in `backend/.env` as `SF_PATH` (wired up in Session 3/4).

## Status

Session 1 complete — both apps scaffolded and verified. See `STATE.md` for the
session log and what's next.
