#!/usr/bin/env node
// Control shim for stage 1: one process that owns the camera, the microphone and the teleprompter.
//   shim.mjs serve <session>     run the shim for a session (direct/launch does this)
//   shim.mjs mcp                 stdio MCP server that forwards to the running shim (for the ChatGPT tunnel)
//   shim.mjs <command> [args]    send one command to the running shim (direct/ctl does this)
// Commands: status | load <file> | roll | cut | keep | discard | prompter start|pause|faster|slower|reset
// Needs Node 22+ (built-in WebSocket), gphoto2 and pw-record.
import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { spawn, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const runFile = path.join(here, ".run.json");
// The teleprompter app watches this file and reloads the on-screen text when it changes.
const prompterScript =
  process.env.DIRECT_PROMPTER_SCRIPT ||
  path.join(os.homedir(), ".local/share/com.teleprompter.app/scripts/current.txt");
const micTarget = process.env.DIRECT_MIC || ""; // a PipeWire source name or id; empty = the default source
const OWN_FILES = new Set(["studio.wav", "script.md", "prompter.jsonl", "take.json"]);

const out = (cmd, args) => {
  try {
    return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return "";
  }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => new Date().toISOString();

// ---------- teleprompter (WebSocket remote control on an OS-assigned port) ----------
function prompterPort() {
  const pid = out("pgrep", ["-x", "teleprompter"]).split("\n")[0];
  if (!pid) return null;
  for (const line of out("ss", ["-H", "-ltnp"]).split("\n")) {
    if (!line.includes(`pid=${pid},`)) continue;
    const m = line.match(/\s\S+:(\d+)\s+\S+:\*/);
    if (m) return Number(m[1]);
  }
  return null;
}
function prompterSend(action) {
  const port = prompterPort();
  if (!port) return Promise.resolve(false);
  return new Promise((resolve) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`);
    // Teleprompter 0.3.0 only starts serving a connection when the next one arrives (its accept loop
    // blocks the thread holding the new connection's task), so follow ours with a throwaway connection.
    setTimeout(() => { const kick = net.connect(port, "127.0.0.1", () => kick.destroy()); kick.on("error", () => {}); }, 50);
    const done = (ok) => {
      clearTimeout(timer);
      try { ws.close(); } catch {}
      resolve(ok);
    };
    const timer = setTimeout(() => done(false), 2000);
    ws.onopen = () => {
      ws.send(JSON.stringify({ action }));
      setTimeout(() => done(true), 100);
    };
    ws.onerror = () => done(false);
  });
}

// ---------- camera (gphoto2, kept open as a shell so one connection spans the take) ----------
function cameraModel() {
  const lines = out("gphoto2", ["--auto-detect"]).split("\n").slice(2);
  const line = lines.find((l) => l.trim());
  return line ? line.replace(/\s+usb:\S*\s*$/, "").trim() : null;
}

// ---------- the shim ----------
function serve(session) {
  const dir = path.join(here, "takes", session);
  fs.mkdirSync(dir, { recursive: true });
  const S = { rolling: false, take: null, mic: null, cam: null, camErr: "", camOut: "", camReady: 0, clip: "none" };

  const takeDirs = () => fs.readdirSync(dir).filter((n) => /^\d{3}$/.test(n)).sort();
  const takeDir = (n) => path.join(dir, n);
  const readTake = (n) => JSON.parse(fs.readFileSync(path.join(takeDir(n), "take.json"), "utf8"));
  const writeTake = (n, patch) => {
    const file = path.join(takeDir(n), "take.json");
    const cur = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : {};
    fs.writeFileSync(file, JSON.stringify({ ...cur, ...patch }, null, 2) + "\n");
  };
  const logPrompter = (action, ok) => {
    if (S.rolling) fs.appendFileSync(path.join(takeDir(S.take), "prompter.jsonl"), JSON.stringify({ t: now(), action, ok }) + "\n");
  };
  const prompter = async (action) => {
    const ok = await prompterSend(action);
    logPrompter(action, ok);
    return ok;
  };

  // The desktop mounts the camera as a storage device as soon as it has a card, and then holds its USB
  // connection; release it before gphoto2 opens the camera.
  function freeCamera() {
    for (const m of out("gio", ["mount", "-l"]).matchAll(/-> (gphoto2:\/\/\S+)/g)) out("gio", ["mount", "-u", m[1]]);
  }
  // One gphoto2 shell stays connected for the whole session: the camera leaves USB control whenever a
  // connection closes. Recording to the card needs the capture target on the card and live view on.
  function camShell() {
    if (S.cam && S.cam.exitCode === null) return S.cam;
    freeCamera();
    S.camOut = "";
    const c = spawn("gphoto2", ["--shell", "--force-overwrite"], { stdio: ["pipe", "pipe", "pipe"] });
    const note = (d) => {
      S.camOut = (S.camOut + String(d)).slice(-40000);
      const lines = String(d).split("\n").filter((l) => /error \(|not set|could not/i.test(l));
      if (lines.length) S.camErr = lines.pop().replace(/\*+/g, "").trim();
    };
    c.stdout.on("data", note);
    c.stderr.on("data", note);
    c.on("error", (e) => { S.camErr = e.message; });
    c.on("exit", () => { if (S.cam === c) S.cam = null; });
    c.stdin.on("error", () => {});
    S.cam = c;
    S.camReady = Date.now() + 9000; // live view takes a few seconds to come up
    for (const line of ["wait-event 2s", "set-config capturetarget=1", "wait-event 2s", "set-config viewfinder=1", "wait-event 3s"]) c.stdin.write(line + "\n");
    return c;
  }
  const cam = (line) => camShell().stdin.write(line + "\n");
  const dropCam = () => { const c = S.cam; S.cam = null; if (c) { try { c.stdin.end("exit\n"); } catch {} setTimeout(() => c.kill(), 3000); } };
  // Wait until the shell prints something matching `re` after position `from`.
  async function camSaid(re, from, ms) {
    for (const end = Date.now() + ms; Date.now() < end; await sleep(150)) if (re.test(S.camOut.slice(from))) return true;
    return false;
  }
  async function camStart(d) {
    camShell();
    const wait = S.camReady - Date.now();
    if (wait > 0) await sleep(wait);
    const from = S.camOut.length;
    for (const line of [`lcd ${d}`, "set-config movierecordtarget=Card", "wait-event 2s", "get-config movierecordtarget"]) cam(line);
    if (await camSaid(/Current: Card/, from, 9000)) return null;
    const why = S.camErr || (/Current: /.test(S.camOut.slice(from)) ? "it refused to start; is the power switch on movie and a card inserted?" : "it did not answer");
    dropCam();
    return why;
  }

  function stopMic() {
    return new Promise((resolve) => {
      const m = S.mic;
      S.mic = null;
      if (!m || m.exitCode !== null) return resolve();
      const kill = setTimeout(() => m.kill("SIGKILL"), 3000);
      m.once("exit", () => { clearTimeout(kill); resolve(); });
      m.kill("SIGINT");
    });
  }

  // After `cut`, gphoto2 downloads the clip into the take folder; wait for it and name it camera.<ext>.
  async function collectClip(n) {
    const d = takeDir(n);
    const strangers = () => fs.readdirSync(d).filter((f) => !OWN_FILES.has(f) && !f.startsWith("camera.") && !f.startsWith("tmpfile")); // gphoto2 downloads to tmpfile*, then renames
    let file = null;
    for (let i = 0; i < 80 && !file; i++) { await sleep(500); file = strangers()[0] || null; }
    if (!file) { dropCam(); S.clip = "missing"; writeTake(n, { clip: null, clipError: S.camErr || "the camera handed over no clip" }); return; }
    let size = -1, still = 0;
    while (still < 4) {
      await sleep(500);
      const s = fs.statSync(path.join(d, file)).size;
      still = s === size ? still + 1 : 0;
      size = s;
    }
    const name = "camera" + path.extname(file).toLowerCase();
    fs.renameSync(path.join(d, file), path.join(d, name));
    writeTake(n, { clip: name, clipSource: file });
    S.clip = "ready";
  }

  const commands = {
    async status() {
      const model = cameraModel();
      const port = prompterPort();
      const takes = takeDirs();
      const last = takes.length ? readTake(takes[takes.length - 1]) : null;
      const data = {
        session, rolling: S.rolling, take: S.take, takes: takes.length,
        camera: model, cameraError: S.camErr || null, clip: S.clip,
        mic: micTarget || "default source", prompter: port ? `ws://127.0.0.1:${port}` : null,
        lastTake: last,
      };
      const text = [
        `session   ${session} (${takes.length} take${takes.length === 1 ? "" : "s"})`,
        `rolling   ${S.rolling ? "yes, take " + S.take : "no"}`,
        `camera    ${model || "not detected"}${S.camErr ? "  [" + S.camErr + "]" : ""}`,
        `clip      ${S.clip}`,
        `mic       ${data.mic}`,
        `prompter  ${port ? "running, port " + port : "not running"}`,
        last ? `last take ${last.take}: ${last.status}${last.clip ? ", " + last.clip : ""}` : "last take none",
      ].join("\n");
      return { ok: true, text, data };
    },

    async load(args, body) {
      let text = body.text;
      if (text == null) {
        if (!args[0]) return { ok: false, text: "load needs a script file" };
        const file = path.resolve(body.cwd || process.cwd(), args[0]);
        if (!fs.existsSync(file)) return { ok: false, text: `no such file: ${file}` };
        text = fs.readFileSync(file, "utf8");
      }
      fs.mkdirSync(path.dirname(prompterScript), { recursive: true });
      fs.writeFileSync(prompterScript, text);
      const words = text.split(/\s+/).filter(Boolean).length;
      return { ok: true, text: `script loaded into the teleprompter (${words} words)` };
    },

    async roll() {
      if (S.rolling) return { ok: false, text: `already rolling take ${S.take}` };
      if (S.clip === "downloading") return { ok: false, text: "still pulling the last clip off the camera; try again in a moment" };
      const n = String(takeDirs().length + 1).padStart(3, "0");
      const d = takeDir(n);
      fs.mkdirSync(d);
      if (fs.existsSync(prompterScript)) fs.copyFileSync(prompterScript, path.join(d, "script.md"));
      S.take = n; S.rolling = true; S.camErr = ""; S.clip = "none";

      S.mic = spawn("pw-record", [...(micTarget ? ["--target", micTarget] : []), path.join(d, "studio.wav")], { stdio: "ignore" });
      const started = now();
      const model = cameraModel();
      const camWhy = model ? await camStart(d) : "not detected";
      const prompting = await prompter("play");
      writeTake(n, { session, take: n, started, status: "rolling", camera: camWhy ? null : model, cameraError: camWhy, mic: micTarget || "default", prompter: prompting });
      const missing = [camWhy && `CAMERA IS NOT RECORDING: ${camWhy}`, !prompting && "teleprompter not running"].filter(Boolean);
      return { ok: true, text: `rolling take ${n}` + (missing.length ? ` (${missing.join("; ")})` : ", camera recording") };
    },

    async cut() {
      if (!S.rolling) return { ok: false, text: "not rolling" };
      const n = S.take;
      const hadCamera = readTake(n).camera;
      if (hadCamera) {
        cam("set-config movierecordtarget=None");
        cam("wait-event-and-download FILEADDED"); // returns as soon as the clip is downloaded
      }
      await stopMic();
      await prompter("pause");
      S.rolling = false;
      const ended = now();
      const wav = path.join(takeDir(n), "studio.wav");
      const micBytes = fs.existsSync(wav) ? fs.statSync(wav).size : 0;
      const seconds = Math.round((Date.parse(ended) - Date.parse(readTake(n).started)) / 100) / 10;
      writeTake(n, { ended, seconds, status: "cut", studio: micBytes > 44 ? "studio.wav" : null });
      if (hadCamera) { S.clip = "downloading"; collectClip(n).catch((e) => { S.clip = "missing"; S.camErr = e.message; }); }
      const notes = [micBytes > 44 ? null : "no microphone audio was recorded", hadCamera ? "pulling the clip off the camera" : "no camera clip"].filter(Boolean);
      return { ok: true, text: `cut take ${n}, ${seconds}s (${notes.join("; ")})` };
    },

    async keep() { return mark("kept"); },
    async discard() { return mark("discarded"); },

    async prompter(args) {
      const action = { start: "play", play: "play", pause: "pause", faster: "faster", slower: "slower", reset: "reset" }[args[0]];
      if (!action) return { ok: false, text: "prompter takes: start | pause | faster | slower | reset" };
      const ok = await prompter(action);
      return { ok, text: ok ? `prompter ${args[0]}` : "the teleprompter is not running" };
    },
  };
  function mark(status) {
    if (S.rolling) return { ok: false, text: "still rolling; cut first" };
    const takes = takeDirs();
    if (!takes.length) return { ok: false, text: "no takes yet" };
    const n = takes[takes.length - 1];
    writeTake(n, { status });
    return { ok: true, text: `take ${n} ${status}` };
  }

  const server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", async () => {
      let result;
      try {
        const body = JSON.parse(raw || "{}");
        const fn = commands[body.cmd];
        result = fn ? await fn(body.args || [], body) : { ok: false, text: `unknown command: ${body.cmd}` };
      } catch (e) {
        result = { ok: false, text: `shim error: ${e.message}` };
      }
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(result));
    });
  });
  server.listen(0, "127.0.0.1", () => {
    fs.writeFileSync(runFile, JSON.stringify({ pid: process.pid, port: server.address().port, session }) + "\n");
    console.log(`shim for session ${session} on 127.0.0.1:${server.address().port}`);
    if (cameraModel()) camShell(); // connect now, so the first roll does not wait for live view
  });

  const shutdown = async () => {
    if (S.rolling) await commands.cut();
    while (S.clip === "downloading") await sleep(500);
    if (S.cam) { try { S.cam.stdin.end("exit\n"); } catch {} }
    try { fs.unlinkSync(runFile); } catch {}
    process.exit(0);
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}

// ---------- client ----------
async function send(cmd, args = [], extra = {}) {
  let run;
  try { run = JSON.parse(fs.readFileSync(runFile, "utf8")); } catch {
    return { ok: false, text: "no session is running; start one with: direct/launch <session>" };
  }
  try {
    const res = await fetch(`http://127.0.0.1:${run.port}/`, { method: "POST", body: JSON.stringify({ cmd, args, cwd: process.cwd(), ...extra }) });
    return await res.json();
  } catch {
    return { ok: false, text: "the shim is not answering; restart it with: direct/launch --stop, then direct/launch <session>" };
  }
}

// ---------- MCP (stdio, newline-delimited JSON-RPC) ----------
const noArgs = { type: "object", properties: {} };
const TOOLS = [
  { name: "status", description: "Report the session: whether a take is rolling, camera, microphone, teleprompter, last take.", inputSchema: noArgs },
  { name: "roll", description: "Start a take: camera, microphone and teleprompter start together.", inputSchema: noArgs },
  { name: "cut", description: "End the take: stop camera, microphone and teleprompter and close the take folder.", inputSchema: noArgs },
  { name: "keep", description: "Mark the last take as kept.", inputSchema: noArgs },
  { name: "discard", description: "Mark the last take as discarded.", inputSchema: noArgs },
  { name: "load_script", description: "Put a script on the teleprompter, replacing what is there.", inputSchema: { type: "object", properties: { text: { type: "string", description: "The full script text." } }, required: ["text"] } },
  { name: "prompter", description: "Control the teleprompter.", inputSchema: { type: "object", properties: { action: { type: "string", enum: ["start", "pause", "faster", "slower", "reset"] } }, required: ["action"] } },
];
// Stitching: DIRECT_MCP_STITCH names other stdio MCP servers (commands separated by ";"). Their tools
// are offered beside the shim's own, so ChatGPT sees one suite behind one tunnel.
function stitch(command) {
  const child = spawn(command, { shell: true, stdio: ["pipe", "pipe", "inherit"] });
  const pending = new Map();
  let next = 0;
  child.stdin.on("error", () => {});
  readline.createInterface({ input: child.stdout }).on("line", (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    const done = pending.get(msg.id);
    if (done) { pending.delete(msg.id); done(msg); }
  });
  const call = (method, params) => new Promise((resolve) => {
    const id = ++next;
    pending.set(id, resolve);
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
    setTimeout(() => { if (pending.delete(id)) resolve({ error: { code: -32000, message: `${command} did not answer` } }); }, 15000);
  });
  const tools = (async () => {
    await call("initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "direct-shim", version: "0.1.0" } });
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
    return (await call("tools/list", {})).result?.tools || [];
  })();
  return { call, tools, child };
}
function mcp() {
  const send_ = (obj) => process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...obj }) + "\n");
  const reply = (id, result) => send_({ id, result });
  const others = (process.env.DIRECT_MCP_STITCH || "").split(";").map((c) => c.trim()).filter(Boolean).map(stitch);
  const own = new Set(TOOLS.map((t) => t.name));
  const input = readline.createInterface({ input: process.stdin });
  input.on("close", () => { for (const o of others) o.child.kill(); process.exit(0); });
  input.on("line", async (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.id === undefined) return; // a notification
    if (msg.method === "initialize") {
      reply(msg.id, { protocolVersion: msg.params?.protocolVersion || "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "direct-shim", version: "0.1.0" } });
    } else if (msg.method === "ping") {
      reply(msg.id, {});
    } else if (msg.method === "tools/list") {
      const extra = (await Promise.all(others.map((o) => o.tools))).flat().filter((t) => !own.has(t.name));
      reply(msg.id, { tools: [...TOOLS, ...extra] });
    } else if (msg.method === "tools/call") {
      const { name, arguments: a = {} } = msg.params || {};
      if (!own.has(name)) {
        for (const o of others) {
          if (!(await o.tools).some((t) => t.name === name)) continue;
          const r = await o.call("tools/call", msg.params);
          return send_(r.error ? { id: msg.id, error: r.error } : { id: msg.id, result: r.result });
        }
        return reply(msg.id, { content: [{ type: "text", text: `unknown tool: ${name}` }], isError: true });
      }
      const r = name === "load_script" ? await send("load", [], { text: a.text })
        : name === "prompter" ? await send("prompter", [a.action])
        : await send(name);
      reply(msg.id, { content: [{ type: "text", text: r.text }], isError: !r.ok });
    } else {
      send_({ id: msg.id, error: { code: -32601, message: `method not found: ${msg.method}` } });
    }
  });
}

// ---------- entry ----------
const [mode, ...rest] = process.argv.slice(2);
if (mode === "serve") {
  if (!/^[A-Za-z0-9._-]+$/.test(rest[0] || "")) { console.error("usage: shim.mjs serve <session>"); process.exit(2); }
  serve(rest[0]);
} else if (mode === "mcp") {
  mcp();
} else if (!mode) {
  console.error("usage: direct/ctl status | load <file> | roll | cut | keep | discard | prompter start|pause|faster|slower|reset");
  process.exit(2);
} else {
  const r = await send(mode, rest);
  console.log(r.text);
  process.exit(r.ok ? 0 : 1);
}
