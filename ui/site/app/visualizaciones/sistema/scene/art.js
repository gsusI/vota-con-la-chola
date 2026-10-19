// Flat SVG illustrations for /visualizaciones/sistema/: people, the public purse, firms, shops, lenders, the debt pile
// and the policy icons. Pure presentational components (no state), drawn around their own origin so the scene can
// place them anywhere. Colours come from the page palette.

export const PAL = {
  ink: "#17191f",
  ink2: "#52514e",
  muted: "#8b8a83",
  line: "#d9d7cf",
  paper: "#fbfaf6",
  blue: "#2a78d6",
  blueSoft: "#dbe8f8",
  orange: "#eb6834",
  orangeSoft: "#fde4d8",
  green: "#1baf7a",
  greenSoft: "#d6f2e6",
  yellow: "#eda100",
  yellowSoft: "#fdf0cf",
  purple: "#7a5af5",
  purpleSoft: "#e9e3fe",
  red: "#d64545",
  skin: ["#f2c7a5", "#d9a27c", "#a8714f", "#f5d3b8"],
  hair: { dark: "#3b2a20", brown: "#8a5a3b", grey: "#c9c4bc", black: "#1d1d1f", blond: "#d9b25f" },
};

// ---------------------------------------------------------------- crowd figure (origin = feet)
export function Figure({ x = 0, y = 0, s = 1, shirt = PAL.blue, skin = PAL.skin[0], hair = PAL.hair.dark, old = false, faded = false, highlight }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} opacity={faded ? 0.28 : 1}>
      {highlight ? <circle cx="0" cy="-20" r="16" fill={highlight} opacity="0.25" /> : null}
      <rect x="-4.5" y="-12" width="3.6" height="12" rx="1.6" fill={PAL.ink2} />
      <rect x="0.9" y="-12" width="3.6" height="12" rx="1.6" fill={PAL.ink2} />
      <path d="M-7 -11 L-7 -23 Q-7 -29 0 -29 Q7 -29 7 -23 L7 -11 Z" fill={shirt} />
      <circle cx="0" cy="-34" r="5.2" fill={skin} />
      <path d={old ? "M-5.4 -35 Q-5 -40.5 0 -40.6 Q5 -40.5 5.4 -35 Q3 -38 0 -38 Q-3 -38 -5.4 -35 Z" : "M-5.4 -34 Q-5.6 -40.8 0 -40.8 Q5.6 -40.8 5.4 -34 Q2 -37.4 -5.4 -34 Z"} fill={old ? PAL.hair.grey : hair} />
      {old ? <path d="M8.5 -21 Q11 -21 11 -18.5 L10.4 0" stroke={PAL.ink2} strokeWidth="1.6" fill="none" strokeLinecap="round" /> : null}
    </g>
  );
}

// ---------------------------------------------------------------- portrait (origin = centre), for the neighbours
const MOUTH = {
  up: "M-9 9 Q0 17 9 9",
  flat: "M-7 11 L7 11",
  down: "M-9 14 Q0 6 9 14",
};

function Face({ mood, glasses }) {
  return (
    <g>
      <circle cx="-8" cy="-2" r="2.3" fill={PAL.ink} />
      <circle cx="8" cy="-2" r="2.3" fill={PAL.ink} />
      {glasses ? (
        <g fill="none" stroke={PAL.ink2} strokeWidth="1.6">
          <circle cx="-8" cy="-2" r="6" />
          <circle cx="8" cy="-2" r="6" />
          <path d="M-2 -2 L2 -2" />
        </g>
      ) : null}
      <circle cx="-14" cy="7" r="3.2" fill="#f19a8f" opacity="0.35" />
      <circle cx="14" cy="7" r="3.2" fill="#f19a8f" opacity="0.35" />
      <path d={MOUTH[mood] || MOUTH.flat} stroke={PAL.ink} strokeWidth="2.4" fill="none" strokeLinecap="round" />
    </g>
  );
}

function Head({ x = 0, y = 0, s = 1, skin, hair, style, mood, glasses }) {
  const hairBack = {
    long: <path d="M-27 -6 Q-30 -36 0 -38 Q30 -36 27 -6 L28 26 Q14 30 0 28 Q-14 30 -28 26 Z" fill={hair} />,
    bob: <path d="M-26 -4 Q-28 -34 0 -36 Q28 -34 26 -4 L26 14 Q0 20 -26 14 Z" fill={hair} />,
    bun: <circle cx="0" cy="-36" r="11" fill={hair} />,
    short: null,
    kid: null,
  }[style];
  const hairFront = {
    long: <path d="M-23 -10 Q-18 -32 4 -30 Q20 -28 23 -10 Q10 -22 -8 -18 Q-16 -16 -23 -10 Z" fill={hair} />,
    bob: <path d="M-24 -6 Q-22 -32 2 -31 Q22 -30 24 -6 Q12 -20 -4 -20 Q-16 -19 -24 -6 Z" fill={hair} />,
    bun: <path d="M-23 -8 Q-20 -30 0 -30 Q20 -30 23 -8 Q12 -20 0 -20 Q-12 -20 -23 -8 Z" fill={hair} />,
    short: <path d="M-23 -6 Q-24 -32 0 -32 Q24 -32 23 -6 Q18 -20 0 -21 Q-16 -21 -23 -6 Z" fill={hair} />,
    kid: <path d="M-21 -6 Q-21 -28 0 -28 Q21 -28 21 -6 Q10 -16 -2 -16 Q-14 -15 -21 -6 Z" fill={hair} />,
  }[style];
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      {hairBack}
      <ellipse cx="0" cy="0" rx="22" ry="25" fill={skin} />
      <ellipse cx="-22" cy="2" rx="3.5" ry="5" fill={skin} />
      <ellipse cx="22" cy="2" rx="3.5" ry="5" fill={skin} />
      {hairFront}
      <Face mood={mood} glasses={glasses} />
    </g>
  );
}

function Shoulders({ x = 0, y = 0, s = 1, color, collar }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-40 40 Q-40 8 -14 4 L14 4 Q40 8 40 40 Z" fill={color} />
      {collar === "blazer" ? (
        <g>
          <path d="M-8 4 L0 20 L8 4 Z" fill="#fff" />
          <path d="M-14 4 L-2 26 L-6 40 M14 4 L2 26 L6 40" stroke="#00000033" strokeWidth="2" fill="none" />
        </g>
      ) : collar === "cardigan" ? (
        <path d="M0 6 L0 40" stroke="#00000030" strokeWidth="2" />
      ) : (
        <path d="M-10 4 Q0 14 10 4" fill="none" stroke="#00000030" strokeWidth="2" />
      )}
    </g>
  );
}

/** Portrait of one of the typical cases. mood: up | flat | down. */
export function Avatar({ who, mood = "flat", size = 120 }) {
  const ring = mood === "up" ? PAL.greenSoft : mood === "down" ? PAL.orangeSoft : "#efeee9";
  const people = {
    p1: (
      <g>
        <Shoulders y="18" color={PAL.orange} />
        <Head y="-4" skin={PAL.skin[0]} hair={PAL.hair.brown} style="long" mood={mood} />
      </g>
    ),
    p2: (
      <g>
        <Shoulders x="-18" y="18" s="0.8" color={PAL.blue} />
        <Head x="-18" y="-2" s="0.8" skin={PAL.skin[1]} hair={PAL.hair.dark} style="short" mood={mood} />
        <Shoulders x="18" y="18" s="0.8" color={PAL.yellow} />
        <Head x="18" y="-2" s="0.8" skin={PAL.skin[1]} hair={PAL.hair.black} style="bob" mood={mood} />
        <Shoulders x="-30" y="40" s="0.45" color={PAL.green} />
        <Head x="-30" y="28" s="0.45" skin={PAL.skin[1]} hair={PAL.hair.dark} style="kid" mood={mood} />
        <Shoulders x="30" y="40" s="0.45" color={PAL.purple} />
        <Head x="30" y="28" s="0.45" skin={PAL.skin[1]} hair={PAL.hair.black} style="kid" mood={mood} />
      </g>
    ),
    p4: (
      <g>
        <Shoulders y="18" color={PAL.purple} collar="cardigan" />
        <Head y="-4" skin={PAL.skin[3]} hair={PAL.hair.grey} style="bun" mood={mood} glasses />
      </g>
    ),
    p5: (
      <g>
        <Shoulders y="18" color={PAL.ink2} collar="blazer" />
        <Head y="-4" skin={PAL.skin[2]} hair={PAL.hair.dark} style="bob" mood={mood} />
      </g>
    ),
  };
  return (
    <svg viewBox="-60 -60 120 120" width={size} height={size} role="img" aria-hidden="true">
      <defs>
        <clipPath id={`clip-${who}`}>
          <circle cx="0" cy="0" r="56" />
        </clipPath>
      </defs>
      <circle cx="0" cy="0" r="56" fill={ring} />
      <g clipPath={`url(#clip-${who})`}>{people[who]}</g>
    </svg>
  );
}

// ---------------------------------------------------------------- places (origin = bottom centre)
export function PiggyBank({ x = 0, y = 0, s = 1, label = "Caja pública", sub }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="4" rx="96" ry="10" fill="#00000012" />
      <rect x="-62" y="-26" width="20" height="30" rx="8" fill="#9cc0ec" />
      <rect x="40" y="-26" width="20" height="30" rx="8" fill="#9cc0ec" />
      <path d="M92 -86 q16 -4 12 10 q-4 10 -14 2" fill="none" stroke="#9cc0ec" strokeWidth="5" strokeLinecap="round" />
      <ellipse cx="0" cy="-82" rx="100" ry="66" fill={PAL.blueSoft} stroke={PAL.blue} strokeWidth="3" />
      <path d="M-58 -138 L-38 -170 L-22 -136 Z" fill="#9cc0ec" stroke={PAL.blue} strokeWidth="3" strokeLinejoin="round" />
      <ellipse cx="-104" cy="-78" rx="22" ry="18" fill="#9cc0ec" stroke={PAL.blue} strokeWidth="3" />
      <ellipse cx="-110" cy="-78" rx="3.4" ry="5" fill={PAL.blue} />
      <ellipse cx="-98" cy="-78" rx="3.4" ry="5" fill={PAL.blue} />
      <circle cx="-62" cy="-100" r="6" fill={PAL.ink} />
      <rect x="-28" y="-150" width="56" height="9" rx="4.5" fill={PAL.blue} />
      <text x="0" y="-80" textAnchor="middle" className="art__piggyLabel">{label}</text>
      {sub ? <text x="0" y="-58" textAnchor="middle" className="art__piggySub">{sub}</text> : null}
    </g>
  );
}

export function Factory({ x = 0, y = 0, s = 1 }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="2" rx="70" ry="6" fill="#00000012" />
      <rect x="34" y="-118" width="16" height="70" fill={PAL.ink2} />
      <g className="art__smoke" fill="#cfcdc4">
        <circle cx="42" cy="-128" r="9" />
        <circle cx="54" cy="-142" r="11" />
        <circle cx="70" cy="-156" r="12" />
      </g>
      <path d="M-62 0 L-62 -60 L-38 -78 L-38 -60 L-14 -78 L-14 -60 L10 -78 L10 -60 L62 -60 L62 0 Z" fill={PAL.purpleSoft} stroke={PAL.purple} strokeWidth="3" strokeLinejoin="round" />
      {[-48, -24, 0, 24, 44].map((wx) => (
        <rect key={wx} x={wx} y="-46" width="12" height="14" rx="2" fill="#fff" stroke={PAL.purple} strokeWidth="2" />
      ))}
      <rect x="-10" y="-26" width="20" height="26" rx="2" fill={PAL.purple} />
    </g>
  );
}

export function Shop({ x = 0, y = 0, s = 1 }) {
  const stripes = [-60, -40, -20, 0, 20, 40];
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="2" rx="68" ry="6" fill="#00000012" />
      <rect x="-56" y="-70" width="112" height="70" fill="#fff" stroke={PAL.orange} strokeWidth="3" />
      {stripes.map((sx, i) => (
        <path key={sx} d={`M${sx} -96 L${sx + 20} -96 L${sx + 20} -76 Q${sx + 10} -66 ${sx} -76 Z`} fill={i % 2 ? "#fff" : PAL.orange} stroke={PAL.orange} strokeWidth="2" />
      ))}
      <rect x="-62" y="-100" width="124" height="8" rx="3" fill={PAL.orange} />
      <rect x="10" y="-50" width="26" height="50" rx="2" fill={PAL.orangeSoft} stroke={PAL.orange} strokeWidth="2" />
      <g transform="translate(-24 -26)" stroke={PAL.ink2} strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M-16 -16 L-10 -16 L-4 4 L14 4 L18 -10 L-8 -10" />
        <circle cx="-2" cy="11" r="2.6" fill={PAL.ink2} />
        <circle cx="12" cy="11" r="2.6" fill={PAL.ink2} />
      </g>
    </g>
  );
}

export function Bank({ x = 0, y = 0, s = 1 }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="2" rx="60" ry="5" fill="#00000012" />
      <path d="M-54 -70 L0 -100 L54 -70 Z" fill={PAL.yellowSoft} stroke={PAL.yellow} strokeWidth="3" strokeLinejoin="round" />
      <text x="0" y="-76" textAnchor="middle" className="art__bankSign">%</text>
      <rect x="-50" y="-70" width="100" height="8" fill={PAL.yellow} />
      {[-38, -14, 10, 34].map((cx) => (
        <rect key={cx} x={cx - 4} y="-62" width="8" height="52" fill="#fff" stroke={PAL.yellow} strokeWidth="2" />
      ))}
      <rect x="-56" y="-10" width="112" height="10" fill={PAL.yellow} />
    </g>
  );
}

export function Services({ x = 0, y = 0, s = 1 }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="2" rx="70" ry="6" fill="#00000012" />
      <rect x="-64" y="-64" width="58" height="64" fill="#fff" stroke={PAL.green} strokeWidth="3" />
      <rect x="-42" y="-54" width="14" height="30" fill={PAL.green} />
      <rect x="-50" y="-46" width="30" height="14" fill={PAL.green} />
      <path d="M2 -52 L32 -76 L62 -52 Z" fill={PAL.greenSoft} stroke={PAL.green} strokeWidth="3" strokeLinejoin="round" />
      <rect x="6" y="-52" width="52" height="52" fill="#fff" stroke={PAL.green} strokeWidth="3" />
      <rect x="22" y="-30" width="20" height="30" fill={PAL.greenSoft} stroke={PAL.green} strokeWidth="2" />
      <circle cx="32" cy="-62" r="5" fill="#fff" stroke={PAL.green} strokeWidth="2" />
    </g>
  );
}

/** Stack of coins, one per `unit` of value; the outline marks the baseline. Origin = bottom centre. */
export function CoinStack({ x = 0, y = 0, value, base, unit = 10, label, sub }) {
  const coin = 11;
  const n = value / unit;
  const nb = base / unit;
  const full = Math.floor(n);
  const coins = [];
  for (let i = 0; i < Math.ceil(n); i += 1) {
    const frac = i < full ? 1 : n - full;
    coins.push(
      <g key={i} transform={`translate(0 ${-i * coin})`} opacity={frac < 1 ? 0.5 + frac / 2 : 1}>
        <ellipse cx="0" cy="-2" rx="34" ry="9" fill="#c98500" />
        <rect x="-34" y={-coin} width="68" height={coin - 2} fill={PAL.yellow} />
        <ellipse cx="0" cy={-coin} rx="34" ry="9" fill="#ffd36b" stroke="#c98500" strokeWidth="1.5" />
      </g>,
    );
  }
  return (
    <g transform={`translate(${x} ${y})`}>
      <ellipse cx="0" cy="2" rx="46" ry="8" fill="#00000014" />
      {coins}
      {Math.abs(nb - n) > 0.05 ? (
        <g>
          <path d={`M-44 ${-nb * coin - 9} L44 ${-nb * coin - 9}`} stroke={PAL.ink2} strokeWidth="2" strokeDasharray="5 4" />
          <text x="48" y={-nb * coin - 5} className="art__tiny">ley actual</text>
        </g>
      ) : null}
      {label ? <text x="0" y="26" textAnchor="middle" className="art__label">{label}</text> : null}
      {sub ? <text x="0" y="44" textAnchor="middle" className="art__sub">{sub}</text> : null}
    </g>
  );
}

// ---------------------------------------------------------------- icons for the controls (24 x 24 grid)
const ICONS = {
  pension: (
    <g>
      <circle cx="10" cy="5" r="3" />
      <path d="M10 9 Q6 9 6 13 L6 20 M10 9 Q14 9 14 13 L14 20 M6 14 L14 14" />
      <path d="M17 11 Q19.5 11 19.5 13.5 L19 21" />
    </g>
  ),
  age: (
    <g>
      <path d="M6 3 L18 3 M6 21 L18 21 M7 3 Q7 9 12 12 Q17 9 17 3 M7 21 Q7 15 12 12 Q17 15 17 21" />
      <path d="M9.5 19 L14.5 19" />
    </g>
  ),
  payroll: (
    <g>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 8 L16 8 M8 12 L16 12 M8 16 L12 16" />
    </g>
  ),
  irpf: (
    <g>
      <path d="M6 3 L15 3 L19 7 L19 21 L6 21 Z" />
      <path d="M15 3 L15 7 L19 7" />
      <path d="M9 17 L16 11" />
      <circle cx="9.5" cy="11.5" r="1.3" />
      <circle cx="15.5" cy="16.5" r="1.3" />
    </g>
  ),
  top: (
    <g>
      <path d="M4 20 L8 14 L12 16 L16 9 L20 5" />
      <path d="M15 5 L20 5 L20 10" />
    </g>
  ),
  cart: (
    <g>
      <path d="M3 4 L6 4 L8.5 15 L18 15 L20 8 L7 8" />
      <circle cx="10" cy="19" r="1.5" />
      <circle cx="17" cy="19" r="1.5" />
    </g>
  ),
  bread: (
    <g>
      <path d="M5 12 Q5 6 12 6 Q19 6 19 12 L19 19 L5 19 Z" />
      <path d="M9 9 L10 12 M12 8.5 L13 11.5 M15 9 L16 12" />
    </g>
  ),
  factory: (
    <g>
      <path d="M3 20 L3 11 L8 8 L8 11 L13 8 L13 11 L21 11 L21 20 Z" />
      <path d="M17 11 L17 4 L20 4 L20 11" />
    </g>
  ),
  debt: (
    <g>
      <ellipse cx="12" cy="6" rx="7" ry="2.5" />
      <path d="M5 6 L5 10 Q12 13 19 10 L19 6 M5 10 L5 14 Q12 17 19 14 L19 10 M5 14 L5 18 Q12 21 19 18 L19 14" />
    </g>
  ),
  people: (
    <g>
      <circle cx="8" cy="7" r="2.6" />
      <circle cx="16" cy="7" r="2.6" />
      <path d="M3 20 Q3 12 8 12 Q13 12 13 20 M11 20 Q11 12 16 12 Q21 12 21 20" />
    </g>
  ),
  rate: (
    <g>
      <circle cx="7" cy="7" r="2.4" />
      <circle cx="17" cy="17" r="2.4" />
      <path d="M18 5 L6 19" />
    </g>
  ),
  building: (
    <g>
      <rect x="5" y="4" width="10" height="17" />
      <path d="M15 9 L20 9 L20 21 L3 21" />
      <path d="M8 8 L8 8.5 M12 8 L12 8.5 M8 12 L8 12.5 M12 12 L12 12.5 M8 16 L8 16.5 M12 16 L12 16.5" />
    </g>
  ),
  land: (
    <g>
      <path d="M3 18 L8 9 L12 14 L15 11 L21 18 Z" />
      <path d="M12 4 L12 8 M10 6 L14 6" />
    </g>
  ),
  suitcase: (
    <g>
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M9 8 L9 5 L15 5 L15 8 M8 20 L8 21 M16 20 L16 21" />
    </g>
  ),
  key: (
    <g>
      <circle cx="8" cy="12" r="4" />
      <path d="M12 12 L21 12 M18 12 L18 15 M15 12 L15 14" />
    </g>
  ),
  cap: (
    <g>
      <path d="M4 11 L12 4 L20 11 L20 20 L4 20 Z" />
      <path d="M12 9 L12 16 M9 13 L12 16 L15 13" />
    </g>
  ),
  mortgage: (
    <g>
      <path d="M4 11 L12 4 L20 11 L20 20 L4 20 Z" />
      <path d="M9.5 17 L14.5 11" />
      <circle cx="10" cy="12" r="1.2" />
      <circle cx="14" cy="16" r="1.2" />
    </g>
  ),
};

export function Icon({ name, size = 28, color = "currentColor", strokeWidth = 1.8 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

/** Apartment blocks with a crane: the housing market. Origin = bottom centre. */
export function Housing({ x = 0, y = 0, s = 1 }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx="0" cy="2" rx="80" ry="6" fill="#00000012" />
      <path d="M44 -150 L44 0 M44 -150 L104 -150 M44 -136 L96 -150 M52 -150 L52 -0" stroke={PAL.yellow} strokeWidth="3" fill="none" />
      <path d="M96 -150 L96 -112" stroke={PAL.ink2} strokeWidth="1.5" />
      <rect x="88" y="-112" width="16" height="10" fill={PAL.orange} />
      <rect x="-70" y="-96" width="50" height="96" fill="#fff" stroke={PAL.blue} strokeWidth="3" />
      <rect x="-14" y="-124" width="56" height="124" fill={PAL.blueSoft} stroke={PAL.blue} strokeWidth="3" />
      {[-62, -46, -30].map((wx) => [-84, -64, -44, -24].map((wy) => <rect key={`${wx}${wy}`} x={wx} y={wy} width="8" height="10" fill={PAL.blue} opacity="0.35" />))}
      {[-6, 10, 26].map((wx) => [-112, -92, -72, -52, -32].map((wy) => <rect key={`${wx}${wy}`} x={wx} y={wy} width="9" height="11" fill={PAL.blue} opacity="0.45" />))}
      <rect x="6" y="-16" width="16" height="16" fill={PAL.blue} />
    </g>
  );
}

// ---------------------------------------------------------------- house for the income ladder (origin = bottom centre)
export function House({ x = 0, y = 0, w = 60, h = 50, color = PAL.blue }) {
  const roof = w * 0.42;
  return (
    <g transform={`translate(${x} ${y})`}>
      <ellipse cx="0" cy="2" rx={w * 0.62} ry="5" fill="#00000012" />
      <rect x={-w / 2} y={-h} width={w} height={h} fill="#fff" stroke={color} strokeWidth="2.5" />
      <path d={`M${-w / 2 - 8} ${-h} L0 ${-h - roof} L${w / 2 + 8} ${-h} Z`} fill={color} />
      <rect x={-w * 0.12} y={-h * 0.5} width={w * 0.24} height={h * 0.5} fill={color} opacity="0.75" />
      <rect x={-w * 0.38} y={-h * 0.78} width={w * 0.18} height={h * 0.18} fill={color} opacity="0.35" />
      <rect x={w * 0.2} y={-h * 0.78} width={w * 0.18} height={h * 0.18} fill={color} opacity="0.35" />
    </g>
  );
}
