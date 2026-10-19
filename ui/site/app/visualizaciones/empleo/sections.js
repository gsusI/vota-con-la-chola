import { formatValue } from "../components/format.mjs";

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

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
          <strong>Causas.</strong> Las series muestran que el paro español es más alto y más volátil y con qué rasgos coincide (dualidad de
          contratos, construcción, formación), no cuánto pesa cada causa. Eso exige modelos y microdatos; aquí se citan estudios cuando existen.
          Tampoco se mide la negociación colectiva ni la eficacia de las políticas activas de empleo.
        </li>
        <li>
          <strong>Estructural frente a cíclico.</strong> No hay una medida directa del paro estructural. El NAWRU es la estimación de un modelo
          y cambia con cada previsión; otras estimaciones darían otras cifras.
        </li>
        <li>
          <strong>Efecto de la reforma de 2022.</strong> La caída de la temporalidad coincide con la reforma, pero también con la recuperación
          tras la pandemia; la serie no aísla el efecto de la ley. Ni la EPA ni las
          estadísticas publicadas miden cuántos días trabaja al año cada fijo discontinuo (hace falta la Muestra Continua de Vidas Laborales) ni
          cuántos contratos indefinidos terminan en el periodo de prueba.
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
          <strong>Diferencias regionales.</strong> Las comunidades autónomas se ven en el paro por edad y estudios, el paro y el empleo regionales y la
          productividad por comunidad, pero la mayoría de las series (contratos, salarios, productividad en el tiempo, gasto) son nacionales. La EPA
          regional no baja a provincia ni a municipio con cruces por edad, y las celdas con poca muestra quedan vacías. No hay paridades de poder
          adquisitivo oficiales por comunidad: un mismo salario no compra lo mismo en Madrid que en Badajoz, y aquí no se corrige.
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
          <strong>Ejes.</strong> Todos los ejes verticales incluyen el cero; los paneles de un mismo gráfico comparten escala. No hay doble eje:
          las comparaciones de crecimiento se indexan a un año base (1995 = 100) y las de nivel a la media europea (= 100).
        </li>
        <li>
          <strong>Rupturas de serie.</strong> Se muestran, no se empalman: las tres medias europeas de AMECO (UE-15 con la RFA, UE-15, UE-27),
          las series histórica y vigente de Eurostat, Alemania Occidental y unificada, y los cambios de la EPA en 2001, 2005 y 2021.
        </li>
        <li>
          <strong>Fuente oficial y réplica.</strong> AMECO y la OCDE se leen de DBnomics, que replica los códigos oficiales, porque
          sdmx.oecd.org responde HTTP 403 a las descargas por script (incidente registrado en el registro público de bloqueos). La Seguridad
          Social se lee de sus ficheros PC-Axis y el Ministerio de Trabajo de su Anuario en Excel; el servidor del Ministerio presenta una cadena
          TLS incompleta y se descarga sin verificar el certificado solo para ese servidor (el fichero queda guardado con su SHA-256). No se ha
          sorteado ningún bloqueo.
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
