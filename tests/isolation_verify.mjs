/* Run the shipped isolation module against a fake service-worker registry. The
 * case that matters is the one a player cannot see: a worker whose install was
 * refused never makes navigator.serviceWorker.ready resolve, so a module that
 * only awaited it would leave the page silent forever. Every assertion below
 * names the state it read back, and the refusal cases are required to refuse.
 */
import {strict as assert} from "node:assert";
import {pathToFileURL} from "node:url";
import path from "node:path";

const release = process.argv[2];
if (!release) {
  console.error("usage: isolation_verify.mjs <release-directory>");
  process.exit(2);
}

class FakeWorker {
  constructor(state) {
    this.state = state;
    this.listeners = [];
  }
  addEventListener(type, handler) {
    if (type === "statechange") this.listeners.push(handler);
  }
  become(state) {
    this.state = state;
    for (const handler of [...this.listeners]) handler({type: "statechange"});
  }
}

let reloads = 0;
let registered = [];

function install({ready, installing = null, isolated}) {
  reloads = 0;
  registered = [];
  const store = new Map();
  Object.defineProperty(globalThis, "isSecureContext", {value: true, configurable: true});
  Object.defineProperty(globalThis, "crossOriginIsolated", {value: isolated, configurable: true});
  Object.defineProperty(globalThis, "location", {
    value: {href: "https://example.test/game/", reload: () => (reloads += 1)},
    configurable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    value: {
      getItem: key => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
      removeItem: key => store.delete(key),
    },
    configurable: true,
  });
  Object.defineProperty(globalThis, "navigator", {
    value: {
      serviceWorker: {
        ready,
        register: async (script, options) => {
          registered.push([script, options?.scope]);
          return {installing, waiting: null};
        },
      },
    },
    configurable: true,
  });
  return store;
}

async function withinSeconds(what, seconds, work) {
  let timer;
  const expired = new Promise((_resolve, reject) => {
    timer = setTimeout(() => reject(new Error(`${what} did not answer within ${seconds}s`)), seconds * 1000);
  });
  try {
    return await Promise.race([work(), expired]);
  } finally {
    clearTimeout(timer);
  }
}

const module = await import(pathToFileURL(path.join(release, "isolation.mjs")).href);

/* The ordinary second load: the worker is active and the page is isolated. */
install({ready: Promise.resolve({}), isolated: true});
assert.equal(await withinSeconds("prepareApplication() when isolated", 5, () => module.prepareApplication()), true,
  "an isolated page is told to go ahead");
assert.deepEqual(registered, [["service-worker.js", "./"]], "the worker is registered once, at the page's own scope");
assert.equal(reloads, 0, "an isolated page is not reloaded");

/* The ordinary first load: isolation arrives only after the worker controls it. */
const store = install({ready: Promise.resolve({}), isolated: false});
assert.equal(await withinSeconds("prepareApplication() on the first load", 5, () => module.prepareApplication()), false,
  "the first load does not proceed; it reloads into isolation");
assert.equal(reloads, 1, "the page is reloaded exactly once");
assert.equal(store.size, 1, "the reload is remembered, so a second failure is not an endless loop");

/* The same page again, still not isolated: refuse rather than reload forever. */
const looping = install({ready: Promise.resolve({}), isolated: false});
looping.set("web-port-isolation:/game/service-worker.js", "requested");
await assert.rejects(() => module.prepareApplication(), /isolation is unavailable/,
  "a second unisolated load is refused by name");
assert.equal(reloads, 0, "a refused page is not reloaded again");

/* The case that has no voice of its own: the worker's install was refused, so
 * ready never resolves. A module that only awaited it hangs here. */
const refused = new FakeWorker("installing");
install({ready: new Promise(() => {}), installing: refused, isolated: false});
const attempt = module.prepareApplication();
const settled = withinSeconds("prepareApplication() with a refused worker install", 5, () => attempt);
// The module only sees the worker once its own register() has resolved, so let
// that happen before the browser refuses the install.
await new Promise(resolve => setTimeout(resolve, 50));
assert.equal(registered.length, 1, "the worker was registered before its install was refused");
refused.become("redundant");
await assert.rejects(() => settled, /resources were refused/,
  "a refused worker install is reported, not waited on");

/* No service workers at all, and no secure context, are refused by name. */
install({ready: Promise.resolve({}), isolated: true});
delete globalThis.navigator.serviceWorker;
await assert.rejects(() => module.prepareApplication(), /secure browser with service workers/,
  "a browser without service workers is refused");

install({ready: Promise.resolve({}), isolated: true});
Object.defineProperty(globalThis, "isSecureContext", {value: false, configurable: true});
await assert.rejects(() => module.prepareApplication(), /secure browser with service workers/,
  "an insecure context is refused");

console.log("isolation-verify: OK");
