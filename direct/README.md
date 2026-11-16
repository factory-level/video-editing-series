# direct — stage 1 (laptop)

Record takes hands-free, then cut them into raw narration. Runs on the laptop that the camera and
microphone are plugged into. See the [top-level README](../README.md) for the whole pipeline.

**Nothing here is built yet.** This file is the specification the code will follow.

## Parts

| Part | Job | Depends on |
| --- | --- | --- |
| Tunnel | Gives the control shim one public HTTPS address so ChatGPT, in the cloud, can call it. Chosen for simplicity: nothing to install on the ChatGPT side, no router changes. | Which tunnel; how the address is protected |
| Control shim | The one thing ChatGPT voice mode talks to, through the tunnel. Turns "roll", "cut", "back to line 12", "slower" into calls on the parts below. | The tunnel |
| Teleprompter adapter | Load a script, start, pause, seek to a line, set speed; report the line on screen. | The teleprompter repo |
| Video download | Pull each take's video file off the Canon T6i over USB onto the laptop. | The USB camera project |
| Sound capture | Record the studio microphone for each take. | Device and recorder choice |
| Upload | Send the session to the edit server. | Transfer method |
| Raw-edit agents | Align scratch audio to studio audio, remove gaps and retakes, write the raw timeline. | Take folder below |

## Commands the shim offers

Run as `bin/direct <command>` from the repo root. Today only `bin/direct doctor` works: it checks the
machine for ffmpeg, git, a Canon camera on USB and an audio input. The rest answer "not built yet".

`load <script>` · `roll` · `cut` · `status` · `prompter start | pause | to <line> | speed <n>` ·
`keep` / `discard` (the last take) · `handoff` (send the session to the server)

`roll` starts sound capture and the teleprompter; `cut` stops them, downloads the take's video from
the camera and closes the take. `handoff` uploads the session to the edit server.

Only these commands and their short answers cross the tunnel. Media goes from the laptop straight to
the edit server, never through ChatGPT. Because the tunnel's address is public, the shim must refuse
calls that do not carry its secret.

## A take

```
takes/<session>/<take>/
  camera.mov        picture, with the camera's scratch audio
  studio.wav        the microphone
  script.md         what the teleprompter showed
  prompter.jsonl    which line was on screen when
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
