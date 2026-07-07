// RuView Service Worker - Offline caching for the dashboard shell
// Strategy: Network-first for API calls, Cache-first for static assets

const CACHE_NAME = 'ruview-v4';
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/config/api.config.js',
  '/components/TabManager.js',
  '/components/DashboardTab.js',
  '/components/LiveDemoTab.js',
  '/components/SensingTab.js',
  '/components/PoseDetectionCanvas.js',
  '/services/api.service.js',
  '/services/websocket.service.js',
  '/services/health.service.js',
  '/services/sensing.service.js',
  '/services/pose.service.js',
  '/services/stream.service.js',
  '/utils/backend-detector.js',
  '/utils/keyboard-shortcuts.js',
  '/utils/perf-monitor.js',
  '/utils/toast.js',
  '/utils/theme-toggle.js',
  '/utils/command-palette.js',
  '/utils/activity-log.js',
  '/utils/data-export.js',
  '/utils/fullscreen.js',
  '/utils/connection-status.js',
  '/utils/mobile-nav.js'
];

// Install - cache shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_ASSETS).catch((err) => {
        // Don't fail install if some assets are missing (dev mode)
        console.warn('[SW] Some assets failed to cache:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate - clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch - network-first for everything, cache only as offline fallback.
// (Cache-first served stale UI after every update; localhost network cost
// is negligible, so freshness wins.)
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip WebSocket upgrade requests
  if (request.headers.get('Upgrade') === 'websocket') return;

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  event.respondWith(networkFirst(request));
});

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // Offline fallback for HTML navigation
    if (request.headers.get('Accept')?.includes('text/html')) {
      const fallback = await caches.match('/index.html');
      if (fallback) return fallback;
    }
    return new Response(JSON.stringify({ error: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
