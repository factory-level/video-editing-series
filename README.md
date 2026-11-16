# video

Workspace for making videos with coding agents, using two HTML-to-video tools:

- [OpenFilm](https://github.com/openfilm/openfilm) — `of-demo/` (a `film.html` plus pages exposing `window.film.frame(t)`)
- [HyperFrames](https://github.com/heygen-com/hyperframes) — `hf-demo/` (HTML compositions)

Agent skills for both live in `.claude/skills/` (pinned in `skills-lock.json`).
Requires Node 22+, ffmpeg and git. Renders and caches are git-ignored.

## Render

```sh
cd hf-demo && npx -y hyperframes@latest render      # -> hf-demo/renders/*.mp4
cd of-demo && npx -y openfilm@latest render         # -> of-demo/of-demo.mp4
```

## Edit in a browser from another machine on the LAN

Replace `HOST` with this machine's LAN address.

**HyperFrames** binds to the LAN when `HYPERFRAMES_PREVIEW_HOST` is set (already set for agent
sessions in `.claude/settings.json`):

```sh
cd hf-demo && HYPERFRAMES_PREVIEW_HOST=0.0.0.0 npx -y hyperframes@latest preview --background --no-open
# then browse to http://HOST:3002
npx -y hyperframes@latest preview --stop           # stop it
```

The preview has no login: anyone on the network can open and edit the project while it runs.

**OpenFilm** Studio only listens on 127.0.0.1 and only answers requests addressed to
127.0.0.1/localhost (ports 4747 and 4748), with no option to change that. Reach it by forwarding
both ports over SSH from the machine whose browser you want to use:

```sh
# on this machine
cd of-demo && OPENFILM_NO_BROWSER=1 npx -y openfilm@latest open .     # prints http://127.0.0.1:4747/open?key=...
# on the other machine
ssh -N -L 4747:127.0.0.1:4747 -L 4748:127.0.0.1:4748 USER@HOST
# then open the printed http://127.0.0.1:4747/open?key=... address there (Chrome or Edge)
```
