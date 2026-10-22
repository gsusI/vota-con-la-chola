import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { mapAxes } from "../mapModel.mjs";
import { axisParties, formatCount } from "../voteAtlasModel.mjs";
import { A, VOTA_ROOT_CRUMBS } from "../VotaSeo";
import { VOTA_PATHS, joinLabels, loadVotaData, ogPath, partyPagePath } from "../votaSeoData.mjs";
import MapClient from "./MapClient";

const title = "Dónde está cada partido, tema a tema";
const description =
  "Dónde está cada partido del Congreso según cómo votó en la XV legislatura: compáralos tema a tema, cruza dos temas en la brújula o juega a adivinar dónde está cada uno.";
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Mapa de partidos", path: VOTA_PATHS.map }];

export const metadata = pageMetadata({ path: VOTA_PATHS.map, title, description, image: { path: ogPath("mapa"), alt: title } });

// Crawlable version of the map: for each axis, which parties sit at each end (shown until the interactive map loads).
function AxisExtremes() {
  const { atlas } = loadVotaData();
  return (
    <section aria-labelledby="vs-ends" className="vs-section">
      <h2 className="v-h2" id="vs-ends">
        Quién está en cada extremo, eje a eje
      </h2>
      <p className="v-muted">De −100 a +100 según hacia dónde empujaron sus votos; se nombran los dos partidos de cada extremo.</p>
      <ul className="vs-rows">
        {mapAxes(atlas).map((axis) => {
          const rows = axisParties(atlas, axis.axis_id);
          const label = (p) => `${p.label} (${p.score > 0 ? "+" : ""}${Math.round(p.score * 100)})`;
          return (
            <li className="vs-row vs-row--stack" key={axis.axis_id}>
              <strong>{axis.label}</strong>
              <span>
                Más hacia «{axis.pos_short}»: {joinLabels(rows.slice(-2).reverse().map(label))}. Más hacia «{axis.neg_short}»:{" "}
                {joinLabels(rows.slice(0, 2).map(label))}. {formatCount(axis.votes)} votaciones.
              </span>
            </li>
          );
        })}
      </ul>
      <p>
        Partidos:{" "}
        {(atlas.parties || []).map((p, i) => (
          <span key={p.party_id}>
            {i ? " · " : ""}
            <A to={partyPagePath(p.party_id)}>{p.label}</A>
          </span>
        ))}
      </p>
    </section>
  );
}

export default function MapPage() {
  return (
    <>
      <MapClient
        fallback={
          <>
            <div className="x-head__text">
              <h1 className="v-h1">{title}</h1>
              <p className="v-lead">Cada posición sale de cómo votó cada partido en el Congreso, no de lo que promete.</p>
            </div>
            <AxisExtremes />
          </>
        }
      />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
