import { formatValue } from "../components/format.mjs";

// Units the shared formatter does not cover: years of schooling, USD PPP and PISA points.
export function fmt(value, unit, digits = 0) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (unit === "years") return `${n.toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} años`;
  if (unit === "usd") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} $`;
  if (unit === "score") return String(Math.round(n));
  return formatValue(n, unit, digits);
}
