import Figure from "../components/Figure";
import { Explain } from "./explain";
import { C, num } from "./common";

// «El dato mata el relato»: one connected scatter that holds both stories at once. No second y-scale: x and y are two
// variables on their own zero-based axes, joined year by year; colour (credit growth) and marker fill (where the
// household count comes from) are the two legends.
const W = 760;
const H = 460;
const M = { top: 24, right: 24, bottom: 52, left: 56 };
const NEG = ["#f6d3c2", "#eb6834", "#a8401a"];
const POS = ["#cfe0f6", "#2a78d6", "#174a8c"];

function creditColor(value) {
  if (value == null) return "#b4b2a9";
  const ramp = value < 0 ? NEG : POS;
  const t = Math.min(1, Math.abs(value) / 20);
  return t < 0.25 ? ramp[0] : t < 0.6 ? ramp[1] : ramp[2];
}

// Years close to another labelled year (2013/2015, 2014/2016) are left unlabelled so no two labels collide.
const LABELLED = new Set([1995, 1998, 2001, 2004, 2007, 2009, 2011, 2013, 2019, 2021, 2023, 2025]);
const avg = (rows, key) => rows.reduce((sum, row) => sum + row[key], 0) / rows.length;

export default function StoryFigure({ story, composition, source }) {
  if (!story?.length) return null;
  const xMax = Math.ceil(Math.max(...story.map((p) => p.x)) * 2) / 2;
  const yMax = Math.ceil(Math.max(...story.map((p) => p.y)) / 2) * 2;
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;
  const sx = (v) => M.left + (v / xMax) * innerW;
  const sy = (v) => M.top + innerH - (v / yMax) * innerH;
  const boom = story.filter((p) => p.year >= 1998 && p.year <= 2007);
  // Windows touched by the 2021 EPA reweighting are drawn but kept out of the averages quoted in the title.
  const scarce = story.filter((p) => p.year >= 2014 && p.basis !== "epa_2021");
  const first = story[0];
  const lastPoint = story[story.length - 1];
  const yearOf = (y) => story.find((p) => p.year === y);
  const p2007 = yearOf(2007);
  const p2013 = yearOf(2013);
  const xTicks = [];
  for (let v = 0; v <= xMax + 1e-9; v += 0.5) xTicks.push(v);
  const yTicks = [];
  for (let v = 0; v <= yMax; v += 2) yTicks.push(v);
  const hollow = (p) => p.basis !== "epa";
  const decLast = composition?.decomposition?.[composition.decomposition.length - 1];
  const cohortPeak = composition?.cohort_25_39?.ES?.persons?.reduce((a, b) => (b.value > a.value ? b : a));

  return (
    <Figure
      id="el-dato"
      title={`Treinta años en un gráfico: de ${boom[0].year} a 2007 la vivienda se encareció terminando ${num(avg(boom, "x"), 1)} viviendas por hogar nuevo con el crédito creciendo un ${num(avg(boom, "credit_growth"), 0)} % al año; desde 2014 se encarece con ${num(avg(scarce, "x"), 1)} y el crédito ${avg(scarce, "credit_growth") < 0 ? "menguando" : "creciendo poco"}`}
      dek={`Cada punto es un año. Hacia la derecha, más viviendas terminadas por cada hogar nuevo; hacia arriba, más años de renta del hogar mediano para pagar un piso (Banco de España). El color es el crédito a los hogares para comprar vivienda: azul si crece, naranja si mengua. El precio sube en dos situaciones opuestas: a la derecha y en azul (1998–2007: se construía mucho y el crédito se desbordaba) y a la izquierda y en naranja (2014–${lastPoint.year}: se construye poco y el crédito no crece). Ningún relato de una sola causa explica las dos.${decLast && cohortPeak ? ` Y la demanda de esta segunda fase no es la de la generación del baby boom, que se encoge desde ${cohortPeak.year}: el ${num((decLast.population_effect / decLast.total) * 100, 0)} % de los hogares nuevos de ${decLast.from}–${decLast.to} se debe al aumento de población, es decir, a la inmigración.` : ""}`}
      sources={[
        source("bde_indicadores_vivienda", "Banco de España: precio / renta del hogar, crédito a hogares para vivienda y tipos de interés"),
        source("mivau_boletin", "Ministerio de Vivienda: viviendas terminadas"),
      ]}
      notes={[
        "Viviendas por hogar nuevo: viviendas terminadas (libres + protegidas) entre hogares nuevos de la EPA, sumando los tres últimos años para suavizar el ruido de la encuesta. Antes de 2003 no hay hogares de la EPA y se usa la media anual entre censos (puntos huecos). Los años cuya ventana incluye 2021, cuando la EPA se reponderó, también van huecos: su posición horizontal es poco fiable.",
        "Precio: precio medio de una vivienda libre de 93,75 m² entre la renta bruta estimada del hogar mediano (Banco de España). Es la única serie continua de 1995 a hoy; con salarios y precio de compraventa del INE la forma es la misma.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Año</th>
                  <th scope="col">Viviendas terminadas por hogar nuevo</th>
                  <th scope="col">Años de renta del hogar</th>
                  <th scope="col">Crédito para vivienda, variación anual</th>
                  <th scope="col">Tipo de interés de las hipotecas</th>
                  <th scope="col">Hogares de</th>
                </tr>
              </thead>
              <tbody>
                {[...story].reverse().map((p) => (
                  <tr key={p.year}>
                    <td>{p.year}</td>
                    <td>{num(p.x, 2)}</td>
                    <td>{num(p.y, 2)}</td>
                    <td>{p.credit_growth != null ? `${num(p.credit_growth)} %` : "—"}</td>
                    <td>{p.rate != null ? `${num(p.rate, 2)} %` : "—"}</td>
                    <td>{p.basis === "epa" ? `EPA ${p.window[0]}–${p.window[p.window.length - 1]}` : p.basis === "epa_2021" ? "EPA (incluye 2021)" : p.basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <ul className="vizLegend" aria-label="Leyenda">
        <li>
          <span className="vizLegend__key" style={{ background: POS[2], width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />
          Crédito para vivienda creciendo (más oscuro, más deprisa)
        </li>
        <li>
          <span className="vizLegend__key" style={{ background: NEG[1], width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />
          Crédito menguando
        </li>
        <li>
          <span className="vizLegend__key" style={{ background: "transparent", border: `2px solid ${C.ref}`, width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />
          Punto hueco: hogares de los censos o ventana con la ruptura de la EPA de 2021
        </li>
      </ul>
      <div className="hvScatter">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Viviendas terminadas por hogar nuevo frente a años de renta para comprar un piso, 1995 a hoy" style={{ display: "block", maxWidth: "100%", height: "auto" }}>
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line x1={M.left} x2={W - M.right} y1={sy(v)} y2={sy(v)} className={v === 0 ? "tsChart__baseline" : "tsChart__grid"} />
            <text x={M.left - 8} y={sy(v) + 4} textAnchor="end" className="tsChart__tick">
              {v}
            </text>
          </g>
        ))}
        {xTicks.map((v) => (
          <g key={`x${v}`}>
            <line x1={sx(v)} x2={sx(v)} y1={M.top} y2={M.top + innerH} className={v === 0 ? "tsChart__baseline" : "tsChart__grid"} />
            <text x={sx(v)} y={M.top + innerH + 18} textAnchor="middle" className="tsChart__tick">
              {num(v, 1)}
            </text>
          </g>
        ))}
        <line x1={sx(1)} x2={sx(1)} y1={M.top} y2={M.top + innerH} className="tsChart__note" strokeDasharray="5 4" />
        {/* Low on the reference line: no year falls below 3 years of income, so the label never meets a point. */}
        <text x={sx(1) + 6} y={sy(1.6)} className="tsChart__noteLabel">
          1 vivienda por hogar nuevo
        </text>
        <text x={sx(1) - 6} y={M.top + innerH - 8} textAnchor="end" className="tsChart__noteLabel">
          ← se construye menos de lo que crecen los hogares
        </text>
        <text x={sx(1) + 6} y={M.top + innerH - 8} className="tsChart__noteLabel">
          se construye más →
        </text>
        <text x={M.left + innerW / 2} y={H - 8} textAnchor="middle" className="tsChart__tick">
          Viviendas terminadas por cada hogar nuevo (media de 3 años)
        </text>
        <text x={14} y={M.top + innerH / 2} textAnchor="middle" transform={`rotate(-90 14 ${M.top + innerH / 2})`} className="tsChart__tick">
          Años de renta del hogar para un piso
        </text>
        {story.slice(1).map((p, i) => {
          const prev = story[i];
          return (
            <line
              key={`l${p.year}`}
              x1={sx(prev.x)}
              y1={sy(prev.y)}
              x2={sx(p.x)}
              y2={sy(p.y)}
              stroke={C.peer}
              strokeWidth={1.6}
              strokeDasharray={hollow(p) || hollow(prev) ? "4 4" : undefined}
            />
          );
        })}
        {story.map((p) => (
          <g key={`p${p.year}`}>
            <circle
              cx={sx(p.x)}
              cy={sy(p.y)}
              r={6.5}
              fill={hollow(p) ? "var(--viz-surface)" : creditColor(p.credit_growth)}
              stroke={creditColor(p.credit_growth)}
              strokeWidth={hollow(p) ? 2.5 : 1}
            >
              <title>
                {`${p.year}: ${num(p.x, 2)} viviendas por hogar nuevo; ${num(p.y, 1)} años de renta; crédito ${p.credit_growth != null ? `${num(p.credit_growth)} %` : "s. d."}; tipo ${p.rate != null ? `${num(p.rate, 2)} %` : "s. d."}`}
              </title>
            </circle>
            {LABELLED.has(p.year) ? (
              <text x={sx(p.x) + 9} y={sy(p.y) - 7} className="tsChart__endLabel">
                {p.year}
              </text>
            ) : null}
          </g>
        ))}
      </svg>
      </div>
      <Explain
        shows="En un solo gráfico, las dos explicaciones que suelen enfrentarse: «falta construir» (eje horizontal) y «es el crédito» (color), frente al precio (eje vertical), año a año desde 1995."
        read={`Sigue la línea por años. De 1998 a 2007 sube y va hacia la derecha en azul oscuro: se terminaban más viviendas que hogares nuevos y aun así el precio pasó de ${num(yearOf(1998)?.y ?? first.y, 1)} a ${num(p2007.y, 1)} años de renta, con el crédito creciendo en torno al 20 % anual. De 2008 a 2013 baja mientras el crédito se frena y empieza a menguar (del azul al naranja). Desde 2014 se queda a la izquierda de la línea discontinua y sube en tonos claros: se construye poco y el precio vuelve a subir (${num(p2013.y, 1)} → ${num(lastPoint.y, 1)}) sin un boom de crédito, incluso con tipos al alza en 2023.`}
        notSay="No reparte la subida entre causas ni descarta otras que no están en el gráfico: tipos de interés históricamente bajos de 2015 a 2021, compradores al contado e inversores, demanda extranjera, pisos turísticos y diferencias entre comunidades (ver los gráficos regionales). Tampoco dice dónde faltan viviendas: es una media nacional."
      />
    </Figure>
  );
}
