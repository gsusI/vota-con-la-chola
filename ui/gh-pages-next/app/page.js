const personas = [
  {
    href: "/citizen/",
    title: "Ciudadanía - respuesta rápida",
    note: "Decide en menos de 5 minutos con un tema concreto y compara partidos.",
    target: "¿Qué partido está más alineado conmigo?",
    cta: "Empezar consulta",
  },
  {
    href: "/citizen/?mode=audit",
    title: "Ciudadanía escéptica",
    note: "Verifica resúmenes con evidencia primaria y señales de incertidumbre.",
    target: "Audita el resultado, trazabilidad y evidencia.",
    cta: "Abrir modo auditoría",
  },
  {
    href: "/citizen/leaderboards/",
    title: "Leaderboards cívicos",
    note: "Prueba hipótesis públicas con resultados comparables y auditable.",
    target: "Ranking por hipótesis y cobertura.",
    cta: "Entrar a leaderboard",
  },
  {
    href: "/explorer-temas/",
    title: "Analista de políticas",
    note: "Analiza ‘dicen vs hacen’ por tema/ámbito con evidencia trazable.",
    target: "Briefing temático y seguimiento de postura.",
    cta: "Abrir explorador de temas",
  },
  {
    href: "/explorer-votaciones/",
    title: "Monitor legislativo",
    note: "Sigue actividad parlamentaria y detecta cambios de postura.",
    target: "Eventos, grupos y seguimiento temporal.",
    cta: "Ver actividad parlamentaria",
  },
  {
    href: "/explorer-politico/",
    title: "Explorador territorial",
    note: "Encuentra actores por territorio, partido y trayectoria.",
    target: "Mapa político y cobertura institucional.",
    cta: "Explorar actores",
  },
  {
    href: "/explorer-sources/",
    title: "Operador de calidad de datos",
    note: "Prioriza bloqueos externos, cobertura y estado técnico.",
    target: "Backlog operativo y trazabilidad de fuentes.",
    cta: "Ver estado de fuentes",
  },
  {
    href: "/explorer/",
    title: "Power user SQL",
    note: "Audita métricas, cruza tablas y baja a evidencias puntuales.",
    target: "Explorador de esquema, FK y registros.",
    cta: "Entrar al explorer",
  },
];

function withBasePath(path) {
  const basePath =
    process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
  return `${basePath}${path}`;
}

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Selección por perfil</p>
        <h1>Vota Con La Chola - GH Pages</h1>
        <p className="sub">
          Elige tu perfil de uso para entrar directo al flujo más útil para tu objetivo.
        </p>
        <div className="chips">
          <span className="chip">UI pública en Next.js estático</span>
          <span className="chip">Estado reproducible por snapshot</span>
          <span className="chip">Trazabilidad prioritaria</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>¿Quién eres?</h2>
        </div>
        <div className="grid">
          {personas.map((item) => (
            <a className="tile" key={item.href} href={withBasePath(item.href)}>
              <span className="tileTitle">{item.title}</span>
              <span className="tileNote">{item.note}</span>
              <span className="tileNote" style={{ marginTop: "2px", color: "#7b2f20", fontWeight: 700 }}>
                {item.target}
              </span>
              <span className="chip">{item.cta}</span>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}
