"use client";

import { MapView } from "./CausalMap";

// Causal map of slice 2 (housing). Same conventions as the pensions map: each arrow with an `edge` opens its card;
// line style says how solid the evidence is; boxes are coloured by their deviation in the chosen year.
const W = 1000;
const H = 600;

export const HOUSING_NODES = [
  { id: "pub", label: "Vivienda pública", x: 90, y: 48, kind: "lever" },
  { id: "land", label: "Suelo liberado", x: 90, y: 136, kind: "lever" },
  { id: "tour", label: "Límite turístico", x: 90, y: 224, kind: "lever" },
  { id: "cap", label: "Tope del alquiler", x: 90, y: 330, kind: "lever" },
  { id: "caps", label: "LTP / LTI máximos", x: 90, y: 446, kind: "lever" },
  { id: "migration", label: "Inmigración", x: 90, y: 552, kind: "context" },
  { id: "obra_publica", label: "Obra pública", x: 300, y: 48 },
  { id: "obra_privada", label: "Obra privada", x: 300, y: 136 },
  { id: "turistica", label: "Turísticas que vuelven", x: 300, y: 224 },
  { id: "oferta_alquiler", label: "Oferta de alquiler", x: 300, y: 330 },
  { id: "credito", label: "Crédito a la vivienda", x: 300, y: 446 },
  { id: "parque", label: "Parque de viviendas", x: 510, y: 136 },
  { id: "hogares", label: "Hogares", x: 510, y: 250 },
  { id: "alquiler", label: "Alquiler de mercado", x: 510, y: 350 },
  { id: "precio", label: "Precio de la vivienda", x: 510, y: 470 },
  { id: "gasto", label: "Gasto público neto", x: 720, y: 48, kind: "var" },
  { id: "emancipacion", label: "Jóvenes que se emancipan", x: 720, y: 250 },
  { id: "alq_cubierto", label: "Alquiler con tope", x: 720, y: 340 },
  { id: "alq_libre", label: "Alquiler sin tope", x: 720, y: 420 },
  { id: "deuda", label: "Deuda o impuestos", x: 912, y: 48, kind: "var" },
  { id: "p1", label: "Caso 1 · busca piso", x: 912, y: 380, kind: "person" },
  { id: "p2", label: "Caso 2 · compra en Madrid", x: 912, y: 500, kind: "person" },
];

export const HOUSING_LINKS = [
  { from: "pub", to: "obra_publica", edge: "V08_public_lag", sign: "+" },
  { from: "obra_publica", to: "gasto", edge: "V09_public_cost", sign: "+" },
  { from: "gasto", to: "deuda", sign: "+" },
  { from: "obra_publica", to: "obra_privada", edge: "V10_crowd_out", sign: "−" },
  { from: "obra_publica", to: "parque", sign: "+" },
  { from: "land", to: "obra_privada", edge: "V11_land_absorption", sign: "+" },
  { from: "obra_privada", to: "parque", sign: "+" },
  { from: "tour", to: "turistica", edge: "V04_tourist_conversion", sign: "+" },
  { from: "turistica", to: "parque", sign: "+" },
  { from: "parque", to: "alquiler", edge: "V12_rent_stock_elasticity", sign: "−" },
  { from: "hogares", to: "alquiler", edge: "V12_rent_stock_elasticity", sign: "+" },
  { from: "alquiler", to: "emancipacion", edge: "V13_emancipation_rent", sign: "−", loop: "B2", curve: -14 },
  { from: "emancipacion", to: "hogares", edge: "V14_new_household_size", sign: "+", loop: "B2" },
  { from: "migration", to: "hogares", edge: "V14_new_household_size", sign: "+" },
  { from: "alquiler", to: "precio", sign: "+" },
  { from: "precio", to: "obra_privada", edge: "V02_private_supply_elasticity", sign: "+", loop: "B3", curve: 30 },
  { from: "cap", to: "oferta_alquiler", edge: "V01_rent_cap_supply", sign: "−" },
  { from: "cap", to: "alq_cubierto", edge: "V05_rent_cap_compliance", sign: "−" },
  { from: "oferta_alquiler", to: "alq_libre", edge: "V06_rental_scarcity_spillover", sign: "−" },
  { from: "alquiler", to: "alq_cubierto", sign: "+" },
  { from: "alquiler", to: "alq_libre", sign: "+" },
  { from: "caps", to: "credito", edge: "V15_constrained_credit_loss", sign: "−" },
  { from: "credito", to: "precio", edge: "V16_price_credit_elasticity", sign: "+", loop: "R2", curve: -16 },
  { from: "precio", to: "credito", edge: "V17_credit_price_feedback", sign: "+", loop: "R2", curve: 16 },
  { from: "credito", to: "alquiler", edge: "V18_tenure_substitution", sign: "−" },
  { from: "alq_cubierto", to: "p1", sign: "+" },
  { from: "alq_libre", to: "p1", sign: "+" },
  { from: "precio", to: "p2", sign: "+" },
  { from: "caps", to: "p2", edge: "V03_mortgage_binding_share", sign: "+" },
];

const lt = (v) => Number(v).toLocaleString("es-ES");

// Where the net public cost goes: extra debt, or the tax rate the closure raises.
function closureValue(run, t, closure) {
  if (closure === "cotizaciones") return [run.closure_contrib_pp[t], "pp", 2, "de cotización"];
  if (closure === "iva") return [run.closure_vat_pp[t], "pp", 2, "de IVA"];
  if (closure === "irpf") return [run.closure_irpf_pp[t], "pp", 2, "de IRPF"];
  return [run.debt_dev_pp[t], "pp", 1, "de deuda"];
}

/** Deviation shown in each node at year index t: [value, unit, digits, suffix, text]. */
export function housingValues(run, t, levers) {
  const caps = [levers.ltvCap ? `LTP ${lt(levers.ltvCap)} %` : "", levers.ltiCap ? `LTI ${lt(levers.ltiCap)}` : ""].filter(Boolean).join(" · ");
  const mig = levers.migration === "low" ? "−33 %" : levers.migration === "high" ? "+33 %" : "base oficial";
  return {
    pub: [levers.pubHomes, "k", 0, "al año"],
    land: [levers.land, "k", 0, "viviendas al año"],
    tour: [levers.tourCut, "pct", 0, "retiradas"],
    cap: [levers.capCov && levers.capCut ? levers.capCut : 0, "pct", 0, "", levers.capCov && levers.capCut ? `−${lt(levers.capCut)} % en el ${lt(levers.capCov)} %` : null],
    caps: [caps ? 1 : 0, "pct", 0, "", caps || null],
    migration: [levers.migration === "base" ? 0 : 1, "pct", 0, "", levers.migration === "base" ? null : mig],
    obra_publica: [run.hs_public_k[t], "k", 0, "terminadas"],
    obra_privada: [run.hs_private_k[t], "k", 0, "acumuladas"],
    turistica: [run.hs_tourist_k[t], "k", 0, ""],
    oferta_alquiler: [run.hs_rental_stock_k[t], "k", 0, ""],
    credito: [run.hs_credit[t] * 100, "pct", 1],
    parque: [run.hs_stock_k[t], "k", 0, ""],
    hogares: [run.hs_households_k[t], "k", 0, ""],
    alquiler: [run.hs_rent[t] * 100, "pct", 1],
    precio: [run.hs_price[t] * 100, "pct", 1],
    gasto: [run.hs_cost_pp[t], "pp", 2, "del PIB"],
    emancipacion: [run.hs_emancipated_k[t], "k", 0, "personas"],
    alq_cubierto: [run.hs_rent_cov[t] * 100, "pct", 1, "contrato nuevo"],
    alq_libre: [run.hs_rent_unc[t] * 100, "pct", 1, "contrato nuevo"],
    deuda: closureValue(run, t, levers.closure),
    p1: [levers.capCov ? run.p1_rent_cov_month[t] : run.p1_rent_unc_month[t], "eur", 0, "al mes"],
    p2: [run.p2b_upfront_eur[t], "eur", 0, "de entrada"],
  };
}

export default function HousingMap({ run, t, levers, edges, selected, onSelect }) {
  return (
    <MapView id="hmap" nodes={HOUSING_NODES} links={HOUSING_LINKS} values={housingValues(run, t, levers)} closure={levers.closure} edges={edges}
      selected={selected} onSelect={onSelect} width={W} height={H}
      loops={[{ label: "B2", x: 604, y: 214 }, { label: "R2", x: 396, y: 486 }, { label: "B3", x: 452, y: 200 }]}
      ariaLabel="Mapa causal del módulo de vivienda" />
  );
}
