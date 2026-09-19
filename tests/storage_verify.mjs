/* Run the shipped storage module against a fake Storage Manager and assert the
 * one property that a browser can break: readiness must not wait on a
 * permission request. The interesting case is a persist() that never settles,
 * so the harness resolves nothing and requires persistentStorage() to answer
 * anyway; a module that awaited the request would simply hang here, which the
 * timeout below reports by name rather than as a silent test-runner death.
 */
import {strict as assert} from "node:assert";
import {pathToFileURL} from "node:url";
import path from "node:path";

const release = process.argv[2];
if (!release) {
  console.error("usage: storage_verify.mjs <release-directory>");
  process.exit(2);
}

const ROOT = {marker: "opfs-root"};

function install({persist, persisted}) {
  const storage = {
    getDirectory: async () => ROOT,
    persist,
    persisted,
  };
  Object.defineProperty(globalThis, "navigator", {value: {storage}, configurable: true});
  Object.defineProperty(globalThis, "isSecureContext", {value: true, configurable: true});
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

const module = await import(pathToFileURL(path.join(release, "storage.mjs")).href);

/* A browser that leaves the permission question open. */
let asked = 0;
install({
  persist: () => { asked += 1; return new Promise(() => {}); },
  persisted: async () => false,
});
const unanswered = await withinSeconds("persistentStorage() with an unanswered prompt", 5,
  () => module.persistentStorage());
assert.equal(unanswered.root, ROOT, "the caller receives the OPFS root");
assert.equal(unanswered.persistent, false, "an unanswered request is reported as storage that may be reclaimed");
assert.equal(asked, 1, "the request is still made, once");
assert.ok(unanswered.granted instanceof Promise, "the pending answer is handed back to the caller");

/* A browser that grants it, late. The caller's note must be able to improve. */
let grant;
install({
  persist: () => new Promise(resolve => (grant = resolve)),
  persisted: async () => false,
});
const late = await withinSeconds("persistentStorage() with a late grant", 5,
  () => module.persistentStorage());
assert.equal(late.persistent, false, "before the answer arrives the state is what persisted() reports");
grant(true);
assert.equal(await late.granted, true, "the caller learns that persistence was granted");

/* A browser that refuses by rejecting. The caller must still be told, not thrown at. */
install({
  persist: () => Promise.reject(new Error("denied")),
  persisted: async () => false,
});
const refused = await withinSeconds("persistentStorage() with a rejected request", 5,
  () => module.persistentStorage());
assert.equal(await refused.granted, false, "a rejected request reads as not granted");

/* Storage already persistent from an earlier visit. */
install({persist: async () => true, persisted: async () => true});
const already = await withinSeconds("persistentStorage() with storage already granted", 5,
  () => module.persistentStorage());
assert.equal(already.persistent, true, "an earlier grant is reported without waiting for a new one");

/* A browser with no private storage at all is refused by name. */
install({persist: async () => true, persisted: async () => true});
delete globalThis.navigator.storage.getDirectory;
await assert.rejects(() => module.persistentStorage(), /private persistent storage/,
  "a browser without OPFS is refused, not given an empty root");

console.log("storage-verify: OK");
