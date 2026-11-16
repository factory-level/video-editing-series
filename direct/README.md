# direct — stage 1 (laptop)

Record takes hands-free, then cut them into raw narration. Runs on the Linux laptop that the camera
and microphone are plugged into. See the [top-level README](../README.md) for the whole pipeline.

**In development: nothing here is built yet** except `bin/direct doctor`. This file is the
specification the code will follow, and it will change as parts are proven on the real equipment.

## Parts

| Part | Job | Depends on |
| --- | --- | --- |
| Tunnel | Gives the control shim one public HTTPS address so ChatGPT, in the cloud, can call it. Chosen for simplicity: nothing to install on the ChatGPT side, no router changes. | Which tunnel; how the address is protected |
| Control shim | An MCP server: the one thing ChatGPT voice mode talks to, through the tunnel. Turns "roll", "cut", "slower" into calls on the parts below. | The tunnel |
| Teleprompter adapter | Load a script, play, pause, faster, slower, back to the top. | [The teleprompter app](#teleprompter), running on the laptop |
| Camera | Start and stop recording on the Canon T6i over USB, then pull the take's video file onto the laptop. | [gphoto2](#camera), wrapped as MCP tools |
| Sound capture | Record the studio microphone for each take. | Undecided: device, recorder, and whether it joins the camera in one MCP server |
| Upload | Send the session to the edit server. | Transfer method |
| Raw-edit agents | Align scratch audio to studio audio, remove gaps and retakes, write the raw timeline. | Take folder below |

## Commands the shim offers

Run as `bin/direct <command>` from the repo root. Today only `bin/direct doctor` works: it checks the
machine for ffmpeg, git, gphoto2, a Canon camera on USB and an audio input. The rest answer "not built yet".

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

## Camera

[gphoto2](https://github.com/gphoto/gphoto2) is the command-line tool for controlling cameras over USB on
Linux (GPL-2.0; it is run as a separate program, not copied into this repository). Its library
lists the camera as "Canon EOS 750D", the T6i's other name, with remote capture and live preview
supported.

There is no MCP server for it yet; writing one is the next piece of work. Planned tools:

| Tool | Does | gphoto2 underneath |
| --- | --- | --- |
| `camera_status` | Is a camera connected, which one, battery, space left | `--auto-detect`, `--summary` |
| `camera_record_start` / `camera_record_stop` | Start and stop movie recording to the card | the `movie` setting |
| `camera_list_files` | What is on the card | `--list-files` |
| `camera_download` | Copy the take's video to the take folder | `--get-file` |

To prove on the real camera before relying on it:

- **Movie start and stop over USB.** The library has the settings for it, but whether they work
  depends on the model and on the mode dial, so this needs a test with the T6i in hand. If it does
  not work, recording is started on the camera by hand and the tools only download.
- **Clip length.** The camera stops a recording by itself after about half an hour, so long reads
  must be split into takes.
- **One program at a time.** While gphoto2 holds the camera, the desktop must not mount it as a
  storage device, or gphoto2 cannot connect.

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

`handoff` uploads the session to the edit server, into that server's content folder for the video
(`<content root>/<video-slug>/`). The upload finishing is what starts stage 2: the server launches
its agent team, which makes the first edit.
