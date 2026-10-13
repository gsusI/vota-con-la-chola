"use client";

import Link from "next/link";
import { useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { resolveBasePath, stripBasePath, withBasePath } from "../path-utils.mjs";

function normalizeSegment(value) {
  return String(value || "")
    .trim()
    .replace(/\+/g, " ");
}

function decodeLabel(value) {
  return decodeURIComponent(normalizeSegment(value))
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatBreadcrumb(segment, index, segments) {
  const map = {
    "parliamentary-accountability": "Rendición de cuentas",
    discipline: "Disciplina",
    attendance: "Asistencia",
    outcomes: "Resultados",
    coalitions: "Coaliciones",
    people: "Personas",
    xray: "Radiografía",
    party: "Partido",
    institution: "Institución",
    ambito: "Ámbito",
    territorio: "Territorio",
    cargo: "Cargo",
    "initiative-lifecycle": "Legislación",
    "initiative-id": "Iniciativa",
    "political-positions": "Posturas",
    "policy-outcomes": "Estado de resultados",
    "legal-sanctions": "Cumplimiento legal",
    "obstruction-tracker": "Obstrucción de datos",
    transparency: "Transparencia",
    promises: "Promesas",
    comparisons: "Dicho frente a hecho",
    spending: "Dinero público",
    agreements: "Acuerdos y reuniones",
    geopolitics: "Geopolítica",
    indicators: "Indicadores",
    "actor-graph": "Grafo de actores",
    questions: "Q&A",
    citizen: "Ciudadanía",
    vota: "¿Con quién coincides?",
    metodologia: "Cómo se hizo",
    leaderboards: "Clasificaciones",
    temas: "Mapa por temas",
    diputados: "Diputados",
  };

  // Voting-aid version and share pages: /citizen/vota/v1/ and /citizen/vota/t/<statement>/.
  if (segments[index - 1] === "vota" && /^v\d+$/u.test(segment)) {
    return `Versión ${segment.slice(1)}`;
  }
  if (segments[index - 1] === "vota" && segment === "t") {
    return "Pregunta";
  }
  if (segments[index - 1] === "t" && segments[index - 2] === "vota") {
    return null;
  }

  const direct = map[segment];
  if (direct) {
    return direct;
  }

  const isDynamicId = /^\d+$/u.test(segment);
  if (isDynamicId && segments[index - 1] === "xray") {
    return `${segments[index - 2] === "initiative-lifecycle" ? "Iniciativa" : "Detalle"} ${segment}`;
  }
  if (isDynamicId && index >= 1 && segments[index - 1] === "people") {
    return `Persona ${segment}`;
  }

  return decodeLabel(segment);
}

export default function Breadcrumbs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const basePath = resolveBasePath();

  const initiativeParam = searchParams.get("initiative");

  const crumbs = useMemo(() => {
    const rawSegments = normalizeSegment(stripBasePath(pathname || "", basePath)).split("/").filter(Boolean);
    const withDynamic = [...rawSegments];

    const initiativeSegment = !withDynamic.includes("initiative-lifecycle") && initiativeParam ? "initiative" : null;
    if (initiativeSegment && !withDynamic.includes("xray")) {
      withDynamic.push(initiativeSegment);
      withDynamic.push(initiativeParam);
    }

    const out = [
      {
        href: withBasePath("/", basePath),
        label: "Inicio",
      },
    ];

    let cumulative = "";
    for (const [index, segment] of withDynamic.entries()) {
      cumulative += `/${segment}`;
      const label = formatBreadcrumb(segment, index, withDynamic);
      // null: a slug with no readable name (the page itself shows it), so the trail stops at its parent.
      if (label === null) continue;
      out.push({
        href: withBasePath(cumulative, basePath),
        label,
      });
    }

    return out;
  }, [basePath, pathname, initiativeParam]);

  if (crumbs.length <= 1) {
    return null;
  }
  // The citizen pages (voting aid included) use a narrower column; line the trail up with it.
  const narrow = /^\/citizen(\/|$)/u.test(stripBasePath(pathname || "", basePath));

  return (
    <nav className={`breadcrumbs site-breadcrumbs${narrow ? " site-breadcrumbs--narrow" : ""}`} aria-label="Miga de pan">
      <ol className="site-breadcrumbs__list">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li className="site-breadcrumbs__item" key={`${crumb.href}-${index}`}>
              {isLast ? (
                <span className="site-breadcrumbs__current">{crumb.label}</span>
              ) : (
                <Link className="site-breadcrumbs__link" href={crumb.href}>{crumb.label}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
