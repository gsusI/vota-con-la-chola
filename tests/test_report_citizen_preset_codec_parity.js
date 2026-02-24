const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_codec_parity.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function writeFile(dir, name, content) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, content, "utf8");
  return p;
}

test("preset codec parity reporter passes strict mode on identical files", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-codec-parity-pass-"));
  const src = writeFile(tmpDir, "src.js", "const a = 1;\nconst b = 2;\n");
  const pub = writeFile(tmpDir, "pub.js", "const a = 1;\nconst b = 2;\n");

  const proc = runReporter(["--source", src, "--published", pub, "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "identical_files");
  assert.equal(out.summary.total_fail, 0);
  assert.equal(out.summary.failed_ids.length, 0);
  assert.equal(Array.isArray(out.results), true);
  assert.equal(out.results.length, 1);
  assert.equal(out.results[0].ok, true);
  assert.equal(out.results[0].first_diff_line, 0);
});

test("preset codec parity reporter fails strict mode on mismatch and exposes first diff", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-codec-parity-fail-"));
  const src = writeFile(tmpDir, "src.js", "const a = 1;\nconst b = 2;\n");
  const pub = writeFile(tmpDir, "pub.js", "const a = 1;\nconst b = 3;\n");

  const proc = runReporter(["--source", src, "--published", pub, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "mismatch_files");
  assert.equal(out.summary.total_fail, 1);
  assert.ok(Array.isArray(out.summary.failed_ids));
  assert.ok(out.summary.failed_ids.includes("parity:source_vs_published"));
  assert.equal(out.results[0].ok, false);
  assert.equal(out.results[0].first_diff_line, 2);
  assert.equal(out.results[0].first_diff_source_line, "const b = 2;");
  assert.equal(out.results[0].first_diff_published_line, "const b = 3;");
});
