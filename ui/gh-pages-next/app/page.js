const sections = [
  {
    href: "/citizen/",
    title: "Ciudadania",
    note: "Compara prioridades personales contra posturas por partido.",
  },
  {
    href: "/citizen/leaderboards.html",
    title: "Leaderboards",
    note: "Rankings transparentes por hipotesis y cobertura.",
  },
  {
    href: "/explorer-temas/",
    title: "Temas",
    note: "Drill-down dice vs hace por tema y partido.",
  },
  {
    href: "/explorer/",
    title: "Explorer SQL",
    note: "Navegacion esquema/filas/FKs sobre snapshot SQLite.",
  },
  {
    href: "/explorer-sources/",
    title: "Fuentes",
    note: "Estado operativo, bloqueos y cobertura por conector.",
  },
  {
    href: "/explorer-politico/",
    title: "Explorer Politico",
    note: "Mapa politico y cobertura por arena institucional.",
  },
  {
    href: "/explorer-votaciones/",
    title: "Votaciones",
    note: "Vista compacta de eventos y trazabilidad inicial.",
  },
  {
    href: "/graph/",
    title: "Graph",
    note: "Exploracion de red y relaciones entre entidades.",
  },
];

const artifacts = [
  { href: "/citizen/data/citizen.json", label: "citizen.json", kind: "combined" },
  { href: "/citizen/data/citizen_votes.json", label: "citizen_votes.json", kind: "votes" },
  { href: "/citizen/data/citizen_declared.json", label: "citizen_declared.json", kind: "declared" },
  { href: "/citizen/data/concern_pack_quality.json", label: "concern_pack_quality.json", kind: "quality" },
  { href: "/explorer-sources/data/status.json", label: "status.json", kind: "sources" },
  { href: "/explorer-temas/data/temas-preview.json", label: "temas-preview.json", kind: "temas" },
  { href: "/explorer-votaciones/data/votes-preview.json", label: "votes-preview.json", kind: "votes-preview" },
  { href: "/graph/data/graph.json", label: "graph.json", kind: "graph" },
  { href: "/explorer-politico/data/arena-mandates.json", label: "arena-mandates.json", kind: "mandates" },
  { href: "/explorer-politico/data/sources.json", label: "sources.json", kind: "sources-meta" },
];

function withBasePath(path) {
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
  return `${basePath}${path}`;
}

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">STATIC NEXT.JS EXPORT</p>
        <h1>Vota Con La Chola - GH Pages</h1>
        <p className="sub">
          Este portal se publica como app estatico de Next.js y mantiene los mismos artefactos JSON trazables por
          snapshot para ciudadania y explorers.
        </p>
        <div className="chips">
          <span className="chip">single SQLite snapshot</span>
          <span className="chip">JSON bounded artifacts</span>
          <span className="chip">privacy gate before publish</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Superficies</h2>
        </div>
        <div className="grid">
          {sections.map((item) => (
            <a className="tile" key={item.href} href={withBasePath(item.href)}>
              <span className="tileTitle">{item.title}</span>
              <span className="tileNote">{item.note}</span>
            </a>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Artefactos JSON</h2>
        </div>
        <ul className="artifactList">
          {artifacts.map((item) => (
            <li key={item.href}>
              <a href={withBasePath(item.href)}>{item.label}</a>
              <span>{item.kind}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
