import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { formatHousing } from "./format.mjs";
import { TaxesFigure, CensusStockFigure, YoungOwnershipFigure, SocialStockBars, SpendingBars } from "./sections";
import StoryFigure from "./StoryFigure";
import WhoPaysFigure from "./segments";
import { BurdenPeersFigure, CapacityFigure, MoneyFigure } from "./capacity";
import { CohortFigure, DistributionFigure, TenantRegionFigure } from "./distribution";
import { C, NAMES, PEER_LEGEND, PeerPanels, at, day, howMany, joinEs, millions, num, paceWord, thousands } from "./common";
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
  const seg = data.segments;
  const segT = seg ? Object.fromEntries(seg.tenure.map((row) => [row.key, row])) : {};
  const src = data.sources;
  const source = (id, label, href) => ({
    label: `${label}${src[id]?.retrieved_at ? ` (consultado ${day(src[id].retrieved_at)})` : ""}`,
    href: href || src[id]?.page,
  });
  const downloads = "/visualizaciones/data/vivienda.csv";
  const aff = data.affordability;
  const sup = data.supply;

  // 1. Years of pay. Headline: median NET pay at the INE sale price (what the typical worker takes home against what homes
  // sell for), from 2008. Context, overlapped and labelled, never spliced: average net pay at the appraisal price from
  // 2000, and the old gross-average measure as a thin line.
  const capA = data.capacity;
  const yearsSeries = [
    { id: "net-median-sale", label: "Sueldo neto mediano, precio de compraventa (INE IPV)", shortLabel: "Neto mediano, compraventa", tableLabel: "Neto mediano, compraventa", color: C.blue, emphasis: true, points: capA.years_net_median_sale_price },
    { id: "net-avg-appraisal", label: "Sueldo neto medio, precio de tasación (serie larga, desde 2000)", shortLabel: "Neto medio, tasación", tableLabel: "Neto medio, tasación", color: C.aqua, dashed: true, points: capA.years_net_avg },
    { id: "ine-retro", label: "Salario bruto medio, tasación, serie retrospectiva 2000–2007", tableLabel: "Bruto medio 2000–2007", color: C.ref, thin: true, noEndLabel: true, points: aff.years_ine_retro },
    { id: "ine", label: "Salario bruto medio, precio de tasación (la medida anterior)", shortLabel: "Bruto medio, tasación", tableLabel: "Bruto medio 2008–", color: C.ref, thin: true, points: aff.years_ine },
    { id: "bde", label: "Renta bruta del hogar mediano (Banco de España, 93,75 m²)", shortLabel: "Renta del hogar (BdE)", tableLabel: "BdE, hogar", color: C.peer, thin: true, points: aff.years_bde_household },
  ];
  const grossSeries = [
    { id: "ine-retro", label: "Salario bruto medio INE, 2000–2007", color: C.blue, emphasis: true, noEndLabel: true, points: aff.years_ine_retro },
    { id: "ine", label: "Salario bruto medio INE", shortLabel: "Salario INE", color: C.blue, emphasis: true, points: aff.years_ine },
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
  const dec = data.drivers.household_decomposition;
  const rents = data.rents;
  const youngRows = ten.young.filter((row) => row.age_group === "<35");
  const youngPeak = youngRows.reduce((a, b) => (b.value > a.value ? b : a), youngRows[0] || { value: 0 });
  const youngLast = youngRows.at(-1);
  const youngFirst = youngRows[0];
  const regionRows = data.regions.rows.filter((row) => row.ratio != null && !["ES63", "ES64"].includes(row.code));
  const regionWorst = [...regionRows].sort((a, b) => a.ratio - b.ratio).slice(0, 4);
  const regionSurplus = data.regions.rows.filter((row) => row.gap != null && row.gap <= 0 && !["ES63", "ES64"].includes(row.code)).concat(regionRows.filter((row) => row.ratio >= 1 && row.gap > 0));
  const protectedShare = sup.completed_protected.at(-1).value / sup.completed_total.at(-1).value;
  const nineties = sup.completed_protected.filter((p) => p.year < 2000).map((p) => (p.value / at(sup.completed_total, p.year)) * 100);
  const credit = data.drivers.credit_pct_gdp;
  const cap = data.capacity;
  const esMoney = data.money.find((row) => row.geo === "ESP");
  const deMoney = data.money.find((row) => row.geo === "DEU");
  const burdenYear = cap.peers.overburden_tenants.ES.at(-1).year;
  const tenantsEs = at(cap.peers.overburden_tenants.ES, burdenYear);
  const tenantsEu = at(cap.peers.overburden_tenants.EU27_2020, burdenYear);
  const creditPeak = credit.reduce((a, b) => (b.value > a.value ? b : a));
  const supplyGap = s13.ratio < 1;
  // Headlines are stated from several base years (2000 start, 2007 peak, 2013 trough, 2019), never from the trough alone.
  const B = data.bases;
  const ys = B.years_sale;
  const ya = B.years_appraisal;
  const nms = capA.years_net_median_sale_price;
  const nmsLast = nms.at(-1);
  const nmsFirst = nms[0];
  const nmsAt = (y) => at(nms, y);
  const TD = capA.tax_decomposition;
  const tdHead = (base) => TD.headline.from_base.find((row) => row.from === base);
  const tdLong = (base) => TD.long_run.from_base.find((row) => row.from === base);
  // Differences between figures shown with one decimal are taken from the shown (rounded) values, so the text adds up.
  const d1 = (a, b) => Math.round(a * 10) / 10 - Math.round(b * 10) / 10;
  const signed = (v, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v), d)}`;
  const W = B.completed_per_household;
  const wLast = W[W.length - 1];
  const wBoom = W[0];
  const decs = data.composition.decomposition;
  const decLast = decs[decs.length - 1];
  const cohortPeak = data.composition.cohort_25_39.ES.persons.reduce((a, b) => (b.value > a.value ? b : a));

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
        {seg ? (
          <div className="card vizStat">
            <span className="vizStat__label">Gastan más del 40 % de su renta en vivienda</span>
            <span className="vizStat__value">{num(segT.RENT_MKT.overburden_pct)} %</span>
            <span className="vizStat__note">
              de quienes alquilan a precio de mercado, frente al {num(segT.OWN_NL.overburden_pct)} % de quienes tienen la casa pagada y el {num(seg.overburden_total)} % de toda la población ({seg.year})
            </span>
          </div>
        ) : null}
        <div className="card vizStat">
          <span className="vizStat__label">Piso de {h.home_m2} m² en años de sueldo neto mediano</span>
          <span className="vizStat__value">{num(nmsLast.value)}</span>
          <span className="vizStat__note">
            al precio de compraventa del INE en {nmsLast.year}; {num(nmsAt(2019))} en 2019, {num(nmsAt(2013))} en 2013 y {num(nmsFirst.value)} en {nmsFirst.year} (la serie del sueldo mediano empieza en {nmsFirst.year}). Con el salario bruto medio y la tasación salen {num(ya[String(B.last_year)])} ({B.last_year})
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Viviendas terminadas por cada hogar nuevo, {wLast.from}–{wLast.to}</span>
          <span className="vizStat__value">{num(wLast.ratio, 2)}</span>
          <span className="vizStat__note">
            {W.slice(0, -1).map((w) => `${num(w.ratio, 2)} en ${w.from}–${w.to}`).join("; ")}
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
            <strong>La vivienda es más cara respecto a los sueldos que en 2019 y que en 2013, aunque menos que antes de la crisis.</strong> Un piso de {h.home_m2} m² cuesta{" "}
            <strong>{num(nmsLast.value)}</strong> años de sueldo neto mediano, el que cobra el trabajador típico, al precio de compraventa del INE ({nmsLast.year}; {num(nmsAt(2019))} en 2019,{" "}
            {num(nmsAt(2013))} en 2013 y {num(nmsFirst.value)} en {nmsFirst.year}). De los {num(tdHead(2019)?.change, 2)} años más desde 2019, {num(tdHead(2019)?.tax_part, 2)} se deben a que el
            trabajador paga más IRPF y cotizaciones. Con el salario bruto medio y la tasación, la medida habitual, salen {num(ya[String(B.last_year)])} ({B.last_year}): se queda corta. Quien más lo sufre es quien alquila: el {num(tenantsEs)} % de los inquilinos a
            precio de mercado dedica más del 40 % de su renta a la vivienda (UE: {num(tenantsEu)} %).
          </li>
          <li>
            <strong>Se construye cada vez menos por cada hogar nuevo:</strong> {joinEs(W.map((w) => `${num(w.ratio, 2)} en ${w.from}–${w.to}`))}. El déficit se concentra en{" "}
            {regionWorst.map((row) => `${row.name} (${num(row.ratio, 2)})`).join(", ")}.
          </li>
          <li>
            <strong>La mayoría de los hogares nuevos sale del aumento de población:</strong> es el{" "}
            {joinEs(decs.map((d) => `${num((d.population_effect / d.total) * 100, 0)} % en ${d.from}–${d.to}`))} de los hogares nuevos (el resto, de hogares más pequeños){data.drivers.natural_negative_since ? `; desde ${data.drivers.natural_negative_since} mueren más personas de las que nacen, así que ese aumento viene de la inmigración` : ""}. No es la generación de 25 a 39 años, la que forma hogares, que se encoge desde {cohortPeak.year}.
          </li>
          <li>
            <strong>El gasto público en vivienda es el más bajo del grupo, y no por falta de ingresos:</strong> {num(spendLast("ES").total, 2)} % del PIB frente a{" "}
            {num(spendLast("EU27_2020").total, 2)} % en la UE, mientras los impuestos sobre inmuebles y sus compraventas recaudan el {num(esMoney.collected, 2)} % ({num(esMoney.collected / esMoney.spent, 0)} euros
            por cada euro gastado){data.social_rental_stock.find((row) => row.country === "ESP") ? `, y solo el ${num(data.social_rental_stock.find((row) => row.country === "ESP").value, 1)} % de las viviendas es social de alquiler` : ""}.
          </li>
          <li>
            <strong>Quien más lo nota son los jóvenes:</strong> se emancipan a los {num(leaveEs.value)} años (UE: {num(leaveEu.value)}) y los hogares de menores de 35 propietarios de
            su casa han pasado del {num(youngPeak.value)} % en {youngPeak.year}, el máximo de la serie ({num(youngFirst?.value)} % en {youngFirst?.year}, la primera ola), al {num(youngLast?.value)} % en {youngLast?.year}.
          </li>
        </ol>
        <p>
          Veredicto, en detalle en <a href="#conclusion">la conclusión</a>: la falta de construcción coincide con el encarecimiento de la última década, sobre todo donde menos se ha
          construido ({joinEs(regionWorst.map((row) => row.name))}); no coincide con la burbuja de {B.boom.from}–{B.boom.to}, cuando se construía mucho y el crédito para vivienda pasó del {num(B.boom.credit_from)} % al {num(B.boom.credit_to)} % del PIB; y la segunda mitad de la hipótesis no se sostiene, porque el gasto público en vivienda sí es bajo. Coincidir en el tiempo no prueba la causa.
        </p>
        <ul className="hvToc" aria-label="Partes de la página">
          <li><a href="#el-dato">El dato frente al relato</a></li>
          <li><a href="#el-dato-dinero">Lo que se cobra y lo que se gasta</a></li>
          <li><a href="#quien-paga">Quién paga la vivienda</a></li>
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

      <StoryFigure story={data.story} composition={data.composition} source={source} />

      <MoneyFigure money={data.money} source={source} />

      <WhoPaysFigure segments={data.segments} source={source} />

      <Part id="precio" title="1. El precio: cuánto cuesta comprar">Medimos el precio en años de sueldo neto, con el precio real de compraventa y con la tasación, por comunidades y frente a otros países.</Part>

      <Figure
        id="anios-de-salario"
        title={`Un piso de ${h.home_m2} m² cuesta ${num(nmsLast.value)} años de sueldo neto mediano al precio de compraventa (${nmsLast.year}): ${num(d1(nmsLast.value, nmsAt(2019)), 1)} más que en 2019 y ${num(d1(nmsLast.value, nmsAt(2013)), 1)} más que en 2013, pero ${num(d1(nmsFirst.value, nmsLast.value), 1)} menos que en ${nmsFirst.year}; con el salario bruto medio y la tasación salen ${num(ya[String(B.last_year)])}`}
        dek={`Precio de un piso de ${h.home_m2} m² dividido por lo que de verdad cobra el trabajador del medio: el salario bruto mediano (INE, Encuesta de Estructura Salarial) menos su IRPF y sus cotizaciones. El precio es el de compraventa (índice del INE sobre escrituras, encadenado al valor tasado de 2015). La serie del sueldo mediano empieza en ${nmsFirst.year}; para ver desde 2000 se dibuja aparte, solapada y sin empalmar, el sueldo neto medio con el precio de tasación (${num(at(capA.years_net_avg, 2000))} años en 2000, ${num(at(capA.years_net_avg, 2007))} en 2007, ${num(capA.years_net_avg.at(-1).value)} en ${capA.years_net_avg.at(-1).year}). La línea gris fina es la medida anterior, salario bruto medio y tasación: ${num(ya[String(B.last_year)])} años, un ${num((nmsLast.value / at(aff.years_ine, nmsLast.year) - 1) * 100, 0)} % menos que la principal en ${nmsLast.year}, porque usa el bruto, la media (que suben los sueldos altos) y la tasación. Debajo, cuánto del cambio se debe a que el trabajador paga más impuestos.`}
        legend={yearsSeries.filter((s) => s.id !== "ine-retro")}
        sources={[
          source("ine_tempus", "INE, Índice de Precios de Vivienda (compraventa), Encuesta de Estructura Salarial (salario mediano) y Encuesta Trimestral de Coste Laboral (salario medio)", "https://www.ine.es/jaxiT3/Tabla.htm?t=28191"),
          source("oecd_dbnomics", "OCDE, Taxing Wages: IRPF y cotizaciones del trabajador al 67 % y al 100 % del salario medio (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
          source("mivau_boletin", "Ministerio de Vivienda, valor tasado de la vivienda libre", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000"),
          source("bde_indicadores_vivienda", "Banco de España, indicadores de vivienda"),
        ]}
        notes={[
          `Neto = bruto × (1 − t), con t el tipo medio de IRPF y cotizaciones del trabajador de un soltero sin hijos (OCDE). El sueldo mediano es el ${num(capA.median_share_of_oecd_wage.at(-1).value * 100, 0)} % del salario medio de la OCDE (${capA.median_share_of_oecd_wage.at(-1).year}), entre los dos niveles publicados (67 % y 100 %): su tipo se interpola entre ambos por esa proporción (${num(capA.net_rate_median.find((p) => p.year === nmsLast.year)?.value)} % en ${nmsLast.year}). Es una aproximación: con hijos o en pareja el tipo es menor.`,
          "Descomposición: años netos = años brutos / (1 − t). El cambio entre dos años se separa, sin resto, en precio frente al salario bruto (años brutos del año final con el tipo del inicial menos los del inicial) e impuestos del trabajador (lo que añade pasar del tipo inicial al final). No mide los impuestos de la compra (ITP, IVA), que se ven en la parte 6.",
          "Salario medio INE: coste salarial total por trabajador × 12, en dos tramos (retrospectiva 2000–2007 y serie actual desde 2008), sin empalmar. Valor tasado: media de tasaciones hipotecarias; en los años de subida va por detrás del mercado. Todo son medias nacionales: en Madrid, Barcelona o la costa el piso típico cuesta bastante más.",
        ]}
        table={
          <>
            <HousingTable series={[...yearsSeries, { id: "rate-med", label: "Tipo del trabajador mediano (%)", points: capA.net_rate_median, unit: "pct" }, { id: "rate-avg", label: "Tipo del trabajador medio (%)", points: capA.net_rate_avg, unit: "pct" }]} unit="years" />
            <details className="vizTable">
              <summary>Ver la descomposición en tabla</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Medida</th>
                      <th scope="col">Tramo</th>
                      <th scope="col">Años netos al inicio</th>
                      <th scope="col">Al final</th>
                      <th scope="col">Cambio</th>
                      <th scope="col">Por el precio frente al bruto</th>
                      <th scope="col">Por los impuestos del trabajador</th>
                      <th scope="col">Tipo del trabajador</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[["headline", "Neto mediano, compraventa"], ["long_run", "Neto medio, tasación"]].flatMap(([key, label]) =>
                      [...TD[key].from_base, ...TD[key].steps.filter((row) => !TD[key].from_base.some((b) => b.from === row.from && b.to === row.to))].map((row) => (
                        <tr key={`${key}-${row.from}-${row.to}`}>
                          <td>{label}</td>
                          <td>
                            {row.from}–{row.to}
                          </td>
                          <td>{num(row.years_from, 2)}</td>
                          <td>{num(row.years_to, 2)}</td>
                          <td>{signed(row.change, 2)}</td>
                          <td>{signed(row.price_part, 2)}</td>
                          <td>{signed(row.tax_part, 2)}</td>
                          <td>
                            {num(row.rate_from)} % → {num(row.rate_to)} %
                          </td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        }
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
          ariaLabel="Años de sueldo necesarios para comprar un piso de 90 metros cuadrados en España"
        />
        <div>
          <h3 className="vizPanelTitle">
            Cuánto del cambio se debe a pagar más IRPF y cotizaciones
            <span>años de sueldo neto mediano a precio de compraventa, por tramos; tipo del trabajador mediano entre paréntesis</span>
          </h3>
          <TaxSplit rows={TD.headline.steps} />
          <p className="hvMuted">
            Desde 2000, con el sueldo neto medio y la tasación: {signed(tdLong(2000)?.change, 2)} años, de los que {signed(tdLong(2000)?.tax_part, 2)} se deben a que el tipo del trabajador medio pasó del{" "}
            {num(tdLong(2000)?.rate_from)} % al {num(tdLong(2000)?.rate_to)} % ({tdLong(2000)?.to}).
          </p>
        </div>
        <Explain
          shows={`Cuántos años de sueldo neto, sin gastar en nada más, hacen falta para pagar un piso de ${h.home_m2} m² al precio medio de España, y cuánto de su subida o bajada se debe al precio y cuánto a los impuestos del trabajador.`}
          read="Más alto = más caro respecto a lo que se cobra. La línea azul gruesa es la medida principal; la verde discontinua da el largo plazo con otra medida (neto medio, tasación) y no se empalma con la azul. Las grises finas son el bruto y la renta del hogar, como referencia. En las barras de abajo, azul es el precio y naranja los impuestos: si el tipo baja, la naranja resta."
          notSay="No incluye intereses de la hipoteca, la entrada ni los impuestos de la compra, y es una media nacional: en las grandes ciudades el piso cuesta bastante más (parte 2 y «Quién paga la vivienda»)."
        />
      </Figure>

      <SalePricesFigure sale={data.sale_prices} bases={data.bases} source={source} />

      <CapacityFigure capacity={data.capacity} homeM2={h.home_m2} source={source} />

      <RegionalPriceFigure regions={data.regions} homeM2={h.home_m2} capacity={data.capacity} source={source} />

      <Figure
        id="pares"
        title={`Respecto a su propia media histórica, la vivienda en España está un ${num(piEs.value - 100, 0)} % más cara en relación con la renta; en la OCDE, un ${num(piLast("OECD").value - 100, 0)} %`}
        dek={`Ratio entre el precio de la vivienda y la renta disponible por habitante, en % de la media de largo plazo de cada país (100 = lo normal en ese país). Compara la evolución, no el nivel: en ${piEs.year} España (${num(piEs.value, 0)}) está ${piRank.indexOf("ESP") === 0 ? "por encima de todos los países del grupo" : `en el puesto ${piRank.indexOf("ESP") + 1} de ${piRank.length} del grupo, por detrás de ${piRank.slice(0, piRank.indexOf("ESP")).map((geo) => `${NAMES[geo]} (${num(piLast(geo).value, 0)})`).join(", ")}`}.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País o media de comparación", color: C.ref },
        ]}
        sources={[source("oecd_dbnomics", "OCDE, Analytical house price indicators (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES")]}
        notes={["La OCDE calcula la media de largo plazo con todos los años disponibles de cada país; un valor de 120 significa un 20 % por encima de esa media, no un 20 % más cara que otro país.", "El agregado «OCDE» es el que publica la OCDE; la serie no dice qué países entran en él cada año, así que puede no ser el mismo grupo en todo el periodo. Los países, uno a uno, sí son comparables en el tiempo."]}
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

      <BurdenPeersFigure capacity={data.capacity} source={source} />

      <TenantRegionFigure territory={data.territory} segments={data.segments} source={source} />

      <Part id="oferta" title="3. Construcción y hogares">El corazón de la hipótesis: ¿se construyen menos viviendas de las que hacen falta? En España y en cada comunidad.</Part>

      <Figure
        id="construccion-y-hogares"
        title={`Las viviendas terminadas por cada hogar nuevo caen tramo a tramo: ${joinEs(W.map((w) => `${num(w.ratio, 2)} en ${w.from}–${w.to}`))}`}
        dek={`${W.map((w) => `${w.from}–${w.to}: ${thousands(w.completed_per_year)} terminadas y ${thousands(w.households_per_year)} hogares nuevos al año`).join("; ")}. Los tramos evitan medir desde el mínimo de construcción de 2013. En la década anterior fue al revés: entre 1991 y 2011 se terminaron más viviendas que hogares nuevos (máximo de ${thousands(h.completed_peak)} terminadas en ${h.completed_peak_year}).`}
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
        title={`En contra de la hipótesis: entre ${boom.from} y ${boom.to} se terminaron ${num(boom.ratio, 2)} viviendas por cada hogar nuevo y aun así el piso pasó de ${num(years2000)} a ${num(years2007)} años de salario bruto medio`}
        dek={`Durante la burbuja sobraban viviendas nuevas y aun así el precio en años de salario bruto medio subió un ${num(B.boom.gross_change_pct, 0)} % entre ${B.boom.from} y ${B.boom.to}. Lo que sí cambió a la vez fue el crédito: el tipo de los préstamos para vivienda bajó del ${num(rateAt(1990), 1)} % en 1990 al ${num(rateAt(2005), 1)} % en 2005. La escasez de obra nueva no coincide con aquella subida; sí con la de después de 2015, con tipos que volvieron a subir en 2023.`}
        legend={[
          { id: "years", label: "Años de salario bruto medio (INE)", color: C.blue },
          { id: "rate", label: "Tipo de interés de los préstamos para vivienda (%)", color: C.orange },
          { id: "credit", label: "Crédito para vivienda (% del PIB)", color: C.aqua },
        ]}
        sources={[source("bde_indicadores_vivienda", "Banco de España, tipos de interés e indicadores de vivienda"), source("ine_tempus", "INE, ETCL")]}
        notes={["Paneles con su propia escala en lugar de un gráfico con varios ejes. Correlación no es causalidad: los tipos, el empleo, la inmigración, la demanda extranjera y el uso turístico se mueven a la vez."]}
        table={
          <HousingTable
            series={[
              { id: "years", label: "Años de salario bruto medio (INE)", points: [...aff.years_ine_retro, ...aff.years_ine], unit: "years" },
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
              Años de salario bruto medio para un piso de {h.home_m2} m²
              <span>INE, tramos 2000–2007 y desde 2008</span>
            </h3>
            <HousingChart series={grossSeries} unit="years" xMin={1989} xMax={h.last_year} height={220} ariaLabel="Años de salario" />
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

      <CohortFigure composition={data.composition} source={source} />

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

      <DistributionFigure distribution={data.distribution} source={source} />

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
            <strong>La vivienda se ha encarecido.</strong> Al precio de compraventa, un piso cuesta {num(nmsLast.value)} años de sueldo neto mediano ({nmsLast.year}): más que en 2019 ({num(nmsAt(2019))})
            y que en 2013 ({num(nmsAt(2013))}), menos que en {nmsFirst.year} ({num(nmsFirst.value)}); con el salario bruto medio, {num(ys[String(B.last_year)])} años frente a {num(ys["2007"])} en 2007.
            Desde 2019, {num(tdHead(2019)?.tax_part, 2)} de los {num(tdHead(2019)?.change, 2)} años más se deben a que el trabajador paga un tipo mayor de IRPF y cotizaciones; entre 2013 y 2019 el tipo bajó. En euros, el precio de compraventa ha subido un {num(B.sale_price_change_pct["2019"], 0)} % desde 2019
            y un {num(B.sale_price_change_pct["2007"], 0)} % desde 2007, y el salario medio un {num(B.wage_change_pct["2019"], 0)} % y un {num(B.wage_change_pct["2007"], 0)} %. Frente a otros países, la carga media de los hogares españoles no es excepcional (casi la mitad de la
            población vive en una vivienda propia ya pagada), pero la de los inquilinos a precio de mercado sí: el {num(tenantsEs)} % gasta más del 40 % de su renta en vivienda, frente al{" "}
            {num(tenantsEu)} % en la UE. El alquiler declarado de todos los contratos vigentes subió hasta {rents.since.last}{" "}
            {rents.since.bases.map((b) => `un ${num(b.rent, 0)} % desde ${b.base} (${paceWord(b.rent, b.wage, b.cpi)} salarios y precios: ${num(b.wage, 0)} % y ${num(b.cpi, 0)} %)`).join(", ")};{" "}
            {rents.since.first} es el primer año de la serie{rents.since.first_is_local_high ? " y un máximo" : ""}, y {rents.since.low} su mínimo. El precio de los contratos nuevos, el que paga quien busca piso hoy, no lo publica la estadística oficial por separado.
          </li>
          <li>
            <Verdict kind="partly" />
            <strong>«Desde 2008 se terminan muchas menos viviendas que hogares se forman».</strong> Es cierto a partir de 2013, no de 2008: {W.map((w) => `${num(w.ratio, 2)} viviendas
            por hogar nuevo en ${w.from}–${w.to}`).join(", ")}. Entre 2008 y 2012 todavía se terminaban más viviendas que hogares (las obras de la burbuja), y el déficit se agrava en
            el último tramo, no solo en el mínimo de 2013. Y el déficit no es uniforme: es grave en {joinEs(regionWorst.map((row) => row.name))} y no existe en{" "}
            {joinEs(regionSurplus.map((row) => row.name))}, donde se terminaron tantas viviendas como hogares nuevos o más.
          </li>
          <li>
            <Verdict kind="partly" />
            <strong>«Sobre todo» por eso.</strong> La escasez coincide con el ciclo posterior a 2015, pero no con el de {B.boom.from}–{B.boom.to}, cuando se construyeron {num(boom.ratio, 2)} viviendas por hogar
            nuevo ({boom.from}–{boom.to}) y aun así el precio en años de salario bruto medio subió un {num(B.boom.gross_change_pct, 0)} % (de {num(B.boom.gross_from)} a {num(B.boom.gross_to)}; con el neto medio, un{" "}
            {num(B.boom.net_change_pct, 0)} %). A la vez, el saldo de préstamos para comprar vivienda pasó del {num(B.boom.credit_from)} % del PIB en {B.boom.from} al {num(B.boom.credit_to)} % en {B.boom.to}, con el tipo
            hipotecario entre el {num(B.boom.rate_min)} % y el {num(B.boom.rate_max)} %. Que el crédito y el precio subieran juntos no prueba que uno causara el otro.
            De dónde salen los hogares nuevos de ahora sí lo miden estos datos: no del eco del baby boom (la generación de 25 a 39 años se encoge desde {cohortPeak.year}), sino del aumento de población, que viene de la inmigración
            (el {num((decLast.population_effect / decLast.total) * 100, 0)} % de los hogares nuevos de {decLast.from}–{decLast.to}), y antes de hogares más pequeños. Los pisos turísticos pesan poco en el total ({num(data.regions.tourist_es, 2)} % del parque), pero mucho en algunas
            comunidades y barrios. Repartir el encarecimiento entre estas causas exige un modelo que esta página no hace.
          </li>
          <li>
            <Verdict kind="no" />
            <strong>«No porque el gasto público sea bajo».</strong> El gasto público en vivienda sí es bajo: {num(spendLast("ES").total, 2)} % del PIB,{" "}
            {spendRank[0] === "ES" ? "el menor de su grupo de comparación" : `menos que ${spendRank.slice(spendRank.indexOf("ES") + 1).map((geo) => NAMES[geo]).join(", ")}`},
            y {num(spendLast("EU27_2020").total / spendLast("ES").total, 1)} veces menos que la media de la UE
            {data.social_rental_stock.find((row) => row.country === "ESP") ? `, con un parque social de alquiler del ${num(data.social_rental_stock.find((row) => row.country === "ESP").value, 1)} % de las viviendas frente al ${num((data.social_rental_stock.find((row) => row.country === "OECD") || {}).value ?? 0, 1)} % de media en la OCDE` : ""}.
            Y no es por falta de ingresos ligados a la vivienda: los impuestos sobre inmuebles y sus compraventas recaudan el {num(esMoney.collected, 2)} % del PIB,{" "}
            {num(esMoney.collected / esMoney.spent, 0)} veces lo que se gasta (en Alemania, {num(deMoney.collected / deMoney.spent, 1)}), aunque esa recaudación no está afectada a la
            vivienda. Lo que los datos no permiten afirmar es que gastar más bajaría los precios: eso depende de si el gasto añade viviendas o solo ayuda a pagar las que hay.
          </li>
        </ul>
        <h2>Lo que estos datos no pueden decir</h2>
        <ul>
          <li>Causalidad: tipos de interés, empleo, inmigración, demanda extranjera y alquiler turístico se mueven a la vez; ninguno se aísla aquí.</li>
          <li>Dónde exactamente: casi todas las cifras son nacionales o autonómicas; solo el alquiler declarado baja a municipio (las grandes ciudades frente al resto de su provincia). El déficit se concentra en ciudades y barrios concretos; las viviendas vacías, a menudo donde no hay demanda.</li>
          <li>
            Quién, cruzando todo: no hay tabla oficial de sobrecarga por edad, tenencia y comunidad a la vez, ni sueldo oficial por edad y comunidad. «Quién paga la vivienda» calcula ese cruce con los microdatos de la ECV, con su margen de error, pero la muestra no baja de comunidad ni llega a todas las celdas (los jóvenes que alquilan en Madrid no llegan a {seg?.micro?.min_n ?? 50} hogares). Los hogares tipo siguen calculándose con cortes sueltos y ponen al lado la celda de la encuesta que más se les parece, diciendo cuál.
          </li>
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
            <dt>Años de sueldo</dt>
            <dd>Precio de un piso de {h.home_m2} m² dividido por el sueldo anual: cuántos años de sueldo íntegro costaría, sin intereses ni gastos. La medida principal usa el sueldo neto mediano (lo que cobra el trabajador del medio tras IRPF y cotizaciones) y el precio de compraventa; con el salario bruto medio y la tasación sale bastante menos.</dd>
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
            <strong>Denominador.</strong> El precio se mide en años de sueldo neto mediano (con el bruto medio y la renta del hogar como complemento); la construcción, por hogar nuevo; el gasto público, en % del PIB.
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

// Change in years of net pay between two years, split into price against gross pay and the worker's tax rate.
function TaxSplit({ rows }) {
  const max = Math.max(...rows.flatMap((row) => [Math.abs(row.price_part), Math.abs(row.tax_part)]));
  const bar = (value, color) => (
    <span className="hvSplit__track">
      <span className="hvSplit__bar" style={{ width: `${(Math.abs(value) / max) * 50}%`, [value < 0 ? "right" : "left"]: "50%", background: color }} />
    </span>
  );
  const sgn = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v), 2)}`;
  return (
    <ul className="hvSplit" aria-label="Cambio en años de sueldo neto por tramos, separado en precio e impuestos">
      {rows.map((row) => (
        <li key={`${row.from}-${row.to}`}>
          <span className="hvSplit__label">
            {row.from}–{row.to}: <strong>{sgn(row.change)} años</strong>
          </span>
          <span className="hvSplit__row">
            <span>Precio frente al sueldo bruto {sgn(row.price_part)}</span>
            {bar(row.price_part, C.blue)}
          </span>
          <span className="hvSplit__row">
            <span>
              IRPF y cotizaciones {sgn(row.tax_part)} ({num(row.rate_from)} % → {num(row.rate_to)} %)
            </span>
            {bar(row.tax_part, C.orange)}
          </span>
        </li>
      ))}
    </ul>
  );
}
