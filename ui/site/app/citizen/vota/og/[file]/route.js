import { ImageResponse } from "next/og";
import { closeMarginLabel, hookStatements, loadVotingAidSnapshot, statementHook } from "../../votingAidHooks.mjs";
import { loadVotaData, testFacts, topicsWithVotes } from "../../votaSeoData.mjs";

// 1200x630 PNG cards, rendered once at build time: /citizen/vota/og/<statement_id>.png (+ inicio.png for the game itself,
// one per explore page, partido-<party_id>.png and tema-<topic_id>.png for the indexable party and topic pages).
export const dynamic = "force-static";
export const dynamicParams = false;

const HOME_ID = "inicio";
const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";

// Cards of the explore pages: [eyebrow, title, footer].
const PAGE_CARDS = {
  partidos: ["CONGRESO · XV LEGISLATURA", "Cómo vota cada partido", "Tema a tema y con quién vota igual, con cada voto enlazado."],
  diputados: ["CONGRESO · XV LEGISLATURA", "Qué ha votado tu diputado", "Cada diputado y diputada, voto a voto, con la fuente oficial."],
  temas: ["CONGRESO · XV LEGISLATURA", "Hacia dónde empujó cada partido", "Todas las votaciones del Pleno, colocadas por temas."],
  votacion: ["CONGRESO · XV LEGISLATURA", "Cada votación, diputado a diputado", "Qué se votó, el resultado y el voto de cada uno."],
  explorar: ["CONGRESO · XV LEGISLATURA", "Explora cómo vota el Congreso", "Partidos, diputados y votaciones, sin hacer el test."],
  mapa: ["CONGRESO · XV LEGISLATURA", "Dónde está cada partido", "Compáralos tema a tema según cómo votaron."],
};

export async function generateStaticParams() {
  const { snapshot, atlas } = loadVotaData();
  return [
    HOME_ID,
    ...Object.keys(PAGE_CARDS),
    ...(snapshot.parties || []).map((p) => `partido-${p.party_id}`),
    ...topicsWithVotes(atlas).map((t) => `tema-${t.topic_id}`),
    ...hookStatements().map((st) => st.statement_id),
  ].map((id) => ({ file: `${id}.png` }));
}

function pageCard(id) {
  const { snapshot, atlas } = loadVotaData();
  if (PAGE_CARDS[id]) {
    const [eyebrow, title, footer] = PAGE_CARDS[id];
    return { eyebrow, title, footer, quote: false };
  }
  if (id.startsWith("partido-")) {
    const party = (snapshot.parties || []).find((p) => `partido-${p.party_id}` === id);
    if (!party) return null;
    const facts = testFacts(snapshot);
    return {
      eyebrow: "CONGRESO · XV LEGISLATURA",
      title: `Cómo vota ${party.label}`,
      footer: `Su postura en las ${facts.questions} preguntas del test, voto a voto.`,
      quote: false,
    };
  }
  if (id.startsWith("tema-")) {
    const topic = topicsWithVotes(atlas).find((t) => `tema-${t.topic_id}` === id);
    if (!topic) return null;
    return { eyebrow: "CONGRESO · XV LEGISLATURA", title: `${topic.label}: qué vota cada partido`, footer: "Hacia dónde empujaron sus votos, con cada voto enlazado.", quote: false };
  }
  return null;
}

function textSize(text) {
  const n = text.length;
  if (n <= 70) return 64;
  if (n <= 110) return 54;
  if (n <= 150) return 46;
  return 40;
}

function Card({ eyebrow, title, badge, footer, quote = true }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: PAPER, color: INK, padding: "56px 64px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 26, color: TEAL, letterSpacing: 1 }}>
        <span>{eyebrow}</span>
        {badge ? (
          <span style={{ background: ACCENT, color: "white", padding: "8px 20px", borderRadius: 999, fontSize: 28 }}>{badge}</span>
        ) : null}
      </div>
      <div style={{ display: "flex", flex: 1, alignItems: "center", fontSize: textSize(title), lineHeight: 1.18 }}>{quote ? `«${title}»` : title}</div>
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
    pageCard(id) ||
    (id === HOME_ID
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
        })());
  return new ImageResponse(<Card {...card} />, { width: 1200, height: 630 });
}
