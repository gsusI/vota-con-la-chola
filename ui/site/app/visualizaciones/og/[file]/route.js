import { ImageResponse } from "next/og";
import { readPublicJson } from "../../../static-snapshot.mjs";
import { VIZ_SLUGS, articleSeo } from "../../articleSeo.mjs";

// 1200x630 PNG share cards, rendered once at build time: /visualizaciones/og/<slug>.png (+ visualizaciones.png for the hub).
// Each shows the article's finding with its number and a zero-based sparkline of the series behind it.
export const dynamic = "force-static";
export const dynamicParams = false;

const HUB_ID = "visualizaciones";
const INK = "#17191f";
const INK_2 = "#52514e";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";
const BLUE = "#2a78d6";
const PEER = "#9a988f";

export async function generateStaticParams() {
  return [HUB_ID, ...VIZ_SLUGS].map((id) => ({ file: `${id}.png` }));
}

function load(slug) {
  const data = readPublicJson(`visualizaciones/data/${slug}.json`, null);
  if (!data) throw new Error(`Missing visualizaciones/data/${slug}.json`);
  return articleSeo(slug, data);
}

// Lines are drawn per series and never joined across gaps or series (breaks stay visible); y starts at zero.
function Sparkline({ series, breaks = [], width = 460, height = 230 }) {
  const all = series.flatMap((s) => s.points.filter((p) => p.value != null));
  const xMin = Math.min(...all.map((p) => p.year));
  const xMax = Math.max(...all.map((p) => p.year));
  const yMax = Math.max(...all.map((p) => p.value)) * 1.08;
  const sx = (year) => ((year - xMin) / Math.max(1, xMax - xMin)) * (width - 8) + 4;
  const sy = (value) => height - 4 - (value / yMax) * (height - 12);
  const path = (points) => {
    let d = "";
    let prev = null;
    for (const p of points) {
      if (p.value == null) {
        prev = null;
        continue;
      }
      d += `${prev ? "L" : "M"}${sx(p.year).toFixed(1)},${sy(p.value).toFixed(1)} `;
      prev = p;
    }
    return d.trim();
  };
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <line x1={0} x2={width} y1={height - 4} y2={height - 4} stroke={INK} strokeWidth={2} />
      {breaks
        .filter((year) => year > xMin && year < xMax)
        .map((year) => (
          <line key={year} x1={sx(year)} x2={sx(year)} y1={6} y2={height - 4} stroke={PEER} strokeWidth={1.5} strokeDasharray="4 4" />
        ))}
      {series.map((s, i) => (
        <path key={i} d={path(s.points)} fill="none" stroke={s.main ? BLUE : PEER} strokeWidth={s.main ? 6 : 3.5} strokeLinejoin="round" strokeLinecap="round" />
      ))}
    </svg>
  );
}

function headlineSize(text) {
  const n = text.length;
  if (n <= 70) return 46;
  if (n <= 95) return 40;
  return 35;
}

function ArticleCard({ seo }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "48px 64px" }}>
      <div style={{ display: "flex", fontSize: 24, color: TEAL, letterSpacing: 1 }}>{`VISUALIZACIONES · ${seo.topic.toUpperCase()}`}</div>
      <div style={{ display: "flex", fontSize: headlineSize(seo.headline), lineHeight: 1.2, marginTop: 18 }}>{seo.headline}</div>
      <div style={{ display: "flex", flex: 1, alignItems: "flex-end", justifyContent: "space-between", marginTop: 18 }}>
        <div style={{ display: "flex", flexDirection: "column", width: 560 }}>
          <span style={{ fontSize: 104, lineHeight: 1, color: BLUE }}>{seo.card.big}</span>
          <span style={{ fontSize: 28, lineHeight: 1.25, marginTop: 10 }}>{seo.card.bigLabel}</span>
          <span style={{ fontSize: 24, lineHeight: 1.25, marginTop: 10, color: INK_2 }}>{seo.card.line}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
          <Sparkline series={seo.card.spark.series} breaks={seo.card.spark.breaks} />
          <span style={{ fontSize: 18, color: INK_2, marginTop: 8, width: 460 }}>{seo.card.spark.label}</span>
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", borderTop: `4px solid ${INK}`, paddingTop: 16, marginTop: 22, fontSize: 24 }}>
        <span style={{ color: ACCENT }}>votaconlachola.org</span>
        <span style={{ color: INK_2 }}>Fuente oficial en cada gráfico · datos en CSV</span>
      </div>
    </div>
  );
}

function HubCard({ items }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "52px 64px" }}>
      <div style={{ display: "flex", fontSize: 24, color: TEAL, letterSpacing: 1 }}>VISUALIZACIONES · DATOS PÚBLICOS</div>
      <div style={{ display: "flex", fontSize: 60, lineHeight: 1.1, marginTop: 18 }}>España en datos, con la fuente oficial</div>
      <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "space-between", marginTop: 12 }}>
        {/* Glyphs outside the bundled font (e.g. arrows) need a network fetch at build time: keep card copy to plain text. */}
        {items.map((seo) => (
          <div key={seo.slug} style={{ display: "flex", flexDirection: "column", alignSelf: "flex-start", width: 200 }}>
            <span style={{ fontSize: 22, color: TEAL }}>{seo.topic}</span>
            <span style={{ fontSize: 42, lineHeight: 1.05, color: BLUE, marginTop: 6, whiteSpace: "nowrap" }}>{seo.card.big}</span>
            <span style={{ fontSize: 19, lineHeight: 1.25, marginTop: 8 }}>{seo.card.bigLabel}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", borderTop: `4px solid ${INK}`, paddingTop: 16, fontSize: 24 }}>
        <span style={{ color: ACCENT }}>votaconlachola.org/visualizaciones</span>
        <span style={{ color: INK_2 }}>Ejes desde cero · rupturas a la vista · CSV</span>
      </div>
    </div>
  );
}

export async function GET(_request, { params }) {
  const { file } = await params;
  const id = String(file).replace(/\.png$/u, "");
  const body = id === HUB_ID ? <HubCard items={VIZ_SLUGS.map(load)} /> : <ArticleCard seo={load(id)} />;
  return new ImageResponse(body, { width: 1200, height: 630 });
}
