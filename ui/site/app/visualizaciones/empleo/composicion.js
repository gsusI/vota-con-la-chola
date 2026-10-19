import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import EmpleoChart from "./EmpleoChart";
import { RegionScatter } from "./DenseCharts";
import { CategoryBars, Chapter, DataTable, Fig, PairedBars } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, at, back, last } from "./common.mjs";
import { fmt, num } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const AREAS = ["ESP", "EU27", "DEU", "FRA", "ITA", "PRT"];
const SHORT = { ES21: "País Vasco", ES30: "Madrid", ES22: "Navarra", ES51: "Cataluña", ES61: "Andalucía", ES43: "Extremadura", ES70: "Canarias", ES63: "Ceuta", ES64: "Melilla", ES53: "Baleares" };

function sourcesOf(data) {
  const src = data.sources;
  const day = (id) => String(src[id]?.retrieved_at || "").slice(0, 10);
  return {
    eurostat: (dataset) => ({ label: `Eurostat, ${dataset} (consultado ${day("eurostat_sdmx")})`, href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table` }),
    ameco: { label: `Comisión Europea, AMECO (vía DBnomics, consultado ${day("ameco_dbnomics")})`, href: src.ameco_dbnomics.page },
    ipt: { label: `INE, Índice de Precios del Trabajo (consultado ${day("ine_ipt_tempus")})`, href: src.ine_ipt_tempus?.page },
    eaes: { label: `INE, Encuesta Anual de Estructura Salarial (consultado ${day("ine_eaes_tempus")})`, href: src.ine_eaes_tempus?.page },
    epa: { label: `INE, EPA, salarios por decil (consultado ${day("ine_epa_tempus")})`, href: "https://www.ine.es/jaxiT3/Tabla.htm?t=66237" },
  };
}

export default function ChapterComposicion({ data }) {
  const comp = data.composition;
  if (!comp) return null;
  const S = sourcesOf(data);
  const by = comp.base_year;
  const prodRows = by.productivity.rows;
  const p = (base) => prodRows.find((r) => r.base === base);
  const wRows = by.real_wage.rows;
  const behindBases = prodRows.filter((r) => r.ESP < r.EU27).map((r) => r.base);
  const wageAhead = (data.composition?.base_year.real_wage.rows || []).filter((r) => r.ESP >= r.EU27).map((r) => r.base);

  const ssP = comp.shift_share.periods["2000"];
  const ss08 = comp.shift_share.periods["2008"];
  const es = ssP.ESP;
  const eu = ssP.EU27;

  const nat = comp.nationality;
  const lastNat = (c, a) => last(nat.rates[c][a]);
  const fs = (a) => last(nat.foreign_share[a]);
  const cf = comp.education_counterfactual;
  const cfLast = cf.at(-1);
  const natSeries = [
    { id: "es_nat", label: "España, nacionales", shortLabel: "España, nacionales", color: C.blue, emphasis: true, points: nat.rates.NAT.ESP },
    { id: "es_for", label: "España, extranjeros", shortLabel: "España, extranjeros", color: C.orange, points: nat.rates.FOR.ESP },
    { id: "eu_nat", label: "UE-27, nacionales", shortLabel: "UE, nacionales", color: C.ref, points: nat.rates.NAT.EU27 || [] },
    { id: "eu_for", label: "UE-27, extranjeros", shortLabel: "UE, extranjeros", color: C.yellow, points: nat.rates.FOR.EU27 || [] },
  ];
  const cfSeries = [
    { id: "es", label: "España (25–64 años)", shortLabel: "España", color: C.blue, emphasis: true, points: cf.map((r) => ({ year: r.year, value: r.es })) },
    { id: "mix", label: "España con la composición educativa de la UE", shortLabel: "Con formación UE", color: C.aqua, points: cf.map((r) => ({ year: r.year, value: r.es_eu_mix })) },
    { id: "eu", label: "UE-27 (25–64 años)", shortLabel: "UE-27", color: C.ref, points: cf.map((r) => ({ year: r.year, value: r.eu })) },
  ];

  const wc = comp.wage_composition;
  const wcLast = (k) => last(wc[k]);
  const wageSeries = [
    { id: "ipt", label: "Índice de Precios del Trabajo (composición fija)", shortLabel: "Composición fija", color: C.orange, emphasis: true, points: wc.ipt },
    { id: "mean", label: "Salario medio (Encuesta de Estructura Salarial)", shortLabel: "Media", color: C.blue, points: wc.mean },
    { id: "median", label: "Salario mediano", shortLabel: "Mediana", color: C.aqua, points: wc.median },
  ];

  const dec = comp.deciles;
  const decIdx = dec.real_index;
  const g1824 = (k) => (at(decIdx[k], 2024) / at(decIdx[k], 2018) - 1) * 100;
  const decSeries = [
    { id: "d1", label: "Decil 1 (el 10 % que menos cobra)", shortLabel: "Decil 1", color: C.blue, emphasis: true, points: decIdx["1"] },
    { id: "d2", noEndLabel: true, label: "Decil 2", shortLabel: "Decil 2", color: C.aqua, points: decIdx["2"] },
    { id: "d5", noEndLabel: true, label: "Decil 5 (mitad de la tabla)", shortLabel: "Decil 5", color: C.ref, points: decIdx["5"] },
    { id: "d10", noEndLabel: true, label: "Decil 10 (el 10 % que más cobra)", shortLabel: "Decil 10", color: C.orange, points: decIdx["10"] },
  ];
  const lw = comp.low_wage_share;
  const lwRows = AREAS.map((a) => ({ id: a, label: NAMES[a], value: last(lw[a])?.value })).filter((r) => r.value != null).sort((a, b) => b.value - a.value);
  const lwYear = last(lw.ESP)?.year;

  const t = comp.territory;
  const ty = t.year;
  const esU = at(data.unemployment.amecos.ESP, ty);
  const euU = at(data.unemployment.amecos.EU27, ty);
  const pts = t.regions.filter((r) => r.unemployment != null).map((r) => ({ id: r.code, x: r.productivity, y: r.unemployment, label: SHORT[r.code], name: r.name }));
  const refs = [
    { id: "ES", x: t.es.productivity, y: esU, label: "España", color: C.ref },
    { id: "EU", x: t.eu.productivity, y: euU, label: "Media UE-27", color: C.orange },
  ];
  const sortedProd = [...t.regions].sort((a, b) => b.productivity - a.productivity);
  const topReg = sortedProd[0];
  const lowMain = [...sortedProd].reverse().find((r) => !["ES63", "ES64"].includes(r.code));
  const aboveEuUnemp = t.regions.filter((r) => r.unemployment != null && r.unemployment > euU).length;

  return (
    <>
      <Chapter id="cap-composicion" kicker="Capítulo 7" title="Antes de concluir: año base, composición, reparto y territorio">
        <p>
          Cuatro comprobaciones que cambian lo que se puede afirmar. Si la conclusión depende del año que se elige como punto de partida; si la
          brecha viene de que España tiene otros trabajadores (más inmigrantes, menos formación, otros sectores) o de que, a igualdad de
          trabajadores, rinde y paga menos; a quién llegan las subidas salariales; y si el problema es de todo el país o de unas regiones.
        </p>
      </Chapter>

      <Fig
        id="ano-base"
        title={`La brecha de productividad con la UE depende del año de partida: desde 1995, ${num(p(1995).ESP)} % frente a ${num(p(1995).EU27)} %; desde 2008, ${num(p(2008).ESP)} % frente a ${num(p(2008).EU27)} %`}
        dek={`En 1995, el primer año de la serie de niveles y el de mayor ventaja, España producía por hora un ${num(data.headline.level_vs_eu_first.ESP - 100, 0)} % más que la media de la UE: empezar ahí exagera la caída. España queda por detrás desde ${behindBases.join(", ")}; desde 2008 crece al ritmo europeo; ese periodo empieza con una crisis que destruyó sobre todo empleo poco productivo, lo que por composición sube la media. ${wageAhead.length ? `Los salarios reales quedan por detrás de la UE desde todas las bases salvo ${wageAhead.join(" y ")}.` : "Los salarios reales quedan por detrás de la UE desde todas las bases."}`}
        sources={[S.eurostat("nama_10_lp_ulc"), S.ameco]}
        notes={[`Crecimiento acumulado hasta ${by.productivity.end}: productividad real por hora (Eurostat) y remuneración real por asalariado deflactada con el consumo privado (AMECO).`]}
        table={
          <>
            <DataTable
              caption="Productividad por hora: crecimiento desde cada año base"
              columns={[{ key: "base", label: "Desde" }, ...AREAS.map((a) => ({ key: a, label: NAMES[a], format: (v) => fmt(v, "growth") }))]}
              rows={prodRows.map((r) => ({ ...r, id: r.base }))}
            />
            <DataTable
              caption="Salario real por asalariado: crecimiento desde cada año base"
              columns={[{ key: "base", label: "Desde" }, ...AREAS.map((a) => ({ key: a, label: NAMES[a], format: (v) => fmt(v, "growth") }))]}
              rows={wRows.map((r) => ({ ...r, id: r.base }))}
            />
          </>
        }
        explain={{
          what: "El mismo cálculo (cuánto ha crecido la productividad y el salario real hasta hoy) empezando en cinco años distintos.",
          read: "Si la barra azul queda por debajo de la gris en todas las filas, la conclusión no depende del año elegido. En productividad, depende: desde 1995 o 2000 España se queda muy atrás; desde 2008, no. En salarios, España queda atrás casi siempre.",
          not: "No dice qué año es «el bueno»: 1995 es el año de mayor ventaja de España en la serie de niveles (que empieza ese año) y 2008 coincide con el inicio de una crisis en la que se destruyó sobre todo empleo poco productivo, lo que por composición sube la productividad media.",
        }}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Productividad por hora
              <span>Crecimiento acumulado hasta {by.productivity.end}, %</span>
            </h3>
            <PairedBars
              label="Productividad desde cada año base"
              measures={[
                { key: "ESP", label: "España", color: C.blue },
                { key: "EU27", label: "UE-27", color: C.ref },
              ]}
              rows={prodRows.map((r) => ({ ...r, id: r.base, label: `Desde ${r.base}`, emphasis: true }))}
            />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Salario real por asalariado
              <span>Crecimiento acumulado hasta {by.real_wage.end}, %</span>
            </h3>
            <PairedBars
              label="Salario real desde cada año base"
              measures={[
                { key: "ESP", label: "España", color: C.blue },
                { key: "EU27", label: "UE-27", color: C.ref },
              ]}
              rows={wRows.map((r) => ({ ...r, id: r.base, label: `Desde ${r.base}`, emphasis: true }))}
            />
          </div>
        </div>
      </Fig>

      <Fig
        id="productividad-sectores"
        title={`La productividad española se queda atrás dentro de cada sector (+${num(es.within)} % desde ${ssP.ESP.from} frente a +${num(eu.within)} % en la UE), no por moverse a sectores menos productivos (${fmt(es.shift, "pp")})`}
        dek={`Descomposición del crecimiento de la productividad por hora ${es.from}–${es.to} en tres partes: mejora dentro de cada sector, cambio del peso de los sectores en las horas trabajadas e interacción. En la UE el cambio de sectores sumó ${fmt(eu.shift, "pp")}. Desde 2008 la mejora dentro de los sectores es casi igual en España (${fmt(ss08.ESP.within, "pp")}) que en la UE (${fmt(ss08.EU27.within, "pp")}).`}
        sources={[S.eurostat("nama_10_a10"), S.eurostat("nama_10_a10_e")]}
        notes={[
          "Nueve ramas NACE A10 sin actividades inmobiliarias (su valor añadido incluye alquileres imputados a los propietarios, sin horas de trabajo detrás). VAB en volumen encadenado de 2015 y horas trabajadas por rama; la suma de volúmenes encadenados es una aproximación.",
          "Puntos porcentuales sobre la productividad del año inicial. Dentro = Σ cambio de productividad de cada rama × su peso inicial; cambio de sectores = Σ productividad inicial × cambio de peso; interacción = el resto.",
        ]}
        table={
          <>
            <DataTable
              caption={`Descomposición ${es.from}–${es.to} por país`}
              columns={[
                { key: "area", label: "País", format: (v) => NAMES[v] },
                { key: "total", label: "Total", format: (v) => fmt(v, "growth") },
                { key: "within", label: "Dentro de los sectores", format: (v) => fmt(v, "pp") },
                { key: "shift", label: "Cambio de sectores", format: (v) => fmt(v, "pp") },
                { key: "interaction", label: "Interacción", format: (v) => fmt(v, "pp") },
              ]}
              rows={AREAS.filter((a) => ssP[a]).map((a) => ({ ...ssP[a], id: a, area: a }))}
            />
            <DataTable
              caption={`España por rama, ${es.from}–${es.to}`}
              columns={[
                { key: "label", label: "Rama" },
                { key: "hours_share_from", label: `% horas ${es.from}`, format: (v) => fmt(v) },
                { key: "hours_share_to", label: `% horas ${es.to}`, format: (v) => fmt(v) },
                { key: "relative_productivity_from", label: `Productividad ${es.from} (media = 100)`, format: (v) => num(v, 0) },
                { key: "productivity_growth", label: "Crecimiento de su productividad", format: (v) => fmt(v, "growth") },
              ]}
              rows={es.sectors.map((x) => ({ ...x, id: x.sector }))}
            />
          </>
        }
        explain={{
          what: "Cuánto del aumento de la productividad viene de que cada sector produce más por hora y cuánto de que el empleo se mueve hacia sectores más o menos productivos.",
          read: "La barra azul (dentro de los sectores) es la eficiencia; la naranja, el efecto de la mezcla. España no pierde por la mezcla: pierde porque dentro de cada rama mejora menos que Europa, sobre todo antes de 2008.",
          not: "Diez ramas son muy agregadas: dentro de «comercio, transporte y hostelería» cabe mucho cambio de composición (más hostelería, menos industria del transporte) que aquí cuenta como «dentro».",
        }}
      >
        <PairedBars
          label="Descomposición de la productividad por país"
          measures={[
            { key: "within", label: "Dentro de los sectores", color: C.blue },
            { key: "shift", label: "Cambio de sectores", color: C.orange },
            { key: "interaction", label: "Interacción", color: C.peer },
          ]}
          unit="pp"
          rows={AREAS.filter((a) => ssP[a]).map((a) => ({ ...ssP[a], id: a, label: NAMES[a], emphasis: a === "ESP" }))}
        />
      </Fig>

      <Fig
        id="composicion-paro"
        title={`Ni la inmigración ni la formación explican la brecha: los nacionales españoles tienen un paro del ${pct(lastNat("NAT", "ESP").value)} frente al ${pct(lastNat("NAT", "EU27").value)} de los nacionales de la UE; con la formación media europea, el paro español sería del ${pct(cfLast.es_eu_mix)} en vez del ${pct(cfLast.es)}`}
        dek={`Los extranjeros son el ${pct(fs("ESP").value)} de la población activa en España (UE: ${pct(fs("EU27").value)}) y tienen más paro (${pct(lastNat("FOR", "ESP").value)}), pero quitarlos apenas cambia la brecha: el paro total es del ${pct(lastNat("TOTAL", "ESP").value)}. Con la composición educativa de la UE, la brecha de los 25 a 64 años pasaría de ${num(cfLast.es - cfLast.eu)} a ${num(cfLast.es_eu_mix - cfLast.eu)} puntos.`}
        legend={[...natSeries, ...cfSeries.slice(1, 2)]}
        sources={[S.eurostat("lfsa_urgan"), S.eurostat("lfsa_agan"), S.eurostat("lfsa_urgaed"), S.eurostat("lfsa_agaed")]}
        notes={[
          "Nacionales = con la nacionalidad del país (los españoles nacidos fuera que se nacionalizaron cuentan como nacionales). Contrafactual educativo: tasas de paro de España por nivel educativo ponderadas con el peso de cada nivel en la población activa de la UE.",
        ]}
        table={
          <>
            <SeriesTable series={natSeries} />
            <SeriesTable series={cfSeries} caption="Ver el contrafactual educativo" />
          </>
        }
        explain={{
          what: "El paro de nacionales y extranjeros en España y en la UE, y el paro que tendría España si su población activa tuviera la misma formación que la europea.",
          read: "Si la línea azul (españoles) estuviera cerca de la gris (nacionales de la UE), la brecha sería un efecto de la inmigración. No lo está. Y si la línea verde (con formación europea) estuviera cerca de la UE, la brecha sería un efecto educativo. Tampoco: la diferencia está dentro de cada grupo.",
          not: "No dice si los inmigrantes ocupan empleos peores o si la formación española es de menor calidad: solo que, a igual nacionalidad o igual nivel de estudios, en España hay más paro.",
        }}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Paro por nacionalidad
              <span>% de la población activa de 15 a 74 años</span>
            </h3>
            <EmpleoChart series={natSeries} xMin={1998} xMax={last(nat.rates.NAT.ESP).year} height={260} ariaLabel="Paro por nacionalidad en España y la UE" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              ¿Y si España tuviera la formación media europea?
              <span>% de la población activa de 25 a 64 años</span>
            </h3>
            <EmpleoChart series={cfSeries} xMin={cf[0].year} xMax={cfLast.year} height={260} ariaLabel="Paro con la composición educativa europea" />
          </div>
        </div>
      </Fig>

      <Fig
        id="salarios-composicion"
        title={`A composición fija, el salario real cayó un ${num(100 - wcLast("ipt").value)} % entre ${wc.base} y ${wcLast("ipt").year}; el salario medio subió un ${num(wcLast("mean").value - 100)} %: la diferencia es el cambio de quién trabaja`}
        dek={`El Índice de Precios del Trabajo del INE sigue el salario de los mismos puestos (misma ocupación, sector y tipo de contrato); la media, el de todos los asalariados de cada año. Tras 2008 se destruyeron sobre todo empleos de salario bajo (construcción y temporales, capítulo 2); por composición, eso sube la media aunque no suba el sueldo de cada puesto. El mediano subió un ${num(wcLast("median").value - 100)} %.`}
        legend={wageSeries}
        sources={[S.ipt, S.eaes, S.eurostat("prc_hicp_aind")]}
        notes={[`Índices ${wc.base} = 100 deflactados por nosotros con el IPC armonizado. Salario bruto anual por trabajador.`]}
        table={<SeriesTable series={wageSeries} unit="count" digits={1} />}
        explain={{
          what: "Tres formas de medir la evolución del salario real: siguiendo el mismo puesto de trabajo, la media de todos y el trabajador del medio.",
          read: "La distancia entre la línea naranja y la azul es el efecto composición. Aquí va en contra de la intuición: los empleos nuevos de salario bajo existen, pero la destrucción de empleo de 2008–2013 eliminó muchos más, y la media subió.",
          not: "El índice de composición fija no recoge la mejora de quien cambia a un puesto mejor pagado; mide el precio de cada puesto, no la carrera de cada persona.",
        }}
      >
        <TimeSeriesChart series={wageSeries} unit="count" xMin={wc.base} xMax={wcLast("ipt").year} ariaLabel="Salario real a composición fija, medio y mediano" />
      </Fig>

      <Fig
        id="distribucion-salarial"
        title={`Entre 2018 y 2024 el 10 % que menos cobra ganó un ${num(g1824("1"), 0)} % de poder de compra; el sueldo de la mitad de la tabla, un ${num(g1824("5"), 0)} %, y el 10 % que más cobra, un ${num(g1824("10"), 0)} %`}
        dek={`Las subidas del salario mínimo comprimieron la parte baja: en ${dec.levels["1"].at(-1).year} el primer decil cobraba de media ${num(dec.levels["1"].at(-1).value, 0)} € brutos al mes y el último ${num(dec.levels["10"].at(-1).value, 0)} €. La proporción de asalariados con salario bajo (menos de 2/3 del mediano por hora) era del ${pct(last(lw.ESP).value)} en ${lwYear}, por debajo de la UE (${pct(last(lw.EU27).value)}).`}
        legend={decSeries}
        sources={[S.epa, S.eurostat("earn_ses_pub1s")]}
        notes={[
          `Deciles del salario mensual del empleo principal (EPA, tiempo completo y parcial juntos); índices ${dec.base} = 100 deflactados por nosotros con el IPC armonizado.`,
          "El primer decil incluye a muchos asalariados a tiempo parcial: su subida mezcla salario por hora y horas trabajadas.",
        ]}
        table={
          <>
            <SeriesTable series={decSeries} unit="count" digits={1} />
            <DataTable
              caption={`Asalariados con salario bajo, ${lwYear}`}
              columns={[
                { key: "label", label: "País" },
                { key: "value", label: "% de los asalariados", format: (v) => fmt(v) },
              ]}
              rows={lwRows}
            />
          </>
        }
        explain={{
          what: "Cómo ha cambiado, descontada la inflación, el salario de cada parte de la tabla: el 10 % que menos cobra, el del medio y el 10 % que más cobra.",
          read: "Hasta 2018 las líneas van juntas y por debajo de 100: nadie ganó poder de compra. Desde 2019 la línea azul se separa: el salario mínimo subió los sueldos más bajos mucho más que el resto.",
          not: "No sigue a las mismas personas: quien estaba en el primer decil en 2018 puede estar en otro en 2024. Tampoco dice si la subida tuvo coste en empleo.",
        }}
      >
        <TimeSeriesChart series={decSeries} unit="count" xMin={2006} xMax={dec.levels["1"].at(-1).year} annotations={[{ year: 2019, label: "SMI 2019" }]} ariaLabel="Salario real por decil" />
        <h3 className="vizPanelTitle">
          Asalariados con salario bajo, {lwYear}
          <span>% de los asalariados (empresas de 10 o más)</span>
        </h3>
        <CategoryBars rows={lwRows} highlight={["ESP"]} label="Asalariados con salario bajo" />
      </Fig>

      <Fig
        id="territorio-productividad"
        title={`Solo ${t.above_eu_productivity === 1 ? `${topReg.name} produce` : `${t.above_eu_productivity} comunidades producen`} por hora tanto como la media de la UE (${num(t.eu.productivity)} €); ${aboveEuUnemp === t.regions.length ? "todas" : aboveEuUnemp} tienen más paro que la UE`}
        dek={`En ${ty}, del ${num(lowMain.productivity)} € por hora de ${lowMain.name} a los ${num(topReg.productivity)} € de ${topReg.name}: la más productiva rinde ${num(t.max_over_min_main, 2)} veces la menos productiva sin Ceuta y Melilla (${num(t.dispersion_peers.ESP.max_over_min, 2)} con ellas; Alemania ${num(t.dispersion_peers.DEU?.max_over_min, 2)}, Italia ${num(t.dispersion_peers.ITA?.max_over_min, 2)}). Las comunidades más productivas tienen menos paro, pero ninguna baja del europeo (${pct(euU)}): la brecha es nacional, con más intensidad en el sur.`}
        legend={[
          { id: "r", label: "Comunidad autónoma (punto)", color: C.blue },
          { id: "es", label: "España (rombo)", color: C.ref },
          { id: "eu", label: "Media UE-27 (rombo)", color: C.orange },
        ]}
        sources={[S.eurostat("nama_10r_2nlp"), S.eurostat("nama_10r_2lp10"), S.eurostat("lfst_r_lfu3rt")]}
        notes={[
          "Productividad nominal: valor añadido por hora trabajada en euros corrientes. Entre regiones de España los precios difieren poco; frente a la UE, en euros sin ajustar por poder de compra, la distancia con países más caros se exagera.",
          `Dispersión de la productividad por hora entre regiones (más alta / más baja): ${Object.entries(t.dispersion_peers)
            .filter(([, v]) => v)
            .map(([a, v]) => `${NAMES[a]} ${num(v.max_over_min, 2)} (${v.year})`)
            .join(", ")}.`,
        ]}
        table={
          <DataTable
            columns={[
              { key: "name", label: "Comunidad" },
              { key: "productivity", label: "Productividad €/hora", format: (v) => num(v) },
              { key: "pay", label: "Remuneración €/hora", format: (v) => (v == null ? "" : num(v)) },
              { key: "unemployment", label: "Paro", format: (v) => (v == null ? "" : fmt(v)) },
              { key: "median_wage", label: "Salario mediano anual (INE)", format: (v) => (v == null ? "" : `${num(v, 0)} €`) },
            ]}
            rows={sortedProd.map((r) => ({ ...r, id: r.code }))}
          />
        }
        explain={{
          what: "Cada punto es una comunidad autónoma: a la derecha, más valor añadido por hora trabajada; arriba, más paro. Los rombos son España y la media europea.",
          read: "Si la brecha fuera de unas pocas regiones, habría comunidades junto al rombo europeo. No las hay: las más productivas (País Vasco, Madrid, Navarra) tienen el paro más bajo de España y aun así por encima del europeo.",
          not: "Correlación no es causa: la productividad alta y el paro bajo pueden deberse a terceros factores (industria, capital humano, tamaño de las empresas).",
        }}
      >
        <RegionScatter points={pts} refs={refs} xLabel="Productividad nominal por hora (€)" yLabel="Tasa de paro" color={C.blue} />
      </Fig>
    </>
  );
}

export { back, PEER_LEGEND, PEERS };
