import { NAMES } from "./common.mjs";
import { num, thousands } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;

function facts(data) {
  const h = data.headline;
  const crisis = data.cycle?.episodes?.[0];
  const covid = data.cycle?.episodes?.[1];
  const row = (ep, area) => ep?.rows.find((r) => r.area === area) || {};
  const adj = data.contract_adjustment?.[0];
  const losses = data.sector_losses_es;
  const wp = data.wages_productivity;
  const it = data.intermittency;
  return { h, crisis, covid, row, adj, losses, wp, it, g: h.productivity_growth_pct };
}

export function Summary({ data }) {
  const { h, crisis, covid, row, adj, losses, wp, it, g } = facts(data);
  return (
    <section className="card vizProse" id="resumen" aria-labelledby="resumen-title">
      <h2 id="resumen-title">En seis datos</h2>
      <p>
        <strong>La hipótesis:</strong> el paro de España es estructural, no cíclico. Desde 1980 ha sido aproximadamente el doble de la media
        europea en casi todos los ciclos, y la productividad por hora apenas ha crecido desde 1995 frente a países comparables.
      </p>
      <ol>
        <li>
          <strong>Alto y persistente.</strong> Desde {h.hypothesis_from}, el paro español ha sido de media {num(h.ratio_mean_since, 2)} veces el
          europeo (UE-15) y ha superado 1,5 veces esa media en {h.years_ratio_ge_1_5} de {h.years_since} años. Hoy: {pct(h.es_last)} frente a{" "}
          {pct(h.eu27_last)} en la UE-27. <a href="#paro">Ver gráfico</a>
        </li>
        <li>
          <strong>Pero no siempre ni «el doble».</strong> Hasta 1975 era similar al europeo; solo en {h.years_ratio_ge_2} de {h.years_since} años
          llegó al doble, y en {h.ratio_lowest_since.year} bajó a {num(h.ratio_lowest_since.value, 2)} veces. <a href="#ratio">Ver gráfico</a>
        </li>
        {crisis ? (
          <li>
            <strong>En la Gran Recesión, el empleo cayó el doble que el PIB.</strong> En {crisis.from}–{crisis.to} el PIB cayó un {num(-row(crisis, "ESP").gdp)} %
            y el empleo un {num(-row(crisis, "ESP").employment)} % (Italia: {num(-row(crisis, "ITA").gdp)} % y {num(-row(crisis, "ITA").employment)} %).
            {adj ? ` Se perdieron ${thousands(-adj.temporal)} de empleos temporales frente a ${thousands(-adj.indefinido)} indefinidos.` : ""}
            {losses ? ` La construcción explica el ${num(losses.construction_share_of_loss, 0)} % de los empleos perdidos.` : ""}
            {covid ? ` Con los ERTE de 2020, el empleo cayó un ${num(-row(covid, "ESP").employment)} % con una caída del PIB del ${num(-row(covid, "ESP").gdp)} %.` : ""}{" "}
            <a href="#ciclo">Ver gráfico</a>
          </li>
        ) : null}
        <li>
          <strong>Menos temporales, más fijos discontinuos.</strong> La temporalidad bajó del {pct(h.temp_es_2021)} (2021) al {pct(h.temp_es_last)}{" "}
          ({h.temp_last_year}).
          {it ? ` Los fijos discontinuos trabajando pasaron de ${num(it.annual_affiliates.find((p) => p.year === 2019)?.value / 1000, 0)} mil (2019) a ${num(it.annual_affiliates.at(-1).value / 1000, 0)} mil (${it.annual_affiliates.at(-1).year}), y los inscritos sin actividad llegaron a ${num(it.inactive_job_seekers.at(-1).value / 1000, 0)} mil en ${it.inactive_job_seekers.at(-1).year}.` : ""}{" "}
          <a href="#temporalidad">Ver gráfico</a>
        </li>
        <li>
          <strong>Productividad y salarios casi parados.</strong> La productividad por hora creció un {num(g.ESP)} % desde {h.productivity_base},
          frente al {num(g.EU27)} % de la UE-27 (Italia: {num(g.ITA)} %).
          {wp?.ESP ? ` El salario real por asalariado, un ${num(wp.ESP.wage.at(-1).value - 100)} % (UE-27: ${num(wp.EU27.wage.at(-1).value - 100)} %).` : ""}{" "}
          <a href="#productividad">Ver gráfico</a>
        </li>
        {data.capacity && data.labour_policy ? (
          <li>
            <strong>Lo que queda en el bolsillo y lo que se gasta.</strong> Descontada la inflación, el neto de un soltero con el salario medio
            cambió un {num(data.capacity.net_growth_first_segment.net_pct)} % entre {data.capacity.net_growth_first_segment.from} y{" "}
            {data.capacity.net_growth_first_segment.to}; el {pct(data.capacity.in_work_poverty.ESP.at(-1).value)} de los ocupados está en riesgo de
            pobreza (UE: {pct(data.capacity.in_work_poverty.EU27.at(-1).value)}). España dedica al paro más PIB que la UE pero menos dinero por
            persona que quiere trabajar, sobre todo en servicios de empleo. <a href="#relato-gasto">Ver gráfico</a>
          </li>
        ) : null}
      </ol>
      <p>
        <strong>Veredicto:</strong> la hipótesis se sostiene en lo esencial, pero el paro español es a la vez estructural y muy cíclico. Detalle
        en las <a href="#conclusion">conclusiones</a>; términos técnicos, en el <a href="#glosario">glosario</a>.
      </p>
      <nav aria-label="Capítulos">
        <p style={{ margin: 0 }}>
          Capítulos: <a href="#cap-cuanto">1. Cuánto paro</a> · <a href="#cap-ciclo">2. Estructural o cíclico</a> ·{" "}
          <a href="#cap-causas">3. Qué hay detrás</a> · <a href="#cap-calidad">4. Qué empleo</a> ·{" "}
          <a href="#cap-productividad">5. Productividad y salarios</a> · <a href="#cap-bolsillo">6. Bolsillo y gasto</a>
        </p>
      </nav>
    </section>
  );
}

export function Conclusion({ data }) {
  const { h, crisis, row, g, wp } = facts(data);
  const lt = data.long_term;
  const fs = data.firm_size;
  const ed = data.education;
  const lastOf = (pts) => pts?.at(-1)?.value;
  return (
    <section className="card vizProse" id="conclusion" aria-labelledby="conclusion-title">
      <h2 id="conclusion-title">Conclusiones: dónde acierta la hipótesis y dónde falla</h2>
      <h3>Se sostiene</h3>
      <ul>
        <li>
          El paro español es persistentemente más alto que el europeo: {num(h.ratio_mean_since, 2)} veces de media desde {h.hypothesis_from} y por
          encima de 1,5 veces en {h.years_ratio_ge_1_5} de {h.years_since} años. La Comisión Europea estima un paro estructural que no ha bajado del{" "}
          {pct(h.nawru_min_since.value)}.
        </li>
        <li>
          La productividad por hora creció un {num(g.ESP)} % en treinta años, menos que la UE-27 ({num(g.EU27)} %), Alemania ({num(g.DEU)} %),
          Francia ({num(g.FRA)} %) y Portugal ({num(g.PRT)} %). España pasó de estar por encima de la media europea en productividad por hora a
          estar por debajo.
        </li>
        {data.capacity ? (
          <li>
            Y se nota en el bolsillo: descontada la inflación, el neto de un trabajador con el salario medio cambió un{" "}
            {num(data.capacity.net_growth_first_segment.net_pct)} % entre {data.capacity.net_growth_first_segment.from} y{" "}
            {data.capacity.net_growth_first_segment.to}, y el {pct(data.capacity.in_work_poverty.ESP.at(-1).value)} de los ocupados vive en riesgo de
            pobreza, más que en la UE ({pct(data.capacity.in_work_poverty.EU27.at(-1).value)}).
          </li>
        ) : null}
      </ul>
      <h3>Falla o hay que matizarla</h3>
      <ul>
        <li>
          <strong>No es «el doble en casi todos los ciclos».</strong> Llegó al doble en {h.years_ratio_ge_2} de {h.years_since} años. En el auge de
          2006 la distancia casi desapareció ({num(h.ratio_lowest_since.value, 2)} veces).
        </li>
        <li>
          <strong>No es un rasgo permanente del país.</strong> Entre 1960 y 1975 el paro español fue similar al europeo
          ({pct(h.es_mean_1960_1974)} de media en 1960–1974). La brecha nace con las crisis de los setenta y ochenta.
        </li>
        <li>
          <strong>No es solo estructural: el ciclo es enorme.</strong>{" "}
          {crisis ? `En ${crisis.from}–${crisis.to} el empleo cayó el doble que el PIB (${num(-row(crisis, "ESP").employment)} % frente a ${num(-row(crisis, "ESP").gdp)} %), por la dualidad de contratos y la burbuja de la construcción.` : ""}{" "}
          Con los ERTE, en 2020, pasó lo contrario. Las instituciones del mercado de trabajo cambian cuánto paro deja cada crisis.
        </li>
        <li>
          <strong>En productividad, Italia lo ha hecho peor</strong> (+{num(g.ITA)} %), y tiene bastante menos paro: productividad baja y paro
          alto no van necesariamente juntos.
        </li>
      </ul>
      <h3>Lo que apunta en contra de explicaciones habituales</h3>
      <ul>
        {lt ? (
          <li>
            El porcentaje de parados de larga duración ({pct(lastOf(lt.share.ESP))}) está en la media europea ({pct(lastOf(lt.share.EU27))}) y muy
            por debajo de Italia ({pct(lastOf(lt.share.ITA))}).
          </li>
        ) : null}
        {fs ? (
          <li>
            Italia ({pct(fs.shares.ITA["0-9"])}) y Portugal ({pct(fs.shares.PRT["0-9"])}) tienen más empleo en microempresas que España (
            {pct(fs.shares.ESP["0-9"])}) y menos paro.
          </li>
        ) : null}
        {ed ? (
          <li>
            Portugal e Italia tienen tantos adultos con estudios hasta la ESO como España (
            {pct(lastOf(ed.population["ED0-2"].PRT))}, {pct(lastOf(ed.population["ED0-2"].ITA))} y {pct(lastOf(ed.population["ED0-2"].ESP))}) y
            menos paro.
          </li>
        ) : null}
        <li>La cuña fiscal española está en la media de la UE y por debajo de la alemana, la francesa y la italiana.</li>
        {data.labour_policy ? (
          <li>
            «España gasta poco en políticas de empleo» depende de cómo se mida: es mucho en % del PIB y poco por persona que quiere trabajar,
            sobre todo en servicios de empleo ({num(data.labour_policy.rows.find((r) => r.area === "ESP").pps_services, 0)} PPS frente a{" "}
            {num(data.labour_policy.rows.find((r) => r.area === "EU27").pps_services, 0)} en la UE).
          </li>
        ) : null}
      </ul>
      <h3>Qué queda abierto</h3>
      <ul>
        <li>
          Si la reforma de 2022 ha reducido la precariedad o la ha cambiado de etiqueta: la temporalidad cayó mucho, pero los fijos discontinuos
          sin actividad crecieron y la estadística oficial que los separaba dejó de publicarse en el Anuario de 2025.
        </li>
        <li>Cuánto pesa cada causa: medirlo exige modelos y microdatos, no series agregadas.</li>
        <li>Si el gasto en políticas activas funciona: la base europea mide cuánto se gasta, no qué consigue cada programa.</li>
        {wp?.ESP ? <li>Por qué la productividad no despega aunque el empleo crece: estos datos lo describen, no lo explican.</li> : null}
      </ul>
      <p style={{ margin: 0, color: "var(--viz-muted)" }}>Países: {["DEU", "FRA", "ITA", "PRT"].map((a) => NAMES[a]).join(", ")} y medias europeas.</p>
    </section>
  );
}

const TERMS = [
  ["Tasa de paro (EPA)", "Parados sobre la población activa según la Encuesta de Población Activa del INE: personas que no trabajan, buscan empleo activamente y podrían empezar en dos semanas. Es la definición de la OIT y la que se compara con Europa."],
  ["Paro registrado (SEPE)", "Demandantes de empleo inscritos en las oficinas públicas que cumplen los criterios administrativos de parado. Excluye, entre otros, a los demandantes con relación laboral. Se publica cada mes, pero no es comparable entre países."],
  ["Población activa", "Personas que trabajan o buscan trabajo. Quien no busca (estudiantes, jubilados, desanimados) es inactivo y no cuenta como parado."],
  ["NAWRU", "Siglas en inglés de la tasa de paro que no acelera los salarios. La Comisión Europea la estima con un modelo como aproximación al paro estructural; no se observa directamente."],
  ["Paro estructural y cíclico", "El estructural es el que persiste aunque la economía vaya bien (desajustes de formación, instituciones, sectores); el cíclico, el que sube en las recesiones y baja en los auges."],
  ["Histéresis", "Cuando el paro de una crisis se queda «pegado»: quien pasa mucho tiempo parado pierde contactos y habilidades, y el paro estructural sube."],
  ["Paro de larga duración", "Parados que llevan doce meses o más buscando empleo."],
  ["Contrato temporal", "Contrato con fecha de fin. Desde la reforma de 2022 solo puede usarse por circunstancias de la producción o para sustituir a otro trabajador."],
  ["Fijo discontinuo", "Contrato indefinido para trabajos que se repiten de forma intermitente (campañas, temporadas, contratas). Entre llamamientos el trabajador no trabaja ni cobra salario, causa baja en la Seguridad Social y puede inscribirse como demandante de empleo «con relación laboral»."],
  ["ERTE", "Expediente de regulación temporal de empleo: la empresa suspende contratos o reduce jornada sin despedir y el trabajador cobra una prestación. Se usó masivamente en 2020."],
  ["Dualidad", "Mercado de trabajo con dos tipos de trabajadores: fijos, caros de despedir, y temporales, baratos de despedir. Los ajustes recaen en los segundos."],
  ["Cuña fiscal", "Diferencia entre lo que cuesta un trabajador a la empresa y lo que cobra neto: IRPF más cotizaciones del trabajador y de la empresa, en porcentaje del coste laboral."],
  ["Salario mínimo frente al mediano", "Salario mínimo legal dividido por el salario del trabajador a tiempo completo que está justo en medio de la distribución."],
  ["Productividad por hora", "PIB en volumen (descontada la inflación) dividido por las horas trabajadas en la economía."],
  ["Paridad de poder de compra (PPA)", "Tipo de cambio que iguala lo que cuesta la misma cesta de bienes en cada país; permite comparar niveles de producción entre países."],
  ["Remuneración real por asalariado", "Sueldo bruto más cotizaciones de la empresa por asalariado, descontada la inflación del consumo."],
  ["NUTS 2", "Nivel de regiones de la UE; en España coincide con las comunidades y ciudades autónomas."],
  ["Ruptura de serie", "Cambio de método o de definición que impide comparar directamente los datos de antes y de después. Aquí se marcan y se solapan, nunca se empalman."],
];

export function Glossary() {
  return (
    <section className="card vizProse" id="glosario" aria-labelledby="glosario-title">
      <h2 id="glosario-title">Glosario</h2>
      <dl style={{ display: "grid", gap: 8, margin: 0 }}>
        {TERMS.map(([term, def]) => (
          <div key={term}>
            <dt style={{ fontWeight: 700 }}>{term}</dt>
            <dd style={{ margin: 0 }}>{def}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
