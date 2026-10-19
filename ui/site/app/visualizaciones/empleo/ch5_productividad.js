import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import { Chapter, Fig } from "./blocks";
import { C, NAMES, PEER_LEGEND, PEERS, at, back, constant, sources } from "./common.mjs";
import { num } from "./format.mjs";

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const WAGE_AREAS = ["ESP", "EU27", "DEU", "FRA", "ITA", "PRT"];

export default function ChapterProductividad({ data }) {
  const h = data.headline;
  const S = sources(data);
  const p = data.productivity;
  const g = h.productivity_growth_pct;
  const prod = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: p.index_1995.ESP },
    { id: "EU27", label: "UE-27", color: C.ref, points: p.index_1995.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: p.index_1995[area] })),
  ];
  const level = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: p.level_vs_eu27.ESP },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: p.level_vs_eu27[area] })),
    { id: "eu", label: "Media de la UE-27 = 100", shortLabel: "UE-27", color: C.ref, points: constant(100, h.productivity_base, h.level_last_year) },
  ];
  const b08 = data.composition?.base_year.productivity.rows.find((r) => r.base === 2008) || { ESP: NaN, EU27: NaN };
  const wBases = data.composition?.base_year.real_wage.rows || [];
  const wBehind = wBases.filter((r) => r.ESP < r.EU27).map((r) => r.base);
  const p08 = at(p.index_1995.ESP, 2008);
  const p13 = at(p.index_1995.ESP, 2013);
  const lvFirst = h.level_vs_eu_first.ESP;
  const lvLast = h.level_vs_eu_last.ESP;
  const peersSlower = Object.entries(g).filter(([area, value]) => area !== "ESP" && value < g.ESP);

  const wp = data.wages_productivity;
  const wLast = (area) => wp?.[area]?.wage.at(-1)?.value;
  const pLast = (area) => wp?.[area]?.productivity.at(-1)?.value;
  const wageMax = wp ? Math.max(...WAGE_AREAS.flatMap((area) => [...(wp[area]?.wage || []), ...(wp[area]?.productivity || [])].map((q) => q.value))) : 0;
  const wageYear = wp?.ESP?.wage.at(-1)?.year;

  const e = data.employment_rate;
  const emp = [
    { id: "es_h", label: "España (serie histórica 1993–2020)", shortLabel: "España, hist.", color: C.aqua, noEndLabel: true, points: e.historical.ESP },
    { id: "eu_h", label: "UE-27 (serie histórica)", shortLabel: "UE-27, hist.", color: C.yellow, noEndLabel: true, points: e.historical.EU27 },
    { id: "es", label: "España (serie vigente)", shortLabel: "España", color: C.blue, emphasis: true, points: e.current.ESP },
    { id: "eu", label: "UE-27 (serie vigente)", shortLabel: "UE-27", color: C.ref, points: e.current.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: e.current[area] })),
  ];
  const euEmp = new Map(e.current.EU27.map((pt) => [pt.year, pt.value]));
  const empGaps = e.current.ESP.filter((pt) => euEmp.has(pt.year)).map((pt) => ({ year: pt.year, gap: euEmp.get(pt.year) - pt.value }));
  const empGapMax = empGaps.reduce((a, b) => (b.gap > a.gap ? b : a));
  const empGapLast = empGaps.at(-1);

  return (
    <>
      <Chapter id="cap-productividad" kicker="Capítulo 5" title="Productividad, salarios y cuánta gente trabaja">
        <p>
          A largo plazo, los salarios solo suben de forma sostenida si sube lo que se produce por hora. La segunda parte de la hipótesis dice que
          en España eso apenas ha ocurrido desde 1995. Aquí se mide, junto con lo que ha pasado con los salarios reales.
        </p>
      </Chapter>

      <Fig
        id="productividad"
        title={`Desde ${h.productivity_base}, la productividad por hora creció un ${num(g.ESP)} % en España y un ${num(g.EU27)} % en la UE-27; desde 2008, al mismo ritmo (${num(b08.ESP)} % frente a ${num(b08.EU27)} %)`}
        dek={`PIB en volumen por hora trabajada, ${h.productivity_base} = 100. ${h.productivity_base} es el primer año de la serie de niveles y el de mayor ventaja de España (producía por hora un ${num(lvFirst - 100, 0)} % más que la media de la UE), así que empezar ahí agranda la distancia; la comparación desde cinco años base está en el capítulo 7. Alemania +${num(g.DEU)} %, Portugal +${num(g.PRT)} %, Francia +${num(g.FRA)} %. ${peersSlower.length ? `Solo ${peersSlower.map(([a]) => NAMES[a]).join(" y ")} creció menos (+${num(peersSlower[0][1])} %).` : ""}`}
        legend={[{ id: "ESP", label: "España", color: C.blue }, { id: "EU27", label: "UE-27", color: C.ref }, PEER_LEGEND]}
        sources={[S.eurostat("nama_10_lp_ulc")]}
        notes={["Índice reescalado por nosotros a 1995 = 100 desde el índice 2015 = 100 de Eurostat (productividad real por hora, RLPR_HW)."]}
        table={<SeriesTable series={prod} unit="count" digits={1} />}
        explain={{
          what: "Cuánto se produce por cada hora trabajada, descontada la inflación, tomando 1995 como punto de partida.",
          read: `Una línea plana significa que cada hora de trabajo produce lo mismo que hace treinta años. España creció poco, aunque más que Italia. Entre 2008 y 2013 su índice pasó de ${num(p08)} a ${num(p13)}, más que en los trece años anteriores, porque se destruyeron primero los empleos menos productivos (construcción): es un efecto composición, no una mejora de eficiencia.`,
          not: "La media de la UE-27 incluye a los países del Este, que crecen deprisa porque parten de niveles bajos: la comparación justa es con Francia, Italia y Alemania. Tampoco separa la productividad de las empresas de la del sector público.",
        }}
      >
        <TimeSeriesChart series={back(prod)} unit="count" xMin={h.productivity_base} xMax={h.productivity_last} ariaLabel="Productividad por hora trabajada, índice 1995 = 100" />
      </Fig>

      <Fig
        id="nivel"
        title={`España pasó de producir por hora un ${num(lvFirst - 100, 0)} % más que la media de la UE-27 a un ${num(100 - lvLast, 0)} % menos`}
        dek={`Nivel del PIB por hora trabajada en dólares de paridad de poder de compra constantes, media de la UE-27 = 100: España ${num(lvFirst)} en ${h.productivity_base} y ${num(lvLast)} en ${h.level_last_year}. Alemania, Francia e Italia siguen muy por encima; Portugal, por debajo.`}
        legend={level.filter((s) => s.color !== C.peer).concat([PEER_LEGEND])}
        sources={[S.pdb]}
        notes={["Cociente calculado por nosotros sobre el PIB por hora en dólares PPA a precios constantes de la OCDE."]}
        table={<SeriesTable series={level} unit="count" digits={1} />}
        explain={{
          what: "Cuánto produce una hora de trabajo en cada país comparado con la media europea (100), ajustando por lo que cuestan las cosas en cada país.",
          read: "Por encima de 100, una hora rinde más que la media europea. España ha ido perdiendo posición mientras el Este convergía; Italia ha perdido aún más.",
          not: "Las paridades de poder de compra tienen varios puntos de margen de error en los niveles entre países: importan más la tendencia y el orden que la cifra exacta.",
        }}
      >
        <TimeSeriesChart series={back(level)} unit="count" xMin={h.productivity_base} xMax={h.level_last_year} ariaLabel="PIB por hora trabajada respecto a la UE-27" />
      </Fig>

      {wp?.ESP ? (
        <Fig
          id="salarios"
          title={`Desde ${h.productivity_base}, el salario real por asalariado subió un ${num(wLast("ESP") - 100)} % en España y la productividad por ocupado un ${num(pLast("ESP") - 100)} %; en la UE-27, un ${num(wLast("EU27") - 100)} % y un ${num(pLast("EU27") - 100)} %`}
          dek={`${wBehind.length ? `España queda por detrás de la UE empezando en ${wBehind.join(", ")}; solo desde 2019 va por delante. ` : ""}Italia es el único país del grupo donde el salario real cayó (${num(wLast("ITA") - 100)} %). En Francia (${num(wLast("FRA") - 100)} %) y Portugal (${num(wLast("PRT") - 100)} %) los salarios crecieron incluso más que la productividad. Cada país en su panel, misma escala.`}
          legend={[
            { id: "wage", label: "Remuneración real por asalariado", color: C.blue },
            { id: "prod", label: "PIB real por ocupado", color: C.orange },
          ]}
          sources={[S.ameco]}
          notes={[
            `Índices reescalados por nosotros a ${h.productivity_base} = 100. Remuneración: sueldo bruto más cotizaciones de la empresa por asalariado, deflactada con los precios del consumo privado (AMECO RWCDC). Productividad: PIB a precios de 2015 por ocupado (AMECO RVGDE). Último año: ${wageYear}.`,
          ]}
          table={
            <SeriesTable
              series={WAGE_AREAS.filter((area) => wp[area]).flatMap((area) => [
                { id: `${area}-w`, label: `${NAMES[area]}: salario real`, points: wp[area].wage },
                { id: `${area}-p`, label: `${NAMES[area]}: productividad`, points: wp[area].productivity },
              ])}
              unit="count"
              digits={1}
            />
          }
          explain={{
            what: "Cómo han evolucionado, desde 1995, el poder de compra del coste salarial por asalariado y lo que produce cada ocupado.",
            read: "Si la línea azul va por debajo de la naranja, los salarios reales crecen menos que la productividad: una parte mayor de lo producido va a beneficios o a otras rentas. En España las dos líneas apenas han subido: el problema principal es que la productividad crece poco.",
            not: "Usa la productividad por ocupado (no por hora) para que sea comparable con el salario por asalariado; si se acortan las jornadas, ambas bajan. Tampoco muestra la distribución: el salario medio puede subir mientras el mediano no.",
          }}
        >
          <div className="vizMultiples">
            {WAGE_AREAS.filter((area) => wp[area]).map((area) => (
              <div key={area}>
                <h3 className="vizPanelTitle">
                  {NAMES[area]}
                  <span>
                    Salario {num(wLast(area) - 100)} %, productividad {num(pLast(area) - 100)} %
                  </span>
                </h3>
                <TimeSeriesChart
                  series={[
                    { id: "prod", label: "PIB real por ocupado", shortLabel: "Productividad", color: C.orange, points: wp[area].productivity },
                    { id: "wage", label: "Remuneración real por asalariado", shortLabel: "Salario", color: C.blue, emphasis: true, points: wp[area].wage },
                  ]}
                  unit="count"
                  xMin={h.productivity_base}
                  xMax={wageYear}
                  yMax={wageMax}
                  height={200}
                  ariaLabel={`Salario real y productividad, ${NAMES[area]}`}
                />
              </div>
            ))}
          </div>
        </Fig>
      ) : null}

      <Fig
        id="tasa-empleo"
        title={`Trabaja el ${pct(h.emp_es_last)} de la población de 20 a 64 años en España, frente al ${pct(h.emp_eu_last)} en la UE-27`}
        dek={`La distancia con la UE-27 pasó de ${num(empGapMax.gap)} puntos en ${empGapMax.year}, la mayor de la serie, a ${num(empGapLast.gap)} en ${empGapLast.year}.`}
        legend={emp.filter((s) => s.color !== C.peer).concat([PEER_LEGEND])}
        sources={[S.eurostat("lfsi_emp_a"), S.eurostat("lfsi_emp_a_h")]}
        notes={["La serie histórica (1993–2020) y la vigente se solapan; no se empalman."]}
        table={<SeriesTable series={emp} />}
        explain={{
          what: "Qué parte de las personas de 20 a 64 años tiene empleo.",
          read: `Es la otra cara del paro y no depende de quién dice estar buscando trabajo. Desde ${empGapMax.year}, el año de mayor distancia, España ha reducido su brecha con Europa de ${num(empGapMax.gap)} a ${num(empGapLast.gap)} puntos: el empleo crece, pero la población activa también.`,
          not: "No distingue jornada completa de parcial ni la calidad del empleo; y una tasa alta puede convivir con mucho paro si mucha gente quiere trabajar.",
        }}
      >
        <TimeSeriesChart series={back(emp)} xMin={1993} xMax={h.emp_last_year} yMax={100} ariaLabel="Tasa de empleo de 20 a 64 años" />
      </Fig>
    </>
  );
}
