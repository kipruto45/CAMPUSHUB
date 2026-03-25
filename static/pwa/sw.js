/**
 * CampusHub Service Worker
 * Provides offline caching and background sync capabilities
 */

const CACHE_VERSION = 'v2';
const SHELL_CACHE = `campushub-shell-${CACHE_VERSION}`;
const STATIC_CACHE = `campushub-static-${CACHE_VERSION}`;
const API_CACHE = `campushub-api-${CACHE_VERSION}`;
const IMAGE_CACHE = `campushub-images-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline/';

// Assets to cache for offline use (app shell)
const STATIC_ASSETS = [
  '/',
  '/offline/',
  '/index.html',
  '/static/pwa/manifest.json',
  '/static/pwa/icons/icon-192x192.png',
  '/static/pwa/icons/icon-512x512.png',
  '/favicon.ico',
];

// Which API routes to cache for fast warm return (read-only)
const API_CACHE_PATHS = [
  '/api/v1/resources/',
  '/api/v1/courses/',
  '/api/v1/units/',
  '/api/v1/announcements/',
];

// Background sync queue storage
const BG_DB = 'campushub-sync';
const BG_STORE = 'requests';

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  
  event.waitUntil(
    Promise.all([
      caches.open(SHELL_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
      caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
      caches.open(API_CACHE),
      caches.open(IMAGE_CACHE),
    ]).then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      const allowed = [SHELL_CACHE, STATIC_CACHE, API_CACHE, IMAGE_CACHE];
      return Promise.all(
        cacheNames.map((cacheName) => {
          // Delete old version caches
          if (!allowed.includes(cacheName)) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// Fetch event - handle requests with appropriate strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Queue write operations when offline
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method)) {
    event.respondWith(sendOrQueue(request));
    return;
  }

  // Skip Chrome extensions and other non-http requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // Handle API requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }

  // Handle static assets
  if (isStaticAsset(url.pathname)) {
    event.respondWith(handleStaticRequest(request));
    return;
  }

  // Handle media/images
  if (url.pathname.startsWith('/media/')) {
    event.respondWith(handleImageRequest(request));
    return;
  }

  // Default: network with cache fallback
  event.respondWith(handleDefaultRequest(request));
});

// Check if request is for static asset
function isStaticAsset(pathname) {
  const staticExtensions = ['.js', '.css', '.woff', '.woff2', '.ttf', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico'];
  return staticExtensions.some(ext => pathname.endsWith(ext));
}

// IndexedDB helpers for offline queue
function openQueueDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(BG_DB, 1);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(BG_STORE)) {
        db.createObjectStore(BG_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = (event) => resolve(event.target.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

async function queueRequest(request) {
  try {
    const db = await openQueueDB();
    const tx = db.transaction(BG_STORE, 'readwrite');
    const store = tx.objectStore(BG_STORE);

    const headers = {};
    request.headers.forEach((value, key) => {
      headers[key] = value;
    });

    const body = ['GET', 'HEAD'].includes(request.method) ? null : await request.clone().text();

    const requestToStore = {
      url: request.url,
      method: request.method,
      headers,
      body,
      queuedAt: Date.now(),
    };

    store.add(requestToStore);

    await new Promise((resolve) => {
      tx.oncomplete = resolve;
      tx.onerror = resolve;
      tx.onabort = resolve;
    });
    await self.registration.sync.register('bg-sync-queue');

    return new Response(
      JSON.stringify({ queued: true, offline: true }),
      { status: 202, headers: { 'Content-Type': 'application/json', 'X-Queued-Offline': 'true' } }
    );
  } catch (err) {
    console.error('[SW] Failed to queue request', err);
    return new Response(
      JSON.stringify({ offline: true, queued: false, error: 'Queue unavailable' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function replayQueuedRequests() {
  const db = await openQueueDB();
  const tx = db.transaction(BG_STORE, 'readwrite');
  const store = tx.objectStore(BG_STORE);
  const all = await store.getAll();

  for (const entry of all) {
    try {
      const response = await fetch(entry.url, {
        method: entry.method,
        headers: entry.headers,
        body: entry.body,
      });
      if (response.ok || response.status < 500) {
        store.delete(entry.id);
      }
    } catch (err) {
      console.warn('[SW] Replay failed, will retry later', err);
    }
  }

  await new Promise((resolve) => {
    tx.oncomplete = resolve;
    tx.onerror = resolve;
    tx.onabort = resolve;
  });
}

async function sendOrQueue(request) {
  try {
    const networkResponse = await fetch(request.clone());
    return networkResponse;
  } catch (error) {
    console.warn('[SW] Offline, queuing request', request.url);
    return queueRequest(request);
  }
}

// Handle API requests - network first with cache fallback
async function handleApiRequest(request) {
  const cache = await caches.open(API_CACHE);
  const shouldCacheFirst = API_CACHE_PATHS.some((path) => request.url.includes(path));

  if (shouldCacheFirst) {
    const cached = await cache.match(request);
    if (cached) {
      fetch(request).then((resp) => resp.ok && cache.put(request, resp.clone())).catch(() => {});
      return cached;
    }
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    const cachedResponse = await cache.match(request) || await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return new Response(
      JSON.stringify({ error: 'Offline', cached: false }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// Handle static requests - cache first
async function handleStaticRequest(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cachedResponse = await cache.match(request);

  // Stale-while-revalidate: serve cached immediately, refresh in background
  if (cachedResponse) {
    eventlessRefresh(request, cache);
    return cachedResponse;
  }

  // If no cache hit, go network-first but cache result for next time
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    return new Response('Offline', { status: 503 });
  }
}

function eventlessRefresh(request, cache) {
  fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
    })
    .catch(() => {});
}

// Handle image requests - cache first with long TTL
async function handleImageRequest(request) {
  const cache = await caches.open(IMAGE_CACHE);
  const cachedResponse = await cache.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    // Return placeholder image for offline
    return new Response(
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="#eee" width="100" height="100"/><text x="50" y="50" text-anchor="middle" dy=".3em" fill="#999">Offline</text></svg>',
      { headers: { 'Content-Type': 'image/svg+xml' } }
    );
  }
}

// Handle default requests - network first
async function handleDefaultRequest(request) {
  try {
    return await fetch(request);
  } catch (error) {
    // Try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const cache = await caches.open(SHELL_CACHE);
      return cache.match(OFFLINE_URL) || new Response('Offline', { status: 503 });
    }
    
    return new Response('Offline', { status: 503 });
  }
}

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync:', event.tag);
  
  if (event.tag === 'bg-sync-queue') {
    event.waitUntil(replayQueuedRequests());
  } else if (event.tag.startsWith('sync-')) {
    event.waitUntil(handleBackgroundSync(event.tag));
  }
});

async function handleBackgroundSync(tag) {
  // Handle different sync types
  if (tag === 'sync-bookmarks') {
    await syncBookmarks();
  } else if (tag === 'sync-uploads') {
    await syncUploads();
  } else if (tag === 'sync-messages') {
    await syncMessages();
  }
}

async function syncBookmarks() {
  // Get pending bookmark operations from IndexedDB
  // This would require additional IndexedDB setup
  console.log('[SW] Syncing bookmarks...');
}

async function syncUploads() {
  console.log('[SW] Syncing uploads...');
}

async function syncMessages() {
  console.log('[SW] Syncing messages...');
}

// Push notifications
self.addEventListener('push', (event) => {
  console.log('[SW] Push notification received');
  
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'CampusHub';
  const options = {
    body: data.body || 'You have a new notification',
    icon: '/static/pwa/icons/icon-192x192.png',
    badge: '/static/pwa/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/',
      timestamp: Date.now(),
    },
    actions: data.actions || [],
  };
  
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked');
  
  event.notification.close();
  
  const url = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus existing window if available
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      // Open new window
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

// Message handling from main app
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);
  
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data.type === 'CACHE_URLS') {
    // Pre-cache specific URLs
    event.waitUntil(
      caches.open(SHELL_CACHE).then((cache) => {
        return cache.addAll(event.data.urls);
      })
    );
  } else if (event.data.type === 'CLEAR_CACHE') {
    // Clear specific caches
    event.waitUntil(
      caches.keys().then((names) => {
        return Promise.all(names.map(name => caches.delete(name)));
      })
    );
  }
});

console.log('[SW] Service worker loaded');
