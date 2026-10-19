import { formatValue } from "../components/format.mjs";

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function HypothesisCard({ h }) {
  const g = h.productivity_growth_pct;
  return (
    <section className="card vizProse" id="hipotesis" aria-labelledby="hipotesis-title">
      <h2 id="hipotesis-title">La hipótesis, contrastada</h2>
      <p>
        <strong>Hipótesis:</strong> el paro de España es estructural, no cíclico. Desde 1980 ha sido aproximadamente el doble de la
        media europea en casi todos los ciclos, y la productividad por hora apenas ha crecido desde 1995 frente a países comparables.
      </p>
      <p>
        <strong>Veredicto: se sostiene en lo esencial, con dos matices importantes.</strong>
      </p>
      <ul>
        <li>
          <strong>A favor.</strong> Desde {h.hypothesis_from}, el paro español ha sido de media {num(h.ratio_mean_since, 2)} veces el de la
          UE-15 y ha superado 1,5 veces esa media en {h.years_ratio_ge_1_5} de {h.years_since} años. La Comisión Europea estima su paro
          estructural (NAWRU) en {num(h.nawru_ratio_mean_since, 2)} veces el europeo en el mismo periodo, y nunca por debajo del{" "}
          {num(h.nawru_min_since.value)} %. La productividad por hora creció un {num(g.ESP)} % desde {h.productivity_base}, frente al{" "}
          {num(g.EU27)} % de la UE-27, {num(g.DEU)} % de Alemania, {num(g.PRT)} % de Portugal y {num(g.FRA)} % de Francia.
        </li>
        <li>
          <strong>En contra: no es «el doble en casi todos los ciclos».</strong> Solo en {h.years_ratio_ge_2} de {h.years_since} años llegó al
          doble. En el auge previo a 2008 bajó a {num(h.ratio_lowest_since.value, 2)} veces ({h.ratio_lowest_since.year}), y en {h.last_year} está
          en {num(h.ratio_eu27_last, 2)} veces la UE-27. Antes de 1975 España tenía un paro similar al europeo, así que no es un rasgo
          permanente del país sino algo que aparece con las crisis de los setenta y ochenta.
        </li>
        <li>
          <strong>En contra: el ciclo pesa mucho.</strong> El paro pasó del {num(h.peaks.min_pre_crisis.value)} % ({h.peaks.min_pre_crisis.year}) al{" "}
          {num(h.peaks.max_crisis.value)} % ({h.peaks.max_crisis.year}) y ha vuelto al {num(h.es_last)} %. Esa amplitud es cíclica; lo que
          parece estructural es que cada crisis empieza y termina más arriba que en Europa. Y en productividad Italia lo ha hecho peor
          (+{num(g.ITA)} %).
        </li>
      </ul>
    </section>
  );
}

export function RatioDecadesTable({ decades, series }) {
  const years = [...new Set(series.flatMap((s) => s.points.map((p) => p.year)))].sort((a, b) => b - a);
  const lookup = series.map((s) => new Map(s.points.map((p) => [p.year, p.value])));
  return (
    <>
      <details className="vizTable" open style={{ minWidth: 0 }}>
        <summary>Media por década (España / UE-15, en veces)</summary>
        <div className="vizTable__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Década</th>
                <th scope="col">Paro España</th>
                <th scope="col">Paro UE-15</th>
                <th scope="col">Veces</th>
                <th scope="col">Años con dato</th>
              </tr>
            </thead>
            <tbody>
              {decades.map((d) => (
                <tr key={d.decade}>
                  <td>{d.decade}s</td>
                  <td>{formatValue(d.es_mean, "pct", 1)}</td>
                  <td>{formatValue(d.eu_mean, "pct", 1)}</td>
                  <td>×{num(d.mean_ratio, 2)}</td>
                  <td>{d.years}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details className="vizTable">
        <summary>Ver los datos en tabla (Europa = 100)</summary>
        <div className="vizTable__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Año</th>
                {series.map((s) => (
                  <th scope="col" key={s.id}>
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {years.map((year) => (
                <tr key={year}>
                  <td>{year}</td>
                  {lookup.map((map, index) => (
                    <td key={series[index].id}>{map.has(year) ? num(map.get(year), 1) : ""}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}

export function WedgeBars({ values, names, year, color }) {
  const rows = Object.entries(values)
    .map(([area, value]) => ({ area, value }))
    .sort((a, b) => b.value - a.value);
  const max = Math.max(...rows.map((row) => row.value));
  return (
    <>
      <h3 className="vizPanelTitle">
        Cuña fiscal en {year}
        <span>% del coste laboral, salario medio, soltero sin hijos</span>
      </h3>
      <ul className="vizBars" aria-label={`Cuña fiscal en ${year}`}>
        {rows.map((row) => (
          <li key={row.area}>
            <span>{names[row.area] || row.area}</span>
            <span className="vizBars__track">
              <span
                className="vizBars__bar"
                style={{ width: `${(row.value / max) * 100}%`, background: row.area === "ESP" ? color : undefined, opacity: row.area === "ESP" ? 1 : 0.55 }}
              />
              <span className="vizBars__value">{formatValue(row.value, "pct", 1)}</span>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function LimitsCard() {
  return (
    <section className="card vizProse" id="limites" aria-labelledby="limites-title">
      <h2 id="limites-title">Lo que estos datos no pueden decir</h2>
      <ul>
        <li>
          <strong>Causas.</strong> Las series muestran que el paro español es más alto y más volátil, no por qué. Las explicaciones habituales
          (dualidad de contratos, negociación colectiva, peso de la construcción y el turismo, políticas activas débiles) no se prueban con
          estos gráficos.
        </li>
        <li>
          <strong>Estructural frente a cíclico.</strong> No hay una medida directa del paro estructural. El NAWRU es la estimación de un modelo
          y cambia con cada previsión; otras estimaciones darían otras cifras.
        </li>
        <li>
          <strong>Efecto de la reforma de 2022.</strong> La caída de la temporalidad coincide con la reforma, pero también con la recuperación
          tras la pandemia; la serie no aísla el efecto de la ley. La EPA no mide cuántos días trabaja al año un fijo discontinuo ni cuántos
          contratos indefinidos terminan en el periodo de prueba.
        </li>
        <li>
          <strong>Paro registrado y economía sumergida.</strong> La EPA es una encuesta: mide quien busca empleo, no quien está inscrito en las
          oficinas públicas (paro registrado, que es otra cifra), y no distingue el trabajo no declarado.
        </li>
        <li>
          <strong>Productividad.</strong> Las horas trabajadas se estiman con métodos distintos en cada país, y el índice mezcla eficiencia con
          cambios en qué sectores emplean a más gente. Los niveles en paridad de poder de compra tienen varios puntos de margen de error.
        </li>
        <li>
          <strong>Diferencias regionales.</strong> Son series nacionales: el paro varía mucho entre comunidades autónomas y aquí no se ve.
        </li>
      </ul>
    </section>
  );
}

export function MethodCard({ data, downloads, events }) {
  const src = data.sources;
  return (
    <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
      <h2 id="metodo-title">Método y fuentes</h2>
      <ul>
        <li>
          <strong>Denominador.</strong> Tasas sobre la población activa o sobre los asalariados, productividad en volumen por hora trabajada y
          cuña fiscal sobre el coste laboral: nunca totales nominales.
        </li>
        <li>
          <strong>Ejes.</strong> Todos los ejes verticales empiezan en cero; los paneles de un mismo gráfico comparten escala. No hay doble eje:
          las comparaciones de crecimiento se indexan a un año base (1995 = 100) y las de nivel a la media europea (= 100).
        </li>
        <li>
          <strong>Rupturas de serie.</strong> Se muestran, no se empalman: las tres medias europeas de AMECO (UE-15 con la RFA, UE-15, UE-27),
          las series histórica y vigente de Eurostat, Alemania Occidental y unificada, y los cambios de la EPA en 2001, 2005 y 2021.
        </li>
        <li>
          <strong>Fuente oficial y réplica.</strong> AMECO y la OCDE se leen de DBnomics, que replica los códigos oficiales, porque
          sdmx.oecd.org responde HTTP 403 a las descargas por script. No se ha sorteado ningún bloqueo.
        </li>
        <li>
          <strong>Reproducible.</strong> <code>just employment-refresh</code> descarga cada fuente, guarda el fichero original y lo carga en
          SQLite con el contrato de indicadores del proyecto: cada publicación oficial es una versión nueva, cada valor se compara con la
          anterior (sin cambios, revisado o eliminado) y apunta a su celda en el original con su SHA-256. Los cocientes, medias anuales e
          índices se calculan desde esa base. <a href={downloads}>Descargar los datos publicados (CSV)</a>.
        </li>
      </ul>
      {events.length ? (
        <details className="vizTable">
          <summary>Reformas y rupturas marcadas en los gráficos</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Hecho</th>
                  <th scope="col">Fuente</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{event.date}</td>
                    <td>{event.label}</td>
                    <td>
                      <a href={event.source_url} rel="noopener noreferrer" target="_blank">
                        {event.source}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
      {data.gaps?.length ? (
        <>
          <h3>Huecos conocidos</h3>
          <ul>
            {data.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </>
      ) : null}
      <p>
        Fuentes:{" "}
        {Object.values(src).map((s, index) => (
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
  );
}
