# first-edit — the cut between recording and effects (server)

Turns an uploaded take into pieces and puts them on the raw timeline. Runs on the server, after
stage 1 uploads a take and before stage 2 adds effects. See the [top-level README](../README.md).

Built and tested on a generated sample take. Not yet tried on a real take from the camera, and the
agent team has not been launched.

## The three steps

1. **Sync** the studio audio to the camera's video.
2. **Cut** the take into pieces, one folder per topic, every attempt kept.
3. **Edit to the timeline**: the best attempt of each topic, in order.

## Directing the cut aloud

While recording, you say what you want cut. Each cue is a word said twice, so it does not turn up
in ordinary speech; the cues are trimmed out of the pieces.

| Say | Means |
| --- | --- |
| **"cut cut"** | This topic is finished. Everything said since the last cut is one set of attempts; the next thing said starts a new set. |
| **"best best"** | The attempt just finished is the one to use for this topic. |

The glossary is [`glossary.json`](glossary.json); add a line there to add another way of saying a
cue. A new kind of cue (something other than cut and best) needs code as well.

Inside a topic, a new attempt starts when you begin the topic again from its opening words, or
after you call one best. If you never say "best best" in a topic, the last full attempt is picked.

## What it does to a take

A take with three topics, the first tried three times:

```
<content root>/<video-slug>/<take>/
  camera.mp4   studio.wav   script.md      what stage 1 uploaded
  pieces.json                              every topic and attempt: times, text, the pick, cues heard
  pieces/
    a-welcome-to-the-video-editing-series/   everything before the first "cut cut"
      a1.mp4                                   first attempt
      a2.mp4                                   a false start
      a3-best.mp4                              followed by "best best"
    b-each-take-is-uploaded-to-the/          between the first and second "cut cut"
      b1-best.mp4                              the only attempt
    c-a-team-of-agents-cuts-every/           after the second "cut cut"
      c1.mp4
      c2-best.mp4                              not called best; the last full attempt
```

Folders are lettered in the order the topics were spoken, and files carry that letter and the
attempt's number, so sorting by name is sorting by time (`aa`, `ab` … past 26 topics). `-best` marks
the pick for the timeline; every other attempt stays beside it.

1. **Align.** Compare the camera's scratch audio with `studio.wav` to find how far apart the two
   recordings started. If they do not line up clearly, nothing is cut and a person is asked to look.
2. **Transcribe** the studio audio with word timings (Whisper, on the GPU when there is one).
3. **Cut every reading** into its own piece, tight to the speech, with the picture from the camera
   and the sound from the studio microphone.
4. **Sort.** When "cut cut" is heard, topics are what you cut them into. When it is not, the
   script decides: each script sentence is a topic, and its retakes and false starts go in its
   folder. With neither, readings that begin with the same words are grouped.

Nothing is thrown away. A remark that is not in the script gets its own folder, placed where it was
said, and stays off the timeline.

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

That sample is synthetic speech with a false start, a retake and an unscripted remark, sorted by
its script: expect `studio = camera -0.270 s` and 8 readings in 6 ideas. Add `--cues` to
`make-sample-take.py` for a take directed aloud instead: three topics closed by "cut cut", with
3, 1 and 2 attempts and `a3` called best. Both were made by a speech synthesiser, so they show
the sorting works, not that the cues are heard reliably in a real voice.

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
- Without spoken cuts, a topic is a script sentence. A script written as long sentences gives long
  pieces.
- With spoken cuts, an attempt is kept whole, pauses between its sentences included; tightening
  those is left to the timeline.
- A cue the transcriber mishears is missed, and its words stay in a piece. `pieces.json` lists the
  cues that were heard, so a missing one shows.
- A reading that the camera did not film (it started late or stopped early) is kept as sound only
  and left off the timeline.
