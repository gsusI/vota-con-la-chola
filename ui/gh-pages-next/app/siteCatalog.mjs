export function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

export function withBasePath(path) {
  return `${resolveBasePath()}${path}`;
}

export const siteSections = [
  {
    id: "topics",
    href: "/topics/",
    navLabel: "Temas",
    title: "Temas",
    question: "¿Qué pasó en este tema y con qué evidencia?",
    description:
      "Consulta postura, evidencia, votaciones relacionadas y resultados clave de cada asunto.",
    chips: ["Posturas", "Evidencia", "Resultados"],
    tasks: [
      {
        title: "Buscar un tema concreto",
        note: "Empieza por un asunto y baja después a actores, eventos y evidencias.",
        href: "/explorer-temas/",
        cta: "Abrir explorador de temas",
      },
      {
        title: "Comparar posiciones",
        note: "Contrasta diferencias entre personas y partidos sobre el mismo tema.",
        href: "/political-positions/",
        cta: "Abrir posturas explicables",
      },
      {
        title: "Ver un resumen guiado",
        note: "Si quieres una lectura más rápida, usa la vista ciudadana como resumen.",
        href: "/citizen/",
        cta: "Abrir vista ciudadana",
      },
    ],
    surfaces: [
      {
        title: "Explorador de temas",
        href: "/explorer-temas/",
        note: "Índice principal de temas, evidencia y acceso por asunto.",
      },
      {
        title: "Posturas explicables",
        href: "/political-positions/",
        note: "Comparación de personas y partidos con soportes, continuidad y filtros.",
      },
      {
        title: "Ciudadanía",
        href: "/citizen/",
        note: "Entrada guiada y compacta para convertir temas en comparaciones útiles.",
      },
    ],
  },
  {
    id: "actors",
    href: "/actors/",
    navLabel: "Actores",
    title: "Actores",
    question: "¿Quién es este actor y qué sabemos sobre él?",
    description:
      "Reúne perfiles, trayectorias, territorios e instituciones para seguir a cada actor con contexto.",
    chips: ["Perfiles", "Trayectorias", "Territorio"],
    tasks: [
      {
        title: "Buscar una persona o partido",
        note: "El directorio es la mejor puerta de entrada para perfiles y relaciones.",
        href: "/people/",
        cta: "Abrir directorio",
      },
      {
        title: "Entrar por territorio o institución",
        note: "Explora por ámbito, territorio o institución cuando no partes de un nombre.",
        href: "/explorer-politico/",
        cta: "Abrir explorador territorial",
      },
      {
        title: "Comparar trayectorias y posiciones",
        note: "Cruza perfiles, continuidad y posiciones en una sola vista.",
        href: "/political-positions/",
        cta: "Comparar actores",
      },
    ],
    surfaces: [
      {
        title: "Personas",
        href: "/people/",
        note: "Perfiles, cargos, actividad y huecos de información pendientes.",
      },
      {
        title: "Explorador territorial",
        href: "/explorer-politico/",
        note: "Entrada por ámbito, territorio, institución y mapa político.",
      },
      {
        title: "Posturas explicables",
        href: "/political-positions/",
        note: "Comparación persona/partido con evidencia rastreable.",
      },
    ],
  },
  {
    id: "decisions",
    href: "/decisions/",
    navLabel: "Decisiones",
    title: "Decisiones",
    question: "¿Qué se decidió, quién votó y cómo avanzó?",
    description:
      "Sigue votaciones, iniciativas y disciplina parlamentaria desde un mismo punto de entrada.",
    chips: ["Votaciones", "Iniciativas", "Disciplina"],
    tasks: [
      {
        title: "Empezar por una votación",
        note: "Sigue la actividad parlamentaria, las implicaciones revisadas y los votos nominales.",
        href: "/explorer-votaciones/",
        cta: "Abrir votaciones",
      },
      {
        title: "Seguir una iniciativa",
        note: "Comprueba por dónde pasó y con qué confianza está enlazada al voto.",
        href: "/initiative-lifecycle/",
        cta: "Abrir tramitación",
      },
      {
        title: "Analizar disciplina y coaliciones",
        note: "Consulta cohesión, rebeldía, asistencia y coaliciones.",
        href: "/parliamentary-accountability/",
        cta: "Abrir seguimiento",
      },
      {
        title: "Ver dossiers de accountability",
        note: "Cruza temas y actores desde el ledger genérico publicado.",
        href: "/accountability-dossiers/",
        cta: "Abrir dossiers",
      },
      {
        title: "Usar Evidence API",
        note: "Abre respuestas repetibles con caveats y muestras de evidencia.",
        href: "/accountability-evidence/",
        cta: "Abrir API",
      },
    ],
    surfaces: [
      {
        title: "Votaciones",
        href: "/explorer-votaciones/",
        note: "Índice de eventos, grupos y explicaciones revisadas.",
      },
      {
        title: "Tramitación legislativa",
        href: "/initiative-lifecycle/",
        note: "Detalle de iniciativa, hitos y secuencia de votos.",
      },
      {
        title: "Seguimiento parlamentario",
        href: "/parliamentary-accountability/",
        note: "Disciplina, asistencia, resultados y coaliciones.",
      },
      {
        title: "Dossiers de accountability",
        href: "/accountability-dossiers/",
        note: "Resumen issue-led y actor-led de responsabilidades trazables.",
      },
      {
        title: "Evidence API",
        href: "/accountability-evidence/",
        note: "Catalogo de preguntas y respuestas parciales con caveats.",
      },
    ],
  },
  {
    id: "outcomes",
    href: "/outcomes/",
    navLabel: "Resultados",
    title: "Resultados",
    question: "¿Qué señales aparecen en los datos?",
    description:
      "Consulta indicadores, sanciones y comportamiento electoral relacionados con decisiones públicas.",
    chips: ["Indicadores", "Sanciones", "Series"],
    tasks: [
      {
        title: "Explorar indicadores",
        note: "Empieza por resultados observables y señales posteriores a decisiones públicas.",
        href: "/policy-outcomes/",
        cta: "Abrir resultados",
      },
      {
        title: "Abrir sanciones y cumplimiento",
        note: "Sigue normas, responsabilidades y volumen sancionador.",
        href: "/legal-sanctions/",
        cta: "Abrir legal + sanciones",
      },
      {
        title: "Ver comportamiento electoral",
        note: "Consulta cambios antes y después de elecciones por partido, tema y territorio.",
        href: "/elections-behavior/",
        cta: "Abrir análisis electoral",
      },
    ],
    surfaces: [
      {
        title: "Resultados de política pública",
        href: "/policy-outcomes/",
        note: "Indicadores económicos y sociales vinculados a eventos relevantes.",
      },
      {
        title: "Cumplimiento legal y sanciones",
        href: "/legal-sanctions/",
        note: "Relaciones entre normas, responsabilidades, volúmenes y ejecución.",
      },
      {
        title: "Elecciones y comportamiento",
        href: "/elections-behavior/",
        note: "Comparativas antes y después de cada elección por partido, tema y territorio.",
      },
    ],
  },
  {
    id: "methods",
    href: "/methods/",
    navLabel: "Datos y método",
    title: "Datos y método",
    question: "¿De dónde sale la información y qué cobertura tiene?",
    description:
      "Consulta cobertura, archivos publicados y herramientas de comprobación para entender el alcance de cada vista.",
    chips: ["Cobertura", "Archivos", "Comprobación"],
    tasks: [
      {
        title: "Revisar cobertura y bloqueos",
        note: "Consulta fuentes, progreso y bloqueos desde un único punto de entrada.",
        href: "/methods/coverage/",
        cta: "Abrir cobertura",
      },
      {
        title: "Ver los archivos publicados",
        note: "Consulta los archivos disponibles y la sección donde se usan.",
        href: "/methods/datasets/",
        cta: "Abrir archivos",
      },
      {
        title: "Abrir herramientas de comprobación",
        note: "Accede a las vistas de base de datos y grafo cuando necesites auditar el detalle.",
        href: "/methods/explorer/",
        cta: "Abrir explorador SQL",
      },
    ],
    surfaces: [
      {
        title: "Fuentes y calidad",
        href: "/explorer-sources/",
        note: "Estado de fuentes, cobertura y bloqueos abiertos.",
      },
      {
        title: "Explorador SQL",
        href: "/explorer/",
        note: "Tablas, registros y evidencias al nivel más detallado.",
      },
      {
        title: "Esquema y relaciones",
        href: "/graph/",
        note: "Vista estructural y esquema navegable.",
      },
    ],
  },
];

export const datasetCatalog = [
  {
    id: "citizen-core",
    sectionId: "topics",
    label: "Ciudadanía",
    path: "/citizen/data/citizen.json",
    note: "Archivo principal para el resumen guiado de temas y comparación.",
    confidence: "Publicado",
  },
  {
    id: "citizen-votes",
    sectionId: "topics",
    label: "Ciudadanía y votaciones",
    path: "/citizen/data/citizen_votes.json",
    note: "Capa de alineación basada en votaciones para relacionar temas y partidos.",
    confidence: "Publicado",
  },
  {
    id: "topics-preview",
    sectionId: "topics",
    label: "Vista previa de temas",
    path: "/explorer-temas/data/temas-preview.json",
    note: "Índice publicado de temas y primeras vistas.",
    confidence: "Publicado",
  },
  {
    id: "stances",
    sectionId: "topics",
    label: "Posturas",
    path: "/political-positions/data/stances.json",
    note: "Base publicada de posturas explicables por actor y tema.",
    confidence: "Publicado",
  },
  {
    id: "profiles",
    sectionId: "actors",
    label: "Perfiles",
    path: "/people/data/profiles.json",
    note: "Directorio unificado de personas y metadatos principales.",
    confidence: "Publicado",
  },
  {
    id: "xray",
    sectionId: "actors",
    label: "Rutas de perfiles",
    path: "/people/data/xray.json",
    note: "Agrupaciones y rutas de exploración de perfiles.",
    confidence: "Publicado",
  },
  {
    id: "person-trajectories",
    sectionId: "actors",
    label: "Trayectorias de personas",
    path: "/political-positions/data/person-trajectories.json",
    note: "Trayectorias comparables de personas y continuidad temporal.",
    confidence: "Publicado",
  },
  {
    id: "party-trajectories",
    sectionId: "actors",
    label: "Trayectorias de partidos",
    path: "/political-positions/data/party-trajectories.json",
    note: "Trayectorias de partidos para comparación agregada.",
    confidence: "Publicado",
  },
  {
    id: "votes-preview",
    sectionId: "decisions",
    label: "Vista previa de votaciones",
    path: "/explorer-votaciones/data/votes-preview.json",
    note: "Índice publicado de eventos de voto recientes y destacados.",
    confidence: "Publicado",
  },
  {
    id: "initiative-lifecycle",
    sectionId: "decisions",
    label: "Tramitación",
    path: "/initiative-lifecycle/data/lifecycle.json",
    note: "Trazabilidad de iniciativa, hitos y confianza de enlace.",
    confidence: "Publicado",
  },
  {
    id: "accountability",
    sectionId: "decisions",
    label: "Seguimiento parlamentario",
    path: "/parliamentary-accountability/data/accountability.json",
    note: "Disciplina, asistencia, coaliciones y resultados por grupo.",
    confidence: "Publicado",
  },
  {
    id: "accountability-dossiers",
    sectionId: "decisions",
    label: "Dossiers de accountability",
    path: "/accountability-dossiers/data/dossiers.json",
    note: "Resumen por tema y por actor del ledger genérico de accountability.",
    confidence: "Publicado",
  },
  {
    id: "accountability-ledger",
    sectionId: "decisions",
    label: "Ledger de accountability",
    path: "/accountability-dossiers/data/ledger.json",
    note: "Ledger trazable completo usado para construir los dossiers compactos.",
    confidence: "Publicado",
  },
  {
    id: "policy-outcomes",
    sectionId: "outcomes",
    label: "Resultados observables",
    path: "/policy-outcomes/data/policy-outcomes.json",
    note: "Indicadores y asociaciones descriptivas posteriores a eventos.",
    confidence: "Publicado",
  },
  {
    id: "legal-sanctions",
    sectionId: "outcomes",
    label: "Sanciones y cumplimiento",
    path: "/legal-sanctions/data/legal-sanctions.json",
    note: "Normas, responsabilidades y volúmenes sancionadores.",
    confidence: "Publicado",
  },
  {
    id: "elections-behavior",
    sectionId: "outcomes",
    label: "Comportamiento electoral",
    path: "/elections-behavior/data/elections-behavior.json",
    note: "Comparación antes y después de cada elección y cambios de cohesión.",
    confidence: "Publicado",
  },
  {
    id: "sources-status",
    sectionId: "methods",
    label: "Estado de fuentes",
    path: "/explorer-sources/data/status.json",
    note: "Estado operativo, hoja de ruta y calidad de fuentes.",
    confidence: "Publicado",
  },
  {
    id: "sources-ideal",
    sectionId: "methods",
    label: "Inventario objetivo",
    path: "/explorer-sources/data/ideal.json",
    note: "Inventario objetivo de fuentes y alcance deseado.",
    confidence: "Publicado",
  },
  {
    id: "sources-coverage",
    sectionId: "methods",
    label: "Cobertura esperada",
    path: "/explorer-sources/data/coverage-capacity.json",
    note: "Cobertura frente al total esperado en cada dimensión.",
    confidence: "Publicado",
  },
  {
    id: "sources-coverage-model",
    sectionId: "methods",
    label: "Modelo de cobertura",
    path: "/explorer-sources/data/coverage-model.json",
    note: "Definición de unidades y criterios usados para medir cobertura.",
    confidence: "Publicado",
  },
  {
    id: "graph",
    sectionId: "methods",
    label: "Esquema y relaciones",
    path: "/graph/data/graph.json",
    note: "Vista estructural del esquema y relaciones publicadas.",
    confidence: "Publicado",
  },
];

export const homeQuestions = [
  {
    id: "question-topics",
    sectionId: "topics",
    title: "¿Qué posición existe sobre un tema?",
    note: "Empieza por tema, postura, evidencia y cobertura.",
  },
  {
    id: "question-actors",
    sectionId: "actors",
    title: "¿Qué ha hecho este actor?",
    note: "Busca una persona, un partido o una institución y sigue su rastro.",
  },
  {
    id: "question-decisions",
    sectionId: "decisions",
    title: "¿Qué se votó y cómo se llegó ahí?",
    note: "Entra por evento, iniciativa o disciplina parlamentaria.",
  },
  {
    id: "question-outcomes",
    sectionId: "outcomes",
    title: "¿Qué resultados o efectos observables hay?",
    note: "Cruza indicadores, sanciones y comportamiento con políticas.",
  },
  {
    id: "question-methods",
    sectionId: "methods",
    title: "¿Qué cobertura tiene esta información?",
    note: "Consulta cobertura, archivos publicados y herramientas de comprobación.",
  },
];

export function getSectionById(sectionId) {
  return siteSections.find((section) => section.id === sectionId) || null;
}

export function getDatasetsForSection(sectionId) {
  return datasetCatalog.filter((dataset) => dataset.sectionId === sectionId);
}

export function getHomeQuestionCards() {
  return homeQuestions
    .map((item) => {
      const section = getSectionById(item.sectionId);
      if (!section) {
        return null;
      }
      return {
        ...item,
        href: section.href,
        label: section.navLabel,
        question: section.question,
      };
    })
    .filter(Boolean);
}
