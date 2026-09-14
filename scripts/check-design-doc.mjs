import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const doc = readFileSync(resolve(root, "project-documents/20_Design_System.md"), "utf8");
const cellFace = readFileSync(resolve(root, "web/src/CellFace.tsx"), "utf8");

const failures = [];

// The old rule, taken literally, made hue the only status channel: a WCAG 1.4.1 Level A failure.
if (/only thing allowed to be\s+chromatic/i.test(doc)) {
  failures.push("still says status is the only thing allowed to be chromatic");
}
if (/colour carries meaning and nothing else\b/i.test(doc)) {
  failures.push('still carries the "colour carries meaning and nothing else" rule');
}
if (!/never the sole\s+status channel/i.test(doc) || !/WCAG 1\.4\.1/.test(doc)) {
  failures.push("does not state that colour is never the sole status channel (WCAG 1.4.1)");
}
if (!/glyph-and-word rule/i.test(doc)) {
  failures.push("does not record the glyph-and-word rule");
}

// The document must describe the faces the page actually renders, not a remembered version.
const faces = [...cellFace.matchAll(/glyph: "([^"]+)",\s*word: "([^"]+)"/g)];
if (faces.length < 5) {
  failures.push(`found ${faces.length} glyph/word faces in CellFace.tsx, expected at least 5`);
}
for (const [, glyph, word] of faces) {
  if (!doc.includes(`| ${glyph} | ${word} |`)) {
    failures.push(`glyph-and-word table is missing the rendered face "${glyph} ${word}"`);
  }
}

if (!doc.includes("PRD-005")) failures.push("does not name PRD-005");
if (doc.includes("PRD-008")) failures.push("still attributes the design work to PRD-008");

if (failures.length > 0) {
  console.error(`20_Design_System.md contradicts the design:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log(
  `20_Design_System.md: glyph-and-word rule recorded for ${faces.length} faces, colour is not the sole channel, PRD-005 named`,
);
