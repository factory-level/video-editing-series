# /// script
# requires-python = ">=3.10"
# dependencies = ["piper-tts>=1.3", "numpy>=1.26"]
# ///
"""Make a stand-in take for trying first-edit without a camera: synthetic speech with a false
start, a retake and an unscripted remark, a camera clip whose scratch audio starts at a different
moment and is noisy, and the script.

    uv run first-edit/test/make-sample-take.py <take folder> [--cues]

With --cues the speaker directs the cut aloud instead: three scenes closed by "cut cut", the first
with three clips and a "best best" (see first-edit/glossary.json).

The camera starts 0.27 s before the studio recorder, so first-edit should report
"studio = camera -0.270 s".
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

RATE = 48000
CAMERA_LEAD = 0.27   # seconds the camera rolls before the studio recorder
VOICE = "en_US-lessac-medium"

SCRIPT = [
    "Welcome to the video editing series.",
    "Each take is uploaded to the edit server as soon as it is kept.",
    "A team of agents cuts every reading into its own piece.",
    "Nothing is thrown away, so you can always pick a different reading.",
    "Then the effects edit begins.",
]
# what is actually said, and the pause before it
PERFORMANCE = [
    (2.0, SCRIPT[0]),
    (0.9, "Each take is uploaded to the"),          # false start
    (1.2, SCRIPT[1]),
    (0.8, SCRIPT[2]),
    (2.5, SCRIPT[3]),
    (1.0, "Sorry, let me do that one again."),      # not in the script
    (0.9, SCRIPT[3]),                               # retake
    (0.7, SCRIPT[4]),
]


# the same idea, directed aloud: three topics, each closed by "cut cut"
CUE_SCRIPT = [
    "Welcome to the video editing series. Today we look at the first edit.",
    "Each take is uploaded to the edit server as soon as it is kept.",
    "A team of agents cuts every attempt into its own piece. Then the effects edit begins.",
]
CUE_PERFORMANCE = [
    (2.0, "Welcome to the video editing series. Today we look at the edit."),      # attempt 1: wrong words
    (1.2, "Welcome to the video"),                                                 # attempt 2: false start
    (1.0, CUE_SCRIPT[0]),                                                          # attempt 3
    (0.8, "Best best."),
    (0.7, "Cut cut."),
    (1.5, CUE_SCRIPT[1]),
    (0.8, "Cut cut."),
    (1.5, "A team of agents cuts every attempt."),                                 # attempt 1: stops short
    (1.2, CUE_SCRIPT[2]),                                                          # attempt 2
]


def say(text: str, folder: Path, voices: Path) -> np.ndarray:
    target = folder / "line.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "--data-dir", str(voices), "-f", str(target)],
                   input=text.encode(), check=True, capture_output=True)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(target), "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())


def main() -> None:
    cues = "--cues" in sys.argv
    where = [a for a in sys.argv[1:] if a != "--cues"]
    if len(where) != 1:
        sys.exit(__doc__)
    take = Path(where[0])
    script, performance = (CUE_SCRIPT, CUE_PERFORMANCE) if cues else (SCRIPT, PERFORMANCE)
    take.mkdir(parents=True, exist_ok=True)
    voices = Path.home() / ".cache" / "first-edit-test-voices"
    voices.mkdir(parents=True, exist_ok=True)
    if not (voices / f"{VOICE}.onnx").exists():
        subprocess.run([sys.executable, "-m", "piper.download_voices", VOICE, "--data-dir", str(voices)], check=True)

    rng = np.random.default_rng(7)
    parts = []
    with tempfile.TemporaryDirectory() as tmp:
        for pause, text in performance:
            parts += [np.zeros(int(pause * RATE), dtype=np.float32), say(text, Path(tmp), voices)]
    parts.append(np.zeros(int(1.5 * RATE), dtype=np.float32))
    speech = np.concatenate(parts)
    studio = speech + rng.normal(0, 0.0015, len(speech)).astype(np.float32)   # a quiet room
    write_wav(take / "studio.wav", studio)

    # the camera's own microphone: starts earlier, is quieter, duller and noisier
    scratch = np.concatenate([np.zeros(int(CAMERA_LEAD * RATE), dtype=np.float32), speech, np.zeros(RATE, dtype=np.float32)])
    scratch = np.convolve(scratch, np.ones(12, dtype=np.float32) / 12, mode="same") * 0.5
    scratch = scratch + rng.normal(0, 0.02, len(scratch)).astype(np.float32)
    seconds = len(scratch) / RATE
    with tempfile.TemporaryDirectory() as tmp:
        write_wav(Path(tmp) / "scratch.wav", scratch)
        subprocess.run([
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={seconds:.3f}",
            "-i", str(Path(tmp) / "scratch.wav"),
            "-vf", "drawtext=text='camera %{pts\\:hms}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.6:x=40:y=40",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-shortest", str(take / "camera.mp4"),
        ], check=True)
    (take / "script.md").write_text("# Sample take\n\n" + "\n".join(script) + "\n", encoding="utf-8")
    print(f"{take}: camera.mp4 ({seconds:.1f} s), studio.wav ({len(studio) / RATE:.1f} s), script.md")
    expected = "3 scenes (a, b, c) with 3, 1 and 2 clips; a3 called best" if cues else "8 clips in 6 scenes"
    print(f"expected: studio = camera {-CAMERA_LEAD:+.3f} s; {expected}")


if __name__ == "__main__":
    main()
