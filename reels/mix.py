"""Mix a reel's sound losslessly from its composition: every <audio> clip in the project's index.html
(data-start, data-duration, data-media-start, data-volume and the voice's data-fx-chain EQ), mixed
in ffmpeg from the original files into one 24-bit 48 kHz stereo WAV. reels/finish takes the picture
from the render and this sound, so the reel's only lossy audio encode is the final one.

    reels/mix <nnnn-slug> [-o <file>]     (default: <content root>/<slug>/edit/final/<slug>-mix.wav)

The composition's EQ nodes become ffmpeg filters (highpass, low and high shelves, peaking). A
compressor node is not copied: reels/finish compresses the whole mix once.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"reels/mix: {message}", file=sys.stderr)
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


class Audio(HTMLParser):
    def __init__(self):
        super().__init__()
        self.clips, self.total = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("data-composition-id") == "main" and a.get("data-duration"):
            self.total = float(a["data-duration"])
        if tag == "audio" and a.get("src"):
            self.clips.append(a)


def eq_filters(chain: str | None) -> list[str]:
    if not chain:
        return []
    out = []
    for node in json.loads(html.unescape(chain)).get("nodes", []):
        k, q = node.get("type"), node.get("params", {})
        if k == "highpass":
            out.append(f"highpass=f={q['frequency']}")
        elif k == "lowpass":
            out.append(f"lowpass=f={q['frequency']}")
        elif k == "lowshelf":
            out.append(f"lowshelf=f={q['frequency']}:g={q['gain']}")
        elif k == "highshelf":
            out.append(f"highshelf=f={q['frequency']}:g={q['gain']}")
        elif k == "peaking":
            out.append(f"equalizer=f={q['frequency']}:t=q:w={q.get('q', 1)}:g={q['gain']}")
        elif k == "compressor":
            continue   # reels/finish compresses the whole mix once
        else:
            print(f"reels/mix: fx node {k!r} has no lossless equivalent here; skipped", file=sys.stderr)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(prog="reels/mix", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reel", metavar="nnnn-slug")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    project = REPO / "edit" / "projects" / args.reel
    page = project / "index.html"
    if not page.exists():
        fail(f"no {page}")
    found = Audio()
    found.feed(page.read_text(encoding="utf-8"))
    if not found.clips or not found.total:
        fail("no <audio> clips or no root duration in index.html")
    out = Path(args.output) if args.output else content_root() / args.reel / "edit" / "final" / f"{args.reel}-mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    inputs, chains = [], []
    for i, c in enumerate(found.clips):
        src = (project / c["src"]).resolve()
        if not src.exists():
            fail(f"missing {c['src']}")
        inputs += ["-i", str(src)]
        start, media = float(c.get("data-start", 0)), float(c.get("data-media-start", 0))
        dur = float(c.get("data-duration", found.total - start))
        vol = float(c.get("data-volume", 1))
        f = [f"atrim=start={media}:duration={dur}", "asetpts=PTS-STARTPTS", "aresample=48000",
             "aformat=sample_fmts=fltp:channel_layouts=stereo", *eq_filters(c.get("data-fx-chain")),
             f"volume={vol}", f"adelay={round(start * 1000)}:all=1"]
        chains.append(f"[{i}:a]{','.join(f)}[a{i}]")
    n = len(found.clips)
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(n)) + \
        f"amix=inputs={n}:normalize=0:dropout_transition=0,atrim=duration={found.total}[mix]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[mix]",
                    "-c:a", "pcm_s24le", "-ar", "48000", str(out)], check=True)
    print(f"wrote {out}: {n} clips, {found.total:.2f} s, 24-bit 48 kHz")


if __name__ == "__main__":
    main()
