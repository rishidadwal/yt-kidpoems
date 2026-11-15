# Dance Mode + Weekly Compilation

## Dance mode
Viral-style kids' **dance songs**, but **100% original** (never copy another song's hook, melody or characters):
- **Tiny catchy nonsense hook,** invented new each time (e.g. "Zum zum dee dee!"), repeated 5 or more times
- **Action calls kids copy:** clap, jump, spin, wiggle, stomp, hop…
- **Big bouncing action words** on screen: **CLAP!**, **JUMP!**, **SPIN!**
- **Party beat:** 124–128 BPM with four-on-the-floor kick, claps and synths (auto-generated and copyright-free). With Level 2 it's a sung dance song.
- **Beat effects:** pictures "punch" on every beat, star bursts every 2 beats, a light flash every bar
- **Scenes:** the cast dancing in a sunny jungle party with balloons, on a rainbow stage, or at a beach party

`config.yaml`:
```yaml
content_mode: alternate   # poem | dance | alternate (dance one day, poem the next)
```
Dance ideas live in `data/dance_topics.txt`. Add as many as you like, one per line.

## Characters
Set in `config.yaml → cast`. They're **original**, so no other channel owns them:
> Pip (a chubby curly-haired toddler in a yellow striped onesie), Gigi (a baby giraffe with a pink bow), Momo (a round fluffy panda cub) and Quack (a little yellow duckling with an orange cap).

Change them any time. Describe the look precisely, because the AI draws whatever the text says. Don't describe another channel's characters.

## Weekly compilation (long videos = much more watch time)
- Every uploaded video is also saved to a free **GitHub Release** called `archive-<lang>` in your repo. The last 40 are kept.
- **Every Sunday at 08:00 IST**, `weekly-compilation.yml` joins the last 7 videos per language into one long video, for example "Kids Dance Party Mix | 7 Songs | 6 Min", with its own thumbnail and a track list in the description.
- It needs at least 3 archived videos per language, so it starts working after your first few daily uploads.
- To run it by hand: Actions → **weekly-compilation** → Run workflow.

```yaml
compilation:
  enabled: true
  videos: 7          # songs per compilation (more songs = longer video)
  mode: any          # any | dance | poem
```
