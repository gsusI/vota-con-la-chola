// Visualization styles load only under /visualizaciones/: editing them must not rehash the CSS every page links.
import "./visualizaciones.css";

export default function VisualizacionesLayout({ children }) {
  return <div className="viz">{children}</div>;
}
