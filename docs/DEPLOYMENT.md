# Deploy: GitHub (code) + GitHub Actions (pipeline) + Vercel (dashboard)

```
GitHub repo ──► GitHub Actions  (runs the pipeline daily 07:00 IST, or on demand)
    ▲                │  writes data/history.json + data/last_run.json back to the repo
    │                ▼
Vercel dashboard ──► GitHub API  (reads status, presses "Run now")
```
Everything is free. The heavy video work runs on **GitHub Actions**; Vercel only hosts the small dashboard.

---
## 1. Install (one time, Windows)
```powershell
winget install Python.Python.3.12 Git.Git Gyan.FFmpeg OpenJS.NodeJS.LTS
npm install -g vercel
```
Close PowerShell, open a new one, and check: `python --version; git --version; ffmpeg -version; node --version`

## 2. Test on your computer
```powershell
cd D:\kidpoems
python -m venv .venv ; .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                              # 7 passed
$env:GEMINI_API_KEY="your-key"                   # free: aistudio.google.com
python -m src.pipeline --no-upload               # videos appear in output\
```

## 3. YouTube keys (one time per channel)
1. Create one channel per language. In **YouTube Studio → Settings → Channel → Advanced**, set the audience to **Made for kids**.
2. In **console.cloud.google.com**:
   - Create a new project.
   - Enable **YouTube Data API v3**.
   - Set up the **OAuth consent screen**: External, add yourself as a test user, then **Publish app** (otherwise tokens expire after 7 days).
   - Go to **Credentials → OAuth client ID → Desktop app**, download it and save it as `client_secret.json` in the project folder.
3. Run `python get_youtube_token.py` once per channel. Save the printed CLIENT_ID, CLIENT_SECRET and each refresh token.

## 4. Put the code on GitHub
1. Go to github.com → **New repository** → name it `kidpoems` → **Public** (unlimited Actions minutes) → Create. Don't add a README.
2. Then run:
```powershell
cd D:\kidpoems
git init ; git branch -M main
git add . ; git status        # client_secret.json and output\ must NOT be listed
git commit -m "feat: kidpoems pipeline + dashboard"
git remote add origin https://github.com/YOUR-USERNAME/kidpoems.git
git push -u origin main
```
If Git asks for a password, use a Personal Access Token (GitHub → Settings → Developer settings → Tokens).

## 5. GitHub Actions (the pipeline)
1. Go to repo → **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `GEMINI_API_KEY`
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_EN_REFRESH_TOKEN`
   - `YT_HI_REFRESH_TOKEN`
   - `YT_ES_REFRESH_TOKEN`
2. Go to repo → **Settings → Actions → General → Workflow permissions** and choose **Read and write** → Save.
3. Test it: go to the **Actions** tab → **daily-kid-poems** → **Run workflow** → upload = `no`. You should see a green ✔ in 10–20 min. Download the videos from the run page (Artifacts).
4. Run it again with upload = `yes`. Private videos appear in YouTube Studio.
5. From now on it runs **every day at 07:00 IST** by itself. The `ci` workflow also runs the tests on every push.

## 6. Deploy the dashboard to Vercel

### 6a. Create a GitHub token for the dashboard
Go to github.com → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate**:
- Repository access: **Only select repositories → kidpoems**
- Permissions:
  - **Actions: Read and write** (to press "Run now")
  - **Contents: Read-only** (to read the status files)
  - **Metadata: Read-only**
- Expiration: 1 year. Copy the token.

### 6b. Import into Vercel (website)
1. vercel.com → **Sign up with GitHub** → **Add New → Project** → import `kidpoems`.
2. **Root Directory: `web`** · Framework Preset: **Other** · leave the build command empty.
3. **Environment Variables:**
   | Name | Value |
   |---|---|
   | `GITHUB_REPO` | `YOUR-USERNAME/kidpoems` |
   | `GITHUB_TOKEN` | the fine-grained token from 6a |
   | `DASHBOARD_PASSWORD` | a strong password (at least 8 characters) |

   ⚠ Do **not** put the YouTube or Gemini keys on Vercel. They stay in GitHub Secrets only.
4. Click **Deploy** and wait about 1 min. Open `https://kidpoems-xxxx.vercel.app`, enter your password, and you'll see the runs, the per-language status, and the videos.
5. **Run now** starts a full run with upload. **Test run** renders without uploading.

### 6c. Or deploy with the CLI
```powershell
cd D:\kidpoems\web
vercel login
vercel link                       # create/link the project
vercel env add GITHUB_REPO        # repeat for GITHUB_TOKEN and DASHBOARD_PASSWORD (Production + Preview)
vercel                            # preview URL - test it
vercel --prod                     # production
```
After this, every `git push` to `main` redeploys the dashboard automatically. Pull requests get a preview URL.

## 7. Daily routine (5–10 min)
1. Open the dashboard and check the last run is ✅. Any language marked `error` shows its reason.
2. Open YouTube Studio, watch the new private videos, then publish or schedule them.
3. Add new ideas to `data/topics.txt` → `git add . ; git commit -m "more topics" ; git push`.

## 8. Troubleshooting
| Problem | Fix |
|---|---|
| Dashboard says "wrong password" | Check `DASHBOARD_PASSWORD` on Vercel, then redeploy (env changes need a redeploy) |
| Dashboard error "GitHub 404/401" | `GITHUB_REPO` is spelled wrong, or the token lacks Actions/Contents permission or has expired |
| "Run now" does nothing | The token needs **Actions: Read and write**; the workflow file must be on `main` |
| Action fails at "Save history" | Set Workflow permissions to **Read and write** (step 5.2) |
| `invalid_grant` in the logs | The refresh token expired. Publish the consent screen, then run `get_youtube_token.py` again |
| `quotaExceeded` | The free daily upload limit (about 6 uploads). It retries tomorrow; the other languages continue |
| Boxes instead of letters | That font is missing locally. On GitHub Actions the Noto fonts are installed automatically |
