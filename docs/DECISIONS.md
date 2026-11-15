# Decisions
- ADR-001 ₹0 stack: Gemini free, edge-tts, Pollinations, FFmpeg, GitHub Actions, YouTube Data API.
- ADR-002 ASS subtitles through libass (HarfBuzz shaping), so every script renders correctly, including RTL and complex scripts.
- ADR-003 Native rewrite per language instead of translation, so the rhymes survive. The line count is fixed so pictures stay in sync.
- ADR-004 One channel per language, because the algorithm groups audiences by language.
- ADR-005 Private-by-default uploads with human review, until the YouTube API audit and 14 clean days.
- ADR-006 Fallback at every stage: the pipeline always produces something valid, or skips cleanly.
- ADR-007 Picture-book look is a free, offline post-process (Pillow + numpy + FFmpeg), not an agent-made film per video. Techniques follow the MIT-licensed lemo-opuscar crayon-book style guide; no code or assets copied. Handwriting font: Patrick Hand (OFL) in assets/handfont.
