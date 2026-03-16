const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const PUBLIC_ROOT = path.join(ROOT, "ui", "gh-pages-next", "public");

const FRAME_ROUTE_FILES = [
  "ui/gh-pages-next/app/citizen/page.js",
  "ui/gh-pages-next/app/citizen/leaderboards/page.js",
  "ui/gh-pages-next/app/explorer/page.js",
  "ui/gh-pages-next/app/explorer-politico/page.js",
  "ui/gh-pages-next/app/explorer-sources/page.js",
  "ui/gh-pages-next/app/explorer-temas/page.js",
  "ui/gh-pages-next/app/explorer-votaciones/page.js",
  "ui/gh-pages-next/app/graph/page.js",
  "ui/gh-pages-next/app/methods/explorer/page.js",
  "ui/gh-pages-next/app/methods/graph/page.js",
];

function resolveLegacyPathTarget(legacyPath) {
  const relativePath = legacyPath.replace(/^\//u, "");
  const directPath = path.join(PUBLIC_ROOT, relativePath);
  if (fs.existsSync(directPath)) {
    return directPath;
  }
  if (legacyPath.endsWith("/")) {
    const indexPath = path.join(PUBLIC_ROOT, relativePath, "index.html");
    if (fs.existsSync(indexPath)) {
      return indexPath;
    }
  }
  return null;
}

test("every LegacyFrame route points to an exported legacy asset", () => {
  for (const relativeFile of FRAME_ROUTE_FILES) {
    const filePath = path.join(ROOT, relativeFile);
    const source = fs.readFileSync(filePath, "utf8");
    const match = source.match(/legacyPath="([^"]+)"/u);

    assert.ok(match, `missing legacyPath in ${relativeFile}`);
    const legacyPath = match[1];
    const resolvedTarget = resolveLegacyPathTarget(legacyPath);

    assert.ok(
      resolvedTarget,
      `legacyPath ${legacyPath} from ${relativeFile} does not exist under public/legacy`,
    );
  }
});
