import { withBasePath } from "../../path-utils.mjs";

const XRAY_KINDS = [
  {
    key: "party",
    label: "Partido",
    description: "Personas vinculadas a cada partido por sus mandatos.",
  },
  {
    key: "institution",
    label: "Institución",
    description: "Personas con mandatos en cada institución.",
  },
  {
    key: "ambito",
    label: "Ámbito",
    description: "Personas agrupadas por ámbito territorial-administrativo.",
  },
  {
    key: "territorio",
    label: "Territorio",
    description: "Personas vinculadas a cada territorio.",
  },
  {
    key: "cargo",
    label: "Cargo",
    description: "Personas con cada tipo de cargo en mandatos.",
  },
];

export const metadata = {
  title: "Radiografía de personas | Vota Con La Chola",
  description: "Índice de agrupaciones del directorio de personas.",
};

export default function PeopleXrayIndexPage() {
  return (
    <main className="people-xray-index shell">
      <section className="people-xray-index__hero hero card">
        <p className="people-xray-index__eyebrow eyebrow">Radiografía de personas</p>
        <h1 className="people-xray-index__title">Personas por agrupación</h1>
        <p className="people-xray-index__summary sub">
          Índice estático para explorar personas por partido, institución, ámbito, territorio o cargo.
        </p>
        <div className="people-xray-index__chips chips">
          <span className="people-xray-index__chip chip">Rutas estáticas</span>
          <span className="people-xray-index__chip chip">Agrupaciones navegables</span>
          <span className="people-xray-index__chip chip">Sin API de servidor</span>
        </div>
        <p className="people-xray-index__back-link sub">
          <a className="people-xray-index__directory-link" href={withBasePath("/people/")}>
            Volver a Directorio
          </a>
        </p>
      </section>

      <section className="people-xray-index__groups card block">
        <div className="people-xray-index__groups-header blockHead">
          <h2 className="people-xray-index__groups-title">Agrupaciones</h2>
        </div>
        <div className="people-xray-index__grid voteIndexGrid">
          {XRAY_KINDS.map((item) => (
            <a className="people-xray-index__card voteIndexCard" href={withBasePath(`/people/xray/${item.key}/`)} key={item.key}>
              <span className="people-xray-index__card-label kpiLabel">{item.label}</span>
              <strong className="people-xray-index__card-title">Explorar por {item.label.toLowerCase()}</strong>
              <span className="people-xray-index__card-summary sub">{item.description}</span>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}
