import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure, { SeriesTable } from "../components/Figure";
import { formatValue } from "../components/format.mjs";
import { StatutoryRatesFigure, ComplexityFigures } from "./sections";
import ConsolidatedBars from "./ConsolidatedBars";
import DistributionFigure from "./Distribution";
import TerritoryFigure from "./Territory";
import { SqueezeFigure, SqueezeIndexFigure, SurveyFigure } from "./Squeeze";
import HouseholdsFigure from "./Households";
import { SpendingSectionIntro, WhereItGoesFigure, DecompositionFigure, LongRunSpendingFigure } from "./WhereItGoes";
import ArticleSeo, { vizArticleMetadata } from "../ArticleSeo";

export const metadata = vizArticleMetadata("carga-fiscal");

const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};

const PEER_LABELS = {
  ESP: "España",
  OECD_REP: "Media OCDE",
  DEU: "Alemania",
  FRA: "Francia",
  ITA: "Italia",
  PRT: "Portugal",
};

const REFORMS = [
  { year: 1940, label: "Reforma Larraz", row: 0 },
  { year: 1957, label: "Navarro Rubio", row: 1 },
  { year: 1964, label: "Reforma 1964", row: 0 },
  { year: 1977, label: "Fernández Ordóñez", row: 1 },
  { year: 1986, label: "IVA", row: 0 },
];

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function points(rows, key = "value") {
  return rows.map((row) => ({ year: row.year, value: row[key] }));
}

export default function CargaFiscalPage() {
  const data = readPublicJson("visualizaciones/data/carga-fiscal.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/carga-fiscal.json");
  const h = data.headline;
  const payers = data.per_capita_payers;
  const src = data.sources;
  const oecdSource = { label: "OCDE, Revenue Statistics", href: src.oecd_revenue_statistics.page };
  const imfSource = { label: "FMI, Public Finances in Modern History", href: src.imf_fpp.page };
  const eurostatTable = (code) => ({ label: `Eurostat, ${code}`, href: `https://ec.europa.eu/eurostat/databrowser/view/${code}/default/table` });
  const householdSources = [
    { label: "OCDE, Taxing Wages (réplica DBnomics)", href: src.oecd_taxing_wages?.page },
    ...["ilc_di03", "ilc_mded03", "icw_tax_02", "icw_tax_03", "prc_ppp_ind", "spr_pns_ben", "gov_10a_exp"].map(eurostatTable),
    { label: "Visualizaciones · Vivienda (alquiler SERPAVI 2024 y salario de 25 a 34 años, con su sha256 en el JSON)", href: "/visualizaciones/vivienda/" },
  ];
  const downloads = "/visualizaciones/data/carga-fiscal.csv";

  // 1. Long run
  const longRun = [
    {
      id: "oecd",
      label: "Impuestos y cotizaciones, todas las AAPP (OCDE)",
      shortLabel: "OCDE",
      color: C.blue,
      emphasis: true,
      points: data.long_run.oecd_tax_pct_gdp,
    },
    {
      id: "imf",
      label: "Ingresos del Estado central (FMI)",
      shortLabel: "FMI",
      color: C.orange,
      points: data.long_run.imf_revenue_pct_gdp.filter((p) => p.year <= 1980),
    },
  ];

  // 2. Per person
  const perCapita = [
    {
      id: "pc",
      label: `Recaudación por habitante (euros de ${h.per_capita_base_year})`,
      shortLabel: String(h.per_capita_last.year),
      color: C.blue,
      points: data.per_capita_real_eur,
    },
  ];
  const pcMultiple = h.per_capita_last.value / h.per_capita_first.value;

  // 3. Who pays
  const payer = data.by_payer_pct_gdp;
  const byPayer = [
    { id: "households", label: "Personas: IRPF + cotizaciones del trabajador y autónomos", shortLabel: "Personas", color: C.blue, points: points(payer, "households") },
    { id: "companies", label: "Empresas: Sociedades + cotizaciones empresariales", shortLabel: "Empresas", color: C.orange, points: points(payer, "companies") },
    { id: "consumption", label: "Consumo: IVA, especiales y otros", shortLabel: "Consumo", color: C.aqua, points: points(payer, "consumption") },
    { id: "property", label: "Propiedad: IBI, patrimonio, sucesiones, transmisiones", shortLabel: "Propiedad", color: C.yellow, points: points(payer, "property") },
  ];
  const first = payer[0];
  const last = payer.at(-1);

  const compCodes = ["T_1100", "T_2100", "T_2300", "T_1200", "T_2200", "T_5000", "T_4000"];
  const compDelta = (code) => data.composition_pct_gdp[code].at(-1).value - data.composition_pct_gdp[code][0].value;
  const compTotal = h.last_value - h.oecd_first_value;
  const compSscIrpf = ["T_1100", "T_2100", "T_2200", "T_2300"].reduce((sum, code) => sum + compDelta(code), 0);
  const compShare = compSscIrpf / compTotal;
  const compMax = Math.max(...compCodes.flatMap((code) => data.composition_pct_gdp[code].map((p) => p.value)));

  // 4. Peers
  const peerOrder = ["DEU", "FRA", "ITA", "PRT", "OECD_REP", "ESP"];
  const peers = peerOrder.map((area) => ({
    id: area,
    label: PEER_LABELS[area],
    color: area === "ESP" ? C.blue : area === "OECD_REP" ? C.ref : C.peer,
    emphasis: area === "ESP",
    points: data.peers_pct_gdp[area],
  }));
  const increases = peerOrder
    .filter((area) => area !== "OECD_REP")
    .map((area) => {
      const rows = data.peers_pct_gdp[area];
      return { area, delta: rows.at(-1).value - rows[0].value, from: rows[0], to: rows.at(-1) };
    })
    .sort((a, b) => b.delta - a.delta);
  const esIncrease = increases.find((item) => item.area === "ESP");
  const esRank = increases.indexOf(esIncrease) + 1;
  const eu = data.eu27_pct_gdp.at(-1);

  // «El dato mata el relato»: level, composition, change and peers in one figure.
  const pc = data.peers_composition;
  const relatoParts = [
    { key: "households", label: "Personas: IRPF y cotizaciones del trabajador y autónomos", short: "personas", color: C.blue },
    { key: "companies", label: "Empresas: Sociedades y cotizaciones empresariales", short: "empresas", color: C.orange },
    { key: "consumption", label: "Consumo: IVA, especiales y otros", short: "consumo", color: C.aqua },
    { key: "property", label: "Propiedad", short: "propiedad", color: C.yellow },
    { key: "other", label: "Otros", short: "otros", color: C.peer },
  ];
  const relatoRows = pc ? [...pc.areas].map((row) => ({ ...row, label: PEER_LABELS[row.area] })).sort((a, b) => b.total - a.total) : [];
  const esRow = relatoRows.find((row) => row.area === "ESP");
  const rankOf = (key, area = "ESP") =>
    [...relatoRows].sort((a, b) => (b[key] || 0) - (a[key] || 0)).findIndex((row) => row.area === area) + 1;
  const growthRank =
    [...relatoRows].sort((a, b) => b.total - b.base_total - (a.total - a.base_total)).findIndex((row) => row.area === "ESP") + 1;
  const above = relatoRows.filter((row) => row.total > (esRow?.total ?? 0) && row.area !== "OECD_REP").map((row) => row.label);
  const ordinal = (n) => (n === 1 ? "la que más" : `la ${n}.ª que más`);
  const relatoMax = Math.ceil(Math.max(...relatoRows.map((row) => row.total), 1) / 10) * 10;
  // «y» becomes «e» before an /i/ sound (Italia), not before Alemania.
  const listJoin = (items) =>
    items.length > 1 ? `${items.slice(0, -1).join(", ")} ${/^h?i(?![aeou])/i.test(items.at(-1)) ? "e" : "y"} ${items.at(-1)}` : items[0] || "";
  const irpfLaw = data.complexity?.amendments?.find((law) => law.boe_id === "BOE-A-2006-20764");
  const irpfLengths = (data.complexity?.law_length || []).filter((row) => row.tax === "irpf").sort((a, b) => a.year - b.year);
  const irpfWords =
    irpfLengths.length > 1 ? { first: irpfLengths[0].words_excl_preamble, last: irpfLengths.at(-1).words_excl_preamble } : null;
  const sqEs = data.squeeze?.areas.find((row) => row.area === "ES");
  const sqEu = data.squeeze?.areas.find((row) => row.area === "EU27_2020");
  const spEs = data.spending?.areas.find((row) => row.area === "ES");
  const ages = data.segments?.income_by_age;
  const ageBase = ages ? String(ages.bases[0]) : null;
  const ageOf = (code) => ages?.areas?.ES?.find((row) => row.age === code);
  const ageOld = ageOf("Y_GE65");
  const ageMid = ageOf("Y25-49");
  const ageAll = ageOf("TOTAL");
  const signedNum = (v) => `${v >= 0 ? "+" : "−"}${num(Math.abs(v))}`;
  const peerMax = Math.max(...peerOrder.flatMap((area) => data.peers_pct_gdp[area].map((p) => p.value)));

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="Cien años de impuestos en España"
        summary="Cuánto recauda el Estado, cuánto les queda a los hogares, quién lo paga, a dónde va y cuánto se ha complicado cumplir. Cada gráfico enlaza su fuente oficial, marca las rupturas de serie y trae sus datos en tabla."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/carga-fiscal.json", label: "JSON con procedencia" },
          { href: "#a-donde-va", label: "¿A dónde va lo recaudado?" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Presión fiscal (impuestos + cotizaciones, % PIB)</span>
          <span className="vizStat__value">×{num(h.multiple_oecd)}</span>
          <span className="vizStat__note">
            {num(h.oecd_first_value)} % en {h.oecd_first_year} → {num(h.last_value)} % en {h.last_year}
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Recaudación real por habitante</span>
          <span className="vizStat__value">×{num(pcMultiple)}</span>
          <span className="vizStat__note">
            {formatValue(h.per_capita_first.value, "eur")} en {h.per_capita_first.year} → {formatValue(h.per_capita_last.value, "eur")} en{" "}
            {h.per_capita_last.year} (euros de {h.per_capita_base_year})
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Ingresos del Estado central en {h.first_year}</span>
          <span className="vizStat__value">{num(h.first_value_imf)} %</span>
          <span className="vizStat__note">del PIB; sin cotizaciones sociales ni haciendas locales (serie FMI)</span>
        </div>
        {ageOld && ageMid ? (
          <div className="card vizStat">
            <span className="vizStat__label">Renta mediana real desde {ageBase}, por edad</span>
            <span className="vizStat__value">
              {signedNum(ageOld.change[ageBase])} % / {signedNum(ageMid.change[ageBase])} %
            </span>
            <span className="vizStat__note">
              65 y más frente a 25 a 49 años (todas las edades: {signedNum(ageAll.change[ageBase])} %)
              {sqEs?.by_base?.[ageBase] ? `; recaudación real por habitante en el mismo periodo, ${signedNum(sqEs.by_base[ageBase].tax)} %` : ""}
            </span>
          </div>
        ) : sqEs ? (
          <div className="card vizStat">
            <span className="vizStat__label">Desde {data.squeeze.base_year}, por habitante y descontada la inflación</span>
            <span className="vizStat__value">+{num(sqEs.real_tax_change_pct)} %</span>
            <span className="vizStat__note">
              de impuestos frente a +{num(sqEs.real_income_change_pct)} % de renta de los hogares (UE: +{num(sqEu.real_tax_change_pct)} % y +
              {num(sqEu.real_income_change_pct)} %)
            </span>
          </div>
        ) : null}
        {spEs ? (
          <div className="card vizStat">
            <span className="vizStat__label">Gasto en pensiones desde {spEs.parts_base_year}</span>
            <span className="vizStat__value">+{num(spEs.parts_change.pensions)} pts</span>
            <span className="vizStat__note">
              del PIB, hasta el {num(spEs.pensions)} %; sanidad {spEs.parts_change.health >= 0 ? "+" : "−"}
              {num(Math.abs(spEs.parts_change.health))}, educación {spEs.parts_change.education >= 0 ? "+" : "−"}
              {num(Math.abs(spEs.parts_change.education))}
            </span>
          </div>
        ) : null}
        {irpfLaw ? (
          <div className="card vizStat">
            <span className="vizStat__label">Normas que han modificado la Ley del IRPF</span>
            <span className="vizStat__value">{irpfLaw.total}</span>
            <span className="vizStat__note">
              desde {String(irpfLaw.enacted).slice(0, 4)}; su texto tiene hoy {irpfWords ? `${num(irpfWords.last / irpfWords.first)} veces` : "más"} las palabras de la ley de 1978
            </span>
          </div>
        ) : null}
      </section>

      {data.squeeze ? (
        <SqueezeFigure squeeze={data.squeeze} distribution={data.distribution} territory={data.territory} segments={data.segments} />
      ) : null}
      {data.segments?.cases ? <HouseholdsFigure segments={data.segments} sources={householdSources} /> : null}
      {data.squeeze?.survey ? <SurveyFigure squeeze={data.squeeze} segments={data.segments} /> : null}

      {esRow ? (
        <Figure
          id="relato"
          title={`España es ${ordinal(growthRank)} ha subido desde ${pc.base_year} y ${ordinal(rankOf("companies"))} recauda de las empresas, pero sigue por debajo de ${listJoin(above)}`}
          dek={`El dato mata el relato: cada barra es lo que recauda cada país en ${pc.year} (% del PIB), repartido por quién lo ingresa; el círculo marca su total en ${pc.base_year}, y la cifra de la derecha, lo que ha subido desde entonces. Nivel, composición, cambio y comparación en una sola figura, para que no se pueda leer a conveniencia.`}
          legend={[...relatoParts.filter((part) => relatoRows.some((row) => (row[part.key] || 0) > 0.05)).map((part) => ({ id: part.key, label: part.label, color: part.color }))]}
          legendKind="bar"
          sources={[oecdSource]}
          notes={[
            `Año ${pc.year}: el último con todas las figuras para todos los países (la media OCDE de ${h.last_year} aún no está desglosada). Media OCDE: media simple de los miembros actuales.`,
            "«Empresas» y «personas» es quién ingresa legalmente el tributo, no quién lo soporta: parte de las cotizaciones empresariales recae sobre el salario y el IVA sobre el consumidor.",
          ]}
          table={
            <details className="vizTable">
              <summary>Ver los datos en tabla (con el puesto de cada país)</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">País</th>
                      <th scope="col">Total {pc.year}</th>
                      <th scope="col">Total {pc.base_year}</th>
                      {relatoParts.map((part) => (
                        <th scope="col" key={part.key}>
                          {part.short}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {relatoRows.map((row) => (
                      <tr key={row.area}>
                        <td>{row.label}</td>
                        <td>{formatValue(row.total, "pct")}</td>
                        <td>{formatValue(row.base_total, "pct")}</td>
                        {relatoParts.map((part) => (
                          <td key={part.key}>
                            {formatValue(row[part.key], "pct")} ({rankOf(part.key, row.area)}.º)
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          }
        >
          <p className="cbars__legendNote">
            <span className="cbars__key" aria-hidden="true" /> Total en {pc.base_year}
          </p>
          <ConsolidatedBars rows={relatoRows} parts={relatoParts} axisMax={relatoMax} year={pc.year} baseYear={pc.base_year} highlight="ESP" />
          <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
            <li>
              <strong>«España es un infierno fiscal»</strong>
              En total recauda menos que {listJoin(above)} ({num(esRow.total)} % del PIB en {pc.year}). Pero es {ordinal(growthRank)} ha subido (+{num(esRow.total - esRow.base_total)} puntos) y{" "}
              {ordinal(rankOf("companies"))} ingresa de las empresas ({num(esRow.companies)} %).
            </li>
            <li>
              <strong>«En España se pagan pocos impuestos, hay margen»</strong>
              La distancia con los grandes está en lo que pagan las personas ({num(esRow.households)} %, puesto {rankOf("households")}.º de {relatoRows.length}) y el consumo (
              {num(esRow.consumption)} %, puesto {rankOf("consumption")}.º), no en las empresas.
            </li>
            <li>
              <strong>Lo que esta figura no resuelve</strong>
              Quién soporta de verdad cada tributo, los tipos efectivos frente a los legales, la economía sumergida y qué servicios recibe cada país a cambio.
            </li>
          </ul>
        </Figure>
      ) : null}

      <Figure
        id="largo-plazo"
        title={`Del ${num(h.first_value_imf, 0)} % del PIB que ingresaba el Estado central en ${h.first_year} al ${num(h.last_value, 0)} % que recaudan hoy todas las administraciones (${h.last_year}): dos coberturas distintas`}
        dek="Hasta 1965 solo hay series homogéneas de los ingresos del Estado central; desde 1965 la OCDE mide todos los impuestos y cotizaciones de todas las administraciones. Las dos series se solapan en 1965–1980 para que se vea la diferencia de cobertura: no se empalman."
        legend={longRun}
        sources={[imfSource, oecdSource]}
        notes={[
          "FMI: ingresos totales (también no tributarios) del Estado central; excluye Seguridad Social y entes territoriales, por eso queda por debajo de la OCDE desde los años 70.",
          "1936–1939: el PIB de la Guerra Civil es una estimación muy incierta; el cociente debe leerse con cautela.",
        ]}
        table={<SeriesTable series={longRun} />}
      >
        <TimeSeriesChart
          series={longRun}
          xMin={1925}
          xMax={h.last_year}
          yMax={40}
          annotations={REFORMS}
          bands={[{ from: 1936, to: 1939, label: "Guerra" }]}
          ariaLabel="Presión fiscal en España, 1925 a hoy, en porcentaje del PIB"
        />
      </Figure>

      <Figure
        id="por-habitante"
        title={`La recaudación real por habitante es ${num(pcMultiple)} veces la de ${h.per_capita_first.year}: ${formatValue(h.per_capita_last.value, "eur")} en ${h.per_capita_last.year}`}
        dek={`Recaudación total (impuestos y cotizaciones) dividida por la población, en euros de ${h.per_capita_base_year}. Es lo que ingresa el sector público por habitante, no lo que paga cada persona: incluye lo que pagan las empresas, los consumidores y los no residentes. ${payers ? `De los ${formatValue(payers.total_eur, "eur")} de ${payers.year}, los hogares pagan directamente (IRPF y cotizaciones del trabajador y de los autónomos) ${formatValue(payers.households.eur, "eur")} (${num(payers.households.pct_of_total)} %); las empresas (Sociedades y cotizaciones de la empresa), ${formatValue(payers.companies.eur, "eur")} (${num(payers.companies.pct_of_total)} %); los impuestos sobre el consumo, ${formatValue(payers.consumption.eur, "eur")} (${num(payers.consumption.pct_of_total)} %), y los de la propiedad, ${formatValue(payers.property.eur, "eur")} (${num(payers.property.pct_of_total)} %), que la OCDE no separa entre hogares y empresas. ` : ""}Crece a la vez por la presión fiscal y por la economía.`}
        sources={[oecdSource, { label: "Banco Mundial, población e IPC", href: src.worldbank_wdi.page }]}
        notes={[`Deflactado con el IPC de España (base ${h.per_capita_base_year}). Pesetas convertidas a euros a 166,386 por la OCDE.`]}
        table={<SeriesTable series={perCapita} unit="eur" />}
      >
        <TimeSeriesChart series={perCapita} unit="eur" xMin={h.oecd_first_year} xMax={h.last_year} ariaLabel="Recaudación real por habitante en España" />
      </Figure>

      {data.squeeze ? <SqueezeIndexFigure squeeze={data.squeeze} /> : null}

      <Figure
        id="quien-paga"
        title={`Lo que ingresan las personas se ha multiplicado por ${num(last.households / first.households)} y lo de las empresas por ${num(last.companies / first.companies)} (en % del PIB)`}
        dek={`Recaudación por quién la ingresa legalmente. Personas: de ${num(first.households)} % a ${num(last.households)} % del PIB. Empresas: de ${num(first.companies)} % a ${num(last.companies)} %. Consumo: de ${num(first.consumption)} % a ${num(last.consumption)} %.`}
        legend={byPayer}
        sources={[oecdSource]}
        notes={[
          "Quien ingresa un impuesto no es necesariamente quien lo soporta: las cotizaciones empresariales y el Impuesto sobre Sociedades recaen en parte sobre salarios y precios, y el IVA lo pagan los consumidores.",
        ]}
        table={<SeriesTable series={byPayer} />}
      >
        <TimeSeriesChart series={byPayer} xMin={h.oecd_first_year} xMax={h.last_year} ariaLabel="Recaudación por tipo de contribuyente, porcentaje del PIB" />
      </Figure>

      <Figure
        id="desglose"
        title={`Cotizaciones sociales e IRPF suman el ${num(compShare * 100, 0)} % del aumento`}
        dek={`De los ${num(compTotal)} puntos del PIB que ha subido la recaudación desde ${h.oecd_first_year}, ${num(compSscIrpf)} vienen de cotizaciones e IRPF. Cada figura en su panel, con la misma escala vertical.`}
        sources={[oecdSource]}
        table={
          <SeriesTable
            series={compCodes.map((code) => ({ id: code, label: data.composition_labels[code], points: data.composition_pct_gdp[code] }))}
          />
        }
      >
        <div className="vizMultiples">
          {compCodes.map((code) => {
            const rows = data.composition_pct_gdp[code];
            return (
              <div key={code}>
                <h3 className="vizPanelTitle">
                  {data.composition_labels[code]}
                  <span>
                    {num(rows[0].value)} % → {num(rows.at(-1).value)} % del PIB
                  </span>
                </h3>
                <TimeSeriesChart
                  series={[{ id: code, label: data.composition_labels[code], shortLabel: String(rows.at(-1).year), color: C.blue, points: rows }]}
                  xMin={h.oecd_first_year}
                  xMax={h.last_year}
                  yMax={compMax}
                  height={190}
                  ariaLabel={`${data.composition_labels[code]}, porcentaje del PIB`}
                />
              </div>
            );
          })}
        </div>
      </Figure>

      <Figure
        id="comparacion"
        title={
          esRank === 1
            ? `España es el país del grupo donde más ha subido la presión fiscal desde ${esIncrease.from.year}`
            : `España es el ${esRank}.º país del grupo en aumento de la presión fiscal desde ${esIncrease.from.year}`
        }
        dek={`+${num(esIncrease.delta)} puntos del PIB (${num(esIncrease.from.value)} % → ${num(esIncrease.to.value)} %), frente a +${num(
          data.peers_pct_gdp.OECD_REP.at(-1).value - data.peers_pct_gdp.OECD_REP[0].value,
        )} de la media OCDE. Partía muy por debajo: hoy supera la media OCDE y sigue por debajo de la media de la UE (${num(eu.es)} % frente a ${num(eu.eu27)} % en ${eu.year}, según Eurostat).`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[oecdSource, { label: "Eurostat, gov_10a_taxag", href: src.eurostat_sdmx.page }]}
        notes={[
          "Media OCDE: media simple de los países miembros actuales. Eurostat y OCDE difieren en unas décimas para España por diferencias de método (Eurostat sigue el SEC 2010 de contabilidad nacional).",
        ]}
        table={<SeriesTable series={[...peers].reverse()} />}
      >
        <div className="vizMultiples">
          {peerOrder
            .filter((area) => area !== "ESP")
            .reverse()
            .map((area) => {
              const other = data.peers_pct_gdp[area];
              return (
                <div key={area}>
                  <h3 className="vizPanelTitle">
                    España frente a {area === "OECD_REP" ? "la media OCDE" : PEER_LABELS[area]}
                    <span>
                      {PEER_LABELS[area]}: {num(other[0].value)} % → {num(other.at(-1).value)} %
                    </span>
                  </h3>
                  <TimeSeriesChart
                    series={[
                      { id: area, label: PEER_LABELS[area], color: C.ref, points: other },
                      { id: "ESP", label: "España", color: C.blue, emphasis: true, points: data.peers_pct_gdp.ESP },
                    ]}
                    xMin={h.oecd_first_year}
                    xMax={h.last_year}
                    yMax={peerMax}
                    height={210}
                    ariaLabel={`Presión fiscal de España frente a ${PEER_LABELS[area]}`}
                  />
                </div>
              );
            })}
        </div>
      </Figure>

      {data.distribution?.irpf ? (
        <DistributionFigure distribution={data.distribution} irpfSource={{ label: "AEAT, Estadística de los declarantes del IRPF", href: src.aeat_irpf_stats?.page }} />
      ) : null}

      {data.territory ? (
        <TerritoryFigure
          territory={data.territory}
          sources={[
            { label: "Hacienda, Tributación autonómica. Medidas 2025", href: "https://www.hacienda.gob.es/SGFAL/FinanciacionTerritorial/Autonomica/Capitulo-I-Tributacion-Autonomica-2025.pdf" },
            { label: "Hacienda, liquidación del sistema de financiación 2024", href: "https://www.hacienda.gob.es/cdi/sist%20financiacion%20y%20deuda/informaci%C3%B3nccaa/cuadros-liquidacion-2024.pdf" },
            { label: "Hacienda, presupuestos liquidados de las CCAA", href: src.hacienda_ccaa?.page },
            { label: "AEAT, declarantes del IRPF por comunidad", href: src.aeat_irpf_stats?.page },
            { label: "OCDE, Tax Database (DBnomics)", href: src.oecd_tax_database?.page },
          ]}
        />
      ) : null}

      {data.spending ? (
        <>
          <SpendingSectionIntro />
          <WhereItGoesFigure spending={data.spending} results={data.service_results} distribution={data.distribution} />
          <DecompositionFigure spending={data.spending} />
          <LongRunSpendingFigure spending={data.spending} imfSource={imfSource} debtInterest={data.debt_interest} />
        </>
      ) : null}

      <StatutoryRatesFigure rates={data.statutory_rates} lastYear={Number(String(data.generated_at).slice(0, 4))} territory={data.territory} />
      <ComplexityFigures complexity={data.complexity} />

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y fuentes</h2>
        <ul>
          <li>
            <strong>Denominador.</strong> La carga se mide en % del PIB, la medida estándar para comparar entre años y países; se complementa con euros constantes por habitante, que reflejan también el crecimiento económico.
          </li>
          <li>
            <strong>Ruptura de serie.</strong> Antes de 1965 solo se dispone de ingresos del Estado central (FMI, a partir de Comín y otras fuentes históricas). No se empalma con la serie de la OCDE: ambas se muestran y se solapan para que se vea la diferencia de cobertura.
          </li>
          <li>
            <strong>Ejes.</strong> Todos los ejes verticales empiezan en cero; los paneles de un mismo gráfico comparten escala.
          </li>
          <li>
            <strong>Comparación.</strong> Cada cifra de España se contrasta con países comparables y con la media de la OCDE y de la UE.
          </li>
          <li>
            <strong>Lo que paga y lo que le queda a cada habitante.</strong> Se compara en estándar de poder adquisitivo (Eurostat), que corrige las
            diferencias de precios entre países; la renta es la disponible ajustada de los hogares, que incluye los servicios públicos en especie. Los
            cambios reales usan índices de precios de consumo (IPC armonizado para la recaudación, deflactor del consumo para la renta).
          </li>
          <li>
            <strong>A dónde va el gasto.</strong> Clasificación funcional COFOG de Eurostat (desde 1995). Los resultados de los servicios se toman tal cual
            de los datos publicados por las páginas de <a href="/visualizaciones/sanidad/">sanidad</a>,{" "}
            <a href="/visualizaciones/educacion/">educación</a> y <a href="/visualizaciones/vivienda/">vivienda</a>, con la huella SHA-256 del fichero
            leído en el JSON de esta página.
          </li>
          <li>
            <strong>Grupos en vez de la media.</strong> La renta se parte por edad con las bandas de la propia fuente (Eurostat: 16–24, 25–49, 50–64, 65 y
            más) y sin cruzar rupturas de serie. Los cinco hogares tipo son los mismos que en las demás visualizaciones (misma edad, tenencia y lugar);
            se calculan con los tipos de la OCDE, los gastos de vivienda de la encuesta de condiciones de vida y el alquiler SERPAVI publicado por{" "}
            <a href="/visualizaciones/vivienda/">vivienda</a> (con su SHA-256 en el JSON), y se marcan como ilustrativos.
          </li>
          <li>
            <strong>Incidencia.</strong> Se clasifica por quién ingresa legalmente cada tributo, no por quién lo soporta económicamente.
          </li>
          <li>
            <strong>Reproducible y reutilizable.</strong> <code>just public-finance-refresh</code> descarga cada fuente, guarda el original y lo
            carga en SQLite con el contrato de indicadores del proyecto: cada publicación oficial es una versión nueva, cada valor se compara con
            la anterior (sin cambios, revisado o eliminado) y apunta a su celda en el fichero original con su SHA-256. Las leyes y sus
            modificaciones quedan como normas enlazadas. Desde ahí se generan los{" "}
            <a href={downloads}>datos publicados</a>.
          </li>
        </ul>
        <p>
          Fuentes: {Object.values(src).map((s, index) => (
            <span key={s.page}>
              {index ? "; " : ""}
              <a href={s.page} rel="noopener noreferrer" target="_blank">
                {s.label}
              </a>
              {s.retrieved_at ? ` (consultado ${String(s.retrieved_at).slice(0, 10)})` : ""}
            </span>
          ))}
          .
        </p>
      </section>
      <ArticleSeo slug="carga-fiscal" />
    </main>
  );
}
