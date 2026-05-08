const CACHE_NAME = 'stock-monitor-v2';
const urlsToCache = [
  '/static/index.html',
  '/static/alerts.html',
  '/static/history.html',
  '/static/server.html',
  '/static/logs.html',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(names =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});