/* Run the shipped canvas module against a minimal DOM and assert the gestures
 * it must take away from the browser. A test that only checked "it ran" would
 * pass for a module that did nothing, so every claim below names the property
 * or the event it read back.
 */
import {strict as assert} from "node:assert";
import {pathToFileURL} from "node:url";
import path from "node:path";

const release = process.argv[2];
if (!release) {
  console.error("usage: canvas_verify.mjs <release-directory>");
  process.exit(2);
}

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }
  addEventListener(type, handler) {
    const existing = this.listeners.get(type) ?? [];
    existing.push(handler);
    this.listeners.set(type, existing);
  }
  removeEventListener(type, handler) {
    const existing = this.listeners.get(type) ?? [];
    const index = existing.indexOf(handler);
    if (index >= 0) existing.splice(index, 1);
    this.listeners.set(type, existing);
  }
  count(type) {
    return (this.listeners.get(type) ?? []).length;
  }
  dispatch(type, event = {}) {
    let prevented = false;
    const full = {type, preventDefault: () => (prevented = true), ...event};
    for (const handler of [...(this.listeners.get(type) ?? [])]) handler(full);
    return prevented;
  }
}

/* A real CSSStyleDeclaration reads back "" for a property nobody set, never
 * undefined, and restoring "" is how a module puts one back. A plain object
 * would fail the restore assertion for a module that behaves correctly. */
function emptyStringStyle() {
  return new Proxy({}, {
    get: (target, key) => (key in target ? target[key] : (typeof key === "string" ? "" : undefined)),
    set: (target, key, value) => ((target[key] = value), true),
  });
}

class FakeElement extends FakeEventTarget {
  constructor(box) {
    super();
    this.style = emptyStringStyle();
    this.box = box;
  }
  getBoundingClientRect() {
    return this.box;
  }
}

/* `env(safe-area-inset-*)` is a browser feature, so the harness resolves the
 * custom properties the way a device with a notch would: a fixed inset for the
 * top, the CSS fallback of 0 everywhere else. A module that never wrote the
 * properties reads back an empty string and fails the numeric assertions.
 */
const kTopInset = 47;
function fakeComputedStyle(element) {
  return {
    getPropertyValue(name) {
      const declared = element.style.getPropertyValue?.(name) ?? element.style[name];
      if (typeof declared !== "string" || declared === "") return "";
      if (!declared.startsWith("env(")) return declared;
      return name.endsWith("top") ? `${kTopInset}px` : "0px";
    },
  };
}

const documentElement = new FakeElement({width: 0, height: 0, x: 0, y: 0});
documentElement.style = {
  values: new Map(),
  setProperty(name, value) {
    this.values.set(name, value);
  },
  getPropertyValue(name) {
    return this.values.get(name) ?? "";
  },
};

const canvas = new FakeElement({width: 390, height: 844, x: 0, y: 0});
const visualViewport = new FakeEventTarget();
const windowTarget = new FakeEventTarget();

globalThis.Element = FakeElement;
globalThis.document = {documentElement};
globalThis.getComputedStyle = fakeComputedStyle;
globalThis.visualViewport = visualViewport;
globalThis.addEventListener = (type, handler) => windowTarget.addEventListener(type, handler);
globalThis.removeEventListener = (type, handler) => windowTarget.removeEventListener(type, handler);

const module = await import(
  pathToFileURL(path.join(release, "canvas.mjs")).href
);

assert.throws(() => module.claimCanvasGestures(null), TypeError,
  "a missing canvas must be refused, not silently skipped");

const seen = [];
const dispose = module.claimCanvasGestures(canvas, {onViewport: (v) => seen.push(v)});

assert.equal(canvas.style.touchAction, "none",
  "touch-action: none is what stops the page scrolling under a stick drag");
assert.equal(canvas.style.userSelect, "none", "a drag must not select page text");
assert.equal(canvas.style.webkitTouchCallout, "none", "a long press must not open the callout");
assert.equal(documentElement.style.overscrollBehavior, "none",
  "an edge swipe must not fire the overscroll refresh");

assert.equal(canvas.dispatch("contextmenu"), true, "long-press contextmenu must be prevented");
assert.equal(canvas.dispatch("dragstart"), true, "dragging the canvas bitmap must be prevented");

assert.equal(seen.length, 1, "the first viewport must be reported without waiting for a resize");
assert.deepEqual(seen[0].width, 390);
assert.deepEqual(seen[0].height, 844);
assert.equal(seen[0].safeArea.top, kTopInset,
  "the safe-area top inset must reach the consumer, not be reported as zero");
assert.equal(seen[0].safeArea.bottom, 0, "an absent inset resolves to its 0 fallback");

visualViewport.dispatch("resize");
assert.equal(seen.length, 2, "a visual-viewport resize must re-report the viewport");
windowTarget.dispatch("orientationchange");
assert.equal(seen.length, 3, "a rotation must re-report the viewport");

dispose();
assert.equal(canvas.style.touchAction, "", "dispose must restore what it changed");
assert.equal(canvas.count("contextmenu"), 0, "dispose must remove its listeners");
assert.equal(visualViewport.count("resize"), 0, "dispose must remove its viewport listeners");
assert.equal(windowTarget.count("orientationchange"), 0, "dispose must remove its window listeners");
visualViewport.dispatch("resize");
assert.equal(seen.length, 3, "a disposed claim must stop reporting");

console.log("canvas-verify: OK");
