import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import EmpleoChart from "./EmpleoChart";
import { Chapter, DataTable, Fig, PairedBars } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, at, back, sources } from "./common.mjs";
import { fmt, num, signed, thousands } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const SECTOR_NAMES = { F: "Construcción", C: "Industria manufacturera", "G-I": "Comercio, transporte y hostelería", A: "Agricultura" };

export default function ChapterCiclo({ data, events }) {
  const h = data.headline;
  const S = sources(data);
  const u = data.unemployment;
  const n = data.nawru;
  const yMaxUne = Math.ceil(Math.max(...u.amecos.ESP.map((p) => p.value)) / 5) * 5;
  const nawru = [
    { id: "es_actual", label: "España, paro observado", shortLabel: "Paro", color: C.blue, emphasis: true, points: u.amecos.ESP.filter((p) => p.year >= 1965) },
    { id: "es_nawru", label: "España, paro estructural estimado (NAWRU)", shortLabel: "NAWRU España", color: C.orange, points: n.ESP },
    { id: "du15_nawru", label: "UE-15 con la RFA, NAWRU (1972–1991)", shortLabel: "NAWRU UE-15 (RFA)", color: C.yellow, points: n.DU15 },
    { id: "eu15_nawru", label: "UE-15, NAWRU (desde 1991)", shortLabel: "NAWRU UE-15", color: C.ref, points: n.EU15 },
  ];

  const cycle = data.cycle;
  const crisis = cycle?.episodes?.[0];
  const covid = cycle?.episodes?.[1];
  const row = (episode, area) => episode?.rows.find((r) => r.area === area) || {};
  const esC = row(crisis, "ESP");
  const itC = row(crisis, "ITA");
  const esP = row(covid, "ESP");
  const growth = cycle
    ? [
        { id: "gdp", label: "PIB en volumen, variación anual", shortLabel: "PIB", color: C.ref, points: cycle.es_growth.gdp },
        { id: "emp", label: "Ocupados, variación anual", shortLabel: "Empleo", color: C.blue, emphasis: true, points: cycle.es_growth.employment },
      ]
    : null;
  const erte = events.find((e) => e.id === "erte_2020");
  const lit = events.find((e) => e.id === "lit_bentolila_2012");

  const adj = data.contract_adjustment || [];
  const adjCrisis = adj[0];
  const adjCovid = adj[1];

  const cs = data.construction_share;
  const losses = data.sector_losses_es;
  const constr = cs
    ? [
        { id: "ESP", label: "España", color: C.blue, emphasis: true, points: cs.ESP },
        { id: "EU27", label: "UE-27", color: C.ref, points: cs.EU27 },
        ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: cs[area] })),
      ]
    : null;

  return (
    <>
      <Chapter id="cap-ciclo" kicker="Capítulo 2" title="¿Estructural o cíclico? Las dos cosas a la vez">
        <p>
          «Estructural» significa que el paro no baja de cierto nivel ni en los buenos años; «cíclico», que sube y baja con la economía. En
          España se dan las dos cosas: un suelo alto y unas oscilaciones enormes. Este capítulo mide ambas y muestra por qué cada crisis destruye
          aquí tanto empleo.
        </p>
      </Chapter>

      <Fig
        id="estructural"
        title={`La Comisión Europea estima que el paro estructural de España no ha bajado del ${pct(h.nawru_min_since.value)} desde ${h.hypothesis_from}`}
        dek={`En ${h.last_year}, ${pct(h.nawru_last)} en España frente a ${pct(h.nawru_eu15_last)} en la UE-15 (${num(h.nawru_ratio_mean_since, 2)} veces de media desde ${h.hypothesis_from}). Pero la parte cíclica también es enorme: el paro observado quedó ${num(-h.gap_min.value)} puntos por debajo del estructural en ${h.gap_min.year} y ${num(h.gap_max.value)} puntos por encima en ${h.gap_max.year}.`}
        legend={nawru}
        sources={[S.ameco]}
        table={<SeriesTable series={nawru} />}
        explain={{
          what: "El paro que hubo (azul) y el paro «estructural» que la Comisión Europea calcula con su modelo (naranja): el nivel de paro con el que los salarios no se aceleran.",
          read: "La distancia entre la línea azul y la naranja es la parte cíclica. La altura de la naranja frente a la gris es la brecha estructural con Europa.",
          not: "El NAWRU no se observa: es la salida de un modelo, se revisa con cada previsión y tiende a seguir al paro real después de crisis largas (histéresis). Puede exagerar lo «estructural».",
        }}
      >
        <TimeSeriesChart series={nawru} xMin={1965} xMax={h.last_year} yMax={yMaxUne} ariaLabel="Paro observado y paro estructural estimado (NAWRU)" />
      </Fig>

      {crisis ? (
        <Fig
          id="ciclo"
          title={`En ${crisis.from}–${crisis.to} el PIB de España cayó un ${num(-esC.gdp)} % y el empleo un ${num(-esC.employment)} %; en Italia, con una caída del PIB mayor (${num(-itC.gdp)} %), el empleo bajó un ${num(-itC.employment)} %`}
          dek={`En España cada punto de PIB perdido se llevó unos ${num(esC.employment / esC.gdp)} puntos de empleo. En la pandemia (${covid.from}–${covid.to}), con los ERTE, fue al revés: el PIB cayó un ${num(-esP.gdp)} % y el empleo un ${num(-esP.employment)} %.`}
          sources={[S.ameco, ...(erte ? [{ label: erte.source, href: erte.source_url }] : [])]}
          notes={[
            "Variación entre el año de partida y el de llegada de cada episodio, en PIB en volumen y ocupados de contabilidad nacional (AMECO). Los trabajadores en ERTE cuentan como ocupados.",
            ...(lit ? [`${lit.source}: «${lit.label}».`] : []),
          ]}
          table={
            <DataTable
              columns={[
                { key: "episode", label: "Episodio" },
                { key: "area", label: "País", format: (v) => NAMES[v] || v },
                { key: "gdp", label: "PIB", format: (v) => fmt(v, "growth") },
                { key: "employment", label: "Empleo", format: (v) => fmt(v, "growth") },
                { key: "unemployment_pp", label: "Tasa de paro", format: (v) => fmt(v, "pp") },
              ]}
              rows={cycle.episodes.flatMap((ep) => ep.rows.map((r) => ({ ...r, id: `${ep.from}-${r.area}`, episode: `${ep.from}–${ep.to}` })))}
            />
          }
          explain={{
            what: "Cuánto cayeron la producción (PIB) y el empleo en cada país en las dos últimas recesiones.",
            read: "Si la barra azul (empleo) es más larga que la gris (PIB), el país ajustó despidiendo más de lo que cayó su actividad. España es el caso extremo en 2007–2013 y el contrario en 2020.",
            not: `No prueba una sola causa. La literatura señala la dualidad de contratos: ${lit ? "Bentolila, Cahuc, Dolado y Le Barbanchon (2012) estiman que con la protección del empleo francesa España habría evitado en torno al 45 % del aumento de su paro" : "la diferencia de costes de despido entre fijos y temporales"}. También pesó la burbuja de la construcción (más abajo).`,
          }}
        >
          <div className="vizMultiples">
            {[crisis, covid].map((ep) => (
              <div key={ep.from}>
                <h3 className="vizPanelTitle">
                  {ep.label}, {ep.from}–{ep.to}
                  <span>Variación acumulada, %</span>
                </h3>
                <PairedBars
                  label={`PIB y empleo, ${ep.from}–${ep.to}`}
                  measures={[
                    { key: "gdp", label: "PIB", color: C.ref },
                    { key: "employment", label: "Empleo", color: C.blue },
                  ]}
                  rows={ep.rows.map((r) => ({ ...r, id: r.area, label: NAMES[r.area], emphasis: r.area === "ESP" }))}
                />
              </div>
            ))}
          </div>
          <h3 className="vizPanelTitle">
            España, cada año desde 1961
            <span>Variación anual del PIB y del empleo, %</span>
          </h3>
          <EmpleoChart series={growth} unit="growth" xMin={1961} xMax={h.last_year} height={260} ariaLabel="Crecimiento anual del PIB y del empleo en España" />
        </Fig>
      ) : null}

      {adjCrisis ? (
        <Fig
          id="ajuste"
          title={`En ${adjCrisis.from}–${adjCrisis.to} se perdieron ${thousands(-adjCrisis.temporal)} de empleos temporales y ${thousands(-adjCrisis.indefinido)} indefinidos, aunque los temporales eran solo el ${pct(adjCrisis.temporal_share_from)} de los asalariados`}
          dek={adjCovid ? `En ${adjCovid.to}, con los ERTE protegiendo a los fijos, el patrón se repitió en pequeño: ${thousands(-adjCovid.temporal)} temporales menos frente a ${thousands(-adjCovid.indefinido)} indefinidos.` : undefined}
          sources={[S.ine]}
          notes={["Media anual de los cuatro trimestres de la EPA; asalariados de 16 y más años."]}
          table={
            <DataTable
              columns={[
                { key: "period", label: "Periodo" },
                { key: "temporal", label: "Temporales", format: (v) => fmt(v, "dthousands") },
                { key: "indefinido", label: "Indefinidos", format: (v) => fmt(v, "dthousands") },
                { key: "temporal_share_from", label: "% temporales al inicio", format: (v) => fmt(v) },
              ]}
              rows={adj.map((a) => ({ ...a, id: a.from, period: `${a.from}–${a.to}` }))}
            />
          }
          explain={{
            what: "Cuántos asalariados con contrato temporal y cuántos con contrato indefinido se perdieron en cada recesión.",
            read: "Despedir a un temporal al acabar su contrato no cuesta indemnización (o muy poca); despedir a un fijo, sí. Por eso las empresas ajustan primero por los temporales, y por eso el empleo español es tan sensible al ciclo.",
            not: "No distingue cuántos temporales eran reemplazados por otros temporales ni cuántos pasaron a ser fijos: son saldos netos.",
          }}
        >
          <PairedBars
            label="Variación de asalariados por tipo de contrato"
            unit="dthousands"
            measures={[
              { key: "temporal", label: "Temporales", color: C.orange },
              { key: "indefinido", label: "Indefinidos", color: C.blue },
            ]}
            rows={adj.map((a) => ({ ...a, id: a.from, label: `${a.from}–${a.to}`, emphasis: true }))}
          />
        </Fig>
      ) : null}

      {constr && losses ? (
        <Fig
          id="construccion"
          title={`La construcción llegó a dar el ${pct(losses.construction_peak.value)} del empleo en ${losses.construction_peak.year} y explica el ${num(losses.construction_share_of_loss, 0)} % de los empleos perdidos en ${losses.from}–${losses.to}`}
          dek={`En ${losses.construction_peak.year} la media de la UE-27 era del ${pct(at(cs.EU27, losses.construction_peak.year))}. De los ${thousands(-losses.total)} de empleos destruidos en España entre ${losses.from} y ${losses.to}, ${thousands(-losses.by_sector.F)} eran de la construcción. Hoy su peso (${pct(cs.ESP.at(-1).value)}) está cerca del europeo (${pct(cs.EU27.at(-1).value)}).`}
          legend={[{ id: "ESP", label: "España", color: C.blue }, { id: "EU27", label: "UE-27", color: C.ref }, PEER_LEGEND]}
          sources={[S.eurostat("nama_10_a10_e")]}
          notes={["Ocupados de contabilidad nacional por rama NACE Rev. 2 (A10). Peso calculado por nosotros sobre el total de ocupados."]}
          table={
            <>
              <SeriesTable series={constr} />
              <DataTable
                caption={`Empleos perdidos por rama en España, ${losses.from}–${losses.to}`}
                columns={[
                  { key: "label", label: "Rama" },
                  { key: "value", label: "Variación", format: (v) => fmt(v, "dthousands") },
                ]}
                rows={[...Object.entries(losses.by_sector).map(([code, value]) => ({ id: code, label: SECTOR_NAMES[code] || code, value })), { id: "total", label: "Total de la economía", value: losses.total }]}
              />
            </>
          }
          explain={{
            what: "Qué parte de los ocupados trabajaba en la construcción, en España y en Europa.",
            read: "Un sector que pesa casi el doble que en Europa convierte un pinchazo inmobiliario en una pérdida de empleo concentrada y rápida: la mitad de los empleos destruidos en la crisis salió de una rama que daba más de uno de cada ocho empleos.",
            not: "No explica por sí solo la brecha de paro antes de 2000 ni después de 2014, cuando el peso de la construcción ya era parecido al europeo y el paro seguía siendo casi el doble.",
          }}
        >
          <TimeSeriesChart series={back(constr)} xMin={1995} xMax={h.last_year} ariaLabel="Peso de la construcción en el empleo" />
        </Fig>
      ) : null}
    </>
  );
}

export { signed };
