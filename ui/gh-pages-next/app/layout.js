import "./globals.css";
import Breadcrumbs from "./components/Breadcrumbs";
import { Suspense } from "react";
import { resolveBasePath } from "./path-utils.mjs";

const basePath = resolveBasePath();

export const metadata = {
  title: "Vota Con La Chola | GH Pages",
  description:
    "Portal estático de Vota Con La Chola para ciudadanía, explorador y artefactos JSON reproducibles por corte.",
  icons: {
    icon: `${basePath}/favicon.svg`,
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        <Suspense fallback={null}>
          <Breadcrumbs />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
