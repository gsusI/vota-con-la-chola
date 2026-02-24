const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_codec_sync_state.js");
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

test("preset codec sync-state reporter passes strict mode when already synchronized", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-codec-sync-pass-"));
  const sourcePath = writeFile(tmpDir, "source.js", "const x = 1;\nconst y = 2;\n");
  const publishedPath = writeFile(tmpDir, "published.js", "const x = 1;\nconst y = 2;\n");

  const proc = runReporter(["--source", sourcePath, "--published", publishedPath, "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "sync_state_pass");
  assert.equal(out.summary.total_fail, 0);
  assert.equal(out.summary.failed_ids.length, 0);
  assert.equal(out.results.length, 1);
  assert.equal(out.results[0].ok, true);
  assert.equal(out.results[0].would_change, false);
  assert.equal(out.results[0].first_diff_line, 0);
  assert.equal(out.results[0].recommended_command, "");
});

test("preset codec sync-state reporter fails strict mode when published copy is stale", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-codec-sync-fail-"));
  const sourcePath = writeFile(tmpDir, "source.js", "const x = 1;\nconst y = 2;\n");
  const publishedPath = writeFile(tmpDir, "published.js", "const x = 1;\nconst y = 3;\n");

  const proc = runReporter(["--source", sourcePath, "--published", publishedPath, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "sync_state_fail");
  assert.equal(out.summary.total_fail, 1);
  assert.ok(out.summary.failed_ids.includes("sync_state:source_to_published"));
  assert.equal(out.results.length, 1);
  assert.equal(out.results[0].ok, false);
  assert.equal(out.results[0].would_change, true);
  assert.equal(out.results[0].first_diff_line, 2);
  assert.equal(out.results[0].first_diff_source_line, "const y = 2;");
  assert.equal(out.results[0].first_diff_published_line, "const y = 3;");
  assert.equal(out.results[0].source_sha256, out.results[0].published_after_sha256);
  assert.ok(out.results[0].source_sha256 !== out.results[0].published_before_sha256);
  assert.equal(out.results[0].recommended_command, "just explorer-gh-pages-build");
});
