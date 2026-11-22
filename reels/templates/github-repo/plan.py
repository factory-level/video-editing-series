"""Step 1 of the GitHub repo reel template: the running order. Takes the best tightened clip of
each scene named in ORDER (edit it per reel), in order, with its words mapped from the cached
transcript through the tighten ranges, and writes plan.json.

    python3 plan.py <content root>/<slug> <project dir> <plan.json>

ORDER entries: (scene opening words, "best" or a clip index, start word, end word). A start word
"getting#2" starts at its second occurrence. Whisper's word times can be off by up to half a
second: check a take's start against its audio level (see README.md, "Cutting") and correct
media_start and the words in plan.json by hand when it is.
"""
import html
import json
import re
import sys
from pathlib import Path

reel, project = Path(sys.argv[1]), Path(sys.argv[2])
plan = "--plan" in sys.argv
scenes = json.loads((reel / "edit/scenes/scenes.json").read_text())
tight = json.loads((reel / "edit/tight/tight.json").read_text())["clips"]
words_all = json.loads((reel / "edit/scenes/.transcripts/01.json").read_text())["words"]

# (opening words of the scene, which clip: "best" or an index, from-word to start at)
ORDER = [   # (scene opening, clip, start word, end word); a start word "getting#2" starts at its 2nd time
    ("yo this is open rig", "best", None),
    ("i use this in all of my software factories", "best", None),
    ("it basically allows you to define your software team", "best", None, "reviewers"),
    ("and this repo makes it really easy to do that", "best", None),
    ("it solves a couple of fundamental things", "best", None),
    ("you get better results taking the output of one model", 2, None),
    ("getting getting models to review", "best", "getting#2"),
    ("and context matters", "best", None),
    ("and each agent gets its own context window", "best", None),
    ("and it's built on top of herder, which is already a very popular way", "best", None),
    ("follow if you like this kind of content", "best", None, "content"),
]


def toks(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


def find(opening):
    want = toks(opening)
    for s in scenes["scenes"]:
        if toks(s["scene"])[:len(want)] == want:
            return s
    sys.exit(f"no scene opens with: {opening}")


def to_tight(t, ranges):
    """clip time -> tightened time, or None when t was cut out"""
    at = 0.0
    for a, b in ranges:
        if a <= t <= b:
            return at + (t - a)
        at += b - a
    return None


pieces, at = [], 0.0
for opening, which, start_word, *rest in ORDER:
    end_word = rest[0] if rest else None
    scene = find(opening)
    clip = next(c for c in scene["clips"] if c["best"]) if which == "best" else scene["clips"][which]
    info = tight[clip["file"]]
    ranges = info["ranges"]
    words = []
    for w in words_all:
        mid = (w["start"] + w["end"]) / 2
        if w["end"] <= w["start"] or not (clip["studio_start"] <= mid <= clip["studio_end"]):
            continue
        s, e = to_tight(max(w["start"], clip["studio_start"]) - clip["studio_start"], ranges), to_tight(min(w["end"], clip["studio_end"]) - clip["studio_start"], ranges)
        if s is None and e is None:
            continue
        s = e - 0.05 if s is None else s
        e = s + 0.05 if e is None else e
        words.append({"text": w["text"], "start": s, "end": e})
    while words and toks(words[0]["text"]) in (["cut"], ["best"]):    # a cue at the clip's edge
        words.pop(0)
    while words and toks(words[-1]["text"]) in (["cut"], ["best"]):
        words.pop()
    # the picture ends a frame or so before the sound (AAC padding): never ask for a frame past it
    import subprocess as _sp
    vdur = float(_sp.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=nw=1:nk=1",
                          str(reel / "edit/tight" / clip["file"])], capture_output=True, text=True).stdout.strip() or info["duration"])
    media_start, length = 0.0, min(info["duration"], vdur - 0.04)
    # a scrap under 0.25 s before the first cut or after the last is the edge of a cue or a breath
    if len(ranges) > 1 and ranges[0][1] - ranges[0][0] < 0.25:
        media_start = ranges[0][1] - ranges[0][0]
        words = [w for w in words if w["start"] >= media_start - 0.01]
    if len(ranges) > 1 and ranges[-1][1] - ranges[-1][0] < 0.25:
        length -= ranges[-1][1] - ranges[-1][0]
        words = [w for w in words if w["end"] <= length + 0.01]
    if start_word:
        sw, _, nth = start_word.partition("#")
        hits = [i for i, w in enumerate(words) if toks(w["text"]) == [sw]]
        first = hits[int(nth) - 1 if nth else 0]
        media_start = max(media_start, words[first]["start"] - 0.06)
        words = words[first:]
    if end_word:   # a hard cut straight after this word
        last = max(i for i, w in enumerate(words) if toks(w["text"]) == [end_word] or toks(w["text"])[-1:] == [end_word])
        length = min(length, words[last]["end"] + 0.06)
        words = words[:last + 1]
    length -= media_start
    for w in words:
        w["start"] -= media_start
        w["end"] -= media_start
    pieces.append({"scene": scene["number"], "file": clip["file"], "called": clip["called_best"], "media_start": round(media_start, 3),
                   "start": round(at, 3), "duration": round(length, 3), "words": words})
    print(f"{at:6.2f}  {length:5.2f} s  {clip['file']}{'  (called best)' if clip['called_best'] else ''}\n        {' '.join(w['text'] for w in words)}")
    at += length
total = round(at, 3)
print(f"\nreel: {total:.1f} s")
if plan:
    sys.exit(0)


Path(sys.argv[3] if len(sys.argv) > 3 else "plan.json").write_text(json.dumps({"total": total, "pieces": pieces}, indent=1))
