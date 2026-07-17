// wave0_envelope.mjs — wrap wave0_packets.json entries through octoloop's OWN makePacket
// (artifacts.mjs) so file-loaded packets carry the exact provenance envelope + contract
// (change_only, limits, protected_deny) the kernel requires. Zero-drift by construction:
// the same function the CLI inline path uses. Usage:
//   node wave0_envelope.mjs <in.json> <out.json> [--first-to <probe.json>]
import { readFileSync, writeFileSync } from "node:fs";
import { makePacket } from "file:///D:/dev/99_tools/octoloop/src/octoloop/artifacts.mjs";

const [inPath, outPath] = process.argv.slice(2);
const raw = JSON.parse(readFileSync(inPath, "utf8"));
const rows = Array.isArray(raw) ? raw : [raw];
const out = rows.map((p) => makePacket({ id: p.id, prompt: p.prompt, laneKey: p.laneKey, files: p.files }));
writeFileSync(outPath, JSON.stringify(Array.isArray(raw) ? out : out[0], null, 1));
console.log("enveloped:", out.length, "->", outPath);
