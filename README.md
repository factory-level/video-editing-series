# video

Workspace for making videos with coding agents, using two HTML-to-video tools:

- [OpenFilm](https://github.com/openfilm/openfilm) — `of-demo/` (a `film.html` plus pages exposing `window.film.frame(t)`)
- [HyperFrames](https://github.com/heygen-com/hyperframes) — `hf-demo/` (HTML compositions)

Agent skills for both live in `.claude/skills/` (pinned in `skills-lock.json`).
Requires Node 22+, ffmpeg and git. Renders and caches are git-ignored.

## Render

```sh
cd hf-demo && npx -y hyperframes@latest render      # -> hf-demo/renders/*.mp4
cd of-demo && ../bin/openfilm render                # -> of-demo/of-demo.mp4
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

**OpenFilm** Studio is loopback-only as shipped, so this repo runs a pinned copy with a small patch
(`tools/openfilm/apply-lan-patch.mjs`) through the `bin/openfilm` wrapper. The wrapper sets
`OPENFILM_LAN_HOST` to this machine's LAN address; with it set, Studio listens on all interfaces
(ports 4747 and 4748) and uses that address for its pages.

```sh
(cd tools/openfilm && npm install)      # once: installs openfilm and applies the patch
bin/openfilm open of-demo               # prints http://HOST:4747/open?key=...
```

Open the printed address from the other machine, in Chrome or Edge. The key in it is required and
changes each time Studio starts. Always use `bin/openfilm`, not `npx openfilm@latest`: a newer
unpatched CLI would replace the running Studio with a loopback-only one.

Limits:

- Plain HTTP on a LAN address is not a browser "secure context", so saving or importing custom panel
  layouts, some copy buttons and microphone recording do not work. To enable them on a client, add
  `http://HOST:4747,http://HOST:4748` under `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
- "Sign in to OpenFilm" does not complete from a remote browser; paste service API keys instead.
- The key travels unencrypted, and the ports are also reachable from this machine's Docker networks.
- To upgrade OpenFilm, bump the version in `tools/openfilm/package.json` and run `npm install`; the
  patch script stops with an error naming what moved if the new version changed the patched lines.
