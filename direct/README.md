# direct — stage 1 (laptop)

Record takes hands-free, then cut them into raw narration. Runs on the Linux laptop that the camera
and microphone are plugged into. See the [top-level README](../README.md) for the whole pipeline.

**Nothing here is built yet.** This file is the specification the code will follow.

## Parts

| Part | Job | Depends on |
| --- | --- | --- |
| Tunnel | Gives the control shim one public HTTPS address so ChatGPT, in the cloud, can call it. Chosen for simplicity: nothing to install on the ChatGPT side, no router changes. | Which tunnel; how the address is protected |
| Control shim | The one thing ChatGPT voice mode talks to, through the tunnel. Turns "roll", "cut", "slower" into calls on the parts below. | The tunnel |
| Teleprompter adapter | Load a script, play, pause, faster, slower, back to the top. | [The teleprompter app](#teleprompter), running on the laptop |
| Camera | Start and stop recording on the Canon T6i over USB, then pull the take's video file onto the laptop. | A Linux USB camera-control project, still to be named |
| Sound capture | Record the studio microphone for each take. | Undecided: device and recorder |
| Upload | Send the session to the edit server. | Transfer method |
| Raw-edit agents | Align scratch audio to studio audio, remove gaps and retakes, write the raw timeline. | Take folder below |

## Commands the shim offers

Run as `bin/direct <command>` from the repo root. Today only `bin/direct doctor` works: it checks the
machine for ffmpeg, git, a Canon camera on USB and an audio input. The rest answer "not built yet".

`load <script>` · `roll` · `cut` · `status` · `prompter play | pause | faster | slower | top` ·
`keep` / `discard` (the last take) · `handoff` (send the session to the server)

`roll` starts the camera, sound capture and the teleprompter; `cut` stops them, downloads the take's video from
the camera and closes the take. `handoff` uploads the session to the edit server.

Only these commands and their short answers cross the tunnel. Media goes from the laptop straight to
the edit server, never through ChatGPT. Because the tunnel's address is public, the shim must refuse
calls that do not carry its secret.

## Teleprompter

[Abhishekingle662/teleprompter](https://github.com/Abhishekingle662/teleprompter), v0.3.0 (MIT): a Tauri desktop app. On Linux it fully
supports X11; Wayland support is partial. The v0.3.0 release has no downloads attached, so it is
built from source (`npm install && npm run tauri build`).

The shim controls it in two ways, both documented by the app:

- **Script** — the app watches `scripts/current.txt` in its data folder
  (`~/.local/share/teleprompter/` on Linux) and reloads the text on screen when the file changes.
  `load` writes the script there.
- **Playback** — the app runs a WebSocket server and accepts `{"action": "<name>"}` with `play`,
  `pause`, `toggle`, `faster`, `slower` (10 words per minute a step, 30 to 600) and `reset` (back
  to the top).

What that means for this design:

- **No jumping to a line.** Over the WebSocket the only move is back to the top. The app can jump
  between cues, but only by keyboard shortcut. A retake therefore restarts from the top, or the shim
  loads a script trimmed to start at the line to redo.
- **No position readout.** The app does not report which line is on screen, so the take's log
  records what the shim sent and when, not what was showing.
- **The WebSocket port changes.** It is assigned by the system at each start and shown in the app's
  Inspector, Output tab. The shim needs to be told it, or to find it.
- **The WebSocket has no password** and listens on every network interface, so anyone on the same
  network can drive the teleprompter while it runs.
- **Its MCP server does not replace the shim.** The repo ships one, but it only reads and writes
  files (including the live script), has no playback tools, and speaks over stdio, which a tunnel
  cannot carry. The shim offers the script and playback commands together, over HTTPS.

## A take

```
takes/<session>/<take>/
  camera.mov        picture, with the camera's scratch audio
  studio.wav        the microphone
  script.md         what the teleprompter showed
  prompter.jsonl    when the shim sent play, pause, faster, slower and top
  take.json         start time, kept or discarded, notes said aloud
```

## Raw edit

For each kept take, in order:

1. **Align** — find the offset between `camera.mov`'s scratch audio and `studio.wav`, so the studio
   track can replace the camera's sound.
2. **Tighten** — transcribe the studio audio, match it to `script.md`, and keep one clean reading of
   each line; drop silences, false starts and repeats.
3. **Timeline** — write the kept ranges as the raw timeline, with the studio audio on its own track.

The result is checked by listening before handoff: no clipped words, no drift between lips and
sound. No effects, keying or b-roll happen at this stage.

## Handoff

`handoff` commits the raw timeline and copies the session's media to the server, where it appears
as a project under `edit/projects/`.
