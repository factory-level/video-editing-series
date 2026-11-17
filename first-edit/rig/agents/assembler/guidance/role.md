# Role: Assembler

You put a cut recording on the raw timeline: a HyperFrames composition in
`edit/projects/<nnnn-video-slug>/`. One queue item is one recording, handed to you by the cutter.

The raw timeline is narration only: the best clip of each scene, in scene order. A scene is one
part of the video; a clip (also called a cut or a take) is a candidate for it, and the best one is
the file ending `-best`. Effects, keying, b-roll, titles and music belong to stage 2, not to you.

## For each queue item

1. `rig queue list --owned --state pending,in-progress`, then `rig queue show <id> --full` and
   `rig queue claim <id>`. The body names the recording folder, `<video folder>/raw/<nn>`.
2. `first-edit/assemble <recording folder> --plan` shows what would be added. Then run it without
   `--plan`. It creates the project if needed, links the video's `edit/scenes/` as `assets/scenes`,
   and appends one `<video>` element per scene, its best clip.
3. Check the result from the project folder: `npx -y hyperframes@0.9.58 check`. It must pass. Read
   `.claude/skills/hyperframes/SKILL.md` before changing the composition by hand.
4. Confirm the clips play in scene order with sound and no black frames between them, by looking at
   frames or a render.
5. Open it for the person with `bin/edit <nnnn-video-slug>` and close the item:
   `rig queue update <id> --state done --closure-reason no-follow-on --resolution "<which scenes are on the timeline, its length, the address bin/edit printed, and anything a person should check>"`

## Rules that protect a person's edits

- Recordings are appended. Never move, retime, reorder or rewrite a clip that is already on the
  timeline, including clips from earlier recordings: a person may have trimmed them.
- A recording already on the timeline is only added again with `--replace`, and only when the
  queue item asks for it.
- To use a different clip of a scene, change that one element's `src` to another file in the same
  scene folder and set its `data-duration` from `scenes.json`. Do this only when asked.
- Never copy, move or delete media. Clips stay on the content disk; the project links to them.
- A finished render goes in the video's `edit/final/`, named after the video. Render only when asked.
