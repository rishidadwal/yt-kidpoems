# Architecture
```
GitHub Actions (cron 07:00 IST)
  └─ src/pipeline.py (orchestrator)
       ├─ poem.py      Gemini free API → validate (pydantic) → safety filter   | fallback: public-domain rhymes
       ├─ tts.py       edge-tts per line → ffprobe durations                  | retry ×4, then skip language
       ├─ visuals.py   Pollinations image per verse (16:9 + 9:16)             | fallback: offline Pillow scene
       ├─ video.py     FFmpeg: zoompan + ASS karaoke (libass/HarfBuzz) + music mix → mp4
       ├─ qa.py        quality gate (duration, loudness, glyph coverage, sync, safety)   ← TO BUILD
       ├─ upload.py    YouTube Data API v3, resumable, per-language OAuth token
       └─ data/history.json  (committed back by the workflow)
```
## Rules
- Each module does one job. Only `upload.py` talks to YouTube. Only `poem.py` talks to the LLM.
- Every external call has a timeout, retries with backoff, and a fallback or a clean skip.
- **One language failing never stops the others.** One poem failing never stops the run.
- Pure logic (validation, ASS building, timing, quota maths) is separated from I/O so it can be unit-tested.
- Config lives in `config.yaml`, secrets in environment variables only.
- Fonts come from system Noto packages. A font is chosen by fontconfig language match, never by guessing.
