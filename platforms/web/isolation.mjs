/* Static hosts can supply pthread isolation through a same-origin service worker.
 * The consumer must register this before loading its native application. */
export async function prepareApplication(serviceWorker = "service-worker.js") {
  if (!globalThis.isSecureContext || !navigator.serviceWorker) {
    throw new Error("This application needs a secure browser with service workers.");
  }
  const registration = await navigator.serviceWorker.register(serviceWorker, {scope: "./"});
  await isolationReady(registration);
  if (!globalThis.crossOriginIsolated) {
    const key = `web-port-isolation:${new URL(serviceWorker, location.href).pathname}`;
    if (sessionStorage.getItem(key)) {
      throw new Error("Browser isolation is unavailable. Enable service workers and reload this page.");
    }
    sessionStorage.setItem(key, "requested");
    location.reload();
    return false;
  }
  sessionStorage.removeItem(`web-port-isolation:${new URL(serviceWorker, location.href).pathname}`);
  return true;
}

/* navigator.serviceWorker.ready never resolves for a worker whose install was
 * refused -- a release file that 404s or fails its hash -- so awaiting it alone
 * leaves the player on a page that says nothing and will never say anything.
 * Fail by name instead: a worker that reaches "redundant" was rejected. */
async function isolationReady(registration) {
  const rejected = new Promise((_resolve, reject) => {
    const worker = registration.installing ?? registration.waiting;
    if (!worker) return;
    worker.addEventListener("statechange", () => {
      if (worker.state === "redundant") {
        reject(new Error("This application's own resources were refused by the browser cache. Reload to try again."));
      }
    });
  });
  await Promise.race([navigator.serviceWorker.ready, rejected]);
}
