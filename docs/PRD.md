# PRD – KidPoems

## Problem
Parents around the world want safe, gentle, educational nursery-rhyme videos in their **own language**. Most channels cover English and a few big languages. Making videos by hand is slow and costly.

## User
- **Viewers:** children aged 2–6 and their parents, worldwide.
- **Operator:** one person (the owner) with **₹0 budget**, spending no more than 10 minutes a day reviewing.

## Goal
A **fully automated, ₹0 pipeline** that produces and uploads one original poem per day in N languages. It must be reliable enough to run unattended for months.

## MVP (v1)
1. Topic queue → original English poem (Gemini free tier) → a native rewrite per language.
2. Neural voice per line (edge-tts) → pictures per verse (Pollinations) → landscape video + vertical Short + thumbnail.
3. Karaoke lyrics that render correctly in every script (Latin, Devanagari, Arabic RTL, CJK, Tamil, Bengali and more).
4. Upload per language channel with **Made for Kids = true** and **synthetic media disclosed**. Uploads are private by default for review.
5. Runs daily on GitHub Actions. History prevents repeats. Every step has a fallback, so the pipeline never produces nothing.
6. **Quality gate** before upload: duration, audio loudness, subtitle glyphs present, no empty lines, child-safety check of the text.

## Out of scope (v1)
Real singing / melody generation · paid APIs · comment moderation · analytics dashboard · multiple poems per language per day beyond the API quota.

## Success criteria
- 30 consecutive daily runs with **0 crashed runs**. Any failure is reported, and other languages still publish.
- 100% of uploads have Made for Kids + AI disclosure set correctly (verified via the API).
- 0 videos with missing glyphs (boxes), silent audio or out-of-sync lyrics (automated checks).
- The operator spends 10 minutes a day or less.
