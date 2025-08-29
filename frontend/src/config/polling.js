/**
 * Centralized Polling Configuration for DEX Sniper Pro
 * 
 * Manages polling intervals across the application to prevent resource waste
 * and ensure consistent behavior between development and production.
 * 
 * File: frontend/src/config/polling.js
 */

/**
 * Base polling intervals in milliseconds
 * Production values prioritize resource efficiency
 * Development values allow for faster feedback during testing
 */
export const POLLING_INTERVALS = {
    // Autotrade system polling
    AUTOTRADE_STATUS: 10000,        // 10 seconds - status updates
    AUTOTRADE_METRICS: 15000,       // 15 seconds - performance metrics
    AUTOTRADE_QUEUE: 8000,          // 8 seconds - queue status
    AUTOTRADE_SETTINGS: 30000,      // 30 seconds - configuration checks

    // Dashboard and analytics
    DASHBOARD: 30000,               // 30 seconds - main dashboard data
    ANALYTICS: 45000,               // 45 seconds - analytics refresh
    PORTFOLIO: 20000,               // 20 seconds - portfolio updates

    // Trading related
    TRADE_STATUS: 5000,             // 5 seconds (only during active trades)
    TRADE_HISTORY: 30000,           // 30 seconds - historical data
    QUOTES: 8000,                   // 8 seconds - price quotes
    
    // Market data
    MARKET_DATA: 15000,             // 15 seconds - general market data
    PAIR_DISCOVERY: 60000,          // 60 seconds - new pair discovery
    RISK_ASSESSMENT: 25000,         // 25 seconds - risk scoring updates

    // Wallet and balance
    WALLET_BALANCE: 30000,          // 30 seconds - balance checks
    WALLET_APPROVALS: 45000,        // 45 seconds - approval status
    TRANSACTION_STATUS: 3000,       // 3 seconds (only during pending tx)

    // AI and intelligence
    AI_INTELLIGENCE: 20000,         // 20 seconds - AI analysis updates
    MARKET_REGIME: 60000,           // 60 seconds - market regime detection
    WHALE_ACTIVITY: 30000,          // 30 seconds - whale monitoring

    // System health
    HEALTH_CHECK: 30000,            // 30 seconds - backend health
    CONNECTION_STATUS: 15000,       // 15 seconds - connection monitoring

    // Development overrides (faster polling for testing)
    DEVELOPMENT: {
        AUTOTRADE_STATUS: 3000,     // 3 seconds in development
        AUTOTRADE_METRICS: 5000,    // 5 seconds in development
        AUTOTRADE_QUEUE: 3000,      // 3 seconds in development
        DASHBOARD: 8000,            // 8 seconds in development
        TRADE_STATUS: 1500,         // 1.5 seconds in development
        QUOTES: 3000,               // 3 seconds in development
        MARKET_DATA: 5000,          // 5 seconds in development
        WALLET_BALANCE: 10000,      // 10 seconds in development
        AI_INTELLIGENCE: 8000,      // 8 seconds in development
        HEALTH_CHECK: 10000,        // 10 seconds in development
        CONNECTION_STATUS: 5000,    // 5 seconds in development
    }
};

/**
 * Get polling interval for a specific type with environment awareness
 * 
 * @param {string} type - Polling type (must exist in POLLING_INTERVALS)
 * @param {object} options - Additional configuration options
 * @param {boolean} options.forceDevelopment - Force development interval
 * @param {number} options.multiplier - Multiply the interval by this factor
 * @returns {number} Polling interval in milliseconds
 */
export const getPollingInterval = (type, options = {}) => {
    const { forceDevelopment = false, multiplier = 1 } = options;
    
    // Determine if we should use development intervals
    const isDevelopment = forceDevelopment || import.meta.env.DEV;
    
    // Get base interval
    let interval;
    if (isDevelopment && POLLING_INTERVALS.DEVELOPMENT[type]) {
        interval = POLLING_INTERVALS.DEVELOPMENT[type];
    } else if (POLLING_INTERVALS[type]) {
        interval = POLLING_INTERVALS[type];
    } else {
        console.warn(`[Polling] Unknown polling type: ${type}. Using fallback interval.`);
        interval = isDevelopment ? 5000 : 10000; // Fallback
    }
    
    // Apply multiplier if provided
    const finalInterval = Math.floor(interval * multiplier);
    
    // Log in development for debugging
    if (isDevelopment && localStorage.getItem('debug_polling')) {
        console.debug(`[Polling] ${type}: ${finalInterval}ms (${isDevelopment ? 'dev' : 'prod'} mode)`);
    }
    
    return finalInterval;
};

/**
 * Create a polling manager for consistent interval handling
 * 
 * @param {string} name - Name for logging purposes
 * @param {function} pollFunction - Function to execute on each poll
 * @param {string} intervalType - Type of interval from POLLING_INTERVALS
 * @param {object} options - Configuration options
 * @returns {object} Polling control object
 */
export const createPollingManager = (name, pollFunction, intervalType, options = {}) => {
    let intervalId = null;
    let isActive = false;
    let pollCount = 0;
    let errorCount = 0;
    
    const { 
        maxErrors = 5,
        errorBackoffMultiplier = 2,
        onError = null,
        onSuccess = null 
    } = options;

    /**
     * Execute poll with error handling
     */
    const executePoll = async () => {
        try {
            pollCount++;
            await pollFunction();
            errorCount = 0; // Reset error count on success
            onSuccess?.(pollCount);
            
        } catch (error) {
            errorCount++;
            console.error(`[Polling:${name}] Poll ${pollCount} failed:`, error);
            
            onError?.(error, errorCount);
            
            // Stop polling if too many consecutive errors
            if (errorCount >= maxErrors) {
                console.error(`[Polling:${name}] Stopping due to ${errorCount} consecutive errors`);
                stop();
                return;
            }
            
            // Apply backoff on errors
            if (errorCount > 1) {
                const backoffDelay = getPollingInterval(intervalType) * Math.pow(errorBackoffMultiplier, errorCount - 1);
                console.warn(`[Polling:${name}] Applying ${backoffDelay}ms backoff after ${errorCount} errors`);
                
                setTimeout(() => {
                    if (isActive) {
                        executePoll();
                    }
                }, backoffDelay);
                return;
            }
        }
    };

    /**
     * Start polling
     */
    const start = () => {
        if (isActive) {
            console.warn(`[Polling:${name}] Already active`);
            return;
        }
        
        isActive = true;
        pollCount = 0;
        errorCount = 0;
        
        const interval = getPollingInterval(intervalType, options);
        console.info(`[Polling:${name}] Starting with ${interval}ms interval`);
        
        // Execute immediately, then start interval
        executePoll();
        intervalId = setInterval(executePoll, interval);
    };

    /**
     * Stop polling
     */
    const stop = () => {
        if (!isActive) {
            return;
        }
        
        isActive = false;
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
        
        console.info(`[Polling:${name}] Stopped after ${pollCount} polls`);
    };

    /**
     * Get current status
     */
    const getStatus = () => ({
        isActive,
        pollCount,
        errorCount,
        intervalType,
        currentInterval: getPollingInterval(intervalType, options)
    });

    return {
        start,
        stop,
        getStatus,
        isActive: () => isActive
    };
};

/**
 * Global polling registry to prevent duplicate polling
 */
const activePollers = new Map();

/**
 * Register a poller to prevent duplicates
 * 
 * @param {string} key - Unique key for this poller
 * @param {object} poller - Poller object from createPollingManager
 * @returns {boolean} True if registered successfully, false if duplicate
 */
export const registerPoller = (key, poller) => {
    if (activePollers.has(key)) {
        console.warn(`[Polling] Poller '${key}' already registered`);
        return false;
    }
    
    activePollers.set(key, poller);
    return true;
};

/**
 * Unregister and stop a poller
 * 
 * @param {string} key - Poller key to remove
 */
export const unregisterPoller = (key) => {
    const poller = activePollers.get(key);
    if (poller) {
        poller.stop();
        activePollers.delete(key);
        console.info(`[Polling] Unregistered poller '${key}'`);
    }
};

/**
 * Stop all active pollers (useful for cleanup)
 */
export const stopAllPollers = () => {
    console.info(`[Polling] Stopping ${activePollers.size} active pollers`);
    activePollers.forEach((poller, key) => {
        poller.stop();
    });
    activePollers.clear();
};

/**
 * Get status of all active pollers
 */
export const getAllPollerStatus = () => {
    const status = {};
    activePollers.forEach((poller, key) => {
        status[key] = poller.getStatus();
    });
    return status;
};

/**
 * Debug helper to log all polling activity
 */
export const enablePollingDebug = () => {
    localStorage.setItem('debug_polling', 'true');
    console.info('[Polling] Debug mode enabled - will log all polling activity');
};

export const disablePollingDebug = () => {
    localStorage.removeItem('debug_polling');
    console.info('[Polling] Debug mode disabled');
};

// Export default configuration for easy importing
export default {
    POLLING_INTERVALS,
    getPollingInterval,
    createPollingManager,
    registerPoller,
    unregisterPoller,
    stopAllPollers,
    getAllPollerStatus,
    enablePollingDebug,
    disablePollingDebug
};