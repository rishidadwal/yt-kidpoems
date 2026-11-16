"""Poem writing: Gemini free tier, with a public-domain fallback (English)."""
from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SAFETY_RULES = (
    "Audience: children aged 2-6. Content must be gentle, positive, educational and 100% child-safe: "
    "no violence, fear, brands, real people, religion or politics. Simple words a toddler understands."
)


class PoemError(RuntimeError):
    pass


MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _version(name: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", name.split("gemini-", 1)[-1])[:3])


def _live_flash_model(key: str) -> str | None:
    """Google retires model names; ask the API for the newest plain 'flash' text model that still exists."""
    try:
        r = requests.get(MODELS_URL, headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
        r.raise_for_status()
        names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"[warn] could not list Gemini models: {type(e).__name__}")
        return None
    skip = ("lite", "image", "tts", "live", "audio", "embedding", "thinking", "preview", "exp")
    flash = [n for n in names if "flash" in n and not any(w in n for w in skip)]
    return max(flash, key=_version) if flash else None


LITE_MODEL = "gemini-flash-lite-latest"


def _gemini(prompt: str, model: str, retries: int = 4) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise PoemError("GEMINI_API_KEY not set")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"},
    }
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key}, json=body, timeout=180)  # newer flash models think longer
            if r.status_code == 404:  # model name retired -> switch once to a live one
                new = _live_flash_model(key)
                if new and new != model:
                    print(f"[warn] Gemini model {model!r} is gone; using {new!r} (update llm_model in config.yaml)")
                    model = new
                    continue
            if r.status_code == 429 and model != LITE_MODEL:  # daily free quota used up -> lite has its own quota
                print(f"[warn] Gemini {model!r} quota used up (429); trying {LITE_MODEL!r}")
                model = LITE_MODEL
                continue
            if r.status_code == 429 or r.status_code >= 500:  # free-tier rate limit / server busy
                raise PoemError(f"HTTP {r.status_code}")
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
            return json.loads(text)
        except (requests.RequestException, KeyError, IndexError, ValueError, PoemError) as e:
            last = re.sub(r"key=[^&\s'\"]+", "key=***", str(e))  # never leak the API key into logs/last_run.json
            time.sleep(2 ** attempt * 5)
    raise PoemError(f"Gemini failed after {retries} tries: {last}")


def _validate(p: dict, need_prompts: bool = True) -> dict:
    lines = [str(x).strip() for x in p.get("lines", []) if str(x).strip()]
    if not (4 <= len(lines) <= 32):
        raise PoemError(f"bad line count {len(lines)}")
    if any(len(ln) > 90 for ln in lines):
        raise PoemError("line too long")
    out = {
        "title": str(p.get("title", "")).strip()[:90] or lines[0][:60],
        "lines": lines,
        "description": str(p.get("description", "")).strip()[:4000],
        "tags": [str(t)[:30] for t in p.get("tags", [])][:15],
    }
    if need_prompts:
        prompts = [str(x) for x in p.get("image_prompts", [])]
        while len(prompts) < len(lines):          # one picture per line
            prompts.append(prompts[-1] if prompts else out["title"])
        out["image_prompts"] = prompts[:len(lines)]
    return out


PICTURE_RULES = """Picture rules: ONE clear star in the middle of the picture (a single cast member, or the whole cast only on
chorus lines), shown big with a huge happy face looking at the camera, in the middle of a big simple movement.
Plain, uncluttered background in bright saturated colours. Never a scared, crying or angry face. Describe each cast
member the same way every time. Vary the shot (close-up, wide, from above). Never put words or letters in the picture."""


def cast_members(cast: str) -> list[str]:
    """'Pip, a toddler; Gigi, a giraffe; and Quack, a duck' -> one entry per character (whole string if no ';')."""
    return [m for m in (re.sub(r"^and\s+", "", x.strip()) for x in cast.split(";")) if m] or [cast]


def with_cast(prompts: list[str], cast: str) -> list[str]:
    """Add the full look of every cast member named in a prompt, so each picture draws them the same way
    (the AI writes only 'Gigi dances' and the image model would invent a new giraffe every scene)."""
    members = cast_members(cast)
    out = []
    for p in prompts:
        named = [m for m in members if "," in m and m.split(",", 1)[0].strip().lower() in p.lower()]
        out.append(f"{p}. Characters: {'; '.join(named)}" if named else p)
    return out


def write_original(topic: str, model: str, cast: str = "two happy little kids and a fluffy orange kitten") -> dict:
    """New English poem about `topic` (the 'master' version, also drives the pictures)."""
    prompt = f"""Write an ORIGINAL rhyming nursery poem in English about: "{topic}".
{SAFETY_RULES}
Small children stay for songs they can join in with, so:
- The FIRST line is the chorus: short, bouncy, exciting, and it speaks to the child ("Can you ...?", "Let's ...!").
  Repeat that exact chorus line 3 or 4 times through the poem and make it the last line too.
- 12 to 16 short lines (max 8 words each), AABB rhyme, strong sing-song rhythm.
- Use fun sound words (splash, zoom, moo, pop) and something to copy or answer: an action, a count to 3 or 5,
  a colour or an animal sound. Build up to one small happy surprise near the end and one tiny kind lesson.
The poem stars this cast: {{CAST}}. Use their names. Make it playful and full of action.
For EACH LINE give one image prompt showing exactly what that line says.
{PICTURE_RULES}
Return JSON only:
{{"title": "short catchy title, max 6 words", "lines": ["..."], "image_prompts": ["..."],
  "description": "2-3 friendly sentences for parents (what the child learns) + the full poem text",
  "tags": ["nursery rhymes","kids songs", "..."]}}"""
    return _validate(_gemini(prompt.replace("{CAST}", cast), model))


def localise(master: dict, lang_name: str, model: str) -> dict:
    """Re-write (not word-by-word translate) so it rhymes naturally in the target language."""
    if lang_name.lower() == "english":
        return master
    n = len(master["lines"])
    prompt = f"""Re-create this children's nursery poem in {lang_name} as a NATIVE {lang_name} nursery rhyme.
Keep the same meaning, characters and the same number of lines ({n}) so each line matches the same picture.
It must RHYME and have a sing-song rhythm in {lang_name} (do not translate word by word). Use the native script.
If it is a dance chant, keep the made-up nonsense hook syllables exactly as they are (they're fun in every language)
and translate only the action calls.
{SAFETY_RULES}
Poem: {json.dumps(master["lines"], ensure_ascii=False)}
Return JSON only: {{"title": "... in {lang_name}", "lines": [exactly {n} lines],
"description": "2-3 sentences in {lang_name} for parents + the poem", "tags": ["up to 12 {lang_name} search tags"]}}"""
    out = _validate(_gemini(prompt, model), need_prompts=False)
    if len(out["lines"]) != n:  # keep picture sync: pad/trim
        out["lines"] = (out["lines"] + out["lines"][-1:] * n)[:n]
    out["image_prompts"] = master["image_prompts"]
    for k in ("actions", "mode", "hook"):
        if k in master:
            out[k] = master[k]
    return out


def public_domain(history: dict) -> dict:
    rhymes = json.loads((DATA / "public_domain_rhymes.json").read_text(encoding="utf-8"))
    left = [r for r in rhymes if r["title"] not in history["done_rhymes"]] or rhymes
    r = random.choice(left)
    rounds = min(3, -(-12 // len(r["lines"])))  # short rhymes are sung 2-3 times (kids love repeats; 4 lines = 20 s)
    shots = ["wide shot", "close-up", "seen from above"]
    return {
        "title": r["title"],
        "lines": r["lines"] * rounds,
        "image_prompts": [f"Nursery rhyme '{r['title']}' scene, {shots[k]}: {ln} - with two happy little kids and a "
                          f"fluffy orange kitten playing" for k in range(rounds) for ln in r["lines"]],
        "description": f"{r['title']} - a classic nursery rhyme for kids to sing along.\n\n" + "\n".join(r["lines"]),
        "tags": ["nursery rhymes", "kids songs", r["title"].lower(), "rhymes for children"],
        "_public_domain": True,
    }


def next_topic(history: dict) -> str | None:
    topics = [t.strip() for t in (DATA / "topics.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    left = [t for t in topics if t not in history["done_topics"]]
    return left[0] if left else None


# =============================================================== DANCE MODE
ACTIONS = ["CLAP", "JUMP", "SPIN", "WIGGLE", "STOMP", "WAVE", "HOP", "SHAKE", "TWIST", "SWAY", "BOUNCE", "TAP"]


def write_dance(topic: str, model: str, cast: str = "two happy little kids and a fluffy orange kitten") -> dict:
    """Original, super-catchy kids' dance chant: a tiny nonsense hook repeated a lot + action calls."""
    prompt = f"""Write an ORIGINAL, super catchy toddler DANCE song in English. Theme: "{topic}".
{SAFETY_RULES}
Style: a tiny silly nonsense HOOK of 2-4 made-up syllables (invent a NEW one, never copy an existing song or any
known hook), repeated many times, plus simple ACTION calls kids can copy (clap, jump, spin, wiggle, stomp, wave, hop).
Structure (24 to 32 short lines, so the song lasts 2+ minutes; max 6 words each): the FIRST line is the HOOK, then action line, action line, HOOK -
repeat with new actions; the hook line appears at least 5 times, exactly the same each time, and is the last line.
Action lines speak to the child ("Can you jump? Jump jump jump!") and the last round is the biggest and silliest.
For each line give ONE action word from: {", ".join(ACTIONS)}.
The dancers are: {{CAST}}. For each line give one image prompt of them DANCING that action in a bright party scene.
{PICTURE_RULES}
Return JSON only:
{{"title": "the hook + 'Dance Song'", "hook": "...", "lines": ["..."], "actions": ["CLAP", ...],
  "image_prompts": ["..."], "description": "2-3 fun sentences for parents + full lyrics", "tags": ["kids dance", "..."]}}"""
    raw = _gemini(prompt.replace("{CAST}", cast), model)
    out = _validate(raw)
    out["actions"] = _actions(raw.get("actions"), len(out["lines"]))
    out["hook"] = str(raw.get("hook", ""))[:40]
    out["mode"] = "dance"
    return out


def _actions(acts, n: int) -> list[str]:
    acts = [str(a).upper().strip() for a in (acts or []) if str(a).upper().strip() in ACTIONS]
    while len(acts) < n:
        acts.append(ACTIONS[len(acts) % len(ACTIONS)])
    return acts[:n]


def builtin_dance(seed: int, cast: str = "two happy little kids and a fluffy orange kitten") -> dict:
    """Offline / no-AI fallback: an original nonsense chant built from random syllables."""
    rnd = random.Random(seed)
    syl = ["bo", "ba", "zum", "zee", "pom", "pa", "tiki", "tak", "boo", "dee", "loo", "bim", "bam", "yay", "wooz", "kiki"]
    a, b = rnd.sample(syl, 2)
    hook = f"{a.title()} {a} {b} {b}!"
    moves = rnd.sample(ACTIONS, 12)
    calls = {"CLAP": "Clap your hands, clap clap clap!", "JUMP": "Jump up high, jump jump jump!",
             "SPIN": "Spin around, spin spin spin!", "WIGGLE": "Wiggle wiggle, wiggle your tail!",
             "STOMP": "Stomp your feet, stomp stomp stomp!", "WAVE": "Wave hello, wave wave wave!",
             "HOP": "Hop like a bunny, hop hop hop!", "SHAKE": "Shake shake shake, shake it out!",
             "TWIST": "Twist to the left, twist to the right!", "SWAY": "Sway like a tree, sway sway!",
             "BOUNCE": "Bounce bounce bounce, bounce like a ball!", "TAP": "Tap your toes, tap tap tap!"}
    lines, actions = [], []
    for k in range(6):  # 6 rounds = 24 lines, about 2 minutes
        m1, m2 = moves[2 * k], moves[2 * k + 1]
        lines += [hook, calls[m1], calls[m2], hook]
        actions += ["BOUNCE", m1, m2, "SPIN"]
    stars = cast_members(cast)
    places = ["sunny jungle clearing with colourful balloons", "rainbow party stage with confetti", "tropical beach party with balloons"]
    return {"title": f"{hook} Dance Song", "hook": hook, "lines": lines, "actions": actions, "mode": "dance",
            # hook lines show the whole cast; each action line has one star, so small eyes know where to look
            "image_prompts": [f"{cast if ln == hook else stars[i % len(stars)]} dancing, doing {act.lower()}, huge happy "
                              f"smile, looking at the camera, big and centred, simple {places[i // 4 % 3]}"
                              for i, (act, ln) in enumerate(zip(actions, lines))],
            "description": f"{hook} - a silly dance song for kids! Clap, jump and spin along.\n\n" + "\n".join(lines),
            "tags": ["kids dance", "dance song for kids", "toddler dance", "action song", "nursery rhymes"],
            "_builtin": True}


def next_dance_topic(history: dict) -> str | None:
    f = DATA / "dance_topics.txt"
    if not f.exists():
        return None
    topics = [t.strip() for t in f.read_text(encoding="utf-8").splitlines() if t.strip()]
    left = [t for t in topics if t not in history.setdefault("done_dance_topics", [])]
    return left[0] if left else (topics[len(history["done_dance_topics"]) % len(topics)] if topics else None)
