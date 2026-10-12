// Renders the landscape Twitter/X video (1920x1080, 30 fps, ~57 s) frame by frame with next/og and encodes it with ffmpeg.
// Usage (from the repo root): node docs/communications/twitter-kit/render-video.mjs
// Figures are copied by hand from ui/site/out/citizen/data/voting_aid_generales_v1.json; re-check them if the snapshot changes.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(HERE, "../../../ui/site/package.json"));
const { ImageResponse } = require("next/og");
const React = require("react");
const h = React.createElement;

const OUT_DIR = path.join(HERE, "video");
const OUT = process.argv[2] || path.join(OUT_DIR, "vota-con-la-chola-x.mp4");
const W = 1920;
const H = 1080;
const FPS = 30;

const INK = "#17191f";
const PAPER = "#f7f8f4";
const ACCENT = "#d84a32";
const TEAL = "#0f766e";
const MUTED = "#5b616e";
const GREY = "#b9bdc6";
const ACCENT_ON_INK = "#ff8a73";
const TEAL_ON_INK = "#5fd0c4";

const row = (style, ...kids) => h("div", { style: { display: "flex", ...style } }, ...kids);
const col = (style, ...kids) => h("div", { style: { display: "flex", flexDirection: "column", ...style } }, ...kids);
const span = (style, text) => h("span", { style }, text);

const clamp = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
// Fade + slide-up for an element that appears at `start` (seconds, scene-local).
const enter = (t, start, dur = 0.5) => {
  const p = ease((t - start) / dur);
  return { opacity: p, transform: `translateY(${(1 - p) * 24}px)` };
};

// ---------- scenes ----------

function darkScene(t, { eyebrow, lines, sub }) {
  return col(
    { width: "100%", height: "100%", background: INK, color: PAPER, padding: "90px 110px" },
    span({ fontSize: 38, color: TEAL_ON_INK, letterSpacing: 2, ...enter(t, lines[0][1] < 0 ? -1 : 0) }, eyebrow),
    col(
      { flex: 1, justifyContent: "center" },
      ...lines.map(([text, at], i) =>
        span({ fontSize: 112, lineHeight: 1.12, color: i === lines.length - 1 ? ACCENT_ON_INK : PAPER, ...enter(t, at, 0.6) }, text),
      ),
    ),
    sub ? span({ fontSize: 44, color: PAPER, ...enter(t, sub[1]) }, sub[0]) : null,
  );
}

function titleScene(t) {
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "90px 110px", justifyContent: "center" },
    span({ fontSize: 40, color: TEAL, letterSpacing: 2, ...enter(t, 0) }, "4 VOTACIONES NOMINALES REALES DEL CONGRESO"),
    span({ fontSize: 150, marginTop: 20, ...enter(t, 0.25, 0.6) }, "Adivina quién votó."),
    span({ fontSize: 50, color: MUTED, marginTop: 24, ...enter(t, 0.9) }, "Piénsalo antes de ver la respuesta."),
  );
}

function tally(t, totals, start) {
  const p = ease((t - start) / 1.4);
  const total = totals.yes + totals.no + (totals.abstain || 0);
  const parts = [
    ["sí", totals.yes, TEAL],
    ["no", totals.no, ACCENT],
    ...(totals.abstain ? [[totals.abstain === 1 ? "abstención" : "abstenciones", totals.abstain, MUTED]] : []),
  ];
  return col(
    { marginTop: 40, opacity: clamp((t - start) / 0.3) },
    row(
      { alignItems: "baseline" },
      ...parts.map(([word, n, color]) => span({ fontSize: 54, color, marginRight: 56 }, `${Math.round(n * p)} ${word}`)),
    ),
    row(
      { marginTop: 16, width: "100%", height: 40, borderRadius: 8, overflow: "hidden", background: "#e6e8e1" },
      ...parts.map(([, n, color]) => h("div", { style: { display: "flex", width: `${(n / total) * 100 * p}%`, height: 40, background: color === MUTED ? GREY : color } })),
    ),
  );
}

const REVEAL_AT = 6.2;

function hookScene(t, hook, index, count) {
  const revealing = t >= REVEAL_AT;
  // Countdown bar between the prompt and the reveal.
  const countdown = 1 - clamp((t - 3.4) / (REVEAL_AT - 3.4));
  return col(
    { width: "100%", height: "100%", background: PAPER, color: INK, padding: "80px 110px" },
    row(
      { justifyContent: "space-between", alignItems: "center", fontSize: 36, color: TEAL, letterSpacing: 2, ...enter(t, 0) },
      span({}, `${hook.eyebrow} · ${hook.date.toUpperCase()}`),
      hook.badge ? span({ background: ACCENT, color: "white", padding: "10px 28px", borderRadius: 999, fontSize: 36, letterSpacing: 0 }, hook.badge) : span({ color: MUTED }, `${index + 1} / ${count}`),
    ),
    // Explicit lines so compound names (Tajo-Segura) never break at the hyphen.
    col({ marginTop: 50, ...enter(t, 0.2, 0.6) }, ...[].concat(hook.question).map((line) => span({ fontSize: 88, lineHeight: 1.14 }, line))),
    tally(t, hook.totals, 1.4),
    col(
      { flex: 1, justifyContent: "flex-end" },
      revealing
        ? col(
            {},
            ...hook.reveal.map(([word, color, parties], i) =>
              row(
                { alignItems: "flex-start", marginTop: 18, ...enter(t, REVEAL_AT + i * 0.35, 0.4) },
                span({ fontSize: 46, color, width: 310 }, word),
                span({ fontSize: 46, flex: 1 }, parties),
              ),
            ),
            span({ fontSize: 40, color: ACCENT, marginTop: 30, ...enter(t, REVEAL_AT + hook.reveal.length * 0.35 + 0.2) }, hook.note),
          )
        : col(
            { ...enter(t, 3.2) },
            span({ fontSize: 68 }, hook.prompt),
            row({ marginTop: 22, height: 12, width: `${countdown * 100}%`, background: ACCENT, borderRadius: 6 }),
          ),
    ),
  );
}

function ctaScene(t) {
  return col(
    { width: "100%", height: "100%", background: INK, color: PAPER, padding: "90px 110px", justifyContent: "center" },
    span({ fontSize: 120, ...enter(t, 0, 0.6) }, "¿Con quién coincides tú?"),
    span({ fontSize: 50, color: PAPER, marginTop: 30, ...enter(t, 0.6) }, "Responde a lo que de verdad se votó y mira tu podio."),
    span({ fontSize: 76, color: ACCENT_ON_INK, marginTop: 70, ...enter(t, 1.2) }, "votaconlachola.org"),
    span({ fontSize: 40, color: TEAL_ON_INK, marginTop: 24, ...enter(t, 1.7) }, "2 minutos · sin registro · cada voto con su enlace oficial"),
  );
}

// ---------- content (neutral by design: one surprise per bloc plus two cross-bloc ones) ----------

const HOOKS = [
  {
    eyebrow: "AGUA",
    date: "13 de mayo de 2025",
    badge: "Se decidió por 1 voto",
    question: ["¿Garantizar por ley el trasvase", "Tajo-Segura?"],
    totals: { yes: 170, no: 171, abstain: 4 },
    prompt: "¿Quién lo decidió?",
    reveal: [
      ["Sí", TEAL, "PP · Vox · UPN"],
      ["No", ACCENT, "PSOE · Sumar · ERC · Junts · EH Bildu · PNV · BNG · CC"],
      ["Abstención", MUTED, "Podemos"],
    ],
    note: "Con los 4 votos de Podemos a favor, habría salido por 174 a 171.",
  },
  {
    eyebrow: "COSTE DE LA VIDA",
    date: "9 de abril de 2024",
    question: "¿Subir el impuesto a los beneficios extraordinarios de la gran banca?",
    totals: { yes: 41, no: 294, abstain: 7 },
    prompt: "¿Quién votó que no?",
    reveal: [
      ["Sí", TEAL, "Sumar · Podemos · ERC · EH Bildu · BNG"],
      ["No", ACCENT, "PSOE · PP · Vox · PNV · CC · UPN"],
      ["Abstención", MUTED, "Junts"],
    ],
    note: "Se votaba una proposición concreta del Grupo Mixto.",
  },
  {
    eyebrow: "INMIGRACIÓN",
    date: "9 de abril de 2024",
    question: ["¿Tramitar la regularización de los", "inmigrantes sin papeles?"],
    totals: { yes: 310, no: 33 },
    prompt: "¿Quién votó que sí?",
    reveal: [
      ["Sí", TEAL, "PSOE · PP · Sumar · Podemos · ERC · Junts · EH Bildu · PNV · BNG · CC · UPN"],
      ["No", ACCENT, "Vox"],
    ],
    note: "Era la toma en consideración: empezar a debatirla, no la ley final.",
  },
  {
    eyebrow: "PENSIONES",
    date: "22 de enero de 2025",
    question: "¿Poder cobrar parte de la pensión y seguir trabajando?",
    totals: { yes: 298, no: 51 },
    prompt: "¿Quién votó que no?",
    reveal: [
      ["Sí", TEAL, "PSOE · PP · Sumar · ERC · PNV · CC · UPN"],
      ["No", ACCENT, "Vox · Podemos · Junts · EH Bildu · BNG"],
    ],
    note: "Vox y Podemos votaron lo mismo.",
  },
];

const HOOK_SECONDS = 11;
const SCENES = [
  [5, (t) => darkScene(t, {
    eyebrow: "CORTES DISUELTAS · 6 OCT 2026",
    lines: [["La legislatura se ha cerrado.", -1], ["Ya no pueden cambiar", 1.4], ["lo que votaron.", 2.3]],
  })],
  [4.5, (t) => darkScene(t, {
    eyebrow: "ARTÍCULO 67.2 DE LA CONSTITUCIÓN",
    lines: [["Prometer no obliga.", 0.2], ["Votar queda registrado.", 1.3]],
    sub: ["Un programa es una promesa. Un voto nominal es un hecho.", 2.4],
  })],
  [3, titleScene],
  ...HOOKS.map((hook, i) => [HOOK_SECONDS, (t) => hookScene(t, hook, i, HOOKS.length)]),
  [6, ctaScene],
];

// ---------- render ----------

const FADE = 0.35; // fade-through-colour between scenes
const totalSeconds = SCENES.reduce((s, [d]) => s + d, 0);
const totalFrames = Math.round(totalSeconds * FPS);

function frameAt(i) {
  let t = i / FPS;
  for (const [k, [dur, render]] of SCENES.entries()) {
    if (t < dur) {
      const fadeOut = clamp((t - (dur - FADE)) / FADE);
      const fadeIn = k === 0 ? 1 : clamp(t / FADE);
      const opacity = Math.min(fadeIn, 1 - fadeOut);
      return h("div", { style: { display: "flex", width: "100%", height: "100%", background: "#000" } },
        h("div", { style: { display: "flex", width: "100%", height: "100%", opacity } }, render(t)));
    }
    t -= dur;
  }
  return null;
}

mkdirSync(path.dirname(OUT), { recursive: true });
const ffmpeg = spawn("ffmpeg", [
  "-y", "-loglevel", "error",
  "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
  "-shortest",
  "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
  "-c:a", "aac", "-b:a", "128k",
  "-movflags", "+faststart",
  OUT,
], { stdio: ["pipe", "inherit", "inherit"] });

const cache = new Map(); // identical frames (holds) are rendered once
for (let i = 0; i < totalFrames; i++) {
  const el = frameAt(i);
  const key = JSON.stringify(el);
  let buf = cache.get(key);
  if (!buf) {
    buf = Buffer.from(await new ImageResponse(el, { width: W, height: H }).arrayBuffer());
    if (cache.size > 200) cache.clear();
    cache.set(key, buf);
  }
  if (!ffmpeg.stdin.write(buf)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
  if (i % (FPS * 5) === 0) process.stdout.write(`${(i / FPS).toFixed(0)}s / ${totalSeconds}s\n`);
}
ffmpeg.stdin.end();
await new Promise((r, j) => ffmpeg.on("close", (c) => (c === 0 ? r() : j(new Error(`ffmpeg exit ${c}`)))));
console.log(`OK ${OUT} (${totalSeconds}s, ${totalFrames} frames)`);
