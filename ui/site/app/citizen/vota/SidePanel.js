"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

const OPEN_EVENT = "sidepanel:open";

/** Modal drawer from the right for "see more" content, on desktop and mobile. Only one is open at a time. */
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
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: titleId }));
    if (!dialog.open) dialog.showModal();
    const root = document.documentElement;
    root.classList.add("has-sideDrawer");
    const onOther = (e) => e.detail !== titleId && closeRef.current();
    window.addEventListener(OPEN_EVENT, onOther);
    return () => {
      root.classList.remove("has-sideDrawer");
      window.removeEventListener(OPEN_EVENT, onOther);
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
      onKeyDown={(e) => e.stopPropagation()}
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
