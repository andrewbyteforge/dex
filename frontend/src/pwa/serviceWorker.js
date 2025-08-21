/**
 * DEX Sniper Pro - Service Worker
 * 
 * Provides offline functionality, caching strategies, and background sync
 * for the PWA experience.
 */

const CACHE_NAME = 'dex-sniper-pro-v1.0.0';
const OFFLINE_URL = '/offline.html';

// Static assets to cache on install
const STATIC_CACHE_URLS = [
  '/',
  '/offline.html',
  '/manifest.json',
  '/static/js/bundle.js',
  '/static/css/main.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
];

// API endpoints that should be cached
const API_CACHE_PATTERNS = [
  /^\/api\/v1\/health\//,
  /^\/api\/v1\/analytics\//,
  /^\/api\/v1\/presets\//
];

// Real-time endpoints that should never be cached
const NO_CACHE_PATTERNS = [
  /^\/api\/v1\/trades\//,
  /^\/api\/v1\/quotes\//,
  /^\/api\/v1\/discovery\//,
  /^\/ws\//
];

self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Pre-caching offline page and static assets');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => {
        // Force the waiting service worker to become the active service worker
        return self.skipWaiting();
      })
  );
});

self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Removing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip real-time endpoints
  if (NO_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))) {
    return;
  }
  
  // Handle API requests with network-first strategy
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }
  
  // Handle navigation requests
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(request));
    return;
  }
  
  // Handle static assets with cache-first strategy
  event.respondWith(handleStaticRequest(request));
});

/**
 * Handle API requests with network-first strategy
 */
async function handleApiRequest(request) {
  const url = new URL(request.url);
  
  try {
    // Try network first
    const response = await fetch(request);
    
    // Cache successful API responses for certain endpoints
    if (response.ok && API_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[ServiceWorker] Network failed for API request, trying cache:', url.pathname);
    
    // Fall back to cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline API response for critical endpoints
    if (url.pathname.includes('/health')) {
      return new Response(JSON.stringify({
        status: 'OFFLINE',
        healthy: false,
        subsystems: {},
        uptime_seconds: 0,
        message: 'Service worker offline mode'
      }), {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      });
    }
    
    // Return generic error for other API endpoints
    return new Response(JSON.stringify({
      error: 'Network unavailable',
      message: 'This feature requires an internet connection'
    }), {
      headers: { 'Content-Type': 'application/json' },
      status: 503
    });
  }
}

/**
 * Handle navigation requests with offline fallback
 */
async function handleNavigationRequest(request) {
  try {
    // Try network first
    const response = await fetch(request);
    return response;
  } catch (error) {
    console.log('[ServiceWorker] Navigation request failed, serving offline page');
    
    // Fall back to offline page
    const cache = await caches.open(CACHE_NAME);
    return cache.match(OFFLINE_URL);
  }
}

/**
 * Handle static assets with cache-first strategy
 */
async function handleStaticRequest(request) {
  try {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Fall back to network
    const response = await fetch(request);
    
    // Cache the response for future use
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[ServiceWorker] Static request failed:', request.url);
    
    // Return a fallback response for images
    if (request.destination === 'image') {
      return new Response(
        '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="#f8f9fa"/><text x="100" y="100" text-anchor="middle" fill="#6c757d">Image unavailable</text></svg>',
        { headers: { 'Content-Type': 'image/svg+xml' } }
      );
    }
    
    throw error;
  }
}

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Background sync:', event.tag);
  
  if (event.tag === 'trade-queue') {
    event.waitUntil(processPendingTrades());
  }
  
  if (event.tag === 'analytics-sync') {
    event.waitUntil(syncAnalyticsData());
  }
});

/**
 * Process pending trades when connection is restored
 */
async function processPendingTrades() {
  try {
    console.log('[ServiceWorker] Processing pending trades');
    
    // Get pending trades from IndexedDB or localStorage
    const pendingTrades = await getPendingTrades();
    
    for (const trade of pendingTrades) {
      try {
        const response = await fetch('/api/v1/trades', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(trade)
        });
        
        if (response.ok) {
          await removePendingTrade(trade.id);
          console.log('[ServiceWorker] Processed pending trade:', trade.id);
        }
      } catch (error) {
        console.error('[ServiceWorker] Failed to process trade:', trade.id, error);
      }
    }
  } catch (error) {
    console.error('[ServiceWorker] Error processing pending trades:', error);
  }
}

/**
 * Sync analytics data when connection is restored
 */
async function syncAnalyticsData() {
  try {
    console.log('[ServiceWorker] Syncing analytics data');
    
    // Fetch latest analytics data
    const response = await fetch('/api/v1/analytics/overview');
    if (response.ok) {
      const data = await response.json();
      
      // Cache the updated data
      const cache = await caches.open(CACHE_NAME);
      cache.put('/api/v1/analytics/overview', new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json' }
      }));
    }
  } catch (error) {
    console.error('[ServiceWorker] Error syncing analytics:', error);
  }
}

// Placeholder functions for IndexedDB operations
async function getPendingTrades() {
  // TODO: Implement IndexedDB storage for pending trades
  return [];
}

async function removePendingTrade(tradeId) {
  // TODO: Implement IndexedDB removal
  console.log('Removing pending trade:', tradeId);
}

// Push notifications (for future use)
self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push received');
  
  const options = {
    body: 'DEX Sniper Pro notification',
    icon: '/images/icon-192.png',
    badge: '/images/badge-72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'view',
        title: 'View',
        icon: '/images/checkmark.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/images/xmark.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('DEX Sniper Pro', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('[ServiceWorker] Notification click received');
  
  event.notification.close();
  
  if (event.action === 'view') {
    event.waitUntil(
      self.clients.openWindow('/')
    );
  }
});