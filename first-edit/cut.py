# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "faster-whisper>=1.1",
#   "numpy>=1.26",
#   "nvidia-cublas-cu12",
#   "nvidia-cudnn-cu12>=9,<10",
# ]
# ///
"""First edit of one take: align the camera's scratch audio to the studio audio, transcribe the
studio audio, cut every reading into its own piece, and sort the pieces by idea.

    first-edit/launch <take folder> [options]

A take folder holds a camera clip (camera.mp4, or any one video file), studio.wav and, optionally,
script.md. Nothing is thrown away: every reading is kept, and readings of the same idea (a line and
its retakes and false starts) go in one folder:

    <take folder>/pieces/b-<idea words>/reading-1.mp4, reading-2.mp4, ...

Idea folders are lettered a, b, c ... in playing order (aa, ab ... past 26), so they sort by name.
    <take folder>/pieces.json     every idea and reading, with times, and which reading is suggested

Picture comes from the camera, sound from the studio microphone.
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

def correlate(a, b, max_lag: int):
    """Where `a` best lines up inside `b`: the lag k (in samples, -max_lag..max_lag) that maximises
    sum a[n] * b[n + k], and how far that peak stands above the rest, in standard deviations."""
    import numpy as np
    a = a - a.mean()
    b = b - b.mean()
    size = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.conj(np.fft.rfft(a, size)) * np.fft.rfft(b, size), size)
    max_lag = min(max_lag, size // 2 - 1)
    window = np.concatenate([c[-max_lag:], c[: max_lag + 1]])     # lags -max_lag .. +max_lag
    peak = int(np.argmax(window))
    spread = float(window.std()) or 1.0
    return peak - max_lag, float((window[peak] - window.mean()) / spread)


def envelope(x):
    import numpy as np
    usable = len(x) - len(x) % ENVELOPE_HOP
    frames = x[:usable].reshape(-1, ENVELOPE_HOP)
    return np.log1p(1000.0 * np.sqrt((frames ** 2).mean(axis=1)))


def offset_between(scratch, studio, max_seconds: float):
    """Seconds to add to a camera time to get the studio time of the same moment, and a score.
    Loudness envelopes find it to 10 ms whatever the microphones did to the waveform; the waveforms
    then refine it when they agree."""
    lag, score = correlate(envelope(scratch), envelope(studio), int(max_seconds * ALIGN_RATE / ENVELOPE_HOP))
    coarse = lag * ENVELOPE_HOP
    reach = 2 * ENVELOPE_HOP
    span = min(len(scratch), ALIGN_RATE * 120)
    start = max(0, min(len(scratch) - span, (len(scratch) - span) // 2))
    a = scratch[start:start + span]
    lo = start + coarse - reach
    if lo >= 0 and lo + span + 2 * reach <= len(studio):
        fine, fine_score = correlate(a, studio[lo:lo + span + 2 * reach], 2 * reach)
        # `a` sits `reach` samples into that window when the coarse answer is exact
        if fine_score > 8:
            return (coarse + fine - reach) / ALIGN_RATE, score
    return coarse / ALIGN_RATE, score


def align(camera: Path, studio: Path, max_seconds: float) -> dict:
    scratch_audio, studio_audio = mono(camera, ALIGN_RATE), mono(studio, ALIGN_RATE)
    if len(scratch_audio) < ALIGN_RATE or len(studio_audio) < ALIGN_RATE:
        fail("the camera clip or studio.wav has under a second of sound; cannot align them")
    offset, score = offset_between(scratch_audio, studio_audio, max_seconds)
    result = {"offset": round(offset, 3), "score": round(score, 1), "drift": None, "ok": score >= 6}
    # the same answer near the start and near the end rules out drift between the two recorders
    third = len(scratch_audio) // 3
    if third >= ALIGN_RATE * 10:
        shift = int(offset * ALIGN_RATE)
        ends = []
        for begin in (0, len(scratch_audio) - third):
            lo, hi = begin + shift - ALIGN_RATE * 2, begin + shift + third + ALIGN_RATE * 2
            if lo < 0 or hi > len(studio_audio):
                continue
            lag, part_score = correlate(envelope(scratch_audio[begin:begin + third]), envelope(studio_audio[lo:hi]), ALIGN_RATE * 4 // ENVELOPE_HOP)
            if part_score >= 6:
                ends.append(lag * ENVELOPE_HOP / ALIGN_RATE - 2.0)
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


def utterances(words: list[dict], gap: float) -> list[dict]:
    """Words grouped into readings: a new one after a pause, or after a sentence end and a short pause."""
    groups: list[list[dict]] = []
    for word in words:
        if groups:
            previous = groups[-1][-1]
            pause = word["start"] - previous["end"]
            if pause < gap and not (re.search(r"[.?!][\"')\]]*$", previous["text"]) and pause >= gap / 2):
                groups[-1].append(word)
                continue
        groups.append([word])
    return [
        {"text": " ".join(w["text"] for w in g), "start": g[0]["start"], "end": g[-1]["end"], "tokens": tokens(" ".join(w["text"] for w in g))}
        for g in groups
    ]


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
    if matched / len(reading) < 0.6 or (matched < 2 and len(reading) > 2):
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


def tighten(readings: list[dict], sound, rate: int) -> None:
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
    for index, r in enumerate(readings):
        # look a little outside the reported times, but never into a neighbouring reading
        before = readings[index - 1]["end"] if index else 0.0
        after = readings[index + 1]["start"] if index + 1 < len(readings) else len(level) / 100
        lo = int(max(before, r["start"] - 0.4) * 100)
        hi = int(min(after, r["end"] + 0.4) * 100)
        speaking = np.nonzero(level[lo:hi] > threshold)[0]
        if len(speaking):
            r["start"], r["end"] = (lo + int(speaking[0])) / 100, (lo + int(speaking[-1]) + 1) / 100


def pad_ranges(readings: list[dict], pad: float, length: float) -> None:
    """Give each reading a little room, without reaching into a neighbouring reading."""
    for index, r in enumerate(readings):
        before = readings[index - 1]["end"] if index else 0.0
        after = readings[index + 1]["start"] if index + 1 < len(readings) else length
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


def letters(number: int, width: int) -> str:
    """1 -> a, 2 -> b ... as `width` letters, so folder names sort in playing order."""
    out, n = "", number - 1
    for _ in range(width):
        out, n = chr(ord("a") + n % 26) + out, n // 26
    return out


def name_for(number: int, total: int, text: str) -> str:
    width = 1
    while 26 ** width < total:
        width += 1
    words = "-".join(tokens(text)[:6]).replace("'", "")
    return f"{letters(number, width)}-{words[:48] or 'idea'}"


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(prog="first-edit/launch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("take", type=Path, help="the take folder")
    parser.add_argument("--pad", type=float, default=0.15, help="seconds kept before and after each reading (default 0.15)")
    parser.add_argument("--gap", type=float, default=0.6, help="a pause this long starts a new piece (default 0.6)")
    parser.add_argument("--model", help="Whisper model (default medium.en on a GPU, small.en on the CPU)")
    parser.add_argument("--language", help="spoken language code; default is the model's own guess")
    parser.add_argument("--max-offset", type=float, default=30.0, help="largest gap to look for between camera and studio starts (default 30 s)")
    parser.add_argument("--plan", action="store_true", help="decide and write pieces.json, but cut nothing")
    parser.add_argument("--force", action="store_true", help="cut even when the alignment check fails")
    args = parser.parse_args()

    take = args.take.resolve()
    if not take.is_dir():
        fail(f"{args.take} is not a folder")
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

    alignment = {"offset": 0.0, "score": None, "drift": None, "ok": True}
    if camera and studio != camera:
        if not has_stream(camera, "a"):
            fail(f"{camera.name} has no sound to align with studio.wav")
        print(f"aligning {camera.name} to {studio.name}…", flush=True)
        alignment = align(camera, studio, args.max_offset)
        drift = "" if alignment["drift"] is None else f", drift {alignment['drift']:+.3f} s"
        print(f"  studio = camera {alignment['offset']:+.3f} s (score {alignment['score']}{drift})")
        if not alignment["ok"] and not args.force:
            fail("the two recordings do not line up clearly (low score, or the offset moves through the take). "
                 "Nothing was cut; a person should look, or pass --force.")

    print(f"transcribing {studio.name}…", flush=True)
    sound = mono(studio, 16000)   # decoded with ffmpeg, which reads whatever the recorder wrote
    words, engine = transcribe(sound, args.model, args.language)
    if not words:
        fail("no speech found in the studio audio")
    length = duration_of(studio)
    readings = utterances(words, args.gap)
    readings.sort(key=lambda r: r["start"])
    tighten(readings, sound, 16000)
    pad_ranges(readings, args.pad, length)
    groups = sort_by_idea(readings, ideas)

    camera_length = duration_of(camera) if camera else None
    extension = ".mp4" if camera else ".wav"
    listed, jobs, outside = [], [], 0
    for number, group in enumerate(groups, 1):
        folder_name = name_for(number, len(groups), group["text"])
        entry = {"number": number, "letter": folder_name.split("-")[0], "idea": group["text"], "in_script": group["scripted"], "folder": f"pieces/{folder_name}", "readings": []}
        for index, r in enumerate(group["readings"], 1):
            r["camera_start"] = r["cut_start"] - alignment["offset"]
            # a reading the camera did not film (it started late or stopped early) is kept as sound
            filmed = bool(camera) and r["camera_start"] >= 0 and r["camera_start"] + (r["cut_end"] - r["cut_start"]) <= camera_length + 0.05
            outside += bool(camera) and not filmed
            file = f"pieces/{folder_name}/reading-{index}{extension if filmed or not camera else '.wav'}"
            entry["readings"].append({
                "file": file,
                "text": r["text"],
                "suggested": r["suggested"],
                "covers_idea": r.get("covers"),
                "studio_start": round(r["cut_start"], 3), "studio_end": round(r["cut_end"], 3),
                "camera_start": round(r["camera_start"], 3) if filmed else None,
                "duration": round(r["cut_end"] - r["cut_start"], 3),
            })
            jobs.append((file, r, filmed))
        listed.append(entry)

    if not args.plan:
        folder = take / "pieces"
        if folder.exists():
            shutil.rmtree(folder)
        video_args = encoder() if camera else []
        for file, r, filmed in jobs:
            (take / file).parent.mkdir(parents=True, exist_ok=True)
            print(f"  cutting {file}  ({r['cut_end'] - r['cut_start']:.1f} s)", flush=True)
            cut_piece(camera if filmed else None, studio, r, alignment["offset"], take / file, video_args)

    total = sum(r["duration"] for e in listed for r in e["readings"])
    suggested = sum(r["duration"] for e in listed for r in e["readings"] if r["suggested"])
    manifest = {
        "take": take.name,
        "camera": camera.name if camera else None,
        "studio": studio.name,
        "script": script_file.name if ideas else None,
        "alignment": alignment,
        "transcription": engine,
        "settings": {"pad": args.pad, "gap": args.gap},
        "cut": not args.plan,
        "take_seconds": round(length, 3),
        "readings": len(jobs),
        "speech_seconds": round(total, 3),
        "suggested_seconds": round(suggested, 3),
        "ideas": listed,
    }
    if ideas:
        heard = {e["idea"] for e in listed if e["in_script"]}
        manifest["script_lines_not_heard"] = [i["text"] for i in ideas if i["text"] not in heard]
    (take / "pieces.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n{len(jobs)} readings in {len(listed)} ideas, all kept: {total:.1f} s of speech in a {length:.1f} s take; "
          f"the suggested readings run {suggested:.1f} s")
    for entry in listed:
        print(f"\n  {entry['letter']:>2}  {entry['idea']}" + ("" if entry["in_script"] or not ideas else "   (not in the script)"))
        for r in entry["readings"]:
            print(f"      {'*' if r['suggested'] else ' '} {r['studio_start']:7.2f}–{r['studio_end']:7.2f}  {r['text']}")
    if manifest.get("script_lines_not_heard"):
        print("\n  script lines not heard in this take:")
        for line in manifest["script_lines_not_heard"]:
            print(f"      {line}")
    if outside:
        print(f"\n  {outside} reading(s) fall outside the camera clip and were kept as sound only")
    print(f"\n* suggested reading of each idea\n{take / 'pieces.json'}")


if __name__ == "__main__":
    use_gpu_libraries()
    main()
