import Figure from "../components/Figure";
import { C, NAMES, num } from "./sections";

// Connected scatter: spending per pupil (Spain 2022 = 100) against PISA maths, both axes from zero.
// Two legends: colour/line says what a mark is (Spain's path, OECD, peers, regions by ISEC group) and marker shape
// says whether it is a country (circle) or a region (square). Server-rendered SVG that scales with its container.
// Both axes are referenced to Spain in 2022: spending as an index (= 100) and PISA as points above or below its
// score, so the origin of the comparison is explicit and the vertical axis includes zero.
const W = 760;
const H = 560;
const M = { top: 18, right: 24, bottom: 46, left: 96 };
const X_MAX = 160;
const Y_MIN = -40;
const Y_MAX = 50;

const sx = (x) => M.left + (x / X_MAX) * (W - M.left - M.right);
const syd = (d) => M.top + (H - M.top - M.bottom) * (1 - (d - Y_MIN) / (Y_MAX - Y_MIN));

// Label offsets [dx, dy, anchor] chosen so the dense middle of the cloud stays legible.
const SPAIN_LABEL = { 2000: [-8, 4, "end"], 2006: [8, 12, "start"], 2009: [8, -6, "start"], 2012: [6, -9, "start"], 2015: [-8, -6, "end"], 2018: [-8, 14, "end"], 2022: [-10, 4, "end"] };
const PEER_LABEL = { OECD: [6, 16, "start"], DEU: [6, -8, "start"], FRA: [6, -8, "start"], ITA: [6, 30, "start"], PRT: [6, -8, "start"] };

const REGION_LABELS = {
  "Castilla y León": "Castilla y León",
  "Madrid, Comunidad de": "Madrid",
  "País Vasco": "País Vasco",
  Canarias: "Canarias",
  Andalucía: "Andalucía",
  "Navarra, Comunidad Foral de": "Navarra",
  Cataluña: "Cataluña",
  "Murcia, Región de": "Murcia",
};

function Arrow({ from, to, color, width = 1.5, label, offset, sy }) {
  return (
    <g>
      <line x1={sx(from.x)} y1={sy(from.y)} x2={sx(to.x)} y2={sy(to.y)} stroke={color} strokeWidth={width} markerEnd={`url(#arrow-${color.slice(1)})`} />
      <circle cx={sx(from.x)} cy={sy(from.y)} r={3.5} fill="var(--viz-surface, #fff)" stroke={color} strokeWidth={1.5}>
        <title>{`${label} ${from.pisa_year}: gasto ${from.x}, PISA ${from.y}`}</title>
      </circle>
      <circle cx={sx(to.x)} cy={sy(to.y)} r={4} fill={color}>
        <title>{`${label} ${to.pisa_year}: gasto ${to.x}, PISA ${to.y}`}</title>
      </circle>
      <text x={sx(to.x) + offset[0]} y={sy(to.y) + offset[1]} textAnchor={offset[2] || "start"} fontSize={11} fill={color}>
        {label}
      </text>
    </g>
  );
}

export default function StoryScatter({ story }) {
  const path = story.spain_path;
  const base = path.find((p) => p.pisa_year === 2022).y;
  const sy = (score) => syd(score - base);
  const xTicks = [0, 20, 40, 60, 80, 100, 120, 140, 160];
  const yTicks = [-40, -30, -20, -10, 0, 10, 20, 30, 40, 50];
  const regionColor = (row) => (row.isec_above_oecd ? C.aqua : C.orange);
  const markers = [C.blue, C.ref, C.peer];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      role="img"
      aria-label="Gasto por alumno frente a PISA matemáticas: trayectoria de España 2000-2022, media OCDE y países comparables 2012-2022, y comunidades autónomas en 2022"
      style={{ display: "block", maxWidth: W, height: "auto" }}
    >
      <defs>
        {markers.map((color) => (
          <marker key={color} id={`arrow-${color.slice(1)}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
          </marker>
        ))}
      </defs>
      {yTicks.map((tick) => (
        <g key={`y-${tick}`}>
          <line x1={M.left} x2={W - M.right} y1={syd(tick)} y2={syd(tick)} className={tick === 0 ? "tsChart__baseline" : "tsChart__grid"} />
          <text x={M.left - 6} y={syd(tick) + 4} textAnchor="end" className="tsChart__tick">
            {tick > 0 ? `+${tick}` : tick} ({base + tick})
          </text>
        </g>
      ))}
      {xTicks.map((tick) => (
        <g key={`x-${tick}`}>
          <line x1={sx(tick)} x2={sx(tick)} y1={syd(Y_MIN)} y2={syd(Y_MIN) + 4} className="tsChart__baseline" />
          <text x={sx(tick)} y={syd(Y_MIN) + 18} textAnchor="middle" className="tsChart__tick">
            {tick}
          </text>
        </g>
      ))}
      <line x1={sx(0)} x2={sx(0)} y1={M.top} y2={syd(Y_MIN)} className="tsChart__baseline" />
      <line x1={sx(100)} x2={sx(100)} y1={M.top} y2={syd(Y_MIN)} className="tsChart__note" />
      <text x={sx(100) + 4} y={M.top + 12} fontSize={11} className="tsChart__noteLabel">
        España 2022 = 100
      </text>
      <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" fontSize={12} className="tsChart__tick">
        Gasto público por alumno (España 2022 = 100)
      </text>
      <text x={14} y={(M.top + syd(Y_MIN)) / 2} textAnchor="middle" fontSize={12} className="tsChart__tick" transform={`rotate(-90 14 ${(M.top + syd(Y_MIN)) / 2})`}>
        PISA matemáticas: puntos frente a España 2022 (nota)
      </text>

      {story.regions.map((row) => (
        <g key={row.region}>
          <rect x={sx(row.x) - 4} y={sy(row.y) - 4} width={8} height={8} fill={regionColor(row)} opacity={0.9}>
            <title>{`${row.region}: gasto ${row.x}, PISA ${row.y} (ISEC ${row.isec_above_oecd ? "superior" : "inferior"} a la media OCDE)`}</title>
          </rect>
          {REGION_LABELS[row.region] ? (
            <text x={sx(row.x) + 6} y={sy(row.y) - 6} fontSize={10.5} fill={regionColor(row)}>
              {REGION_LABELS[row.region]}
            </text>
          ) : null}
        </g>
      ))}

      {story.peer_arrows.map((arrow) => (
        <Arrow
          key={arrow.area}
          from={arrow.points[0]}
          to={arrow.points[1]}
          color={arrow.area === "OECD" ? C.ref : C.peer}
          width={arrow.area === "OECD" ? 2 : 1.5}
          label={arrow.area === "OECD" ? "OCDE" : NAMES[arrow.area]}
          offset={PEER_LABEL[arrow.area] || [6, 12]}
          sy={sy}
        />
      ))}

      <polyline
        points={path.filter((p) => p.comparable).map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")}
        fill="none"
        stroke={C.blue}
        strokeWidth={2.5}
        strokeLinejoin="round"
      />
      {path.map((p) => (
        <g key={p.pisa_year}>
          <circle cx={sx(p.x)} cy={sy(p.y)} r={5} fill={p.comparable ? C.blue : "var(--viz-surface, #fff)"} stroke={C.blue} strokeWidth={2}>
            <title>{`España ${p.pisa_year}: gasto ${p.x} (año ${p.spending_year}), PISA ${p.y}${p.comparable ? "" : " (no comparable)"}`}</title>
          </circle>
          <text
            x={sx(p.x) + (SPAIN_LABEL[p.pisa_year] || [8, -6])[0]}
            y={sy(p.y) + (SPAIN_LABEL[p.pisa_year] || [8, -6])[1]}
            textAnchor={(SPAIN_LABEL[p.pisa_year] || [0, 0, "start"])[2]}
            fontSize={11}
            fontWeight={700}
            fill={C.blue}
          >
            {p.pisa_year}
          </text>
        </g>
      ))}
    </svg>
  );
}

const pct = (a, b) => Math.round((b / a - 1) * 100);

function Narratives({ items }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "10px 18px", margin: "4px 0 14px", fontSize: "0.86rem", lineHeight: 1.45 }}>
      {items.map(([title, verdict, text]) => (
        <div key={title} style={{ padding: "10px 12px", background: "var(--viz-band)", borderRadius: 6, borderLeft: `3px solid ${verdict === "No" ? C.orange : verdict === "Sí" ? C.aqua : C.ref}` }}>
          <div style={{ fontWeight: 700 }}>
            «{title}» <span style={{ color: "var(--viz-muted)", fontWeight: 400 }}>· {verdict === "No" ? "los datos no lo sostienen" : verdict === "Sí" ? "los datos lo sostienen" : "los datos no lo resuelven"}</span>
          </div>
          <div style={{ color: "var(--viz-ink-2)" }}>{text}</div>
        </div>
      ))}
    </div>
  );
}

export function StoryFigure({ story, sources, h }) {
  const by = Object.fromEntries(story.spain_path.map((p) => [p.pisa_year, p]));
  const peak = by[2009];
  const trough = by[2015];
  const last = by[2022];
  const cut = pct(peak.x, trough.x);
  const rise = pct(trough.x, last.x);
  const arrows = story.peer_arrows.map((a) => ({
    area: a.area,
    spend: pct(a.points[0].x, a.points[1].x),
    score: a.points[1].y - a.points[0].y,
  }));
  const allRightDown = arrows.every((a) => a.spend > 0 && a.score < 0);
  const oecd = arrows.find((a) => a.area === "OECD");
  const group = (flag) => story.regions.filter((row) => row.isec_above_oecd === flag);
  const mean = (rows) => rows.reduce((sum, row) => sum + row.y, 0) / rows.length;
  const hi = group(true);
  const lo = group(false);
  const gap = mean(hi) - mean(lo);
  const xs = story.regions.map((row) => row.x);
  return (
    <Figure
      id="dato-relato"
      title={`El dato mata el relato: con los recortes de 2009 a 2015 el gasto por alumno cayó un ${Math.abs(cut)} % y la nota PISA subió ${trough.y - peak.y} puntos; con un ${rise} % más hasta 2022, bajó ${trough.y - last.y}. Entre comunidades, el origen social explica el ${num(story.r2_isec_regions, 0)} % de las diferencias y el gasto, el ${num(story.r2_spending_regions, 0)} %`}
      dek={`Todo en una imagen: la trayectoria de España en cada ciclo de PISA (línea azul), la media OCDE y cuatro países comparables de 2012 a 2022 (flechas) y las 17 comunidades en 2022 (cuadrados, en verde las de origen social medio por encima de la media OCDE). ${allRightDown ? `Todas las flechas van hacia la derecha y hacia abajo: la OCDE gastó un ${oecd.spend} % más por alumno y perdió ${Math.abs(oecd.score)} puntos.` : ""} Las comunidades de origen social más alto sacan de media ${num(gap, 0)} puntos más, gasten lo que gasten (de ${num(Math.min(...xs), 0)} a ${num(Math.max(...xs), 0)} sobre 100).`}
      legend={[
        { id: "es", label: "España, ciclo a ciclo (2000 hueco: no comparable)", color: C.blue },
        { id: "oecd", label: "Media OCDE, 2012 → 2022", color: C.ref },
        { id: "peers", label: "Alemania, Francia, Italia y Portugal, 2012 → 2022", color: C.peer },
        { id: "hi", label: "Comunidad con ISEC medio superior a la media OCDE", color: C.aqua },
        { id: "lo", label: "Comunidad con ISEC inferior", color: C.orange },
      ]}
      sources={sources}
      notes={[
        `Eje horizontal: ${story.base} Base: ${num(story.spain_base_usd, 0)} dólares PPA de 2020 por alumno (OCDE) y ${num(story.regional_base_eur, 0)} € por alumno (consejerías, 2022). Las dos escalas están referidas a la media de España en 2022, no convertidas entre sí.`,
        `Eje vertical: puntos de PISA matemáticas por encima o por debajo de la nota de España en 2022 (${story.spain_path.find((p) => p.pisa_year === 2022).y}); entre paréntesis, la nota. Los dos ejes toman como referencia a España en 2022 e incluyen el cero.`,
        "Marcas: círculo = país o media; cuadrado = comunidad autónoma; flecha = de 2012 a 2022. Para PISA 2006 se usa el gasto de 2005 (la OCDE no publica 2006).",
        `Origen social (ISEC): grupo de comunidades «con un ISEC superior al Promedio de la OCDE» según el informe español de PISA 2022 (Madrid, País Vasco, Asturias, Castilla y León, Galicia, Cantabria y Navarra). R² del ISEC entre comunidades y ciudades autónomas: ${num(story.r2_isec_regions, 1)} % (19 territorios; Ceuta y Melilla, en los extremos, lo elevan), y entre países de la OCDE y la UE: ${num(story.r2_isec_countries, 1)} % (INEE). R² del gasto entre las 17 comunidades: ${num(story.r2_spending_regions, 0)} % (cálculo propio con estos datos; Ceuta y Melilla no tienen consejería).`,
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Punto</th>
                  <th scope="col">Gasto (España 2022 = 100)</th>
                  <th scope="col">PISA matemáticas</th>
                </tr>
              </thead>
              <tbody>
                {story.spain_path.map((p) => (
                  <tr key={`es-${p.pisa_year}`}>
                    <td>
                      España {p.pisa_year}
                      {p.spending_year !== p.pisa_year ? ` (gasto de ${p.spending_year})` : ""}
                      {p.comparable ? "" : " (no comparable)"}
                    </td>
                    <td>{num(p.x)}</td>
                    <td>{p.y}</td>
                  </tr>
                ))}
                {story.peer_arrows.flatMap((a) =>
                  a.points.map((p) => (
                    <tr key={`${a.area}-${p.pisa_year}`}>
                      <td>
                        {a.area === "OECD" ? "Media OCDE" : NAMES[a.area]} {p.pisa_year}
                      </td>
                      <td>{num(p.x)}</td>
                      <td>{p.y}</td>
                    </tr>
                  )),
                )}
                {story.regions.map((row) => (
                  <tr key={row.region}>
                    <td>
                      {row.region} 2022 · ISEC {row.isec_above_oecd ? "superior" : "inferior"} a la OCDE
                    </td>
                    <td>{num(row.x)}</td>
                    <td>{row.y}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Narratives
        items={[
          [
            "Más dinero, mejores resultados",
            "No",
            `No a escala nacional: España gastó más en 2009 que en 2015 y sacó menos nota; la OCDE y los cuatro países comparables gastaron más en 2022 que en 2012 y todos bajaron. Entre comunidades, el gasto explica el ${num(story.r2_spending_regions, 0)} % de las diferencias. Y el eje solo mide gasto público: las familias ponen además el ${num(h.familyShare, 0)} % del total.`,
          ],
          [
            "Los recortes hundieron la educación",
            "No",
            `Entre 2009 y 2015 el gasto por alumno cayó un ${Math.abs(cut)} % y PISA matemáticas pasó de ${peak.y} a ${trough.y}. La caída llegó en 2022, con más gasto y tras la pandemia, y fue general en la OCDE.`,
          ],
          [
            "Las diferencias entre comunidades son de origen social",
            "Sí",
            `En buena parte: el origen social medio explica el ${num(story.r2_isec_regions, 0)} % de las diferencias en PISA entre comunidades y ciudades autónomas, frente al ${num(story.r2_spending_regions, 0)} % del gasto. Pero el cambio en la mezcla de alumnos explica poco de la caída nacional desde 2012 (${num(h.compositionPoints)} de ${h.compositionDrop} puntos; ver «Equidad»).`,
          ],
          [
            "La educación mejora con cada generación",
            "?",
            `En parte: los jóvenes de 16 a 24 años sacan ${h.piaacYoung} en comprensión lectora (PIAAC 2023) y los de 55 a 65, ${h.piaacOld}; hay mucho menos abandono. Pero la distancia con la OCDE es mayor entre los jóvenes (${Math.abs(h.gapYoung)} puntos) que entre los mayores (${Math.abs(h.gapOld)}): España ha mejorado, la OCDE más.`,
          ],
          [
            "¿Sirve o no sirve gastar?",
            "?",
            "Queda abierto: medias nacionales y 17 comunidades no permiten medir el efecto de un euro más. El gasto actúa con años de retraso, se reparte en salarios, edificios o apoyo y cambia a la vez que la población, las leyes y la pandemia.",
          ],
        ]}
      />
      <div style={{ overflowX: "auto" }} tabIndex={0} aria-label="Gráfico desplazable en pantallas estrechas">
        <div style={{ minWidth: 600 }}>
          <StoryScatter story={story} />
        </div>
      </div>
      <p className="vizFigure__dek" style={{ marginTop: 10 }}>
        Qué no puede mostrar: causalidad; el efecto retardado del gasto sobre alumnos que llevan años en el sistema; cuánto de la caída de 2022 es
        pandemia; ni la mejora de la permanencia (menos repetición y abandono), que cambia quién llega a cada curso aunque PISA examine a alumnos de 15 años
        escolarizados, estén en el curso que estén.
      </p>
    </Figure>
  );
}
