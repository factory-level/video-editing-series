# video

A two-stage, two-machine pipeline for recording and finishing narrated videos, driven by voice and
by coding agents.

| Stage | Folder | Machine | What happens | Output |
| --- | --- | --- | --- | --- |
| 1. Direct + raw edit (live) | [`direct/`](direct/) | Laptop, at the camera | Record takes hands-free, then cut them into a clean raw narration | A take folder with a raw timeline |
| 2. Effects edit + upload | [`edit/`](edit/) | Server | Green screen removal, b-roll, effects, review in a browser, render, upload | The finished video, published |

Status: stage 2's editors are set up and working. Stage 1 and the handoff are designed here but not
built yet; see [Open decisions](#open-decisions).

## Stage 1: direct + raw edit (laptop)

You record alone. ChatGPT Advanced Voice is the director: you talk to it with its sound off, and it
drives the session through a small control shim on the laptop.

**Direct.** The voice session controls three things:

- **Teleprompter** — its own git repo. Load a script, start, pause, scroll back to a line, change
  speed.
- **Camera** — a Canon Rebel T6i over USB, through a USB camera-control project wrapped by a shim:
  start and stop recording, check that it is rolling.
- **Mic input** — the studio microphone: arm, start and stop its recording together with the
  camera, so every take has both.

Each take leaves two recordings of the same performance: the camera's video with its own **scratch
audio**, and the microphone's **studio audio**.

**Raw edit (live).** As takes land, a team of editor agents on the laptop turns them into raw
narration:

1. Align the scratch audio to the studio audio, so the studio track replaces the camera's sound in
   sync.
2. Remove the gaps: silences, false starts and retakes, checked against the teleprompter script.
3. Write a **raw timeline**: the kept ranges of picture and studio sound, in order.

Nothing creative happens here. No effects, no keying, no b-roll: only what was said, tightened.

## Handoff: laptop → server

A take is handed over as one folder: the camera files, the studio audio, the script, and the raw
timeline that cuts them. The timeline is small text and travels by git; the media is large and
travels beside it (copied, not committed).

## Stage 2: effects edit + upload (server)

The server takes the raw timeline as its starting point and a second team of agents finishes it:
green screen removal, b-roll overlays, titles, captions, music, effects. Two HTML-to-video tools do
the work, both built for coding agents:

- [OpenFilm](https://github.com/openfilm/openfilm) — a `film.html` timeline of clips and pages.
- [HyperFrames](https://github.com/heygen-com/hyperframes) — HTML compositions rendered to video.

You review and adjust from any browser on the LAN:

```sh
edit/launch              # list projects and what is running
edit/launch <project>    # start its editor and print the address to open
```

Then render and upload. See [`edit/README.md`](edit/README.md) for setup, the LAN details and their
limits.

## Layout

```
direct/            stage 1, runs on the laptop (not built yet)
edit/              stage 2, runs on the server
  launch           open a project's editor on the LAN
  projects/        one folder per video (of-demo and hf-demo are working samples)
  bin/openfilm     OpenFilm, pinned and patched to serve the LAN
  tools/openfilm   that pinned copy and its patch
.claude/skills/    agent skills for OpenFilm and HyperFrames
```

## Open decisions

These are not settled, and stage 1 cannot be built until they are:

1. **Teleprompter repo** — which repository, and how it is controlled (HTTP, WebSocket, keys).
2. **Camera USB project** — which project drives the T6i, and what it exposes.
3. **How ChatGPT reaches the laptop** — Advanced Voice has to call the control shim somehow (a
   connector the shim serves, or another route). This decides the shim's shape.
4. **Mic recording** — which device and which recorder on the laptop.
5. **Raw timeline format** — proposed: an OpenFilm `film.html`, since stage 2 opens it directly.
6. **Media transfer** — proposed: `rsync` of the take folder to `edit/projects/` on the server.
7. **Upload target** — where the finished video goes (YouTube or elsewhere) and with what account.

## License

MIT; see [LICENSE](LICENSE). Bundled agent skills and the HyperFrames sample keep their own licenses; see
[THIRD_PARTY.md](THIRD_PARTY.md).
