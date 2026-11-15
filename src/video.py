"""Assemble the video with FFmpeg.

One picture per lyric line, each with its own camera move (zoom in/out, pan, gentle bounce), smooth
transitions between scenes, bouncing karaoke lyrics, floating stars/hearts, a pop-in title card,
an upbeat backing track and loudness normalisation. Shorts reuse the landscape pictures over a
blurred background, so no extra images are needed.
"""
from __future__ import annotations

import random
import subprocess
from pathlib import Path

import numpy as np

from . import picturebook as pb

FPS = 25
LEAD = 0.6   # short title flash: the song must start within the first second (hook)
GAP = 0.35   # pause between lines
TAIL = 2.5   # ending card
XF = 0.4     # transition length (seconds)
PB_XF = 0.9  # picture-book page turn (seconds)
PAPER_SLOT = "<paper>"  # replaced by the render's paper sheet
LOOKS = ("classic", "picturebook")
TRANSITIONS = ["fade", "slideleft", "slideright", "circleopen", "smoothleft", "wipeup", "radial", "dissolve"]


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)[:1500]}\n{p.stderr[-2500:]}")


def _ts(t: float) -> str:
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def build_voice_track(clips: list[tuple[Path, float]], workdir: Path) -> tuple[Path, list[tuple[float, float]]]:
    """Joins line clips with pauses. Returns (wav, [(start, end) per line])."""
    times, t = [], LEAD
    lead = workdir / "lead.wav"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(LEAD), lead.as_posix()])
    for i, (mp3, dur) in enumerate(clips):
        seg = workdir / f"seg_{i:02d}.wav"
        _run(["ffmpeg", "-y", "-i", mp3.as_posix(), "-af", f"aresample=24000,apad=pad_dur={GAP}",
              "-ac", "1", seg.as_posix()])
        times.append((t, t + dur))
        t += dur + GAP
    tail = workdir / "tail.wav"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(TAIL), tail.as_posix()])
    lst = workdir / "voice.txt"
    names = [lead.name] + [f"seg_{i:02d}.wav" for i in range(len(clips))] + [tail.name]
    lst.write_text("".join(f"file '{n}'\n" for n in names))
    voice = workdir / "voice.wav"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.as_posix(), "-c", "copy", voice.as_posix()])
    return voice, times


# ---------------------------------------------------------------- subtitles & decorations (ASS)
STAR = "m 0 -10 l 3 -3 10 -3 4 2 6 10 0 5 -6 10 -4 2 -10 -3 -3 -3"
HEART = "m 0 3 b -9 -4 -6 -12 0 -6 b 6 -12 9 -4 0 3"
DECO_COLORS = ["&H0069E0FF&", "&H00B469FF&", "&H00FFB4A0&", "&H0080FFB4&", "&H00FFFFFF&", "&H009BE6FF&"]


def _decorations(total: float, w: int, h: int, rnd: random.Random) -> list[str]:
    ev, t = [], 0.3
    while t < total - 1:
        shape = rnd.choice([STAR, STAR, HEART])
        sc = rnd.randint(int(h / 4), int(h / 2.2))                 # percent scale of the 20-px shape
        x = rnd.randint(int(w * 0.05), int(w * 0.95))
        y0, y1 = rnd.randint(int(h * 0.55), h), rnd.randint(0, int(h * 0.4))
        life = rnd.uniform(2.5, 4.0)
        col = rnd.choice(DECO_COLORS)
        ev.append(f"Dialogue: 1,{_ts(t)},{_ts(t + life)},Deco,,0,0,0,,"
                  f"{{\\an5\\move({x},{y0},{x + rnd.randint(-80, 80)},{y1})\\fscx{sc}\\fscy{sc}\\1c{col}\\bord2\\3c&H00FFFFFF&"
                  f"\\alpha&H40&\\fad(400,600)\\t(0,{int(life * 1000)},\\frz{rnd.choice([-360, 360])})\\p1}}{shape}{{\\p0}}")
        t += rnd.uniform(0.35, 0.7)
    return ev


def _beat_events(total: float, bpm: int, w: int, h: int, rnd: random.Random) -> list[str]:
    """Dance mode: a burst of stars on every 2nd beat + a soft white flash on every bar."""
    ev, beat, t, k = [], 60 / bpm, LEAD, 0
    while t < total - 0.5:
        if k % 2 == 0:
            x, y = rnd.choice([(int(w * 0.12), int(h * 0.2)), (int(w * 0.88), int(h * 0.2)),
                               (int(w * 0.1), int(h * 0.55)), (int(w * 0.9), int(h * 0.55))])
            col = rnd.choice(DECO_COLORS)
            ms = int(beat * 900)
            ev.append(f"Dialogue: 1,{_ts(t)},{_ts(t + beat)},Deco,,0,0,0,,{{\\an5\\pos({x},{y})\\1c{col}\\bord3\\3c&H00FFFFFF&"
                      f"\\fscx{h // 6}\\fscy{h // 6}\\t(0,{ms // 3},\\fscx{h // 2}\\fscy{h // 2})\\t({ms // 3},{ms},\\alpha&HFF&)\\p1}}{STAR}{{\\p0}}")
        if k % 4 == 0:
            ev.append(f"Dialogue: 0,{_ts(t)},{_ts(t + 0.12)},Deco,,0,0,0,,{{\\an7\\pos(0,0)\\1c&H00FFFFFF&\\alpha&HC8&\\bord0\\p1}}"
                      f"m 0 0 l {w} 0 {w} {h} 0 {h}{{\\p0}}")
        t += beat
        k += 1
    return ev


def write_ass(title: str, lines: list[str], times: list[tuple[float, float]], font: str,
              w: int, h: int, out: Path, seed: int = 0, actions: list[str] | None = None,
              bpm: int | None = None, look: str = "classic") -> Path:
    if look == "picturebook":
        return _write_ass_picturebook(title, lines, times, font, w, h, out, seed, actions, bpm)
    landscape = w > h
    fs = int(h * (0.075 if landscape else 0.048))
    tfs = int(fs * 1.35)
    margin_v = int(h * (0.07 if landscape else 0.2))
    rnd = random.Random(seed)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,{font},{fs},&H0000E1FF,&H00FFFFFF,&H007B2ADD,&H96000000,1,0,0,0,100,100,1,0,1,{max(5, fs // 9)},4,2,60,60,{margin_v},1
Style: Title,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H007B2ADD,&H96000000,1,0,0,0,100,100,1,0,1,{max(6, tfs // 8)},5,5,60,60,0,1
Style: Action,{font},{int(tfs * 1.25)},&H0000E1FF,&H00FFFFFF,&H00AF3481,&H96000000,1,0,0,0,100,100,2,0,1,{max(7, tfs // 7)},6,8,60,60,{int(h * 0.1)},1
Style: Deco,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pop = "\\fscx40\\fscy40\\t(0,350,\\fscx115\\fscy115)\\t(350,550,\\fscx100\\fscy100)"
    ev = [f"Dialogue: 2,{_ts(0.1)},{_ts(LEAD)},Title,,0,0,0,,{{\\fad(0,250){pop}}}{_esc(title)}"]
    for line, (s, e) in zip(lines, times):
        words = line.split() or [line]
        cs = max(1, int((e - s) * 100 / len(words)))
        karaoke = "".join(f"{{\\kf{cs}}}{_esc(wd)} " for wd in words).strip()
        bounce = "\\fscx80\\fscy80\\t(0,160,\\fscx106\\fscy106)\\t(160,280,\\fscx100\\fscy100)"
        ev.append(f"Dialogue: 2,{_ts(s - 0.12)},{_ts(e + 0.25)},Lyric,,0,0,0,,{{\\fad(80,120){bounce}}}{karaoke}")
    if actions:  # dance mode: big bouncing action word ("CLAP!") for each line
        for act, (s, e) in zip(actions, times):
            wob = "\\frz-8\\t(0,300,\\frz8\\fscx120\\fscy120)\\t(300,600,\\frz-4\\fscx100\\fscy100)"
            ev.append(f"Dialogue: 3,{_ts(s)},{_ts(e + 0.2)},Action,,0,0,0,,{{\\fad(60,150){wob}}}{_esc(act)}!")
    end = times[-1][1] if times else LEAD
    if bpm:
        ev += _beat_events(end + TAIL, bpm, w, h, rnd)
    ev.append(f"Dialogue: 2,{_ts(end + 0.4)},{_ts(end + TAIL)},Title,,0,0,0,,{{{pop}}}♪ ♥ ♪")
    ev += _decorations(end + TAIL, w, h, rnd)
    out.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return out


def _ass_colour(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    r, g, b = rgb
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _write_ass_picturebook(title: str, lines: list[str], times: list[tuple[float, float]], font: str,
                           w: int, h: int, out: Path, seed: int, actions: list[str] | None, bpm: int | None) -> Path:
    """Storybook words: handwriting (Latin scripts) in indigo crayon on a patch of paper, sung words turn coral.

    The title is written letter by letter; no glossy stars or hearts (the page is the decoration)."""
    landscape = w > h
    hand = pb.font_for(font)
    fs = int(h * (0.082 if landscape else 0.052))
    tfs = int(fs * 1.4)
    margin_v = int(h * (0.06 if landscape else 0.2))
    ink, coral, paper = _ass_colour(pb.INK), _ass_colour(pb.CORAL), _ass_colour(pb.PAPER, 0x28)
    rnd = random.Random(seed)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,{hand},{fs},{coral},{ink},{paper},&H00000000,0,0,0,0,100,100,1,0,3,{max(4, fs // 5)},0,2,80,80,{margin_v},1
Style: Title,{hand},{tfs},{ink},{ink},{paper},&H00000000,0,0,0,0,100,100,2,0,3,{max(5, tfs // 5)},0,5,80,80,0,1
Style: Action,{hand},{int(tfs * 1.2)},{coral},{coral},{paper},&H00000000,0,0,0,0,100,100,2,0,3,{max(5, tfs // 5)},0,8,80,80,{int(h * 0.08)},1
Style: Deco,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def tilt() -> str:
        return f"\\frz{rnd.uniform(-1.6, 1.6):.1f}"

    def written(text: str, start_ms: int, ms_per_letter: int) -> str:
        """Letter-by-letter writing. Only for the handwriting face: splitting complex scripts breaks their shaping."""
        if hand != pb.HAND_FONT:
            return f"{{\\fad(300,0)}}{_esc(text)}"
        return "".join(f"{{\\alpha&HFF&\\t({start_ms + k * ms_per_letter},{start_ms + k * ms_per_letter + 1},\\alpha&H00&)}}{_esc(c)}"
                       for k, c in enumerate(text))

    ev = [f"Dialogue: 2,{_ts(0.1)},{_ts(LEAD)},Title,,0,0,0,,{{{tilt()}}}{written(title, 0, max(25, min(60, 900 // max(1, len(title)))))}"]
    for line, (s, e) in zip(lines, times):
        words = line.split() or [line]
        cs = max(1, int((e - s) * 100 / len(words)))
        karaoke = "".join(f"{{\\kf{cs}}}{_esc(wd)} " for wd in words).strip()
        ev.append(f"Dialogue: 2,{_ts(s - 0.3)},{_ts(e + 0.3)},Lyric,,0,0,0,,{{\\fad(150,150){tilt()}}}{karaoke}")
    if actions:  # dance mode: the action word, scribbled big
        for act, (s, e) in zip(actions, times):
            ev.append(f"Dialogue: 3,{_ts(s)},{_ts(e + 0.2)},Action,,0,0,0,,{{\\fad(60,150){tilt()}\\fscx90\\fscy90"
                      f"\\t(0,250,\\fscx110\\fscy110)\\t(250,500,\\fscx100\\fscy100)}}{_esc(act)}!")
    end = times[-1][1] if times else LEAD
    if bpm:
        ev += _beat_events(end + TAIL, bpm, w, h, rnd)
    ev.append(f"Dialogue: 2,{_ts(end + 0.4)},{_ts(end + TAIL)},Title,,0,0,0,,{{\\fad(300,0)}}♪ ♥ ♪")
    out.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------- picture timeline
def scene_durations(n: int, times: list[tuple[float, float]], total: float) -> list[float]:
    """Scene i starts just before line i; the first scene also covers the title card."""
    starts = [0.0] + [max(0.1, times[min(i, len(times) - 1)][0] - 0.25) for i in range(1, n)]
    return [max(0.8, (starts[i + 1] if i + 1 < n else total) - starts[i]) for i in range(n)]


def _motion(i: int, frames: int, rnd: random.Random) -> tuple[str, str, str]:
    """(zoom, x, y) zoompan expressions - a different camera move for every scene."""
    k = f"(on/{frames})"
    moves = [
        (f"1.0+0.18*{k}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                         # zoom in
        (f"1.18-0.18*{k}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                         # zoom out
        ("1.2", f"(iw-iw/zoom)*{k}", "ih/2-(ih/zoom/2)"),                                    # pan right
        ("1.2", f"(iw-iw/zoom)*(1-{k})", "ih/2-(ih/zoom/2)"),                                # pan left
        ("1.18", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)/2+(ih-ih/zoom)/2*sin(on/5)"),             # happy bounce
        (f"1.1+0.12*{k}", f"(iw-iw/zoom)*(0.2+0.6*{k})", f"(ih-ih/zoom)*(0.7-0.4*{k})"),    # diagonal drift
    ]
    return moves[(i + rnd.randint(0, 5)) % len(moves)]


INTER = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-an"]  # lossless-ish parts


def _scene_filter(img: Path, i: int, d: float, w: int, h: int, rnd: random.Random, bpm: int | None) -> str:
    landscape = w > h
    fw, fh = (w, h) if landscape else (w, w)  # Shorts: big square picture over a blurred background
    frames = max(2, int(d * FPS))
    z, x, y = _motion(i, frames, rnd)
    if bpm:  # dance mode: the picture "punches" in on every beat
        bf = FPS * 60 / bpm
        z = f"1.06+0.07*pow(1-mod(on,{bf:.3f})/{bf:.3f},3)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if img.suffix.lower() == ".mp4":  # already moving: just fit it, no fake camera move
        zp = (f"scale={fw}:{fh}:force_original_aspect_ratio=increase:flags=lanczos,crop={fw}:{fh},fps={FPS},"
              f"unsharp=5:5:0.5,setsar=1,trim=duration={d:.2f},setpts=PTS-STARTPTS")
    else:
        zp = (f"scale={fw * 5 // 4}:{fh * 5 // 4}:force_original_aspect_ratio=increase:flags=lanczos,crop={fw * 5 // 4}:{fh * 5 // 4},"
              f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={fw}x{fh}:fps={FPS},unsharp=5:5:0.6,"
              f"eq=saturation=1.12:contrast=1.04,setsar=1")
    if landscape:
        return f"[0:v]{zp},format=yuv420p[v]"
    return (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=25:2,"
            f"eq=brightness=0.04:saturation=1.3,fps={FPS},setsar=1[bg];[b]{zp}[fg];"
            f"[bg][fg]overlay=0:(H-h)/2-{h // 12}:shortest=1,format=yuv420p[v]")


def _turn_frame(a: np.ndarray, b: np.ndarray, p: float) -> np.ndarray:
    """One page-turn frame (uint8 RGB, h x w x 3). `p` runs 1 -> 0 over the turn.

    The old page `a` is lifted from the right edge: its paper back sweeps left over it, the new page `b` lies
    underneath in the flap's shadow, and the old page darkens a little at the fold. Every weight depends only on
    the column, so the work is a few cheap slices per frame."""
    w = a.shape[1]
    x = np.arange(w, dtype=np.float32)
    e, f = w * p, w * 0.7 * p * (1 - p)
    ie, iff = int(np.clip(round(e), 0, w)), int(np.clip(round(e + f), 0, w))
    out = np.empty_like(a)
    if ie:
        ga = 1 - 0.25 * np.exp((x[:ie] - e) / (w * 0.025))
        out[:, :ie] = (a[:, :ie] * ga[None, :, None] + 0.5).astype(np.uint8)
    if iff > ie:
        shade = 0.80 + 0.18 * (x[ie:iff] - e) / max(f, 1.0)
        out[:, ie:iff] = (np.asarray(pb.PAPER, np.float32)[None, None, :] * shade[None, :, None] + 0.5).astype(np.uint8)
    if iff < w:
        gb = 1 - 0.45 * np.exp((e + f - x[iff:]) / (w * 0.05))
        out[:, iff:] = (b[:, iff:] * gb[None, :, None] + 0.5).astype(np.uint8)
    return out


def _page_turn(seg_a: Path, a_start: float, seg_b: Path, xf: float, w: int, h: int, out: Path) -> None:
    """Page turn from the end of `seg_a` into the start of `seg_b`, streamed frame by frame (low memory, fast)."""
    n = max(1, round(xf * FPS))
    size = w * h * 3

    def reader(src: Path, start: float) -> subprocess.Popen[bytes]:
        return subprocess.Popen(["ffmpeg", "-v", "error", "-i", src.as_posix(), "-vf",
                                 f"trim=start={start:.3f},setpts=PTS-STARTPTS,fps={FPS},scale={w}:{h}",
                                 "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    ra, rb = reader(seg_a, a_start), reader(seg_b, 0.0)
    wr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                           "-r", str(FPS), "-i", "-", *INTER, out.as_posix()],
                          stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert ra.stdout and rb.stdout and wr.stdin  # pipes were requested above
    last_a = last_b = np.full((h, w, 3), pb.PAPER, np.uint8)
    try:
        for k in range(n):
            da, db = ra.stdout.read(size), rb.stdout.read(size)
            if len(da) == size:
                last_a = np.frombuffer(da, np.uint8).reshape(h, w, 3)
            if len(db) == size:
                last_b = np.frombuffer(db, np.uint8).reshape(h, w, 3)
            wr.stdin.write(_turn_frame(last_a, last_b, 1 - (k + 0.5) / n).tobytes())
    finally:
        wr.stdin.close()
        for r in (ra, rb):
            r.kill()
            r.wait()
        err = wr.stderr.read().decode(errors="replace") if wr.stderr else ""
        if wr.wait() != 0:
            raise RuntimeError(f"ffmpeg page turn failed:\n{err[-2000:]}")


def _pb_scene(img: Path, i: int, d: float, w: int, h: int, rnd: random.Random,
              bpm: int | None) -> tuple[list[str], str]:
    """Picture-book scene: (ffmpeg inputs, filter). Input 1 is always a sheet of paper the size of the frame.

    Stills step through their redrawn versions at 12 fps (line boil) under a slow, calm camera drift.
    Animated clips are stepped to 12 fps too and printed onto the paper."""
    landscape = w > h
    fw, fh = (w, h) if landscape else (w, w)
    bw, bh = fw * 27 // 25 // 2 * 2, fh * 27 // 25 // 2 * 2       # 8 % bigger, room for the drift
    x0, x1, y0, y1 = (rnd.uniform(0.15, 0.85) for _ in range(4))
    k = f"min(t/{max(d, 0.1):.3f},1)"
    y = f"(ih-oh)*({y0:.3f}+({y1 - y0:.3f})*{k})"
    if bpm:  # dance mode: the page hops on every beat
        beat = 60 / bpm
        y = f"(ih-oh)*(0.65-0.5*pow(1-mod(t,{beat:.4f})/{beat:.4f},3))"
    move = f"crop={fw}:{fh}:x='(iw-ow)*({x0:.3f}+({x1 - x0:.3f})*{k})':y='{y}'"
    fit = f"scale={bw}:{bh}:force_original_aspect_ratio=increase:flags=lanczos,crop={bw}:{bh}"
    clip = img.suffix.lower() == ".mp4"
    if clip:
        inputs = ["-stream_loop", "-1", "-t", f"{d:.2f}", "-i", img.as_posix()]
    else:
        frames = pb.boil_frames(img)
        if len(frames) > 1:
            pattern = frames[0].with_name(frames[0].name.replace("_pb0.jpg", "_pb%d.jpg"))
            inputs = ["-framerate", str(pb.BOIL_FPS), "-loop", "1", "-t", f"{d:.2f}", "-i", pattern.as_posix()]
        else:
            inputs = ["-loop", "1", "-t", f"{d:.2f}", "-i", img.as_posix()]
    if clip or not landscape:
        inputs += ["-loop", "1", "-i", PAPER_SLOT]
    parts = []
    paper_for_clip, paper_for_bg = "[1:v]", "[1:v]"
    if clip and not landscape:
        parts.append("[1:v]split[pc][pg]")
        paper_for_clip, paper_for_bg = "[pc]", "[pg]"
    tail = "[v]" if landscape else "[fg]"
    if clip:
        parts.append(f"[0:v]{fit},fps={pb.BOIL_FPS},fps={FPS},{move},setsar=1,format=gbrp[c]")
        parts.append(f"{paper_for_clip}scale={fw}:{fh},setsar=1,fps={FPS},format=gbrp[pf]")
        parts.append(f"[c][pf]blend=all_mode=multiply:shortest=1,eq=saturation=1.1,format=yuv420p{tail}")
    else:
        parts.append(f"[0:v]{fit},fps={FPS},{move},setsar=1,format=yuv420p{tail}")
    if not landscape:
        parts.append(f"{paper_for_bg}scale={w}:{h},setsar=1,fps={FPS}[bg]")
        parts.append(f"[bg][fg]overlay=0:(H-h)/2-{h // 12}:shortest=1,format=yuv420p[v]")
    return inputs, ";".join(parts)


def render(images: list[Path], lines: list[str], voice: Path, times: list[tuple[float, float]],
           ass: Path, fonts_dir: Path, music: Path | None, music_vol: float,
           w: int, h: int, out: Path, seed: int = 0, total: float | None = None, bpm: int | None = None,
           look: str = "classic") -> Path:
    """Low-memory renderer. `images` may mix still pictures (.jpg) and animated clips (.mp4, Level 2).

    1) every scene -> its own short clip      2) each transition -> a 0.4 s clip
    3) join all pieces without re-encoding     4) add lyrics, stars, voice + music in one streaming pass
    Only one or two scenes are ever in memory, so long dance songs and 1080p work on small machines.
    """
    if look not in LOOKS:
        raise ValueError(f"unknown look {look!r}; use one of {LOOKS}")
    picture_book = look == "picturebook"
    xf = PB_XF if picture_book else XF
    rnd = random.Random(seed)
    total = total or ((times[-1][1] if times else LEAD) + TAIL + 0.3)
    n = len(images)
    durs = scene_durations(n, times, total)
    clip = [d + (xf if i < n - 1 else 0) for i, d in enumerate(durs)]   # overlap for transitions
    tmp = out.parent / f"_parts_{out.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    paper = pb.paper_image(w, h, seed, tmp / "paper.jpg").as_posix() if picture_book else ""

    scenes = []
    for i, (img, d) in enumerate(zip(images, clip)):
        if picture_book:
            src, graph = _pb_scene(img, i, d, w, h, rnd, bpm)
            src = [paper if a == PAPER_SLOT else a for a in src]
        else:
            src = (["-stream_loop", "-1", "-t", f"{d:.2f}", "-i", img.as_posix()] if img.suffix.lower() == ".mp4"
                   else ["-loop", "1", "-t", f"{d:.2f}", "-i", img.as_posix()])
            graph = _scene_filter(img, i, d, w, h, rnd, bpm)
        seg = tmp / f"scene_{i:02d}.mp4"
        _run(["ffmpeg", "-y", *src, "-filter_complex", graph, "-map", "[v]",
              "-t", f"{d:.2f}", "-r", str(FPS), *INTER, seg.as_posix()])
        scenes.append(seg)

    pieces = []
    for i, seg in enumerate(scenes):
        start = xf if i > 0 else 0.0
        end = clip[i] - (xf if i < n - 1 else 0.0)
        body = tmp / f"body_{i:02d}.mp4"
        _run(["ffmpeg", "-y", "-i", seg.as_posix(), "-vf", f"trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS",
              "-r", str(FPS), *INTER, body.as_posix()])
        pieces.append(body)
        if i < n - 1:
            tr = tmp / f"trans_{i:02d}.mp4"
            if picture_book:
                _page_turn(seg, clip[i] - xf, scenes[i + 1], xf, w, h, tr)
            else:
                fade = f"[a][b]xfade=transition={rnd.choice(TRANSITIONS)}:duration={xf}:offset=0,format=yuv420p[v]"
                _run(["ffmpeg", "-y", "-i", seg.as_posix(), "-i", scenes[i + 1].as_posix(), "-filter_complex",
                      (f"[0:v]trim=start={clip[i] - xf:.3f},setpts=PTS-STARTPTS[a];[1:v]trim=end={xf:.3f},setpts=PTS-STARTPTS[b];"
                       + fade),
                      "-map", "[v]", "-t", f"{xf:.3f}", "-r", str(FPS), *INTER, tr.as_posix()])
            pieces.append(tr)

    lst = tmp / "pieces.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in pieces))
    joined = tmp / "joined.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.as_posix(), "-c", "copy", joined.as_posix()])

    cmd = ["ffmpeg", "-y", "-i", joined.as_posix(), "-i", voice.as_posix()]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music.as_posix()]
    ass_path = ass.as_posix().replace(":", "\\:")
    fl = [f"[0:v]ass='{ass_path}':fontsdir='{fonts_dir.as_posix()}'[vout]"]
    voice_chain = "[1:a]aresample=44100,volume=1.5[vo]"
    if music and music_vol > 0:
        fl.append(f"{voice_chain};[2:a]aresample=44100,volume={music_vol}[m];"
                  f"[vo][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                  f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    else:
        fl.append(f"{voice_chain};[vo]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    # crayon grain is all fine detail: cap the bitrate near YouTube's 1080p advice so files stay small
    quality = (["-crf", "20", "-tune", "grain", "-maxrate", "8M", "-bufsize", "16M"] if picture_book
               else ["-crf", "18"])
    cmd += ["-filter_complex", ";".join(fl), "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", *quality,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", out.as_posix()]
    _run(cmd)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return out
