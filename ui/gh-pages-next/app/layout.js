import "./globals.css";
import Breadcrumbs from "./components/Breadcrumbs";
import SiteHeader from "./components/SiteHeader";
import { Suspense } from "react";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const siteOrigin = process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://votaconlachola.org";

export const metadata = {
  metadataBase: new URL(siteOrigin),
  title: "Vota Con La Chola",
  description:
    "Información pública sobre temas, actores, decisiones y resultados con evidencia y archivos publicados.",
  alternates: {
    canonical: basePath ? `${basePath}/` : "/",
  },
  icons: {
    icon: `${basePath}/favicon.svg`,
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        <Suspense fallback={null}>
          <SiteHeader />
        </Suspense>
        <Suspense fallback={null}>
          <Breadcrumbs />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
