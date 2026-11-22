"""Step 3 of the GitHub repo reel template (README.md): write the composition. This is reel
0002-github-openrig's build, kept as the worked example: the diagram sections (A team roles,
B cross-model review, C context, herdr) and their words are that reel's; a new reel keeps the
frame (backgrounds, the speaker's sides, the title, captions, sound) and writes its own sections.

Build reel 0002-github-openrig: a green-screen reel. The speaker (cut out with
hyperframes remove-background) moves left and right over screen captures and animated
infographics in the Factory Level Signal design system; Instagram-style effects (reel-sfx).

    python3 build2.py <plan.json> <project dir>
"""
import html
import json
import re
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text())
project = Path(sys.argv[2])
TOTAL = round(plan["total"], 3)

# ---- words, absolute times, spelled the way the brands spell them -------------------------
words = []
for p in plan["pieces"]:
    for w in p["words"]:
        words.append({"text": w["text"].strip(), "start": p["start"] + w["start"], "end": p["start"] + w["end"]})
fixed = []
for w in words:
    t, last = w["text"], fixed[-1] if fixed else None
    if last and last["text"].lower() == "chachi" and t.lower().startswith("bt"):
        last["text"], last["end"] = "ChatGPT" + t[2:], w["end"]; continue
    if last and last["text"].lower() == "open" and t.lower().startswith("rig"):
        last["text"], last["end"] = "OpenRig" + t[3:], w["end"]; continue
    if last and t.startswith("-"):
        last["text"], last["end"] = last["text"] + t, w["end"]; continue
    t = re.sub(r"(?i)^herder", "herdr", t)
    fixed.append({**w, "text": t})
words = fixed


def toks(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def at(word, after=0.0):
    """Start time of the first word matching `word` at or after `after`."""
    for w in words:
        if w["start"] >= after - 0.01 and toks(w["text"])[:1] == toks(word)[:1]:
            return round(w["start"], 3)
    sys.exit(f"no word {word!r} after {after}")


P = plan["pieces"]
seg = [round(p["start"], 3) for p in P] + [TOTAL]

# ---- the speaker's place in each stretch: side, scale ---------------------------------
#   x is the shift of the full-frame cutout; the face sits about 540 + x
PLACES = [  # (from, x, scale)
    (seg[0], 170, 0.86),    # Yo, this is OpenRig: over the repo
    (seg[1], -250, 0.80),   # software factories: over openrig.dev
    (seg[2], 250, 0.76),    # A: team roles
    (seg[3], -250, 0.80),   # this repo makes it easy: README
    (seg[4], 250, 0.78),    # two fundamental things
    (seg[5], -250, 0.76),   # B: cross-model review
    (seg[7], 250, 0.76),    # C: context
    (seg[8], -250, 0.76),   # herdr
    (seg[9], -250, 0.80),  # outro: back over the repo
]

# ---- sound effects: varied, under the voice (reel-sfx skill) -------------------------------
SFX = []


def fx(name, t, vol=0.3):
    SFX.append((name, max(0.0, round(t, 3)), vol))


DUR = {"boom": 2.1, "scratch": 1.9, "shutter": 0.34, "ding": 1.5, "whip": 0.47, "pop": 0.24, "chaching": 2.0,
       "typing": 1.32, "whoosh-short": 0.57, "whoosh": 0.57, "click": 0.37, "sparkle": 1.8}

js, layers = [], []


def tl(s):
    js.append("      " + s)


# ---- stretch 0-1: screen captures ------------------------------------------------------------
layers.append(f'''      <div id="bg-github" class="clip bg" data-start="0" data-duration="{seg[1]:.3f}" data-track-index="1">
        <img src="assets/fetched/github-top.png" alt="" style="width:1080px" />
      </div>
      <video id="bg-site" class="clip bgv" data-start="{seg[1]:.3f}" data-duration="{seg[2] - seg[1]:.3f}" data-media-start="0.6" data-track-index="2" muted playsinline src="assets/fetched/openrig-dev.mp4"></video>
      <div id="bg-readme" class="clip bg" data-start="{seg[3]:.3f}" data-duration="{seg[4] - seg[3]:.3f}" data-track-index="1">
        <img src="assets/fetched/github-readme.png" alt="" style="width:1080px" />
      </div>''')
tl('tl.fromTo("#bg-github img", { y: 0, scale: 1.06 }, { y: -160, scale: 1, duration: %.3f, ease: "none" }, 0);' % seg[1])
tl('tl.fromTo("#bg-readme img", { y: -80 }, { y: -520, duration: %.3f, ease: "none" }, %.3f);' % (seg[4] - seg[3], seg[3]))
# fewer and quieter: one swoosh into each diagram section, a handful of accents
fx("shutter", 0.02, 0.18)
fx("whoosh-short", seg[2] - 0.2, 0.16)
fx("whip", seg[5] - 0.2, 0.15)
fx("whoosh-short", seg[7] - 0.2, 0.15)
fx("whip", seg[8] - 0.2, 0.15)


def label(num, topic):
    return f'<div class="label">{num} <b>/</b> {html.escape(topic)}</div>'


def head(text, cls="h-l"):
    body, mark = text[:-1], text[-1]
    return f'<div class="{cls}">{html.escape(body)}<b>{html.escape(mark)}</b></div><div class="bar"></div>'


def icon(name, size=96):
    ext = "png" if name == "herdr" else "svg"
    return f'<img class="ico" src="assets/icons/{name}.{ext}" alt="{name}" style="width:{size}px;height:{size}px" />'


# ---- A: the agent team (seg 2) -------------------------------------------------------------
a0, a1 = seg[2], seg[3]
t_team, t_mgr, t_dev, t_qa, t_rev = at("define", a0), at("manager", a0), at("developer", a0), at("qa", a0), at("reviewers", a0)
layers.append(f'''      <div id="A" class="clip board" data-start="{a0:.3f}" data-duration="{a1 - a0:.3f}" data-track-index="3">
        <div class="org">
          <div class="card mgr" id="A-mgr">{icon("claude", 84)}<div><div class="role">Team manager</div><div class="who">Claude Code</div></div></div>
          <div class="wire" id="A-wire"></div>
          <div class="row">
            <div class="card sm" id="A-dev">{icon("chatgpt", 72)}<div class="role">Developer</div><div class="who">Codex</div></div>
            <div class="card sm" id="A-qa">{icon("claude", 72)}<div class="role">QA</div><div class="who">Claude Code</div></div>
            <div class="card sm" id="A-rev">{icon("chatgpt", 72)}<div class="role">Reviewer</div><div class="who">GPT</div></div>
          </div>
        </div>
      </div>''')
for sel, t, v in (("#A-mgr", t_mgr, 0.32), ("#A-dev", t_dev, 0.3), ("#A-qa", t_qa, 0.28), ("#A-rev", t_rev, 0.26)):
    tl(f'tl.from("{sel}", {{ opacity: 0, scale: 0.6, y: 24, duration: 0.32, ease: "back.out(1.8)" }}, {t - 0.05:.3f});')
    if sel == "#A-mgr":
        fx("pop", t - 0.05, 0.16)
tl(f'tl.from("#A-wire", {{ scaleY: 0, transformOrigin: "50% 0%", duration: 0.4, ease: "power2.out" }}, {t_mgr + 0.25:.3f});')

# ---- the two things it solves (seg 4): the openrig.dev scroll carries on, no card ------------------
f0, f1 = seg[4], seg[5]
layers.append(f'''      <video id="bg-site2" class="clip bgv" data-start="{f0:.3f}" data-duration="{f1 - f0:.3f}" data-media-start="4.2" data-track-index="2" muted playsinline src="assets/fetched/openrig-dev.mp4"></video>''')

# ---- B: models reviewing each other (seg 5-6) -----------------------------------------------------
b0, b1 = seg[5], seg[7]
t_out, t_gpt, t_inp, t_models = at("output", b0), at("chatgpt", b0), at("another", b0), at("models", seg[6])
t_rev2, t_each, t_claude, t_home = at("review", seg[6]), at("each", seg[6]), at("claude", seg[6]), at("homework", seg[6])
layers.append(f'''      <div id="B" class="clip board" data-start="{b0:.3f}" data-duration="{b1 - b0:.3f}" data-track-index="3">
        <div class="handoff" id="B-hand">
          <div class="node" id="B-gpt">{icon("chatgpt", 110)}<div class="cap2">ChatGPT</div></div>
          <div class="chip" id="B-chip">output</div>
          <div class="arrow" id="B-arr">&rarr;</div>
          <div class="node" id="B-cl">{icon("claude", 110)}<div class="cap2">next model</div></div>
        </div>
        <div class="chain" id="B-chain">
          <div class="node" id="B-c1">{icon("claude", 104)}<div class="cap2">writes</div></div>
          <div class="arrow" id="B-a1">&rarr;</div>
          <div class="node" id="B-c2">{icon("chatgpt", 104)}<div class="cap2">reviews</div></div>
          <div class="arrow" id="B-a2">&rarr;</div>
          <div class="node" id="B-c3">{icon("claude", 104)}<div class="cap2">fixes</div></div>
        </div>
        <div class="self" id="B-self">
          {icon("claude", 72)}<div class="selftext">Claude grading<br />its own homework</div><div class="x" id="B-x">&times;</div>
        </div>
      </div>''')
tl(f'tl.from("#B-gpt", {{ opacity: 0, scale: 0.5, duration: 0.32, ease: "back.out(1.8)" }}, {t_gpt - 0.05:.3f});')
tl(f'tl.from("#B-chip", {{ opacity: 0, x: -60, duration: 0.35, ease: "power3.out" }}, {t_gpt + 0.6:.3f});')
tl(f'tl.from("#B-arr", {{ opacity: 0, x: -30, duration: 0.25 }}, {t_inp - 0.3:.3f});')
tl(f'tl.from("#B-cl", {{ opacity: 0, scale: 0.5, duration: 0.32, ease: "back.out(1.8)" }}, {t_inp:.3f});')
tl(f'tl.to("#B-chip", {{ x: 250, duration: 0.6, ease: "power2.inOut" }}, {t_inp - 0.25:.3f});')
fx("pop", t_gpt - 0.05, 0.15)
swap = seg[6] - 0.05
tl(f'tl.to("#B-hand", {{ opacity: 0, y: -20, duration: 0.25, ease: "power2.in" }}, {swap:.3f});')
for sel, t in (("#B-c1", t_models), ("#B-a1", t_rev2 - 0.15), ("#B-c2", t_rev2), ("#B-a2", t_each - 0.1), ("#B-c3", t_each + 0.1)):
    tl(f'tl.fromTo("{sel}", {{ opacity: 0, scale: 0.5 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "back.out(1.8)" }}, {t:.3f});')
tl(f'tl.fromTo("#B-self", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }}, {t_claude - 0.1:.3f});')
tl(f'tl.fromTo("#B-x", {{ opacity: 0, scale: 2.4, rotation: -20 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: 0.25, ease: "back.out(2)" }}, {t_home - 0.25:.3f});')

# ---- C: context (seg 7-8) ---------------------------------------------------------------------
c0, c1 = seg[7], seg[8]
t_agent, t_window = at("agent", c0), at("window", c0)
t_short, t_eff, t_drawn, t_tokens = at("shorter", c0), at("effective", c0), at("drawn", c0), at("tokens", c0)
layers.append(f'''      <div id="C" class="clip board" data-start="{c0:.3f}" data-duration="{c1 - c0:.3f}" data-track-index="3">
        <div class="agents" id="C-agents">
          <div class="ag" id="C-g1">{icon("claude", 64)}<div class="win"><i></i></div></div>
          <div class="ag" id="C-g2">{icon("chatgpt", 64)}<div class="win"><i></i></div></div>
          <div class="ag" id="C-g3">{icon("claude", 64)}<div class="win"><i></i></div></div>
        </div>
        <div class="ctx" id="C-short">
          <div class="ctxlab">Short chat</div>
          <div class="track"><div class="fill pink" id="C-sf"></div></div>
          <div class="verdict good" id="C-smart">smart &check;</div>
        </div>
        <div class="ctx" id="C-long">
          <div class="ctxlab">Drawn-out chat <span class="tok"><span id="C-tok">0</span> tokens</span></div>
          <div class="track"><div class="fill grey" id="C-lf"></div></div>
          <div class="verdict bad" id="C-dumb">dumb &times;</div>
        </div>
      </div>''')
for i, (sel, t, v) in enumerate((("#C-g1", t_agent, 0.3), ("#C-g2", t_agent + 0.35, 0.27), ("#C-g3", t_agent + 0.7, 0.24))):
    tl(f'tl.from("{sel}", {{ opacity: 0, y: 30, scale: 0.6, duration: 0.3, ease: "back.out(1.8)" }}, {t:.3f});')
    tl(f'tl.from("{sel} .win i", {{ scaleX: 0, transformOrigin: "0% 50%", duration: 0.5, ease: "power2.out" }}, {t + 0.25:.3f});')
tl(f'tl.to("#C-agents", {{ opacity: 0.35, duration: 0.3 }}, {t_short - 0.6:.3f});')
tl(f'tl.from("#C-short", {{ opacity: 0, y: 30, duration: 0.3, ease: "power3.out" }}, {t_short - 0.3:.3f});')
tl(f'tl.from("#C-sf", {{ width: 0, duration: 0.6, ease: "power2.out" }}, {t_short:.3f});')
tl(f'tl.from("#C-smart", {{ opacity: 0, scale: 0.4, duration: 0.3, ease: "back.out(2)" }}, {t_eff:.3f});')
fx("ding", t_eff, 0.14)
tl(f'tl.from("#C-long", {{ opacity: 0, y: 30, duration: 0.3, ease: "power3.out" }}, {t_drawn - 0.3:.3f});')
tl(f'tl.from("#C-lf", {{ width: 0, duration: {t_tokens - t_drawn + 0.2:.3f}, ease: "power1.in" }}, {t_drawn:.3f});')
tl(f'tl.fromTo(tok, {{ n: 0 }}, {{ n: 184000, duration: {t_tokens - t_drawn + 0.2:.3f}, ease: "power1.in", '
   f'onUpdate: () => {{ document.getElementById("C-tok").textContent = (Math.round(tok.n / 1000) * 1000).toLocaleString("en-US"); }} }}, {t_drawn:.3f});')
tl(f'tl.from("#C-dumb", {{ opacity: 0, scale: 0.4, duration: 0.3, ease: "back.out(2)" }}, {t_tokens:.3f});')

# ---- herdr (seg 9) -----------------------------------------------------------------------------
h0, h1 = seg[8], seg[9]
t_herdr, t_manage = at("herdr", h0), at("manage", h0)
panes = "\n".join(f'          <div class="pane" id="H-p{i}">{icon(n, 44)}<div class="ln"></div><div class="ln s"></div></div>'
                  for i, n in enumerate(["claude", "chatgpt", "claude", "chatgpt", "claude", "chatgpt"]))
layers.append(f'''      <div id="H" class="clip board" data-start="{h0:.3f}" data-duration="{h1 - h0:.3f}" data-track-index="3">
        <div class="herdr" id="H-logo">{icon("herdr", 300)}</div>
        <div class="grid" id="H-grid">
{panes}
        </div>
      </div>''')
tl(f'tl.from("#H-logo", {{ opacity: 0, scale: 0.5, duration: 0.35, ease: "back.out(1.8)" }}, {t_herdr - 0.1:.3f});')
fx("boom", t_herdr - 0.1, 0.16)
for i in range(6):
    t = t_manage + i * 0.17
    tl(f'tl.from("#H-p{i}", {{ opacity: 0, scale: 0.5, duration: 0.25, ease: "back.out(2)" }}, {t:.3f});')

# ---- outro (seg 10): back to the repo, no wordmark -------------------------------------------------
o0 = seg[9]
layers.append(f'''      <div id="bg-github2" class="clip bg" data-start="{o0:.3f}" data-duration="{TOTAL - o0:.3f}" data-track-index="1">
        <img src="assets/fetched/github-top.png" alt="" style="width:1080px" />
      </div>''')
tl('tl.fromTo("#bg-github2 img", { y: -40, scale: 1.04 }, { y: -120, scale: 1, duration: %.3f, ease: "none" }, %.3f);' % (TOTAL - o0, o0))

# ---- the speaker -----------------------------------------------------------------------------------
tl(f'tl.set("#me", {{ x: {PLACES[0][1]}, scale: {PLACES[0][2]} }}, 0);')
for (t, x, s) in PLACES[1:]:
    tl(f'tl.to("#me", {{ x: {x}, scale: {s}, duration: 0.42, ease: "power3.inOut" }}, {t - 0.21:.3f});')


def side(t):
    x = [p for p in PLACES if p[0] <= t + 0.001][-1][1]
    return "right" if x > 50 else "left" if x < -50 else "center"


# ---- captions: beside the speaker, on the open side ---------------------------------------------------
groups, cur = [], []
for i, w in enumerate(words):
    if not toks(w["text"]):
        continue
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    boundary = nxt is None or any(abs(nxt["start"] - b) < 0.02 for b in seg)
    if len(cur) == 3 or re.search(r"[.?!,]$", w["text"]) or boundary or nxt["start"] - w["end"] >= 0.25:
        groups.append(cur); cur = []
SMALL = set("a an the and or but so to of in on at for with is it it's its that this you your i i'm we they be are was can will just like if do what as by from all have has than each own more lot".split())
caps = []
for gi, g in enumerate(groups):
    start = max(0.05, g[0]["start"] - 0.04)
    nxt = groups[gi + 1][0]["start"] - 0.04 if gi + 1 < len(groups) else TOTAL
    end = max(g[-1]["end"], min(nxt, g[-1]["end"] + 0.45))
    if gi + 1 == len(groups):
        end = TOTAL
    keyi = max(range(len(g)), key=lambda i: 0 if toks(g[i]["text"])[0] in SMALL else len(g[i]["text"]))
    if toks(g[keyi]["text"])[0] in SMALL or len(g[keyi]["text"]) < 4:
        keyi = -1
    where = side(g[0]["start"])
    spans = " ".join(f'<span class="w{" key" if i == keyi else ""}" id="c{gi}w{i}">{html.escape(re.sub(r"[.,!]+$", "", w["text"]))}</span>' for i, w in enumerate(g))
    caps.append(f'        <div class="cap {"cap-l" if where == "right" else "cap-r" if where == "left" else "cap-c"}" id="c{gi}">{spans}</div>')
    tl(f'tl.set("#c{gi}", {{ opacity: 1, visibility: "visible" }}, {start:.3f});')
    for i, w in enumerate(g):
        tl(f'tl.fromTo("#c{gi}w{i}", {{ opacity: 0, y: 26, scale: 0.92 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.14, ease: "power3.out" }}, {max(start, w["start"] - 0.04):.3f});')
    tl(f'tl.set("#c{gi}", {{ opacity: 0, visibility: "hidden" }}, {end:.3f});')

# ---- the voice ---------------------------------------------------------------------------------------
VOICE = {"version": 1, "nodes": [
    {"type": "highpass", "id": "v1", "label": "Remove rumble", "params": {"frequency": 80, "q": 0.707}},
    {"type": "lowshelf", "id": "v2", "label": "Body", "params": {"frequency": 160, "gain": 2}},
    {"type": "peaking", "id": "v3", "label": "Less harsh", "params": {"frequency": 3000, "gain": -1.5, "q": 1.2}},
    {"type": "highshelf", "id": "v4", "label": "Air", "params": {"frequency": 9000, "gain": 1.0}},
]}   # no compressor here: reels/finish compresses once (highest-quality rule)
voice_fx = html.escape(json.dumps(VOICE, separators=(",", ":")), quote=True)
audio = [f'      <audio id="voice" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1" '
         f'data-fx-chain="{voice_fx}" src="assets/green/talk-hq-v3-C.wav"></audio>']
for i, (name, t, vol) in enumerate(sorted(SFX, key=lambda s: s[1])):
    d = min(DUR[name], TOTAL - t - 0.01)
    audio.append(f'      <audio id="fx{i}" class="clip" data-start="{t:.3f}" data-duration="{d:.3f}" data-track-index="{11 + i % 4}" '
                 f'data-volume="{vol}" data-audio-group="sfx" src="assets/sfx/{name}.mp3"></audio>')

page = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      /* Factory Level Signal: ground #050505, ink #fff, ink-muted #a9a9a9, signal-pink #FF2D8A, surface-raised #141414 */
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #050505; }}
      #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #050505;
               font-family: "Plus Jakarta Sans", system-ui, sans-serif; color: #fff; font-feature-settings: "liga" 0; }}
      .bg {{ position: absolute; inset: 0; overflow: hidden; }}
      .bg img {{ display: block; transform-origin: 50% 0%; }}
      .bgv {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; object-position: 50% 0%; }}
      .bg::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1350px;
               background: linear-gradient(#05050500, #050505cc 30%, #050505f2 60%); }}
      #shade {{ position: absolute; left: 0; right: 0; bottom: 0; height: 1350px; background: linear-gradient(#05050500, #050505cc 30%, #050505f2 60%); }}
      #shade {{ z-index: 3; }}
      #me {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; z-index: 20;
             transform-origin: 50% 100%; clip-path: inset(33.5% 0 0 0);   /* the shelf above the head stays out */
             -webkit-mask-image: linear-gradient(to right, transparent 0, #000 16%, #000 84%, transparent 100%);
             mask-image: linear-gradient(to right, transparent 0, #000 16%, #000 84%, transparent 100%); }}  /* the camera frame's edges dissolve */
      .board {{ position: absolute; inset: 0; background: #050505; }}
      .label {{ position: absolute; left: 112px; top: 262px; font-weight: 700; font-size: 26px; letter-spacing: 0.2em; color: #fff; font-size: 28px; }}
      .label b, .head b {{ color: #FF2D8A; }}
      .rule {{ position: absolute; left: 112px; right: 112px; top: 318px; height: 2px; background: #ffffffd9; }}
      .head {{ position: absolute; left: 112px; top: 360px; right: 112px; }}
      .h-l {{ font-weight: 800; font-size: 96px; line-height: 0.92; letter-spacing: -0.045em; }}
      .bar {{ width: 104px; height: 10px; border-radius: 5px; background: #FF2D8A; margin-top: 30px; }}
      .head.swap {{ opacity: 0; }}
      .card {{ background: #141414; border-radius: 16px; box-shadow: 0 24px 60px #000000a6; }}
      .org {{ position: absolute; left: 112px; right: 112px; top: 370px; }}
      .card.mgr {{ display: flex; align-items: center; gap: 24px; padding: 24px 32px; width: 560px; margin: 0 auto; }}
      .role {{ font-weight: 800; font-size: 40px; letter-spacing: -0.03em; }}
      .who {{ font-weight: 500; font-size: 28px; color: #a9a9a9; margin-top: 4px; }}
      .wire {{ width: 4px; height: 56px; background: #FF2D8A; margin: 0 auto; border-radius: 2px; }}
      .row {{ display: flex; gap: 22px; justify-content: center; }}
      .card.sm {{ width: 268px; padding: 26px 20px; text-align: center; }}
      .card.sm .ico {{ margin: 0 auto 14px; display: block; }}
      .card.sm .role {{ font-size: 34px; }}
      .ico {{ object-fit: contain; }}
      .list {{ position: absolute; left: 112px; right: 112px; top: 640px; }}
      .item {{ font-weight: 800; font-size: 50px; letter-spacing: -0.03em; margin-bottom: 30px; }}
      .item .n {{ display: inline-block; width: 92px; color: #FF2D8A; }}
      .handoff, .chain {{ position: absolute; left: 112px; right: 112px; top: 460px; display: flex; align-items: center; justify-content: space-between; }}
      .chain {{ top: 440px; }}
      .node {{ text-align: center; width: 200px; }}
      .node .ico {{ display: block; margin: 0 auto 14px; }}
      .cap2 {{ font-weight: 700; font-size: 30px; color: #a9a9a9; }}
      .arrow {{ font-weight: 800; font-size: 90px; color: #FF2D8A; line-height: 1; }}
      .chip {{ position: absolute; left: 230px; top: -70px; font-family: "JetBrains Mono", monospace; font-size: 28px;
               padding: 10px 18px; border-radius: 6px; background: #FF2D8A; color: #050505; font-weight: 500; }}
      .chain .node, .chain .arrow {{ opacity: 0; }}
      .self {{ position: absolute; right: 112px; top: 740px; display: flex; align-items: center; gap: 20px; opacity: 0;
               background: #141414; border-radius: 16px; padding: 18px 26px; box-shadow: 0 24px 60px #000000a6; }}
      .selftext {{ font-weight: 700; font-size: 28px; line-height: 1.2; color: #a9a9a9; }}
      .x {{ font-weight: 800; font-size: 84px; color: #FF2D8A; line-height: 0.8; opacity: 0; }}
      .agents {{ position: absolute; left: 112px; right: 112px; top: 380px; display: flex; gap: 26px; flex-wrap: wrap; }}
      .ag {{ display: flex; align-items: center; gap: 14px; }}
      .win {{ width: 160px; height: 22px; border-radius: 6px; background: #141414; overflow: hidden; }}
      .win i {{ display: block; width: 30%; height: 100%; background: #FF2D8A; }}
      .agcap {{ width: 100%; font-weight: 600; font-size: 28px; color: #a9a9a9; margin-top: 4px; }}
      .ctx {{ position: absolute; left: 112px; right: 112px; }}
      #C-short {{ top: 540px; }}
      #C-long {{ top: 690px; }}
      .ctxlab {{ font-weight: 800; font-size: 36px; letter-spacing: -0.02em; margin-bottom: 12px; }}
      .tok {{ font-family: "JetBrains Mono", monospace; font-weight: 500; font-size: 28px; color: #a9a9a9; margin-left: 14px; }}
      .track {{ width: 640px; height: 30px; border-radius: 6px; background: #141414; overflow: hidden; }}
      .fill {{ height: 100%; }}
      .fill.pink {{ width: 22%; background: #FF2D8A; }}
      .fill.grey {{ width: 100%; background: #8a8a8a; }}
      .verdict {{ position: absolute; left: 560px; top: -2px; font-weight: 800; font-size: 38px; }}
      .verdict.good {{ color: #FF2D8A; }}
      .verdict.bad {{ color: #a9a9a9; }}
      .herdr {{ position: absolute; left: 112px; right: 112px; top: 360px; display: flex; justify-content: center; }}
      .head.inline {{ position: static; }}
      .herdr .ico {{ border-radius: 56px; }}
      .grid {{ position: absolute; left: 520px; right: 112px; top: 700px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
      .pane {{ background: #0d0d0d; border-radius: 10px; padding: 14px; height: 96px; box-shadow: 0 24px 60px #000000a6; position: relative; }}
      .pane .ico {{ position: absolute; left: 14px; top: 14px; }}
      .pane .ln {{ position: absolute; left: 72px; right: 16px; top: 26px; height: 10px; border-radius: 5px; background: #2a2a2a; }}
      .pane .ln.s {{ top: 50px; right: 70px; background: #FF2D8A; opacity: 0.7; }}
      .wm {{ position: absolute; left: 0; right: 0; top: 300px; text-align: center; font-weight: 800; font-size: 96px; letter-spacing: -0.05em; }}
      .wm span {{ display: inline-block; width: 60px; height: 14px; background: #FF2D8A; border-radius: 3px; margin-left: 8px; }}
      .tag {{ position: absolute; left: 0; right: 0; top: 440px; text-align: center; font-weight: 600; font-size: 28px; letter-spacing: 0.22em; color: #a9a9a9; }}
      /* the reel's title: the repo's address, the whole way through, clear of Instagram's top bar */
      #title {{ position: absolute; left: 50%; top: 224px; transform: translateX(-50%); z-index: 45; white-space: nowrap;
                padding: 22px 40px; border-radius: 12px; background: #050505e0; box-shadow: 0 24px 60px #000000a6;
                font-family: "JetBrains Mono", ui-monospace, monospace; font-weight: 500; font-size: 44px; line-height: 1; color: #fff; letter-spacing: -0.01em; }}
      #captions {{ position: absolute; inset: 0; z-index: 40; pointer-events: none; }}
      .cap {{ position: absolute; top: 1030px; width: 500px; font-weight: 800; font-size: 74px; line-height: 0.98; letter-spacing: -0.04em;
              opacity: 0; visibility: hidden; text-shadow: 0 2px 4px #000000b3, 0 10px 30px #000000b3; }}
      .cap-l {{ left: 92px; text-align: left; }}
      .cap-r {{ right: 180px; width: 420px; text-align: right; }}  /* clear of Instagram's like / comment / share column */
      .cap-c {{ left: 0; right: 0; width: auto; text-align: center; top: 640px; }}
      .cap .w {{ display: inline-block; margin-right: 0.18em; opacity: 0; }}
      .cap-r .w {{ margin: 0 0 0 0.18em; }}
      .cap .w.key {{ color: #FF2D8A; }}
    </style>
  </head>
  <body>
    <!-- Reel 0002-github-openrig: green-screen reel (reels/README.md). Built by the scratch build2.py. -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="1080" data-height="1920">
{chr(10).join(layers)}
      <div id="shade" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="4"></div>
      <video id="me" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="5" muted playsinline src="assets/green/cut-v3.webm"></video>
      <div id="title" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="7">github.com/mvschwarz/openrig</div>
      <div id="captions" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="6">
{chr(10).join(caps)}
      </div>
{chr(10).join(audio)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      const tok = {{ n: 0 }};
{chr(10).join(js)}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""
(project / "index.html").write_text(page)
print(f"wrote {project / 'index.html'}: {TOTAL} s, {len(groups)} caption groups, {len(SFX)} sound effects")
