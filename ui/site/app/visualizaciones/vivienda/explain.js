// Reading aids for every figure: what it shows, how to read it and what it cannot say.
export function Explain({ shows, read, notSay }) {
  return (
    <div className="hvExplain" role="note" aria-label="Cómo leer este gráfico">
      <div>
        <h3>Qué muestra</h3>
        <p>{shows}</p>
      </div>
      <div>
        <h3>Cómo leerlo</h3>
        <p>{read}</p>
      </div>
      <div>
        <h3>Qué no dice</h3>
        <p>{notSay}</p>
      </div>
    </div>
  );
}

export function Part({ id, title, children }) {
  return (
    <header className="hvPart" id={id}>
      <h2>{title}</h2>
      {children ? <p>{children}</p> : null}
    </header>
  );
}

const VERDICT = { yes: "Se sostiene", partly: "En parte", no: "No se sostiene" };

export function Verdict({ kind }) {
  return <span className={`hvVerdict hvVerdict--${kind}`}>{VERDICT[kind]}</span>;
}
