// Units this page needs beyond the shared formatter (years of life, days of waiting, rates per 1,000 / 100,000).
export function formatHealth(value, unit, digits = 1) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  const fixed = (d) => n.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });
  if (unit === "eur") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} €`;
  if (unit === "count") return Math.round(n).toLocaleString("es-ES", { useGrouping: "always" });
  if (unit === "years") return `${fixed(digits)} años`;
  if (unit === "days") return `${fixed(0)} días`;
  if (unit === "per1000") return `${fixed(digits)} por mil`;
  if (unit === "per100k") return fixed(0);
  return `${fixed(digits)} %`;
}

export function tickHealth(value, unit) {
  if (unit === "eur" || unit === "count") {
    return Math.abs(value) >= 1000 ? `${(value / 1000).toLocaleString("es-ES")} mil` : String(value);
  }
  if (unit === "pct") return `${value.toLocaleString("es-ES")}%`;
  return value.toLocaleString("es-ES");
}
