import TimeSeriesChart from "../components/TimeSeriesChart";
import { SeriesTable } from "../components/Figure";
import { DataTable, Fig } from "./blocks";
import { C, sources } from "./common.mjs";
import { fmt, num } from "./format.mjs";
import { Verdicts } from "./relato";

// «Estructural, ¿de quién?»: unemployment by age x education x autonomous community (Eurostat lfst_r_lfu3rt), with the
// Spanish and EU-27 rate of the same group, plus the typical cases shared with the other /visualizaciones/ pages.

const pct = (value, digits = 1) => `${num(value, digits)} %`;
const MARKET_COLORS = { bajo_alto: C.blue, bajo_medio: C.aqua, alto: C.orange, ceuta_melilla: C.peer };
// Each market gets its own lane inside a row, so 19 dots overlap less and position repeats the colour.
const MARKET_LANE = { bajo_alto: 0, bajo_medio: 1, alto: 2, ceuta_melilla: 3 };
const LEVEL_PHRASE = { "ED0-2": "sin bachillerato ni FP", ED3_4: "con bachillerato o FP de grado medio", "ED5-8": "con estudios superiores" };
const SEG_SOURCE = (S) => S.eurostat("lfst_r_lfu3rt");

function ageWords(code) {
  const [a, b] = code.replace("Y", "").split("-");
  return `de ${a} a ${b} años`;
}

// «de Andalucía», «del País Vasco», «de la Comunidad de Madrid»; inName: «en Andalucía», «en el País Vasco».
function deName(name) {
  if (/^(País|Principado)\b/.test(name)) return `del ${name}`;
  if (/^(Comunidad|Región|Ciudad)\b/.test(name)) return `de la ${name}`;
  return `de ${name}`;
}

function inName(name) {
  return deName(name).replace(/^del /, "en el ").replace(/^de /, "en ");
}

function groupWords(cell) {
  return `los activos ${ageWords(cell.age)} ${LEVEL_PHRASE[cell.isced]} ${deName(cell.name)}`;
}

function cellOf(seg, isced, age) {
  return seg.rows.find((row) => row.isced === isced && row.age === age);
}

function Marker({ kind }) {
  if (kind === "es") return <span aria-hidden="true" style={{ display: "inline-block", width: 3, height: 14, background: "var(--viz-ink)", verticalAlign: "middle" }} />;
  return (
    <span
      aria-hidden="true"
      style={{ display: "inline-block", width: 9, height: 9, border: "2px solid var(--viz-ink)", borderRadius: "50%", background: "transparent", verticalAlign: "middle" }}
    />
  );
}

function StripRow({ seg, row, max, regionName, levelLabel, ageLabel }) {
  const x = (value) => `${(value / max) * 100}%`;
  const present = Object.entries(row.values).filter(([, v]) => v != null);
  const lo = present.reduce((a, b) => (b[1] < a[1] ? b : a), present[0]);
  const hi = present.reduce((a, b) => (b[1] > a[1] ? b : a), present[0]);
  const laneTop = (lane) => 4 + lane * 7;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(4.2rem, 5.5rem) minmax(0, 1fr)", columnGap: 10, alignItems: "start" }}>
      <span style={{ fontSize: "0.82rem", fontWeight: 600, paddingTop: 8 }}>{ageLabel}</span>
      <div style={{ minWidth: 0 }}>
        <div
          role="img"
          aria-label={`${levelLabel}, ${ageLabel} años: España ${fmt(row.es)}, UE-27 ${fmt(row.eu)}; de ${fmt(lo?.[1])} en ${regionName(lo?.[0])} a ${fmt(hi?.[1])} en ${regionName(hi?.[0])}`}
          style={{ position: "relative", height: 34, borderBottom: "1px solid var(--viz-grid)" }}
        >
          {seg.regions.map((reg) => {
            const v = row.values[reg.code];
            if (v == null) return null;
            return (
              <span
                key={reg.code}
                title={`${reg.name}, ${levelLabel.toLowerCase()}, ${ageLabel} años: ${fmt(v)}`}
                style={{
                  position: "absolute",
                  left: x(v),
                  top: laneTop(MARKET_LANE[reg.market]),
                  width: 9,
                  height: 9,
                  marginLeft: -4.5,
                  borderRadius: "50%",
                  background: MARKET_COLORS[reg.market],
                  opacity: 0.9,
                }}
              />
            );
          })}
          {row.es != null ? (
            <span title={`España: ${fmt(row.es)}`} style={{ position: "absolute", left: x(row.es), top: 0, bottom: 0, width: 3, marginLeft: -1.5, background: "var(--viz-ink)" }} />
          ) : null}
          {row.eu != null ? (
            <span
              title={`UE-27: ${fmt(row.eu)}`}
              style={{ position: "absolute", left: x(row.eu), top: 11, width: 12, height: 12, marginLeft: -6, borderRadius: "50%", border: "2px solid var(--viz-ink)", boxSizing: "border-box", background: "transparent" }}
            />
          ) : null}
        </div>
        <p style={{ margin: "3px 0 8px", fontSize: "0.74rem", lineHeight: 1.35, color: "var(--viz-muted)" }}>
          España {fmt(row.es)} · UE-27 {fmt(row.eu)} · de {fmt(lo?.[1])} ({regionName(lo?.[0])}) a {fmt(hi?.[1])} ({regionName(hi?.[0])})
        </p>
      </div>
    </div>
  );
}

function Axis({ max }) {
  const ticks = [];
  for (let t = 0; t <= max; t += 10) ticks.push(t);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(4.2rem, 5.5rem) minmax(0, 1fr)", columnGap: 10 }}>
      <span style={{ fontSize: "0.72rem", color: "var(--viz-muted)" }}>Edad</span>
      <div style={{ position: "relative", height: 16, fontSize: "0.72rem", color: "var(--viz-muted)" }} aria-hidden="true">
        {ticks.map((t) => (
          <span key={t} style={{ position: "absolute", left: `${(t / max) * 100}%`, transform: t === 0 ? "none" : t === max ? "translateX(-100%)" : "translateX(-50%)" }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

export function WhoFigure({ data }) {
  const seg = data.segments;
  if (!seg) return null;
  const S = sources(data);
  const names = Object.fromEntries(seg.regions.map((r) => [r.code, r.name]));
  const regionName = (code) => names[code] || code;
  const levelLabel = Object.fromEntries(seg.levels.map((l) => [l.code, l.label]));
  const ageLabel = Object.fromEntries(seg.ages.map((a) => [a.code, a.label]));
  const all = seg.rows.flatMap((row) => [row.es, row.eu, ...Object.values(row.values)]).filter((v) => v != null);
  const max = Math.ceil(Math.max(...all) / 10) * 10;
  const { min: lo, max: hi } = seg.extremes;

  // Narratives, from the same table: 45-54 (everyone has finished studying, and the four cells are reliable).
  const BAND = "Y45-54";
  const low = cellOf(seg, "ED0-2", BAND);
  const high = cellOf(seg, "ED5-8", BAND);
  const AND = "ES61";
  const PV = "ES21";
  const cmp = (a, b) => (a > b ? "más" : a < b ? "menos" : "lo mismo");
  const narrOk = [low.values[AND], low.values[PV], high.values[AND], high.values[PV]].every((v) => v != null);
  const esAbove = seg.rows.filter((row) => row.es != null && row.eu != null && row.es > row.eu).length;
  const withBoth = seg.rows.filter((row) => row.es != null && row.eu != null).length;
  const hiYoung = cellOf(seg, "ED5-8", "Y25-34");
  const emptyCells = seg.cells_unreliable + seg.cells_missing;
  const totalCells = seg.rows.length * seg.regions.length;

  return (
    <Fig
      id="relato-quien"
      title={`El paro va del ${pct(lo.value)} de ${groupWords(lo)} al ${pct(hi.value)} de ${groupWords(hi)}: la media española, ${pct(seg.es_total)}, no describe a casi nadie`}
      dek={`Estructural, sí, pero ¿de quién? Cada fila es un grupo de edad y cada punto una comunidad autónoma, coloreada por su mercado de trabajo; la línea negra es España y el círculo hueco, la UE-27 del mismo grupo. ${narrOk ? `Con ${ageWords(BAND).replace("de ", "")} y hasta la ESO: ${regionName(AND)} ${fmt(low.values[AND])}, ${regionName(PV)} ${fmt(low.values[PV])}; con estudios superiores, ${fmt(high.values[AND])} y ${fmt(high.values[PV])}.` : ""}`}
      legend={[...seg.markets.groups.map((g) => ({ id: g.id, label: g.label, color: MARKET_COLORS[g.id] }))]}
      legendKind="bar"
      sources={[SEG_SOURCE(S)]}
      notes={[
        `Tasa de paro ${seg.year}: parados sobre los activos de cada grupo de edad y nivel de estudios (CINE 2011: hasta la ESO = ED0-2; bachillerato o FP de grado medio = ED3_4; superiores = ED5-8). Bandas de edad de Eurostat (15–24, 25–34…), no las etapas comunes 16–29 / 30–44 / 45–64.`,
        `Mercados de trabajo: ${seg.markets.criterion}`,
        `Celdas vacías: ${emptyCells} de ${totalCells} (Eurostat marca ${seg.cells_unreliable} con «u», poca muestra, y no publica ${seg.cells_missing}); se dejan vacías, nunca se imputan.`,
      ]}
      table={
        <DataTable
          caption="Ver los datos en tabla (paro, %; vacío = poca muestra o sin dato)"
          columns={[
            { key: "level", label: "Estudios" },
            { key: "age", label: "Edad" },
            { key: "es", label: "España", format: (v) => (v == null ? "" : num(v)) },
            { key: "eu", label: "UE-27", format: (v) => (v == null ? "" : num(v)) },
            ...seg.regions.map((reg) => ({ key: reg.code, label: reg.name, format: (v) => (v == null ? "" : num(v)) })),
          ]}
          rows={seg.rows.map((row) => ({
            id: `${row.isced}-${row.age}`,
            level: levelLabel[row.isced],
            age: ageLabel[row.age],
            es: row.es,
            eu: row.eu,
            ...row.values,
          }))}
        />
      }
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", fontSize: "0.82rem", marginBottom: 6 }}>
        <span>
          <Marker kind="es" /> España, mismo grupo
        </span>
        <span>
          <Marker kind="eu" /> UE-27, mismo grupo
        </span>
      </div>
      <div style={{ display: "grid", gap: 14 }}>
        {seg.levels.map((level) => (
          <div key={level.code}>
            <h3 className="vizPanelTitle" style={{ minHeight: 0 }}>
              {level.label}
              <span>paro, % de los activos de cada edad (misma escala en los tres paneles)</span>
            </h3>
            <Axis max={max} />
            {seg.ages.map((age) => (
              <StripRow
                key={age.code}
                seg={seg}
                row={cellOf(seg, level.code, age.code)}
                max={max}
                regionName={regionName}
                levelLabel={level.label}
                ageLabel={age.label}
              />
            ))}
          </div>
        ))}
      </div>
      {narrOk ? (
      <Verdicts
        settled={[
          [
            "El paro es cosa de la formación",
            `Solo en parte. A igual formación, la comunidad sigue pesando: los universitarios ${ageWords(BAND)} tienen un paro del ${pct(high.values[AND])} ${inName(regionName(AND))} y del ${pct(high.values[PV])} ${inName(regionName(PV))}.`,
          ],
          [
            "El paro es cosa del sur",
            `Tampoco basta. ${inName(regionName(PV)).replace(/^en/, "En")}, quien no pasó de la ESO tiene ${ageWords(BAND).replace("de ", "con ")} un paro del ${pct(low.values[PV])}: ${cmp(low.values[PV], high.values[AND])} que un universitario andaluz de su edad (${pct(high.values[AND])}) y ${cmp(low.values[PV], low.values[AND])} que un andaluz con sus mismos estudios (${pct(low.values[AND])}). Formación y territorio se suman; ninguno lo explica solo.`,
          ],
          [
            "En España no hay paro de cualificados: la brecha con Europa es de los que estudiaron poco",
            `No. El paro español supera al europeo del mismo grupo ${esAbove === withBoth ? `en los ${withBoth} grupos de edad y estudios` : `en ${esAbove} de los ${withBoth} grupos de edad y estudios`}, también entre los universitarios: con 25 a 34 años, ${pct(hiYoung.es)} frente a ${pct(hiYoung.eu)}.`,
          ],
        ]}
        ambiguous={[
          "Eurostat no cruza esta tabla con el sector: no se puede separar si pesa la comunidad o lo que se produce en ella (turismo, agricultura, construcción, administración).",
          "La EPA sitúa a cada persona en la comunidad donde vive, no donde trabaja, y la tasa se calcula sobre los activos: quien deja de buscar empleo sale de la cuenta.",
          `Las ${emptyCells} celdas vacías se concentran donde la muestra es pequeña (jóvenes con estudios superiores, Ceuta, Melilla, comunidades poco pobladas): ahí no se puede decir nada.`,
        ]}
      />
      ) : null}
    </Fig>
  );
}

const valueText = (f) => (f.unit === "eur_month" ? `${num(f.value, 0)} €/mes` : pct(f.value));

export function TypicalCases({ data }) {
  const seg = data.segments;
  if (!seg?.cases?.length) return null;
  const S = sources(data);
  return (
    <section aria-labelledby="casos-tipo-title" id="casos-tipo">
      <div className="card vizProse">
        <h3 id="casos-tipo-title">Cinco personas frente a la media</h3>
        <p>
          Las personas 1, 3 y 5 son las mismas en todas las páginas de visualizaciones (misma edad, estudios y lugar). Al lado de cada cifra, la media que
          da la página. Cuando no hay un cruce oficial, la cifra es la del corte que define al caso, y se dice.
        </p>
      </div>
      <div className="vizStats">
        {seg.cases.map((c) => {
          const [main, ...rest] = c.figures;
          return (
            <div className="card vizStat" key={c.id}>
              <span className="vizStat__label">
                {c.persona ? `Persona ${c.persona} · ` : ""}
                {c.title}
              </span>
              <span className="vizStat__value">{valueText(main)}</span>
              <span className="vizStat__note">
                <span style={{ display: "block" }}>
                  {main.label} ({main.year}). {c.who}.
                </span>
                {rest.map((f) => (
                  <span key={f.label} style={{ display: "block" }}>
                    {f.label}: <strong>{valueText(f)}</strong>
                  </span>
                ))}
                <span style={{ display: "block", marginTop: 4 }}>
                  Frente a: {c.national.map((f) => `${f.label}, ${valueText(f)}`).join(" · ")}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <details className="vizTable">
        <summary>Cómo se define cada caso y de dónde sale cada cifra</summary>
        <ul>
          {seg.cases.map((c) => (
            <li key={c.id}>
              <strong>{c.title}.</strong> {c.cut_note} Fuentes: {[...new Set([...c.figures, ...c.national].map((f) => f.source))].join(", ")}.
            </li>
          ))}
        </ul>
        <p>
          Paro: <a href={SEG_SOURCE(S).href}>Eurostat, lfst_r_lfu3rt</a>. Temporalidad: INE, EPA, tablas{" "}
          <a href="https://www.ine.es/jaxiT3/Tabla.htm?t=65978">65978</a>, <a href="https://www.ine.es/jaxiT3/Tabla.htm?t=65979">65979</a> y{" "}
          <a href="https://www.ine.es/jaxiT3/Tabla.htm?t=65980">65980</a>. Jornada parcial involuntaria: <a href={S.eurostat("lfsa_eppgai").href}>Eurostat, lfsa_eppgai</a>.
          Salario por jornada: <a href="https://www.ine.es/jaxiT3/Tabla.htm?t=66237">INE, tabla 66237</a>. Definiciones de los casos:{" "}
          <code>{seg.definitions}</code>.
        </p>
      </details>
    </section>
  );
}

const SECTOR_SERIES = [
  { id: "private", label: "Sector privado", color: C.blue },
  { id: "public", label: "Sector público", color: C.orange },
  { id: "all", label: "Todos los asalariados", color: C.ref },
];

export function SectorTemporality({ data }) {
  const ts = data.segments?.temporary_by_sector;
  if (!ts) return null;
  const S = sources(data);
  const series = SECTOR_SERIES.map((s) => ({ ...s, emphasis: s.id !== "all", points: ts.series[s.id] }));
  const at = (sec, year) => ts.series[sec].find((p) => p.year === year)?.value;
  const first = 2021;
  const last = ts.last_year;
  const byAge = ts.by_age_last.filter((a) => (a.public_employees_k ?? 0) >= 50); // tiny public groups (16-19, 70+) left out of the bars
  const young = ts.by_age_last.find((a) => a.age === "De 25 a 29 años");
  const shareTemp = ts.public_share_of_temporary;
  const shareEmp = ts.public_share_of_employees.at(-1)?.value;
  const max = Math.ceil(Math.max(...byAge.flatMap((a) => [a.private, a.public])) / 10) * 10;
  return (
    <Fig
      id="temporalidad-sector"
      title={`La temporalidad privada bajó del ${pct(at("private", first))} al ${pct(at("private", last))} entre ${first} y ${last}; en el sector público sigue en el ${pct(at("public", last))}${young ? `, y en el ${pct(young.public)} entre sus asalariados de 25 a 29 años` : ""}`}
      dek={`El sector público tiene el ${pct(shareEmp)} de los asalariados y el ${pct(shareTemp.at(-1)?.value)} de los temporales (${pct(shareTemp.find((p) => p.year === first)?.value)} en ${first}). La reforma laboral de 2022 cambió los contratos del sector privado; el empleo público temporal (interinos y sustitutos) se rige por otras normas.`}
      legend={SECTOR_SERIES}
      sources={[{ label: `INE, EPA, tablas 65978, 65979 y 65980 (consultado ${String(data.sources.ine_epa_tempus?.retrieved_at || "").slice(0, 10)})`, href: "https://www.ine.es/jaxiT3/Tabla.htm?t=65980" }]}
      notes={[
        "Asalariados con contrato temporal sobre el total de asalariados de cada sector y edad, media anual de la EPA. Se calcula con los dos recuentos oficiales de cada tabla (temporales y total); los fijos discontinuos cuentan como indefinidos.",
        "En las barras se omiten los grupos con menos de 50.000 asalariados públicos (16 a 19 y 70 o más años): la muestra es pequeña.",
      ]}
      table={
        <>
          <SeriesTable series={series} caption="Ver la serie en tabla (% de asalariados temporales)" />
          <DataTable
            caption={`Ver por edad en ${last}`}
            columns={[
              { key: "age", label: "Edad" },
              { key: "private", label: "Privado", format: (v) => fmt(v) },
              { key: "public", label: "Público", format: (v) => fmt(v) },
              { key: "all", label: "Todos", format: (v) => fmt(v) },
              { key: "public_employees_k", label: "Asalariados públicos (miles)", format: (v) => num(v, 1) },
            ]}
            rows={ts.by_age_last.map((a) => ({ ...a, id: a.age }))}
          />
        </>
      }
      explain={{
        what: `Qué parte de los asalariados tiene contrato temporal en el sector privado y en el público, desde ${ts.series.all[0].year}, y por edad en ${last}.`,
        read: "La caída de la temporalidad tras 2022 es casi toda privada. En el sector público la temporalidad apenas ha bajado y se concentra en los menores de 40 años.",
        not: "No distingue entre administraciones (Estado, comunidades, ayuntamientos) ni por comunidad autónoma, y no dice cuánto duran los contratos ni cuántos temporales públicos encadenan sustituciones.",
      }}
    >
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Temporales por sector
            <span>% de los asalariados</span>
          </h3>
          <TimeSeriesChart series={series} xMin={ts.series.all[0].year} xMax={last} yMax={max} height={240} ariaLabel="Temporalidad en el sector público y en el privado" />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Por edad, {last}
            <span>% de temporales en cada grupo</span>
          </h3>
          <ul className="vizBars" aria-label={`Temporalidad por edad y sector, ${last}`}>
            {byAge.flatMap((a) =>
              ["private", "public"].map((sec) => (
                <li key={`${a.age}-${sec}`}>
                  <span>{sec === "private" ? a.age.replace("De ", "").replace(" años", "") : ""}</span>
                  <span className="vizBars__track">
                    <span className="vizBars__bar" style={{ width: `${(a[sec] / max) * 100}%`, background: sec === "private" ? C.blue : C.orange }} />
                    <span className="vizBars__value">{fmt(a[sec])}</span>
                  </span>
                </li>
              )),
            )}
          </ul>
        </div>
      </div>
    </Fig>
  );
}
