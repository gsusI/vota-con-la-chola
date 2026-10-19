import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import { CategoryBars, Chapter, DataTable, Fig } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, at, back, last, sources } from "./common.mjs";
import { fmt, num } from "./format.mjs";
import { WedgeBars } from "./sections";

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const SIZE_LABELS = { "0-9": "Micro (0–9)", "10-19": "10–19", "20-49": "20–49", "50-249": "Medianas (50–249)", GE250: "Grandes (250 o más)" };
const AREAS = ["ESP", "PRT", "ITA", "EU27", "FRA", "DEU"];

export default function ChapterCausas({ data, events }) {
  const h = data.headline;
  const S = sources(data);

  // Long-term unemployment
  const lt = data.long_term;
  const ltSeries = lt
    ? [
        { id: "es_h", label: "España (serie histórica 1996–2020)", shortLabel: "España, hist.", color: C.aqua, noEndLabel: true, points: lt.rate_h.ESP },
        { id: "eu_h", label: "UE-27 (serie histórica)", shortLabel: "UE-27, hist.", color: C.yellow, noEndLabel: true, points: lt.rate_h.EU27 || [] },
        { id: "es", label: "España (serie vigente)", shortLabel: "España", color: C.blue, emphasis: true, points: lt.rate.ESP },
        { id: "eu", label: "UE-27 (serie vigente)", shortLabel: "UE-27", color: C.ref, points: lt.rate.EU27 },
        ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: lt.rate[area] })),
      ]
    : null;
  const ltPeak = lt ? lt.rate.ESP.reduce((a, b) => (b.value > a.value ? b : a)) : null;
  const shareEs = lt ? last(lt.share.ESP) : null;
  const shareEu = lt ? last(lt.share.EU27) : null;
  const shareIt = lt ? last(lt.share.ITA) : null;

  // Education
  const ed = data.education;
  const edSeries = ed
    ? [
        { id: "es_low", label: "España, hasta la ESO (CINE 0–2)", shortLabel: "España, hasta ESO", color: C.blue, emphasis: true, points: ed.rate["ED0-2"].ESP },
        { id: "eu_low", label: "UE-27, hasta la ESO", shortLabel: "UE-27, hasta ESO", color: C.ref, points: ed.rate["ED0-2"].EU27 },
        { id: "es_high", label: "España, estudios superiores (CINE 5–8)", shortLabel: "España, superiores", color: C.aqua, points: ed.rate["ED5-8"].ESP },
        { id: "eu_high", label: "UE-27, estudios superiores", shortLabel: "UE-27, superiores", color: C.yellow, points: ed.rate["ED5-8"].EU27 },
      ]
    : null;
  const lowPop = ed ? AREAS.map((area) => ({ id: area, label: NAMES[area], value: last(ed.population["ED0-2"][area])?.value })).filter((r) => r.value != null).sort((a, b) => b.value - a.value) : [];
  const lowRate = (area) => last(ed?.rate["ED0-2"][area])?.value;
  const highRate = (area) => last(ed?.rate["ED5-8"][area])?.value;
  const popLow = (area) => last(ed?.population["ED0-2"][area])?.value;
  const edYear = ed ? last(ed.rate["ED0-2"].ESP).year : null;

  // Firm size
  const fs = data.firm_size;
  const micro = fs ? AREAS.map((area) => ({ id: area, label: NAMES[area], value: fs.shares[area]?.["0-9"] })).filter((r) => r.value != null).sort((a, b) => b.value - a.value) : [];

  // Minimum wage
  const mw = data.minimum_wage;
  const mwOrder = ["ESP", "FRA", "PRT", "DEU", "GRC", "NLD", "IRL", "GBR", "USA"];
  const mwSeries = mw
    ? mwOrder
        .filter((area) => mw[area])
        .map((area) => ({
          id: area,
          label: NAMES[area],
          color: area === "ESP" ? C.blue : area === "FRA" ? C.orange : area === "PRT" ? C.aqua : area === "DEU" ? C.yellow : C.peer,
          emphasis: area === "ESP",
          noEndLabel: !["ESP", "FRA", "PRT", "DEU", "USA"].includes(area),
          points: mw[area],
        }))
    : null;
  const smi = events.find((e) => e.id === "smi_2019");
  const mwEs = mw ? last(mw.ESP) : null;
  const mwLow = mw ? mw.ESP.filter((p) => p.year >= 1990).reduce((a, b) => (b.value < a.value ? b : a)) : null;
  const mw2018 = mw ? at(mw.ESP, 2018) : null;
  const mw2019 = mw ? at(mw.ESP, 2019) : null;

  // Tax wedge
  const w = data.tax_wedge;
  const wedgeOrder = ["DEU", "FRA", "ITA", "PRT", "OECD_REP", "EU22OECD", "ESP"];
  const wedge = wedgeOrder.map((area) => ({
    id: area,
    label: NAMES[area],
    color: area === "ESP" ? C.blue : area === "OECD_REP" ? C.ref : area === "EU22OECD" ? C.orange : C.peer,
    emphasis: area === "ESP",
    points: w.aw100[area],
  }));
  const wl = h.wedge_last;
  const wf = h.wedge_first;

  return (
    <>
      <Chapter id="cap-causas" kicker="Capítulo 3" title="Qué hay detrás de la brecha: cinco sospechosos habituales">
        <p>
          Los economistas suelen señalar varias causas del paro estructural español. Aquí se miden cinco con datos comparables: cuánto dura el
          paro, la formación de los parados, el tamaño de las empresas, el salario mínimo y los impuestos sobre el trabajo. Ninguna explica sola la
          brecha, y alguna apunta en contra de lo que se suele decir.
        </p>
      </Chapter>

      {ltSeries ? (
        <Fig
          id="larga-duracion"
          title={`El paro de larga duración llegó al ${pct(ltPeak.value)} de los activos en ${ltPeak.year}; hoy es del ${pct(last(lt.rate.ESP).value)}, frente al ${pct(last(lt.rate.EU27).value)} de la UE-27`}
          dek={`Personas que llevan un año o más buscando empleo. Como parte del total de parados, España (${pct(shareEs.value)} en ${shareEs.year}) está en la media europea (${pct(shareEu.value)}) y muy por debajo de Italia (${pct(shareIt.value)}): el problema español es que hay muchos parados, no que los parados lo sean durante más tiempo que en otros países.`}
          legend={ltSeries.filter((s) => s.color !== C.peer).concat([PEER_LEGEND])}
          sources={[S.eurostat("une_ltu_a"), S.eurostat("une_ltu_a_h")]}
          notes={["La serie histórica (cerrada en 2020) y la vigente se solapan; no se empalman."]}
          table={
            <>
              <SeriesTable series={ltSeries} />
              <SeriesTable
                caption="Ver el porcentaje de parados que lo son desde hace un año o más"
                series={["ESP", "EU27", ...PEERS].map((area) => ({ id: area, label: NAMES[area], points: lt.share[area] || [] }))}
              />
            </>
          }
          explain={{
            what: "Qué porcentaje de la población activa lleva más de un año en paro.",
            read: "El paro largo es el que más se parece a «estructural»: quien pasa años sin trabajar pierde contactos y habilidades, y le cuesta más volver (histéresis). En España se disparó tras 2008 y ha bajado con la recuperación.",
            not: "No cuenta a quien deja de buscar empleo y pasa a la inactividad (desanimados), ni distingue por edad o por sexo.",
          }}
        >
          <TimeSeriesChart series={back(ltSeries)} xMin={1996} xMax={h.last_year} ariaLabel="Paro de larga duración, porcentaje de la población activa" />
        </Fig>
      ) : null}

      {edSeries ? (
        <Fig
          id="educacion"
          title={`El ${pct(popLow("ESP"))} de los adultos españoles no pasó de la ESO, frente al ${pct(popLow("EU27"))} de la UE-27; su paro es del ${pct(lowRate("ESP"))}`}
          dek={`En ${edYear}, el paro de quien tiene estudios superiores es del ${pct(highRate("ESP"))} en España y del ${pct(highRate("EU27"))} en la UE-27. Portugal (${pct(popLow("PRT"))}) e Italia (${pct(popLow("ITA"))}) tienen tantos adultos con poca formación como España y bastante menos paro: la formación explica una parte, no toda.`}
          legend={edSeries}
          sources={[S.eurostat("lfsa_urgaed"), S.eurostat("edat_lfse_03")]}
          notes={["Población de 25 a 64 años. CINE 0–2: hasta la primera etapa de secundaria (ESO); CINE 5–8: estudios superiores. Eurostat marca ruptura de serie para España en 1998, 2001, 2005, 2006, 2014 (paso de CINE 1997 a CINE 2011) y 2021."]}
          table={
            <>
              <SeriesTable series={edSeries} />
              <DataTable
                caption="Adultos de 25 a 64 años con estudios hasta la ESO (último año)"
                columns={[
                  { key: "label", label: "País" },
                  { key: "value", label: "%", format: (v) => fmt(v) },
                  { key: "rate", label: "Su tasa de paro", format: (v) => fmt(v) },
                ]}
                rows={lowPop.map((r) => ({ ...r, rate: lowRate(r.id) }))}
              />
            </>
          }
          explain={{
            what: "La tasa de paro según el nivel de estudios (líneas) y qué parte de los adultos tiene como máximo la ESO (barras).",
            read: "En todas partes el paro baja con los estudios. En España la diferencia es mayor y, además, hay casi el doble de adultos con poca formación que en Europa: las dos cosas suman.",
            not: "No dice si la formación causa el empleo o si los trabajos disponibles no la exigen; ni mide la calidad de la formación ni la sobrecualificación (en /visualizaciones/educacion/).",
          }}
        >
          <TimeSeriesChart series={edSeries} xMin={2002} xMax={h.last_year} ariaLabel="Tasa de paro por nivel educativo" />
          <h3 className="vizPanelTitle">
            Adultos con estudios hasta la ESO, {last(ed.population["ED0-2"].ESP).year}
            <span>% de la población de 25 a 64 años</span>
          </h3>
          <CategoryBars rows={lowPop} highlight={["ESP"]} label="Adultos con estudios hasta la ESO" />
        </Fig>
      ) : null}

      {fs ? (
        <Fig
          id="tamano-empresa"
          title={`El ${pct(fs.shares.ESP["0-9"])} del empleo empresarial español está en microempresas, algo más que en la UE (${pct(fs.shares.EU27["0-9"])}) pero menos que en Italia (${pct(fs.shares.ITA["0-9"])}) y Portugal (${pct(fs.shares.PRT["0-9"])})`}
          dek={`En ${fs.year}. Alemania: ${pct(fs.shares.DEU["0-9"])}. Las empresas pequeñas suelen ser menos productivas, pero Italia y Portugal tienen aún más empleo en ellas y mucho menos paro: el tamaño medio no basta para explicar la brecha.`}
          sources={[S.eurostat("sbs_sc_ovw")]}
          notes={["Personas ocupadas en la economía empresarial (industria, construcción y servicios de mercado, sin administración pública), por tramo de ocupados de la empresa. Porcentajes calculados por nosotros."]}
          table={
            <DataTable
              columns={[{ key: "label", label: "País" }, ...Object.entries(SIZE_LABELS).map(([key, label]) => ({ key, label, format: (v) => fmt(v) }))]}
              rows={AREAS.filter((area) => fs.shares[area]).map((area) => ({ id: area, label: NAMES[area], ...fs.shares[area] }))}
            />
          }
          explain={{
            what: "Qué parte de los ocupados en empresas trabaja en microempresas (menos de 10 personas).",
            read: "Más empleo en microempresas suele ir con menos productividad y menos estabilidad. España está algo por encima de la media europea, lejos de Alemania.",
            not: "No incluye a la administración pública ni a la agricultura, y es una foto de un año: no muestra si el tamaño de las empresas ha cambiado.",
          }}
        >
          <CategoryBars rows={micro} highlight={["ESP"]} label="Empleo en microempresas" />
        </Fig>
      ) : null}

      {mwSeries ? (
        <Fig
          id="salario-minimo"
          title={`El salario mínimo pasó del ${pct(mwLow.value)} del salario mediano en ${mwLow.year} al ${pct(mwEs.value)} en ${mwEs.year}; Francia está en el ${pct(last(mw.FRA).value)} y Portugal en el ${pct(last(mw.PRT).value)}`}
          dek={`La mayor subida fue la de ${smi ? smi.date.slice(0, 4) : 2019} (${smi ? smi.label.toLowerCase() : "+22 %"}): del ${pct(mw2018)} al ${pct(mw2019)} del salario mediano. Desde entonces el paro ha bajado del ${pct(at(data.unemployment.amecos.ESP, 2018))} al ${pct(h.es_last)}.`}
          legend={mwSeries.filter((s) => s.color !== C.peer).concat([{ id: "others", label: "Grecia, Países Bajos, Irlanda, Reino Unido y Estados Unidos", color: C.peer }])}
          sources={[S.minwage, ...(smi ? [{ label: smi.source, href: smi.source_url }] : [])]}
          notes={["Salario mínimo legal sobre el salario mediano bruto de los asalariados a tiempo completo (OCDE). Italia no tiene salario mínimo legal general: los fijan los convenios."]}
          table={<SeriesTable series={mwSeries} />}
          explain={{
            what: "El salario mínimo como porcentaje del salario que cobra el trabajador a tiempo completo del medio de la distribución.",
            read: "Cuanto más alto, más trabajadores cobran el mínimo y más «muerde». Un mínimo muy alto puede expulsar del empleo a los menos productivos; uno muy bajo, dejar salarios por debajo de lo que la empresa podría pagar.",
            not: "Que el paro bajara tras la subida de 2019 no prueba que el salario mínimo no destruya empleo, ni lo contrario: la pandemia y la recuperación posterior lo mezclan todo. Los estudios sobre esa subida llegan a conclusiones distintas.",
          }}
        >
          <TimeSeriesChart series={back(mwSeries)} xMin={1980} xMax={mwEs.year} annotations={smi ? [{ year: 2019, label: "SMI 2019" }] : []} ariaLabel="Salario mínimo en porcentaje del salario mediano" />
        </Fig>
      ) : null}

      <Fig
        id="cuna-fiscal"
        title={`La cuña fiscal sobre el salario medio es del ${pct(wl.ESP)} en España: más que la media OCDE (${pct(wl.OECD_REP)}) y en la media de la UE (${pct(wl.EU22OECD)})`}
        dek={`IRPF y cotizaciones (del trabajador y de la empresa) sobre el coste laboral de un soltero sin hijos con el salario medio. Desde ${h.wedge_first_year} subió en España (${pct(wf.ESP)} → ${pct(wl.ESP)}) mientras bajaba en Alemania (${pct(wf.DEU)} → ${pct(wl.DEU)}), Francia e Italia, que siguen por encima. Con el 67 % del salario medio: ${pct(h.wedge_low_last.ESP)} en España frente a ${pct(h.wedge_low_last.OECD_REP)} en la OCDE.`}
        legend={wedge.filter((s) => s.color !== C.peer).concat([PEER_LEGEND])}
        sources={[S.wages, { label: "Cien años de impuestos en España", href: "/visualizaciones/carga-fiscal/" }]}
        notes={["Media UE en la OCDE: media simple de los 22 países de la UE que pertenecen a la OCDE."]}
        table={<SeriesTable series={[...wedge].reverse()} />}
        explain={{
          what: "La parte del coste de un trabajador que se queda el Estado en impuestos y cotizaciones.",
          read: "Una cuña alta encarece contratar o reduce el sueldo neto. España está en la media europea y por debajo de Alemania, Francia e Italia.",
          not: "No explica la brecha de paro: Alemania tiene más cuña y mucho menos paro. Tampoco incluye las prestaciones que esas cotizaciones financian (pensión, desempleo).",
        }}
      >
        <TimeSeriesChart series={back(wedge)} xMin={h.wedge_first_year} xMax={h.wedge_last_year} yMax={60} height={280} ariaLabel="Cuña fiscal sobre el salario medio" />
        <WedgeBars values={wl} names={NAMES} year={h.wedge_last_year} color={C.blue} />
      </Fig>
    </>
  );
}
