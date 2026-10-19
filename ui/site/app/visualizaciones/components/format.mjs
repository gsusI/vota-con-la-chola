export function formatValue(value, unit, digits = 1) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (unit === "eur") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} €`;
  if (unit === "count") return Math.round(n).toLocaleString("es-ES", { useGrouping: "always" });
  return `${n.toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`;
}
