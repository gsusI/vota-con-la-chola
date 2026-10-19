import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { formatHousing } from "./format.mjs";
import { TaxesFigure, CensusStockFigure, YoungOwnershipFigure, SocialStockBars, SpendingBars } from "./sections";

export const metadata = {
  title: "Vivienda: ¿falta construir o falta gasto público? | Vota Con La Chola",
  description:
    "Años de salario para comprar un piso, viviendas terminadas frente a hogares nuevos, edad de emancipación, propiedad y alquiler, impuestos de compra y gasto público en vivienda en España, con fuentes oficiales y datos descargables.",
};

const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};

const NAMES = {
  ES: "España",
  ESP: "España",
  EU27_2020: "Media UE-27",
  EU: "Media UE",
  OECD: "OCDE",
  DE: "Alemania",
  DEU: "Alemania",
  FR: "Francia",
  FRA: "Francia",
  IT: "Italia",
  ITA: "Italia",
  PT: "Portugal",
  PRT: "Portugal",
};

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const thousands = (value) => Math.round(Number(value)).toLocaleString("es-ES", { useGrouping: "always" });
const millions = (value, digits = 2) =>
  Math.abs(Number(value)) >= 1e6 ? `${num(Number(value) / 1e6, digits)} millones` : thousands(value);
// «1,67 millones de hogares» but «957.674 viviendas».
const howMany = (value, noun) => (Math.abs(Number(value)) >= 1e6 ? `${millions(value)} de ${noun}` : `${thousands(value)} ${noun}`);
const day = (iso) => (iso ? String(iso).slice(0, 10) : null);
const at = (rows, year) => rows.find((p) => p.year === year)?.value;

// Spain against each peer, one panel per peer with a shared scale (as in /visualizaciones/carga-fiscal/).
function PeerPanels({ data, spain, peers, unit, digits = 1, xMin, xMax, yMax, panelNote }) {
  return (
    <div className="vizMultiples">
      {peers.map((geo) => {
        const other = data[geo] || [];
        if (!other.length) return null;
        return (
          <div key={geo}>
            <h3 className="vizPanelTitle">
              España frente a {NAMES[geo]}
              <span>{panelNote(other, geo)}</span>
            </h3>
            <HousingChart
              series={[
                { id: geo, label: NAMES[geo], color: geo === "EU27_2020" || geo === "OECD" ? C.ref : C.peer, points: other },
                { id: spain, label: "España", color: C.blue, emphasis: true, points: data[spain] },
              ]}
              unit={unit}
              digits={digits}
              xMin={xMin}
              xMax={xMax}
              yMax={yMax}
              height={210}
              ariaLabel={`España frente a ${NAMES[geo]}`}
            />
          </div>
        );
      })}
    </div>
  );
}

export default function ViviendaPage() {
  const data = readPublicJson("visualizaciones/data/vivienda.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/vivienda.json");
  const h = data.headline;
  const src = data.sources;
  const source = (id, label, href) => ({
    label: `${label}${src[id]?.retrieved_at ? ` (consultado ${day(src[id].retrieved_at)})` : ""}`,
    href: href || src[id]?.page,
  });
  const downloads = "/visualizaciones/data/vivienda.csv";
  const aff = data.affordability;
  const sup = data.supply;

  // 1. Years of salary
  const yearsSeries = [
    { id: "ine-retro", label: "Salario INE (ETCL), serie retrospectiva 2000–2007", tableLabel: "INE 2000–2007", color: C.blue, emphasis: true, noEndLabel: true, points: aff.years_ine_retro },
    { id: "ine", label: "Salario bruto medio INE (ETCL)", shortLabel: "Salario INE", tableLabel: "INE 2008–", color: C.blue, emphasis: true, points: aff.years_ine },
    { id: "oecd", label: "Salario medio a tiempo completo (OCDE)", shortLabel: "Salario OCDE", tableLabel: "OCDE", color: C.orange, points: aff.years_oecd },
    { id: "bde", label: "Renta bruta del hogar mediano (Banco de España, 93,75 m²)", shortLabel: "Renta del hogar (BdE)", tableLabel: "BdE, hogar", color: C.aqua, points: aff.years_bde_household },
  ];
  const yearsLegend = yearsSeries.filter((s) => s.id !== "ine-retro");

  // 1b. Price-to-income against peers (OECD standardised ratio)
  const piPeers = ["OECD", "DEU", "FRA", "ITA", "PRT"];
  const piLast = (geo) => data.peers_price_income[geo]?.at(-1);
  const piMax = Math.max(...Object.values(data.peers_price_income).flatMap((rows) => rows.map((p) => p.value)));
  const piEs = piLast("ESP");
  const piRank = Object.keys(data.peers_price_income)
    .filter((geo) => geo !== "OECD" && piLast(geo))
    .sort((a, b) => piLast(b).value - piLast(a).value);

  // 2. Supply vs households
  const s13 = h.since_2013;
  const supplySeries = [
    { id: "completed", label: "Viviendas terminadas (libres + protegidas, MIVAU)", shortLabel: "Terminadas", color: C.blue, emphasis: true, points: sup.completed_total },
    { id: "starts", label: "Viviendas iniciadas (MIVAU)", shortLabel: "Iniciadas", color: C.orange, points: sup.starts.filter((p) => p.year >= 1991) },
    { id: "households", label: "Hogares nuevos netos al año (EPA, INE)", shortLabel: "Hogares nuevos (EPA)", color: C.aqua, points: sup.net_households_epa },
    {
      id: "census",
      label: "Hogares nuevos por año entre censos (media)",
      shortLabel: "Hogares, media entre censos",
      color: C.yellow,
      step: true,
      until: 2021,
      points: sup.intercensal.filter((i) => i.from >= 1991).map((i) => ({ year: i.from, value: i.per_year })),
    },
  ];
  const supplyTable = [
    { id: "free", label: "Libres terminadas", points: sup.completed_free, unit: "count" },
    { id: "protected", label: "Protegidas terminadas", points: sup.completed_protected, unit: "count" },
    { id: "completed", label: "Total terminadas", points: sup.completed_total, unit: "count" },
    { id: "starts", label: "Iniciadas", points: sup.starts.filter((p) => p.year >= 1991), unit: "count" },
    { id: "permits", label: "Visados de obra nueva", points: sup.permits, unit: "count" },
    { id: "households", label: "Hogares nuevos netos (EPA)", points: sup.net_households_epa, unit: "count" },
    { id: "stock", label: "Hogares (EPA, media anual)", points: sup.households_epa, unit: "count" },
  ];
  const balancePeak = h.balance_peak;
  const balanceLast = h.balance_last;

  // Counter-evidence: the boom years and interest rates
  const boom = h.boom;
  const rate = aff.mortgage_rate_pct;
  const rateAt = (year) => at(rate, year);
  const years2000 = h.years_2000;
  const years2007 = at([...aff.years_ine_retro, ...aff.years_ine], 2007);

  // 3. Leaving home
  const leave = data.leaving_home_age;
  const leaveEs = leave.ES.at(-1);
  const leaveEu = leave.EU27_2020.at(-1);
  const leaveEs2008 = at(leave.ES, 2008);
  const leaveMax = Math.max(...Object.values(leave).flatMap((rows) => rows.map((p) => p.value)));

  // 4. Tenure
  const ten = data.tenure;
  const censusOwner = [...ten.census_early.filter((row) => row.owner != null).map((row) => ({ year: row.year, value: row.owner })), ...ten.census.map((row) => ({ year: row.year, value: row.owner }))];
  const censusRent = [...ten.census_early.filter((row) => row.rent != null).map((row) => ({ year: row.year, value: row.rent })), ...ten.census.map((row) => ({ year: row.year, value: row.rent }))];
  const tenureSeries = [
    { id: "census-own", label: "Propiedad, censos (INE)", shortLabel: "Propiedad (censos)", color: C.blue, emphasis: true, connect: true, dashed: true, markers: true, points: censusOwner },
    { id: "survey-own", label: "Propiedad, encuestas anuales (ECPF hasta 2004, ECV desde 2005)", shortLabel: "Propiedad (encuestas)", color: C.blue, points: ten.survey_owner },
    { id: "census-rent", label: "Alquiler, censos (INE)", shortLabel: "Alquiler (censos)", color: C.orange, connect: true, dashed: true, markers: true, points: censusRent },
    { id: "survey-rent", label: "Alquiler, encuestas anuales", shortLabel: "Alquiler (encuestas)", color: C.orange, points: ten.survey_rent },
  ];
  const ownPeak = ten.census.reduce((best, row) => (row.owner > best.owner ? row : best), ten.census[0]);
  const ownLast = ten.census.at(-1);
  const silc = ten.silc_owner;
  const silcMkt = ten.silc_rent_market;
  const silcLast = (geo) => silc[geo]?.at(-1);
  const silcFirstCommon = silc.ES.find((p) => at(silc.EU27_2020, p.year) != null);
  const silcGapFirst = silcFirstCommon.value - at(silc.EU27_2020, silcFirstCommon.year);
  const silcGapLast = silcLast("ES").value - silcLast("EU27_2020").value;

  // 6. Public spending on housing
  const spend = data.public_spending_pct_gdp;
  const spendPoints = Object.fromEntries(Object.entries(spend).map(([geo, rows]) => [geo, rows.map((row) => ({ year: row.year, value: row.total }))]));
  const spendLast = (geo) => spend[geo]?.at(-1);
  const spendRank = Object.keys(spend)
    .filter((geo) => geo !== "EU27_2020" && spendLast(geo))
    .sort((a, b) => spendLast(a).total - spendLast(b).total);

  const yearsUp = h.years_last > years2000;
  const supplyGap = s13.ratio < 1;

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="Vivienda: ¿falta construir o falta gasto público?"
        summary="Ponemos a prueba una hipótesis: la vivienda se ha encarecido sobre todo porque desde 2008 se terminan muchas menos viviendas de los hogares que se forman, y no porque el gasto público sea bajo. Cada gráfico enlaza su fuente oficial, marca las rupturas de serie y trae sus datos en tabla; también publicamos lo que contradice la hipótesis."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/vivienda.json", label: "JSON con procedencia" },
          { href: "#veredicto", label: "Qué dicen los datos" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Piso de {h.home_m2} m² en años de salario bruto medio</span>
          <span className="vizStat__value">{num(h.years_last)}</span>
          <span className="vizStat__note">
            en {h.last_year}; {num(years2000)} en 2000 y {num(h.years_peak)} en el máximo de {h.peak_year}
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Viviendas terminadas por cada hogar nuevo, {s13.from}–{s13.to}</span>
          <span className="vizStat__value">{num(s13.ratio, 2)}</span>
          <span className="vizStat__note">
            {thousands(s13.completed_per_year)} terminadas al año frente a {thousands(s13.households_per_year)} hogares nuevos
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Edad media a la que los jóvenes dejan la casa de sus padres</span>
          <span className="vizStat__value">{num(leaveEs.value)}</span>
          <span className="vizStat__note">
            años en España en {leaveEs.year}; {num(leaveEu.value)} en la media de la UE
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Gasto público directo en vivienda</span>
          <span className="vizStat__value">{num(spendLast("ES").total, 2)} %</span>
          <span className="vizStat__note">
            del PIB en {spendLast("ES").year}, frente al {num(spendLast("EU27_2020").total, 2)} % de la media de la UE
          </span>
        </div>
      </section>

      <Figure
        id="anios-de-salario"
        title={`Un piso de ${h.home_m2} m² cuesta hoy ${num(h.years_last)} años de salario bruto medio: ${yearsUp ? "más" : "menos"} que en 2000 (${num(years2000)}) y menos que en ${h.peak_year} (${num(h.years_peak)})`}
        dek={`Valor tasado medio de la vivienda libre por m² multiplicado por ${h.home_m2} m², dividido por el salario bruto anual medio. En ${h.last_year}: ${formatHousing(h.home_price_last, "eur")} frente a ${formatHousing(h.wage_last, "eur")} de salario. Tres denominadores distintos, sin empalmar: el salario por trabajador del INE (incluye tiempo parcial), el salario por asalariado a tiempo completo de la OCDE y la renta del hogar mediano que usa el Banco de España.`}
        legend={yearsLegend}
        sources={[
          source("mivau_boletin", "Ministerio de Vivienda, valor tasado de la vivienda libre", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000"),
          source("ine_tempus", "INE, Encuesta Trimestral de Coste Laboral"),
          source("oecd_dbnomics", "OCDE, Average annual wages (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_EARNINGS@AV_AN_WAGE"),
          source("bde_indicadores_vivienda", "Banco de España, indicadores de vivienda"),
        ]}
        notes={[
          "Salario INE: coste salarial total por trabajador y mes × 12 (ordinario, pagas extra y atrasos; antes de IRPF y cotizaciones del trabajador). 2000–2007 es la serie retrospectiva del INE y 2008 en adelante la actual: se dibujan como tramos separados.",
          "Valor tasado: media de tasaciones hipotecarias, no precio escriturado; en los años de subida puede ir por detrás del mercado. Es una media nacional: en Madrid, Barcelona o la costa el piso típico cuesta bastante más.",
          `Año ${h.last_year}: media de los cuatro trimestres publicados. La serie de la OCDE termina en ${aff.years_oecd.at(-1).year}.`,
        ]}
        table={<HousingTable series={yearsSeries} unit="years" />}
      >
        <HousingChart
          series={yearsSeries}
          unit="years"
          xMin={1987}
          xMax={h.last_year}
          annotations={[
            { year: 2008, label: "Quiebra de Lehman", row: 0 },
            { year: 2013, label: "Mínimo de construcción", row: 1 },
          ]}
          ariaLabel="Años de salario necesarios para comprar un piso de 90 metros cuadrados en España"
        />
      </Figure>

      <Figure
        id="pares"
        title={`Respecto a su propia media histórica, la vivienda en España está un ${num(piEs.value - 100, 0)} % más cara en relación con la renta; en la OCDE, un ${num(piLast("OECD").value - 100, 0)} %`}
        dek={`Ratio entre el precio de la vivienda y la renta disponible por habitante, en % de la media de largo plazo de cada país (100 = lo normal en ese país). Compara la evolución, no el nivel: en ${piEs.year} España (${num(piEs.value, 0)}) está ${piRank.indexOf("ESP") === 0 ? "por encima de todos los países del grupo" : `en el puesto ${piRank.indexOf("ESP") + 1} de ${piRank.length} del grupo, por detrás de ${piRank.slice(0, piRank.indexOf("ESP")).map((geo) => `${NAMES[geo]} (${num(piLast(geo).value, 0)})`).join(", ")}`}.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[source("oecd_dbnomics", "OCDE, Analytical house price indicators (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES")]}
        notes={["La OCDE calcula la media de largo plazo con todos los años disponibles de cada país; un valor de 120 significa un 20 % por encima de esa media, no un 20 % más cara que otro país."]}
        table={<HousingTable series={["ESP", ...piPeers].map((geo) => ({ id: geo, label: NAMES[geo], points: data.peers_price_income[geo] || [], unit: "index" }))} />}
      >
        <PeerPanels
          data={data.peers_price_income}
          spain="ESP"
          peers={piPeers}
          unit="index"
          digits={0}
          xMin={1980}
          xMax={piEs.year}
          yMax={piMax}
          panelNote={(rows, geo) => `${NAMES[geo]}: ${num(rows.at(-1).value, 0)} en ${rows.at(-1).year}; España: ${num(piEs.value, 0)}`}
        />
      </Figure>

      <Figure
        id="construccion-y-hogares"
        title={`Desde ${s13.from} se han terminado ${howMany(s13.completed, "viviendas")} y se han formado ${howMany(s13.net_households, "hogares nuevos")}`}
        dek={`De ${s13.from} a ${s13.to}, ${thousands(s13.completed_per_year)} viviendas terminadas al año frente a ${thousands(s13.households_per_year)} hogares nuevos: ${num(s13.ratio, 2)} viviendas por hogar. En la década anterior fue al revés: entre 1991 y 2011 se terminaron más viviendas que hogares nuevos (máximo de ${thousands(h.completed_peak)} terminadas en ${h.completed_peak_year}).`}
        legend={supplySeries}
        sources={[
          source("mivau_boletin", "Ministerio de Vivienda, viviendas libres terminadas y calificaciones definitivas de vivienda protegida", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=32000000"),
          source("bde_indicadores_vivienda", "Banco de España (iniciadas y visados del Ministerio; hogares de la EPA y de los censos del INE)"),
        ]}
        notes={[
          "Hogares nuevos netos: variación de la media anual de hogares de la EPA (serie base 2021, desde 2002). En 2021 la EPA cambió de cuestionario y de base de población; el descenso de 2021 y el salto de 2022 deben leerse con cautela. La media entre censos (amarillo) no depende de la EPA.",
          "Terminadas = libres (certificados de fin de obra, estimación del Ministerio) + protegidas (calificaciones definitivas). Incluyen segundas residencias y viviendas compradas por no residentes; los hogares nuevos son netos de los que desaparecen. Ni una ni otra serie mide demoliciones o cambios de uso.",
          "La media entre censos 2011–2021 es baja en parte porque el Censo 2011 (muestral) contó más hogares que la EPA reponderada.",
        ]}
        table={<HousingTable series={supplyTable} unit="count" />}
      >
        <HousingChart
          series={supplySeries}
          unit="count"
          xMin={1991}
          xMax={h.last_year}
          annotations={[{ year: 2008, label: "Crisis financiera", row: 0 }]}
          ariaLabel="Viviendas terminadas e iniciadas frente a hogares nuevos en España"
        />
      </Figure>

      {balancePeak && balanceLast ? (
        <Figure
          id="saldo"
          title={`El excedente de viviendas de la burbuja, ${millions(balancePeak.value)} en ${balancePeak.year}, se ha reducido a ${thousands(balanceLast.value)} en ${balanceLast.year}`}
          dek={`Saldo acumulado desde ${sup.cumulative_balance[0].year}: viviendas terminadas menos hogares nuevos netos (EPA). Mientras sube, se construye más de lo que se forman hogares; cuando baja, al revés. Desde ${balancePeak.year} se ha consumido el ${num((1 - balanceLast.value / balancePeak.value) * 100, 0)} % del excedente.`}
          sources={[source("mivau_boletin", "Ministerio de Vivienda"), source("bde_indicadores_vivienda", "INE, EPA (vía Banco de España)")]}
          notes={["Es un saldo nacional: no dice dónde están esas viviendas. Si el excedente de la burbuja está en la costa o en municipios con poca demanda, no sirve a los hogares que se forman en las ciudades; estos datos no tienen ese desglose (ver también el censo de viviendas vacías más abajo)."]}
          table={<HousingTable series={[{ id: "balance", label: "Saldo acumulado (viviendas)", points: sup.cumulative_balance }]} unit="count" />}
        >
          <HousingChart
            series={[{ id: "balance", label: "Terminadas menos hogares nuevos, acumulado", shortLabel: String(balanceLast.year), color: C.blue, emphasis: true, points: sup.cumulative_balance }]}
            unit="count"
            xMin={sup.cumulative_balance[0].year}
            xMax={h.last_year}
            height={260}
            ariaLabel="Saldo acumulado entre viviendas terminadas y hogares nuevos"
          />
        </Figure>
      ) : null}

      <Figure
        id="contra"
        title={`En contra de la hipótesis: entre ${boom.from} y ${boom.to} se terminaron ${num(boom.ratio, 2)} viviendas por cada hogar nuevo y aun así el piso pasó de ${num(years2000)} a ${num(years2007)} años de salario`}
        dek={`Durante la burbuja sobraban viviendas nuevas y los precios subieron más que nunca. Lo que sí cambió fue el crédito: el tipo de los préstamos para vivienda bajó del ${num(rateAt(1990), 1)} % en 1990 al ${num(rateAt(2005), 1)} % en 2005. La escasez de obra nueva no explica aquella subida; sí encaja con la de después de 2015, con tipos que volvieron a subir en 2023.`}
        legend={[
          { id: "years", label: "Años de salario (INE)", color: C.blue },
          { id: "rate", label: "Tipo de interés de los préstamos para vivienda (%)", color: C.orange },
        ]}
        sources={[source("bde_indicadores_vivienda", "Banco de España, tipos de interés e indicadores de vivienda"), source("ine_tempus", "INE, ETCL")]}
        notes={["Dos paneles con su propia escala en lugar de un gráfico con dos ejes. Correlación no es causalidad: los tipos, el empleo, la inmigración, la demanda extranjera y el uso turístico se mueven a la vez."]}
        table={
          <HousingTable
            series={[
              { id: "years", label: "Años de salario (INE)", points: [...aff.years_ine_retro, ...aff.years_ine], unit: "years" },
              { id: "rate", label: "Tipo préstamos vivienda", points: rate, unit: "pct", digits: 2 },
              { id: "effort", label: "Esfuerzo teórico (% renta)", points: aff.effort_pct, unit: "pct" },
            ]}
          />
        }
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Años de salario para un piso de {h.home_m2} m²
              <span>INE, tramos 2000–2007 y desde 2008</span>
            </h3>
            <HousingChart series={yearsSeries.slice(0, 2)} unit="years" xMin={1989} xMax={h.last_year} height={220} ariaLabel="Años de salario" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Tipo de los préstamos para comprar vivienda
              <span>
                {num(rate[0].value)} % en {rate[0].year} → {num(rate.at(-1).value)} % en {rate.at(-1).year}
              </span>
            </h3>
            <HousingChart
              series={[{ id: "rate", label: "Tipo de interés", shortLabel: String(rate.at(-1).year), color: C.orange, points: rate }]}
              unit="pct"
              xMin={1989}
              xMax={h.last_year}
              height={220}
              ariaLabel="Tipo de interés de los préstamos para vivienda"
            />
          </div>
        </div>
      </Figure>

      <CensusStockFigure rows={data.census_stock} source={source("bde_indicadores_vivienda", "INE, Censos de Población y Viviendas (vía Banco de España)")} />

      <Figure
        id="emancipacion"
        title={`Los jóvenes españoles se van de casa a los ${num(leaveEs.value)} años, ${num(leaveEs.value - leaveEu.value)} más que la media de la UE (${num(leaveEu.value)})`}
        dek={`Edad media estimada de salida del hogar de los padres. España ya estaba entre los países más tardíos antes de la crisis (${num(leaveEs2008)} años en 2008), junto a Italia; desde entonces ha subido ${num(leaveEs.value - leaveEs2008)} años. Alemania y Francia rondan los 24.`}
        legend={[
          { id: "ES", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[source("eurostat_sdmx", "Eurostat, yth_demo_030", "https://ec.europa.eu/eurostat/databrowser/view/yth_demo_030/default/table")]}
        notes={["La edad de emancipación depende también del empleo juvenil, los salarios, la educación y la cultura familiar: la comparación con Italia y Portugal, con mercados de vivienda distintos, muestra que no es solo una cuestión de precios."]}
        table={<HousingTable series={["ES", "EU27_2020", "DE", "FR", "IT", "PT"].map((geo) => ({ id: geo, label: NAMES[geo], points: leave[geo] }))} unit="age" />}
      >
        <PeerPanels
          data={leave}
          spain="ES"
          peers={["EU27_2020", "DE", "FR", "IT", "PT"]}
          unit="age"
          xMin={2000}
          xMax={leaveEs.year}
          yMax={leaveMax}
          panelNote={(rows) => `${num(rows[0].value)} en ${rows[0].year} → ${num(rows.at(-1).value)} en ${rows.at(-1).year}`}
        />
      </Figure>

      <Figure
        id="tenencia"
        title={`La propiedad tocó techo en ${ownPeak.year} (${num(ownPeak.owner)} % de los hogares) y ha bajado al ${num(ownLast.owner)} % en ${ownLast.year}; el alquiler sube del ${num(at(censusRent, ownPeak.year))} % al ${num(ownLast.rent)} %`}
        dek={`Régimen de tenencia de la vivienda principal${ten.census_early.length ? `, desde el censo de ${ten.census_early[0].year}` : " en los censos desde 1970"} y en las encuestas anuales de hogares. Censos y encuestas se dibujan por separado: miden con métodos distintos y no se empalman.`}
        legend={tenureSeries}
        sources={[
          source("bde_indicadores_vivienda", "INE, censos y encuestas de hogares (vía Banco de España)"),
          ...(ten.census_early.length ? ten.census_early.map((row) => ({ label: `${row.source} (${row.year})`, href: row.source_url })) : []),
        ]}
        notes={[
          "El resto hasta 100 % es cesión gratuita u otras formas. La ECPF (hasta 2004) y la ECV (desde 2005) son encuestas distintas: el salto de 2004 es un cambio de fuente.",
          ...(ten.census_early.filter((row) => row.note).map((row) => `${row.year}: ${row.note}`)),
        ]}
        table={<HousingTable series={tenureSeries} />}
      >
        <HousingChart series={tenureSeries} xMin={ten.census_early[0]?.year ?? 1970} xMax={h.last_year} yMax={100} ariaLabel="Viviendas principales en propiedad y en alquiler en España" />
      </Figure>

      <Figure
        id="tenencia-ue"
        title={`España sigue por encima de la media de la UE en propiedad (${num(silcLast("ES").value)} % frente a ${num(silcLast("EU27_2020").value)} % de la población en ${silcLast("ES").year}), pero la distancia ${silcGapLast < silcGapFirst ? "se ha reducido" : "ha crecido"} de ${num(silcGapFirst)} a ${num(silcGapLast)} puntos desde ${silcFirstCommon.year}`}
        dek={`Población que vive en una vivienda en propiedad según la encuesta europea de condiciones de vida. En alquiler a precio de mercado vive el ${num(silcMkt.ES.at(-1).value)} % en España (${num(silcMkt.ES[0].value)} % en ${silcMkt.ES[0].year}), frente al ${num(silcMkt.EU27_2020.at(-1).value)} % en la UE.`}
        legend={[
          { id: "ES", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[source("eurostat_sdmx", "Eurostat, ilc_lvho02", "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho02/default/table")]}
        notes={["Mide personas, no hogares, por eso no coincide con los porcentajes de hogares del gráfico anterior."]}
        table={
          <HousingTable
            series={["ES", "EU27_2020", "DE", "FR", "IT", "PT"].flatMap((geo) => [
              { id: `own-${geo}`, label: `${NAMES[geo]}: propiedad`, points: silc[geo] || [] },
              { id: `mkt-${geo}`, label: `${NAMES[geo]}: alquiler de mercado`, points: silcMkt[geo] || [] },
            ])}
          />
        }
      >
        <PeerPanels
          data={silc}
          spain="ES"
          peers={["EU27_2020", "DE", "FR", "IT", "PT"]}
          unit="pct"
          xMin={2004}
          xMax={silcLast("ES").year}
          yMax={100}
          panelNote={(rows) => `${num(rows.at(-1).value)} % en ${rows.at(-1).year}`}
        />
      </Figure>

      <YoungOwnershipFigure young={ten.young} retrieved={day(src.vclc_housing_curated?.retrieved_at)} />

      <TaxesFigure taxes={data.taxes} wageLast={h.wage_last} lastYear={h.last_year} retrieved={day(src.vclc_housing_curated?.retrieved_at)} />

      <Figure
        id="gasto-publico"
        title={`España dedica a vivienda un ${num(spendLast("ES").total, 2)} % del PIB, ${spendRank[0] === "ES" ? "el menor de su grupo de comparación" : `por encima solo de ${spendRank.slice(0, spendRank.indexOf("ES")).map((geo) => NAMES[geo]).join(", ")}`}; la media de la UE gasta ${num(spendLast("EU27_2020").total / spendLast("ES").total, 1)} veces más`}
        dek={`Gasto de todas las administraciones en desarrollo de la vivienda (promoción, compra y ayudas a la construcción) y en ayudas a la vivienda de la protección social (alquiler y similares), en % del PIB. ${spendLast("ES").year}: España ${num(spendLast("ES").total, 2)} %, UE ${num(spendLast("EU27_2020").total, 2)} %, Francia ${num(spendLast("FR").total, 2)} %, Alemania ${num(spendLast("DE").total, 2)} %, Portugal ${num(spendLast("PT").total, 2)} %, Italia ${num(spendLast("IT").total, 2)} %.`}
        legend={[
          { id: "ES", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[
          source("eurostat_sdmx", "Eurostat, gov_10a_exp (COFOG GF0601 + GF1006) y nama_10_gdp", "https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table"),
          ...(data.social_rental_stock.length ? [{ label: `OCDE, Affordable Housing Database PH4.2 (consultado ${day(src.vclc_housing_curated?.retrieved_at)})`, href: data.social_rental_stock[0].source_url }] : []),
        ]}
        notes={[
          "No incluye beneficios fiscales: la deducción por compra de vivienda habitual del IRPF (suprimida para compras desde 2013) era gasto público en forma de menor recaudación y no aparece en estas cifras.",
          "Tampoco incluye el suelo público cedido ni la vivienda de empresas públicas fuera del sector administraciones públicas.",
          ...(data.social_rental_stock.length
            ? ["Vivienda social en alquiler (OCDE): el año difiere por país; el dato de España procede de una ronda anterior del cuestionario y puede incluir viviendas de empresa a renta reducida; las medias OCDE y UE promedian el último dato de cada país."]
            : []),
          `Italia 2021–2023: los créditos fiscales del «Superbonus» para rehabilitar viviendas se contabilizan como gasto en desarrollo de la vivienda (${num(at(spendPoints.IT, 2022), 2)} % del PIB en 2022 y ${num(at(spendPoints.IT, 2023), 2)} % en 2023) y elevan también la media de la UE; por eso se compara el último año y la media 2015–2019, y la serie completa está en la tabla.`,
        ]}
        table={
          <HousingTable
            series={["ES", "EU27_2020", "DE", "FR", "IT", "PT"].flatMap((geo) => [
              { id: `t-${geo}`, label: `${NAMES[geo]}: total`, points: spendPoints[geo] || [], digits: 2 },
              { id: `a-${geo}`, label: `${NAMES[geo]}: ayudas a hogares`, points: (spend[geo] || []).map((row) => ({ year: row.year, value: row.allowances })), digits: 2 },
            ])}
          />
        }
      >
        <SpendingBars spend={spend} names={NAMES} order={["ES", "EU27_2020", "DE", "FR", "IT", "PT"]} />
        <SocialStockBars rows={data.social_rental_stock} names={NAMES} />
      </Figure>

      <section className="card vizProse" id="veredicto" aria-labelledby="veredicto-title">
        <h2 id="veredicto-title">Qué dicen los datos sobre la hipótesis</h2>
        <ul>
          <li>
            <strong>Se ha encarecido, pero no en todas las medidas ni respecto a cualquier año.</strong> Un piso de {h.home_m2} m² cuesta {num(h.years_last)} años de
            salario en {h.last_year}, frente a {num(years2000)} en 2000 y {num(h.years_trough)} en {h.trough_year}; sigue por debajo del máximo de {h.peak_year} ({num(h.years_peak)}).
            Con la renta de los hogares (Banco de España) y frente a su propia media histórica (OCDE), la conclusión es la misma.
          </li>
          <li>
            <strong>{supplyGap ? "Desde 2013 se construye menos de lo que crecen los hogares: se sostiene." : "Desde 2013 no falta construcción: no se sostiene."}</strong>{" "}
            {thousands(s13.completed_per_year)} viviendas terminadas al año frente a {thousands(s13.households_per_year)} hogares nuevos. Pero entre 2008 y 2012 todavía se terminaron más
            viviendas que hogares, así que «desde 2008» es inexacto: el déficit empieza hacia 2013, cuando ya se había agotado el ritmo de la burbuja.
          </li>
          <li>
            <strong>La escasez no explica la burbuja de 2000–2007.</strong> Entonces se terminaron {num(boom.ratio, 2)} viviendas por hogar nuevo y el precio subió más que nunca, con
            el crédito barato. La hipótesis describe mejor el ciclo de después de 2015 que el anterior.
          </li>
          <li>
            <strong>El gasto público en vivienda sí es bajo.</strong> España gasta el {num(spendLast("ES").total, 2)} % del PIB,{" "}
            {spendRank[0] === "ES" ? "menos que todos sus comparables" : `menos que ${spendRank.slice(spendRank.indexOf("ES") + 1).map((geo) => NAMES[geo]).join(", ")}`} y{" "}
            {num(spendLast("EU27_2020").total / spendLast("ES").total, 1)} veces menos de lo que gasta la media de la UE
            {data.social_rental_stock.find((row) => row.country === "ESP") ? `, y su parque de vivienda social en alquiler es de los más pequeños de la OCDE` : ""}. La segunda mitad de la
            hipótesis («no porque el gasto sea bajo») no se puede sostener tal cual: el gasto es bajo; lo que estos datos no permiten medir es cuánto bajaría el precio si fuera mayor.
          </li>
        </ul>
        <h2>Lo que estos datos no pueden decir</h2>
        <ul>
          <li>Causalidad: las series se mueven juntas con los tipos de interés, el empleo, la inmigración, la demanda extranjera y el alquiler turístico; ninguna se aísla aquí.</li>
          <li>Dónde: todo es media nacional. El déficit de vivienda se concentra en grandes ciudades y en la costa; las viviendas vacías, a menudo donde no hay demanda.</li>
          <li>Precio real de compraventa: se usa el valor de tasación (Ministerio de Vivienda), que va por detrás del mercado en las subidas.</li>
          <li>Alquiler: el precio del alquiler, que es lo que más ha subido para los jóvenes, no se mide aquí con una serie larga comparable.</li>
          <li>Normas: no contamos todavía cuántas normas estatales y autonómicas de vivienda se aprueban cada año (pendiente: API del BOE).</li>
        </ul>
      </section>

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y fuentes</h2>
        <ul>
          <li>
            <strong>Denominador.</strong> El precio se mide en años de salario y de renta del hogar; la construcción, por hogar nuevo; el gasto público, en % del PIB.
          </li>
          <li>
            <strong>Rupturas de serie.</strong> Salario del INE en dos tramos (retrospectiva 2000–2007 y serie actual desde 2008); censos frente a encuestas; ECPF frente a ECV en 2004; EPA
            reponderada en 2021. Nada se empalma: se dibujan por separado.
          </li>
          <li>
            <strong>Ejes.</strong> Todos los ejes verticales empiezan en cero (el saldo de hogares baja de cero en 2021); los paneles de un mismo gráfico comparten escala; no hay dobles ejes.
          </li>
          <li>
            <strong>Comparación.</strong> Emancipación, tenencia, precio frente a renta y gasto público se contrastan con la UE, la OCDE, Alemania, Francia, Italia y Portugal.
          </li>
          <li>
            <strong>Reproducible y reutilizable.</strong> <code>just housing-refresh</code> descarga cada fuente oficial, guarda el original y lo carga en SQLite con el contrato de indicadores del
            proyecto: cada publicación es una versión nueva, cada valor se compara con la anterior y apunta a su celda en el fichero original con su SHA-256. Los tipos impositivos y los datos
            transcritos de publicaciones guardan la norma o el documento citado fila a fila. Desde ahí se generan los <a href={downloads}>datos publicados</a>.
          </li>
        </ul>
        <p>
          Fuentes:{" "}
          {Object.values(src).map((s, index) => (
            <span key={s.page}>
              {index ? "; " : ""}
              <a href={s.page} rel="noopener noreferrer" target="_blank">
                {s.label}
              </a>
              {s.retrieved_at ? ` (consultado ${day(s.retrieved_at)})` : ""}
            </span>
          ))}
          .
        </p>
      </section>
    </main>
  );
}
