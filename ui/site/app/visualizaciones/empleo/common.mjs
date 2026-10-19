// Shared constants and helpers for the /visualizaciones/empleo/ chapters.
export const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};

export const NAMES = {
  ESP: "España",
  EU27: "UE-27",
  DEU: "Alemania",
  DEU_W: "Alemania Occidental (RFA)",
  FRA: "Francia",
  ITA: "Italia",
  PRT: "Portugal",
  OECD_REP: "Media OCDE",
  EU22OECD: "Media UE en la OCDE",
  GRC: "Grecia",
  NLD: "Países Bajos",
  IRL: "Irlanda",
  GBR: "Reino Unido",
  USA: "Estados Unidos",
};

export const PEERS = ["DEU", "FRA", "ITA", "PRT"];
export const PEER_LEGEND = { id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer };

export function constant(value, from, to) {
  const out = [];
  for (let year = from; year <= to; year += 1) out.push({ year, value });
  return out;
}

// Peers in gray are drawn first so the highlighted series stay on top.
export function back(series) {
  return [...series.filter((s) => s.color === C.peer), ...series.filter((s) => s.color !== C.peer)];
}

export function at(points, year) {
  return points?.find((p) => p.year === year)?.value ?? null;
}

export function last(points) {
  return points?.at(-1) ?? null;
}

export function sources(data) {
  const src = data.sources;
  const retrieved = (id) => String(src[id]?.retrieved_at || "").slice(0, 10);
  return {
    ameco: { label: `Comisión Europea, AMECO (vía DBnomics, consultado ${retrieved("ameco_dbnomics")})`, href: src.ameco_dbnomics.page },
    ine: { label: `INE, EPA (consultado ${retrieved("ine_epa_tempus")})`, href: src.ine_epa_tempus.page },
    eurostat: (dataset) => ({
      label: `Eurostat, ${dataset} (consultado ${retrieved("eurostat_sdmx")})`,
      href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table`,
    }),
    wages: { label: `OCDE, Taxing Wages (vía DBnomics, consultado ${retrieved("oecd_taxing_wages")})`, href: src.oecd_taxing_wages.page },
    pdb: { label: `OCDE, Productivity Database (vía DBnomics, consultado ${retrieved("oecd_productivity")})`, href: src.oecd_productivity.page },
    minwage: src.oecd_earnings
      ? { label: `OCDE, salario mínimo frente al mediano (vía DBnomics, consultado ${retrieved("oecd_earnings")})`, href: src.oecd_earnings.page }
      : null,
    registered: src.oecd_registered_unemployment
      ? { label: `SEPE, paro registrado, vía OCDE (DBnomics, consultado ${retrieved("oecd_registered_unemployment")})`, href: src.oecd_registered_unemployment.page }
      : null,
  };
}
