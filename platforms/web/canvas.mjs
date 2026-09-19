/* A game canvas in a browser competes with the browser's own gestures.
 *
 * A drag that the page has not claimed scrolls it, a second finger zooms it, a
 * long press opens the context menu and a swipe past the top or bottom edge
 * fires the overscroll refresh. All four land on the element the player is
 * trying to play on, so an on-screen stick is unusable until the page says
 * these gestures belong to the application. Measured before this existed: one
 * 12-step drag up the middle of a 390x844 canvas scrolled the document 551px
 * and the game saw nothing.
 *
 * This is the page-side half of touch play. The application still owns what a
 * contact means; this owns only whether the contact arrives at all.
 */

const kInsetProperties = ["top", "right", "bottom", "left"];

/** Read the platform's safe-area insets, in CSS pixels.
 *
 * `env(safe-area-inset-*)` is only readable through a property that resolves
 * it, so this parks the four values on custom properties and reads them back.
 * A browser without the feature resolves the fallback, which is 0 -- the same
 * answer as a device with no notch, and the right one for both.
 */
export function safeAreaInsets(element = document.documentElement) {
  for (const side of kInsetProperties) {
    element.style.setProperty(`--web-port-safe-${side}`, `env(safe-area-inset-${side}, 0px)`);
  }
  const computed = getComputedStyle(element);
  const insets = {};
  for (const side of kInsetProperties) {
    const value = Number.parseFloat(computed.getPropertyValue(`--web-port-safe-${side}`));
    insets[side] = Number.isFinite(value) ? value : 0;
  }
  return insets;
}

/** Give the application every gesture that lands on its canvas.
 *
 * `onViewport` is called with the canvas size in CSS pixels and the current
 * safe-area insets whenever either can have changed, so a consumer can hand
 * them to its runtime. It is called once immediately, so a consumer never has
 * to guess the first value.
 *
 * Returns a function that undoes every listener and style this applied.
 */
export function claimCanvasGestures(canvas, {onViewport} = {}) {
  if (!(canvas instanceof Element)) {
    throw new TypeError("claimCanvasGestures needs the canvas element");
  }

  // `touch-action: none` is what stops the scroll and the pinch. The rest keep
  // a held or dragged finger from selecting text, opening the callout menu, or
  // dragging the canvas as an image.
  const applied = {
    touchAction: "none",
    userSelect: "none",
    webkitUserSelect: "none",
    webkitTouchCallout: "none",
    webkitTapHighlightColor: "transparent",
  };
  const previous = {};
  for (const [property, value] of Object.entries(applied)) {
    previous[property] = canvas.style[property];
    canvas.style[property] = value;
  }
  const previousOverscroll = document.documentElement.style.overscrollBehavior;
  document.documentElement.style.overscrollBehavior = "none";

  // A long press still raises contextmenu even with the callout suppressed,
  // and a drag can still start a native drag of the canvas bitmap.
  const swallow = (event) => event.preventDefault();
  canvas.addEventListener("contextmenu", swallow);
  canvas.addEventListener("dragstart", swallow);

  const report = () => {
    if (!onViewport) {
      return;
    }
    const box = canvas.getBoundingClientRect();
    onViewport({width: box.width, height: box.height, safeArea: safeAreaInsets()});
  };
  const viewport = globalThis.visualViewport;
  viewport?.addEventListener("resize", report);
  viewport?.addEventListener("scroll", report);
  addEventListener("orientationchange", report);
  addEventListener("resize", report);
  report();

  return () => {
    for (const [property, value] of Object.entries(previous)) {
      canvas.style[property] = value;
    }
    document.documentElement.style.overscrollBehavior = previousOverscroll;
    canvas.removeEventListener("contextmenu", swallow);
    canvas.removeEventListener("dragstart", swallow);
    viewport?.removeEventListener("resize", report);
    viewport?.removeEventListener("scroll", report);
    removeEventListener("orientationchange", report);
    removeEventListener("resize", report);
  };
}
