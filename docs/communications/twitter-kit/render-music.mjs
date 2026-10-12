// Synthesizes an original, royalty-free soundtrack for the X video, synced to its timeline
// (countdown ticks, reveal "ding", groove drops during each countdown), and muxes it into the MP4.
// Usage (from the repo root, after render-video.mjs): node docs/communications/twitter-kit/render-music.mjs
import { spawnSync } from "node:child_process";
import { writeFileSync, renameSync, unlinkSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VIDEO = process.argv[2] || path.join(HERE, "video", "vota-con-la-chola-x.mp4");
const WAV = path.join(HERE, "video", "soundtrack.wav");

// Must match SCENES in render-video.mjs.
const INTRO = 5, PROMESA = 4.5, TITLE = 3, HOOK = 11, HOOKS = 4, CTA = 6;
const GAME_START = INTRO + PROMESA + TITLE;
const CTA_START = GAME_START + HOOK * HOOKS;
const TOTAL = CTA_START + CTA;
const COUNTDOWN_FROM = 3.4, REVEAL_AT = 6.2; // hook-local, as in render-video.mjs
const hookStarts = Array.from({ length: HOOKS }, (_, i) => GAME_START + i * HOOK);

const SR = 44100;
const N = Math.ceil(TOTAL * SR);
const L = new Float32Array(N);
const R = new Float32Array(N);

const BPM = 100;
const BEAT = 60 / BPM;
const BAR = BEAT * 4;
const midi = (m) => 440 * Math.pow(2, (m - 69) / 12);

// vi–IV–I–V in C: Am, F, C, G (one chord per bar).
const PROG = [
  { root: 45, tones: [57, 60, 64] },
  { root: 41, tones: [53, 57, 60] },
  { root: 48, tones: [55, 60, 64] },
  { root: 43, tones: [55, 59, 62] },
];
const chordAt = (t) => PROG[Math.floor(t / BAR) % PROG.length];

const inCountdown = (t) => hookStarts.some((s) => t >= s + COUNTDOWN_FROM && t < s + REVEAL_AT);
const grooveOn = (t) => t >= INTRO && !inCountdown(t) && t < TOTAL - 2.4;
const drumsOn = (t) => t >= GAME_START - 0.01 && !inCountdown(t) && t < TOTAL - 2.4;

let seed = 12345;
const noise = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32) * 2 - 1;

const osc = {
  sine: (p) => Math.sin(2 * Math.PI * p),
  tri: (p) => 1 - 4 * Math.abs(((p + 0.25) % 1) - 0.5),
  saw: (p) => 2 * (p % 1) - 1,
};

// Adds one voice with an ADSR-ish envelope, optional one-pole lowpass, pan and pitch glide.
function voice({ at, dur, freq, wave = "sine", gain = 0.2, attack = 0.005, release = 0.1, decay = null, pan = 0, cutoff = null, glideTo = null, noiseMix = 0 }) {
  const start = Math.floor(at * SR);
  const len = Math.floor((dur + release) * SR);
  const a = Math.max(1, attack * SR);
  const sustainEnd = dur * SR;
  const lp = cutoff ? 1 - Math.exp((-2 * Math.PI * cutoff) / SR) : 1;
  let y = 0, phase = 0;
  const gl = (1 - pan) / 2, gr = (1 + pan) / 2;
  for (let i = 0; i < len; i++) {
    const n = start + i;
    if (n < 0 || n >= N) continue;
    const f = glideTo ? freq * Math.pow(glideTo / freq, Math.min(1, i / len)) : freq;
    phase += f / SR;
    let env = i < a ? i / a : 1;
    if (decay) env *= Math.exp(-(i / SR) / decay);
    if (i > sustainEnd) env *= Math.max(0, 1 - (i - sustainEnd) / (release * SR));
    let s = (1 - noiseMix) * osc[wave](phase) + noiseMix * noise();
    y += lp * (s - y);
    const out = y * env * gain;
    L[n] += out * gl * 2;
    R[n] += out * gr * 2;
  }
}

// ---------- music ----------

const bars = Math.ceil(TOTAL / BAR);
for (let b = 0; b < bars; b++) {
  const t0 = b * BAR;
  const ch = PROG[b % PROG.length];
  // Pad: soft detuned triangles through a lowpass that opens once the game starts.
  const cutoff = t0 < GAME_START ? 900 : 1800;
  ch.tones.forEach((m, k) => {
    voice({ at: t0, dur: BAR, freq: midi(m), wave: "saw", gain: 0.035, attack: 0.4, release: 0.6, cutoff, pan: (k - 1) * 0.4 });
    voice({ at: t0, dur: BAR, freq: midi(m) * 1.004, wave: "tri", gain: 0.03, attack: 0.4, release: 0.6, pan: (1 - k) * 0.4 });
  });
}

// Arpeggio pluck on 8ths (whole video, quieter during intro).
for (let t = 0; t < TOTAL - 2.4; t += BEAT / 2) {
  const ch = chordAt(t);
  const step = Math.round(t / (BEAT / 2));
  const pattern = [0, 1, 2, 1, 0, 2, 1, 2];
  const note = ch.tones[pattern[step % 8]] + 12;
  const quiet = t < INTRO ? 0.6 : inCountdown(t) ? 0.35 : 1;
  voice({ at: t, dur: 0.05, freq: midi(note), wave: "tri", gain: 0.05 * quiet, decay: 0.18, release: 0.25, pan: step % 2 ? 0.35 : -0.35 });
}

// Bass: root on 1 and the "and" of 2, octave on 3.
for (let t = 0; t < TOTAL; t += BEAT / 2) {
  if (!grooveOn(t)) continue;
  const step = Math.round(t / (BEAT / 2)) % 8;
  if (![0, 3, 4, 6].includes(step)) continue;
  const root = chordAt(t).root - 12 + (step === 4 ? 12 : 0);
  voice({ at: t, dur: BEAT * 0.45, freq: midi(root), wave: "saw", gain: 0.11, attack: 0.004, release: 0.06, cutoff: 380 });
  voice({ at: t, dur: BEAT * 0.45, freq: midi(root), wave: "sine", gain: 0.12, attack: 0.004, release: 0.06 });
}

// Drums.
for (let t = 0; t < TOTAL; t += BEAT / 2) {
  const step = Math.round(t / (BEAT / 2)) % 8;
  if (step % 2 === 0 && grooveOn(t)) {
    const soft = t < GAME_START ? 0.5 : 1;
    voice({ at: t, dur: 0.02, freq: 150, glideTo: 45, wave: "sine", gain: 0.5 * soft, decay: 0.12, release: 0.2 }); // kick
  }
  if (!drumsOn(t)) continue;
  if (step % 2 === 1) voice({ at: t, dur: 0.01, freq: 1, noiseMix: 1, gain: 0.05, decay: 0.03, release: 0.05, pan: 0.2 }); // hat
  if (step === 2 || step === 6) voice({ at: t, dur: 0.02, freq: 190, noiseMix: 0.75, wave: "tri", gain: 0.16, decay: 0.09, release: 0.15, cutoff: 5000 }); // clap
}

// ---------- sound effects synced to the picture ----------

// Riser into the game.
voice({ at: GAME_START - 2.4, dur: 2.4, freq: 1, noiseMix: 1, gain: 0.07, attack: 2.3, release: 0.05, cutoff: 2500 });

for (const s of hookStarts) {
  // Tally bars filling: a short upward sweep.
  voice({ at: s + 1.4, dur: 1.2, freq: 220, glideTo: 880, wave: "tri", gain: 0.035, attack: 0.3, release: 0.2 });
  // Countdown ticks (4 over the countdown bar).
  for (let k = 0; k < 4; k++) {
    const at = s + COUNTDOWN_FROM + k * ((REVEAL_AT - COUNTDOWN_FROM) / 4);
    voice({ at, dur: 0.01, freq: k === 3 ? 1760 : 1320, wave: "sine", gain: 0.16, decay: 0.05, release: 0.08 });
  }
  // Reveal: bell chord + cymbal.
  [76, 79, 84].forEach((m, k) => voice({ at: s + REVEAL_AT, dur: 0.05, freq: midi(m), wave: "sine", gain: 0.09, decay: 0.7, release: 1.2, pan: (k - 1) * 0.5 }));
  voice({ at: s + REVEAL_AT, dur: 0.05, freq: 1, noiseMix: 1, gain: 0.08, decay: 0.6, release: 0.8 });
}

// Final resolving chord (C major) under the CTA tail.
[48, 55, 60, 64, 67].forEach((m, k) =>
  voice({ at: TOTAL - 2.4, dur: 1.4, freq: midi(m), wave: "tri", gain: 0.06, attack: 0.05, release: 1.0, pan: (k - 2) * 0.2 }),
);

// ---------- master: fades, soft clip, normalise, 16-bit WAV ----------

let peak = 0;
for (let n = 0; n < N; n++) {
  const t = n / SR;
  const fade = Math.min(1, t / 0.05, (TOTAL - t) / 1.0);
  L[n] = Math.tanh(L[n] * 1.2) * fade;
  R[n] = Math.tanh(R[n] * 1.2) * fade;
  peak = Math.max(peak, Math.abs(L[n]), Math.abs(R[n]));
}
const norm = peak > 0 ? 0.89 / peak : 1;
const data = Buffer.alloc(N * 4);
for (let n = 0; n < N; n++) {
  data.writeInt16LE(Math.round(L[n] * norm * 32767), n * 4);
  data.writeInt16LE(Math.round(R[n] * norm * 32767), n * 4 + 2);
}
const header = Buffer.alloc(44);
header.write("RIFF", 0); header.writeUInt32LE(36 + data.length, 4); header.write("WAVE", 8);
header.write("fmt ", 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(2, 22);
header.writeUInt32LE(SR, 24); header.writeUInt32LE(SR * 4, 28); header.writeUInt16LE(4, 32); header.writeUInt16LE(16, 34);
header.write("data", 36); header.writeUInt32LE(data.length, 40);
writeFileSync(WAV, Buffer.concat([header, data]));

// Replace the video's (silent) audio track with the soundtrack, without re-encoding the picture.
const tmp = VIDEO.replace(/\.mp4$/u, ".tmp.mp4");
const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", VIDEO, "-i", WAV, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp], { stdio: "inherit" });
if (r.status !== 0) throw new Error("ffmpeg mux failed");
renameSync(tmp, VIDEO);
unlinkSync(WAV);
console.log(`OK ${VIDEO} (${TOTAL}s soundtrack)`);
