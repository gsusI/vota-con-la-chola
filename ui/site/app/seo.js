// Shared SEO helpers: one metadata shape (canonical + Open Graph + X card) and schema.org JSON-LD builders.
// Every indexable page should go through pageMetadata so canonical, og:url and the share card never drift apart.
import { SITE_ORIGIN, absoluteSiteUrl, siteCardImage } from "./path-utils.mjs";

export const SITE_NAME = "Vota Con La Chola";
const BRAND_SUFFIX = ` | ${SITE_NAME}`;

function withoutBrand(title) {
  return String(title).endsWith(BRAND_SUFFIX) ? String(title).slice(0, -BRAND_SUFFIX.length) : String(title);
}

// image: { path, alt, width?, height? } for a site-relative PNG (e.g. an app/**/og route), or omitted for the site card.
export function pageMetadata({ path, title, description, image, type = "website", robots, keywords, publishedTime, modifiedTime }) {
  const url = absoluteSiteUrl(path);
  const fullTitle = String(title).endsWith(BRAND_SUFFIX) ? title : `${title}${BRAND_SUFFIX}`;
  const shareTitle = withoutBrand(title);
  const card = image
    ? { url: absoluteSiteUrl(image.path), width: image.width || 1200, height: image.height || 630, alt: image.alt || shareTitle }
    : siteCardImage();
  const openGraph = { type, url, title: shareTitle, description, siteName: SITE_NAME, locale: "es_ES", images: [card] };
  if (type === "article") {
    if (publishedTime) openGraph.publishedTime = publishedTime;
    if (modifiedTime) openGraph.modifiedTime = modifiedTime;
  }
  const metadata = {
    title: fullTitle,
    description,
    alternates: { canonical: url },
    openGraph,
    twitter: { card: "summary_large_image", title: shareTitle, description, images: [card.url] },
  };
  if (keywords?.length) metadata.keywords = keywords;
  if (robots) metadata.robots = robots;
  return metadata;
}

// Renders a schema.org graph; "<" is escaped so data strings can never close the script tag.
export function JsonLd({ data }) {
  const graph = Array.isArray(data) ? { "@context": "https://schema.org", "@graph": data } : { "@context": "https://schema.org", ...data };
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(graph).replace(/</g, "\\u003c") }} />;
}

export const ORGANIZATION_ID = `${SITE_ORIGIN}/#organization`;
export const WEBSITE_ID = `${SITE_ORIGIN}/#website`;

export function organizationLd() {
  return {
    "@type": "Organization",
    "@id": ORGANIZATION_ID,
    name: SITE_NAME,
    url: `${SITE_ORIGIN}/`,
    logo: absoluteSiteUrl("/og/site.png"),
    description: "Datos públicos de España con la fuente oficial a un clic: qué se votó, qué se gastó y quién responde.",
  };
}

export function websiteLd() {
  return {
    "@type": "WebSite",
    "@id": WEBSITE_ID,
    name: SITE_NAME,
    url: `${SITE_ORIGIN}/`,
    inLanguage: "es-ES",
    publisher: { "@id": ORGANIZATION_ID },
  };
}

// crumbs: [{ name, path }], root first; the last one is the page itself.
export function breadcrumbLd(crumbs) {
  return {
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, i) => ({ "@type": "ListItem", position: i + 1, name: crumb.name, item: absoluteSiteUrl(crumb.path) })),
  };
}

// The citable unit of a visualization: headline = its finding with the number, dates as YYYY-MM-DD.
export function articleLd({ path, headline, description, image, datePublished, dateModified, about, citations }) {
  const ld = {
    "@type": "Article",
    "@id": `${absoluteSiteUrl(path)}#article`,
    mainEntityOfPage: absoluteSiteUrl(path),
    headline: String(headline).slice(0, 110),
    description,
    inLanguage: "es-ES",
    isAccessibleForFree: true,
    author: { "@id": ORGANIZATION_ID },
    publisher: { "@id": ORGANIZATION_ID },
    image: image ? absoluteSiteUrl(image) : absoluteSiteUrl("/og/site.png"),
  };
  if (datePublished) ld.datePublished = datePublished;
  if (dateModified || datePublished) ld.dateModified = dateModified || datePublished;
  if (about?.length) ld.about = about.map((name) => ({ "@type": "Thing", name }));
  if (citations?.length) ld.citation = citations.map((c) => ({ "@type": "CreativeWork", name: c.name, url: c.url }));
  return ld;
}

// Downloadable data behind a page (Google Dataset Search): distribution = [{ path or url, format }].
export function datasetLd({ path, name, description, keywords, temporalCoverage, spatialCoverage = "España", distribution, sources, dateModified, license }) {
  const ld = {
    "@type": "Dataset",
    "@id": `${absoluteSiteUrl(path)}#dataset`,
    name,
    description,
    url: absoluteSiteUrl(path),
    inLanguage: "es-ES",
    isAccessibleForFree: true,
    creator: { "@id": ORGANIZATION_ID },
    publisher: { "@id": ORGANIZATION_ID },
    spatialCoverage: { "@type": "Place", name: spatialCoverage },
  };
  if (keywords?.length) ld.keywords = keywords;
  if (temporalCoverage) ld.temporalCoverage = temporalCoverage;
  if (dateModified) ld.dateModified = dateModified;
  if (license) ld.license = license;
  if (distribution?.length) {
    ld.distribution = distribution.map((d) => ({
      "@type": "DataDownload",
      encodingFormat: d.format,
      contentUrl: d.url || absoluteSiteUrl(d.path),
    }));
  }
  if (sources?.length) ld.isBasedOn = sources.map((s) => ({ "@type": "CreativeWork", name: s.name, url: s.url }));
  return ld;
}

// Interactive tools (simulator, voting aid): free browser apps.
export function webApplicationLd({ path, name, description, category = "EducationalApplication", image, featureList }) {
  const ld = {
    "@type": "WebApplication",
    "@id": `${absoluteSiteUrl(path)}#app`,
    name,
    description,
    url: absoluteSiteUrl(path),
    applicationCategory: category,
    operatingSystem: "Cualquiera (navegador web)",
    inLanguage: "es-ES",
    isAccessibleForFree: true,
    offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
    publisher: { "@id": ORGANIZATION_ID },
  };
  if (image) ld.image = absoluteSiteUrl(image);
  if (featureList?.length) ld.featureList = featureList;
  return ld;
}

// faqs: [{ q, a }] with plain-text answers that are also visible on the page (Google requires visible content).
export function faqLd(faqs) {
  return {
    "@type": "FAQPage",
    mainEntity: faqs.map(({ q, a }) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
  };
}
