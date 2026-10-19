import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { Explain } from "./explain";
import { Bars, C, NAMES, PEER_LEGEND, PeerPanels, joinEs, num, thousands } from "./common";

const last = (rows) => rows[rows.length - 1];
const ORDER = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"];

export function CohortFigure({ composition, source }) {
  const es = composition.cohort_25_39.ES;
  const peak = es.persons.reduce((a, b) => (b.value > a.value ? b : a));
  const now = last(es.persons);
  const shares = Object.fromEntries(Object.entries(composition.cohort_25_39).map(([geo, block]) => [geo, block.share_pct.filter((p) => p.year >= 1990)]));
  const shareMax = Math.max(...Object.values(shares).flatMap((rows) => rows.map((p) => p.value)));
  const dec = composition.decomposition;
  const share = (d) => (d.population_effect / d.total) * 100;
  const max = Math.max(...dec.map((d) => Math.max(d.population_effect, d.size_effect)));
  return (
    <Figure
      id="cohorte"
      title={`La generación que forma hogares (25 a 39 años) pasó de ${num(peak.value / 1e6, 1)} millones en ${peak.year} a ${num(now.value / 1e6, 1)} en ${now.year}: el eco del baby boom ya no empuja la demanda; los hogares nuevos de ${dec[dec.length - 1].from}–${dec[dec.length - 1].to} salen en un ${num(share(dec[dec.length - 1]), 0)} % del aumento de población`}
      dek={`Los nacidos en el baby boom español (hasta mediados de los setenta) llenaron la franja de 25 a 39 años en los 2000, justo en la burbuja; desde ${peak.year} esa franja se encoge. Aun así se siguen formando hogares por dos vías que se separan abajo, en cuatro tramos: más población (sobre todo inmigración) o menos personas por hogar.`}
      legend={PEER_LEGEND}
      sources={[
        source("eurostat_sdmx", "Eurostat, demo_pjangroup (población por edad)", "https://ec.europa.eu/eurostat/databrowser/view/demo_pjangroup/default/table"),
        source("bde_indicadores_vivienda", "INE, hogares de la EPA (vía Banco de España)"),
      ]}
      notes={["La descomposición usa la población media de cada año y los hogares de la EPA; el reparto entre «más población» y «hogares más pequeños» depende del año inicial del tramo, por eso se dan cuatro tramos y no uno."]}
      table={
        <HousingTable
          series={[
            { id: "persons", label: "España, personas de 25 a 39 años", points: es.persons, unit: "count" },
            ...ORDER.map((geo) => ({ id: `s-${geo}`, label: `${NAMES[geo]}: 25–39 años en % de la población`, points: shares[geo] || [], unit: "pct" })),
          ]}
        />
      }
    >
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            España: personas de 25 a 39 años
            <span>
              máximo de {num(peak.value / 1e6, 1)} millones en {peak.year}; {num(now.value / 1e6, 1)} en {now.year}
            </span>
          </h3>
          <HousingChart series={[{ id: "cohort", label: "Personas de 25 a 39 años", shortLabel: String(now.year), color: C.blue, emphasis: true, points: es.persons.filter((p) => p.year >= 1980) }]} unit="count" xMin={1980} xMax={now.year} height={220} ariaLabel="Personas de 25 a 39 años en España" />
        </div>
      </div>
      <PeerPanels data={shares} spain="ES" peers={["EU27_2020", "DE", "FR", "IT", "PT"]} unit="pct" xMin={1990} xMax={now.year} yMax={shareMax} panelNote={(rows) => `${num(last(rows).value)} % en ${last(rows).year}`} />
      <div className="vizStack">
        {dec.map((d) => (
          <div key={d.from}>
            <h3>
              {d.from}–{d.to}: {thousands(d.total)} hogares nuevos ({thousands(d.per_year)} al año)
            </h3>
            <Bars
              rows={[
                { id: `${d.from}-pop`, label: "Por más población", value: d.population_effect, color: C.blue, text: `${thousands(d.population_effect)} (${num(share(d), 0)} %)` },
                { id: `${d.from}-size`, label: "Por hogares más pequeños", value: d.size_effect, color: C.aqua, text: `${thousands(d.size_effect)} (${num(100 - share(d), 0)} %)` },
              ]}
              max={max}
              label={`Hogares nuevos ${d.from}–${d.to}`}
            />
          </div>
        ))}
      </div>
      <Explain
        shows="Cuánta gente tiene la edad a la que se forman los hogares y, en cada tramo, cuántos hogares nuevos se deben a que hay más habitantes o a que viven menos personas en cada uno."
        read="Arriba, la línea azul es el tamaño de la generación de 25 a 39 años. En los paneles, su peso en la población frente a otros países. Abajo, cada tramo reparte sus hogares nuevos: barra azul, más población; verde, hogares más pequeños."
        notSay="No separa a los inmigrantes por edad ni dice cuántos hogares se habrían formado con vivienda más barata: la demanda observada ya está limitada por los precios."
      />
    </Figure>
  );
}

export function DistributionFigure({ distribution, source }) {
  const q = distribution.overburden_quintile;
  const year = q.QU1.ES.year;
  const qs = ["QU1", "QU2", "QU3", "QU4", "QU5"];
  const qLabel = { QU1: "20 % con menos renta", QU2: "Segundo quintil", QU3: "Tercer quintil", QU4: "Cuarto quintil", QU5: "20 % con más renta" };
  const ages = [
    ["Y_LT18", "Menores de 18"],
    ["Y15-29", "15 a 29 años"],
    ["Y18-64", "18 a 64 años"],
    ["Y_GE65", "65 y más"],
  ];
  const a = distribution.overburden_age;
  const tp = distribution.tenure_poverty;
  const max = Math.max(...qs.flatMap((k) => [q[k].ES?.value || 0, q[k].EU27_2020?.value || 0]));
  const maxAge = Math.max(...ages.flatMap(([k]) => [a[k].ES?.value || 0, a[k].EU27_2020?.value || 0]));
  const bar = (geo, value, label, id) => ({ id, label, value, color: geo === "ES" ? C.blue : C.ref, text: `${num(value)} %` });
  return (
    <Figure
      id="distribucion"
      title={`La sobrecarga se concentra abajo: el ${num(q.QU1.ES.value)} % del 20 % con menos renta gasta más del 40 % de su renta en vivienda (UE: ${num(q.QU1.EU27_2020.value)} %), frente al ${num(q.QU5.ES.value)} % del 20 % más rico; bajo el umbral de pobreza, ${num(tp["RENT_MKT|B_60"].ES.value, 0)} de cada 100 alquilan a precio de mercado (${num(tp["RENT_MKT|A_60"].ES.value, 0)} por encima)`}
      dek={`Sobrecarga por gastos de vivienda (más del 40 % de la renta disponible) por quintil de renta y por edad, España frente a la media de la UE, ${year}. En España la carga media es moderada porque muchos hogares son propietarios ya pagados; quien no lo es —la población bajo el umbral de pobreza alquila a precio de mercado ${num(tp["RENT_MKT|B_60"].ES.value / tp["RENT_MKT|A_60"].ES.value, 1)} veces más que el resto— soporta casi toda la presión. Los niños viven más en hogares sobrecargados que en la UE (${num(a.Y_LT18.ES.value)} % frente a ${num(a.Y_LT18.EU27_2020.value)} %); los mayores, mucho menos.`}
      legendKind="bar"
      legend={[
        { id: "ES", label: "España", color: C.blue },
        { id: "EU", label: "Media UE-27", color: C.ref },
      ]}
      sources={[source("eurostat_sdmx", "Eurostat, EU-SILC: ilc_lvho07b (quintil), ilc_lvho07a (edad), ilc_lvho02 (tenencia por umbral de pobreza)", "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07b/default/table")]}
      notes={["Umbral de pobreza: 60 % de la renta mediana equivalente del país. La sobrecarga de los jóvenes es baja en España porque muchos siguen en casa de sus padres: el problema no aparece en esta estadística, sino en la edad de emancipación."]}
      table={
        <HousingTable
          series={[
            ...qs.map((k) => ({ id: k, label: `España, ${qLabel[k]}`, points: distribution.overburden_quintile_es_series[k] || [], unit: "pct" })),
            { id: "rb", label: "España, bajo el umbral de pobreza: alquiler a precio de mercado", points: distribution.rent_mkt_below_poverty_es, unit: "pct" },
            { id: "ra", label: "España, sobre el umbral: alquiler a precio de mercado", points: distribution.rent_mkt_above_poverty_es, unit: "pct" },
          ]}
        />
      }
    >
      <div className="vizStack">
        <div>
          <h3>Por quintil de renta: población que gasta más del 40 % de su renta en vivienda</h3>
          <Bars rows={qs.flatMap((k) => [bar("ES", q[k].ES.value, qLabel[k], `${k}-es`), bar("EU", q[k].EU27_2020.value, "", `${k}-eu`)])} max={max} label="Sobrecarga por quintil" />
        </div>
        <div>
          <h3>Por edad</h3>
          <Bars rows={ages.flatMap(([k, label]) => [bar("ES", a[k].ES.value, label, `${k}-es`), bar("EU", a[k].EU27_2020.value, "", `${k}-eu`)])} max={maxAge} label="Sobrecarga por edad" />
        </div>
        <div>
          <h3>Tenencia según la renta: población que alquila a precio de mercado y que es propietaria</h3>
          <Bars
            rows={[
              bar("ES", tp["RENT_MKT|B_60"].ES.value, "Alquila, bajo el umbral de pobreza", "rb-es"),
              bar("EU", tp["RENT_MKT|B_60"].EU27_2020.value, "", "rb-eu"),
              bar("ES", tp["RENT_MKT|A_60"].ES.value, "Alquila, por encima del umbral", "ra-es"),
              bar("EU", tp["RENT_MKT|A_60"].EU27_2020.value, "", "ra-eu"),
              bar("ES", tp["OWN|B_60"].ES.value, "Propietaria, bajo el umbral", "ob-es"),
              bar("EU", tp["OWN|B_60"].EU27_2020.value, "", "ob-eu"),
              bar("ES", tp["OWN|A_60"].ES.value, "Propietaria, por encima", "oa-es"),
              bar("EU", tp["OWN|A_60"].EU27_2020.value, "", "oa-eu"),
            ]}
            max={100}
            label="Tenencia según renta"
          />
        </div>
      </div>
      <Explain
        shows="Quién soporta el coste de la vivienda: por nivel de renta, por edad y según si se alquila o se es propietario."
        read="Cada pareja de barras compara España (azul) con la media de la UE (gris). Una barra azul más larga indica que en España ese grupo está peor que en la media europea."
        notSay="No mide a quien no ha podido formar su propio hogar ni distingue ciudades; la renta es la de un año, no la del ciclo vital."
      />
    </Figure>
  );
}

const CITY_NAMES = { "28079": "Madrid", "08019": "Barcelona", "07040": "Palma", "46250": "València", "41091": "Sevilla", "29067": "Málaga", "50297": "Zaragoza", "48020": "Bilbao" };
const PROVINCE_OF = { "28079": "Madrid", "08019": "Barcelona", "07040": "Illes Balears", "46250": "Valencia", "41091": "Sevilla", "29067": "Málaga", "50297": "Zaragoza", "48020": "Bizkaia" };

// Rent against the pay of the people who rent: the median declared rent over the net pay of 25-34 year-olds (scaled to
// each region's wage level), in each big city against the rest of its province and in each region. The old ratio to the
// mean income of all households stays in the table: owners earn more than tenants, so it understated the burden.
export function TenantRegionFigure({ territory, segments, source }) {
  const cities = (segments?.cities || []).filter((c) => c.burden_young_pct != null).sort((a, b) => b.burden_young_pct - a.burden_young_pct);
  const regions = segments?.regions || [];
  if (!cities.length || !regions.length) return null;
  const old = Object.fromEntries(territory.rows.map((row) => [row.code, row]));
  const madrid = cities.find((c) => c.code === "28079");
  const year = cities[0].year;
  const max = Math.max(...cities.map((c) => c.burden_young_pct), ...regions.map((row) => row.burden_young_pct));
  const scale = (v) => (v / max) * 82;
  const top = regions[0];
  const bottom = regions[regions.length - 1];
  const youngEs = segments.young_net_es;
  const cityGap = cities.map((c) => c.burden_young_pct - (c.rest_burden_young_pct ?? c.burden_young_pct));
  return (
    <Figure
      id="alquiler-regiones"
      title={`Un piso alquilado en la ciudad de Madrid (${thousands(madrid.rent_month)} € al mes, mediana declarada) se lleva el ${num(madrid.burden_young_pct, 0)} % del sueldo neto de quien tiene de 25 a 34 años, y el ${num(madrid.rest_burden_young_pct, 0)} % en el resto de la provincia; por comunidades, del ${num(top.burden_young_pct, 0)} % en ${top.name} al ${num(bottom.burden_young_pct, 0)} % en ${bottom.name} (${year})`}
      dek={`Alquiler mensual mediano de los pisos alquilados como vivienda habitual (declarado en el IRPF) × 12, dividido por el sueldo neto medio de las personas de 25 a 34 años, que es quien más alquila: en España, ${thousands(youngEs.value)} € al año (${youngEs.year}), ajustado al nivel salarial de cada comunidad. Arriba, cada gran ciudad frente al resto de su provincia: la capital es entre ${num(Math.min(...cityGap), 0)} y ${num(Math.max(...cityGap), 0)} puntos más cara. Abajo, las comunidades: los inquilinos de mercado son más del 20 % de los hogares en ${joinEs(territory.rows.filter((row) => row.renters_pct > 20).map((row) => row.name))}, frente al ${num(territory.renters_es_pct)} % en España.`}
      legendKind="bar"
      legend={[
        { id: "city", label: "La ciudad", color: C.orange },
        { id: "rest", label: "Resto de su provincia (círculo hueco)", color: "#f6d3c2" },
      ]}
      sources={[
        source("mivau_boletin", "Ministerio de Vivienda, Sistema Estatal de Referencia del Precio del Alquiler (SERPAVI 2011–2024), hojas de comunidades y municipios", "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi"),
        source("ine_tempus", "INE, Encuesta de Estructura Salarial (salario por edad), Encuesta Trimestral de Coste Laboral (salario por comunidad) y Encuesta de Condiciones de Vida (renta y tenencia por comunidad)", "https://www.ine.es/jaxiT3/Tabla.htm?t=28201"),
        source("oecd_dbnomics", "OCDE, Taxing Wages (paso de bruto a neto)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
      ]}
      notes={[
        "Sueldo neto: salario bruto medio de 25 a 34 años (INE, EES) menos el IRPF y las cotizaciones de un soltero que gana el 67 % del salario medio (OCDE), multiplicado por el cociente entre el salario de la comunidad y el de España (ETCL). No hay salario oficial por edad y comunidad: es el corte por edad ajustado por el de territorio, una aproximación.",
        "Resto de la provincia: media de las medianas de sus municipios ponderada por el número de pisos alquilados (la mediana del conjunto no se puede rehacer con medianas municipales). El SERPAVI recoge todos los contratos vigentes, no solo los nuevos: quien firma hoy paga más. País Vasco y Navarra tienen su propia Hacienda y entran con menos años (Bilbao, solo 2024).",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Ciudad</th>
                  <th scope="col">Alquiler mediano (€/mes)</th>
                  <th scope="col">Resto de la provincia (€/mes)</th>
                  <th scope="col">Sueldo neto de 25–34 (€/año)</th>
                  <th scope="col">Ciudad: % del sueldo</th>
                  <th scope="col">Resto: % del sueldo</th>
                  <th scope="col">Alquiler en 2019 (€/mes)</th>
                </tr>
              </thead>
              <tbody>
                {cities.map((c) => (
                  <tr key={c.code}>
                    <td>{CITY_NAMES[c.code]}</td>
                    <td>{thousands(c.rent_month)} €</td>
                    <td>{c.rest_rent_month != null ? `${thousands(c.rest_rent_month)} €` : "—"}</td>
                    <td>{thousands(c.young_net)} €</td>
                    <td>{num(c.burden_young_pct)} %</td>
                    <td>{c.rest_burden_young_pct != null ? `${num(c.rest_burden_young_pct)} %` : "—"}</td>
                    <td>{c.rent_2019 != null ? `${thousands(c.rent_2019)} €` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">Alquiler mediano (€/mes)</th>
                  <th scope="col">Sueldo neto de 25–34 (€/año)</th>
                  <th scope="col">Alquiler en % del sueldo joven</th>
                  <th scope="col">Alquiler en % de la renta media de todos los hogares</th>
                  <th scope="col">Igual, año base</th>
                  <th scope="col">Hogares en alquiler de mercado</th>
                </tr>
              </thead>
              <tbody>
                {regions.map((row) => (
                  <tr key={row.code}>
                    <td>{row.name}</td>
                    <td>{thousands(row.rent_month)} €</td>
                    <td>{thousands(row.young_net)} €</td>
                    <td>{num(row.burden_young_pct)} %</td>
                    <td>{old[row.code] ? `${num(old[row.code].burden_pct)} %` : "—"}</td>
                    <td>{old[row.code]?.burden_base_pct != null ? `${num(old[row.code].burden_base_pct)} % (${old[row.code].burden_base_year})` : "—"}</td>
                    <td>{old[row.code]?.renters_pct != null ? `${num(old[row.code].renters_pct)} %` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <div>
        <h3 className="vizPanelTitle">
          Las grandes ciudades frente al resto de su provincia
          <span>alquiler mediano en % del sueldo neto de 25 a 34 años, {year}</span>
        </h3>
        <ul className="hvDumbbell" aria-label="Alquiler en % del sueldo joven: ciudad frente al resto de la provincia">
          {cities.map((c) => {
            const a = scale(c.rest_burden_young_pct ?? c.burden_young_pct);
            const b = scale(c.burden_young_pct);
            return (
              <li key={c.code}>
                <span>
                  {CITY_NAMES[c.code]} <small className="hvMuted">({PROVINCE_OF[c.code]})</small>
                </span>
                <span className="hvDumbbell__track" title={`${CITY_NAMES[c.code]}: ${num(c.burden_young_pct)} % (${thousands(c.rent_month)} €); resto de la provincia: ${c.rest_burden_young_pct != null ? `${num(c.rest_burden_young_pct)} % (${thousands(c.rest_rent_month)} €)` : "—"}`}>
                  <span className="hvDumbbell__line" style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(b - a)}%` }} />
                  {c.rest_burden_young_pct != null ? <span className="hvDumbbell__dot" style={{ left: `${a}%` }} /> : null}
                  <span className="hvDumbbell__dot hvDumbbell__dot--city" style={{ left: `${b}%` }} />
                  <span className="hvDumbbell__text" style={{ "--hv-at": `calc(${Math.max(a, b)}% + 12px)` }}>
                    {num(c.burden_young_pct, 0)} % ({thousands(c.rent_month)} €){c.rest_burden_young_pct != null ? ` · resto ${num(c.rest_burden_young_pct, 0)} %` : ""}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <div>
        <h3 className="vizPanelTitle">
          Por comunidades
          <span>alquiler mediano en % del sueldo neto de 25 a 34 años ajustado a la comunidad, {regions[0].year}</span>
        </h3>
        <Bars
          rows={regions.map((row) => ({
            id: row.code,
            label: row.name,
            value: row.burden_young_pct,
            color: C.orange,
            text: `${num(row.burden_young_pct)} % (${thousands(row.rent_month)} €/mes)`,
          }))}
          max={max}
          label="Alquiler en % del sueldo neto joven por comunidad"
        />
      </div>
      <Explain
        shows="Cuánto del sueldo de una persona joven se lleva el alquiler típico donde vive, en las grandes ciudades frente al resto de su provincia y en cada comunidad."
        read="Punto lleno = la ciudad; hueco = el resto de su provincia. Cuanto más a la derecha, más sueldo se va en el alquiler. Por encima del 40 % se habla de sobrecarga; aquí no se suman los suministros, que lo elevan."
        notSay="No es lo que paga quien firma un contrato hoy (más caro), ni sirve para quien comparte piso o vive en pareja con dos sueldos; el sueldo por edad y comunidad es una aproximación."
      />
    </Figure>
  );
}
