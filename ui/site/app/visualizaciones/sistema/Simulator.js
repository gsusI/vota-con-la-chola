"use client";

import { useEffect, useMemo, useState } from "react";
import { SeriesTable } from "../components/Figure";
import FanChart, { fmt } from "./FanChart";
import CausalMap from "./CausalMap";
import HousingMap from "./HousingMap";
import { housingRows } from "./housingScenarios.mjs";
import { DEFAULT_LEVERS, LAYERS, applyLayer, centralParams, decodeState, encodeState, mainDriver, quintileImpact, runEnsemble, simulate } from "./engine.mjs";
import QuintileFigure from "./QuintileFigure";
import "./sistema.css";

const C = { base: "#8b8a83", scen: "#2a78d6", p1: "#eb6834", p2: "#eda100", p4: "#1baf7a", p5: "#7a5af5" };

export const PARAM_LABELS = {
  lambda_renovacion: "renovación anual de las pensiones",
  kappa_cohorte: "tamaño de la cohorte que se jubila",
  permanencia_empleo: "quién sigue trabajando si se retrasa la jubilación",
  prestacion_alternativa: "otras prestaciones de quien no sigue trabajando",
  tipo_marginal_irpf_pension: "IRPF que se recupera de la pensión",
  multiplicador_transferencias: "efecto de las pensiones sobre el PIB",
  multiplicador_impuestos: "efecto de los impuestos sobre el PIB",
  persistencia_multiplicador: "duración del efecto sobre el PIB",
  semielasticidad_saldo: "respuesta del saldo público al PIB",
  traslado_cotizacion_salario: "parte de la cotización empresarial que pagan los salarios",
  elasticidad_empleo_coste: "respuesta del empleo al coste laboral",
  base_cotizacion_pib: "recaudación por punto de cotización",
  recaudacion_por_1pct_empleo: "ingresos por cada 1 % de empleo",
  recaudacion_por_punto_iva: "recaudación por punto de IVA",
  traslado_iva_precios: "traslado del IVA a los precios",
  cuota_iva_general: "consumo gravado al tipo general",
  indiciacion_salarios: "salarios que recuperan la inflación",
  prima_por_deuda: "prima de riesgo por deuda",
  cuota_refinanciacion: "ritmo de refinanciación de la deuda",
  recaudacion_por_punto_irpf: "recaudación por punto de IRPF",
  recaudacion_por_punto_irpf_alto: "recaudación por punto del tramo alto",
  pareto_a_alto: "forma de la distribución de las rentas altas",
  eti_general: "respuesta de la renta declarada al IRPF",
  eti_alta: "respuesta de las rentas altas al IRPF",
  recaudacion_por_punto_iva_reducido: "recaudación por punto de IVA reducido",
  recaudacion_por_punto_sociedades: "recaudación por punto de Sociedades",
  semielasticidad_base_sociedades: "beneficios que se declaran fuera o dejan de declararse",
  traslado_sociedades_salarios: "parte del Impuesto sobre Sociedades que pagan los salarios",
  salarios_pib: "peso de los salarios en el PIB",
  respuesta_oferta_tope: "pisos de alquiler que salen del mercado con el tope",
  elasticidad_oferta_privada: "respuesta de la obra privada al precio",
  hip_sobre_ltv80: "hipotecas por encima del 80 % del precio",
  hip_sobre_ltv90: "hipotecas por encima del 90 % del precio",
  hip_sobre_ltv70: "hipotecas por encima del 70 % del precio",
  hip_sobre_lti6: "hipotecas de más de 6 veces la renta",
  hip_sobre_lti45: "hipotecas de más de 4,5 veces la renta",
  conversion_turistica: "pisos turísticos que vuelven a vivienda habitual",
  cumplimiento_tope: "parte del tope que se cumple",
  traslado_escasez_alquiler: "subida del alquiler sin tope cuando falta oferta",
  renovacion_contratos: "contratos de alquiler nuevos cada año",
  retardo_obra_publica: "años hasta terminar la vivienda pública",
  retardo_obra_privada: "años de obra de la vivienda privada",
  coste_vivienda_publica: "coste de cada vivienda pública",
  renta_social_mes: "alquiler de la vivienda pública",
  cuota_financiacion_publica: "parte del coste que paga el presupuesto",
  desplazamiento_obra_privada: "obra privada que desplaza la pública",
  absorcion_suelo: "suelo liberado que acaba construido",
  respuesta_alquiler_parque: "respuesta del alquiler a las viviendas por hogar",
  elasticidad_emancipacion: "jóvenes que se emancipan cuando baja el alquiler",
  personas_por_hogar_nuevo: "personas por hogar nuevo",
  hogares_por_inmigrante: "hogares por inmigrante",
  perdida_credito_restringido: "crédito que desaparece con el límite",
  elasticidad_precio_credito: "respuesta del precio al crédito",
  elasticidad_credito_precio: "respuesta del crédito al precio (garantía)",
  cuota_credito_nuevo: "crédito nuevo sobre el saldo",
  sustitucion_alquiler: "compradores que pasan a alquilar",
};

const LAYER_LABELS = {
  contable: "Solo aritmética",
  comportamiento: "+ reacción de empresas, trabajadores y mercados",
  segunda_ronda: "+ efectos de segunda ronda",
};

const CLOSURES = [
  { id: "deuda", label: "Con deuda", note: "nadie paga hoy; la deuda y sus intereses crecen" },
  { id: "cotizaciones", label: "Con cotizaciones", note: "sube el tipo cada año lo necesario (5/6 empresa, 1/6 trabajador)" },
  { id: "iva", label: "Con IVA", note: "sube el tipo general cada año lo necesario" },
  { id: "irpf", label: "Con IRPF", note: "suben todos los tramos de la escala general lo necesario" },
];

const HORIZONS = [2030, 2035, 2050];
const signed = (v, unit, digits) => {
  const d = unit === "eur" || unit === "k" ? 0 : digits;
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return (r > 0 ? "+" : r < 0 ? "−" : "") + fmt(Math.abs(r), unit, digits);
};

function Slider({ id, label, value, min, max, step, unit, onChange, hint }) {
  return (
    <label className="sim__slider" htmlFor={id}>
      <span className="sim__sliderLabel">
        {label}
        <strong>{value > 0 ? "+" : value < 0 ? "−" : ""}{Math.abs(value).toLocaleString("es-ES")} {unit}</strong>
      </span>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      {hint ? <span className="sim__hint">{hint}</span> : null}
    </label>
  );
}

function Segmented({ name, options, value, onChange, label }) {
  return (
    <fieldset className="sim__seg">
      <legend>{label}</legend>
      <div>
        {options.map((o) => (
          <label key={o.id} className={value === o.id ? "is-on" : ""}>
            <input type="radio" name={name} value={o.id} checked={value === o.id} onChange={() => onChange(o.id)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function EdgeCard({ edge }) {
  if (!edge) return <p className="sim__muted">Toca una flecha del mapa para ver su ficha: qué número usa el modelo, de dónde sale y qué lo contradice.</p>;
  const p = edge.parameter;
  return (
    <article className="edgeCard" aria-live="polite">
      <header>
        <span className={`edgeCard__grade edgeCard__grade--${edge.grade}`}>Evidencia {edge.grade}</span>
        <span className="edgeCard__layer">{edge.layer === "contable" ? "aritmética" : edge.layer === "comportamiento" ? "comportamiento" : "segunda ronda"}</span>
      </header>
      <p className="edgeCard__note">{edge.note_es}</p>
      <p className="edgeCard__value">
        {p.unit}: <strong>{p.central.toLocaleString("es-ES")}</strong>
        {p.low !== p.high ? ` (rango ${p.low.toLocaleString("es-ES")} a ${p.high.toLocaleString("es-ES")})` : ""}
      </p>
      <p className="sim__muted">{edge.derivation}</p>
      <ul className="edgeCard__sources">
        {edge.sources.map((s) => (
          <li key={s.url + s.locator}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">{s.authors_year}</a>, {s.title} ({s.locator}; {s.country}).
          </li>
        ))}
      </ul>
      {edge.contrary_evidence?.length ? (
        <>
          <p className="edgeCard__sub">Lo que apunta en otra dirección</p>
          <ul className="edgeCard__sources">
            {edge.contrary_evidence.map((c) => (
              <li key={c.url + c.finding}>
                <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a>: {c.finding}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}

/** Rows × panels of central value (dot) and 5-95 % range (bar), zero always on the axis. */
export function DotRangeFigure({ rows, panels, ariaLabel }) {
  return (
    <div className="closureFig" role="table" aria-label={ariaLabel}>
      {panels.map((panel) => {
        const vals = rows.filter((r) => r[panel.key]).flatMap((r) => [r[panel.key].lo, r[panel.key].hi, 0]);
        const lo = Math.min(...vals);
        const hi = Math.max(...vals);
        const sx = (v) => ((v - lo) / (hi - lo || 1)) * 100;
        return (
          <div className="closureFig__panel" key={panel.key} role="rowgroup">
            <h3>{panel.title}</h3>
            {rows.map((r) => {
              const d = r[panel.key];
              if (!d) return null;
              return (
                <div className="closureFig__row" key={r.id} role="row">
                  <span className="closureFig__label" role="rowheader">{r.label}</span>
                  <span className="closureFig__track" aria-hidden="true">
                    <span className="closureFig__zero" style={{ left: `${sx(0)}%` }} />
                    <span className="closureFig__range" style={{ left: `${sx(d.lo)}%`, width: `${Math.max(0.6, sx(d.hi) - sx(d.lo))}%` }} />
                    <span className="closureFig__dot" style={{ left: `${sx(d.v)}%` }} />
                  </span>
                  <span className="closureFig__value" role="cell">
                    {signed(d.v, panel.unit, panel.digits)}
                    <small>
                      {signed(d.lo, panel.unit, panel.digits)} a {signed(d.hi, panel.unit, panel.digits)}
                    </small>
                  </span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

export function HousingFigure({ model, debates }) {
  const rows = useMemo(() => housingRows(model, debates), [model, debates]);
  const panels = [
    { key: "rent", title: "Alquiler de un contrato nuevo en 2035", unit: "pct", digits: 1 },
    { key: "p1", title: "Caso 1 (joven en Madrid), alquiler al mes en 2035", unit: "eur", digits: 0 },
    { key: "homes", title: "Viviendas para residentes en 2035 (en el tope: pisos que salen del alquiler)", unit: "k", digits: 0 },
    { key: "young", title: "Jóvenes que se emancipan en 2035", unit: "k", digits: 0 },
  ];
  return <DotRangeFigure rows={rows} panels={panels} ariaLabel="Seis políticas de vivienda: alquiler, caso 1, viviendas y emancipación en 2035" />;
}

// «Tres formas de pagar lo mismo»: the same lever under each closure, four outcomes, central value and 5-95 % range.
function ClosureFigure({ model, debates }) {
  const t30 = model.years.indexOf(2035);
  const t50 = model.years.length - 1;
  const rows = useMemo(
    () =>
      CLOSURES.map((c) => {
        const e = runEnsemble(model, { ...DEFAULT_LEVERS, reval: 1, closure: c.id }, { draws: 160, debates });
        const pick = (key, t) => ({ v: e.central[key][t], lo: e.bands[key].lo[t], hi: e.bands[key].hi[t] });
        return {
          ...c,
          debt: pick("debt_dev_pp", t50),
          p4: pick("p4_month", t30),
          p1: pick("p1_month", t30),
          jobs: pick("employment_k", t30),
        };
      }),
    [model, debates, t30, t50],
  );
  const panels = [
    { key: "debt", title: "Deuda extra en 2050", unit: "pp", digits: 1, suffix: "del PIB" },
    { key: "p4", title: "Caso 4 (pensionista) en 2035", unit: "eur", digits: 0, suffix: "al mes" },
    { key: "p1", title: "Caso 1 (joven asalariada) en 2035", unit: "eur", digits: 0, suffix: "al mes" },
    { key: "jobs", title: "Empleo en 2035", unit: "k", digits: 0, suffix: "" },
  ];
  return <DotRangeFigure rows={rows} panels={panels} ariaLabel="Subir las pensiones un punto sobre el IPC: resultados según cómo se pague" />;
}

export default function Simulator({ model }) {
  const [levers, setLevers] = useState(DEFAULT_LEVERS);
  const [debates, setDebates] = useState({});
  const [horizon, setHorizon] = useState(2035);
  const [layer, setLayer] = useState("segunda_ronda");
  const [selected, setSelected] = useState(null);
  const [ready, setReady] = useState(false);

  // Shareable state lives in the URL fragment (never the query string).
  useEffect(() => {
    const { levers: l, debates: d, extra } = decodeState(window.location.hash);
    setLevers(l);
    setDebates(d);
    if (extra.h && HORIZONS.includes(Number(extra.h))) setHorizon(Number(extra.h));
    setReady(true);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const hash = encodeState(levers, debates, horizon !== 2035 ? { h: horizon } : {});
    const url = `${window.location.pathname}${window.location.search}${hash ? `#${hash}` : ""}`;
    window.history.replaceState(null, "", url);
  }, [levers, debates, horizon, ready]);

  const set = (key) => (value) => setLevers((prev) => ({ ...prev, [key]: value }));
  const edgeById = useMemo(() => Object.fromEntries(model.edges.map((e) => [e.id, e])), [model]);
  const ensemble = useMemo(() => runEnsemble(model, levers, { debates, layer }), [model, levers, debates, layer]);
  const run = ensemble.central;
  const layerParams = useMemo(() => applyLayer(model, centralParams(model, debates), layer), [model, debates, layer]);
  const quintiles = quintileImpact(model, run, model.years.indexOf(horizon), layerParams);
  const base = model.baseline;
  const t = model.years.indexOf(horizon);
  const tEnd = model.years.length - 1;
  const moved =
    levers.reval || levers.age || levers.contrib || levers.irpfAll || levers.irpfTop || levers.vatStd || levers.vatRed || levers.corp ||
    levers.migration !== "base" || levers.rateShock || housingMoved(levers);
  const housingOn = housingMoved(levers) || levers.migration !== "base";

  // Same outputs under each certainty layer (central parameters), to show what is arithmetic and what is assumption.
  const layered = useMemo(
    () =>
      LAYERS.map((ly) => {
        const p = applyLayer(model, centralParams(model, debates), ly);
        return { layer: ly, run: simulate(model, levers, p), params: p };
      }),
    [model, levers, debates],
  );
  const outputs = [
    { key: "debt_dev_pp", label: "Deuda extra en 2050", unit: "pp", digits: 1, t: tEnd },
    { key: "pension_gross_pp", label: `Gasto extra en pensiones en ${horizon}`, unit: "pp", digits: 2, t },
    { key: "p4_month", label: `Caso 4 en ${horizon}, al mes`, unit: "eur", digits: 0, t },
    { key: "p1_month", label: `Caso 1 en ${horizon}, al mes`, unit: "eur", digits: 0, t },
    { key: "employment_k", label: `Empleo en ${horizon}`, unit: "k", digits: 0, t },
    { key: "q1", label: `Hogares del quintil 1 en ${horizon}, al mes`, unit: "eur", digits: 0, t, quintile: 0 },
    { key: "q5", label: `Hogares del quintil 5 en ${horizon}, al mes`, unit: "eur", digits: 0, t, quintile: 4 },
    ...(housingOn
      ? [
          { key: "hs_rent_unc", label: `Alquiler de un contrato nuevo sin tope en ${horizon}`, unit: "pct", digits: 1, t, scale: 100 },
          ...(levers.capCov && levers.capCut ? [{ key: "hs_rent_cov", label: `Alquiler de un contrato nuevo con tope en ${horizon}`, unit: "pct", digits: 1, t, scale: 100 },
            { key: "hs_rental_stock_k", label: `Pisos de alquiler de mercado en ${horizon}`, unit: "k", digits: 0, t }] : []),
          { key: "hs_price", label: `Precio de la vivienda en ${horizon}`, unit: "pct", digits: 1, t, scale: 100 },
          { key: "hs_stock_k", label: `Viviendas para residentes en ${horizon}`, unit: "k", digits: 0, t },
          { key: "hs_emancipated_k", label: `Jóvenes que se emancipan en ${horizon}`, unit: "k", digits: 0, t },
        ]
      : []),
  ];
  const valueOf = (o, r, p) => (o.quintile != null ? quintileImpact(model, r, o.t, p)[o.quintile].total : r[o.key][o.t] * (o.scale || 1));
  const debateParams = Object.entries(model.params).filter(([, p]) => p.debate);
  const closureRate = { cotizaciones: "closure_contrib_pp", iva: "closure_vat_pp", irpf: "closure_irpf_pp" }[levers.closure] || null;
  const band = (key) => ({ lo: ensemble.bands[key].lo, hi: ensemble.bands[key].hi });
  const asPoints = (values) => model.years.map((year, i) => ({ year, value: Math.round(values[i] * 100) / 100 }));

  return (
    <div className="sim">
      <section className="sim__panel" aria-label="Palancas">
        <div className="sim__group">
          <h3>Pensiones</h3>
          <Slider id="lv-reval" label="Revalorización sobre el IPC, cada año" value={levers.reval} min={-2} max={2} step={0.25} unit="pp"
            onChange={set("reval")} hint="0 = la ley actual (IPC). Se aplica a todas las pensiones desde 2026." />
          <Slider id="lv-age" label="Edad efectiva de jubilación frente a la línea base" value={levers.age} min={-2} max={2} step={0.5} unit="años"
            onChange={set("age")} hint="Se aplica a dos meses por año. La línea base ya sube la edad efectiva de 63,4 (2022) a 66,2 (2050)." />
          <Slider id="lv-contrib" label="Cotizaciones sociales (para pensiones)" value={levers.contrib} min={-1} max={2} step={0.25} unit="pp"
            onChange={set("contrib")} hint={`Como el MEI, que la ley ya sube hasta ${String(model.mei_2029 ?? 1.2).replace(".", ",")} pp en 2029 (incluido en la línea base).`} />
        </div>
        <div className="sim__group">
          <h3>Impuestos</h3>
          <Slider id="lv-irpf" label="IRPF: todos los tramos" value={levers.irpfAll} min={-3} max={3} step={0.5} unit="pp" onChange={set("irpfAll")}
            hint="Escala general, estatal y autonómica." />
          <Slider id="lv-irpftop" label="IRPF: tramo de más de 60.000 €" value={levers.irpfTop} min={-5} max={5} step={1} unit="pp" onChange={set("irpfTop")} />
          <Slider id="lv-vat" label="IVA general (21 %)" value={levers.vatStd} min={-3} max={3} step={0.5} unit="pp" onChange={set("vatStd")} />
          <Slider id="lv-vatred" label="IVA reducido (10 %)" value={levers.vatRed} min={-3} max={3} step={0.5} unit="pp" onChange={set("vatRed")}
            hint="Alimentos elaborados, restaurantes, transporte, agua." />
          <Slider id="lv-corp" label="Impuesto sobre Sociedades (25 %)" value={levers.corp} min={-5} max={5} step={1} unit="pp" onChange={set("corp")} />
        </div>
        <div className="sim__group">
          <h3>Vivienda</h3>
          <Slider id="lv-pub" label="Vivienda pública en alquiler, más al año" value={levers.pubHomes} min={0} max={60} step={5} unit="mil"
            onChange={set("pubHomes")} hint={`Hoy se terminan unas ${fmt(model.housing.completions_protected_k, "k")} protegidas al año (de todo tipo). Se paga como diga «¿Cómo se paga?».`} />
          <Slider id="lv-land" label="Suelo liberado, viviendas posibles al año" value={levers.land} min={0} max={60} step={5} unit="mil"
            onChange={set("land")} hint="Suelo finalista listo para construir; lo que se construya depende de los promotores." />
          <Slider id="lv-tour" label="Viviendas turísticas retiradas" value={levers.tourCut} min={0} max={100} step={10} unit="%"
            onChange={set("tourCut")} hint={`Hoy son el ${String(model.housing.tourist_share * 100).replace(".", ",")} % de las viviendas (unas ${fmt(model.housing.tourist_k, "k")}).`} />
          <Slider id="lv-capcov" label="Tope del alquiler: alquiler cubierto" value={levers.capCov} min={0} max={100} step={10} unit="%"
            onChange={set("capCov")} hint="Parte de los hogares de alquiler de mercado en zonas tensionadas declaradas, además de las que ya lo aplican." />
          <Slider id="lv-capcut" label="Tope del alquiler: rebaja que exige" value={levers.capCut} min={0} max={20} step={2} unit="%"
            onChange={set("capCut")} hint="Rebaja media que impone a los contratos cubiertos frente al precio de mercado." />
          <Segmented name="ltv" label="Hipoteca máxima sobre el precio de compra (LTP)" value={String(levers.ltvCap)} onChange={(v) => set("ltvCap")(Number(v))}
            options={[{ id: "0", label: "Sin límite" }, { id: "90", label: "90 %" }, { id: "80", label: "80 %" }, { id: "70", label: "70 %" }]} />
          <Segmented name="lti" label="Hipoteca máxima sobre la renta bruta (LTI)" value={String(levers.ltiCap)} onChange={(v) => set("ltiCap")(Number(v))}
            options={[{ id: "0", label: "Sin límite" }, { id: "6", label: "6 veces" }, { id: "4.5", label: "4,5 veces" }]} />
        </div>
        <div className="sim__group">
          <Segmented name="closure" label="¿Cómo se paga el coste neto de cada año?" value={levers.closure} onChange={set("closure")} options={CLOSURES} />
          <p className="sim__hint">{CLOSURES.find((c) => c.id === levers.closure).note}</p>
          <h3>Contexto (no es una política)</h3>
          <Segmented name="migration" label="Inmigración (escenarios del Ageing Report)" value={levers.migration} onChange={set("migration")}
            options={[{ id: "low", label: "−33 %" }, { id: "base", label: "Base" }, { id: "high", label: "+33 %" }]} />
          <Slider id="lv-rate" label="Tipos de interés de mercado frente a la línea base" value={levers.rateShock} min={-1} max={2} step={0.25} unit="pp" onChange={set("rateShock")} />
        </div>
        <div className="sim__group">
          <h3>Supuestos en disputa</h3>
          {debateParams.map(([name, p]) => (
            <label key={name} className="sim__select">
              <span>{PARAM_LABELS[name] || name}</span>
              <select
                value={debates[p.debate.id] ?? ""}
                onChange={(e) =>
                  setDebates((prev) => {
                    const next = { ...prev };
                    if (e.target.value === "") delete next[p.debate.id];
                    else next[p.debate.id] = Number(e.target.value);
                    return next;
                  })
                }
              >
                <option value="">Valor central ({p.central.toLocaleString("es-ES")}) y todo el rango</option>
                {p.debate.schools.map((s, i) => (
                  <option key={s.label} value={i}>
                    {s.label} ({s.central.toLocaleString("es-ES")})
                  </option>
                ))}
              </select>
            </label>
          ))}
          <Segmented name="horizon" label="Año que se muestra en el mapa y los casos" value={String(horizon)} onChange={(v) => setHorizon(Number(v))}
            options={HORIZONS.map((h) => ({ id: String(h), label: String(h) }))} />
          <Segmented name="layer" label="Capas de certeza que se suman" value={layer} onChange={setLayer}
            options={LAYERS.map((ly) => ({ id: ly, label: ly === "contable" ? "Aritmética" : ly === "comportamiento" ? "+ Reacción" : "+ 2.ª ronda" }))} />
          <button type="button" className="sim__reset" onClick={() => { setLevers(DEFAULT_LEVERS); setDebates({}); setLayer("segunda_ronda"); }}>
            Volver a la ley actual
          </button>
        </div>
      </section>

      {!moved ? (
        <p className="sim__callout">Mueve una palanca: con todo a cero, el escenario es la línea base oficial y todas las desviaciones valen cero.</p>
      ) : null}

      <figure className="vizFigure sim__figure" id="mapa">
        <h2>Cómo se propaga el cambio, en {horizon}</h2>
        <p className="vizFigure__dek">
          Cada caja muestra cuánto se aparta de la línea base en {horizon}; las flechas encendidas son las que transmiten el cambio. Línea continua: evidencia
          A (contabilidad o datos de España); discontinua: B (estudios de otros países); punteada: C o D (consenso o supuesto). R1: la deuda paga intereses que
          aumentan la deuda. B1: cotizar más encarece el empleo y devuelve parte de lo recaudado.
        </p>
        <CausalMap run={run} t={t} levers={levers} edges={model.edges} selected={selected} onSelect={setSelected} />
        <EdgeCard edge={selected ? edgeById[selected] : null} />
      </figure>

      <figure className="vizFigure sim__figure" id="series">
        <h2>Línea base oficial y escenario, 2025–2050</h2>
        <p className="vizFigure__dek">
          Gris: la ley actual según el Ageing Report 2024, con el resto del presupuesto constante en % del PIB. Azul: tu escenario; la banda cubre del 5 % al
          95 % de 200 simulaciones con los parámetros dentro de sus rangos.
        </p>
        <div className="sim__charts">
          <div>
            <h3 className="vizPanelTitle">Gasto en pensiones públicas, % del PIB</h3>
            <FanChart years={model.years} unit="pct" ariaLabel="Gasto en pensiones, línea base y escenario"
              series={[
                { id: "b", label: "Línea base", color: C.base, values: base.pension_pct, dash: true },
                { id: "s", label: "Escenario", color: C.scen, values: run.pension_pct, emphasis: true, ...band("pension_pct") },
              ]} />
          </div>
          <div>
            <h3 className="vizPanelTitle">Deuda pública, % del PIB</h3>
            <FanChart years={model.years} unit="pct" digits={0} ariaLabel="Deuda pública, línea base y escenario"
              series={[
                { id: "b", label: "Línea base", color: C.base, values: base.debt_pct, dash: true },
                { id: "s", label: "Escenario", color: C.scen, values: run.debt_pct, emphasis: true, ...band("debt_pct") },
              ]} />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              {{ closure_contrib_pp: "Subida de cotización necesaria, pp de la base", closure_vat_pp: "Subida del IVA general necesaria, pp", closure_irpf_pp: "Subida de todos los tramos del IRPF necesaria, pp" }[closureRate] || "Deuda extra, pp del PIB"}
            </h3>
            <FanChart years={model.years} unit="pp" ariaLabel="Coste del escenario según cómo se paga"
              series={[{ id: "c", label: "Escenario", color: C.scen, emphasis: true, values: run[closureRate || "debt_dev_pp"], ...band(closureRate || "debt_dev_pp") }]} />
          </div>
          <div>
            <h3 className="vizPanelTitle">Empleo frente a la línea base, miles de personas</h3>
            <FanChart years={model.years} unit="k" digits={0} ariaLabel="Empleo frente a la línea base"
              series={[{ id: "e", label: "Escenario", color: C.scen, emphasis: true, values: run.employment_k, ...band("employment_k") }]} />
          </div>
        </div>
        <SeriesTable
          unit="pct"
          digits={2}
          series={[
            { id: "pb", label: "Pensiones, línea base (% PIB)", points: asPoints(base.pension_pct) },
            { id: "ps", label: "Pensiones, escenario (% PIB)", points: asPoints(run.pension_pct) },
            { id: "db", label: "Deuda, línea base (% PIB)", points: asPoints(base.debt_pct) },
            { id: "ds", label: "Deuda, escenario (% PIB)", points: asPoints(run.debt_pct) },
          ]}
        />
      </figure>

      <figure className="vizFigure sim__figure" id="personas">
        <h2>Qué les pasa a cuatro casos tipo, en {horizon}</h2>
        <p className="vizFigure__dek">
          Euros al mes a precios de {model.personas.p1.year}, frente a la ley actual. Son los casos 1, 2, 4 y 5 de las demás páginas, con su misma renta:
          el cálculo es ilustrativo (IRPF con las reglas generales, sin deducciones autonómicas ni por hijos) y no incluye lo que cambie en vivienda o
          servicios.
        </p>
        <div className="sim__people">
          {[
            { id: "p1", color: C.p1, title: "Caso 1 · 25–34 años, asalariada, vive sola de alquiler en Madrid", base: `Sueldo de ${fmt(model.personas.p1.gross, "eur")} brutos al año (${fmt(model.personas.p1.net / 12, "eur")} netos al mes)` },
            { id: "p2", color: C.p2, title: "Caso 2 · pareja de 30–44 con dos hijos y dos sueldos", base: `Sueldos de ${fmt(model.personas.p2.gross, "eur")} brutos al año entre los dos (${fmt(model.personas.p2.net / 12, "eur")} netos al mes)` },
            { id: "p4", color: C.p4, title: "Caso 4 · pensionista de 65 años o más, vive solo, casa pagada", base: `Pensión de ${fmt(model.personas.p4.gross, "eur")} brutos al año (${fmt(model.personas.p4.net / 12, "eur")} netos al mes)` },
            { id: "p5", color: C.p5, title: "Caso 5 · profesional de 45–54, universitario, en Madrid", base: `Sueldo de ${fmt(model.personas.p5.gross, "eur")} brutos al año (${fmt(model.personas.p5.net / 12, "eur")} netos al mes); no llega al tramo de 60.000 €` },
          ].map((p) => {
            const key = `${p.id}_month`;
            const v = run[key][t];
            const same = ensemble.bands[key].sameSign[t];
            return (
              <div className="sim__person" key={p.id} style={{ "--tone": p.color }}>
                <h3>{p.title}</h3>
                <p className="sim__personValue">{Math.abs(v) < 0.5 ? "Sin cambio" : signed(v, "eur", 0)}<small> al mes</small></p>
                {Math.abs(v) >= 0.5 ? (
                  <p className="sim__muted">
                    Entre {signed(ensemble.bands[key].lo[t], "eur", 0)} y {signed(ensemble.bands[key].hi[t], "eur", 0)}.{" "}
                    {same >= 0.95 ? "El signo es el mismo en todas las hipótesis." : `El signo cambia según los supuestos (${Math.round(same * 100)} % de las simulaciones).`}
                  </p>
                ) : null}
                <p className="sim__muted">{p.base}.</p>
              </div>
            );
          })}
        </div>
        {levers.closure === "deuda" && Math.abs(run.debt_dev_pp[tEnd]) >= 0.5 ? (
        <p className="sim__muted">
          {run.debt_dev_pp[tEnd] > 0 ? "Con deuda, nadie paga hoy:" : "El ahorro reduce la deuda:"} en 2050 la diferencia de deuda equivale a {fmt(Math.abs(run.debt_per_person_eur[tEnd]), "eur")} por habitante (al PIB y la
          población de {model.start.year}){run.debt_dev_pp[tEnd] > 0 ? ", que alguien pagará después o seguirá pagando en intereses" : ""}.
        </p>
        ) : null}
      </figure>

      <figure className="vizFigure sim__figure" id="quintiles">
        <h2>Quién gana y quién pierde por nivel de renta, en {horizon}</h2>
        <p className="vizFigure__dek">
          Euros al mes por hogar a precios de {model.start.year}, según el quintil de renta disponible por unidad de consumo. Es la carga legal de
          cada cambio (antes de que la gente reaccione), repartida con los microdatos de la Encuesta de Condiciones de Vida {model.incidence.ecv.year} y,
          para el IVA, con el gasto de la Encuesta de Presupuestos Familiares {model.incidence.vat.year}. Lo que se paga con deuda no aparece: lo pagará
          alguien después.
        </p>
        <QuintileFigure rows={quintiles} cuts={model.incidence.ecv.cuts_eq_income} />
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Quintil</th>
                  {Object.keys(quintiles[0].byPart).map((p) => (
                    <th scope="col" key={p}>{p}</th>
                  ))}
                  <th scope="col">Total al mes</th>
                  <th scope="col">% de la renta</th>
                </tr>
              </thead>
              <tbody>
                {quintiles.map((q) => (
                  <tr key={q.q}>
                    <td>{q.q}</td>
                    {Object.values(q.byPart).map((v, i) => (
                      <td key={i}>{signed(v, "eur", 0)}</td>
                    ))}
                    <td>{signed(q.total, "eur", 0)}</td>
                    <td>{signed(q.pctDisposable, "pct", 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </figure>

      <figure className="vizFigure sim__figure" id="mapa-vivienda">
        <h2>Vivienda: cómo se propaga el cambio, en {horizon}</h2>
        <p className="vizFigure__dek">
          Las mismas reglas que el mapa de arriba. B2: construir abarata, abaratar emancipa y los hogares nuevos ocupan parte de lo construido. R2: el
          crédito sube el precio y el precio sube la garantía del crédito. B3: si baja el precio, la obra privada se retira.
        </p>
        <HousingMap run={run} t={t} levers={levers} edges={model.edges} selected={selected} onSelect={setSelected} />
        <EdgeCard edge={selected ? edgeById[selected] : null} />
      </figure>

      <HousingSeries model={model} run={run} band={band} />

      <HousingPeople model={model} run={run} ensemble={ensemble} t={t} horizon={horizon} levers={levers} />

      <figure className="vizFigure sim__figure" id="certeza">
        <h2>Qué parte es aritmética y qué parte es supuesto</h2>
        <p className="vizFigure__dek">
          El mismo escenario con los valores centrales, sumando capas: primero solo la contabilidad, después la reacción de empresas, trabajadores y mercados,
          y por último los efectos sobre el PIB. La última columna dice qué supuesto mueve más el resultado.
        </p>
        <div className="vizTable__scroll">
          <table className="sim__table">
            <thead>
              <tr>
                <th scope="col">Resultado</th>
                {LAYERS.map((ly) => (
                  <th scope="col" key={ly}>{LAYER_LABELS[ly]}</th>
                ))}
                <th scope="col">Robustez y supuesto clave</th>
              </tr>
            </thead>
            <tbody>
              {outputs.map((o) => {
                const central = valueOf(o, run, layerParams);
                const values = ensemble.runs.map((r, j) => valueOf(o, r, ensemble.sample[j]));
                const same = Math.sign(central) ? values.filter((v) => Math.sign(v) === Math.sign(central)).length / values.length : 1;
                const driver = Math.abs(central) > 1e-6 ? mainDriver(model, ensemble, values, o.t) : null;
                return (
                  <tr key={o.key}>
                    <th scope="row">{o.label}</th>
                    {layered.map((l) => (
                      <td key={l.layer}>{signed(valueOf(o, l.run, l.params), o.unit, o.digits)}</td>
                    ))}
                    <td>
                      {Math.abs(central) < 1e-6 ? "—" : same >= 0.95 ? "Signo robusto" : `Signo incierto (${Math.round(same * 100)} %)`}
                      {driver && Math.abs(driver.rho) > 0.2 ? <span className="sim__muted"> · depende sobre todo de: {PARAM_LABELS[driver.name] || driver.name}</span> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </figure>

      <VotesBlock model={model} levers={levers} />
    </div>
  );
}

const VOTE_LABEL = { S: "Sí", N: "No", A: "Abst.", "?": "—" };

export function housingMoved(levers) {
  return Boolean(levers.pubHomes || levers.land || levers.tourCut || (levers.capCov && levers.capCut) || levers.ltvCap || levers.ltiCap);
}

function HousingSeries({ model, run, band }) {
  const pctBand = (key) => {
    const b = band(key);
    return { lo: b.lo.map((v) => v * 100), hi: b.hi.map((v) => v * 100) };
  };
  const pct = (key) => run[key].map((v) => v * 100);
  const capOn = run.hs_rent_cov.some((v) => v !== 0);
  return (
    <figure className="vizFigure sim__figure" id="series-vivienda">
      <h2>Vivienda: escenario frente a la línea base, 2025–2050</h2>
      <p className="vizFigure__dek">
        Desviaciones frente a la línea base: los hogares de la proyección del INE ({model.housing.households_k[1].toLocaleString("es-ES", { maximumFractionDigits: 0 })} mil
        en {model.years[1]}) y la obra terminada constante en la media de {model.housing.base_year - 2}–{model.housing.base_year} ({fmt(model.housing.completions_free_k + model.housing.completions_protected_k, "k")} al año). Banda: del 5 % al 95 % de las simulaciones.
      </p>
      <div className="sim__charts">
        <div>
          <h3 className="vizPanelTitle">Alquiler de un contrato nuevo, % frente a la línea base</h3>
          <FanChart years={model.years} unit="pct" ariaLabel="Alquiler de contratos nuevos frente a la línea base"
            series={[
              { id: "u", label: capOn ? "Sin tope" : "Mercado", color: C.scen, values: pct("hs_rent_unc"), emphasis: true, ...pctBand("hs_rent_unc") },
              ...(capOn ? [{ id: "c", label: "Con tope", color: C.p1, values: pct("hs_rent_cov"), ...pctBand("hs_rent_cov") }] : []),
            ]} />
        </div>
        <div>
          <h3 className="vizPanelTitle">Precio de la vivienda y crédito, % frente a la línea base</h3>
          <FanChart years={model.years} unit="pct" ariaLabel="Precio de la vivienda y crédito frente a la línea base"
            series={[
              { id: "p", label: "Precio", color: C.scen, values: pct("hs_price"), emphasis: true, ...pctBand("hs_price") },
              { id: "c", label: "Crédito", color: C.p5, values: pct("hs_credit") },
            ]} />
        </div>
        <div>
          <h3 className="vizPanelTitle">Viviendas y hogares de más, miles</h3>
          <FanChart years={model.years} unit="k" digits={0} ariaLabel="Viviendas y hogares de más frente a la línea base"
            series={[
              { id: "s", label: "Viviendas", color: C.scen, values: run.hs_stock_k, emphasis: true, ...band("hs_stock_k") },
              { id: "h", label: "Hogares", color: C.p2, values: run.hs_households_k, ...band("hs_households_k") },
            ]} />
        </div>
        <div>
          <h3 className="vizPanelTitle">Jóvenes que se emancipan (miles) y pisos de alquiler de mercado (miles)</h3>
          <FanChart years={model.years} unit="k" digits={0} ariaLabel="Jóvenes emancipados y oferta de alquiler frente a la línea base"
            series={[
              { id: "e", label: "Jóvenes emancipados", color: C.p4, values: run.hs_emancipated_k, emphasis: true, ...band("hs_emancipated_k") },
              ...(capOn ? [{ id: "r", label: "Pisos de alquiler", color: C.p1, values: run.hs_rental_stock_k, ...band("hs_rental_stock_k") }] : []),
            ]} />
        </div>
      </div>
    </figure>
  );
}

const share = (rent, net) => (rent / (net / 12)) * 100;

function HousingPeople({ model, run, ensemble, t, horizon, levers }) {
  const H = model.housing;
  const c1 = H.cases.p1;
  const c2 = H.cases.p2_renter;
  const b2 = H.cases.p2_buyer;
  const capOn = Boolean(levers.capCov && levers.capCut);
  const rentLine = (label, key, base, net) => {
    const v = run[key][t];
    const b = ensemble.bands[key];
    return (
      <li key={key}>
        {label}: <strong>{Math.abs(v) < 0.5 ? "sin cambio" : `${signed(v, "eur", 0)} al mes`}</strong>
        {Math.abs(v) >= 0.5 ? <span className="sim__muted"> ({signed(b.lo[t], "eur", 0)} a {signed(b.hi[t], "eur", 0)})</span> : null}; esfuerzo del{" "}
        {share(base, net).toLocaleString("es-ES", { maximumFractionDigits: 1 })} % al {share(base + v, net).toLocaleString("es-ES", { maximumFractionDigits: 1 })} % de la renta neta
      </li>
    );
  };
  const rentFactor = run.hs_rent_paid[t];
  const cells = H.effort_cells.filter((c) => c.burden_mean);
  const label = { "16-29": "16–29", "30-44": "30–44", "45-64": "45–64", "65+": "65 o más" };
  return (
    <figure className="vizFigure sim__figure" id="personas-vivienda">
      <h2>Vivienda: qué les pasa a los casos 1 y 2, en {horizon}</h2>
      <p className="vizFigure__dek">
        Alquileres del SERPAVI de {c1.rent_year} y rentas netas de la página de <a href="/visualizaciones/vivienda/">vivienda</a>, a precios de entonces. Un
        contrato nuevo es lo que paga quien busca piso; quien ya tiene contrato se acerca al mercado a medida que renueva.
      </p>
      <div className="sim__people">
        <div className="sim__person" style={{ "--tone": C.p1 }}>
          <h3>Caso 1 · 25–34 años, vive sola de alquiler en Madrid ({fmt(c1.rent_month, "eur")} al mes)</h3>
          <ul className="sim__list">
            {capOn ? rentLine("Si encuentra un piso con tope", "p1_rent_cov_month", c1.rent_month, c1.net_year) : null}
            {rentLine(capOn ? "Si busca fuera del tope" : "Contrato nuevo", "p1_rent_unc_month", c1.rent_month, c1.net_year)}
            {capOn ? (
              <li>
                Pisos de alquiler de mercado: <strong>{signed(run.hs_rental_stock_k[t], "k", 0)}</strong> en toda España (
                {signed((run.hs_rental_stock_k[t] / H.renters_k) * 100, "pct", 1)} de la oferta).
              </li>
            ) : null}
          </ul>
        </div>
        <div className="sim__person" style={{ "--tone": C.p2 }}>
          <h3>Caso 2 · pareja con dos hijos, alquila en el área de Madrid ({fmt(c2.rent_month, "eur")} al mes)</h3>
          <ul className="sim__list">
            {capOn ? rentLine("Si encuentra un piso con tope", "p2r_rent_cov_month", c2.rent_month, c2.net_year) : null}
            {rentLine(capOn ? "Si busca fuera del tope" : "Contrato nuevo", "p2r_rent_unc_month", c2.rent_month, c2.net_year)}
          </ul>
        </div>
        <div className="sim__person" style={{ "--tone": C.p2 }}>
          <h3>Caso 2 · la misma pareja compra un piso de {fmt(b2.home_price, "eur")} en Madrid</h3>
          <ul className="sim__list">
            <li>
              Precio: <strong>{signed(run.hs_price[t] * b2.home_price, "eur", 0)}</strong>; entrada e impuestos necesarios:{" "}
              <strong>{signed(run.p2b_upfront_eur[t], "eur", 0)}</strong> (hoy {fmt(b2.upfront, "eur")}, {String(b2.upfront_years_income).replace(".", ",")} años de renta neta).
            </li>
            <li>
              Cuota de la hipoteca: <strong>{signed(run.p2b_payment_month[t], "eur", 0)} al mes</strong> (hoy {fmt(b2.cost_month, "eur")}, al {String(b2.rate_pct).replace(".", ",")} % y {b2.years} años).
            </li>
            <li className="sim__muted">
              Sus sueldos brutos ({fmt(c2.gross_year, "eur")}) dan {(((b2.home_price * b2.ltv_pct) / 100) / c2.gross_year).toLocaleString("es-ES", { maximumFractionDigits: 2 })} veces la renta con una hipoteca del {b2.ltv_pct} %: un LTI de 4,5 los obliga a
              poner más entrada.
            </li>
          </ul>
        </div>
      </div>
      <details className="vizTable" open={capOn || Math.abs(rentFactor) > 0.005}>
        <summary>Esfuerzo de los hogares de alquiler de mercado por edad (Encuesta de Condiciones de Vida {H.effort_year})</summary>
        <p className="sim__muted">
          Gasto en vivienda sobre la renta disponible, media de cada celda con su intervalo del 95 %, y cómo quedaría con el cambio medio del alquiler que pagan
          los inquilinos de mercado en {horizon} ({signed(rentFactor * 100, "pct", 1)}, contando renovaciones). Quien tiene hipoteca no cambia: su cuota está
          fijada; quien es propietario sin hipoteca, tampoco.
        </p>
        <div className="vizTable__scroll">
          <table className="sim__table">
            <thead>
              <tr>
                <th scope="col">Edad de la persona de referencia</th>
                <th scope="col">España, alquiler de mercado</th>
                <th scope="col">España, con el escenario</th>
                <th scope="col">Comunidad de Madrid, alquiler de mercado</th>
                <th scope="col">Madrid, con el escenario</th>
              </tr>
            </thead>
            <tbody>
              {["16-29", "30-44", "45-64", "65+"].map((age) => {
                const es = cells.find((c) => c.geo === "ES" && c.age === age && c.tenure === "RENT_MKT");
                const md = cells.find((c) => c.geo === "ES30" && c.age === age && c.tenure === "RENT_MKT");
                const cellText = (c) => (c ? `${c.burden_mean[0].toLocaleString("es-ES")} % (${c.burden_mean[1].toLocaleString("es-ES")}–${c.burden_mean[2].toLocaleString("es-ES")})` : "muestra pequeña");
                const scen = (c) => (c ? `${(c.burden_mean[0] * (1 + rentFactor)).toLocaleString("es-ES", { maximumFractionDigits: 1 })} %` : "—");
                return (
                  <tr key={age}>
                    <th scope="row">{label[age]}</th>
                    <td>{cellText(es)}</td>
                    <td>{scen(es)}</td>
                    <td>{cellText(md)}</td>
                    <td>{scen(md)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

function VotesBlock({ model, levers }) {
  const groups = [
    [levers.reval, "reval", "Revalorización de las pensiones"],
    [levers.age, "age", "Edad de jubilación"],
    [levers.contrib, "contrib", "Cotizaciones"],
    [levers.irpfAll || levers.irpfTop || levers.closure === "irpf", "irpf", "IRPF"],
    [levers.vatStd || levers.vatRed || levers.closure === "iva", "iva", "IVA"],
    [levers.corp, "corp", "Impuesto sobre Sociedades"],
    [levers.pubHomes, "publica", "Vivienda pública"],
    [levers.land, "suelo", "Suelo y licencias"],
    [levers.capCov && levers.capCut, "tope", "Tope y regulación del alquiler"],
    [levers.tourCut, "turistico", "Viviendas turísticas"],
    [levers.ltvCap || levers.ltiCap, "credito", "Hipotecas y avales"],
  ];
  const active = groups.filter(([on, id]) => on && model.votes[id]?.votes.length).map(([, id, title]) => [id, title]);
  const shown = active.length ? active : [["reval", "Revalorización de las pensiones"]];
  return (
    <figure className="vizFigure sim__figure" id="votos">
      <h2>Cómo votaron los partidos en el Congreso sobre estas palancas</h2>
      <p className="vizFigure__dek">
        Votaciones de la XV legislatura relacionadas con las palancas que has movido. Muchas son decretos que mezclan varias medidas: el voto no es una
        cifra y el simulador no lo usa como escenario. Cada votación enlaza su registro oficial.
      </p>
      {shown.map(([lever, title]) => {
        const v = model.votes[lever];
        return (
          <div key={lever} className="sim__votes">
            <h3 className="vizPanelTitle">{title}</h3>
            <div className="vizTable__scroll">
              <table className="sim__table sim__table--votes">
                <thead>
                  <tr>
                    <th scope="col">Votación</th>
                    {v.party_order.map((p) => (
                      <th scope="col" key={p}>{v.party_labels[p]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {v.votes.map((vote) => (
                    <tr key={vote.id}>
                      <th scope="row">
                        <a href={vote.url} target="_blank" rel="noopener noreferrer">{vote.summary}</a>
                        <span className="sim__muted"> · {vote.date}, {vote.approved ? "aprobada" : "rechazada"}</span>
                      </th>
                      {v.party_order.map((p) => (
                        <td key={p} className={`vote vote--${vote.parties[p] || "?"}`}>{VOTE_LABEL[vote.parties[p]] || "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
      <p className="sim__muted">
        Más votaciones y su resumen por partido en el <a href="/citizen/vota/">test de voto</a>.
      </p>
    </figure>
  );
}

export { ClosureFigure };
