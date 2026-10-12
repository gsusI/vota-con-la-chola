import { ImageResponse } from "next/og";

// Generic 1200x630 PNG share card, rendered once at build time: /og/site.png.
// Used as og:image for pages without their own card (WhatsApp/X/Telegram ignore SVG previews).
export const dynamic = "force-static";
export const dynamicParams = false;

const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";

export async function generateStaticParams() {
  return [{ file: "site.png" }];
}

export async function GET() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "56px 64px" }}>
        <div style={{ display: "flex", fontSize: 26, color: TEAL, letterSpacing: 1 }}>DATOS PÚBLICOS · EVIDENCIA AUDITABLE</div>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, justifyContent: "center" }}>
          <span style={{ fontSize: 92, lineHeight: 1.05 }}>Vota Con La Chola</span>
          <span style={{ fontSize: 40, lineHeight: 1.25, marginTop: 24 }}>Qué votaron, qué gastaron y quién responde, con la fuente oficial a un clic.</span>
        </div>
        <div style={{ display: "flex", borderTop: `4px solid ${INK}`, paddingTop: 22, fontSize: 30, color: ACCENT }}>votaconlachola.org</div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
