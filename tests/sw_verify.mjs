/* Behavioural check of the SHIPPED service worker template.
 *
 * Loads the rendered worker from the release directory, stubs caches/fetch, and
 * dispatches a real install event twice: once where the network returns the
 * released bytes, and once where it returns the previous deployment's bytes (the
 * stale-HTTP-cache case that broke returning visitors). The first MUST cache the
 * release; the second MUST refuse it.
 */
import { readFileSync } from "node:fs";
import vm from "node:vm";
import crypto from "node:crypto";

const releaseDir = process.argv[2];
const source = readFileSync(`${releaseDir}/service-worker.js`, "utf8");
const release = JSON.parse(/const RELEASE = (.+);/.exec(source)[1]);
const scope = "https://example.test/xmen2/";

function context(network) {
  const stored = new Map();
  const listeners = {};
  const activated = [];
  const caches = {
    open: async () => ({
      put: async (key, response) => stored.set(String(key), response),
      match: async (key) => stored.get(String(key)),
    }),
    keys: async () => [],
    delete: async () => true,
  };
  const sandbox = {
    self: {
      addEventListener: (type, handler) => (listeners[type] = handler),
      registration: { scope },
      clients: { claim: async () => {} },
      location: { origin: "https://example.test" },
      skipWaiting: async () => activated.push(true),
    },
    caches,
    fetch: async (url) => {
      const name = new URL(String(url)).pathname.split("/").pop();
      const body = network(name);
      return body === null
        ? new Response("absent", { status: 404 })
        : new Response(body, { status: 200 });
    },
    crypto: crypto.webcrypto,
    Headers,
    Response,
    URL,
    console,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  return { listeners, stored, activated };
}

async function install(listeners) {
  let settled;
  listeners.install({ waitUntil: (promise) => (settled = promise) });
  return settled;
}

const released = (name) => readFileSync(`${releaseDir}/${name}`);
let failures = 0;
const check = (label, ok, detail) => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` -- ${detail}` : ""}`);
  if (!ok) failures += 1;
};

// 1. The released bytes install, are cached, and take over immediately.
{
  const { listeners, stored, activated } = context((name) => released(name));
  try {
    await install(listeners);
    check("released bytes install", true);
    check("every asset cached", stored.size === release.files.length,
      `${stored.size}/${release.files.length}`);
    check("a served release takes over without waiting", activated.length === 1,
      `${activated.length} skipWaiting call(s)`);
  } catch (error) {
    check("released bytes install", false, error.message);
  }
}

// 2. The previous deployment's bytes are refused, so the cache is never poisoned.
{
  const staleTarget = release.files[0];
  const { listeners, stored, activated } = context((name) =>
    name === staleTarget ? Buffer.from("the previous deployment") : released(name));
  try {
    await install(listeners);
    check("stale bytes refused", false, "install resolved with mismatched bytes");
  } catch (error) {
    check("stale bytes refused", /release hash/.test(error.message), error.message);
    check("nothing cached from a refused install", stored.size === 0, `${stored.size} entries`);
    check("a refused release never takes over", activated.length === 0,
      `${activated.length} skipWaiting call(s)`);
  }
}

// 3. A missing asset is refused rather than silently skipped.
{
  const absentTarget = release.files[release.files.length - 1];
  const { listeners } = context((name) => (name === absentTarget ? null : released(name)));
  try {
    await install(listeners);
    check("absent asset refused", false, "install resolved with a 404 asset");
  } catch (error) {
    check("absent asset refused", /unavailable/.test(error.message), error.message);
  }
}

console.log(failures === 0 ? "sw-verify: OK" : `sw-verify: ${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
