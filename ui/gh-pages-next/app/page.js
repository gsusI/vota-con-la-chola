import Link from "next/link";
import { getHomeQuestionCards, siteSections, withBasePath } from "./siteCatalog.mjs";

export default function HomePage() {
  const questions = getHomeQuestionCards();

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Explora</p>
        <h1>Vota Con La Chola</h1>
        <p className="sub">
          Sigue temas, actores, decisiones y resultados con enlaces directos a la evidencia y a los datos publicados.
        </p>
        <div className="chips">
          <span className="chip">Temas</span>
          <span className="chip">Actores</span>
          <span className="chip">Datos verificables</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Empieza por una pregunta</h2>
        </div>
        <div className="grid">
          {questions.map((item) => (
            <Link className="tile" key={item.id} href={withBasePath(item.href)}>
              <span className="tileTitle">{item.title}</span>
              <span className="tileNote">{item.note}</span>
              <span className="tileNote" style={{ marginTop: "2px", color: "#7b2f20", fontWeight: 700 }}>
                {item.question}
              </span>
              <span className="chip">Abrir {item.label}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Secciones principales</h2>
        </div>
        <div className="grid">
          {siteSections.map((section) => (
            <Link className="tile" key={section.id} href={withBasePath(section.href)}>
              <span className="tileTitle">{section.navLabel}</span>
              <span className="tileNote">{section.description}</span>
              <span className="tileNote" style={{ marginTop: "2px", color: "#7b2f20", fontWeight: 700 }}>
                {section.question}
              </span>
              <span className="chip">Entrar en {section.navLabel}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Accesos destacados</h2>
        </div>
        <div className="grid">
          <Link className="tile" href={withBasePath("/citizen/")}>
            <span className="tileTitle">Ciudadanía</span>
            <span className="tileNote">Vista resumida para traducción rápida de temas e implicaciones.</span>
            <span className="chip">Abrir ciudadanía</span>
          </Link>
          <Link className="tile" href={withBasePath("/citizen/leaderboards/")}>
            <span className="tileTitle">Comparativas cívicas</span>
            <span className="tileNote">Hipótesis públicas, rankings y cobertura comparada.</span>
            <span className="chip">Abrir comparativas</span>
          </Link>
          <Link className="tile" href={withBasePath("/methods/datasets/")}>
            <span className="tileTitle">Archivos publicados</span>
            <span className="tileNote">Consulta los archivos disponibles y la sección donde se usan.</span>
            <span className="chip">Abrir archivos</span>
          </Link>
          <Link className="tile" href={withBasePath("/methods/coverage/")}>
            <span className="tileTitle">Cobertura y calidad</span>
            <span className="tileNote">Consulta el estado de las fuentes, la cobertura y los bloqueos abiertos.</span>
            <span className="chip">Abrir cobertura</span>
          </Link>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Cómo orientarte</h2>
        </div>
        <div className="twoCols">
          <div>
            <h3>Si empiezas por un asunto</h3>
            <p className="sub">
              Entra por <strong>Temas</strong> para ver posiciones, votaciones relacionadas y resultados.
            </p>
          </div>
          <div>
            <h3>Si empiezas por una persona o partido</h3>
            <p className="sub">
              Entra por <strong>Actores</strong> para seguir perfiles, trayectorias y actividad pública.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
