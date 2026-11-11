import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import { JsonLd, breadcrumbLd, pageMetadata } from "../../seo";
import { Legend } from "../components/Figure";
import IndicatorPanel from "./IndicatorPanel";
import VoteMatrix from "./VoteMatrix";
import MeasureEvidence from "./MeasureEvidence";
import GovernmentBlock from "./GovernmentBlock";
import {
  DATA_PATH, PAGE_PATH, STANCE, VERDICT, count, dateEs, headline, ledger, measureName, num, pageDescription, pageTitle,
} from "./model.mjs";
import "./decisiones.css";

function load() {
  const data = readPublicJson(DATA_PATH, null);
  if (!data) throw new Error(`Missing ${DATA_PATH}`);
  return data;
}

export function generateMetadata() {
  const h = headline(load());
  return pageMetadata({ path: PAGE_PATH, title: pageTitle(h), description: pageDescription(h), type: "article" });
}

const C = { es: "#2a78d6", eu: "#52514e" };
const PANEL = {
  empleo: { indicator: "temporalidad", suffix: " %", notes: [{ from: 2021.95, to: 2022.25, label: "Reforma laboral (RDL 32/2021): fuera de nuestros datos de voto", short: "Reforma laboral (fuera)" }] },
  sanidad: { indicator: "espera_quirurgica", suffix: "", notes: [{ from: 2020, to: 2021, label: "Covid", short: "Covid" }] },
};

function PartyLedger({ data }) {
  const rows = ledger(data);
  const verdictParts = (cell, stance) => {
    const parts = Object.entries(cell[stance] || {}).map(([v, list]) => `${list.length} ${VERDICT[v]?.short || v}`);
    return parts.length ? ` (${parts.join(", ")})` : "";
  };
  return (
    <div className="vizTable__scroll decLedger">
      <table>
        <caption className="decSr">Medidas por partido y ámbito: a favor, en contra y abstención, con su evaluación</caption>
        <thead>
          <tr>
            <th scope="col">Partido</th>
            {data.domains.map((d) => (
              <th scope="col" key={d.id}>
                {d.label} ({d.measures})
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.party}>
              <th scope="row">{row.label}</th>
              {data.domains.map((d) => {
                const cell = row.domains[d.id];
                if (!cell.total) return <td key={d.id} className="decMuted">sin escaño o sin voto</td>;
                return (
                  <td key={d.id}>
                    {["backed", "opposed", "abstained"].map((s) =>
                      count(cell, s) ? (
                        <span key={s} className="decVoteLine">
                          <span className="decDot" style={{ background: STANCE[s].color }} aria-hidden="true" />
                          {STANCE[s].short} {count(cell, s)}
                          <span className="decMuted">{verdictParts(cell, s)}</span>
                        </span>
                      ) : null,
                    )}
                    {cell.decisive.length ? <span className="decVoteLine decMuted">decisivo en {cell.decisive.length}</span> : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DecisionesPage() {
  const data = load();
  const h = headline(data);
  const labels = data.party_labels;
  const numbering = Object.fromEntries(data.measures.map((m, i) => [m.measure_id, i + 1]));
  const byDomain = Object.fromEntries(data.domains.map((d) => [d.id, data.measures.filter((m) => m.domains.includes(d.id))]));
  const governing = data.parties.filter((p) => p.governing);
  const hs = data.health_state || {};
  const pos = data.positions || {};
  const stanceLegend = ["backed", "opposed", "abstained", "split"].map((s) => ({ id: s, label: STANCE[s].label, color: STANCE[s].color }));

  return (
    <main className="shell vizArticle decArticle">
      <JsonLd
        data={breadcrumbLd([
          { name: "Inicio", path: "/" },
          { name: "Visualizaciones", path: "/visualizaciones/" },
          { name: "Decisiones de los partidos", path: PAGE_PATH },
        ])}
      />
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title={`Qué votó cada partido en empleo, autónomos, sanidad e inmigración: ${h.measures} medidas con efecto legal; de las ${h.documented} ya documentadas, ${h.evaluated === 0 ? "ninguna tiene" : `${h.evaluated} tienen`} evaluación posterior`}
        summary={`Leyes, decretos-ley y presupuestos votados en el Congreso entre ${dateEs(h.first)} y ${dateEs(h.last)}: qué cambiaba cada uno, quién lo apoyó, si sus votos decidían el resultado y qué dicen las evaluaciones oficiales y académicas. No es una nota de los partidos ni una cuenta de «empleos creados»: eso no se puede medir.`}
        actions={[
          { href: "/visualizaciones/data/decisiones.csv", label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/decisiones.json", label: "JSON con fuentes" },
          { href: "#el-dato-mata-el-relato", label: "El gráfico de conjunto" },
          { href: "#lo-que-no-dicen", label: "Lo que estos datos no dicen" },
        ]}
      />

      <section className="card vizProse" id="resumen" aria-labelledby="resumen-title">
        <h2 id="resumen-title">Lo esencial</h2>
        <ol>
          <li>
            <strong>{h.measures} medidas con efecto legal</strong> salen de aplicar una regla fijada antes de mirar nada: toda ley, decreto-ley o
            sección de presupuestos votada en el Pleno con partidos enfrentados y cuyo texto toca el ámbito ({h.byDomain.empleo} de empleo,{" "}
            {h.byDomain.autonomos} de autónomos, {h.byDomain.sanidad} de sanidad, {h.byDomain.inmigracion} de inmigración). Ninguna se eligió a mano;{" "}
            {h.counterfactual} no llegaron a tener efecto y se muestran como contrafactual.
          </li>
          <li>
            <strong>
              De las {h.documented} medidas ya documentadas y revisadas, {h.evaluated === 0 ? "ninguna tiene" : `${h.evaluated} tienen`} una
              evaluación posterior de calidad
            </strong>{" "}
            (causal, o descriptiva atribuida por la propia fuente) sobre el objetivo que la medida declaraba. «Sin evaluar» no es «sin efecto»: es
            que nadie lo ha medido de forma que se pueda comprobar. Las otras {h.measures - h.documented} muestran ya sus votos, pero su evidencia
            está pendiente: el control de calidad de la primera tanda no alcanzó el umbral fijado y la documentación se paró hasta corregir el
            método.
          </li>
          <li>
            <strong>{h.narrow} se decidieron por 10 votos o menos.</strong> En esas, el voto de varios partidos fue decisivo: sin sus votos el resultado
            cambiaba. El gráfico lo marca con un anillo.
          </li>
          <li>
            <strong>Mucho voto es posición, no ley.</strong> Además de las medidas, hubo {h.positions} mociones y proposiciones no de ley en estos
            ámbitos: dicen qué querría cada partido, pero no cambian nada por sí solas. Se cuentan aparte.
          </li>
        </ol>
      </section>

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Medidas con efecto legal (o que lo buscaban)</span>
          <span className="vizStat__value">{h.measures}</span>
          <span className="vizStat__note">XIV desde oct. 2022 y XV completa hasta {dateEs(data.window.last)}</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Documentadas y revisadas contra la fuente</span>
          <span className="vizStat__value">
            {h.documented} de {h.measures}
          </span>
          <span className="vizStat__note">{h.evaluated === 0 ? "Ninguna" : h.evaluated} con evaluación posterior A o B</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Decididas por 10 votos o menos</span>
          <span className="vizStat__value">{h.narrow}</span>
          <span className="vizStat__note">Donde el voto de un partido mediano decidía</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Mociones y PNL sin efecto legal</span>
          <span className="vizStat__value">{h.positions}</span>
          <span className="vizStat__note">Posiciones, contadas aparte</span>
        </div>
      </section>

      <figure className="card vizFigure" id="el-dato-mata-el-relato" aria-labelledby="conjunto-title">
        <h2 id="conjunto-title">
          Cada medida, quién la votó y qué dice la evidencia, sobre el indicador oficial de su ámbito
        </h2>
        <p className="vizFigure__dek">
          Arriba, el indicador oficial de cada ámbito (España y media de la UE-27, eje desde cero) con cada medida marcada por su número en la
          fecha en que se votó; trazo discontinuo, la que no llegó a tener efecto. Debajo, el voto de cada partido (color) y si fue decisivo
          (anillo), y el resultado de la evaluación (símbolo). Un partido que apoyó una medida no puede atribuirse la mejora del indicador sin
          mirar la columna de la evaluación, y uno que se opuso no puede negar su voto.
        </p>
        <Legend items={stanceLegend} kind="bar" />
        <p className="decMuted decLegendNote">
          Letras: F a favor, C en contra, A abstención, D grupo dividido. Anillo negro: sin los votos de ese partido el resultado cambiaba. Evaluación: {Object.entries(VERDICT).filter(([k]) => k !== "pendiente").map(([k, v]) => `${v.marker} ${v.short}`).join(" · ")}.
        </p>
        {data.domains.map((d) => {
          const list = byDomain[d.id];
          const spec = PANEL[d.id];
          const series = spec ? (data.indicators[d.id] || []).find((s) => s.id === spec.indicator) : null;
          const lines = series
            ? [
                ...(series.peers.EU27 || series.peers.EU27_2020
                  ? [{ id: "eu", label: "Media UE-27", short: "UE-27", color: C.eu, points: series.peers.EU27 || series.peers.EU27_2020 }]
                  : []),
                { id: "es", label: "España", short: "España", color: C.es, emphasis: true, points: series.es },
              ]
            : [];
          const marks = list.map((m) => ({
            n: numbering[m.measure_id], date: m.date, name: measureName(m), took_effect: m.took_effect, verdict: m.verdict,
            verdictLabel: VERDICT[m.verdict]?.label,
          }));
          return (
            <section key={d.id} className="decDomain" aria-labelledby={`dom-${d.id}`}>
              <h3 id={`dom-${d.id}`}>
                {d.label}: {list.length} medidas{series ? ` · ${series.label}` : " · sin serie oficial comparable en nuestros datos"}
              </h3>
              <IndicatorPanel
                lines={lines}
                marks={marks}
                notes={spec?.notes || []}
                unitSuffix={spec?.suffix || ""}
                ariaLabel={`${d.label}: ${series ? series.label : "medidas en el tiempo"}`}
              />
              <VoteMatrix measures={list} labels={labels} numbering={numbering} caption={`${d.label}: voto de cada partido en cada medida`} />
            </section>
          );
        })}
        <figcaption className="vizFigure__caption">
          <span>
            Fuente: votos de cada diputado, datos abiertos del Congreso (vía el{" "}
            <a href="/citizen/vota/temas/">atlas de votaciones</a>); temporalidad: INE (EPA) y Eurostat; espera quirúrgica: Ministerio de Sanidad
            (SISLE-SNS), corte de diciembre. Evaluaciones: enlazadas en cada medida. Los partidos de la XIV se agrupan por su grupo parlamentario.
          </span>
          <span>
            La temporalidad cae sobre todo en 2022, con la reforma laboral aprobada en diciembre de 2021, que queda fuera de nuestros datos de voto
            (empiezan el 4 de octubre de 2022).
          </span>
        </figcaption>
      </figure>

      <section className="card vizProse" id="partidos" aria-labelledby="partidos-title">
        <h2 id="partidos-title">Cada partido, ámbito por ámbito</h2>
        <p>
          Cuántas de estas medidas apoyó, rechazó o dejó pasar cada partido, y qué dice la evaluación de cada una. No es una clasificación: un
          partido que gobierna propone casi todas las medidas; uno que nunca gobernó solo pudo votar las de otros.{" "}
          {governing.map((p) => `${p.label}: ${p.governing}`).join(". ")}.
        </p>
      </section>
      <PartyLedger data={data} />

      <section className="card vizProse" id="medidas" aria-labelledby="medidas-title">
        <h2 id="medidas-title">Las {h.measures} medidas, una a una</h2>
        <p>
          Cada ficha enlaza el texto oficial y la votación. La evidencia se gradúa como en el{" "}
          <a href="/visualizaciones/sistema/">simulador</a>: A, evaluación causal de esta medida en España; B, evaluación descriptiva de la
          medida o causal de una muy parecida fuera; C, estimación previa o manual; D, supuesto sin método. Solo A o B permiten decir «positiva»,
          «negativa» o «mixta».
        </p>
      </section>
      {data.domains.map((d) => (
        <section key={d.id} className="decMeasures" aria-labelledby={`medidas-${d.id}`}>
          <h2 id={`medidas-${d.id}`}>{d.label}</h2>
          {byDomain[d.id].map((m) => (
            <MeasureEvidence key={`${d.id}-${m.measure_id}`} m={m} n={numbering[m.measure_id]} labels={labels} />
          ))}
        </section>
      ))}

      <GovernmentBlock government={data.government} labels={labels} />

      <section className="card vizProse" id="mociones" aria-labelledby="mociones-title">
        <h2 id="mociones-title">Posiciones sin efecto legal</h2>
        <p>
          Mociones y proposiciones no de ley clasificadas en cada ámbito con confianza alta o media. Muestran qué pedía cada partido; no
          cambiaron ninguna norma por sí mismas.
        </p>
      </section>
      <div className="vizTable__scroll decLedger">
        <table>
          <caption className="decSr">Mociones y proposiciones no de ley por partido y ámbito</caption>
          <thead>
            <tr>
              <th scope="col">Partido</th>
              {data.domains.map((d) => (
                <th scope="col" key={d.id}>
                  {d.label} ({pos[d.id]?.votes ?? 0})
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.parties
              .filter((p) => data.domains.some((d) => pos[d.id]?.parties?.[p.party_id]))
              .map((p) => (
                <tr key={p.party_id}>
                  <th scope="row">{p.label}</th>
                  {data.domains.map((d) => {
                    const c = pos[d.id]?.parties?.[p.party_id] || {};
                    return (
                      <td key={d.id}>
                        sí {c.si || 0} · no {c.no || 0} · abst. {c.abst || 0}
                      </td>
                    );
                  })}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <section className="card vizProse" id="lo-que-no-dicen" aria-labelledby="limites-title">
        <h2 id="limites-title">Lo que estos datos no dicen</h2>
        <ul>
          <li>
            <strong>Causa.</strong> Que un indicador mejore después de una medida no prueba que la medida lo mejorara: se mueve con el ciclo, los
            fondos europeos, la inmigración y muchas medidas a la vez. Por eso cada ficha dice «se movió con», y solo una evaluación A o B permite
            hablar de efecto.
          </li>
          <li>
            <strong>Quién pudo decidir.</strong> Los partidos que nunca gobernaron solo votaron medidas de otros: su registro es de apoyos y
            rechazos, no de resultados propios. Lo que habría pasado con su alternativa es un contrafactual que nadie evaluó.
          </li>
          <li>
            <strong>La sanidad la gestionan las comunidades.</strong>{" "}
            {hs.by_sector ? (
              <>
                En {hs.by_sector.year}, las comunidades autónomas gastaron el {num(hs.by_sector.shares["Comunidades Autónomas"], 1)} % del gasto
                sanitario público; el Estado gestiona directamente poco más del{" "}
                {num(hs.by_sector.shares["Administración Central"] + hs.by_sector.shares["Mutualidades de Funcionarios"] + hs.by_sector.shares["Sistema de Seguridad Social (INGESA)"], 1)} %
                (ministerio, mutualidades de funcionarios e INGESA en Ceuta y Melilla) (
                <a href={hs.by_sector.url} rel="noopener noreferrer" target="_blank">
                  EGSP
                </a>
                {hs.by_sector.provisional ? ", provisional" : ""}). El Congreso fija el marco y la financiación general;{" "}
              </>
            ) : null}
            el gasto y las listas de espera dependen sobre todo de cada comunidad: en {hs.regions_year}, el gasto sanitario público por habitante iba de{" "}
            {num(hs.min?.value, 0)} € en {hs.min?.name} a {num(hs.max?.value, 0)} € en {hs.max?.name} ({num(hs.ratio_max_min, 2)} veces){" "}
            {hs.provisional ? "(datos provisionales)" : ""}. Ver <a href="/visualizaciones/sanidad/#comunidades">sanidad por comunidades</a>.
          </li>
          <li>
            <strong>La ventana.</strong> {data.window.gap} Las medidas se buscan en votaciones con partidos enfrentados; las aprobadas por
            unanimidad no aparecen porque no separan a nadie.
          </li>
          <li>
            <strong>La clasificación.</strong> Qué votación toca qué ámbito sale del <a href="/citizen/vota/temas/">atlas de votaciones</a>{" "}
            (clasificado con IA a partir del texto oficial y revisado por muestra) y de palabras del título; puede dejar fuera alguna medida o
            meter alguna lateral (la ley de universidades entra por su parte de personal).
          </li>
        </ul>
      </section>

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método</h2>
        <p>
          Regla de selección fija, publicada antes de documentar ninguna medida. Votos contados diputado a diputado; «decisivo» significa que,
          si los diputados de ese partido no hubieran votado, el resultado habría sido el contrario (las leyes orgánicas necesitan 176 síes). Cada
          ficha documentada fue revisada por un segundo revisor que solo veía la ficha y sus enlaces, con una regla fijada antes: al menos 4 de
          5 fichas con todas sus afirmaciones verificadas. La primera tanda dio 3 de 5; las dos fallidas se corrigieron con lo que señaló la
          revisión (una fecha de entrada en vigor y dos cifras que no eran evaluación ni la misma serie) y el resto quedó sin documentar. Datos: <a href="/visualizaciones/data/decisiones.csv">CSV</a> ·{" "}
          <a href="/visualizaciones/data/decisiones.json">JSON</a>.
        </p>
      </section>
    </main>
  );
}
