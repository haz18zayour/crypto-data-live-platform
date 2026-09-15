// US-501: run every gate declared in .uf/config.json and fail unless the web typecheck and
// the web test really ran. A gate that skips exits 0 exactly like a gate that passes, which is
// how the web suite went ungated from US-009 until PRD-005.
//
//   node scripts/gates-cover-web.mjs [path/to/config.json]
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = resolve(process.argv[2] ?? resolve(root, ".uf/config.json"));
const { verification } = JSON.parse(readFileSync(configPath, "utf8"));
const web = JSON.parse(readFileSync(resolve(root, "web/package.json"), "utf8"));

let output = "";
let failed = false;
for (const gate of verification.gates) {
  console.log(`\n=== gate: ${gate.name} ===`);
  const result = spawnSync(gate.run, {
    cwd: root,
    shell: true,
    encoding: "utf8",
    maxBuffer: 256 * 1024 * 1024,
  });
  process.stdout.write(result.stdout ?? "");
  process.stderr.write(result.stderr ?? "");
  output += `${result.stdout ?? ""}\n${result.stderr ?? ""}\n`;
  if (result.status !== 0) {
    console.error(`gate ${gate.name} exited ${result.status ?? result.error}`);
    failed = true;
  }
}

// npm prints `> <name>@<version> <script>` before running a script; vitest prints its
// `Tests  N passed` summary only after tests actually executed.
const lines = output.replace(/\x1b\[[0-9;]*m/g, "").split(/\r?\n/).map((line) => line.trim());
const ran = (script) => lines.includes(`> ${web.name}@${web.version} ${script}`);
const missing = [];
if (!ran("typecheck")) missing.push("web typecheck");
if (!ran("test") || !lines.some((line) => /^Tests\s+[1-9]\d* passed/.test(line))) {
  missing.push("web test");
}

if (missing.length > 0) {
  console.error(`\nNOT RUN by any gate in ${configPath}: ${missing.join(", ")}`);
  failed = true;
} else {
  console.log(`\nweb typecheck and web test both ran inside the gates of ${configPath}`);
}
process.exit(failed ? 1 : 0);
