import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import { JsonLd, breadcrumbLd, datasetLd, pageMetadata } from "../../seo";
import Figure from "../components/Figure";
import Explain from "./Explain";
import SafeguardMap, { MapLegend, partyOfEpisode } from "./SafeguardMap";
import { CLASS_COLORS, CLASS_LABELS, CLASS_SHORT, COUNTRY, HBars, LineChart, PairedBars, PARTY_COLORS, YearStrip, num } from "./charts";
import { PEER_CODES, democracyModel, democracySeo, partyOf } from "./model.mjs";
import "./democracia.css";

const DATA_PATH = "visualizaciones/data/democracia.json";

function load() {
  const data = readPublicJson(DATA_PATH, null);
  if (!data) throw new Error(`Missing ${DATA_PATH}`);
  return data;
}

export function generateMetadata() {
  const seo = democracySeo(load());
  return pageMetadata({ path: seo.path, title: seo.title, description: seo.description, type: "article", keywords: [
    "separación de poderes España", "decretos-leyes", "renovación CGPJ", "presupuestos prorrogados", "estado de derecho España", "V-Dem España",
  ] });
}

const BUCKETS = {
  gobierno: "Proyectos del Gobierno",
  grupos_gobierno: "Proposiciones de PSOE o Sumar",
  pp: "Proposiciones del PP",
  otros_grupos: "Proposiciones de otros grupos",
  senado: "Proposiciones del Senado",
  ccaa: "Proposiciones de parlamentos autonómicos",
};
const BUDGET_COLORS = { a_tiempo: "#2f7d55", tarde: "#c08a00", prorrogado: "#b23a48" };
const BUDGET_LABELS = { a_tiempo: "Aprobado antes del 1 de enero", tarde: "Aprobado ya empezado el año", prorrogado: "Prorrogado todo el año" };
const KIND_LABELS = {
  incumplimiento_declarado: "Incumplimiento declarado",
  plazo_vencido: "Plazo vencido",
  tension: "Tensión",
  remedio: "Remedio",
  aval: "Aval",
};

function SourceLinks({ sources }) {
  return (sources || []).map((s, i) => (
    <span key={s.url}>
      {i ? " · " : ""}
      <a href={s.url} rel="noopener noreferrer" target="_blank">
        {s.label}
      </a>
    </span>
  ));
}

function powerText(ep, governments) {
  const ph = ep.power_holder || {};
  const gov = governments.find((g) => g.id === ph.government);
  const parts = [];
  if (gov) parts.push(`Gobierno de ${gov.president} (${gov.party})`);
  else if (ph.body) parts.push(ph.body);
  if (ph.indispensable_parties?.length) parts.push(`votos indispensables: ${ph.indispensable_parties.join(", ")}`);
  if (ph.note) parts.push(ph.note);
  return parts.join("; ");
}

// Qualified-majority arithmetic of one episode, per legislature (computed by the exporter from the JEC seat table).
function Arithmetic({ rows }) {
  return (
    <ul className="demoArith">
      {rows.map((r) => (
        <li key={r.legislature}>
          <strong>Leg. {r.legislature}</strong>
          {r.status === "sin_tabla" ? (
            " sin tabla de escaños"
          ) : (
            <>
              {r.congress
                ? ` Congreso, ${r.rule} = ${r.congress.needed} de 350: ${Object.entries(r.congress.seats).slice(0, 5).map(([k, v]) => `${k} ${v}`).join(", ")}. ${
                    r.congress.block_alone.length
                      ? `Podía bloquear solo: ${r.congress.block_alone.join(", ")}.`
                      : r.congress.block_pairs.length
                        ? `Ninguno bloqueaba solo; juntos podían: ${r.congress.block_pairs.map((p) => p.join(" y ")).join("; ")}.`
                        : "Ningún grupo ni pareja de grupos grandes bloqueaba."
                  }`
                : ""}
              {r.senate
                ? ` Senado: ${r.senate.block_alone_certain.length ? `${r.senate.block_alone_certain.join(", ")} bloqueaba solo con sus senadores elegidos.` : "no determinado (faltan los senadores designados por las comunidades)."}`
                : ""}{" "}
              <a href={r.url} rel="noopener noreferrer" target="_blank">
                JEC {r.election.slice(0, 4)}
              </a>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function DemocraciaPage() {
  const data = load();
  const m = democracyModel(data);
  const seo = democracySeo(data);
  const raw = data.generated_from.raw;
  const retrieved = (key) => (raw[key]?.retrieved_at ? `, consultado ${String(raw[key].retrieved_at).slice(0, 10)}` : "");
  const S = {
    boe: { label: `BOE, árbol ELI de leyes y decretos-leyes${retrieved("boe_eli_inventory.json.gz")}`, href: "https://www.boe.es/eli/es" },
    boeBudget: { label: `BOE, legislación consolidada (API de datos abiertos)${retrieved("boe_budget_laws.json")}`, href: "https://www.boe.es/datosabiertos/" },
    congreso: { label: `Congreso de los Diputados, datos abiertos de iniciativas (corte ${data.freezer.snapshot_date})`, href: "https://www.congreso.es/es/opendata/iniciativas" },
    vdem: { label: `V-Dem, versión distribuida por Our World in Data${retrieved("owid_vdem_libdem.csv.gz")}`, href: "https://ourworldindata.org/grapher/liberal-democracy-index" },
    vdemOfficial: { label: "V-Dem Institute (fuente original)", href: "https://www.v-dem.net/data/the-v-dem-dataset/" },
    sheets: { label: "fichas de cada salvaguarda, con su fuente primaria", href: "#fichas" },
  };
  const goodwill = m.byClass.buena_voluntad.length;
  const late = m.byClass.tercero_tarde.length;
  const inTime = m.byClass.tercero_a_tiempo.length;
  const dl = data.decree_laws;
  const cur = m.current;
  const govRows = dl.governments.map((g) => ({
    id: g.id,
    label: `${g.president} (${g.start.slice(0, 4)}–${g.end ? g.end.slice(0, 4) : "hoy"})`,
    swatch: PARTY_COLORS[g.party],
    rdl: g.rdl_per_month,
    laws: g.laws_per_month,
  }));
  const annual = dl.annual;
  const partial = dl.partial_year;
  const legBands = data.legislatures
    .filter((_, i) => i % 2 === 0)
    .map((l) => ({ from: Number(l.start.slice(0, 4)) + Number(l.start.slice(5, 7)) / 12, to: l.end ? Number(l.end.slice(0, 4)) + Number(l.end.slice(5, 7)) / 12 : partial + 1, color: "#17191f", opacity: 0.04 }));
  const fz = m.fz;
  const freezerRows = Object.keys(BUCKETS)
    .map((id) => ({ id, s: fz.summary.find((r) => r.bucket === id) }))
    .filter((r) => r.s)
    .map(({ id, s }) => ({
      id,
      label: `${BUCKETS[id]} (${s.bills})`,
      value: s.median_extensions,
      color: id === "gobierno" || id === "grupos_gobierno" ? "#eb6834" : "#52514e",
      note: `· ${s.still_in_amendments} de ${s.bills} siguen en enmiendas`,
    }));
  const vdemPanels = [
    ["libdem", "Democracia liberal"],
    ["jucon", "Límites judiciales al Ejecutivo"],
    ["legcon", "Límites legislativos al Ejecutivo"],
  ];
  const vdemColors = { ESP: "#2a78d6", DEU: "#b4b2a9", FRA: "#b4b2a9", ITA: "#b4b2a9", PRT: "#b4b2a9", POL: "#eb6834", HUN: "#b23a48" };
  const mapRows = m.byClass.buena_voluntad.concat(m.byClass.tercero_tarde, m.byClass.tercero_a_tiempo);
  const partyRows = m.partyRows;
  const party = (p) => partyRows.find((r) => r.party === p) || { episodes: 0, per10: 0, safeguards: 0, years: 0 };
  const context = data.context || {};
  const pending = data.pending || [];
  const inReview = pending.filter((p) => p.status !== "pendiente_documentar");
  const undocumented = pending.filter((p) => p.status === "pendiente_documentar");
  const esPrev = m.atYear("libdem", "ESP", 2015);
  const delayRows = m.delays.map((d) => ({
    id: `${d.safeguard}-${d.episode}`,
    label: `${d.ruling || d.by} (${d.ruling_date.slice(0, 4)})`,
    value: d.days,
    color: PARTY_COLORS[partyOf(data.governments, d.government)] || "#52514e",
  }));
  const ld = [
    breadcrumbLd([
      { name: "Inicio", path: "/" },
      { name: "Visualizaciones", path: "/visualizaciones/" },
      { name: "Separación de poderes", path: seo.path },
    ]),
    datasetLd({
      path: seo.path,
      name: "Salvaguardas de la separación de poderes en España",
      description: seo.description,
      keywords: ["separación de poderes", "decretos-leyes", "CGPJ", "presupuestos", "V-Dem"],
      temporalCoverage: `1979/${data.snapshot_date.slice(0, 4)}`,
      distribution: [
        { encodingFormat: "text/csv", contentUrl: "/visualizaciones/data/democracia.csv" },
        { encodingFormat: "application/json", contentUrl: "/visualizaciones/data/democracia.json" },
      ],
    }),
  ];

  return (
    <main className="shell vizArticle">
      <JsonLd data={ld} />
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title={`Separación de poderes: ${goodwill} de las ${m.n} reglas revisadas que limitan al poder en España no tienen quien las haga cumplir`}
        summary={`Dónde puede romperse la democracia española, salvaguarda a salvaguarda: qué ordena cada regla, quién puede obligar a cumplirla, cuánto tarda el remedio, cada vez que se incumplió o se forzó desde 1978 con el Gobierno que había entonces, y cómo resuelven el mismo bloqueo Alemania, Francia, Italia y Portugal. Cada dato enlaza su fuente primaria.${pending.length ? ` Publicadas ${m.n} fichas revisadas; ${pending.length} más están en revisión o pendientes de documentar.` : ""}`}
        actions={[
          { href: "/visualizaciones/data/democracia.csv", label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/democracia.json", label: "JSON con procedencia" },
          { href: "#mapa", label: "El mapa de salvaguardas" },
          { href: "#fichas", label: "Fichas con fuentes" },
        ]}
      />

      <section className="card vizProse" id="resumen" aria-labelledby="resumen-title">
        <h2 id="resumen-title">Lo esencial, con sus cifras</h2>
        <ol>
          <li>
            <strong>
              {goodwill} de las {m.n} salvaguardas revisadas dependen de la buena voluntad de quien debe cumplirlas.
            </strong>{" "}
            Si no se cumplen, nadie puede obligar ni sustituir: solo queda el coste político. Otras {late} tienen un tercero que puede anular u obligar, pero llega tarde (cuando el acto ya produjo sus efectos), y {inTime} se cumplen solas o con un tercero a tiempo. En {m.goodwillWithAnyPeerFix} de las {goodwill} que dependen de la buena voluntad en España, al menos uno de los países comparados resuelve el mismo bloqueo con un tercero; de las {m.peerCellsGoodwill} comparaciones posibles con Alemania, Francia, Italia y Portugal, {m.peerWithData} tienen fuente y {m.peerThirdParty} de ellas dan con un tercero (las demás quedan sin dato).
          </li>
          {m.longest ? (
            <li>
              <strong>
                El mandato más largo caducado: {num(m.longest.days_expired)} días ({m.longest.body}, {m.longest.term}).
              </strong>{" "}
              La renovación exige tres quintos de las Cámaras, de modo que ningún partido puede renovar solo y cualquier minoría de bloqueo puede impedirlo; la Constitución no prevé qué pasa si el plazo vence.
            </li>
          ) : null}
          <li>
            <strong>
              {m.prorrogued.length} años sin presupuesto nuevo desde {m.budgetFirst} ({m.prorrogued.join(", ")}).
            </strong>{" "}
            El artículo 134.4 prorroga automáticamente el anterior, así que el Estado no se paraliza, pero el deber de presentar las cuentas a tiempo no tiene sanción.
          </li>
          <li>
            <strong>
              Decretos-leyes: {num(cur.rdl_per_month, 2)} al mes con {cur.president}, frente a {num(m.maxEarlierRate, 2)} como máximo de los gobiernos anteriores.
            </strong>{" "}
            Su peso sobre el total de normas con rango de ley sube más ({num(cur.rdl_share, 0)} %) porque se aprueban muchas menos leyes al mes ({num(cur.laws_per_month, 2)} frente a {num(Math.min(...dl.governments.slice(0, -1).map((g) => g.laws_per_month)), 2)} del gobierno anterior con menos).
          </li>
          <li>
            <strong>
              En los índices de expertos, España sigue entre las democracias liberales: {num(m.libdem.ESP, 2)} sobre 1 en {m.libdemYear} (V-Dem).
            </strong>{" "}
            Alemania {num(m.libdem.DEU, 2)}, Francia {num(m.libdem.FRA, 2)}, Italia {num(m.libdem.ITA, 2)}, Portugal {num(m.libdem.PRT, 2)}; Polonia {num(m.libdem.POL, 2)} y Hungría {num(m.libdem.HUN, 2)}. España estaba en {num(esPrev, 2)} en 2015.
          </li>
        </ol>
      </section>

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Salvaguardas que dependen de la buena voluntad</span>
          <span className="vizStat__value">
            {goodwill} de {m.n}
          </span>
          <span className="vizStat__note">
            {late} se hacen cumplir tarde y {inTime} a tiempo
          </span>
        </div>
        {m.longest ? (
          <div className="card vizStat">
            <span className="vizStat__label">Mandato caducado más largo</span>
            <span className="vizStat__value">{num(m.longest.days_expired)} días</span>
            <span className="vizStat__note">
              {m.longest.body}, {m.longest.mandate_end.slice(0, 4)}–{m.longest.successor_took_office ? m.longest.successor_took_office.slice(0, 4) : "hoy"}
            </span>
          </div>
        ) : null}
        <div className="card vizStat">
          <span className="vizStat__label">
            Años con presupuesto prorrogado, {m.budgetFirst}–{m.budgetLast}
          </span>
          <span className="vizStat__value">{m.prorrogued.length}</span>
          <span className="vizStat__note">{m.prorrogued.join(", ")}</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Decretos-leyes por mes, gobierno actual</span>
          <span className="vizStat__value">{num(cur.rdl_per_month, 2)}</span>
          <span className="vizStat__note">
            Máximo anterior: {num(m.maxEarlierRate, 2)}. Leyes por mes: {num(cur.laws_per_month, 2)}
          </span>
        </div>
      </section>

      <Figure
        id="mapa"
        title={`Mapa de salvaguardas: de las ${m.n} revisadas, ${goodwill} dependen de la buena voluntad, ${late} se hacen cumplir tarde y ${inTime} a tiempo; los incumplimientos documentados se reparten entre gobiernos de todos los partidos`}
        dek={`Una fila por regla: quién la hace cumplir, qué pasa si se ignora, cuánto tarda el remedio, cada episodio desde 1978 coloreado por el partido que gobernaba, y en cuatro casillas cómo resuelven el mismo bloqueo Alemania (DE), Francia (FR), Italia (IT) y Portugal (PT). Zanja dos relatos: «solo lo hace un lado» (hay episodios atribuidos a gobiernos del PSOE en ${party("PSOE").safeguards} salvaguardas y del PP en ${party("PP").safeguards}) y «las instituciones se defienden solas» (${goodwill} reglas no tienen a nadie que obligue a cumplirlas). Queda abierto cuánto pesa cada episodio: el mapa cuenta hechos, no mide su gravedad.`}
        sources={[S.sheets, S.boe]}
        notes={[
          `Clase fijada antes de documentar: «a tiempo» si un tercero puede obligar, anular o sustituir y el efecto llega antes de que el incumplimiento se consume (o en seis meses si es continuado); «tarde» si llega después; «buena voluntad» si nadie puede obligar ni sustituir. Ante la duda, la más débil.`,
          `Episodios: ● incumplimiento declarado por un tribunal u órgano competente; ○ tensión (uso en el límite discutido por órganos oficiales, sin declaración de incumplimiento); ▬ plazo vencido, de inicio a fin; ◇ aval o remedio. Color: partido del Gobierno en la fecha; gris, cuando la decisión era de una mayoría reforzada o de otro órgano (las fichas dicen qué partidos eran indispensables).`,
          `Retraso del remedio: días entre el acto y la resolución que lo corrige, según lo que se mide en cada ficha.`,
        ]}
        table={
          <details className="vizTable">
            <summary>Ver el mapa en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Salvaguarda</th>
                    <th scope="col">Clase</th>
                    <th scope="col">Quién la hace cumplir</th>
                    <th scope="col">Sanción</th>
                    <th scope="col">Retraso (días)</th>
                    <th scope="col">Episodios</th>
                    {PEER_CODES.map((c) => (
                      <th scope="col" key={c}>
                        {COUNTRY[c]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {mapRows.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <a href={`#s-${s.id}`}>{s.name}</a>
                      </td>
                      <td>{CLASS_SHORT[s.classification]}</td>
                      <td>{s.enforcer.who}</td>
                      <td>{s.sanction}</td>
                      <td>{s.remedy_delay?.days == null ? "—" : num(s.remedy_delay.days)}</td>
                      <td>{s.episodes.length}</td>
                      {PEER_CODES.map((c) => (
                        <td key={c}>{CLASS_SHORT[s.peers[c]?.classification] || "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <Explain
          shows="Todas las reglas que separan los poderes y que este análisis ha documentado, con lo que pasa cuando alguien no las cumple y cómo lo resuelven los países vecinos."
          read="Las filas van de las más débiles (rojo: nadie puede obligar) a las más sólidas (verde). La línea de cada fila es el tiempo, de 1978 a hoy: cada marca es un episodio, del color del partido que gobernaba. Las cuatro casillas DE, FR, IT y PT dicen si en Alemania, Francia, Italia y Portugal el mismo bloqueo lo resuelve un tercero (verde o ámbar) o también depende de la buena voluntad (rojo); en gris, los países sin fuente comprobada. Pase el cursor por una marca o abra la ficha para ver el hecho y su fuente."
          not="No mide la gravedad de cada episodio ni compara intenciones. Una regla sin episodios no está probada como fuerte: puede que nadie la haya puesto a prueba. Los recuentos dependen de lo que se recurrió y de lo que llegó a juicio, y los años recientes están mejor documentados."
        />
        <MapLegend />
        <SafeguardMap safeguards={mapRows} governments={data.governments} snapshot={data.snapshot_date} maxDelay={m.maxDelay} />
        {inReview.length ? (
          <p className="vizFigure__dek">
            En revisión ({inReview.length}), se publicarán cuando una revisión independiente las verifique: {inReview.map((p) => p.name).join(" · ")}.
          </p>
        ) : null}
        {undocumented.length ? (
          <p className="vizFigure__dek">
            Pendientes de documentar ({undocumented.length}), solo con su referencia legal:{" "}
            {undocumented.map((p, i) => (
              <span key={p.id}>
                {i ? " · " : ""}
                {p.name} (
                <a href={p.rule.url} rel="noopener noreferrer" target="_blank">
                  {p.rule.articles.join(", ")}
                </a>
                )
              </span>
            ))}
            .
          </p>
        ) : null}
      </Figure>

      <Figure
        id="todos-los-partidos"
        title={`Episodios atribuidos a cada partido de gobierno: ${party("PSOE").episodes} con el PSOE (${num(party("PSOE").per10, 1)} por cada diez años de gobierno) y ${party("PP").episodes} con el PP (${num(party("PP").per10, 1)})`}
        dek={`Incumplimientos declarados, tensiones y plazos vencidos que la ficha atribuye al Gobierno de la fecha (${m.attributedCount} de ${m.episodesCount} episodios; el resto son de mayorías reforzadas, de otros órganos, o avales y remedios). Dividir por los años de gobierno evita premiar a quien gobernó menos. ${m.recent} de los ${m.attributedCount} son de 2004 en adelante, y una sola ficha pesa mucho: los decretos-leyes anulados o derogados son ${party("PP").decreeLaws} de los ${party("PP").episodes} episodios del PP y ${party("PSOE").decreeLaws} de los ${party("PSOE").episodes} del PSOE. La documentación disponible y la litigiosidad (quién recurre y cuánto tarda el TC) cambian con el tiempo, así que esta cifra no basta para decir que un gobierno incumple más que otro.`}
        sources={[S.sheets]}
        table={
          <details className="vizTable">
            <summary>Ver en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Partido del Gobierno</th>
                    <th scope="col">Episodios</th>
                    <th scope="col">De ellos, declarados</th>
                    <th scope="col">Salvaguardas afectadas</th>
                    <th scope="col">Años de gobierno desde 1979</th>
                    <th scope="col">Episodios por diez años</th>
                    <th scope="col">De ellos, decretos-leyes</th>
                  </tr>
                </thead>
                <tbody>
                  {partyRows.map((r) => (
                    <tr key={r.party}>
                      <td>{r.party}</td>
                      <td>{r.episodes}</td>
                      <td>{r.declared}</td>
                      <td>{r.safeguards}</td>
                      <td>{num(r.years, 1)}</td>
                      <td>{num(r.per10, 1)}</td>
                      <td>{r.decreeLaws}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <PairedBars
          ariaLabel="Episodios por partido de gobierno"
          rows={partyRows.map((r) => ({ id: r.party, label: `Gobierno ${r.party} (${num(r.years, 1)} años)`, swatch: PARTY_COLORS[r.party], episodes: r.episodes, per10: r.per10 }))}
          keys={[
            { key: "episodes", color: "#52514e" },
            { key: "per10", color: "#b4b2a9" },
          ]}
          digits={1}
        />
        <p className="vizFigure__dek">Barra oscura: episodios; barra clara: episodios por cada diez años de gobierno (misma escala).</p>
      </Figure>

      <Figure
        id="decretos-ley"
        title={`Decretos-leyes y leyes por año desde 1979: ${num(cur.rdl_per_month, 2)} decretos-leyes al mes con ${cur.president}, frente a ${num(m.maxEarlierRate, 2)} como máximo antes; las leyes bajan a ${num(cur.laws_per_month, 2)} al mes`}
        dek={`Cuenta todas las normas con rango de ley del Estado publicadas en el BOE (decretos-leyes, leyes y leyes orgánicas) por año y por gobierno. El número oficial más alto de cada año coincide con el recuento, así que la serie está completa. El decreto-ley no es ilegítimo en sí: la Constitución lo admite «en caso de extraordinaria y urgente necesidad» y el Congreso debe convalidarlo en 30 días. ${partial} está incompleto (hasta ${dl.retrieved_at.slice(0, 10)}).`}
        legend={[
          { id: "rdl", label: "Decretos-leyes", color: "#b23a48" },
          { id: "laws", label: "Leyes y leyes orgánicas", color: "#52514e" },
        ]}
        sources={[S.boe]}
        notes={[`Bandas: legislaturas alternas. Gobierno: el del día de la norma (incluidos los gobiernos en funciones).`]}
        table={
          <details className="vizTable">
            <summary>Ver todos los años y gobiernos en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Año</th>
                    <th scope="col">Decretos-leyes</th>
                    <th scope="col">Leyes</th>
                    <th scope="col">Leyes orgánicas</th>
                    <th scope="col">% decretos-leyes</th>
                  </tr>
                </thead>
                <tbody>
                  {[...annual].reverse().map((r) => (
                    <tr key={r.year}>
                      <td>{r.year === partial ? `${r.year} (parcial)` : r.year}</td>
                      <td>{r.rdl}</td>
                      <td>{r.l}</td>
                      <td>{r.lo}</td>
                      <td>{num(r.rdl_share, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Gobierno</th>
                    <th scope="col">Meses</th>
                    <th scope="col">Decretos-leyes</th>
                    <th scope="col">Leyes</th>
                    <th scope="col">Decretos-leyes al mes</th>
                    <th scope="col">Leyes al mes</th>
                  </tr>
                </thead>
                <tbody>
                  {dl.governments.map((g) => (
                    <tr key={g.id}>
                      <td>
                        {g.president} ({g.party})
                      </td>
                      <td>{num(g.months, 1)}</td>
                      <td>{g.rdl}</td>
                      <td>{g.laws}</td>
                      <td>{num(g.rdl_per_month, 2)}</td>
                      <td>{num(g.laws_per_month, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <Explain
          shows="Cuántas normas con rango de ley aprueba el Gobierno por decreto y cuántas pasan por las Cortes como ley, cada año y con cada presidente."
          read="Arriba, una línea por tipo de norma (misma escala, desde cero). Abajo, el ritmo mensual de cada gobierno: barra roja, decretos-leyes; gris, leyes. Al dividir por meses, los gobiernos cortos y largos se comparan igual."
          not="No dice si cada decreto-ley era urgente: eso solo lo decide el Tribunal Constitucional caso a caso (ver la ficha). Una legislatura sin mayoría aprueba menos leyes por razones que esta serie no separa."
        />
        <LineChart
          ariaLabel="Decretos-leyes y leyes por año"
          unitLabel="Normas por año"
          xMin={1979}
          xMax={partial}
          bands={legBands}
          series={[
            { id: "laws", label: "Leyes", color: "#52514e", points: annual.map((r) => ({ year: r.year, value: r.laws })) },
            { id: "rdl", label: "Decretos-leyes", color: "#b23a48", width: 2.5, points: annual.map((r) => ({ year: r.year, value: r.rdl })) },
          ]}
        />
        <PairedBars
          ariaLabel="Decretos-leyes y leyes al mes por gobierno"
          rows={govRows}
          keys={[
            { key: "rdl", color: "#b23a48" },
            { key: "laws", color: "#52514e" },
          ]}
        />
      </Figure>

      {m.mandates.length ? (
        <Figure
          id="mandatos-caducados"
          title={`Días con el mandato caducado: el récord, ${num(m.longest.days_expired)} días (${m.longest.body}, ${m.longest.term})`}
          dek="Días entre el fin legal de cada mandato y la toma de posesión de quienes lo sustituyen. Estos órganos se renuevan por mayorías de tres quintos: ningún partido puede renovarlos solo, y ninguna norma dice qué pasa si el plazo vence; mientras, siguen los anteriores."
          sources={[S.sheets]}
          table={
            <details className="vizTable">
              <summary>Ver todos los mandatos en tabla</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Órgano</th>
                      <th scope="col">Mandato</th>
                      <th scope="col">Fin legal</th>
                      <th scope="col">Toma de posesión del sustituto</th>
                      <th scope="col">Días caducado</th>
                      <th scope="col">Fuente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.mandates.map((r, i) => (
                      <tr key={`${r.safeguard}-${r.term}-${i}`}>
                        <td>{r.body}</td>
                        <td>{r.term}</td>
                        <td>{r.mandate_end}</td>
                        <td>{r.successor_took_office || "pendiente"}</td>
                        <td>{num(r.days_expired)}</td>
                        <td>
                          <SourceLinks sources={r.sources} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          }
        >
          <HBars
            ariaLabel="Días con el mandato caducado"
            unit=" días"
            rows={m.mandates.map((r, i) => ({ id: `${r.safeguard}-${r.term}-${i}`, label: `${r.body}, ${r.term}`, value: r.days_expired, color: r.ongoing ? "#b23a48" : "#52514e", note: r.ongoing ? "(sigue)" : "" }))}
          />
        </Figure>
      ) : null}

      <Figure
        id="presupuestos"
        title={`${m.prorrogued.length} de ${m.budgetLast - m.budgetFirst + 1} años sin presupuesto nuevo (${m.budgetFirst}–${m.budgetLast}), ${m.prorrogued.filter((y) => y >= 2019).length} de ellos desde 2019`}
        dek="Cada casilla es un año: verde si la Ley de Presupuestos se publicó antes del 1 de enero, ámbar si llegó con el año empezado, rojo si no hubo ley y rigió la prórroga del año anterior todo el año. La línea fina de debajo es el partido que gobernaba el 1 de enero. La Constitución obliga a presentar el proyecto tres meses antes de que acabe el año (art. 134.3), pero no prevé sanción; la prórroga automática (art. 134.4) evita la parálisis."
        legend={Object.keys(BUDGET_COLORS).map((k) => ({ id: k, label: BUDGET_LABELS[k], color: BUDGET_COLORS[k] }))}
        legendKind="bar"
        sources={[S.boeBudget]}
        notes={["Leyes de Presupuestos Generales del Estado «para el año» de la base de legislación consolidada del BOE; las de 1979 a 1982 no figuran en ella y quedan fuera de la serie."]}
        table={
          <details className="vizTable">
            <summary>Ver todos los años en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Año</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Ley</th>
                    <th scope="col">Publicada</th>
                    <th scope="col">Gobierno el 1 de enero</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.budgets.years].reverse().map((y) => (
                    <tr key={y.year}>
                      <td>{y.year}</td>
                      <td>{BUDGET_LABELS[y.status]}</td>
                      <td>{y.law ? <a href={y.law.url}>{y.law.law}</a> : "—"}</td>
                      <td>{y.law?.published || "—"}</td>
                      <td>{data.governments.find((g) => g.id === y.government_on_jan1)?.president}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <YearStrip
          years={data.budgets.years}
          statusColors={BUDGET_COLORS}
          statusLabels={BUDGET_LABELS}
          partyOf={(y) => partyOf(data.governments, y.government_on_jan1)}
        />
      </Figure>

      {m.delays.length ? (
        <Figure
          id="retraso"
          title={`Cuando hay un tercero, llega tarde: mediana de ${num(m.medianDelay)} días entre el acto y la resolución que lo corrige o lo avala`}
          dek="Cada barra es un acto recurrido de las fichas (decreto-ley, estado de alarma, nombramiento…) y el tiempo hasta la sentencia o resolución. Color: partido del Gobierno autor del acto; gris, otros órganos. Muchas de estas resoluciones llegaron cuando el acto ya había agotado sus efectos."
          sources={[S.sheets]}
          table={
            <details className="vizTable">
              <summary>Ver en tabla</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Resolución</th>
                      <th scope="col">Órgano</th>
                      <th scope="col">Fecha del acto</th>
                      <th scope="col">Fecha de la resolución</th>
                      <th scope="col">Días</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.delays.map((d) => (
                      <tr key={`${d.safeguard}-${d.episode}`}>
                        <td>
                          <a href={`#s-${d.safeguard}`}>{d.ruling}</a>
                        </td>
                        <td>{d.by}</td>
                        <td>{d.act_date}</td>
                        <td>{d.ruling_date}</td>
                        <td>{num(d.days)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          }
        >
          <HBars ariaLabel="Días hasta la resolución" unit=" días" rows={delayRows} />
        </Figure>
      ) : null}

      <Figure
        id="congelador"
        title={`El «congelador» del Congreso: ${num(fz.total_extensions)} ampliaciones semanales del plazo de enmiendas en ${fz.bills_in_amendments} iniciativas de la XV legislatura; mediana de ${m.bucket("gobierno").median_extensions} para los proyectos del Gobierno y de ${m.bucket("senado").median_extensions} para las proposiciones del Senado`}
        dek={`La Mesa del Congreso (mayoría de PSOE y Sumar en esta legislatura) amplía cada semana el plazo de enmiendas; mientras está abierto, la iniciativa no avanza. Mediana de ampliaciones por iniciativa según su autor, y cuántas seguían en enmiendas en el corte de los datos (${fz.snapshot_date}). Se amplían también los proyectos del propio Gobierno: la ampliación sirve tanto para negociar como para frenar, y los datos no dicen cuál de las dos cosas pasa en cada caso.`}
        sources={[S.congreso]}
        notes={["Cuenta las entradas «Ampliación de enmiendas» y «Ampliación de enmiendas al articulado» del calendario de plazos de cada iniciativa (proyectos 121, proposiciones 122, 124 y 125). Solo XV legislatura: no hay serie comparable de legislaturas anteriores ni del Senado en la base del proyecto. Las ampliaciones las acuerda la Mesa, normalmente a petición de algún grupo; los datos abiertos no dicen de quién."]}
        table={
          <details className="vizTable">
            <summary>Ver las {fz.bills.length} iniciativas en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Expediente</th>
                    <th scope="col">Título</th>
                    <th scope="col">Autor</th>
                    <th scope="col">Ampliaciones</th>
                    <th scope="col">Días en enmiendas</th>
                    <th scope="col">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {fz.bills.map((b) => (
                    <tr key={b.expediente}>
                      <td>{b.expediente}</td>
                      <td>{b.title}</td>
                      <td>{b.author}</td>
                      <td>{b.extensions}</td>
                      <td>{num(b.days_in_amendments)}</td>
                      <td>{b.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        }
      >
        <HBars ariaLabel="Mediana de ampliaciones por autor" rows={freezerRows} unit=" ampliaciones (mediana)" />
      </Figure>

      <Figure
        id="pares"
        title={`Índices de V-Dem: España en ${num(m.libdem.ESP, 2)} de democracia liberal (${m.libdemYear}), por debajo de su máximo (${num(m.esPeak.value, 2)} en ${m.esPeak.year}) y lejos de Hungría (${num(m.libdem.HUN, 2)})`}
        dek="Tres índices de V-Dem (0 a 1), el mismo eje en los tres paneles. España en azul; Alemania, Francia, Italia y Portugal en gris; Polonia y Hungría, los dos casos de erosión documentados por la Comisión de Venecia y la Comisión Europea, en naranja y rojo. Los índices son juicios de expertos agregados por un modelo, con margen de error (no se dibuja: V-Dem lo publica en su base)."
        sources={[S.vdem, S.vdemOfficial]}
        notes={["Se usa la copia de Our World in Data porque la descarga oficial de V-Dem pasa por un formulario web. Estimación central de v2x_libdem, v2x_jucon y v2xlg_legcon."]}
        table={
          <details className="vizTable">
            <summary>Ver los valores en tabla</summary>
            <div className="vizTable__scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Índice</th>
                    <th scope="col">Año</th>
                    {data.vdem.countries.map((c) => (
                      <th scope="col" key={c}>
                        {COUNTRY[c]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {vdemPanels.flatMap(([key, label]) =>
                    [2000, 2010, 2015, 2020, m.libdemYear].map((year) => (
                      <tr key={`${key}-${year}`}>
                        <td>{label}</td>
                        <td>{year}</td>
                        {data.vdem.countries.map((c) => (
                          <td key={c}>{num(m.atYear(key, c, year), 3)}</td>
                        ))}
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          </details>
        }
        legend={["ESP", "POL", "HUN", "DEU"].map((c) => ({ id: c, label: c === "DEU" ? "Alemania, Francia, Italia y Portugal" : COUNTRY[c], color: vdemColors[c] }))}
      >
        <div className="demoMultiples">
          {vdemPanels.map(([key, label]) => (
            <div key={key}>
              <h3>{label}</h3>
              <LineChart
                ariaLabel={`${label}, V-Dem`}
                height={260}
                width={380}
                rightMargin={64}
                yMax={1}
                digits={1}
                xMin={1975}
                xMax={m.libdemYear}
                series={["DEU", "FRA", "ITA", "PRT", "POL", "HUN", "ESP"].map((c) => ({
                  id: c,
                  label: COUNTRY[c],
                  shortLabel: c === "ESP" || c === "POL" || c === "HUN" ? COUNTRY[c] : undefined,
                  noEndLabel: !["ESP", "POL", "HUN"].includes(c),
                  color: vdemColors[c],
                  width: c === "ESP" ? 2.6 : 1.4,
                  dash: c === "POL" || c === "HUN" ? "5 3" : undefined,
                  points: data.vdem.indices[key][c],
                }))}
              />
            </div>
          ))}
        </div>
      </Figure>

      {context.erosion?.length ? (
        <section className="card vizProse" id="erosion" aria-labelledby="erosion-title">
          <h2 id="erosion-title">{context.title}</h2>
          <p>{context.intro}</p>
          <div className="demoScrollX">
            <table className="demoErosion">
              <thead>
                <tr>
                  <th scope="col">Lo que se erosionó</th>
                  <th scope="col">Polonia</th>
                  <th scope="col">Hungría</th>
                  <th scope="col">En España</th>
                </tr>
              </thead>
              <tbody>
                {context.erosion.map((row) => (
                  <tr key={row.id}>
                    <td>{row.what}</td>
                    <td>
                      {row.POL?.text === "no_signal" ? "Sin dato en las fuentes consultadas." : row.POL?.text} <SourceLinks sources={row.POL?.sources} />
                    </td>
                    <td>
                      {row.HUN?.text === "no_signal" ? "Sin dato en las fuentes consultadas." : row.HUN?.text} <SourceLinks sources={row.HUN?.sources} />
                    </td>
                    <td>
                      {row.ESP?.text}{" "}
                      {row.ESP?.safeguard ? (
                        <a href={`#s-${row.ESP.safeguard}`}>({CLASS_SHORT[data.safeguards.find((s) => s.id === row.ESP.safeguard)?.classification] || "ficha"})</a>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {context.conclusion ? <p>{context.conclusion}</p> : null}
        </section>
      ) : null}

      <section className="card vizProse" id="limites" aria-labelledby="limites-title">
        <h2 id="limites-title">Lo que estos datos no pueden decir</h2>
        <ul>
          <li>Los índices (V-Dem y similares) son juicios de expertos agregados con un modelo, no medidas directas. Sirven para comparar países y años, no para fechar un deterioro concreto.</li>
          <li>Una regla que nunca se ha incumplido no está probada como fuerte: puede que nadie haya tenido incentivo para ponerla a prueba.</li>
          <li>Los recuentos de episodios dependen de lo que alguien recurrió y de lo que llegó a juicio, y la documentación de los años recientes es más completa que la de los ochenta.</li>
          <li>Atribuir un episodio a quien gobernaba no dice nada de sus motivos. En las renovaciones por tres quintos, el bloqueo es de quien tiene la minoría de bloqueo y también de quien no logra el acuerdo: las fichas listan a todos los partidos cuyos votos eran indispensables.</li>
          <li>La clase de cada salvaguarda es una decisión de este análisis con un criterio escrito antes de documentar; las fichas explican cada caso y se pueden discutir con la fuente delante.</li>
          <li>No hay previsiones: el mapa dice dónde la regla depende de la buena voluntad, no si alguien la va a dejar de cumplir.</li>
        </ul>
      </section>

      <section className="card vizProse" id="fichas" aria-labelledby="fichas-title">
        <h2 id="fichas-title">Las {m.n} fichas, con sus fuentes</h2>
        <p>Cada ficha trae la regla con su enlace oficial, quién la hace cumplir, la sanción, el retraso del remedio, todos los episodios con la autoridad que los tenía a su cargo y la fuente primaria, y cómo se resuelve el mismo bloqueo en los cuatro países comparados.</p>
        <div className="demoSheets">
          {mapRows.map((s) => (
            <details className="demoSheet" id={`s-${s.id}`} key={s.id}>
              <summary>
                <span className="demoPill" style={{ background: CLASS_COLORS[s.classification] }}>
                  {CLASS_SHORT[s.classification]}
                </span>{" "}
                {s.name}
              </summary>
              <dl>
                <dt>Regla</dt>
                <dd>
                  {s.rule.text} (
                  <a href={s.rule.url} rel="noopener noreferrer" target="_blank">
                    {s.rule.articles.join(", ")}
                  </a>
                  ){s.rule.deadline ? `. Plazo: ${s.rule.deadline}` : ""}
                </dd>
                <dt>Debe cumplirla</dt>
                <dd>{s.obligated}</dd>
                <dt>Quién la hace cumplir</dt>
                <dd>{s.enforcer.who}</dd>
                <dt>Sanción</dt>
                <dd>{s.sanction}</dd>
                <dt>Retraso del remedio</dt>
                <dd>
                  {s.remedy_delay?.days == null ? "Sin remedio de tercero. " : `${num(s.remedy_delay.days)} días. `}
                  {s.remedy_delay?.basis} <SourceLinks sources={s.remedy_delay?.sources} />
                </dd>
                <dt>Clase</dt>
                <dd>
                  {CLASS_LABELS[s.classification]}. {s.classification_reason}
                </dd>
                <dt>Lo que la ficha no dice</dt>
                <dd>{s.limits}</dd>
              </dl>
              {s.episodes.length ? (
                <div className="vizTable__scroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Fechas</th>
                        <th scope="col">Tipo</th>
                        <th scope="col">Qué pasó</th>
                        <th scope="col">Quién tenía el poder</th>
                        <th scope="col">Fuente</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.episodes.map((ep) => (
                        <tr key={ep.id}>
                          <td>
                            {ep.start}
                            {ep.end ? ` a ${ep.end}` : ep.kind === "plazo_vencido" ? " (sigue)" : ""}
                          </td>
                          <td>
                            <span className="demoSwatch" style={{ background: PARTY_COLORS[partyOfEpisode(ep, data.governments)] || "#52514e" }} aria-hidden="true" />
                            {KIND_LABELS[ep.kind]}
                          </td>
                          <td>
                            {ep.summary}
                            {ep.remedy ? ` (${ep.remedy.by}${ep.remedy.ruling ? `, ${ep.remedy.ruling}` : ""}, ${ep.remedy.date})` : ""}
                          </td>
                          <td>
                            {powerText(ep, data.governments)}
                            {ep.arithmetic?.length ? <Arithmetic rows={ep.arithmetic} /> : null}
                          </td>
                          <td>
                            <SourceLinks sources={ep.sources} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>Sin episodios documentados.</p>
              )}
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">País</th>
                      <th scope="col">Cómo resuelve el mismo bloqueo</th>
                      <th scope="col">Clase</th>
                      <th scope="col">Fuente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {PEER_CODES.map((c) => (
                      <tr key={c}>
                        <td>{COUNTRY[c]}</td>
                        <td>{s.peers[c]?.mechanism}</td>
                        <td>{CLASS_SHORT[s.peers[c]?.classification]}</td>
                        <td>
                          <SourceLinks sources={s.peers[c]?.sources} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ))}
        </div>
      </section>

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y datos</h2>
        <p>
          Inventario de {m.n} salvaguardas de la separación de poderes, documentadas con fuentes primarias (BOE, Tribunal Constitucional, Cortes, CGPJ, Comisión de Venecia, Comisión Europea y el texto legal de cada país comparado). El criterio de clasificación y de atribución se fijó antes de documentar, y cada ficha pasó una revisión independiente que comprobó fechas, atribución, texto legal y cifras contra sus fuentes. Las series (normas por año, presupuestos, ampliaciones de plazos, V-Dem) se recalculan desde la copia guardada de cada fuente, con su huella sha256.
        </p>
        <p>
          Descargas: <a href="/visualizaciones/data/democracia.csv">CSV</a> · <a href="/visualizaciones/data/democracia.json">JSON con procedencia</a>. Instantánea de {data.snapshot_date}.
        </p>
      </section>
    </main>
  );
}
