import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";

const require = createRequire(import.meta.url);
const cli = resolve(dirname(require.resolve("playwright/package.json")), "cli.js");
const required = ["chromium-", "chromium_headless_shell-"];

function runPlaywright(args) {
  return spawnSync(process.execPath, [cli, ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

const listed = runPlaywright(["install", "--list"]);
const installed = listed.status === 0 && required.every((name) => listed.stdout.includes(name));

if (installed) {
  process.stdout.write("Playwright browsers already installed.\n");
  process.exit(0);
}

const installedNow = spawnSync(
  process.execPath,
  [cli, "install", "chromium", "chromium-headless-shell"],
  { stdio: "inherit" },
);
process.exit(installedNow.status ?? 1);
