import { ImageResponse } from "next/og";
import { closeMarginLabel, hookStatements, loadVotingAidSnapshot, statementHook } from "../../votingAidHooks.mjs";

// 1200x630 PNG cards, rendered once at build time: /citizen/vota/og/<statement_id>.png (+ inicio.png for the game itself).
export const dynamic = "force-static";
export const dynamicParams = false;

const HOME_ID = "inicio";
const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";

export async function generateStaticParams() {
  return [HOME_ID, ...hookStatements().map((st) => st.statement_id)].map((id) => ({ file: `${id}.png` }));
}

function textSize(text) {
  const n = text.length;
  if (n <= 70) return 64;
  if (n <= 110) return 54;
  if (n <= 150) return 46;
  return 40;
}

function Card({ eyebrow, title, badge, footer }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "56px 64px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 26, color: TEAL, letterSpacing: 1 }}>
        <span>{eyebrow}</span>
        {badge ? (
          <span style={{ background: ACCENT, color: "white", padding: "8px 20px", borderRadius: 999, fontSize: 28 }}>{badge}</span>
        ) : null}
      </div>
      <div style={{ display: "flex", flex: 1, alignItems: "center", fontSize: textSize(title), lineHeight: 1.18 }}>«{title}»</div>
      <div style={{ display: "flex", flexDirection: "column", borderTop: `4px solid ${INK}`, paddingTop: 22 }}>
        <span style={{ fontSize: 34 }}>{footer}</span>
        <span style={{ fontSize: 26, color: ACCENT, marginTop: 8 }}>votaconlachola.org · ¿Con quién coincides?</span>
      </div>
    </div>
  );
}

export async function GET(_request, { params }) {
  const { file } = await params;
  const id = String(file).replace(/\.png$/u, "");
  const card =
    id === HOME_ID
      ? {
          eyebrow: "CONGRESO DE LOS DIPUTADOS",
          title: "Lo que votaron, no lo que dicen",
          badge: null,
          footer: "Responde y descubre qué partidos votaron como tú.",
        }
      : (() => {
          const statement = hookStatements(loadVotingAidSnapshot()).find((st) => st.statement_id === id);
          const hook = statementHook(statement);
          return {
            eyebrow: hook.concern ? `CONGRESO · ${hook.concern.toUpperCase()}` : "CONGRESO DE LOS DIPUTADOS",
            title: hook.text,
            badge: hook.closeMargin !== null ? closeMarginLabel(hook.closeMargin) : null,
            footer: "¿De acuerdo? Adivina qué partidos votaron como tú.",
          };
        })();
  return new ImageResponse(<Card {...card} />, { width: 1200, height: 630 });
}
