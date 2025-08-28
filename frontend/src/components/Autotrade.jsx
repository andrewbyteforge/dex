/**
 * Enhanced Autotrade dashboard component with Secure Wallet Funding Integration
 * SECURITY: Integrates wallet approval system with user confirmation before trading
 *
 * File: frontend/src/components/Autotrade.jsx
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Container, Row, Col, Card, Button, Badge, Alert, Spinner, Nav, Modal, ProgressBar } from 'react-bootstrap';
import { Play, Pause, Square, Activity, AlertTriangle, Wifi, WifiOff, RefreshCw, Settings, Brain, Shield, CheckCircle } from 'lucide-react';

import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';
import AIIntelligenceDisplay from './AIIntelligenceDisplay';
import WalletApproval from './WalletApproval';
import useWebSocket from '../hooks/useWebSocket';
import { useWallet } from '../hooks/useWallet';

const API_BASE_URL = 'http://localhost:8001';

/**
 * Enhanced Autotrade dashboard component with secure wallet funding
 */
const Autotrade = ({ connectedWallet, systemHealth }) => {
    // UI State management
    const [activeTab, setActiveTab] = useState('overview');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showEmergencyModal, setShowEmergencyModal] = useState(false);
    const [showWalletApprovalModal, setShowWalletApprovalModal] = useState(false);
    const [showSecurityWarningModal, setShowSecurityWarningModal] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [backendAvailable, setBackendAvailable] = useState(true);

    // Test discovery trigger feedback
    const [discoveryLoading, setDiscoveryLoading] = useState(false);
    const [discoveryResult, setDiscoveryResult] = useState(null);
    
    // Test discovery UI state - UPDATED
    const [testDiscoveryResults, setTestDiscoveryResults] = useState(null);
    const [showTestResults, setShowTestResults] = useState(false);
    
    // Component lifecycle management
    const [shouldConnect, setShouldConnect] = useState(true);
    const [wsKey] = useState(() => Date.now());
    const mountedRef = useRef(true);
    const retryTimeoutRef = useRef(null);
    
    // Autotrade engine state
    const [autotradeStatus, setAutotradeStatus] = useState({
        mode: 'disabled',
        is_running: false,
        queue_size: 0,
        active_trades: 0,
        uptime_seconds: 0
    });
    const [engineMode, setEngineMode] = useState('disabled');
    const [isRunning, setIsRunning] = useState(false);
    const [metrics, setMetrics] = useState({
        opportunities_found: 0,
        opportunities_executed: 0,
        success_rate: 0,
        total_profit_usd: 0,
        last_updated: null
    });
    
    // Secure wallet funding state
    const [walletApprovalStatus, setWalletApprovalStatus] = useState({
        approved_wallets: {},
        daily_spending: {},
        pending_approvals: []
    });
    const [canStartAutotrade, setCanStartAutotrade] = useState(false);
    const [pendingStartMode, setPendingStartMode] = useState(null);
    
    // AI Intelligence State
    const [aiIntelligenceData, setAiIntelligenceData] = useState(null);
    const [marketRegime, setMarketRegime] = useState({ regime: 'unknown', confidence: 0 });
    const [aiStats, setAiStats] = useState({
        pairs_analyzed: 0,
        avg_ai_score: 0,
        high_risk_blocked: 0
    });
    
    // Error tracking and retry logic
    const [errorHistory, setErrorHistory] = useState([]);
    const [retryCount, setRetryCount] = useState(0);
    const MAX_RETRY_ATTEMPTS = 3;

    // Wallet integration - Fixed property names
    const { 
        isConnected: walletConnected,
        walletAddress: walletAddress,
        selectedChain: currentChain
    } = useWallet();

    // FIX: Check both the hook state AND localStorage for connection status
    // This handles cases where the hook hasn't synchronized yet
    const [walletStateFixed, setWalletStateFixed] = useState({
        connected: walletConnected,
        address: walletAddress,
        chain: currentChain
    });

    // Update the fixed state whenever wallet state or localStorage changes
    useEffect(() => {
        const checkWalletState = () => {
            // First check the hook state
            if (walletConnected && walletAddress) {
                setWalletStateFixed({
                    connected: true,
                    address: walletAddress,
                    chain: currentChain
                });
                return;
            }
            
            // Fallback to localStorage if hook reports disconnected
            const persistedConnection = localStorage.getItem('dex_wallet_connection');
            if (persistedConnection) {
                try {
                    const parsed = JSON.parse(persistedConnection);
                    if (parsed.walletAddress) {
                        setWalletStateFixed({
                            connected: true,
                            address: parsed.walletAddress,
                            chain: parsed.selectedChain || 'ethereum'
                        });
                    }
                } catch (e) {
                    // Keep current state if parse fails
                }
            } else if (!walletConnected) {
                // Only set disconnected if both sources agree
                setWalletStateFixed({
                    connected: false,
                    address: null,
                    chain: 'ethereum'
                });
            }
        };

        checkWalletState();
        
        // Also check periodically to catch delayed updates
        const interval = setInterval(checkWalletState, 5000);
        return () => clearInterval(interval);
    }, [walletConnected, walletAddress, currentChain]);

    // Use the fixed values throughout the component
    const walletConnectedFixed = walletStateFixed.connected;
    const walletAddressFixed = walletStateFixed.address;
    const currentChainFixed = walletStateFixed.chain;

    /**
     * Production-ready logging with environment awareness
     */
    const logMessage = useCallback((level, message, data = {}) => {
        const logEntry = {
            timestamp: new Date().toISOString(),
            level,
            component: 'Autotrade',
            wsKey,
            message,
            ...data
        };

        if (import.meta.env.DEV || localStorage.getItem('debug_autotrade')) {
            switch (level) {
                case 'error':
                    console.error(`[Autotrade] ${message}`, logEntry);
                    break;
                case 'warn':
                    console.warn(`[Autotrade] ${message}`, logEntry);
                    break;
                case 'info':
                    console.info(`[Autotrade] ${message}`, logEntry);
                    break;
                case 'debug':
                    if (localStorage.getItem('debug_autotrade')) {
                        console.debug(`[Autotrade] ${message}`, logEntry);
                    }
                    break;
                default:
                    console.log(`[Autotrade] ${message}`, logEntry);
            }
        }

        return logEntry.trace_id || `autotrade_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }, [wsKey]);

    /**
     * Enhanced error logging with history tracking
     */
    const logError = useCallback((operation, error, context = {}) => {
        const errorEntry = {
            timestamp: new Date().toISOString(),
            operation,
            error: error.message || String(error),
            stack: error.stack || '',
            context,
            component: 'Autotrade',
            wsKey
        };

        logMessage('error', `[Autotrade:${operation}]`, errorEntry);
        
        // Track error history for debugging
        setErrorHistory(prev => [errorEntry, ...prev.slice(0, 9)]);
    }, [logMessage, wsKey]);

    /**
     * SECURITY: Load wallet approval status
     */
/**
 * SECURITY: Load wallet approval status - FIXED approval validation
 */
    const loadWalletApprovalStatus = useCallback(async () => {
        if (!backendAvailable || !walletConnectedFixed) return;

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/wallet-funding/wallet-status`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                
                // Map the response properly
                const mappedData = {
                    ...data,
                    approved_wallets: data.approvals || {},
                    daily_spending: data.daily_spending || {}
                };
                
                setWalletApprovalStatus(mappedData);
                
                // FIXED: Check approval based on chain-protocol mapping instead of direct chain lookup
                let hasApprovalForChain = false;
                if (data.approvals && data.wallet_funded) {
                    // Define chain to protocol mappings
                    const chainProtocolMappings = {
                        'ethereum': ['uniswap_v2', 'uniswap_v3', 'sushiswap', 'curve', 'balancer'],
                        'bsc': ['pancakeswap', 'bakeryswap', 'apeswap', 'biswap'],
                        'base': ['uniswap_v3', 'aerodrome', 'swapbased', 'baseswap'],
                        'polygon': ['quickswap', 'sushiswap', 'curve', 'balancer'],
                        'arbitrum': ['uniswap_v3', 'sushiswap', 'camelot', 'trader_joe'],
                        'solana': ['raydium', 'orca', 'jupiter']
                    };
                    
                    const currentChainLower = currentChainFixed?.toLowerCase();
                    const expectedProtocols = chainProtocolMappings[currentChainLower] || [];
                    const approvedProtocols = Object.keys(data.approvals);
                    
                    // Check if any protocol for the current chain is approved
                    hasApprovalForChain = expectedProtocols.some(protocol => 
                        approvedProtocols.includes(protocol)
                    );
                    
                    logMessage('debug', 'Approval validation details', {
                        current_chain: currentChainLower,
                        expected_protocols: expectedProtocols,
                        approved_protocols: approvedProtocols,
                        has_matching_approval: hasApprovalForChain,
                        wallet_funded: data.wallet_funded
                    });
                }
                
                setCanStartAutotrade(hasApprovalForChain);
                
                logMessage('info', 'Wallet approval status loaded', {
                    approved_protocols: Object.keys(data.approvals || {}),
                    current_chain: currentChainFixed,
                    can_start_autotrade: hasApprovalForChain,
                    wallet_funded: data.wallet_funded
                });
            }
        } catch (error) {
            logMessage('debug', 'Could not load wallet approval status', { error: error.message });
        }
    }, [backendAvailable, walletConnectedFixed, currentChainFixed, logMessage]);









    /**
     * Load AI intelligence data from API
     */
    const loadAIIntelligenceData = useCallback(async () => {
        if (!backendAvailable) return;

        try {
            // Get recent AI analyzed pairs
            const recentResponse = await fetch(`${API_BASE_URL}/api/v1/intelligence/pairs/recent?limit=1`);
            if (recentResponse.ok) {
                const recentData = await recentResponse.json();
                if (recentData.pairs && recentData.pairs.length > 0) {
                    const latestPair = recentData.pairs[0];
                    setAiIntelligenceData({
                        pair_address: latestPair.pair_address,
                        token_symbol: latestPair.token_symbol,
                        opportunity_level: latestPair.opportunity_level,
                        ai_intelligence: latestPair.intelligence_data,
                        timestamp: latestPair.analyzed_at
                    });
                }
            }

            // Get current market regime
            const regimeResponse = await fetch(`${API_BASE_URL}/api/v1/intelligence/market/regime`);
            if (regimeResponse.ok) {
                const regimeData = await regimeResponse.json();
                setMarketRegime({
                    regime: regimeData.regime,
                    confidence: regimeData.confidence,
                    updated_at: regimeData.updated_at
                });
            }

            // Get AI processing stats
            const statsResponse = await fetch(`${API_BASE_URL}/api/v1/intelligence/stats/processing`);
            if (statsResponse.ok) {
                const statsData = await statsResponse.json();
                setAiStats(prev => ({
                    ...prev,
                    ...statsData.ai_intelligence_stats
                }));
            }

        } catch (error) {
            logMessage('debug', 'AI intelligence data not available', { error: error.message });
        }
    }, [backendAvailable, logMessage]);

    /**
     * Load initial autotrade data with comprehensive error handling
     */
    const loadInitialData = useCallback(async (isRetry = false) => {
        if (!mountedRef.current) return;

        try {
            if (!isRetry) {
                setLoading(true);
                setError(null);
            }

            logMessage('info', 'Loading initial autotrade data', { 
                isRetry, 
                attempt: retryCount + 1,
                backendAvailable 
            });

            // Create abort controller for timeout handling
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);

            try {
                const statusResponse = await fetch(`${API_BASE_URL}/api/v1/autotrade/status`, {
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!statusResponse.ok) {
                    if (statusResponse.status >= 500) {
                        throw new Error(`Server error: ${statusResponse.status}`);
                    } else if (statusResponse.status === 404) {
                        throw new Error('Autotrade API endpoint not found');
                    } else {
                        throw new Error(`API Error: ${statusResponse.status} ${statusResponse.statusText}`);
                    }
                }

                const statusData = await statusResponse.json();
                
                if (!mountedRef.current) return;

                // Update state with fetched data
                setAutotradeStatus(statusData);
                setEngineMode(statusData.mode || 'disabled');
                setIsRunning(statusData.is_running || false);
                
                if (statusData.metrics) {
                    setMetrics(prev => ({
                        ...prev,
                        ...statusData.metrics,
                        last_updated: new Date().toISOString()
                    }));
                }

                setBackendAvailable(true);
                setRetryCount(0);
                setLastUpdate(new Date());

                logMessage('info', 'Initial data loaded successfully', {
                    mode: statusData.mode,
                    running: statusData.is_running,
                    queueSize: statusData.queue_size || 0
                });

                // Load AI intelligence data
                await loadAIIntelligenceData();
                
                // SECURITY: Load wallet approval status
                await loadWalletApprovalStatus();

            } catch (fetchError) {
                clearTimeout(timeoutId);
                throw fetchError;
            }

        } catch (error) {
            logError('load_initial_data', error);

            if (!mountedRef.current) return;

            // Handle different error types
            if (error.name === 'AbortError') {
                setError('Request timeout - backend may be slow or unavailable');
            } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                setBackendAvailable(false);
                setError('Backend unavailable - autotrade features disabled');
            } else {
                setError(`Failed to load autotrade data: ${error.message}`);
            }

            // Implement retry logic for transient errors
            if (retryCount < MAX_RETRY_ATTEMPTS && 
                !error.message.includes('404') && 
                !error.message.includes('NetworkError')) {
                
                const delay = Math.min(2000 * Math.pow(2, retryCount), 10000);
                logMessage('info', `Retrying in ${delay}ms`, { 
                    attempt: retryCount + 1, 
                    maxAttempts: MAX_RETRY_ATTEMPTS 
                });

                setRetryCount(prev => prev + 1);
                
                retryTimeoutRef.current = setTimeout(() => {
                    if (mountedRef.current) {
                        loadInitialData(true);
                    }
                }, delay);
            }
        } finally {
            if (mountedRef.current) {
                setLoading(false);
            }
        }
    }, [retryCount, backendAvailable, logMessage, logError, loadAIIntelligenceData, loadWalletApprovalStatus]);

    /**
     * Handle WebSocket message processing with AI intelligence support
     */
    const handleWebSocketMessage = useCallback((message) => {
        if (!mountedRef.current) return;

        try {
            if (!message || typeof message !== 'object') {
                logMessage('warn', 'Invalid WebSocket message format', { message });
                return;
            }

            logMessage('debug', `WebSocket message received: ${message.type}`);
            setLastUpdate(new Date());

            switch (message.type) {
                case 'engine_status':
                    if (message.data) {
                        setAutotradeStatus(prev => ({ ...prev, ...message.data }));
                        setEngineMode(message.data.mode || 'disabled');
                        setIsRunning(message.data.is_running || false);
                    }
                    break;

                case 'trade_executed':
                    if (message.data) {
                        logMessage('info', 'Trade executed', { 
                            trade_id: message.data.trade_id,
                            profit: message.data.profit_usd 
                        });
                        // Update metrics if trade data includes profit
                        if (message.data.profit_usd) {
                            setMetrics(prev => ({
                                ...prev,
                                total_profit_usd: (prev.total_profit_usd || 0) + message.data.profit_usd,
                                opportunities_executed: (prev.opportunities_executed || 0) + 1
                            }));
                        }
                    }
                    break;

                case 'opportunity_found':
                    if (message.data) {
                        setMetrics(prev => ({
                            ...prev,
                            opportunities_found: (prev.opportunities_found || 0) + 1
                        }));
                    }
                    break;

                case 'metrics_update':
                    if (message.data) {
                        setMetrics(prev => ({
                            ...prev,
                            ...message.data,
                            last_updated: new Date().toISOString()
                        }));
                    }
                    break;

                // AI Intelligence WebSocket Messages
                case 'new_pair_analysis':
                    if (message.data && message.data.intelligence_data) {
                        logMessage('info', 'New pair AI analysis received', { 
                            pair_address: message.data.pair_address,
                            intelligence_score: message.data.intelligence_data.intelligence_score 
                        });
                        
                        // Store the most recent AI analysis for display
                        setAiIntelligenceData({
                            pair_address: message.data.pair_address,
                            token_symbol: message.data.token_symbol,
                            opportunity_level: message.data.opportunity_level,
                            ai_intelligence: message.data.intelligence_data,
                            timestamp: new Date().toISOString()
                        });
                    }
                    break;

                case 'market_regime_change':
                    if (message.data) {
                        logMessage('info', 'Market regime change', { 
                            regime: message.data.regime,
                            confidence: message.data.confidence 
                        });
                        setMarketRegime({
                            regime: message.data.regime,
                            confidence: message.data.confidence,
                            updated_at: new Date().toISOString()
                        });
                    }
                    break;

                case 'whale_activity_alert':
                    if (message.data) {
                        logMessage('warn', 'Whale activity detected', message.data);
                        // Update AI intelligence data if it matches current pair
                        if (aiIntelligenceData && message.data.token_address === aiIntelligenceData.pair_address) {
                            setAiIntelligenceData(prev => ({
                                ...prev,
                                ai_intelligence: {
                                    ...prev.ai_intelligence,
                                    whale_activity: message.data.activity_score,
                                    whale_dump_risk: message.data.dump_risk
                                }
                            }));
                        }
                    }
                    break;

                case 'coordination_detected':
                    if (message.data) {
                        logMessage('error', 'Coordination pattern detected', message.data);
                        // Show coordination warning
                        setError(`AI Alert: Coordination detected - ${message.data.pattern_type} (Risk: ${message.data.risk_level})`);
                    }
                    break;

                case 'ai_stats_update':
                    if (message.data) {
                        setAiStats(prev => ({
                            ...prev,
                            ...message.data,
                            last_updated: new Date().toISOString()
                        }));
                    }
                    break;

                case 'emergency_stop':
                    logMessage('warn', 'Emergency stop triggered', message.data);
                    setIsRunning(false);
                    setEngineMode('disabled');
                    setError('Emergency stop activated');
                    break;

                case 'connection_ack':
                    logMessage('info', 'WebSocket connection acknowledged');
                    // Clear connection errors
                    if (error && error.includes('WebSocket')) {
                        setError(null);
                    }
                    break;

                case 'error':
                    logMessage('error', 'Server error via WebSocket', message.data);
                    if (message.data?.message) {
                        setError(`Server: ${message.data.message}`);
                    }
                    break;

                default:
                    logMessage('debug', `Unhandled message type: ${message.type}`, message.data);
            }
        } catch (err) {
            logError('websocket_message_handler', err, { message });
        }
    }, [error, logMessage, logError, aiIntelligenceData]);

    /**
     * Production WebSocket connection with AI intelligence support
     */
    const { 
        isConnected: wsConnected, 
        isConnecting: wsConnecting,
        sendMessage,
        error: wsError,
        reconnectAttempts: wsReconnectAttempts
    } = useWebSocket(shouldConnect ? '/ws/autotrade' : null, {
        maxReconnectAttempts: 3,
        reconnectInterval: 5000,
        shouldReconnect: shouldConnect && backendAvailable,
        suppressDevErrors: true,
        onOpen: () => {
            logMessage('info', 'Autotrade WebSocket connected successfully');
            
            if (mountedRef.current && sendMessage) {
                // Subscribe to all autotrade events INCLUDING AI intelligence events
                sendMessage({
                    type: 'subscribe',
                    channels: [
                        'engine_status',
                        'trade_executed', 
                        'opportunity_found',
                        'metrics_update',
                        'emergency_stop',
                        // AI Intelligence channels
                        'new_pair_analysis',
                        'market_regime_change',
                        'whale_activity_alert',
                        'coordination_detected',
                        'ai_stats_update'
                    ]
                });
            }
            
            // Clear WebSocket-related errors
            if (error && (error.includes('WebSocket') || error.includes('Backend unavailable'))) {
                setError(null);
            }
            setBackendAvailable(true);
        },
        onMessage: handleWebSocketMessage,
        onClose: (event) => {
            logMessage('info', 'Autotrade WebSocket disconnected', { 
                code: event.code, 
                reason: event.reason 
            });
        },
        onError: () => {
            logMessage('warn', 'Autotrade WebSocket error occurred');
        }
    });

    /**
     * SECURITY: Check wallet approval before starting autotrade
     */
    const checkWalletApprovalAndStart = useCallback(async (mode = 'standard') => {
        if (!walletConnectedFixed || !walletAddressFixed) {
            setError('Please connect your wallet first');
            return;
        }

        if (!currentChainFixed) {
            setError('Unable to determine current blockchain');
            return;
        }

        // Check if wallet is approved for current chain
        if (!canStartAutotrade) {
            setPendingStartMode(mode);
            setShowSecurityWarningModal(true);
            return;
        }

        // Wallet is approved, proceed with start
        await startAutotradeSecure(mode);
    }, [walletConnectedFixed, walletAddressFixed, currentChainFixed, canStartAutotrade]);

    /**
     * SECURITY: Start autotrade with wallet approval verification
     */
    const startAutotradeSecure = useCallback(async (mode = 'standard') => {
        if (!backendAvailable) {
            setError('Backend unavailable - cannot start autotrade');
            return;
        }

        // Final security check
        if (!canStartAutotrade) {
            setError('Wallet not approved for autotrade on this chain');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            logMessage('info', `Starting secure autotrade in ${mode} mode`, {
                wallet_address: walletAddressFixed,
                chain: currentChainFixed
            });
            
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                body: JSON.stringify({
                    mode: mode,
                    wallet_address: walletAddressFixed,
                    chain: currentChainFixed
                })
            });

            let result;
            try {
                result = await response.json();
            } catch (parseError) {
                logError('start_autotrade_parse', parseError, {
                    status: response.status,
                    statusText: response.statusText
                });
                throw new Error(`Response parsing failed: ${response.status} ${response.statusText}`);
            }

            if (!response.ok) {
                const errorMessage = result.detail || result.message || `Failed to start: ${response.status} ${response.statusText}`;
                throw new Error(errorMessage);
            }

            logMessage('info', 'Secure autotrade started successfully', {
                mode: mode,
                status: result.status,
                message: result.message,
                trace_id: result.trace_id,
                wallet_address: walletAddressFixed
            });

            // Update state
            setIsRunning(true);
            setEngineMode(mode);
            
            // Reload data
            setTimeout(() => {
                if (mountedRef.current) {
                    loadInitialData();
                }
            }, 1000);

        } catch (error) {
            logError('start_autotrade_secure', error, { mode });
            if (mountedRef.current) {
                setError(error.message);
            }
        } finally {
            if (mountedRef.current) {
                setLoading(false);
            }
        }
    }, [backendAvailable, canStartAutotrade, walletAddressFixed, currentChainFixed, logMessage, logError, loadInitialData]);

    /**
     * Stop autotrade engine
     */
    const stopAutotrade = useCallback(async () => {
        if (!backendAvailable) {
            setError('Backend unavailable - cannot stop autotrade');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            logMessage('info', 'Stopping autotrade engine');

            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/stop`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to stop: ${response.status} ${response.statusText}`);
            }

            if (mountedRef.current) {
                setIsRunning(false);
                setEngineMode('disabled');
                logMessage('info', 'Autotrade stopped successfully');
                
                // Reload status after stopping
                setTimeout(() => {
                    if (mountedRef.current) {
                        loadInitialData();
                    }
                }, 1000);
            }
        } catch (error) {
            logError('stop_autotrade', error);
            if (mountedRef.current) {
                setError(`Failed to stop autotrade: ${error.message}`);
            }
        } finally {
            if (mountedRef.current) {
                setLoading(false);
            }
        }
    }, [backendAvailable, logMessage, logError, loadInitialData]);

    /**
     * Emergency stop functionality
     */
    const handleEmergencyStop = useCallback(async () => {
        if (!backendAvailable) {
            setError('Backend unavailable - cannot execute emergency stop');
            return;
        }

        try {
            logMessage('warn', 'Emergency stop initiated by user');

            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/emergency-stop`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`Emergency stop failed: ${response.status}`);
            }

            if (mountedRef.current) {
                setIsRunning(false);
                setEngineMode('disabled');
                setShowEmergencyModal(false);
                setError('Emergency stop executed successfully');
                
                // Reload status
                setTimeout(() => {
                    if (mountedRef.current) {
                        loadInitialData();
                    }
                }, 1000);
            }
        } catch (error) {
            logError('emergency_stop', error);
            if (mountedRef.current) {
                setError(`Emergency stop failed: ${error.message}`);
            }
        }
    }, [backendAvailable, logMessage, logError, loadInitialData]);

    /**
     * Trigger test discovery with FIXED data parsing - UPDATED
     */
    const triggerTestDiscovery = useCallback(async () => {
        try {
            logMessage('info', 'Triggering test discovery...');
            setDiscoveryLoading(true);
            
            const response = await fetch(`${API_BASE_URL}/api/v1/discovery/test-discovery`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            logMessage('info', 'Triggered test discovery', { response: data });
            
            // FIXED: Parse the response correctly based on backend structure
            const processedResult = {
                success: data.success || false,
                message: data.message || 'Discovery completed',
                status: data.success ? 'success' : 'error',
                pairs_discovered: data.scan_results?.pairs_found || data.pairs?.length || 0,
                scan_duration_ms: data.scan_results?.scan_duration_ms || 0,
                success_rate: data.scan_results?.success_rate || 100,
                pairs: (data.pairs || []).map(pair => ({
                    symbol: `${pair.token0?.symbol || 'UNKNOWN'}/${pair.token1?.symbol || 'UNKNOWN'}`,
                    name: pair.token0?.name || 'Unknown Token',
                    chain: pair.chain,
                    dex: pair.dex,
                    pair_address: pair.pair_address,
                    liquidity_usd: parseFloat(pair.liquidity_eth || 0) * 2000, // Rough conversion
                    volume_24h: parseFloat(pair.metadata?.volume_24h || 0),
                    price_change_24h: parseFloat(pair.metadata?.price_change_24h || 0),
                    risk_score: (pair.risk_score || 50) / 100, // Convert from percentage to decimal
                    token0: pair.token0,
                    token1: pair.token1,
                    metadata: pair.metadata
                }))
            };
            
            // Update UI state with processed results
            setTestDiscoveryResults(processedResult);
            setShowTestResults(true);
            
            // Show success alert
            alert(`Test Discovery Success!\nFound ${processedResult.pairs_discovered} pairs in ${processedResult.scan_duration_ms}ms`);
            
        } catch (error) {
            logMessage('error', '[Autotrade:trigger_test_discovery]', {
                operation: 'trigger_test_discovery',
                error: error.message,
                stack: error.stack || '',
                context: {}
            });
            
            // Show error alert
            alert(`Test Discovery Failed: ${error.message}`);
        } finally {
            setDiscoveryLoading(false);
        }
    }, [logMessage]);

    /**
     * Handle wallet approval completion
     */
    const handleWalletApprovalComplete = useCallback(async (result) => {
        await loadWalletApprovalStatus();
        setShowWalletApprovalModal(false);
        
        // If user had a pending start mode, proceed with it
        if (pendingStartMode) {
            await startAutotradeSecure(pendingStartMode);
            setPendingStartMode(null);
        }
    }, [loadWalletApprovalStatus, pendingStartMode, startAutotradeSecure]);

    /**
     * Component initialization
     */
    useEffect(() => {
        mountedRef.current = true;
        logMessage('info', 'Secure Autotrade component mounted');
        
        // Load initial data
        loadInitialData();

        return () => {
            mountedRef.current = false;
            setShouldConnect(false);
            
            if (retryTimeoutRef.current) {
                clearTimeout(retryTimeoutRef.current);
            }
            
            logMessage('info', 'Secure Autotrade component unmounting - cleanup initiated');
        };
    }, [loadInitialData, logMessage]);

    /**
     * Watch for wallet changes and update approval status
     */
    useEffect(() => {
        if (walletConnectedFixed && walletAddressFixed) {
            loadWalletApprovalStatus();
        } else {
            setCanStartAutotrade(false);
        }
    }, [walletConnectedFixed, walletAddressFixed, currentChainFixed, loadWalletApprovalStatus]);

    /**
     * Render connection status indicator
     */
    const renderConnectionStatus = () => (
        <div className="d-flex align-items-center gap-2">
            <div className="d-flex align-items-center gap-1">
                {wsConnected ? (
                    <><Wifi size={14} className="text-success" /> Connected</>
                ) : wsConnecting ? (
                    <><RefreshCw size={14} className="text-warning" /> Connecting...</>
                ) : (
                    <><WifiOff size={14} className="text-muted" /> {backendAvailable ? 'Disconnected' : 'Backend Offline'}</>
                )}
            </div>
            {wsReconnectAttempts > 0 && (
                <Badge bg="warning" className="small">
                    Attempt {wsReconnectAttempts}/3
                </Badge>
            )}
        </div>
    );

    /**
     * Render wallet security status
     */
    const renderWalletSecurityStatus = () => {
        if (!walletConnectedFixed) {
            return (
                <Alert variant="warning" className="mb-4">
                    <Shield size={18} className="me-2" />
                    <strong>Wallet Required:</strong> Connect your wallet to use autotrade features.
                </Alert>
            );
        }

        if (!canStartAutotrade) {
            const currentApproval = walletApprovalStatus?.approved_wallets?.[currentChainFixed?.toLowerCase()];
            
            return (
                <Alert variant="info" className="mb-4">
                    <Shield size={18} className="me-2" />
                    <strong>Wallet Security:</strong> Your wallet needs approval for autotrade on {currentChainFixed}.
                    {currentApproval && (
                        <div className="mt-1 small">
                            Wallet approved but may have expired. Please check approval status.
                        </div>
                    )}
                    <Button 
                        variant="outline-primary" 
                        size="sm" 
                        className="mt-2"
                        onClick={() => setShowWalletApprovalModal(true)}
                    >
                        <Shield size={14} className="me-1" />
                        Manage Wallet Approval
                    </Button>
                </Alert>
            );
        }

        const currentApproval = walletApprovalStatus?.approved_wallets?.[currentChainFixed?.toLowerCase()];
        const dailySpending = parseFloat(walletApprovalStatus?.daily_spending?.[currentChainFixed?.toLowerCase()] || 0);
        const dailyLimit = parseFloat(currentApproval?.daily_limit_usd || 0);
        const spendingPercentage = dailyLimit > 0 ? Math.min((dailySpending / dailyLimit) * 100, 100) : 0;

        return (
            <Alert variant="success" className="mb-4">
                <div className="d-flex align-items-start justify-content-between">
                    <div>
                        <div className="d-flex align-items-center gap-2">
                            <CheckCircle size={18} className="text-success" />
                            <strong>Wallet Approved</strong>
                        </div>
                        <div className="small text-muted mt-1">
                            {walletAddressFixed?.slice(0, 8)}...{walletAddressFixed?.slice(-6)} on {currentChainFixed}
                        </div>
                        <div className="mt-2">
                            <div className="d-flex justify-content-between small mb-1">
                                <span>Daily Spending:</span>
                                <span>${dailySpending.toFixed(2)} / ${dailyLimit.toFixed(2)}</span>
                            </div>
                            <ProgressBar
                                now={spendingPercentage}
                                variant={spendingPercentage > 80 ? 'danger' : spendingPercentage > 60 ? 'warning' : 'success'}
                                style={{ height: '6px' }}
                            />
                        </div>
                    </div>
                    <Button 
                        variant="outline-secondary" 
                        size="sm"
                        onClick={() => setShowWalletApprovalModal(true)}
                    >
                        <Settings size={14} />
                    </Button>
                </div>
            </Alert>
        );
    };

    /**
     * Render engine status overview with security integration
     */
    const renderEngineStatus = () => (
        <Card className="mb-4">
            <Card.Body>
                <Row className="align-items-center">
                    <Col md={8}>
                        <div className="d-flex align-items-center gap-3">
                            <div 
                                className={`rounded-circle ${isRunning ? 'bg-success' : 'bg-secondary'}`} 
                                style={{ width: '12px', height: '12px' }}
                            ></div>
                            <div>
                                <div className="fw-bold">
                                    Mode: {engineMode.charAt(0).toUpperCase() + engineMode.slice(1)}
                                </div>
                                <div className={`small ${isRunning ? 'text-success' : 'text-muted'}`}>
                                    {isRunning ? 'Active' : 'Stopped'}
                                    {autotradeStatus?.uptime_seconds && isRunning && (
                                        <span className="ms-2">
                                            (Uptime: {Math.floor(autotradeStatus.uptime_seconds / 60)}m)
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {autotradeStatus && (
                            <Row className="small text-muted mt-2">
                                <Col sm={4}>
                                    Queue: <span className="fw-bold">{autotradeStatus.queue_size || 0}</span>
                                </Col>
                                <Col sm={4}>
                                    Active Trades: <span className="fw-bold">{autotradeStatus.active_trades || 0}</span>
                                </Col>
                                <Col sm={4}>
                                    {renderConnectionStatus()}
                                </Col>
                            </Row>
                        )}
                    </Col>

                    <Col md={4} className="text-end">
                        {lastUpdate && (
                            <div className="text-muted small">
                                Last Update: {lastUpdate.toLocaleTimeString()}
                            </div>
                        )}
                        {!backendAvailable && (
                            <Badge bg="warning" className="mt-1">Backend Offline</Badge>
                        )}
                    </Col>
                </Row>

                <div className="d-flex flex-wrap gap-2 mt-3">
                    {!isRunning ? (
                        <>
                            <Button 
                                variant="success" 
                                onClick={() => checkWalletApprovalAndStart('standard')} 
                                disabled={loading || !backendAvailable || !walletConnectedFixed}
                                size="sm"
                            >
                                {loading ? (
                                    <><Spinner animation="border" size="sm" className="me-1" /> Starting...</>
                                ) : (
                                    <><Play size={16} className="me-1" /> Start Standard</>
                                )}
                            </Button>
                            
                            <Button 
                                variant="outline-success" 
                                onClick={() => checkWalletApprovalAndStart('conservative')} 
                                disabled={loading || !backendAvailable || !walletConnectedFixed}
                                size="sm"
                            >
                                <Play size={16} className="me-1" /> Conservative
                            </Button>
                            
                            <Button 
                                variant="outline-warning" 
                                onClick={() => checkWalletApprovalAndStart('aggressive')} 
                                disabled={loading || !backendAvailable || !walletConnectedFixed}
                                size="sm"
                            >
                                <Play size={16} className="me-1" /> Aggressive
                            </Button>
                        </>
                    ) : (
                        <>
                            <Button 
                                variant="warning" 
                                onClick={stopAutotrade} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                {loading ? (
                                    <><Spinner animation="border" size="sm" className="me-1" /> Stopping...</>
                                ) : (
                                    <><Pause size={16} className="me-1" /> Stop</>
                                )}
                            </Button>
                            
                            <Button 
                                variant="danger" 
                                onClick={() => setShowEmergencyModal(true)} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                <Square size={16} className="me-1" /> Emergency Stop
                            </Button>
                        </>
                    )}
                    
                    <Button 
                        variant="outline-secondary" 
                        onClick={() => loadInitialData()} 
                        disabled={loading}
                        size="sm"
                    >
                        <RefreshCw size={16} className={loading ? 'spin' : ''} />
                    </Button>
                </div>
            </Card.Body>
        </Card>
    );

    /**
     * Enhanced performance metrics with AI statistics
     */
    const renderMetrics = () => (
        <Card className="mb-4">
            <Card.Header>
                <div className="d-flex align-items-center gap-2">
                    <Activity size={18} />
                    <span>Performance & AI Metrics</span>
                </div>
            </Card.Header>
            <Card.Body>
                <Row>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-primary mb-1">
                                {metrics.opportunities_found || 0}
                            </div>
                            <div className="small text-muted">Opportunities Found</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-info mb-1">
                                {metrics.opportunities_executed || 0}
                            </div>
                            <div className="small text-muted">Trades Executed</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className={`h4 mb-1 ${(metrics.total_profit_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                                ${Number((metrics.total_profit_usd || 0)).toFixed(2)}
                            </div>
                            <div className="small text-muted">Total Profit</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-info mb-1">
                                {Number(((metrics.success_rate || 0) * 100)).toFixed(1)}%
                            </div>
                            <div className="small text-muted">Success Rate</div>
                        </div>
                    </Col>
                    {/* AI Metrics */}
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-warning mb-1">
                                {aiStats.pairs_analyzed || 0}
                            </div>
                            <div className="small text-muted">AI Analyzed</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-danger mb-1">
                                {aiStats.high_risk_blocked || 0}
                            </div>
                            <div className="small text-muted">AI Blocked</div>
                        </div>
                    </Col>
                </Row>

                {/* Market Regime Display */}
                {marketRegime.regime !== 'unknown' && (
                    <Row className="mt-3">
                        <Col>
                            <div className="text-center">
                                <Badge 
                                    bg={
                                        marketRegime.regime === 'bull' ? 'success' :
                                        marketRegime.regime === 'bear' ? 'danger' :
                                        marketRegime.regime === 'volatile' ? 'warning' : 'info'
                                    }
                                    className="px-3 py-2"
                                >
                                    <Brain size={14} className="me-1" />
                                    Market Regime: {marketRegime.regime.toUpperCase()} 
                                    ({(marketRegime.confidence * 100).toFixed(0)}% confidence)
                                </Badge>
                            </div>
                        </Col>
                    </Row>
                )}

                {metrics.last_updated && (
                    <div className="text-center small text-muted mt-3">
                        Metrics updated: {new Date(metrics.last_updated).toLocaleString()}
                    </div>
                )}
            </Card.Body>
        </Card>
    );

    /**
     * Main component render with loading and error states
     */
    if (loading && !autotradeStatus.mode) {
        return (
            <Container className="text-center py-5">
                <Spinner animation="border" role="status" variant="primary">
                    <span className="visually-hidden">Loading...</span>
                </Spinner>
                <div className="mt-3">Loading secure AI-powered autotrade dashboard...</div>
                <div className="text-muted small mt-1">
                    {backendAvailable ? 'Connecting to backend...' : 'Backend appears to be offline'}
                </div>
            </Container>
        );
    }

    return (
        <Container fluid>
            {/* Error Display */}
            {error && (
                <Alert 
                    variant={error.includes('Backend unavailable') ? 'warning' : 'danger'} 
                    dismissible 
                    onClose={() => setError(null)}
                    className="mb-4"
                >
                    <div className="d-flex align-items-center gap-2">
                        <AlertTriangle size={18} />
                        <div>
                            <strong>
                                {error.includes('Backend unavailable') ? 'Backend Offline' : 'Error'}
                            </strong>
                            <div>{error}</div>
                            {!backendAvailable && (
                                <small className="text-muted mt-1">
                                    Start the backend server to enable autotrade functionality
                                </small>
                            )}
                        </div>
                    </div>
                </Alert>
            )}

            {/* Discovery result toast-ish */}
            {discoveryResult && (
                <Alert 
                    variant={discoveryResult.type} 
                    onClose={() => setDiscoveryResult(null)} 
                    dismissible 
                    className="mb-3"
                >
                    {discoveryResult.text}
                </Alert>
            )}

            {/* Test Discovery Results Display - FIXED */}
            {showTestResults && testDiscoveryResults && (
                <Card className="mb-3">
                    <Card.Header className="d-flex justify-content-between align-items-center">
                        <h6 className="mb-0">Test Discovery Results</h6>
                        <Button 
                            variant="outline-secondary" 
                            size="sm" 
                            onClick={() => setShowTestResults(false)}
                        >
                            ×
                        </Button>
                    </Card.Header>
                    <Card.Body>
                        <Row className="mb-3">
                            <Col md={3}>
                                <strong>Status:</strong> <Badge bg={testDiscoveryResults.success ? 'success' : 'danger'}>
                                    {testDiscoveryResults.status || 'Unknown'}
                                </Badge>
                            </Col>
                            <Col md={3}>
                                <strong>Pairs Found:</strong> {testDiscoveryResults.pairs_discovered || 0}
                            </Col>
                            <Col md={3}>
                                <strong>Scan Duration:</strong> {testDiscoveryResults.scan_duration_ms || 0}ms
                            </Col>
                            <Col md={3}>
                                <strong>Success Rate:</strong> {testDiscoveryResults.success_rate || 0}%
                            </Col>
                        </Row>
                        
                        {testDiscoveryResults.pairs && testDiscoveryResults.pairs.length > 0 && (
                            <div>
                                <h6>Discovered Pairs:</h6>
                                {testDiscoveryResults.pairs.map((pair, index) => (
                                    <Card key={index} className="mb-2" style={{ fontSize: '0.9em' }}>
                                        <Card.Body className="py-2">
                                            <Row>
                                                <Col md={4}>
                                                    <strong>{pair.symbol || 'UNKNOWN/UNKNOWN'}</strong> ({pair.name || 'Unknown'})
                                                    <br />
                                                    <small className="text-muted">{pair.chain} • {pair.dex}</small>
                                                </Col>
                                                <Col md={2}>
                                                    <small>Liquidity</small>
                                                    <br />
                                                    <strong>${(pair.liquidity_usd || 0).toLocaleString()}</strong>
                                                </Col>
                                                <Col md={2}>
                                                    <small>Volume 24h</small>
                                                    <br />
                                                    <strong>${(pair.volume_24h || 0).toLocaleString()}</strong>
                                                </Col>
                                                <Col md={2}>
                                                    <small>Price Change</small>
                                                    <br />
                                                    <span className={(pair.price_change_24h || 0) >= 0 ? 'text-success' : 'text-danger'}>
                                                        {(pair.price_change_24h || 0) > 0 ? '+' : ''}{(pair.price_change_24h || 0).toFixed(2)}%
                                                    </span>
                                                </Col>
                                                <Col md={2}>
                                                    <small>Risk Score</small>
                                                    <br />
                                                    <Badge bg={(pair.risk_score || 0.5) < 0.3 ? 'success' : (pair.risk_score || 0.5) < 0.6 ? 'warning' : 'danger'}>
                                                        {((pair.risk_score || 0.5) * 100).toFixed(0)}%
                                                    </Badge>
                                                </Col>
                                            </Row>
                                        </Card.Body>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </Card.Body>
                </Card>
            )}

            {/* SECURITY: Wallet Security Status */}
            {renderWalletSecurityStatus()}

            {/* Engine Status Overview */}
            {renderEngineStatus()}

            {/* Performance Metrics */}
            {renderMetrics()}

            {/* Navigation Tabs */}
            <Row className="mb-4">
                <Col>
                    <Nav variant="tabs">
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'overview'} 
                                onClick={() => setActiveTab('overview')}
                            >
                                Overview
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'wallet-security'} 
                                onClick={() => setActiveTab('wallet-security')}
                            >
                                <Shield size={14} className="me-1" />
                                Wallet Security
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'monitor'} 
                                onClick={() => setActiveTab('monitor')}
                                disabled={!backendAvailable}
                            >
                                Monitor
                                {autotradeStatus.queue_size > 0 && (
                                    <Badge bg="primary" className="ms-1">{autotradeStatus.queue_size}</Badge>
                                )}
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'config'} 
                                onClick={() => setActiveTab('config')}
                                disabled={!backendAvailable}
                            >
                                Configuration
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'advanced'} 
                                onClick={() => setActiveTab('advanced')}
                                disabled={!backendAvailable}
                            >
                                Advanced Orders
                            </Nav.Link>
                        </Nav.Item>
                    </Nav>
                </Col>
            </Row>

            {/* Tab Content */}
            {activeTab === 'overview' && (
                <Row>
                    <Col lg={8}>
                        <Card>
                            <Card.Body>
                                <h5>Secure AI-Powered Autotrade Engine</h5>
                                <p className="text-muted">
                                    The secure AI-powered autotrade engine monitors opportunities across multiple chains and executes trades 
                                    based on configured strategies and AI intelligence analysis. Advanced market intelligence including 
                                    social sentiment, whale behavior, and coordination pattern detection informs all trading decisions.
                                    All trades require explicit wallet approval and respect your configured spending limits.
                                    {!backendAvailable && ' Backend connection required for full functionality.'}
                                </p>

                                <Row>
                                    <Col md={6}>
                                        <h6 className="text-muted">Current Status</h6>
                                        <ul className="list-unstyled">
                                            <li>WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}</li>
                                            <li>Engine: {isRunning ? `Running (${engineMode})` : 'Stopped'}</li>
                                            <li>Backend: {backendAvailable ? 'Available' : 'Offline'}</li>
                                            <li>Wallet: {walletConnectedFixed ? `Connected (${currentChainFixed})` : 'Not Connected'}</li>
                                            <li>Security: {canStartAutotrade ? 'Approved' : 'Approval Required'}</li>
                                            <li>Queue Size: {autotradeStatus.queue_size || 0}</li>
                                            <li>AI Analysis: {aiStats.pairs_analyzed || 0} pairs analyzed</li>
                                            <li>Market Regime: {marketRegime.regime !== 'unknown' ? marketRegime.regime : 'Unknown'}</li>
                                        </ul>
                                    </Col>
                                    <Col md={6}>
                                        <h6 className="text-muted">Quick Actions</h6>
                                        <div className="d-flex flex-column gap-2">
                                            <Button 
                                                variant="outline-primary" 
                                                size="sm" 
                                                onClick={() => setActiveTab('wallet-security')}
                                            >
                                                <Shield size={16} className="me-1" /> Manage Wallet Security
                                            </Button>
                                            <Button 
                                                variant="outline-secondary" 
                                                size="sm" 
                                                onClick={() => setActiveTab('config')}
                                                disabled={!backendAvailable}
                                            >
                                                <Settings size={16} className="me-1" /> Configure Settings
                                            </Button>
                                            <Button 
                                                variant="outline-info" 
                                                size="sm" 
                                                onClick={() => setActiveTab('monitor')}
                                                disabled={!backendAvailable}
                                            >
                                                <Activity size={16} className="me-1" /> View Monitor
                                            </Button>
                                            {/* FIXED: Trigger test discovery with corrected loading state */}
                                            <Button
                                                variant="outline-success"
                                                size="sm"
                                                disabled={!backendAvailable || discoveryLoading}
                                                onClick={triggerTestDiscovery}
                                            >
                                                {discoveryLoading ? (
                                                    <>
                                                        <Spinner animation="border" size="sm" className="me-1" />
                                                        Testing...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Brain size={16} className="me-1" />
                                                        Trigger Test Discovery
                                                    </>
                                                )}
                                            </Button>
                                        </div>
                                    </Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    </Col>
                    
                    {/* AI Intelligence Display Column */}
                    <Col lg={4}>
                        <AIIntelligenceDisplay 
                            intelligenceData={aiIntelligenceData}
                            className="mb-4"
                        />
                        
                        {/* Recent AI Alerts */}
                        {errorHistory.filter(e => e.operation.includes('coordination') || e.operation.includes('whale')).length > 0 && (
                            <Card>
                                <Card.Header className="py-2">
                                    <h6 className="mb-0 text-warning">
                                        <AlertTriangle size={16} className="me-1" />
                                        Recent AI Alerts
                                    </h6>
                                </Card.Header>
                                <Card.Body>
                                    {errorHistory
                                        .filter(e => e.operation.includes('coordination') || e.operation.includes('whale'))
                                        .slice(0, 3)
                                        .map((alert, index) => (
                                            <div key={index} className="small mb-2">
                                                <div className="text-danger fw-bold">{alert.operation}</div>
                                                <div className="text-muted">{new Date(alert.timestamp).toLocaleTimeString()}</div>
                                            </div>
                                        ))
                                    }
                                </Card.Body>
                            </Card>
                        )}
                    </Col>
                </Row>
            )}

            {activeTab === 'wallet-security' && (
                <WalletApproval 
                    connectedWallet={{ address: walletAddressFixed, chain: currentChainFixed }}
                    onApprovalComplete={handleWalletApprovalComplete}
                />
            )}

            {activeTab === 'monitor' && backendAvailable && (
                <AutotradeMonitor 
                    autotradeStatus={autotradeStatus}
                    isRunning={isRunning}
                    wsConnected={wsConnected}
                    metrics={metrics}
                    aiIntelligenceData={aiIntelligenceData}
                    marketRegime={marketRegime}
                    onRefresh={loadInitialData}
                />
            )}

            {activeTab === 'config' && backendAvailable && (
                <AutotradeConfig 
                    currentMode={engineMode}
                    isRunning={isRunning}
                    aiStats={aiStats}
                    onModeChange={(mode) => {
                        setEngineMode(mode);
                        if (isRunning) {
                            checkWalletApprovalAndStart(mode);
                        }
                    }}
                />
            )}

            {activeTab === 'advanced' && backendAvailable && (
                <AdvancedOrders 
                    isRunning={isRunning}
                    wsConnected={wsConnected}
                    aiIntelligenceData={aiIntelligenceData}
                    />
           )}

           {/* Security Warning Modal */}
           <Modal show={showSecurityWarningModal} onHide={() => setShowSecurityWarningModal(false)} size="lg">
               <Modal.Header closeButton>
                   <Modal.Title>
                       <Shield className="me-2 text-warning" />
                       Wallet Approval Required
                   </Modal.Title>
               </Modal.Header>
               <Modal.Body>
                   <Alert variant="warning" className="mb-4">
                       <strong>Security Check:</strong> Your wallet needs approval before autotrade can execute trades with your funds.
                   </Alert>
                   
                   <p>
                       To start autotrade in <strong>{pendingStartMode}</strong> mode, you must first approve your wallet 
                       and set spending limits. This ensures you maintain full control over your funds.
                   </p>
                   
                   <div className="bg-light p-3 rounded mb-3">
                       <h6>Why wallet approval is required:</h6>
                       <ul className="mb-0">
                           <li>Set daily and per-trade spending limits</li>
                           <li>Prevent unauthorized or excessive trading</li>
                           <li>Maintain audit trail of all approved activities</li>
                           <li>Enable emergency stop functionality</li>
                       </ul>
                   </div>
               </Modal.Body>
               <Modal.Footer>
                   <Button variant="secondary" onClick={() => setShowSecurityWarningModal(false)}>
                       Close
                   </Button>
                   <Button variant="primary" onClick={() => {
                       setShowSecurityWarningModal(false);
                       setShowWalletApprovalModal(true);
                   }}>
                       Approve Wallet
                   </Button>
               </Modal.Footer>
           </Modal>

           {/* Wallet Approval Modal */}
           <Modal 
               show={showWalletApprovalModal} 
               onHide={() => setShowWalletApprovalModal(false)}
               size="xl"
           >
               <Modal.Header closeButton>
                   <Modal.Title>
                       <Shield className="me-2 text-primary" />
                       Wallet Security & Approval
                   </Modal.Title>
               </Modal.Header>
               <Modal.Body>
                   <WalletApproval 
                       connectedWallet={{ address: walletAddressFixed, chain: currentChainFixed }}
                       onApprovalComplete={handleWalletApprovalComplete}
                       embedded={true}
                   />
               </Modal.Body>
           </Modal>

           {/* Emergency Stop Confirmation */}
           <Modal
               show={showEmergencyModal}
               onHide={() => setShowEmergencyModal(false)}
               centered
           >
               <Modal.Header closeButton>
                   <Modal.Title>
                       <Square className="me-2 text-danger" />
                       Confirm Emergency Stop
                   </Modal.Title>
               </Modal.Header>
               <Modal.Body>
                   <Alert variant="danger">
                       <strong>Are you sure?</strong> This will immediately halt the autotrade engine,
                       clear the queue, and stop all operations.
                   </Alert>
                   <div className="small text-muted">
                       You can restart the engine later from this dashboard.
                   </div>
               </Modal.Body>
               <Modal.Footer>
                   <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
                       Cancel
                   </Button>
                   <Button variant="danger" onClick={handleEmergencyStop}>
                       Execute Emergency Stop
                   </Button>
               </Modal.Footer>
           </Modal>
       </Container>
   );
};

export default Autotrade;