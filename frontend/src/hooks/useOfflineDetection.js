import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * useOfflineDetection - Comprehensive network state and offline management hook
 * 
 * Provides real-time network status monitoring, connection quality detection,
 * and offline queue management optimized for trading applications.
 * 
 * @param {Object} options - Configuration options
 * @returns {Object} - Network state and offline management utilities
 * 
 * @example
 * const { 
 *   isOnline, 
 *   connectionType, 
 *   isSlowConnection, 
 *   queueRequest,
 *   retryQueue 
 * } = useOfflineDetection({
 *   onOffline: () => showOfflineToast(),
 *   onOnline: () => hideOfflineToast(),
 *   enableQueue: true
 * });
 */
const useOfflineDetection = (options = {}) => {
  const {
    // Network monitoring configuration
    pollingInterval = 30000,        // Check connection every 30 seconds
    timeoutDuration = 5000,         // Request timeout for health checks
    maxRetries = 3,                 // Maximum retry attempts
    retryDelay = 1000,              // Base delay between retries (exponential backoff)
    
    // Connection quality thresholds
    slowConnectionThreshold = 1000,  // Consider connection slow if response > 1s
    fastConnectionThreshold = 300,   // Consider connection fast if response < 300ms
    
    // Health check endpoints
    healthCheckUrls = [
      '/api/v1/health/',
      'https://www.google.com/favicon.ico',
      'https://1.1.1.1/favicon.ico'  // Cloudflare DNS
    ],
    
    // Offline queue management
    enableQueue = true,
    maxQueueSize = 100,
    queueStorageKey = 'dex_offline_queue',
    
    // Event callbacks
    onOnline = null,
    onOffline = null,
    onConnectionChange = null,
    onQueueProcess = null,
    onSlowConnection = null,
    onFastConnection = null,
    
    // Analytics
    enableAnalytics = true,
    analyticsCallback = null
  } = options;

  // Network state
  const [networkState, setNetworkState] = useState({
    isOnline: navigator.onLine,
    wasOffline: false,
    connectionType: 'unknown',
    effectiveType: 'unknown',
    downlink: 0,
    rtt: 0,
    isSlowConnection: false,
    isFastConnection: false,
    lastOnlineTime: Date.now(),
    lastOfflineTime: null,
    connectionQuality: 'unknown'
  });

  // Request queue for offline scenarios
  const [requestQueue, setRequestQueue] = useState([]);
  const [isProcessingQueue, setIsProcessingQueue] = useState(false);

  // Refs for managing intervals and timeouts
  const healthCheckIntervalRef = useRef(null);
  const connectionTestRef = useRef(null);
  const retryTimeoutRef = useRef(null);

  // Connection quality tracking
  const connectionMetricsRef = useRef({
    recentTests: [],
    averageLatency: 0,
    successRate: 1.0,
    lastTestTime: 0
  });

  /**
   * Load queued requests from localStorage
   */
  const loadQueueFromStorage = useCallback(() => {
    if (!enableQueue) return [];
    
    try {
      const stored = localStorage.getItem(queueStorageKey);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.warn('[Offline] Failed to load queue from storage:', error);
      return [];
    }
  }, [enableQueue, queueStorageKey]);

  /**
   * Save queue to localStorage
   */
  const saveQueueToStorage = useCallback((queue) => {
    if (!enableQueue) return;
    
    try {
      localStorage.setItem(queueStorageKey, JSON.stringify(queue));
    } catch (error) {
      console.warn('[Offline] Failed to save queue to storage:', error);
    }
  }, [enableQueue, queueStorageKey]);

  /**
   * Detect connection type and speed
   */
  const detectConnectionInfo = useCallback(() => {
    const connection = navigator.connection || 
                     navigator.mozConnection || 
                     navigator.webkitConnection;
    
    if (connection) {
      return {
        connectionType: connection.type || 'unknown',
        effectiveType: connection.effectiveType || 'unknown',
        downlink: connection.downlink || 0,
        rtt: connection.rtt || 0
      };
    }
    
    return {
      connectionType: 'unknown',
      effectiveType: 'unknown',
      downlink: 0,
      rtt: 0
    };
  }, []);

  /**
   * Perform health check to verify real connectivity
   */
  const performHealthCheck = useCallback(async () => {
    const startTime = Date.now();
    
    for (const url of healthCheckUrls) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutDuration);
        
        const response = await fetch(url, {
          method: 'HEAD',
          mode: 'no-cors',
          cache: 'no-cache',
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        const latency = Date.now() - startTime;
        
        // Update connection metrics
        connectionMetricsRef.current.recentTests.push({
          url,
          latency,
          success: true,
          timestamp: Date.now()
        });
        
        // Keep only recent tests (last 10)
        if (connectionMetricsRef.current.recentTests.length > 10) {
          connectionMetricsRef.current.recentTests.shift();
        }
        
        return { success: true, latency, url };
      } catch (error) {
        console.warn(`[Offline] Health check failed for ${url}:`, error.message);
        
        connectionMetricsRef.current.recentTests.push({
          url,
          latency: timeoutDuration,
          success: false,
          timestamp: Date.now(),
          error: error.message
        });
      }
    }
    
    return { success: false, latency: timeoutDuration };
  }, [healthCheckUrls, timeoutDuration]);

  /**
   * Calculate connection quality metrics
   */
  const calculateConnectionQuality = useCallback(() => {
    const metrics = connectionMetricsRef.current;
    const recentTests = metrics.recentTests.slice(-5); // Last 5 tests
    
    if (recentTests.length === 0) {
      return 'unknown';
    }
    
    const successfulTests = recentTests.filter(test => test.success);
    const successRate = successfulTests.length / recentTests.length;
    const averageLatency = successfulTests.reduce((sum, test) => sum + test.latency, 0) / successfulTests.length;
    
    metrics.successRate = successRate;
    metrics.averageLatency = averageLatency;
    
    // Determine quality based on success rate and latency
    if (successRate < 0.5) {
      return 'poor';
    } else if (successRate < 0.8 || averageLatency > slowConnectionThreshold) {
      return 'slow';
    } else if (averageLatency < fastConnectionThreshold) {
      return 'fast';
    } else {
      return 'good';
    }
  }, [slowConnectionThreshold, fastConnectionThreshold]);

  /**
   * Update network state
   */
  const updateNetworkState = useCallback(async (isOnline) => {
    const previousState = networkState;
    const connectionInfo = detectConnectionInfo();
    let connectionQuality = 'unknown';
    
    if (isOnline) {
      // Perform health check to verify real connectivity
      const healthCheck = await performHealthCheck();
      isOnline = healthCheck.success;
      connectionQuality = calculateConnectionQuality();
    }
    
    const newState = {
      ...connectionInfo,
      isOnline,
      wasOffline: previousState.isOnline === false && isOnline === true,
      lastOnlineTime: isOnline ? Date.now() : previousState.lastOnlineTime,
      lastOfflineTime: !isOnline ? Date.now() : previousState.lastOfflineTime,
      connectionQuality,
      isSlowConnection: connectionQuality === 'slow' || connectionQuality === 'poor',
      isFastConnection: connectionQuality === 'fast'
    };
    
    setNetworkState(newState);
    
    // Trigger callbacks for state changes
    if (previousState.isOnline !== isOnline) {
      if (isOnline) {
        console.log('[Offline] Connection restored');
        onOnline?.(newState);
        
        // Process queued requests
        if (enableQueue && requestQueue.length > 0) {
          processRequestQueue();
        }
      } else {
        console.log('[Offline] Connection lost');
        onOffline?.(newState);
      }
      
      onConnectionChange?.(newState, previousState);
      trackEvent('connection_change', { 
        from: previousState.isOnline ? 'online' : 'offline',
        to: isOnline ? 'online' : 'offline',
        quality: connectionQuality
      });
    }
    
    // Trigger connection speed callbacks
    if (previousState.connectionQuality !== connectionQuality) {
      if (connectionQuality === 'slow' || connectionQuality === 'poor') {
        onSlowConnection?.(newState);
      } else if (connectionQuality === 'fast') {
        onFastConnection?.(newState);
      }
    }
  }, [
    networkState, detectConnectionInfo, performHealthCheck, calculateConnectionQuality,
    onOnline, onOffline, onConnectionChange, onSlowConnection, onFastConnection,
    enableQueue, requestQueue.length
  ]);

  /**
   * Add request to offline queue
   */
  const queueRequest = useCallback((request) => {
    if (!enableQueue) {
      console.warn('[Offline] Queue is disabled');
      return false;
    }
    
    const queueItem = {
      id: Date.now() + Math.random(),
      timestamp: Date.now(),
      retryCount: 0,
      ...request
    };
    
    setRequestQueue(prevQueue => {
      const newQueue = [...prevQueue, queueItem];
      
      // Enforce max queue size
      if (newQueue.length > maxQueueSize) {
        console.warn('[Offline] Queue size limit reached, removing oldest items');
        newQueue.splice(0, newQueue.length - maxQueueSize);
      }
      
      saveQueueToStorage(newQueue);
      return newQueue;
    });
    
    console.log('[Offline] Request queued:', queueItem.id);
    trackEvent('request_queued', { queueSize: requestQueue.length + 1 });
    
    return queueItem.id;
  }, [enableQueue, maxQueueSize, requestQueue.length, saveQueueToStorage]);

  /**
   * Process queued requests when back online
   */
  const processRequestQueue = useCallback(async () => {
    if (!enableQueue || requestQueue.length === 0 || isProcessingQueue) {
      return;
    }
    
    console.log('[Offline] Processing request queue:', requestQueue.length, 'items');
    setIsProcessingQueue(true);
    
    const successfulRequests = [];
    const failedRequests = [];
    
    for (const queueItem of requestQueue) {
      try {
        // Implement the actual request based on queueItem.type
        const result = await executeQueuedRequest(queueItem);
        
        if (result.success) {
          successfulRequests.push(queueItem.id);
          console.log('[Offline] Queued request successful:', queueItem.id);
        } else {
          queueItem.retryCount++;
          if (queueItem.retryCount >= maxRetries) {
            failedRequests.push(queueItem.id);
            console.error('[Offline] Queued request failed permanently:', queueItem.id);
          } else {
            console.warn('[Offline] Queued request failed, will retry:', queueItem.id);
          }
        }
      } catch (error) {
        console.error('[Offline] Error processing queued request:', queueItem.id, error);
        queueItem.retryCount++;
        if (queueItem.retryCount >= maxRetries) {
          failedRequests.push(queueItem.id);
        }
      }
    }
    
    // Remove successful and permanently failed requests from queue
    const idsToRemove = [...successfulRequests, ...failedRequests];
    setRequestQueue(prevQueue => {
      const newQueue = prevQueue.filter(item => !idsToRemove.includes(item.id));
      saveQueueToStorage(newQueue);
      return newQueue;
    });
    
    setIsProcessingQueue(false);
    
    // Analytics
    trackEvent('queue_processed', {
      successful: successfulRequests.length,
      failed: failedRequests.length,
      remaining: requestQueue.length - idsToRemove.length
    });
    
    onQueueProcess?.({
      successful: successfulRequests.length,
      failed: failedRequests.length,
      remaining: requestQueue.length - idsToRemove.length
    });
  }, [
    enableQueue, requestQueue, isProcessingQueue, maxRetries, 
    saveQueueToStorage, onQueueProcess
  ]);

  /**
   * Execute a queued request (placeholder - would integrate with your API layer)
   */
  const executeQueuedRequest = useCallback(async (queueItem) => {
    // This would integrate with your actual API calls
    // For now, we'll simulate the request
    
    switch (queueItem.type) {
      case 'trade':
        // Would call your trade API
        console.log('[Offline] Executing queued trade:', queueItem.data);
        break;
      case 'analytics':
        // Would call your analytics API
        console.log('[Offline] Executing queued analytics:', queueItem.data);
        break;
      default:
        console.warn('[Offline] Unknown queue item type:', queueItem.type);
    }
    
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 100));
    
    return { success: true };
  }, []);

  /**
   * Retry processing queue manually
   */
  const retryQueue = useCallback(() => {
    if (networkState.isOnline && !isProcessingQueue) {
      processRequestQueue();
    }
  }, [networkState.isOnline, isProcessingQueue, processRequestQueue]);

  /**
   * Clear the request queue
   */
  const clearQueue = useCallback(() => {
    setRequestQueue([]);
    saveQueueToStorage([]);
    console.log('[Offline] Request queue cleared');
  }, [saveQueueToStorage]);

  /**
   * Track analytics events
   */
  const trackEvent = useCallback((eventName, properties = {}) => {
    if (!enableAnalytics) return;
    
    const eventData = {
      event: eventName,
      timestamp: Date.now(),
      connectionQuality: networkState.connectionQuality,
      isOnline: networkState.isOnline,
      ...properties
    };
    
    console.log('[Offline] Analytics:', eventData);
    
    if (analyticsCallback) {
      analyticsCallback(eventData);
    }
  }, [enableAnalytics, analyticsCallback, networkState.connectionQuality, networkState.isOnline]);

  /**
   * Setup event listeners and polling
   */
  useEffect(() => {
    // Load initial queue from storage
    const storedQueue = loadQueueFromStorage();
    setRequestQueue(storedQueue);
    
    // Initial network state check
    updateNetworkState(navigator.onLine);
    
    // Setup browser online/offline event listeners
    const handleOnline = () => updateNetworkState(true);
    const handleOffline = () => updateNetworkState(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    // Setup connection change listener (for mobile networks)
    if (navigator.connection) {
      const handleConnectionChange = () => updateNetworkState(navigator.onLine);
      navigator.connection.addEventListener('change', handleConnectionChange);
    }
    
    // Setup periodic health checks
    healthCheckIntervalRef.current = setInterval(() => {
      if (navigator.onLine) {
        updateNetworkState(true);
      }
    }, pollingInterval);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      
      if (navigator.connection) {
        navigator.connection.removeEventListener('change', handleConnectionChange);
      }
      
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
      }
      
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [updateNetworkState, loadQueueFromStorage, pollingInterval]);

  return {
    // Network state
    ...networkState,
    
    // Connection metrics
    averageLatency: connectionMetricsRef.current.averageLatency,
    successRate: connectionMetricsRef.current.successRate,
    
    // Queue management
    requestQueue,
    queueSize: requestQueue.length,
    isProcessingQueue,
    queueRequest,
    retryQueue,
    clearQueue,
    
    // Utilities
    forceCheck: () => updateNetworkState(navigator.onLine),
    getConnectionMetrics: () => connectionMetricsRef.current,
    
    // Queue helpers
    hasQueuedRequests: requestQueue.length > 0,
    canProcessQueue: networkState.isOnline && !isProcessingQueue
  };
};

export default useOfflineDetection;