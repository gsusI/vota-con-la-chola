// URLs of the indexable voting-aid pages (party, key question, topic) and their share cards. Pure: safe for client code.

export const VOTA_PATHS = {
  test: "/citizen/vota/",
  parties: "/citizen/vota/partidos/",
  people: "/citizen/vota/diputados/",
  topics: "/citizen/vota/temas/",
  vote: "/citizen/vota/votacion/",
  explore: "/citizen/vota/explorar/",
  map: "/citizen/vota/mapa/",
  method: "/citizen/vota/metodologia/",
};

const PARTY_SLUGS = { bildu: "eh-bildu", cc: "coalicion-canaria" };

// Slug (reads like a search) and short title (the question's subject) of each key question of the current test.
const QUESTION_SEO = {
  "eje-vivienda-intervencion": ["limitar-precio-alquiler", "Limitar el precio del alquiler"],
  "eje-vivienda-okupacion": ["okupacion-desalojos-familias-vulnerables", "Okupación y desalojo de familias vulnerables"],
  "eje-empleo-derechos": ["reduccion-jornada-derechos-laborales", "Reducir la jornada o rebajar costes a las empresas"],
  "eje-proteccion-social": ["subsidio-desempleo-pensiones-ingreso-minimo", "Ampliar subsidios, pensiones e ingreso mínimo"],
  "eje-autonomos-empresa": ["cuota-autonomos-salario-minimo", "Cuota de autónomos que ganan menos del SMI"],
  "eje-fiscalidad": ["bajar-impuestos-o-mantener-recaudacion", "Bajar impuestos o mantener la recaudación"],
  "eje-regulacion-economica": ["regular-empresas-proteger-consumidores", "Regular más a empresas y mercados"],
  "eje-educacion-modelo": ["escuela-concertada-eleccion-de-centro", "Escuela concertada y elección de centro"],
  "eje-lenguas": ["lenguas-cooficiales-congreso-juzgados", "Lenguas cooficiales en el Congreso y los juzgados"],
  "eje-clima-transicion": ["pacto-verde-europeo-politicas-climaticas", "Frenar el Pacto Verde Europeo"],
  "eje-nuclear": ["cierre-centrales-nucleares", "Cierre de las centrales nucleares"],
  "eje-transporte-publico": ["descuentos-abonos-transporte-publico", "Descuentos y abonos del transporte público"],
  "eje-campo-ambiente": ["lobo-agua-regadio-ganaderia", "El lobo, el agua, el regadío y la ganadería"],
  "eje-campo-comercio": ["aranceles-importaciones-agricolas", "Proteger el campo frente a las importaciones"],
  "eje-seguridad-penal": ["ley-mordaza-leyes-penales", "Ley mordaza y leyes penales"],
  "eje-justicia-independencia": ["cgpj-independencia-judicial-fiscalia", "CGPJ, jueces y Fiscalía"],
  "eje-inmigracion": ["politica-migratoria-control-fronteras", "Endurecer la política migratoria"],
  "eje-anticorrupcion": ["medidas-contra-la-corrupcion", "Más reglas contra la corrupción"],
  "eje-control-gobierno": ["exigir-responsabilidades-gobierno-corrupcion", "Exigir responsabilidades al Gobierno"],
  "eje-igualdad-genero": ["leyes-igualdad-genero-lgtbi", "Leyes de igualdad y LGTBI"],
  "eje-bioetica": ["aborto-eutanasia-sanidad-publica", "Aborto y eutanasia en la sanidad pública"],
  "eje-territorial-autogobierno": ["competencias-estado-comunidades-autonomas", "Más Estado o más autogobierno"],
  "eje-amnistia-proces": ["amnistia-pactos-independentistas", "Amnistía y pactos con independentistas"],
  "eje-memoria-democratica": ["ley-memoria-democratica", "Ley de memoria democrática"],
  "eje-instituciones-reglas": ["gobierno-rendir-cuentas-congreso", "Que el Gobierno rinda cuentas ante el Congreso"],
  "eje-israel-palestina": ["israel-gaza-embargo-armas", "Israel, Gaza y el embargo de armas"],
  "eje-defensa-otan": ["gasto-militar-otan-ucrania", "Gasto militar, OTAN y Ucrania"],
  "eje-sahara-marruecos": ["sahara-occidental-marruecos", "Sáhara Occidental y Marruecos"],
  "eje-venezuela-latam": ["venezuela-cuba-nicaragua-sanciones", "Venezuela, Cuba y Nicaragua"],
};

export function slugify(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/^-+|-+$/gu, "");
}

export const partySlug = (partyId) => PARTY_SLUGS[partyId] || slugify(partyId);
export const partyPagePath = (partyId) => `${VOTA_PATHS.parties}${partySlug(partyId)}/`;
export const questionSlug = (statementId) => QUESTION_SEO[statementId]?.[0] || slugify(String(statementId).replace(/^eje-/u, ""));
export const questionTitle = (statement) => QUESTION_SEO[statement.statement_id]?.[1] || statement.theme || statement.text;
export const hasQuestionPage = (statementId) => Boolean(QUESTION_SEO[statementId]);
export const questionPagePath = (statementId) => `/citizen/vota/pregunta/${questionSlug(statementId)}/`;
export const topicSlug = (topic) => slugify(topic.label);
export const topicPagePath = (topic) => `${VOTA_PATHS.topics}${topicSlug(topic)}/`;
export const ogPath = (id) => `/citizen/vota/og/${id}.png`;
