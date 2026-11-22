# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26"]
# ///
"""Sync a reel's sound to its picture: pair each video pulled from Drive with the separate audio
recording of the same moment, and lay each pair out as a recording first edit can cut.

    reels/sync <nnnn-slug> [--plan] [--force] [--broll] [--min-alike 0.25] [--quiet-db -50]

Reads <content root>/<nnnn-slug>/drive/ (what reels/pull downloaded) and writes raw/:

    <reel>/
      drive/                 the Drive folder, as downloaded. Only read.
      raw/
        sync.json            every file: which recording it became, or why not, and each match
        01/  camera.mov -> ../../drive/IMG_0412.MOV   studio.wav (that video's stretch of the audio)
        02/  camera.mp4 -> ../../drive/IMG_0413.MP4   (no audio matched: first edit uses the camera's sound)

Each video is matched against every audio file by its scratch sound, with the same alignment first
edit uses (first-edit/cut.py). One long audio file may cover several videos: each recording gets
its own stretch of it, so first edit lines it up again within a second. A video with no sound of its
own, and every still image, is b-roll: listed in sync.json, not made a recording. Each b-roll
video is laid out as raw/broll/<name>.mp4, tone-mapped to Rec.709 when it is HDR.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "first-edit"))
import cut  # noqa: E402  first edit's alignment: mono(), align(), trusted(), has_stream(), duration_of()

AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".aif", ".aiff", ".ogg", ".opus"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
MARGIN = 1.0   # seconds of audio kept either side of the video's span


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"reels/sync: {message}", file=sys.stderr)
    sys.exit(1)


def content_root() -> Path:
    root = os.environ.get("CONTENT_ROOT", "")
    for source in (REPO / ".env", REPO / "PATH.md"):
        if root and root != "/path/to/content":
            break
        if source.exists():
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTENT_ROOT="):
                    root = line.split("=", 1)[1].strip().strip('"\'')
    if not root or root == "/path/to/content":
        fail("no content root: set CONTENT_ROOT in .env or PATH.md (see edit/README.md)")
    return Path(root)


def loudness(path: Path) -> float:
    """Mean volume of the file's sound in dB (volumedetect)."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split()[0])
    return -99.0


def match(video: Path, audio: Path, audio_length: float, video_length: float) -> dict | None:
    scratch, studio = cut.mono(video, cut.ALIGN_RATE), cut.mono(audio, cut.ALIGN_RATE)
    if len(scratch) < cut.ALIGN_RATE or len(studio) < cut.ALIGN_RATE:
        return None
    reach = audio_length + video_length   # the audio may start long before or after the camera
    offset, clear, alike = cut.offset_between(scratch, studio, reach)
    return {"audio": audio.name, "offset": round(offset, 3), "clear": round(clear, 2), "alike": round(alike, 2),
            "ok": cut.trusted(clear, alike)}


def make_broll(report: dict, pulled: Path, raw: Path) -> None:
    """Every b-roll video as raw/broll/<name>.mp4 the editor can use as it is: tone-mapped to
    Rec.709 when it is HDR (as phones record it), else a link to the Drive file."""
    folder = raw / "broll"
    folder.mkdir(parents=True, exist_ok=True)
    for entry in report["broll"]:
        source = pulled / entry["video"]
        target = folder / (Path(entry["video"]).stem.split(".")[0] + ".mp4")
        target.unlink(missing_ok=True)
        options = cut.picture_filter(source)
        if options:
            print(f"  b-roll {entry['video']}: HDR, tone-mapping to {target.relative_to(raw.parent)}", flush=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?", *cut.encoder(), *options,
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)], check=True)
        else:
            target.symlink_to(os.path.relpath(source, folder))
        entry["file"] = str(target.relative_to(raw))


def main() -> None:
    parser = argparse.ArgumentParser(prog="reels/sync", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reel", metavar="nnnn-slug")
    parser.add_argument("--plan", action="store_true", help="match and print; write nothing")
    parser.add_argument("--force", action="store_true", help="make raw/ again even though it has recordings")
    parser.add_argument("--quiet-db", type=float, default=-50.0, help="a video whose sound averages below this is b-roll (default -50 dB)")
    parser.add_argument("--broll", action="store_true", help="only (re)make raw/broll/; leave the recordings as they are")
    parser.add_argument("--min-alike", type=float, default=0.25, help="weakest match taken as the same moment (default 0.25)")
    args = parser.parse_args()

    reel = content_root() / args.reel
    pulled, raw = reel / "drive", reel / "raw"
    if not pulled.is_dir():
        fail(f"no {pulled}; run reels/pull (or reels/launch) first")
    made = sorted(p for p in raw.glob("[0-9][0-9]") if p.is_dir()) if raw.is_dir() else []
    if made and not args.force and not args.plan and not args.broll:
        fail(f"{raw} already has recordings ({', '.join(p.name for p in made)}); pass --force to make them again")

    files = sorted(p for p in pulled.iterdir() if p.is_file() and not p.name.startswith("."))
    videos = [p for p in files if p.suffix.lower() in cut.VIDEO_TYPES]
    audios = [p for p in files if p.suffix.lower() in AUDIO_TYPES]
    stills = [p for p in files if p.suffix.lower() in IMAGE_TYPES]
    if not videos:
        fail(f"no video in {pulled} ({', '.join(p.name for p in files) or 'empty'})")
    lengths = {p: cut.duration_of(p) for p in videos + audios}

    report = {"recordings": [], "broll": [], "stills": [p.name for p in stills], "audio_unused": [], "other": []}
    known = set(videos) | set(audios) | set(stills) | {pulled / "source.json", pulled / "prompt.md"}
    report["other"] = [p.name for p in files if p not in known]
    used: set[str] = set()
    number = 0
    for video in videos:
        if not cut.has_stream(video, "a"):
            report["broll"].append({"video": video.name, "why": "no sound of its own", "duration": round(lengths[video], 3)})
            print(f"  {video.name}: b-roll (no sound)")
            continue
        level = loudness(video)
        if level < args.quiet_db:
            report["broll"].append({"video": video.name, "why": f"near silent ({level:.1f} dB mean)", "duration": round(lengths[video], 3)})
            print(f"  {video.name}: b-roll (near silent, {level:.1f} dB)")
            continue
        tries = [m for a in audios if (m := match(video, a, lengths[a], lengths[video]))]
        good = sorted((m for m in tries if m["ok"] and m["alike"] >= args.min_alike), key=lambda m: -m["alike"])
        number += 1
        entry = {"recording": f"{number:02d}", "video": video.name, "duration": round(lengths[video], 3),
                 "audio": None, "tried": tries}
        if good:
            best = good[0]
            entry["audio"] = best
            used.add(best["audio"])
            print(f"  {entry['recording']}  {video.name}  <-  {best['audio']} at {best['offset']:+.3f} s (alike {best['alike']}, clear {best['clear']})")
        else:
            print(f"  {entry['recording']}  {video.name}  (no audio matched; the camera's own sound is used)")
        report["recordings"].append(entry)
    report["audio_unused"] = [a.name for a in audios if a.name not in used]
    for name in report["audio_unused"]:
        print(f"  {name}: matched no video", file=sys.stderr)

    if args.plan:
        print("plan only: nothing was written")
        return
    raw.mkdir(parents=True, exist_ok=True)
    if args.broll:
        make_broll(report, pulled, raw)
        old = json.loads((raw / "sync.json").read_text(encoding="utf-8")) if (raw / "sync.json").exists() else report
        old["broll"] = report["broll"]
        (raw / "sync.json").write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(report['broll'])} b-roll clips to {raw / 'broll'}")
        return
    for old in made:
        for child in old.iterdir():
            child.unlink()
        old.rmdir()
    for entry in report["recordings"]:
        folder = raw / entry["recording"]
        folder.mkdir()
        video = pulled / entry["video"]
        (folder / f"camera{video.suffix.lower()}").symlink_to(os.path.relpath(video, folder))
        if entry["audio"]:
            audio = pulled / entry["audio"]["audio"]
            start = max(0.0, entry["audio"]["offset"] - MARGIN)
            span = entry["duration"] + 2 * MARGIN
            entry["audio"]["studio_starts_at"] = round(start, 3)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", str(audio),
                            "-vn", "-c:a", "pcm_s24le", str(folder / "studio.wav")], check=True)
    make_broll(report, pulled, raw)
    (raw / "sync.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(report['recordings'])} recordings and {raw / 'sync.json'}")


if __name__ == "__main__":
    main()
