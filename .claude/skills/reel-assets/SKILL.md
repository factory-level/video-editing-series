---
name: reel-assets
description: Download outside assets for a reel (an Instagram reel or post, a TikTok, a YouTube or X video, or a plain image, video or sound URL) with reels/fetch, and lay them over a vertical talking head in HyperFrames, such as the clip a reaction reel is reacting to. Use when a reel needs footage that is not in its Drive folder, when the prompt names a creator, post or link, or when building a reaction, picture-in-picture or split-screen layout.
---

# Reel assets: fetch outside media and play it over the reel

## Fetch

```sh
bin/reel fetch <nnnn-slug> <url> [--name <name>] [--cookies-from-browser chrome] [--plan]
bin/reel <drive folder> <nnnn-slug> --prompt "…" --asset <url> [--asset <url>]   # at the start of a reel
```

- Lands in `<content root>/<nnnn-slug>/fetched/<name>.<ext>`; the project sees it as
  `assets/fetched/<name>.<ext>`. Never copy it into the project.
- `fetched/fetched.json` records each file's URL, site, creator, handle, profile link, length and
  size. Read it for the credit and for timing.
- Pages go through a current yt-dlp (`uvx yt-dlp@latest`): Instagram reels and posts, TikTok,
  YouTube, X, Vimeo and most video sites. Anything else is downloaded as a plain file.
- A private or login-gated post fails without cookies: `--cookies-from-browser chrome` (or
  `firefox`) uses that browser's session on this machine. A carousel post gives its first item.
- HDR (phone footage) is tone-mapped to Rec.709 on arrival, like the reel's own clips.
- `--plan` shows the site, creator, length and size without downloading.

## Rights and credit

Use someone else's clip only to comment on it: a reaction, a reply, a quote. Show the shortest part
that makes the point (a few seconds, rarely more than 10), keep the commentary the main thing, and
credit the creator on screen the whole time their clip is visible: `@handle` from `fetched.json`
(`creator_handle`), small, on the clip. If the person has not said they may use it, say whose clip
it is and ask before publishing. Never strip a watermark.

## Layouts for a 1080x1920 talking head

Look at frames first (`npx -y hyperframes@0.9.58 snapshot`): where the face is decides the layout.
A phone propped for a talking head leaves the top 35–45% of the frame as background, which is
where an outside clip goes.

| Layout | When | How |
| --- | --- | --- |
| **Card at the top** | The default for a reaction: their clip and your face both visible | The clip in a rounded card across the top background, about 960 px wide (a 9:16 source: about 520x925; 16:9: 960x540), `top: 90px`, centred. A thin border and shadow so it reads as a separate screen. Credit under or on the card. |
| **Watching, then reacting** | The opening of a reaction reel | Open on the speaker watching their phone (silent b-roll), with the source clip in the card and its sound up, for 2–4 s; cut to the speaker's first line as the hook. |
| **Full-frame cutaway** | Showing a detail of the source (a screen, a product) | The source fills the frame (`object-fit: cover`) while the speaker's voice continues underneath (an L-cut); 1–3 s, then back. |
| **Split screen** | A back-and-forth with the source | Top half the source, bottom half the speaker (`object-fit: cover`, crop to the face). Use when the face sits in the lower half anyway. |

- Captions move clear of a card at the top: keep them below the face, as before.
- Keep everything inside Instagram's safe area: clear of the top 250 px for text, and of the bottom
  400 px.
- Enter the card with a short scale-and-fade (0.2 s, `back.out`), leave with a fade; a whoosh from
  the `media-use` sound effects on the entrance.

## Sound

- The source's own sound is up (`data-volume` about 0.8, `data-has-audio="true"`) only while the
  speaker is silent: the "watching" opening, or a quote the speaker is responding to.
- While the speaker talks over it, the source is muted (`muted`, or `data-volume="0"`): never two
  voices at once.
- The source's loudness differs from the speaker's: let `reels/finish` normalize the mix, and listen
  to the joins.

## In the composition

The source clip is a `<video>` on its own lane, above the speaker (`z-index`), timed with
`data-start`, `data-duration` and `data-media-start` (the point in the source to start from). Wrap
it in a positioned `<div>` for the card's frame and the credit. See
`.claude/skills/hyperframes/references/format.md` for media attributes and `overlays.md` for cards.
