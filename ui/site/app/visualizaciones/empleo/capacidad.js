import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import { CategoryBars, Chapter, DataTable, Fig } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, back, last } from "./common.mjs";
import { fmt, num } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const eur = (value) => `${Math.round(value).toLocaleString("es-ES", { useGrouping: "always" })} €`;
const MW_NAMES = { ES: "España", DE: "Alemania", FR: "Francia", PT: "Portugal", EL: "Grecia", NL: "Países Bajos", IE: "Irlanda" };
const AREAS = ["ESP", "EU27", "DEU", "FRA", "ITA", "PRT"];

export default function ChapterCapacidad({ data }) {
  const cap = data.capacity;
  const lp = data.labour_policy;
  if (!cap) return null;
  const src = data.sources;
  const day = (id) => String(src[id]?.retrieved_at || "").slice(0, 10);
  const eurostat = (dataset) => ({ label: `Eurostat, ${dataset} (consultado ${day("eurostat_sdmx")})`, href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table` });
  const taxben = { label: `OCDE, Tax-Benefit (vía DBnomics, consultado ${day("oecd_taxben")})`, href: src.oecd_taxben?.page };
  const lmp = { label: `Comisión Europea, DG EMPL, base LMP (consultado ${day("dg_empl_lmp")})`, href: src.dg_empl_lmp?.page };

  // 1. Net pay in constant euros (Spain), split at the Eurostat break.
  const segLabel = (i, segs) => (segs.length > 1 ? (i === 0 ? ` (${segs[0][0].year}–${segs[0].at(-1).year})` : ` (desde ${segs[i][0].year}, nueva base)`) : "");
  const realSeries = [
    ["single_aw100_grs", "Bruto, soltero con el salario medio", C.ref],
    ["single_aw100_net", "Neto, soltero con el salario medio", C.blue],
    ["couple2_aw100_net", "Neto, pareja con dos hijos y un sueldo medio", C.aqua],
    ["single_aw67_net", "Neto, soltero con el 67 % del salario medio", C.orange],
  ].flatMap(([key, label, color]) =>
    cap.real_eur[key].map((seg, i, segs) => ({
      id: `${key}-${i}`,
      label: `${label}${segLabel(i, segs)}`,
      shortLabel: i === segs.length - 1 ? label.split(",")[0] + (key.includes("67") ? " 67 %" : key.includes("couple") ? " familia" : "") : undefined,
      noEndLabel: i < segs.length - 1,
      color,
      emphasis: key === "single_aw100_net",
      points: seg,
    })),
  );
  const g = cap.net_growth_first_segment;
  const netSeg = cap.real_eur.single_aw100_net[0];
  const netFrom = (y) => {
    const a = netSeg.find((q) => q.year === y);
    return a ? (netSeg.at(-1).value / a.value - 1) * 100 : null;
  };
  const ppsYear = last(cap.pps_net.single_aw100.ESP)?.year;
  const ppsRows = AREAS.map((area) => ({ id: area, label: NAMES[area], value: last(cap.pps_net.single_aw100[area])?.value }))
    .filter((r) => r.value != null)
    .sort((a, b) => b.value - a.value);
  const ppsFam = AREAS.map((area) => ({ id: area, label: NAMES[area], value: last(cap.pps_net.couple2_aw100[area])?.value })).filter((r) => r.value != null);
  const netShare = cap.net_share_of_gross;

  // 2. Minimum wage: gross in PPS across countries, net against the net median.
  const mwRows = Object.entries(cap.min_wage_pps.values)
    .map(([geo, value]) => ({ id: geo, label: MW_NAMES[geo] || geo, value }))
    .sort((a, b) => b.value - a.value);
  const netMwOrder = ["ESP", "FRA", "PRT", "DEU", "GRC", "NLD", "IRL"];
  const netMw = netMwOrder
    .filter((a) => cap.min_wage_net_vs_median[a])
    .map((a) => ({
      id: a,
      label: NAMES[a],
      color: a === "ESP" ? C.blue : a === "FRA" ? C.orange : a === "PRT" ? C.aqua : a === "DEU" ? C.yellow : C.peer,
      emphasis: a === "ESP",
      noEndLabel: !["ESP", "FRA", "PRT", "DEU"].includes(a),
      points: cap.min_wage_net_vs_median[a],
    }));
  const nmEs = last(cap.min_wage_net_vs_median.ESP);
  const nm2018 = cap.min_wage_net_vs_median.ESP.find((p) => p.year === 2018)?.value;
  const grossMedian = last(data.minimum_wage?.ESP);

  // 3. In-work poverty.
  const iw = cap.in_work_poverty;
  const iwSeries = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: iw.ESP },
    { id: "EU27", label: "UE-27", color: C.ref, points: iw.EU27 },
    ...PEERS.map((a) => ({ id: a, label: NAMES[a], color: C.peer, points: iw[a] || [] })),
  ];
  const iwEs = last(iw.ESP);
  const iwEu = last(iw.EU27);
  const iwRank = AREAS.filter((a) => iw[a]).map((a) => ({ a, v: last(iw[a]).value })).sort((x, y) => y.v - x.v);

  // 4. Spain's labour-market policy spending over time.
  const lpSeries = lp
    ? [
        { id: "es_active", label: "España, medidas activas", shortLabel: "España, activas", color: C.blue, emphasis: true, points: lp.series.pps_active.ESP },
        { id: "eu_active", label: "UE-27, medidas activas", shortLabel: "UE-27, activas", color: C.ref, points: lp.series.pps_active.EU27 || [] },
        { id: "es_services", label: "España, servicios de empleo", shortLabel: "España, servicios", color: C.aqua, points: lp.series.pps_services.ESP },
        { id: "eu_services", label: "UE-27, servicios de empleo", shortLabel: "UE-27, servicios", color: C.yellow, points: lp.series.pps_services.EU27 || [] },
      ]
    : null;

  return (
    <>
      <Chapter id="cap-bolsillo" kicker="Capítulo 6" title="Lo que queda en el bolsillo y lo que se gasta contra el paro">
        <p>
          Un salario bruto o un porcentaje del PIB dicen poco por sí solos. Aquí se mira lo que el trabajador cobra de verdad (neto, descontada la
          inflación y en paridad de poder de compra), si un empleo basta para no ser pobre, y cuánto dinero público se dedica al paro y con qué
          resultados.
        </p>
      </Chapter>

      <Fig
        id="salario-neto"
        title={`Descontada la inflación, el sueldo neto de un soltero con el salario medio apenas cambió entre ${g.from} y ${g.to} (${g.net_pct > 0 ? "+" : ""}${num(g.net_pct)} %); el bruto subió un ${num(g.gross_pct)} %`}
        dek={`Desde otros años el resultado apenas cambia: ${[2008, 2013, 2019].filter((y) => netFrom(y) != null).map((y) => `${num(netFrom(y))} % desde ${y}`).join(", ")} (hasta ${g.to}). El trabajador se queda con una parte menor del bruto: el ${pct(netShare[0].value)} en ${netShare[0].year} y el ${pct(last(netShare).value)} en ${last(netShare).year}. En paridad de poder de compra, el neto de ese trabajador en ${ppsYear} (${num(last(cap.pps_net.single_aw100.ESP).value, 0)} PPS) está en la media de la UE (${num(last(cap.pps_net.single_aw100.EU27).value, 0)}), por debajo de Alemania y por encima de Italia y Portugal.`}
        legend={[
          { id: "g", label: "Bruto, soltero con el salario medio", color: C.ref },
          { id: "n", label: "Neto, soltero con el salario medio", color: C.blue },
          { id: "f", label: "Neto, pareja con dos hijos y un sueldo medio", color: C.aqua },
          { id: "l", label: "Neto, soltero con el 67 % del salario medio", color: C.orange },
        ]}
        sources={[eurostat("earn_nt_net"), eurostat("prc_hicp_aind")]}
        notes={[
          `Euros constantes de ${cap.real_base_year}, deflactados por nosotros con el IPC armonizado de España. Eurostat marca ruptura de serie en ${cap.breaks.join(", ")} (nueva definición del salario medio): los tramos se muestran por separado, sin empalmar.`,
          "Neto = bruto menos IRPF y cotizaciones del trabajador más prestaciones familiares en efectivo (modelo de impuestos y prestaciones de la OCDE). PPS: paridad de poder de compra.",
        ]}
        table={
          <>
            <SeriesTable series={realSeries} unit="eur" />
            <DataTable
              caption={`Neto anual en PPS, ${ppsYear}`}
              columns={[
                { key: "label", label: "País" },
                { key: "single", label: "Soltero, salario medio", format: (v) => num(v, 0) },
                { key: "family", label: "Pareja con dos hijos, un sueldo medio", format: (v) => (v == null ? "" : num(v, 0)) },
              ]}
              rows={ppsRows.map((r) => ({ id: r.id, label: r.label, single: r.value, family: ppsFam.find((f) => f.id === r.id)?.value }))}
            />
          </>
        }
        explain={{
          what: "Lo que cobra al año un trabajador tipo del sector privado, antes y después de impuestos, en euros de hoy, y cuánto compra ese neto en cada país.",
          read: "Si la línea gris (bruto) sube y la azul (neto) no, la diferencia se la llevan IRPF y cotizaciones. La comparación entre países está en paridad de poder de compra: un euro rinde distinto en Madrid que en Múnich.",
          not: "Es un trabajador tipo con el salario medio, no el mediano ni el más frecuente; no refleja a quien trabaja a tiempo parcial o solo parte del año. Tampoco descuenta la vivienda, el gasto que más ha subido.",
        }}
      >
        <TimeSeriesChart series={realSeries} unit="eur" xMin={2000} xMax={cap.real_base_year} ariaLabel="Sueldo bruto y neto en euros constantes" />
        <h3 className="vizPanelTitle">
          Neto anual de un soltero con el salario medio, {ppsYear}
          <span>Paridad de poder de compra (PPS)</span>
        </h3>
        <CategoryBars rows={ppsRows} unit="index" digits={0} highlight={["ESP"]} label="Neto anual en PPS" />
      </Fig>

      <Fig
        id="salario-minimo-neto"
        title={`El salario mínimo neto equivale al ${pct(nmEs.value)} de lo que se queda un trabajador con el salario mediano (${pct(nm2018)} en 2018); en poder de compra, ${num(cap.min_wage_pps.values.ES, 0)} PPS al mes, menos que Alemania o Francia`}
        dek={`En bruto, el salario mínimo es el ${pct(grossMedian?.value)} del mediano (OCDE): la distancia se acorta en neto porque quien cobra el mínimo apenas paga IRPF. En el segundo semestre de ${cap.min_wage_pps.period.slice(0, 4)}: Alemania ${num(cap.min_wage_pps.values.DE, 0)} PPS, Francia ${num(cap.min_wage_pps.values.FR, 0)}, Portugal ${num(cap.min_wage_pps.values.PT, 0)}.`}
        legend={netMw.filter((s) => s.color !== C.peer).concat([{ id: "o", label: "Grecia, Países Bajos e Irlanda", color: C.peer }])}
        sources={[taxben, eurostat("earn_mw_cur")]}
        notes={[
          "Renta neta de un soltero sin hijos con el salario mínimo a tiempo completo, en % de la de un soltero con el salario mediano a tiempo completo, sin ayudas de vivienda ni asistencia social (OCDE TaxBEN).",
          "Salario mínimo mensual bruto en PPS (Eurostat), prorrateando pagas extraordinarias. Italia no tiene salario mínimo legal.",
        ]}
        table={
          <>
            <SeriesTable series={netMw} />
            <DataTable
              caption={`Salario mínimo bruto mensual en PPS, ${cap.min_wage_pps.period}`}
              columns={[
                { key: "label", label: "País" },
                { key: "value", label: "PPS al mes", format: (v) => num(v, 0) },
              ]}
              rows={mwRows}
            />
          </>
        }
        explain={{
          what: "Cuánto deja en el bolsillo el salario mínimo comparado con un sueldo del medio de la tabla, y cuánto compra en cada país.",
          read: `Un ${pct(nmEs.value)} significa que quien cobra el mínimo se queda con esa parte de lo que se queda un trabajador del medio de la tabla. Desde 2019 esa distancia se ha estrechado mucho en España (${pct(nm2018)} en 2018).`,
          not: "No dice cuánta gente cobra el mínimo ni si su subida destruyó o no empleo (ver el gráfico del salario mínimo en el capítulo 3). Tampoco descuenta el alquiler, que se come una parte muy distinta del sueldo según la ciudad.",
        }}
      >
        <TimeSeriesChart series={back(netMw)} xMin={2001} xMax={nmEs.year} yMax={100} annotations={[{ year: 2019, label: "SMI 2019" }]} ariaLabel="Salario mínimo neto en porcentaje del neto mediano" />
        <h3 className="vizPanelTitle">
          Salario mínimo bruto mensual, {cap.min_wage_pps.period.replace("-S", ", semestre ")}
          <span>Paridad de poder de compra (PPS)</span>
        </h3>
        <CategoryBars rows={mwRows} unit="index" digits={0} highlight={["ES"]} label="Salario mínimo en PPS" />
      </Fig>

      <Fig
        id="pobreza-laboral"
        title={`El ${pct(iwEs.value)} de los ocupados españoles vive en riesgo de pobreza, frente al ${pct(iwEu.value)} en la UE-27: ${iwRank[0].a === "ESP" ? "el más alto del grupo" : `por detrás de ${NAMES[iwRank[0].a]}`}`}
        dek={`Tener empleo no basta para salir de la pobreza: en ${iwEs.year}, Alemania ${pct(last(iw.DEU).value)}, Francia ${pct(last(iw.FRA).value)}, Portugal ${pct(last(iw.PRT).value)}, Italia ${pct(last(iw.ITA).value)}.`}
        legend={[{ id: "ESP", label: "España", color: C.blue }, { id: "EU27", label: "UE-27", color: C.ref }, PEER_LEGEND]}
        sources={[eurostat("ilc_iw01")]}
        notes={["Ocupados de 18 y más años en hogares con renta disponible equivalente por debajo del 60 % de la mediana nacional (EU-SILC). La renta es la del año anterior a la encuesta."]}
        table={<SeriesTable series={iwSeries} />}
        explain={{
          what: "Qué parte de las personas con empleo vive en un hogar pobre según el umbral europeo (60 % de la renta mediana del país).",
          read: "Mide a la vez salarios bajos, jornadas cortas, contratos de pocos meses y hogares con un solo sueldo. Una tasa alta indica que el problema no es solo encontrar trabajo, sino que el trabajo alcance.",
          not: "El umbral es relativo a cada país: un trabajador pobre en España puede tener más renta que uno no pobre en otro país. Tampoco separa las causas (salario, horas o tamaño del hogar).",
        }}
      >
        <TimeSeriesChart series={back(iwSeries)} xMin={2005} xMax={iwEs.year} ariaLabel="Riesgo de pobreza de los ocupados" />
      </Fig>

      {lpSeries ? (
        <Fig
          id="politicas-empleo"
          title={`España gasta en servicios de empleo ${num(lp.rows.find((r) => r.area === "ESP").pps_services, 0)} PPS por persona que quiere trabajar, menos de la mitad que la media de la UE (${num(lp.rows.find((r) => r.area === "EU27").pps_services, 0)})`}
          dek={`En medidas activas (formación, incentivos a la contratación, empleo público temporal), ${num(lp.rows.find((r) => r.area === "ESP").pps_active, 0)} PPS por persona frente a ${num(lp.rows.find((r) => r.area === "EU27").pps_active, 0)} en la UE. La comparación con otros países y con los resultados está en «El dato mata el relato», arriba.`}
          legend={lpSeries}
          sources={[lmp]}
          notes={["PPS por persona que quiere trabajar: gasto en paridad de poder de compra dividido por los parados más los inactivos que quieren y pueden trabajar."]}
          table={<SeriesTable series={lpSeries} unit="count" digits={0} />}
          explain={{
            what: "Cuánto dinero público se dedica, por cada persona que quiere trabajar, a las oficinas de empleo y a las políticas activas, en España y en la UE.",
            read: "Los servicios de empleo (orientación, intermediación) son el gasto más barato y donde España está más lejos de Europa. Las políticas activas por persona suben y bajan con el número de parados: cuando hay muchos, el dinero se reparte entre más.",
            not: "No mide si ese gasto funciona: la eficacia de cada programa exige evaluaciones de impacto que no forman parte de esta base. Los países clasifican algunas partidas de forma distinta (Italia apenas declara gasto en servicios).",
          }}
        >
          <TimeSeriesChart series={lpSeries} unit="count" xMin={2005} xMax={lp.year} ariaLabel="Gasto en políticas activas y servicios de empleo por persona que quiere trabajar" />
        </Fig>
      ) : null}
    </>
  );
}

export { eur, fmt };
