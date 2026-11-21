// Alerta JF service worker: network-first for the app shell and static assets.
// Live data (Supabase, weather, official sources) is never cached.
const CACHE = "alertajf-v1";
const CACHEABLE = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png", "/og-image.png"];
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => { event.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (!(url.pathname.startsWith("/assets/") || CACHEABLE.includes(url.pathname))) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) { const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put(event.request, copy)); }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || Response.error()))
  );
});
