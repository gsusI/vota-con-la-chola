import Link from "next/link";
import { withBasePath } from "../../../siteCatalog.mjs";
import { MIN_ANSWERS_FOR_RANKING } from "../votingAidModel.mjs";
import { BULLETS_SEED, PROMPTS_DIR, REPO_URL, STATEMENTS_SEED, STATEMENT_REVIEW, loadMethodology, repoLink } from "./methodologyData.mjs";

export const metadata = {
  title: "Cómo se hizo «¿Con quién coincides?» | Vota Con La Chola",
  description:
    "Proceso completo de la ayuda al voto: fuentes oficiales, cálculo, modelos de IA usados, prompts literales, revisiones, limitaciones y cómo mejorarlo.",
};

const fmt = (n) => (Number.isFinite(n) ? n.toLocaleString("es-ES") : "—");

function Ext({ href, children }) {
  return (
    <a href={href} rel="noopener noreferrer" target="_blank">
      {children}
    </a>
  );
}

function Code({ rel }) {
  return (
    <Ext href={repoLink(rel)}>
      <code>{rel}</code>
    </Ext>
  );
}

function Step({ n, title, children }) {
  return (
    <section className="card block vaMethod__step" id={`paso-${n}`}>
      <h2>
        <span className="vaMethod__num">{n}</span> {title}
      </h2>
      {children}
    </section>
  );
}

export default function VotingAidMethodologyPage() {
  const m = loadMethodology();
  const meta = m.snapshot.meta || {};
  const quality = meta.quality || {};
  const poolMeta = m.pool.meta || {};
  const hlMeta = m.highlights.meta || {};
  const balance = quality.direction_balance?.agree_sides_only_with || {};
  const cells = quality.cells_by_position || {};
  const bs = m.bulletStats;
  const ss = m.statementStats;
  const totalQuestions = (quality.statements_total || 0) + (poolMeta.items_total || 0);
  const sample = m.sampleStatement;
  const individualParties = (m.seed.parties || []).filter((p) => !p.group_codes?.length);

  return (
    <main className="shell vaMethod">
      <section className="hero card">
        <p className="eyebrow">Metodología abierta · ¿Con quién coincides?</p>
        <h1>Cómo se hizo «¿Con quién coincides?»</h1>
        <p className="sub">
          Esta página cuenta, paso a paso, cómo se construyó la{" "}
          <Link href={withBasePath("/citizen/vota/")}>ayuda al voto para las generales</Link>: de dónde salen los datos, qué
          decidió una persona, qué hizo una IA (con los prompts literales), cómo se calcula tu coincidencia y qué falla todavía. No
          es perfecta. La idea es que puedas comprobar cada paso y proponer mejoras.
        </p>
        <div className="chips">
          <span className="chip">Solo votos reales del Congreso</span>
          <span className="chip">Cálculo sin IA, reproducible</span>
          <span className="chip">Resúmenes con IA revisados con IA</span>
          <span className="chip vaMethod__chipWarn">Falta revisión humana independiente</span>
          <span className="chip">Código y datos abiertos</span>
        </div>
      </section>

      <section className="card block">
        <h2>En 30 segundos</h2>
        <ul className="vaMethod__list">
          <li>
            <strong>Lo que comparas son votos, no promesas.</strong> Cada pregunta es una o varias votaciones nominales del Congreso
            (legislatura XV). La posición de un partido es lo que votó la mayoría de sus diputados.
          </li>
          <li>
            <strong>{fmt(quality.statements_total)} afirmaciones curadas + {fmt(poolMeta.items_total)} votaciones reales</strong> (
            {fmt(totalQuestions)} preguntas en total), de {poolMeta.votes_first_date || "—"} a{" "}
            {meta.votes_last_date > (poolMeta.votes_last_date || "") ? meta.votes_last_date : poolMeta.votes_last_date || "—"}.
          </li>
          <li>
            <strong>El cálculo de coincidencia es una fórmula sencilla</strong>, sin IA, que se ejecuta en tu navegador. Tus respuestas
            no salen de tu dispositivo.
          </li>
          <li>
            <strong>La IA se usó para escribir</strong> (código, redacción de afirmaciones y resúmenes en lenguaje llano del texto
            oficial) <strong>y para revisar</strong> esos textos contra el BOCG/BOE. Nunca para decidir cómo votó un partido.
          </li>
          <li>
            <strong>Estado honesto:</strong> todo está revisado por IA, pero{" "}
            <strong>ninguna afirmación ni resumen ha pasado aún una revisión humana independiente</strong>. Ese es el siguiente paso, y
            puedes ayudar.
          </li>
        </ul>
        <nav aria-label="Índice" className="vaMethod__toc">
          <a href="#paso-1">1. Datos</a>
          <a href="#paso-2">2. Partidos</a>
          <a href="#paso-3">3. Afirmaciones</a>
          <a href="#paso-4">4. Modo infinito</a>
          <a href="#paso-5">5. Texto oficial</a>
          <a href="#paso-6">6. «Qué se votaba»</a>
          <a href="#paso-7">7. Revisión</a>
          <a href="#paso-8">8. Cálculo</a>
          <a href="#paso-9">9. Privacidad e IA</a>
          <a href="#modelos">Modelos</a>
          <a href="#prompts">Prompts</a>
          <a href="#fuentes">Fuentes</a>
          <a href="#limitaciones">Limitaciones</a>
          <a href="#reproducir">Reproducir</a>
          <a href="#contribuir">Contribuir</a>
        </nav>
      </section>

      <Step n={1} title="Datos de partida: votaciones nominales del Congreso">
        <p>
          La fuente es el portal de datos abiertos del Congreso de los Diputados, que publica cada votación nominal en JSON con el voto
          de cada diputado (Sí, No, Abstención, No vota) y su grupo parlamentario. El ETL del proyecto los descarga y guarda en una base
          SQLite (tablas <code>parl_vote_events</code> y <code>parl_vote_member_votes</code>), conservando la URL original de cada
          votación para poder comprobarla.
        </p>
        <p>
          Comando de ingesta usado para el último tramo:{" "}
          <code>
            python3 scripts/ingestar_parlamentario_es.py ingest --source congreso_votaciones --congreso-legs 15 --since-date 2025-11-01
            --strict-network
          </code>
          . En cada pregunta de la herramienta hay un enlace al JSON oficial de la votación.
        </p>
      </Step>

      <Step n={2} title="De diputados a partidos de la papeleta">
        <ul className="vaMethod__list">
          <li>
            Se comparan {m.snapshot.parties.length} partidos que concurren a las generales: {m.snapshot.parties.map((p) => p.label).join(", ")}.
          </li>
          <li>
            La mayoría de partidos se asignan por su grupo parlamentario. {individualParties.map((p) => p.label).join(", ")} votan dentro de
            otros grupos (sobre todo el Mixto), así que se asignan diputado a diputado por nombre, definido en{" "}
            <Code rel={STATEMENTS_SEED} />.
          </li>
          <li>
            <strong>Posición del partido en una votación</strong> = la opción mayoritaria entre Sí / No / Abstención de sus diputados. «No
            vota» no cuenta. Si hay empate exacto entre las dos opciones más votadas, la posición es «votos distintos».
          </li>
          <li>
            Diputados que no se asignan a ningún partido (sus votos no cuentan):
            <ul className="vaMethod__list">
              {(m.snapshot.unmapped_members || []).map((u) => (
                <li key={u.member_name}>
                  {u.member_name}: {u.reason}
                </li>
              ))}
            </ul>
          </li>
          <li>
            Si falta un dato, la celda queda como <strong>«sin datos»</strong> y no cuenta: nunca se inventa una posición. Hoy hay{" "}
            {fmt(cells.no_data)} celdas sin datos de {fmt(quality.cells_total)} en las afirmaciones curadas.
          </li>
        </ul>
      </Step>

      <Step n={3} title={`Las ${fmt(quality.statements_total)} afirmaciones curadas`}>
        <p>
          Son frases en lenguaje llano («Los alquileres de temporada… deberían…») sobre las 12 preocupaciones ciudadanas del proyecto más
          cultura, política exterior y modelo territorial. Cada una se apoya en 1 a 3 votaciones ({fmt(quality.votes_total)} en total) y
          declara qué voto significa «de acuerdo» (<code>agree_vote</code>).
        </p>
        <ul className="vaMethod__list">
          <li>
            <strong>Quién las redactó:</strong> un agente de IA (Claude Opus 5.5) a partir de las votaciones disponibles, dirigido por
            el mantenedor del proyecto, que pidió una herramienta para decidir el voto en las generales. No hubo un panel de expertos.
          </li>
          <li>
            <strong>Sentido del voto:</strong> se comprobó contra el texto oficial (BOCG/BOE) que votar <code>agree_vote</code> equivale
            a estar de acuerdo con la frase. Regla explícita: votar Sí a una <em>toma en consideración</em> (aceptar debatir una ley) se
            interpreta como apoyo a su objetivo.
          </li>
          <li>
            <strong>Sesgo de aquiescencia:</strong> mucha gente tiende a decir «sí» a todo. Por eso las frases se redactan en ambos
            sentidos y se comprueba que «de acuerdo» no favorezca a un bloque: hoy coincide solo con el PSOE (y no con el PP) en{" "}
            {fmt(balance.psoe)} afirmaciones y solo con el PP en {fmt(balance.pp)}. El test exige una diferencia de 3 como máximo.
          </li>
          <li>
            Cada afirmación lleva una nota de contexto y el enlace al texto votado. Todo está en <Code rel={STATEMENTS_SEED} />.
          </li>
        </ul>
        {sample ? (
          <details className="vaMethod__details">
            <summary>Ver cómo está definida una afirmación (dato real)</summary>
            <pre className="vaMethod__pre">{JSON.stringify(sample, null, 2)}</pre>
          </details>
        ) : null}
      </Step>

      <Step n={4} title={`El modo infinito: ${fmt(poolMeta.items_total)} votaciones reales`}>
        <ul className="vaMethod__list">
          <li>
            <strong>Selección automática</strong> (sin elección manual): todas las votaciones nominales de la legislatura XV de estos
            tipos — tomas en consideración, convalidaciones de decretos ley, proposiciones no de ley, mociones y votaciones finales — en
            las que <strong>al menos un partido votó Sí y otro No</strong>. Las unánimes no dicen nada sobre diferencias y se descartan.
          </li>
          <li>
            Reparto actual por tipo:{" "}
            {Object.entries(poolMeta.by_kind || {})
              .map(([k, v]) => `${k} ${v}`)
              .join(", ")}
            . Si una ley tiene toma en consideración y votación final, solo queda la final.
          </li>
          <li>
            La pregunta es el <strong>título oficial sin el grupo que lo propuso</strong> (se revela tras responder, para que no te
            condicione). «De acuerdo» siempre significa votar Sí.
          </li>
          <li>
            <strong>Orden:</strong> primero las curadas; luego se alternan votaciones donde el Sí favorece al PSOE, al PP o a ambos (
            {fmt(poolMeta.by_side?.psoe)} / {fmt(poolMeta.by_side?.pp)} / {fmt(poolMeta.by_side?.cross)}), empezando por las que dividen
            a más partidos ({fmt(poolMeta.by_tier?.split)} con ≥2 partidos en cada lado). Así responder siempre «Sí» no te arrastra hacia
            un lado.
          </li>
          <li>
            <strong>Tema:</strong> por palabras clave del título (reglas en <Code rel="scripts/export_voting_aid_pool.py" />). Es tosco:{" "}
            {fmt(poolMeta.by_theme?.Otros)} votaciones quedan en «Otros».
          </li>
        </ul>
      </Step>

      <Step n={5} title="El texto oficial de cada votación">
        <p>
          Un título puede esconder mucho: un decreto «de transporte» que también cambia impuestos. Por eso cada votación se enlaza al
          documento oficial votado: decretos ley en el BOE, proposiciones y proyectos en el BOCG (serie B/A), proposiciones no de ley y
          mociones en el BOCG serie D. Hoy hay texto para {fmt(hlMeta.votes_with_text)} votaciones ({fmt(hlMeta.documents)} documentos),
          cada uno con su URL y su huella <strong>SHA-256</strong>, para que cualquiera compruebe que es el mismo documento.
        </p>
        <ul className="vaMethod__list">
          <li>
            Las PNL y mociones sin enlace directo se buscaron en el buscador de iniciativas del Congreso, y el expediente solo se aceptó
            si su ficha enlaza <em>la misma</em> votación nominal (<Code rel="scripts/voting_aid_motion_texts.py" />).
          </li>
          <li>
            Se indica <strong>qué versión del texto</strong> es: aprobado, original votado en sus términos, original con enmienda
            incorporada, enmienda transaccional no publicada, texto inicial antes de enmiendas…
          </li>
          <li>
            <strong>Ómnibus</strong> (automático, sin IA): si el título, los bloques y las normas que modifica abarcan 3 o más temas (
            {fmt(hlMeta.omnibus_documents)} documentos). También se marcan los «cambios ajenos al título» en disposiciones finales. Puedes
            excluir las ómnibus del cálculo.
          </li>
        </ul>
      </Step>

      <Step n={6} title="«Qué se votaba»: resúmenes en lenguaje llano con IA">
        <p>
          Antes de responder ves hasta 6 viñetas que dicen qué contenía el texto votado y una frase «En pocas palabras». Esto sí lo
          escribió una IA, con reglas estrictas (ver <a href="#prompts">prompts</a>):
        </p>
        <ul className="vaMethod__list">
          <li>Solo la parte dispositiva (el articulado o los puntos que se piden), nunca la exposición de motivos.</li>
          <li>Cada viñeta lleva un localizador («Artículo 9 bis», «Punto 3») para comprobarla en el documento.</li>
          <li>Neutral: sin partidos, sin quién lo propuso, sin resultado, sin adjetivos valorativos.</li>
          <li>Condicional en proposiciones («se permitiría…»): no se presenta como ley vigente lo que solo se propuso.</li>
        </ul>
        <p>
          <strong>Proceso:</strong> (1) Claude Sonnet 5.5 redacta por lotes leyendo el texto extraído del PDF/XML oficial; (2) otro
          subagente Sonnet 5.5, sin ver el borrador como «correcto», comprueba cada viñeta contra el texto y la corrige; (3) un validador
          automático (<Code rel="scripts/export_voting_aid_vote_bullets.py" />) rechaza viñetas sin localizador, con nombres de partidos,
          de más de 6 o cuyo documento no coincide en URL y SHA-256 con el publicado. La frase «En pocas palabras» la escribió el agente
          principal (Claude Opus 5.5) a partir de las viñetas ya revisadas, sin añadir nada.
        </p>
        {bs ? (
          <div className="kpiGrid vaMethod__kpis">
            <div className="vaMethod__kpi">
              <strong>{fmt(bs.withBullets)}</strong>
              <span>votaciones con viñetas (de {fmt(bs.votes)})</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(bs.bullets)}</strong>
              <span>viñetas</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>
                {fmt(bs.corrected)} / {fmt(bs.docs)}
              </strong>
              <span>documentos corregidos por el revisor IA</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(bs.changes)}</strong>
              <span>cambios hechos en la revisión (cifras, condiciones, localizadores…)</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(bs.issues)}</strong>
              <span>avisos abiertos para revisión humana</span>
            </div>
            <div className="vaMethod__kpi vaMethod__kpi--warn">
              <strong>{fmt(bs.humanReviewed)}</strong>
              <span>revisadas por una persona</span>
            </div>
          </div>
        ) : null}
        <p className="vaMethod__muted">
          Que el revisor corrigiera {bs ? `${fmt(bs.corrected)} de ${fmt(bs.docs)}` : "la mayoría de los"} documentos indica que el
          primer borrador de una IA no es fiable por sí solo. Cada corrección queda guardada (borrador original, cambios y avisos) en{" "}
          <Code rel={BULLETS_SEED} />.
        </p>
      </Step>

      <Step n={7} title="Revisión independiente de las afirmaciones">
        <p>
          {m.statementReviewMethod ||
            "Dos revisores IA independientes por afirmación leyeron el texto oficial y juzgaron el sentido del voto y la redacción, sin ver cómo votaron los partidos."}
        </p>
        {ss ? (
          <div className="kpiGrid vaMethod__kpis">
            <div className="vaMethod__kpi">
              <strong>
                {fmt(ss.correct)} / {fmt(ss.checks)}
              </strong>
              <span>comprobaciones de sentido correctas</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(ss.wrong)}</strong>
              <span>erróneas</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(ss.unclear)}</strong>
              <span>dudosas</span>
            </div>
            <div className="vaMethod__kpi">
              <strong>{fmt(ss.wordingIssues)}</strong>
              <span>objeciones de redacción (de {fmt(ss.statements * 2)} juicios)</span>
            </div>
          </div>
        ) : null}
        <p>
          Resultado: {m.seed.review?.result || "ver evidencia"} La evidencia completa, con la cita literal y el localizador que usó cada
          revisor, está en <Code rel={STATEMENT_REVIEW} />.
        </p>
      </Step>

      <Step n={8} title="Cómo se calcula tu coincidencia">
        <ul className="vaMethod__list">
          <li>Tus respuestas: de acuerdo / sí = +1, neutral / me da igual = 0, en desacuerdo / no = −1.</li>
          <li>
            Partido: a favor = +1, en contra = −1, abstención o votos distintos = 0. Si una afirmación tiene varias votaciones y el
            partido votó igual en todas, esa es su posición; si no, «votos distintos».
          </li>
          <li>
            Coincidencia en una pregunta = <code>1 − |tú − partido| / 2</code> (1 si coincidís, 0,5 a medias, 0 si sois opuestos).
          </li>
          <li>Coincidencia total = media ponderada; las que marcas como «me importa mucho» cuentan doble.</li>
          <li>Las preguntas que saltas y las celdas sin datos no cuentan. Ves con cuántas preguntas se ha comparado cada partido.</li>
          <li>Con menos de {MIN_ANSWERS_FOR_RANKING} respuestas el resultado se marca como provisional.</li>
        </ul>
        <p className="vaMethod__muted">
          Código: <Code rel="ui/site/app/citizen/vota/votingAidModel.mjs" /> (función <code>scoreParties</code>), con tests en{" "}
          <Code rel="tests/test_citizen_voting_aid_model.mjs" />.
        </p>
      </Step>

      <Step n={9} title="Privacidad y los botones «Pregúntale a una IA»">
        <ul className="vaMethod__list">
          <li>Tus respuestas se guardan solo en tu navegador (localStorage). No hay servidor que las reciba.</li>
          <li>Compartir es voluntario y usa el fragmento de la URL (<code>#r=…</code>), que los navegadores no envían al servidor.</li>
          <li>
            Los botones de ChatGPT, Claude y Gemini abren esos servicios con una pregunta ya escrita que contiene lo votado (título,
            fechas, enlaces oficiales, viñetas) y, solo después de responder, cómo votó cada partido.{" "}
            <strong>Nunca incluye tus respuestas</strong>, y puedes leerla entera antes de enviarla. Lo que conteste ese servicio no lo
            controlamos ni lo revisamos: úsalo como ayuda, no como fuente.
          </li>
        </ul>
      </Step>

      <section className="card block" id="modelos">
        <h2>Quién hizo qué: personas, modelos y código</h2>
        <div className="vaMethod__tableWrap">
          <table className="vaMethod__table">
            <thead>
              <tr>
                <th>Tarea</th>
                <th>Quién</th>
                <th>Comprobación</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td data-label="Tarea">Idea, dirección y decisiones de producto</td>
                <td data-label="Quién">El mantenedor del proyecto (persona)</td>
                <td data-label="Comprobación">—</td>
              </tr>
              <tr>
                <td data-label="Tarea">Descarga de votaciones y textos oficiales, posiciones de partidos, selección del modo infinito, ómnibus, temas</td>
                <td data-label="Quién">Código determinista (Python), sin IA en tiempo de ejecución</td>
                <td data-label="Comprobación">Tests automáticos y datos oficiales enlazados</td>
              </tr>
              <tr>
                <td data-label="Tarea">Escribir ese código y la web</td>
                <td data-label="Quién">Claude Opus 5.5 (Anthropic) como agente de programación, dirigido por el mantenedor</td>
                <td data-label="Comprobación">Tests, revisión del mantenedor</td>
              </tr>
              <tr>
                <td data-label="Tarea">Redactar las {fmt(quality.statements_total)} afirmaciones y su sentido de voto</td>
                <td data-label="Quién">Claude Opus 5.5</td>
                <td data-label="Comprobación">2 revisores Claude Sonnet 5.5 independientes · falta revisión humana</td>
              </tr>
              <tr>
                <td data-label="Tarea">Viñetas «Qué se votaba»</td>
                <td data-label="Quién">Claude Sonnet 5.5 (subagentes por lotes)</td>
                <td data-label="Comprobación">Otro subagente Sonnet 5.5 + validador automático · falta revisión humana</td>
              </tr>
              <tr>
                <td data-label="Tarea">Frase «En pocas palabras»</td>
                <td data-label="Quién">Claude Opus 5.5</td>
                <td data-label="Comprobación">Validador (≤180 caracteres, sin partidos) · falta revisión humana</td>
              </tr>
              <tr>
                <td data-label="Tarea">Calcular tu coincidencia</td>
                <td data-label="Quién">Fórmula en tu navegador, sin IA</td>
                <td data-label="Comprobación">Tests</td>
              </tr>
              <tr>
                <td data-label="Tarea">Respuestas en «Pregúntale a una IA»</td>
                <td data-label="Quién">ChatGPT, Claude o Gemini, elegido por ti</td>
                <td data-label="Comprobación">Ninguna por nuestra parte</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="vaMethod__muted">
          Las fechas de trabajo con IA: 11 y 12 de octubre de 2026. Las afirmaciones revisadas por IA el {m.seed.review?.reviewed_at || "—"}
          ; datos generados el {(meta.generated_at || "").slice(0, 10) || "—"}.
        </p>
      </section>

      <section className="card block" id="prompts">
        <h2>Los prompts, literales</h2>
        <p>
          Estas son las instrucciones exactas que recibieron los modelos. Solo se ha sustituido la ruta de una carpeta temporal local por{" "}
          <code>&lt;scratchpad&gt;</code>. Archivos en <Code rel={PROMPTS_DIR} />.
        </p>
        {m.prompts.map((p) => (
          <details className="vaMethod__details" key={p.file}>
            <summary>
              {p.title} <span className="vaMethod__muted">· {p.who}</span>
            </summary>
            {p.text ? (
              <pre className="vaMethod__pre">{p.text}</pre>
            ) : (
              <p>
                <Code rel={p.path} />
              </p>
            )}
          </details>
        ))}
        <h3>Las decisiones humanas que dieron forma a la herramienta</h3>
        <p>
          La herramienta nació de una sesión de trabajo del mantenedor con el agente de programación (Claude Opus 5.5). Estas fueron,
          en orden, las indicaciones que marcaron su diseño. Están resumidas con nuestras palabras; no son citas literales.
        </p>
        <ol className="vaMethod__list">
          <li>
            <strong>Objetivo:</strong> convertir los datos de votaciones del proyecto en algo útil para decidir el voto en las próximas
            generales, empezando por un cuestionario basado en votaciones reales, y dejar al agente iterar de forma autónoma sobre él.
          </li>
          <li>
            <strong>Profundidad y claridad:</strong> muchas más preguntas, poder seguir respondiendo sin límite y ver, partido a partido,
            en qué preguntas coincides y en cuáles no. Y que la experiencia resultara amena.
          </li>
          <li>
            <strong>Explicaciones verificables:</strong> enlaces directos a Gemini, ChatGPT y Claude para entender en términos sencillos
            qué se votaba y por qué cada partido votó como votó, con un contexto que incluya exactamente el texto votado.
          </li>
          <li>
            <strong>Que el título no engañe:</strong> mostrar en cada pregunta lo esencial de lo votado, porque las votaciones ómnibus
            mezclan asuntos distintos y su título a menudo no describe lo que realmente se decide.
          </li>
          <li>
            <strong>Texto completo y concreción:</strong> enlazar también el texto de las proposiciones no de ley y mociones, y revisar
            cada pregunta para añadir hasta cinco o seis puntos concretos de lo que se votaba.
          </li>
          <li>
            <strong>Una versión en una frase:</strong> un resumen breve de cada votación para quien quiera la idea principal de un
            vistazo.
          </li>
        </ol>
        <h3>Ejemplos reales del prompt «Pregúntale a una IA»</h3>
        <p>Generados con el mismo código y los mismos datos que usa la herramienta:</p>
        {m.examples.map((e) => (
          <details className="vaMethod__details" key={e.title}>
            <summary>{e.title}</summary>
            <pre className="vaMethod__pre">{e.text}</pre>
          </details>
        ))}
      </section>

      <section className="card block" id="fuentes">
        <h2>Fuentes</h2>
        <h3>Oficiales</h3>
        <ul className="vaMethod__list">
          <li>
            <Ext href="https://www.congreso.es/es/opendata/votaciones">Congreso de los Diputados · datos abiertos de votaciones</Ext> (JSON
            por votación con el voto de cada diputado).
          </li>
          <li>
            <Ext href="https://www.congreso.es/es/ultimaspublicacionesoficiales">Boletín Oficial de las Cortes Generales (BOCG)</Ext>: textos
            de proposiciones de ley (serie B), proyectos (serie A), PNL y mociones (serie D).
          </li>
          <li>
            <Ext href="https://www.congreso.es/es/busqueda-de-iniciativas">Buscador de iniciativas del Congreso</Ext>, para enlazar cada
            votación con su expediente.
          </li>
          <li>
            <Ext href="https://www.boe.es/">Boletín Oficial del Estado (BOE)</Ext>: reales decretos ley, por su identificador ELI.
          </li>
        </ul>
        <h3>Del proyecto (todo público)</h3>
        <ul className="vaMethod__list">
          <li>
            Afirmaciones y asignación de partidos: <Code rel={STATEMENTS_SEED} />
          </li>
          <li>
            Viñetas con borrador, cambios y avisos: <Code rel={BULLETS_SEED} />
          </li>
          <li>
            Textos de PNL y mociones enlazados: <Code rel="etl/data/seeds/voting_aid_motion_texts_v1.json" />
          </li>
          <li>
            Exportadores: <Code rel="scripts/export_voting_aid_snapshot.py" />, <Code rel="scripts/export_voting_aid_pool.py" />,{" "}
            <Code rel="scripts/export_voting_aid_highlights.py" />, <Code rel="scripts/export_voting_aid_vote_bullets.py" />
          </li>
          <li>
            Datos que carga la web: <Code rel="ui/site/public/citizen/data/voting_aid_generales_v1.json" />,{" "}
            <Code rel="ui/site/public/citizen/data/voting_aid_pool_v1.json" />,{" "}
            <Code rel="ui/site/public/citizen/data/voting_aid_highlights_v1.json" />,{" "}
            <Code rel="ui/site/public/citizen/data/voting_aid_vote_bullets_v1.json" />
          </li>
          <li>
            Registro de avances y huecos: <Code rel="docs/etl/e2e-scrape-load-tracker.md" />
          </li>
        </ul>
      </section>

      <section className="card block" id="limitaciones">
        <h2>Limitaciones conocidas</h2>
        <ul className="vaMethod__list">
          <li>
            <strong>Sin revisión humana independiente.</strong> Afirmaciones, sentido del voto y viñetas los ha revisado otra IA. Una IA
            revisando a otra reduce errores, pero comparte puntos ciegos.
          </li>
          <li>
            <strong>Votar no es lo mismo que pensar.</strong> Un partido puede votar en contra de algo con lo que está de acuerdo por
            cómo está redactado, por táctica o por disciplina de bloque. La herramienta mide votos, no intenciones ni programas.
          </li>
          <li>
            <strong>Toma en consideración ≠ apoyo total.</strong> Votar Sí a debatir una ley se interpreta como apoyo a su objetivo; es
            una simplificación.
          </li>
          <li>
            <strong>La mayoría esconde divisiones internas</strong> (los recuentos por partido sí se muestran) y ignora la abstención como
            matiz: cuenta 0.
          </li>
          <li>
            <strong>Partidos sin diputados en el Congreso XV no aparecen</strong>, y solo se usa el Congreso (no Senado, parlamentos
            autonómicos ni Parlamento Europeo).
          </li>
          <li>
            <strong>Versiones del texto:</strong> a veces solo existe el texto inicial o se votó una enmienda transaccional que no se
            publicó; la herramienta lo avisa, pero el resumen puede no reflejar exactamente lo votado.
          </li>
          <li>
            <strong>Temas por palabras clave:</strong> {fmt(poolMeta.by_theme?.Otros)} votaciones quedan en «Otros» y alguna puede estar
            mal clasificada.
          </li>
          <li>
            <strong>Ocultar al proponente es imperfecto:</strong> se quita del título con reglas de texto y algunos títulos aún dejan
            pistas (por ejemplo, nombres de grupos en títulos compuestos).
          </li>
          <li>
            <strong>Selección de afirmaciones:</strong> qué temas y votaciones se eligieron es una decisión editorial (de una IA dirigida
            por una persona), con sesgos posibles aunque el equilibrio PSOE/PP se controle.
          </li>
        </ul>
      </section>

      <section className="card block" id="reproducir">
        <h2>Cómo reproducirlo</h2>
        <p>Con el repositorio y una base SQLite con las votaciones del Congreso XV:</p>
        <pre className="vaMethod__pre">{`python3 scripts/ingestar_parlamentario_es.py ingest --db <db> --source congreso_votaciones --congreso-legs 15 --strict-network
python3 scripts/export_voting_aid_snapshot.py --db <db> --out ui/site/public/citizen/data/voting_aid_generales_v1.json
python3 scripts/export_voting_aid_pool.py --db <db> --out ui/site/public/citizen/data/voting_aid_pool_v1.json
python3 scripts/voting_aid_motion_texts.py link --db <db>
python3 scripts/export_voting_aid_highlights.py
python3 scripts/export_voting_aid_vote_bullets.py
node tests/test_citizen_voting_aid_model.mjs
python3 -m unittest tests.test_export_voting_aid_snapshot tests.test_export_voting_aid_pool tests.test_export_voting_aid_highlights tests.test_export_voting_aid_vote_bullets`}</pre>
        <p className="vaMethod__muted">
          Los pasos de IA (redactar y revisar textos) no son deterministas: con los mismos prompts saldrán frases distintas. Por eso su
          resultado se guarda versionado en las semillas, con el documento y su SHA-256, y lo que se publica es siempre ese fichero
          revisable.
        </p>
      </section>

      <section className="card block" id="contribuir">
        <h2>Cómo contribuir</h2>
        <p>Lo que más ayuda ahora mismo, de más a menos urgente:</p>
        <ol className="vaMethod__list">
          <li>
            <strong>Revisar afirmaciones</strong>: ¿la frase es neutral y de una sola idea? ¿votar <code>agree_vote</code> significa de
            verdad estar de acuerdo con ella? Compruébalo con el texto oficial enlazado.
          </li>
          <li>
            <strong>Revisar viñetas</strong>, empezando por las que tienen avisos (<code>review.issues</code>): ¿lo que dicen está en el
            artículo o punto indicado?
          </li>
          <li>
            <strong>Proponer afirmaciones</strong> sobre temas que falten, con la votación nominal que las respalda.
          </li>
          <li>
            <strong>Mejorar el método</strong>: clasificación por temas, tratamiento de abstenciones, ocultación del proponente…
          </li>
        </ol>
        <p>
          Abre una incidencia o una propuesta de cambio en <Ext href={`${REPO_URL}/issues`}>GitHub</Ext> indicando el identificador de la
          afirmación (p. ej. <code>vivienda-alquiler-temporada</code>) o de la votación, qué cambiarías y la fuente. Una corrección revisada
          por una persona pasará a marcarse como <code>reviewed</code>.
        </p>
        <p>
          <Link className="votingAidButton" href={withBasePath("/citizen/vota/")}>
            Volver a «¿Con quién coincides?»
          </Link>
        </p>
      </section>
    </main>
  );
}
