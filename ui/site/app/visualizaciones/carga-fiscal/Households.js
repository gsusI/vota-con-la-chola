import Figure from "../components/Figure";
import "./consolidated.css";

// «Cinco hogares»: the shared typical cases (docs/etl/sprints/VIZ-SEGMENTOS-20261019/README.md §3), each as a cascade
// gross -> direct taxes -> housing -> what is left (household euros), and what is left per consumption unit against the
// median household. One euro axis from zero for both panels. Illustrative: computed, not observed households.
const TAX = "#eb6834";
const HOUSING = "#eda100";
const LEFT = "#1baf7a";
const nf = (v, digits = 0) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const listJoin = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} y ${items.at(-1)}` : items[0] || "");
const OECD_LABELS = { ESP: "España", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal" };

const CASES = {
  p1_young_renter_madrid: {
    who: "Persona 1 · 25 a 34 años, asalariada, vive sola de alquiler en la ciudad de Madrid",
    how: (c) =>
      `Salario bruto medio de los 25 a 34 años (Encuesta de Estructura Salarial) × ${nf(c.madrid_wage_factor, 2)}, el nivel salarial de la Comunidad de Madrid (como en vivienda). Alquiler: mediana SERPAVI de la ciudad de Madrid, ${nf(c.rent_month)} € al mes (${c.rent_year}), sin suministros.`,
  },
  p2_family_renter_metro: {
    who: "Persona 2 · pareja de 30 a 44 años con dos hijos, alquila en el área de Madrid",
    how: (c) =>
      `Hogar tipo de la OCDE: un sueldo del 100 % y otro del 67 % del salario medio de España, dos hijos. Alquiler: mediana SERPAVI del resto de la provincia de Madrid, ${nf(c.rent_month)} € al mes (${c.rent_year}).`,
  },
  c_single_parent_renter: {
    who: "Madre o padre solo de 30 a 44 años con dos hijos, de alquiler",
    how: (c) =>
      `Hogar tipo de la OCDE: un sueldo del 67 % del salario medio, dos hijos; las prestaciones por hijo ya están descontadas de sus impuestos. Vivienda: gastos medios de los hogares monoparentales que alquilan (EU-SILC), ${nf(c.cost_month)} € al mes con suministros.`,
  },
  p4_retired_owner_interior: {
    who: "Persona 4 · pensionista de 65 años o más, vive sola en casa pagada, en una provincia del interior",
    how: (c) =>
      `Pensión: gasto en pensiones de vejez y supervivencia por pensionista (${c.pension_year}), media nacional. IRPF estimado con la escala del asalariado soltero a ese nivel menos su cotización (las pensiones no cotizan). Vivienda: gastos de los propietarios de 65 o más que viven solos (EU-SILC), ${nf(c.cost_month)} € al mes.`,
  },
  p5_professional_madrid: {
    who: "Persona 5 · profesional de 45 a 54 años, sin hijos, propietario, en Madrid",
    how: (c) =>
      `Hogar tipo de la OCDE: soltero con el 167 % del salario medio de España. Vivienda: gastos de los propietarios de menos de 65 que viven solos, con y sin hipoteca (EU-SILC), ${nf(c.cost_month)} € al mes; con una hipoteca reciente serían bastante más.`,
  },
};

function ticks(max, step) {
  const out = [];
  for (let t = 0; t <= max + 1e-9; t += step) out.push(t);
  return out;
}

export default function HouseholdsFigure({ segments, sources }) {
  const data = segments?.cases;
  if (!data?.rows?.length) return null;
  const rows = data.rows.filter((row) => CASES[row.key]);
  const nat = data.national;
  const max = Math.ceil(Math.max(...rows.map((row) => row.gross)) / 10000) * 10000;
  const x = (v) => `${(v / max) * 100}%`;
  const axis = ticks(max, 10000);
  const byKey = Object.fromEntries(rows.map((row) => [row.key, row]));
  const p1 = byKey.p1_young_renter_madrid;
  const p4 = byKey.p4_retired_owner_interior;
  const lone = byKey.c_single_parent_renter;
  const relief = data.family_relief || [];
  const es = relief.find((row) => row.area === "ESP");
  const peers = relief.filter((row) => row.area !== "ESP");
  const loneBelow = peers.filter((row) => row.single_parent_aw67_net_rate < 0);
  const q = data.vat_by_quintile || {};
  const below = rows.filter((row) => row.left_per_uc < nat.after_housing_per_uc);

  return (
    <Figure
      id="cinco-hogares"
      title={`La joven que alquila en Madrid gana un ${nf((p1.gross / p4.gross - 1) * 100)} % más que el pensionista con la casa pagada, pero tras impuestos y alquiler le quedan ${nf(p1.left_per_uc)} € al año frente a ${nf(p4.left_per_uc)} €; la madre sola con dos hijos se queda en ${nf(lone.left_per_uc)} € por unidad de consumo, el ${nf(lone.vs_median_pct)} % del hogar mediano`}
      dek={`Cinco hogares tipo, los mismos en todas las visualizaciones: cuánto ganan, cuánto pagan en impuestos directos, cuánto se lleva la vivienda y cuánto les queda. A la izquierda, en euros del hogar al año; a la derecha, lo que queda dividido por sus unidades de consumo, frente al hogar mediano. Mismo eje en euros en los dos paneles. Son cálculos ilustrativos con tipos oficiales, no hogares observados.`}
      sources={sources}
      notes={[
        `Impuestos directos = IRPF + cotización del trabajador − prestaciones en efectivo, con el tipo medio neto de la OCDE (Taxing Wages ${data.year}) para cada hogar tipo; para la persona 1, interpolado entre el 67 % y el 100 % del salario medio (${nf(data.average_wage)} € en ${data.year}). La OCDE usa una sola escala autonómica de referencia: no se ve la diferencia entre comunidades ni el régimen foral.`,
        `Lo que queda = salario neto − vivienda; por unidad de consumo, con la escala de la OCDE modificada (1 el primer adulto, 0,5 los demás, 0,3 cada menor de 14). Hogar mediano: renta mediana por unidad de consumo (${nf(nat.income_per_uc)} €, encuesta de ${nat.survey_year}) menos el peso mediano de la vivienda (${nf(nat.median_housing_share_pct, 1)} %); es una aproximación, porque las dos medianas no son del mismo hogar.`,
        `IVA (marca negra): la parte de lo que queda que se iría en IVA si lo gastan, con la mediana del IVA pagado en % de la renta bruta de su tipo de hogar (Eurostat, estadística experimental, ${data.vat_year}). Dentro de cada tipo baja con la renta: del ${nf(q.QU1, 1)} % de la renta en el quintil más pobre al ${nf(q.QU5, 1)} % en el más rico.`,
        `Años mezclados: salarios, tipos y alquileres de ${data.year}; gastos de vivienda de la encuesta de ${rows.find((row) => row.cost_year)?.cost_year} (pasados a euros con la paridad de ${data.ppp_year}, ${nf(data.eur_per_pps, 3)} € por PPS); IVA de ${data.vat_year}. La cotización de la empresa (en la tabla) no sale del salario, pero también la paga el trabajo.`,
        `El ejemplo habitual, el soltero sin hijos con el salario medio de la OCDE (cuña del ${nf(data.single_aw100_wedge, 1)} % del coste laboral en ${data.year}), describe a poca gente: ese salario medio (${nf(data.average_wage)} €) está un ${nf((data.average_wage / data.median_wage - 1) * 100)} % por encima del salario mediano (${nf(data.median_wage)} €, Encuesta de Estructura Salarial), y la mayoría no vive sola sin hijos.`,
        "Faltan: los servicios que cada hogar recibe en especie (sanidad, educación de los hijos), el IBI y otros impuestos locales fuera de los gastos de vivienda, y las diferencias de precios entre comunidades más allá del alquiler (no hay paridades regionales oficiales).",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver el cálculo de cada hogar</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Hogar</th>
                  <th scope="col">Bruto</th>
                  <th scope="col">Impuestos directos</th>
                  <th scope="col">Cotización de la empresa</th>
                  <th scope="col">Neto</th>
                  <th scope="col">Vivienda</th>
                  <th scope="col">Queda</th>
                  <th scope="col">Unidades de consumo</th>
                  <th scope="col">Queda por unidad</th>
                  <th scope="col">IVA estimado</th>
                  <th scope="col">Supuestos</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{CASES[row.key].who}</th>
                    <td>{nf(row.gross)} €</td>
                    <td>
                      {nf(row.direct_taxes)} € ({nf(row.direct_rate_pct, 1)} %)
                    </td>
                    <td>{row.employer_ssc != null ? `${nf(row.employer_ssc)} €` : "—"}</td>
                    <td>{nf(row.net)} €</td>
                    <td>
                      {nf(row.housing)} € ({nf(row.housing_share_pct, 1)} % del neto)
                    </td>
                    <td>{nf(row.left)} €</td>
                    <td>{nf(row.uc, 1)}</td>
                    <td>{nf(row.left_per_uc)} €</td>
                    <td>
                      {nf(row.vat)} € ({nf(row.vat_share_pct, 1)} %)
                    </td>
                    <td>{CASES[row.key].how(row)}</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">Hogar mediano (aproximación)</th>
                  <td colSpan={7}>—</td>
                  <td>{nf(nat.after_housing_per_uc)} €</td>
                  <td colSpan={2}>Renta mediana por unidad de consumo menos el peso mediano de la vivienda.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <ul className="vizLegend" aria-label="Leyenda de los cinco hogares">
        <li>
          <span className="vizLegend__key" style={{ background: TAX }} aria-hidden="true" /> Impuestos directos
        </li>
        <li>
          <span className="vizLegend__key" style={{ background: HOUSING }} aria-hidden="true" /> Vivienda
        </li>
        <li>
          <span className="vizLegend__key" style={{ background: LEFT }} aria-hidden="true" /> Lo que queda
        </li>
        <li>
          <span className="hh__vatKey" aria-hidden="true" /> IVA si lo gastan (estimado)
        </li>
        <li>
          <span className="hh__refKey" aria-hidden="true" /> Hogar mediano tras la vivienda
        </li>
      </ul>
      <div className="sq hh" role="table" aria-label="Cinco hogares tipo: impuestos, vivienda y lo que queda">
        <div className="sq__row sq__head" role="row">
          <span role="columnheader">Hogar</span>
          <span role="columnheader">
            Renta bruta del hogar y adónde va <em>(euros al año)</em>
          </span>
          <span role="columnheader">
            Lo que queda por unidad de consumo <em>(euros al año)</em>
          </span>
        </div>
        {rows.map((row) => (
          <div className="sq__row hh__row" role="row" key={row.key}>
            <span className="sq__label hh__label" role="rowheader">
              {CASES[row.key].who}
            </span>
            <div className="sq__panel" role="cell">
              <div className="sq__track">
                {axis.map((t) => (
                  <span className="sq__tick" key={t} style={{ left: x(t) }} aria-hidden="true" />
                ))}
                <span className="hh__seg" style={{ left: 0, width: x(row.direct_taxes), background: TAX }} />
                <span className="hh__seg" style={{ left: x(row.direct_taxes), width: x(row.housing), background: HOUSING }} />
                <span className="hh__seg" style={{ left: x(row.direct_taxes + row.housing), width: x(Math.max(0, row.left)), background: LEFT }} />
                <span className="hh__vat" style={{ left: x(row.direct_taxes + row.housing + row.vat) }} aria-hidden="true" />
              </div>
              <span className="sq__values">
                bruto {nf(row.gross)} · impuestos {nf(row.direct_taxes)} · vivienda {nf(row.housing)} · queda {nf(row.left)}
              </span>
            </div>
            <div className="sq__panel" role="cell">
              <div className="sq__track">
                {axis.map((t) => (
                  <span className="sq__tick" key={t} style={{ left: x(t) }} aria-hidden="true" />
                ))}
                <span className="hh__seg" style={{ left: 0, width: x(Math.max(0, row.left_per_uc)), background: LEFT }} />
                <span className="hh__ref" style={{ left: x(nat.after_housing_per_uc) }} aria-hidden="true" />
              </div>
              <span className="sq__values">
                <strong>{nf(row.left_per_uc)} €</strong> · {nf(row.vs_median_pct)} % del hogar mediano
              </span>
            </div>
          </div>
        ))}
        <div className="sq__row sq__axis" aria-hidden="true">
          <span />
          {[0, 1].map((panel) => (
            <div className="sq__track sq__track--axis" key={panel}>
              {axis
                .filter((t) => t % 20000 === 0)
                .map((t) => (
                  <span className="sq__tickLabel" key={t} style={{ left: x(t) }}>
                    {t ? `${nf(t / 1000)} mil` : "0"}
                  </span>
                ))}
            </div>
          ))}
        </div>
      </div>
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«Los pensionistas viven mejor que los jóvenes»</strong>
          Tras pagar la vivienda, sí: con menos renta bruta ({nf(p4.gross)} € de pensión frente a {nf(p1.gross)} € de salario), al pensionista con la casa
          pagada le quedan {nf(p4.left_per_uc)} € y a la joven que alquila en Madrid, {nf(p1.left_per_uc)} €. Paga menos impuestos ({nf(p4.direct_taxes)} €
          frente a {nf(p1.direct_taxes)} €, porque la pensión no cotiza) y casi nada de vivienda. Antes de la vivienda, no tanto: la renta disponible
          apenas cambia con la edad (<a href="#bolsillo">figura anterior</a>). Lo que los separa es la vivienda: el alquiler se lleva el {nf(p1.housing_share_pct)} %
          de su neto; al pensionista, el {nf(p4.housing_share_pct)} %.
        </li>
        {es ? (
          <li>
            <strong>«En España se pagan pocos impuestos»</strong>
            Depende del hogar. El soltero con el salario medio paga menos que en los países vecinos (cuña del {nf(es.single_aw100_wedge, 1)} % frente al{" "}
            {peers.map((row) => `${nf(row.single_aw100_wedge, 1)} % de ${OECD_LABELS[row.area]}`).join(", ")}). Pero tener hijos alivia poco: una pareja con dos
            hijos y un solo sueldo paga {nf(es.relief_pts, 1)} puntos menos que el soltero, frente a{" "}
            {peers.map((row) => `${nf(row.relief_pts, 1)} en ${OECD_LABELS[row.area]}`).join(", ")}. Y una madre sola con dos hijos y el 67 % del salario medio paga
            en neto el {nf(es.single_parent_aw67_net_rate, 1)} % de su sueldo
            {loneBelow.length ? `, cuando en ${listJoin(loneBelow.map((row) => OECD_LABELS[row.area]))} recibe más de lo que paga` : ""} (OCDE, {data.year}).
          </li>
        ) : null}
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          {below.length} de los {rows.length} hogares quedan por debajo del mediano tras la vivienda, pero son casos tipo, no un reparto: cuántos hogares se parecen a
          cada uno lo da la encuesta (en <a href="/visualizaciones/vivienda/">vivienda</a>, la tenencia por edad). Tampoco recoge lo que reciben en especie ni el
          patrimonio: el pensionista propietario tiene además una casa que el joven no tiene.
        </li>
      </ul>
    </Figure>
  );
}
