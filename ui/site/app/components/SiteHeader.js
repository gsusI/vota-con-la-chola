"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { siteSections, withBasePath } from "../siteCatalog.mjs";

function isActive(pathname, href) {
  if (!pathname) {
    return false;
  }
  if (href === "/") {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(href);
}

export default function SiteHeader() {
  const pathname = usePathname() || "/";

  return (
    <header className="siteHeaderWrap">
      <div className="siteHeader card">
        <div className="siteHeaderTop">
          <div className="siteBrand">
            <Link className="siteBrandLink" href={withBasePath("/")}>
              Vota Con La Chola
            </Link>
            <p className="siteBrandNote">
              Sigue temas, actores, decisiones y resultados con evidencias y datos publicados.
            </p>
          </div>
          <div className="siteUtilityLinks">
            <Link className="siteUtilityLink" href={withBasePath("/citizen/")}>
              Ciudadanía
            </Link>
            <Link className="siteUtilityLink" href={withBasePath("/methods/datasets/")}>
              Archivos
            </Link>
          </div>
        </div>
        <nav className="siteNav" aria-label="Secciones principales">
          {siteSections.map((section) => (
            <Link
              key={section.id}
              className="siteNavLink"
              data-active={isActive(pathname, section.href) ? "true" : "false"}
              href={withBasePath(section.href)}
            >
              <span className="siteNavLabel">{section.navLabel}</span>
              <span className="siteNavNote">{section.title}</span>
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
