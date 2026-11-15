# 🎵 KidPoems – Fully Automated, ₹0 Kids' Song Channel

Every day, with no clicks, GitHub Actions:
**writes an original poem or dance song → rewrites it natively in every language → voices or sings it → makes 3D-cartoon pictures and animations → builds a Full-HD video + Short → uploads to YouTube as "Made for Kids".**
Every Sunday it also joins the week's videos into one long compilation.

| Step | Free tool |
|---|---|
| Lyrics & translation | Google **Gemini API** free tier (fallback: built-in rhymes and chants) |
| Voice | **edge-tts** neural voices, 70+ languages |
| Singing + animation *(Level 2, optional)* | **ACE-Step** + **LTX-Video** + **SDXL** on a free **Kaggle GPU** |
| Pictures *(Level 1)* | **Pollinations.ai** (fallback: built-in drawings) |
| Video | **FFmpeg**: karaoke lyrics, motion, beat effects, music |
| Upload & schedule | **YouTube Data API v3** + **GitHub Actions** |

📚 More guides in `docs/`:
- `LEVEL2_SETUP.md`: singing + animation
- `DANCE_MODE.md`: dance songs + weekly compilation
- `AUTO_PUBLISH.md`: automatic daily posting
- `DEPLOYMENT.md`: the Vercel dashboard

For AI agents: start with `AGENT_PROMPT.md`.

---

# 🚀 Deploy (about 45 minutes the first time)

Deploying means putting the code on GitHub, adding your keys as **Secrets**, and letting **GitHub Actions** run it every day for free.
The commands below are for **Windows PowerShell**. On Mac or Linux, use the notes marked 🍎.

## Step 1 – Install 3 things (one time)
1. **Python 3.12** from python.org. ✔ Tick **"Add Python to PATH"** during install.
2. **Git** from git-scm.com.
3. **FFmpeg**: open PowerShell and run `winget install ffmpeg`. (🍎 `brew install ffmpeg`)

Close PowerShell, open a new one, and check all three are installed:
```powershell
python --version; git --version; ffmpeg -version
```

## Step 2 – Test on your computer
1. Unzip **kidpoems.zip**, for example to `D:\kidpoems`. Make sure you get `D:\kidpoems\src`, **not** `D:\kidpoems\kidpoems\src`.
2. Get a free Gemini key at **aistudio.google.com → Get API key**. It starts with `AIza…`. Never share it.
3. Set up the project and make a first video, without uploading:
```powershell
cd D:\kidpoems
python -m venv .venv
.venv\Scripts\activate                   # 🍎 source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                      # should say: 22 passed
$env:GEMINI_API_KEY="paste-your-key"     # 🍎 export GEMINI_API_KEY="..."
python -m src.pipeline --no-upload
```
4. Open `output\...\en\video.mp4` and watch it. Check the `hi` and `es` folders too.
   - If Hindi letters show as boxes, install **Noto Sans Devanagari** from fonts.google.com/noto. On GitHub Actions the fonts install automatically.
   - Test without any internet or AI: `python -m src.pipeline --offline --no-upload`

## Step 3 – Create the YouTube channels
1. Go to youtube.com → profile → **Create a channel**. Make **one per language**, e.g. "KidPoems English", "KidPoems हिंदी" and "KidPoems Español". Tip: use **Settings → Add or manage channels** to create extra channels under the same Google account.
2. For each channel: **YouTube Studio → Settings → Channel → Advanced settings → Audience: "Yes, it's made for kids"**.
3. Verify your phone at **youtube.com/verify** so custom thumbnails work.

## Step 4 – Get the YouTube keys
1. In **console.cloud.google.com**, create a new project called **kidpoems**.
2. Go to **APIs & Services → Library**, search **YouTube Data API v3** and click **Enable**.
3. Set up the **OAuth consent screen**:
   - choose **External**
   - give the app a name and your email
   - under **Test users**, add your Gmail
4. Create the credentials:
   - go to **Credentials → Create credentials → OAuth client ID → Desktop app**
   - click **Download JSON**, rename it to **`client_secret.json`** and put it in `D:\kidpoems`
5. Run this **once per channel**:
```powershell
python get_youtube_token.py
```
   The browser opens. Choose the channel (English first), then allow access. It prints `YT_CLIENT_ID`, `YT_CLIENT_SECRET` and a **refresh token**.
6. Save the values in Notepad: the first run's token is `YT_EN_REFRESH_TOKEN`, then run it again for `YT_HI_REFRESH_TOKEN` and `YT_ES_REFRESH_TOKEN`.

> ⚠ While the consent screen is in **"Testing"** mode, refresh tokens **expire after 7 days**. To stop that, go to **OAuth consent screen → Publish app** and set it to **"In production"**. You'll see an "unverified app" warning, but it's fine for your own account. Then create the tokens again.

## Step 5 – Put the code on GitHub
1. Go to github.com → **New repository** → name it `kidpoems` → choose **Public** (unlimited free minutes) → **Create**.
2. In PowerShell:
```powershell
cd D:\kidpoems
git init
git branch -M main
git add .
git status          # make sure client_secret.json is NOT listed
git commit -m "first version"
git remote add origin https://github.com/YOUR-USERNAME/kidpoems.git
git push -u origin main
```
If it asks for a password, use a **token** from GitHub → Settings → Developer settings → Personal access tokens.

> Your keys and `client_secret.json` are ignored by `.gitignore` and never uploaded. That's why a public repo is safe.

## Step 6 – Add your secrets on GitHub
Go to repo → **Settings → Secrets and variables → Actions → Repository secrets → New repository secret**, and add each one. Use exact names, and no quotes or spaces in the values.

| Name | Value | Needed for |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini key | Lyrics + translation |
| `YT_CLIENT_ID` | From Step 4 | Uploads |
| `YT_CLIENT_SECRET` | From Step 4 | Uploads |
| `YT_EN_REFRESH_TOKEN` | English channel token | English uploads |
| `YT_HI_REFRESH_TOKEN` | Hindi channel token | Hindi uploads |
| `YT_ES_REFRESH_TOKEN` | Spanish channel token | Spanish uploads |
| `KAGGLE_USERNAME` | From kaggle.json *(optional)* | Level 2 singing + animation |
| `KAGGLE_KEY` | From kaggle.json *(optional)* | Level 2 singing + animation |

Then go to **Settings → Actions → General → Workflow permissions** and choose **Read and write**. This lets the workflow save its topic history and the video archive used for compilations.

## Step 7 – First live run
1. Go to repo → **Actions** tab. If asked, click **"I understand, enable workflows"**.
2. Click **daily-kid-poems → Run workflow → upload = yes**. It takes about **10–20 minutes**, or **40–150 minutes** with Level 2 on Kaggle.
3. In the log, **Check secrets** should show ✅ for each secret, and **Make & upload** should show `[uploaded] en video https://youtu.be/...`.
4. A green ✔ means it worked. Open **YouTube Studio → Content**: new **private** videos should be on each channel.
5. Watch them. If they're good, set each one to **Public**, or schedule it.

From now on it runs **every day at 7:00 AM IST** by itself. Your only job is about **5–10 minutes a day** reviewing and publishing in YouTube Studio. To post automatically instead, see `docs/AUTO_PUBLISH.md`.

## The three automatic jobs
| Workflow | When | What it does |
|---|---|---|
| **daily-kid-poems** | Every day, 7:00 AM IST | New video + Short per language. Alternates poem and dance song. Archives each video. |
| **weekly-compilation** | Sundays, 8:00 AM IST | Joins the last 7 videos per language into one long video (needs 3+ archived videos) |
| **ci** | Every `git push` | Runs lint + tests only |

---

## If something goes wrong
| Problem | Fix |
|---|---|
| Red ✖ in Actions | Click the run and read the red step. Copy the lines starting with `[` (they contain no secrets) and paste them to your helper or agent. |
| `GEMINI_API_KEY not set` / `no YouTube token` | A secret is missing or misnamed. It must be a **Repository** secret with the exact name from Step 6. |
| `invalid_grant` | The refresh token expired. Publish the consent screen (Step 4), then create the token again. |
| `quotaExceeded` | You hit the free daily upload limit (about 6 uploads per Google project). Wait until tomorrow. |
| Videos stay private | Normal. New API projects can only upload private until Google's free audit approves them (see `docs/AUTO_PUBLISH.md`). |
| A language is missing | Check the run log for `[error] hi: ...`. The other languages still upload. |
| `JSONDecodeError` on history.json | A git conflict broke the file. The pipeline now repairs this automatically; run `git pull` before editing. |
| Weekly compilation says `[skip] only 1 archived videos` | Normal at the start. It needs 3+ uploaded videos per language. |
| `[gpu] Kaggle not configured` | Level 2 is off. Add `KAGGLE_USERNAME` and `KAGGLE_KEY`, and verify your phone on Kaggle. |

## To change things later
**Always run `git pull` first**: the robot updates the repo after every run.
- **More poem topics:** edit `data/topics.txt`. **More dance ideas:** edit `data/dance_topics.txt`.
- **Poem, dance or both:** `content_mode:` in `config.yaml` (`poem`, `dance` or `alternate`).
- **Characters and art style:** `cast:` and `art_style:` in `config.yaml`.
- **More languages:** edit `config.yaml`, create a channel, add its token secret, and add a line in both `.github/workflows/daily.yml` and `weekly-compilation.yml`.
- **Save your changes to GitHub:**
```powershell
git pull ; git add . ; git commit -m "update" ; git push
```

## ⚠ Rules that keep the channel alive
- **Made for Kids** and **AI disclosure** (`containsSyntheticMedia`) are set on every upload. Never remove them.
- **Only original or public-domain songs.** Never copy other channels' songs, hooks or characters.
- **Review videos before they go public**, especially at the start. YouTube demonetizes repetitive, low-quality AI content.
- **Free tiers have limits.** Check the terms of Gemini, Pollinations, edge-tts and Kaggle before you monetize.
