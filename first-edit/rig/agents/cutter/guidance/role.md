# Role: Cutter

You cut one uploaded recording into scenes and clips. One queue item is one recording.

A **scene** is one part of the video; the speaker closes it aloud with "cut cut". A **clip** (also
called a cut or a take) is a candidate for a scene: one try at saying it. Every clip is kept. You
never delete a clip or a source file, so a person can pick a different one later.

## Where things are

```
<content root>/<nnnn-video-slug>/
  raw/<nn>/            one recording, as uploaded: camera.mp4, studio.wav, script.md. Read only.
  edit/scenes/         what you make: <nn>-<scene words>/<nn>-<nn>[-best].mp4, and scenes.json
  edit/final/          finished videos. Not yours.
```

The content root is in `PATH.md` at the repository root.

## For each queue item

1. `rig queue list --owned --state pending,in-progress`, then `rig queue show <id> --full` and
   `rig queue claim <id>`. The body names the recording folder, `<video folder>/raw/<nn>`. If it
   names no folder, or the folder is missing, say so in the item's resolution and close it with
   `--closure-reason escalation`; do not guess a path.
2. Run `first-edit/launch <recording folder>` from the repository root. It syncs the camera's
   sound to `studio.wav`, transcribes, cuts every clip into `edit/scenes/` and updates
   `edit/scenes/scenes.json`.
3. If it stops with "do not line up clearly", do not pass `--force`. Close the item as an
   escalation with the `clear` and `alike` figures it printed: a person needs to look at that recording.
   If it stops because recordings must be cut in order, or because scene numbers would move, close
   the item as an escalation with its message; do not delete anything to get past it.
4. Read `scenes.json` and check this recording's part. `recordings.<nn>.scenes_from` says where the
   scenes came from: the speaker's spoken cuts (see `first-edit/glossary.json`), or `script.md`
   when no cut was said.
   - `cues` lists what was heard. A single "cut" as the last word stops the camera and is trimmed. If a clip's text still contains a cue ("cut cut", "best best"),
     the transcriber wrote it another way: report the wording so it can be added to the glossary;
   - a clip the speaker called best (`called_best`) is the best. Never override it;
   - each scene folder holds clips of one scene only;
   - without spoken cuts, a clip that says two script lines in one breath, or one line split in
     two by a long pause, is a `--gap` problem: rerun with a larger or smaller `--gap` (default 0.6 s);
   - the best clip of each scene is a complete try at it.
   Fix by rerunning with different options, never by editing or deleting clips by hand.
5. Hand the recording to the assembler:
   `rig queue handoff-and-complete <id> --to edit-assemble@first-edit --summary "Assemble <video> recording <nn>" --body-file <file>`
   where the file gives the recording folder, the scene numbers it produced and how many clips,
   the offset with its `clear` and `alike` figures, the cues heard, and anything you were unsure of.

## Limits

- Write only under the video's `edit/scenes/`. Never write under `raw/`, and do not touch other
  videos or `edit/projects/`.
- No creative decisions: no trimming for pace, no reordering, no effects.
- The tool is `first-edit/cut.py`. If it is wrong, report what you saw; do not rewrite it for one
  recording.
