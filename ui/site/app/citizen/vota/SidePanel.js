"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Same breakpoint as the voting-aid layout: below it the panel is a modal drawer from the right.
const DRAWER_QUERY = "(max-width: 900px)";
const OPEN_EVENT = "sidepanel:open";

/**
 * Side panel for "see more" content. Desktop: a non-modal sidebar docked on the right; the page shifts left and
 * stays usable. Mobile: a modal drawer from the right over a backdrop. Only one panel is open at a time.
 */
export default function SidePanel({ open, onClose, title, children }) {
  const ref = useRef(null);
  const titleId = useId();
  const [mounted, setMounted] = useState(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return undefined;
    const drawer = window.matchMedia(DRAWER_QUERY).matches;
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: titleId }));
    if (!dialog.open) (drawer ? dialog.showModal() : dialog.show());
    const root = document.documentElement;
    root.classList.add(drawer ? "has-sideDrawer" : "has-sidePanel");
    const onOther = (e) => e.detail !== titleId && closeRef.current();
    const onKey = (e) => e.key === "Escape" && closeRef.current();
    window.addEventListener(OPEN_EVENT, onOther);
    if (!drawer) document.addEventListener("keydown", onKey);
    return () => {
      root.classList.remove("has-sideDrawer", "has-sidePanel");
      window.removeEventListener(OPEN_EVENT, onOther);
      document.removeEventListener("keydown", onKey);
      if (dialog.open) dialog.close();
    };
  }, [open, titleId]);

  if (!mounted) return null;
  return createPortal(
    <dialog
      aria-labelledby={titleId}
      className="sidePanel"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      onClose={onClose}
      // Keep the question card's swipe-to-answer and shortcut keys out of the panel.
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") onClose();
      }}
      onPointerDown={(e) => e.stopPropagation()}
      ref={ref}
    >
      <div className="sidePanel__inner">
        <header className="sidePanel__head">
          <h2 className="sidePanel__title" id={titleId}>
            {title}
          </h2>
          <button aria-label="Cerrar" className="sidePanel__close" onClick={onClose} type="button">
            ✕
          </button>
        </header>
        <div className="sidePanel__body">{open ? children : null}</div>
      </div>
    </dialog>,
    document.body,
  );
}
