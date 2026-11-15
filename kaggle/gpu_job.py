"""Runs on a FREE Kaggle GPU notebook (pushed automatically by src/gpu.py).

Input : /kaggle/input/**/job.json (+ scene_XX.jpg pictures)
Output: /kaggle/working/out/
          song_<lang>.wav          sung nursery song (ACE-Step, Apache-2.0)
          times_<lang>.json        [[start, end], ...] per lyric line (faster-whisper word timestamps)
          clip_XX.mp4              animated scene (LTX-Video image-to-video)
          status.json              what worked / what failed (the pipeline falls back per item)
Every step is wrapped: a failure in one item never stops the others.
"""
import glob
import json
import os
import subprocess
import sys
import time
import traceback

OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
STATUS = {"started": time.time(), "songs": {}, "clips": {}, "errors": []}


def save_status():
    STATUS["finished"] = time.time()
    with open(f"{OUT}/status.json", "w") as f:
        json.dump(STATUS, f, indent=2)


def pip(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs], check=True)


def find_job():
    hits = glob.glob("/kaggle/input/**/job.json", recursive=True)
    if not hits:
        raise SystemExit("job.json not found in /kaggle/input")
    return hits[0], os.path.dirname(hits[0])


job_path, JOB_DIR = find_job()
JOB = json.load(open(job_path, encoding="utf-8"))
print("job:", json.dumps({k: v for k, v in JOB.items() if k != "songs"}, ensure_ascii=False)[:500])


# ------------------------------------------------------------------ 1. songs (ACE-Step)
def lyrics_block(lines):
    parts = []
    for i in range(0, len(lines), 4):
        tag = "[verse]" if (i // 4) % 2 == 0 else "[chorus]"
        parts.append(tag + "\n" + "\n".join(lines[i:i + 4]))
    return "\n\n".join(parts)


def align(wav, lines, lang):
    """Line start/end times from word timestamps; even split if whisper fails."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3", device="cuda", compute_type="float16")
        segs, _ = model.transcribe(wav, language=lang or None, word_timestamps=True, vad_filter=False)
        words = [w for s in segs for w in (s.words or [])]
        if len(words) >= max(4, len(lines)):
            counts = [max(1, len(l.split())) for l in lines]
            total = sum(counts)
            out, k = [], 0
            for c in counts:
                n = max(1, round(c / total * len(words)))
                chunk = words[k:k + n] or words[-1:]
                out.append([round(chunk[0].start, 2), round(chunk[-1].end, 2)])
                k = min(len(words) - 1, k + n)
            del model
            return out, "whisper"
    except Exception as e:  # noqa: BLE001
        STATUS["errors"].append(f"align {lang}: {e}")
    import soundfile as sf
    dur = sf.info(wav).duration
    start, end = min(6.0, dur * 0.12), dur - 3.0
    step = (end - start) / max(1, len(lines))
    return [[round(start + i * step, 2), round(start + (i + 1) * step - 0.3, 2)] for i in range(len(lines))], "even"


def make_songs():
    if not JOB.get("songs"):
        return
    try:
        pip("git+https://github.com/ace-step/ACE-Step.git", "faster-whisper", "soundfile")
        import torch
        from acestep.pipeline_ace_step import ACEStepPipeline
        bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        pipe = ACEStepPipeline(checkpoint_dir=None, dtype="bfloat16" if bf16 else "float32",
                               cpu_offload=not bf16, overlapped_decode=True)
    except Exception as e:  # noqa: BLE001
        STATUS["errors"].append(f"ace-step setup: {e}\n{traceback.format_exc()[-800:]}")
        return
    for lang, song in JOB["songs"].items():
        try:
            t0 = time.time()
            path = f"{OUT}/song_{lang}.wav"
            dur = float(min(120, max(30, len(song["lines"]) * 3.4 + 10)))
            res = pipe(audio_duration=dur, prompt=JOB.get("music_tags", "children's song, cheerful"),
                       lyrics=lyrics_block(song["lines"]), infer_step=JOB.get("song_steps", 60),
                       guidance_scale=15.0, manual_seeds=[JOB.get("seed", 1)], save_path=path)
            if not os.path.exists(path):  # some versions return a different file name
                wavs = [p for p in (res or []) if isinstance(p, str) and p.endswith(".wav")]
                if wavs:
                    os.replace(wavs[0], path)
            times, how = align(path, song["lines"], song.get("whisper_lang"))
            json.dump(times, open(f"{OUT}/times_{lang}.json", "w"))
            STATUS["songs"][lang] = {"ok": True, "seconds": round(time.time() - t0), "align": how, "duration": dur}
            print(f"[song] {lang} ok in {time.time() - t0:.0f}s ({how})")
        except Exception as e:  # noqa: BLE001
            STATUS["songs"][lang] = {"ok": False}
            STATUS["errors"].append(f"song {lang}: {e}\n{traceback.format_exc()[-800:]}")
        save_status()
    del pipe
    import gc, torch  # noqa: E401
    gc.collect(); torch.cuda.empty_cache()


# ------------------------------------------------------------------ 2. HD pictures (SDXL, CreativeML OpenRAIL++)
HD = {}


def make_images():
    spec = JOB.get("images") or {}
    if not spec.get("prompts"):
        return
    try:
        pip("diffusers>=0.32", "transformers", "accelerate", "safetensors")
        import torch
        from diffusers import StableDiffusionXLPipeline
        pipe = StableDiffusionXLPipeline.from_pretrained(spec.get("model", "stabilityai/stable-diffusion-xl-base-1.0"),
                                                         torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
        pipe.to("cuda")
        pipe.enable_vae_tiling()
    except Exception as e:  # noqa: BLE001
        STATUS["errors"].append(f"sdxl setup: {e}\n{traceback.format_exc()[-800:]}")
        return
    neg = ("blurry, low quality, lowres, deformed, bad anatomy, extra fingers, extra limbs, ugly, scary, dark, "
           "text, letters, watermark, logo, signature, frame, cropped")
    STATUS["images"] = {}
    for i, prompt in enumerate(spec["prompts"]):
        try:
            g = torch.Generator("cuda").manual_seed(int(JOB.get("seed", 1)))  # same seed -> consistent characters
            img = pipe(prompt=f"{prompt}. {spec.get('style', '')}", negative_prompt=neg, width=1344, height=768,
                       num_inference_steps=spec.get("steps", 30), guidance_scale=6.5, generator=g).images[0]
            path = f"{OUT}/image_{i:02d}.png"
            img.save(path)
            HD[i] = path
            STATUS["images"][str(i)] = True
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"image {i}: {e}")
    del pipe
    import gc
    gc.collect(); torch.cuda.empty_cache()
    save_status()


# ------------------------------------------------------------------ 3. animated scenes (LTX-Video)
def make_clips():
    scenes = JOB.get("animate", [])
    if not scenes:
        return
    try:
        pip("diffusers>=0.32", "transformers", "accelerate", "sentencepiece", "imageio", "imageio-ffmpeg")
        import torch
        from diffusers import LTXImageToVideoPipeline
        from diffusers.utils import export_to_video, load_image
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        pipe = LTXImageToVideoPipeline.from_pretrained(JOB.get("video_model", "Lightricks/LTX-Video"), torch_dtype=dtype)
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
    except Exception as e:  # noqa: BLE001
        STATUS["errors"].append(f"ltx setup: {e}\n{traceback.format_exc()[-800:]}")
        return
    budget = time.time() + JOB.get("clip_budget_minutes", 150) * 60
    for sc in scenes:
        if time.time() > budget:
            STATUS["errors"].append("clip time budget reached; remaining scenes stay as pictures")
            break
        try:
            t0 = time.time()
            src = HD.get(sc["index"]) or os.path.join(JOB_DIR, sc["image"])   # prefer the new HD picture
            img = load_image(src).resize((704, 480))
            frames = pipe(image=img,
                          prompt=sc["prompt"] + ", smooth gentle joyful motion, characters moving and playing, "
                                                "high quality 3D cartoon animation, stable camera",
                          negative_prompt="worst quality, inconsistent motion, blurry, jittery, distorted, "
                                          "deformed faces, extra limbs, text, watermark, scary",
                          width=704, height=480, num_frames=JOB.get("clip_frames", 97),
                          num_inference_steps=JOB.get("clip_steps", 30), guidance_scale=3.0).frames[0]
            export_to_video(frames, f"{OUT}/clip_{sc['index']:02d}.mp4", fps=24)
            STATUS["clips"][str(sc["index"])] = {"ok": True, "seconds": round(time.time() - t0)}
            print(f"[clip] {sc['index']} ok in {time.time() - t0:.0f}s")
        except Exception as e:  # noqa: BLE001
            STATUS["clips"][str(sc["index"])] = {"ok": False}
            STATUS["errors"].append(f"clip {sc['index']}: {e}")
        save_status()


try:
    make_songs()
    make_images()
    make_clips()
finally:
    save_status()
    print(json.dumps(STATUS, indent=2)[:3000])
