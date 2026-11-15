# Testing & Zero-Defect Gates

> No software can be *proven* bug-free. These gates make sure every change is verified automatically,
> nothing reaches YouTube unchecked, and every bug found becomes a permanent regression test.

## Test layers
| Layer | Tool | What |
|---|---|---|
| Static | ruff, mypy --strict | style, types, unsafe patterns |
| Unit | pytest + hypothesis | validation, safety filter, ASS escaping and timing, karaoke splits, quota maths, history rotation, config schema |
| Integration (mocked) | pytest + respx/monkeypatch | Gemini 200/429/500/bad JSON · edge-tts failure · Pollinations timeout → fallback · YouTube 5xx retry, quotaExceeded, thumbnail forbidden |
| Media | pytest + ffprobe | rendered mp4 has the right duration, resolution, fps, an audio stream, loudness in range, the Short is ≤ 60 s |
| Script coverage | pytest (parametrised over every configured language) | the font has glyphs for every character of a sample poem (fontTools cmap check); RTL renders; no tofu |
| Golden | snapshot of the ASS file for fixed input | lyric timing never drifts |
| End-to-end (offline) | `python -m src.pipeline --offline --no-upload` in CI | a full run produces valid files |
| Canary (online) | a manual workflow with `--no-upload` | real APIs still work (run weekly) |

## Coverage gates
- `src/` ≥ 90% lines and branches. Pure-logic modules (`qa.py`, validation, ASS builder) = 100%.
- `mutmut` on the pure-logic modules: 0 surviving mutants (or each one justified).

## Gates
| When | Runs | Blocks |
|---|---|---|
| pre-commit | ruff, mypy, related tests | commit |
| push / PR (ci.yml) | `make verify` + offline end-to-end run | merge |
| daily run | `qa.py` quality gate on every video | upload of that video |
| after upload | read the video back via the API and assert madeForKids + privacy | alerts the owner |

## Commands
```
make lint     # ruff + mypy --strict
make test     # pytest with coverage thresholds
make e2e      # offline full pipeline
make verify   # all of the above
```
