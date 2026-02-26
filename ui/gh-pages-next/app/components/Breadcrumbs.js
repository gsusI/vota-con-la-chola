"use client";

import Link from "next/link";
import { useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

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
    "parliamentary-accountability": "Accountability",
    discipline: "Disciplina",
    attendance: "Asistencia",
    outcomes: "Resultados",
    coalitions: "Coaliciones",
    people: "Personas",
    xray: "X-ray",
    party: "Partido",
    institution: "Institución",
    ambito: "Ámbito",
    territorio: "Territorio",
    cargo: "Cargo",
    "initiative-lifecycle": "Legislación",
    "initiative-id": "Iniciativa",
    "political-positions": "Posturas",
    "policy-outcomes": "Resultados",
    "legal-sanctions": "Cumplimiento legal",
  };

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
    const rawSegments = normalizeSegment(pathname || "").split("/").filter(Boolean);
    const withDynamic = [...rawSegments];

    const initiativeSegment = !withDynamic.includes("initiative-lifecycle") && initiativeParam ? "initiative" : null;
    if (initiativeSegment && !withDynamic.includes("xray")) {
      withDynamic.push(initiativeSegment);
      withDynamic.push(initiativeParam);
    }

    const out = [
      {
        href: `${basePath}/`,
        label: "Inicio",
      },
    ];

    let cumulative = "";
    for (const [index, segment] of withDynamic.entries()) {
      cumulative += `/${segment}`;
      out.push({
        href: `${basePath}${cumulative}`,
        label: formatBreadcrumb(segment, index, withDynamic),
      });
    }

    return out;
  }, [basePath, pathname, initiativeParam]);

  if (crumbs.length <= 1) {
    return null;
  }

  return (
    <nav className="breadcrumbs" aria-label="Miga de pan">
      <ol>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={`${crumb.href}-${index}`}>
              {isLast ? <span>{crumb.label}</span> : <Link href={crumb.href}>{crumb.label}</Link>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
