# first-edit — the cut between recording and effects (server)

Turns an uploaded take into scenes and clips and puts the best clips on the raw timeline. Runs on
the server, after stage 1 uploads a take and before stage 2 adds effects. See the
[top-level README](../README.md).

Built and tested on generated sample takes. Not yet tried on a real take from the camera, and the
agent team has not been launched.

## Words

| Word | Means |
| --- | --- |
| **Take** | One continuous recording from stage 1: a camera file and a studio audio file, uploaded as one folder. |
| **Scene** | One part of the video. A take holds one or more scenes. |
| **Clip** | A candidate for a scene: one try at saying it. A scene holds one or more clips, and one of them is the best. |

## The three steps

1. **Sync** the studio audio to the camera's video.
2. **Cut** the take into scenes, every clip kept.
3. **Edit to the timeline**: the best clip of each scene, in order.

## Directing the cut aloud

While recording, you say what you want cut. Each cue is a word said twice, so it does not turn up
in ordinary speech; the cues are trimmed out of the clips.

| Say | Means |
| --- | --- |
| **"cut cut"** | This scene is finished. Everything said since the last cut is one scene; the next thing said starts a new one. |
| **"best best"** | The clip just finished is the one to use for this scene. |

The glossary is [`glossary.json`](glossary.json); add a line there to add another way of saying a
cue. A new kind of cue (something other than cut and best) needs code as well.

Inside a scene, a new clip starts when you begin the scene again from its opening words, or after
you call one best. If you never say "best best" in a scene, the last full clip is the best.

## What it does to a take

A take with three scenes, the first tried three times:

```
<content root>/<video-slug>/<take>/
  camera.mp4   studio.wav   script.md      what stage 1 uploaded
  scenes.json                              every scene and clip: times, text, the best, cues heard
  scenes/
    a-welcome-to-the-video-editing-series/   scene a: everything before the first "cut cut"
      a1.mp4                                   first clip
      a2.mp4                                   a false start
      a3-best.mp4                              followed by "best best"
    b-each-take-is-uploaded-to-the/          scene b: between the first and second "cut cut"
      b1-best.mp4                              the only clip
    c-a-team-of-agents-cuts-every/           scene c: after the second "cut cut"
      c1.mp4
      c2-best.mp4                              not called best; the last full clip
```

Scene folders are lettered in the order the scenes were spoken, and clips carry that letter and
their number, so sorting by name is sorting by time (`aa`, `ab` … past 26 scenes). `-best` marks the
clip that goes on the timeline; every other clip stays beside it.

1. **Align.** Compare the camera's scratch audio with `studio.wav` to find how far apart the two
   recordings started. If they do not line up clearly, nothing is cut and a person is asked to look.
2. **Transcribe** the studio audio with word timings (Whisper, on the GPU when there is one).
3. **Cut every clip**, tight to the speech, with the picture from the camera and the sound from the
   studio microphone.
4. **Sort into scenes.** When "cut cut" is heard, scenes are what you cut them into. When it is
   not, the script decides: each script sentence is a scene, and its retakes and false starts are
   its clips. With neither, clips that begin with the same words share a scene.

Nothing is thrown away. A remark that is not in the script gets its own scene, placed where it was
said, and stays off the timeline.

## Commands

```sh
first-edit/launch <take folder>              # sync, cut into scenes and clips; writes scenes/ and scenes.json
first-edit/launch <take folder> --plan       # decide and write scenes.json, cut nothing
first-edit/assemble <take folder>            # add the take to edit/projects/<video-slug>/ (HyperFrames)
bin/edit <video-slug>                        # open the timeline in a browser on the LAN
```

`launch` needs [uv](https://docs.astral.sh/uv/) and ffmpeg; the first run downloads the Whisper
model and, for the GPU, about 1 GB of libraries. Options: `--gap` (without spoken cuts, a pause
this long starts a new clip, default 0.6 s), `--pad` (room kept around each clip, default 0.15 s),
`--model`, `--force`.

`assemble` puts the best clip of each scene on the timeline, in letter order. It only ever
appends: clips already there are not moved, so a person's trims are kept. The scenes folder is
linked into the project, not copied.

## Try it without a camera

```sh
uv run first-edit/test/make-sample-take.py <content root>/sample-video/take-001
first-edit/launch   <content root>/sample-video/take-001
first-edit/assemble <content root>/sample-video/take-001
bin/edit sample-video
```

That sample is synthetic speech with a false start, a retake and an unscripted remark, sorted by
its script: expect `studio = camera -0.270 s` and 8 clips in 6 scenes. Add `--cues` to
`make-sample-take.py` for a take directed aloud instead: three scenes closed by "cut cut", with
3, 1 and 2 clips and `a3` called best. Both were made by a speech synthesiser, so they show
the sorting works, not that the cues are heard reliably in a real voice.

## The team

`rig/rig.yaml` defines an [OpenRig](https://github.com/mvschwarz/openrig) team named `first-edit`
with two Claude Code agents. One queue item is one take.

| Seat | Does | Hands on to |
| --- | --- | --- |
| `edit-cut@first-edit` | Runs `first-edit/launch`, checks the scenes and clips against what was said, reruns with other options if needed | `edit-assemble@first-edit` |
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
- The transcriber can leave out a stumble or a repeated word, so a very short false start may not
  become a clip.
- Without spoken cuts, a scene is a script sentence. A script written as long sentences gives long
  clips.
- With spoken cuts, a clip is kept whole, pauses between its sentences included; tightening those
  is left to the timeline.
- A cue the transcriber mishears is missed, and its words stay in a clip. `scenes.json` lists the
  cues that were heard, so a missing one shows.
- A clip that the camera did not film (it started late or stopped early) is kept as sound only
  and left off the timeline.
