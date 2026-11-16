# video

A two-stage, two-machine pipeline for recording and finishing narrated videos, driven by voice and
by coding agents.

| Stage | Folder | Machine | What happens | Output |
| --- | --- | --- | --- | --- |
| 1. Direct + raw edit (live) | [`direct/`](direct/) | Linux laptop, at the camera | Record takes hands-free, then cut them into a clean raw narration | A take folder with a raw timeline |
| 2. Effects edit + upload | [`edit/`](edit/) | Server | Green screen removal, b-roll, effects, review in a browser, render, upload | The finished video, published |

Status: stage 2's editors are set up and working. Stage 1 and the handoff are designed here but not
built yet; see [Open decisions](#open-decisions).

## Stage 1: direct + raw edit (laptop)

You record alone. ChatGPT in voice mode is the director: you talk to it with its sound off, and it
runs the session for you.

**How ChatGPT reaches the laptop: a tunnel.** ChatGPT runs in the cloud and the equipment is on your
desk, so something has to connect them. For simplicity that is a single tunnel: a small control
shim runs on the laptop, the tunnel gives it one public HTTPS address, and ChatGPT is connected to
that address. There is no app to install, no port to open on the router, and nothing else to host.
When you say "roll" or "slower", ChatGPT calls the shim through the tunnel and the
shim does the work locally.

```
you ── voice ──> ChatGPT ── tunnel ──> control shim (laptop) ──> teleprompter
                                                             ──> sound capture (studio mic)
                                                             ──> camera: record, download the video
                                                             ──> upload the take to the edit server
```

**Direct.** Through the tunnel, the voice session controls four things:

- **Teleprompter** — [Abhishekingle662/teleprompter](https://github.com/Abhishekingle662/teleprompter)
  v0.3.0, a desktop app for Windows, macOS and Linux. Load a script, play, pause, go faster or
  slower, return to the top.
- **Sound capture** — the studio microphone: start and stop recording with each take. How it is
  captured is not decided yet.
- **Camera** — the Canon Rebel T6i over USB, through a Linux camera-control project wrapped by the
  shim: start and stop recording, then pull the take's video file off the camera onto the laptop.
  This makes the laptop a Linux machine.
- **Upload to the edit server** — send the finished session to the server for stage 2.

The tunnel carries only these short commands and their answers. Video and audio never pass through
ChatGPT: they go from the laptop straight to the edit server.

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

Saying "hand it off" makes the shim upload the session to the edit server. A take is handed over as
one folder: the camera files, the studio audio, the script, and the raw timeline that cuts them.
The timeline is small text and travels by git; the media is large and travels beside it (copied,
not committed).

## Stage 2: effects edit + upload (server)

The server takes the raw timeline as its starting point and a second team of agents finishes it:
green screen removal, b-roll overlays, titles, captions, music, effects. Two HTML-to-video tools do
the work, both built for coding agents:

- [OpenFilm](https://github.com/openfilm/openfilm) — a `film.html` timeline of clips and pages.
- [HyperFrames](https://github.com/heygen-com/hyperframes) — HTML compositions rendered to video.

You review and adjust from any browser on the LAN:

```sh
bin/edit              # list projects and what is running
bin/edit <project>    # start its editor and print the address to open
```

Then render and upload. See [`edit/README.md`](edit/README.md) for setup, the LAN details and their
limits.

## Commands

Two commands at the root, one per stage:

```sh
bin/direct           # stage 1, on the laptop: `bin/direct doctor` checks the machine; recording is not built yet
bin/edit             # stage 2, on the server: list projects, or `bin/edit <project>` to open its editor
```

## Layout

```
bin/direct         stage 1 command
bin/edit           stage 2 command
direct/            stage 1, runs on the laptop (not built yet)
edit/              stage 2, runs on the server
  launch           what bin/edit runs
  projects/        one folder per video (of-demo and hf-demo are working samples)
  bin/openfilm     OpenFilm, pinned and patched to serve the LAN
  tools/openfilm   that pinned copy and its patch
.claude/skills/    agent skills for OpenFilm and HyperFrames
```

## Open decisions

These are not settled, and stage 1 cannot be built until they are:

1. **Teleprompter** — decided: Abhishekingle662/teleprompter v0.3.0. See
   [`direct/README.md`](direct/README.md#teleprompter) for how it is controlled and what it cannot do.
2. **Camera USB project** — a Linux project for controlling the T6i over USB; which one, and what
   it exposes, is still to be named.
3. **The tunnel** — decided in principle: ChatGPT reaches the shim through one tunnel. Still to
   choose and prove: which tunnel, how ChatGPT is connected to it, how the address is protected so
   only your ChatGPT can call it, and that voice mode can trigger those calls.
4. **Sound capture** — undecided: which device, and what records it on the Linux laptop.
5. **Raw timeline format** — proposed: an OpenFilm `film.html`, since stage 2 opens it directly.
6. **Media transfer** — proposed: `rsync` of the take folder to `edit/projects/` on the server.
7. **Upload target** — where the finished video goes (YouTube or elsewhere) and with what account.

## License

MIT; see [LICENSE](LICENSE). Bundled agent skills and the HyperFrames sample keep their own licenses; see
[THIRD_PARTY.md](THIRD_PARTY.md).
