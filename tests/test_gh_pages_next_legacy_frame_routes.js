const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const APP_ROOT = path.join(ROOT, "ui", "gh-pages-next", "app");
const PUBLIC_ROOT = path.join(ROOT, "ui", "gh-pages-next", "public");

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

function findLegacyFrameRouteFiles(dir = APP_ROOT) {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findLegacyFrameRouteFiles(entryPath));
      continue;
    }
    if (entry.name !== "page.js") {
      continue;
    }
    const source = fs.readFileSync(entryPath, "utf8");
    if (source.includes("LegacyFrame")) {
      files.push(entryPath);
    }
  }
  return files;
}

test("every LegacyFrame route points to an exported legacy asset", () => {
  const frameRouteFiles = findLegacyFrameRouteFiles();
  assert.ok(frameRouteFiles.length > 0, "expected at least one LegacyFrame route");

  for (const filePath of frameRouteFiles) {
    const relativeFile = path.relative(ROOT, filePath);
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
