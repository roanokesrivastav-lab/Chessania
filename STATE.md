# Chessania — live state & decisions

## OPEN QUESTIONS (keep at top)

- [ ] Production depth: hold 12 or drop to 11 for Railway speed? (S24)
- [ ] Report retention: keep all reports forever, or cap per player? (beta)

## DECISION LOG

- 2026-07: Input = username auto-pull only; no upload, no OAuth (Locked 1)
- 2026-07: No accounts; identity = (platform, username) (Locked 2)
- 2026-07-24: Clean rebuild — removed pre-roadmap MVP (PGN upload / questionnaire /
  localStorage) that violated Locked 1–3; scaffolded roadmap A6 layout; ran Session 1.
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
Phase 1:  [x] S1 [ ] S2 [ ] S3 [ ] S4 [ ] S5 [ ] S6 [ ] S7
Phase 2:  [ ] S8 [ ] S9 [ ] S10 [ ] S11 [ ] S12 [ ] S13 [ ] S14 [ ] S15 [ ] S16 [ ] S17
Phase 3:  [ ] S18 [ ] S19 [ ] S20 [ ] S21 [ ] S22
Phase 4:  [ ] S23 [ ] S24 [ ] S25 [ ] weekly beta ×4–6

## SESSION LOG (newest first; honesty tags mandatory)

### 2026-07-24 · Session 1 · Machine setup + "Hello, both apps"

- Changed: repo cleaned to roadmap A6 layout; added PRD.md, CHESSANIA_ROADMAP.md,
  CLAUDE.md, STATE.md; backend/app/main.py (GET /health), backend/requirements.txt;
  fresh Next.js app in frontend/.
- Claims:
  - `curl localhost:8000/health` returns `{"status":"ok"}` [unverified — founder to run]
  - Next.js dev server hot-reloads a text edit [unverified — founder to run]
  - `pytest` runs (0 tests collected is fine) [unverified — founder to run]
- Open bugs: none
- Next step: Session 2 (git + guardrail docs — largely in place) or Session 3
  (config + full schema migration 001 from Appendix 1).

## WEEKLY BETA METRICS SQL (filled in S26)

## PARKING LOT (wants that appeared mid-session — logged, not built)
