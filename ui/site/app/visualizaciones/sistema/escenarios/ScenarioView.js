import { StaticRouteHero } from "../../../static-route-components";
import { withBasePath } from "../../../path-utils.mjs";
import { JsonLd, breadcrumbLd, faqLd } from "../../../seo";
import {
  CASE_METRICS, DRAWS, METRICS, PERSONAS_ES, SCENARIOS, SCENARIOS_PATH, SIM_PATH, YEARS,
  fmt, metricText, scenarioClosures, scenarioPath, scenarioResult, simulatorHref,
} from "../scenarios.mjs";

// Server-rendered landing page of one scenario: the question, the engine's answer with its range, who it reaches,
// how it is paid, the evidence and the votes. Everything is in the exported HTML; the simulator link preloads it.
const GRADE_TEXT = {
  A: "Evidencia fuerte: contabilidad, ley o datos de España",
  B: "Evidencia media: estudio sólido de otro país o meta-análisis",
  C: "Evidencia débil: consenso institucional sin estimación propia",
  D: "Supuesto: sin estimación publicada",
};
const VOTE_LABEL = { S: "Sí", N: "No", A: "Abst.", "?": "—" };
const QUINTILE_NAMES = ["El 20 % con menos renta", "Segundo quinto", "Tercer quinto", "Cuarto quinto", "El 20 % con más renta"];

const n = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });
const signedEur = (v) => fmt.eur(v);
const tiny = (v, unit) => Math.abs(v) < (unit === "pp" ? 0.005 : unit === "pct" ? 0.005 : 0.5);

// Net cost is shown as net revenue when the lever raises money (the label says which).
function metricView(id, r) {
  const m = METRICS[id];
  const flip = id === "cost" && r.revenue;
  const label = flip ? "Recaudación neta para las cuentas públicas, al año" : m.label;
  const side = (b) => (flip ? { v: -b.v, lo: -b.hi, hi: -b.lo, sameSign: b.sameSign } : b);
  return { id, label, years: YEARS.map((y) => ({ year: y, ...side(r[id][y]) })) };
}

function rangeText(id, b) {
  if (Math.abs(b.hi - b.lo) < 1e-9) return "sin rango: aritmética";
  return `${metricText(id, b.lo)} a ${metricText(id, b.hi)}`;
}

function caseRows(sc, r) {
  return sc.cases.map((id) => {
    const m = CASE_METRICS[id];
    const p = PERSONAS_ES[m.who];
    return { id, m, p, years: YEARS.map((y) => ({ year: y, ...r.cases[id][y] })) };
  });
}

export function scenarioFaqs(model, sc) {
  const r = scenarioResult(model, sc);
  const first = metricView(sc.metrics[0], r).years[0];
  const faqs = [
    {
      q: sc.question,
      a: `${r.lead} El rango del 5 % al 95 % de ${DRAWS} simulaciones en ${first.year} va de ${rangeText(sc.metrics[0], first)}.`,
    },
  ];
  const cases = caseRows(sc, r)
    .map((c) => `${c.p.name} (caso ${c.p.case}), ${c.m.label}: ${tiny(c.years[0].v) ? "sin cambio" : signedEur(c.years[0].v)}${c.m.once ? "" : " al mes"}`)
    .join("; ");
  faqs.push({
    q: "¿A quién le afecta?",
    a: `En 2035, frente a la ley actual y a precios de ${model.personas.p1.year}: ${cases}. Son casos tipo con su renta real, no la media de España.${
      sc.quintiles && r.quintiles ? ` Por renta, la carga legal es del ${n(-r.quintiles[0].pctDisposable, 2)} % de la renta disponible en el 20 % con menos renta y del ${n(-r.quintiles[4].pctDisposable, 2)} % en el 20 % con más.` : ""
    }`,
  });
  faqs.push({
    q: "¿Es una predicción?",
    a: `No. Es un escenario de un modelo pequeño de forma reducida que calcula diferencias frente a la ley actual (línea base del Ageing Report 2024 y la proyección de hogares del INE), con cada parámetro sorteado dentro de su rango. ${sc.caveat || "Cada relación tiene una ficha con su fuente, su rango y lo que la contradice."}`,
  });
  const votes = sc.votes.flatMap((key) => model.votes[key]?.votes || []);
  if (votes.length) {
    const last = [...votes].sort((a, b) => String(b.date).localeCompare(String(a.date)))[0];
    faqs.push({
      q: "¿Qué ha votado el Congreso sobre esto?",
      a: `Hay ${votes.length} votaciones de la XV legislatura relacionadas; la más reciente, del ${last.date}: «${last.summary}» (${last.approved ? "aprobada" : "rechazada"}). Muchas son decretos o iniciativas que mezclan varias medidas, así que el voto no equivale al escenario.`,
    });
  }
  return faqs;
}

function Evidence({ edge }) {
  const p = edge.parameter;
  return (
    <article className="scn__card">
      <p className="scn__grade">
        <span className={`edgeCard__grade edgeCard__grade--${edge.grade}`}>Evidencia {edge.grade}</span> {GRADE_TEXT[edge.grade]}
      </p>
      <p>{edge.note_es}</p>
      <p className="sim__muted">
        {p.unit}: <strong>{p.central.toLocaleString("es-ES")}</strong>
        {p.low !== p.high ? ` (rango ${p.low.toLocaleString("es-ES")} a ${p.high.toLocaleString("es-ES")})` : ""}
      </p>
      <ul className="scn__sources">
        {edge.sources.map((s) => (
          <li key={s.url + s.locator}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">{s.authors_year}</a>, {s.title} ({s.locator}; {s.country}).
          </li>
        ))}
      </ul>
      {edge.contrary_evidence?.length ? (
        <>
          <p className="scn__sub">Lo que apunta en otra dirección</p>
          <ul className="scn__sources">
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

export default function ScenarioView({ model, sc }) {
  const r = scenarioResult(model, sc);
  const closures = scenarioClosures(model, sc);
  const metrics = sc.metrics.map((id) => metricView(id, r));
  const cases = caseRows(sc, r);
  const edgeById = Object.fromEntries(model.edges.map((e) => [e.id, e]));
  const edges = sc.edges.map((id) => edgeById[id]).filter(Boolean);
  const faqs = scenarioFaqs(model, sc);
  const path = scenarioPath(sc);
  const crumbs = [
    { name: "Visualizaciones", path: "/visualizaciones/" },
    { name: "Simulador", path: SIM_PATH },
    { name: "Escenarios", path: SCENARIOS_PATH },
    { name: sc.short, path },
  ];
  const siblings = SCENARIOS.filter((s) => s.slug !== sc.slug);
  const groups = [...new Set(SCENARIOS.map((s) => s.group))];
  const debateEdge = r.debate ? edgeById[r.debate.edge] : null;
  const debateMetric = r.debate ? METRICS[r.debate.metric] || CASE_METRICS[r.debate.metric] : null;
  const debateFlip = r.debate?.metric === "cost";

  return (
    <main className="shell vizArticle scn">
      <JsonLd data={[breadcrumbLd(crumbs), faqLd(faqs)]} />
      <nav className="scn__crumbs" aria-label="Ruta">
        {crumbs.slice(0, -1).map((c) => (
          <span key={c.path}>
            <a href={withBasePath(c.path)}>{c.name}</a> ›{" "}
          </span>
        ))}
        <span aria-current="page">{sc.short}</span>
      </nav>
      <StaticRouteHero
        eyebrow={`Simulador · ${sc.group}`}
        title={sc.question}
        summary={`${r.lead} Escenario de un modelo con supuestos visibles, no una predicción.`}
        actions={[
          { href: simulatorHref(sc), label: "Abrir este escenario en el simulador" },
          { href: "#fichas", label: "De dónde salen los números" },
          { href: SCENARIOS_PATH, label: "Otros escenarios" },
        ]}
      />

      <section className="vizFigure" aria-labelledby="resultado">
        <h2 id="resultado">El resultado, frente a la ley actual</h2>
        <p className="vizFigure__dek">
          Valor central y, debajo, el rango del 5 % al 95 % de {DRAWS} simulaciones que sortean todos los parámetros dentro de su rango, en 2035 y en 2050.
          Desde {model.policy_start}, con todo lo demás igual{r.cost && sc.metrics.includes("debt") ? " y la diferencia pagada con deuda" : ""}.
        </p>
        <div className="scn__stats">
          {metrics.map((m) => (
            <div className="vizStat scn__stat" key={m.id}>
              <span className="vizStat__label">{m.label}</span>
              <span className="scn__years">
                {m.years.map((y) => (
                  <span key={y.year}>
                    <small>{y.year}</small>
                    <strong className="vizStat__value">{metricText(m.id, y.v)}</strong>
                    <span className="vizStat__note">
                      {rangeText(m.id, y)}
                      {y.sameSign < 0.95 && !tiny(y.v, METRICS[m.id].unit) ? ` · el signo se mantiene en el ${Math.round(y.sameSign * 100)} % de las simulaciones` : ""}
                    </span>
                  </span>
                ))}
              </span>
            </div>
          ))}
        </div>
        {sc.caveat ? <p className="scn__caveat"><strong>Lo que queda abierto.</strong> {sc.caveat}</p> : null}
        <p>
          <a className="scn__cta" href={withBasePath(simulatorHref(sc))}>Abrir este escenario en el simulador y cambiarlo →</a>
        </p>
      </section>

      <section className="vizFigure" aria-labelledby="casos">
        <h2 id="casos">Qué les pasa a {cases.length > 1 ? `${cases.length} casos tipo` : "un caso tipo"}</h2>
        <p className="vizFigure__dek">
          Euros {cases.some((c) => !c.m.once) ? "al mes " : ""}frente a la ley actual, a precios de {model.personas.p1.year}. Son los mismos casos tipo que en las
          demás páginas, con su renta real{sc.group === "Vivienda" || sc.group === "Población" ? "; el alquiler es el de un piso nuevo en su zona (Madrid y su área metropolitana)" : ""}.
          {closures ? " Aquí, pagado con deuda: la tabla siguiente cambia quién paga." : ""}
        </p>
        <div className="vizTable__scroll">
          <table className="sim__table">
            <thead>
              <tr>
                <th scope="col">Caso</th>
                <th scope="col">Qué se mide</th>
                {YEARS.map((y) => <th scope="col" key={y}>{y}</th>)}
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <th scope="row">
                    {c.p.name} <span className="sim__muted">(caso {c.p.case}: {c.p.who})</span>
                  </th>
                  <td>{c.m.label}</td>
                  {c.years.map((y) => (
                    <td key={y.year}>
                      <strong>{tiny(y.v) ? "0 €" : signedEur(y.v)}</strong>
                      {Math.abs(y.hi - y.lo) >= 0.5 ? <span className="sim__muted"><br />{signedEur(y.lo)} a {signedEur(y.hi)}</span> : null}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {r.quintiles ? (
          <>
            <h3 className="vizPanelTitle">Por nivel de renta, en 2035</h3>
            <p className="sim__muted">
              Carga legal antes de que nadie reaccione, por hogar y mes y en % de la renta disponible de cada quinto de la población (microdatos de la Encuesta
              de Condiciones de Vida {model.incidence.ecv.year}; el IVA, con el gasto de la Encuesta de Presupuestos Familiares {model.incidence.vat.year}).
            </p>
            <div className="vizTable__scroll">
              <table className="sim__table">
                <thead>
                  <tr>
                    <th scope="col">Quinto</th>
                    <th scope="col">Euros al mes por hogar</th>
                    <th scope="col">% de la renta disponible</th>
                  </tr>
                </thead>
                <tbody>
                  {r.quintiles.map((q, i) => (
                    <tr key={q.q}>
                      <th scope="row">{QUINTILE_NAMES[i]}</th>
                      <td>{signedEur(q.total)}</td>
                      <td>{fmt.pp(q.pctDisposable, 2)} %</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      {closures ? (
        <section className="vizFigure" aria-labelledby="cierre">
          <h2 id="cierre">{r.revenue ? "Qué pasa según en qué se use lo recaudado" : "Quién lo paga: cuatro formas de pagarlo"}</h2>
          <p className="vizFigure__dek">
            {r.revenue
              ? "El dinero que entra puede reducir deuda o devolverse bajando otro impuesto; cada fila ajusta ese impuesto cada año lo justo para que el saldo no cambie."
              : "Cada fila sube un impuesto cada año lo justo para cubrir el coste; con deuda no paga nadie hoy y crecen la deuda y sus intereses."}{" "}
            Valor central y rango del 5 % al 95 % de 160 simulaciones.
          </p>
          <div className="vizTable__scroll">
            <table className="sim__table">
              <thead>
                <tr>
                  <th scope="col">{r.revenue ? "Uso" : "Cómo se paga"}</th>
                  <th scope="col">Cambio del impuesto en 2035</th>
                  <th scope="col">Deuda extra en 2050</th>
                  <th scope="col">Lucía en 2035, al mes</th>
                  <th scope="col">Carmen en 2035, al mes</th>
                  <th scope="col">Empleo en 2035</th>
                  <th scope="col">Simulador</th>
                </tr>
              </thead>
              <tbody>
                {closures.map((c) => (
                  <tr key={c.id}>
                    <th scope="row">{c.label}</th>
                    <td>{c.rate == null ? "—" : `${fmt.pp(c.rate, 2)} pp`}</td>
                    {[["debt", "pp"], ["p1", "eur"], ["p4", "eur"], ["jobs", "k"]].map(([key, unit]) => {
                      const b = c[key];
                      const f = (v) => (unit === "pp" ? `${fmt.pp(v, 1)} pp` : unit === "k" ? fmt.k(v) : signedEur(v));
                      return (
                        <td key={key}>
                          <strong>{tiny(b.v, unit) ? "0" : f(b.v)}</strong>
                          {tiny(b.v, unit) || Math.abs(b.hi - b.lo) < (unit === "pp" ? 0.05 : 0.5) ? null : <span className="sim__muted"><br />{f(b.lo)} a {f(b.hi)}</span>}
                        </td>
                      );
                    })}
                    <td><a href={withBasePath(c.href)}>Ver</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {r.debate ? (
        <section className="vizProse" aria-labelledby="disputa">
          <h2 id="disputa">El supuesto en disputa</h2>
          <p>
            {debateEdge?.note_es} El mismo escenario en {r.debate.year} con el valor central de cada escuela ({debateMetric.label}
            {debateFlip ? ", en positivo si recauda" : ""}):
          </p>
          <ul>
            {r.debate.schools.map((s) => {
              const v = debateFlip ? -s.v : s.v;
              return (
                <li key={s.label}>
                  {s.label} ({s.central.toLocaleString("es-ES")}): <strong>{CASE_METRICS[r.debate.metric] ? signedEur(v) : metricText(r.debate.metric, v)}</strong>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section className="vizProse" id="fichas" aria-labelledby="fichas-title">
        <h2 id="fichas-title">De dónde salen los números ({edges.length} fichas)</h2>
        <p>
          Cada relación que mueve este escenario, con su valor, su rango, su grado de evidencia, sus fuentes y lo que la contradice. El catálogo completo y las
          pruebas del modelo están en el <a href={withBasePath(`${SIM_PATH}#fichas`)}>simulador</a>.
        </p>
      </section>
      <div className="scn__cards">
        {edges.map((e) => <Evidence key={e.id} edge={e} />)}
      </div>

      {sc.votes.some((key) => model.votes[key]?.votes.length) ? (
        <section className="vizFigure" aria-labelledby="votos">
          <h2 id="votos">Cómo votaron los partidos en el Congreso</h2>
          <p className="vizFigure__dek">
            Votaciones de la XV legislatura relacionadas con esta palanca. Muchas son decretos o iniciativas que mezclan varias medidas: el voto no es una cifra
            y no equivale al escenario. Cada votación enlaza su registro oficial.
          </p>
          {sc.votes.map((key) => {
            const v = model.votes[key];
            if (!v?.votes.length) return null;
            return (
              <div className="vizTable__scroll" key={key}>
                <table className="sim__table sim__table--votes">
                  <thead>
                    <tr>
                      <th scope="col">Votación</th>
                      {v.party_order.map((p) => <th scope="col" key={p}>{v.party_labels[p]}</th>)}
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
            );
          })}
          <p className="sim__muted">
            Más votaciones y su resumen por partido en el <a href={withBasePath("/citizen/vota/")}>test de voto</a>.
          </p>
        </section>
      ) : null}

      <section className="vizProse" aria-labelledby="faq">
        <h2 id="faq">Preguntas frecuentes</h2>
        {faqs.map((f) => (
          <div key={f.q} className="scn__faq">
            <h3>{f.q}</h3>
            <p>{f.a}</p>
          </div>
        ))}
      </section>

      <section className="vizProse" aria-labelledby="otros">
        <h2 id="otros">Otros escenarios</h2>
        {groups.map((g) => (
          <div key={g}>
            <h3>{g}</h3>
            <ul>
              {siblings.filter((s) => s.group === g).map((s) => (
                <li key={s.slug}><a href={withBasePath(scenarioPath(s))}>{s.question}</a></li>
              ))}
            </ul>
          </div>
        ))}
        <p className="sim__muted">
          Modelo y datos: <a href={withBasePath("/visualizaciones/data/sistema.json")}>sistema.json</a> · método, simplificaciones y fuentes en el{" "}
          <a href={withBasePath(`${SIM_PATH}#metodo`)}>simulador</a>. Modelo generado el {String(model.generated_at).slice(0, 10)}.
        </p>
      </section>
    </main>
  );
}
