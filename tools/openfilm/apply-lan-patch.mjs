// Lets OpenFilm Studio serve the LAN. Stock Studio listens on 127.0.0.1, answers only requests addressed to
// 127.0.0.1/localhost, and names its two origins after them. With OPENFILM_LAN_HOST set (see bin/openfilm) the
// patched Studio listens on every interface and uses that host in both origins; unset, it behaves as stock.
// Each replacement must match exactly once, so a new OpenFilm version that moved the code fails here, loudly.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('./node_modules/openfilm/', import.meta.url));
const MARK = '/* lan-patch */';
const LAN = `(/^[a-z0-9.-]+$/i.test(process.env.OPENFILM_LAN_HOST ?? '') ? process.env.OPENFILM_LAN_HOST.toLowerCase() : null)`;

const edits = {
  'src/host.mjs': [
    ['export async function listenLocal(server, port = 0) {',
      `export async function listenLocal(server, port = 0, host = '127.0.0.1') { ${MARK}`],
    ["server.listen(port, '127.0.0.1', () => {", 'server.listen(port, host, () => {'],
  ],
  'studio/server/pages.mjs': [
    ["  const names = ['127.0.0.1', 'localhost', '[::1]'];",
      `  const lan = ${LAN}; ${MARK}\n  const names = ['127.0.0.1', 'localhost', '[::1]', ...(lan ? [lan] : [])];`],
    ['  await listenLocal(server, port);', `  await listenLocal(server, port, ${LAN} ? '0.0.0.0' : undefined);`],
    ['  const origin = `http://localhost:${', `  const origin = \`http://\${${LAN} ?? 'localhost'}:\${`],
  ],
  'studio/server/server.mjs': [
    ['  await listenLocal(editor, port);', `  await listenLocal(editor, port, ${LAN} ? '0.0.0.0' : undefined); ${MARK}`],
    ['  origin = `http://127.0.0.1:${address.port}`;', `  origin = \`http://\${${LAN} ?? '127.0.0.1'}:\${address.port}\`;`],
  ],
};

for (const [file, list] of Object.entries(edits)) {
  let text = readFileSync(root + file, 'utf8');
  if (text.includes(MARK)) { console.log(`lan-patch: ${file} already patched`); continue; }
  for (const [from, to] of list) {
    const count = text.split(from).length - 1;
    if (count !== 1) throw new Error(`lan-patch: expected exactly one match in ${file}, found ${count}, for:\n  ${from}\nOpenFilm changed; update tools/openfilm/apply-lan-patch.mjs.`);
    text = text.replace(from, () => to);
  }
  writeFileSync(root + file, text);
  console.log(`lan-patch: patched ${file}`);
}
