import { ImageResponse } from "next/og";
import { readPublicJson } from "../../../../static-snapshot.mjs";
import { SCENARIOS, fmt, mainFindings, scenarioBySlug, scenarioResult } from "../../scenarios.mjs";

// 1200x630 PNG cards, rendered once at build time: /visualizaciones/sistema/og/<slug>.png for each scenario, plus
// inicio.png (the simulator) and escenarios.png (the index). Numbers come from the same engine run as the page.
export const dynamic = "force-static";
export const dynamicParams = false;

const HOME_ID = "inicio";
const INDEX_ID = "escenarios";
const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#2a78d6";
const WARM = "#d84a32";

export async function generateStaticParams() {
  return [HOME_ID, INDEX_ID, ...SCENARIOS.map((sc) => sc.slug)].map((id) => ({ file: `${id}.png` }));
}

function textSize(text) {
  const n = text.length;
  if (n <= 60) return 66;
  if (n <= 90) return 56;
  if (n <= 120) return 48;
  return 42;
}

function Card({ eyebrow, title, badge, footer }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "56px 64px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 26, color: ACCENT, letterSpacing: 1 }}>
        <span>{eyebrow}</span>
      </div>
      <div style={{ display: "flex", flex: 1, alignItems: "center", fontSize: textSize(title), lineHeight: 1.16 }}>{title}</div>
      {badge ? (
        <div style={{ display: "flex", marginBottom: 26 }}>
          <span style={{ background: WARM, color: "white", padding: "10px 24px", borderRadius: 999, fontSize: 34 }}>{badge}</span>
        </div>
      ) : null}
      <div style={{ display: "flex", flexDirection: "column", borderTop: `4px solid ${INK}`, paddingTop: 20 }}>
        <span style={{ fontSize: 28 }}>{footer}</span>
        <span style={{ fontSize: 26, color: ACCENT, marginTop: 8 }}>votaconlachola.org · Simulador: ¿quién lo paga?</span>
      </div>
    </div>
  );
}

export async function GET(_request, { params }) {
  const { file } = await params;
  const id = String(file).replace(/\.png$/u, "");
  const model = readPublicJson("visualizaciones/data/sistema.json", null);
  let card;
  if (id === HOME_ID) {
    const m = mainFindings(model);
    card = {
      eyebrow: "SIMULADOR · PENSIONES, IMPUESTOS Y VIVIENDA",
      title: "Si se suben las pensiones o los impuestos, o se interviene la vivienda, ¿quién lo paga?",
      badge: `Pensiones IPC + 1: ${fmt.pp(m.debt50, 0)} pp de deuda en 2050`,
      footer: "Mueve las palancas: cuánto cuesta, a quién y con qué incertidumbre.",
    };
  } else if (id === INDEX_ID) {
    card = {
      eyebrow: "SIMULADOR · ESCENARIOS",
      title: "Pensiones, IVA, IRPF, alquiler: qué pasa si se cambian y quién lo paga",
      badge: `${SCENARIOS.length} preguntas con su respuesta y su rango`,
      footer: "Escenarios de un modelo con supuestos visibles, no predicciones.",
    };
  } else {
    const sc = scenarioBySlug(id);
    const r = scenarioResult(model, sc);
    card = {
      eyebrow: `SIMULADOR · ${sc.group.toUpperCase()}`,
      title: sc.question,
      badge: r.badge,
      footer: "Escenario de un modelo con supuestos visibles, no una predicción.",
    };
  }
  return new ImageResponse(<Card {...card} />, { width: 1200, height: 630 });
}
