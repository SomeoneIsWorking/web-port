/* Rendered by the consumer's packager. Only explicitly listed redistributable
 * application resources are cached. Player files remain exclusively in OPFS. */
const RELEASE = __WEB_PORT_RELEASE__;
const cachePrefix = `web-port-app:${self.registration.scope}:`;
const cacheName = cachePrefix + RELEASE.version;
const assets = new Set(RELEASE.files.map(path => new URL(path, self.registration.scope).href));

function releaseName(url) {
  return new URL(url).pathname.split("/").pop();
}

function hex(bytes) {
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

/* Populate the release cache from the network and refuse any body whose digest
 * is not the one this release was addressed with. cache.addAll() would accept a
 * response out of the browser's HTTP cache, so a browser that had loaded the
 * previous deployment could store those bytes under this release's version name
 * and serve them for as long as that version stayed current. */
async function fetchVerified(url) {
  const response = await fetch(url, {cache: "reload"});
  if (!response.ok) {
    throw new Error(`Application resource unavailable: ${url}`);
  }
  const expected = RELEASE.hashes[releaseName(url)];
  if (!expected) {
    throw new Error(`Application resource is absent from the release hashes: ${url}`);
  }
  const observed = hex(await crypto.subtle.digest("SHA-256", await response.clone().arrayBuffer()));
  if (observed !== expected) {
    throw new Error(`Application resource does not match its release hash: ${url}`);
  }
  return response;
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    // Verify every body before writing any of them, so an install that must be
    // refused does not leave a partially populated release behind.
    const verified = await Promise.all(
      [...assets].map(async url => [url, await fetchVerified(url)])
    );
    const cache = await caches.open(cacheName);
    await Promise.all(verified.map(([url, response]) => cache.put(url, response)));
    // Otherwise the new worker waits for every client of the old one to close,
    // and a player who keeps the page open never receives the new release.
    // Activation claims the open clients, so the next load serves it.
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(cachePrefix) && key !== cacheName) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  /* A query string names arguments for the page, not a different file. Keeping
   * it in the lookup made "index.html?arg=..." miss the release cache, so that
   * navigation was answered by the network WITHOUT the isolation headers below
   * and the page loaded without cross-origin isolation -- which reads as the
   * browser refusing service workers rather than as this line. */
  const resource = new URL(url.pathname, url.origin);
  if (resource.href === self.registration.scope) resource.pathname += "index.html";
  if (!assets.has(resource.href)) return;
  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    const response = await cache.match(resource.href);
    if (!response) throw new Error(`Application resource absent from release cache: ${resource.pathname}`);
    const headers = new Headers(response.headers);
    headers.set("Cross-Origin-Opener-Policy", "same-origin");
    headers.set("Cross-Origin-Embedder-Policy", "require-corp");
    headers.set("Cross-Origin-Resource-Policy", "same-origin");
    return new Response(response.body, {status: response.status, statusText: response.statusText, headers});
  })());
});
