# first-edit — the cut between recording and effects (server)

Turns an uploaded take into pieces and puts them on the raw timeline. Runs on the server, after
stage 1 uploads a take and before stage 2 adds effects. See the [top-level README](../README.md).

Built and tested on a generated sample take. Not yet tried on a real take from the camera, and the
agent team has not been launched.

## What it does to a take

```
<content root>/<video-slug>/<take>/
  camera.mp4   studio.wav   script.md          what stage 1 uploaded
  pieces/
    a-welcome-to-the-video-editing-series/     one folder per idea, lettered in playing order
      reading-1.mp4
    b-each-take-is-uploaded-to-the/
      reading-1.mp4                            a false start
      reading-2.mp4                            the full line
    ...
  pieces.json                                  every idea and reading, times, the suggested reading
```

1. **Align.** Compare the camera's scratch audio with `studio.wav` to find how far apart the two
   recordings started. If they do not line up clearly, nothing is cut and a person is asked to look.
2. **Transcribe** the studio audio with word timings (Whisper, on the GPU when there is one).
3. **Cut every reading** into its own piece, tight to the speech, with the picture from the camera
   and the sound from the studio microphone.
4. **Sort by idea.** With a script, an idea is a script sentence, and its retakes and false starts
   go in the same folder. Without one, readings that begin with the same words are grouped.

Nothing is thrown away. Each idea has one reading marked `suggested` (the fullest, and the latest
of those); the others stay beside it. Idea folders are lettered `a`, `b`, `c` … so they sort in
playing order (`aa`, `ab` … past 26). A remark that is not in the script gets its own folder, placed
where it was said.

## Commands

```sh
first-edit/launch <take folder>              # align, transcribe, cut, sort; writes pieces/ and pieces.json
first-edit/launch <take folder> --plan       # decide and write pieces.json, cut nothing
first-edit/assemble <take folder>            # add the take to edit/projects/<video-slug>/ (HyperFrames)
bin/edit <video-slug>                        # open the timeline in a browser on the LAN
```

`launch` needs [uv](https://docs.astral.sh/uv/) and ffmpeg; the first run downloads the Whisper
model and, for the GPU, about 1 GB of libraries. Options: `--gap` (a pause this long starts a new
piece, default 0.6 s), `--pad` (room kept around each reading, default 0.15 s), `--model`, `--force`.

`assemble` puts one clip per idea on the timeline, in letter order, using the suggested reading. It
only ever appends: clips already there are not moved, so a person's trims are kept. Remarks that
are not in the script stay off the timeline. The pieces are linked into the project, not copied.

## Try it without a camera

```sh
uv run first-edit/test/make-sample-take.py <content root>/sample-video/take-001
first-edit/launch   <content root>/sample-video/take-001
first-edit/assemble <content root>/sample-video/take-001
bin/edit sample-video
```

The sample is synthetic speech with a false start, a retake and an unscripted remark, and a camera
clip that starts 0.27 s before the studio recording. Expect `studio = camera -0.270 s` and
8 readings in 6 ideas.

## The team

`rig/rig.yaml` defines an [OpenRig](https://github.com/mvschwarz/openrig) team named `first-edit`
with two Claude Code agents. One queue item is one take.

| Seat | Does | Hands on to |
| --- | --- | --- |
| `edit-cut@first-edit` | Runs `first-edit/launch`, checks the sorting against the script, reruns with other options if a pause split or joined ideas | `edit-assemble@first-edit` |
| `edit-assemble@first-edit` | Runs `first-edit/assemble`, checks the composition, opens it with `bin/edit` | the person, in the item's resolution |

```sh
rig up first-edit/rig/rig.yaml                 # start the team
rig queue create --destination edit-cut@first-edit \
  --summary "First edit sample-video take-001" \
  --body "Take folder: <content root>/sample-video/take-001"
rig down first-edit                            # stop it
```

Starting the team adds OpenRig's managed blocks to this repository's `CLAUDE.md` and hooks to
`.claude/settings.local.json`, and its agents use your Claude account while they work.

## Known limits

- Tested only on the generated sample. Real scratch audio from the camera is noisier and may need
  `--max-offset` raised or a person's look when the alignment score is low.
- The transcriber can leave out a stumble or a repeated word, so a very short false start may be
  missing from the pieces.
- An idea is a script sentence. A script written as long sentences gives long pieces.
- A reading that the camera did not film (it started late or stopped early) is kept as sound only
  and left off the timeline.
