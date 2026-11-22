# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26"]
# ///
"""Cut the silence out of a reel's clips: every pause inside a clip longer than --min-pause becomes
a jump cut, leaving --keep seconds of room either side so no word is clipped.

    reels/tighten <nnnn-slug> [--min-pause 0.3] [--keep 0.08] [--plan] [--force]

Reads the clips first edit cut (edit/scenes/, scenes.json) and writes a tightened copy of each,
same name, under edit/tight/, with edit/tight/tight.json listing every clip's kept ranges and new
length. The clips in edit/scenes/ are not changed, so a pause can be put back by using the original.

What counts as speech is decided per recording, from its studio.wav: above a level set between that
recording's noise floor and its speech (the same rule first edit uses to put clip edges on speech).
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
import cut  # noqa: E402  mono(), encoder(), duration_of()

RATE = 16000
HOP = RATE // 100          # 10 ms
FADE = 0.008               # seconds of fade at each audio join, against clicks


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"reels/tighten: {message}", file=sys.stderr)
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


def levels(path: Path):
    import numpy as np
    sound = cut.mono(path, RATE)
    usable = len(sound) - len(sound) % HOP
    return np.sqrt((sound[:usable].reshape(-1, HOP) ** 2).mean(axis=1))


def threshold_for(recording: Path) -> float:
    import numpy as np
    source = recording / "studio.wav"
    if not source.exists():
        source = next((p for p in sorted(recording.iterdir()) if p.suffix.lower() in cut.VIDEO_TYPES), None)
        if source is None:
            fail(f"no sound in {recording}")
    level = levels(source)
    floor, loud = float(np.percentile(level, 10)), float(np.percentile(level, 95))
    return max(floor * 3.0, floor + (loud - floor) * 0.08)


def keep_ranges(level, threshold: float, length: float, min_pause: float, keep: float) -> list[tuple[float, float]]:
    """The stretches to keep: speech, with every pause of min_pause or more cut down to 2 x keep."""
    import numpy as np
    speaking = np.nonzero(level > threshold)[0]
    if not len(speaking):
        return [(0.0, length)]
    runs, start, last = [], int(speaking[0]), int(speaking[0])
    for frame in speaking[1:]:
        frame = int(frame)
        if (frame - last) / 100 >= min_pause:
            runs.append((start, last + 1))
            start = frame
        last = frame
    runs.append((start, last + 1))
    ranges = [(max(0.0, a / 100 - keep), min(length, b / 100 + keep)) for a, b in runs]
    merged = [ranges[0]]
    for a, b in ranges[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def frame_rate(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True).stdout.strip()
    num, _, den = out.partition("/")
    return float(num) / float(den or 1) if out and float(num) else 30.0


def on_frames(ranges: list[tuple[float, float]], fps: float) -> list[tuple[float, float]]:
    """Put every cut on a frame boundary, so picture and sound are cut at the same instant and
    no drift builds up over many cuts."""
    snapped = [(round(a * fps) / fps, round(b * fps) / fps) for a, b in ranges]
    return [(a, b) for a, b in snapped if b > a]


def render(source: Path, target: Path, ranges: list[tuple[float, float]], video_args: list[str]) -> None:
    parts, labels = [], []
    for i, (a, b) in enumerate(ranges):
        fade_out = max(0.0, b - a - FADE)
        parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={FADE},afade=t=out:st={fade_out:.3f}:d={FADE}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(ranges)}:v=1:a=1[v][a]")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(source), "-filter_complex", ";".join(parts),
               "-map", "[v]", "-map", "[a]", *video_args, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(target)]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        fail(f"ffmpeg could not tighten {source.name}: {done.stderr.strip()[-400:]}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="reels/tighten", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reel", metavar="nnnn-slug")
    parser.add_argument("--min-pause", type=float, default=0.3, help="a pause this long or longer is cut out (default 0.3 s)")
    parser.add_argument("--keep", type=float, default=0.08, help="room kept either side of speech at a cut (default 0.08 s)")
    parser.add_argument("--plan", action="store_true", help="measure and print; write nothing")
    parser.add_argument("--force", action="store_true", help="tighten clips again even when edit/tight/ has them")
    args = parser.parse_args()

    reel = content_root() / args.reel
    scenes_dir, tight_dir = reel / "edit" / "scenes", reel / "edit" / "tight"
    manifest_file = scenes_dir / "scenes.json"
    if not manifest_file.exists():
        fail(f"no {manifest_file}; cut the recordings with first-edit/launch first")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    report_file = tight_dir / "tight.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else {}
    report.setdefault("settings", {})
    report["settings"] = {"min_pause": args.min_pause, "keep": args.keep}
    report.setdefault("clips", {})

    thresholds: dict[str, float] = {}
    video_args = None
    before = after = 0.0
    for scene in manifest["scenes"]:
        for clip in scene["clips"]:
            source = scenes_dir / clip["file"]
            if source.suffix.lower() != ".mp4" or not source.exists():
                continue
            target = tight_dir / clip["file"]
            recording = scene["recording"]
            if recording not in thresholds:
                thresholds[recording] = threshold_for(reel / "raw" / recording)
            length = cut.duration_of(source)
            ranges = on_frames(keep_ranges(levels(source), thresholds[recording], length, args.min_pause, args.keep), frame_rate(source))
            new_length = sum(b - a for a, b in ranges)
            before, after = before + length, after + new_length
            print(f"  {clip['file']}: {length:6.2f} s -> {new_length:6.2f} s  ({len(ranges) - 1} cuts)")
            if args.plan:
                continue
            if target.exists() and not args.force and report["clips"].get(clip["file"], {}).get("ranges") == [[round(a, 3), round(b, 3)] for a, b in ranges]:
                continue
            if video_args is None:
                video_args = cut.encoder()
            render(source, target, ranges, video_args)
            report["clips"][clip["file"]] = {"best": clip["best"], "text": clip["text"], "duration": round(cut.duration_of(target), 3),
                                             "original_duration": round(length, 3),
                                             "ranges": [[round(a, 3), round(b, 3)] for a, b in ranges]}
    print(f"\n{before:.1f} s of clips -> {after:.1f} s with the silence cut out ({before - after:.1f} s removed)")
    if args.plan:
        print("plan only: nothing was written")
        return
    tight_dir.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(report_file)


if __name__ == "__main__":
    main()
