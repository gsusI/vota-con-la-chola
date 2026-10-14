"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { stripBasePath, withBasePath } from "../../path-utils.mjs";

// The test itself: current version (/citizen/vota/), earlier ones (/v1/) and per-question share pages (/t/<id>/).
const TEST_PATH = /^\/citizen\/vota\/(?:v\d+\/)?$/u;
const EXPLORE_PATH = /^\/citizen\/vota\/(?:explorar|partidos|diputados|temas|votacion|mapa)\//u;
// Test views the shell links to, by their `?p=` value (see VIEW_PARAM in VotingAidClient).
const TAB_VIEW = { test: "play", resultados: "results", respuestas: "review" };
const PARAM_TAB = { jugar: "test", resultados: "resultados", partido: "resultados", respuestas: "respuestas" };

/**
 * Contract with the test client (VotingAidClient):
 * - on the test page, clicking Test / Resultados / Respuestas does not reload: the shell dispatches
 *   `vota:navigate` with `{ view }` ("play" | "results" | "review") and the client switches view;
 * - the client dispatches `vota:view` with `{ view }` whenever its view changes, so the right tab is lit.
 */
export const NAVIGATE_EVENT = "vota:navigate";
export const VIEW_EVENT = "vota:view";

function viewTab(view) {
  if (view === "results" || view === "party") return "resultados";
  if (view === "review") return "respuestas";
  return "test";
}

function Icon({ name }) {
  const common = { "aria-hidden": true, width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  if (name === "test") {
    return (
      <svg {...common}>
        <rect x="4" y="3" width="16" height="18" rx="2" />
        <path d="M8 9l2 2 4-4M8 16h8" />
      </svg>
    );
  }
  if (name === "resultados") {
    return (
      <svg {...common}>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </svg>
    );
  }
  if (name === "explorar") {
    return (
      <svg {...common}>
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-4-4" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
    </svg>
  );
}

export default function VotaShell() {
  const pathname = stripBasePath(usePathname() || "/").replace(/\/?$/u, "/");
  const onTest = TEST_PATH.test(pathname);
  const testBase = onTest ? pathname : "/citizen/vota/";
  const [testTab, setTestTab] = useState("test");

  useEffect(() => {
    if (!onTest) return undefined;
    const sync = () => setTestTab(PARAM_TAB[new URLSearchParams(window.location.search).get("p")] || "test");
    const onView = (e) => setTestTab(viewTab(e.detail?.view));
    sync();
    window.addEventListener("popstate", sync);
    window.addEventListener(VIEW_EVENT, onView);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener(VIEW_EVENT, onView);
    };
  }, [onTest, pathname]);

  const active = EXPLORE_PATH.test(pathname) ? "explorar" : onTest ? testTab : pathname.startsWith("/citizen/vota/t/") ? "test" : "";
  const tabs = [
    { id: "test", label: "Test", href: testBase },
    { id: "resultados", label: "Resultados", href: `${testBase}?p=resultados` },
    { id: "explorar", label: "Explorar", href: "/citizen/vota/explorar/" },
    { id: "respuestas", label: "Respuestas", href: `${testBase}?p=respuestas` },
  ];

  function onClick(event, tab) {
    const view = TAB_VIEW[tab.id];
    if (!onTest || !view || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    window.dispatchEvent(new CustomEvent(NAVIGATE_EVENT, { detail: { view } }));
  }

  const links = (cls) =>
    tabs.map((tab) => (
      <a
        aria-current={active === tab.id ? "page" : undefined}
        className={cls}
        href={withBasePath(tab.href)}
        key={tab.id}
        onClick={(e) => onClick(e, tab)}
      >
        {cls === "v-tabbar__item" ? <Icon name={tab.id} /> : null}
        {tab.label}
      </a>
    ));

  return (
    <>
      <header className="v-top">
        <div className="v-top__inner">
          <a className="v-brand" href={withBasePath("/citizen/vota/")}>
            <span aria-hidden="true" className="v-brand__mark">
              V
            </span>
            Vota con la chola
          </a>
          <nav aria-label="Secciones" className="v-nav">
            {links("v-nav__item")}
          </nav>
          <p className="v-top__meta">
            Congreso · XV legislatura · <a href={withBasePath("/citizen/vota/metodologia/")}>Cómo funciona</a>
          </p>
        </div>
      </header>
      <nav aria-label="Secciones" className="v-tabbar">
        {links("v-tabbar__item")}
      </nav>
    </>
  );
}
