"use client";

// Pieces of the simulator page: parameter names in plain words, the evidence card, the votes table.
export const PARAM_LABELS = {
  lambda_renovacion: "renovación anual de las pensiones",
  kappa_cohorte: "tamaño de la cohorte que se jubila",
  permanencia_empleo: "quién sigue trabajando si se retrasa la jubilación",
  prestacion_alternativa: "otras prestaciones de quien no sigue trabajando",
  tipo_marginal_irpf_pension: "IRPF que se recupera de la pensión",
  multiplicador_transferencias: "efecto de las pensiones sobre el PIB",
  multiplicador_impuestos: "efecto de los impuestos sobre el PIB",
  persistencia_multiplicador: "duración del efecto sobre el PIB",
  semielasticidad_saldo: "respuesta del saldo público al PIB",
  traslado_cotizacion_salario: "parte de la cotización empresarial que pagan los salarios",
  elasticidad_empleo_coste: "respuesta del empleo al coste laboral",
  base_cotizacion_pib: "recaudación por punto de cotización",
  recaudacion_por_1pct_empleo: "ingresos por cada 1 % de empleo",
  recaudacion_por_punto_iva: "recaudación por punto de IVA",
  traslado_iva_precios: "traslado del IVA a los precios",
  cuota_iva_general: "consumo gravado al tipo general",
  indiciacion_salarios: "salarios que recuperan la inflación",
  prima_por_deuda: "prima de riesgo por deuda",
  cuota_refinanciacion: "ritmo de refinanciación de la deuda",
  recaudacion_por_punto_irpf: "recaudación por punto de IRPF",
  recaudacion_por_punto_irpf_alto: "recaudación por punto del tramo alto",
  pareto_a_alto: "forma de la distribución de las rentas altas",
  eti_general: "respuesta de la renta declarada al IRPF",
  eti_alta: "respuesta de las rentas altas al IRPF",
  recaudacion_por_punto_iva_reducido: "recaudación por punto de IVA reducido",
  recaudacion_por_punto_sociedades: "recaudación por punto de Sociedades",
  semielasticidad_base_sociedades: "beneficios que se declaran fuera o dejan de declararse",
  traslado_sociedades_salarios: "parte del Impuesto sobre Sociedades que pagan los salarios",
  salarios_pib: "peso de los salarios en el PIB",
  respuesta_oferta_tope: "pisos de alquiler que salen del mercado con el tope",
  elasticidad_oferta_privada: "respuesta de la obra privada al precio",
  hip_sobre_ltv80: "hipotecas por encima del 80 % del precio",
  hip_sobre_ltv90: "hipotecas por encima del 90 % del precio",
  hip_sobre_ltv70: "hipotecas por encima del 70 % del precio",
  hip_sobre_lti6: "hipotecas de más de 6 veces la renta",
  hip_sobre_lti45: "hipotecas de más de 4,5 veces la renta",
  conversion_turistica: "pisos turísticos que vuelven a vivienda habitual",
  cumplimiento_tope: "parte del tope que se cumple",
  traslado_escasez_alquiler: "subida del alquiler sin tope cuando falta oferta",
  renovacion_contratos: "contratos de alquiler nuevos cada año",
  retardo_obra_publica: "años hasta terminar la vivienda pública",
  retardo_obra_privada: "años de obra de la vivienda privada",
  coste_vivienda_publica: "coste de cada vivienda pública",
  renta_social_mes: "alquiler de la vivienda pública",
  cuota_financiacion_publica: "parte del coste que paga el presupuesto",
  desplazamiento_obra_privada: "obra privada que desplaza la pública",
  absorcion_suelo: "suelo liberado que acaba construido",
  respuesta_alquiler_parque: "respuesta del alquiler a las viviendas por hogar",
  elasticidad_emancipacion: "jóvenes que se emancipan cuando baja el alquiler",
  personas_por_hogar_nuevo: "personas por hogar nuevo",
  hogares_por_inmigrante: "hogares por inmigrante",
  perdida_credito_restringido: "crédito que desaparece con el límite",
  elasticidad_precio_credito: "respuesta del precio al crédito",
  elasticidad_credito_precio: "respuesta del crédito al precio (garantía)",
  cuota_credito_nuevo: "crédito nuevo sobre el saldo",
  sustitucion_alquiler: "compradores que pasan a alquilar",
  cuota_afectados_smi: "asalariados afectados por el SMI",
  cuota_masa_afectados_smi: "masa salarial de los afectados por el SMI",
  elasticidad_empleo_smi: "efecto del SMI sobre el empleo de los afectados",
  cuota_afectados_jornada: "asalariados con jornada de más de 37,5 horas",
  elasticidad_empleo_jornada: "efecto de reducir la jornada sobre el empleo",
  compensacion_productividad_jornada: "productividad que compensa la jornada más corta",
  autonomos_k: "número de autónomos",
  cuota_media_autonomos: "cuota media de los autónomos",
  elasticidad_autonomos_cuota: "autónomos que se dan de baja si sube la cuota",
  salario_relativo_inmigrante: "salario de los trabajadores extranjeros frente a la media",
  ajuste_empleo_inmigrante: "empleo de quien llega frente a los extranjeros de su edad",
  uso_sanitario_relativo_inmigrante: "uso de la sanidad de los inmigrantes frente a los nacidos aquí de su edad",
  cuota_gasto_congestionable: "parte del gasto en otros servicios que crece con cada residente",
  tipo_implicito_consumo: "impuestos sobre lo que se consume",
  propension_consumo: "parte de la renta que se consume",
  pension_relativa_inmigrante: "pensión de quien llegó de adulto frente a la media",
  retardo_formacion_medico: "años para formar a un médico especialista",
  permanencia_sns_medicos: "médicos formados que se quedan en la sanidad pública",
  coste_residente_anual: "coste anual de un residente MIR",
  capacidad_por_gasto: "capacidad que el dinero compra sin más médicos",
  elasticidad_demanda_espera: "pacientes que dejan de entrar en lista cuando la espera crece",
};


export const LAYER_LABELS = {
  contable: "Solo aritmética",
  comportamiento: "+ reacción de empresas, trabajadores y mercados",
  segunda_ronda: "+ efectos de segunda ronda",
};


export function EdgeCard({ edge }) {
  if (!edge) return <p className="sim__muted">Toca «De dónde sale» en un paso para ver su ficha: qué número usa el modelo, de dónde sale y qué lo contradice.</p>;
  const p = edge.parameter;
  return (
    <article className="edgeCard" aria-live="polite">
      <header>
        <span className={`edgeCard__grade edgeCard__grade--${edge.grade}`}>Evidencia {edge.grade}</span>
        <span className="edgeCard__layer">{edge.layer === "contable" ? "aritmética" : edge.layer === "comportamiento" ? "comportamiento" : "segunda ronda"}</span>
      </header>
      <p className="edgeCard__note">{edge.note_es}</p>
      <p className="edgeCard__value">
        {p.unit}: <strong>{p.central.toLocaleString("es-ES")}</strong>
        {p.low !== p.high ? ` (rango ${p.low.toLocaleString("es-ES")} a ${p.high.toLocaleString("es-ES")})` : ""}
      </p>
      <p className="sim__muted">{edge.derivation}</p>
      <ul className="edgeCard__sources">
        {edge.sources.map((s) => (
          <li key={s.url + s.locator}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">{s.authors_year}</a>, {s.title} ({s.locator}; {s.country}).
          </li>
        ))}
      </ul>
      {edge.contrary_evidence?.length ? (
        <>
          <p className="edgeCard__sub">Lo que apunta en otra dirección</p>
          <ul className="edgeCard__sources">
            {edge.contrary_evidence.map((c) => (
              <li key={c.url + c.finding}>
                <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a>: {c.finding}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}

const VOTE_LABEL = { S: "Sí", N: "No", A: "Abst.", "?": "—" };

// Mean direction of each party on the vote atlas axis (-1 to +1), from every classified vote of that axis.
function AxisSummary({ v }) {
  const ax = v.axis;
  const rows = v.party_order.map((p) => [p, ax.party_scores[p]]).filter(([, sc]) => sc && sc.votes);
  return (
    <div className="sim__axis">
      <p className="sim__muted">
        Eje del atlas de votaciones: «{ax.label}», de {ax.neg.toLowerCase()} (−1) a {ax.pos.toLowerCase()} (+1), con {ax.n_votes} votaciones clasificadas por el
        texto votado. Dirección media de cada partido:
      </p>
      <ul className="sim__axisList">
        {rows.map(([p, sc]) => (
          <li key={p} style={{ "--x": (sc.score + 1) / 2 }}>
            <span>{v.party_labels[p]}</span>
            <span className="sim__axisBar" aria-hidden="true"><span /></span>
            <b>{sc.score > 0 ? "+" : sc.score < 0 ? "−" : ""}{Math.abs(sc.score).toLocaleString("es-ES", { maximumFractionDigits: 2 })}</b>
            <small>{sc.votes} votos</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function VotesBlock({ model, levers }) {
  const groups = [
    [levers.reval, "reval", "Revalorización de las pensiones"],
    [levers.age, "age", "Edad de jubilación"],
    [levers.contrib, "contrib", "Cotizaciones"],
    [levers.irpfAll || levers.irpfTop || levers.closure === "irpf", "irpf", "IRPF"],
    [levers.vatStd || levers.vatRed || levers.closure === "iva", "iva", "IVA"],
    [levers.corp, "corp", "Impuesto sobre Sociedades"],
    [levers.pubHomes, "publica", "Vivienda pública"],
    [levers.land, "suelo", "Suelo y licencias"],
    [levers.capCov && levers.capCut, "tope", "Tope y regulación del alquiler"],
    [levers.tourCut, "turistico", "Viviendas turísticas"],
    [levers.ltvCap || levers.ltiCap, "credito", "Hipotecas y avales"],
    [levers.smi, "smi", "Salario mínimo y derechos laborales"],
    [levers.hours, "jornada", "Jornada laboral"],
    [levers.selfQuota, "autonomos", "Autónomos y pymes"],
    [levers.migScale || levers.migration !== "base", "inmigracion", "Inmigración"],
    [levers.mir || levers.healthSpend || levers.svcFunding === "fixed", "sanidad", "Sanidad"],
  ];
  const active = groups.filter(([on, id]) => on && model.votes[id]?.votes.length).map(([, id, title]) => [id, title]);
  const shown = active.length ? active : [["reval", "Revalorización de las pensiones"]];
  return (
    <figure className="vizFigure sim__figure" id="votos">
      <h2>Cómo votaron los partidos en el Congreso sobre estas palancas</h2>
      <p className="vizFigure__dek">
        Votaciones de la XV legislatura relacionadas con las palancas que has movido. Muchas son decretos que mezclan varias medidas: el voto no es una
        cifra y el simulador no lo usa como escenario. Cada votación enlaza su registro oficial.
      </p>
      {shown.map(([lever, title]) => {
        const v = model.votes[lever];
        return (
          <div key={lever} className="sim__votes">
            <h3 className="vizPanelTitle">{title}</h3>
            {v.axis ? <AxisSummary v={v} /> : null}
            <div className="vizTable__scroll">
              <table className="sim__table sim__table--votes">
                <thead>
                  <tr>
                    <th scope="col">Votación</th>
                    {v.party_order.map((p) => (
                      <th scope="col" key={p}>{v.party_labels[p]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {v.votes.map((vote) => (
                    <tr key={vote.id}>
                      <th scope="row">
                        <a href={vote.url} target="_blank" rel="noopener noreferrer">{vote.summary}</a>
                        <span className="sim__muted"> · {vote.date}, {vote.approved ? "aprobada" : "rechazada"}
                          {vote.pushes && v.axis ? ` · votar Sí: ${(vote.pushes === "+" ? v.axis.pos : v.axis.neg).toLowerCase()}` : ""}</span>
                      </th>
                      {v.party_order.map((p) => (
                        <td key={p} className={`vote vote--${vote.parties[p] || "?"}`}>{VOTE_LABEL[vote.parties[p]] || "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
      <p className="sim__muted">
        Más votaciones y su resumen por partido en el <a href="/citizen/vota/">test de voto</a>.
      </p>
    </figure>
  );
}
