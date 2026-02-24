import "./globals.css";

export const metadata = {
  title: "Vota Con La Chola | GH Pages",
  description:
    "Portal estatico de Vota Con La Chola para ciudadania, explorer y artefactos JSON reproducibles por snapshot.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
