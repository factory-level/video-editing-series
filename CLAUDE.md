# video workspace

Two stages on two machines; read `README.md` first. `direct/` is stage 1 (laptop: record, raw edit) and is a
specification only so far. `edit/` is stage 2 (this server: effects edit, render, upload).

- Stage 2 starts from the raw timeline. Do not re-cut narration there, and do not add effects, keying or b-roll in
  stage 1.
- Projects live in `edit/projects/<name>`. Open one for the person with `edit/launch <name>` and give them the
  address it prints; this machine is headless, so they open it from another computer.
- **OpenFilm: run `edit/bin/openfilm <command>`** wherever the OpenFilm skill or its manual says
  `npx -y openfilm@latest <command>` or `openfilm <command>`. It is a pinned copy (`edit/tools/openfilm`) patched so
  Studio serves the LAN. A newer unpatched CLI replaces the running Studio with a loopback-only one, so do not run
  `npx openfilm@latest` or `openfilm update` here.
- HyperFrames previews bind to the LAN through `HYPERFRAMES_PREVIEW_HOST` (set in `.claude/settings.json`); start
  them with `edit/launch`, or with `--background --no-open`.
