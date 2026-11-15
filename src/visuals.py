"""Pictures: free Pollinations.ai image API (no key), with an offline Pillow fallback. Plus thumbnails."""
from __future__ import annotations

import hashlib
import logging
import math
import random
import threading
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

POLLINATIONS = "https://image.pollinations.ai/prompt/{p}"
MIN_GAP_S = 47.0  # free tier allows 1 image / 45 s per IP (HTTP 402 otherwise); +2 s margin
_lock = threading.Lock()
_last_call = [0.0]  # monotonic time of the last request, shared by all worker threads
log = logging.getLogger(__name__)


def _wait_turn() -> None:
    """Space requests MIN_GAP_S apart across threads, so the free limit is never hit."""
    with _lock:
        wait = _last_call[0] + MIN_GAP_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
PALETTE = [(255, 214, 165), (253, 255, 182), (202, 255, 191), (155, 246, 255),
           (160, 196, 255), (189, 178, 255), (255, 198, 255), (255, 173, 173)]


def ai_image(prompt: str, style: str, w: int, h: int, seed: int, out: Path, retries: int = 3) -> bool:
    q = urllib.parse.quote(f"{prompt}. {style}. sharp focus, 4k, highly detailed, clean composition, "
                           f"no blur, no text, no watermark, no deformed hands or faces")
    for attempt in range(1, retries + 1):
        _wait_turn()
        try:
            r = requests.get(POLLINATIONS.format(p=q),
                             params={"width": w, "height": h, "seed": seed, "nologo": "true", "enhance": "true",
                                     "safe": "true", "model": "flux"},
                             timeout=120)
            if r.ok and r.headers.get("content-type", "").startswith("image") and len(r.content) > 20_000:
                out.write_bytes(r.content)
                im = Image.open(out).convert("RGB")
                cw, ch = im.size  # trim 6% per side: removes the corner watermark the free API adds
                im = im.crop((cw * 6 // 100, ch * 6 // 100, cw * 94 // 100, ch * 94 // 100))
                if im.size != (w, h):  # cropped / smaller image -> high-quality upscale
                    im = im.resize((w, h), Image.LANCZOS)
                im.save(out, "JPEG", quality=95)
                return True
            log.warning("image %d try %d/%d: HTTP %s", seed, attempt, retries, r.status_code)
        except (requests.RequestException, OSError) as e:
            log.warning("image %d try %d/%d: %s", seed, attempt, retries, e)
    log.warning("image %d: using the built-in fallback picture", seed)
    return False


# ---------------- offline fallback: a cute hand-drawn scene with a kid and a kitten ----------------
SKIN = [(255, 224, 189), (241, 194, 125), (224, 172, 105), (198, 134, 66), (141, 85, 36)]
HAIR = [(60, 40, 30), (20, 20, 20), (120, 70, 30), (230, 180, 80)]
CLOTHES = [(255, 105, 150), (80, 160, 255), (255, 190, 60), (120, 210, 120), (180, 120, 255)]
CATS = [(255, 170, 80), (240, 240, 240), (120, 120, 130), (60, 60, 60), (230, 200, 160)]


def _kid(d: ImageDraw.ImageDraw, x: int, y: int, s: float, rnd: random.Random) -> None:
    skin, hair, cloth = rnd.choice(SKIN), rnd.choice(HAIR), rnd.choice(CLOTHES)
    r = int(60 * s)
    d.rounded_rectangle([x - r * 0.8, y + r * 0.8, x + r * 0.8, y + r * 2.6], radius=int(r * 0.5), fill=cloth)   # body
    d.line([x - r * 0.8, y + r * 1.3, x - r * 1.6, y + r * 0.6], fill=skin, width=int(r * 0.3))                  # waving arm
    d.line([x + r * 0.8, y + r * 1.3, x + r * 1.5, y + r * 1.9], fill=skin, width=int(r * 0.3))
    d.line([x - r * 0.4, y + r * 2.5, x - r * 0.4, y + r * 3.3], fill=skin, width=int(r * 0.32))                 # legs
    d.line([x + r * 0.4, y + r * 2.5, x + r * 0.4, y + r * 3.3], fill=skin, width=int(r * 0.32))
    d.ellipse([x - r, y - r, x + r, y + r], fill=skin)                                                           # head
    d.chord([x - r * 1.05, y - r * 1.1, x + r * 1.05, y + r * 0.6], 180, 360, fill=hair)                        # hair
    if rnd.random() < 0.5:                                                                                        # pigtails
        d.ellipse([x - r * 1.45, y - r * 0.4, x - r * 0.85, y + r * 0.3], fill=hair)
        d.ellipse([x + r * 0.85, y - r * 0.4, x + r * 1.45, y + r * 0.3], fill=hair)
    for ex in (-0.38, 0.38):                                                                                      # big eyes
        d.ellipse([x + r * ex - r * 0.16, y - r * 0.05, x + r * ex + r * 0.16, y + r * 0.33], fill=(40, 30, 40))
        d.ellipse([x + r * ex - r * 0.06, y + r * 0.02, x + r * ex + r * 0.04, y + r * 0.12], fill="white")
        d.ellipse([x + r * ex - r * 0.28, y + r * 0.38, x + r * ex + r * 0.02, y + r * 0.55], fill=(255, 150, 160))  # blush
    d.arc([x - r * 0.3, y + r * 0.25, x + r * 0.3, y + r * 0.7], 20, 160, fill=(170, 60, 70), width=max(2, int(r * 0.08)))


def _cat(d: ImageDraw.ImageDraw, x: int, y: int, s: float, rnd: random.Random) -> None:
    fur = rnd.choice(CATS)
    r = int(48 * s)
    d.ellipse([x - r * 1.1, y + r * 0.5, x + r * 1.1, y + r * 2.0], fill=fur)                                  # body
    d.arc([x + r * 0.6, y - r * 0.2, x + r * 2.0, y + r * 1.8], 200, 330, fill=fur, width=int(r * 0.28))       # tail
    d.polygon([(x - r * 0.9, y - r * 0.4), (x - r * 0.75, y - r * 1.35), (x - r * 0.1, y - r * 0.8)], fill=fur)  # ears
    d.polygon([(x + r * 0.9, y - r * 0.4), (x + r * 0.75, y - r * 1.35), (x + r * 0.1, y - r * 0.8)], fill=fur)
    d.polygon([(x - r * 0.78, y - r * 0.55), (x - r * 0.7, y - r * 1.05), (x - r * 0.35, y - r * 0.75)], fill=(255, 170, 190))
    d.polygon([(x + r * 0.78, y - r * 0.55), (x + r * 0.7, y - r * 1.05), (x + r * 0.35, y - r * 0.75)], fill=(255, 170, 190))
    d.ellipse([x - r, y - r, x + r, y + r * 0.8], fill=fur)                                                      # head
    for ex in (-0.4, 0.4):
        d.ellipse([x + r * ex - r * 0.18, y - r * 0.25, x + r * ex + r * 0.18, y + r * 0.15], fill=(60, 160, 90))
        d.ellipse([x + r * ex - r * 0.07, y - r * 0.2, x + r * ex + r * 0.07, y + r * 0.1], fill=(20, 20, 20))
        d.ellipse([x + r * ex - r * 0.06, y - r * 0.2, x + r * ex, y - r * 0.12], fill="white")
    d.polygon([(x - r * 0.1, y + r * 0.22), (x + r * 0.1, y + r * 0.22), (x, y + r * 0.34)], fill=(255, 120, 150))  # nose
    for sy in (0.3, 0.42):
        d.line([x - r * 0.25, y + r * sy, x - r * 1.1, y + r * (sy - 0.08)], fill=(90, 70, 70), width=2)
        d.line([x + r * 0.25, y + r * sy, x + r * 1.1, y + r * (sy - 0.08)], fill=(90, 70, 70), width=2)


def fallback_image(seed_text: str, w: int, h: int, out: Path) -> None:
    """Bright sky, rainbow, hills, flowers, a smiling sun, a kid and a kitten - never fails, works offline."""
    rnd = random.Random(int(hashlib.md5(seed_text.encode()).hexdigest(), 16))
    top, bottom = rnd.sample(PALETTE, 2)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    u = min(w, h)
    if rnd.random() < 0.6:  # rainbow
        cx, cy, rr = rnd.randint(w // 4, 3 * w // 4), int(h * 0.62), int(u * 0.55)
        for k, col in enumerate([(255, 99, 99), (255, 170, 80), (255, 230, 90), (120, 210, 120), (100, 170, 255), (170, 120, 255)]):
            rk = rr - k * int(u * 0.03)
            d.arc([cx - rk, cy - rk, cx + rk, cy + rk], 180, 360, fill=col, width=int(u * 0.03))
    sx, sy, sr = rnd.choice([w // 7, w - w // 7]), int(h * 0.14), int(u * 0.09)
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 221, 89))
    d.arc([sx - sr * 0.5, sy - sr * 0.1, sx + sr * 0.5, sy + sr * 0.6], 20, 160, fill=(200, 120, 40), width=4)
    for ex in (-0.35, 0.35):
        d.ellipse([sx + sr * ex - 5, sy - sr * 0.25, sx + sr * ex + 5, sy - sr * 0.05], fill=(120, 70, 30))
    for _ in range(3):
        cx, cy = rnd.randint(0, w), rnd.randint(int(h * 0.08), int(h * 0.35))
        for dx in (-u * 0.05, 0, u * 0.05):
            d.ellipse([cx + dx - u * 0.06, cy - u * 0.04, cx + dx + u * 0.06, cy + u * 0.04], fill="white")
    for k, col in enumerate([(140, 215, 120), (100, 190, 100)]):
        base = int(h * (0.7 + 0.08 * k))
        ph = rnd.random() * 6
        pts = [(x, base - int(u * 0.05 * math.sin(x / (w / (2 + k)) + ph))) for x in range(0, w + 20, 20)]
        d.polygon(pts + [(w, h), (0, h)], fill=col)
    for _ in range(14):  # flowers
        fx, fy = rnd.randint(0, w), rnd.randint(int(h * 0.8), h)
        pc = rnd.choice(CLOTHES)
        for a in range(5):
            ang = a * 2 * math.pi / 5
            d.ellipse([fx + 9 * math.cos(ang) - 7, fy + 9 * math.sin(ang) - 7, fx + 9 * math.cos(ang) + 7, fy + 9 * math.sin(ang) + 7], fill=pc)
        d.ellipse([fx - 5, fy - 5, fx + 5, fy + 5], fill=(255, 230, 90))
    s = u / 720
    ground = int(h * 0.62)
    kx = rnd.randint(int(w * 0.25), int(w * 0.45))
    _kid(d, kx, ground - int(60 * s * 1.6), s * 1.6, rnd)
    _cat(d, kx + int(u * 0.33), ground + int(40 * s), s * 1.5, rnd)
    img.filter(ImageFilter.SMOOTH).save(out, "JPEG", quality=92)


def make_scene(prompt: str, style: str, w: int, h: int, seed: int, out: Path, offline: bool = False) -> Path:
    if offline or not ai_image(prompt, style, w, h, seed, out):
        fallback_image(prompt + str(seed), w, h, out)
    return out


def make_scenes(prompts: list[str], style: str, w: int, h: int, seed: int, outdir: Path, offline: bool = False) -> list[Path]:
    """All scenes in parallel (4 at a time) to keep the run fast."""
    from concurrent.futures import ThreadPoolExecutor
    outdir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(make_scene, p, style, w, h, seed + i, outdir / f"scene_{i:02d}.jpg", offline)
                for i, p in enumerate(prompts)]
        return [f.result() for f in futs]


def _font(fonts_dir: Path, family: str, size: int, lang: str = "") -> ImageFont.FreeTypeFont:
    """Pick a font that really has the glyphs: fontconfig by language first, then family name, then scan."""
    import shutil
    import subprocess
    if shutil.which("fc-match"):
        for pattern in ([f":lang={lang}:weight=bold"] if lang else []) + [f"{family}:bold"]:
            path = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, check=False).stdout.strip()
            if path and (lang or family.split()[-1].lower() in Path(path).stem.lower()):
                return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    key = family.replace(" ", "").lower()
    files = [f for f in sorted(fonts_dir.rglob("*")) if f.suffix.lower() in (".ttf", ".otf", ".ttc")]
    for want_bold in (True, False):
        for f in files:
            n = f.stem.replace("-", "").lower()
            if key in n and (not want_bold or "bold" in n):
                return ImageFont.truetype(str(f), size, layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.load_default(size)


def thumb_lines(title: str, width, max_w: int) -> list[str]:
    """At most 2 lines that fit `max_w` (`width(text)` measures). A long title keeps its first words: few, big words win."""
    lines, cur = [], ""
    for wd in title.split():
        test = (cur + " " + wd).strip()
        if width(test) > max_w and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = test
    return (lines + [cur])[:2]


def thumbnail(bg: Path, title: str, fonts_dir: Path, family: str, out: Path, lang: str = "") -> Path:
    """Bright picture + a few very big words: it is read at phone size, by a parent, in a second."""
    from PIL import ImageEnhance
    img = Image.open(bg).convert("RGB").resize((1280, 720))
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.35)).enhance(1.08)
    d = ImageDraw.Draw(img)
    size = 120
    font = _font(fonts_dir, family, size, lang)
    lines = thumb_lines(title, lambda t: d.textlength(t, font=font), 1150)
    y = 720 - 50 - len(lines) * (size + 14)
    for ln in lines:
        x = max(20, (1280 - d.textlength(ln, font=font)) / 2)
        d.text((x, y), ln, font=font, fill=(255, 236, 60), stroke_width=12, stroke_fill=(140, 30, 160))
        y += size + 14
    img.save(out, "JPEG", quality=90)
    return out
