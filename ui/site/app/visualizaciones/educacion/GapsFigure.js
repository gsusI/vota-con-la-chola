import Figure from "../components/Figure";
import { C, Explain, num } from "./sections";

// «¿Dónde está la diferencia?»: every PISA maths gap of 2022 on one scale from zero, ranked, with the gap that is left
// when pupils of the same socio-economic status (ISEC) are compared. HTML rows (not SVG) so labels stay readable on phones.
const SCALE = 100;
const TICKS = [0, 25, 50, 75, 100];
const MARK = 12;

const REGION_SHORT = {
  "Asturias, Principado de": "Asturias",
  "Madrid, Comunidad de": "Madrid",
};

const short = (region) => REGION_SHORT[region] || region;
const at = (value) => `max(0px, calc(${(value / SCALE) * 100}% - ${MARK / 2}px))`;

function Marker({ value, kind }) {
  const style = {
    position: "absolute",
    top: "50%",
    left: at(value),
    width: MARK,
    height: MARK,
    marginTop: -MARK / 2,
    borderRadius: "50%",
    boxSizing: "border-box",
  };
  if (kind === "raw") Object.assign(style, { background: C.orange });
  if (kind === "adjusted") Object.assign(style, { background: C.aqua });
  if (kind === "school") Object.assign(style, { background: "var(--viz-surface)", border: `3px solid ${C.aqua}` });
  if (kind === "context") Object.assign(style, { background: C.ref });
  return <span aria-hidden="true" style={style} />;
}

function Track({ marks, label }) {
  const values = marks.map((m) => m.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
      <span style={{ position: "relative", flex: "1 1 auto", height: 22, minWidth: 120 }}>
        {TICKS.map((t) => (
          <span
            key={t}
            aria-hidden="true"
            style={{ position: "absolute", left: `${t}%`, top: 0, bottom: 0, width: 1, background: t ? "var(--viz-grid)" : "var(--viz-axis)" }}
          />
        ))}
        {hi > lo ? (
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              top: "50%",
              height: 3,
              marginTop: -1.5,
              left: `${(lo / SCALE) * 100}%`,
              width: `${((hi - lo) / SCALE) * 100}%`,
              background: "var(--viz-peer)",
            }}
          />
        ) : null}
        {marks.map((m) => (
          <Marker key={m.kind} value={m.value} kind={m.kind} />
        ))}
      </span>
      <span className="vizBars__value" style={{ minWidth: "7.5em" }}>
        {label}
      </span>
    </span>
  );
}

export function GapsFigure({ data, sources }) {
  const g = data.gaps;
  const row = (id) => g.rows.find((r) => r.id === id);
  const escs = row("escs");
  const regions = row("regions");
  const priv = row("private");
  const imm = row("immigrant");
  const gender = row("gender");
  const change = row("change");
  const oecd = row("oecd");
  const times = Math.round(escs.raw / change.raw);
  const muted = { color: "var(--viz-muted)", fontWeight: 400 };
  const rows = [
    {
      id: "escs",
      label: "Origen social: el 25 % de alumnos más favorecido frente al 25 % menos",
      note: `OCDE: ${escs.oecd}. Dentro de cada comunidad, de ${escs.regions_min[1]} (${escs.regions_min[0]}) a ${escs.regions_max[1]} (${escs.regions_max[0]})`,
      marks: [{ kind: "raw", value: escs.raw }],
      value: `${escs.raw}`,
    },
    {
      id: "regions",
      label: `Comunidades: ${regions.best} (${regions.best_value}) frente a ${regions.worst} (${regions.worst_value})`,
      note: `El origen social medio de cada comunidad explica el ${num(regions.r2_isec, 0)} % de estas diferencias; el gasto por alumno, el ${num(regions.r2_spending, 0)} %`,
      marks: [{ kind: "raw", value: regions.raw }],
      value: `${regions.raw}`,
    },
    {
      id: "private",
      label: "Centros privados y concertados frente a públicos",
      note: `${priv.public_share} % del alumnado va a la pública. OCDE: ${priv.oecd} puntos de diferencia bruta`,
      marks: [
        { kind: "raw", value: priv.raw },
        { kind: "adjusted", value: priv.adjusted },
        { kind: "school", value: priv.adjusted_school },
      ],
      value: `${priv.raw} → ${priv.adjusted} → ${priv.adjusted_school}`,
    },
    {
      id: "immigrant",
      label: "Alumnado nativo frente a inmigrante",
      note: `El ${num(imm.share, 0)} % del alumnado de 15 años es de origen inmigrante`,
      marks: [
        { kind: "raw", value: imm.raw },
        { kind: "adjusted", value: imm.adjusted },
      ],
      value: `${imm.raw} → ${imm.adjusted}`,
    },
    {
      id: "change",
      label: `Caída de España desde ${change.from} (${change.first} → ${change.last})`,
      note: "Referencia: lo que más se discute",
      marks: [{ kind: "context", value: change.raw }],
      value: `${change.raw}`,
    },
    {
      id: "gender",
      label: "Chicos frente a chicas",
      note: `OCDE: ${gender.oecd}. En lectura, al revés: las chicas sacan ${gender.reading} más`,
      marks: [{ kind: "raw", value: gender.raw }],
      value: `${gender.raw}`,
    },
    {
      id: "oecd",
      label: `España (${oecd.spain}) frente a la media OCDE (${oecd.oecd_value})`,
      note: "Referencia",
      marks: [{ kind: "context", value: oecd.raw }],
      value: `${oecd.raw}`,
    },
  ];
  const caseOf = (region, school) => g.cases.find((c) => c.region === region && c.school === school)?.value;
  const spain = data.headline.math_2022;
  const cases = [
    { label: "Centro público en Canarias", value: caseOf("Canarias", "public") },
    { label: "Centro público en Andalucía", value: caseOf("Andalucía", "public") },
    { label: "Media de España", value: spain, isMean: true },
    { label: "Centro privado o concertado en Madrid", value: caseOf("Madrid, Comunidad de", "private") },
    { label: "Centro privado o concertado en Castilla y León", value: caseOf("Castilla y León", "private") },
    { label: "Centro privado o concertado en Asturias", value: caseOf("Asturias, Principado de", "private") },
  ].filter((c) => c.value != null);
  const caseMax = 550;
  return (
    <Figure
      id="donde-diferencia"
      title={`Dentro de España, el origen familiar separa ${escs.raw} puntos de PISA: ${times} veces lo que ha caído la nota desde ${change.from} y más que cualquier diferencia entre comunidades o entre la pública y la concertada`}
      dek={`Cada fila es una brecha en puntos de PISA matemáticas ${g.year}, todas en la misma escala desde cero. El punto naranja es la diferencia tal cual; el verde, la que queda al comparar alumnos del mismo origen social; el círculo hueco, la que queda si además se compara el origen social medio del centro. La concertada y la privada sacan ${priv.raw} puntos más que la pública, pero ${priv.adjusted} a igual origen social del alumno y ${priv.adjusted_school} si además se iguala el del centro. El alumnado inmigrante saca ${imm.raw} menos, pero ${imm.adjusted} a igual origen social. Al lado, las dos cifras que más se discuten son pequeñas: ${change.raw} puntos perdidos desde ${change.from} y ${oecd.raw} de distancia con la OCDE.`}
      legend={[
        { id: "raw", label: "Brecha tal cual", color: C.orange },
        { id: "adj", label: "A igual origen social del alumno (ISEC)", color: C.aqua },
        { id: "ctx", label: "Referencia: cambio en el tiempo y distancia con la OCDE", color: C.ref },
      ]}
      legendKind="bar"
      sources={sources}
      notes={[
        `${g.notes} Brecha por origen social: diferencia entre el cuarto superior e inferior del índice ISEC (estudios y profesión de los padres, recursos en casa). Titularidad: «privados» incluye los concertados, financiados al menos en parte con fondos públicos (INEE). Ajustes del INEE (regresión del rendimiento sobre el ISEC del alumno y, en el segundo, también del centro) y de la nota de país de la OCDE (inmigración).`,
        `Casos tipo: medias publicadas por comunidad y titularidad del centro (INEE, Tabla 3.3.b). No son alumnos concretos: dentro de cada celda conviven familias de todo origen social, y el informe no publica el cruce comunidad × titularidad × ISEC. Las puntuaciones por cuarto del ISEC solo están en figuras (imagen) y en oecd.org, que bloquea la descarga: por eso se muestra la brecha, no los niveles.`,
      ]}
      table={
        <details className="vizTable">
          <summary>Ver las brechas en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Brecha (puntos de PISA matemáticas, {g.year})</th>
                  <th scope="col">Tal cual</th>
                  <th scope="col">A igual ISEC del alumno</th>
                  <th scope="col">A igual ISEC del alumno y del centro</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.label}</td>
                    <td>{r.marks.find((m) => m.kind === "raw" || m.kind === "context")?.value}</td>
                    <td>{r.marks.find((m) => m.kind === "adjusted")?.value ?? ""}</td>
                    <td>{r.marks.find((m) => m.kind === "school")?.value ?? ""}</td>
                  </tr>
                ))}
                {cases.map((c) => (
                  <tr key={c.label}>
                    <td>Caso tipo: {c.label}</td>
                    <td colSpan={3}>{c.value} puntos</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Explain
        shows="Dónde están las diferencias de resultados a los 15 años (entre familias, comunidades, tipos de centro, por origen y por sexo), al lado del cambio en el tiempo y de la distancia con la OCDE, en una sola escala."
        read="Cuanto más a la derecha, mayor la brecha. Si el punto verde queda muy a la izquierda del naranja, la brecha tal cual era sobre todo origen social. Los puntos grises son las dos cifras habituales del debate, como vara de medir."
        notSay={`El ajuste por origen social no es un efecto causal: los ${priv.adjusted_school} puntos que quedan entre centros privados y públicos pueden deberse a qué familias eligen cada centro y a lo que el índice no mide. La brecha entre comunidades es entre medias: dentro de cada una, la brecha por origen social va de ${escs.regions_min[1]} a ${escs.regions_max[1]} puntos.`}
      />
      <ul className="vizBars" style={{ width: "100%" }} aria-label={`Brechas en PISA matemáticas ${g.year}, en puntos, tal cual y a igual origen social`}>
        {rows.map((r) => (
          <li key={r.id}>
            <span>
              {r.label}
              <span style={{ ...muted, display: "block", fontSize: "0.78rem" }}>{r.note}</span>
            </span>
            <Track marks={r.marks} label={r.value} />
          </li>
        ))}
        <li aria-hidden="true">
          <span />
          <span style={{ display: "flex", gap: 10 }}>
            <span style={{ position: "relative", flex: "1 1 auto", height: 16, minWidth: 120, fontSize: "0.74rem", color: "var(--viz-muted)" }}>
              {TICKS.map((t) => (
                <span key={t} style={{ position: "absolute", whiteSpace: "nowrap", left: `${t}%`, transform: t ? (t === SCALE ? "translateX(-100%)" : "translateX(-50%)") : "none" }}>
                  {t}
                </span>
              ))}
            </span>
            <span style={{ minWidth: "7.5em" }}>puntos</span>
          </span>
        </li>
      </ul>
      <p>
        <strong>Relatos que zanja.</strong> «La concertada enseña mejor»: a igual origen social del alumno y del centro, la diferencia baja de{" "}
        {priv.raw} a {priv.adjusted_school} puntos. «Los inmigrantes bajan la media»: a igual origen social, {imm.adjusted} puntos. «El problema es la
        comunidad»: el origen social medio explica el {num(regions.r2_isec, 0)} % de las diferencias entre comunidades. «España se ha hundido»: los{" "}
        {change.raw} puntos perdidos desde {change.from} son el {num((change.raw / escs.raw) * 100, 0)} % de la brecha por origen social que hay dentro del país.{" "}
        <strong>Lo que deja abierto:</strong> por qué el origen familiar pesa tanto, qué parte se debe a la escuela y qué parte a la casa, y si los
        puntos que quedan tras el ajuste son efecto del centro o de quién lo elige.
      </p>
      <h3 className="vizPanelTitle">
        Casos tipo: alumnos de 15 años según dónde estudian
        <span>PISA matemáticas {g.year}, media de cada comunidad y tipo de centro, frente a la media de España ({spain})</span>
      </h3>
      <ul className="vizBars" style={{ width: "100%" }} aria-label="Casos tipo de PISA matemáticas por comunidad y titularidad del centro">
        {cases.map((c) => (
          <li key={c.label}>
            <span style={c.isMean ? { fontWeight: 700 } : undefined}>{c.label}</span>
            <span className="vizBars__track">
              <span
                className="vizBars__bar"
                style={{ width: `${(c.value / caseMax) * 100}%`, background: c.isMean ? C.ref : c.value < spain ? C.orange : C.aqua }}
              />
              <span className="vizBars__value">
                {c.value}
                {c.isMean ? null : <span style={muted}> ({c.value > spain ? "+" : "−"}{Math.abs(c.value - spain)} frente a la media)</span>}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Figure>
  );
}
