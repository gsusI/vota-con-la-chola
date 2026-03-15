import fs from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import XrayKindPageClient from "./XrayKindPageClient";
import { XRAY_KIND_META, XRAY_KIND_ORDER } from "../xrayKinds.mjs";

function resolveDataPath() {
  return path.resolve(process.cwd(), "public", "people", "data", "xray.json");
}

function loadXrayPayload() {
  const dataPath = resolveDataPath();
  if (!fs.existsSync(dataPath)) {
    return null;
  }
  const raw = fs.readFileSync(dataPath, "utf-8");
  return JSON.parse(raw);
}

export async function generateStaticParams() {
  return XRAY_KIND_ORDER.map((kind) => ({ kind }));
}

async function resolveRouteValue(value) {
  return (await value) || {};
}

export default async function XrayKindIndexPage({ params }) {
  const payload = loadXrayPayload();
  const resolvedParams = await resolveRouteValue(params);
  const kind = String(resolvedParams?.kind || "").toLowerCase();
  const meta = XRAY_KIND_META[kind];

  if (!meta || !payload || !payload.groups) {
    return notFound();
  }

  const groups = Array.isArray(payload.groups[kind]) ? payload.groups[kind] : [];
  return <XrayKindPageClient kind={kind} meta={meta} groups={groups} snapshotDate={payload?.meta?.snapshot_date || ""} />;
}
