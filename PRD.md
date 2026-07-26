# Chessania — Product Brief (PRD)

> **Strategy source.** This brief explains *what* Chessania is and *why*.
> Execution lives in [CHESSANIA_ROADMAP.md](CHESSANIA_ROADMAP.md); live state in [STATE.md](STATE.md).
> Where this brief and the roadmap's **Locked Decisions** (roadmap Part A3) conflict — most notably the
> v1 input method — **the roadmap's locked decisions win.** v1 is username-based auto-pull only:
> no manual PGN upload, no questionnaire, no accounts.

## One-line pitch

A free, accessible "poor man's chess coach" — a website that analyzes your games and gives you a personalized baseline improvement plan, instead of the generic advice you get everywhere else.

## The problem

Most improving chess players (especially sub-1800) can't afford or don't have time for a real coach. Chess.com and Lichess give you raw analysis and generic "top openings" lists, but not a personalized diagnosis of *why* you're stuck at your current rating or *what specifically* to work on next.

## Target user

Players under ~1800. At this level, the bottleneck is usually concrete tactical/positional mistakes (blunders, weak endgames, poor opening fundamentals) — not deep opening prep or calculation depth, which is what matters more at 2000+. Scope is deliberately narrow to this segment for v1.

## Core value prop

Instead of "here are the top 10 openings," Chessania looks at a player's actual games and tells them:

- What they're doing wrong, concretely and backed by their own numbers (e.g. "you hung a piece in 9 of your last 20 games, and 72% of those blunders came with under 45 seconds on your clock") — the recurring pattern shown with evidence plus a testable fix, NOT a confident guess at *why* you chose a move (eval-drops measure what went wrong, not the internal calculation behind it — 2026-07-26 research amendment)
- What opening repertoire actually fits their level and demonstrated playstyle — not a generic list
- Where to go next (specific study resources, puzzle practice, etc.) — Chessania doesn't try to replace tactics trainers or opening courses, it redirects players to the right ones for their specific gaps

## Core pipeline (game analysis)

1. Pull the player's recent games from the Chess.com / Lichess public API (by username)
2. Parse games with python-chess
3. Run Stockfish evaluation on every move
4. Compare best move vs. played move; classify each move as blunder / mistake / inaccuracy based on eval drop
5. Detect patterns across games (e.g. "you hang pieces on defended squares," "you overextend pawns")
6. Feed classified data into a coaching/recommendation layer
7. Generate a structured, human-readable coaching report

## Coaching layer

Rule-based in v1 (no ML, no LLM in the pipeline). Example rules:

- blunders_per_game > 2 → recommend daily tactics (e.g. 20 puzzles/day)
- opening eval drop before move 10 → recommend studying opening fundamentals
- consistently losing endgames → recommend king+pawn endgame study
- opening repertoire suggestion based on player's level *and* demonstrated playstyle (aggressive/tactical vs. positional/quiet), not a generic "top openings" list

Later: evolve the rule-based system into a personalized ML recommender once there's enough usage data to train on (deferred — see roadmap Part G).

## Feature set (v1 scope)

- Username-based auto-pull of recent rapid/blitz games from Chess.com / Lichess
- Stockfish-powered move analysis and blunder/mistake/inaccuracy classification
- Rule-based recommendation engine mapping error patterns to advice
- Personalized opening repertoire suggestions (level + playstyle based)
- Structured coaching report output at a shareable URL
- Progress tracking: blunder rate and accuracy trends over time (basic dashboard)

## Later / explicitly deferred

- Manual PGN upload + OTB games
- ML-based personalized recommendations (start rule-based)
- Support for 2000+ players (deeper engine analysis, opening prep tools, opponent-specific prep) — not a v1 priority; this segment's needs are fundamentally different (strategy/calculation/prep vs. obvious mistakes)

_(Full deferral list with reserved "seats": roadmap Part G.)_

## Tech stack

- **Frontend:** Next.js + Tailwind CSS (Vercel)
- **Backend:** FastAPI, Python 3.12 (Railway)
- **Chess tooling:** python-chess + Stockfish binary
- **Data:** Postgres (prod) / SQLite (dev), SQLAlchemy + Alembic

## Known pitfalls to design around

- **Overengineering too early** — start dumb, improve later. Don't build the ML recommender before the rule-based version proves out.
- **Don't try to out-engine Chess.com/Lichess** — the differentiation is personalization and coaching narrative, not raw analysis depth.
- **Weak/generic recommendations kill retention** — if the advice reads like something a player could've gotten anywhere, they won't come back. The bar is specificity: name the actual pattern, not a category.

## What "success" looks like

Not the tech stack — the insight quality. The tool needs to say something specific *and true* — e.g. "you hung a piece in 9 of your last 20 games, most often in time trouble; here's the one habit to fix it and how to measure the change" — not "You should study tactics." What it must NOT do is guess at the internal *why* (eval-drops measure what went wrong, not how many moves ahead you calculated — see the 2026-07-26 research council, which flagged the old "calculating only one move ahead" phrasing as an unsupportable causal claim). **Specificity — specific and true, never specific and guessed — is the whole product.**
