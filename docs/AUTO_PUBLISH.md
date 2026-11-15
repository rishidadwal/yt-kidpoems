# Post videos to your channel automatically every day

The pipeline can make videos **go public by themselves**, with no daily clicking. There are three modes in `config.yaml`:

```yaml
review_mode: false        # must be false for automatic publishing
publish:
  mode: scheduled         # scheduled | public | private
  time_ist: "17:00"       # when "scheduled" videos go public (IST)
```
| Mode | What happens |
|---|---|
| `scheduled` ⭐ recommended | Upload in the morning, then YouTube **makes it public at 17:00 IST** (peak time for kids' videos). You have a few hours to catch a bad video in Studio. |
| `public` | Public straight after upload |
| `private` | You publish by hand (same as `review_mode: true`) |

**Safety net:** before anything goes public, every video is checked automatically. It must be at least 8 s long and its audio must not be silent. If it fails, it's uploaded **private** instead and the log shows `[warn] quality check failed`.

## ⚠ Required once: the YouTube API audit (free)
Google **locks uploads from new, unverified API projects to private**, whatever the code asks for. To remove the lock:

1. Go to **console.cloud.google.com** → your project → **OAuth consent screen**. Make sure it's **Published** ("In production"), with an app name, your email, and a privacy policy URL. You can host a simple privacy page for free, for example on your Vercel dashboard or with GitHub Pages.
2. Open the form: **support.google.com/youtube/contact/yt_api_form** → *"YouTube API Services – Audit and Quota Extension"*.
3. Fill it in honestly:
   - **API client:** your Google Cloud project number (on the project dashboard)
   - **Use case:** "Uploading my own original, AI-assisted children's nursery-rhyme videos to my own channels. Videos are marked Made for Kids and disclosed as synthetic media. No third-party user data is accessed."
   - **Channels:** list your channel URLs
   - **Quota:** you can ask for more than 10,000 units/day if you want more languages
4. Google usually replies in **1–4 weeks** by email.
5. When it's approved, set `review_mode: false` in `config.yaml` and push:
```powershell
git pull ; git add config.yaml ; git commit -m "auto publish" ; git push
```

**Until the audit is approved:** the videos still upload (private) with the go-live time attached. Publish them in YouTube Studio (Content → Visibility → Public), or use Studio's own schedule button.

## Tips
- Keep **one video a day per channel** at a fixed time. Consistency helps the algorithm.
- Shorts go live at the same time as the main video.
- Even with auto-publish, look at the channel a few times a week, and watch comments and Studio notifications for any policy warnings.
