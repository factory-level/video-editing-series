---
name: reel-sfx
description: Instagram-style sound design for a reel - which effects (whoosh, pop, ding, shutter, bass boom, record scratch, typing, cha-ching), where they go, and how to mix them so they vary and sit under the voice. Use when a reel or short needs sound effects, when told to "mix up" or "add" SFX, or when animating infographics, icons or text that should land with a sound.
---

# Reel sound effects: the Instagram palette

Built on the `media-use` skill's sound effects (`.claude/skills/media-use/audio/references/sfx.md`):
Openverse (CC0 and CC BY only) first, then the bundled library. This skill says **which** effects a
reel wants and **how to place and mix them**.

## Fetch the palette

From the project folder, one search per effect (`--json` prints where it landed):

```sh
npx -y hyperframes@0.9.58 media-use resolve --type sfx --intent "<effect>" --json
```

| Role | Ask for | Bundled fallback |
| --- | --- | --- |
| Cut to a new idea or section | `swoosh whip`, `whoosh-short` | `whoosh-short`, `whoosh` |
| Element pops in (icon, chip, card) | `bubble pop` | `pop`, `click` |
| Key word or punchline lands | `vine boom bass` | `impact-bass-1` |
| Correct, done, a tick | `ding bell short` | `ping`, `chime` |
| A "wrong" or "dumb" beat | `record scratch` | `error`, `glitch-1` |
| Screenshot, site or page appears | `camera shutter` | `click` |
| Code, a terminal or a prompt types | `keyboard typing short` | `typing`, `key-press` |
| Money, a win, a stat | `cash register cha-ching` | `sparkle` |
| A build-up before a reveal | `riser` (bundled, 10.03 s: start at reveal − 10.03) | `riser` |

Copy each file into the project's `assets/sfx/` with a name that says what it is (`whip.mp3`,
`boom.mp3`). A CC BY sound goes in `assets/sfx/CREDITS.md`, and in the post's caption.

## Place and mix

- **Vary them.** Never the same effect on two cuts in a row. Alternate whip and whoosh on cuts,
  and save the boom for at most two moments.
- **Sync to the picture.** A pop starts on the frame the element appears. A whoosh peaks on the cut,
  so it starts about 0.2 s before. A boom lands with the word.
- **Under the voice.** `data-volume` 0.25–0.4, booms and risers at 0.3 or less while someone talks.
  Never put an effect on top of a stressed word unless it is the boom for that word.
- **Pace.** About one effect every 2–4 s in an infographic, fewer over plain talking. A stack of
  icons popping in can take quick pops 0.15–0.25 s apart, each a touch quieter (0.35, 0.3, 0.25).
- **Silence works too.** Drop the effects for the line just before the payoff, then hit it.
- Each effect is an `<audio>` on its own track index with `data-audio-group="sfx"`; `reels/finish`
  normalizes the whole mix afterwards.
