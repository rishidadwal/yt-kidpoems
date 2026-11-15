"""Weekly compilation: join the last N archived videos per language into one long video
(long videos = much more watch time on kids' channels) and upload it.

Run:  python -m src.compile            (GitHub Actions: weekly-compilation.yml, Sundays)
      python -m src.compile --no-upload
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import json
import operator
import subprocess
import sys
from pathlib import Path

import yaml

from . import archive, video, visuals
from .pipeline import (
    DATA,
    OUT,
    ROOT,
    find_fonts_dir,
    load_history,
    publish_settings,
    quality_ok,
)

TITLES = {  # simple built-in titles; Gemini isn't needed for these
    "en": ("Kids Dance Party Mix", "Nursery Rhymes Collection"),
    "hi": ("बच्चों का डांस पार्टी मिक्स", "बच्चों की कविताएँ संग्रह"),
    "es": ("Mix de Baile para Niños", "Colección de Canciones Infantiles"),
    "fr": ("Mix Danse pour Enfants", "Comptines pour Enfants"),
    "pt": ("Mix de Dança Infantil", "Coletânea de Músicas Infantis"),
}


def concat(files: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    fast = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                           "-c", "copy", "-movflags", "+faststart", str(out)], capture_output=True, text=True, check=False)
    if fast.returncode != 0 or not out.exists():   # different formats -> re-encode everything the same way
        n = len(files)
        inputs = functools.reduce(operator.iadd, (["-i", str(f)] for f in files), [])
        fl = "".join(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                     f"fps=25,setsar=1[v{i}];[{i}:a]aresample=44100[a{i}];" for i in range(n))
        fl += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fl, "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", str(out)], check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cc = cfg.get("compilation", {}) or {}
    if not cc.get("enabled", True):
        print("compilation disabled")
        return 0
    hist = load_history(DATA / "history.json")
    n, want = int(cc.get("videos", 7)), cc.get("mode", "any")
    fonts, made = find_fonts_dir(), 0
    for lang in cfg["languages"]:
        code = lang["code"]
        names = [a for a in archive.list_assets(code) if want == "any" or f"-{want}-" in a][-n:]
        if len(names) < 3:
            print(f"[skip] {code}: only {len(names)} archived videos (need 3+)")
            continue
        work = OUT / f"compilation-{dt.datetime.now(dt.UTC).date()}" / code
        files = archive.fetch(code, names, work / "parts")
        if len(files) < 3:
            continue
        out = concat(files, work / "compilation.mp4")
        minutes = max(1, round(video.duration_of(out) / 60))
        dance_t, poem_t = TITLES.get(code, TITLES["en"])
        base = dance_t if want == "dance" or all("-dance-" in f.name for f in files) else poem_t
        title = f"{base} | {len(files)} Songs | {minutes} Min"
        # thumbnail: a frame from the middle of the first song + the title
        frame = work / "frame.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "8", "-i", str(files[0]), "-frames:v", "1", str(frame)], check=False)
        thumb = visuals.thumbnail(frame, base, fonts, lang["font"], work / "thumb.jpg", code) if frame.exists() else None
        print(f"[ok] {code}: {title} -> {out}")
        made += 1
        if args.no_upload or not cfg.get("upload"):
            continue
        from . import upload as U
        prefix = cfg.get("channels", {}).get(code)
        yt = U.client_for(prefix) if prefix else None
        if not yt:
            print(f"[info] {code}: no YouTube token")
            continue
        privacy, at = publish_settings(cfg)
        if not quality_ok(out)[0]:
            privacy, at = "private", None
        desc = f"{title}\n\n" + "\n".join(f"{i + 1}. {f.stem.split('-', 3)[-1].replace('-', ' ').title()}"
                                        for i, f in enumerate(files)) + "\n\n#nurseryrhymes #kidssongs #kidsdance"
        vid = U.upload(yt, out, thumb, title, desc, ["nursery rhymes", "kids songs", "kids dance", "compilation"],
                       code, privacy, at)
        print(f"[uploaded] {code} compilation https://youtu.be/{vid}")
        hist.setdefault("compilations", []).append({"lang": code, "video_id": vid, "title": title,
                                                    "at": dt.datetime.now(dt.UTC).isoformat()})
    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
