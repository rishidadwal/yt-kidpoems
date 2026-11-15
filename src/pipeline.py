"""Kid-poems pipeline: poem -> every language -> voice -> pictures -> video (+Short) -> YouTube.

Run:  python -m src.pipeline            (uses config.yaml)
      python -m src.pipeline --offline  (no AI/APIs: public-domain rhyme + offline pictures; still needs TTS)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import shutil
import sys
import traceback
from pathlib import Path

import yaml

from . import picturebook, tts, video, visuals
from . import poem as P

ROOT = Path(__file__).resolve().parent.parent
OUT, DATA = ROOT / "output", ROOT / "data"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "poem"


def find_fonts_dir() -> Path:
    for d in [ROOT / "assets" / "fonts", Path("/usr/share/fonts"), Path("C:/Windows/Fonts"),
              Path("/System/Library/Fonts"), Path.home() / ".fonts"]:
        if d.exists():
            return d
    return ROOT


def pick_music() -> Path | None:
    files = list((ROOT / "assets" / "music").glob("*.mp3"))
    return random.choice(files) if files else None


def look_of(cfg: dict, dance: bool = False) -> str:
    """classic (glossy 3D cartoon) or picturebook (crayon storybook pages). Unknown values fail fast.
    Dance songs may have their own look (`dance_look`): a bright party reads better than a quiet crayon page."""
    look = str((dance and cfg.get("dance_look")) or cfg.get("look", "classic")).lower()
    if look not in video.LOOKS:
        raise ValueError(f"config.yaml look: {look!r} - use one of {', '.join(video.LOOKS)}")
    return look


def art_style_for(cfg: dict, dance: bool = False) -> str:
    """The picture prompt style that matches the look."""
    if look_of(cfg, dance) == "picturebook":
        return str(cfg.get("picturebook_art_style") or picturebook.ART_STYLE)
    return str(cfg["art_style"])


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def todays_mode(cfg: dict, today: dt.date | None = None) -> str:
    """poem | dance | alternate (dance on odd days of the year, poem on even)."""
    m = str(cfg.get("content_mode", "poem")).lower()
    if m == "alternate":
        return "dance" if (today or dt.datetime.now(IST).date()).toordinal() % 2 else "poem"
    return "dance" if m == "dance" else "poem"


def get_master(cfg: dict, hist: dict, offline: bool) -> tuple[dict, str | None]:
    cast = cfg.get("cast", "two happy little kids and a fluffy orange kitten")
    if todays_mode(cfg) == "dance":
        topic = P.next_dance_topic(hist)
        if not offline and topic:
            try:
                d = P.write_dance(topic, cfg["llm_model"], cast)
                d["_dance_topic"] = topic
                return d, None
            except P.PoemError as e:
                print(f"[warn] AI dance song failed ({e}); using built-in chant")
        d = P.builtin_dance(random.randint(1, 10**6), cast)
        d["_dance_topic"] = topic
        return d, None
    if not offline:
        topic = P.next_topic(hist)
        if topic:
            try:
                return P.write_original(topic, cfg["llm_model"], cast), topic
            except P.PoemError as e:
                print(f"[warn] AI poem failed ({e}); using public-domain rhyme")
    return P.public_domain(hist), None


W, H = 1920, 1080  # Full-HD output (YouTube recommends 1080p+)
RUN_LOG: list[dict] = []  # per-language status for data/last_run.json (shown on the dashboard)


def make_one(cfg: dict, hist: dict, offline: bool) -> list[dict]:
    master, topic = get_master(cfg, hist, offline)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    job = OUT / f"{stamp}-{slug(master['title'])}"
    job.mkdir(parents=True, exist_ok=True)
    fonts = find_fonts_dir()
    seed = random.randint(1, 10**6)
    is_dance = master.get("mode") == "dance"
    look = look_of(cfg, is_dance)
    style = art_style_for(cfg, is_dance)
    subs_fonts = picturebook.FONT_DIR if look == "picturebook" else fonts

    # one picture per line, shared by every language (Shorts reuse them over a blurred background)
    master["image_prompts"] = P.with_cast(master["image_prompts"], str(cfg.get("cast", "")))
    scenes = visuals.make_scenes(master["image_prompts"], style, 1920, 1080, seed, job / "scenes", offline)

    # 1) text for every language first (so the GPU job can sing all of them in one go)
    per_lang: dict[str, dict] = {}
    for lang in cfg["languages"]:
        code = lang["code"]
        try:
            if (master.get("_public_domain") or master.get("_builtin")) and code != "en" and offline:
                print(f"[skip] {code}: offline mode can't localise")
                continue
            per_lang[code] = master if code == "en" else P.localise(master, lang["name"], cfg["llm_model"])
        except Exception as e:  # noqa: BLE001 - must never stop the whole run
            print(f"[error] {code}: {e}")
            RUN_LOG.append({"lang": code, "title": master["title"], "status": "error", "error": str(e)[:300]})

    # 2) Level 2 (optional): real singing + animated scenes on a free Kaggle GPU
    gpu_res = None
    if cfg.get("gpu", {}).get("enabled") and not offline and per_lang:
        from . import gpu
        job_spec = gpu.build_job(cfg, per_lang, master["image_prompts"], seed, style,
                                 dance=master.get("mode") == "dance")
        gpu_res = gpu.run(job_spec, scenes, job / "gpu", int(cfg["gpu"].get("timeout_minutes", 150)))
    if gpu_res and gpu_res.images:  # sharper SDXL pictures made on the GPU replace the free-API ones
        scenes = [gpu_res.images.get(i, s) for i, s in enumerate(scenes)]
    if look == "picturebook":  # every picture redrawn as a crayon page (animated clips get paper in video.py)
        scenes = picturebook.stylize_all(scenes, seed)
    visuals_list = [gpu_res.clips.get(i, s) if gpu_res else s for i, s in enumerate(scenes)]

    # 3) render + package every language
    results = []
    for lang in cfg["languages"]:
        code = lang["code"]
        if code not in per_lang:
            continue
        try:
            p = per_lang[code]
            from . import music as M
            bpm = M.pick_bpm(seed, "dance") if is_dance else None
            actions = p.get("actions") if is_dance else None
            ld = job / code
            ld.mkdir(parents=True, exist_ok=True)
            vol = float(cfg.get("music_volume", 0))
            song = gpu_res.songs.get(code) if gpu_res else None
            if song:  # sung by the AI - the song already contains the music
                voice, times = song
                music, vol = None, 0.0
                bpm = None  # AI song tempo isn't known exactly -> no beat pulses (actions still shown)
                total = video.duration_of(voice) + 0.5
                print(f"[level2] {code}: using AI-sung song")
            else:
                clips = tts.speak_lines(p["lines"], lang["voice"], cfg["voice_rate"], cfg["voice_pitch"], ld / "tts")
                voice, times = video.build_voice_track(clips, ld / "tts")
                total = None
                music = pick_music()
                if music is None and vol > 0:  # no files provided -> synthesise a copyright-free happy tune
                    from . import music as M
                    music = M.make_track(times[-1][1] + video.TAIL + 2, ld / "music.wav", seed,
                                         "dance" if is_dance else "happy")

            ass = video.write_ass(p["title"], p["lines"], times, lang["font"], W, H, ld / "subs.ass", seed, actions, bpm,
                                 look=look)
            mp4 = video.render(visuals_list, p["lines"], voice, times, ass, subs_fonts, music, vol, W, H,
                               ld / "video.mp4", seed, total, bpm, look=look)
            thumb = visuals.thumbnail(scenes[0], p["title"], fonts, lang["font"], ld / "thumb.jpg", code)
            item = {"lang": code, "title": p["title"], "video": mp4, "thumb": thumb, "mode": master.get("mode", "poem"),
                    "description": p["description"], "tags": p["tags"], "short": None}

            length = total or (times[-1][1] + video.TAIL)
            if cfg.get("make_shorts") and length <= 58:
                vass = video.write_ass(p["title"], p["lines"], times, lang["font"], 1080, 1920, ld / "subs_v.ass", seed, actions,
                                      bpm, look=look)
                item["short"] = video.render(visuals_list, p["lines"], voice, times, vass, subs_fonts, music, vol,
                                             1080, 1920, ld / "short.mp4", seed, total, bpm, look=look)
            (ld / "meta.json").write_text(json.dumps({k: str(v) for k, v in item.items()}, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
            results.append(item)
            RUN_LOG.append({"lang": code, "title": p["title"], "status": "rendered",
                            "level": 2 if song or (gpu_res and gpu_res.clips) else 1})
            print(f"[ok] {code}: {mp4}")
        except Exception as e:  # noqa: BLE001 - one language failing must not stop the others
            print(f"[error] {code}: {e}")
            RUN_LOG.append({"lang": code, "title": p["title"] if code in per_lang else master["title"],
                            "status": "error", "error": str(e)[:300]})
            traceback.print_exc()

    if master.get("_dance_topic"):
        hist.setdefault("done_dance_topics", []).append(master["_dance_topic"])
    if topic:
        hist["done_topics"].append(topic)
    if master.get("_public_domain"):
        hist["done_rhymes"].append(master["title"])
    return results


def _offline(prompt: str, i: int, w: int, h: int, out: Path) -> Path:
    visuals.fallback_image(prompt + str(i), w, h, out)
    return out


def publish_settings(cfg: dict, now: dt.datetime | None = None) -> tuple[str, str | None]:
    """-> (privacy, publish_at_iso). review_mode wins; 'scheduled' = go public automatically at the chosen IST time."""
    if cfg.get("review_mode", True):
        return "private", None
    pub = cfg.get("publish", {}) or {}
    mode = pub.get("mode", "public")
    if mode != "scheduled":
        return ("public" if mode == "public" else "private"), None
    hh, mm = (int(x) for x in str(pub.get("time_ist", "17:00")).split(":"))
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    now = (now or dt.datetime.now(dt.UTC)).astimezone(ist)
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when <= now + dt.timedelta(minutes=20):   # too close / passed -> tomorrow
        when += dt.timedelta(days=1)
    return "private", when.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def quality_ok(video_path: Path) -> tuple[bool, str]:
    """Automatic safety net before anything goes public: real length, not silent, real picture."""
    import subprocess
    try:
        dur = video.duration_of(video_path)
        if dur < 8:
            return False, f"too short ({dur:.1f}s)"
        vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True, check=False).stderr
        mean = float(vol.split("mean_volume:")[1].split("dB")[0]) if "mean_volume:" in vol else -99
        if mean < -40:
            return False, f"audio almost silent ({mean} dB)"
        return True, "ok"
    except Exception as e:  # noqa: BLE001 - must never stop the whole run
        return False, f"check failed: {e}"


def publish(cfg: dict, items: list[dict], hist: dict) -> None:
    from . import upload as U
    privacy, publish_at = publish_settings(cfg)
    for it in items:
        prefix = cfg.get("channels", {}).get(it["lang"])
        yt = U.client_for(prefix) if prefix else None
        if not yt:
            print(f"[info] {it['lang']}: no YouTube token -> kept in output/ only")
            continue
        pv, pa = privacy, publish_at
        ok, why = quality_ok(it["video"])
        if not ok and (pv == "public" or pa):
            print(f"[warn] {it['lang']}: quality check failed ({why}) -> uploading as PRIVATE for review")
            pv, pa = "private", None
        tags = list(dict.fromkeys(it["tags"] + ["nursery rhymes", "kids songs"]))
        desc = it["description"] + "\n\n#nurseryrhymes #kidssongs"
        try:
            vid = U.upload(yt, it["video"], it["thumb"], it["title"], desc, tags, it["lang"], pv, pa)
        except Exception as e:  # noqa: BLE001 - one failed upload must not stop the others
            print(f"[error] upload {it['lang']}: {e}")
            _set_status(it["lang"], "upload_error", str(e)[:300])
            continue
        when = f"goes public {pa}" if pa else pv
        print(f"[uploaded] {it['lang']} video https://youtu.be/{vid} ({when})")
        rec = {"lang": it["lang"], "title": it["title"], "video_id": vid, "mode": it.get("mode", "poem"), "at": dt.datetime.now(dt.UTC).isoformat(),
               "privacy": pv, "publish_at": pa}
        if it.get("short"):
            try:
                sid = U.upload(yt, it["short"], None, (it["title"] + " #shorts")[:100], desc, tags, it["lang"], pv, pa)
                rec["short_id"] = sid
                print(f"[uploaded] {it['lang']} short https://youtu.be/{sid}")
            except Exception as e:  # noqa: BLE001 - must never stop the whole run
                print(f"[error] short upload {it['lang']}: {e}")
        hist["videos"].append(rec)
        _set_status(it["lang"], "uploaded", video_id=vid, short_id=rec.get("short_id"))
        from . import (
            archive,  # keep a copy for the weekly compilation (free GitHub Release storage)
        )
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d")
        archive.store(it["lang"], it["video"], f"{stamp}-{it.get('mode', 'poem')}-{slug(it['title'])}.mp4",
                      int((cfg.get("compilation") or {}).get("keep_archive", 40)))


def _set_status(lang: str, status: str, error: str = "", **extra) -> None:
    for r in RUN_LOG:
        if r["lang"] == lang and r["status"] == "rendered":
            r["status"] = status
            if error:
                r["error"] = error
            r.update({k: v for k, v in extra.items() if v})
            return


def load_history(path: Path) -> dict:
    """Never crash on a broken history file (e.g. git merge-conflict markers): back it up and start clean."""
    empty = {"done_topics": [], "done_rhymes": [], "videos": []}
    try:
        h = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(h, dict):
            raise TypeError("not an object")
    except FileNotFoundError:
        return empty
    except (ValueError, TypeError) as e:
        bak = path.with_suffix(".broken.json")
        bak.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        print(f"::warning::history.json was broken ({e}); saved a copy to {bak.name} and started fresh")
        return empty
    for k, v in empty.items():
        h.setdefault(k, v)
    return h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="no AI / image APIs (test mode)")
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("ffmpeg not found - install it first")
        return 2
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    hist_path = DATA / "history.json"
    hist = load_history(hist_path)

    made = []
    for _ in range(int(cfg.get("videos_per_run", 1))):
        made += make_one(cfg, hist, args.offline)
    if made and cfg.get("upload") and not args.no_upload:
        publish(cfg, made, hist)
    tmp = hist_path.with_suffix(".tmp")  # atomic write: never leave a half-written history
    tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(hist_path)
    (DATA / "last_run.json").write_text(json.dumps({
        "at": dt.datetime.now(dt.UTC).isoformat(), "offline": args.offline,
        "upload": bool(cfg.get("upload")) and not args.no_upload, "results": RUN_LOG,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {len(made)} video(s)")
    if not made:
        return 1
    want_upload = bool(cfg.get("upload")) and not args.no_upload
    uploaded = [r for r in RUN_LOG if r["status"] == "uploaded"]
    if want_upload and not uploaded:
        print("::error::Upload was ON but nothing was uploaded - check the YouTube secrets / [error] lines above")
        return 1
    if any(r["status"] in ("error", "upload_error") for r in RUN_LOG):
        print("::warning::Some languages failed - see [error] lines above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
