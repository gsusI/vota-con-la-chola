import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Lab, { WhoPays } from "./scene/Lab";
import HousingCompare from "./scene/HousingCompare";
import { housingRows } from "./housingScenarios.mjs";
import { CLOSURES, DEFAULT_LEVERS, centralParams, quintileImpact, simulate } from "./engine.mjs";
import { computeBacktests } from "./backtests.mjs";
import { JsonLd, breadcrumbLd, faqLd, pageMetadata, webApplicationLd } from "../../seo";
import { withBasePath } from "../../path-utils.mjs";
import { LEVER_LIST, SCENARIOS, SCENARIOS_PATH, SIM_PATH, SIM_TITLE, fmt, mainFindings, scenarioPath, simDescription } from "./scenarios.mjs";

const loadModel = () => {
  const model = readPublicJson("visualizaciones/data/sistema.json", null);
  if (!model) throw new Error("Missing visualizaciones/data/sistema.json");
  return model;
};

export function generateMetadata() {
  return pageMetadata({
    path: SIM_PATH,
    title: SIM_TITLE,
    description: simDescription(loadModel()),
    image: { path: "/visualizaciones/sistema/og/inicio.png", alt: "Simulador de pensiones, impuestos y vivienda: ¿quién lo paga?" },
    keywords: ["simulador pensiones", "simulador impuestos", "subir pensiones", "subir IVA", "bajar IRPF", "tope alquiler", "vivienda pública", "deuda pública"],
  });
}

const num = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });

const GRADE_TEXT = {
  A: "contabilidad, ley o dato de España",
  B: "estudio sólido de otro país o meta-análisis",
  C: "consenso institucional sin estimación propia",
  D: "supuesto",
};

export default function SistemaPage() {
  const model = loadModel();
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

  // Housing (slice 2): the same six policies as the consolidated figure, central values for the title and the text.
  const H = model.housing;
  const hRowsList = housingRows(model, {}, 2035, 160);
  const hRows = Object.fromEntries(hRowsList.map((r) => [r.id, r]));
  // Size of each flow in the scene: revenue by tax in % of GDP, latest year of the tax page.
  const fiscal = readPublicJson("visualizaciones/data/carga-fiscal.json", null);
  const comp = fiscal.composition_pct_gdp;
  const last = (code) => comp[code].at(-1).value;
  const composition = { irpf: last("T_1100"), corp: last("T_1200"), contrib: last("T_2100") + last("T_2200") + last("T_2300"), vat: last("T_5000") };
  const verb = (v, d = 1) => (v < 0 ? `baja un ${num(-v, d)} %` : `sube un ${num(v, d)} %`);
  const t35h = model.years.indexOf(2035);
  const pubRun = simulate(model, { ...DEFAULT_LEVERS, pubHomes: 20 });
  const pubCostMeur = (pubRun.hs_cost_pp[t35h] / 100) * model.start.gdp_meur * model.baseline.real_index[t35h];
  const b2Share = pubRun.hs_households_k[t35h] / pubRun.hs_stock_k[t35h];
  const capDebate = model.params.respuesta_oferta_tope.debate;
  const capSchools = (capDebate?.schools || []).map((school, i) => {
    const run = simulate(model, { ...DEFAULT_LEVERS, capCov: 50, capCut: 10 }, centralParams(model, { [capDebate.id]: i }));
    return { label: school.label, value: school.central, stock: run.hs_rental_stock_k[t35h], cov: run.hs_rent_cov[t35h], unc: run.hs_rent_unc[t35h],
      p1cov: run.p1_rent_cov_month[t35h], p1unc: run.p1_rent_unc_month[t35h] };
  });
  const creditRun = simulate(model, { ...DEFAULT_LEVERS, ltvCap: 80, ltiCap: 4.5 });
  const creditNoLoop = simulate(model, { ...DEFAULT_LEVERS, ltvCap: 80, ltiCap: 4.5 }, { ...P, elasticidad_credito_precio: 0 });
  const r2 = creditRun.hs_price[t35h] / creditNoLoop.hs_price[t35h];
  const baseGap = H.net_households_next_k - (H.completions_free_k + H.completions_protected_k);

  // Visible FAQ (and its FAQPage JSON-LD): answers use only the engine numbers computed above.
  const costMeur35 = mainFindings(model).costMeur35;
  const faqs = [
    {
      q: "¿Cómo funciona el simulador?",
      a: `Mueves una palanca (pensiones, edad de jubilación, cotizaciones, IRPF, IVA, Sociedades, vivienda pública, suelo, tope del alquiler, pisos turísticos o hipotecas) y eliges cómo se paga: con deuda, cotizaciones, IVA o IRPF. El modelo calcula año a año, de ${model.policy_start} a 2050, la diferencia frente a la ley actual en deuda, empleo, precios, alquiler, por nivel de renta y en cuatro casos tipo, con 200 simulaciones que sortean cada parámetro dentro de su rango.`,
    },
    {
      q: "¿Es una predicción?",
      a: "No. Es un modelo pequeño de forma reducida con supuestos visibles: calcula diferencias frente a las proyecciones oficiales y no dice cuánto crecerá la economía ni qué hará el BCE. Los deslizadores se quedan cerca de lo observado; fuera de ese rango, el modo ilustrativo enseña el mecanismo, no estimaciones.",
    },
    {
      q: "¿De dónde salen los números?",
      a: `La línea base es el Ageing Report 2024 de la Comisión Europea y la proyección de hogares del INE; el punto de partida, las cuentas de ${model.start.year} de Eurostat; el reparto por renta, los microdatos de la Encuesta de Condiciones de Vida ${model.incidence.ecv.year} y la Encuesta de Presupuestos Familiares ${model.incidence.vat.year}. Cada una de las ${cards.length} relaciones tiene una ficha con su fuente, su rango, su grado de evidencia y lo que la contradice.`,
    },
    {
      q: "¿Cuánto cuesta subir las pensiones un punto más que el IPC?",
      a: `Unos ${fmt.meurAbs(costMeur35)} al año en 2035 y ${num(debt50, 0)} puntos de PIB de deuda extra en 2050 si se paga con deuda. Si se paga con impuestos, a Lucía (caso 1, 25 a 34 años) le cuesta entre ${num(Math.min(...taxPaid), 0)} y ${num(Math.max(...taxPaid), 0)} euros al mes en 2035 según el impuesto, y Carmen (caso 4, jubilada) gana unos ${num(p4Gain, 0)} euros al mes si se paga con deuda o con cotizaciones.`,
    },
    {
      q: "¿Quién paga una subida del IVA?",
      a: `Un punto más de IVA general recauda unos ${num(vatRow.behaviour / 1000, 1)} mil millones el primer año tras la reacción y pesa un ${num(-vatRow.q[0].pctDisposable, 2)} % de la renta disponible en el 20 % con menos renta y un ${num(-vatRow.q[4].pctDisposable, 2)} % en el 20 % con más: en proporción a la renta, pesa más abajo. Un punto de IRPF en todos los tramos pesa ${num(ratio(irpfRow), 1)} veces más en el quinto más rico que en el más pobre.`,
    },
    {
      q: "¿Baja el alquiler con un tope?",
      a: `A quien tiene o encuentra un contrato cubierto, sí: un tope del 10 % en la mitad del mercado ${verb(hRows.capIn.rent.v)} el alquiler de un contrato nuevo con tope en 2035. A quien busca fuera del tope, ${verb(hRows.capOut.rent.v)}, porque algunos caseros dejan el alquiler; cuántos es el supuesto más disputado del simulador (los estudios de Cataluña y San Francisco no coinciden).`,
    },
  ];
  const crumbs = [
    { name: "Visualizaciones", path: "/visualizaciones/" },
    { name: "Simulador", path: SIM_PATH },
  ];
  const appLd = webApplicationLd({
    path: SIM_PATH,
    name: "Simulador de pensiones, impuestos y vivienda",
    description: simDescription(model),
    image: "/visualizaciones/sistema/og/inicio.png",
    featureList: LEVER_LIST,
  });

  return (
    <main className="shell vizArticle">
      <JsonLd data={[breadcrumbLd(crumbs), appLd, faqLd(faqs)]} />
      <StaticRouteHero
        eyebrow="Visualizaciones · simulador"
        title="Si se suben las pensiones o los impuestos, o se interviene la vivienda, ¿quién lo paga?"
        summary="Un modelo pequeño de las pensiones, los impuestos, la vivienda y las cuentas públicas de España: mueve las palancas y mira cómo se propaga el cambio, cuánto cuesta y a quién, por nivel de renta y en casos concretos, según se pague con deuda, cotizaciones, IVA o IRPF. Es un escenario con supuestos a la vista, no una predicción."
        actions={[
          { href: "#simulador", label: "Ir al simulador" },
          { href: "#vivienda", label: "Vivienda" },
          { href: SCENARIOS_PATH, label: "Escenarios" },
          { href: "/visualizaciones/data/sistema.json", label: "Modelo y datos (JSON)" },
          { href: "/visualizaciones/data/sistema.csv", label: "Línea base (CSV)" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />


      <div className="vizProse">
        <p>
          Cada euro de más en pensiones o en vivienda pública se paga con deuda, con impuestos o recortando otra cosa, y cada forma de pagarlo mueve el
          empleo, los precios y los intereses. Elige un cambio y mira cómo circula el dinero, a quién le toca y por qué. El modelo solo calcula diferencias
          frente a la ley actual según las proyecciones oficiales, y cada relación tiene una ficha con su fuente, su rango y lo que la contradice.
        </p>
        <p>
          <strong>Qué puedes mover:</strong> {LEVER_LIST.join("; ")}.
        </p>
      </div>

      <section id="simulador" aria-label="Simulador">
        <p className="sim__label">Escenario de un modelo con supuestos visibles, no una predicción.</p>
        <Lab model={model} composition={composition} />
      </section>

      <figure className="vizFigure" id="tres-formas">
        <h2>
          Subir las pensiones un punto sobre el IPC suma {num(debt50, 0)} puntos de deuda en 2050 o, si se paga con impuestos, le cuesta a la joven del
          caso 1 entre {num(Math.min(...taxPaid), 0)} y {num(Math.max(...taxPaid), 0)} euros al mes en 2035
        </h2>
        <p className="vizFigure__dek">
          El mismo cambio (todas las pensiones suben cada año un punto más que el IPC desde 2026) con las cuatro formas de pagarlo. Carmen, la pensionista del
          caso 4, gana unos {num(p4Gain, 0)} euros al mes en 2035 si se paga con deuda o con cotizaciones, y unos {num(runs.irpf.p4_month[t35], 0)} si se paga
          con IRPF, que también paga ella. Cada casilla da el valor central y, debajo, el rango del 5 % al 95 % de las simulaciones; verde, mejor para quien
          lo vive. Zanja dos relatos: «subir las pensiones no le cuesta a nadie» (con deuda la factura crece; con impuestos la paga Lucía desde el primer año)
          y «lo pagan solo los jóvenes» (con deuda no paga nadie hoy; con IVA y con IRPF también pagan los pensionistas). Lo que queda abierto: cuánto
          empleo se pierde con las cotizaciones depende de un supuesto en disputa.
        </p>
        <WhoPays model={model} />
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

      <figure className="vizFigure" id="vivienda">
        <h2>
          Veinte mil viviendas públicas más al año bajan el alquiler de un contrato nuevo un {num(-hRows.pub.rent.v)} % en 2035; un tope del 10 % en la mitad
          del mercado {verb(hRows.capIn.rent.v)} a quien encuentra piso con tope y {verb(hRows.capOut.rent.v)} a quien busca fuera
        </h2>
        <p className="vizFigure__dek">
          Seis políticas de vivienda con el tamaño que dice cada fila, desde {model.policy_start}, y la inmigración como contexto. Cada casilla da el valor central y,
          debajo, el rango del 5 % al 95 % de las simulaciones; verde, mejor para quien alquila o compra. Pone a prueba tres relatos. «Construir no baja el alquiler»: lo baja, pero tarde (la obra pública tarda
          unos {num(P.retardo_obra_publica, 0)} años) y poco a poco: en 2035 suma {num(pubRun.hs_stock_k[t35h], 0)} mil viviendas, un{" "}
          {num((pubRun.hs_stock_k[t35h] / H.households_k[t35h]) * 100, 1)} % de los hogares; los jóvenes que se emancipan al bajar el alquiler (bucle B2) ocupan
          un {num(b2Share * 100, 0)} % de lo construido, y cuesta unos {num(pubCostMeur, 0)} millones al año en 2035. «El tope
          abarata el alquiler»: a quien tiene o encuentra un contrato cubierto, sí; a quien busca fuera, depende de cuántos caseros dejen el alquiler, que es el
          supuesto más disputado de la página. «Los pisos turísticos son el problema»: retirar la mitad {verb(hRows.tour.rent.v, 1)} el alquiler medio de España, porque son el {num(H.tourist_share * 100, 2)} % de las viviendas (en algunos barrios pesan mucho más). Lo que queda
          abierto: la respuesta de la oferta al tope y cuántos pisos turísticos vuelven a vivienda habitual.
        </p>
        <HousingCompare rows={hRowsList} />
        <figcaption className="vizFigure__caption">
          <span>
            Fuente: modelo de esta página sobre la{" "}
            <a href={src.ine_proh.page} target="_blank" rel="noopener noreferrer">proyección de hogares del INE</a>, la obra terminada, el parque, las
            viviendas turísticas y los alquileres del SERPAVI de la página de <a href="/visualizaciones/vivienda/">vivienda</a>, y las fichas del catálogo.
          </span>
          <span>
            Las hipotecas: limitarlas al 80 % del precio y a 4,5 veces la renta {verb(hRows.credit.price.v)} el precio en 2035 y el alquiler{" "}
            {verb(hRows.credit.rent.v, 1)} (algunos compradores pasan a alquilar); el bucle crédito-precio (R2) multiplica la caída del precio por{" "}
            {num(r2, 2)}.
          </span>
        </figcaption>
      </figure>

      <section className="vizProse" aria-label="El tope del alquiler según cada escuela">
        <p>
          <strong>El tope, según cada escuela.</strong> Con el mismo tope (rebaja del 10 % en la mitad del alquiler de mercado), en 2035:
        </p>
      </section>
      <div className="vizTable__scroll">
        <table className="sim__table">
          <thead>
            <tr>
              <th scope="col">Escuela (pisos que salen por cada 1 % de rebaja)</th>
              <th scope="col">Pisos de alquiler de mercado</th>
              <th scope="col">Contrato nuevo con tope</th>
              <th scope="col">Contrato nuevo sin tope</th>
              <th scope="col">Caso 1, con tope / sin tope, al mes</th>
            </tr>
          </thead>
          <tbody>
            {capSchools.map((sc) => (
              <tr key={sc.label}>
                <th scope="row">
                  {sc.label} <span className="sim__muted">({num(sc.value, 1)})</span>
                </th>
                <td>{Math.round(sc.stock).toLocaleString("es-ES", { useGrouping: "always" })} mil</td>
                <td>{num(sc.cov * 100)} %</td>
                <td>{sc.unc >= 0 ? "+" : "−"}{num(Math.abs(sc.unc * 100))} %</td>
                <td>
                  {num(sc.p1cov, 0)} € / {sc.p1unc >= 0 ? "+" : "−"}{num(Math.abs(sc.p1unc), 0)} €
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>


      <section className="vizProse" id="escenarios" aria-labelledby="escenarios-title">
        <h2 id="escenarios-title">Escenarios: las preguntas más buscadas, con su respuesta</h2>
        <p>
          Cada escenario tiene su página con el resultado y su rango, los casos tipo, las formas de pagarlo, las fichas de evidencia y las votaciones del
          Congreso, y un botón que lo abre aquí. <a href={withBasePath(SCENARIOS_PATH)}>Todos los escenarios</a>.
        </p>
        <ul className="scn__links">
          {SCENARIOS.map((sc) => (
            <li key={sc.slug}><a href={withBasePath(scenarioPath(sc))}>{sc.question}</a></li>
          ))}
        </ul>
      </section>

      <section className="vizProse" id="preguntas" aria-labelledby="preguntas-title">
        <h2 id="preguntas-title">Preguntas frecuentes</h2>
        {faqs.map((f) => (
          <div key={f.q} className="scn__faq">
            <h3>{f.q}</h3>
            <p>{f.a}</p>
          </div>
        ))}
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
        <p>
          <strong>Vivienda.</strong> La línea base son los hogares de la{" "}
          <a href={src.ine_proh.page} target="_blank" rel="noopener noreferrer">proyección del INE</a> (hasta {H.households_source_last_year - 1}; después crecen con la
          población del Ageing Report) y la obra terminada constante en {num(H.completions_free_k + H.completions_protected_k, 0)} mil viviendas al año, que es un
          supuesto: nadie publica una proyección oficial de obra. El parque parte del Censo 2021 más lo terminado desde entonces ({num(H.stock_k / 1000, 1)}{" "}
          millones de viviendas, {num(H.stock_k / H.households_k[0], 2)} por hogar porque hay vacías y secundarias). El alquiler de mercado se mueve con las
          viviendas por hogar; los jóvenes que viven con sus padres ({num(H.at_home_share_2534 * 100, 0)} % de los de 25 a 34 años) se emancipan cuando baja; el
          precio sigue al alquiler y al crédito, y el crédito sigue al precio. El tope rebaja los contratos cubiertos, saca del alquiler una parte de los pisos
          y sube los no cubiertos; quien ya tiene contrato se acerca al mercado al renovarlo. La vivienda pública se paga en los dos años antes de terminarse y
          recupera su alquiler social; ese coste entra en «¿Cómo se paga?».
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
            Vivienda: un solo mercado nacional (el alquiler medio de España), sin barrios ni comunidades; el tope se aplica a la parte del alquiler que elijas.
            Los pisos que salen del alquiler por el tope se venden o se usan de otra forma sin cambiar el parque total. Los límites de LTP y LTI se tratan como
            independientes. La obra pública no tiene multiplicador sobre el PIB ni crea empleo en el modelo. El esfuerzo por edad aplica el cambio del alquiler
            a todo el gasto en vivienda de cada celda.
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
          <li>
            Cuántos caseros dejan el alquiler con un tope: los estudios de Cataluña y San Francisco no coinciden. Elige la escuela en «Supuestos en disputa».
          </li>
          <li>
            Qué pasa en un barrio concreto: el modelo es nacional. En los barrios con muchos pisos turísticos o mucha demanda el efecto de cada política puede ser
            varias veces mayor.
          </li>
          <li>Los efectos en sanidad, dependencia, empleo o educación: llegarán en los siguientes módulos.</li>
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
          Modelo generado el {String(model.generated_at).slice(0, 10)}. Siguiente módulo: empleo e inmigración (salario mínimo, jornada, cuota de
          autónomos e inmigración como contexto), que une las cotizaciones con los hogares.
        </p>
      </section>
    </main>
  );
}

