# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "faster-whisper>=1.1",
#   "numpy>=1.26",
#   "nvidia-cublas-cu12",
#   "nvidia-cudnn-cu12>=9,<10",
# ]
# ///
"""First edit of one recording: sync the camera's scratch audio to the studio audio, transcribe
the studio audio, and cut the recording into scenes, each holding its clips.

    first-edit/launch <video folder>/raw/<nn> [options]

A scene is one part of the video, closed aloud by "cut cut". A clip (also called a cut or a take)
is a candidate for it: one try at saying that scene. Every clip is kept; one per scene is the best.

A recording folder holds a camera file (camera.mp4, or any one video file), studio.wav and,
optionally, script.md. It is only read. The result goes beside raw/, under edit/:

    <video folder>/
      raw/01/  camera.mp4  studio.wav  script.md
      edit/
        scenes/
          scenes.json                     every scene and clip of the video, the best, cues heard
          01-<scene words>/  01-01.mp4  01-02.mp4  01-03-best.mp4
          02-<scene words>/  02-01-best.mp4
        final/

Scenes are numbered through the whole video in the order spoken, and a later recording carries on
from the last number, so sorting by name is sorting by time.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".mkv"}
ALIGN_RATE = 8000     # Hz, for the waveform comparison
ENVELOPE_HOP = 80     # samples at ALIGN_RATE: a 10 ms loudness envelope


def use_gpu_libraries() -> None:
    """Whisper on the GPU loads cuBLAS and cuDNN by name, so their folders must be on the library
    path before the process starts: start again once with them added."""
    if os.environ.get("FIRST_EDIT_LIBS") or os.environ.get("FIRST_EDIT_DEVICE") == "cpu":
        return
    folders = []
    for name in ("nvidia.cublas.lib", "nvidia.cudnn.lib"):
        try:
            module = __import__(name, fromlist=["__path__"])
            folders.extend(list(module.__path__))
        except Exception:
            return
    env = dict(os.environ, FIRST_EDIT_LIBS="1")
    env["LD_LIBRARY_PATH"] = os.pathsep.join(folders + [p for p in [env.get("LD_LIBRARY_PATH")] if p])
    os.execve(sys.executable, [sys.executable, *sys.argv], env)


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"first-edit: {message}", file=sys.stderr)
    sys.exit(1)


def run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, **kw)


def duration_of(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.stdout.decode().strip())


def has_stream(path: Path, kind: str) -> bool:
    out = run(["ffprobe", "-v", "error", "-select_streams", kind, "-show_entries", "stream=index", "-of", "csv=p=0", str(path)])
    return bool(out.stdout.strip())


def mono(path: Path, rate: int):
    """The file's sound as one channel of floats at `rate`."""
    import numpy as np
    out = run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"])
    return np.frombuffer(out.stdout, dtype=np.float32)


# ---------------------------------------------------------------- alignment

def correlate(a, b, max_lag: int, guard: int):
    """Where `a` best lines up inside `b`: the lag k (in samples, -max_lag..max_lag) that maximises
    sum a[n] * b[n + k], with two measures of how much to trust it. `clear` is the peak against the
    best lag anywhere else (more than `guard` samples away): noise gives about 1, a real match 2 or
    more. `alike` is the peak as a correlation, 0 to 1: how alike the two are once lined up."""
    import numpy as np
    a = a - a.mean()
    b = b - b.mean()
    size = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.conj(np.fft.rfft(a, size)) * np.fft.rfft(b, size), size)
    max_lag = min(max_lag, size // 2 - 1)
    window = np.concatenate([c[-max_lag:], c[: max_lag + 1]])     # lags -max_lag .. +max_lag
    peak = int(np.argmax(window))
    elsewhere = window.copy()
    elsewhere[max(0, peak - guard):peak + guard + 1] = -np.inf
    second = float(elsewhere.max()) if np.isfinite(elsewhere).any() else 0.0
    clear = float(window[peak] / second) if second > 0 else 99.0
    scale = float(np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return peak - max_lag, min(clear, 99.0), float(window[peak] / scale)


def envelope(x):
    import numpy as np
    usable = len(x) - len(x) % ENVELOPE_HOP
    frames = x[:usable].reshape(-1, ENVELOPE_HOP)
    return np.log1p(1000.0 * np.sqrt((frames ** 2).mean(axis=1)))


PER_SECOND = ALIGN_RATE // ENVELOPE_HOP   # envelope frames in a second


def offset_between(scratch, studio, max_seconds: float):
    """Seconds to add to a camera time to get the studio time of the same moment, and how clear
    and how alike the match is. Loudness envelopes find it to 10 ms whatever the microphones did to
    the waveform; the waveforms then refine it when they agree."""
    lag, clear, alike = correlate(envelope(scratch), envelope(studio), int(max_seconds * PER_SECOND), PER_SECOND // 2)
    coarse = lag * ENVELOPE_HOP
    reach = 2 * ENVELOPE_HOP
    span = min(len(scratch), ALIGN_RATE * 120)
    start = max(0, (len(scratch) - span) // 2)
    lo = start + coarse - reach
    if lo >= 0 and lo + span + 2 * reach <= len(studio):
        fine, fine_clear, fine_alike = correlate(scratch[start:start + span], studio[lo:lo + span + 2 * reach], 2 * reach, 8)
        # the stretch sits `reach` samples into that window when the coarse answer is exact
        if fine_alike >= 0.3 and abs(fine - reach) <= ENVELOPE_HOP:
            return (coarse + fine - reach) / ALIGN_RATE, clear, alike
    return coarse / ALIGN_RATE, clear, alike


def trusted(clear: float, alike: float) -> bool:
    """Whether to believe a match. `alike` is the main evidence: silence or noise gives under 0.15,
    and the first real camera-against-recorder take gave 0.92. `clear` alone is a weak test on
    speech, where a retake or the rhythm of a sentence puts a second peak near the first (that same
    real take gave 1.5), so it is only asked for when the two recordings are not very alike."""
    return alike >= 0.5 or (alike >= 0.25 and clear >= 1.5)


def align(camera: Path, studio: Path, max_seconds: float) -> dict:
    scratch_audio, studio_audio = mono(camera, ALIGN_RATE), mono(studio, ALIGN_RATE)
    if len(scratch_audio) < ALIGN_RATE or len(studio_audio) < ALIGN_RATE:
        fail("the camera clip or studio.wav has under a second of sound; cannot align them")
    offset, clear, alike = offset_between(scratch_audio, studio_audio, max_seconds)
    result = {"offset": round(offset, 3), "clear": round(clear, 2), "alike": round(alike, 2), "drift": None, "ok": trusted(clear, alike)}
    # the same answer near the start and near the end rules out drift between the two recorders
    third = len(scratch_audio) // 3
    if third >= ALIGN_RATE * 10:
        shift = int(offset * ALIGN_RATE)
        ends = []
        for begin in (0, len(scratch_audio) - third):
            lo, hi = begin + shift - ALIGN_RATE * 2, begin + shift + third + ALIGN_RATE * 2
            if lo < 0 or hi > len(studio_audio):
                continue
            lag, part_clear, part_alike = correlate(envelope(scratch_audio[begin:begin + third]), envelope(studio_audio[lo:hi]), 4 * PER_SECOND, PER_SECOND // 2)
            if trusted(part_clear, part_alike):
                ends.append(lag / PER_SECOND - 2.0)
        if len(ends) == 2:
            result["drift"] = round(ends[1] - ends[0], 3)
            result["ok"] = result["ok"] and abs(result["drift"]) <= 0.045
    return result


# ---------------------------------------------------------------- transcription

def transcribe(sound, model_name: str | None, language: str | None) -> tuple[list[dict], dict]:
    from faster_whisper import WhisperModel
    device = os.environ.get("FIRST_EDIT_DEVICE", "cuda")
    attempts = [(device, "float16")] if device == "cuda" else []
    attempts.append(("cpu", "int8"))
    last = None
    for dev, kind in attempts:
        name = model_name or ("medium.en" if dev == "cuda" else "small.en")
        try:
            model = WhisperModel(name, device=dev, compute_type=kind)
            segments, info = model.transcribe(
                sound, word_timestamps=True, language=language,
                condition_on_previous_text=False,   # otherwise a repeated line is often left out
                temperature=0.0,   # no random retries: the same recording must always cut the same way
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
            )
            words = [
                {"text": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                for s in segments for w in (s.words or []) if w.word.strip()
            ]
            return words, {"model": name, "device": dev, "language": info.language}
        except Exception as error:  # a GPU that cannot be used falls back to the CPU
            last = error
            if dev == "cuda":
                print(f"first-edit: GPU transcription unavailable ({str(error).splitlines()[0][:120]}); using the CPU", file=sys.stderr)
    fail(f"could not transcribe the studio audio: {last}")


# ---------------------------------------------------------------- sorting by idea

def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


def load_glossary(path: Path) -> list[dict]:
    try:
        cues = json.loads(path.read_text(encoding="utf-8"))["cues"]
    except (OSError, ValueError, KeyError) as error:
        fail(f"cannot read the glossary {path}: {error}")
    phrases = []
    for cue in cues:
        if cue.get("action") not in ("cut", "best", "end"):
            fail(f"glossary: \"{cue.get('say')}\" has action \"{cue.get('action')}\"; this version knows cut, best and end")
        for said in [cue["say"], *cue.get("heard_as", [])]:
            phrases.append({"tokens": tokens(said), "action": cue["action"], "say": cue["say"]})
    return sorted(phrases, key=lambda p: -len(p["tokens"]))   # the longest way of saying it first


def take_out_cues(words: list[dict], phrases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Find the spoken cues. Returns the words without them, each marked with the stretch it
    belongs to (a new stretch starts after every cue), and the cues with their times."""
    flat = [(token, index) for index, word in enumerate(words) for token in tokens(word["text"])]
    cue_words: dict[int, int] = {}      # word index -> cue number
    cues: list[dict] = []
    at = 0
    while at < len(flat):
        for phrase in phrases:
            size = len(phrase["tokens"])
            if phrase["action"] == "end" and at + size != len(flat):
                continue   # an end cue only counts as the last thing said in the recording
            if [t for t, _ in flat[at:at + size]] == phrase["tokens"]:
                covered = sorted({index for _, index in flat[at:at + size]})
                cues.append({"say": phrase["say"], "action": phrase["action"],
                             "start": words[covered[0]]["start"], "end": words[covered[-1]]["end"]})
                for index in covered:
                    cue_words[index] = len(cues) - 1
                at += size
                break
        else:
            at += 1
    kept, stretch, last_cue = [], 0, None
    for index, word in enumerate(words):
        if index in cue_words:
            if cue_words[index] != last_cue:
                stretch, last_cue = stretch + 1, cue_words[index]
            continue
        kept.append({**word, "stretch": stretch})
    return kept, cues


def utterances(words: list[dict], gap: float) -> list[dict]:
    """Words grouped into readings: a new one after a pause, after a sentence end and a short pause,
    or after a spoken cue."""
    groups: list[list[dict]] = []
    for word in words:
        if groups:
            previous = groups[-1][-1]
            pause = word["start"] - previous["end"]
            if word.get("stretch") == previous.get("stretch") and pause < gap and not (re.search(r"[.?!][\"')\]]*$", previous["text"]) and pause >= gap / 2):
                groups[-1].append(word)
                continue
        groups.append([word])
    return [reading_of(g) for g in groups]


def reading_of(words: list[dict]) -> dict:
    text = " ".join(w["text"] for w in words)
    return {"text": text, "start": words[0]["start"], "end": words[-1]["end"], "tokens": tokens(text), "words": list(words)}


def script_ideas(path: Path) -> list[dict]:
    """The script as ideas: one per sentence, each with its words and where they sit in the script."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)                 # code blocks are not read aloud
    text = re.sub(r"^\s*#.*$", "", text, flags=re.M)                   # headings are not read aloud
    text = re.sub(r"^\s*([-*>]|\d+\.)\s*", "", text, flags=re.M)        # list and quote markers
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)                # links: keep their words
    ideas, at = [], 0
    for sentence in re.split(r"(?<=[.?!])\s+|\n\s*\n|\n", text):
        words = tokens(sentence)
        if words:
            ideas.append({"text": " ".join(sentence.split()), "tokens": words, "from": at, "to": at + len(words)})
            at += len(words)
    return ideas


def place_in_script(reading: list[str], script: list[str]) -> tuple[int, int] | None:
    """The stretch of the script this reading covers, as word positions, or None when it is not
    from the script."""
    if not reading:
        return None
    matcher = difflib.SequenceMatcher(None, script, reading, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size]
    if not blocks:
        return None
    # the words of one reading sit together in the script: keep the blocks around the largest one
    anchor = max(blocks, key=lambda b: b.size)
    reach = len(reading) + 4
    near = [b for b in blocks if abs(b.a - anchor.a) <= reach and (b.size >= 2 or len(reading) <= 3)] or [anchor]
    matched = sum(b.size for b in near)
    if matched < 2:   # one word in common is not a reading of the script
        return None
    # mostly script words, or (when the speaker said other things around it) a good run of them
    if matched / len(reading) < 0.6 and matched < 5:
        return None
    return min(b.a for b in near), max(b.a + b.size for b in near)


def sort_by_idea(readings: list[dict], ideas: list[dict] | None) -> list[dict]:
    """Put every reading under an idea; none is left out. With a script, an idea is a script
    sentence and a reading belongs to the sentence it shares most words with. Without one, a reading
    joins an earlier idea when it starts with the same words, and otherwise starts a new idea.
    Returns the ideas that have readings, in the order they should play."""
    groups: list[dict] = []
    if ideas:
        script = [w for idea in ideas for w in idea["tokens"]]
        by_sentence: dict[int, dict] = {}
        for r in readings:
            place = place_in_script(r["tokens"], script)
            if place is None:
                groups.append({"text": r["text"], "scripted": False, "order": (len(ideas), r["start"]), "readings": [r]})
                continue
            overlap = [max(0, min(place[1], idea["to"]) - max(place[0], idea["from"])) for idea in ideas]
            best = max(range(len(ideas)), key=lambda i: overlap[i])
            r["covers"] = round(overlap[best] / len(ideas[best]["tokens"]), 2)
            if best not in by_sentence:
                by_sentence[best] = {"text": ideas[best]["text"], "scripted": True, "order": (best, 0.0), "readings": []}
                groups.append(by_sentence[best])
            by_sentence[best]["readings"].append(r)
        # unscripted remarks stay where they were said: after the scripted idea spoken before them
        last_order = (-1, 0.0)
        for r in sorted(readings, key=lambda r: r["start"]):
            group = next(g for g in groups if r in g["readings"])
            if group["scripted"]:
                last_order = group["order"]
            else:
                group["order"] = (last_order[0], 1.0 + r["start"])
    else:
        for r in readings:
            head = r["tokens"][:6]
            home = None
            for group in reversed(groups[-4:]):
                first = group["readings"][0]["tokens"]
                size = min(len(head), len(first), 6)
                if size >= 2 and difflib.SequenceMatcher(None, head[:size], first[:size], autojunk=False).ratio() >= 0.8:
                    home = group
                    break
            if home is None:
                home = {"text": r["text"], "scripted": False, "order": (len(groups), 0.0), "readings": []}
                groups.append(home)
            home["readings"].append(r)
        for group in groups:   # name the idea after its fullest reading
            group["text"] = max(group["readings"], key=lambda r: len(r["tokens"]))["text"]
    groups.sort(key=lambda g: g["order"])
    for group in groups:
        group["readings"].sort(key=lambda r: r["start"])
        # suggested: the fullest reading, and the latest of those, since a retake is usually the fix
        fullest = max(r.get("covers", len(r["tokens"])) for r in group["readings"])
        tolerance = 0.05 if group["scripted"] else 1
        best = [r for r in group["readings"] if r.get("covers", len(r["tokens"])) >= fullest - tolerance][-1]
        for r in group["readings"]:
            r["suggested"] = r is best
    return groups


def same_opening(a: list[str], b: list[str]) -> bool:
    size = min(len(a), len(b), 6)
    return size >= 2 and difflib.SequenceMatcher(None, a[:size], b[:size], autojunk=False).ratio() >= 0.8


def script_part(clip: dict, script: list[str]) -> tuple[int, int, int, int] | None:
    """Where a clip reads the script: the script words it covers (from, to) and the clip's own
    words that do so (first, last), or None when it is not a reading of the script."""
    reading = clip["tokens"]
    every = [b for b in difflib.SequenceMatcher(None, script, reading, autojunk=False).get_matching_blocks() if b.size]
    blocks = [b for b in every if b.size >= 2]
    if sum(b.size for b in blocks) < max(3, 0.3 * min(len(reading), len(script))):
        return None
    # a single matching word counts only when it sits right beside the run, as the last word of
    # "just me and an AI" does when the speaker drops the "an"
    for b in [x for x in every if x.size == 1 and x.a > blocks[-1].a]:
        if b.a - (blocks[-1].a + blocks[-1].size) <= 2 and b.b - (blocks[-1].b + blocks[-1].size) <= 2:
            blocks.append(b)
    for b in reversed([x for x in every if x.size == 1 and x.a < blocks[0].a]):
        if blocks[0].a - (b.a + 1) <= 2 and blocks[0].b - (b.b + 1) <= 2:
            blocks.insert(0, b)
    owner = [index for index, word in enumerate(clip["words"]) for _ in tokens(word["text"])]   # token -> word
    return blocks[0].a, blocks[-1].a + blocks[-1].size, owner[blocks[0].b], owner[blocks[-1].b + blocks[-1].size - 1]


def alike_enough(a: list[str], b: list[str]) -> bool:
    """Whether two clips say the same thing: most of the shorter one is found, in order, in the other."""
    shared = sum(block.size for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return shared >= 0.6 * min(len(a), len(b)) and shared >= 2


def sort_by_cut(readings: list[dict], cues: list[dict], ideas: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Clips are what the speaker cut aloud: everything between two spoken cuts is one clip, and a
    clip also ends where the speaker starts the same words again, or calls one best. Clips that say
    the same thing are candidates for one scene. With a script, a clip is trimmed to the part that
    reads it, so talk to the director before or after is left out; what was trimmed is returned
    too, so that no cut reaches into it."""
    cuts = [c["start"] for c in cues if c["action"] == "cut"]
    bests = [c["start"] for c in cues if c["action"] == "best"]
    stretches: dict[int, list[dict]] = {}
    for r in sorted(readings, key=lambda r: r["start"]):
        clips = stretches.setdefault(sum(1 for at in cuts if at <= r["start"]), [])
        judged = clips and any(clips[-1]["end"] <= at <= r["start"] for at in bests)
        if clips and not judged and not same_opening(r["tokens"], clips[0]["tokens"]):
            clips[-1] = reading_of(clips[-1]["words"] + r["words"])
        else:
            clips.append(dict(r))
    clips = [clip for number in sorted(stretches) for clip in stretches[number]]

    script = [w for idea in ideas for w in idea["tokens"]] if ideas else None
    trimmed: list[dict] = []
    for index, clip in enumerate(clips):
        clip["part"] = None
        if not script:
            continue
        part = script_part(clip, script)
        if part is None:
            continue
        words = clip["words"]
        trimmed += [{"start": w["start"], "end": w["end"]} for w in words[:part[2]] + words[part[3] + 1:]]
        clips[index] = {**reading_of(words[part[2]:part[3] + 1]), "part": (part[0], part[1])}
        clips[index]["covers"] = round(difflib.SequenceMatcher(None, script[part[0]:part[1]], clips[index]["tokens"], autojunk=False).ratio()
                                       * (part[1] - part[0]) / len(script), 2)

    groups: list[dict] = []
    for clip in clips:
        home = None
        for group in groups:
            first = group["readings"][0]
            if script and (clip["part"] is None) != (first["part"] is None):
                continue
            if clip["part"] and first["part"]:
                shared = min(clip["part"][1], first["part"][1]) - max(clip["part"][0], first["part"][0])
                if shared >= 0.5 * min(clip["part"][1] - clip["part"][0], first["part"][1] - first["part"][0]):
                    home = group
                    break
            elif alike_enough(clip["tokens"], first["tokens"]):
                home = group
                break
        if home is None:
            home = {"scripted": not script or clip["part"] is not None, "order": (len(groups), 0.0), "readings": []}
            groups.append(home)
        home["readings"].append(clip)
    for group in groups:
        candidates = group["readings"]
        if script and candidates[0]["part"]:
            top = max(c["covers"] for c in candidates)            # the closest reading of the script,
            pick = [c for c in candidates if c["covers"] >= top - 0.02][-1]   # and the latest of those
        else:
            fullest = max(len(c["tokens"]) for c in candidates)
            pick = [c for c in candidates if len(c["tokens"]) >= 0.8 * fullest][-1]
        for c in candidates:
            c["suggested"] = c is pick
        group["text"] = pick["text"]
    return groups, trimmed


def apply_best(groups: list[dict], cues: list[dict]) -> None:
    """A spoken "best" picks the attempt that was just finished, over the automatic choice."""
    everything = sorted((r for g in groups for r in g["readings"]), key=lambda r: r["end"])
    for cue in cues:
        if cue["action"] != "best":
            continue
        before = [r for r in everything if r["end"] <= cue["start"] + 0.05]
        if not before:
            continue
        chosen = before[-1]
        group = next(g for g in groups if any(r is chosen for r in g["readings"]))
        for r in group["readings"]:
            r["suggested"] = r is chosen
        chosen["called_best"] = True
        if any("part" in r for r in group["readings"]):   # scenes cut aloud are named after their best clip
            group["text"] = chosen["text"]


def neighbours(r: dict, others: list[dict], length: float) -> tuple[float, float]:
    """The end of whatever comes before this reading and the start of whatever comes after it,
    counting other readings and spoken cues, so a cut never reaches into either."""
    before = max((o["end"] for o in others if o is not r and o["end"] <= r["start"] + 1e-6), default=0.0)
    after = min((o["start"] for o in others if o is not r and o["start"] >= r["end"] - 1e-6), default=length)
    return before, after


def tighten(readings: list[dict], cues: list[dict], sound, rate: int) -> None:
    """Move each reading's start and end onto the speech itself. The transcriber's word times can
    sit a few tenths of a second early or late, which would leave dead air at a jump cut."""
    import numpy as np
    hop = rate // 100
    usable = len(sound) - len(sound) % hop
    level = np.sqrt((sound[:usable].reshape(-1, hop) ** 2).mean(axis=1))
    if not len(level):
        return
    floor = float(np.percentile(level, 10))
    loud = float(np.percentile(level, 95))
    threshold = max(floor * 3.0, floor + (loud - floor) * 0.08)
    spans = [*readings, *cues]
    for r in readings:
        # look a little outside the reported times, but never into a neighbouring reading or cue
        before, after = neighbours(r, spans, len(level) / 100)
        lo = int(max(before, r["start"] - 0.4) * 100)
        hi = int(min(after, r["end"] + 0.4) * 100)
        speaking = np.nonzero(level[lo:hi] > threshold)[0]
        if len(speaking):
            r["start"], r["end"] = (lo + int(speaking[0])) / 100, (lo + int(speaking[-1]) + 1) / 100


def pad_ranges(readings: list[dict], cues: list[dict], pad: float, length: float) -> None:
    """Give each reading a little room, without reaching into a neighbouring reading or cue."""
    spans = [*readings, *cues]
    for r in readings:
        before, after = neighbours(r, spans, length)
        r["cut_start"] = max(0.0, r["start"] - min(pad, max(0.0, (r["start"] - before) / 2)))
        r["cut_end"] = min(length, r["end"] + min(pad, max(0.0, (after - r["end"]) / 2)))


# ---------------------------------------------------------------- cutting

def encoder() -> list[str]:
    probe = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x144:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True,
    )
    if probe.returncode == 0:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def cut_piece(camera: Path | None, studio: Path, piece: dict, offset: float, target: Path, video_args: list[str]) -> None:
    length = piece["cut_end"] - piece["cut_start"]
    command = ["ffmpeg", "-v", "error", "-y"]
    if camera:
        command += ["-ss", f"{piece['camera_start']:.3f}", "-t", f"{length:.3f}", "-i", str(camera)]
    command += ["-ss", f"{piece['cut_start']:.3f}", "-t", f"{length:.3f}", "-i", str(studio)]
    if camera:
        command += ["-map", "0:v:0", "-map", "1:a:0", *video_args, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        command += ["-map", "0:a:0", "-c:a", "pcm_s16le"]
    command.append(str(target))
    try:
        run(command)
    except subprocess.CalledProcessError as error:
        fail(f"ffmpeg could not cut {target.name}: {error.stderr.decode(errors='replace').strip()[-400:]}")


def scene_folder(number: str, text: str) -> str:
    words = "-".join(tokens(text)[:6]).replace("'", "")
    return f"{number}-{words[:48] or 'scene'}"


def scene_numbers(manifest: dict, recording: str, count: int) -> list[str]:
    """The numbers this recording's scenes get. Cutting a recording again keeps its numbers; a new
    recording carries on after the last scene. Numbers never move under scenes already cut."""
    mine = [sc["number"] for sc in manifest["scenes"] if sc["recording"] == recording]
    others = [int(sc["number"]) for sc in manifest["scenes"] if sc["recording"] != recording]
    if mine and len(mine) == count:
        return mine
    later = [sc for sc in manifest["scenes"] if sc["recording"] > recording]
    if mine and later:
        fail(f"recording {recording} now cuts into {count} scenes, not {len(mine)}, and recordings after it are already cut. "
             "Renumbering would break the timeline: cut it with the same scenes, or remove edit/scenes and cut every recording again in order.")
    if later:
        fail(f"recordings after {recording} are already cut; cut recordings in order")
    first = max(others, default=0) + 1
    return [f"{n:02d}" for n in range(first, first + count)]


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(prog="first-edit/launch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("take", type=Path, metavar="recording", help="a recording folder: <video folder>/raw/<nn>")
    parser.add_argument("--pad", type=float, default=0.15, help="seconds kept before and after each clip (default 0.15)")
    parser.add_argument("--gap", type=float, default=0.6, help="without spoken cuts, a pause this long starts a new clip (default 0.6)")
    parser.add_argument("--model", help="Whisper model (default medium.en on a GPU, small.en on the CPU)")
    parser.add_argument("--language", help="spoken language code; default is the model's own guess")
    parser.add_argument("--max-offset", type=float, default=30.0, help="largest gap to look for between camera and studio starts (default 30 s)")
    parser.add_argument("--glossary", type=Path, default=Path(__file__).resolve().parent / "glossary.json",
                        help="the spoken cues to listen for (default first-edit/glossary.json)")
    parser.add_argument("--plan", action="store_true", help="decide and print, but write nothing")
    parser.add_argument("--force", action="store_true", help="cut even when the alignment check fails")
    args = parser.parse_args()

    take = args.take.resolve()
    if not take.is_dir():
        fail(f"{args.take} is not a folder")
    if take.parent.name != "raw":
        fail(f"{args.take} is not a recording folder: expected <video folder>/raw/<nn>")
    video, recording = take.parent.parent, take.name
    scenes_dir = video / "edit" / "scenes"
    manifest_file = scenes_dir / "scenes.json"
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fail(f"{tool} is not installed")
    studio = take / "studio.wav"
    videos = sorted(p for p in take.iterdir() if p.suffix.lower() in VIDEO_TYPES and p.is_file())
    camera = (take / "camera.mp4") if (take / "camera.mp4").exists() else (videos[0] if videos else None)
    if not studio.exists():
        if camera and has_stream(camera, "a"):
            print("first-edit: no studio.wav; using the camera's own sound", file=sys.stderr)
            studio = camera
        else:
            fail(f"no studio.wav in {take}")
    script_file = take / "script.md"
    ideas = script_ideas(script_file) if script_file.exists() else None

    alignment = {"offset": 0.0, "clear": None, "alike": None, "drift": None, "ok": True}
    if camera and studio != camera:
        if not has_stream(camera, "a"):
            fail(f"{camera.name} has no sound to align with studio.wav")
        print(f"aligning {camera.name} to {studio.name}…", flush=True)
        alignment = align(camera, studio, args.max_offset)
        drift = "" if alignment["drift"] is None else f", drift {alignment['drift']:+.3f} s"
        print(f"  studio = camera {alignment['offset']:+.3f} s (clear {alignment['clear']}, alike {alignment['alike']}{drift})")
        if not alignment["ok"] and not args.force:
            fail("the two recordings do not line up clearly (needs alike >= 0.5, or alike >= 0.25 with clear >= 1.5, and no drift). "
                 "Nothing was cut; a person should look, or pass --force.")

    print(f"transcribing {studio.name}…", flush=True)
    sound = mono(studio, 16000)   # decoded with ffmpeg, which reads whatever the recorder wrote
    words, engine = transcribe(sound, args.model, args.language)
    if not words:
        fail("no speech found in the studio audio")
    length = duration_of(studio)
    words, cues = take_out_cues(words, load_glossary(args.glossary))
    if not words:
        fail("only spoken cues were found in the studio audio")
    readings = utterances(words, args.gap)
    readings.sort(key=lambda r: r["start"])
    tighten(readings, cues, sound, 16000)
    by_cut = any(c["action"] == "cut" for c in cues)
    trimmed: list[dict] = []
    if by_cut:
        groups, trimmed = sort_by_cut(readings, cues, ideas)
    else:
        groups = sort_by_idea(readings, ideas)
    apply_best(groups, cues)
    readings = [r for g in groups for r in g["readings"]]
    barriers = [*cues, *trimmed]
    if by_cut:
        tighten(readings, barriers, sound, 16000)   # clips were joined and trimmed since the first pass
    pad_ranges(readings, barriers, args.pad, length)

    manifest = {"video": video.name, "recordings": {}, "scenes": []}
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    numbers = scene_numbers(manifest, recording, len(groups))

    camera_length = duration_of(camera) if camera else None
    extension = ".mp4" if camera else ".wav"
    listed, jobs, outside = [], [], 0
    for number, group in zip(numbers, groups):
        folder_name = scene_folder(number, group["text"])
        entry = {"number": number, "scene": group["text"], "recording": recording, "in_script": group["scripted"], "folder": folder_name, "clips": []}
        for index, r in enumerate(group["readings"], 1):
            r["camera_start"] = r["cut_start"] - alignment["offset"]
            # a clip the camera did not film (it started late or stopped early) is kept as sound
            filmed = bool(camera) and r["camera_start"] >= 0 and r["camera_start"] + (r["cut_end"] - r["cut_start"]) <= camera_length + 0.05
            outside += bool(camera) and not filmed
            file = f"{folder_name}/{number}-{index:02d}{'-best' if r['suggested'] else ''}{extension if filmed or not camera else '.wav'}"
            entry["clips"].append({
                "file": file,
                "text": r["text"],
                "best": r["suggested"],
                "called_best": bool(r.get("called_best")),
                "covers_script_line": r.get("covers"),
                "studio_start": round(r["cut_start"], 3), "studio_end": round(r["cut_end"], 3),
                "camera_start": round(r["camera_start"], 3) if filmed else None,
                "duration": round(r["cut_end"] - r["cut_start"], 3),
            })
            jobs.append((file, r, filmed))
        listed.append(entry)

    total = sum(r["duration"] for e in listed for r in e["clips"])
    best_total = sum(r["duration"] for e in listed for r in e["clips"] if r["best"])
    report = {
        "camera": camera.name if camera else None,
        "studio": studio.name,
        "script": script_file.name if ideas else None,
        "alignment": alignment,
        "transcription": engine,
        "settings": {"pad": args.pad, "gap": args.gap},
        "scenes_from": "spoken cuts" if by_cut else ("script" if ideas else "similar openings"),
        "cues": [{"say": c["say"], "action": c["action"], "at": round(c["start"], 3)} for c in cues],
        "seconds": round(length, 3),
        "speech_seconds": round(total, 3),
        "best_seconds": round(best_total, 3),
    }
    if ideas and not by_cut:
        heard = {e["scene"] for e in listed if e["in_script"]}
        report["script_lines_not_heard"] = [i["text"] for i in ideas if i["text"] not in heard]

    if not args.plan:
        for old in [sc for sc in manifest["scenes"] if sc["recording"] == recording]:
            shutil.rmtree(scenes_dir / old["folder"], ignore_errors=True)   # this recording's earlier cut
        (video / "edit" / "final").mkdir(parents=True, exist_ok=True)
        video_args = encoder() if camera else []
        for file, r, filmed in jobs:
            (scenes_dir / file).parent.mkdir(parents=True, exist_ok=True)
            print(f"  cutting {file}  ({r['cut_end'] - r['cut_start']:.1f} s)", flush=True)
            cut_piece(camera if filmed else None, studio, r, alignment["offset"], scenes_dir / file, video_args)
        manifest["recordings"][recording] = report
        manifest["scenes"] = sorted([sc for sc in manifest["scenes"] if sc["recording"] != recording] + listed, key=lambda sc: sc["number"])
        manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nrecording {recording}: {len(jobs)} clips in {len(listed)} scenes, all kept: {total:.1f} s of speech in "
          f"{length:.1f} s; the best clips run {best_total:.1f} s")
    for entry in listed:
        print(f"\n  {entry['number']}  {entry['scene']}" + ("" if entry["in_script"] or not ideas else "   (not in the script)"))
        for index, r in enumerate(entry["clips"], 1):
            mark = "**" if r["called_best"] else ("* " if r["best"] else "  ")
            print(f"      {mark} {index:02d}  {r['studio_start']:7.2f}–{r['studio_end']:7.2f}  {r['text']}")
    if report.get("script_lines_not_heard"):
        print("\n  script lines not heard in this recording:")
        for line in report["script_lines_not_heard"]:
            print(f"      {line}")
    if outside:
        print(f"\n  {outside} clip(s) fall outside the camera recording and were kept as sound only")
    if cues:
        print("\n  cues heard: " + ", ".join(f"\"{c['say']}\" at {c['start']:.1f} s" for c in cues))
    print(f"\n*  best clip   ** called best aloud   (scenes from {report['scenes_from']})")
    print("plan only: nothing was written" if args.plan else str(manifest_file))


if __name__ == "__main__":
    use_gpu_libraries()
    main()
