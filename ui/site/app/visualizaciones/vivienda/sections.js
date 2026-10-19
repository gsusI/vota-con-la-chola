import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { formatHousing } from "./format.mjs";
import { Bars } from "./common";
import { Explain } from "./explain";

const C = { blue: "#2a78d6", orange: "#eb6834", aqua: "#1baf7a", yellow: "#eda100", ref: "#52514e", peer: "#b4b2a9" };
const SCOPES = { ES: "Tipo estatal", "ES-MD": "Madrid", "ES-CT": "Cataluña", "ES-AN": "Andalucía", "ES-VC": "C. Valenciana" };
const TAX_LABELS = {
  iva_vivienda_nueva: "IVA, vivienda nueva",
  iva_vivienda_protegida: "IVA, vivienda protegida de régimen especial",
  ajd_vivienda_nueva: "AJD, escritura de vivienda nueva",
  itp_vivienda_usada: "ITP, vivienda usada",
  plusvalia_municipal_tipo_max: "Plusvalía municipal: tipo máximo (paga el vendedor)",
  plusvalia_municipal_coef_max: "Plusvalía municipal: coeficiente máximo, 20 años o más (paga el vendedor)",
};

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const pct = (value) => `${Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 })} %`;

export function TaxesFigure({ taxes, wageLast, lastYear, retrieved }) {
  if (!taxes?.scenarios?.length) return null;
  const years = [...new Set(taxes.scenarios.map((s) => s.year))].sort();
  const [first, last] = [years[0], years.at(-1)];
  const used = (year) => taxes.scenarios.filter((s) => s.year === year && s.kind === "usada" && (s.scope !== "ES" || year === first));
  const usedLast = used(last);
  const usedFirst = used(first);
  const range = (rows, key) => [Math.min(...rows.map((r) => r[key])), Math.max(...rows.map((r) => r[key]))];
  const [lo, hi] = range(usedLast, "pct");
  const [loFirst, hiFirst] = range(usedFirst, "pct");
  const [loEur, hiEur] = range(usedLast, "eur");
  const months = (eur) => num((eur / wageLast) * 12, 1);
  const max = Math.max(...taxes.scenarios.map((s) => s.eur));
  // Rate change per region and kind; a region without its own rate in the first year paid the state rate.
  const deltas = taxes.scenarios
    .filter((s) => s.year === last && s.scope !== "ES")
    .map((s) => {
      const before = taxes.scenarios.find((b) => b.year === first && b.kind === s.kind && b.scope === s.scope) ||
        taxes.scenarios.find((b) => b.year === first && b.kind === s.kind && b.scope === "ES");
      return before ? s.pct - before.pct : null;
    })
    .filter((d) => d != null);
  const signed = (d) => `${d > 0 ? "+" : d < 0 ? "−" : ""}${num(Math.abs(d), 2).replace(/,?0+$/, "")}`;
  const groups = years.flatMap((year) =>
    ["nueva", "usada"].map((kind) => ({
      id: `${year}-${kind}`,
      title: `${year} · vivienda ${kind} · piso medio de ${formatHousing(taxes.scenarios.find((s) => s.year === year)?.home_price, "eur")}`,
      rows: taxes.scenarios
        .filter((s) => s.year === year && s.kind === kind && !(year === last && s.scope === "ES"))
        .map((s) => ({
          id: `${s.year}-${s.scope}-${s.kind}`,
          label: `${SCOPES[s.scope] || s.scope}: ${s.parts.map((p) => `${p.key.split("_")[0].toUpperCase()} ${pct(p.pct)}`).join(" + ")}`,
          value: s.eur,
          text: `${formatHousing(s.eur, "eur")} (${pct(s.pct)})`,
          color: year === last ? C.blue : C.peer,
        })),
    })),
  ).filter((group) => group.rows.length);
  const lowConfidence = taxes.rates.filter((r) => r.confidence !== "high");

  return (
    <Figure
      id="impuestos"
      title={`Al comprar una vivienda usada se paga hoy entre el ${pct(lo)} y el ${pct(hi)} de impuestos según la comunidad (en ${first}, entre el ${pct(loFirst)} y el ${pct(hiFirst)}): de ${formatHousing(loEur, "eur")} a ${formatHousing(hiEur, "eur")} en un piso medio, entre ${months(loEur)} y ${months(hiEur)} meses de salario`}
      dek={`Impuestos que paga el comprador sobre el precio, ${first} frente a ${last}, en las cuatro comunidades más pobladas. La vivienda nueva paga IVA más AJD; la usada, ITP. Aplicados al piso medio de 90 m² de cada año. Por comunidad y tipo de vivienda, el tipo ha cambiado entre ${signed(Math.min(...deltas))} y ${signed(Math.max(...deltas))} puntos; casi todo el aumento en euros viene de que el piso cuesta más.`}
      legend={[
        { id: "last", label: String(last), color: C.blue },
        { id: "first", label: String(first), color: C.peer },
      ]}
      legendKind="bar"
      sources={[{ label: `BOE: la norma vigente el 1 de julio de cada año, una por fila (${taxes.rates.length} filas en la tabla)${retrieved ? `; consultado ${retrieved}` : ""}`, href: "https://www.boe.es/" }]}
      notes={[
        "Tipos generales. Hay tipos reducidos para vivienda habitual de menor valor, jóvenes, familias numerosas o vivienda protegida (por ejemplo, el 4 % de IVA en vivienda protegida de régimen especial); se detallan en la tabla.",
        "La plusvalía municipal la paga el vendedor, depende del valor catastral del suelo y de los años de tenencia y no se puede calcular para un piso medio; se recoge su tipo y coeficiente máximos.",
        ...taxes.rules.map((rule) => rule.text),
        ...(lowConfidence.length ? [`${lowConfidence.length} tipos con confianza media: se indica en la tabla.`] : []),
      ]}
      table={
        <details className="vizTable">
          <summary>Ver cada tipo con su norma</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Año (1 de julio)</th>
                  <th scope="col">Impuesto</th>
                  <th scope="col">Ámbito</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Norma</th>
                  <th scope="col">Nota</th>
                </tr>
              </thead>
              <tbody>
                {taxes.rates.map((r) => (
                  <tr key={`${r.key}-${r.year}-${r.scope}`}>
                    <td>{r.year}</td>
                    <td>{TAX_LABELS[r.key] || r.key}</td>
                    <td>{SCOPES[r.scope] || r.scope}</td>
                    <td>{r.unit === "coef" ? num(r.value, 2) : pct(r.value)}</td>
                    <td>
                      <a href={r.source_url} rel="noopener noreferrer" target="_blank">
                        {r.norm}
                      </a>
                      {r.confidence !== "high" ? ` (confianza ${r.confidence})` : ""}
                    </td>
                    <td>{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <div className="vizStack">
        {groups.map((group) => (
          <div key={group.id}>
            <h3>{group.title}</h3>
            <Bars rows={group.rows} max={max} label={group.title} />
          </div>
        ))}
      </div>
      <Explain
        shows="Cuánto paga el comprador en impuestos al comprar un piso medio, en 2000 y hoy, en las cuatro comunidades con más población."
        read="Cada barra es el impuesto en euros y, entre paréntesis, en % del precio. La vivienda nueva paga IVA (estatal) más AJD (autonómico); la usada, solo ITP (autonómico)."
        notSay="No incluye notaría, registro, gestoría ni la plusvalía municipal (la paga el vendedor), ni los tipos reducidos para jóvenes o vivienda protegida."
      />
    </Figure>
  );
}

export function CensusStockFigure({ rows, source }) {
  if (!rows?.length) return null;
  const last = rows.at(-1);
  const share = (key, row = last) => (row[key] / row.total) * 100;
  const kinds = [
    { id: "principales", key: "principales", label: "Principales (hogares)", color: C.blue },
    { id: "secundarias", key: "secundarias", label: "Secundarias", color: C.aqua },
    { id: "desocupadas", key: "desocupadas", label: "Vacías y otras", color: C.orange },
  ];
  const max = Math.max(...rows.map((row) => row.total));
  return (
    <Figure
      id="viviendas-vacias"
      title={`En ${last.year} había ${num(last.desocupadas / 1e6)} millones de viviendas vacías o de otros usos (${num(share("desocupadas"), 0)} %) y ${num(last.secundarias / 1e6)} millones secundarias`}
      dek={`Parque de viviendas en cada censo. De ${num(last.total / 1e6)} millones de viviendas en ${last.year}, ${num(last.principales / 1e6)} millones eran residencia habitual de un hogar.`}
      legend={kinds}
      legendKind="bar"
      sources={[source]}
      notes={[
        "El Censo 2021 identificó las viviendas vacías con datos de consumo eléctrico y los anteriores con recorridos de campo: el cambio de método impide comparar el número de vacías entre censos con precisión.",
        "Una vivienda vacía no está necesariamente disponible: incluye viviendas en mal estado, en herencias, en venta o en municipios sin demanda.",
      ]}
      table={<HousingTable series={kinds.map((k) => ({ id: k.key, label: k.label, points: rows.map((row) => ({ year: row.year, value: row[k.key] })), unit: "count" }))} />}
    >
      <div className="vizStack">
        {rows.map((row) => (
          <div key={row.year}>
            <h3>
              Censo {row.year}: {num(row.total / 1e6)} millones de viviendas
            </h3>
            <Bars
              rows={kinds.map((k) => ({
                id: `${row.year}-${k.key}`,
                label: k.label,
                value: row[k.key],
                color: k.color,
                text: `${num(row[k.key] / 1e6, 2)} millones (${num(share(k.key, row), 0)} %)`,
              }))}
              max={max}
              label={`Censo ${row.year}`}
            />
          </div>
        ))}
      </div>
      <Explain
        shows="Cuántas viviendas hay en España según cada censo y para qué se usan: residencia habitual, segunda residencia o vacías."
        read="Cada bloque es un censo. Las barras suman el total de viviendas; el porcentaje es sobre ese total."
        notSay="No dice cuántas vacías podrían alquilarse o venderse ni dónde están; el método del Censo 2021 no es comparable con los anteriores."
      />
    </Figure>
  );
}

export function YoungOwnershipFigure({ young, retrieved }) {
  if (!young?.length) return null;
  const groups = [...new Set(young.map((row) => row.age_group))];
  const ordered = [...groups.filter((g) => g !== "total"), ...groups.filter((g) => g === "total")];
  const colors = [C.blue, C.orange, C.aqua, C.yellow];
  const series = ordered.map((group, index) => ({
    id: group,
    label: group === "total" ? "Todos los hogares" : `Persona de referencia ${group.replace("<", "menor de ")} años`,
    shortLabel: group === "total" ? "Todos" : group,
    color: group === "total" ? C.ref : colors[index],
    emphasis: group !== "total",
    connect: true,
    markers: true,
    points: young.filter((row) => row.age_group === group).map((row) => ({ year: row.year, value: row.value })),
  }));
  const main = series[0];
  const first = main.points[0];
  const last = main.points.at(-1);
  const peak = main.points.reduce((best, p) => (p.value > best.value ? p : best), first);
  const low = main.points.filter((p) => p.year > peak.year).reduce((best, p) => (p.value < best.value ? p : best), last);
  const sources = [...new Map(young.map((row) => [row.source_url, `Banco de España, EFF ${row.year}${retrieved ? ` (consultado ${retrieved})` : ""}`])).entries()].map(([href, label]) => ({ href, label }));
  return (
    <Figure
      id="jovenes-propietarios"
      title={`Entre los hogares de menores de 35 años, los propietarios de su vivienda son el ${num(last.value)} % en ${last.year}, frente al ${num(first.value)} % en ${first.year} y el ${num(peak.value)} % de ${peak.year}`}
      dek={`Hogares que tienen en propiedad su vivienda principal, según la edad de la persona de referencia (Encuesta Financiera de las Familias del Banco de España). ${low.year !== last.year ? `El mínimo fue el ${num(low.value)} % de ${low.year}. ` : ""}En el conjunto de los hogares la caída es mucho menor: del ${num(series.at(-1).points[0].value)} % al ${num(series.at(-1).points.at(-1).value)} %. Cada punto es una ola de la encuesta; las líneas solo unen olas.`}
      legend={series}
      sources={sources}
      notes={[
        "La encuesta es de hogares: los jóvenes que siguen en casa de sus padres no forman hogar propio y no cuentan aquí, así que la caída infravalora el problema de acceso.",
        "Cada ola se toma de su propio artículo del Banco de España; algunas se revisaron después (2011: 69,8 % en su artículo, 69,3 % en el de 2014). Edad de la persona de referencia (cabeza de familia).",
      ]}
      table={<HousingTable series={series} />}
    >
      <HousingChart series={series} xMin={first.year} xMax={last.year} yMax={100} ariaLabel="Hogares propietarios de su vivienda por edad" />
      <Explain
        shows="Qué parte de los hogares jóvenes (persona de referencia menor de 35 años) y del total es dueña de la vivienda en la que vive."
        read="Cada punto es una ola de la Encuesta Financiera de las Familias del Banco de España (cada dos o tres años). La distancia entre las dos líneas es la brecha generacional."
        notSay="Solo cuenta a los jóvenes que ya han formado su propio hogar; los que siguen con sus padres no aparecen."
      />
    </Figure>
  );
}

export function SocialStockBars({ rows, names }) {
  if (!rows?.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const max = Math.max(...sorted.map((row) => row.value));
  const es = rows.find((row) => row.country === "ESP");
  return (
    <div className="vizStack" style={{ marginTop: 18 }}>
      <h3>
        Vivienda social en alquiler, % del total de viviendas{es ? ` (España: ${num(es.value)} % en ${es.year})` : ""}
      </h3>
      <Bars
        rows={sorted.map((row) => ({
          id: row.country,
          label: `${names[row.country] || row.country} (${row.year ?? "último dato de cada país"})`,
          value: row.value,
          color: row.country === "ESP" ? C.blue : row.country === "OECD" || row.country === "EU" ? C.ref : C.peer,
          text: `${num(row.value)} %`,
        }))}
        max={max}
        label="Vivienda social en alquiler"
      />
    </div>
  );
}

export function SpendingBars({ spend, names, order }) {
  const avg = (rows, from, to) => {
    const sel = (rows || []).filter((row) => row.year >= from && row.year <= to);
    return sel.length === to - from + 1 ? sel.reduce((sum, row) => sum + row.total, 0) / sel.length : null;
  };
  const lastYear = Math.max(...order.map((geo) => spend[geo]?.at(-1)?.year || 0));
  const periods = [
    { id: "last", title: `${lastYear}`, value: (geo) => spend[geo]?.find((row) => row.year === lastYear)?.total },
    { id: "avg", title: "Media 2015–2019", value: (geo) => avg(spend[geo], 2015, 2019) },
  ];
  const max = Math.max(...periods.flatMap((period) => order.map((geo) => period.value(geo) || 0)));
  return (
    <div className="vizStack">
      {periods.map((period) => (
        <div key={period.id}>
          <h3>Gasto público en vivienda, % del PIB · {period.title}</h3>
          <Bars
            rows={order
              .filter((geo) => period.value(geo) != null)
              .map((geo) => ({ geo, value: period.value(geo) }))
              .sort((a, b) => b.value - a.value)
              .map(({ geo, value }) => ({
                id: `${period.id}-${geo}`,
                label: names[geo] || geo,
                value,
                color: geo === "ES" ? C.blue : geo === "EU27_2020" ? C.ref : C.peer,
                text: `${num(value, 2)} %`,
              }))}
            max={max}
            label={`Gasto público en vivienda ${period.title}`}
          />
        </div>
      ))}
    </div>
  );
}
