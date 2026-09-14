import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const npmArgs = ["--prefix", "web", "run", "build"];
const command = process.platform === "win32" ? process.execPath : "npm";
if (process.platform === "win32") {
  npmArgs.unshift(
    join(dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"),
  );
}
const build = spawnSync(command, npmArgs, {
  cwd: root,
  stdio: "inherit",
});

if (build.status !== 0) {
  if (build.error) console.error(build.error.message);
  process.exit(build.status ?? 1);
}

const sentinel = ["US_505", "MIXED_BOARD_FIXTURE", "DEV_ONLY"].join("__");
const pending = [resolve(root, "web/dist")];
const files = [];
while (pending.length > 0) {
  const directory = pending.pop();
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) pending.push(path);
    else files.push(path);
  }
}

const leaked = files.filter((path) =>
  readFileSync(path).includes(Buffer.from(sentinel)),
);
if (leaked.length > 0) {
  console.error(`Development fixture leaked into: ${leaked.join(", ")}`);
  process.exit(1);
}

console.log("Production bundle contains no mixed-board fixture sentinel");
