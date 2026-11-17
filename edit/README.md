# edit — stage 2 (server)

Finish a raw timeline into a video: green screen removal, b-roll, titles, captions, effects, then
render and upload. Runs on the server; you review in a browser from another machine on the LAN. See
the [top-level README](../README.md) for the whole pipeline.

Working today: both editors, on the LAN, with a sample project each; OpenRig is installed. Not built
yet: receiving a handoff from stage 1, the video agent that makes the first edit, and upload.

## Setup

Requires Node 22+, ffmpeg and git.

```sh
(cd edit/tools/openfilm && npm install)     # installs OpenFilm 0.3.2 and applies the LAN patch
```

HyperFrames runs through `npx` and needs no install.

**Content root.** Media lives outside the repository. Create a git-ignored `PATH.md` at the
repository root naming where, on a disk with room for video:

```
CONTENT_ROOT=/path/to/content
```

Each video's media goes in `$CONTENT_ROOT/<video-slug>/`.

**OpenRig.** The agent team that makes the first edit runs under
[OpenRig](https://github.com/mvschwarz/openrig) (needs tmux and a signed-in Claude Code):

```sh
npm install -g @openrig/cli              # add --prefix ~/.local if the global prefix needs root
rig setup --providers claude --no-herdr  # writes an OpenRig block to ~/.tmux.conf
rig daemon start --no-kernel             # the daemon only; no agents start until a team is launched
```

The team for this pipeline is not defined yet, so nothing runs after an upload today.

## Open a project

```sh
bin/edit                    # list projects, and which HyperFrames previews are running
bin/edit of-demo            # OpenFilm:    prints http://HOST:4747/open?key=...
bin/edit hf-demo            # HyperFrames: prints http://HOST:3002/#project/hf-demo
bin/edit hf-demo --stop     # stop that HyperFrames preview
bin/edit --stop-openfilm    # stop OpenFilm Studio (it serves every OpenFilm project)
```

A folder in `projects/` with a `film.html` is an OpenFilm project; one with a `hyperframes.json` is
a HyperFrames project. Open the printed address in Chrome or Edge on the other machine. Neither
editor restarts by itself after a reboot.

## Render

```sh
cd edit/projects/of-demo && ../../bin/openfilm render          # -> of-demo.mp4
cd edit/projects/hf-demo && npx -y hyperframes@0.9.58 render   # -> renders/*.mp4
```

Renders and caches are git-ignored.

## How the LAN access works

**HyperFrames** binds to the LAN when `HYPERFRAMES_PREVIEW_HOST=0.0.0.0` is set, which `launch`
does. The preview has no login: anyone on the network can open and edit the project while it runs.

**OpenFilm** Studio is loopback-only as shipped, so this repo runs a pinned copy with a small patch
(`tools/openfilm/apply-lan-patch.mjs`) through the `bin/openfilm` wrapper. With `OPENFILM_LAN_HOST`
set, which the wrapper and `launch` do, Studio listens on all interfaces (ports 4747 and 4748) and
uses the LAN address for its pages. The key in the printed address is required and changes each
time Studio starts.

Always use `bin/openfilm`, not `npx openfilm@latest`: a newer unpatched CLI would replace the
running Studio with a loopback-only one.

Limits of OpenFilm over the LAN:

- Plain HTTP on a LAN address is not a browser "secure context", so saving or importing custom
  panel layouts, some copy buttons and microphone recording do not work. To enable them on a
  client, add `http://HOST:4747,http://HOST:4748` under
  `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
- "Sign in to OpenFilm" does not complete from a remote browser; paste service API keys instead.
- The key travels unencrypted, and the ports are also reachable from this machine's Docker networks.
- To upgrade OpenFilm, bump the version in `tools/openfilm/package.json` and run `npm install`; the
  patch script stops with an error naming what moved if the new version changed the patched lines.
