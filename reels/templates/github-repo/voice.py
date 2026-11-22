"""Step 2 of the GitHub repo reel template.

    python3 voice.py <content root>/<slug> plan.json frames.json <out.wav>

Lossless voice for a reel: the studio WAV cut exactly as reels/tighten cut each take (each kept range is
padded to the frames its picture got, as tighten's concat does), then as the plan cut the takes."""
import json, math, subprocess, sys
R, plan_path, frames_path, out = sys.argv[1:5]
plan = json.load(open(plan_path)); frames = json.load(open(frames_path))
scenes = json.load(open(f"{R}/edit/scenes/scenes.json"))
tight = json.load(open(f"{R}/edit/tight/tight.json"))["clips"]
start_of = {c["file"]: c["studio_start"] for s in scenes["scenes"] for c in s["clips"]}
FPS = 30
parts, labels = [], []
for n, p in enumerate(plan["pieces"]):
    lo_t, hi_t = p["media_start"], p["media_start"] + p["duration"]
    at, names = 0.0, []
    for i, (a, b) in enumerate(tight[p["file"]]["ranges"]):
        a3, b3 = float(f"{a:.3f}"), float(f"{b:.3f}")
        count = math.ceil(b3 * FPS - 1e-9) - math.ceil(a3 * FPS - 1e-9)     # frames with a <= t < b
        L = max(count / FPS, b3 - a3)                                        # the segment's length in the take
        x, y = max(lo_t, at), min(hi_t, at + L)
        if y > x + 1e-4:
            s0 = start_of[p["file"]] + a3 + (x - at)
            snd = max(0.0, min(y, at + (b3 - a3)) - x)                         # how much of it is sound
            nm = f"p{n}r{i}"
            fade_out = max(0.0, (b3 - a3) - 0.008 - (x - at))
            parts.append(f"[0:a]atrim=start={s0:.6f}:duration={snd:.6f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.008,afade=t=out:st={max(0.0, min(fade_out, snd - 0.008)):.6f}:d=0.008,"
                         f"apad=whole_dur={y - x:.6f},atrim=duration={y - x:.6f}[{nm}];")
            names.append(f"[{nm}]")
        at += L
    k = frames[n]
    parts.append("".join(names) + f"concat=n={len(names)}:v=0:a=1,apad=whole_dur={k / FPS:.6f},atrim=duration={k / FPS:.6f}[p{n}];")
    labels.append(f"[p{n}]")
graph = "".join(parts) + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[a]"
open(out + ".graph", "w").write(graph)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{R}/raw/01/studio.wav", "-filter_complex_script", out + ".graph",
                "-map", "[a]", "-c:a", "pcm_s24le", out], check=True)
print("wrote", out)
