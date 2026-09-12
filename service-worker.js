const CACHE_NAME = "diario-autista-v40-rapportino-esterno-password";
const PRECACHE = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192-v37.png",
  "./icon-512-v37.png",
  "./apple-touch-icon.png",
  "./torabook-header.png",
  "./RAPPORTINO_SETTIMANALE.xlsx"
];
const HGV_DB = "./hgv_europe.json";
const RAPPORTINO_TEMPLATE = "./RAPPORTINO_SETTIMANALE.xlsx";

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(PRECACHE);
    // Il database HGV e' utile offline, ma non deve impedire l'installazione
    // della PWA se GitHub Pages lo sta ancora propagando.
    try { await cache.add(HGV_DB); } catch (_) {}
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(key => key.startsWith("diario-autista-") && key !== CACHE_NAME)
        .map(key => caches.delete(key))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("message", event => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

async function networkFirst(request, fallbackKey) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (response && response.ok) {
      await cache.put(fallbackKey || request, response.clone());
    }
    return response;
  } catch (err) {
    return (await cache.match(fallbackKey || request)) || Response.error();
  }
}

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // Google Drive e librerie esterne restano fuori dal service worker.
  if (url.origin !== self.location.origin) return;

  // HTML: sempre rete prima, cache solo come fallback offline.
  if (event.request.mode === "navigate" || url.pathname.endsWith("/index.html")) {
    event.respondWith(networkFirst(event.request, "./index.html"));
    return;
  }

  // Database HGV: sempre rete prima. Il ?t=... del pulsante Aggiorna
  // non crea infinite copie: salviamo sempre nella chiave canonica.
  if (url.pathname.endsWith("/hgv_europe.json")) {
    event.respondWith(networkFirst(event.request, HGV_DB));
    return;
  }

  // Modello Rapportino Excel: rete prima, cache offline come fallback.
  if (url.pathname.endsWith("/RAPPORTINO_SETTIMANALE.xlsx")) {
    event.respondWith(networkFirst(event.request, RAPPORTINO_TEMPLATE));
    return;
  }

  // Manifest e icone: cache-first con aggiornamento in background.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(event.request);
    const network = fetch(event.request, { cache: "no-store" })
      .then(response => {
        if (response && response.ok) cache.put(event.request, response.clone());
        return response;
      })
      .catch(() => null);

    if (cached) {
      event.waitUntil(network);
      return cached;
    }
    return (await network) || Response.error();
  })());
});
