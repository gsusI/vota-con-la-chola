import "./globals.css";
import Breadcrumbs from "./components/Breadcrumbs";
import VotingAidBanner from "./components/VotingAidBanner";
import { Suspense } from "react";
import { SITE_ORIGIN, resolveBasePath, siteCardImage } from "./path-utils.mjs";

const basePath = resolveBasePath();

// Site-wide share defaults; pages with their own openGraph/twitter replace these objects wholesale.
export const metadata = {
  metadataBase: new URL(SITE_ORIGIN),
  title: "Vota Con La Chola",
  description:
    "Portal estático de Vota Con La Chola para ciudadanía, explorador y artefactos JSON reproducibles por corte.",
  icons: {
    icon: `${basePath}/favicon.svg`,
  },
  openGraph: { type: "website", siteName: "Vota Con La Chola", locale: "es_ES", images: [siteCardImage()] },
  twitter: { card: "summary_large_image", images: [siteCardImage().url] },
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        <VotingAidBanner />
        <Suspense fallback={null}>
          <Breadcrumbs />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
