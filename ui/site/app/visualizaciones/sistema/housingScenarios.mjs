// Housing scenarios shared by the page (server, headline numbers) and the simulator (client figure).
import { DEFAULT_LEVERS, runEnsemble } from "./engine.mjs";

// Housing policies side by side, each at the size stated in its label: rents for new contracts (with and without the
// cap), prices, dwellings, young adults who leave home. Central value and 5-95 % range of the draws.
export const HOUSING_SCENARIOS = [
  { id: "pub", label: "+20.000 viviendas públicas al año", levers: { pubHomes: 20 } },
  { id: "land", label: "Suelo para 20.000 viviendas al año", levers: { land: 20 } },
  { id: "tour", label: "Retirar la mitad de las turísticas", levers: { tourCut: 50 } },
  { id: "capIn", label: "Tope −10 % en la mitad del alquiler: contrato con tope", levers: { capCov: 50, capCut: 10 }, rent: "hs_rent_cov" },
  { id: "capOut", label: "El mismo tope: contrato fuera del tope", levers: { capCov: 50, capCut: 10 }, rent: "hs_rent_unc" },
  { id: "credit", label: "Hipoteca de hasta el 80 % del precio y 4,5 veces la renta", levers: { ltvCap: 80, ltiCap: 4.5 } },
  { id: "mig", label: "Contexto: un tercio más de inmigración", levers: { migration: "high" } },
];

export function housingRows(model, debates = {}, year = 2035, draws = 160) {
  const t = model.years.indexOf(year);
  return HOUSING_SCENARIOS.map((sc) => {
    const e = runEnsemble(model, { ...DEFAULT_LEVERS, ...sc.levers }, { draws, debates });
    const pick = (key, scale = 1) => ({ v: e.central[key][t] * scale, lo: e.bands[key].lo[t] * scale, hi: e.bands[key].hi[t] * scale });
    const capRow = sc.id === "capIn" || sc.id === "capOut";
    return {
      ...sc,
      rent: pick(sc.rent || "hs_rent_unc", 100),
      price: pick("hs_price", 100),
      homes: capRow ? pick("hs_rental_stock_k") : pick("hs_stock_k"),
      young: pick("hs_emancipated_k"),
      p1: pick(sc.rent === "hs_rent_cov" ? "p1_rent_cov_month" : "p1_rent_unc_month"),
      cost: pick("hs_cost_pp"),
    };
  });
}

