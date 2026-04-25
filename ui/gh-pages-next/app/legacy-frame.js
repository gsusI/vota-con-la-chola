"use client";

import { useEffect, useState } from "react";
import { withBasePath } from "./path-utils.mjs";

export default function LegacyFrame({ legacyPath, title }) {
  const [searchString, setSearchString] = useState("");

  useEffect(() => {
    setSearchString(typeof window !== "undefined" ? window.location.search || "" : "");
  }, []);

  const src = `${withBasePath(legacyPath)}${searchString}`;
  return (
    <div className="legacyFrameShell">
      <iframe className="legacyFrame" src={src} title={title || "Legacy UI"} loading="eager" suppressHydrationWarning />
    </div>
  );
}
