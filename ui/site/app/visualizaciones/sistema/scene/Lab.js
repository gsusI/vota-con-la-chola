"use client";

import { useEffect, useMemo, useState } from "react";
import { SeriesTable } from "../../components/Figure";
import FanChart, { fmt } from "../FanChart";
import { DEFAULT_LEVERS, LAYERS, applyLayer, centralParams, decodeState, encodeState, mainDriver, quintileImpact, runEnsemble, simulate } from "../engine.mjs";
import { Avatar, Icon, PAL } from "./art";
import Scene from "./Scene";
import Controls, { CLOSURE_CHOICES } from "./Controls";
import { Ladder, Neighbours } from "./People";
import Chain from "./Chain";
import { EdgeCard, LAYER_LABELS, PARAM_LABELS, VotesBlock } from "./parts";
import "../sistema.css";
import "./scene.css";

const signed = (v, unit, digits = 1) => {
  const d = unit === "eur" || unit === "k" ? 0 : digits;
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return (r > 0 ? "+" : r < 0 ? "−" : "") + fmt(Math.abs(r), unit, digits);
};

const COST_LEVERS = ["reval", "age", "contrib", "irpfAll", "irpfTop", "vatStd", "vatRed", "corp", "rateShock", "pubHomes", "land"];

function Timeline({ years, year, setYear, playing, setPlaying }) {
  return (
    <div className="timeline">
      <button type="button" className="timeline__play" onClick={() => setPlaying(!playing)} aria-label={playing ? "Pausar" : "Ver de 2025 a 2050"}>
        {playing ? "❚❚" : "▶"}
      </button>
      <input type="range" min={years[0]} max={years.at(-1)} step={1} value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Año" />
      <span className="timeline__ticks" aria-hidden="true">
        {years.filter((y) => y % 5 === 0).map((y) => (
          <span key={y}>{y}</span>
        ))}
      </span>
    </div>
  );
}

/** Same lever, four ways to pay: debt, two neighbours and jobs, central value and 5-95 % range. */
export function WhoPays({ model }) {
  const t35 = model.years.indexOf(2035);
  const tEnd = model.years.length - 1;
  const cols = useMemo(
    () =>
      CLOSURE_CHOICES.map((c) => {
        const e = runEnsemble(model, { ...DEFAULT_LEVERS, reval: 1, closure: c.id }, { draws: 160 });
        const pick = (key, t) => ({ v: e.central[key][t], lo: e.bands[key].lo[t], hi: e.bands[key].hi[t] });
        return { ...c, debt: pick("debt_dev_pp", tEnd), p1: pick("p1_month", t35), p4: pick("p4_month", t35), jobs: pick("employment_k", t35) };
      }),
    [model, t35, tEnd],
  );
  const rows = [
    { key: "debt", head: <Icon name="debt" size={34} color={PAL.yellow} />, title: "Deuda extra en 2050", unit: "pp" },
    { key: "p4", head: <Avatar who="p4" mood="up" size={52} />, title: "Carmen, pensionista, en 2035", unit: "eur", suffix: " al mes" },
    { key: "p1", head: <Avatar who="p1" mood="down" size={52} />, title: "Lucía, 25–34 años, en 2035", unit: "eur", suffix: " al mes" },
    { key: "jobs", head: <Icon name="people" size={34} color={PAL.blue} />, title: "Empleo en 2035", unit: "k" },
  ];
  return (
    <div className="whopays">
      <div className="whopays__cols">
        <span />
        {cols.map((c) => (
          <span key={c.id} className="whopays__col">
            <Icon name={c.icon} size={30} />
            {c.label}
          </span>
        ))}
      </div>
      {rows.map((r) => (
        <div className="whopays__row" key={r.key}>
          <span className="whopays__head">
            {r.head}
            <span>{r.title}</span>
          </span>
          {cols.map((c) => {
            const d = c[r.key];
            const zero = Math.abs(d.v) < (r.unit === "pp" ? 0.05 : 0.5);
            const tone = zero ? "" : (r.key === "debt" ? d.v < 0 : d.v > 0) ? " is-good" : " is-bad";
            return (
              <span key={c.id} className={`whopays__cell${tone}`}>
                <b>{zero ? "0" : signed(d.v, r.unit, 1)}{zero ? "" : r.suffix || ""}</b>
                {zero ? null : (
                  <small>
                    {signed(d.lo, r.unit, 1)} a {signed(d.hi, r.unit, 1)}
                  </small>
                )}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export default function Lab({ model, composition }) {
  const [levers, setLeversState] = useState(DEFAULT_LEVERS);
  const [debates, setDebates] = useState({});
  const [layer, setLayer] = useState("segunda_ronda");
  const [year, setYear] = useState(2035);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const { levers: l, debates: d, extra } = decodeState(window.location.hash);
    setLeversState(l);
    setDebates(d);
    if (extra.y && model.years.includes(Number(extra.y))) setYear(Number(extra.y));
    setReady(true);
  }, [model]);
  useEffect(() => {
    if (!ready) return;
    const hash = encodeState(levers, debates, year !== 2035 ? { y: year } : {});
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash ? `#${hash}` : ""}`);
  }, [levers, debates, year, ready]);
  useEffect(() => {
    if (!playing) return undefined;
    const id = setInterval(() => {
      setYear((y) => {
        if (y >= model.years.at(-1)) {
          setPlaying(false);
          return y;
        }
        return y + 1;
      });
    }, 420);
    return () => clearInterval(id);
  }, [playing, model]);

  const setLever = (key, value) => setLeversState((prev) => ({ ...prev, [key]: value }));
  const setLevers = (patch) => {
    setLeversState({ ...DEFAULT_LEVERS, ...patch });
    setYear(2035);
  };
  const ensemble = useMemo(() => runEnsemble(model, levers, { debates, layer }), [model, levers, debates, layer]);
  const run = ensemble.central;
  const t = model.years.indexOf(year);
  const tEnd = model.years.length - 1;
  const layerParams = useMemo(() => applyLayer(model, centralParams(model, debates), layer), [model, debates, layer]);
  const quintiles = quintileImpact(model, run, t, layerParams);
  const edgeById = useMemo(() => Object.fromEntries(model.edges.map((e) => [e.id, e])), [model]);
  const needsClosure = COST_LEVERS.some((k) => levers[k]);
  const base = model.baseline;
  const band = (key) => ({ lo: ensemble.bands[key].lo, hi: ensemble.bands[key].hi });

  const layered = useMemo(
    () => LAYERS.map((ly) => {
      const p = applyLayer(model, centralParams(model, debates), ly);
      return { layer: ly, run: simulate(model, levers, p), params: p };
    }),
    [model, levers, debates],
  );
  const outputs = [
    { key: "debt_dev_pp", label: "Deuda extra en 2050", unit: "pp", digits: 1, t: tEnd },
    { key: "pension_gross_pp", label: `Gasto extra en pensiones en ${year}`, unit: "pp", digits: 2, t },
    { key: "p1_month", label: `Lucía en ${year}, al mes`, unit: "eur", digits: 0, t },
    { key: "p4_month", label: `Carmen en ${year}, al mes`, unit: "eur", digits: 0, t },
    { key: "employment_k", label: `Empleo en ${year}`, unit: "k", digits: 0, t },
    { key: "q1", label: `Hogares del quinto con menos renta en ${year}, al mes`, unit: "eur", digits: 0, t, quintile: 0 },
    { key: "q5", label: `Hogares del quinto con más renta en ${year}, al mes`, unit: "eur", digits: 0, t, quintile: 4 },
  ];
  const valueOf = (o, r, p) => (o.quintile != null ? quintileImpact(model, r, o.t, p)[o.quintile].total : r[o.key][o.t]);
  const debateParams = Object.entries(model.params).filter(([, p]) => p.debate);
  const asPoints = (values) => model.years.map((y, i) => ({ year: y, value: Math.round(values[i] * 100) / 100 }));

  return (
    <div className="lab">
      <div className="lab__grid">
        <Controls levers={levers} setLever={setLever} setLevers={setLevers} needsClosure={needsClosure} compact />
        <div className="lab__stage">
          <Scene model={model} run={run} t={t} composition={composition} />
          <Timeline years={model.years} year={year} setYear={(y) => { setPlaying(false); setYear(y); }} playing={playing}
            setPlaying={(p) => { if (p && year >= model.years.at(-1)) setYear(model.years[0]); setPlaying(p); }} />
        </div>
      </div>

      <section className="lab__section" aria-labelledby="vecinos-title">
        <h2 id="vecinos-title">Qué les pasa a cuatro vecinos en {year}</h2>
        <p className="lab__dek">
          Euros al mes frente a la ley actual, a precios de {model.personas.p1.year}. Son los mismos casos tipo que en las demás páginas, con su misma renta;
          el cálculo es ilustrativo (IRPF con las reglas generales, sin deducciones por hijos ni autonómicas). Si mueves la vivienda, Lucía y Ana y Javi
          muestran aparte lo que cambiaría el alquiler de un piso nuevo en su zona (Madrid y su área metropolitana).
        </p>
        <Neighbours model={model} run={run} bands={ensemble.bands} t={t} levers={levers} />
      </section>

      <section className="lab__section" aria-labelledby="escalera-title">
        <h2 id="escalera-title">La escalera de rentas: quién gana y quién pierde en {year}</h2>
        <p className="lab__dek">
          Cada casa es un quinto de la población, de menos a más renta disponible. Euros al mes por hogar a precios de {model.start.year}: la carga legal de
          cada cambio antes de que nadie reaccione, repartida con los microdatos de la Encuesta de Condiciones de Vida {model.incidence.ecv.year} y, para el
          IVA, con el gasto de la Encuesta de Presupuestos Familiares {model.incidence.vat.year}. Lo que se paga con deuda no aparece: lo pagará alguien después.
        </p>
        <Ladder rows={quintiles} cuts={model.incidence.ecv.cuts_eq_income} />
        {["pubHomes", "land", "capCov", "capCut", "tourCut", "ltvCap", "ltiCap"].some((key) => levers[key]) ? (
          <p className="lab__note">
            La vivienda todavía no se reparte por quintiles: su efecto se ve en el alquiler de Lucía y de Ana y Javi y en la escena. Su coste público, si se paga
            con impuestos, sí aparece aquí.
          </p>
        ) : null}
      </section>

      <section className="lab__section" aria-labelledby="porque-title">
        <h2 id="porque-title">Por qué pasa, paso a paso</h2>
        <p className="lab__dek">
          Las relaciones que transmiten tu cambio en {year}, con lo fuerte que es la evidencia de cada una. Cada paso tiene una ficha con su número, su rango,
          su fuente y lo que la contradice.
        </p>
        <Chain run={run} t={t} levers={levers} edges={model.edges} selected={selected} onSelect={setSelected} />
        <EdgeCard edge={selected ? edgeById[selected] : null} />
      </section>

      <details className="lab__section lab__more">
        <summary>
          <h2>Los números, año a año</h2>
        </summary>
        <p className="lab__dek">
          Gris: la ley actual según el Ageing Report 2024, con el resto del presupuesto constante en % del PIB. Azul: tu escenario; la banda cubre del 5 % al
          95 % de 200 simulaciones con los parámetros dentro de sus rangos.
        </p>
        <div className="lab__charts">
          <div>
            <h3 className="vizPanelTitle">Gasto en pensiones públicas, % del PIB</h3>
            <FanChart years={model.years} unit="pct" ariaLabel="Gasto en pensiones, línea base y escenario"
              series={[
                { id: "b", label: "Ley actual", color: "#8b8a83", values: base.pension_pct, dash: true },
                { id: "s", label: "Escenario", color: PAL.blue, values: run.pension_pct, emphasis: true, ...band("pension_pct") },
              ]} />
          </div>
          <div>
            <h3 className="vizPanelTitle">Deuda pública, % del PIB</h3>
            <FanChart years={model.years} unit="pct" digits={0} ariaLabel="Deuda pública, línea base y escenario"
              series={[
                { id: "b", label: "Ley actual", color: "#8b8a83", values: base.debt_pct, dash: true },
                { id: "s", label: "Escenario", color: PAL.blue, values: run.debt_pct, emphasis: true, ...band("debt_pct") },
              ]} />
          </div>
          <div>
            <h3 className="vizPanelTitle">Empleo frente a la ley actual, miles de personas</h3>
            <FanChart years={model.years} unit="k" digits={0} ariaLabel="Empleo frente a la ley actual"
              series={[{ id: "e", label: "Escenario", color: PAL.blue, emphasis: true, values: run.employment_k, ...band("employment_k") }]} />
          </div>
        </div>
        <SeriesTable unit="pct" digits={2}
          series={[
            { id: "pb", label: "Pensiones, ley actual (% PIB)", points: asPoints(base.pension_pct) },
            { id: "ps", label: "Pensiones, escenario (% PIB)", points: asPoints(run.pension_pct) },
            { id: "db", label: "Deuda, ley actual (% PIB)", points: asPoints(base.debt_pct) },
            { id: "ds", label: "Deuda, escenario (% PIB)", points: asPoints(run.debt_pct) },
          ]} />
      </details>

      <details className="lab__section lab__more">
        <summary>
          <h2>Qué parte es aritmética y qué parte es supuesto</h2>
        </summary>
        <p className="lab__dek">
          El mismo escenario sumando capas: solo la contabilidad, después la reacción de empresas, trabajadores y mercados, y por último los efectos sobre el
          PIB. La última columna dice si el signo aguanta todas las hipótesis y qué supuesto mueve más el resultado.
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
        <div className="lab__expert">
          <h3>Supuestos en disputa</h3>
          {debateParams.map(([name, p]) => (
            <label key={name} className="sim__select">
              <span>{PARAM_LABELS[name] || name}</span>
              <select value={debates[p.debate.id] ?? ""} onChange={(e) => setDebates((prev) => {
                const next = { ...prev };
                if (e.target.value === "") delete next[p.debate.id];
                else next[p.debate.id] = Number(e.target.value);
                return next;
              })}>
                <option value="">Valor central ({p.central.toLocaleString("es-ES")}) y todo el rango</option>
                {p.debate.schools.map((s, i) => (
                  <option key={s.label} value={i}>{s.label} ({s.central.toLocaleString("es-ES")})</option>
                ))}
              </select>
            </label>
          ))}
          <h3>Capas de certeza en la escena</h3>
          <div className="chips">
            {LAYERS.map((ly) => (
              <button key={ly} type="button" className={`chip${layer === ly ? " is-on" : ""}`} onClick={() => setLayer(ly)}>
                {ly === "contable" ? "Solo aritmética" : ly === "comportamiento" ? "+ Reacción" : "+ 2.ª ronda"}
              </button>
            ))}
          </div>
        </div>
      </details>

      <VotesBlock model={model} levers={levers} />
    </div>
  );
}
