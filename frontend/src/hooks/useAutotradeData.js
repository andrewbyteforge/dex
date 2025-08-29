import { useState, useEffect, useRef, useCallback } from 'react';
import useWebSocket from './useWebSocket';

const POLLING_INTERVALS = {
    AUTOTRADE_STATUS: import.meta.env.DEV ? 20000 : 10000,
    AUTOTRADE_SETTINGS: import.meta.env.DEV ? 60000 : 30000,
    AUTOTRADE_METRICS: import.meta.env.DEV ? 30000 : 15000,
    AI_DATA: import.meta.env.DEV ? 40000 : 20000
};

const API_BASE_URL = 'http://localhost:8001';

export const useAutotradeData = (backendAvailable = true) => {
    const mountedRef = useRef(true);
    const pollingIntervalsRef = useRef({});
    const apiHandlersRef = useRef({});
    
    // State
    const [autotradeStatus, setAutotradeStatus] = useState({
        mode: 'disabled',
        is_running: false,
        queue_size: 0,
        active_trades: 0,
        uptime_seconds: 0
    });
    
    const [autotradeSettings, setAutotradeSettings] = useState({});
    const [metrics, setMetrics] = useState({});
    const [aiIntelligenceData, setAiIntelligenceData] = useState(null);
    const [marketRegime, setMarketRegime] = useState({ regime: 'unknown', confidence: 0 });
    const [aiStats, setAiStats] = useState({});
    
    // Initialize API handlers once
    useEffect(() => {
        apiHandlersRef.current = {
            loadStatus: async () => {
                if (!backendAvailable || !mountedRef.current) return;
                try {
                    const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/status`);
                    if (response.ok) {
                        const data = await response.json();
                        if (mountedRef.current) {
                            setAutotradeStatus(data);
                        }
                    }
                } catch (error) {
                    console.debug('Failed to load status', error.message);
                }
            },
            loadSettings: async () => {
                if (!backendAvailable || !mountedRef.current) return;
                try {
                    const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/settings`);
                    if (response.ok) {
                        const data = await response.json();
                        if (mountedRef.current) {
                            setAutotradeSettings(data.settings || data);
                        }
                    }
                } catch (error) {
                    console.debug('Failed to load settings', error.message);
                }
            },
            loadMetrics: async () => {
                if (!backendAvailable || !mountedRef.current) return;
                try {
                    const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/metrics`);
                    if (response.ok) {
                        const data = await response.json();
                        if (mountedRef.current) {
                            setMetrics(data);
                        }
                    }
                } catch (error) {
                    console.debug('Failed to load metrics', error.message);
                }
            }
        };
    }, []);
    
    // WebSocket connection
    const { 
        isConnected: wsConnected,
        isConnecting: wsConnecting,
        sendMessage,
        error: wsError,
        reconnectAttempts: wsReconnectAttempts
    } = useWebSocket(backendAvailable ? '/ws/autotrade' : null, {
        maxReconnectAttempts: 3,
        reconnectInterval: 5000,
        onMessage: (message) => {
            if (!mountedRef.current) return;
            // Handle WebSocket messages
            switch (message.type) {
                case 'engine_status':
                    setAutotradeStatus(prev => ({ ...prev, ...message.data }));
                    break;
                case 'metrics_update':
                    setMetrics(prev => ({ ...prev, ...message.data }));
                    break;
                // ... other cases
            }
        }
    });
    
    // Polling setup
    useEffect(() => {
        // Clear existing intervals
        Object.keys(pollingIntervalsRef.current).forEach(key => {
            if (pollingIntervalsRef.current[key]) {
                clearInterval(pollingIntervalsRef.current[key]);
                pollingIntervalsRef.current[key] = null;
            }
        });
        
        if (!backendAvailable || wsConnected) return;
        
        // Set up polling
        const setupTimeout = setTimeout(() => {
            // Initial calls
            apiHandlersRef.current.loadStatus?.();
            apiHandlersRef.current.loadSettings?.();
            apiHandlersRef.current.loadMetrics?.();
            
            // Set intervals
            pollingIntervalsRef.current.status = setInterval(
                () => apiHandlersRef.current.loadStatus?.(),
                POLLING_INTERVALS.AUTOTRADE_STATUS
            );
            pollingIntervalsRef.current.settings = setInterval(
                () => apiHandlersRef.current.loadSettings?.(),
                POLLING_INTERVALS.AUTOTRADE_SETTINGS
            );
            pollingIntervalsRef.current.metrics = setInterval(
                () => apiHandlersRef.current.loadMetrics?.(),
                POLLING_INTERVALS.AUTOTRADE_METRICS
            );
        }, 2000);
        
        return () => {
            clearTimeout(setupTimeout);
            Object.keys(pollingIntervalsRef.current).forEach(key => {
                if (pollingIntervalsRef.current[key]) {
                    clearInterval(pollingIntervalsRef.current[key]);
                    pollingIntervalsRef.current[key] = null;
                }
            });
        };
    }, [backendAvailable, wsConnected]);
    
    // Cleanup
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);
    
    return {
        autotradeStatus,
        autotradeSettings,
        metrics,
        aiIntelligenceData,
        marketRegime,
        aiStats,
        wsConnected,
        wsConnecting,
        wsError,
        wsReconnectAttempts,
        sendMessage,
        refresh: () => {
            apiHandlersRef.current.loadStatus?.();
            apiHandlersRef.current.loadSettings?.();
            apiHandlersRef.current.loadMetrics?.();
        }
    };
};