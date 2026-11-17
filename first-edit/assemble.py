"""Put a cut take on the raw timeline: a HyperFrames composition in edit/projects/<video-slug>/.

    first-edit/assemble <take folder> [--project <folder>] [--replace] [--plan]

Reads the take's pieces.json (written by first-edit/launch) and adds one clip per idea, in letter
order, using each idea's suggested reading. Alternate readings stay in the idea's folder; to use
one, change that clip's src. Remarks that are not in the script are left off the timeline.

Takes are appended: clips already on the timeline are never moved or rewritten, so edits a person
made stay. --replace removes this take's own clips first and adds them again at the end.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
START, END = "<!-- raw-timeline:start -->", "<!-- raw-timeline:end -->"
HYPERFRAMES = ["npx", "-y", "hyperframes@0.9.58"]

PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #000; }
      #root { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
      #root > video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    </style>
  </head>
  <body>
    <!-- The raw timeline: narration only, one clip per idea. first-edit/assemble appends takes between
         the two markers and never moves a clip that is already there. Effects belong to stage 2. -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="1" data-width="1920" data-height="1080">
      @START@
      @END@
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
""".replace("@START@", START).replace("@END@", END)


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"assemble: {message}", file=sys.stderr)
    sys.exit(1)


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def main() -> None:
    parser = argparse.ArgumentParser(prog="first-edit/assemble", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("take", type=Path)
    parser.add_argument("--project", type=Path, help="the HyperFrames project (default edit/projects/<video-slug>)")
    parser.add_argument("--replace", action="store_true", help="remove this take's clips and add them again at the end")
    parser.add_argument("--plan", action="store_true", help="print what would be added; change nothing")
    args = parser.parse_args()

    take = args.take.resolve()
    manifest_file = take / "pieces.json"
    if not manifest_file.exists():
        fail(f"{take} has no pieces.json; run first-edit/launch on it first")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not manifest.get("cut"):
        fail("pieces.json is only a plan (made with --plan); run first-edit/launch without it")
    slug, take_name = take.parent.name, take.name
    key = re.sub(r"[^a-z0-9]+", "", take_name.lower()) or "take"
    project = (args.project or REPO / "edit" / "projects" / slug).resolve()

    scripted = bool(manifest.get("script"))
    chosen = []
    for idea in manifest["ideas"]:
        if scripted and not idea["in_script"]:
            continue
        reading = next(r for r in idea["readings"] if r["suggested"])
        if not reading["file"].endswith(".mp4"):
            print(f"assemble: idea {idea['letter']} has no picture (kept as sound only); left off the timeline", file=sys.stderr)
            continue
        if not (take / reading["file"]).exists():
            fail(f"missing piece {reading['file']}")
        chosen.append((idea, reading))
    if not chosen:
        fail("no pieces to place")

    index = project / "index.html"
    if not index.exists():
        if args.plan:
            page = PAGE
        else:
            project.parent.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, DO_NOT_TRACK="1", HYPERFRAMES_SKIP_SKILLS="1")
            made = subprocess.run([*HYPERFRAMES, "init", project.name, "--example", "blank", "--non-interactive", "--skip-skills"],
                                  cwd=project.parent, env=env, capture_output=True, text=True)
            if made.returncode or not index.exists():
                fail(f"could not create the project: {(made.stderr or made.stdout).strip()[-300:]}")
            for extra in ("CLAUDE.md", "AGENTS.md"):   # the repository's own CLAUDE.md covers this
                (project / extra).unlink(missing_ok=True)
            page = PAGE
    else:
        page = index.read_text(encoding="utf-8")
    if START not in page or END not in page:
        fail(f"{index} has no raw-timeline markers ({START} … {END}); add them inside the root where takes should go")

    head, rest = page.split(START, 1)
    body, tail = rest.split(END, 1)
    mine = re.compile(rf"\n?[ \t]*<!-- take {re.escape(take_name)}:start -->.*?<!-- take {re.escape(take_name)}:end -->", re.S)
    if mine.search(body):
        if not args.replace:
            fail(f"{take_name} is already on the timeline; pass --replace to add it again at the end")
        body = mine.sub("", body)

    ends = [float(s) + float(d) for s, d in re.findall(r'data-start="([\d.]+)"[^>]*?data-duration="([\d.]+)"', body)]
    at = max(ends, default=0.0)
    lines = [f"<!-- take {take_name}:start -->"]
    for idea, reading in chosen:
        source = f"assets/{take_name}/{reading['file'].split('/', 1)[1]}"
        lines.append(
            f'<video id="{key}-{idea["letter"]}" class="clip" data-start="{number(at)}" data-duration="{number(reading["duration"])}" '
            f'data-track-index="0" data-has-audio="true" src="{html.escape(source)}" '
            f'title="{html.escape(idea["idea"], quote=True)}"></video>'
        )
        print(f"  {number(at):>8}  {idea['letter']}  {reading['duration']:5.2f} s  {idea['idea']}")
        at += reading["duration"]
    lines.append(f"<!-- take {take_name}:end -->")
    indent = "      "
    body = body.rstrip() + "\n" + "\n".join(indent + line for line in lines) + "\n" + indent
    page = head + START + body + END + tail
    page, changed = re.subn(r'(data-composition-id="main"[^>]*?data-duration=")[\d.]+(")', rf"\g<1>{number(at)}\g<2>", page, count=1)
    if not changed:
        fail('could not find the root\'s data-duration (expected data-composition-id="main" … data-duration="…")')

    print(f"\n{len(chosen)} clips from {take_name}; the timeline now runs {number(at)} s")
    if args.plan:
        print("plan only: nothing was written")
        return
    assets = project / "assets"
    assets.mkdir(exist_ok=True)
    link = assets / take_name
    if link.is_symlink() or link.exists():
        if not (link.is_symlink() and link.resolve() == (take / "pieces").resolve()):
            fail(f"{link} exists and is not a link to this take's pieces")
    else:
        link.symlink_to(take / "pieces", target_is_directory=True)
    # the link is an absolute path on this machine's content disk: keep it out of git
    ignore = assets / ".gitignore"
    listed = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    if f"/{take_name}" not in listed:
        ignore.write_text("\n".join([*listed, f"/{take_name}"]) + "\n", encoding="utf-8")
    index.write_text(page, encoding="utf-8")
    print(f"{index}\ncheck it:  (cd {project} && {' '.join(HYPERFRAMES)} check)\nopen it:   bin/edit {project.name}")


if __name__ == "__main__":
    main()
