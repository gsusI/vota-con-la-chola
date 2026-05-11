import { notFound } from "next/navigation";
import {
  buildOfficialLinks,
  buildSiteImageUrl,
  caveatSeverityClass,
  formatInt,
  formatVoteDate,
  freshnessToneClass,
  loadVoteExplainerManifest,
  loadVoteExplainerPayload,
  percentWidth,
  resultToneClass,
  topVisibleCaveat,
  withBasePath,
} from "../pageData.mjs";

export const dynamicParams = false;

export async function generateStaticParams() {
  const manifest = loadVoteExplainerManifest();
  return (manifest.votes || []).map((vote) => ({ publicVoteId: vote.public_vote_id }));
}

export async function generateMetadata({ params }) {
  const { publicVoteId } = await params;
  const payload = loadVoteExplainerPayload(publicVoteId);
  if (!payload) {
    return {
      title: "Voto no encontrado | Vota Con La Chola",
      description: "No encontramos esa votación en el corte público actual.",
    };
  }
  return {
    title: payload.social?.title || "Explicador de votos | Vota Con La Chola",
    description: payload.social?.description || "Página pública y auditable de una votación concreta.",
    alternates: {
      canonical: payload.social?.canonical_url || undefined,
    },
    openGraph: {
      title: payload.social?.title || "Explicador de votos | Vota Con La Chola",
      description: payload.social?.description || "Página pública y auditable de una votación concreta.",
      url: payload.social?.canonical_url || undefined,
      type: "article",
      siteName: "Vota Con La Chola",
      locale: "es_ES",
      images: [buildSiteImageUrl()],
    },
    twitter: {
      card: "summary",
      title: payload.social?.title || "Explicador de votos | Vota Con La Chola",
      description: payload.social?.description || "Página pública y auditable de una votación concreta.",
      images: [buildSiteImageUrl()],
    },
  };
}

function TotalsCard({ label, value }) {
  return (
    <div className="kpiCard">
      <span className="kpiLabel">{label}</span>
      <span className="kpiValue">{formatInt(value)}</span>
    </div>
  );
}

function GroupVoteBar({ group }) {
  const total = Number(group?.total || 0);
  return (
    <div className="voteBar" aria-hidden="true">
      <span className="voteBarYes" style={{ width: percentWidth(group?.yes, total) }} />
      <span className="voteBarNo" style={{ width: percentWidth(group?.no, total) }} />
      <span className="voteBarAbstain" style={{ width: percentWidth(group?.abstain, total) }} />
      <span className="voteBarNoVote" style={{ width: percentWidth(group?.no_vote, total) }} />
      <span className="voteBarOther" style={{ width: percentWidth(group?.other, total) }} />
    </div>
  );
}

export default async function VoteExplainerDetailPage({ params }) {
  const { publicVoteId } = await params;
  const payload = loadVoteExplainerPayload(publicVoteId);
  if (!payload) {
    return notFound();
  }

  const event = payload.event || {};
  const totals = payload.totals || {};
  const groups = Array.isArray(payload.groups) ? payload.groups : [];
  const initiative = payload.initiative || null;
  const caveats = Array.isArray(payload.caveats) ? payload.caveats : [];
  const officialLinks = buildOfficialLinks(payload);
  const freshness = payload.meta?.freshness || {};
  const topCaveat = topVisibleCaveat(caveats);
  const explorerLink = payload.audit_links?.explorer_votaciones ? withBasePath(payload.audit_links.explorer_votaciones) : "";
  const snapshotLink = payload.audit_links?.source_snapshot ? withBasePath(payload.audit_links.source_snapshot) : "";

  return (
    <main className="shell">
      <section className="hero card explainerHero">
        <p className="eyebrow">Explicador de votos</p>
        <h1>{event.headline || "Votación sin titular legible"}</h1>
        <p className="sub">
          {event.chamber || "Institución parlamentaria"} · {formatVoteDate(event.vote_date)} · página pública y auditable de una votación concreta.
        </p>
        <div className="chips">
          <span className={`chip ${resultToneClass(payload.result?.status)}`}>{payload.result?.label || "Resultado no disponible"}</span>
          <span className={`chip ${freshnessToneClass(freshness.tier)}`}>Corte {freshness.label || "desconocido"}</span>
          <span className="chip">Evento: {payload.meta?.public_vote_id}</span>
        </div>
        {event.subtitle ? (
          <p className="sub" style={{ marginTop: 12 }}>
            {event.subtitle}
          </p>
        ) : null}
        <p className="sub" style={{ marginTop: 12 }}>
          {officialLinks[0] ? <a href={officialLinks[0].url}>Abrir fuente oficial principal</a> : "No hay fuente oficial directa enlazada en este corte."}
          {explorerLink ? (
            <span style={{ marginLeft: "10px" }}>
              <a href={explorerLink}>Auditar en el explorador de votaciones</a>
            </span>
          ) : null}
        </p>
        {topCaveat ? <p className={`voteNotice ${caveatSeverityClass(topCaveat.severity)}`}>{topCaveat.detail}</p> : null}
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Qué se votaba</h2>
        </div>
        <div className="voteMetaGrid">
          <div className="voteMetaCard">
            <span className="kpiLabel">Titular del voto</span>
            <strong>{event.title || event.headline || "Sin título"}</strong>
          </div>
          <div className="voteMetaCard">
            <span className="kpiLabel">Expediente</span>
            <strong>{initiative?.expediente || event.expediente_text || "No disponible"}</strong>
          </div>
        </div>
        {initiative?.title ? (
          <p className="sub" style={{ marginTop: 12 }}>
            <strong>Iniciativa enlazada:</strong> {initiative.title}
          </p>
        ) : null}
        {event.expediente_text ? (
          <p className="sub" style={{ marginTop: 12 }}>
            {event.expediente_text}
          </p>
        ) : null}
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Qué pasó</h2>
        </div>
        <div className="kpiGrid">
          <TotalsCard label="Sí" value={totals.yes} />
          <TotalsCard label="No" value={totals.no} />
          <TotalsCard label="Abstención" value={totals.abstain} />
          <TotalsCard label="No vota" value={totals.no_vote} />
          <TotalsCard label="Presentes" value={totals.present} />
        </div>
        <p className="sub" style={{ marginTop: 12 }}>
          {payload.result?.summary_text || "Sin resumen numérico."}
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Cómo votaron los grupos</h2>
        </div>
        <p className="sub">
          Vista pública resumida de grupos parlamentarios. No equivale a una votación nominal completa.
        </p>
        <div className="voteGroupGrid">
          {groups.map((group) => (
            <article className="voteGroupCard" key={`${group.group_code}-${group.total}`}>
              <div className="voteGroupHead">
                <strong>{group.group_code || "Sin grupo"}</strong>
                <span>Total {formatInt(group.total)}</span>
              </div>
              <GroupVoteBar group={group} />
              <p className="voteBreakdownText">
                Sí {formatInt(group.yes)} · No {formatInt(group.no)} · Abst. {formatInt(group.abstain)} · No vota {formatInt(group.no_vote)}
                {Number(group.other || 0) > 0 ? ` · Otras ${formatInt(group.other)}` : ""}
              </p>
            </article>
          ))}
        </div>
        {explorerLink ? (
          <p className="sub" style={{ marginTop: 12 }}>
            <a href={explorerLink}>Abrir esta votación en el explorador de votaciones</a>
          </p>
        ) : null}
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Fuentes oficiales y documentos</h2>
        </div>
        {officialLinks.length ? (
          <div className="voteLinkList">
            {officialLinks.map((item) => (
              <a className="voteLinkCard" href={item.url} key={`${item.label}:${item.url}`}>
                <span className="kpiLabel">{item.label}</span>
                <span>{item.url}</span>
              </a>
            ))}
          </div>
        ) : (
          <p className="sub">Todavía no hay enlaces oficiales directos en este corte público.</p>
        )}
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Salvedades metodológicas</h2>
        </div>
        <div className="voteCaveatGrid">
          {caveats.map((caveat) => (
            <article className={`voteNotice ${caveatSeverityClass(caveat.severity)}`} key={caveat.code}>
              <strong>{caveat.label}</strong>
              <p>{caveat.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Auditoría</h2>
        </div>
        <div className="voteLinkList">
          {explorerLink ? (
            <a className="voteLinkCard" href={explorerLink}>
              <span className="kpiLabel">Explorador</span>
              <span>Auditar esta votación en el explorador de votaciones</span>
            </a>
          ) : null}
          {snapshotLink ? (
            <a className="voteLinkCard" href={snapshotLink}>
              <span className="kpiLabel">Corte fuente</span>
              <span>{payload.meta?.source_snapshot_path}</span>
            </a>
          ) : null}
        </div>
        <p className="monoInline" style={{ marginTop: 12 }}>
          vote_event_id: {payload.meta?.vote_event_id}
        </p>
      </section>
    </main>
  );
}
