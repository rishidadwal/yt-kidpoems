"""Picture-book look. Run: python -m pytest -q tests/test_picturebook.py   (no internet needed)"""
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src import picturebook as pb
from src import video, visuals


def _scene(tmp_path: Path, name: str = "scene_00.jpg", size=(320, 180)) -> Path:
    p = tmp_path / name
    visuals.fallback_image(name, *size, p)
    return p


def _wav(tmp_path: Path, secs: int = 6) -> Path:
    wav = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(secs), str(wav)], check=True)
    return wav


def _probe(path: Path, entries: str) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", entries,
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=False).stdout.strip()


# ---------------------------------------------------------------- pictures
def test_paper_is_deterministic_and_in_range():
    a, b = pb.paper_tooth(64, 48, 5), pb.paper_tooth(64, 48, 5)
    assert a.shape == (48, 64) and np.array_equal(a, b)
    assert a.min() >= 0 and a.max() <= 1 and a.std() > 0.05            # real grain, not flat
    assert not np.array_equal(a, pb.paper_tooth(64, 48, 6))


def test_paper_image_is_warm_off_white(tmp_path):
    out = pb.paper_image(64, 48, 1, tmp_path / "p.jpg")
    r, g, b = np.asarray(Image.open(out), np.float32).reshape(-1, 3).mean(axis=0)
    assert r > b + 8 and 200 < g < 250                                  # warm, light, not pure white


def test_stylize_writes_boil_frames_that_differ(tmp_path):
    src = _scene(tmp_path)
    frames = pb.stylize(src, seed=3)
    assert [f.name for f in frames] == [f"scene_00_pb{k}.jpg" for k in range(pb.BOIL_FRAMES)]
    arrs = [np.asarray(Image.open(f), np.int16) for f in frames]
    assert all(a.shape == (180, 320, 3) for a in arrs)
    assert np.abs(arrs[0] - arrs[1]).mean() > 1                          # the lines "boil"
    assert pb.boil_frames(frames[1]) == frames == pb.boil_frames(src)
    lonely = _scene(tmp_path, "scene_09.jpg")
    assert pb.boil_frames(lonely) == [lonely]


def test_outlines_are_indigo_never_black(tmp_path):
    page = np.asarray(pb.draw_page(Image.open(_scene(tmp_path, size=(480, 270))), seed=1), np.float32)
    dark = page[page.sum(axis=2) < 260]
    assert len(dark) > 50
    assert dark[:, 2].mean() > dark[:, 0].mean() + 15                    # blue wins: indigo crayon
    assert (page.sum(axis=2) < 30).mean() < 0.001                        # no true black


def test_stylize_keeps_unreadable_picture(tmp_path):
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not a picture")
    assert pb.stylize(bad, seed=1) == [bad]


def test_stylize_all_skips_animated_clips(tmp_path):
    still, clip = _scene(tmp_path), tmp_path / "scene_01.mp4"
    clip.write_bytes(b"")
    out = pb.stylize_all([still, clip], seed=2, frames=2)
    assert out == [tmp_path / "scene_00_pb0.jpg", clip] and (tmp_path / "scene_00_pb1.jpg").exists()


def test_font_for_scripts():
    assert pb.font_for("Noto Sans") == pb.HAND_FONT
    assert pb.font_for("Noto Sans Devanagari") == "Noto Sans Devanagari"   # keeps the glyphs it needs
    assert (pb.FONT_DIR / "PatrickHand-Regular.ttf").exists() and (pb.FONT_DIR / "OFL.txt").exists()


# ---------------------------------------------------------------- words
def test_picturebook_ass_is_handwritten_and_calm(tmp_path):
    ass = video.write_ass("Hi {x}", ["one two", "three"], [(1.6, 2.5), (3.0, 4.0)], "Noto Sans", 1280, 720,
                          tmp_path / "s.ass", look="picturebook")
    txt = ass.read_text(encoding="utf-8")
    assert "Style: Lyric,Patrick Hand" in txt and "{\\kf" in txt
    assert "\\p1" not in txt                                              # no floating stars/hearts
    assert "{x}" not in txt and txt.count("\\alpha&HFF&") == len("Hi (x)")  # title written letter by letter


def test_picturebook_ass_keeps_script_font(tmp_path):
    txt = video.write_ass("नमस्ते", ["एक दो"], [(1.6, 2.5)], "Noto Sans Devanagari", 1280, 720,
                          tmp_path / "s.ass", look="picturebook").read_text(encoding="utf-8")
    assert "Style: Lyric,Noto Sans Devanagari" in txt and "\\alpha&HFF&" not in txt  # no split conjuncts


def test_dance_keeps_beat_and_actions(tmp_path):
    txt = video.write_ass("T", ["a", "b"], [(1.6, 2.5), (3.0, 4.0)], "Noto Sans", 640, 360, tmp_path / "s.ass",
                          actions=["CLAP", "JUMP"], bpm=120, look="picturebook").read_text(encoding="utf-8")
    assert "CLAP!" in txt and "\\p1" in txt


# ---------------------------------------------------------------- video
def test_turn_frame_sweeps_from_old_to_new_page():
    a, b = np.full((4, 100, 3), 200, np.uint8), np.full((4, 100, 3), 50, np.uint8)
    assert np.abs(video._turn_frame(a, b, 1.0)[:, :90].astype(int) - 200).max() <= 1   # start: old page
    end = video._turn_frame(a, b, 0.0)
    assert abs(int(end[0, 99, 0]) - 50) <= 1 and end[0, 0, 0] < 50          # end: new page, shadow at the spine
    mid = video._turn_frame(a, b, 0.5)
    flap = mid[0, 55:63]
    assert (flap[:, 0] > 180).all() and (flap[:, 0] != flap[:, 2]).any()     # paper-coloured back of the page


def test_render_picturebook_landscape_with_page_turns(tmp_path):
    imgs = pb.stylize_all([_scene(tmp_path, f"scene_{i:02d}.jpg") for i in range(2)], seed=4, frames=2)
    times = [(1.6, 2.5), (3.0, 4.0)]
    ass = video.write_ass("T", ["a b", "c"], times, "Noto Sans", 320, 180, tmp_path / "s.ass", look="picturebook")
    out = video.render(imgs, ["a b", "c"], _wav(tmp_path), times, ass, pb.FONT_DIR, None, 0, 320, 180,
                       tmp_path / "o.mp4", seed=4, look="picturebook")
    assert _probe(out, "stream=width,height") == "320,180"
    assert abs(video.duration_of(out) - (4.0 + video.TAIL + 0.3)) < 0.3


def test_render_picturebook_short_with_animated_clip(tmp_path):
    clip = tmp_path / "scene_01.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24",
                    "-t", "2", "-pix_fmt", "yuv420p", str(clip)], check=True)
    imgs = [pb.stylize(_scene(tmp_path), seed=1, frames=2)[0], clip]
    times = [(1.6, 2.5), (3.0, 4.0)]
    ass = video.write_ass("T", ["a", "b"], times, "Noto Sans", 270, 480, tmp_path / "v.ass", look="picturebook")
    out = video.render(imgs, ["a", "b"], _wav(tmp_path), times, ass, pb.FONT_DIR, None, 0, 270, 480,
                       tmp_path / "s.mp4", seed=2, look="picturebook")
    assert _probe(out, "stream=width,height") == "270,480"


def test_render_rejects_unknown_look(tmp_path):
    with pytest.raises(ValueError):
        video.render([], [], tmp_path / "v.wav", [], tmp_path / "s.ass", tmp_path, None, 0, 32, 32,
                     tmp_path / "o.mp4", look="sparkly")


# ---------------------------------------------------------------- config
def test_look_and_art_style_from_config():
    from src.pipeline import art_style_for, look_of
    assert look_of({}) == "classic" and art_style_for({"art_style": "3D"}) == "3D"
    assert art_style_for({"look": "picturebook", "art_style": "3D"}) == pb.ART_STYLE
    assert art_style_for({"look": "PictureBook", "picturebook_art_style": "crayon"}) == "crayon"
    with pytest.raises(ValueError):
        look_of({"look": "sparkly"})
