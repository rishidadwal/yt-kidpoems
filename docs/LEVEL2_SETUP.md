# Level 2 – Real Singing + Animated Scenes (free Kaggle GPU)

**What changes:** instead of a speaking voice and moving pictures, each video gets:
- 🎤 **A real sung nursery song** with melody and music, made by **ACE-Step** (open source, Apache-2.0).
- 🎬 **Animated scenes.** Each picture comes to life (kids running, kittens jumping) using **LTX-Video** (open source).
- ⏱ **Lyrics synced to the singing**, using faster-whisper word timings.

GitHub Actions still runs everything. It sends the heavy work to a free Kaggle GPU, waits, and downloads the result.
**If Kaggle fails, is busy or isn't set up, the video is still made with Level 1**, so the daily run never stops.

## One-time setup (15 minutes)
1. **Create a free account** at kaggle.com.
2. **Verify your phone number:** Kaggle → your profile picture → **Settings → Phone verification**. This is required, because without it Kaggle notebooks can't use a GPU or internet.
3. **Create an API token:** Kaggle → **Settings → API → Create New Token**. A file `kaggle.json` downloads, containing `{"username":"...","key":"..."}`.
4. **Add 2 GitHub secrets:** repo → Settings → Secrets and variables → Actions → New repository secret:
   - `KAGGLE_USERNAME` = the username from kaggle.json
   - `KAGGLE_KEY` = the key from kaggle.json
5. Copy the new files into `D:\kidpoems` and push:
```powershell
git pull ; git add . ; git commit -m "feat: Level 2 singing + animation" ; git push
```
6. Go to **Actions → daily-kid-poems → Run workflow → upload = no** for a first test. The run now takes **40–150 min**. The log shows lines like:
```
[gpu] Kaggle GPU job started - this usually takes 20-90 minutes
[gpu] ... has status "running"
[gpu] kaggle state=complete, songs=['en', 'hi', 'es'], clips=8
[level2] en: using AI-sung song
```
7. You can also watch it live: kaggle.com → **Code → Your Work → kidpoems-gpu**.

## Settings (`config.yaml` → `gpu:`)
| Setting | Meaning |
|---|---|
| `enabled` | `false` switches back to Level 1 only |
| `sing_languages` | Languages to sing. ACE-Step sings best in English, Chinese, Russian, Spanish, Japanese, German, French, Portuguese, Italian and Korean. Other languages may sound weak; if so, remove them and they'll use the Level 1 voice. |
| `music_tags` | Style of the song (instruments, mood, tempo) |
| `max_animated_scenes` | How many scenes get animated (the rest stay as moving pictures). Lower it if runs are too slow. |
| `clip_steps` / `clip_frames` | Animation quality vs. speed |
| `timeout_minutes` | After this, stop waiting and use Level 1 |

## Free limits to know
- **Kaggle gives about 30 GPU hours per week.** One daily run uses roughly 1–2 hours, so it fits.
- **The first run is slower**, because it downloads the AI models (about 15–25 GB).
- **GitHub Actions jobs can run up to 6 hours;** the workflow allows 4.
- **Quality varies.** AI singing can sometimes mispronounce words, and animation can occasionally look odd. **Keep `review_mode: true`** and watch every video before publishing.

## Troubleshooting
| Log line | Fix |
|---|---|
| `Kaggle not configured` | Add the `KAGGLE_USERNAME` and `KAGGLE_KEY` secrets |
| `401` / `Unauthorized` | Wrong key. Create a new token on Kaggle and update the secret. |
| `GPU / internet not allowed` or the kernel fails at once | Verify your phone number on Kaggle (step 2) |
| `kaggle state=timeout` | Kaggle queue was busy. Level 1 was used; it tries again tomorrow. |
| `songs=[]` with `ace-step setup` error | Paste me the error from Kaggle → Code → kidpoems-gpu → Logs |
| `clip X: out of memory` | Lower `clip_frames` to 65 or `max_animated_scenes` to 5 |
