# video workspace

- **OpenFilm: run `bin/openfilm <command>`** (from the repo root; `../bin/openfilm` inside a film folder) wherever
  the OpenFilm skill or its manual says `npx -y openfilm@latest <command>` or `openfilm <command>`. It is a pinned
  copy (`tools/openfilm`) patched so Studio serves the LAN. A newer unpatched CLI replaces the running Studio with a
  loopback-only one, so do not run `npx openfilm@latest` or `openfilm update` here.
- This machine is headless. Give the person the `http://<LAN address>:4747/open?key=…` address that
  `bin/openfilm open` prints; they open it from another computer.
- HyperFrames previews bind to the LAN through `HYPERFRAMES_PREVIEW_HOST` (set in `.claude/settings.json`); start
  them with `--background --no-open`.
