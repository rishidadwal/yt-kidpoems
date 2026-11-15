"""Free neural voices via Microsoft Edge TTS (edge-tts). One audio file per line."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


async def _say(text: str, voice: str, rate: str, pitch: str, out: Path, retries: int = 4) -> None:
    for attempt in range(retries):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))
            if out.exists() and out.stat().st_size > 1000:
                return
        except Exception as e:  # noqa: BLE001 - network hiccups are common; log and retry
            print(f"[retry] tts attempt {attempt + 1}: {e}")
        await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(f"TTS failed for: {text[:40]}")


def speak_lines(lines: list[str], voice: str, rate: str, pitch: str, workdir: Path) -> list[tuple[Path, float]]:
    """Returns [(mp3_path, seconds)] per line."""
    workdir.mkdir(parents=True, exist_ok=True)

    async def run() -> None:
        for i, line in enumerate(lines):
            await _say(line, voice, rate, pitch, workdir / f"line_{i:02d}.mp3")

    asyncio.run(run())
    return [(workdir / f"line_{i:02d}.mp3", duration(workdir / f"line_{i:02d}.mp3")) for i in range(len(lines))]
