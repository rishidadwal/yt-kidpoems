"""Run: python -m pytest -q   (no internet needed)"""
import subprocess
from pathlib import Path

import pytest

from src import poem as P
from src import video, visuals


def test_validate_rejects_bad_poems():
    with pytest.raises(P.PoemError):
        P._validate({"lines": ["too", "short"]})
    with pytest.raises(P.PoemError):
        P._validate({"lines": ["x" * 120] * 4})


def test_validate_pads_image_prompts():
    p = P._validate({"title": "T", "lines": [f"line {i}" for i in range(8)], "image_prompts": ["a"]})
    assert len(p["image_prompts"]) == 8  # one per line


def test_localise_keeps_line_count(monkeypatch):
    master = {"title": "T", "lines": [f"l{i}" for i in range(8)], "image_prompts": ["a", "b"]}
    monkeypatch.setattr(P, "_gemini", lambda prompt, model: {"title": "टी", "lines": ["x"] * 6})
    out = P.localise(master, "Hindi", "m")
    assert len(out["lines"]) == 8 and out["image_prompts"] == ["a", "b"]


def test_public_domain_and_topics_rotate():
    hist = {"done_topics": [], "done_rhymes": [], "videos": []}
    assert P.public_domain(hist)["lines"]
    first = P.next_topic(hist)
    hist["done_topics"].append(first)
    assert P.next_topic(hist) != first


def test_ass_escapes_and_times(tmp_path):
    ass = video.write_ass("A {b}", ["one two", "three"], [(1.2, 2.0), (2.5, 3.0)], "Noto Sans", 1280, 720, tmp_path / "s.ass")
    txt = ass.read_text(encoding="utf-8")
    assert txt.count(",Lyric,") == 2 and txt.count(",Title,") == 2 and "\\kf" in txt and ",Deco," in txt


def test_fallback_image_never_fails(tmp_path):
    out = tmp_path / "x.jpg"
    visuals.fallback_image("seed", 320, 180, out)
    assert out.stat().st_size > 1000


def test_render_small_video(tmp_path):
    img = tmp_path / "s.jpg"
    visuals.fallback_image("s", 320, 180, img)
    wav = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "6", str(wav)], check=True)
    times = [(1.2, 2.5), (3.0, 4.0)]
    ass = video.write_ass("T", ["a b", "c"], times, "Noto Sans", 320, 180, tmp_path / "s.ass")
    out = video.render([img], ["a b", "c"], wav, times, ass, Path("/usr/share/fonts"), None, 0, 320, 180, tmp_path / "o.mp4")
    assert out.stat().st_size > 5000


def test_broken_history_does_not_crash(tmp_path):
    from src.pipeline import load_history
    f = tmp_path / "history.json"
    f.write_text('{\n "done_topics": [],\n<<<<<<< HEAD\n', encoding="utf-8")
    h = load_history(f)
    assert h["videos"] == [] and (tmp_path / "history.broken.json").exists()


def test_music_track_is_generated(tmp_path):
    from src import music
    out = music.make_track(6.0, tmp_path / "m.wav", seed=3)
    assert out.stat().st_size > 6 * 44100  # ~6 s of 16-bit mono


def test_scene_durations_cover_timeline():
    from src.video import scene_durations
    times = [(1.6, 3.0), (3.4, 5.0), (5.4, 7.0)]
    d = scene_durations(3, times, 10.0)
    assert len(d) == 3 and abs(sum(d) - 10.0) < 0.01


def test_render_short_from_landscape(tmp_path):
    img = tmp_path / "s.jpg"
    visuals.fallback_image("s", 640, 360, img)
    wav = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "6", str(wav)], check=True)
    times = [(1.6, 2.5), (3.0, 4.0)]
    ass = video.write_ass("T", ["a b", "c"], times, "Noto Sans", 270, 480, tmp_path / "v.ass")
    out = video.render([img, img], ["a b", "c"], wav, times, ass, Path("/usr/share/fonts"), None, 0, 270, 480, tmp_path / "s.mp4")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True, check=False).stdout.strip()
    assert probe == "270,480"


# ---------------- Level 2 (Kaggle GPU) - all offline, Kaggle is mocked ----------------
def _clip(path, secs=2, w=320, h=180):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=24",
                    "-t", str(secs), "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_build_job_limits_and_languages():
    from src import gpu
    cfg = {"gpu": {"sing_languages": ["en", "fr"], "max_animated_scenes": 2}}
    job = gpu.build_job(cfg, {"en": {"lines": ["a", "b"]}, "hi": {"lines": ["c"]}}, ["p0", "p1", "p2"], 5)
    assert list(job["songs"]) == ["en"] and len(job["animate"]) == 2 and job["animate"][1]["image"] == "scene_01.jpg"


def test_gpu_not_configured_falls_back(monkeypatch, tmp_path):
    from src import gpu
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    r = gpu.run({"songs": {}, "animate": []}, [], tmp_path)
    assert not r.songs and not r.clips and "Level 1" in r.notes[0]


def test_gpu_run_parses_outputs(monkeypatch, tmp_path):
    import json as _j

    from src import gpu
    monkeypatch.setenv("KAGGLE_USERNAME", "me")
    monkeypatch.setenv("KAGGLE_KEY", "k")
    monkeypatch.setattr(gpu, "available", lambda: True)
    monkeypatch.setattr(gpu.time, "sleep", lambda s: None)

    def fake(*args, timeout=600):
        if args[:2] == ("datasets", "status"):
            return "ready"
        if args[:2] == ("kernels", "status"):
            return 'me/kidpoems-gpu has status "complete"'
        if args[:2] == ("kernels", "output"):
            out = Path(args[args.index("-p") + 1])
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=8", str(out / "song_en.wav")], check=True)
            (out / "times_en.json").write_text(_j.dumps([[1, 2], [3, 4]]))
            _clip(out / "clip_00.mp4")
            (out / "status.json").write_text(_j.dumps({"errors": ["clip 1: out of memory"]}))
        return ""
    monkeypatch.setattr(gpu, "_kaggle", fake)
    img = tmp_path / "s.jpg"
    visuals.fallback_image("x", 320, 180, img)
    job = {"songs": {"en": {"lines": ["a", "b"]}}, "animate": [{"index": 0, "image": "scene_00.jpg", "prompt": "p"},
                                                              {"index": 1, "image": "scene_01.jpg", "prompt": "p"}]}
    r = gpu.run(job, [img, img], tmp_path / "w")
    assert r.songs["en"][1] == [(1.0, 2.0), (3.0, 4.0)] and list(r.clips) == [0]
    assert any("out of memory" in n for n in r.notes)


def test_render_mixes_clips_and_pictures(tmp_path):
    img = tmp_path / "s.jpg"
    visuals.fallback_image("s", 320, 180, img)
    clip = _clip(tmp_path / "c.mp4", secs=1)                      # shorter than its scene -> must loop
    song = tmp_path / "song.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=330:d=7", str(song)], check=True)
    times = [(1.6, 3.0), (3.4, 5.0)]
    ass = video.write_ass("T", ["a b", "c"], times, "Noto Sans", 320, 180, tmp_path / "s.ass")
    out = video.render([clip, img], ["a b", "c"], song, times, ass, Path("/usr/share/fonts"), None, 0,
                       320, 180, tmp_path / "o.mp4", 1, total=7.0)
    assert abs(video.duration_of(out) - 7.0) < 0.3


# ---------------- publishing ----------------
def test_publish_settings_modes():
    import datetime as dt

    from src.pipeline import publish_settings
    assert publish_settings({"review_mode": True}) == ("private", None)
    assert publish_settings({"review_mode": False, "publish": {"mode": "public"}}) == ("public", None)
    utc = dt.UTC
    morning = dt.datetime(2026, 9, 26, 2, 0, tzinfo=utc)          # 07:30 IST
    pv, at = publish_settings({"review_mode": False, "publish": {"mode": "scheduled", "time_ist": "17:00"}}, morning)
    assert pv == "private" and at == "2026-09-26T11:30:00Z"       # 17:00 IST same day
    evening = dt.datetime(2026, 9, 26, 13, 0, tzinfo=utc)         # 18:30 IST -> tomorrow
    assert publish_settings({"review_mode": False, "publish": {"mode": "scheduled", "time_ist": "17:00"}}, evening)[1] == "2026-09-27T11:30:00Z"


def test_quality_gate(tmp_path):
    from src.pipeline import quality_ok
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=pink:s=320x180:d=10", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=mono", "-t", "10", "-shortest", str(silent)], check=True)
    assert quality_ok(silent)[0] is False
    good = tmp_path / "good.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=pink:s=320x180:d=10", "-f", "lavfi",
                    "-i", "sine=f=440:d=10", "-shortest", str(good)], check=True)
    assert quality_ok(good) == (True, "ok")


def test_upload_sets_publish_at(tmp_path):
    from src import upload as U
    captured = {}

    class Req:
        def next_chunk(self):
            return None, {"id": "VID"}

    class Videos:
        def insert(self, part, body, media_body):
            captured.update(body)
            return Req()

    class YT:
        def videos(self): return Videos()
        def thumbnails(self): raise AssertionError("no thumb given")

    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 100)
    assert U.upload(YT(), f, None, "T", "D", ["t"], "en", "private", "2026-09-26T11:30:00Z") == "VID"
    st = captured["status"]
    assert st["publishAt"] == "2026-09-26T11:30:00Z" and st["selfDeclaredMadeForKids"] is True and st["containsSyntheticMedia"] is True


# ---------------- dance mode ----------------
def test_builtin_dance_is_catchy_and_complete():
    d = P.builtin_dance(7)
    assert d["mode"] == "dance" and len(d["lines"]) == len(d["actions"]) == len(d["image_prompts"]) == 12
    assert d["lines"].count(d["hook"]) >= 5 and all(a in P.ACTIONS for a in d["actions"])


def test_mode_alternates_by_day():
    import datetime as dt

    from src.pipeline import todays_mode
    a, b = todays_mode({"content_mode": "alternate"}, dt.date(2026, 9, 26)), todays_mode({"content_mode": "alternate"}, dt.date(2026, 9, 27))
    assert {a, b} == {"poem", "dance"} and todays_mode({"content_mode": "dance"}) == "dance"


def test_dance_music_and_beat_effects(tmp_path):
    from src import music
    assert music.pick_bpm(5, "dance") in (124, 126, 128)
    assert music.make_track(4, tmp_path / "d.wav", 5, "dance").stat().st_size > 4 * 44100
    ass = video.write_ass("T", ["Zum zum!", "Clap!"], [(1.6, 2.5), (3, 4)], "Noto Sans", 1920, 1080,
                          tmp_path / "d.ass", 1, ["CLAP", "JUMP"], 126).read_text(encoding="utf-8")
    assert "CLAP!" in ass and ass.count(",Action,") == 2 and "pos(0,0)" in ass


def test_compilation_concat(tmp_path):
    from src.compile import concat
    parts = []
    for i in range(3):
        f = tmp_path / f"p{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=25:d=2", "-f", "lavfi",
                        "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
        parts.append(f)
    out = concat(parts, tmp_path / "all.mp4")
    assert 5.5 < video.duration_of(out) < 6.6


class _Resp:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status_code, self.ok, self.content = status, status == 200, body
        self.headers = {"content-type": "image/jpeg" if status == 200 else "application/json"}


def _jpeg(tmp_path: Path) -> bytes:
    import io

    import numpy as np
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (300, 400, 3), dtype=np.uint8)).save(buf, "JPEG")
    return buf.getvalue()


def test_ai_image_waits_out_free_rate_limit(monkeypatch, tmp_path):
    """Pollinations free tier: 1 image / 45 s per IP, else HTTP 402. Must wait and retry, not fall back."""
    replies = [_Resp(402), _Resp(200, _jpeg(tmp_path))]
    sleeps: list[float] = []
    monkeypatch.setattr(visuals.requests, "get", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(visuals.time, "sleep", sleeps.append)
    monkeypatch.setattr(visuals.time, "monotonic", lambda: 1000.0)   # frozen clock: exact, not flaky
    monkeypatch.setattr(visuals, "_last_call", [0.0])
    assert visuals.ai_image("cat", "style", 400, 300, 1, tmp_path / "a.jpg")
    assert max(sleeps) >= visuals.MIN_GAP_S   # waited a full rate-limit window before the retry


def test_ai_image_spaces_calls_and_gives_up_cleanly(monkeypatch, tmp_path):
    clock = [1000.0]
    sleeps: list[float] = []
    monkeypatch.setattr(visuals.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(visuals.time, "sleep", lambda s: (sleeps.append(s), clock.__setitem__(0, clock[0] + s)))
    monkeypatch.setattr(visuals, "_last_call", [clock[0]])   # a call just happened
    monkeypatch.setattr(visuals.requests, "get", lambda *a, **k: _Resp(500))
    assert not visuals.ai_image("cat", "style", 400, 300, 1, tmp_path / "b.jpg", retries=2)
    assert sleeps[0] >= visuals.MIN_GAP_S     # first request waited for the gap
    assert not (tmp_path / "b.jpg").exists()  # nothing half-written -> caller uses the fallback picture


# ---------------------------------------------------------------- watchability (hook, focus, thumbnail)
def test_dance_videos_can_use_their_own_look():
    from src.pipeline import art_style_for, look_of
    cfg = {"look": "picturebook", "dance_look": "classic", "art_style": "3D", "picturebook_art_style": "crayon"}
    assert look_of(cfg) == "picturebook" and look_of(cfg, dance=True) == "classic"
    assert art_style_for(cfg) == "crayon" and art_style_for(cfg, dance=True) == "3D"
    assert look_of({"look": "picturebook"}, dance=True) == "picturebook"   # no dance_look -> same as look
    with pytest.raises(ValueError):
        look_of({"dance_look": "sparkly"}, dance=True)


def test_builtin_dance_pictures_have_one_clear_star():
    cast = "Pip, a toddler in a yellow onesie; Gigi, a baby giraffe; and Quack, a little duckling"
    d = P.builtin_dance(7, cast)
    solo = [p for p, ln in zip(d["image_prompts"], d["lines"]) if ln != d["hook"]]
    assert solo and all("looking at the camera" in p for p in d["image_prompts"])
    assert all(sum(n in p for n in ("Pip", "Gigi", "Quack")) == 1 for p in solo)   # one star per action picture
    assert {n for n in ("Pip", "Gigi", "Quack") if any(n in p for p in solo)} == {"Pip", "Gigi", "Quack"}


def test_cast_members_handles_plain_cast():
    assert P.cast_members("two happy kids and a kitten") == ["two happy kids and a kitten"]
    assert P.cast_members("A, a cat; and B, a dog") == ["A, a cat", "B, a dog"]


@pytest.mark.parametrize("writer", ["write_original", "write_dance"])
def test_ai_prompts_ask_for_a_hook_and_clear_pictures(monkeypatch, writer):
    seen: list[str] = []

    def fake(prompt, model):
        seen.append(prompt)
        return {"title": "T", "hook": "zim zam", "lines": [f"line {i}" for i in range(12)], "image_prompts": ["a"] * 12}
    monkeypatch.setattr(P, "_gemini", fake)
    getattr(P, writer)("colours", "m", "Pip, a toddler")
    text = seen[0]
    assert "FIRST line" in text and P.PICTURE_RULES in text and P.SAFETY_RULES in text
    assert "Pip, a toddler" in text and "{CAST}" not in text


def test_thumbnail_is_bright_with_big_short_text(tmp_path):
    from PIL import Image, ImageStat
    src = tmp_path / "bg.jpg"
    Image.new("RGB", (1920, 1080), (120, 150, 110)).save(src)
    out = visuals.thumbnail(src, "Pom pom bo bo! Dance Song for happy little kids everywhere", Path("assets/fonts"),
                            "Noto Sans", tmp_path / "t.jpg")
    im = Image.open(out)
    assert im.size == (1280, 720)
    sat = lambda i: ImageStat.Stat(i.convert("HSV")).mean[1]
    assert sat(im.crop((0, 0, 1280, 200))) > sat(Image.open(src).resize((1280, 720)).crop((0, 0, 1280, 200)))
    assert len(visuals.thumb_lines("one two three four five six seven", lambda s: len(s) * 100, 1150)) <= 2


def test_gemini_errors_never_contain_the_api_key(monkeypatch):
    """requests puts the full URL (with ?key=...) in its error text; that text ends up in data/last_run.json."""
    def boom(*a, **k):
        raise P.requests.HTTPError("401 Client Error: Unauthorized for url: https://x/y:generateContent?key=AQ.SECRET123")
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.SECRET123")
    monkeypatch.setattr(P.requests, "post", boom)
    monkeypatch.setattr(P.time, "sleep", lambda s: None)
    with pytest.raises(P.PoemError) as ei:
        P._gemini("hi", "m", retries=2)
    assert "SECRET123" not in str(ei.value) and "key=***" in str(ei.value)


def test_gemini_key_goes_in_a_header_not_the_url(monkeypatch):
    seen: dict = {}

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]}

    def fake_post(url, **kw):
        seen.update(url=url, **kw)
        return R()
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.SECRET123")
    monkeypatch.setattr(P.requests, "post", fake_post)
    assert P._gemini("hi", "m") == {"ok": 1}
    assert seen["headers"]["x-goog-api-key"] == "AQ.SECRET123"
    assert "SECRET123" not in seen["url"] and "key" not in (seen.get("params") or {})


def test_youtube_token_script_needs_no_file_and_hides_secrets(monkeypatch):
    import get_youtube_token as G
    cfg = G.client_config("123.apps.googleusercontent.com", "s3cret")
    assert cfg["installed"]["client_secret"] == "s3cret"
    with pytest.raises(ValueError):
        G.client_config("not-a-client-id", "s3cret")
    with pytest.raises(ValueError):
        G.client_config("123.apps.googleusercontent.com", "")
    calls: list = []
    monkeypatch.setattr(G.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)))
    G.set_secret("o/r", "YT_CLIENT_SECRET", "s3cret")
    cmd, kw = calls[0]
    assert "s3cret" not in " ".join(cmd) and kw["input"] == "s3cret" and kw["timeout"]
    assert G.main(["x"]) == 2   # usage error, nothing asked


def test_gpu_accepts_new_kaggle_api_token(monkeypatch):
    from src import gpu
    monkeypatch.setattr(gpu.shutil, "which", lambda n: "/bin/kaggle")
    for v in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_API_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KAGGLE_USERNAME", "me")
    assert not gpu.available()                      # username alone is not enough
    monkeypatch.setenv("KAGGLE_API_TOKEN", "t")
    assert gpu.available()                          # new token type (kaggle CLI >= 1.8)
    monkeypatch.delenv("KAGGLE_API_TOKEN")
    monkeypatch.setenv("KAGGLE_KEY", "k")
    assert gpu.available()                          # legacy key still works


def test_kaggle_creates_dataset_when_version_is_forbidden(monkeypatch, tmp_path):
    """A brand-new account has no dataset yet; Kaggle answers 403 (not 404) to 'version'."""
    from src import gpu
    calls: list[str] = []

    def fake(*args, **kw):
        calls.append(args[1])
        if args[1] == "version":
            raise RuntimeError("kaggle datasets version failed: 403 Client Error: Forbidden for url: ...")
        return "ready"
    monkeypatch.setattr(gpu, "_kaggle", fake)
    gpu._upload_dataset("me", tmp_path)
    assert calls[:2] == ["version", "create"]


def test_gemini_switches_to_a_live_model_when_the_name_is_retired(monkeypatch):
    posted: list[str] = []

    class R:
        def __init__(self, code, data=None): self.status_code, self._d = code, data or {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise P.requests.HTTPError(f"{self.status_code} Client Error")
        def json(self): return self._d

    def fake_post(url, **kw):
        posted.append(url)
        if "old-flash" in url:
            return R(404)
        return R(200, {"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]})
    models = {"models": [
        {"name": "models/gemini-9.0-flash-image", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.1-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.2-flash-lite", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.0-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-9.0-pro", "supportedGenerationMethods": ["generateContent"]},
    ]}
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(P.requests, "post", fake_post)
    monkeypatch.setattr(P.requests, "get", lambda url, **kw: R(200, models))
    monkeypatch.setattr(P.time, "sleep", lambda s: None)
    assert P._gemini("hi", "old-flash") == {"ok": 1}
    assert "gemini-3.1-flash:generateContent" in posted[-1]   # newest plain flash, not lite/image/pro
