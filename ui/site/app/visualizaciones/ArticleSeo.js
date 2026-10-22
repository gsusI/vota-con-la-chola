// Search layer shared by the five data articles: metadata, JSON-LD, a visible FAQ and related reading.
// The copy comes from articleSeo.mjs, computed from the same published JSON the page renders.
import { readPublicJson } from "../static-snapshot.mjs";
import { JsonLd, articleLd, breadcrumbLd, datasetLd, faqLd, pageMetadata } from "../seo";
import { ARTICLES, articleSeo, cardPath } from "./articleSeo.mjs";

export function loadArticleSeo(slug) {
  const data = readPublicJson(`visualizaciones/data/${slug}.json`, null);
  if (!data) throw new Error(`Missing visualizaciones/data/${slug}.json`);
  return articleSeo(slug, data);
}

export function vizArticleMetadata(slug) {
  const seo = loadArticleSeo(slug);
  return pageMetadata({
    path: seo.path,
    title: seo.title,
    description: seo.description,
    image: { path: cardPath(slug), alt: seo.headline },
    type: "article",
    keywords: seo.keywords,
    publishedTime: seo.datePublished,
    modifiedTime: seo.dateModified,
  });
}

function structuredData(seo) {
  return [
    breadcrumbLd([
      { name: "Inicio", path: "/" },
      { name: "Visualizaciones", path: "/visualizaciones/" },
      { name: ARTICLES[seo.slug].topic, path: seo.path },
    ]),
    articleLd({
      path: seo.path,
      headline: seo.headline,
      description: seo.description,
      image: cardPath(seo.slug),
      datePublished: seo.datePublished,
      dateModified: seo.dateModified,
      about: seo.about,
      citations: seo.sources,
    }),
    datasetLd({
      path: seo.path,
      name: `${seo.topic} en España: datos de «${seo.linkText}»`,
      description: `${seo.description} Cada valor con su fuente oficial, fecha de consulta y huella SHA-256 del fichero original.`,
      keywords: seo.keywords,
      temporalCoverage: seo.temporalCoverage,
      distribution: seo.downloads,
      sources: seo.sources,
      dateModified: seo.dateModified,
    }),
    faqLd(seo.faqs),
  ];
}

// Placed at the end of each article: questions people search, answered with the page's own numbers, then related reading.
export default function ArticleSeo({ slug }) {
  const seo = loadArticleSeo(slug);
  const related = [
    ...seo.related.map((other) => ({ href: `/visualizaciones/${other}/`, anchor: ARTICLES[other].linkText })),
    ...seo.extra.map((item) => ({ href: item.href, anchor: item.anchor, note: item.note })),
  ];
  return (
    <>
      <section className="vizFaq" id="preguntas" aria-labelledby="preguntas-title">
        <h2 id="preguntas-title">Preguntas frecuentes</h2>
        {seo.faqs.map((faq) => (
          <div key={faq.q} className="vizFaq__item">
            <h3>{faq.q}</h3>
            <p>{faq.a}</p>
          </div>
        ))}
      </section>
      <nav className="vizRelated" aria-labelledby="sigue-leyendo-title">
        <h2 id="sigue-leyendo-title">Sigue leyendo</h2>
        <ul>
          {related.map((item) => (
            <li key={item.href}>
              <a href={item.href}>{item.anchor}</a>
              {item.note ? <span> {item.note}</span> : null}
            </li>
          ))}
        </ul>
      </nav>
      <JsonLd data={structuredData(seo)} />
    </>
  );
}
