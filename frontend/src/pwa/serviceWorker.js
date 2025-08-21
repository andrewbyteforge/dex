/* eslint-env serviceworker */

/**
 * DEX Sniper Pro Service Worker
 * 
 * Provides offline functionality, caching strategies, and background sync
 * for the trading application. Optimized for financial data freshness
 * while maintaining performance.
 */

const CACHE_NAME = 'dex-sniper-v1.0.0';
const STATIC_CACHE = `${CACHE_NAME}-static`;
const DYNAMIC_CACHE = `${CACHE_NAME}-dynamic`;
const API_CACHE = `${CACHE_NAME}-api`;

// Cache duration settings (in milliseconds)
const CACHE_DURATIONS = {
  STATIC: 7 * 24 * 60 * 60 * 1000,    // 7 days for static assets
  API: 5 * 60 * 1000,                  // 5 minutes for API responses
  QUOTES: 30 * 1000,                   // 30 seconds for price quotes
  HEALTH: 60 * 1000                    // 1 minute for health checks
};

// URLs to cache on install
const STATIC_ASSETS = [
  '/',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  // Bootstrap and core CSS
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  // Offline fallback page
  '/offline.html'
];

// API endpoints that should be cached with short TTL
const CACHEABLE_API_PATTERNS = [
  /^\/api\/v1\/health\//,
  /^\/api\/v1\/chains\//,
  /^\/api\/v1\/tokens\/metadata\//,
  /^\/api\/v1\/wallet\/balances\//
];

// API endpoints that should NEVER be cached (real-time trading data)
const NEVER_CACHE_PATTERNS = [
  /^\/api\/v1\/quotes\//,
  /^\/api\/v1\/trades\//,
  /^\/api\/v1\/pairs\/discovery\//,
  /^\/ws\//,
  /^\/api\/v1\/autotrade\/execute/
];

/**
 * Install event - Cache static assets
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  
  event.waitUntil(
    (async () => {
      try {
        const staticCache = await caches.open(STATIC_CACHE);
        await staticCache.addAll(STATIC_ASSETS);
        console.log('[SW] Static assets cached successfully');
        
        // Skip waiting to activate immediately
        await self.skipWaiting();
      } catch (error) {
        console.error('[SW] Failed to cache static assets:', error);
      }
    })()
  );
});

/**
 * Activate event - Clean up old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  
  event.waitUntil(
    (async () => {
      try {
        // Clean up old caches
        const cacheNames = await caches.keys();
        const oldCaches = cacheNames.filter(name => 
          name.startsWith('dex-sniper-') && name !== STATIC_CACHE && name !== DYNAMIC_CACHE && name !== API_CACHE
        );
        
        await Promise.all(oldCaches.map(name => caches.delete(name)));
        console.log('[SW] Old caches cleaned up:', oldCaches);
        
        // Take control of all clients immediately
        await self.clients.claim();
      } catch (error) {
        console.error('[SW] Activation failed:', error);
      }
    })()
  );
});

/**
 * Fetch event - Handle network requests with caching strategies
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests and chrome-extension requests
  if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
    return;
  }
  
  // Handle different types of requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
  } else if (url.pathname.startsWith('/ws/')) {
    // Let WebSocket requests pass through
    return;
  } else {
    event.respondWith(handleStaticRequest(request));
  }
});

/**
 * Handle API requests with appropriate caching strategy
 */
async function handleApiRequest(request) {
  const url = new URL(request.url);
  
  // Never cache real-time trading endpoints
  if (NEVER_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))) {
    try {
      return await fetch(request);
    } catch (error) {
      console.warn('[SW] Real-time API request failed:', error);
      return new Response(
        JSON.stringify({ 
          error: 'Network unavailable', 
          offline: true,
          timestamp: Date.now()
        }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }
  }
  
  // Cache-first strategy for suitable API endpoints
  if (CACHEABLE_API_PATTERNS.some(pattern => pattern.test(url.pathname))) {
    return await cacheFirstStrategy(request, API_CACHE, CACHE_DURATIONS.API);
  }
  
  // Network-first for other API requests
  return await networkFirstStrategy(request, API_CACHE, CACHE_DURATIONS.API);
}

/**
 * Handle static asset requests
 */
async function handleStaticRequest(request) {
  const url = new URL(request.url);
  
  // Cache-first for static assets
  if (STATIC_ASSETS.some(asset => url.pathname === asset || url.pathname.startsWith('/static/'))) {
    return await cacheFirstStrategy(request, STATIC_CACHE, CACHE_DURATIONS.STATIC);
  }
  
  // Stale-while-revalidate for other resources
  return await staleWhileRevalidateStrategy(request, DYNAMIC_CACHE, CACHE_DURATIONS.STATIC);
}

/**
 * Cache-first strategy: Check cache first, fallback to network
 */
async function cacheFirstStrategy(request, cacheName, maxAge) {
  try {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse && !isExpired(cachedResponse, maxAge)) {
      return cachedResponse;
    }
    
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const responseClone = networkResponse.clone();
      await cache.put(request, responseClone);
    }
    
    return networkResponse;
  } catch (error) {
    console.warn('[SW] Cache-first strategy failed:', error);
    
    // Return cached version even if expired
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline fallback
    return await getOfflineFallback(request);
  }
}

/**
 * Network-first strategy: Try network first, fallback to cache
 */
async function networkFirstStrategy(request, cacheName, maxAge) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      const responseClone = networkResponse.clone();
      await cache.put(request, responseClone);
    }
    
    return networkResponse;
  } catch (error) {
    console.warn('[SW] Network-first strategy failed, checking cache:', error);
    
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse && !isExpired(cachedResponse, maxAge)) {
      return cachedResponse;
    }
    
    return await getOfflineFallback(request);
  }
}

/**
 * Stale-while-revalidate strategy: Return cache immediately, update in background
 */
async function staleWhileRevalidateStrategy(request, cacheName, maxAge) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);
  
  // Fetch in background (don't await)
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(error => {
    console.warn('[SW] Background fetch failed:', error);
  });
  
  // Return cached response immediately if available
  if (cachedResponse) {
    return cachedResponse;
  }
  
  // If no cache, wait for network
  try {
    return await fetchPromise;
  } catch (error) {
    return await getOfflineFallback(request);
  }
}

/**
 * Check if cached response is expired
 */
function isExpired(response, maxAge) {
  const dateHeader = response.headers.get('date');
  if (!dateHeader) return true;
  
  const responseTime = new Date(dateHeader).getTime();
  const now = Date.now();
  
  return (now - responseTime) > maxAge;
}

/**
 * Get offline fallback response
 */
async function getOfflineFallback(request) {
  const url = new URL(request.url);
  
  // For API requests, return JSON error
  if (url.pathname.startsWith('/api/')) {
    return new Response(
      JSON.stringify({
        error: 'Offline - No cached data available',
        offline: true,
        timestamp: Date.now()
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
  
  // For page requests, return offline page
  try {
    const cache = await caches.open(STATIC_CACHE);
    const offlinePage = await cache.match('/offline.html');
    if (offlinePage) {
      return offlinePage;
    }
  } catch (error) {
    console.error('[SW] Failed to serve offline page:', error);
  }
  
  // Final fallback
  return new Response(
    '<!DOCTYPE html><html><head><title>Offline</title></head><body><h1>You are offline</h1><p>Please check your internet connection.</p></body></html>',
    {
      status: 503,
      headers: { 'Content-Type': 'text/html' }
    }
  );
}

/**
 * Background sync for failed API requests
 */
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync event:', event.tag);
  
  if (event.tag === 'trade-sync') {
    event.waitUntil(syncFailedTrades());
  } else if (event.tag === 'analytics-sync') {
    event.waitUntil(syncAnalyticsData());
  }
});

/**
 * Sync failed trade requests when back online
 */
async function syncFailedTrades() {
  try {
    // This would integrate with IndexedDB to replay failed trades
    console.log('[SW] Syncing failed trades...');
    
    // Implementation would depend on how failed trades are stored
    // For now, just log the sync attempt
  } catch (error) {
    console.error('[SW] Failed to sync trades:', error);
  }
}

/**
 * Sync analytics data when back online
 */
async function syncAnalyticsData() {
  try {
    console.log('[SW] Syncing analytics data...');
    
    // Implementation for analytics sync
  } catch (error) {
    console.error('[SW] Failed to sync analytics:', error);
  }
}

/**
 * Handle push notifications (future feature)
 */
self.addEventListener('push', (event) => {
  const options = {
    body: 'New trading opportunity detected!',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'View Details',
        icon: '/icons/action-explore.png'
      },
      {
        action: 'close',
        title: 'Dismiss',
        icon: '/icons/action-close.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('DEX Sniper Pro', options)
  );
});

/**
 * Handle notification clicks
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'explore') {
    // Open the app to the relevant section
    event.waitUntil(
      self.clients.openWindow('/?tab=trade&notification=true')
    );
  }
});

/**
 * Message handling for communication with main thread
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type) {
    switch (event.data.type) {
      case 'SKIP_WAITING':
        self.skipWaiting();
        break;
      case 'CACHE_URLS':
        event.waitUntil(cacheUrls(event.data.payload));
        break;
      case 'CLEAR_CACHE':
        event.waitUntil(clearCache(event.data.payload));
        break;
      default:
        console.log('[SW] Unknown message type:', event.data.type);
    }
  }
});

/**
 * Cache specific URLs on demand
 */
async function cacheUrls(urls) {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    await cache.addAll(urls);
    console.log('[SW] URLs cached on demand:', urls);
  } catch (error) {
    console.error('[SW] Failed to cache URLs:', error);
  }
}

/**
 * Clear specific cache
 */
async function clearCache(cacheName) {
  try {
    const success = await caches.delete(cacheName || DYNAMIC_CACHE);
    console.log('[SW] Cache cleared:', cacheName, success);
  } catch (error) {
    console.error('[SW] Failed to clear cache:', error);
  }
}