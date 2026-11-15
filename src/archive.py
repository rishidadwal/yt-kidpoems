"""Keep every finished video in a free GitHub Release ("archive-<lang>") so the weekly
compilation can join them later. Uses the `gh` CLI that is pre-installed on GitHub Actions.
Silently does nothing outside GitHub Actions or when GH_TOKEN is missing."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def enabled() -> bool:
    return bool(os.environ.get("GITHUB_ACTIONS") and os.environ.get("GH_TOKEN") and shutil.which("gh"))


def _gh(*args: str, timeout: int = 900) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, check=False, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[-400:])
    return p.stdout


def tag(lang: str) -> str:
    return f"archive-{lang}"


def ensure_release(lang: str) -> None:
    try:
        _gh("release", "view", tag(lang))
    except RuntimeError:
        _gh("release", "create", tag(lang), "--title", f"Video archive ({lang})",
            "--notes", "Automatic archive for weekly compilations. Do not delete.", "--latest=false")


def list_assets(lang: str) -> list[str]:
    try:
        data = json.loads(_gh("release", "view", tag(lang), "--json", "assets"))
    except (RuntimeError, ValueError):
        return []
    return sorted(a["name"] for a in data.get("assets", []))


def store(lang: str, video: Path, name: str, keep: int = 40) -> bool:
    if not enabled():
        return False
    try:
        ensure_release(lang)
        target = video.with_name(name)
        if target != video:
            shutil.copy(video, target)
        _gh("release", "upload", tag(lang), str(target), "--clobber")
        for old in list_assets(lang)[:-keep]:        # keep the archive small
            _gh("release", "delete-asset", tag(lang), old, "--yes")
        print(f"[archive] {lang}: stored {name}")
        return True
    except Exception as e:  # noqa: BLE001 - archiving must never break the daily run
        print(f"[warn] archive {lang}: {e}")
        return False


def fetch(lang: str, names: list[str], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for n in names:
        try:
            _gh("release", "download", tag(lang), "-p", n, "-D", str(dest), "--clobber")
            if (dest / n).exists():
                out.append(dest / n)
        except RuntimeError as e:
            print(f"[warn] download {n}: {e}")
    return out
