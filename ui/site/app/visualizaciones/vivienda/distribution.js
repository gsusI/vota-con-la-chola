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

export function TenantRegionFigure({ territory, source }) {
  const rows = territory.rows;
  const top = rows.slice(0, 3);
  const bottom = rows.slice(-3);
  const max = Math.max(...rows.map((row) => row.burden_pct));
  const year = rows[0].year;
  const rentFaster = rows.filter((row) => row.rent_change_pct != null && row.rent_change_pct > row.income_change_pct);
  const manyRenters = rows.filter((row) => row.renters_pct != null && row.renters_pct > 20);
  return (
    <Figure
      id="alquiler-regiones"
      title={`Pagar el alquiler mediano declarado cuesta el ${num(top[0].burden_pct, 0)} % de la renta media del hogar en ${joinEs(top.map((row) => row.name))}, y en torno al ${num(bottom[0].burden_pct, 0)} % en ${joinEs(bottom.map((row) => row.name))} (${year})`}
      dek={`Alquiler mensual mediano de los pisos alquilados como vivienda habitual (declarado en el IRPF) × 12, dividido por la renta neta media de los hogares de la comunidad ese mismo año. En la mayoría de comunidades la renta media creció más que ese alquiler desde 2015; el alquiler creció más en ${joinEs(rentFaster.map((row) => row.name))}. Los hogares que alquilan a precio de mercado son el ${num(territory.renters_es_pct)} % en España y más del 20 % en ${joinEs(manyRenters.map((row) => row.name))}.`}
      legendKind="bar"
      sources={[
        source("mivau_boletin", "Ministerio de Vivienda, Sistema Estatal de Referencia del Precio del Alquiler (SERPAVI 2011–2024)", "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi"),
        source("ine_tempus", "INE, Encuesta de Condiciones de Vida (renta por hogar y tenencia por comunidad)", "https://www.ine.es/jaxiT3/Tabla.htm?t=9949"),
      ]}
      notes={[
        "La renta es la media de todos los hogares, propietarios incluidos, que suelen ganar más que los inquilinos: el esfuerzo real de quien alquila es mayor que este porcentaje. El alquiler es el de todos los contratos vigentes, no el de los nuevos. País Vasco (solo 2024) y Navarra (desde 2021) tienen su propia Hacienda y entran con menos años.",
        "La ECV de un año recoge la renta del año anterior: la ECV de 2025 se empareja con el alquiler de 2024.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">Alquiler mediano (€/mes)</th>
                  <th scope="col">Renta neta media del hogar (€/año)</th>
                  <th scope="col">Alquiler en % de la renta</th>
                  <th scope="col">Igual, año base</th>
                  <th scope="col">Alquiler: variación</th>
                  <th scope="col">Renta: variación</th>
                  <th scope="col">Hogares en alquiler de mercado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.code}>
                    <td>{row.name}</td>
                    <td>{thousands(row.rent_month)} €</td>
                    <td>{thousands(row.income_year)} €</td>
                    <td>{num(row.burden_pct)} %</td>
                    <td>{row.burden_base_pct != null ? `${num(row.burden_base_pct)} % (${row.burden_base_year})` : "—"}</td>
                    <td>{row.rent_change_pct != null ? `${num(row.rent_change_pct)} %` : "—"}</td>
                    <td>{row.income_change_pct != null ? `${num(row.income_change_pct)} %` : "—"}</td>
                    <td>{row.renters_pct != null ? `${num(row.renters_pct)} %` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Bars
        rows={rows.map((row) => ({
          id: row.code,
          label: row.name,
          value: row.burden_pct,
          color: C.orange,
          text: `${num(row.burden_pct)} % (${thousands(row.rent_month)} €/mes)${row.burden_base_pct != null ? ` · ${num(row.burden_base_pct)} % en ${row.burden_base_year}` : ""}`,
        }))}
        max={max}
        label="Alquiler en % de la renta del hogar por comunidad"
      />
      <Explain
        shows="Cuánto pesa el alquiler típico sobre la renta típica en cada comunidad, y cómo ha cambiado desde 2015."
        read="Barra más larga = el alquiler se come más renta. El dato final de cada barra compara con 2015: si es mayor que hoy, el alquiler declarado ha subido menos que la renta media."
        notSay="No es lo que paga quien firma un contrato hoy, que suele ser más, ni la renta de los inquilinos, que suele ser menor; tampoco distingue la capital del resto de la comunidad."
      />
    </Figure>
  );
}
