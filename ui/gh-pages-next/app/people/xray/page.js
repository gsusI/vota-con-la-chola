import Link from "next/link";
import { buildXrayKindSummaries, loadXrayPayload } from "./xrayServerData.mjs";

export const metadata = {
  title: "Perfiles | Vota Con La Chola",
  description: "Explora perfiles por partido, institución, ámbito, territorio y cargo.",
};

function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return "0";
  }
  return parsed.toLocaleString("es-ES");
}

export default function XrayHubPage() {
  const payload = loadXrayPayload();
  const snapshotDate = String(payload?.meta?.snapshot_date || "").trim();
  const summaries = buildXrayKindSummaries(payload);

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Personas</p>
        <h1>Perfiles</h1>
        <p className="sub">
          Entra por el tipo de agrupación que mejor te sirva para seguir personas, mandatos y actividad pública.
        </p>
        <div className="chips">
          <span className="chip">Vistas: {summaries.length}</span>
          <span className="chip">Publicación: {snapshotDate || "—"}</span>
        </div>
        <p className="sub">
          <Link href="/people/">Volver a Directorio</Link>
        </p>
      </section>

      {!payload ? (
        <section className="card block">
          <div className="blockHead">
            <h2>Perfiles no disponibles</h2>
            <p className="sub">
              Falta el archivo publicado `people/data/xray.json`, así que este índice no puede mostrar las agrupaciones.
            </p>
          </div>
        </section>
      ) : (
        <section className="card block">
          <div className="blockHead">
            <h2>Agrupaciones disponibles</h2>
            <p className="sub">
              Cada vista abre un listado navegable y permite bajar a un grupo concreto mediante `?group=`.
            </p>
          </div>
          <div className="grid">
            {summaries.map((summary) => (
              <Link key={summary.kind} className="tile" href={summary.href}>
                <span className="tileTitle">{summary.pluralLabel}</span>
                <span className="tileNote">{summary.description}</span>
                <span className="chip">Grupos: {formatInt(summary.groupCount)}</span>
                {summary.topGroupLabel ? (
                  <span className="chip">
                    Mayor grupo: {summary.topGroupLabel} ({formatInt(summary.topGroupPeople)})
                  </span>
                ) : null}
                <span className="chip">Última acción: {summary.latestActionDate || "—"}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
