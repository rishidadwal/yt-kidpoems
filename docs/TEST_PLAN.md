# Test Plan (manual acceptance before switching review_mode off)
- [ ] 14 days of daily runs with 0 crashed runs, and every video watched by a human
- [ ] Each language: correct script, no boxes, the lyrics follow the voice, the rhyme sounds natural (native speaker spot-check)
- [ ] Short is vertical, ≤ 60 s, and appears in the Shorts feed
- [ ] YouTube Studio shows "Made for kids: Yes" and "Altered or synthetic content: Yes" on every upload
- [ ] Gemini key removed → public-domain fallback works · offline images work · one bad voice name → only that language skipped
- [ ] quotaExceeded → the run reports it, and nothing is lost (the history isn't updated for failed uploads)
- [ ] 7 days of history show no repeated topic
