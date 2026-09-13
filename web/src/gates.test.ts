import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";

const root = fileURLToPath(new URL("../..", import.meta.url).href);
const web = JSON.parse(readFileSync(join(root, "web/package.json"), "utf8"));

function runCoverageScript(gateCommand: string) {
  const config = join(mkdtempSync(join(tmpdir(), "gates-cover-web-")), "config.json");
  writeFileSync(
    config,
    JSON.stringify({
      verification: {
        gates: [
          { name: "typecheck", run: gateCommand },
          { name: "test", run: gateCommand },
        ],
      },
    }),
  );
  return spawnSync(process.execPath, [join(root, "scripts/gates-cover-web.mjs"), config], {
    encoding: "utf8",
  });
}

describe("scripts/gates-cover-web.mjs", () => {
  it("the gate-coverage script fails when the web project is absent from the gate commands", () => {
    // The pre-US-501 gate shape: guarded on a root package.json that does not exist, so it
    // runs, skips, and exits 0.
    const result = runCoverageScript(
      `node -e "const f=require('fs'),c=require('child_process');console.log('root-guarded gate ran');if(f.existsSync('package.json'))c.execSync('npm test --if-present',{stdio:'inherit'})"`,
    );

    expect(result.stdout).toContain("root-guarded gate ran");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("NOT RUN");
    expect(result.stderr).toContain("web typecheck");
    expect(result.stderr).toContain("web test");
  }, 30_000);

  it("passes once the gates show the web typecheck and web test executing", () => {
    const result = runCoverageScript(
      `node -e "console.log('> ${web.name}@${web.version} typecheck');console.log('> ${web.name}@${web.version} test');console.log('      Tests  1 passed (1)')"`,
    );

    expect(result.stderr).not.toContain("NOT RUN");
    expect(result.status).toBe(0);
  }, 30_000);
});

type Step = {
  id?: string;
  uses?: string;
  run?: string;
  if?: string;
  "working-directory"?: string;
};

describe(".github/workflows/uf-verify.yml", () => {
  it("every node step in the CI workflow guards on the web manifest and none guards on a root manifest", () => {
    const workflow = parse(
      readFileSync(join(root, ".github/workflows/uf-verify.yml"), "utf8"),
    );
    const steps: Step[] = workflow.jobs.verify.steps;

    const detect = steps.find((step) => step.id === "detect");
    const nodeManifests = [...(detect?.run ?? "").matchAll(/test -f (\S+)[^\n]*node=true/g)].map(
      (match) => match[1],
    );
    expect(nodeManifests).toEqual(["web/package.json"]);

    for (const step of steps) {
      expect(`${step.if ?? ""}\n${step.run ?? ""}`).not.toMatch(
        /(test -f |hashFiles\(')(\.\/)?package\.json/,
      );
    }

    const nodeSteps = steps.filter(
      (step) => step.uses?.startsWith("actions/setup-node") || /\bnpm\b/.test(step.run ?? ""),
    );
    expect(nodeSteps.map((step) => step.run)).toEqual(
      expect.arrayContaining(["npm run typecheck", "npm test"]),
    );
    for (const step of nodeSteps) {
      expect(step.if).toBe("steps.detect.outputs.node == 'true'");
      if (step.run) expect(step["working-directory"]).toBe("web");
    }
  });
});
