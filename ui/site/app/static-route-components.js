import { withBasePath } from "./path-utils.mjs";

function isExternalHref(href) {
  return /^[a-z][a-z\d+.-]*:/iu.test(String(href || ""));
}

export function StaticRouteLink({ href, children }) {
  const external = isExternalHref(href);
  const resolvedHref = external ? href : withBasePath(href);
  return (
    <a
      className="staticRouteDataLink"
      href={resolvedHref}
      rel={external ? "noopener noreferrer" : undefined}
      target={external ? "_blank" : undefined}
    >
      {children}
    </a>
  );
}

export function StaticRouteHero({ eyebrow, title, summary, actions = [], meta = [] }) {
  return (
    <section className="hero card staticRouteHero">
      <div className="staticRouteHero__copy">
        <p className="eyebrow staticRouteHero__eyebrow">{eyebrow}</p>
        <h1 className="staticRouteHero__title">{title}</h1>
        <p className="sub staticRouteHero__summary">{summary}</p>
        {actions.length ? (
          <div className="staticRouteHero__actions">
            {actions.map((action) => (
              <StaticRouteLink href={action.href} key={`${action.href}-${action.label}`}>
                {action.label}
              </StaticRouteLink>
            ))}
          </div>
        ) : null}
      </div>
      {meta.length ? (
        <dl className="staticRouteHero__meta">
          {meta.map((item) => (
            <div className="staticRouteHero__metaItem" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}

export function StaticRouteMetrics({ metrics }) {
  return (
    <section className="staticRouteMetricGrid" aria-label="Métricas del corte">
      {metrics.map((metric) => (
        <div className="staticRouteMetric" key={metric.label}>
          <span className="staticRouteMetric__label">{metric.label}</span>
          <strong className="staticRouteMetric__value">{metric.value}</strong>
          {metric.note ? <span className="staticRouteMetric__note">{metric.note}</span> : null}
        </div>
      ))}
    </section>
  );
}

export function StaticRoutePanelGrid({ children }) {
  return <section className="staticRoutePanelGrid">{children}</section>;
}

export function StaticRoutePanel({ title, note, children }) {
  return (
    <article className="card block staticRoutePanel">
      <div className="blockHead staticRoutePanel__head">
        <h2>{title}</h2>
        {note ? <p className="staticRoutePanel__note">{note}</p> : null}
      </div>
      {children}
    </article>
  );
}

export function StaticRouteList({ items, renderItem, empty = "Sin filas en este corte." }) {
  if (!items.length) {
    return <p className="sub staticRouteEmpty">{empty}</p>;
  }
  return (
    <ul className="staticRouteList">
      {items.map((item, index) => (
        <li className="staticRouteList__item" key={item.id || item.source_id || item.vote_event_id || index}>
          {renderItem(item, index)}
        </li>
      ))}
    </ul>
  );
}

export function StaticRouteStatusPill({ value }) {
  return <span className={`staticRouteStatusPill ${value.className || ""}`}>{value.label}</span>;
}
