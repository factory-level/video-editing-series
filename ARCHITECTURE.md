# How the pieces connect

The wiring between the voice director, the laptop and the server. The overview diagram is in the
[README](README.md#how-it-fits-together); this file covers each link, and says which are built.

| Link | State |
| --- | --- |
| Shim to camera, microphone, teleprompter | Built and tested |
| MCP server (`direct/ctl mcp`) to shim | Built and tested locally |
| ChatGPT voice to MCP server, through the OpenAI tunnel | Profile written, not tried |
| Take upload to the server | Not built |
| Callback to OpenRig on the server | Not built; commands below are checked against `rig` 0.6.10 help only |
| `video:first-edit`: waveform alignment, jump cuts, raw timeline | Not built; the command is a stub |

## One take, end to end

```mermaid
sequenceDiagram
    actor You
    participant Voice as ChatGPT voice
    participant Tunnel as OpenAI tunnel
    participant Shim as Shim (laptop)
    participant Gear as Camera + mic + prompter
    participant Rig as OpenRig (server)
    participant Editors as First-edit agents

    You->>Voice: "roll"
    Voice->>Tunnel: tools/call roll
    Tunnel->>Shim: roll
    Shim->>Gear: start all three
    Shim-->>Voice: rolling take 004, camera recording
    You->>Voice: "cut, keep it"
    Voice->>Shim: cut, then keep
    Shim->>Gear: stop; pull clip off the card
    Note over Shim: take folder complete
    Shim->>Rig: rsync take folder, verify checksums
    Shim->>Rig: callback, a queue item for this take
    Rig->>Editors: queue item: cut take 004
    Editors->>Editors: align waveforms, pick kept ranges
    Editors->>Rig: append take to the raw timeline
    Note over You,Editors: you are already filming the next take
```

## 1. ChatGPT voice to the laptop: MCP over an OpenAI tunnel

The laptop has no public address. OpenAI's `tunnel-client` makes one outbound connection to the
OpenAI control plane and runs a local MCP server on its behalf; ChatGPT reaches that server as a
connector.

```
ChatGPT Advanced Voice
   |  connector tool call (roll, cut, status, ...)
OpenAI control plane                 api.openai.com, tunnel tunnel_...
   |  outbound tunnel, opened from the laptop
tunnel-client run --profile direct   ~/.config/tunnel-client/direct.yaml
   |  stdio, newline-delimited JSON-RPC (MCP)
direct/ctl mcp                       direct/shim.mjs, MCP mode
   |  HTTP POST on 127.0.0.1, port from direct/.run.json
control shim                         direct/shim.mjs serve <session>
```

- **Three processes, on purpose.** The shim is long-lived because it holds the camera connection for
  the session. The MCP server is a thin forwarder that tunnel-client starts and stops as it likes.
  `direct/ctl <command>` uses the same HTTP route, so the terminal and ChatGPT drive one session.
- **Tools offered:** `status`, `roll`, `cut`, `keep`, `discard`, `load_script {text}`,
  `prompter {action}`. Each returns one line of text for the director to say or act on. `roll`
  answers `camera recording` only after the camera confirms it.
- **Profile:** [`direct/tunnel.example.yaml`](direct/tunnel.example.yaml). The tunnel id comes from
  https://platform.openai.com/settings/organization/tunnels; the key is read from
  `CONTROL_PLANE_API_KEY` and never written into the profile.
- **Order of start:** `direct/launch <session>` first, then the tunnel. With no session running,
  every tool answers "no session is running".
- **Not tried:** that Advanced Voice calls connector tools hands-free, and how long a call takes
  end to end. The teleprompter's own MCP server is tunnelled the same way today.

## 2. Laptop to server: upload, then the OpenRig callback

Two steps per kept take, in this order, so the server never starts on half a take.

**Upload.** `rsync --checksum` of `direct/takes/<session>/<take>/` to the server's content folder, then a second
dry run that must report nothing left to send. The take is marked uploaded in `take.json`.

**Callback.** One queue item on the server's OpenRig, created from the laptop:

```sh
# once, on the laptop: register the server's OpenRig daemon
rig host pair http://<server>:<port>          # one approval on the server; or
rig host add --id edit-server --transport http --url http://<server>:<port> --bearer-env OPENRIG_SERVER_TOKEN

# per take: the callback
rig queue create --host edit-server \
  --destination <first-edit seat>@<rig> \
  --id <session>-<take> \
  --summary "First edit <session> take <take>" \
  --tags video,first-edit \
  --body-file take-callback.json
```

- `--host` sends the write to the registered remote daemon over HTTP; nothing is typed into an
  agent's terminal.
- `--id <session>-<take>` is the retry identity. If the laptop cannot tell whether the callback
  arrived, it sends the same id again and the server does not get a second job.
- The body carries what the editors need: session, take number, the take's path on the server, the
  script, and whether the take is kept.
- `rig queue create` is the one queue command that accepts `--host`; `rig stream emit` does not.

Takes land in `<content root>/<video-slug>/` on the server; the content root is in that machine's
git-ignored `PATH.md`. Still to decide: which rig and seat receive the item, and the server's
address and token.

## 3. On the server: `video:first-edit` aligns, cuts, appends

Waveform alignment and jump cuts are the `video:first-edit` command (`first-edit/launch`). The
first-edit agents run it for one queue item, which is one take.

**Waveform alignment.** The camera clip carries scratch audio from the camera's own microphone;
`studio.wav` is the good recording of the same performance. They start at slightly different
moments (about a quarter of a second apart in tests, up to 9 seconds on the first take of a session).

1. Extract both as mono at a low sample rate: `ffmpeg -i camera.mp4 -vn -ac 1 -ar 8000 scratch.wav`,
   and the same for `studio.wav`.
2. Cross-correlate the two waveforms; the peak gives the offset between them.
3. Check the peak is clear, and that the offset is the same near the start and the end of the take,
   which rules out drift. A weak or moving peak fails the take for a person to look at.
4. From here on the picture comes from `camera.mp4`, the sound from `studio.wav` shifted by the
   offset. The scratch audio is not used again.

**Jump cuts.** Decide which stretches of the take stay.

1. Transcribe `studio.wav` with word timings.
2. Match the words to `script.md`. Where a line was read more than once, keep the last complete
   reading.
3. Drop silences, false starts and repeats. Each kept stretch becomes a range, start to end.
4. Leave a little padding on each side of a range, or none for a clean jump cut, so a person can
   still trim. How much is open decision 8 in the README.

**Append.** Add the take's ranges to the session's raw timeline, a HyperFrames composition: picture
and studio sound for each range, in script order, after the takes already there. The timeline trails
the filming by one take's upload and cut. Earlier ranges are not rewritten, so trims a person has
already made are kept; how the composition is laid out to guarantee that is open decision 5.

Nothing creative happens here. Effects, keying, b-roll, titles and music belong to stage 2.
