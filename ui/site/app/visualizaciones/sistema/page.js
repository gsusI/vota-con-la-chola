import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Simulator, { ClosureFigure } from "./Simulator";
import { CLOSURES, DEFAULT_LEVERS, centralParams, quintileImpact, simulate } from "./engine.mjs";
import { computeBacktests } from "./backtests.mjs";

export const metadata = {
  title: "Simulador: pensiones, impuestos y cuentas públicas | Vota Con La Chola",
  description:
    "Qué pasa si se suben o se bajan las pensiones, el IRPF, el IVA, las cotizaciones o el Impuesto sobre Sociedades: cuánto recauda, quién lo paga por nivel de renta y en casos concretos, y cómo se mueven la deuda y el empleo. Modelo con supuestos visibles sobre la línea base oficial del Ageing Report 2024.",
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
  const taxPaid = ["cotizaciones", "iva", "irpf"].map((c) => -runs[c].p1_month[t35]);

  // One more point of each tax from the first year: revenue (statutory and after behaviour) and who bears it.
  const t1 = model.years.indexOf(model.policy_start);
  const P = centralParams(model);
  const meur = (pp) => (pp / 100) * model.start.gdp_meur * model.baseline.real_index[t1];
  const TAXES = [
    { key: "irpfAll", label: "IRPF, todos los tramos", stat: "s_irpf_all_pp", rev: (r) => r.irpf_revenue_pp[t1] },
    { key: "irpfTop", label: "IRPF, tramo de más de 60.000 €", stat: "s_irpf_top_pp", rev: (r) => r.irpf_revenue_pp[t1] },
    { key: "vatStd", label: "IVA general (21 %)", stat: "s_vat_std_pp", rev: (r) => r.vat_revenue_pp[t1] },
    { key: "vatRed", label: "IVA reducido (10 %)", stat: "s_vat_red_pp", rev: (r) => r.vat_red_revenue_pp[t1] },
    { key: "contrib", label: "Cotizaciones sociales", stat: "s_contrib_pp", rev: (r) => r.contrib_revenue_pp[t1] + r.labour_revenue_pp[t1] },
    { key: "corp", label: "Impuesto sobre Sociedades", stat: "s_corp_pp", rev: (r) => r.corp_revenue_pp[t1] },
  ].map((tax) => {
    const run = simulate(model, { ...DEFAULT_LEVERS, [tax.key]: 1 });
    const q = quintileImpact(model, run, t1, P);
    return { ...tax, statutory: meur(run[tax.stat][t1]), behaviour: meur(tax.rev(run)), q, cases: ["p1", "p2", "p4", "p5"].map((id) => run[`${id}_month`][t1]) };
  });
  const irpfRow = TAXES[0];
  // Does raising the top bracket raise revenue? One answer per school of the contested elasticity.
  const topDebate = model.params.eti_alta.debate;
  const topSchools = (topDebate?.schools || []).map((school, i) => {
    const run = simulate(model, { ...DEFAULT_LEVERS, irpfTop: 1 }, centralParams(model, { [topDebate.id]: i }));
    return { label: school.label, eti: school.central, meur: meur(run.irpf_revenue_pp[t1]) };
  });
  const vatRow = TAXES[2];
  const contribRow = TAXES[4];
  const ratio = (row) => -row.q[4].pctDisposable / -row.q[0].pctDisposable;

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · simulador"
        title="Si se suben las pensiones o los impuestos, ¿quién lo paga?"
        summary="Un modelo pequeño de las pensiones, los impuestos y las cuentas públicas de España: mueve las palancas y mira cómo se propaga el cambio, cuánto cuesta y a quién, por nivel de renta y en casos concretos, según se pague con deuda, cotizaciones, IVA o IRPF. Es un escenario con supuestos a la vista, no una predicción."
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
          caso 1 entre {num(Math.min(...taxPaid), 0)} y {num(Math.max(...taxPaid), 0)} euros al mes en 2035
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

      <figure className="vizFigure" id="impuestos">
        <h2>
          Un punto más de IRPF en todos los tramos recauda unos {num(irpfRow.behaviour / 1000, 1)} mil millones y pesa {num(ratio(irpfRow), 1)} veces más en
          la renta del quintil más rico que en la del más pobre; uno de IVA general, {num(vatRow.behaviour / 1000, 1)} mil millones y pesa más en el más pobre
        </h2>
        <p className="vizFigure__dek">
          Cada fila sube un punto un impuesto desde {model.policy_start}, con todo lo demás igual. La recaudación legal es la aritmética; «tras la reacción»
          resta lo que la gente y las empresas dejan de declarar o de ganar (elasticidades con su rango en el catálogo). El reparto por quintiles es la carga
          legal sobre la renta disponible de cada quinto de la población, de menos a más renta. Pone a prueba dos relatos: «subir impuestos lo pagan los
          ricos» (el IVA general pesa un {num(-vatRow.q[0].pctDisposable, 2)} % de la renta en el primer quintil y un {num(-vatRow.q[4].pctDisposable, 2)} %
          en el quinto; las cotizaciones, del {num(-contribRow.q[0].pctDisposable, 2)} % al {num(-contribRow.q[4].pctDisposable, 2)} %) y «el IRPF lo
          pagan las clases medias» (pesa {num(ratio(irpfRow), 1)} veces más arriba que abajo). Lo que queda abierto: si subir el tramo más alto recauda o
          no depende de cuánto reaccionan las rentas altas, un valor en disputa; y la encuesta recoge peor las rentas más altas.
        </p>
        <div className="vizTable__scroll">
          <table className="sim__table sim__table--taxes">
            <thead>
              <tr>
                <th scope="col" rowSpan={2}>Un punto más de…</th>
                <th scope="col" colSpan={2}>Recaudación el primer año (millones)</th>
                <th scope="col" colSpan={5}>Carga en % de la renta disponible, por quintil</th>
                <th scope="col" colSpan={4}>Casos tipo, euros al mes</th>
              </tr>
              <tr>
                <th scope="col">legal</th>
                <th scope="col">tras la reacción</th>
                {["1.º", "2.º", "3.º", "4.º", "5.º"].map((q) => (
                  <th scope="col" key={q}>{q}</th>
                ))}
                {["1", "2", "4", "5"].map((c) => (
                  <th scope="col" key={c}>caso {c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TAXES.map((row) => (
                <tr key={row.key}>
                  <th scope="row">{row.label}</th>
                  <td>{Math.round(row.statutory).toLocaleString("es-ES", { useGrouping: "always" })}</td>
                  <td className={row.behaviour < 0 ? "sim__neg" : undefined}>{Math.round(row.behaviour).toLocaleString("es-ES", { useGrouping: "always" })}</td>
                  {row.q.map((q) => (
                    <td key={q.q} className="sim__heat" style={{ "--heat": Math.min(1, -q.pctDisposable / 0.9) }}>
                      {num(-q.pctDisposable, 2)}
                    </td>
                  ))}
                  {row.cases.map((v, i) => (
                    <td key={i}>{Math.abs(v) < 0.5 ? "0" : `−${num(-v, 0)}`}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <figcaption className="vizFigure__caption">
          <span>
            Fuente: modelo de esta página; recaudación por punto de la Agencia Tributaria (IRPF y Sociedades), la Memoria de Beneficios Fiscales y la AEAT
            (IVA) y la Seguridad Social (cotizaciones); reparto con los microdatos de la{" "}
            <a href={src.ecv_microdata.page} target="_blank" rel="noopener noreferrer">Encuesta de Condiciones de Vida {model.incidence.ecv.year}</a> y la{" "}
            <a href={src.eurostat_hbs.page} target="_blank" rel="noopener noreferrer">Encuesta de Presupuestos Familiares {model.incidence.vat.year}</a>{" "}
            (Eurostat) con los tipos de la Ley del IVA.
          </span>
          <span>
            Los casos tipo están por debajo de 60.000 € de base y no pagan el tramo alto. Las cotizaciones se reparten según los salarios; Sociedades, entre
            los dueños del capital y los salarios según el valor central de su traslado ({num(P.traslado_sociedades_salarios * 100, 0)} %, en disputa).
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
          <li>Los casos tipo no cambian de vivienda, de empleo ni de servicios: se miden solo los cambios de pensión, salario, cotización, IRPF y precios.</li>
          <li>
            IRPF: la recaudación por punto sale de las declaraciones de la Agencia Tributaria; el reparto, de una microsimulación con las reglas generales
            (gastos deducibles, reducción por rendimientos del trabajo, mínimo personal) sin declaración conjunta, mínimos por hijos ni escalas autonómicas
            concretas. La reacción se mide con la elasticidad de la renta gravable.
          </li>
          <li>
            IVA: el reparto usa el gasto por quintil de {model.incidence.vat.year}, el último antes de la pandemia, con el tipo de la ley que corresponde a cada
            grupo de gasto; las rebajas temporales de alimentos y energía no cuentan. El precio sube con el traslado medio estimado.
          </li>
          <li>
            Carga legal: los quintiles muestran quién paga cada impuesto antes de que nadie reaccione, salvo el traslado de cotizaciones y de Sociedades a
            salarios, que sigue el valor central de su ficha.
          </li>
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
          <li>
            Si subir un punto el tramo más alto del IRPF recauda depende de cuánto reaccionan las rentas altas:{" "}
            {topSchools.map((sc, i) => (
              <span key={sc.label}>
                {i ? "; " : ""}
                «{sc.label}» (elasticidad {num(sc.eti, 2)}): {sc.meur >= 0 ? "+" : "−"}
                {Math.abs(Math.round(sc.meur)).toLocaleString("es-ES")} millones
              </span>
            ))}
            . Elige la escuela en «Supuestos en disputa».
          </li>
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
          Modelo generado el {String(model.generated_at).slice(0, 10)}. Siguiente módulo: vivienda (construcción, crédito, límite del alquiler y alquiler
          turístico).
        </p>
      </section>
    </main>
  );
}

