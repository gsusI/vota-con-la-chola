"use client";

import { useEffect, useMemo, useState } from "react";
import { SeriesTable } from "../components/Figure";
import FanChart, { fmt } from "./FanChart";
import CausalMap from "./CausalMap";
import { DEFAULT_LEVERS, LAYERS, applyLayer, centralParams, decodeState, encodeState, mainDriver, runEnsemble, simulate } from "./engine.mjs";
import "./sistema.css";

const C = { base: "#8b8a83", scen: "#2a78d6", p1: "#eb6834", p4: "#1baf7a" };

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
  return (
    <div className="closureFig" role="table" aria-label="Subir las pensiones un punto sobre el IPC: resultados según cómo se pague">
      {panels.map((panel) => {
        const vals = rows.flatMap((r) => [r[panel.key].lo, r[panel.key].hi, 0]);
        const lo = Math.min(...vals);
        const hi = Math.max(...vals);
        const sx = (v) => ((v - lo) / (hi - lo || 1)) * 100;
        return (
          <div className="closureFig__panel" key={panel.key} role="rowgroup">
            <h3>{panel.title}</h3>
            {rows.map((r) => {
              const d = r[panel.key];
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
  const base = model.baseline;
  const t = model.years.indexOf(horizon);
  const tEnd = model.years.length - 1;
  const moved = levers.reval || levers.age || levers.contrib || levers.migration !== "base" || levers.rateShock;

  // Same outputs under each certainty layer (central parameters), to show what is arithmetic and what is assumption.
  const layered = useMemo(
    () =>
      LAYERS.map((ly) => ({ layer: ly, run: simulate(model, levers, applyLayer(model, centralParams(model, debates), ly)) })),
    [model, levers, debates],
  );
  const outputs = [
    { key: "debt_dev_pp", label: "Deuda extra en 2050", unit: "pp", digits: 1, t: tEnd },
    { key: "pension_gross_pp", label: `Gasto extra en pensiones en ${horizon}`, unit: "pp", digits: 2, t },
    { key: "p4_month", label: `Caso 4 en ${horizon}, al mes`, unit: "eur", digits: 0, t },
    { key: "p1_month", label: `Caso 1 en ${horizon}, al mes`, unit: "eur", digits: 0, t },
    { key: "employment_k", label: `Empleo en ${horizon}`, unit: "k", digits: 0, t },
  ];
  const debateParams = Object.entries(model.params).filter(([, p]) => p.debate);
  const closureRate = levers.closure === "cotizaciones" ? "closure_contrib_pp" : levers.closure === "iva" ? "closure_vat_pp" : null;
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
          <Slider id="lv-contrib" label="Cotización extra para pensiones" value={levers.contrib} min={-1} max={2} step={0.25} unit="pp"
            onChange={set("contrib")} hint={`Como el MEI, que la ley ya sube hasta ${String(model.mei_2029 ?? 1.2).replace(".", ",")} pp en 2029 (incluido en la línea base).`} />
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
              {closureRate === "closure_contrib_pp" ? "Subida de cotización necesaria, pp de la base" : closureRate ? "Subida del IVA general necesaria, pp" : "Deuda extra, pp del PIB"}
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
        <h2>Qué les pasa a dos casos tipo, en {horizon}</h2>
        <p className="vizFigure__dek">
          Euros al mes a precios de {model.personas.p1.year}, frente a la ley actual. Son los casos 1 y 4 de las demás páginas, con su misma renta: el cálculo
          es ilustrativo y no incluye lo que cambie en vivienda o servicios.
        </p>
        <div className="sim__people">
          {[
            { id: "p4", color: C.p4, title: "Caso 4 · pensionista de 65 años o más, vive solo, casa pagada", base: `Pensión de ${fmt(model.personas.p4.gross, "eur")} brutos al año (${fmt(model.personas.p4.net / 12, "eur")} netos al mes)` },
            { id: "p1", color: C.p1, title: "Caso 1 · 25–34 años, asalariada, vive sola de alquiler en Madrid", base: `Sueldo de ${fmt(model.personas.p1.gross, "eur")} brutos al año (${fmt(model.personas.p1.net / 12, "eur")} netos al mes)` },
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
                const same = ensemble.bands[o.key].sameSign[o.t];
                const central = run[o.key][o.t];
                const driver = Math.abs(central) > 1e-6 ? mainDriver(model, ensemble, o.key, o.t) : null;
                return (
                  <tr key={o.key}>
                    <th scope="row">{o.label}</th>
                    {layered.map((l) => (
                      <td key={l.layer}>{signed(l.run[o.key][o.t], o.unit, o.digits)}</td>
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

function VotesBlock({ model, levers }) {
  const active = [
    levers.reval ? ["reval", "Revalorización de las pensiones"] : null,
    levers.age ? ["age", "Edad de jubilación"] : null,
    levers.contrib ? ["contrib", "Cotizaciones"] : null,
  ].filter(Boolean);
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
