import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Simulator, { ClosureFigure } from "./Simulator";
import { CLOSURES, DEFAULT_LEVERS, simulate } from "./engine.mjs";
import { computeBacktests } from "./backtests.mjs";

export const metadata = {
  title: "Simulador: pensiones y cuentas públicas | Vota Con La Chola",
  description:
    "Qué pasa si se suben o se bajan las pensiones, se retrasa la jubilación o se cotiza más, y quién lo paga según se financie con deuda, cotizaciones o IVA. Modelo con supuestos visibles sobre la línea base oficial del Ageing Report 2024.",
};

const num = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });

const GRADE_TEXT = {
  A: "contabilidad, ley o dato de España",
  B: "estudio sólido de otro país o meta-análisis",
  C: "consenso institucional sin estimación propia",
  D: "supuesto",
};

export default function SistemaPage() {
  const model = readPublicJson("visualizaciones/data/sistema.json", null);
  if (!model) throw new Error("Missing visualizaciones/data/sistema.json");
  const b = model.baseline;
  const y2050 = model.years.length - 1;
  const src = model.sources;
  const cards = model.edges.filter((e) => !e.id.startsWith("B0"));
  const benches = model.edges.filter((e) => e.id.startsWith("B0"));
  const backtests = computeBacktests(model);
  // Headline numbers of the consolidated figure, central values (the figure itself shows the ranges).
  const t35 = model.years.indexOf(2035);
  const runs = Object.fromEntries(CLOSURES.map((c) => [c, simulate(model, { ...DEFAULT_LEVERS, reval: 1, closure: c })]));
  const debt50 = runs.deuda.debt_dev_pp[y2050];
  const p1Vat = -runs.iva.p1_month[t35];
  const p1Ssc = -runs.cotizaciones.p1_month[t35];
  const p4Gain = runs.deuda.p4_month[t35];

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · simulador"
        title="Si se suben las pensiones, ¿quién lo paga?"
        summary="Un modelo pequeño del sistema de pensiones y las cuentas públicas de España: mueve las palancas y mira cómo se propaga el cambio, cuánto cuesta y a quién, según se pague con deuda, con cotizaciones o con IVA. Es un escenario con supuestos a la vista, no una predicción."
        actions={[
          { href: "#simulador", label: "Ir al simulador" },
          { href: "/visualizaciones/data/sistema.json", label: "Modelo y datos (JSON)" },
          { href: "/visualizaciones/data/sistema.csv", label: "Línea base (CSV)" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave de la línea base">
        <div className="card vizStat">
          <span className="vizStat__label">Gasto en pensiones públicas, ley actual</span>
          <span className="vizStat__value">
            {num(b.pension_pct[0])} → {num(b.pension_pct[y2050])} %
          </span>
          <span className="vizStat__note">del PIB, {model.years[0]} → 2050 (Ageing Report 2024)</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Pensionistas</span>
          <span className="vizStat__value">
            {num(b.pensioners_k[0] / 1000)} → {num(b.pensioners_k[y2050] / 1000)} M
          </span>
          <span className="vizStat__note">{model.years[0]} → 2050, misma fuente</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Deuda pública si nada más cambiara</span>
          <span className="vizStat__value">
            {num(model.start.debt_pct, 0)} → {num(b.debt_pct[y2050], 0)} %
          </span>
          <span className="vizStat__note">
            del PIB, {model.start.year} → 2050: cálculo propio con el resto del presupuesto constante en % del PIB; no es una previsión
          </span>
        </div>
      </section>

      <div className="vizProse">
        <p>
          El gasto en pensiones no es una partida aislada: cada euro de más se paga con deuda, con impuestos o recortando otra cosa, y cada una de esas formas
          tiene sus propios efectos sobre el empleo, los precios y los intereses. Este simulador junta esas piezas en un modelo pequeño, con cada relación
          respaldada por una ficha con su fuente, su rango y lo que la contradice.
        </p>
        <p>
          La regla del modelo: <strong>solo calcula diferencias frente a la línea base oficial</strong> (la ley actual según la Comisión Europea), año a año
          hasta 2050. Lo que es aritmética se separa de lo que depende de cómo reaccionen empresas, trabajadores y mercados, y cada resultado dice si su
          signo aguanta todas las hipótesis.
        </p>
      </div>

      <figure className="vizFigure" id="tres-formas">
        <h2>
          Subir las pensiones un punto sobre el IPC suma {num(debt50, 0)} puntos de deuda en 2050 o, si se paga con impuestos, le cuesta a la joven del
          caso 1 entre {num(p1Vat, 0)} y {num(p1Ssc, 0)} euros al mes en 2035
        </h2>
        <p className="vizFigure__dek">
          El mismo cambio (todas las pensiones suben cada año un punto más que el IPC desde 2026) con las tres formas de pagarlo. El pensionista del caso 4
          gana unos {num(p4Gain, 0)} euros al mes en 2035 en los tres casos. El punto es el valor central;
          la barra, del 5 % al 95 % de las simulaciones. Zanja dos relatos: «subir las pensiones no le cuesta a nadie» (con deuda la factura crece; con impuestos
          la paga el caso 1 desde el primer año) y «lo pagan solo los jóvenes» (con deuda no paga nadie hoy y con IVA también lo pagan los pensionistas, que
          recuperan el IPC un año después). Lo que queda abierto: cuánto empleo se pierde con las cotizaciones depende de un supuesto en disputa.
        </p>
        <ClosureFigure model={model} debates={{}} />
        <figcaption className="vizFigure__caption">
          <span>
            Fuente: modelo de esta página sobre la línea base del{" "}
            <a href={src.ageing_report.page} target="_blank" rel="noopener noreferrer">
              Ageing Report 2024
            </a>{" "}
            (Comisión Europea) y las fichas del catálogo; casos tipo de <a href="/visualizaciones/carga-fiscal/">Carga fiscal</a>.
          </span>
        </figcaption>
      </figure>

      <section id="simulador" aria-label="Simulador">
        <p className="sim__label">Escenario de un modelo con supuestos visibles, no una predicción.</p>
        <Simulator model={model} />
      </section>

      <section className="vizProse" id="metodo">
        <h2>Método</h2>
        <p>
          <strong>Línea base.</strong> El gasto en pensiones públicas brutas, los pensionistas, el empleo, el crecimiento potencial, la inflación y el tipo de
          interés de mercado salen del anexo estadístico del{" "}
          <a href={src.ageing_report.page} target="_blank" rel="noopener noreferrer">Ageing Report 2024</a> para España, que incluye las reformas de 2021 y 2023
          (revalorización con el IPC, MEI). El punto de partida son las cuentas de {model.start.year} de Eurostat: deuda del {num(model.start.debt_pct)} % del PIB,
          déficit del {num(model.start.deficit_pct)} % e intereses del {num(model.start.interest_pct)} %. El resto de ingresos y gastos se mantiene constante en %
          del PIB, así que la deuda de la línea base solo recoge el envejecimiento en pensiones y los intereses: no incluye sanidad ni dependencia, ni ningún
          ajuste futuro.
        </p>
        <p>
          <strong>Diferencia de definiciones.</strong> El Ageing Report cuenta {num(model.start.pension_pct_ar, 2)} % del PIB en {model.start.year}; la
          clasificación COFOG de Eurostat (vejez y supervivencia) daba {num(model.start.pension_pct_cofog_2024)} % en 2024, porque no incluye las pensiones de
          incapacidad.
        </p>
        <p>
          <strong>Cómo se calcula.</strong> Pasos anuales de 2026 a 2050. Una revalorización extra se acumula en las pensiones que ya existen, mientras las
          nuevas entran sin ella. Retrasar la jubilación quita una parte de una cohorte por cada año. Cotizar más encarece el empleo según quién acabe pagando
          la cotización. El IVA sube los precios. La deuda paga intereses y, si crece, una prima de riesgo. Cada flecha tiene una ficha con su número, su rango y
          su fuente. Las 200 simulaciones de cada escenario sortean todos los parámetros dentro de su rango (hipercubo latino con semilla fija, así que un
          enlace reproduce el mismo resultado) y tardan unas decenas de milisegundos en el navegador.
        </p>
        <h2>Simplificaciones</h2>
        <ul>
          <li>Economía pequeña y abierta: tipos del BCE, crecimiento europeo y productividad son contexto, no resultados.</li>
          <li>
            Forma reducida: las elasticidades medidas con unas reglas pueden no valer con reglas muy distintas. Los deslizadores se quedan en rangos cercanos
            a lo observado.
          </li>
          <li>
            Sin equilibrio general completo: el PIB solo responde al empleo y a un multiplicador de corto plazo. El efecto del IVA sobre los precios no cambia
            los cocientes sobre el PIB, solo el poder de compra.
          </li>
          <li>Los casos tipo no cambian de vivienda, de empleo ni de servicios: se miden solo los cambios de pensión, salario, cotización y precios.</li>
          <li>
            Las sensibilidades de inmigración son las oficiales, que empiezan en 2023: aquí se les resta su valor de {model.start.year}.
          </li>
        </ul>
        <h2>Lo que el simulador no puede decir</h2>
        <ul>
          <li>Cuánto crecerá la economía o qué hará el BCE: son escenarios.</li>
          <li>
            Si la edad efectiva puede subir de verdad: el deslizador la mueve y el modelo calcula. El Ageing Report da efectos mayores al congelar la edad legal
            (+2,9 puntos de PIB en 2040), porque también mueve la participación laboral de toda la franja de 55 a 74 años.
          </li>
          <li>Qué parte de una cotización empresarial acaba en salarios: está en disputa y se deja elegir.</li>
          <li>Los efectos en sanidad, dependencia, vivienda o educación: llegarán en los siguientes módulos.</li>
        </ul>
      </section>

      <section className="vizProse" id="fichas">
        <h2>Catálogo de relaciones ({cards.length} fichas)</h2>
        <p>
          Grado de la evidencia:{" "}
          {Object.entries(GRADE_TEXT).map(([g, t], i) => (
            <span key={g}>
              {i ? "; " : ""}
              <strong>{g}</strong>, {t}
            </span>
          ))}
          .
        </p>
      </section>
      <div className="vizTable__scroll sim__catalog">
        <table className="sim__table">
          <thead>
            <tr>
              <th scope="col">Relación</th>
              <th scope="col">Valor (rango)</th>
              <th scope="col">Grado</th>
              <th scope="col">Fuente</th>
            </tr>
          </thead>
          <tbody>
            {cards.map((e) => (
              <tr key={e.id} id={`ficha-${e.id}`}>
                <th scope="row">
                  {e.note_es}
                  <span className="sim__muted"> · {e.parameter.unit}</span>
                </th>
                <td>
                  {e.parameter.central.toLocaleString("es-ES")}
                  {e.parameter.low !== e.parameter.high
                    ? ` (${e.parameter.low.toLocaleString("es-ES")} a ${e.parameter.high.toLocaleString("es-ES")})`
                    : ""}
                  {(e.extra_parameters || []).map((x) => (
                    <span key={x.name} className="sim__muted">
                      <br />
                      {x.unit}: {x.central.toLocaleString("es-ES")} ({x.low.toLocaleString("es-ES")} a {x.high.toLocaleString("es-ES")})
                    </span>
                  ))}
                </td>
                <td>{e.grade}</td>
                <td>
                  {e.sources.map((s, i) => (
                    <span key={s.url + i}>
                      {i ? "; " : ""}
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.authors_year}
                      </a>
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="vizProse" id="pruebas">
        <h2>Pruebas del modelo</h2>
        <p>
          Antes de publicar, el modelo se contrasta con episodios reales y con proyecciones oficiales (las pruebas se ejecutan en cada construcción de la
          página):
        </p>
        <ul>
          {backtests.map((bt) => (
            <li key={bt.id}>
              <strong>{bt.label}</strong> {bt.text} <span className="sim__muted">(tolerancia fijada de antemano: {bt.tolerance}; {bt.ok ? "dentro" : "fuera"}).</span>
            </li>
          ))}
        </ul>
        {benches.length ? (
          <p className="sim__muted">
            Referencias:{" "}
            {benches.map((e, i) => (
              <span key={e.id}>
                {i ? "; " : ""}
                <a href={e.sources[0].url} target="_blank" rel="noopener noreferrer">
                  {e.sources[0].authors_year}
                </a>
              </span>
            ))}
            .
          </p>
        ) : null}
        <h2>Fuentes</h2>
        <ul>
          {Object.values(src).map((s) => (
            <li key={s.label}>
              {s.page ? (
                <a href={s.page} target={s.page.startsWith("http") ? "_blank" : undefined} rel="noopener noreferrer">
                  {s.label}
                </a>
              ) : (
                s.label
              )}
              {s.sha256 ? <span className="sim__muted"> · sha256 {s.sha256.slice(0, 12)}…</span> : null}
              {s.retrieved_at ? <span className="sim__muted"> · consultado el {s.retrieved_at}</span> : null}
            </li>
          ))}
        </ul>
        <p className="sim__muted">
          Modelo generado el {String(model.generated_at).slice(0, 10)}. Siguiente módulo: impuestos (IRPF, IVA, cotizaciones) con su reparto por quintil.
        </p>
      </section>
    </main>
  );
}

