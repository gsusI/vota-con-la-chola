"use client";

import { useEffect, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

export default function LegacyFrame({ legacyPath, title }) {
  const [searchString, setSearchString] = useState("");

  useEffect(() => {
    setSearchString(typeof window !== "undefined" ? window.location.search || "" : "");
  }, []);

  const src = `${resolveBasePath()}${legacyPath}${searchString}`;
  return (
    <div className="legacyFrameShell">
      <iframe className="legacyFrame" src={src} title={title || "Legacy UI"} loading="eager" suppressHydrationWarning />
    </div>
  );
}
