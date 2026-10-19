"use client";

import { useEffect, useRef, useState } from "react";
import { Bank, CoinStack, Factory, Figure, Housing, PAL, PiggyBank, Services, Shop } from "./art";

// The illustrated economy: who pays into the public purse, who it pays, and the debt pile. Flow width = size in % of
// GDP in the chosen year; the coloured number = change with the scenario. Two layouts (wide, narrow) share the
// same drawing so phones get a tall scene instead of a shrunken one.
const LAYOUTS = {
  wide: {
    box: [1200, 900],
    shop: [190, 200],
    factory: [190, 730],
    workers: { x: 190, y: 455, cols: 8 },
    piggy: [600, 440, 1.1],
    pensioners: { x: 1010, y: 300, cols: 6 },
    services: [1060, 590],
    stack: [440, 770],
    bank: [820, 770],
    housing: [1060, 800],
    year: [36, 64],
  },
  narrow: {
    box: [420, 1690],
    shop: [100, 160],
    factory: [320, 160],
    workers: { x: 210, y: 410, cols: 8 },
    piggy: [215, 770, 0.86],
    pensioners: { x: 105, y: 1060, cols: 5 },
    services: [322, 1070],
    stack: [105, 1365],
    bank: [322, 1365],
    housing: [210, 1590],
    year: [16, 44],
  },
};

const FLOWS = {
  wide: {
    vat: { from: [255, 170], to: [520, 330], bend: -70, at: 0.45 },
    irpf: { from: [330, 372], to: [492, 388], bend: -18, at: 0.5, dy: -16 },
    contrib: { from: [330, 470], to: [500, 440], bend: 26, at: 0.5, dy: 22 },
    corp: { from: [265, 665], to: [545, 462], bend: 50, at: 0.45 },
    pensions: { from: [705, 330], to: [905, 255], bend: -50, at: 0.5 },
    services: { from: [712, 425], to: [985, 520], bend: 24, at: 0.55, dy: -18 },
    loans: { from: [840, 680], to: [680, 462], bend: 50, at: 0.45, dx: 80 },
    interest: { from: [600, 468], to: [785, 690], bend: 60, at: 0.62, dx: -80 },
    housing: { from: [700, 470], to: [990, 700], bend: 40, at: 0.55, dx: 10, dy: 18 },
  },
  narrow: {
    vat: { from: [92, 190], to: [160, 655], bend: 40, label: [12, 500], anchor: "start" },
    corp: { from: [328, 190], to: [272, 655], bend: -40, label: [408, 500], anchor: "end" },
    irpf: { from: [185, 462], to: [200, 650], bend: 0, label: [12, 585], anchor: "start" },
    contrib: { from: [238, 462], to: [232, 650], bend: 0, label: [408, 585], anchor: "end" },
    pensions: { from: [170, 790], to: [110, 975], bend: -16, label: [12, 880], anchor: "start" },
    services: { from: [262, 790], to: [318, 985], bend: 16, label: [408, 880], anchor: "end", short: "Servicios" },
    loans: { from: [345, 1280], to: [285, 790], bend: -50, label: [408, 1205], anchor: "end", short: "Préstamos" },
    interest: { from: [205, 795], to: [295, 1285], bend: 40, label: [12, 1205], anchor: "start" },
  },
};

const FLOW_STYLE = {
  vat: { color: PAL.orange, label: "IVA y consumo" },
  irpf: { color: PAL.blue, label: "IRPF" },
  contrib: { color: PAL.yellow, label: "Cotizaciones" },
  corp: { color: PAL.purple, label: "Sociedades" },
  pensions: { color: PAL.green, label: "Pensiones" },
  services: { color: "#0f8a5f", label: "Sanidad, educación y el resto" },
  loans: { color: PAL.red, label: "Préstamos (déficit)" },
  interest: { color: "#b07a00", label: "Intereses" },
  housing: { color: PAL.blue, label: "Vivienda pública" },
};

const n1 = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
const sgn = (v, d = 1) => `${v > 0 ? "+" : "−"}${n1(Math.abs(v), d)}`;

function curve([x1, y1], [x2, y2], bend, at = 0.5) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const len = Math.hypot(x2 - x1, y2 - y1) || 1;
  const cx = mx + (-(y2 - y1) / len) * bend;
  const cy = my + ((x2 - x1) / len) * bend;
  const u = 1 - at;
  const point = [u * u * x1 + 2 * u * at * cx + at * at * x2, u * u * y1 + 2 * u * at * cy + at * at * y2];
  return { d: `M${x1} ${y1} Q${cx} ${cy} ${x2} ${y2}`, mid: point };
}

// Payments out of the purse to people read green when they grow; borrowing and interest red; taxes neutral.
function deltaColor(id, delta) {
  if (id === "loans" || id === "interest") return delta > 0 ? "#b3401a" : "#0f7a55";
  if (id === "pensions" || id === "services" || id === "housing") return delta > 0 ? "#0f7a55" : "#b3401a";
  return "#1d4f8f";
}

function Flow({ id, spec, value, delta, scale, still }) {
  const st = FLOW_STYLE[id];
  if (value <= 0.01) return null;
  const { d, mid: m } = curve(spec.from, spec.to, spec.bend, spec.at);
  const mid = spec.label || [m[0] + (spec.dx || 0) * scale, m[1] + (spec.dy || 0) * scale];
  const anchor = spec.anchor || "middle";
  const w = Math.min(44, 3 + value * 1.4) * scale;
  const coins = Math.max(1, Math.min(6, Math.round(value / 3)));
  const changed = Math.abs(delta) >= 0.005;
  return (
    <g className="scene__flow">
      <path d={d} stroke={st.color} strokeWidth={w} strokeOpacity="0.28" fill="none" strokeLinecap="round" />
      <path d={d} stroke={st.color} strokeWidth={Math.max(1.5, w / 6)} strokeOpacity="0.7" fill="none" strokeDasharray="2 9" strokeLinecap="round" />
      {still
        ? null
        : Array.from({ length: coins }, (_, i) => (
            <g key={i}>
              <circle r={6 * scale} fill="#ffd36b" stroke="#c98500" strokeWidth={1.5 * scale}>
                <animateMotion dur={`${3.6}s`} begin={`${(-3.6 * i) / coins}s`} repeatCount="indefinite" path={d} />
              </circle>
            </g>
          ))}
      <text x={mid[0]} y={mid[1] - 6} textAnchor={anchor} className="scene__flowLabel">
        {spec.short || st.label} {n1(value, value < 1 ? 2 : 1)} %
      </text>
      {changed ? (
        <text x={mid[0]} y={mid[1] + 14} textAnchor={anchor} className="scene__flowDelta" fill={deltaColor(id, delta)}>
          {sgn(delta, 2)} puntos
        </text>
      ) : null}
    </g>
  );
}

function Crowd({ x, y, cols, count, delta, old, label, sub, scale }) {
  const per = 22 * scale;
  const rows = Math.ceil(Math.max(count, count - delta) / cols);
  const total = Math.max(count, Math.round(count - delta));
  const figs = [];
  for (let i = 0; i < total; i += 1) {
    const r = Math.floor(i / cols);
    const c = i % cols;
    const fx = x + (c - (cols - 1) / 2) * per + (r % 2 ? per / 2 : 0);
    const fy = y - (rows - 1 - r) * 30 * scale;
    const added = i >= Math.round(count - delta) && delta > 0;
    const removed = i >= count && delta < 0;
    const shirt = old ? [PAL.purple, PAL.blue, PAL.green, PAL.ink2][i % 4] : [PAL.blue, PAL.orange, PAL.yellow, PAL.green, PAL.purple][i % 5];
    figs.push(
      <Figure key={i} x={fx} y={fy} s={0.82 * scale} old={old} shirt={shirt} skin={PAL.skin[i % 4]}
        hair={[PAL.hair.dark, PAL.hair.brown, PAL.hair.black, PAL.hair.blond][i % 4]} faded={removed} highlight={added ? PAL.green : undefined} />,
    );
  }
  return (
    <g>
      {figs}
      <text x={x} y={y + 26 * scale} textAnchor="middle" className="art__label">{label}</text>
      <text x={x} y={y + 44 * scale} textAnchor="middle" className="art__sub">{sub}</text>
    </g>
  );
}

export function useLayout(ref) {
  const [layout, setLayout] = useState("wide");
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver((entries) => setLayout(entries[0].contentRect.width < 640 ? "narrow" : "wide"));
    ro.observe(node);
    return () => ro.disconnect();
  }, [ref]);
  return layout;
}

export default function Scene({ model, run, t, composition }) {
  const wrap = useRef(null);
  const layout = useLayout(wrap);
  const [still, setStill] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return undefined;
    setStill(mq.matches);
    const on = () => setStill(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  const L = LAYOUTS[layout];
  const F = FLOWS[layout];
  const sc = layout === "wide" ? 1 : 0.8;
  const B = model.baseline;
  const year = model.years[t];

  const services = model.start.spending_pct - B.pension_pct[0] - model.start.interest_pct;
  const flows = {
    vat: [composition.vat + run.vat_revenue_pp[t] + run.vat_red_revenue_pp[t], run.vat_revenue_pp[t] + run.vat_red_revenue_pp[t]],
    irpf: [composition.irpf + run.irpf_revenue_pp[t] + run.irpf_back_pp[t], run.irpf_revenue_pp[t] + run.irpf_back_pp[t]],
    contrib: [composition.contrib + run.contrib_revenue_pp[t] + run.labour_revenue_pp[t], run.contrib_revenue_pp[t] + run.labour_revenue_pp[t]],
    corp: [composition.corp + run.corp_revenue_pp[t], run.corp_revenue_pp[t]],
    pensions: [run.pension_pct[t], run.pension_pct[t] - B.pension_pct[t]],
    services: [services, 0],
    loans: [Math.max(0, run.deficit_pct[t]), run.deficit_pct[t] - B.deficit_pct[t]],
    interest: [B.interest_pct[t] + run.interest_dev_pp[t], run.interest_dev_pp[t]],
    housing: [Math.max(0, run.hs_cost_pp?.[t] ?? 0), run.hs_cost_pp?.[t] ?? 0],
  };
  const pct = (v) => `${v > 0 ? "+" : "−"}${n1(Math.abs(v * 100))} %`;
  const k = (v) => `${v > 0 ? "+" : "−"}${Math.round(Math.abs(v)).toLocaleString("es-ES", { useGrouping: "always" })} mil`;
  const hs = (key) => run[key]?.[t] ?? 0;
  const housingLines = [
    Math.abs(hs("hs_rent_new")) >= 0.0005 ? `Alquiler de un contrato nuevo ${pct(hs("hs_rent_new"))}` : null,
    Math.abs(hs("hs_price")) >= 0.0005 ? `Precio ${pct(hs("hs_price"))}` : null,
    Math.abs(hs("hs_stock_k")) >= 0.5 ? `Viviendas ${k(hs("hs_stock_k"))}` : null,
    Math.abs(hs("hs_emancipated_k")) >= 0.5 ? `Jóvenes que se independizan ${k(hs("hs_emancipated_k"))}` : null,
  ].filter(Boolean);
  const workers = Math.max(0, (B.employment_k[t] + run.employment_k[t]) / 1000);
  const workersBase = B.employment_k[t] / 1000;
  const pensioners = Math.max(0, (B.pensioners_k[t] * (1 + run.pensioners_dev[t])) / 1000);
  const pensionersBase = B.pensioners_k[t] / 1000;
  const debt = run.debt_pct[t];
  const debtBase = B.debt_pct[t];
  const thousands = (v) => Math.round(v * 1000).toLocaleString("es-ES", { useGrouping: "always" });

  return (
    <div className="scene" ref={wrap}>
      <svg viewBox={`0 0 ${L.box[0]} ${L.box[1]}`} width="100%" role="img"
        aria-label={`En ${year}: deuda del ${n1(debt, 0)} % del PIB, gasto en pensiones del ${n1(flows.pensions[0])} %, ${n1(workers)} millones de personas trabajando y ${n1(pensioners)} millones cobrando pensión.`}>
        <text x={L.year[0]} y={L.year[1]} className="scene__year">{year}</text>
        {Object.entries(F).map(([id, spec]) => (
          <Flow key={id} id={id} spec={spec} value={flows[id][0]} delta={flows[id][1]} scale={sc} still={still} />
        ))}
        <Shop x={L.shop[0]} y={L.shop[1]} s={sc} />
        <text x={L.shop[0]} y={L.shop[1] + 26 * sc} textAnchor="middle" className="art__label">Tiendas</text>
        <text x={L.shop[0]} y={L.shop[1] + 44 * sc} textAnchor="middle" className="art__sub">todos pagan IVA al comprar</text>
        <Factory x={L.factory[0]} y={L.factory[1]} s={sc} />
        <text x={L.factory[0]} y={L.factory[1] + 26 * sc} textAnchor="middle" className="art__label">Empresas</text>
        <Crowd x={L.workers.x} y={L.workers.y} cols={L.workers.cols} count={Math.min(40, Math.round(workers))} delta={Math.round(workers) - Math.round(workersBase)}
          label="Trabajan" scale={sc}
          sub={`${n1(workers)} millones${Math.abs(run.employment_k[t]) >= 1 ? ` (${run.employment_k[t] > 0 ? "+" : "−"}${thousands(Math.abs(run.employment_k[t]) / 1000)})` : ""}`} />
        <PiggyBank x={L.piggy[0]} y={L.piggy[1]} s={L.piggy[2]} label="Caja pública"
          sub={run.deficit_pct[t] > 0 ? `déficit del ${n1(run.deficit_pct[t])} % del PIB` : `superávit del ${n1(-run.deficit_pct[t])} % del PIB`} />
        <Crowd x={L.pensioners.x} y={L.pensioners.y} cols={L.pensioners.cols} count={Math.min(30, Math.round(pensioners))} delta={Math.round(pensioners) - Math.round(pensionersBase)}
          old label="Cobran pensión" scale={sc}
          sub={`${n1(pensioners)} millones${Math.abs(pensioners - pensionersBase) >= 0.001 ? ` (${pensioners > pensionersBase ? "+" : "−"}${thousands(Math.abs(pensioners - pensionersBase))})` : ""}`} />
        <Services x={L.services[0]} y={L.services[1]} s={sc} />
        <text x={L.services[0]} y={L.services[1] + 26 * sc} textAnchor="middle" className="art__label">Servicios públicos</text>
        <CoinStack x={L.stack[0]} y={L.stack[1]} value={debt} base={debtBase} label="Deuda pública"
          sub={`${n1(debt, 0)} % del PIB${Math.abs(debt - debtBase) >= 0.5 ? ` (${sgn(debt - debtBase, 0)})` : ""}`} />
        <Housing x={L.housing[0]} y={L.housing[1]} s={sc} />
        <text x={L.housing[0]} y={L.housing[1] + 26 * sc} textAnchor="middle" className="art__label">Vivienda</text>
        {(housingLines.length ? housingLines : ["sin cambio"]).map((line, i) => (
          <text key={line} x={L.housing[0]} y={L.housing[1] + (44 + i * 18) * sc} textAnchor="middle" className="art__sub">{line}</text>
        ))}
        <Bank x={L.bank[0]} y={L.bank[1]} s={sc} />
        <text x={L.bank[0]} y={L.bank[1] + 26 * sc} textAnchor="middle" className="art__label">Quien presta</text>
      </svg>
      <p className="scene__key">
        Cada figura es un millón de personas. Cada moneda de la pila, 10 puntos de PIB de deuda. El grosor de cada flujo es su tamaño en % del PIB de {year};
        el número de color, cuánto cambia con tu escenario frente a la ley actual.
      </p>
    </div>
  );
}
