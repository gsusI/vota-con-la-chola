// Number formats for /visualizaciones/empleo/ (the shared format.mjs only knows %, euros and counts).
export function num(value, digits = 1) {
  return Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signed(value, digits = 1) {
  const n = Number(value);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${num(Math.abs(n), digits)}`;
}

export function thousands(value, withSign = false) {
  const n = Number(value);
  const sign = n < 0 ? "−" : withSign && n > 0 ? "+" : "";
  const a = Math.abs(n);
  return `${sign}${a >= 1000 ? `${num(a / 1000, 2)} millones` : `${num(a, 0)} mil`}`;
}

export function fmt(value, unit = "pct", digits = 1) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  if (unit === "thousands") return thousands(value);
  if (unit === "dthousands") return thousands(value, true);
  if (unit === "index") return num(value, digits);
  if (unit === "growth") return `${signed(value, digits)} %`;
  if (unit === "pp") return `${signed(value, digits)} p.`;
  return `${num(value, digits)} %`;
}
