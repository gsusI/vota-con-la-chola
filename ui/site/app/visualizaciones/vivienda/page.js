import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { formatHousing } from "./format.mjs";
import { TaxesFigure, CensusStockFigure, YoungOwnershipFigure, SocialStockBars, SpendingBars } from "./sections";
import StoryFigure from "./StoryFigure";
import { C, NAMES, PEER_LEGEND, PeerPanels, at, day, howMany, millions, num, thousands } from "./common";
import { Explain, Part, Verdict } from "./explain";
import {
  HouseholdSizeFigure,
  NormsFigure,
  PopulationFigure,
  RegionalGapFigure,
  RegionalPriceFigure,
  RentFigure,
  RentPeersFigure,
  SalePricesFigure,
  TouristFigure,
} from "./expanded";

export const metadata = {
  title: "Vivienda: ¿falta construir o falta gasto público? | Vota Con La Chola",
  description:
    "Años de salario para comprar un piso, viviendas terminadas frente a hogares nuevos, edad de emancipación, propiedad y alquiler, impuestos de compra y gasto público en vivienda en España, con fuentes oficiales y datos descargables.",
};

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
    { id: "ipv", label: "Salario INE con precio de compraventa (INE IPV, encadenado al valor tasado de 2015)", shortLabel: "Con precio de compraventa", tableLabel: "Compraventa (INE IPV)", color: C.yellow, dashed: true, emphasis: true, points: data.sale_prices.years_ipv_chained },
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
  const ipvYears = data.sale_prices.years_ipv_chained;
  const ipvLast = ipvYears.at(-1);
  const ipvLow = ipvYears.filter((p) => p.year > 2007).reduce((a, b) => (b.value < a.value ? b : a));
  const ipvPeak = at(ipvYears, 2007);
  const dec = data.drivers.household_decomposition;
  const rents = data.rents;
  const rentYear = rents.ipva_idx.at(-1).year;
  const youngRows = ten.young.filter((row) => row.age_group === "<35");
  const youngPeak = youngRows.reduce((a, b) => (b.value > a.value ? b : a), youngRows[0] || { value: 0 });
  const youngLast = youngRows.at(-1);
  const regionRows = data.regions.rows.filter((row) => row.ratio != null && !["ES63", "ES64"].includes(row.code));
  const regionWorst = [...regionRows].sort((a, b) => a.ratio - b.ratio).slice(0, 4);
  const regionSurplus = data.regions.rows.filter((row) => row.gap != null && row.gap <= 0 && !["ES63", "ES64"].includes(row.code)).concat(regionRows.filter((row) => row.ratio >= 1 && row.gap > 0));
  const protectedShare = sup.completed_protected.at(-1).value / sup.completed_total.at(-1).value;
  const nineties = sup.completed_protected.filter((p) => p.year < 2000).map((p) => (p.value / at(sup.completed_total, p.year)) * 100);
  const credit = data.drivers.credit_pct_gdp;
  const creditPeak = credit.reduce((a, b) => (b.value > a.value ? b : a));
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
          { href: "#conclusion", label: "Conclusión" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Piso de {h.home_m2} m² en años de salario bruto medio</span>
          <span className="vizStat__value">{num(ipvLast.value)}</span>
          <span className="vizStat__note">
            en {h.last_year} con el precio de compraventa del INE ({num(h.years_last)} con la tasación); {num(ipvLow.value)} en {ipvLow.year} y {num(ipvPeak)} en 2007
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

      <section className="card hvLead" aria-labelledby="resumen-title">
        <h2 id="resumen-title">En resumen</h2>
        <ol>
          <li>
            <strong>La vivienda es hoy más cara respecto a los sueldos que hace diez años.</strong> Un piso de {h.home_m2} m² cuesta {num(h.years_last)} años de salario
            bruto medio según la tasación y <strong>{num(ipvLast.value)}</strong> según el precio de compraventa del INE, frente a {num(ipvLow.value)} en {ipvLow.year}. El
            máximo de la burbuja fue {num(ipvPeak)} en 2007.
          </li>
          <li>
            <strong>Desde {s13.from} se construye mucho menos de lo que crecen los hogares:</strong> {num(s13.ratio, 2)} viviendas terminadas por cada hogar nuevo (
            {thousands(s13.completed_per_year)} al año frente a {thousands(s13.households_per_year)}). El déficit se concentra en{" "}
            {regionWorst.map((row) => `${row.name} (${num(row.ratio, 2)})`).join(", ")}.
          </li>
          <li>
            <strong>La demanda la empuja sobre todo la población:</strong> el {num((dec.population_effect / dec.total) * 100, 0)} % de los hogares nuevos entre {dec.from} y{" "}
            {dec.to} se explica porque hay más habitantes, y en España el crecimiento viene de la inmigración; el resto, porque los hogares son más pequeños.
          </li>
          <li>
            <strong>El gasto público en vivienda es el más bajo del grupo:</strong> {num(spendLast("ES").total, 2)} % del PIB frente a {num(spendLast("EU27_2020").total, 2)} % en la
            UE{data.social_rental_stock.find((row) => row.country === "ESP") ? `, y solo el ${num(data.social_rental_stock.find((row) => row.country === "ESP").value, 1)} % de las viviendas es social de alquiler` : ""}.
          </li>
          <li>
            <strong>Quien más lo nota son los jóvenes:</strong> se emancipan a los {num(leaveEs.value)} años (UE: {num(leaveEu.value)}) y los hogares de menores de 35 propietarios de
            su casa han pasado del {num(youngPeak.value)} % en {youngPeak.year} al {num(youngLast?.value)} % en {youngLast?.year}.
          </li>
        </ol>
        <p>
          Veredicto, en detalle en <a href="#conclusion">la conclusión</a>: la falta de construcción explica bien el encarecimiento desde 2013, sobre todo donde menos se ha
          construido ({regionWorst.map((row) => row.name).join(", ")}); no explica la burbuja de 2000–2007, que fue de crédito; y la segunda mitad de la hipótesis no se sostiene, porque el gasto público en vivienda sí es bajo.
        </p>
        <ul className="hvToc" aria-label="Partes de la página">
          <li><a href="#el-dato">El dato frente al relato</a></li>
          <li><a href="#precio">1. El precio</a></li>
          <li><a href="#alquiler-parte">2. El alquiler</a></li>
          <li><a href="#oferta">3. Construcción y hogares</a></li>
          <li><a href="#otras-causas">4. Otras causas</a></li>
          <li><a href="#consecuencias">5. Consecuencias</a></li>
          <li><a href="#politicas">6. Impuestos, gasto y normas</a></li>
          <li><a href="#conclusion">Conclusión</a></li>
          <li><a href="#glosario">Glosario</a></li>
          <li><a href="#metodo">Método</a></li>
        </ul>
      </section>

      <StoryFigure story={data.story} source={source} />

      <Part id="precio" title="1. El precio: cuánto cuesta comprar">Medimos el precio en años de salario, con la tasación y con el precio real de compraventa, por comunidades y frente a otros países.</Part>

      <Figure
        id="anios-de-salario"
        title={`Un piso de ${h.home_m2} m² cuesta hoy ${num(h.years_last)} años de salario bruto medio con el valor de tasación y ${num(ipvLast.value)} con el precio de compraventa: más que en ${ipvLow.year} (${num(ipvLow.value)}) y cerca del máximo de 2007 (${num(ipvPeak)})`}
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
        <Explain
          shows="Cuántos años de salario bruto medio, sin gastar en nada más, hacen falta para pagar un piso de 90 m² al precio medio de España."
          read="Más alto = más caro respecto a los sueldos. Las líneas usan salarios o precios distintos; fíjate en la forma común (subida hasta 2007, caída hasta 2013–2015, subida después), no en que coincidan. La línea discontinua usa el precio real de compraventa, que desde 2018 sube más que la tasación."
          notSay="No incluye intereses de la hipoteca, la entrada, los impuestos ni el precio de tu ciudad: es una media nacional."
        />
      </Figure>

      <SalePricesFigure sale={data.sale_prices} source={source} />

      <RegionalPriceFigure regions={data.regions} homeM2={h.home_m2} source={source} />

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
        <Explain
          shows="Si la vivienda está cara o barata respecto a la renta, comparando cada país con su propia historia."
          read="100 es la media histórica de cada país. Por encima de 100, la vivienda está más cara de lo habitual en ese país en relación con lo que ganan sus habitantes."
          notSay="No dice qué país es más caro en euros: un país en 120 puede ser más barato en euros que otro en 90."
        />
      </Figure>

      <Part id="alquiler-parte" title="2. El alquiler">Lo que dicen las estadísticas oficiales del alquiler y, sobre todo, lo que no pueden medir.</Part>

      <RentFigure rents={data.rents} source={source} />

      <RentPeersFigure rents={data.rents} source={source} />

      <Part id="oferta" title="3. Construcción y hogares">El corazón de la hipótesis: ¿se construyen menos viviendas de las que hacen falta? En España y en cada comunidad.</Part>

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
        <Explain
          shows="Cuántas viviendas se terminan cada año frente a cuántos hogares nuevos se forman."
          read="Cuando la línea azul (terminadas) va por encima de la verde (hogares nuevos), se construye más de lo que crece la necesidad de primera vivienda; cuando va por debajo, se acumula déficit. La naranja (iniciadas) adelanta lo que se terminará uno o dos años después."
          notSay="No cuenta demoliciones, cambios de uso, viviendas vacías que vuelven al mercado ni la demanda de segunda residencia o de compradores extranjeros no residentes."
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
          <Explain
            shows="El balance acumulado entre viviendas terminadas y hogares nuevos desde 2003."
            read="Mientras la línea sube, sobran viviendas nuevas; cuando baja, faltan. Sigue por encima de cero: a escala nacional aún queda parte del excedente de la burbuja."
            notSay="No dice dónde están esas viviendas ni si están en condiciones o a la venta."
          />
        </Figure>
      ) : null}

      <RegionalGapFigure regions={data.regions} source={source} />

      <CensusStockFigure rows={data.census_stock} source={source("bde_indicadores_vivienda", "INE, Censos de Población y Viviendas (vía Banco de España)")} />

      <Part id="otras-causas" title="4. Otras causas que compiten con la hipótesis">Crédito y tipos de interés, población e inmigración, hogares más pequeños y pisos turísticos.</Part>

      <Figure
        id="contra"
        title={`En contra de la hipótesis: entre ${boom.from} y ${boom.to} se terminaron ${num(boom.ratio, 2)} viviendas por cada hogar nuevo y aun así el piso pasó de ${num(years2000)} a ${num(years2007)} años de salario`}
        dek={`Durante la burbuja sobraban viviendas nuevas y los precios subieron más que nunca. Lo que sí cambió fue el crédito: el tipo de los préstamos para vivienda bajó del ${num(rateAt(1990), 1)} % en 1990 al ${num(rateAt(2005), 1)} % en 2005. La escasez de obra nueva no explica aquella subida; sí encaja con la de después de 2015, con tipos que volvieron a subir en 2023.`}
        legend={[
          { id: "years", label: "Años de salario (INE)", color: C.blue },
          { id: "rate", label: "Tipo de interés de los préstamos para vivienda (%)", color: C.orange },
          { id: "credit", label: "Crédito para vivienda (% del PIB)", color: C.aqua },
        ]}
        sources={[source("bde_indicadores_vivienda", "Banco de España, tipos de interés e indicadores de vivienda"), source("ine_tempus", "INE, ETCL")]}
        notes={["Paneles con su propia escala en lugar de un gráfico con varios ejes. Correlación no es causalidad: los tipos, el empleo, la inmigración, la demanda extranjera y el uso turístico se mueven a la vez."]}
        table={
          <HousingTable
            series={[
              { id: "years", label: "Años de salario (INE)", points: [...aff.years_ine_retro, ...aff.years_ine], unit: "years" },
              { id: "rate", label: "Tipo préstamos vivienda", points: rate, unit: "pct", digits: 2 },
              { id: "effort", label: "Esfuerzo teórico (% renta)", points: aff.effort_pct, unit: "pct" },
              { id: "credit", label: "Crédito vivienda (% PIB)", points: credit, unit: "pct" },
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
            <div>
            <h3 className="vizPanelTitle">
              Crédito a los hogares para comprar vivienda, % del PIB
              <span>
                máximo {num(creditPeak.value)} % en {creditPeak.year}; {num(credit.at(-1).value)} % en {credit.at(-1).year}
              </span>
            </h3>
            <HousingChart
              series={[{ id: "credit", label: "Crédito para vivienda (% del PIB)", shortLabel: String(credit.at(-1).year), color: C.aqua, points: credit }]}
              unit="pct"
              xMin={1989}
              xMax={h.last_year}
              height={220}
              ariaLabel="Crédito a los hogares para comprar vivienda en porcentaje del PIB"
            />
          </div>
        </div>
        </div>
        <Explain
          shows="La subida de 2000–2007 junto al tipo de interés de las hipotecas y el crédito a los hogares para comprar vivienda."
          read="Compara la forma de las líneas: los años de salario suben cuando los tipos bajan y el crédito crece, y caen cuando el crédito se contrae."
          notSay="No prueba que los tipos causen los precios: ambos responden al ciclo económico, al empleo y a las expectativas."
        />
      </Figure>

      <PopulationFigure drivers={data.drivers} source={source} />

      <HouseholdSizeFigure drivers={data.drivers} source={source} />

      <TouristFigure drivers={data.drivers} regions={data.regions} source={source} />

      <Part id="consecuencias" title="5. Consecuencias">Quién lo nota: emancipación, propiedad y alquiler, y los hogares jóvenes.</Part>

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
        <Explain
          shows="A qué edad, de media, los jóvenes dejan de vivir con sus padres en España y en países comparables."
          read="Cada panel compara España (azul) con un país o la media de la UE. Más alto = se van más tarde."
          notSay="No separa a quienes se quedan por falta de vivienda de quienes lo hacen por paro, estudios o costumbre."
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
        <Explain
          shows="Qué proporción de hogares vive en una vivienda propia o de alquiler desde 1970."
          read="Puntos unidos con trazo discontinuo: censos, cada diez años. Líneas continuas: encuestas anuales. Ambas cuentan hogares; el resto hasta 100 % son viviendas cedidas."
          notSay="No dice si los propietarios tienen hipoteca ni quién compra las viviendas que dejan de estar ocupadas por sus dueños."
        />
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
        <Explain
          shows="El porcentaje de la población que vive en una vivienda en propiedad en España y en otros países."
          read="Cada panel compara España con otro país o con la media de la UE; mide personas, no hogares."
          notSay="Mucha propiedad no significa vivienda asequible: Alemania tiene poca propiedad y precios más contenidos."
        />
      </Figure>

      <YoungOwnershipFigure young={ten.young} retrieved={day(src.vclc_housing_curated?.retrieved_at)} />

      <Part id="politicas" title="6. Impuestos, gasto público y normas">Lo que hacen las administraciones: cuánto cobran al comprar, cuánto gastan y cuánto legislan.</Part>

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
        <Explain
          shows="Cuánto gastan las administraciones en vivienda (promoción pública, ayudas a la compra y al alquiler) en relación con el tamaño de la economía."
          read="Barra más larga = más esfuerzo público. Se compara el último año y la media 2015–2019 para no confundir con el Superbonus italiano de 2021–2023."
          notSay="No incluye deducciones fiscales ni suelo público, y no dice si gastar más bajaría los precios: eso depende de en qué se gaste."
        />
      </Figure>

      <NormsFigure norms={data.norms} source={source} />

      <section className="card vizProse" id="conclusion" aria-labelledby="conclusion-title">
        <h2 id="conclusion-title">Conclusión: dónde acierta y dónde falla la hipótesis</h2>
        <p>
          La hipótesis tenía tres partes. Los datos las tratan de forma distinta, y lo decimos también cuando la contradicen.
        </p>
        <ul>
          <li>
            <Verdict kind="yes" />
            <strong>La vivienda se ha encarecido.</strong> Desde {ipvLow.year}, el precio de compraventa ha pasado de {num(ipvLow.value)} a {num(ipvLast.value)} años de salario
            ({num(h.years_trough)} → {num(h.years_last)} con la tasación, que va por detrás). Sigue por debajo del máximo de 2007 ({num(ipvPeak)}), pero se acerca. El alquiler medio
            de todos los contratos, en cambio, ha subido al ritmo de salarios y precios ({num(at(rents.ipva_idx, rentYear) - 100, 0)} % entre 2015 y {rentYear}); lo que se ha
            disparado son los contratos nuevos, que la estadística oficial no mide por separado.
          </li>
          <li>
            <Verdict kind="partly" />
            <strong>«Desde 2008 se terminan muchas menos viviendas que hogares se forman».</strong> Es cierto desde {s13.from}: {num(s13.ratio, 2)} viviendas por hogar nuevo, un déficit
            acumulado de {thousands(s13.net_households - s13.completed)} hogares sin vivienda nueva. Entre 2008 y 2012 todavía se terminaban más viviendas que hogares (las obras de la
            burbuja). Y el déficit no es uniforme: es grave en {regionWorst.map((row) => row.name).join(", ")} y no existe en{" "}
            {regionSurplus.map((row) => row.name).join(", ")}, donde se terminaron tantas viviendas como hogares nuevos o más.
          </li>
          <li>
            <Verdict kind="partly" />
            <strong>«Sobre todo» por eso.</strong> La escasez explica el ciclo posterior a 2015, pero no el de 2000–2007, cuando se construyeron {num(boom.ratio, 2)} viviendas por hogar
            nuevo y aun así el precio se dobló en años de salario: entonces mandaba el crédito: el saldo de préstamos para comprar vivienda pasó del {num(at(credit, 2000))} % del PIB en 2000 al{" "}
            {num(at(credit, 2007))} % en 2007, con tipos del 3–5 %.
            La demanda actual tiene causas propias que estos datos sí miden: la inmigración (el {num((dec.population_effect / dec.total) * 100, 0)} % de los hogares nuevos se explica
            por más población) y los hogares más pequeños. Los pisos turísticos pesan poco en el total ({num(data.regions.tourist_es, 2)} % del parque), pero mucho en algunas
            comunidades y barrios. Repartir el encarecimiento entre estas causas exige un modelo que esta página no hace.
          </li>
          <li>
            <Verdict kind="no" />
            <strong>«No porque el gasto público sea bajo».</strong> El gasto público en vivienda sí es bajo: {num(spendLast("ES").total, 2)} % del PIB,{" "}
            {spendRank[0] === "ES" ? "el menor de su grupo de comparación" : `menos que ${spendRank.slice(spendRank.indexOf("ES") + 1).map((geo) => NAMES[geo]).join(", ")}`},
            y {num(spendLast("EU27_2020").total / spendLast("ES").total, 1)} veces menos que la media de la UE
            {data.social_rental_stock.find((row) => row.country === "ESP") ? `, con un parque social de alquiler del ${num(data.social_rental_stock.find((row) => row.country === "ESP").value, 1)} % de las viviendas frente al ${num((data.social_rental_stock.find((row) => row.country === "OECD") || {}).value ?? 0, 1)} % de media en la OCDE` : ""}.
            Lo que los datos no permiten afirmar es que gastar más bajaría los precios: eso depende de si el gasto añade viviendas o solo ayuda a pagar las que hay.
          </li>
        </ul>
        <h2>Lo que estos datos no pueden decir</h2>
        <ul>
          <li>Causalidad: tipos de interés, empleo, inmigración, demanda extranjera y alquiler turístico se mueven a la vez; ninguno se aísla aquí.</li>
          <li>Dónde exactamente: las cifras son nacionales o autonómicas. El déficit se concentra en ciudades y barrios concretos; las viviendas vacías, a menudo donde no hay demanda.</li>
          <li>El precio de los alquileres nuevos: no hay una serie oficial larga; el IPVA y el IPCA miden todos los contratos vigentes.</li>
          <li>El suelo: cuánto suelo urbanizable hay y cuánto tarda en tramitarse depende del planeamiento municipal, que no tiene estadística nacional comparable.</li>
          <li>Censos de 1950 y 1960: no hay una fuente oficial digitalizada del régimen de tenencia; la serie empieza en 1970.</li>
        </ul>
      </section>

      <section className="card vizProse" id="glosario" aria-labelledby="glosario-title">
        <h2 id="glosario-title">Glosario</h2>
        <dl className="hvGlossary">
          <div>
            <dt>Valor de tasación y precio de compraventa</dt>
            <dd>
              La tasación es lo que un tasador homologado estima que vale una vivienda, normalmente para conceder una hipoteca. El precio de compraventa es lo que se paga en la
              escritura. En las subidas, la tasación suele quedarse por detrás. El IPV del INE mide la compraventa comparando viviendas parecidas (ajuste por calidad).
            </dd>
          </div>
          <div>
            <dt>Años de salario</dt>
            <dd>Precio de un piso de {h.home_m2} m² dividido por el salario bruto anual medio: cuántos años de sueldo íntegro costaría, sin intereses ni gastos.</dd>
          </div>
          <div>
            <dt>Hogares nuevos netos</dt>
            <dd>
              Hogares que hay al final del año menos los que había al principio. Es neto: resta los que desaparecen (por fallecimiento o porque dos hogares se juntan) a los que se
              crean (emancipaciones, separaciones, inmigrantes).
            </dd>
          </div>
          <div>
            <dt>Vivienda iniciada, terminada y visado</dt>
            <dd>
              El visado es el permiso del colegio profesional para empezar una obra; iniciada, cuando arranca; terminada, cuando se certifica el fin de obra (vivienda libre) o se
              concede la calificación definitiva (vivienda protegida). Entre una y otra suelen pasar dos años.
            </dd>
          </div>
          <div>
            <dt>VPO (vivienda de protección oficial)</dt>
            <dd>
              Vivienda con precio de venta o alquiler limitado por ley a cambio de ayudas o suelo público. En {sup.completed_total.at(-1).year} fue el {num(protectedShare * 100, 0)} % de
              las viviendas terminadas; en los años noventa, entre el {num(Math.min(...nineties), 0)} % y el {num(Math.max(...nineties), 0)} %.
            </dd>
          </div>
          <div>
            <dt>Vivienda social en alquiler</dt>
            <dd>Vivienda de alquiler por debajo del precio de mercado y asignada según necesidad, de propiedad pública o de entidades sin ánimo de lucro (definición de la OCDE).</dd>
          </div>
          <div>
            <dt>IPVA e IPCA de alquiler</dt>
            <dd>
              El IPVA del INE mide la renta de todos los contratos declarados a Hacienda; el IPCA (índice armonizado de precios de consumo) incluye el alquiler que pagan los
              inquilinos. Ambos incluyen contratos antiguos y suben más despacio que los anuncios de pisos.
            </dd>
          </div>
          <div>
            <dt>EPA y NUTS 2</dt>
            <dd>
              La Encuesta de Población Activa del INE cuenta también los hogares; Eurostat la publica por regiones NUTS 2, que en España son las comunidades autónomas.
            </dd>
          </div>
          <div>
            <dt>PPS (estándar de poder adquisitivo)</dt>
            <dd>
              Unidad de Eurostat que corrige el euro por el nivel de precios de cada país para comparar niveles. No la usamos: comparamos a cada país consigo mismo (índices y medias
              de largo plazo) o en % del PIB, que no necesitan esa conversión.
            </dd>
          </div>
          <div>
            <dt>% del PIB</dt>
            <dd>Gasto o deuda divididos por todo lo que produce la economía en un año: permite comparar países y años de distinto tamaño.</dd>
          </div>
          <div>
            <dt>Ruptura de serie</dt>
            <dd>Cambio de método o de fuente que impide unir dos tramos de datos como si fueran la misma medida. Aquí se dibujan separados, nunca empalmados.</dd>
          </div>
        </dl>
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
            <strong>Comparación.</strong> Precio frente a renta, alquiler real, migración, tamaño del hogar, alquiler turístico, emancipación, tenencia y gasto público se contrastan
            con la UE, la OCDE, Alemania, Francia, Italia y Portugal; el déficit de construcción y los años de salario, también por comunidad autónoma.
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
