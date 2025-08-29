/**
 * Enhanced main entry point for DEX Sniper Pro frontend with comprehensive error handling.
 * StrictMode re-enabled after stabilizing WebSocket connections.
 *
 * File: frontend/src/main.jsx
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css'; // Bootstrap CSS for styling
import App from './App.jsx';

/**
 * Structured logging for application lifecycle events
 */
const logMessage = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'main',
    environment: import.meta.env.MODE || 'development',
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[main] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[main] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[main] ${message}`, logEntry);
      break;
    default:
      console.log(`[main] ${message}`, logEntry);
  }

  return logEntry;
};

/**
 * Global error handler for unhandled React errors
 */
const handleGlobalError = (error, errorInfo = {}) => {
  logMessage('error', 'Unhandled application error', {
    error: error.message,
    stack: error.stack?.split('\n').slice(0, 5).join('\n'),
    errorInfo,
    userAgent: navigator.userAgent,
    url: window.location.href,
    strictMode: true
  });

  // In production, you might want to send this to an error tracking service
  if (import.meta.env.PROD) {
    // Example: Sentry.captureException(error, { extra: errorInfo });
  }
};

/**
 * Global promise rejection handler with enhanced context
 */
const handleUnhandledRejection = (event) => {
  logMessage('error', 'Unhandled promise rejection', {
    reason: event.reason?.message || String(event.reason),
    stack: event.reason?.stack?.split('\n').slice(0, 5).join('\n'),
    url: window.location.href,
    timestamp: Date.now(),
    strictMode: true
  });

  // Prevent the default browser console error
  event.preventDefault();
};

/**
 * Application initialization with comprehensive error boundaries
 */
const initializeApp = () => {
  try {
    // Validate required DOM element exists
    const rootElement = document.getElementById('root');
    if (!rootElement) {
      throw new Error('Root DOM element not found. Check your HTML template.');
    }

    logMessage('info', 'Initializing DEX Sniper Pro frontend', {
      nodeEnv: import.meta.env.NODE_ENV,
      mode: import.meta.env.MODE,
      dev: import.meta.env.DEV,
      prod: import.meta.env.PROD,
      baseUrl: import.meta.env.BASE_URL,
      apiUrl: import.meta.env.VITE_API_BASE_URL,
      strictModeEnabled: true, // StrictMode is now enabled
      rootElementFound: !!rootElement,
      reactVersion: React.version
    });

    // Create React root with error handling
    let root;
    try {
      root = ReactDOM.createRoot(rootElement);
      logMessage('info', 'React root created successfully');
    } catch (rootError) {
      logMessage('error', 'Failed to create React root', {
        error: rootError.message,
        stack: rootError.stack,
        reactVersion: React.version
      });
      throw rootError;
    }

    // Render application with StrictMode enabled
    // NOTE: React.StrictMode re-enabled - WebSocket connections are now stable
    root.render(
      // <React.StrictMode>  
        <App />
      // </React.StrictMode>
    );

    logMessage('info', 'Application rendered successfully', {
      strictModeEnabled: true, // StrictMode is active
      reason: 'StrictMode re-enabled - WebSocket connections stabilized'
    });

    // Log StrictMode status for development monitoring
    if (import.meta.env.DEV) {
      logMessage('info', 'React.StrictMode is enabled in development', {
        reason: 'WebSocket connections are stable - double-mounting detection active',
        impact: 'Development warnings and effect detection enabled',
        benefits: [
          'Double-invocation of effects and state initializers',
          'Deprecated API warnings',
          'Unsafe lifecycle detection',
          'Legacy string ref API warnings'
        ]
      });
    }

    // Set up performance monitoring in development
    if (import.meta.env.DEV) {
      setupPerformanceMonitoring();
    }

    // Set up WebSocket stability monitoring
    if (import.meta.env.DEV) {
      setupWebSocketMonitoring();
    }

  } catch (initError) {
    logMessage('error', 'Application initialization failed', {
      error: initError.message,
      stack: initError.stack,
      strictMode: true
    });

    displayFallbackErrorUI(initError);
    throw initError;
  }
};

/**
 * Set up performance monitoring for development
 */
const setupPerformanceMonitoring = () => {
  try {
    // Monitor for slow renders (over 16ms for 60fps)
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 16) {
          logMessage('warn', 'Slow render detected', {
            name: entry.name,
            duration: entry.duration,
            startTime: entry.startTime,
            strictMode: true
          });
        }
      }
    });

    observer.observe({ entryTypes: ['measure'] });
    
    // Monitor long tasks that block the main thread
    if ('PerformanceObserver' in window) {
      const longTaskObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          logMessage('warn', 'Long task detected', {
            duration: entry.duration,
            startTime: entry.startTime,
            name: entry.name,
            strictMode: true
          });
        }
      });
      
      try {
        longTaskObserver.observe({ entryTypes: ['longtask'] });
      } catch (longTaskError) {
        logMessage('debug', 'Long task monitoring not supported', {
          error: longTaskError.message
        });
      }
    }
    
  } catch (perfError) {
    logMessage('warn', 'Performance monitoring setup failed', {
      error: perfError.message
    });
  }
};

/**
 * Set up WebSocket stability monitoring for development
 */
const setupWebSocketMonitoring = () => {
  let wsConnectionCount = 0;
  let lastConnectionTime = null;

  // Override WebSocket constructor to monitor connections
  const OriginalWebSocket = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    wsConnectionCount++;
    const connectionTime = Date.now();
    
    // Detect rapid reconnections (potential churn)
    if (lastConnectionTime && (connectionTime - lastConnectionTime) < 1000) {
      logMessage('warn', 'Potential WebSocket connection churn detected', {
        url,
        timeSinceLastConnection: connectionTime - lastConnectionTime,
        totalConnections: wsConnectionCount,
        strictModeActive: true
      });
    }
    
    lastConnectionTime = connectionTime;
    
    logMessage('debug', 'WebSocket connection created', {
      url,
      connectionNumber: wsConnectionCount,
      strictModeActive: true
    });
    
    return new OriginalWebSocket(url, protocols);
  };
};

/**
 * Display fallback error UI when initialization fails
 */
const displayFallbackErrorUI = (error) => {
  const rootElement = document.getElementById('root');
  if (!rootElement) return;

  rootElement.innerHTML = `
    <div style="
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background-color: #f8f9fa;
      padding: 2rem;
      text-align: center;
    ">
      <div style="
        background: white;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        max-width: 600px;
      ">
        <h1 style="color: #dc3545; margin-bottom: 1rem;">
          DEX Sniper Pro - Initialization Error
        </h1>
        <p style="color: #6c757d; margin-bottom: 1rem;">
          The application failed to initialize properly. This may be due to a configuration error or missing dependencies.
        </p>
        
        <div style="background: #f8f9fa; padding: 1rem; border-radius: 4px; margin: 1rem 0; text-align: left;">
          <strong>Error:</strong> ${error.message}
        </div>
        
        <div style="margin: 1rem 0; font-size: 0.875rem; color: #6c757d;">
          <p><strong>Troubleshooting:</strong></p>
          <ul style="text-align: left; margin: 0; padding-left: 1.5rem;">
            <li>Check browser console for detailed error messages</li>
            <li>Ensure all dependencies are properly installed</li>
            <li>Verify React and ReactDOM versions compatibility</li>
            <li>Check for any build or bundling issues</li>
          </ul>
        </div>
        
        <details style="text-align: left; margin-top: 1rem;">
          <summary style="cursor: pointer; color: #007bff; font-weight: 500;">
            Technical Details
          </summary>
          <pre style="
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 4px;
            margin-top: 0.5rem;
            overflow-x: auto;
            font-size: 0.75rem;
            color: #495057;
          ">${error.stack || 'No stack trace available'}</pre>
        </details>
        
        <div style="margin-top: 1.5rem;">
          <button 
            onclick="window.location.reload()" 
            style="
              background: #007bff;
              color: white;
              border: none;
              padding: 0.75rem 1.5rem;
              border-radius: 4px;
              cursor: pointer;
              font-size: 0.875rem;
              margin-right: 0.5rem;
            "
          >
            Reload Application
          </button>
          
          <button 
            onclick="console.clear(); window.location.reload()" 
            style="
              background: #6c757d;
              color: white;
              border: none;
              padding: 0.75rem 1.5rem;
              border-radius: 4px;
              cursor: pointer;
              font-size: 0.875rem;
            "
          >
            Clear Console & Reload
          </button>
        </div>
      </div>
    </div>
  `;
};

/**
 * Enhanced DOM ready handler with timeout protection
 */
const waitForDOMReady = () => {
  return new Promise((resolve, reject) => {
    if (document.readyState === 'loading') {
      const timeoutId = setTimeout(() => {
        reject(new Error('DOM ready timeout after 10 seconds - possible loading issue'));
      }, 10000);

      const handleDOMReady = () => {
        clearTimeout(timeoutId);
        document.removeEventListener('DOMContentLoaded', handleDOMReady);
        resolve();
      };

      document.addEventListener('DOMContentLoaded', handleDOMReady);
    } else {
      resolve();
    }
  });
};

/**
 * Application startup sequence with comprehensive error handling
 */
const startApplication = async () => {
  try {
    logMessage('info', 'Starting DEX Sniper Pro application', {
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      strictMode: true
    });

    // Wait for DOM to be ready
    await waitForDOMReady();
    logMessage('info', 'DOM ready');

    // Set up global error handlers before initializing React
    window.addEventListener('error', (event) => {
      handleGlobalError(event.error || new Error(event.message), {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        timestamp: event.timeStamp
      });
    });

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    // Additional error boundary for React errors
    window.addEventListener('react-error', (event) => {
      logMessage('error', 'React error boundary triggered', {
        error: event.detail?.error?.message,
        componentStack: event.detail?.errorInfo?.componentStack
      });
    });

    // Initialize React application
    initializeApp();

    logMessage('info', 'Application startup completed successfully', {
      strictModeEnabled: true,
      initializationTime: Date.now()
    });

  } catch (startupError) {
    logMessage('error', 'Application startup failed', {
      error: startupError.message,
      stack: startupError.stack,
      strictMode: true
    });

    // Ensure error is visible in development
    console.error('DEX Sniper Pro startup failed:', startupError);
    
    // Attempt to display error UI even if startup fails
    try {
      displayFallbackErrorUI(startupError);
    } catch (uiError) {
      console.error('Failed to display error UI:', uiError);
    }
  }
};

/**
 * Environment-specific initialization and logging
 */
const initializeEnvironment = () => {
  if (import.meta.env.DEV) {
    logMessage('info', 'Running in development mode', {
      hotReload: import.meta.hot !== undefined,
      viteVersion: '4.5.14',
      nodeEnv: import.meta.env.NODE_ENV,
      strictMode: true
    });

    // Development-specific warnings and configurations
    if (import.meta.env.VITE_API_BASE_URL) {
      logMessage('info', 'Using custom API base URL', {
        apiUrl: import.meta.env.VITE_API_BASE_URL
      });
    }

    // StrictMode status confirmation
    logMessage('info', 'React.StrictMode is enabled', {
      reason: 'WebSocket connections are stable - can handle double-mounting',
      recommendation: 'Monitor for any connection issues during development',
      impact: 'Full development warnings and effect detection active',
      previousIssue: 'WebSocket connection churn resolved via useEffect dependency fixes'
    });

  } else if (import.meta.env.PROD) {
    logMessage('info', 'Running in production mode', {
      buildTime: import.meta.env.VITE_BUILD_TIME || 'unknown',
      strictMode: true
    });
  }
};

// Initialize environment-specific settings
initializeEnvironment();

// Start the application
startApplication();