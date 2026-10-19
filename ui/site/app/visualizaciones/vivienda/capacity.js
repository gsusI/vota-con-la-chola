import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { Explain } from "./explain";
import { Bars, C, NAMES, at, num, thousands } from "./common";

const ORDER = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"];
const last = (rows) => rows[rows.length - 1];
const common = (...lists) => Math.max(...lists.map((rows) => rows[0]?.year ?? 0)) <= Math.min(...lists.map((rows) => last(rows)?.year ?? 0)) && Math.min(...lists.map((rows) => last(rows).year));

export function CapacityFigure({ capacity, homeM2, source }) {
  const c = capacity;
  const series = [
    { id: "gross", label: "Salario bruto medio (INE, ETCL)", shortLabel: "Bruto medio", color: C.blue, points: c.years_gross_avg },
    { id: "net", label: "Salario neto medio (bruto menos IRPF y cotizaciones del trabajador)", shortLabel: "Neto medio", color: C.orange, points: c.years_net_avg },
    { id: "median", label: "Salario neto mediano (INE, Encuesta de Estructura Salarial)", shortLabel: "Neto mediano", color: C.aqua, emphasis: true, points: c.years_net_median },
    { id: "young", label: "Salario neto de 25 a 34 años", shortLabel: "Neto 25–34 años", color: C.yellow, points: c.years_net_young },
    { id: "median-sale", label: "Neto mediano con precio de compraventa (INE IPV)", shortLabel: "Neto mediano, compraventa", color: C.aqua, dashed: true, points: c.years_net_median_sale_price },
  ];
  const y = common(c.years_gross_avg, c.years_net_median, c.years_net_young, c.years_net_median_sale_price);
  const g = at(c.years_gross_avg, y);
  const m = at(c.years_net_median, y);
  const ms = at(c.years_net_median_sale_price, y);
  const yg = at(c.years_net_young, y);
  const rate = at(c.net_rate_avg, y);
  const rate67 = at(c.net_rate_67, y);
  const rateMed = at(c.net_rate_median, y);
  const shareYear = last(c.median_share_of_oecd_wage).year;
  const shareMed = last(c.median_share_of_oecd_wage).value;
  const wedge = at(c.tax_wedge, y);
  const effort = c.effort_pct;
  const effortPeak = effort.reduce((a, b) => (b.value > a.value ? b : a));
  return (
    <Figure
      id="capacidad"
      title={`Con el sueldo neto mediano, un piso de ${homeM2} m² cuesta ${num(m)} años (${num(ms)} con el precio de compraventa), no los ${num(g)} que salen con el salario bruto medio (${y})`}
      dek={`El mismo piso medido con lo que de verdad cobra un trabajador típico. Del salario bruto se restan el IRPF y las cotizaciones del trabajador (${num(rate)} % para el salario medio, ${num(rateMed)} % para el mediano y ${num(rate67)} % para uno del 67 % de la media; la cuña fiscal total, contando las cotizaciones de la empresa, es del ${num(wedge)} % del coste laboral). La mediana es lo que cobra el trabajador del medio, menos que la media, que suben los sueldos altos. Para quien tiene de 25 a 34 años: ${num(yg)} años.`}
      legend={series}
      sources={[
        source("ine_tempus", "INE, Encuesta de Estructura Salarial (mediana y por edad) y ETCL", "https://www.ine.es/jaxiT3/Tabla.htm?t=28191"),
        source("oecd_dbnomics", "OCDE, Taxing Wages (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
        source("mivau_boletin", "Ministerio de Vivienda, valor tasado"),
        source("bde_indicadores_vivienda", "Banco de España, esfuerzo teórico"),
      ]}
      notes={[
        `Neto = bruto × (1 − tipo medio de IRPF y cotizaciones del trabajador de la OCDE para un soltero sin hijos). La OCDE publica el tipo al 67 % y al 100 % de su salario medio: para el sueldo mediano (el ${num(shareMed * 100, 0)} % de ese salario en ${shareYear}) y el de 25 a 34 años se interpola entre ambos según lo que cobran. Es una aproximación; con hijos o en pareja el tipo es menor.`,
        "La Encuesta de Estructura Salarial es anual desde 2008 y se publica con dos años de retraso; incluye tiempo parcial. «Con precio de compraventa» encadena el IPV del INE al valor tasado de 2015.",
      ]}
      table={
        <HousingTable
          series={[
            ...series.map((s) => ({ ...s, unit: "years" })),
            { id: "pay-m", label: "Neto mediano (€/año)", points: c.pay.net_median, unit: "eur" },
            { id: "pay-y", label: "Neto 25–34 (€/año)", points: c.pay.net_young, unit: "eur" },
            { id: "effort", label: "Esfuerzo teórico (% de la renta)", points: effort, unit: "pct" },
          ]}
        />
      }
    >
      <HousingChart series={series} unit="years" xMin={2000} xMax={last(c.years_gross_avg).year} ariaLabel="Años de sueldo para un piso según bruto, neto, mediano y jóvenes" />
      <div>
        <h3 className="vizPanelTitle">
          Cuota de la hipoteca en el primer año, en % de la renta del hogar mediano
          <span>
            {num(last(effort).value)} % en {last(effort).year}; máximo {num(effortPeak.value)} % en {effortPeak.year} (Banco de España)
          </span>
        </h3>
        <HousingChart
          series={[{ id: "effort", label: "Esfuerzo teórico sin deducciones", shortLabel: String(last(effort).year), color: C.ref, points: effort }]}
          unit="pct"
          xMin={2000}
          xMax={last(effort).year}
          height={200}
          ariaLabel="Esfuerzo teórico de la hipoteca"
        />
      </div>
      <Explain
        shows="Cuántos años de sueldo cuesta el piso medio según qué sueldo se use: bruto o neto, medio o mediano, de todos o de los de 25 a 34 años. Abajo, cuánto de la renta se lleva la cuota de una hipoteca tipo."
        read="Cuanto más arriba la línea, más caro para ese trabajador. La distancia entre la azul (bruto medio) y la verde (neto mediano) es lo que se pierde al medir con el sueldo que no cobra casi nadie. El panel de abajo incluye el efecto de los tipos de interés: con tipos bajos, el mismo precio pesa menos cada mes."
        notSay="No cuenta la entrada (en torno al 20 % del precio más impuestos), que es la barrera principal para los jóvenes, ni hogares con dos sueldos."
      />
    </Figure>
  );
}

export function BurdenPeersFigure({ capacity, source }) {
  const p = capacity.peers;
  const year = Math.min(...ORDER.map((geo) => last(p.overburden_tenants[geo] || [{ year: 9999 }]).year));
  const val = (key, geo) => at(p[key][geo], year);
  const groups = [
    { key: "overburden_tenants", title: "Inquilinos a precio de mercado que gastan más del 40 % de su renta en vivienda" },
    { key: "rent_share_tenants", title: "Alquiler en % de la renta de los hogares inquilinos" },
    { key: "overburden_total", title: "Toda la población: gasta más del 40 % de su renta en vivienda" },
    { key: "overburden_young", title: "Jóvenes de 15 a 29 años: gastan más del 40 % de su renta en vivienda" },
  ];
  const residualYear = Math.min(...ORDER.map((geo) => last(capacity.residual_pps[geo] || [{ year: 9999 }]).year));
  const residual = (geo) => at(capacity.residual_pps[geo], residualYear);
  const resMax = Math.max(...ORDER.map((geo) => residual(geo) || 0));
  return (
    <Figure
      id="sobrecarga"
      title={`Frente a Europa, el inquilino español a precio de mercado está más sobrecargado: el ${num(val("overburden_tenants", "ES"))} % gasta más del 40 % de su renta en vivienda, frente al ${num(val("overburden_tenants", "EU27_2020"))} % en la UE; la tasa de toda la población (${num(val("overburden_total", "ES"))} % frente a ${num(val("overburden_total", "EU27_2020"))} %) lo esconde`}
      dek={`Capacidad de pago comparada en niveles con otros países (encuesta europea de condiciones de vida, ${year}). Casi la mitad de la población vive en una vivienda propia ya pagada y gasta poco en ella; la presión cae en los inquilinos (el desglose por tenencia y edad, en «Quién paga la vivienda»). Tras pagar la vivienda, al hogar mediano le quedan ${thousands(residual("ES"))} PPS por adulto equivalente al año, frente a ${thousands(residual("EU27_2020"))} en la UE.`}
      legendKind="bar"
      legend={[
        { id: "ES", label: "España", color: C.blue },
        { id: "EU", label: "Media UE-27", color: C.ref },
        { id: "peer", label: "Otro país", color: C.peer },
      ]}
      sources={[source("eurostat_sdmx", "Eurostat, EU-SILC: ilc_lvho07a, ilc_lvho07c, ilc_mded01, ilc_mded02, ilc_di03", "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07c/default/table")]}
      notes={[
        "Renta tras la vivienda = renta disponible equivalente mediana en PPS × (1 − peso medio de los gastos de vivienda). Combina una mediana y una media: es una aproximación para comparar países, no la renta de un hogar concreto.",
        "Los jóvenes que siguen en casa de sus padres viven en hogares con poco gasto de vivienda: por eso la sobrecarga de los jóvenes españoles parece baja. La emancipación tardía esconde el problema en esta estadística.",
      ]}
      table={
        <HousingTable
          series={[
            ...groups.flatMap((gr) => ORDER.map((geo) => ({ id: `${gr.key}-${geo}`, label: `${NAMES[geo]}: ${gr.title.toLowerCase()}`, points: p[gr.key][geo] || [], unit: "pct" }))),
            ...ORDER.map((geo) => ({ id: `res-${geo}`, label: `${NAMES[geo]}: renta tras la vivienda (PPS)`, points: capacity.residual_pps[geo] || [], unit: "count" })),
          ]}
        />
      }
    >
      <div className="vizStack">
        {groups.map((gr) => {
          const rows = ORDER.filter((geo) => val(gr.key, geo) != null).sort((a, b) => val(gr.key, b) - val(gr.key, a));
          const max = Math.max(...rows.map((geo) => val(gr.key, geo)));
          return (
            <div key={gr.key}>
              <h3>{gr.title}</h3>
              <Bars
                rows={rows.map((geo) => ({ id: `${gr.key}-${geo}`, label: NAMES[geo], value: val(gr.key, geo), color: geo === "ES" ? C.blue : geo === "EU27_2020" ? C.ref : C.peer, text: `${num(val(gr.key, geo))} %` }))}
                max={max}
                label={gr.title}
              />
            </div>
          );
        })}
        <div>
          <h3>Renta que queda tras pagar la vivienda, PPS por adulto equivalente ({residualYear})</h3>
          <Bars
            rows={ORDER.filter((geo) => residual(geo) != null)
              .sort((a, b) => residual(b) - residual(a))
              .map((geo) => ({ id: `res-${geo}`, label: NAMES[geo], value: residual(geo), color: geo === "ES" ? C.blue : geo === "EU27_2020" ? C.ref : C.peer, text: `${thousands(residual(geo))} PPS` }))}
            max={resMax}
            label="Renta tras la vivienda"
          />
        </div>
      </div>
      <Explain
        shows="Cuánto pesa la vivienda en el presupuesto de los hogares en España y en países comparables, separando inquilinos del resto, y cuánto les queda después en poder adquisitivo."
        read="Barra más larga = más gente ahogada por la vivienda (más del 40 % de su renta). El PPS corrige el euro por los precios de cada país: 1.000 PPS compran lo mismo en Madrid que en Berlín."
        notSay="No distingue ciudades ni recoge a quien no ha podido emanciparse. Una media nacional parecida a la europea es compatible con un problema grave en un grupo concreto: los inquilinos."
      />
    </Figure>
  );
}

// Second «el dato mata el relato»: taxes collected on property and its transfers against public housing spending.
export function MoneyFigure({ money, source }) {
  const rows = money.filter((row) => row.spent != null).sort((a, b) => b.collected / b.spent - a.collected / a.spent);
  const es = rows.find((row) => row.geo === "ESP");
  const oecd = money.find((row) => row.geo === "OECD");
  const max = Math.max(...money.map((row) => row.collected));
  const W = 720;
  const rowH = 46;
  const M = { left: 120, right: 150, top: 26 };
  const H = M.top + rowH * rows.length + 30;
  const sx = (v) => M.left + (v / max) * (W - M.left - M.right);
  const ticks = [];
  for (let v = 0; v <= max + 1e-9; v += 0.5) ticks.push(v);
  const de = rows.find((row) => row.geo === "DEU");
  return (
    <Figure
      id="el-dato-dinero"
      title={`España cobra en impuestos sobre inmuebles y sus compraventas el ${num(es.collected, 2)} % del PIB y gasta en vivienda el ${num(es.spent, 2)} %: ${num(es.collected / es.spent, 0)} euros recaudados por cada euro gastado${rows[0].geo === "ESP" ? ", la mayor proporción del grupo" : ""}${de ? ` (Alemania: ${num(de.collected / de.spent, 1)})` : ""}`}
      dek={`Para cada país, el punto naranja es lo que recaudan todas las administraciones por la tenencia de inmuebles (en España, el IBI: ${num(es.recurrent_property, 2)} % del PIB) y por sus transmisiones (ITP y AJD: ${num(es.transactions, 2)} %); el azul, lo que gastan en vivienda (${num(es.spent_development, 2)} % en promoción y ayudas a la construcción y ${num(es.spent_allowances, 2)} % en ayudas al alquiler en España). Mismo eje, % del PIB, ${es.year}. En 2015–2019 la proporción era parecida (${num(es.collected_2015_2019, 2)} % frente a ${num(es.spent_2015_2019, 2)} %).`}
      legend={[
        { id: "in", label: "Recaudado: impuestos sobre inmuebles y sus transmisiones", color: C.orange },
        { id: "out", label: "Gastado: vivienda (promoción y ayudas)", color: C.blue },
      ]}
      sources={[
        source("oecd_dbnomics", "OCDE, Revenue Statistics 4100 y 4400 (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_REV_COMP_OECD@DF_RSOECD"),
        source("eurostat_sdmx", "Eurostat, COFOG GF0601 + GF1006", "https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table"),
      ]}
      notes={[
        "La recaudación no está afectada a la vivienda: el IBI financia a los ayuntamientos y el ITP y el AJD a las comunidades, que lo gastan en lo que deciden. El 4100 grava también locales, oficinas y suelo, no solo viviendas. No se incluye el IVA de la vivienda nueva (la estadística oficial no lo separa del resto del IVA) ni la plusvalía municipal, que la OCDE no publica aparte: con ellos, lo recaudado sería mayor.",
        `El gasto no incluye beneficios fiscales (la deducción por vivienda del IRPF). Media OCDE de recaudación: ${oecd ? `${num(oecd.collected, 2)} % del PIB en ${oecd.year}` : "sin dato"}; la OCDE no publica el gasto comparable.`,
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">País</th>
                  <th scope="col">Año</th>
                  <th scope="col">Tenencia (4100)</th>
                  <th scope="col">Transmisiones (4400)</th>
                  <th scope="col">Recaudado</th>
                  <th scope="col">Gastado: promoción</th>
                  <th scope="col">Gastado: ayudas al alquiler</th>
                  <th scope="col">Gastado</th>
                  <th scope="col">Recaudado / gastado</th>
                </tr>
              </thead>
              <tbody>
                {money.map((row) => (
                  <tr key={row.geo}>
                    <td>{NAMES[row.geo] || row.geo}</td>
                    <td>{row.year}</td>
                    <td>{num(row.recurrent_property, 2)} %</td>
                    <td>{num(row.transactions, 2)} %</td>
                    <td>{num(row.collected, 2)} %</td>
                    <td>{row.spent_development != null ? `${num(row.spent_development, 2)} %` : "—"}</td>
                    <td>{row.spent_allowances != null ? `${num(row.spent_allowances, 2)} %` : "—"}</td>
                    <td>{row.spent != null ? `${num(row.spent, 2)} %` : "—"}</td>
                    <td>{row.spent ? num(row.collected / row.spent, 1) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <div className="hvScatter">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Recaudación sobre inmuebles frente a gasto público en vivienda por país" style={{ display: "block", maxWidth: "100%", height: "auto" }}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={sx(v)} x2={sx(v)} y1={M.top - 6} y2={H - 26} className={v === 0 ? "tsChart__baseline" : "tsChart__grid"} />
              <text x={sx(v)} y={H - 8} textAnchor="middle" className="tsChart__tick">
                {num(v, 1)} %
              </text>
            </g>
          ))}
          {rows.map((row, i) => {
            const y = M.top + i * rowH + rowH / 2;
            const isEs = row.geo === "ESP";
            return (
              <g key={row.geo}>
                <text x={M.left - 10} y={y + 4} textAnchor="end" className="tsChart__tick" style={{ fontWeight: isEs ? 700 : 400 }}>
                  {NAMES[row.geo]}
                </text>
                <line x1={sx(row.spent)} x2={sx(row.collected)} y1={y} y2={y} stroke={isEs ? C.ref : C.peer} strokeWidth={isEs ? 3 : 2} />
                <circle cx={sx(row.spent)} cy={y} r={7} fill={C.blue}>
                  <title>{`${NAMES[row.geo]}: gasta ${num(row.spent, 2)} % del PIB en vivienda`}</title>
                </circle>
                <circle cx={sx(row.collected)} cy={y} r={7} fill={C.orange}>
                  <title>{`${NAMES[row.geo]}: recauda ${num(row.collected, 2)} % del PIB en impuestos sobre inmuebles y transmisiones`}</title>
                </circle>
                <text x={sx(Math.max(row.collected, row.spent)) + 12} y={y + 4} className="tsChart__endLabel">
                  {num(row.collected / row.spent, 1)} € por € gastado
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <Explain
        shows="Lo que entra (impuestos sobre la propiedad inmobiliaria y sus compraventas) frente a lo que sale (gasto público en vivienda), en España y en países comparables, en la misma escala."
        read="Cuanto más larga la línea gris, más se recauda sobre la vivienda y los inmuebles en relación con lo que se gasta en ella. Compara la longitud de la línea de España con la de los demás: recauda menos que Francia o Italia, más que Alemania o Portugal, y gasta menos que todos."
        notSay="No dice que la recaudación «debería» ir a vivienda (los impuestos no están afectados) ni que gastar más bajara los precios. Deja fuera el IVA de la vivienda nueva y la plusvalía municipal, que aumentarían la recaudación española."
      />
    </Figure>
  );
}
