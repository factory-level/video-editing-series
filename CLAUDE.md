# video workspace

Two stages on two machines; read `README.md` first. `direct/` is stage 1 (laptop: record, then upload
each take; the raw cut runs on this server's OpenRig when the laptop calls back); start it with `direct/launch`.
`edit/` is stage 2 (this server: effects edit, render, upload).

- First edit (`first-edit/`, this server) turns each uploaded recording into scenes and clips and puts the best
  clips on the raw timeline. Media lives outside the repository: `<content root>/<nnnn-video-slug>/raw/<nn>/` is
  read only, and `edit/scenes/` and `edit/final/` beside it are written. The content root is in the git-ignored
  `PATH.md`; never write that path into a tracked file. A scene is one part of the video; a clip (a cut, a take)
  is a candidate for it. The team is `first-edit/rig/rig.yaml`; see `first-edit/README.md`.
- Stage 2 starts from the raw timeline. Do not re-cut narration there, and do not add effects, keying or b-roll in
  stage 1.
- Projects live in `edit/projects/<name>`. Open one for the person with `bin/edit <name>` and give them the
  address it prints; this machine is headless, so they open it from another computer.
- **OpenFilm: run `edit/bin/openfilm <command>`** wherever the OpenFilm skill or its manual says
  `npx -y openfilm@latest <command>` or `openfilm <command>`. It is a pinned copy (`edit/tools/openfilm`) patched so
  Studio serves the LAN. A newer unpatched CLI replaces the running Studio with a loopback-only one, so do not run
  `npx openfilm@latest` or `openfilm update` here.
- HyperFrames previews bind to the LAN through `HYPERFRAMES_PREVIEW_HOST` (set in `.claude/settings.json`); start
  them with `bin/edit`, or with `--background --no-open`.
