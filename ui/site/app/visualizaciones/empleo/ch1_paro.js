import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import EmpleoChart from "./EmpleoChart";
import { Chapter, Fig } from "./blocks";
import { C, NAMES, PEERS, constant, sources } from "./common.mjs";
import { fmt, num, thousands } from "./format.mjs";
import { RatioDecadesTable } from "./sections";

const pct = (value, digits = 1) => `${num(value, digits)} %`;

export default function ChapterParo({ data, epaBreaks, reform }) {
  const h = data.headline;
  const S = sources(data);
  const u = data.unemployment;
  const m = h.mean_since_1980;

  const longRun = [
    { id: "ESP", label: "España (AMECO, desde la EPA)", shortLabel: "España", color: C.blue, emphasis: true, points: u.amecos.ESP },
    { id: "DU15", label: "UE-15 con la RFA (1971–1991)", shortLabel: "UE-15 (RFA)", color: C.yellow, points: u.amecos.DU15 },
    { id: "EU15", label: "UE-15 (desde 1991)", shortLabel: "UE-15", color: C.ref, points: u.amecos.EU15 },
    { id: "EU27", label: "UE-27 (desde 1997)", shortLabel: "UE-27", color: C.orange, points: u.amecos.EU27 },
  ];
  const epaRow = { id: "EPA", label: "España, EPA del INE (media de los cuatro trimestres)", points: u.epa_annual };
  const yMaxUne = Math.ceil(Math.max(...u.amecos.ESP.map((p) => p.value)) / 5) * 5;

  const ratioSeries = [
    { id: "r_DU15", label: "España frente a la UE-15 con la RFA", shortLabel: "vs UE-15 (RFA)", color: C.yellow, points: data.ratio_es_europe.DU15 },
    { id: "r_EU15", label: "España frente a la UE-15", shortLabel: "vs UE-15", color: C.blue, emphasis: true, points: data.ratio_es_europe.EU15 },
    { id: "r_EU27", label: "España frente a la UE-27", shortLabel: "vs UE-27", color: C.orange, points: data.ratio_es_europe.EU27 },
  ];
  const refLines = [
    { id: "eq", label: "Igual que Europa (100)", shortLabel: "Igual", color: C.peer, points: constant(100, 1971, h.last_year) },
    { id: "double", label: "El doble que Europa (200)", shortLabel: "El doble", color: C.peer, points: constant(200, 1971, h.last_year) },
  ];
  const peerMax = Math.max(...u.amecos.ESP.map((p) => p.value), ...Object.values(u.peers).flatMap((rows) => rows.map((p) => p.value)));

  const reg = data.registered;
  const regSeries = reg
    ? [
        { id: "epa", label: "Parados según la encuesta (EPA, vía AMECO)", shortLabel: "EPA", color: C.blue, emphasis: true, points: reg.epa.filter((p) => p.year >= 1976) },
        { id: "sepe", label: "Paro registrado en las oficinas de empleo (SEPE)", shortLabel: "Registrado", color: C.orange, points: reg.sepe.filter((p) => p.year >= 1976) },
      ]
    : null;

  return (
    <>
      <Chapter id="cap-cuanto" kicker="Capítulo 1" title="Cuánto paro, desde cuándo y frente a quién">
        <p>
          Primero, la foto larga: cómo ha evolucionado el paro en España desde 1960, cuánto se ha separado del europeo y si las dos formas
          oficiales de contarlo (la encuesta y el registro) cuentan lo mismo.
        </p>
      </Chapter>

      <Fig
        id="paro"
        title={`Desde ${h.hypothesis_from}, el paro de España ha sido de media ${num(h.ratio_mean_since)} veces el europeo`}
        dek={`España tuvo un paro parecido al europeo hasta mediados de los setenta (${pct(h.es_mean_1960_1974)} de media en 1960–1974). Desde 1980 la distancia solo se estrechó en el auge previo a 2008: picos del ${pct(h.peaks.max_1980s.value)} (${h.peaks.max_1980s.year}), ${pct(h.peaks.max_1990s.value)} (${h.peaks.max_1990s.year}) y ${pct(h.peaks.max_crisis.value)} (${h.peaks.max_crisis.year}); mínimo del ${pct(h.peaks.min_pre_crisis.value)} en ${h.peaks.min_pre_crisis.year}.`}
        legend={longRun}
        sources={[S.ameco, S.ine]}
        notes={[
          `AMECO homogeneiza la EPA a lo largo del tiempo; desde 2002 coincide con la EPA del INE (en la tabla) con una diferencia máxima de ${num(h.epa_vs_ameco_max_gap, 2)} puntos. La EPA cambió de definición o de cuestionario en 2001, 2005 y 2021 (marcadas).`,
          `Último año observado: ${h.last_year}. Las previsiones de AMECO para años posteriores se descartan.`,
        ]}
        table={<SeriesTable series={[...longRun.slice(0, 1), epaRow, ...longRun.slice(1)]} />}
        explain={{
          what: "El porcentaje de la población activa (quien trabaja o busca trabajo) que está en paro, en España y en la media europea, cada año desde 1960.",
          read: "Cuanto más se separa la línea azul de las grises, mayor es la brecha con Europa. La media europea cambia de países dos veces (UE-15 con la Alemania Occidental, UE-15, UE-27): por eso son tres líneas distintas y no una sola.",
          not: "Los años sesenta no son comparables con hoy: la emigración a Europa y el trabajo en el campo familiar rebajaban el paro medido. Tampoco dice por qué la brecha aparece a partir de 1975.",
        }}
      >
        <TimeSeriesChart
          series={longRun}
          xMin={h.first_year}
          xMax={h.last_year}
          yMax={yMaxUne}
          annotations={[...reform("reform_1984_temporary_contracts", "Contratos temporales (1984)"), ...epaBreaks]}
          ariaLabel="Tasa de paro de España y de la media europea desde 1960"
        />
      </Fig>

      <Fig
        id="ratio"
        title={`El paro español superó 1,5 veces el europeo en ${h.years_ratio_ge_1_5} de los ${h.years_since} años desde ${h.hypothesis_from}, y el doble en ${h.years_ratio_ge_2}`}
        dek={`Por década: ${data.ratio_decades.map((d) => `${d.decade}s ×${num(d.mean_ratio, 2)}`).join(", ")}. La excepción es el auge previo a 2008: en ${h.ratio_lowest_since.year} el paro español fue solo ${num(h.ratio_lowest_since.value, 2)} veces el de la UE-15. El máximo, ${num(h.ratio_highest.value, 2)} veces, llegó en ${h.ratio_highest.year}.`}
        legend={ratioSeries}
        sources={[S.ameco]}
        notes={["Cociente calculado por nosotros con las tasas de AMECO del mismo año."]}
        table={<RatioDecadesTable decades={data.ratio_decades} series={ratioSeries} />}
        explain={{
          what: "Cuántas veces es el paro de España el de la media europea. 100 significa «igual que Europa»; 200, «el doble».",
          read: "Por encima de la línea de 100, España tiene más paro que Europa. La línea sube en las crisis y baja en los auges: la brecha no es fija, se agranda cuando la economía cae.",
          not: "Un cociente alto puede venir de que España empeora o de que Europa mejora. Por eso se lee junto al gráfico anterior, que muestra los niveles.",
        }}
      >
        <TimeSeriesChart series={[...refLines, ...ratioSeries]} unit="count" xMin={1971} xMax={h.last_year} annotations={reform("reform_1984_temporary_contracts", "1984")} ariaLabel="Paro de España en relación con la media europea, Europa = 100" />
      </Fig>

      <Fig
        id="paises"
        title={`Desde ${h.hypothesis_from}, el paro medio de España (${pct(m.ESP)}) casi duplica el de Italia (${pct(m.ITA)}), Francia (${pct(m.FRA)}) y Portugal (${pct(m.PRT)})`}
        dek={`Alemania: ${pct(m.DEU)}. Cada país en su panel, con la misma escala vertical. Antes de 1975 España no tenía más paro que sus vecinos.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País de comparación", color: C.ref },
        ]}
        sources={[S.ameco]}
        notes={["Alemania: hasta 1991, Alemania Occidental (RFA); desde 1991, Alemania unificada. Se muestran como dos tramos."]}
        table={
          <SeriesTable
            series={[
              { id: "ESP", label: "España", points: u.amecos.ESP },
              { id: "DEU_W", label: NAMES.DEU_W, points: u.peers.DEU_W },
              ...PEERS.map((area) => ({ id: area, label: NAMES[area], points: u.peers[area] })),
            ]}
          />
        }
        explain={{
          what: "El paro de España frente al de cada país vecino por separado, con la misma escala para que las alturas sean comparables.",
          read: "Italia y Portugal tienen instituciones, clima y estructura productiva parecidos a los de España. Si tienen mucho menos paro, la explicación no puede ser solo «el sur de Europa».",
          not: "No tiene en cuenta cuánto crece la población activa en cada país: en España, la inmigración de 2000–2008 la amplió mucho, y una economía puede crear mucho empleo y aun así no bajar el paro si llegan más personas a buscarlo.",
        }}
      >
        <div className="vizMultiples">
          {PEERS.map((area) => (
            <div key={area}>
              <h3 className="vizPanelTitle">
                España frente a {NAMES[area]}
                <span>
                  Media desde {h.hypothesis_from}: {pct(m.ESP)} frente a {pct(m[area])}
                </span>
              </h3>
              <TimeSeriesChart
                series={[
                  ...(area === "DEU" ? [{ id: "DEU_W", label: "RFA", color: C.ref, points: u.peers.DEU_W }] : []),
                  { id: area, label: NAMES[area], color: C.ref, points: u.peers[area] },
                  { id: "ESP", label: "España", color: C.blue, emphasis: true, points: u.amecos.ESP },
                ]}
                xMin={h.first_year}
                xMax={h.last_year}
                yMax={peerMax}
                height={210}
                ariaLabel={`Tasa de paro de España frente a ${NAMES[area]}`}
              />
            </div>
          ))}
        </div>
      </Fig>

      {regSeries ? (
        <Fig
          id="registrado"
          title={`Encuesta y registro cuentan hoy casi lo mismo (${thousands(reg.last.epa)} frente a ${thousands(reg.last.sepe)} en ${reg.last.year}), pero llegaron a separarse ${thousands(reg.max_gap.diff)} de personas`}
          dek={`La EPA pregunta a una muestra de hogares quién busca empleo; el paro registrado cuenta a quien se inscribe en las oficinas públicas. En ${reg.max_gap.year} la encuesta contaba ${thousands(reg.max_gap.epa)} de parados y el registro ${thousands(reg.max_gap.sepe)}.`}
          legend={regSeries}
          sources={[S.registered, S.ameco]}
          notes={["Paro registrado: media anual de los datos mensuales del SEPE (Ministerio de Trabajo) que publica la OCDE. EPA: parados según la definición de la OIT, en miles, de AMECO."]}
          table={<SeriesTable series={regSeries} unit="count" digits={0} caption="Ver los datos en tabla (miles de personas)" />}
          explain={{
            what: "Dos formas oficiales de contar a los parados en España, en miles de personas.",
            read: "Cuando la línea naranja queda por debajo, hay parados que no se inscriben (por ejemplo, jóvenes sin derecho a prestación). Cuando queda por encima, hay inscritos que la encuesta no considera parados porque no buscan activamente o trabajan unas horas.",
            not: "El registro depende de normas administrativas que cambian: no cuenta como parados a los demandantes con relación laboral (entre ellos, muchos fijos discontinuos sin actividad) y su criterio se ha revisado varias veces. La EPA es la cifra comparable con Europa.",
          }}
        >
          <EmpleoChart series={regSeries} unit="thousands" xMin={1976} xMax={h.last_year} ariaLabel="Parados según la EPA y paro registrado en el SEPE" />
        </Fig>
      ) : null}
    </>
  );
}

export { fmt };
