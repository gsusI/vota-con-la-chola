import { formatValue } from "../components/format.mjs";

// Units the shared formatter does not cover: years of schooling, USD PPP, PISA points, ratios and indices.
export function fmt(value, unit, digits = 0) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (unit === "years") return `${n.toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} años`;
  if (unit === "usd") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} $`;
  if (unit === "score") return String(Math.round(n));
  if (unit === "ratio" || unit === "index") return n.toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return formatValue(n, unit, digits);
}
