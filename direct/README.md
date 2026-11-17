# direct — stage 1 (laptop)

Record takes hands-free, then cut them into raw narration. Runs on the laptop that the camera and
microphone are plugged into. See the [top-level README](../README.md) for the whole pipeline.

## Run it

```sh
direct/launch                 # check the laptop: tools, camera, microphone, teleprompter
direct/launch <session>       # start the teleprompter and the control shim
direct/ctl roll               # then: cut | status | load <file> | keep | discard | prompter <action>
direct/launch --stop          # stop the shim; a rolling take is cut first
```

`npm run video:direct -- <session>` from the repo root is the same as `direct/launch <session>`.
`direct/ctl mcp` serves the same commands to ChatGPT as an MCP server. Set `DIRECT_MIC` to a PipeWire
source to record something other than the default microphone.

**What works:** the shim, the camera (T6i, 1080p clips recorded to the card and pulled into the take
folder), the microphone, the teleprompter. **Not built:** upload, callback, `handoff`, and
`prompter to <line>` (the teleprompter cannot seek to a line). The rest of this file is the
specification.

**Camera setup** (full notes in [camera-t6i.md](camera-t6i.md))**.** Power switch on the movie position, a card inserted, USB connected. The shim keeps
one connection open for the whole session, sets the capture target to the card and turns live view
on; without those the camera accepts "record" and records nothing. It also unmounts the camera from
the desktop, which otherwise holds the USB connection. Clips are removed from the card once
downloaded. Wait about ten seconds after `direct/launch` before the first `roll`, or the camera
starts that take late.

## Teleprompter

[Abhishekingle662/teleprompter](https://github.com/Abhishekingle662/teleprompter) v0.3.0 (MIT), a
Tauri desktop app, built from source because the release has no downloads. The shim controls it two
ways:

- **Script** — the app watches `scripts/current.txt` in its data folder
  (`~/.local/share/com.teleprompter.app/` on Linux) and reloads the text on screen when the file
  changes. `load` writes the script there; `DIRECT_PROMPTER_SCRIPT` overrides the path.
- **Playback** — the app runs a WebSocket server and accepts `{"action": "<name>"}` with `play`,
  `pause`, `toggle`, `faster`, `slower` (10 words per minute a step) and `reset` (back to the top).

What that means here:

- **No jumping to a line.** Over the WebSocket the only move is back to the top.
- **No position readout.** `prompter.jsonl` records what the shim sent and when, not what was
  showing.
- **The WebSocket port changes** at each start. The shim finds it by looking up the port the
  `teleprompter` process is listening on.
- **The WebSocket has no password** and listens on every network interface, so anyone on the same
  network can drive the teleprompter while it runs.
- **A connection is only served when the next one arrives** (a bug in 0.3.0; its own
  `scripts/ws-smoke.mjs` times out). The shim follows each command with a throwaway connection.
- **Its own MCP server does not replace the shim**: it only reads and writes files and has no
  playback tools.

## Parts

| Part | Job | Depends on |
| --- | --- | --- |
| Control shim | The one thing ChatGPT Advanced Voice talks to. Turns "roll", "cut", "back to line 12", "slower" into calls on the parts below. | How ChatGPT reaches the laptop |
| Teleprompter adapter | Load a script, start, pause, seek to a line, set speed; report the line on screen. | The teleprompter repo |
| Camera adapter | Start and stop recording on the Canon T6i over USB; report whether it is rolling; pull the clip off the card. | The USB camera project |
| Mic adapter | Record the studio microphone for exactly the span the camera rolls. | Device and recorder choice |
| Uploader | When a take closes, copy its folder to the server, confirm every file arrived intact, then call back to the OpenRig there. | Transfer method; the OpenRig callback |
| First-edit agents (on the server's OpenRig) | Align scratch audio to studio audio, remove gaps and retakes, append the take to the raw timeline. | The callback; take folder below |

## Commands the shim offers

`load <script>` · `roll` · `cut` · `status` · `prompter start | pause | to <line> | speed <n>` ·
`keep` / `discard` (the last take) · `handoff` (send the session to the server)

`roll` starts camera, microphone and teleprompter together; `cut` stops them and closes the take.

## A take

```
takes/<session>/<take>/
  camera.mp4        picture, with the camera's scratch audio (the camera's own file type)
  studio.wav        the microphone
  script.md         what the teleprompter showed
  prompter.jsonl    which teleprompter command was sent when
  take.json         start time, kept or discarded, notes said aloud
```

## First edit

The cut runs on the server, not the laptop. It starts by itself for each kept take, as soon as the
upload is confirmed and the laptop has called back to the OpenRig:

1. **Align** — find the offset between `camera.mov`'s scratch audio and `studio.wav`, so the studio
   track can replace the camera's sound.
2. **Tighten** — transcribe the studio audio, match it to `script.md`, and keep one clean reading of
   each line; drop silences, false starts and repeats.
3. **Append** — add the kept ranges to the session's raw timeline, with the studio audio on its own
   track. Each range lands either as a clean jump cut or with a little padding on each side, so a
   person can trim it further.

The timeline is a HyperFrames (HeyGen) composition. It lags the live filming by one take's upload
and cut, and fills in as filming goes on; at the end of the session the whole piece is there for
human edits. It is checked by listening: no clipped words, no drift between lips and sound. No
effects, keying or b-roll happen at this stage.

## Handoff

Handoff is per take. `cut` followed by `keep` uploads the take folder, confirms it, and sends the
callback. The take goes into the server's content folder for the video,
`<content root>/<nnnn-video-slug>/raw/<nn>/` (one numbered folder per take). `handoff` is what is left for the end of the session: check that
every kept take is uploaded and on the timeline, and report anything missing. None of this is built.
