# Tasks – from v0.1 to production-ready
Each task: tests first → implement → `make verify` → commit → update MEMORY.md.

## Phase 0 – Quality tooling
- [ ] TASK-001 pyproject.toml with ruff + mypy --strict + pytest-cov config, a Makefile, pre-commit
- [ ] TASK-002 CI workflow `ci.yml`: verify + offline end-to-end run on every push/PR; pip-audit; Dependabot
- [ ] TASK-003 Fix all ruff/mypy findings in the existing code (no behaviour change, tests stay green)

## Phase 1 – Harden the core
- [ ] TASK-004 pydantic models for Config, Poem and LanguageSpec; fail fast on a bad config.yaml
- [ ] TASK-005 Child-safety text filter (blocklist + rules), 100% tested with 200+ phrases in multiple languages
- [ ] TASK-006 Mocked integration tests for Gemini (200/429/500/bad JSON), edge-tts, Pollinations, YouTube (5xx, quota, 403)
- [ ] TASK-007 History is written only after a successful upload (atomic write), with a test

## Phase 2 – Media quality gate
- [ ] TASK-008 `qa.py`: ffprobe checks (duration, streams, resolution, Short ≤ 60 s), no silent audio, EBU R128 loudness
- [ ] TASK-009 Loudness normalisation (ffmpeg loudnorm to −16 LUFS)
- [ ] TASK-010 Glyph-coverage check per language using fontTools, plus a parametrised test for every configured language
- [ ] TASK-011 Golden ASS snapshot tests + a lyric-sync check (each line starts within ±0.1 s of its voice clip)

## Phase 3 – Reliability
- [ ] TASK-012 Structured JSON logs + a run summary (per language: ok/skip/error + reason) posted as a GitHub Actions job summary
- [ ] TASK-013 Failure notification (free): open a GitHub Issue automatically when a run has errors
- [ ] TASK-014 Post-upload verification: read the video via the API and assert madeForKids / synthetic / privacy
- [ ] TASK-015 Quota planner: never start uploads that exceed the remaining daily quota

## Phase 4 – Go live
- [ ] TASK-016 Weekly online canary workflow (`--no-upload`)
- [ ] TASK-017 14-day review period (TEST_PLAN.md) → apply for the YouTube API audit → consider review_mode: false

## Extra – Looks
- [x] TASK-PB Picture-book look (`look: picturebook`): crayon-on-paper pages, line boil, calm drift, page turns, handwritten karaoke, tests
