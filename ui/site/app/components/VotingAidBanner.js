"use client";

import { usePathname } from "next/navigation";
import { stripBasePath, withBasePath } from "../path-utils.mjs";

const VOTING_AID_PATH = "/citizen/vota/";
// Every voting-aid page (test, versions, share pages, Explorar) already carries the section nav.
const TEST_PAGE = /^\/citizen\/vota\//u;

export default function VotingAidBanner() {
  const pathname = stripBasePath(usePathname() || "/");
  // The tool does not need an ad for itself (and a share page must not lure people off its question).
  if (TEST_PAGE.test(pathname.replace(/\/?$/u, "/"))) {
    return null;
  }

  return (
    <aside className="voting-aid-banner" aria-label="Herramienta de decisión de voto">
      <a className="voting-aid-banner__link" href={withBasePath(VOTING_AID_PATH)}>
        <span className="voting-aid-banner__badge" aria-hidden="true">🗳️</span>
        <span className="voting-aid-banner__text">
          <strong>¿A quién votar?</strong>
          <span className="voting-aid-banner__note"> Compara tus opiniones con votos reales del Congreso.</span>
        </span>
        <span className="voting-aid-banner__cta">
          Empezar<span aria-hidden="true"> →</span>
        </span>
      </a>
    </aside>
  );
}
