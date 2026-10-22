import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ARTICLES, VIZ_SLUGS, articleSeo } from "./articleSeo.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const load = (slug) => JSON.parse(fs.readFileSync(path.resolve(here, "../../public/visualizaciones/data", `${slug}.json`), "utf-8"));
const BRAND = " | Vota Con La Chola";

for (const slug of VIZ_SLUGS) {
  test(`${slug}: search copy fits snippets and every figure resolved`, () => {
    const seo = articleSeo(slug, load(slug));
    assert.ok((seo.title + BRAND).length <= 60, `title too long: ${seo.title}`);
    assert.ok(seo.description.length <= 155, `description ${seo.description.length} chars`);
    assert.ok(seo.headline.length <= 110, `headline ${seo.headline.length} chars`);
    assert.ok(/\d/.test(seo.title) && /\d/.test(seo.headline), "title and headline carry a number");
    assert.ok(seo.faqs.length >= 4 && seo.faqs.length <= 6);
    // The share card font has no arrows: a missing glyph triggers a network font fetch at build time.
    assert.ok(!/[→←↑↓]/.test(JSON.stringify(seo.card)), "arrow in card copy");
    const text = JSON.stringify(seo);
    for (const bad of ["undefined", "NaN", "Infinity", "null %"]) assert.ok(!text.includes(bad), `${bad} in copy`);
    for (const word of ["gracias a", "por culpa de"]) assert.ok(!text.toLowerCase().includes(word), `causal wording: ${word}`);
    assert.ok(seo.sources.length > 0 && seo.sources.every((s) => /^https:\/\//.test(s.url)));
    assert.ok(ARTICLES[slug].related.every((other) => VIZ_SLUGS.includes(other) && other !== slug));
    assert.match(seo.dateModified, /^\d{4}-\d{2}-\d{2}T/);
  });
}
