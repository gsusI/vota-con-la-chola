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
        title: "Contrastar lo dicho y lo observado",
        note: "Revisa pares explícitos sin convertir similitud temática o ausencia en un veredicto.",
        href: "/comparisons/",
        cta: "Abrir comparaciones",
      },
      {
        title: "Comparar tus opiniones con los votos",
        note: "Responde afirmaciones y mira qué partidos votaron en el Congreso como tú, con cada voto enlazado.",
        href: "/citizen/vota/",
        cta: "Abrir ayuda al voto",
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
        title: "Dicho frente a hecho",
        href: "/comparisons/",
        note: "Promesas y acciones posteriores con mapping, capacidad, incertidumbre y evidencia oficial.",
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
        title: "Seguir relaciones con evidencia",
        note: "Consulta actores, vínculos, vigencia y fuente sin fusionar identidades solo por nombre.",
        href: "/actor-graph/",
        cta: "Abrir grafo de actores",
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
        title: "Grafo de actores",
        href: "/actor-graph/",
        note: "Relaciones temporales entre actores con alcance de identidad y evidencia oficial.",
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
    id: "calendar",
    href: "/calendario-electoral/",
    navLabel: "Calendario",
    title: "Calendario electoral",
    question: "¿Cuándo son las próximas elecciones y con qué fuente?",
    description:
      "Ordena convocatorias oficiales, ciclos legales y fechas condicionales por ámbito y territorio.",
    chips: ["Convocatorias", "Ciclos", "Territorio"],
    tasks: [
      {
        title: "Ver próximas elecciones",
        note: "Timeline de citas oficiales, fechas calculadas y ventanas condicionales.",
        href: "/calendario-electoral/",
        cta: "Abrir calendario",
      },
      {
        title: "Auditar una elección",
        note: "Entra en páginas dedicadas con candidaturas, programas y evidencia separada de claims.",
        href: "/elecciones/",
        cta: "Abrir elecciones",
      },
      {
        title: "Revisar comportamiento electoral",
        note: "Cruza cada elección con señales antes y después del voto.",
        href: "/elections-behavior/",
        cta: "Abrir análisis electoral",
      },
      {
        title: "Auditar fuentes electorales",
        note: "Consulta cobertura, bloqueos y fuentes del dominio electoral.",
        href: "/explorer-sources/?domain=infoelectoral",
        cta: "Ver fuentes",
      },
    ],
    surfaces: [
      {
        title: "Calendario electoral",
        href: "/calendario-electoral/",
        note: "Próximas citas por ámbito, territorio, estado y fuente.",
      },
      {
        title: "Páginas electorales",
        href: "/elecciones/",
        note: "Índice de elecciones con cortes dedicados de candidaturas, programas y medidas.",
      },
      {
        title: "Elecciones y comportamiento",
        href: "/elections-behavior/",
        note: "Comparativas antes y después de cada elección por partido, tema y territorio.",
      },
      {
        title: "Fuentes electorales",
        href: "/explorer-sources/",
        note: "Estado operativo de Infoelectoral, JEC y otros datos electorales.",
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
      "Consulta indicadores, sanciones y comportamiento electoral; cualquier vínculo con una decisión exige revisión explícita.",
    chips: ["Indicadores", "Sanciones", "Series"],
    tasks: [
      {
        title: "Revisar el estado de resultados",
        note: "Consulta qué vínculos han superado evidencia, revisión humana y publicación.",
        href: "/policy-outcomes/",
        cta: "Abrir estado",
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
      {
        title: "Auditar Andalucía 2026",
        note: "Parte de candidaturas oficiales y huecos de evidencia antes de atribuir responsabilidad.",
        href: "/elecciones/andalucia-2026/",
        cta: "Abrir Andalucía 2026",
      },
    ],
    surfaces: [
      {
        title: "Estado de resultados",
        href: "/policy-outcomes/",
        note: "Evidencia, revisión humana y estado de publicación de cada vínculo.",
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
      {
        title: "Andalucía 2026",
        href: "/elecciones/andalucia-2026/",
        note: "Partidos, candidatos, actores enlazados y scrapers pendientes para culpa/mérito.",
      },
    ],
  },
  {
    id: "visualizaciones",
    href: "/visualizaciones/",
    navLabel: "Visualizaciones",
    title: "Visualizaciones de datos públicos",
    question: "¿Qué cuentan las series oficiales a largo plazo?",
    description:
      "Gráficos sobre datos públicos con la fuente oficial enlazada, rupturas de serie señaladas, comparación con países similares y datos descargables.",
    chips: ["Series largas", "Fuentes oficiales", "Datos descargables"],
    tasks: [
      {
        title: "Cien años de impuestos en España",
        note: "Presión fiscal desde 1925, recaudación real por habitante, quién paga, tipos legales y complejidad normativa.",
        href: "/visualizaciones/carga-fiscal/",
        cta: "Abrir visualización",
      },
      {
        title: "El paro en España: ¿estructural o cíclico?",
        note: "Paro desde 1960 frente a Europa, por qué cada crisis destruye tanto empleo, causas de la brecha, fijos discontinuos, regiones, productividad y salarios.",
        href: "/visualizaciones/empleo/",
        cta: "Abrir visualización",
      },
      {
        title: "Vivienda: ¿falta construir o falta gasto público?",
        note: "Años de salario para comprar un piso, viviendas terminadas frente a hogares nuevos, emancipación, propiedad, impuestos de compra y gasto público.",
        href: "/visualizaciones/vivienda/",
        cta: "Abrir visualización",
      },
      {
        title: "Educación: más gasto, resultados estancados y mucho menos abandono",
        note: "Gasto público real por alumno, PISA, abandono escolar, repetición, sobrecualificación y un siglo de alfabetización.",
        href: "/visualizaciones/educacion/",
        cta: "Abrir visualización",
      },
      {
        title: "Sanidad: vivir más, gastar menos y más gente esperando",
        note: "Esperanza de vida desde 1925, gasto sanitario público frente a Europa, listas de espera del SNS con sus rupturas de serie y médicos por habitante.",
        href: "/visualizaciones/sanidad/",
        cta: "Abrir visualización",
      },
      {
        title: "Simulador: si se suben las pensiones o los impuestos, ¿quién lo paga?",
        note: "Mueve pensiones, IRPF, IVA, cotizaciones o Sociedades y mira cómo se propaga a la deuda, el empleo, cada quintil de renta y cuatro casos tipo, según se pague con deuda, cotizaciones, IVA o IRPF.",
        href: "/visualizaciones/sistema/",
        cta: "Abrir simulador",
      },
    ],
    surfaces: [
      {
        title: "Carga y complejidad fiscal",
        href: "/visualizaciones/carga-fiscal/",
        note: "FMI, OCDE, Eurostat, Banco Mundial y BOE, con tabla y procedencia por gráfico.",
      },
      {
        title: "Empleo, paro y productividad",
        href: "/visualizaciones/empleo/",
        note: "AMECO, Eurostat, EPA del INE, OCDE, Seguridad Social y Ministerio de Trabajo, con rupturas de serie marcadas y comparación con la UE.",
      },
      {
        title: "Vivienda, construcción y hogares",
        href: "/visualizaciones/vivienda/",
        note: "Ministerio de Vivienda, Banco de España, INE, Eurostat, OCDE y BOE, con tabla y procedencia por gráfico.",
      },
      {
        title: "Gasto y resultados educativos",
        href: "/visualizaciones/educacion/",
        note: "Ministerio de Educación, Eurostat, OCDE (Education at a Glance, PISA), Banco Mundial y Our World in Data.",
      },
      {
        title: "Esperanza de vida, gasto y listas de espera",
        href: "/visualizaciones/sanidad/",
        note: "Ministerio de Sanidad (SISLE-SNS, EGSP), INE, Eurostat, OCDE y Banco Mundial, con rupturas de serie y procedencia por gráfico.",
      },
      {
        title: "Simulador de pensiones, impuestos y cuentas públicas",
        href: "/visualizaciones/sistema/",
        note: "Modelo sobre la línea base del Ageing Report 2024, con fichas de relaciones causales con fuente, rango y revisión de calidad, y reparto por quintil con microdatos de la ECV.",
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
        title: "Auditar obstrucciones públicas",
        note: "Revisa cada bloqueo con señal técnica, evidencia, impacto y siguiente escalado.",
        href: "/obstruction-tracker/",
        cta: "Abrir registro",
      },
      {
        title: "Comprobar el estado del proyecto",
        note: "Contrasta frescura, salud de fuentes, snapshot vigente y cambios publicados.",
        href: "/transparency/",
        cta: "Abrir transparencia",
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
        title: "Obstrucción de datos públicos",
        href: "/obstruction-tracker/",
        note: "Registro append-only de acceso bloqueado o degradado con evidencia reproducible.",
      },
      {
        title: "Transparencia operativa",
        href: "/transparency/",
        note: "Frescura, salud de fuentes, versión pública y cambios con evidencia por métrica.",
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
    id: "viz-carga-fiscal",
    sectionId: "visualizaciones",
    label: "Carga y complejidad fiscal (CSV)",
    path: "/visualizaciones/data/carga-fiscal.csv",
    note: "Series de presión fiscal, desglose y recaudación por habitante usadas en la visualización.",
    confidence: "Publicado",
  },
  {
    id: "viz-carga-fiscal-json",
    sectionId: "visualizaciones",
    label: "Carga y complejidad fiscal (JSON con procedencia)",
    path: "/visualizaciones/data/carga-fiscal.json",
    note: "Mismas series con URL, fecha de consulta y SHA-256 de cada fuente original.",
    confidence: "Publicado",
  },
  {
    id: "viz-empleo",
    sectionId: "visualizaciones",
    label: "Empleo, paro y productividad (CSV)",
    path: "/visualizaciones/data/empleo.csv",
    note: "Paro, paro juvenil, temporalidad, productividad por hora, cuña fiscal y tasa de empleo usados en la visualización.",
    confidence: "Publicado",
  },
  {
    id: "viz-empleo-json",
    sectionId: "visualizaciones",
    label: "Empleo, paro y productividad (JSON con procedencia)",
    path: "/visualizaciones/data/empleo.json",
    note: "Mismas series con URL, fecha de consulta, ruta del original y SHA-256 de cada fuente.",
    confidence: "Publicado",
  },
  {
    id: "viz-vivienda",
    sectionId: "visualizaciones",
    label: "Vivienda, construcción y hogares (CSV)",
    path: "/visualizaciones/data/vivienda.csv",
    note: "Años de salario por piso, viviendas terminadas e iniciadas, hogares, emancipación, tenencia, impuestos de compra y gasto público en vivienda.",
    confidence: "Publicado",
  },
  {
    id: "viz-vivienda-json",
    sectionId: "visualizaciones",
    label: "Vivienda, construcción y hogares (JSON con procedencia)",
    path: "/visualizaciones/data/vivienda.json",
    note: "Mismas series con URL, fecha de consulta y SHA-256 de cada fuente; tipos impositivos con su norma del BOE.",
    confidence: "Publicado",
  },
  {
    id: "viz-educacion",
    sectionId: "visualizaciones",
    label: "Gasto y resultados educativos (CSV)",
    path: "/visualizaciones/data/educacion.csv",
    note: "Gasto público real por alumno, PISA, abandono temprano, idoneidad, sobrecualificación, alfabetización y años de escolarización.",
    confidence: "Publicado",
  },
  {
    id: "viz-educacion-json",
    sectionId: "visualizaciones",
    label: "Gasto y resultados educativos (JSON con procedencia)",
    path: "/visualizaciones/data/educacion.json",
    note: "Mismas series con URL, fecha de consulta y SHA-256 de cada fuente; valores de PISA 2022 con documento, página y cita.",
    confidence: "Publicado",
  },
  {
    id: "viz-sanidad",
    sectionId: "visualizaciones",
    label: "Esperanza de vida, gasto y listas de espera (CSV)",
    path: "/visualizaciones/data/sanidad.csv",
    note: "Esperanza de vida, gasto sanitario público y privado, listas de espera del SNS por corte semestral y comunidad, y médicos por habitante.",
    confidence: "Publicado",
  },
  {
    id: "viz-sanidad-json",
    sectionId: "visualizaciones",
    label: "Esperanza de vida, gasto y listas de espera (JSON con procedencia)",
    path: "/visualizaciones/data/sanidad.json",
    note: "Mismas series con URL, fecha de consulta y SHA-256 de cada fuente; rupturas de serie y rectificaciones de las listas de espera marcadas.",
    confidence: "Publicado",
  },
  {
    id: "viz-sistema",
    sectionId: "visualizaciones",
    label: "Simulador de pensiones: línea base (CSV)",
    path: "/visualizaciones/data/sistema.csv",
    note: "Línea base 2025-2050: gasto en pensiones, pensionistas, empleo, crecimiento, tipos, deuda y sensibilidades de inmigración del Ageing Report 2024.",
    confidence: "Publicado",
  },
  {
    id: "viz-sistema-json",
    sectionId: "visualizaciones",
    label: "Simulador de pensiones: modelo completo (JSON con procedencia)",
    path: "/visualizaciones/data/sistema.json",
    note: "Línea base, parámetros con rango, fichas de las relaciones con fuente y revisión, casos tipo, votaciones enlazadas y SHA-256 de cada fuente.",
    confidence: "Publicado",
  },
  {
    id: "citizen-core",
    sectionId: "topics",
    label: "Ciudadanía",
    path: "/citizen/data/citizen.json",
    note: "Archivo principal para el resumen guiado de temas y comparación.",
    confidence: "Publicado",
  },
  {
    id: "voting-aid-generales",
    sectionId: "topics",
    label: "Ayuda al voto (generales)",
    path: "/citizen/data/voting_aid_generales_v1.json",
    note: "Afirmaciones respaldadas por votaciones del Congreso y posición de cada partido; borrador sin revisión independiente.",
    confidence: "Borrador",
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
    id: "actor-graph-v1",
    sectionId: "actors",
    label: "Grafo temporal de actores",
    path: "/actor-graph/data/graph.json",
    note: "Agregados completos y muestra estable de actores y relaciones reales con fuente, vigencia y política de resolución de identidad.",
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
    label: "Estado de resultados",
    path: "/policy-outcomes/data/policy-outcomes.json",
    note: "Estado agregado del pipeline; no publica candidatos pendientes ni afirma efectos.",
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
    id: "andalucia-2026-accountability",
    sectionId: "outcomes",
    label: "Andalucía 2026",
    path: "/elecciones/andalucia-2026/data/accountability.json",
    note: "Candidaturas proclamadas, actores enlazados y gaps de evidencia para responsabilidad.",
    confidence: "Publicado",
  },
  {
    id: "election-calendar",
    sectionId: "calendar",
    label: "Calendario electoral",
    path: "/calendario-electoral/data/election-calendar.json",
    note: "Convocatorias oficiales, ciclos legales y fechas condicionales.",
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
    id: "obstruction-tracker",
    sectionId: "methods",
    label: "Obstrucción de datos públicos",
    path: "/obstruction-tracker/data/obstructions.json",
    note: "Incidencias abiertas e históricas, evidencia enlazada y readiness de escala real.",
    confidence: "Publicado",
  },
  {
    id: "transparency-dashboard",
    sectionId: "methods",
    label: "Transparencia operativa",
    path: "/transparency/data/transparency.json",
    note: "Frescura, salud, obstrucciones, readiness, snapshot durable y notas de versión trazables.",
    confidence: "Publicado",
  },
  {
    id: "manifesto-promises-bng-2023",
    sectionId: "decisions",
    label: "Promesas BNG 2023",
    path: "/promises/data/bng-2023.json",
    note: "Compromisos rule-confirmed con actor, página, cita y hash del manifiesto oficial.",
    confidence: "Publicado",
  },
  {
    id: "promise-action-comparisons-v1",
    sectionId: "decisions",
    label: "Dicho frente a hecho",
    path: "/comparisons/data/comparisons.json",
    note: "Cinco comparaciones reales revisadas con identidad pública, estados de incertidumbre y evidencia primaria; cero veredictos fuertes en v1.",
    confidence: "Publicado",
  },
  {
    id: "placsp-spending-awards-sample",
    sectionId: "decisions",
    label: "Adjudicaciones PLACSP",
    path: "/spending/data/placsp-sample.json",
    note: "Muestra real actor-adjudicación-evidencia con identidad oficial e importes decimales exactos; no representa pagos.",
    confidence: "Publicado",
  },
  {
    id: "moncloa-agreements-sample",
    sectionId: "decisions",
    label: "Acuerdos del Consejo de Ministros",
    path: "/agreements/data/moncloa-sample.json",
    note: "Muestra real sesión-acuerdo-actores-evidencia; temas derivados visibles y cero afirmaciones de influencia.",
    confidence: "Publicado",
  },
  {
    id: "moncloa-geopolitics-sample",
    sectionId: "decisions",
    label: "Acciones exteriores de La Moncloa",
    path: "/geopolitics/data/moncloa-sample.json",
    note: "Dos acciones reales de autorización/remisión con contrapartes y evidencia; vigencia, ejecución, alineamiento e impacto no evaluados.",
    confidence: "Publicado",
  },
  {
    id: "eurostat-gdp-spain-indicator",
    sectionId: "outcomes",
    label: "PIB regional por habitante Eurostat",
    path: "/indicators/data/eurostat-gdp-es.json",
    note: "2.091 observaciones reales con territorio, periodo, valor decimal, estado provisional y evidencia de celda; sin inferencia causal.",
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
    id: "question-calendar",
    sectionId: "calendar",
    title: "¿Cuándo vuelve a votar cada ámbito?",
    note: "Consulta citas oficiales, ciclos fijos y ventanas condicionales.",
  },
  {
    id: "question-outcomes",
    sectionId: "outcomes",
    title: "¿Qué vínculos con resultados están validados?",
    note: "Distingue candidatos, revisión humana y publicaciones trazables.",
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
