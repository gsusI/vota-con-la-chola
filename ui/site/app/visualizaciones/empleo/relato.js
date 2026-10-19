import { DataTable, Fig, PairedBars } from "./blocks";
import { C, sources } from "./common.mjs";
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
          Casi cualquier gráfico suelto de paro sirve para defender una historia y la contraria. Estos dos ponen el problema entero sobre la mesa:
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
    </>
  );
}
