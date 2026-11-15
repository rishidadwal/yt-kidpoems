# Security & Safety
- Secrets (GEMINI_API_KEY, YT_CLIENT_ID/SECRET, YT_*_REFRESH_TOKEN) live only in GitHub Actions Secrets. Never commit `client_secret.json` (it's in .gitignore).
- Tokens are never logged. The workflow uses least-privilege `permissions: contents: write` only.
- Pin action versions and dependency versions. Run `pip-audit` in CI. Dependabot is on.
- **Child safety:** LLM text passes a blocklist and safety check (violence, fear, brands, real people, adult words, URLs) before any rendering. Prompts force child-safe content, and Pollinations requests use `safe=true`.
- **Legal:** Made for Kids is always true, synthetic media is always disclosed, and only original or public-domain text is used. Music must be royalty-free with a licence noted in `assets/music/LICENSES.md`.
- Check the terms of Gemini, Pollinations and edge-tts for commercial use before you monetize.
