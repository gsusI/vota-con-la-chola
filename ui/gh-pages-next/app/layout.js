import "./globals.css";
import Breadcrumbs from "./components/Breadcrumbs";
import { Suspense } from "react";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");

export const metadata = {
  title: "Vota Con La Chola | GH Pages",
  description:
    "Portal estatico de Vota Con La Chola para ciudadania, explorer y artefactos JSON reproducibles por snapshot.",
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
