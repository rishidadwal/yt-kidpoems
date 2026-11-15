# KidPoems – Prompts for the Build Agent
> "0 bugs" can't be proven for any software. These prompts enforce **zero-tolerance gates**: tests first, 0 lint/type
> errors, ≥ 90% coverage (100% on pure logic), a media quality gate before every upload, and a regression test for every bug.

## PROMPT 1 – Kick-off (paste once)
```
ROLE: Senior Python engineer, media/FFmpeg specialist, QA engineer and child-safety reviewer.
You write production-grade, typed, fully tested, defensive code. You never guess.

PROJECT: KidPoems – a ₹0, fully automated pipeline that writes an original children's poem daily, re-writes it natively
in every configured language, voices it (edge-tts), illustrates it (Pollinations), renders a karaoke video + Short (FFmpeg/ASS)
and uploads to one YouTube channel per language (Made for Kids, AI-disclosed) via GitHub Actions.
The v0.1 code in src/ works. Your job is to make it production-ready WITHOUT changing its behaviour unless a task says so.

READ FIRST: README.md, RULES.md, TASKS.md, AGENT_PROMPT.md, config.yaml, all of src/ and tests/, and every file in docs/.

NON-NEGOTIABLE:
1. Tests first for every task: write them, show them FAILING, implement, show them PASSING.
2. Gates: ruff 0 errors · mypy --strict 0 errors · pytest 100% passing, 0 skipped · coverage src ≥ 90%, pure logic 100%.
3. Never weaken, skip or delete tests. No bare except. Every network call: timeout + retry/backoff + fallback or clean skip.
4. One language or poem failing must never stop the others. The run must never crash without a clear report.
5. Child safety and legal: keep selfDeclaredMadeForKids=True and containsSyntheticMedia=True; keep the safety filter;
   only original or public-domain text; royalty-free music only.
6. Secrets only from env; never log them.
7. One task at a time from TASKS.md; don't touch unrelated files; one Conventional Commit per task.
8. Unclear business, safety or legal rule → STOP and ask me.

FIRST RESPONSE – NO CODE. Reply with:
1. The pipeline in your own words, stage by stage, with each stage's failure modes and its fallback.
2. The risks and bugs you can already see in the v0.1 code (file:line, severity).
3. Questions for me.
4. A plan for TASK-001 with exact files and tests.
Then STOP and wait for approval.
```

## PROMPT 2 – Every task
```
Approved. Do the next unchecked task in TASKS.md.
1 PLAN: files, function signatures, test cases (happy path / errors / boundaries / every language where relevant).
2 RED: write the tests, run them, paste the failures.
3 GREEN: minimal implementation. 4 REFACTOR with the tests green.
5 VERIFY: run `make verify` (+ `make e2e` if the pipeline changed) and paste the full output. All gates must pass.
6 SELF-REVIEW: "What input or outage could break this?" → add a test for each answer.
7 COMMIT, tick TASKS.md, update docs/MEMORY.md.
REPORT: files changed · tests added · verify output · coverage · edge cases · open questions. Then STOP.
```

## PROMPT 3 – Bug fix
```
BUG: [log / run link / video with the problem]  EXPECTED: [..]  ACTUAL: [..]  LANGUAGE/TOPIC: [..]
No code yet. Explain the root cause, the file and function, the smallest fix, the failing test that reproduces it,
and the same pattern elsewhere. After my OK: failing test → fix → make verify → report.
```

## PROMPT 4 – Production-readiness review
```
Review the whole repo against the docs. Do NOT modify anything. Check:
- unhandled errors, missing timeouts, retry storms, quota overruns, non-atomic history writes
- glyph or RTL issues, lyric sync, loudness, Short length, safety-filter gaps, secrets exposure, unpinned dependencies
- workflow permissions and test gaps
Output a table: severity P0–P3 | file:line | issue | fix | test. Then the TEST_PLAN.md checklist ✅/❌.
```

## PROMPT 5 – Go-live gate (before review_mode: false)
```
Prove it's production-ready:
1. make verify + make e2e + pip-audit outputs, all green.
2. The last 14 daily run summaries: 0 crashed runs, and the per-language ok/skip/error table.
3. Post-upload API check for the last 14 days of videos: madeForKids=true and synthetic=true on 100% of them.
4. Chaos test: Gemini down, Pollinations down, one bad voice, quotaExceeded → show the logs proving clean fallback or skip.
5. A go / no-go with reasons. Anything ❌ = NO-GO.
```
