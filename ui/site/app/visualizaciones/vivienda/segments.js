import Figure from "../components/Figure";
import { Explain } from "./explain";
import { C, num, thousands } from "./common";
import MicroGrid, { MICRO_AGES, MICRO_TERR, ageLabel, ci, eurCi, microIndex, stat } from "./micro";

// Who pays for housing: one figure for the composition effect behind the national mean. Top: one column per tenure,
// as wide as its share of the population and as tall as its overburden rate, so the national rate is the area-weighted
// mean of the columns. Middle: who sits in each column, by age of the household's reference person (now and in the
// first year the survey splits owners by mortgage), plus the young people still living with their parents, whom no
// cost statistic sees. Bottom: the shared typical cases with the national mean and median beside them.
export const TENURE = {
  OWN_NL: { label: "Propietario sin hipoteca", short: "Casa pagada", color: C.aqua, ink: "#0b3d2b" },
  OWN_L: { label: "Propietario con hipoteca", short: "Hipoteca", color: C.blue, ink: "#ffffff" },
  RENT_MKT: { label: "Alquiler a precio de mercado", short: "Alquiler de mercado", color: C.orange, ink: "#ffffff" },
  RENT_FR: { label: "Alquiler reducido o vivienda cedida", short: "Reducido o cedido", color: C.yellow, ink: "#3d2a00" },
};
const ORDER = ["OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR"];
const CASE_TENURE = { p1_young_renter_madrid: "RENT_MKT", p2_family_renter_metro: "RENT_MKT", p2_family_buyer_madrid: "OWN_L", p4_retired_owner_interior: "OWN_NL" };
const CASE_TAG = { p1_young_renter_madrid: "1", p2_family_renter_metro: "2a", p2_family_buyer_madrid: "2b", p4_retired_owner_interior: "4" };

const listYears = (years) => (years.length > 1 ? `${years.slice(0, -1).join(", ")} y ${years[years.length - 1]}` : String(years[0]));

function eur(value) {
  return `${thousands(value)} €`;
}

// The survey cell beside each typical case: the narrowest definition with enough sample (README §3). When the exact
// definition has too few households, the row says so and which broader cell it uses; with none, the marginal cut stays.
function surveyCell(micro, key) {
  const defs = micro?.cases?.[key];
  if (!defs?.length) return null;
  const used = defs.find((d) => d.s);
  return { used, exact: defs[0], all: defs };
}

const SURVEY_CAVEAT = {
  p1_young_renter_madrid: "Es la renta encuestada de esos hogares, no el sueldo modelo: incluye a quienes alquilan en pareja o compartiendo gastos, y alquileres firmados hace años.",
  p2_family_renter_metro: "Hogares de la comunidad entera, no solo del área metropolitana, con su renta encuestada en lugar de los dos sueldos modelo.",
  p2_family_buyer_madrid: "La encuesta solo cuenta los intereses de la hipoteca, no la amortización, y es de quien ya compró, a menudo hace años y más barato: no es la cuota de quien compra hoy.",
  p4_retired_owner_interior: "Renta encuestada de quienes viven solos con 65 o más años en casa pagada en Aragón, Castilla y León, Castilla-La Mancha, Extremadura, Navarra y La Rioja.",
};

function surveyText(cell, micro, key) {
  if (!cell?.used) return null;
  const med = stat(cell.used, "burden_median");
  const over = stat(cell.used, "overburden_pct");
  const exact = cell.used === cell.exact;
  return {
    main: `${num(med.value, 0)} % de peso mediano; ${num(over.value, 0)} % pasan del 40 %`,
    caveat: SURVEY_CAVEAT[key],
    detail: `${exact ? "" : `Con su definición exacta («${cell.exact.label}») hay ${cell.exact.n} hogares en la muestra, menos de ${micro.min_n}: se usa el grupo «${cell.used.label}». `}${exact ? `Grupo «${cell.used.label}»: ` : ""}${cell.used.n} hogares en la muestra${cell.used.n < micro.low_n ? " (precisión baja)" : ""}; intervalos del 95 %: peso ${ci(med)}, sobrecarga ${ci(over)}.`,
  };
}

export default function WhoPaysFigure({ segments, source }) {
  if (!segments?.tenure?.length) return null;
  const sg = segments;
  const t = Object.fromEntries(sg.tenure.map((row) => [row.key, row]));
  const yMax = Math.ceil(Math.max(...sg.tenure.map((row) => row.overburden_pct)) / 5) * 5;
  const at = sg.age_tenure;
  const cases = Object.fromEntries(sg.cases.map((c) => [c.key, c]));
  const nat = cases.national;
  const home = sg.at_home["Y25-34"];
  const p1 = cases.p1_young_renter_madrid;
  const p2r = cases.p2_family_renter_metro;
  const p2b = cases.p2_family_buyer_madrid;
  const p4 = cases.p4_retired_owner_interior;
  const madrid = sg.cities.find((c) => c.code === "28079");
  const young = at.rows.find((row) => row.age === "16–29");
  const mid = at.rows.find((row) => row.age === "30–44");
  const old = at.rows.find((row) => row.age === "65+");
  const ratio = t.RENT_MKT.overburden_pct / t.OWN_NL.overburden_pct;
  const micro = sg.micro;
  const cellOf = micro ? microIndex(micro) : () => null;
  const natCell = cellOf("ES", "TOTAL", "TOTAL");
  const survey = (key) => surveyText(surveyCell(micro, key), micro, key);
  const geoName = (g) => micro?.geo_names?.[g] || g;
  const mc = (geo, age, tenure, key) => stat(cellOf(geo, age, tenure), key);
  const rentYoung = micro && mc("ES", "16-29", "RENT_MKT", "overburden_pct");
  const rentMid = micro && mc("ES", "30-44", "RENT_MKT", "overburden_pct");
  const rentBy = (geo) => micro && mc(geo, "TOTAL", "RENT_MKT", "overburden_pct");
  const rentInc = (geo) => micro && mc(geo, "TOTAL", "RENT_MKT", "income_cu_median");
  const youngMadrid = micro && cellOf("ES30", "16-29", "RENT_MKT");
  const val = micro?.validation?.[String(micro?.year)];
  const trendOf = (year, geo, age, tenure, key) => {
    const c = micro?.trend?.find((row) => row.year === year && row.geo === geo && row.age === age && row.tenure === tenure);
    return stat(c, key);
  };
  const firstYear = micro?.years?.[0];
  const rent0 = micro && trendOf(firstYear, "ES", "TOTAL", "RENT_MKT", "overburden_pct");
  const rentNow = micro && mc("ES", "TOTAL", "RENT_MKT", "overburden_pct");
  const microDek = micro && rentYoung && rentMid && rentBy("ES30") && rentBy("ES51") && rentBy("ES_RESTO")
    ? ` Debajo, lo que las tablas oficiales no cruzan, calculado con los microdatos de la ECV ${micro.year} (en hogares, con su margen de error): entre los que alquilan a precio de mercado pasa del 40 % el ${num(rentYoung.value, 0)} % de los hogares de 16 a 29 años y el ${num(rentMid.value, 0)} % de los de 30 a 44; entre Madrid (${num(rentBy("ES30").value, 0)} %), Cataluña (${num(rentBy("ES51").value, 0)} %) y el resto de España (${num(rentBy("ES_RESTO").value, 0)} %) ${micro.reading.rent_territory_overlap ? "las diferencias caben en el margen de error" : "hay diferencias mayores que el margen de error"}, y los alquileres más altos de Madrid y Cataluña van con rentas más altas de sus inquilinos (${thousands(rentInc("ES30").value)} y ${thousands(rentInc("ES51").value)} € por unidad de consumo, frente a ${thousands(rentInc("ES_RESTO").value)} €). Queda abierto lo que ni así se ve: la muestra no da para los jóvenes que alquilan en Madrid (${youngMadrid?.n ?? 0} hogares).`
    : " Queda abierto lo que estas tablas no cruzan: no hay sobrecarga oficial por edad dentro de cada tenencia ni por comunidad dentro de cada tenencia.";
  const caseRows = [
    p1 && {
      id: "p1",
      tag: "1",
      who: "Joven de 25 a 34 años que vive sola de alquiler en la ciudad de Madrid",
      cost: `${eur(p1.cost_month)} de alquiler`,
      share: p1.share_pct,
      left: p1.left_month,
      group: `${num(p1.overburden_pct)} % (inquilinos de mercado)`,
      survey: survey("p1_young_renter_madrid"),
      how: `Alquiler mediano declarado de la ciudad (SERPAVI ${p1.rent_year}) sobre el sueldo neto medio de 25 a 34 años ajustado al nivel salarial de Madrid, con el tipo de IRPF y cotizaciones que corresponde a ese sueldo (${eur(p1.income_year)} al año, ${p1.pay_year}).`,
    },
    p2r && {
      id: "p2a",
      tag: "2a",
      who: "Pareja de 30 a 44 años con dos hijos y dos sueldos, de alquiler en el área metropolitana de Madrid",
      cost: `${eur(p2r.cost_month)} de alquiler`,
      share: p2r.share_pct,
      left: p2r.left_month,
      group: `${num(p2r.overburden_pct)} % (inquilinos de mercado)`,
      survey: survey("p2_family_renter_metro"),
      how: `Alquiler mediano del resto de la provincia de Madrid (media de los municipios ponderada por contratos, SERPAVI ${p2r.rent_year}) sobre la renta neta de dos sueldos, al 100 % y al 67 % del salario medio (OCDE Taxing Wages ${p2r.pay_year}: ${eur(p2r.gross_year)} brutos, ${num(p2r.net_rate_pct)} % de IRPF y cotizaciones netos de prestaciones, ${eur(p2r.income_year)} netos), como en la carga fiscal.`,
    },
    p2b && {
      id: "p2b",
      tag: "2b",
      who: `La misma pareja si compra hoy un piso de 90 m² en la Comunidad de Madrid`,
      cost: `${eur(p2b.cost_month)} de cuota`,
      share: p2b.share_pct,
      left: p2b.left_month,
      group: `${num(p2b.overburden_pct)} % (con hipoteca; no cuenta la amortización)`,
      survey: survey("p2_family_buyer_madrid"),
      how: `Precio de tasación de ${p2b.price_year} (${eur(p2b.home_price)}), ${num(p2b.ltv_pct, 0)} % financiado a ${p2b.years} años al ${num(p2b.rate_pct, 2)} % (tipo medio, Banco de España); la entrada y el ITP (${num(p2b.itp_pct, 0)} %) suman ${eur(p2b.upfront)}, ${num(p2b.upfront_years_income)} años de su renta neta. Renta: la de los mismos dos sueldos (${eur(p2b.income_year)} netos).`,
    },
    p4 && {
      id: "p4",
      tag: "4",
      who: "Pensionista de 65 años o más que vive solo, propietario sin hipoteca, en una provincia del interior",
      cost: `${eur(p4.cost_month)} de gastos`,
      share: p4.share_pct,
      left: p4.left_month,
      group: `${num(p4.overburden_pct)} % (casa pagada)`,
      survey: survey("p4_retired_owner_interior"),
      how: `Gasto medio de quien vive solo con 65 o más años en casa propia (EU-SILC ${p4.survey_year}, ${num(sg.assumptions.eur_per_pps, 3)} € por PPS) sobre la pensión media de vejez y supervivencia por pensionista (${eur(p4.pension_gross)} brutos en ${p4.pension_year}: gasto en pensiones de la contabilidad pública entre pensionistas de Eurostat) menos su IRPF (${num(p4.pension_tax_pct)} %, OCDE), ${eur(p4.income_year)} netos. Es un dato nacional: no hay pensión media por provincia en estas fuentes.`,
    },
  ].filter(Boolean);

  return (
    <Figure
      id="quien-paga"
      title={`La media dice que la vivienda se lleva el ${num(sg.cost_share_mean)} % de la renta (la mediana, el ${num(sg.cost_share_median)} %); pero el ${num(t.OWN_NL.pop_pct)} % vive en casa pagada y dedica poco a la vivienda (sobrecarga del ${num(t.OWN_NL.overburden_pct)} %), mientras el ${num(t.RENT_MKT.pop_pct)} % que alquila a precio de mercado carga con el problema (${num(t.RENT_MKT.overburden_pct)} %)`}
      dek={`Arriba, una columna por régimen de tenencia: su anchura es la parte de la población que vive así y su altura, cuántos gastan más del 40 % de su renta en vivienda (EU-SILC ${sg.year}). La tasa de toda la población (${num(sg.overburden_total)} %, como la media de la UE, ${num(sg.overburden_total_eu)} %) es la media de las columnas pesada por su anchura: es baja porque la columna ancha, la de la casa pagada, casi no tiene sobrecarga. Entre quien alquila a precio de mercado es ${num(ratio, 0)} veces mayor, y ${num(t.RENT_MKT.overburden_pct - t.RENT_MKT.overburden_eu, 0)} puntos más alta que en la UE. En medio, quién está en cada columna: el ${num(old.shares.OWN_NL)} % de los hogares de 65 o más años tiene la casa pagada; de los de 16 a 29 años que se han ido de casa, el ${num(young.shares.RENT_MKT)} % alquila a precio de mercado, y entre los de 30 a 44 el alquiler de mercado ha pasado del ${num(mid.shares_first.RENT_MKT)} % en ${at.first_year} al ${num(mid.shares.RENT_MKT)} %. Y la mitad de los jóvenes ni aparece: el ${num(home.ES.value)} % de los de 25 a 34 años vive con sus padres (UE: ${num(home.EU27_2020.value)} %). Abajo, cinco hogares tipo con la media nacional al lado. Zanja dos relatos: ni «la vivienda no es un problema, estamos en la media europea» ni «a todos los hogares les ahoga la vivienda».${microDek}`}
      legendKind="bar"
      legend={ORDER.map((key) => ({ id: key, label: TENURE[key].label, color: TENURE[key].color }))}
      sources={[
        source("eurostat_sdmx", "Eurostat, EU-SILC: ilc_lvho02 (población por tenencia), ilc_lvho07c (sobrecarga por tenencia), ilc_mded01 y ilc_lvho08a (media y mediana del peso de la vivienda), ilc_lvps08 (viven con sus padres), ilc_mded03 (gasto en PPS)", "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07c/default/table"),
        source("ine_tempus", "INE, Encuesta de Condiciones de Vida: tenencia por edad de la persona de referencia (t. 9994), renta por tenencia (t. 59956) y por comunidad (t. 9949)", "https://www.ine.es/jaxiT3/Tabla.htm?t=9994"),
        source("mivau_boletin", "Ministerio de Vivienda, SERPAVI (alquiler declarado por municipio) y valor tasado por comunidad", "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi"),
        ...(micro
          ? [
              source("ine_ecv_microdatos", `INE, Encuesta de Condiciones de Vida, microdatos transversales ${listYears(micro.years)} (estimación propia por celda)`),
              { label: `INE, «Cambio de base poblacional en las estimaciones de la ECV» (intervalos de confianza de la ECV ${micro.calibration.year})`, href: micro.calibration.document_url },
            ]
          : []),
      ]}
      notes={[
        "Sobrecarga: gasto total en vivienda (alquiler o intereses de la hipoteca, suministros, comunidad, seguros, reparaciones e impuestos, netos de ayudas) por encima del 40 % de la renta disponible. No incluye la amortización del capital de la hipoteca, así que subestima el esfuerzo de quien está pagando su casa. La EU-SILC cuenta personas; la ECV de la segunda parte cuenta hogares según la edad de su persona de referencia.",
        `Los hogares tipo son ilustrativos: no hay cruce oficial de edad, tenencia y municipio, así que cada cifra sale del corte que define al hogar (su municipio, su tenencia, su edad) y se dice cuál en cada fila. Renta de la encuesta ${sg.assumptions.ecv_year} (ingresos del año anterior); alquileres declarados en el IRPF, que son los de todos los contratos vigentes: quien firma hoy paga más.`,
        `Media y mediana: el ${num(sg.cost_share_mean)} % es la media de lo que pesa la vivienda en la renta de cada hogar; la mitad de la población dedica menos del ${num(sg.cost_share_median)} %. La fila «Media nacional» de la tabla divide el gasto medio por la renta media (${num(nat.share_pct)} %).`,
        ...(micro
          ? [
              `Microdatos: estimación propia con los ficheros transversales de la ECV y sus factores de elevación, con la edad de la persona de referencia del hogar, su régimen de tenencia y su comunidad, y el peso de la vivienda definido como Eurostat (gasto menos ayudas a la vivienda, sobre la renta disponible del año anterior menos esas ayudas). Celdas con menos de ${micro.min_n} hogares en la muestra, vacías; de ${micro.min_n} a ${micro.low_n - 1}, marcadas. Intervalos del 95 %: el fichero público no trae los estratos ni las secciones del muestreo, así que el error se calcula con el hogar como unidad y se agranda con un factor (${num(micro.design_effect, 2)}, el mayor de los ${micro.calibration.indicators} que salen de comparar con los intervalos publicados por el INE para la ECV ${micro.calibration.year}).`,
              val
                ? `Comprobación: con los mismos ficheros se reproducen, en ${listYears(micro.years)}, las tablas del INE de tenencia por edad (t. 9994) y de renta por tenencia (t. 59956), y la sobrecarga por tenencia y la mediana del peso de la vivienda de Eurostat, dentro del redondeo. La media del peso sale del ${num(val.ilc_mded01.microdata)} % frente al ${num(val.ilc_mded01.published)} % de Eurostat: depende de cómo se cuente a las personas en hogares con renta nula o negativa (el ${num(val.ilc_mded01.non_positive_income_pct)} %; aquí, al 100 %; sin ellas, ${num(val.ilc_mded01.excluding_non_positive_income)} %).`
                : null,
              `Hogares, no personas: el panel de microdatos cuenta hogares, y la columna de arriba, personas. Por eso la sobrecarga de quien alquila a precio de mercado sale más alta en hogares (${num(rentNow.value, 0)} %) que en personas (${num(t.RENT_MKT.overburden_pct, 0)} %): los hogares de una persona, más sobrecargados, cuentan lo mismo que los grandes.${rent0 ? ` En ${firstYear}, antes de la pandemia, la de los hogares que alquilaban a precio de mercado era del ${num(rent0.value, 0)} % (${num(rent0.lo, 0)}–${num(rent0.hi, 0)}); el paso de ${firstYear} a ${micro.year} se ve en la tabla, año a año.` : ""}`,
            ].filter(Boolean)
          : []),
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Régimen de tenencia</th>
                  <th scope="col">% de la población ({sg.year})</th>
                  <th scope="col">Sobrecarga, España</th>
                  <th scope="col">Sobrecarga, UE-27</th>
                </tr>
              </thead>
              <tbody>
                {ORDER.map((key) => (
                  <tr key={key}>
                    <td>{TENURE[key].label}</td>
                    <td>{num(t[key].pop_pct)} %</td>
                    <td>{num(t[key].overburden_pct)} %</td>
                    <td>{t[key].overburden_eu != null ? `${num(t[key].overburden_eu)} %` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th scope="col">Edad de la persona de referencia</th>
                  {ORDER.map((key) => (
                    <th scope="col" key={key}>
                      {TENURE[key].short}, {at.year} ({at.first_year})
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {at.rows.map((row) => (
                  <tr key={row.age}>
                    <td>{row.age}</td>
                    {ORDER.map((key) => (
                      <td key={key}>
                        {num(row.shares[key])} % ({num(row.shares_first[key])} %)
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {micro ? <MicroTables micro={micro} geoName={geoName} /> : null}
          </div>
        </details>
      }
    >
      <div className="hvMosaic" role="img" aria-label={`Sobrecarga por régimen de tenencia, con el ancho proporcional a la población: ${ORDER.map((key) => `${TENURE[key].label}, ${num(t[key].pop_pct)} % de la población, sobrecarga ${num(t[key].overburden_pct)} %`).join("; ")}`}>
        <h3 className="vizPanelTitle">
          Gastan más del 40 % de su renta en vivienda, según cómo viven
          <span>ancho = parte de la población; alto = tasa de sobrecarga</span>
        </h3>
        <div className="hvMosaic__plot">
          <div className="hvMosaic__mean" style={{ bottom: `${(sg.overburden_total / yMax) * 100}%` }}>
            <span>Toda la población: {num(sg.overburden_total)} %</span>
          </div>
          {ORDER.map((key) => (
            <div key={key} className="hvMosaic__col" style={{ flexBasis: `${t[key].pop_pct}%` }}>
              <span className="hvMosaic__value">{num(t[key].overburden_pct)} %</span>
              <span className="hvMosaic__bar" style={{ height: `${(t[key].overburden_pct / yMax) * 100}%`, background: TENURE[key].color }} />
            </div>
          ))}
        </div>
        <div className="hvMosaic__axis" aria-hidden="true">
          {ORDER.map((key) => (
            <div key={key} style={{ flexBasis: `${t[key].pop_pct}%` }}>
              <span className="hvMosaic__share">{num(t[key].pop_pct, 0)} %</span>
              <span className="hvMosaic__cases">
                {Object.entries(CASE_TENURE)
                  .filter(([caseKey, tenureKey]) => tenureKey === key && cases[caseKey])
                  .map(([caseKey]) => (
                    <b key={caseKey} className="hvCaseTag">
                      {CASE_TAG[caseKey]}
                    </b>
                  ))}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="vizPanelTitle">
          Quién vive en cada columna: hogares por edad de la persona de referencia
          <span>
            barra gruesa: {at.year}; fina: {at.first_year}
          </span>
        </h3>
        <ul className="hvStack" aria-label="Régimen de tenencia por edad">
          {at.rows.map((row) => (
            <li key={row.age} className={row.age === "Total" ? "hvStack__total" : undefined}>
              <span className="hvStack__label">{row.age === "Total" ? "Todos" : `${row.age} años`}</span>
              <span className="hvStack__bars">
                {["shares", "shares_first"].map((which) => (
                  <span key={which} className={`hvStack__bar hvStack__bar--${which === "shares" ? "now" : "then"}`}>
                    {ORDER.map((key) => (
                      <span
                        key={key}
                        title={`${TENURE[key].label}: ${num(row[which][key])} % (${which === "shares" ? at.year : at.first_year})`}
                        style={{ width: `${row[which][key]}%`, background: TENURE[key].color, color: TENURE[key].ink }}
                      >
                        {which === "shares" && row[which][key] >= 12 ? `${num(row[which][key], 0)} %` : ""}
                      </span>
                    ))}
                  </span>
                ))}
              </span>
            </li>
          ))}
          <li className="hvStack__home">
            <span className="hvStack__label">Personas de 25–34</span>
            <span className="hvStack__bars">
              <span className="hvStack__bar hvStack__bar--now">
                <span style={{ width: `${home.ES.value}%` }} className="hvStack__parents">
                  {num(home.ES.value)} % con sus padres
                </span>
                <span style={{ width: `${100 - home.ES.value}%` }} className="hvStack__away">
                  se han ido
                </span>
              </span>
              <span className="hvStack__note">UE: {num(home.EU27_2020.value)} % con sus padres ({home.ES.year}). No pagan vivienda propia y no salen en ninguna estadística de gasto.</span>
            </span>
          </li>
        </ul>
      </div>

      {micro ? <MicroGrid micro={micro} order={ORDER} tenure={TENURE} /> : null}

      <div>
        <h3 className="vizPanelTitle">
          Cinco hogares tipo frente a la media
          <span>{micro ? "cifras ilustrativas, cada una con su cálculo; a la derecha, hogares reales parecidos de la encuesta" : "cifras ilustrativas, cada una con su cálculo"}</span>
        </h3>
        <div className="hvCases__wrap">
          <table className="hvCases">
            <thead>
              <tr>
                <th scope="col">Hogar</th>
                <th scope="col">Vivienda al mes</th>
                <th scope="col">Peso en su renta</th>
                <th scope="col">Le queda al mes</th>
                <th scope="col">{micro ? `Hogares como este en la encuesta (ECV ${micro.year})` : "Sobrecarga de su grupo"}</th>
              </tr>
            </thead>
            <tbody>
              <tr className="hvCases__ref">
                <th scope="row">Media nacional (todos los hogares)</th>
                <td data-label="Vivienda al mes">{eur(nat.cost_month)}</td>
                <td data-label="Peso en su renta">
                  {num(sg.cost_share_mean)} % de media
                  <br />
                  {num(sg.cost_share_median)} % la mediana
                </td>
                <td data-label="Le queda al mes">{eur(nat.left_month)}</td>
                <td data-label="En la encuesta" className="hvCases__survey">
                  {micro && stat(natCell, "burden_median") ? (
                    <>
                      {num(stat(natCell, "burden_median").value, 0)} % de peso mediano por hogar; {num(stat(natCell, "overburden_pct").value, 0)} % de los hogares pasan del 40 %
                      <small>Contando personas (EU-SILC): {num(nat.overburden_pct)} % sobrecargadas y {num(sg.cost_share_median)} % de peso mediano. {thousands(natCell.n)} hogares en la muestra.</small>
                    </>
                  ) : (
                    `${num(nat.overburden_pct)} %`
                  )}
                </td>
              </tr>
              {caseRows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">
                    <b className="hvCaseTag">{row.tag}</b> {row.who}
                    <small>{row.how}</small>
                  </th>
                  <td data-label="Vivienda al mes">{row.cost}</td>
                  <td data-label="Peso en su renta">
                    <strong>{num(row.share)} %</strong>
                  </td>
                  <td data-label="Le queda al mes">{eur(row.left)}</td>
                  <td data-label="En la encuesta" className="hvCases__survey">
                    {row.survey ? (
                      <>
                        {row.survey.main}
                        <small>
                          {row.survey.detail} {row.survey.caveat}
                        </small>
                      </>
                    ) : (
                      <>
                        {row.group}
                        {micro ? <small>Corte marginal: la muestra no llega a {micro.min_n} hogares con esta definición.</small> : null}
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {cases.e_living_with_parents ? (
                <tr>
                  <th scope="row">
                    <b className="hvCaseTag">E</b> Joven de 25 a 34 años que sigue en casa de sus padres
                    <small>
                      Es el {num(cases.e_living_with_parents.at_home_pct)} % de su edad ({cases.e_living_with_parents.year}; UE: {num(cases.e_living_with_parents.at_home_eu_pct)} %). Se cuenta dentro del hogar de sus padres, casi siempre propietarios: su coste es no poder irse.
                    </small>
                  </th>
                  <td data-label="Vivienda al mes">—</td>
                  <td data-label="Peso en su renta">no se mide</td>
                  <td data-label="Le queda al mes">—</td>
                  <td data-label="En la encuesta" className="hvCases__survey">no aparece</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      <Explain
        shows={`Por qué la media de lo que cuesta la vivienda (${num(sg.cost_share_mean)} % de la renta) no describe a casi nadie: el país está partido entre quien ya tiene la casa pagada, quien la está pagando y quien alquila, y esa partición sigue la edad.`}
        read={`El área de cada columna es su aportación a la sobrecarga total. La columna naranja es estrecha (${num(t.RENT_MKT.pop_pct)} % de la población) pero alta; la verde, ancha y casi plana. Los números de bajo cada columna (${Object.values(CASE_TAG).join(", ")}) son los hogares tipo de la tabla.${madrid ? ` En el hogar 1, el alquiler (${eur(madrid.rent_month)}) es el de la ciudad de Madrid; en el resto de su provincia es ${eur(madrid.rest_rent_month)}.` : ""}${micro ? " En el panel de microdatos, cada bloque es una de esas columnas partida por edad (filas) y territorio (Madrid, Cataluña y el resto, que juntos son España): si las rayas de dos puntos se solapan, la diferencia entre ellos cabe en el margen de error." : ""} En la tabla de hogares tipo, la cifra principal es un cálculo con precios y sueldos modelo; la última columna, lo que declaran en la encuesta hogares reales parecidos.`}
        notSay={
          micro
            ? `Las celdas por edad, tenencia y territorio son una estimación propia con los microdatos, no una tabla oficial. Sus intervalos se calculan sin los estratos ni las secciones del muestreo, con un factor calibrado con indicadores de pobreza; la tenencia puede concentrarse más por barrios, así que pueden quedarse cortos. Donde la muestra no llega a ${micro.min_n} hogares (los jóvenes que alquilan en Madrid, quienes alquilan en Ceuta o en Melilla) no hay cifra, y por debajo de comunidad no hay muestra: la ciudad de Madrid frente al resto de su provincia solo se ve con el alquiler declarado. No cuenta el alquiler que se ahorra quien vive en casa propia ni la amortización de la hipoteca, y la renta es la del año anterior a la encuesta.`
            : "No da la sobrecarga de cada edad dentro de cada tenencia ni la de cada comunidad: las tablas oficiales no la cruzan y la muestra de la encuesta no da para tanto (haría falta trabajar los microdatos, con sus márgenes de error). Tampoco cuenta el alquiler que se ahorra quien vive en casa propia ni la amortización de la hipoteca."
        }
      />
    </Figure>
  );
}

const TEN_LABEL = { OWN_NL: "Casa pagada", OWN_L: "Con hipoteca", RENT_MKT: "Alquiler de mercado", RENT_FR: "Reducido o cedido", TOTAL: "Todas" };

function cellText(cell, key, digits = 0, money = false) {
  const s = stat(cell, key);
  if (!s) return "—";
  return money ? eurCi(s) : ci(s, digits);
}

function MicroTables({ micro, geoName }) {
  const get = microIndex(micro);
  const regions = Object.keys(micro.geo_names).filter((g) => /^ES\d/.test(g));
  const terr = ["ES", ...MICRO_TERR.map(([g]) => g)];
  const trendGet = (year, geo, age, tenure) => micro.trend.find((r) => r.year === year && r.geo === geo && r.age === age && r.tenure === tenure);
  return (
    <>
      <table>
        <caption>
          Microdatos ECV {micro.year}: hogares por edad de la persona de referencia, tenencia y territorio (valor e intervalo del 95 %; renta de {micro.income_year}, al año por unidad de consumo)
        </caption>
        <thead>
          <tr>
            <th scope="col">Territorio</th>
            <th scope="col">Edad</th>
            <th scope="col">Tenencia</th>
            <th scope="col">Hogares en la muestra</th>
            <th scope="col">% de los hogares de su edad</th>
            <th scope="col">Peso mediano de la vivienda</th>
            <th scope="col">Peso medio</th>
            <th scope="col">Hogares por encima del 40 %</th>
            <th scope="col">Renta mediana por unidad de consumo</th>
            <th scope="col">Le queda tras la vivienda (mediana)</th>
          </tr>
        </thead>
        <tbody>
          {terr.flatMap((g) =>
            MICRO_AGES.flatMap((age) =>
              ["OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR", "TOTAL"].map((tk) => {
                const c = get(g, age, tk);
                if (!c) return null;
                return (
                  <tr key={`${g}${age}${tk}`}>
                    <td>{geoName(g)}</td>
                    <td>{ageLabel(age)}</td>
                    <td>{TEN_LABEL[tk]}</td>
                    <td>
                      {c.n}
                      {c.n < micro.min_n ? " (vacía)" : c.n < micro.low_n ? " (precisión baja)" : ""}
                    </td>
                    <td>{tk === "TOTAL" ? "—" : cellText(c, "households_pct", 1)}</td>
                    <td>{cellText(c, "burden_median", 1)}</td>
                    <td>{cellText(c, "burden_mean", 1)}</td>
                    <td>{cellText(c, "overburden_pct", 1)}</td>
                    <td>{cellText(c, "income_cu_median", 0, true)}</td>
                    <td>{cellText(c, "left_cu_median", 0, true)}</td>
                  </tr>
                );
              }),
            ),
          )}
        </tbody>
      </table>
      <table>
        <caption>Microdatos ECV {micro.year}: hogares que alquilan a precio de mercado y hogares en casa pagada, por comunidad (todas las edades)</caption>
        <thead>
          <tr>
            <th scope="col">Comunidad</th>
            <th scope="col">Alquiler de mercado: hogares en la muestra</th>
            <th scope="col">Peso mediano</th>
            <th scope="col">Por encima del 40 %</th>
            <th scope="col">Renta mediana por unidad de consumo</th>
            <th scope="col">Casa pagada: hogares en la muestra</th>
            <th scope="col">Peso mediano</th>
            <th scope="col">Por encima del 40 %</th>
          </tr>
        </thead>
        <tbody>
          {regions.map((g) => {
            const r = get(g, "TOTAL", "RENT_MKT");
            const o = get(g, "TOTAL", "OWN_NL");
            return (
              <tr key={g}>
                <td>{geoName(g)}</td>
                <td>{r?.n ?? 0}</td>
                <td>{cellText(r, "burden_median", 1)}</td>
                <td>{cellText(r, "overburden_pct", 1)}</td>
                <td>{cellText(r, "income_cu_median", 0, true)}</td>
                <td>{o?.n ?? 0}</td>
                <td>{cellText(o, "burden_median", 1)}</td>
                <td>{cellText(o, "overburden_pct", 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <table>
        <caption>Microdatos ECV, año a año: hogares por encima del 40 % (intervalo del 95 %)</caption>
        <thead>
          <tr>
            <th scope="col">Territorio</th>
            <th scope="col">Edad</th>
            <th scope="col">Tenencia</th>
            {micro.years.map((y) => (
              <th scope="col" key={y}>
                {y}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {terr.flatMap((g) =>
            MICRO_AGES.flatMap((age) =>
              ["OWN_NL", "RENT_MKT", "TOTAL"].map((tk) => (
                <tr key={`${g}${age}${tk}`}>
                  <td>{geoName(g)}</td>
                  <td>{ageLabel(age)}</td>
                  <td>{TEN_LABEL[tk]}</td>
                  {micro.years.map((y) => {
                    const c = y === micro.year ? get(g, age, tk) : trendGet(y, g, age, tk);
                    return <td key={y}>{c ? `${cellText(c, "overburden_pct", 0)} · n ${c.n}` : "—"}</td>;
                  })}
                </tr>
              )),
            ),
          )}
        </tbody>
      </table>
    </>
  );
}
