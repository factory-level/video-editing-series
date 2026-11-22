# GitHub repo reel template

A 9:16 Instagram reel that introduces a GitHub repository. The speaker is green-screened over
the repo page, the project's site and animated diagrams. Reel `0002-github-openrig` is the worked
example, and every decision below was settled while editing it. The other reels steps
(`reels/README.md`) still apply; this page covers what is specific to this kind of reel.

## Status

Reel 0002 was approved and delivered to Drive on 2026-11-21.

Set by the person while editing 0002:
- green screen, switching sides per section;
- no titles except the repo address (larger, squarer box, more space);
- Factory Level Signal colours and type;
- only Claude and OpenAI icons;
- few, subtle effects;
- the highest quality, lossless until the final encode;
- mastered audio with no echo: the RNNoise chain below (a gentle version wasn't enough);
- no record scratch;
- captions clear of Instagram's buttons;
- cuts tightened at the joins;
- "announcing" lines removed.

Chosen while editing and not yet reviewed:
- the shelf mask line and the edge fade;
- captions beside the speaker;
- the diagram designs;
- how backgrounds are captured;
- the exact mastering settings.

Change these when the person asks.

## The story

| Part | Background | Speaker | Example (0002) |
| --- | --- | --- | --- |
| Hook | The repo's GitHub page, drifting slowly | Right | "Yo, this is OpenRig." |
| Where you use it | The project's site, a scroll recording | Left | "I use this in all of my software factories." |
| One diagram per idea | Black ground, a diagram animated to the words | Alternates right, left, right… | Team roles; models reviewing each other; context windows |
| "This repo makes it easy" | The repo's README, scrolling | Opposite side to the last diagram | "And this repo makes it really easy to do that." |
| What it's built on | That project's logo, then a grid of agent panes | Next side | "It's built on top of herdr…" |
| Call to action | The repo page again | Left | "Follow if you like this kind of content." Hard cut at the end. |

- **No titles.** No section labels, headlines, numbers, accent bars or wordmark. The narration says
  what is happening; the diagrams carry only short labels (role names, "writes / reviews / fixes",
  "smart / dumb").
- **One title for the whole reel: the repo's address**, for example `github.com/mvschwarz/openrig`.
  It sits in a JetBrains Mono box for the whole reel: 44 px, white on `#050505e0`, 22 x 40 px
  padding, 12 px corners (not a pill), centred at `top: 224px`. The diagrams start 40 px below it.
- Keep it under about 50 s. Cut any line that only announces the next one, such as "And context
  matters."

## Look

- **Colours and type come from the Factory Level Signal design system**
  (https://claude.ai/artifact/NM6NhKyvEESZcfvWP7J4fB):
  - ground `#050505`, raised surface `#141414`, text `#fff` and `#a9a9a9`;
  - one accent, `#FF2D8A`, for arrows, bars and the key word in each caption;
  - Plus Jakarta Sans 800 for text, JetBrains Mono for code and the address.
  - Its headline and wordmark patterns are **not** used in reels.
- **Icons: only Claude and OpenAI marks for agents.** Use LobeHub `claude-color.svg` and the
  OpenAI mark (`openai.svg`, filled white for the dark ground). Never the Codex icon: a Codex
  agent gets the OpenAI mark, with "Codex" as its label. The project the repo is built on keeps
  its own logo in its own section (herdr: `assets/logo.png` from its repo). Credits go in
  `assets/icons/CREDITS.md`.
- **Diagrams** use `#141414` cards (radius 16, `0 24px 60px #000000a6` shadow) and pink arrows.
  - They sit in the top half, from y 370 to about 1000, below the title.
  - Each element pops in on the word that names it (`back.out`, 0.3 s).
- **Captions** are up to 3 words: Plus Jakarta Sans 800, 74 px, key word in pink.
  - They sit **beside the speaker, on the open side**, from `top: 1030px`.
  - On the left: 92 px from the edge, 500 px wide. On the right: **180 px from the edge**, 420 px
    wide, so they stay clear of Instagram's like / comment / share column (about x 940–1080,
    y 1050–1650). Check with a box drawn there on the snapshots.
  - Each word rises in as it is said.

## Green screen

1. Join the chosen takes into one talking-head video (`edit/green/talk.mp4`).
2. Split it into three frame-exact chunks and run
   `npx -y hyperframes@0.9.58 remove-background` on all three at once.
   - On this server's CPU that takes about 30 minutes for 50 s.
   - Running in parallel doesn't speed it up much, so start it early.
   - Install once: `npm install onnxruntime-node@1.21.1 --onnxruntime-node-install-cuda=skip --prefix ~/.cache/hyperframes/optional/onnxruntime-node@1.21.1`.
3. Join the three chunks with `ffmpeg -f concat -c copy`. The transparency survives the join.
4. Look at the alpha masks before using the cutout (tile one frame in 25 with `alphaextract`).
   - Things in the room can survive the cut. In 0002 a red shelf bracket did, never lower than
     32% of the frame height.
   - Mask them with `clip-path: inset(33.5% 0 0 0)` (pick the line from the masks, between the
     object and the top of the head).
5. Fade the camera frame's side edges with a mask:
   `linear-gradient(to right, transparent 0, #000 16%, #000 84%, transparent 100%)`.
   Otherwise a raised hand or shoulder is cut by a hard vertical line.
6. The speaker switches between `x: 250` and `x: -250`, at scale 0.76–0.86 anchored at the
   bottom, for each new section. The move takes 0.42 s, `power3.inOut`, centred on the cut.
7. **Changing the edit later:** never redo the background removal.
   - Find the take boundaries in `talk.mp4` by frame-to-frame jumps (`signalstats` YDIF over 10).
   - Drop those frames from the cutout, re-encoded **losslessly** with transparency:
     `libvpx-vp9 -lossless 1 -pix_fmt yuva420p`, `alpha_mode=1`.

## Backgrounds

- **The GitHub page:** Playwright 1.64 with the Pixel 7 profile (1082 px wide). Capture the top
  of the page, and the README (crop the full-page capture from where the README starts).
  ```sh
  npx -y playwright@1.64.0 screenshot --device="Pixel 7" --wait-for-timeout=2500 <repo url> github-top.png
  ```
- **The site:** a frame-by-frame Playwright scroll at full resolution (screenshot, scroll, repeat;
  30 frames a second, 1 s on the hero, then ease down). Join the frames into a 1080x1920 H.264
  file with `-movflags +faststart`. The playback recorder is only phone-CSS sized (412 px).
- **A dark shade at the bottom** (1350 px, `#050505` from 0 to f2) on every screen capture, so
  captions read over white pages.

## Sound

- **Effects: few and subtle.** About 10 in 50 s, at volume 0.14–0.18.
  - The whole set: a shutter on the opening; one swoosh (whoosh-short and whip alternating) into
    each diagram section; one pop on the first element of a diagram; a ding on the "right" beat; a boom on the project's logo.
  - No typing, clicks or pop-per-item.
  - Use the `reel-sfx` skill; CC BY sounds are credited in the post caption.
- **Highest quality: lossless until the one final encode.**
  - The voice is cut from the 24-bit studio WAV with `voice.py`, exactly as `reels/tighten` cut
    each take: each kept range padded to its picture's frames, each take to its frame count.
    Never use the AAC sound in `edit/scenes/` or `edit/tight/`.
  - **Master the voice before mixing**, because the room echoes on a lav. Into
    `edit/green/talk-hq-master.wav`, still 24-bit:
    `highpass=f=80,arnndn=m=~/.cache/rnnoise/sh.rnnn:mix=1,atrim=start_sample=480,asetpts=PTS-STARTPTS,apad=whole_len=<samples>,afftdn=nr=10:nf=-50:tn=1,equalizer=f=300:t=q:w=1:g=-2.5,agate=threshold=0.045:ratio=4:range=0.05:attack=2:release=60:knee=2,deesser=i=0.4`.
    - **RNNoise** (ffmpeg's `arnndn` with the `sh` model from
      [richardpl/arnndn-models](https://github.com/richardpl/arnndn-models)) removes the room and
      noise. It delays the sound by exactly 480 samples (10 ms), so trim them back and pad to the
      original length, or the voice drifts off the lips.
    - Then light noise reduction, a cut for the boxy room tone, a firm downward expander that
      kills the room's tail between words, and a de-esser.
    - In 0002 a gentle version (no RNNoise) still left audible echo. This one takes the room floor
      from −43 to −80 dB with speech unchanged.
    - Put a short A/B page up (raw and each version, the same 9 s) when changing it: echo and
      clipped word endings can only be judged by ear.
  - Voice EQ in the composition, and no compressor: high-pass 80 Hz, low shelf +2 dB at 160 Hz,
    −1.5 dB at 3 kHz (q 1.2), high shelf +1 dB at 9 kHz.
  - `reels/mix <slug>` mixes the voice and effects losslessly into `edit/final/<slug>-mix.wav`.
  - Render the picture as ProRes HQ:
    `npx -y hyperframes@0.9.58 render --format mov --prores-profile hq --quality delivery -o <content root>/<slug>/edit/final/<slug>-master.mov`
    (HyperFrames always encodes its own sound as AAC, so it isn't used).
  - `reels/finish <slug>` takes the ProRes picture and the lossless mix, compresses once, and
    normalizes to −14 LUFS and −1.5 dBTP. It encodes H.264 CRF 16 and AAC 320 kbps.
- **Check sync by correlation.** Compare the new voice with a track known to match the picture,
  around every cut. A take's own clip in `edit/tight/` is in sync with itself, so compare its
  sound and frames with the reel's at the mapped time. A few ms off means the frame accounting is
  wrong; the final AAC encode adds a constant 1 ms, which is fine.

## Cutting

- **Don't trust Whisper's word times at a cut.** In 0002 they were half a second early at the
  start of a take, so "start at the second 'getting'" began inside the first one and kept a
  breath.
  - Plot the take's level in 10–20 ms steps and start in the silence just before the word.
  - Re-transcribe the trimmed take from the lossless audio (`words.py`) and fix the first words
    by the level plot.
- **Start and end every take on a frame boundary.** A start in the middle of a frame puts the
  sound up to a frame ahead of the picture.
- **Trim the joins.** Take off a trailing breath at the end of a take, and the click and pause at
  the start of the next one (herdr → "Follow" lost 2 + 8 frames).
- Take the takes you called "best best"; check the closing line ends right after its last word.

## Steps

```sh
reels/photos <slug> <photos share link> --new          # or a Drive folder with reels/pull
reels/pull <drive folder> <slug> --force               # the studio WAV, from the reel's Drive folder
reels/launch local <slug> --no-queue --prompt "…"      # project, links
reels/sync <slug>                                      # pair the video with the studio audio
first-edit/launch <content root>/<slug>/raw/01         # takes (CPU transcription: about 10 min)
reels/tighten <slug>
python3 reels/templates/github-repo/plan.py <content root>/<slug> edit/projects/<slug> plan.json
#   join the planned takes into edit/green/talk.mp4, cut the background out (above)
python3 reels/templates/github-repo/voice.py <content root>/<slug> plan.json frames.json <content root>/<slug>/edit/green/talk-hq.wav
ffmpeg -i <content root>/<slug>/edit/green/talk-hq.wav -af "<the mastering chain above>" -c:a pcm_s24le <content root>/<slug>/edit/green/talk-hq-master.wav
#   capture the GitHub page and the site (above); fetch the icons; write the sections in build.py
python3 reels/templates/github-repo/build.py plan.json edit/projects/<slug>
npx -y hyperframes@0.9.58 check                        # the 422 "browser_safe_codec" errors are harmless
npx -y hyperframes@0.9.58 render --format mov --prores-profile hq --quality delivery -o <content root>/<slug>/edit/final/<slug>-master.mov
reels/mix <slug> && reels/finish <slug>
bin/edit <slug>                                        # review on the LAN
```

`example-plan.json` and `example-frames.json` are 0002's final plan and frame counts. Upload to
Drive (`reels/deliver`) only after the person approves the cut.

## Reviewing

- **HyperFrames Studio** (`bin/edit <slug>`) previews the composition.
  - Paused, it shows a still without transparency; press play.
  - The first play uses a VP8 copy of the cutout that keeps transparency, so the room may show for
    a moment while it is made.
- **The finished MP4** goes on a LAN page served with range support, so seeking works
  (`npx -y http-server@14.1.1 -p 8767 -a 0.0.0.0 -c-1`). Python's `http.server` can't serve
  ranges, and playback stalls.
