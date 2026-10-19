import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import EmpleoChart from "./EmpleoChart";
import MonthlyLine from "./MonthlyLine";
import { CategoryBars, Chapter, DataTable, Fig } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, back, last, sources } from "./common.mjs";
import { fmt, num } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;

export default function ChapterCalidad({ data, epaBreaks, reform, children }) {
  const h = data.headline;
  const S = sources(data);

  const t = data.temporary;
  const tempMax = Math.ceil(Math.max(...Object.values(t.eurostat).flatMap((rows) => rows.map((p) => p.value))) / 5) * 5;
  const temp = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: t.eurostat.ESP },
    { id: "EU27", label: "UE-27", color: C.ref, points: t.eurostat.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: t.eurostat[area] })),
  ];
  const epaContracts = [
    { id: "temporal", label: "Con contrato temporal", shortLabel: "Temporales", color: C.blue, emphasis: true, points: t.epa_temporal_share },
    { id: "discontinuo", label: "Fijos discontinuos (indefinidos)", shortLabel: "Fijos discontinuos", color: C.orange, points: t.epa_discontinuo_share },
  ];
  const breakYears = Object.entries(t.eurostat_es_flags || {})
    .filter(([, flag]) => flag.includes("b"))
    .map(([year]) => year);
  const reformMarks = [...reform("reform_2012", "Reforma 2012"), ...reform("reform_2022", "Reforma 2022")];
  const tempDrop = h.temp_es_2021 - h.temp_es_last;
  const discontRise = h.discont_last - h.discont_2021;

  const y = data.youth;
  const youth = [
    { id: "es_h", label: "España (serie histórica 1993–2020)", shortLabel: "España, hist.", color: C.aqua, noEndLabel: true, points: y.historical.ESP },
    { id: "eu_h", label: "UE-27 (serie histórica)", shortLabel: "UE-27, hist.", color: C.yellow, noEndLabel: true, points: y.historical.EU27 },
    { id: "es", label: "España (serie vigente, desde 2003)", shortLabel: "España", color: C.blue, emphasis: true, points: y.current.ESP },
    { id: "eu", label: "UE-27 (serie vigente)", shortLabel: "UE-27", color: C.ref, points: y.current.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: y.current[area] })),
  ];

  const rg = data.regions;
  const regionBars = rg
    ? [...rg.spain.map((r) => ({ id: r.code, label: r.name, value: r.unemployment })), { id: "EU27", label: "Media UE-27", value: rg.eu27_rate, color: C.ref }].sort((a, b) => b.value - a.value)
    : [];
  const best = rg ? rg.spain.at(-1) : null;
  const worstMain = rg ? rg.spain.find((r) => !["ES63", "ES64"].includes(r.code)) : null;
  const disp = rg?.dispersion;
  const dispLess = disp?.ESP && disp?.ITA && last(disp.ESP).value < last(disp.ITA).value;
  const dispSeries = disp
    ? [
        { id: "ESP", label: "España", color: C.blue, emphasis: true, points: disp.ESP },
        { id: "EU27", label: "UE-27 (entre todas sus regiones)", shortLabel: "UE-27", color: C.ref, points: disp.EU27 },
        ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: disp[area] })),
      ]
    : null;

  return (
    <>
      <Chapter id="cap-calidad" kicker="Capítulo 4" title="Qué empleo: temporalidad, jóvenes y territorios">
        <p>
          No basta con contar parados. La mitad del problema español ha sido la calidad del empleo: contratos cortos que se encadenan, jóvenes que
          entran y salen del paro y diferencias grandes entre comunidades.
        </p>
      </Chapter>

      <Fig
        id="temporalidad"
        title={`La temporalidad bajó del ${pct(h.temp_es_2021)} al ${pct(h.temp_es_last)} tras la reforma de 2022, y los fijos discontinuos casi se duplicaron`}
        dek={`Tras décadas con la temporalidad más alta de este grupo de países (máximo del ${pct(h.temp_es_max.value)} en ${h.temp_es_max.year}), España queda en ${h.temp_last_year} a ${num(h.temp_es_last - h.temp_eu_last)} puntos de la UE-27 (${pct(h.temp_eu_last)}). La caída de ${num(tempDrop)} puntos desde 2021 no se explica solo por el cambio de etiqueta: los fijos discontinuos, que cuentan como indefinidos, subieron ${num(discontRise)} puntos (de ${num(h.discont_k_2021, 0)} mil a ${num(h.discont_k_last, 0)} mil asalariados, según la EPA).`}
        legend={[{ id: "ESP", label: "España", color: C.blue }, { id: "EU27", label: "UE-27", color: C.ref }, PEER_LEGEND]}
        sources={[S.eurostat("lfsa_etpgan"), S.ine]}
        notes={[
          breakYears.length ? `Eurostat marca ruptura de serie para España en ${breakYears.join(", ")}; desde 2021 la definición difiere de la anterior (reglamento IESS).` : "",
          "Eurostat: asalariados de 15 a 64 años. INE: asalariados de 16 y más años, media de los cuatro trimestres de cada año completo.",
        ].filter(Boolean)}
        table={<SeriesTable series={[...temp, ...epaContracts.map((s) => ({ ...s, label: `EPA (INE): ${s.label}` }))]} />}
        explain={{
          what: "Qué parte de los asalariados tiene un contrato con fecha de fin (izquierda) y, a la derecha, temporales y fijos discontinuos en España según la EPA.",
          read: "La reforma de 2022 limitó los contratos temporales a causas concretas y empujó a usar el fijo discontinuo para trabajos que se repiten (campañas, temporadas). La línea azul de la derecha cae; la naranja sube, pero mucho menos.",
          not: "Un fijo discontinuo no trabaja ni cobra entre llamamientos: un contrato indefinido puede esconder la misma intermitencia que antes tenía un temporal. La EPA no mide cuántos días al año trabaja cada uno ni cuántos contratos indefinidos terminan en el periodo de prueba.",
        }}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Asalariados con contrato temporal
              <span>% del total de asalariados, Eurostat</span>
            </h3>
            <TimeSeriesChart series={back(temp)} xMin={1995} xMax={h.last_year} yMax={tempMax} height={260} annotations={reformMarks} ariaLabel="Porcentaje de asalariados temporales, España frente a la UE" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Temporales y fijos discontinuos en España
              <span>% del total de asalariados, EPA del INE</span>
            </h3>
            <TimeSeriesChart series={epaContracts} xMin={2002} xMax={h.last_year} yMax={tempMax} height={260} annotations={reformMarks} ariaLabel="Temporales y fijos discontinuos en España, porcentaje de asalariados" />
          </div>
        </div>
      </Fig>

      {children}

      <Fig
        id="jovenes"
        title={`El paro de los jóvenes activos es del ${pct(h.youth_es_last)} en España y del ${pct(h.youth_eu_last)} en la UE-27`}
        dek={`Menores de 25 años (15–24). Desde 2003 ha sido de media ${num(h.youth_ratio_mean, 2)} veces el europeo y llegó al ${pct(h.youth_es_max.value)} en ${h.youth_es_max.year}.`}
        legend={youth.filter((s) => s.color !== C.peer).concat([PEER_LEGEND])}
        sources={[S.eurostat("une_rt_a"), S.eurostat("une_rt_a_h")]}
        notes={["La serie histórica de Eurostat (cerrada en 2020) y la vigente se solapan para que se vea la ruptura."]}
        table={<SeriesTable series={youth} />}
        explain={{
          what: "El paro de los menores de 25 años que trabajan o buscan trabajo.",
          read: "El paro juvenil amplifica el general: sube más en las crisis porque los jóvenes son los últimos en entrar y suelen tener contratos temporales, los primeros en no renovarse.",
          not: "Se calcula sobre los jóvenes activos, no sobre todos: muchos estudian. Un 25 % de paro juvenil no significa que uno de cada cuatro jóvenes esté parado; la proporción sobre toda la población joven es mucho menor.",
        }}
      >
        <TimeSeriesChart series={back(youth)} xMin={1993} xMax={h.last_year} annotations={epaBreaks.filter((b) => b.year >= 1993)} ariaLabel="Paro juvenil, España frente a la UE" />
      </Fig>

      {rg ? (
        <Fig
          id="regiones"
          title={`${rg.spain_above_eu === rg.spain.length ? `Las ${rg.spain.length}` : `${rg.spain_above_eu} de las ${rg.spain.length}`} comunidades y ciudades autónomas tienen más paro que la media de la UE (${pct(rg.eu27_rate)}); ${rg.spanish_in_top20} de las 20 regiones con más paro de la UE son españolas`}
          dek={`En ${rg.year}, del ${pct(best.unemployment)} de ${best.name} al ${pct(worstMain.unemployment)} de ${worstMain.name} (${pct(rg.spain[0].unemployment)} en ${rg.spain[0].name}). ${dispLess ? "Pero la dispersión entre comunidades es moderada: menor que entre las regiones de Italia. El paro alto es un rasgo nacional, no de unas pocas comunidades." : ""}`}
          sources={[S.eurostat("lfst_r_lfu3rt"), S.eurostat("lfst_r_lfe2emprt"), S.eurostat("lfst_r_lmdur")]}
          notes={[
            `Regiones NUTS 2 de la UE-27 (${rg.eu_regions} con dato en ${rg.year}); en España coinciden con las comunidades y ciudades autónomas. Las regiones ultraperiféricas francesas figuran como regiones de la UE.`,
            "Dispersión: coeficiente de variación de las tasas de paro regionales de cada país, que publica Eurostat.",
          ]}
          table={
            <>
              <DataTable
                columns={[
                  { key: "name", label: "Comunidad" },
                  { key: "unemployment", label: `Paro ${rg.year}`, format: (v) => fmt(v) },
                  { key: "employment", label: `Empleo 20–64 ${rg.year}`, format: (v) => fmt(v) },
                  { key: "unemployment_2007", label: "Paro 2007", format: (v) => fmt(v) },
                  { key: "unemployment_2013", label: "Paro 2013", format: (v) => fmt(v) },
                ]}
                rows={rg.spain.map((r) => ({ ...r, id: r.code }))}
              />
              <DataTable
                caption={`Región con menos y con más paro de cada país, ${rg.year}`}
                columns={[
                  { key: "area", label: "País", format: (v) => NAMES[v] || v },
                  { key: "min", label: "Menos paro", format: (v) => `${v.name} (${fmt(v.value)})` },
                  { key: "max", label: "Más paro", format: (v) => `${v.name} (${fmt(v.value)})` },
                  { key: "regions", label: "Regiones" },
                ]}
                rows={Object.entries(rg.ranges).map(([area, r]) => ({ ...r, id: area, area }))}
              />
              <DataTable
                caption={`Las 20 regiones de la UE con más paro, ${rg.year}`}
                columns={[
                  { key: "name", label: "Región" },
                  { key: "value", label: "Paro", format: (v) => fmt(v) },
                ]}
                rows={rg.eu_top20.map((r) => ({ ...r, id: r.code, name: r.spanish ? `${r.name} (España)` : r.name }))}
              />
              {dispSeries ? <SeriesTable series={dispSeries} caption="Ver la dispersión regional por país" /> : null}
            </>
          }
          explain={{
            what: "La tasa de paro de cada comunidad autónoma y, abajo, cuánto se diferencian entre sí las regiones de cada país.",
            read: "Incluso la comunidad con menos paro está por encima de la media europea. A la vez, las diferencias internas de España son menores que las de Italia: el problema se reparte por todo el territorio, con más intensidad en el sur y en Ceuta y Melilla.",
            not: "Las tasas regionales de la EPA tienen más error de muestreo que la nacional (sobre todo en las comunidades pequeñas y en Ceuta y Melilla), y no recogen el paro de quien trabaja en otra comunidad.",
          }}
        >
          <h3 className="vizPanelTitle">
            Tasa de paro por comunidad autónoma, {rg.year}
            <span>% de la población activa de 15 a 74 años</span>
          </h3>
          <CategoryBars rows={regionBars} highlight={rg.spain.map((r) => r.code)} label="Tasa de paro por comunidad autónoma" />
          {dispSeries ? (
            <>
              <h3 className="vizPanelTitle">
                Dispersión del paro entre regiones de cada país
                <span>Coeficiente de variación, %</span>
              </h3>
              <TimeSeriesChart series={back(dispSeries)} xMin={1999} xMax={rg.year} height={240} ariaLabel="Dispersión regional del paro por país" />
            </>
          ) : null}
        </Fig>
      ) : null}
    </>
  );
}

export { last };

export function IntermittencyFigure({ data, reform }) {
  const it = data.intermittency;
  if (!it) return null;
  const S = sources(data);
  const src = data.sources;
  const ss = { label: `Seguridad Social, afiliación y días cotizados (consultado ${String(src.seg_social_pxweb?.retrieved_at || "").slice(0, 10)})`, href: src.seg_social_pxweb.page };
  const mites = { label: `Ministerio de Trabajo, Anuario MLR-18 y MLR-25 (consultado ${String(src.mites_anuario?.retrieved_at || "").slice(0, 10)})`, href: src.mites_anuario.page };
  const aff = it.annual_affiliates;
  const a2019 = aff.find((p) => p.year === 2019);
  const aLast = aff.at(-1);
  const seek = it.inactive_job_seekers;
  const sLast = seek.at(-1);
  const sFirst = seek[0];
  const shareLast = it.inactive_share_estimate.at(-1);
  const aSame = aff.find((p) => p.year === sLast.year) || aLast;
  const dFd = it.days_per_contributor.fd.at(-1);
  const dInd = it.days_per_contributor.indefinido.at(-1);
  const swingLast = it.seasonal_swing[String(aLast.year)];
  const monthly = it.monthly_affiliates.map((m) => ({ year: Number(m.month.slice(0, 4)) + (Number(m.month.slice(5)) - 0.5) / 12, value: m.fd / 1000 }));
  const yearlySeries = [
    { id: "aff", label: "Fijos discontinuos en alta (trabajando), media anual", shortLabel: "En alta", color: C.blue, emphasis: true, points: aff.filter((p) => p.year >= 2015).map((p) => ({ year: p.year, value: p.value / 1000 })) },
    { id: "seek", label: "Fijos discontinuos inscritos como demandantes sin actividad, media anual", shortLabel: "Inactivos inscritos", color: C.orange, points: seek.map((p) => ({ year: p.year, value: p.value / 1000 })) },
  ];
  return (
    <Fig
      id="intermitencia"
      title={`En ${sLast.year}, ${num(sLast.value / 1000, 0)} mil fijos discontinuos estaban de media sin actividad e inscritos como demandantes de empleo, frente a ${num(aSame.value / 1000, 0)} mil trabajando`}
      dek={`Los fijos discontinuos en alta en la Seguridad Social pasaron de ${num(a2019.value / 1000, 0)} mil de media en 2019 a ${num(aLast.value / 1000, 0)} mil en ${aLast.year}. Los inscritos sin actividad, de ${num(sFirst.value / 1000, 0)} mil en ${sFirst.year} a ${num(sLast.value / 1000, 0)} mil en ${sLast.year}. Cuando trabajan, cotizan ${num(dFd.value)} días al mes de media, frente a ${num(dInd.value)} de un indefinido ordinario (${dFd.year}).`}
      legend={yearlySeries}
      sources={[ss, mites]}
      notes={[
        `Estimación nuestra, solo orientativa: inactivos inscritos / (inactivos inscritos + en alta) ≈ ${num(shareLast.value, 0)} % en ${shareLast.year}. Mezcla dos registros distintos: la afiliación es solo del Régimen General y no todos los fijos discontinuos sin actividad se inscriben en el SEPE.`,
        "El Anuario de 2025 del Ministerio de Trabajo ya no separa a los fijos discontinuos dentro de los demandantes no parados (los integra en «otros ocupados»): no hay cifra oficial publicada para 2025.",
        `Contratos fijos discontinuos registrados: ${it.contracts_fd.map((p) => `${num(p.value / 1e6, 2)} millones en ${p.year}`).join(", ")}.`,
      ]}
      table={
        <>
          <DataTable
            columns={[
              { key: "year", label: "Año" },
              { key: "aff", label: "En alta (media)", format: (v) => (v == null ? "" : num(v, 0)) },
              { key: "seek", label: "Inactivos inscritos (media)", format: (v) => (v == null ? "" : num(v, 0)) },
              { key: "share", label: "Estimación % inactivos", format: (v) => (v == null ? "" : fmt(v)) },
              { key: "dfd", label: "Días/mes fijo discontinuo", format: (v) => (v == null ? "" : num(v)) },
              { key: "dind", label: "Días/mes indefinido", format: (v) => (v == null ? "" : num(v)) },
              { key: "swing", label: "Mes máx./mín.", format: (v) => (v == null ? "" : `×${num(v, 2)}`) },
            ]}
            rows={aff
              .filter((p) => p.year >= 2019)
              .map((p) => ({
                id: p.year,
                year: p.year,
                aff: p.value,
                seek: seek.find((q) => q.year === p.year)?.value,
                share: it.inactive_share_estimate.find((q) => q.year === p.year)?.value,
                dfd: it.days_per_contributor.fd.find((q) => q.year === p.year)?.value,
                dind: it.days_per_contributor.indefinido.find((q) => q.year === p.year)?.value,
                swing: it.seasonal_swing[String(p.year)]?.max_over_min,
              }))
              .reverse()}
          />
          <DataTable
            caption="Ver la afiliación mensual de fijos discontinuos"
            columns={[
              { key: "month", label: "Mes" },
              { key: "fd", label: "Afiliados medios", format: (v) => num(v, 0) },
              { key: "share", label: "% del Régimen General", format: (v) => fmt(v, "pct", 2) },
            ]}
            rows={[...it.monthly_affiliates].reverse().map((m) => ({ ...m, id: m.month }))}
          />
        </>
      }
      explain={{
        what: "Cuántos fijos discontinuos trabajan cada mes (dados de alta en la Seguridad Social) y cuántos, en los meses sin llamamiento, se inscriben como demandantes de empleo.",
        read: `La línea mensual sube en temporada y baja fuera de ella: en ${aLast.year} el mes con más fijos discontinuos trabajando tuvo ${num(swingLast.max_over_min, 2)} veces los del mes con menos. Desde 2022 la cifra se multiplicó porque muchos contratos que antes eran temporales pasaron a esta modalidad.`,
        not: "No mide los días trabajados al año por persona: eso exige los historiales individuales (Muestra Continua de Vidas Laborales), que no son públicos sin solicitud. Tampoco dice cuántos fijos discontinuos sin actividad no se inscriben.",
      }}
    >
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Fijos discontinuos: trabajando e inactivos inscritos
            <span>Miles de personas, media anual</span>
          </h3>
          <EmpleoChart series={yearlySeries} unit="thousands" xMin={2015} xMax={aLast.year} height={260} annotations={reform("reform_2022", "Reforma 2022")} ariaLabel="Fijos discontinuos en alta e inactivos inscritos" />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Fijos discontinuos en alta cada mes
            <span>Miles de afiliados medios, Régimen General</span>
          </h3>
          <MonthlyLine points={monthly} color={C.blue} />
        </div>
      </div>
    </Fig>
  );
}
