import { Avatar, Icon, PAL } from "./art";

// Six housing policies side by side (2035), with icons: rent of a new contract, price, dwellings, young people who
// leave home, Lucía's rent and the public cost. Green = better for whoever rents or buys; the range is 5-95 %.
const ICON = { pub: "building", land: "land", tour: "suitcase", capIn: "cap", capOut: "cap", credit: "mortgage", mig: "people" };

const n = (v, d = 1) => Math.abs(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
const sg = (v, d = 1, unit = "") => {
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${n(r, d)}${unit}`;
};

const COLS = [
  { key: "rent", head: <Icon name="key" size={30} color={PAL.orange} />, title: "Alquiler de un contrato nuevo", unit: " %", d: 1, good: -1 },
  { key: "price", head: <Icon name="mortgage" size={30} color={PAL.yellow} />, title: "Precio de la vivienda", unit: " %", d: 1, good: -1 },
  { key: "homes", head: <Icon name="building" size={30} color={PAL.blue} />, title: "Viviendas (mil)", unit: "", d: 0, good: 1 },
  { key: "young", head: <Icon name="people" size={30} color={PAL.green} />, title: "Jóvenes que se independizan (mil)", unit: "", d: 0, good: 1 },
  { key: "p1", head: <Avatar who="p1" mood="flat" size={40} />, title: "Lucía, alquiler al mes", unit: " €", d: 0, good: -1 },
  { key: "cost", head: <Icon name="debt" size={30} color={PAL.ink2} />, title: "Coste público (% del PIB)", unit: "", d: 2, good: -1 },
];

export default function HousingCompare({ rows }) {
  return (
    <div className="hcomp">
      <div className="hcomp__row hcomp__head">
        <span />
        {COLS.map((c) => (
          <span key={c.key} className="hcomp__colhead">
            {c.head}
            <span>{c.title}</span>
          </span>
        ))}
      </div>
      {rows.map((r) => (
        <div className="hcomp__row" key={r.id}>
          <span className="hcomp__policy">
            <span className="hcomp__icon">
              <Icon name={ICON[r.id] || "building"} size={24} />
            </span>
            {r.label}
          </span>
          {COLS.map((c) => {
            const d = r[c.key];
            const zero = Math.abs(d.v) < 0.5 * 10 ** -c.d;
            const tone = zero ? "" : d.v * c.good > 0 ? " is-good" : " is-bad";
            return (
              <span key={c.key} className={`hcomp__cell${tone}`}>
                <b>{zero ? "0" : sg(d.v, c.d, c.unit)}</b>
                {zero ? null : (
                  <small>
                    {sg(d.lo, c.d)} a {sg(d.hi, c.d)}
                  </small>
                )}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
