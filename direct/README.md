# direct — stage 1 (laptop)

Record takes hands-free, then cut them into raw narration. Runs on the laptop that the camera and
microphone are plugged into. See the [top-level README](../README.md) for the whole pipeline.

**Nothing here is built yet.** This file is the specification the code will follow.

## Parts

| Part | Job | Depends on |
| --- | --- | --- |
| Control shim | The one thing ChatGPT Advanced Voice talks to. Turns "roll", "cut", "back to line 12", "slower" into calls on the parts below. | How ChatGPT reaches the laptop |
| Teleprompter adapter | Load a script, start, pause, seek to a line, set speed; report the line on screen. | The teleprompter repo |
| Camera adapter | Start and stop recording on the Canon T6i over USB; report whether it is rolling; pull the clip off the card. | The USB camera project |
| Mic adapter | Record the studio microphone for exactly the span the camera rolls. | Device and recorder choice |
| Raw-edit agents | Align scratch audio to studio audio, remove gaps and retakes, write the raw timeline. | Take folder below |

## Commands the shim offers

`load <script>` · `roll` · `cut` · `status` · `prompter start | pause | to <line> | speed <n>` ·
`keep` / `discard` (the last take) · `handoff` (send the session to the server)

`roll` starts camera, microphone and teleprompter together; `cut` stops them and closes the take.

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
