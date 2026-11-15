"""Picture-book look: turns any scene picture into a crayon-on-paper storybook page. Free and offline (Pillow + numpy).

The techniques (not code) come from the MIT-licensed lemo-opuscar "crayon-book" style guide:
- warm off-white paper whose grain ("tooth") is anchored to the page,
- wax that only sticks to the peaks of the tooth; more pressure = more paper covered,
- flat, bright crayon colours, coloured in with visible back-and-forth hatching that overshoots the outline,
- outlines in one dark colour (indigo), never black, that "boil" because every drawing is redrawn,
- a paper page turn between pages (see video.py).

`stylize()` writes a few slightly different drawings of the same page; the video steps through them at 12 fps.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)

PAPER = (244, 239, 227)         # warm off-white page
INK = (46, 42, 92)              # outline crayon: dark indigo, never black
CORAL = (232, 107, 90)          # accent crayon (sung karaoke words)
BOIL_FRAMES = 3                 # redrawn versions of every page (line boil)
BOIL_FPS = 12                   # drawings change on twos, like hand animation
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "handfont"
HAND_FONT = "Patrick Hand"      # OFL handwriting face (Latin scripts only)
LATIN_FONTS = {"Noto Sans", "Noto Serif"}

ART_STYLE = ("children's picture book illustration drawn in wax crayon with a soft watercolour wash on warm off-white "
             "textured paper, simple chunky rounded shapes, thick dark indigo outlines, a small box of bright crayon "
             "colours, plenty of bare paper, child-like perspective, cosy and tender, cute characters with dot eyes and "
             "pink cheeks, storybook page, 16:9, no text, no letters, no watermark")


def font_for(lang_font: str) -> str:
    """Handwriting face for Latin-script languages; other scripts keep their own Noto font (it has the glyphs)."""
    return HAND_FONT if lang_font.strip() in LATIN_FONTS else lang_font


# ---------------------------------------------------------------- noise helpers
def _noise(h: int, w: int, cell_y: float, cell_x: float, rng: np.random.Generator) -> np.ndarray:
    """Smooth value noise in [0, 1]: a random grid upscaled bicubically."""
    gh, gw = max(2, math.ceil(h / cell_y) + 1), max(2, math.ceil(w / cell_x) + 1)
    grid = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8))
    up = grid.resize((int(gw * cell_x), int(gh * cell_y)), Image.BICUBIC)
    return np.asarray(up, dtype=np.float32)[:h, :w] / 255.0


def paper_tooth(w: int, h: int, seed: int) -> np.ndarray:
    """Paper grain in [0, 1]: three octaves of fine noise plus horizontal fibres. Same seed = same page."""
    rng = np.random.default_rng(seed)
    t = (0.45 * _noise(h, w, 1.5, 1.5, rng) + 0.35 * _noise(h, w, 4, 4, rng)
         + 0.2 * _noise(h, w, 11, 11, rng) + 0.25 * _noise(h, w, 2, 60, rng))
    t -= t.min()
    return t / max(float(t.max()), 1e-6)


def paper_rgb(w: int, h: int, seed: int, tooth: np.ndarray | None = None) -> np.ndarray:
    """Bare paper as float RGB (h, w, 3): tooth, soft mottling (+-2 %) and a warm vignette."""
    tooth = paper_tooth(w, h, seed) if tooth is None else tooth
    rng = np.random.default_rng(seed + 1)
    mottle = 1 + 0.04 * (_noise(h, w, max(h / 6, 2), max(w / 8, 2), rng) - 0.5)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    vig = 1 - 0.10 * np.clip(r - 0.55, 0, None) ** 1.5
    shade = (0.955 + 0.055 * tooth) * mottle * vig
    return np.asarray(PAPER, np.float32)[None, None, :] * shade[..., None]


def paper_image(w: int, h: int, seed: int, out: Path) -> Path:
    Image.fromarray(np.clip(paper_rgb(w, h, seed), 0, 255).astype(np.uint8)).save(out, "JPEG", quality=92)
    return out


def _wobble(arr: np.ndarray, rng: np.random.Generator, amp: float, cell: float) -> np.ndarray:
    """Shift pixels by a low-frequency hand wobble of up to `amp` px (nearest pixel, cheap)."""
    h, w = arr.shape[:2]
    dx = np.rint((_noise(h, w, cell, cell, rng) - 0.5) * 2 * amp).astype(np.int32)
    dy = np.rint((_noise(h, w, cell, cell, rng) - 0.5) * 2 * amp).astype(np.int32)
    yy, xx = np.mgrid[0:h, 0:w]
    return arr[np.clip(yy + dy, 0, h - 1), np.clip(xx + dx, 0, w - 1)]


def _coverage(tooth: np.ndarray, pressure: np.ndarray, soft: float = 0.07) -> np.ndarray:
    """Wax adhesion: wax lands where tooth > 1 - pressure (soft edge). Light pressure = speckled peaks only."""
    return np.clip((tooth - (1 - pressure) + soft) / (2 * soft), 0, 1)


# ---------------------------------------------------------------- the page
def flatten(img: Image.Image) -> Image.Image:
    """Simple, bright colour areas: small details and soft 3D shading are smoothed away, accents are kept.

    Done at half size (fast, and a crayon can't draw finer than that anyway)."""
    w, h = img.size
    small = img.convert("RGB").resize((max(2, w // 2), max(2, h // 2)), Image.BILINEAR)
    small = small.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MedianFilter(5))
    small = ImageEnhance.Color(small).enhance(1.18)
    return ImageOps.posterize(small, 4).filter(ImageFilter.MedianFilter(3)).resize((w, h), Image.BILINEAR)


def draw_page(img: Image.Image, seed: int, variant: int = 0) -> Image.Image:
    """One crayon drawing of `img`. `variant` changes only the hand (wobble, hatching), never the paper."""
    img = img.convert("RGB")
    w, h = img.size
    u = min(w, h) / 1080                       # scale strokes with resolution
    tooth = paper_tooth(w, h, seed)            # anchored to the page: identical for every variant
    paper = paper_rgb(w, h, seed, tooth)
    rng = np.random.default_rng(seed * 31 + variant * 7919 + 17)

    flat = np.asarray(flatten(img), np.float32)
    # colouring in: wavy back-and-forth hatching rows with paper showing between them, plus a lighter cross pass;
    # the colour layer is wobbled on its own, so it overshoots the outline by a few pixels like a real child's
    fill = _wobble(flat, rng, amp=max(1.0, 3.0 * u), cell=max(8.0, 45 * u))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a1, a2 = math.radians(rng.uniform(20, 35)), math.radians(rng.uniform(-65, -50))
    period = max(3.0, 7 * u)
    bend = 2.2 * _noise(h, w, max(8.0, 70 * u), max(8.0, 70 * u), rng)       # rows drift like a hand's
    ph1, ph2 = rng.uniform(0, 2 * math.pi, 2)
    hatch = 0.5 + 0.5 * np.sin((xx * math.cos(a1) + yy * math.sin(a1)) / period * 2 * math.pi + ph1 + bend)
    cross = 0.5 + 0.5 * np.sin((xx * math.cos(a2) + yy * math.sin(a2)) / (period * 1.6) * 2 * math.pi + ph2 - bend)
    patchy = _noise(h, w, max(6.0, 30 * u), max(6.0, 30 * u), rng)           # pressure changes stroke to stroke
    lum = fill.mean(axis=2) / 255
    pressure = 0.40 + 0.30 * hatch + 0.12 * cross + 0.16 * (patchy - 0.5) + 0.16 * (1 - lum)  # dark crayon = heavier
    cov = _coverage(tooth, np.clip(pressure, 0, 1), soft=0.09)[..., None]
    wax = fill * (1.0 - 0.07 * cov)            # heavy wax reads a touch darker
    page = paper * (1 - cov) + wax * cov

    # outlines: along the big colour changes, thickened, wobbled differently from the colouring, in indigo
    smooth = np.asarray(Image.fromarray(flat.astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5 * u)), np.float32)
    grad = (np.abs(np.diff(smooth, axis=0, prepend=smooth[:1])).sum(axis=2)
            + np.abs(np.diff(smooth, axis=1, prepend=smooth[:, :1])).sum(axis=2))
    edge = grad > max(28.0, float(np.percentile(grad, 90)))
    e_img = Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    line = np.asarray(e_img.filter(ImageFilter.GaussianBlur(1.0 * u)), np.float32) / 255
    line = _wobble(line, rng, amp=max(1.0, 1.5 * u), cell=max(12.0, 80 * u))
    ink_cov = (_coverage(tooth, np.clip(0.55 + 0.45 * line, 0, 1)) * np.clip(line * 1.6, 0, 1))[..., None]
    page = page * (1 - ink_cov) + np.asarray(INK, np.float32) * ink_cov

    # emboss the paper (lit from the top-left), less where wax filled the tooth
    relief = tooth - np.roll(np.roll(tooth, 1, axis=0), 1, axis=1)
    total = np.clip(cov[..., 0] + ink_cov[..., 0], 0, 1)
    page *= (1 + 0.07 * relief * (1 - 0.7 * total))[..., None]
    return Image.fromarray(np.clip(page, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- files
def frame_path(src: Path, k: int) -> Path:
    return src.with_name(f"{src.stem}_pb{k}.jpg")


def boil_frames(path: Path) -> list[Path]:
    """All redrawn versions of a stylised page (given any one of them); [path] if it has none."""
    stem = path.stem
    base = stem[: stem.rfind("_pb")] if "_pb" in stem else stem
    frames = sorted(path.parent.glob(f"{base}_pb[0-9].jpg"))
    return frames or [path]


def stylize(src: Path, seed: int, frames: int = BOIL_FRAMES) -> list[Path]:
    """Write `frames` crayon drawings of `src` next to it. Never fails the run: a bad picture is used as-is."""
    try:
        with Image.open(src) as im:
            img = im.convert("RGB")
    except (OSError, UnidentifiedImageError) as e:
        log.warning("picture-book: can't read %s (%s) - using it unchanged", src, e)
        return [src]
    out = []
    for k in range(max(1, frames)):
        p = frame_path(src, k)
        draw_page(img, seed, k).save(p, "JPEG", quality=93)
        out.append(p)
    return out


def stylize_all(scenes: list[Path], seed: int, frames: int = BOIL_FRAMES) -> list[Path]:
    """Stylise every still picture (in parallel). Animated clips (.mp4) pass through; video.py gives them paper."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(stylize, s, seed + i, frames) if s.suffix.lower() != ".mp4" else None
                for i, s in enumerate(scenes)]
        return [f.result()[0] if f else s for f, s in zip(futs, scenes)]
