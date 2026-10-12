// Renders the Twitter/X campaign images (1200x675) with the same look as the site's OG cards.
// Usage (from the repo root): node docs/communications/twitter-kit/render.mjs
// Figures are copied by hand from ui/site/out/citizen/data/voting_aid_generales_v1.json; re-check them if the snapshot changes.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(HERE, "../../../ui/site/package.json"));
const { ImageResponse } = require("next/og");
const React = require("react");
const h = React.createElement;

const OUT = process.argv[2] || path.join(HERE, "img");
mkdirSync(OUT, { recursive: true });

const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";
const MUTED = "#5b616e";
const W = 1200;
const H = 675;

const row = (style, ...kids) => h("div", { style: { display: "flex", ...style } }, ...kids);
const col = (style, ...kids) => h("div", { style: { display: "flex", flexDirection: "column", ...style } }, ...kids);
const span = (style, text) => h("span", { style }, text);

function footer(cta) {
  return col(
    { borderTop: `4px solid ${INK}`, paddingTop: 20 },
    span({ fontSize: 32 }, cta),
    span({ fontSize: 26, color: ACCENT, marginTop: 6 }, "votaconlachola.org · ¿Con quién coincides?"),
  );
}

function eyebrowRow(eyebrow, badge) {
  return row(
    { justifyContent: "space-between", alignItems: "center", fontSize: 26, color: TEAL, letterSpacing: 1 },
    span({}, eyebrow),
    badge ? span({ background: ACCENT, color: "white", padding: "8px 20px", borderRadius: 999, fontSize: 26 }, badge) : null,
  );
}

// Tally bar: yes / no / abstain as proportional segments, numbers above. Never shows parties.
function tally({ yes, no, abstain = 0 }) {
  const total = yes + no + abstain;
  const seg = (n, color) => (n > 0 ? h("div", { style: { display: "flex", width: `${(n / total) * 100}%`, height: 26, background: color } }) : null);
  const label = (n, word, color) => span({ fontSize: 30, color, marginRight: 36 }, `${n} ${word}`);
  return col(
    { marginTop: 26 },
    row({ alignItems: "baseline" }, label(yes, "sí", TEAL), label(no, "no", ACCENT), abstain ? label(abstain, abstain === 1 ? "abstención" : "abstenciones", MUTED) : null),
    row({ marginTop: 10, width: "100%", borderRadius: 6, overflow: "hidden" }, seg(yes, TEAL), seg(no, ACCENT), seg(abstain, "#b9bdc6")),
  );
}

function size(text) {
  const n = text.length;
  if (n <= 45) return 70;
  if (n <= 75) return 60;
  if (n <= 110) return 52;
  return 44;
}

// Question card: the hook, the official tally, a CTA. The answer goes in the reply, not the image.
function question({ eyebrow, title, badge, totals, date, cta = "Adivina quién votó qué. Luego mira tu podio." }) {
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "52px 64px" },
    eyebrowRow(eyebrow, badge),
    col(
      { flex: 1, justifyContent: "center" },
      span({ fontSize: size(title), lineHeight: 1.15 }, title),
      totals ? tally(totals) : null,
      date ? span({ fontSize: 22, color: MUTED, marginTop: 12 }, date) : null,
    ),
    footer(cta),
  );
}

// Statement card: one big line on dark ink, for the core message.
function statement({ eyebrow, lines, sub }) {
  return col(
    { width: "100%", height: "100%", background: INK, color: PAPER, padding: "52px 64px" },
    span({ fontSize: 26, color: "#5fd0c4", letterSpacing: 1 }, eyebrow),
    col({ flex: 1, justifyContent: "center" }, ...lines.map((l, i) => span({ fontSize: 76, lineHeight: 1.12, color: i === lines.length - 1 ? "#ff8a73" : PAPER }, l))),
    col(
      { borderTop: `4px solid ${PAPER}`, paddingTop: 20 },
      span({ fontSize: 30 }, sub),
      span({ fontSize: 26, color: "#ff8a73", marginTop: 6 }, "votaconlachola.org"),
    ),
  );
}

// Reveal card: two parties that voted the same, plus the full yes/no lists.
function reveal({ eyebrow, title, groups, date }) {
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "52px 64px" },
    eyebrowRow(eyebrow, null),
    col(
      { flex: 1, justifyContent: "center" },
      span({ fontSize: size(title), lineHeight: 1.15 }, title),
      ...groups.map(([word, color, parties]) =>
        row({ marginTop: 18, alignItems: "baseline" }, span({ fontSize: 30, color, width: 90 }, word), span({ fontSize: 30 }, parties)),
      ),
      span({ fontSize: 22, color: MUTED, marginTop: 14 }, date),
    ),
    footer("¿Y tú? Responde y mira con quién coincides."),
  );
}

// "Dijeron / Votaron" card: what was said, what was voted, and the party's own defence.
function dijeron({ eyebrow, rows, source }) {
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "48px 64px" },
    eyebrowRow(eyebrow, "Dijeron / Votaron"),
    col(
      { flex: 1, justifyContent: "center" },
      ...rows.map(([label, color, text]) =>
        row({ marginTop: 20, alignItems: "flex-start" }, span({ fontSize: 24, color, width: 170, marginTop: 6, letterSpacing: 1 }, label), span({ fontSize: 34, lineHeight: 1.2, flex: 1 }, text)),
      ),
      span({ fontSize: 22, color: MUTED, marginTop: 18 }, source),
    ),
    footer("No les preguntes qué harán. Mira qué votaron."),
  );
}

// How-it-works card.
function steps() {
  const step = (n, t, d) =>
    row(
      { alignItems: "center", marginTop: 22 },
      span({ display: "flex", width: 64, height: 64, borderRadius: 999, background: ACCENT, color: "white", fontSize: 34, justifyContent: "center", alignItems: "center", marginRight: 26 }, n),
      col({}, span({ fontSize: 40 }, t), span({ fontSize: 26, color: MUTED }, d)),
    );
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "52px 64px" },
    eyebrowRow("CÓMO FUNCIONA · 2 MINUTOS · SIN REGISTRO", null),
    col(
      { flex: 1, justifyContent: "center" },
      step("1", "Responde a lo que de verdad se votó", "33 votaciones reales de la última legislatura del Congreso"),
      step("2", "Mira qué votó cada partido", "Cada voto con su enlace oficial a congreso.es"),
      step("3", "Descubre tu podio", "Tus respuestas no salen de tu móvil"),
    ),
    footer("Lo que votaron, no lo que dicen."),
  );
}

const CARDS = {
  "01-lanzamiento": statement({
    eyebrow: "CORTES DISUELTAS · 6 OCT 2026",
    lines: ["La legislatura se ha cerrado.", "Ya no pueden cambiar", "lo que votaron."],
    sub: "Compara sus votos con lo que te prometan en campaña.",
  }),
  "02-como-funciona": steps(),
  "03-prometer-no-obliga": statement({
    eyebrow: "ART. 67.2 DE LA CONSTITUCIÓN",
    lines: ["Prometer no obliga.", "Votar queda registrado."],
    sub: "Un programa no es un contrato. Un voto nominal es un hecho.",
  }),
  "04-trasvase": question({
    eyebrow: "CONGRESO · AGUA",
    badge: "Se decidió por 1 voto",
    title: "Garantizar por ley el trasvase Tajo-Segura",
    totals: { yes: 170, no: 171, abstain: 4 },
    date: "Votación nominal, 13 de mayo de 2025",
    cta: "¿Sabes quién lo decidió? Te sorprenderá.",
  }),
  "05-banca": question({
    eyebrow: "CONGRESO · COSTE DE LA VIDA",
    title: "¿Quién votó NO a subir el impuesto a la gran banca?",
    totals: { yes: 41, no: 294, abstain: 7 },
    date: "Votación nominal, 9 de abril de 2024",
  }),
  "06-regularizacion": question({
    eyebrow: "CONGRESO · INMIGRACIÓN",
    title: "¿Quién apoyó tramitar la regularización de inmigrantes sin papeles?",
    totals: { yes: 310, no: 33 },
    date: "Votación nominal, 9 de abril de 2024",
  }),
  "07-jubilacion-activa": reveal({
    eyebrow: "CONGRESO · PENSIONES",
    title: "Cobrar parte de la pensión y seguir trabajando. Vox y Podemos votaron lo mismo.",
    groups: [
      ["Sí", TEAL, "PSOE · PP · Sumar · ERC · PNV · CC · UPN"],
      ["No", ACCENT, "Vox · Podemos · Junts · EH Bildu · BNG"],
    ],
    date: "Real Decreto-ley 11/2024 · votación nominal, 22 de enero de 2025 · 298 sí / 51 no",
  }),
  "08-saharauis": question({
    eyebrow: "CONGRESO · INMIGRACIÓN",
    title: "¿Quién votó NO a la nacionalidad para los saharauis nacidos bajo administración española?",
    totals: { yes: 195, no: 116, abstain: 33 },
    date: "Votación nominal, 25 de febrero de 2025",
  }),
  "09-jornada-35": question({
    eyebrow: "CONGRESO · EMPLEO",
    title: "¿Quién tumbó la jornada laboral de 35 horas?",
    totals: { yes: 162, no: 178, abstain: 6 },
    date: "Votación nominal, 14 de octubre de 2025",
  }),
  "10-lobo": question({
    eyebrow: "CONGRESO · CAMPO",
    title: "¿Qué partidos votaron con PP y Vox sobre el control del lobo?",
    totals: { yes: 180, no: 155, abstain: 7 },
    date: "Votación nominal, 23 de abril de 2024",
  }),
  "11-toros": question({
    eyebrow: "CONGRESO · CULTURA",
    title: "Quitar a los toros la protección como patrimonio cultural. ¿Quién se abstuvo?",
    totals: { yes: 57, no: 169, abstain: 118 },
    date: "Votación nominal, 7 de octubre de 2025",
  }),
  "12-educacion-especial": question({
    eyebrow: "CONGRESO · EDUCACIÓN",
    badge: "Se decidió por 7 votos",
    title: "¿Deben las familias poder elegir un centro de educación especial?",
    totals: { yes: 170, no: 177 },
    date: "Votación nominal, 9 de septiembre de 2025",
  }),
  "13-whatsapp-familia": statement({
    eyebrow: "ANTES DEL 29 DE NOVIEMBRE",
    lines: ["Antes de votar,", "10 preguntas.", "Después, comparad podios."],
    sub: "Para el grupo de la familia. Sin registro y sin guardar tus respuestas.",
  }),
  "14-dv-amnistia-psoe": dijeron({
    eyebrow: "AMNISTÍA · PSOE",
    rows: [
      ["DIJERON", TEAL, "Antes del 23-J de 2023: la amnistía no cabía en la Constitución."],
      ["VOTARON", ACCENT, "14 de marzo de 2024: sí. Aprobada por 178 a 172."],
      ["SU DEFENSA", MUTED, "Un «cambio de opinión» porque la situación en Cataluña había evolucionado."],
    ],
    source: "Votación nominal del Congreso, 14-03-2024 · hemeroteca: Maldita",
  }),
  "15-dv-regularizacion-pp": dijeron({
    eyebrow: "REGULARIZACIÓN · PP",
    rows: [
      ["VOTARON", ACCENT, "9 de abril de 2024: sus 136 diputados presentes, sí a tramitarla. 310 a 33."],
      ["DIJERON", TEAL, "En 2026, Feijóo critica la regularización y estudia recurrir el decreto."],
      ["SU DEFENSA", MUTED, "Su sí era a debatirla con condiciones: caso a caso y sin antecedentes penales."],
    ],
    source: "Votación nominal del Congreso, 09-04-2024 · hemeroteca: elDiario.es",
  }),
};

for (const [name, el] of Object.entries(CARDS)) {
  const res = new ImageResponse(el, { width: W, height: H });
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(path.join(OUT, `${name}.png`), buf);
  console.log(name, buf.length);
}
