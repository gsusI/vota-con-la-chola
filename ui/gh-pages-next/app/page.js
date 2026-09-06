import { readPublicJson } from "./static-snapshot.mjs";
import { withBasePath } from "./path-utils.mjs";

const primaryRoutes = [
  {
    href: "/citizen/",
    label: "Ciudadanía",
    title: "Comparar partidos por tema",
    note: "Consulta rápida con evidencia y señales de incertidumbre.",
    cta: "Empezar",
  },
  {
    href: "/vote-explainer/",
    label: "Votaciones",
    title: "Abrir voto compartible",
    note: "Resultado, grupos, fuente oficial y salvedades visibles.",
    cta: "Ver votos",
  },
  {
    href: "/responsibility-explainer/",
    label: "Responsabilidad",
    title: "Seguir caso público",
    note: "Deberes, avisos, decisiones, huecos y evidencia.",
    cta: "Abrir casos",
  },
  {
    href: "/calendario-electoral/",
    label: "Calendario",
    title: "Ver próximas elecciones",
    note: "Convocatorias, ciclos legales y fechas condicionales.",
    cta: "Abrir",
  },
];

const routeGroups = [
  {
    title: "Para decidir",
    summary: "Entradas pensadas para ciudadanía y comparación rápida.",
    links: [
      {
        href: "/citizen/?mode=audit",
        title: "Modo auditoría ciudadana",
        note: "Verifica trazabilidad, incertidumbre y soporte primario.",
      },
      {
        href: "/citizen/leaderboards/",
        title: "Clasificaciones cívicas",
        note: "Ordenación por hipótesis, cobertura y comparabilidad.",
      },
      {
        href: "/elecciones/andalucia-2026/",
        title: "El recibo del agua de Andalucía",
        note: "Tres compromisos de investidura, estado verificable y fuentes oficiales.",
      },
      {
        href: "/policy-outcomes/",
        title: "Resultados de política pública",
        note: "Indicadores asociados a eventos de política.",
      },
      {
        href: "/calendario-electoral/",
        title: "Calendario electoral",
        note: "Próximas citas por ámbito, territorio y fuente.",
      },
    ],
  },
  {
    title: "Para auditar",
    summary: "Superficies de evidencia, votos, esquema y fuentes.",
    links: [
      {
        href: "/explorer-temas/",
        title: "Explorador de temas",
        note: "Dicho vs hecho por tema, ámbito y soporte.",
      },
      {
        href: "/explorer-votaciones/",
        title: "Monitor legislativo",
        note: "Eventos, grupos y seguimiento temporal.",
      },
      {
        href: "/explorer/",
        title: "Índice de datos",
        note: "Catálogo estático; reproduce consultas SQL con la descarga.",
      },
      {
        href: "/explorer-sources/",
        title: "Calidad de datos",
        note: "Cobertura, bloqueos externos y backlog operativo.",
      },
    ],
  },
  {
    title: "Para investigar actores",
    summary: "Quién hizo qué, dónde, cuándo y con qué señales.",
    links: [
      {
        href: "/people/",
        title: "Directorio de personas",
        note: "Perfil xray, cargos, posiciones y huecos.",
      },
      {
        href: "/explorer-politico/",
        title: "Explorador territorial",
        note: "Actores por territorio, partido y trayectoria.",
      },
      {
        href: "/political-positions/",
        title: "Posturas explicables",
        note: "Comparación persona/partido con evidencia rastreable.",
      },
      {
        href: "/elections-behavior/",
        title: "Elecciones y comportamiento",
        note: "Cambios pre/post elección por partido y territorio.",
      },
      {
        href: "/elecciones/andalucia-2026/",
        title: "Andalucía 2026",
        note: "Candidaturas oficiales y backlog de scrapers para culpa/mérito.",
      },
    ],
  },
  {
    title: "Para fiscalizar",
    summary: "Cohesión parlamentaria, ciclo legislativo y responsabilidad jurídica.",
    links: [
      {
        href: "/parliamentary-accountability/",
        title: "Accountability parlamentaria",
        note: "Disciplina, rebeldía, coaliciones, asistencia y pivotes.",
      },
      {
        href: "/accountability-dossiers/",
        title: "Dossiers de accountability",
        note: "Responsabilidades por tema y por actor desde el ledger trazable.",
      },
      {
        href: "/initiative-lifecycle/",
        title: "Lifecycle legislativo",
        note: "Tramitación, cuellos de botella y secuencia de votos.",
      },
      {
        href: "/legal-sanctions/",
        title: "Cumplimiento legal y sanciones",
        note: "Normas, infracciones, volumen sancionador y monitoreo.",
      },
    ],
  },
];

const signalRows = [
  ["temas", "evidencia", "votos", "fuentes"],
  ["actores", "territorio", "mandatos", "posturas"],
  ["casos", "deberes", "avisos", "huecos"],
  ["leyes", "ciclo", "grupos", "resultado"],
];

export default function HomePage() {
  const launch = readPublicJson("spending/launch/latest.json", null);
  if (!launch) throw new Error("Missing PLACSP launch");
  return (
    <main className="homepage">
      <section className="homepage-hero" aria-labelledby="homepage-title">
        <div className="homepage-hero__content">
          <p className="homepage-hero__eyebrow eyebrow">Corte público · evidencia primero</p>
          <h1 className="homepage-hero__title" id="homepage-title">Vota Con La Chola</h1>
          <p className="homepage-hero__summary">
            Investiga decisiones públicas con datos descargables y resultados que puedes comprobar. Empieza por una pregunta: ¿a quién se adjudicó, cuánto y en qué expedientes?
          </p>
          <div className="homepage-launch" aria-label="Caso de contratación pública">
            <h2 className="homepage-launch__title">Sigue el dinero hasta el expediente</h2>
            <p className="homepage-launch__scope">Todas las adjudicaciones PLACSP disponibles, sin recorte mensual. Filtra por organismo, proveedor y fechas. Adjudicado no significa pagado.</p>
            <p className="homepage-launch__actions">
              <a className="homepage-launch__demo" href={withBasePath("/spending/")}>Explorar adjudicaciones</a>{" · "}
              <a className="homepage-launch__download" href={withBasePath(`/spending/launch/${launch.release}/placsp-launch.zip`)}>Descargar datos y consultas</a>{" · "}
              <a className="homepage-launch__contribute" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/community/placsp-launch-tasks.md">Contribuir</a>
            </p>
          </div>
          <div className="homepage-hero__actions" aria-label="Entradas principales">
            {primaryRoutes.map((item) => (
              <a className="homepage-primary-link" href={withBasePath(item.href)} key={item.href}>
                <span className="homepage-primary-link__label">{item.label}</span>
                <span className="homepage-primary-link__title">{item.title}</span>
                <span className="homepage-primary-link__note">{item.note}</span>
                <span className="homepage-primary-link__cta">{item.cta}</span>
              </a>
            ))}
          </div>
        </div>

        <div className="homepage-signal-panel" aria-label="Mapa visual de evidencia">
          <div className="homepage-signal-panel__header">
            <span className="homepage-signal-panel__status">static</span>
            <span className="homepage-signal-panel__title">evidence graph</span>
          </div>
          <div className="homepage-signal-panel__matrix">
            {signalRows.map((row, rowIndex) => (
              <div className="homepage-signal-panel__row" key={row.join("-")}>
                {row.map((item, index) => (
                  <span
                    className="homepage-signal-panel__node"
                    data-weight={(rowIndex + index) % 3}
                    key={item}
                  >
                    {item}
                  </span>
                ))}
              </div>
            ))}
          </div>
          <div className="homepage-signal-panel__footer">
            <span className="homepage-signal-panel__metric">200 votos explicables</span>
            <span className="homepage-signal-panel__metric">0 server runtime</span>
          </div>
        </div>
      </section>

      <section className="homepage-routes" aria-labelledby="homepage-routes-title">
        <div className="homepage-section-heading">
          <p className="homepage-section-heading__eyebrow eyebrow">Workbench</p>
          <h2 className="homepage-section-heading__title" id="homepage-routes-title">Elige superficie</h2>
          <p className="homepage-section-heading__summary">
            Todas las rutas son estáticas y publicables. Cada enlace debe abrir sin servidor.
          </p>
        </div>

        <div className="homepage-route-groups">
          {routeGroups.map((group) => (
            <section className="homepage-route-group" aria-label={group.title} key={group.title}>
              <div className="homepage-route-group__heading">
                <h3 className="homepage-route-group__title">{group.title}</h3>
                <p className="homepage-route-group__summary">{group.summary}</p>
              </div>
              <div className="homepage-route-group__links">
                {group.links.map((item) => (
                  <a className="homepage-route-link" href={withBasePath(item.href)} key={item.href}>
                    <span className="homepage-route-link__title">{item.title}</span>
                    <span className="homepage-route-link__note">{item.note}</span>
                    <span className="homepage-route-link__path">{item.href}</span>
                  </a>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>

      <section className="homepage-proof" aria-label="Estado de publicación">
        <p className="homepage-proof__statement">Frontend estático. Rutas profundas. Evidencia enlazada.</p>
        <a className="homepage-proof__link" href={withBasePath("/explorer-sources/")}>
          Ver estado de fuentes
        </a>
      </section>
    </main>
  );
}
