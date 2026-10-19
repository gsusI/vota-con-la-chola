// Pointer x in the SVG's own user units (viewBox coordinates), whatever element received the event
// (usually a hit rect that starts inside the plot) and however CSS scales the drawing.
export function svgPointerX(event) {
  const target = event.currentTarget;
  const svg = target.ownerSVGElement || target;
  const ctm = svg.getScreenCTM();
  if (ctm) return (event.clientX - ctm.e) / ctm.a;
  const rect = svg.getBoundingClientRect();
  return ((event.clientX - rect.left) / rect.width) * svg.viewBox.baseVal.width;
}
