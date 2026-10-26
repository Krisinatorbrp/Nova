// Nova website: keeps the app (and the AI library) available offline after the first visit.
// Pages and scripts: fresh from the network when online, from the cache when offline.
const CACHE = 'nova-web-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // the AI model files are huge and stored by the AI library itself: leave them alone
  if (/huggingface\.co|hf\.co|raw\.githubusercontent\.com/.test(url.hostname)) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const res = await fetch(req);
      if (res.ok && (url.origin === location.origin || url.hostname === 'cdn.jsdelivr.net')) cache.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await cache.match(req, { ignoreSearch: url.origin === location.origin });
      if (hit) return hit;
      throw err;
    }
  })());
});
