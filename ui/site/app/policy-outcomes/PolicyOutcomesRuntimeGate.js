"use client";

import { useEffect, useState } from "react";

import { verifyPolicyOutcomesRuntimePackage } from "./runtime-verification.mjs";
import styles from "./policy-outcomes.module.css";


const VERIFY_TIMEOUT_MS = 45_000;

export default function PolicyOutcomesRuntimeGate({ children }) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ phase: "checking", errors: [] });

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), VERIFY_TIMEOUT_MS);
    setState({ phase: "checking", errors: [] });
    verifyPolicyOutcomesRuntimePackage({ signal: controller.signal })
      .then((result) => {
        if (!active) return;
        setState({
          phase: result.ok ? "verified" : "blocked",
          errors: result.errors || [],
        });
      })
      .catch(() => {
        if (active) setState({ phase: "blocked", errors: ["runtime_verification:failed"] });
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  if (state.phase === "verified") {
    return <div className={`policy-outcomes-runtime policy-outcomes-runtime--verified ${styles.runtimeVerified}`}>{children}</div>;
  }

  const blocked = state.phase === "blocked";
  return (
    <main className={`shell policy-outcomes-runtime-gate policy-outcomes-runtime-gate--${blocked ? "blocked" : "checking"} ${styles.page} ${styles.runtimeGate}`}>
      <section
        className={`policy-outcomes-runtime-gate__panel policy-outcomes-runtime-gate__panel--${state.phase} ${styles.statePanel} ${styles.runtimePhasePanel}`}
        aria-labelledby="policy-outcomes-runtime-title"
        aria-live="polite"
        key={state.phase}
        role="status"
      >
        <div className={`policy-outcomes-runtime-gate__marker ${styles.stateMarker}`} aria-hidden="true">
          {blocked ? "!" : "…"}
        </div>
        <div className="policy-outcomes-runtime-gate__copy">
          <p className={`policy-outcomes-runtime-gate__eyebrow ${styles.eyebrow}`}>
            {blocked ? "Bloqueo preventivo" : "Verificación local en curso"}
          </p>
          <h1 className={`policy-outcomes-runtime-gate__title ${styles.sectionTitle}`} id="policy-outcomes-runtime-title">
            {blocked
              ? "La evidencia pública no supera la verificación en este navegador"
              : "Verificando estado, manifest y todos los activos de evidencia"}
          </h1>
          <p className={`policy-outcomes-runtime-gate__description ${styles.sectionCopy}`}>
            {blocked
              ? "No se muestran candidatos, conteos, fuentes ni conclusiones. Todos los bytes deben coincidir con la identidad de release fijada."
              : "Los hechos permanecen ocultos hasta completar bytes y SHA-256 del paquete íntegro."}
          </p>
          {blocked ? (
            <button
              className={`policy-outcomes-runtime-gate__retry ${styles.runtimeRetry}`}
              onClick={() => setAttempt((value) => value + 1)}
              type="button"
            >
              Reintentar verificación
            </button>
          ) : null}
        </div>
      </section>
    </main>
  );
}
