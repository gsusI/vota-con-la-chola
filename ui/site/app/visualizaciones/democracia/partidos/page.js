import { readPublicJson } from "../../../static-snapshot.mjs";
import { StaticRouteHero } from "../../../static-route-components";
import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo";
import Figure from "../../components/Figure";
import { ConductMatrix, DecreeBars, SeverityLegend, VPartyDots, VoteDots } from "./charts";
import {
  ATTRIBUTION_LABEL,
  FINDING_LABEL,
  ROLE_LABEL,
  VOTE_CATEGORY_LABEL,
  dateEs,
  eventsFor,
  headline,
  matrixTotals,
  num,
  partyLabel,
  signed,
} from "./model.mjs";
import "./partidos.css";

const DATA_PATH = "visualizaciones/data/democracia-partidos.json";
const PATH = "/visualizaciones/democracia/partidos/";

function load() {
  const data = readPublicJson(DATA_PATH, null);
  if (!data) throw new Error(`Missing ${DATA_PATH}`);
  return data;
}

export function generateMetadata() {
  const data = load();
  const h = headline(data);
  return pageMetadata({
    path: PATH,
    title: `Partidos y contrapesos: ${h.events} resoluciones oficiales`,
    description: `Registro con fuentes de cómo ha usado el poder cada partido del Congreso: ${h.events} resoluciones de tribunales y órganos independientes desde ${h.firstYear}, votos sobre controles al Gobierno y decretos-leyes.`,
    type: "article",
    modifiedTime: data.meta.snapshot_date,
  });
}

function EventItem({ event, pid, data }) {
  const a = event.attributions.find((x) => x.party_id === pid);
  const others = event.attributions.filter((x) => x.party_id !== pid).map((x) => partyLabel(data, x.party_id));
  const ind = data.codebook.indicators.find((i) => i.id === event.indicator);
  return (
    <li className={`dpxEvent dpxEvent--s${event.severity}${a.lineage === "predecessor" ? " dpxEvent--predecessor" : ""}`} id={`ev-${event.event_id}-${pid}`}>
      <span className="dpxEvent__head">
        {dateEs(event.date)} · {event.title}
      </span>
      <span className="dpxEvent__meta">
        <span className="dpxTag">{ind?.label}</span>
        <span className="dpxTag">gravedad {event.severity}: {FINDING_LABEL[event.finding_type]}</span>
        {ROLE_LABEL[a.role]} · {ATTRIBUTION_LABEL[a.attribution]}
        {a.power_only ? " · acto que solo puede hacer quien gobierna" : ""}
        {a.lineage === "predecessor" ? " · partido predecesor, no se cuenta" : ""}
        {others.length ? ` · también atribuido a ${others.join(", ")}` : ""}
      </span>
      {a.note ? <span className="dpxEvent__meta">{a.note}</span> : null}
      <span>
        {event.act.replace(/\.$/, "")}. {event.status && event.status !== "firme" ? `Estado: ${event.status.replace(/\.$/, "")}. ` : ""}
        <q lang={event.source.quote_lang}>{event.source.quote}</q>{" "}
        <a href={event.source.url} rel="noopener noreferrer" target="_blank">
          {event.body}
          {event.source.locator ? `, ${event.source.locator}` : ""}
        </a>
        {(event.extra_sources || []).map((s, i) => (
          <span key={`${i}-${s.url}`}>
            {" · "}
            <a href={s.url} rel="noopener noreferrer" target="_blank">
              fuente {i + 2}
            </a>
          </span>
        ))}
      </span>
    </li>
  );
}

function PendingItem({ x }) {
  return (
    <li className="dpxEvent dpxEvent--pending">
      <span className="dpxEvent__head">
        {dateEs(x.date)} · {x.finding}
      </span>
      <span className="dpxEvent__meta">
        {x.person} · {x.body} · {ROLE_LABEL[x.role] || x.role}
      </span>
      <span>
        {x.appeal}. <q lang={x.source.quote_lang || "es"}>{x.source.quote}</q>{" "}
        <a href={x.source.url} rel="noopener noreferrer" target="_blank">
          fuente
        </a>
      </span>
    </li>
  );
}

function CensusTable({ data }) {
  const fams = data.census?.families || [];
  return (
    <details className="vizTable" open>
      <summary>Qué cuenta y qué no: censo o selección, familia por familia</summary>
      <div className="vizTable__scroll">
        <table className="dpxCensus">
          <thead>
            <tr>
              <th scope="col">Familia</th>
              <th scope="col">Tipo</th>
              <th scope="col">Cobertura</th>
              <th scope="col">Por partido</th>
            </tr>
          </thead>
          <tbody>
            {fams.map((f) => (
              <tr key={f.family}>
                <td>
                  {f.label}
                  {f.list_source?.url ? (
                    <>
                      {" "}
                      <a href={f.list_source.url} rel="noopener noreferrer" target="_blank">
                        lista oficial
                      </a>
                    </>
                  ) : null}
                </td>
                <td>{f.type === "census" ? "censo" : "selección, no censo"}</td>
                <td>
                  {f.type === "census"
                    ? `${f.n_in_scope} de ${f.n_listed} elementos de la lista entran en el alcance; ${f.n_events} atribuibles a un partido. ${f.scope}`
                    : `${f.n_events} casos listados en los perfiles. ${f.scope}`}
                </td>
                <td>
                  {f.type === "census"
                    ? Object.entries(f.by_party || {})
                        .sort((a, b) => b[1] - a[1])
                        .map(([pid, n]) => `${partyLabel(data, pid)} ${n}`)
                        .join(" · ") || "ninguno"
                    : "no se cuenta"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function VoteSummary({ s }) {
  if (!s) return null;
  const parts = [];
  for (const leg of ["15", "14"]) {
    const v = s[leg];
    if (!v) continue;
    const c = v.estructural_vinculante;
    const sc = v.escrutinio;
    if (!c?.votes && !sc?.votes) continue;
    parts.push(
      `${leg === "15" ? "XV" : "XIV"} legislatura (${v.role === "gobierno" ? "en el Gobierno" : "fuera del Gobierno"}): reglas vinculantes ${signed(c?.score)} en ${c?.votes || 0} votaciones; escrutinio ${signed(sc?.score)} en ${sc?.votes || 0}`,
    );
  }
  return parts.length ? <p>Votos en el Congreso (de −1, siempre contra más controles, a +1, siempre a favor): {parts.join(". ")}.</p> : <p>Sin votos clasificados en el Congreso.</p>;
}

function Profile({ party, data }) {
  const evs = eventsFor(data, party.party_id);
  const counted = evs.filter((e) => e.attributions.find((a) => a.party_id === party.party_id)?.lineage !== "predecessor");
  const vp = party.vparty;
  const pend = (data.pending || []).filter((x) => x.party_id === party.party_id);
  return (
    <details className="dpxProfile" id={`perfil-${party.party_id}`}>
      <summary>
        {party.label}{" "}
        <span className="dpxProfile__meta">
          · {counted.length
            ? `${party.events_census} en censos completos${party.events_selection ? `, ${party.events_selection} en selección` : ""}`
            : "sin señal en el registro"}
          {pend.length ? ` · ${pend.length} pendiente${pend.length === 1 ? "" : "s"}, no contado${pend.length === 1 ? "" : "s"}` : ""}
          {party.national_government_years_in_window ? ` · ${num(party.national_government_years_in_window, 1)} años en el Gobierno de España` : ""}
        </span>
      </summary>
      <div className="dpxProfile__body">
        {party.note ? <p>{party.note}</p> : null}
        {counted.length === 0 ? (
          <p>
            Ninguna resolución de los órganos del registro le atribuye un acto en el periodo. No es prueba de buena conducta:
            {party.national_government_years_in_window ? "" : " no ha gobernado España en el periodo y"} la mayoría de los indicadores requieren
            tener poder.
          </p>
        ) : null}
        {evs.filter((e) => e.coverage?.type === "census").length ? (
          <>
            <p className="dpxSubhead">De censos completos (comparables)</p>
            <ul className="dpxEvents">
              {evs
                .filter((e) => e.coverage?.type === "census")
                .map((e) => (
                  <EventItem key={e.event_id} event={e} pid={party.party_id} data={data} />
                ))}
            </ul>
          </>
        ) : null}
        {evs.filter((e) => e.coverage?.type !== "census").length ? (
          <>
            <p className="dpxSubhead">Selección, no censo (no se cuenta ni se compara)</p>
            <ul className="dpxEvents">
              {evs
                .filter((e) => e.coverage?.type !== "census")
                .map((e) => (
                  <EventItem key={e.event_id} event={e} pid={party.party_id} data={data} />
                ))}
            </ul>
          </>
        ) : null}
        {pend.length ? (
          <>
            <p className="dpxSubhead">Pendiente, no contado (no es firme)</p>
            <ul className="dpxEvents">
              {pend.map((x) => (
                <PendingItem key={x.pending_id} x={x} />
              ))}
            </ul>
          </>
        ) : null}
        <VoteSummary s={party.votes} />
        {party.alignment_with_psoe_leg15?.same_as_psoe_pct != null && party.party_id !== "psoe" ? (
          <p>
            En la XV legislatura votó lo mismo que el PSOE en el {num(party.alignment_with_psoe_leg15.same_as_psoe_pct, 0)} % de {num(party.alignment_with_psoe_leg15.votes)} votaciones.
          </p>
        ) : null}
        <p>
          V-Party (expertos, elección de 2019):{" "}
          {vp?.antiplural != null
            ? `índice de antipluralismo ${num(vp.antiplural, 2)} (intervalo ${num(vp.antiplural_low, 2)}–${num(vp.antiplural_high, 2)}).`
            : vp?.partial
              ? `sin puntuación propia; ${vp.partial.map((x) => `${x.name} ${num(x.antiplural, 2)}`).join(", ")}.`
              : "sin puntuación (V-Party solo cubre los partidos con más del 5 % de los votos)."}
        </p>
      </div>
    </details>
  );
}

export default function DemocraciaPartidosPage() {
  const data = load();
  const h = headline(data);
  const totals = matrixTotals(data);
  const sens = data.sensitivity;
  const dec = data.decrees;
  const govs = dec.available ? dec.by_government : [];
  const lastGov = govs.at(-1);
  const rajoy = govs.find((g) => g.id === "rajoy");
  const prior = govs.filter((g) => g.start < "2018-06-02");
  const priorMin = Math.min(...prior.map((g) => g.rdl_share_pct));
  const priorMax = Math.max(...prior.map((g) => g.rdl_share_pct));
  const lawsPerYear = (g) => ((g.laws + g.organic_laws) / g.months) * 12;
  const agg = (list) => {
    const months = list.reduce((t, g) => t + g.months, 0);
    const rdl = list.reduce((t, g) => t + g.rdl, 0);
    const laws = list.reduce((t, g) => t + g.laws + g.organic_laws, 0);
    return { months, rdlPm: rdl / months, lawsPm: laws / months, share: (100 * rdl) / (rdl + laws) };
  };
  const sanchezGovs = govs.filter((g) => g.id.startsWith("sanchez"));
  const sAgg = sanchezGovs.length ? agg(sanchezGovs) : null;
  const pAgg = prior.length ? agg(prior) : null;
  const pm = (g, k) => (k === "rdl" ? g.rdl / g.months : (g.laws + g.organic_laws) / g.months);
  const priorRdlMin = Math.min(...prior.map((g) => pm(g, "rdl")));
  const priorRdlMax = Math.max(...prior.map((g) => pm(g, "rdl")));
  const priorLawMin = Math.min(...prior.map((g) => pm(g, "laws")));
  const priorLawMax = Math.max(...prior.map((g) => pm(g, "laws")));
  // Counterfactual split of the share: only decree-laws at today's pace (laws as before), or only laws at today's pace.
  const shareOnlyRdl = sAgg && pAgg ? (100 * sAgg.rdlPm) / (sAgg.rdlPm + pAgg.lawsPm) : null;
  const shareOnlyLaws = sAgg && pAgg ? (100 * pAgg.rdlPm) / (pAgg.rdlPm + sAgg.lawsPm) : null;
  const lawsMovedMore = shareOnlyLaws != null && shareOnlyLaws > shareOnlyRdl;
  const vpRows = data.parties
    .filter((p) => p.vparty?.antiplural != null)
    .map((p) => ({ label: p.label, value: p.vparty.antiplural, low: p.vparty.antiplural_low, high: p.vparty.antiplural_high }))
    .concat(
      data.parties
        .filter((p) => p.vparty?.partial)
        .flatMap((p) => p.vparty.partial.map((x) => ({ label: `${x.name} (hoy en ${p.label})`, value: x.antiplural, low: x.antiplural_low, high: x.antiplural_high }))),
    )
    .sort((a, b) => b.value - a.value);
  const weightIds = Object.keys(sens.weightings);
  const sensParties = data.parties.filter((p) => sens.parties_with_items.includes(p.party_id));
  const reversalPairs = [...new Set(sens.reversals.map((r) => r.pair.map((pid) => partyLabel(data, pid)).join(" y ")))];
  const indTotals = data.codebook.indicators.map((i) => ({ ...i, ...totals[i.id] }));
  const emptyList = indTotals.filter((i) => !i.gobierno && !i.fuera && !i.selection);
  const emptyInds = emptyList.map((i) => i.label.toLowerCase());
  const emptyIds = emptyList.map((i) => i.id);

  return (
    <main className="shell vizArticle">
      <JsonLd
        data={[
          breadcrumbLd([
            { name: "Inicio", path: "/" },
            { name: "Visualizaciones", path: "/visualizaciones/" },
            { name: "Democracia", path: "/visualizaciones/democracia/" },
            { name: "Partidos", path: PATH },
          ]),
        ]}
      />
      <StaticRouteHero
        eyebrow="Visualizaciones · democracia"
        title={`Cómo han usado el poder los partidos: ${h.events} resoluciones oficiales desde ${h.firstYear}`}
        summary="Un registro con fuentes, no un ranking: sentencias firmes, anulaciones del Tribunal Constitucional y conclusiones de la Comisión de Venecia, la Comisión Europea y GRECO, atribuidas a cada partido con el papel que tenía entonces; junto a cómo votó cada uno las reglas que limitan a cualquier Gobierno y cuántos decretos-leyes firmó cada Gobierno."
        actions={[
          { href: "#matriz", label: "La figura que lo resume" },
          { href: "#perfiles", label: "Perfil por partido" },
          { href: "/visualizaciones/data/democracia-partidos.csv", label: "Descargar el registro (CSV)" },
          { href: "/visualizaciones/data/democracia-partidos.json", label: "JSON con fuentes" },
          { href: "#metodo", label: "Método" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Resoluciones de censos completos</span>
          <span className="vizStat__value">{h.censusEvents}</span>
          <span className="vizStat__note">
            de {h.censusFamilies} listas oficiales completas; además, {h.selectionEvents} en selección (no comparables) y {h.pending} pendientes, no contadas
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Partidos sin señal en el registro</span>
          <span className="vizStat__value">
            {h.partiesNoSignal} de {data.parties.length}
          </span>
          <span className="vizStat__note">sin resolución no significa buena conducta: casi todo exige gobernar</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Nivel de «riesgo» compuesto</span>
          <span className="vizStat__value">{sens.publish_composite ? "Publicado" : "No publicado"}</span>
          <span className="vizStat__note">
            {sens.publish_composite ? "el orden resiste las siete ponderaciones" : `${sens.reversal_count} inversiones de orden entre ${weightIds.length} ponderaciones`}
          </span>
        </div>
        {lastGov && rajoy && sAgg ? (
          <div className="card vizStat">
            <span className="vizStat__label">Decretos-leyes y leyes al mes, Gobiernos de Sánchez (desde 2018)</span>
            <span className="vizStat__value">
              {num(sAgg.rdlPm, 2)} y {num(sAgg.lawsPm, 2)}
            </span>
            <span className="vizStat__note">
              de 1979 a 2018: entre {num(priorRdlMin, 2)} y {num(priorRdlMax, 2)} decretos-leyes y entre {num(priorLawMin, 2)} y {num(priorLawMax, 2)} leyes al mes. El peso
              de los decretos ({num(sAgg.share, 0)} %) sube {lawsMovedMore ? "más por las leyes que faltan que por los decretos de más" : "más por los decretos de más que por las leyes que faltan"} (BOE)
            </span>
          </div>
        ) : null}
      </section>

      <Figure
        id="matriz"
        title={`Quién aparece y con qué papel: ${h.censusEvents} resoluciones de ${h.censusFamilies} listas oficiales completas`}
        dek={`Los números solo cuentan resoluciones de listas oficiales recorridas de principio a fin (censos): por eso son comparables entre partidos. Un anillo indica casos encontrados por selección, que se listan en el perfil pero no se cuentan. Cada casilla tiene dos mitades: a la izquierda, actos hechos gobernando (España, una comunidad o un ayuntamiento); a la derecha, sin gobernar. El color es la gravedad máxima según la fuerza legal de la resolución. Bajo cada partido, su exposición: años en el Gobierno de España dentro del periodo.`}
        sources={[{ href: "#perfiles", label: "registro de resoluciones (tribunales, Comisión de Venecia, Comisión Europea, GRECO), enlazadas una a una en cada perfil" }]}
        notes={[
          "Zanja dos relatos: «solo un lado abusa» (la tabla muestra resoluciones en varios partidos y en los dos papeles) y «todos son iguales» (difieren el indicador, la gravedad y el papel). Lo que no zanja: quien no ha gobernado tiene pocas ocasiones de aparecer, y las condenas llegan años después de los hechos.",
        ].filter(Boolean)}
        table={<CensusTable data={data} />}
      >
        <SeverityLegend />
        <ConductMatrix data={data} />
        {emptyInds.length ? (
          <p className="vizFigure__dek">
            {emptyInds.length === 1 ? "Un indicador del codebook no tiene" : `${emptyInds.length} indicadores del codebook no tienen`} ninguna resolución, ni de censo ni de
            selección: {emptyInds.join(", ")}. No es una prueba de ausencia: el método solo cuenta resoluciones oficiales, y sobre discursos, insultos o
            tolerancia hacia la violencia casi nunca hay una.
            {emptyIds.includes("legitimidad") && emptyIds.includes("violencia")
              ? " Dos de ellos, negar la legitimidad del adversario y tolerar la violencia, son los indicadores de Levitsky y Ziblatt más ligados a la erosión democrática; la única aproximación que mostramos para ellos es la valoración de expertos de V-Party (más abajo), que no es una resolución oficial."
              : ""}
          </p>
        ) : null}
      </Figure>

      {(data.pending || []).length ? (
        <section className="vizProse" id="pendiente" aria-labelledby="pendiente-title">
          <h2 id="pendiente-title">Pendiente, no contado: {data.pending.length} resoluciones que aún no son firmes</h2>
          <p>
            Condenas en primera instancia recurridas y sanciones administrativas recurridas, con la misma vara para todos los partidos. No cuentan en
            ninguna cifra; se muestran para que un perfil corto no se lea como un perfil limpio.
          </p>
          <ul className="dpxEvents">
            {data.pending.map((x) => (
              <li key={x.pending_id} className="dpxEvent">
                <span className="dpxEvent__head">
                  {partyLabel(data, x.party_id)} · {dateEs(x.date)} · {x.finding}
                </span>
                <span className="dpxEvent__meta">
                  {x.person} · {x.body} · {x.appeal}
                </span>
                <span>
                  <q lang={x.source.quote_lang || "es"}>{x.source.quote}</q>{" "}
                  <a href={x.source.url} rel="noopener noreferrer" target="_blank">
                    fuente
                  </a>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="vizProse" aria-labelledby="como-leer">
        <h2 id="como-leer">Cómo se ha hecho y qué no puede decir</h2>
        <p>
          Cada resolución entra solo si la dictó un órgano oficial o independiente (Tribunal Constitucional, Tribunal Supremo y otros tribunales con
          sentencia firme, Junta Electoral Central, Tribunal de Cuentas, Comisión de Venecia, Comisión Europea, GRECO) y si ese órgano, o un registro
          oficial, permite atribuir el acto a un partido. Se clasifica en uno de nueve indicadores tomados de Levitsky y Ziblatt, del índice de
          antipluralismo de V-Party y de los cuatro pilares del Informe sobre el Estado de Derecho de la Comisión Europea. La regla es la misma para
          quien gobierna y para quien está en la oposición.
        </p>
        <p>
          La gravedad mide la fuerza legal de la resolución, fijada antes de recoger nada: 3 si anula un acto entero o condena con prisión de un año o
          más, 2 si anula en parte, ampara un derecho, condena sin prisión o sanciona, y 1 si es una conclusión no vinculante. No mide el daño del acto.
        </p>
        <ul>
          <li>Que un partido no aparezca no prueba buena conducta: casi todos los indicadores exigen haber gobernado.</li>
          <li>Las condenas llegan años después de los hechos; lo reciente está infrarrepresentado.</li>
          <li>El registro solo contiene lo que los órganos oficiales decidieron examinar y lo que alguien les llevó.</li>
          <li>No se recogen declaraciones, columnas de opinión ni motivos: solo lo que consta en la resolución.</li>
        </ul>
      </section>

      <Figure
        id="votos"
        title="Cómo votó cada partido las reglas que limitan al Gobierno, según el papel que tenía"
        dek={`${data.votes.items.length} votaciones del Congreso de las legislaturas XIV y XV clasificadas en los ejes de independencia judicial, reglas institucionales, medidas anticorrupción y control al Gobierno. Separamos las reglas que obligarían a cualquier Gobierno futuro del escrutinio del Gobierno de turno: en las dos legislaturas gobernó el PSOE, y la oposición siempre vota a favor de controlar a quien gobierna.`}
        legend={[
          { id: "gov", label: "en el Gobierno", color: "var(--viz-s2)" },
          { id: "out", label: "fuera del Gobierno", color: "var(--viz-s1)" },
        ]}
        legendKind="bar"
        sources={[{ href: "/citizen/data/vote_atlas_v1.json", label: "Congreso de los Diputados, votaciones en datos abiertos, clasificadas en el atlas de votaciones" }]}
        notes={[
          "Punto lleno: XV legislatura (2023-2026); hueco: XIV (2019-2023). Cada iniciativa pesa uno aunque se votara por puntos.",
          data.votes.coverage_note,
          `Ningún partido cambió de papel dentro de estos datos, así que no se puede separar convicción de papel: es «cómo votó con el papel que tenía», no una comparación entre iguales. Fuera del Gobierno no es lo mismo que oposición: en la XV, ${data.parties
            .filter((p) => !["psoe", "sumar"].includes(p.party_id) && p.alignment_with_psoe_leg15?.same_as_psoe_pct >= 55)
            .map((p) => `${p.label} (${num(p.alignment_with_psoe_leg15.same_as_psoe_pct, 0)} %)`)
            .join(", ")} votaron lo mismo que el PSOE en la mayoría de las votaciones.`,
        ]}
        table={
          <details className="vizTable">
            <summary>Ver las {data.votes.items.length} votaciones</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Fecha</th>
                    <th scope="col">Qué se votaba (votar Sí)</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Sí empuja a</th>
                    {data.votes.parties_order.map((pid) => (
                      <th scope="col" key={pid}>
                        {partyLabel(data, pid)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...data.votes.items].reverse().map((v) => (
                    <tr key={v.id}>
                      <td>
                        <a href={v.url} rel="noopener noreferrer" target="_blank">
                          {v.date}
                        </a>
                      </td>
                      <td style={{ whiteSpace: "normal", minWidth: 260, textAlign: "left" }}>{v.summary_yes}</td>
                      <td>{v.category === "escrutinio" ? "escrutinio" : v.category === "estructural_vinculante" ? "regla, vinculante" : "regla, declarativa"}</td>
                      <td>{v.sign === "+" ? "más controles" : "menos controles"}</td>
                      {v.parties.split("").map((c, i) => (
                        <td key={i}>{{ S: "Sí", N: "No", A: "Abst." }[c] || ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <div className="dpxVotes">
          {["estructural_vinculante", "estructural_declarativa", "escrutinio"].map((cat) => (
            <div key={cat}>
              <h3>{VOTE_CATEGORY_LABEL[cat]}</h3>
              <VoteDots data={data} category={cat} />
            </div>
          ))}
        </div>
      </Figure>

      {dec.available ? (
        <Figure
          id="decretos"
          title={`Decretos-leyes: ${num(sAgg.rdlPm, 2)} al mes desde 2018, frente a ${num(priorRdlMin, 2)}–${num(priorRdlMax, 2)} antes; leyes: ${num(sAgg.lawsPm, 2)} al mes, frente a ${num(priorLawMin, 2)}–${num(priorLawMax, 2)}`}
          dek="Reales decretos-leyes publicados en el BOE cada año desde 1979, coloreados por el partido que gobernaba a mitad de año. Un decreto ley entra en vigor sin pasar antes por el Congreso, que solo puede convalidarlo o derogarlo en bloque. Volumen no es abuso: la señal de abuso son las anulaciones del Tribunal Constitucional del registro."
          legend={[
            { id: "psoe", label: "PSOE", color: "var(--viz-s2)" },
            { id: "pp", label: "PP", color: "var(--viz-s1)" },
            { id: "ucd", label: "UCD", color: "var(--viz-peer)" },
          ]}
          legendKind="bar"
          sources={[{ href: dec.source.url, label: `BOE, listados ELI de decretos-leyes, leyes y leyes orgánicas (consulta ${dec.source.retrieved})` }]}
          notes={[
            "El año en curso aparece más claro: está incompleto. La tabla da el ritmo por Gobierno (por 12 meses en el cargo) y el peso de los decretos sobre toda la legislación con rango de ley.",
            `Qué se movió: el peso de los decretos sobre toda la legislación con rango de ley pasó del ${num(pAgg.share, 0)} % (1979-2018) al ${num(sAgg.share, 0)} % (desde 2018). Si solo hubieran subido los decretos-leyes, al ritmo actual y con las leyes al ritmo de antes, el peso sería del ${num(shareOnlyRdl, 0)} %; si solo hubieran bajado las leyes, del ${num(shareOnlyLaws, 0)} %. ${lawsMovedMore ? "Pesa más la caída de las leyes que la subida de los decretos" : "Pesa más la subida de los decretos que la caída de las leyes"}: el porcentaje se multiplicó por ${num(sAgg.share / pAgg.share, 1)}, pero los decretos-leyes al mes, por ${num(sAgg.rdlPm / pAgg.rdlPm, 1)}, y las leyes al mes cayeron un ${num(100 * (1 - sAgg.lawsPm / pAgg.lawsPm), 0)} %. Los datos no dicen por qué.`,
          ]}
          table={
            <details className="vizTable" open>
              <summary>Por Gobierno</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Gobierno</th>
                      <th scope="col">Desde</th>
                      <th scope="col">Decretos-leyes</th>
                      <th scope="col">Decretos-leyes al mes</th>
                      <th scope="col">Leyes y leyes orgánicas</th>
                      <th scope="col">Leyes al mes</th>
                      <th scope="col">% decretos sobre el total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {govs.map((g) => (
                      <tr key={g.id}>
                        <td>
                          {g.president} ({g.party})
                        </td>
                        <td>{g.start}</td>
                        <td>{g.rdl}</td>
                        <td>{num(g.rdl / g.months, 2)}</td>
                        <td>{g.laws + g.organic_laws}</td>
                        <td>{num((g.laws + g.organic_laws) / g.months, 2)}</td>
                        <td>{num(g.rdl_share_pct, 0)} %</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          }
        >
          <DecreeBars series={dec.series} governments={govs} />
        </Figure>
      ) : null}

      <Figure
        id="vparty"
        title="La referencia externa: el índice de antipluralismo de V-Party"
        dek={`${data.vparty.measures} Lo que no mide: ${data.vparty.does_not_measure.replace(/^No mide/, "no mide")}`}
        sources={[{ href: data.vparty.url, label: `V-Dem, ${data.vparty.release}` }]}
        notes={[data.vparty.mirror_note, "Es una valoración de expertos, independiente de nuestro registro: sirve para contrastar, no para sumar."]}
      >
        <VPartyDots rows={vpRows} />
      </Figure>

      <Figure
        id="sensibilidad"
        title={sens.publish_composite ? "La prueba de sensibilidad: el orden de partidos resiste" : `Por qué no hay un «riesgómetro»: ${sens.reversal_count} inversiones de orden en la prueba de sensibilidad`}
        dek={`Regla fijada antes de mirar los datos: ${sens.rule.charAt(0).toLowerCase()}${sens.rule.slice(1)} Probamos ${weightIds.length} ponderaciones sobre las ${sens.events_used} resoluciones de censos completos (las de selección no son comparables).${sens.publish_composite ? "" : ` El orden cambia, sobre todo entre ${reversalPairs.slice(0, 4).join("; ")}, así que publicamos perfiles sin nivel compuesto.`}`}
        table={
          <details className="vizTable" open>
            <summary>Puntuación de cada partido con cada ponderación</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Ponderación</th>
                    {sensParties.map((p) => (
                      <th scope="col" key={p.party_id}>
                        {p.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {weightIds.map((w) => (
                    <tr key={w}>
                      <td style={{ whiteSpace: "normal", minWidth: 220 }}>
                        {w}: {sens.weightings[w]}
                      </td>
                      {sensParties.map((p) => (
                        <td key={p.party_id}>
                          {sens.scores[w][p.party_id] == null ? "—" : num(sens.scores[w][p.party_id], Number.isInteger(sens.scores[w][p.party_id]) ? 0 : 2)}
                          {sens.ranks[w][p.party_id] ? ` (${sens.ranks[w][p.party_id]}.º)` : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      />

      <section className="vizProse" id="perfiles" aria-labelledby="perfiles-title">
        <h2 id="perfiles-title">Perfil por partido</h2>
        <p>
          Cada resolución enlaza al documento oficial, con una cita literal breve. Ordenados por la gravedad de lo que cuentan los censos, que no es un
          ranking: depende de cuánto tiempo y dónde ha gobernado cada uno. Cada perfil separa lo que viene de un censo, lo que viene de una selección y
          lo que está pendiente.
        </p>
        <div className="dpxProfiles">
          {[...data.parties]
            .sort((a, b) => b.severity_sum_census - a.severity_sum_census || b.events_selection - a.events_selection || a.label.localeCompare(b.label))
            .map((p) => (
              <Profile key={p.party_id} party={p} data={data} />
            ))}
        </div>
      </section>

      {data.system_findings.length ? (
        <section className="vizProse" id="sistema" aria-labelledby="sistema-title">
          <h2 id="sistema-title">Lo que los órganos señalan sin atribuirlo a un partido</h2>
          <p>
            Estas conclusiones hablan del sistema, no de un acto concreto de un partido, así que no cuentan en ningún perfil. Qué contrapesos dependen de
            la buena voluntad se analiza en <a href="/visualizaciones/democracia/">la página sobre el sistema</a>.
          </p>
          <ul>
            {data.system_findings.map((f) => (
              <li key={`${f.event_id || f.finding}-${f.year}`}>
                {f.year}: {f.finding}{" "}
                <a href={f.source?.url || f.url} rel="noopener noreferrer" target="_blank">
                  fuente
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y fuentes</h2>
        <ul>
          {data.codebook.indicators.map((i) => (
            <li key={i.id}>
              <strong>{i.label}</strong> ({i.family}): {i.definition}
            </li>
          ))}
        </ul>
        <p>
          Atribución: un decreto o decisión, al partido o partidos que formaban ese Gobierno; una proposición, al grupo que la registró; una condena, al
          partido del que era miembro la persona cuando ocupaba el cargo en que ocurrieron los hechos; el propio partido cuando es el condenado o el
          responsable civil. Los actos de partidos predecesores distintos (CDC, PDeCAT) se muestran pero no se cuentan. Periodo: resoluciones fechadas
          desde el {dateEs(data.meta.window.start)}, de modo que PP y PSOE tienen ambos años de Gobierno dentro.
        </p>
        <p>
          Revisión: un revisor independiente comprobó, solo con cada ficha y su enlace, la fecha, la atribución, la clasificación y la cita de una muestra
          aleatoria; los resultados y la prueba de simetría están en el{" "}
          <a href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/README.md" rel="noopener noreferrer" target="_blank">
            cuaderno del método
          </a>
          .
        </p>
        <p>
          Datos: <a href="/visualizaciones/data/democracia-partidos.csv">registro en CSV</a> y{" "}
          <a href="/visualizaciones/data/democracia-partidos.json">JSON completo</a> con votaciones, decretos y prueba de sensibilidad. Actualizado el{" "}
          {dateEs(data.meta.snapshot_date)}.
        </p>
      </section>
    </main>
  );
}
