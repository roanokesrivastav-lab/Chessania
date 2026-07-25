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
