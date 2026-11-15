"""Level 2: send heavy AI work (singing + animation) to a FREE Kaggle GPU and wait for the result.

Flow (all via the official `kaggle` CLI):
  1. upload job.json + scene pictures as a private Kaggle dataset (new version each run)
  2. push kaggle/gpu_job.py as a private GPU notebook that reads that dataset
  3. poll until it finishes, then download /kaggle/working/out
Any failure returns an empty result -> the pipeline silently falls back to Level 1 for that item.
Needs env: KAGGLE_USERNAME + KAGGLE_API_TOKEN (or legacy KAGGLE_KEY) (GitHub Secrets). Your Kaggle account must be phone-verified
(Kaggle requires this for GPU + internet in notebooks).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = "kidpoems-job"
KERNEL = "kidpoems-gpu"


@dataclass
class GpuResult:
    songs: dict[str, tuple[Path, list[tuple[float, float]]]] = field(default_factory=dict)  # lang -> (wav, times)
    clips: dict[int, Path] = field(default_factory=dict)                                   # scene index -> mp4
    images: dict[int, Path] = field(default_factory=dict)                                  # scene index -> HD png
    notes: list[str] = field(default_factory=list)


def available() -> bool:
    key = os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")  # new API token, or the legacy key
    return bool(os.environ.get("KAGGLE_USERNAME") and key and shutil.which("kaggle"))


def _kaggle(*args: str, timeout: int = 600) -> str:
    p = subprocess.run(["kaggle", *args], capture_output=True, text=True, check=False, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args[:2])} failed: {(p.stderr or p.stdout)[-600:]}")
    return p.stdout


def _upload_dataset(user: str, job_dir: Path) -> None:
    (job_dir / "dataset-metadata.json").write_text(json.dumps(
        {"title": DATASET, "id": f"{user}/{DATASET}", "licenses": [{"name": "CC0-1.0"}]}))
    try:
        _kaggle("datasets", "version", "-p", str(job_dir), "-m", f"job {int(time.time())}", "--dir-mode", "zip")
    except RuntimeError as e:
        if "not found" in str(e).lower() or "404" in str(e) or "does not exist" in str(e).lower():
            _kaggle("datasets", "create", "-p", str(job_dir), "--dir-mode", "zip")
        else:
            raise
    for _ in range(60):  # wait until Kaggle has processed the new version
        if "ready" in _kaggle("datasets", "status", f"{user}/{DATASET}").lower():
            return
        time.sleep(10)
    raise RuntimeError("dataset never became ready")


def _push_kernel(user: str, work: Path) -> None:
    kdir = work / "kernel"
    kdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "kaggle" / "gpu_job.py", kdir / "gpu_job.py")
    (kdir / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{user}/{KERNEL}", "title": KERNEL, "code_file": "gpu_job.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [f"{user}/{DATASET}"], "competition_sources": [], "kernel_sources": [],
    }))
    _kaggle("kernels", "push", "-p", str(kdir))


def _wait(user: str, timeout_min: int) -> str:
    end = time.time() + timeout_min * 60
    time.sleep(60)
    last = ""
    while time.time() < end:
        try:
            last = _kaggle("kernels", "status", f"{user}/{KERNEL}", timeout=120).lower()
        except RuntimeError as e:
            last = str(e).lower()
        print(f"[gpu] {last.strip()[-80:]}")
        if "complete" in last:
            return "complete"
        if "error" in last or "cancel" in last:
            return "error"
        time.sleep(60)
    return "timeout"


def run(job: dict, images: list[Path], work: Path, timeout_min: int = 150) -> GpuResult:
    res = GpuResult()
    if not available():
        res.notes.append("Kaggle not configured (KAGGLE_USERNAME + KAGGLE_API_TOKEN) - using Level 1")
        return res
    user = os.environ["KAGGLE_USERNAME"]
    try:
        jdir = work / "job"
        jdir.mkdir(parents=True, exist_ok=True)
        for sc in job.get("animate", []):
            shutil.copy(images[sc["index"]], jdir / sc["image"])
        (jdir / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        _upload_dataset(user, jdir)
        _push_kernel(user, work)
        print("[gpu] Kaggle GPU job started - this usually takes 20-90 minutes")
        state = _wait(user, timeout_min)
        out = work / "out"
        out.mkdir(exist_ok=True)
        _kaggle("kernels", "output", f"{user}/{KERNEL}", "-p", str(out), "-o", timeout=900)
        found = {p.name: p for p in out.rglob("*") if p.is_file()}
        for lang in job.get("songs", {}):
            wav, tj = found.get(f"song_{lang}.wav"), found.get(f"times_{lang}.json")
            if wav and tj and wav.stat().st_size > 100_000:
                times = [(float(a), float(b)) for a, b in json.loads(tj.read_text())]
                res.songs[lang] = (wav, times)
        for i in range(len(job.get("images", {}).get("prompts", []))):
            img = found.get(f"image_{i:02d}.png")
            if img and img.stat().st_size > 50_000:
                res.images[i] = img
        for sc in job.get("animate", []):
            clip = found.get(f"clip_{sc['index']:02d}.mp4")
            if clip and clip.stat().st_size > 5_000:
                res.clips[sc["index"]] = clip
        if "status.json" in found:
            st = json.loads(found["status.json"].read_text())
            res.notes += [e.splitlines()[0][:200] for e in st.get("errors", [])]
        res.notes.append(f"kaggle state={state}, songs={list(res.songs)}, hd_images={len(res.images)}, clips={len(res.clips)}")
    except Exception as e:  # noqa: BLE001 - never break the daily run
        res.notes.append(f"GPU step failed, falling back to Level 1: {e}")
    for n in res.notes:
        print(f"[gpu] {n}")
    return res


def build_job(cfg: dict, per_lang: dict[str, dict], prompts: list[str], seed: int, style: str = "",
              dance: bool = False) -> dict:
    g = cfg.get("gpu", {})
    sing = [lg for lg in g.get("sing_languages", []) if lg in per_lang] if g.get("singing", True) else []
    n_anim = min(len(prompts), int(g.get("max_animated_scenes", 8))) if g.get("animate", True) else 0
    return {
        "seed": seed,
        "music_tags": (g.get("dance_music_tags", "kids dance song, party, catchy chant, 128 bpm") if dance
                       else g.get("music_tags", "children's song, nursery rhyme, cheerful")),
        "song_steps": int(g.get("song_steps", 60)),
        "songs": {lg: {"lines": per_lang[lg]["lines"], "whisper_lang": lg} for lg in sing},
        "animate": [{"index": i, "image": f"scene_{i:02d}.jpg", "prompt": prompts[i]} for i in range(n_anim)],
        "images": ({"prompts": prompts, "style": style, "model": g.get("image_model", "stabilityai/stable-diffusion-xl-base-1.0"),
                    "steps": int(g.get("image_steps", 30))} if g.get("hd_images", True) else {}),
        "video_model": g.get("video_model", "Lightricks/LTX-Video"),
        "clip_frames": int(g.get("clip_frames", 97)),
        "clip_steps": int(g.get("clip_steps", 30)),
        "clip_budget_minutes": int(g.get("clip_budget_minutes", 120)),
    }
