"use client";

import { useEffect, useState } from "react";
import { Icon, PAL } from "./art";

// Policy cards: an icon, what it is, a stepper. Then «¿Quién paga?» as four illustrated choices, the context, and
// ready-made scenarios.
export const POLICIES = [
  { key: "reval", group: "Pensiones", icon: "pension", title: "Pensiones", unit: "pp al año sobre el IPC", min: -2, max: 2, step: 0.5, tone: PAL.green,
    hint: "Todas las pensiones, cada año desde 2026. 0 = ley actual (IPC)." },
  { key: "age", group: "Pensiones", icon: "age", title: "Edad de jubilación", unit: "años", min: -2, max: 2, step: 0.5, tone: PAL.green,
    hint: "Edad efectiva frente a la línea base, a dos meses por año." },
  { key: "irpfAll", group: "Impuestos", icon: "irpf", title: "IRPF", unit: "pp en todos los tramos", min: -3, max: 3, step: 0.5, tone: PAL.blue },
  { key: "irpfTop", group: "Impuestos", icon: "top", title: "IRPF alto", unit: "pp por encima de 60.000 €", min: -5, max: 5, step: 1, tone: PAL.blue },
  { key: "vatStd", group: "Impuestos", icon: "cart", title: "IVA general", unit: "pp (hoy 21 %)", min: -3, max: 3, step: 0.5, tone: PAL.orange },
  { key: "vatRed", group: "Impuestos", icon: "bread", title: "IVA reducido", unit: "pp (hoy 10 %)", min: -3, max: 3, step: 0.5, tone: PAL.orange,
    hint: "Alimentos elaborados, restaurantes, transporte, agua." },
  { key: "contrib", group: "Pensiones", icon: "payroll", title: "Cotizaciones", unit: "pp de la base", min: -1, max: 2, step: 0.25, tone: PAL.yellow },
  { key: "corp", group: "Impuestos", icon: "factory", title: "Sociedades", unit: "pp (hoy 25 %)", min: -5, max: 5, step: 1, tone: PAL.purple },
  { key: "pubHomes", icon: "building", title: "Vivienda pública", unit: "mil más al año", values: [0, 10, 20, 40, 60], tone: PAL.blue, group: "Vivienda",
    hint: "Alquiler público que se empieza a construir desde 2026; tarda unos años en estar listo." },
  { key: "land", icon: "land", title: "Suelo liberado", unit: "mil viviendas al año", values: [0, 10, 20, 40, 60], tone: PAL.blue, group: "Vivienda" },
  { key: "capCov", icon: "cap", title: "Tope del alquiler: alcance", unit: "% del alquiler de mercado cubierto", values: [0, 25, 50, 75, 100], tone: PAL.orange, group: "Vivienda",
    hint: "Hogares en alquiler de mercado en zonas tensionadas, además de los ya cubiertos." },
  { key: "capCut", icon: "cap", title: "Tope del alquiler: rebaja", unit: "% frente al mercado", values: [0, 5, 10, 15, 20], tone: PAL.orange, group: "Vivienda" },
  { key: "tourCut", icon: "suitcase", title: "Pisos turísticos", unit: "% retirados", values: [0, 25, 50, 75, 100], tone: PAL.purple, group: "Vivienda" },
  { key: "ltvCap", icon: "mortgage", title: "Hipoteca máxima", unit: "% del precio", values: [0, 90, 80, 70], labels: { 0: "Sin límite" }, tone: PAL.yellow, group: "Vivienda" },
  { key: "ltiCap", icon: "mortgage", title: "Hipoteca frente a renta", unit: "veces la renta", values: [0, 6, 4.5], labels: { 0: "Sin límite" }, tone: PAL.yellow, group: "Vivienda" },
];

// Beyond the reliable range: wider limits, bigger steps and shortcuts, unlocked once after a confirmation.
// `abolish` values (the rate change that removes a tax) are computed by the page from revenue per point.
export const EXTREMES = {
  reval: { min: -10, max: 10, step: 1 },
  age: { min: -5, max: 10, step: 1 },
  irpfAll: { min: "abolish", max: 20, step: 2, shortcuts: [["abolish", "Sin IRPF"]] },
  irpfTop: { min: -20, max: 30, step: 5 },
  vatStd: { min: -21, max: 20, step: 1, shortcuts: [[-21, "Sin IVA general"]] },
  vatRed: { min: -10, max: 11, step: 1, shortcuts: [[-10, "Sin IVA reducido"], [11, "Todo al 21 %"]] },
  contrib: { min: "abolish", max: 20, step: 2, shortcuts: [["abolish", "Sin cotizaciones"]] },
  corp: { min: -25, max: 25, step: 5, shortcuts: [[-25, "Sin Sociedades"]] },
  pubHomes: { values: [100, 200, 500] },
  land: { values: [100, 200, 500] },
  capCut: { values: [30, 50] },
  ltvCap: { values: [50, 30] },
  ltiCap: { values: [3, 2] },
};

/** Lever values outside the reliable range (for the banner and to unlock a shared link). */
export function outOfRange(levers) {
  return POLICIES.filter((p) => {
    const v = levers[p.key];
    if (p.values) return !p.values.includes(v);
    return v < p.min - 1e-9 || v > p.max + 1e-9;
  });
}

export const CLOSURE_CHOICES = [
  { id: "deuda", icon: "debt", label: "Con deuda", note: "nadie paga hoy; crecen la deuda y sus intereses" },
  { id: "cotizaciones", icon: "payroll", label: "Con cotizaciones", note: "sube la cotización lo necesario" },
  { id: "iva", icon: "cart", label: "Con IVA", note: "sube el IVA general lo necesario" },
  { id: "irpf", icon: "irpf", label: "Con IRPF", note: "suben todos los tramos lo necesario" },
];

export const PRESETS = [
  { label: "Subir las pensiones 1 punto, con deuda", levers: { reval: 1 } },
  { label: "…y pagarlo con IVA", levers: { reval: 1, closure: "iva" } },
  { label: "…o con IRPF", levers: { reval: 1, closure: "irpf" } },
  { label: "Jubilarse 2 años más tarde", levers: { age: 2 } },
  { label: "Bajar 2 puntos el IVA general", levers: { vatStd: -2 } },
  { label: "Subir 3 puntos el IRPF alto", levers: { irpfTop: 3 } },
  { label: "Un tercio menos de inmigración", levers: { migration: "low" } },
  { label: "20.000 viviendas públicas más al año", levers: { pubHomes: 20 } },
  { label: "Tope del alquiler: −10 % en la mitad del mercado", levers: { capCov: 50, capCut: 10 } },
  { label: "Retirar la mitad de los pisos turísticos", levers: { tourCut: 50 } },
  { label: "Hipotecas hasta el 80 % y 4,5 veces la renta", levers: { ltvCap: 80, ltiCap: 4.5 } },
];

const fmt = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("es-ES")}`;

function PolicyCard({ p, value, onChange, compact, unlocked, askUnlock, abolish }) {
  const on = value !== 0;
  const x = EXTREMES[p.key];
  const resolve = (v) => (v === "abolish" ? abolish[p.key] : v);
  // Value lists: the reliable ones, then the extreme ones once unlocked (in the order that moves away from 0).
  const list = p.values ? (unlocked && x?.values ? [...p.values, ...x.values] : p.values) : null;
  const lo = unlocked && x && !p.values ? resolve(x.min) : p.min;
  const hi = unlocked && x && !p.values ? x.max : p.max;
  const stepAt = (v, dir) => {
    const outside = dir > 0 ? v >= p.max : v <= p.min;
    return unlocked && x?.step && outside ? x.step : p.step;
  };
  const round = (v) => Math.round(v * 100) / 100;
  const idx = list ? Math.max(0, list.indexOf(value)) : -1;
  const go = (dir) => {
    if (list) {
      const next = idx + dir;
      if (next >= list.length) return x?.values && !unlocked ? askUnlock(() => onChange(x.values[0])) : null;
      return onChange(list[Math.max(0, next)]);
    }
    const target = round(value + dir * stepAt(value, dir));
    if (target > p.max + 1e-9 || target < p.min - 1e-9) {
      if (!x) return null;
      if (!unlocked) return askUnlock(() => onChange(target));
    }
    return onChange(Math.min(hi, Math.max(lo, target)));
  };
  const atMin = list ? idx <= 0 : value <= lo + 1e-9 && (unlocked || !x);
  const atMax = list ? idx >= list.length - 1 && (unlocked || !x?.values) : value >= hi - 1e-9 && (unlocked || !x);
  const prefix = { capCut: "−", pubHomes: "+", land: "+" }[p.key] ?? "";
  const shortcut = x?.shortcuts?.find(([v]) => Math.abs(resolve(v) - value) < 1e-6);
  const shown = shortcut
    ? shortcut[1]
    : p.labels?.[value] ?? (p.values ? (value ? `${prefix}${value.toLocaleString("es-ES")}` : "0") : on ? fmt(round(value)) : "0");
  const extreme = list ? !p.values.includes(value) : value < p.min - 1e-9 || value > p.max + 1e-9;
  return (
    <div className={`pcard${on ? " is-on" : ""}${extreme ? " is-extreme" : ""}`} style={{ "--tone": p.tone }} title={p.hint}>
      <span className="pcard__icon">
        <Icon name={p.icon} size={26} />
      </span>
      <span className="pcard__body">
        <span className="pcard__title">{p.title}</span>
        <span className="pcard__value">
          {shown} {shortcut || p.labels?.[value] ? null : <small>{p.unit}</small>}
        </span>
        {p.hint && !compact ? <span className="pcard__hint">{p.hint}</span> : null}
        {unlocked && x && !p.values ? (
          <span className="pcard__extreme">
            <input type="number" step={x.step} min={lo} max={hi} value={round(value)} aria-label={`${p.title}: valor`}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v)) onChange(Math.min(hi, Math.max(lo, v)));
              }} />
            {(x.shortcuts || []).map(([v, label]) => (
              <button key={label} type="button" className="chip chip--tiny" onClick={() => onChange(resolve(v))}>
                {label}
              </button>
            ))}
          </span>
        ) : null}
      </span>
      <span className="pcard__steps">
        <button type="button" aria-label={`${p.title}: menos`} disabled={atMin} onClick={() => go(-1)}>
          −
        </button>
        <button type="button" aria-label={`${p.title}: más`} disabled={atMax} onClick={() => go(1)}>
          +
        </button>
      </span>
    </div>
  );
}

function UnlockDialog({ onYes, onNo }) {
  return (
    <div className="unlock" role="dialog" aria-modal="true" aria-labelledby="unlock-title">
      <div className="unlock__box">
        <h3 id="unlock-title">¿Ver valores extremos?</h3>
        <p>
          El modelo está calibrado con cambios parecidos a los que se han visto en España y en países comparables. Fuera de ese rango sigue calculando con
          las mismas relaciones, en línea recta, así que el resultado sirve para ilustrar el mecanismo (qué se mueve y hacia dónde), no como estimación:
          quitar un impuesto entero o duplicar las pensiones cambiaría también cosas que el modelo no tiene.
        </p>
        <div className="unlock__actions">
          <button type="button" className="chip is-on" onClick={onYes}>
            Sí, quiero verlo
          </button>
          <button type="button" className="chip" onClick={onNo}>
            Volver
          </button>
        </div>
      </div>
    </div>
  );
}

const GROUPS = [
  { id: "Pensiones", icon: "pension" },
  { id: "Impuestos", icon: "irpf" },
  { id: "Vivienda", icon: "building" },
];

export default function Controls({ levers, setLever, setLevers, needsClosure, compact, unlocked, setUnlocked, abolish }) {
  const [pending, setPending] = useState(null);
  const askUnlock = (apply) => setPending(() => apply);
  const activeIn = (g) => POLICIES.filter((p) => p.group === g && levers[p.key]).length;
  const [tab, setTab] = useState("Pensiones");
  // Follow the scenario: open the tab of the first lever that moved (presets, shared links).
  useEffect(() => {
    const moved = POLICIES.find((p) => levers[p.key]);
    if (moved && !activeIn(tab)) setTab(moved.group);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [levers]);
  return (
    <div className="ctrl">
      <div className="ctrl__presets" role="group" aria-label="Escenarios de ejemplo">
        <span className="ctrl__kicker">Prueba</span>
        {PRESETS.map((pr) => (
          <button key={pr.label} type="button" className="chip" onClick={() => setLevers(pr.levers)}>
            {pr.label}
          </button>
        ))}
        <button type="button" className="chip chip--ghost" onClick={() => setLevers({})}>
          Volver a la ley actual
        </button>
      </div>
      <div className="ctrl__policies">
      <div className="ctrl__tabs" role="tablist" aria-label="Palancas">
        {GROUPS.map((g) => (
          <button key={g.id} type="button" role="tab" aria-selected={tab === g.id} className={`ctrl__tab${tab === g.id ? " is-on" : ""}`} onClick={() => setTab(g.id)}>
            <Icon name={g.icon} size={20} />
            {g.id}
            {activeIn(g.id) ? <span className="ctrl__badge">{activeIn(g.id)}</span> : null}
          </button>
        ))}
      </div>
      <div className="ctrl__cards" role="tabpanel">
        {POLICIES.filter((p) => p.group === tab).map((p) => (
          <PolicyCard key={p.key} p={p} value={levers[p.key]} onChange={(v) => setLever(p.key, v)} compact={compact}
            unlocked={unlocked} askUnlock={askUnlock} abolish={abolish} />
        ))}
      </div>
      {unlocked ? null : (
        <button type="button" className="ctrl__unlockLink" onClick={() => askUnlock(() => {})}>
          Probar valores extremos (quitar un impuesto, duplicar las pensiones…)
        </button>
      )}
      </div>
      {pending ? (
        <UnlockDialog
          onYes={() => {
            setUnlocked(true);
            pending();
            setPending(null);
          }}
          onNo={() => setPending(null)}
        />
      ) : null}
      <fieldset className={`ctrl__closure${needsClosure ? " is-needed" : ""}`}>
        <legend>¿Quién paga lo que cuesta cada año?</legend>
        <div>
          {CLOSURE_CHOICES.map((c) => (
            <label key={c.id} className={levers.closure === c.id ? "is-on" : ""}>
              <input type="radio" name="closure" checked={levers.closure === c.id} onChange={() => setLever("closure", c.id)} />
              <Icon name={c.icon} size={30} />
              <span>{c.label}</span>
              <small>{c.note}</small>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="ctrl__context">
        <span className="ctrl__kicker">
          <Icon name="people" size={18} /> Inmigración (escenarios oficiales)
        </span>
        {[
          ["low", "−33 %"],
          ["base", "Base"],
          ["high", "+33 %"],
        ].map(([id, label]) => (
          <button key={id} type="button" className={`chip${levers.migration === id ? " is-on" : ""}`} onClick={() => setLever("migration", id)}>
            {label}
          </button>
        ))}
        <span className="ctrl__kicker">
          <Icon name="rate" size={18} /> Tipos de interés
        </span>
        {[-1, 0, 1, 2].map((v) => (
          <button key={v} type="button" className={`chip${levers.rateShock === v ? " is-on" : ""}`} onClick={() => setLever("rateShock", v)}>
            {v ? `${fmt(v)} pp` : "Base"}
          </button>
        ))}
      </div>
    </div>
  );
}
