import VotingAidClient from "../../VotingAidClient";
import { SITE_ORIGIN, hookImagePath, hookPagePath, hookStatements, loadVotingAidSnapshot, statementHook, statementVersion } from "../../votingAidHooks.mjs";

// One shareable page per curated statement: same game, opened on that question, with its own OG card.
export const dynamicParams = false;

export async function generateStaticParams() {
  return hookStatements().map((st) => ({ statementId: st.statement_id }));
}

export async function generateMetadata({ params }) {
  const { statementId } = await params;
  const statement = hookStatements().find((st) => st.statement_id === statementId);
  const hook = statementHook(statement);
  const title = `«${hook.text}» ¿De acuerdo?`;
  const description = "Responde y descubre qué partidos votaron como tú en el Congreso. Cada voto, con su enlace oficial.";
  const url = `${SITE_ORIGIN}${hookPagePath(statementId)}`;
  const image = { url: `${SITE_ORIGIN}${hookImagePath(statementId)}`, width: 1200, height: 630, alt: hook.text };
  return {
    title: `${title} | Vota Con La Chola`,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES", images: [image] },
    twitter: { card: "summary_large_image", title, description, images: [image.url] },
  };
}

export default async function VotingAidHookPage({ params }) {
  const { statementId } = await params;
  // Statements of earlier versions open in that version, so old shared links still work.
  const version = statementVersion(statementId);
  return <VotingAidClient snapshot={loadVotingAidSnapshot(version.id)} startStatementId={statementId} versionId={version.id} />;
}
