const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const codec = require("../ui/citizen/preset_codec.js");

function loadPresetHashFixtureMatrix() {
  const p = path.join(__dirname, "fixtures", "citizen_preset_hash_matrix.json");
  const raw = fs.readFileSync(p, "utf8");
  return JSON.parse(raw);
}

function assertReadPresetResult(got, expected, id) {
  assert.equal(String(got.error_code || ""), String(expected.error_code || ""), `${id}: error_code mismatch`);
  assert.deepEqual(got.preset, expected.preset, `${id}: preset mismatch`);
  if (Object.prototype.hasOwnProperty.call(expected, "recovered_from")) {
    assert.equal(String(got.recovered_from || ""), String(expected.recovered_from || ""), `${id}: recovered_from mismatch`);
  }
  if (typeof expected.canonical_hash_prefix === "string") {
    assert.equal(
      String(got.canonical_hash || "").slice(0, expected.canonical_hash_prefix.length),
      expected.canonical_hash_prefix,
      `${id}: canonical_hash_prefix mismatch`
    );
  }
  if (typeof expected.canonical_hash === "string") {
    assert.equal(String(got.canonical_hash || ""), expected.canonical_hash, `${id}: canonical_hash mismatch`);
  }

  const errorContains = String(expected.error_contains || "").trim();
  if (errorContains) {
    assert.match(String(got.error || ""), new RegExp(errorContains, "i"), `${id}: error text mismatch`);
    return;
  }
  assert.equal(String(got.error || ""), String(expected.error || ""), `${id}: error mismatch`);
}

test("preset codec encodes and decodes with normalization", () => {
  const matrix = loadPresetHashFixtureMatrix();
  const cfg = matrix.config || { knownConcernIds: ["vivienda", "empleo", "sanidad"], maxConcerns: 6 };

  const payload = codec.encodePresetPayload(
    {
      method: "votes",
      pack_id: " Hogar y bolsillo ",
      concerns_ids: ["vivienda", "vivienda", "otro", "empleo"],
      concern_id: "sanidad",
    },
    cfg
  );

  const got = codec.decodePresetPayload(payload, cfg);
  assert.deepEqual(got, {
    view: "alignment",
    method: "votes",
    concern_pack: "hogar_y_bolsillo",
    concerns_ids: ["vivienda", "empleo"],
    concern: "sanidad",
  });
});

test("readPresetFromHash follows fixture matrix contract", () => {
  const matrix = loadPresetHashFixtureMatrix();
  assert.equal(matrix.schema_version, "v2");
  assert.ok(Array.isArray(matrix.hash_cases));
  assert.ok(matrix.hash_cases.length > 0);

  for (const c of matrix.hash_cases) {
    const got = codec.readPresetFromHash(c.hash, matrix.config || {});
    const expected = c.expect || {};
    const id = String(c.id || "unknown_case");
    assertReadPresetResult(got, expected, id);
  }
});

test("buildAlignmentPresetShareUrl follows fixture roundtrip contract", () => {
  const matrix = loadPresetHashFixtureMatrix();
  assert.ok(Array.isArray(matrix.share_cases));
  assert.ok(matrix.share_cases.length > 0);

  for (const c of matrix.share_cases) {
    const id = String(c.id || "unknown_share_case");
    const input = c.input || {};
    const expected = c.expect || {};

    const url = codec.buildAlignmentPresetShareUrl(
      input.options || {},
      String(input.href || ""),
      String(input.origin || ""),
      matrix.config || {}
    );

    const parsed = new URL(url);
    if (typeof expected.search === "string") {
      assert.equal(parsed.search, expected.search, `${id}: search mismatch`);
    }
    if (typeof expected.hash_prefix === "string") {
      assert.equal(parsed.hash.slice(0, expected.hash_prefix.length), expected.hash_prefix, `${id}: hash prefix mismatch`);
    }
    if (typeof expected.hash === "string") {
      assert.equal(parsed.hash, expected.hash, `${id}: hash mismatch`);
    }

    const decoded = codec.readPresetFromHash(parsed.hash, matrix.config || {});
    assertReadPresetResult(decoded, expected.decoded || {}, `${id}: decoded`);
  }
});

test("decodePresetPayload returns empty object when fields are unsupported", () => {
  const got = codec.decodePresetPayload("view=otra&method=foo&pack=%24%24&concerns=xx,yy&concern=", {
    knownConcernIds: ["vivienda"],
    maxConcerns: 6,
  });
  assert.deepEqual(got, {});
});
