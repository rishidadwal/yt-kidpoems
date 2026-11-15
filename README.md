> 👉 Building/hardening with an AI agent? Start with **AGENT_PROMPT.md**. **Deploying? → docs/DEPLOYMENT.md** · **Singing + animation → docs/LEVEL2_SETUP.md** · **Auto-publish daily → docs/AUTO_PUBLISH.md** · **Dance mode + compilations → docs/DANCE_MODE.md** (docs/ holds PRD, architecture, testing, tasks).

# KidPoems – Fully Automated, ₹0 Kids' Poem Channel Pipeline

Every day it runs on its own (free GitHub Actions):
**topic → AI writes an original poem → re-written natively in every language → free neural voice → AI pictures → video with karaoke lyrics + Short → uploaded to YouTube as "Made for Kids".**

| Step | Free tool |
|---|---|
| Poem writing & translation | Google **Gemini API free tier** (fallback: built-in public-domain rhymes) |
| Voice | **edge-tts** (Microsoft neural voices, 70+ languages) |
| Pictures | **Pollinations.ai** free image API (fallback: built-in cartoon backgrounds, offline) |
| Video | **FFmpeg** (zoom animation, karaoke subtitles, music mix) |
| Upload | **YouTube Data API v3** (free quota) |
| Scheduler / server | **GitHub Actions** (free) |

---

## 1. Run it on your computer (10 min)
1. Install **Python 3.12**, **FFmpeg** (Windows: `winget install ffmpeg` · Mac: `brew install ffmpeg`) and Google **Noto fonts** (fonts.google.com/noto → install the scripts you use).
2. Get the code and install the libraries:
```bash
git clone https://github.com/<you>/kidpoems.git && cd kidpoems
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                                   # 7 tests should pass
```
3. Get a free Gemini key at **aistudio.google.com → Get API key**.
4. Make a test video without uploading:
```bash
export GEMINI_API_KEY=xxxx          # Windows PowerShell: $env:GEMINI_API_KEY="xxxx"
python -m src.pipeline --no-upload
```
The videos appear in `output/<date>-<title>/<lang>/video.mp4`, along with `short.mp4` and `thumb.jpg`.
Test mode with no AI (uses the built-in rhymes and pictures): `python -m src.pipeline --offline --no-upload`

## 2. Connect YouTube (once per channel)
1. Create **one channel per language** (for example "KidPoems English" and "KidPoems हिंदी"). In YouTube Studio → Settings → Channel → Advanced, set the audience to **Yes, it's made for kids**.
2. In **console.cloud.google.com**:
   - Create a new project.
   - Enable **YouTube Data API v3**.
   - Set up the OAuth consent screen: External, and add yourself as a test user.
   - Go to Credentials → **OAuth client ID → Desktop app**, and download it as `client_secret.json`.
3. Run `python get_youtube_token.py`. When the browser opens, pick the channel. Repeat for each channel.
4. ⚠ Uploads from a new, unaudited API project are **locked to private**. That's fine while `review_mode: true` is on. To upload public automatically, apply for the free *YouTube API Services audit* in Google Cloud.

## 3. Make it fully automatic (GitHub Actions)
1. Push this folder to a GitHub repo. A **public** repo gets unlimited free minutes.
2. Go to repo → Settings → Secrets and variables → Actions, and add:
   - `GEMINI_API_KEY`
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - one refresh token per channel: `YT_EN_REFRESH_TOKEN`, `YT_HI_REFRESH_TOKEN`, `YT_ES_REFRESH_TOKEN`
3. Go to the Actions tab → **daily-kid-poems** → *Run workflow* to test it. After that it runs every day at 07:00 IST.
4. Each run saves `data/history.json` so topics never repeat. Videos can be downloaded from the run page for 7 days.

## 4. Add more languages (any language, any time)
1. Add a line to `config.yaml → languages` with its voice. `edge-tts --list-voices` shows all of them.
2. Add a channel prefix under `channels:`, plus the secret `YT_<PREFIX>_REFRESH_TOKEN`. Also add that secret to the `env:` block in `.github/workflows/daily.yml`.
3. Examples are already in config.yaml (commented out): Arabic, Bengali, Portuguese, French, Indonesian, Japanese and Tamil.

## 5. Daily routine (5–10 min, keeps the channel safe)
With `review_mode: true`, every video is uploaded **private**. Open YouTube Studio, watch it quickly, and switch it to **Public** or schedule it. This check protects children, catches bad translations or pictures, and keeps you inside YouTube's rules. Only switch `review_mode: false` once the API audit is approved and quality has been consistent for weeks.

## Customise
- `data/topics.txt`: one poem idea per line. Add hundreds; the pipeline works through them in order.
- `assets/music/`: drop royalty-free `.mp3` files here (for example from the YouTube Audio Library). One is picked at random.
- `config.yaml`: art style, voice speed and pitch, music volume, poems per run, and Shorts on or off.
- `look: picturebook` (default) turns every video into a crayon storybook; `look: classic` brings back the glossy 3D cartoon. Details: **docs/PICTUREBOOK.md**.

## ⚠ Rules that keep the channel alive
- **Made for Kids** is set automatically on every upload (a legal requirement for children's content).
- **AI disclosure**: `containsSyntheticMedia` is set to true on every upload.
- **Avoid "repetitive / mass-produced content"**: vary the topics, keep adding new ideas, and review the videos. Channels that upload identical, templated AI videos often get rejected from monetization.
- **Only original or public-domain poems.** Never modern copyrighted songs or poems.
- **Free tiers have limits.** Gemini, Pollinations and edge-tts can rate-limit or change their terms. The pipeline retries and falls back, but check each service's current terms (especially edge-tts for commercial use) before you monetize.
- **API quota**: an upload costs 1,600 of the 10,000 free daily units, so about **6 uploads a day per Google project**. Each language uses 1–2 uploads (video + Short). For more languages, create more free Google Cloud projects.

## Troubleshooting
| Problem | Fix |
|---|---|
| `ffmpeg not found` | Install FFmpeg and reopen the terminal |
| Boxes instead of letters | Install the Noto font for that script (for example Noto Sans Devanagari) |
| `GEMINI_API_KEY not set` / 429 errors | Set the key, or wait. The free tier resets daily. The pipeline falls back to public-domain rhymes. |
| Pictures look plain | Pollinations was busy. The built-in backgrounds were used; the next run retries. |
| Upload `quotaExceeded` | Wait for the daily reset, or split languages across more Google projects |
| Video stays private | Normal until the API audit is approved. Publish it in Studio. |
