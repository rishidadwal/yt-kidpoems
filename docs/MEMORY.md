# Memory
Status: v0.1 pipeline works end-to-end (offline test passed, 7 unit tests). Hardening tasks start at TASK-001.
Look: `look: picturebook` (default) = crayon pages with 12 fps boil, page turns, handwritten karaoke (src/picturebook.py, tests/test_picturebook.py). Renders ~2x slower than classic; bitrate capped at 8 Mbps.
Known gaps: no qa.py gate yet · no loudness normalisation · safety filter is prompt-only · no glyph-coverage test · no mypy/ruff config · CI doesn't run tests yet.

## 2026-11-15 — deploy + watchability (branch `deploy-new`, NOT merged to main yet)
Deployed to `rishidadwal8065/ty-kidpoems` (made public for free Actions minutes; secrets live there). CI green (45 tests on CI).
Done: Pollinations free limit (1 image / 45 s per IP) now waited out -> 12/12 AI pictures · history save uses the current branch ·
`dance_look: classic` (no crayon filter on dance songs) · hook-first prompts · one star per picture · bolder thumbnail · `six` added.

### NEXT STEPS (owner must do 1-3; they need his Google/Kaggle logins)
1. GEMINI_API_KEY is dead (401). New key: aistudio.google.com -> `gh secret set GEMINI_API_KEY -R rishidadwal8065/ty-kidpoems`
2. YT_EN_REFRESH_TOKEN expired (invalid_grant). Google Cloud -> OAuth consent screen -> Publish app (In production),
   put client_secret.json in the project, `python get_youtube_token.py`, then `gh secret set YT_EN_REFRESH_TOKEN -R ...`
3. Kaggle login fails. kaggle.com -> Settings -> API -> new token -> `gh secret set KAGGLE_USERNAME` / `KAGGLE_KEY`
   (unlocks real singing + moving, consistent characters = the biggest quality jump)
4. Then (agent): run daily-kid-poems with upload=yes on deploy-new, watch the video, tune singing/animation.
5. Then (agent, after owner says yes): merge deploy-new -> main so the 07:00 IST cron uses the new code.
Open: "pollinations" watermark in a corner of some pictures · poem (non-dance) mode not re-tested · add well-known
public-domain rhymes (Wheels on the Bus etc.) as song choices - owner has not answered yet.
