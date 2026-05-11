import fs from "node:fs";
import path from "node:path";

export function readPublicJson(relativePath, fallback = {}) {
  const cleanPath = String(relativePath || "")
    .split("/")
    .filter(Boolean);
  const filePath = path.resolve(process.cwd(), "public", ...cleanPath);
  if (!fs.existsSync(filePath)) {
    return fallback;
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

export function explorerRows(snapshot, tableName) {
  const rows = snapshot?.tables?.[tableName]?.rows;
  return Array.isArray(rows) ? rows : [];
}

export function explorerTableMeta(snapshot, tableName) {
  return snapshot?.tables?.[tableName]?.meta || {};
}

export function rowPreviewValue(row, key) {
  return row?.preview_display?.[key] ?? row?.preview?.[key] ?? "";
}

export function rowIdentityValue(row) {
  const identity = row?.identity || {};
  const firstKey = Object.keys(identity)[0];
  return firstKey ? identity[firstKey] : "";
}

export function rowsAsObjects(columns, rows) {
  const safeColumns = Array.isArray(columns) ? columns : [];
  const safeRows = Array.isArray(rows) ? rows : [];
  return safeRows.map((row) => {
    const item = {};
    safeColumns.forEach((column, index) => {
      item[column] = Array.isArray(row) ? row[index] : undefined;
    });
    return item;
  });
}

export function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "0";
  }
  return Math.trunc(parsed).toLocaleString("es-ES");
}

export function formatPct(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "0%";
  }
  return `${Math.round(parsed * 100).toLocaleString("es-ES")}%`;
}

export function formatDate(value) {
  const raw = String(value || "").trim();
  return raw || "sin fecha";
}

export function formatMethod(value) {
  const key = String(value || "").toLowerCase().trim();
  if (key === "votes") {
    return "Votos";
  }
  if (key === "declared") {
    return "Declaraciones";
  }
  if (key === "combined") {
    return "Combinado";
  }
  if (key === "all") {
    return "Todos";
  }
  return String(value || "").trim() || "sin método";
}

export function compactText(value, limit = 150) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(0, limit - 1)).trim()}...`;
}

export function tallyBy(rows, key) {
  const counts = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const value = String(row?.[key] || "sin dato");
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function sourceStatusClass(value) {
  const status = String(value || "").toLowerCase();
  if (status === "ok" || status === "done" || status === "match" || status === "available") {
    return "staticRouteStatusPill--ok";
  }
  if (status === "partial" || status === "degraded" || status === "running" || status === "stale") {
    return "staticRouteStatusPill--warn";
  }
  if (status === "missing" || status === "error" || status === "blocked") {
    return "staticRouteStatusPill--bad";
  }
  return "staticRouteStatusPill--muted";
}
