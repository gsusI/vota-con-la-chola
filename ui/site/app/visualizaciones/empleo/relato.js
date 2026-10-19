import { DataTable, Fig, PairedBars } from "./blocks";
import { C, NAMES, sources } from "./common.mjs";
import { GapDecomposition, ContractStack } from "./DenseCharts";
import { fmt, num, thousands } from "./format.mjs";

// «El dato mata el relato»: the two consolidated figures that settle the competing stories on this page.
const verdictStyle = { display: "grid", gap: 6, margin: 0, padding: 0, listStyle: "none", fontSize: "0.92rem", lineHeight: 1.45 };

function Verdicts({ settled, ambiguous }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div>
        <h3 className="vizPanelTitle" style={{ minHeight: 0 }}>
          Relatos que este gráfico zanja
        </h3>
        <ul style={verdictStyle}>
          {settled.map(([claim, answer]) => (
            <li key={claim}>
              <strong>«{claim}»</strong> {answer}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="vizPanelTitle" style={{ minHeight: 0 }}>
          Lo que sigue siendo ambiguo
        </h3>
        <ul style={verdictStyle}>
          {ambiguous.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

const LP_PARTS = [
  { key: "services", label: "Servicios de empleo", color: "#1baf7a" },
  { key: "active", label: "Medidas activas", color: "#2a78d6" },
  { key: "passive", label: "Prestaciones (pasivas)", color: "#b4b2a9" },
];

function StackCell({ row, prefix, max, unit }) {
  const total = row[`${prefix}_total`] ?? LP_PARTS.reduce((sum, p) => sum + (row[`${prefix}_${p.key}`] || 0), 0);
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <div style={{ display: "flex", height: 14, width: "100%", background: "var(--viz-band)", borderRadius: 3, overflow: "hidden" }} aria-hidden="true">
        {LP_PARTS.map((p) => (
          <span key={p.key} style={{ width: `${((row[`${prefix}_${p.key}`] || 0) / max) * 100}%`, background: p.color }} />
        ))}
      </div>
      <span style={{ fontSize: "0.78rem", fontWeight: row.area === "ESP" ? 700 : 400 }}>
        {unit === "gdp" ? `${num(total, 2)} % del PIB` : `${num(total, 0)} PPS`}
      </span>
    </div>
  );
}

function BarCell({ value, max, color, suffix }) {
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <div style={{ height: 14, width: "100%", background: "var(--viz-band)", borderRadius: 3, overflow: "hidden" }} aria-hidden="true">
        <span style={{ display: "block", height: "100%", width: `${((value || 0) / max) * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: "0.78rem" }}>{value == null ? "—" : `${num(value)}${suffix}`}</span>
    </div>
  );
}

export function MoneyResults({ rows }) {
  const maxGdp = Math.max(...rows.map((r) => r.gdp_total || 0));
  const maxPps = Math.max(...rows.map((r) => r.pps_total || 0));
  const maxNawru = Math.max(...rows.map((r) => r.nawru || 0));
  const maxLtu = Math.max(...rows.map((r) => r.ltu_rate || 0));
  const head = { fontSize: "0.78rem", color: "var(--viz-muted)", fontWeight: 600 };
  const grid = { display: "grid", gridTemplateColumns: "minmax(70px, 100px) repeat(4, minmax(0, 1fr))", gap: "8px 12px", alignItems: "center" };
  return (
    <div style={{ display: "grid", gap: 10, overflowX: "auto" }}>
      <ul className="vizLegend" aria-label="Leyenda del gasto">
        {LP_PARTS.map((p) => (
          <li key={p.key}>
            <span className="vizLegend__key" style={{ background: p.color, height: 10, width: 10 }} aria-hidden="true" />
            {p.label}
          </li>
        ))}
        <li>
          <span className="vizLegend__key" style={{ background: "#52514e", height: 10, width: 10 }} aria-hidden="true" />
          Resultados: paro estructural y paro de larga duración
        </li>
      </ul>
      <div style={{ ...grid, minWidth: 560 }} role="table" aria-label="Gasto en políticas de empleo frente a resultados">
        <span style={head} role="columnheader">País</span>
        <span style={head} role="columnheader">Dinero: % del PIB</span>
        <span style={head} role="columnheader">Dinero: PPS por persona que quiere trabajar</span>
        <span style={head} role="columnheader">Resultado: paro estructural (NAWRU)</span>
        <span style={head} role="columnheader">Resultado: paro de larga duración (% activos)</span>
        {rows.map((row) => (
          <div key={row.area} role="row" style={{ display: "contents" }}>
            <span role="rowheader" style={{ fontSize: "0.84rem", fontWeight: row.area === "ESP" ? 700 : 400 }}>
              {NAMES[row.area]}
            </span>
            <StackCell row={row} prefix="gdp" max={maxGdp} unit="gdp" />
            <StackCell row={row} prefix="pps" max={maxPps} unit="pps" />
            <BarCell value={row.nawru} max={maxNawru} color={row.area === "ESP" ? "#17191f" : "#52514e"} suffix=" %" />
            <BarCell value={row.ltu_rate} max={maxLtu} color={row.area === "ESP" ? "#17191f" : "#52514e"} suffix=" %" />
          </div>
        ))}
      </div>
    </div>
  );
}


export default function DatoMataRelato({ data }) {
  const nar = data.narratives;
  if (!nar) return null;
  const S = sources(data);
  const sg = nar.structural_gap;
  const rows = sg.rows;
  const lastRow = rows.at(-1);
  const r2007 = rows.find((r) => r.year === 2007);
  const r2013 = rows.find((r) => r.year === 2013);
  const rf = nar.reform;
  const ch = rf.change;
  const a0 = rf.annual[String(rf.base_year)];
  const a1 = rf.annual[String(rf.last_year)];
  const share0 = (a0.temporal / a0.total) * 100;
  const share1 = (a1.temporal / a1.total) * 100;
  const seekLast = rf.fd_inactive_seekers.at(-1);
  const fdUpperBound = ch.fd + (seekLast?.value || 0);
  const colors = { structural: C.orange, cyclicalUp: C.blue, cyclicalDown: C.aqua, gap: "#17191f" };
  const contractColors = { ordinary: C.blue, fd: C.orange, temporal: C.yellow };
  const src = data.sources;
  const mites = { label: `Ministerio de Trabajo, Anuario MLR-18 (consultado ${String(src.mites_anuario?.retrieved_at || "").slice(0, 10)})`, href: src.mites_anuario?.page };

  return (
    <>
      <section className="card vizProse" id="dato-relato" aria-labelledby="dato-relato-title">
        <h2 id="dato-relato-title">El dato mata el relato</h2>
        <p>
          Casi cualquier gráfico suelto de paro sirve para defender una historia y la contraria. Estos tres ponen el problema entero sobre la mesa:
          cada uno combina varias medidas en una sola escala, de modo que no se puede recortar para contar solo media historia.
        </p>
      </section>

      <Fig
        id="relato-estructural"
        title={`De los ${num(sg.mean_gap)} puntos de paro que España ha tenido de más que la UE-15 desde 1980, ${num(sg.mean_structural)} son estructurales; el ciclo los ensancha o estrecha hasta ${num(Math.max(sg.cyclical_max.value, -sg.cyclical_min.value), 0)} puntos`}
        dek={`Cada año, la brecha observada (punto negro) es la suma de una parte estructural (barra naranja: NAWRU de España menos NAWRU de la UE-15) y una cíclica (tramo azul si el ciclo la agranda, verde si la reduce). En ${lastRow.year}: brecha de ${fmt(lastRow.gap, "pp")}, de los que ${fmt(lastRow.structural, "pp")} son estructurales y ${fmt(lastRow.cyclical, "pp")} cíclicos.`}
        legend={[
          { id: "structural", label: "Parte estructural (barra)", color: colors.structural },
          { id: "up", label: "Parte cíclica que agranda la brecha (tramo)", color: colors.cyclicalUp },
          { id: "down", label: "Parte cíclica que la reduce (tramo)", color: colors.cyclicalDown },
          { id: "gap", label: "Brecha observada: paro de España menos paro de la UE-15 (punto)", color: colors.gap },
        ]}
        legendKind="bar"
        sources={[S.ameco]}
        notes={[
          "Puntos porcentuales de paro. Media europea: UE-15 con la Alemania Occidental hasta 1990 y UE-15 desde 1991 (AMECO); la descomposición la calculamos nosotros con la tasa de paro (ZUTN) y el NAWRU de la Comisión Europea.",
        ]}
        table={
          <DataTable
            columns={[
              { key: "year", label: "Año" },
              { key: "gap", label: "Brecha observada", format: (v) => fmt(v, "pp") },
              { key: "structural", label: "Estructural", format: (v) => fmt(v, "pp") },
              { key: "cyclical", label: "Cíclica", format: (v) => fmt(v, "pp") },
              { key: "es", label: "Paro España", format: (v) => fmt(v) },
              { key: "eu", label: "Paro UE-15", format: (v) => fmt(v) },
              { key: "nawru_es", label: "NAWRU España", format: (v) => fmt(v) },
              { key: "nawru_eu", label: "NAWRU UE-15", format: (v) => fmt(v) },
            ]}
            rows={[...rows].reverse().map((r) => ({ ...r, id: r.year }))}
          />
        }
      >
        <GapDecomposition rows={rows} colors={colors} />
        <Verdicts
          settled={[
            [
              "El paro español es cosa de las crisis",
              `No. En ninguno de los ${rows.length} años la parte cíclica pesa más que la estructural. Incluso en ${r2007.year}, en pleno auge, la parte estructural era de ${fmt(r2007.structural, "pp")}: el ciclo favorable la tapaba (${fmt(r2007.cyclical, "pp")}).`,
            ],
            [
              "Es todo estructural: el ciclo da igual",
              `Tampoco. El ciclo llevó la brecha de ${fmt(r2007.gap, "pp")} en ${r2007.year} a ${fmt(r2013.gap, "pp")} en ${r2013.year}: sin su parte cíclica, la de ${r2013.year} habría sido de ${fmt(r2013.structural, "pp")} y el paro español no habría llegado al ${num(r2013.es)} %.`,
            ],
            [
              "España ya converge con Europa",
              `Solo en parte. La brecha de ${lastRow.year} (${fmt(lastRow.gap, "pp")}) es menor que la estructural (${fmt(lastRow.structural, "pp")}) porque el ciclo ahora ayuda (${fmt(lastRow.cyclical, "pp")}). Cuando cambie, la brecha volverá a abrirse si la parte estructural no baja; esa sí se ha reducido, de ${fmt(r2013.structural, "pp")} en ${r2013.year} a ${fmt(lastRow.structural, "pp")}.`,
            ],
          ]}
          ambiguous={[
            "El NAWRU no se observa: es el resultado de un modelo y tiende a seguir al paro real tras crisis largas (histéresis). Parte de lo que aquí aparece como «estructural» puede ser el poso de crisis anteriores.",
            "En 1991 cambia la media europea (de la UE-15 con la RFA a la UE-15): el salto de ese año es de definición, no de la economía.",
          ]}
        />
      </Fig>

      <Fig
        id="relato-reforma"
        title={`Desde ${rf.base_year} hay ${thousands(-ch.temporal)} de temporales menos, ${thousands(ch.ordinary)} de indefinidos ordinarios más y ${thousands(ch.fd)} de fijos discontinuos más trabajando`}
        dek={`Asalariados por tipo de contrato cada trimestre (áreas, EPA) con una capa rayada encima de los fijos discontinuos que trabajan: los que no tienen actividad y están inscritos como demandantes (media de cada año, Ministerio de Trabajo). La temporalidad pasó del ${num(share0)} % en ${rf.base_year} al ${num(share1)} % en ${rf.last_year}.`}
        legend={[
          { id: "ordinary", label: "Indefinidos ordinarios (área)", color: contractColors.ordinary },
          { id: "fd", label: "Fijos discontinuos trabajando (área)", color: contractColors.fd },
          { id: "temporal", label: "Temporales (área)", color: contractColors.temporal },
          { id: "seek", label: "Fijos discontinuos sin actividad inscritos (capa rayada sobre los que trabajan, solo 2022–2024)", color: "repeating-linear-gradient(45deg, #eb6834 0 2px, transparent 2px 5px)" },
        ]}
        legendKind="bar"
        sources={[S.ine, mites]}
        notes={[
          "EPA: asalariados de 16 y más años; un fijo discontinuo cuenta como asalariado cuando trabaja en la semana de referencia. Indefinidos ordinarios = indefinidos menos fijos discontinuos.",
          `Los inscritos sin actividad solo se publican en el Anuario de Trabajo de 2022 a ${seekLast?.year ?? 2024}; el Anuario de 2025 ya no los separa.`,
        ]}
        table={
          <DataTable
            columns={[
              { key: "quarter", label: "Trimestre" },
              { key: "ordinary", label: "Indefinidos ordinarios", format: (v) => fmt(v, "thousands") },
              { key: "fd", label: "Fijos discontinuos", format: (v) => fmt(v, "thousands") },
              { key: "temporal", label: "Temporales", format: (v) => fmt(v, "thousands") },
              { key: "total", label: "Total asalariados", format: (v) => fmt(v, "thousands") },
              { key: "seek", label: "Fijos discontinuos inactivos inscritos (año)", format: (v) => (v == null ? "" : fmt(v, "thousands")) },
            ]}
            rows={[...rf.quarters].reverse().map((q) => ({ ...q, id: q.quarter, seek: rf.fd_inactive_seekers.find((s) => String(s.year) === q.quarter.slice(0, 4))?.value }))}
          />
        }
      >
        <ContractStack quarters={rf.quarters} seekers={rf.fd_inactive_seekers} colors={contractColors} reformQuarter="2022T2" />
        <h3 className="vizPanelTitle">
          Variación entre {rf.base_year} y {rf.last_year}
          <span>Miles de asalariados (media anual); el bloque rayado cuenta todos los inactivos inscritos de {seekLast?.year}, como cota máxima</span>
        </h3>
        <PairedBars
          label={`Variación de asalariados por contrato entre ${rf.base_year} y ${rf.last_year}`}
          unit="dthousands"
          measures={[{ key: "value", label: "Variación", color: C.ref }]}
          rows={[
            { id: "temporal", label: "Temporales", value: ch.temporal, color: contractColors.temporal },
            { id: "ordinary", label: "Indefinidos ordinarios", value: ch.ordinary, emphasis: true, color: contractColors.ordinary },
            { id: "fd", label: "Fijos discontinuos trabajando", value: ch.fd, color: contractColors.fd },
            { id: "seek", label: `Fijos discontinuos inactivos inscritos (${seekLast?.year}, total)`, value: seekLast?.value || 0, color: `repeating-linear-gradient(45deg, ${contractColors.fd} 0 2px, transparent 2px 5px)` },
          ]}
        />
        <Verdicts
          settled={[
            [
              "La reforma acabó con la temporalidad",
              `No del todo. Bajó del ${num(share0)} % al ${num(share1)} % de los asalariados, pero en ${rf.last_year} seguía habiendo ${thousands(a1.temporal)} de temporales.`,
            ],
            [
              "Es maquillaje: los temporales ahora son fijos discontinuos",
              `No. Aunque todos los fijos discontinuos nuevos que trabajan (${thousands(ch.fd)}) y todos los inscritos sin actividad de ${seekLast?.year} (${thousands(seekLast?.value || 0)}) vinieran de contratos temporales, sumarían ${thousands(fdUpperBound)}: menos que la caída de los temporales (${thousands(-ch.temporal)}). Lo que más creció fue el indefinido ordinario (${thousands(ch.ordinary)}).`,
            ],
            [
              "El empleo creado es solo de fijos discontinuos",
              `No. De los ${thousands(ch.total)} de asalariados más entre ${rf.base_year} y ${rf.last_year}, los fijos discontinuos que trabajan son ${thousands(ch.fd)}.`,
            ],
          ]}
          ambiguous={[
            "Cuánto duran los nuevos contratos indefinidos: ni la EPA ni las estadísticas publicadas dicen cuántos acaban en el periodo de prueba o en despido al poco tiempo.",
            "Cuánto trabajan al año los fijos discontinuos: requiere historiales individuales que no son públicos.",
            "Qué parte se debe a la reforma y qué parte a la recuperación tras la pandemia: las dos ocurren a la vez y la serie no puede separarlas.",
            "Los fijos discontinuos sin actividad que no se inscriben en el SEPE no aparecen en ninguna estadística.",
          ]}
        />
      </Fig>
      {data.labour_policy ? <MoneyFigure data={data} /> : null}
    </>
  );
}

function MoneyFigure({ data }) {
  const lp = data.labour_policy;
  const src = data.sources;
  const lmp = { label: `Comisión Europea, DG EMPL, base LMP (consultado ${String(src.dg_empl_lmp?.retrieved_at || "").slice(0, 10)})`, href: src.dg_empl_lmp?.page };
  const S = sources(data);
  const rows = [...lp.rows].sort((a, b) => (b.pps_total || 0) - (a.pps_total || 0));
  const es = lp.rows.find((r) => r.area === "ESP");
  const eu = lp.rows.find((r) => r.area === "EU27");
  const de = lp.rows.find((r) => r.area === "DEU");
  const passiveShare = (r) => (r.pps_passive / r.pps_total) * 100;
  return (
    <Fig
      id="relato-gasto"
      title={`España dedica al paro el ${num(es.gdp_total, 2)} % del PIB, más que la UE (${num(eu.gdp_total, 2)} %), pero por persona que quiere trabajar gasta menos (${num(es.pps_total, 0)} PPS frente a ${num(eu.pps_total, 0)}) y su paro estructural es del ${num(es.nawru)} % frente al ${num(eu.nawru)} %`}
      dek={`Dinero que entra (gasto en políticas de mercado de trabajo, ${lp.year}) frente a resultados que salen (paro estructural estimado por la Comisión y paro de más de un año), en la misma fila para cada país, ordenados por gasto por persona.`}
      sources={[lmp, S.ameco, S.eurostat("une_ltu_a")]}
      notes={[
        "PPS por persona que quiere trabajar: gasto en paridad de poder de compra dividido por los parados más los inactivos disponibles para trabajar. Servicios = categoría 1 de la base LMP; activas = categorías 2 a 7; pasivas = 8 y 9 (prestaciones y jubilación anticipada).",
        "Cada columna tiene su propia escala, indicada en su cabecera; las barras de una columna son comparables entre países, no entre columnas.",
      ]}
      table={
        <DataTable
          columns={[
            { key: "area", label: "País", format: (v) => NAMES[v] || v },
            { key: "gdp_total", label: "% PIB total", format: (v) => (v == null ? "" : num(v, 2)) },
            { key: "gdp_services", label: "% PIB servicios", format: (v) => (v == null ? "" : num(v, 2)) },
            { key: "gdp_active", label: "% PIB activas", format: (v) => (v == null ? "" : num(v, 2)) },
            { key: "gdp_passive", label: "% PIB pasivas", format: (v) => (v == null ? "" : num(v, 2)) },
            { key: "pps_total", label: "PPS por persona, total", format: (v) => (v == null ? "" : num(v, 0)) },
            { key: "pps_services", label: "PPS servicios", format: (v) => (v == null ? "" : num(v, 0)) },
            { key: "pps_active", label: "PPS activas", format: (v) => (v == null ? "" : num(v, 0)) },
            { key: "pps_passive", label: "PPS pasivas", format: (v) => (v == null ? "" : num(v, 0)) },
            { key: "nawru", label: "Paro estructural", format: (v) => (v == null ? "" : fmt(v)) },
            { key: "ltu_rate", label: "Paro larga duración", format: (v) => (v == null ? "" : fmt(v)) },
          ]}
          rows={rows.map((r) => ({ ...r, id: r.area }))}
        />
      }
    >
      <MoneyResults rows={rows} />
      <Verdicts
        settled={[
          [
            "España gasta poco contra el paro",
            `No en relación con su economía: el ${num(es.gdp_total, 2)} % del PIB, por encima de la UE (${num(eu.gdp_total, 2)} %) y de Alemania (${num(de.gdp_total, 2)} %). Pero es porque tiene muchos más parados.`,
          ],
          [
            "España gasta mucho contra el paro",
            `No por persona: ${num(es.pps_total, 0)} PPS por cada persona que quiere trabajar, frente a ${num(eu.pps_total, 0)} en la UE y ${num(de.pps_total, 0)} en Alemania. En servicios de empleo, ${num(es.pps_services, 0)} frente a ${num(eu.pps_services, 0)}.`,
          ],
          [
            "El dinero se va en subsidios",
            `Las prestaciones son el ${num(passiveShare(es), 0)} % del gasto por persona en España y el ${num(passiveShare(eu), 0)} % en la UE; por persona, España paga en prestaciones casi lo mismo que la media europea (${num(es.pps_passive, 0)} frente a ${num(eu.pps_passive, 0)} PPS). La diferencia está en orientación e intermediación, no en prestaciones.`,
          ],
        ]}
        ambiguous={[
          "La causalidad va en los dos sentidos: más paro eleva el gasto en % del PIB y reparte el gasto por persona entre más gente. Esta comparación no dice que gastar más reduzca el paro.",
          "Los países no clasifican igual sus programas (Italia apenas declara gasto en servicios de empleo) y la base no mide la eficacia de cada uno.",
          "La proporción de contrataciones que pasan por los servicios públicos de empleo no tiene una estadística comparable entre países; la serie europea de quién contacta con ellos se cerró en 2020.",
        ]}
      />
    </Fig>
  );
}
