// «Qué muestra / Cómo leerlo / Qué no dice»: a plain-language reading guide under each figure's title.
export default function Explain({ shows, read, not }) {
  const items = [
    ["Qué muestra", shows],
    ["Cómo leerlo", read],
    ["Qué no dice", not],
  ].filter(([, text]) => text);
  return (
    <dl
      style={{
        display: "grid",
        gap: "10px 18px",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        margin: "4px 0 14px",
        padding: "10px 12px",
        borderRadius: 8,
        background: "rgba(127, 127, 127, 0.07)",
        fontSize: "0.86rem",
        lineHeight: 1.45,
      }}
    >
      {items.map(([label, text]) => (
        <div key={label}>
          <dt style={{ fontWeight: 700, marginBottom: 2 }}>{label}</dt>
          <dd style={{ margin: 0 }}>{text}</dd>
        </div>
      ))}
    </dl>
  );
}
