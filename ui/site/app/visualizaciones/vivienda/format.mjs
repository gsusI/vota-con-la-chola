// Units this page needs beyond the shared formatter (years of salary, ages, index points).
export function formatHousing(value, unit, digits = 1) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  const fixed = (d) => n.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
  if (unit === "eur") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} €`;
  if (unit === "count") return Math.round(n).toLocaleString("es-ES", { useGrouping: "always" });
  if (unit === "years" || unit === "age") return `${fixed(digits)} años`;
  if (unit === "index") return fixed(digits);
  return `${fixed(digits)} %`;
}

export function tickHousing(value, unit) {
  if (unit === "eur" || unit === "count") {
    if (Math.abs(value) >= 1e6) return `${(value / 1e6).toLocaleString("es-ES")} M`;
    return Math.abs(value) >= 1000 ? `${(value / 1000).toLocaleString("es-ES")} mil` : String(value);
  }
  if (unit === "pct") return `${value.toLocaleString("es-ES")}%`;
  return value.toLocaleString("es-ES");
}
