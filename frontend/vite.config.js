import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
 
  server: {
    port: 3000,
    host: 'localhost',
   
    // Force WebSocket to use a different port to avoid SES interference
    hmr: {
      port: 3001,
      protocol: 'ws',
      host: 'localhost'
    },
   
    // Ensure proper CORS headers
    cors: true,
   
    // Explicit proxy configuration for backend
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        ws: false, // Separate WebSocket handling to avoid conflicts
        timeout: 10000, // 10 second timeout
        configure: (proxy, _options) => {
          proxy.on('error', (err, req, res) => {
            console.error('[Vite] API proxy error:', {
              message: err.message,
              code: err.code,
              url: req?.url,
              method: req?.method,
              timestamp: new Date().toISOString()
            });
            
            // Send meaningful error response
            if (res && !res.headersSent) {
              res.writeHead(503, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                error: 'Backend API unavailable',
                message: 'Make sure the backend server is running on port 8001',
                timestamp: new Date().toISOString()
              }));
            }
          });

          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('[Vite] API request:', {
              method: req.method,
              url: req.url,
              target: proxyReq.path,
              timestamp: new Date().toISOString()
            });
          });

          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('[Vite] API response:', {
              method: req.method,
              url: req.url,
              status: proxyRes.statusCode,
              timestamp: new Date().toISOString()
            });
          });
        }
      },
      '/ws': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 30000, // 30 second timeout for WebSocket connections
        configure: (proxy, _options) => {
          proxy.on('error', (err, req, res) => {
            console.error('[Vite] WebSocket proxy error:', {
              message: err.message,
              code: err.code,
              errno: err.errno,
              syscall: err.syscall,
              address: err.address,
              port: err.port,
              url: req?.url,
              timestamp: new Date().toISOString()
            });

            // Check for specific error types with detailed explanations
            if (err.code === 'ECONNREFUSED') {
              console.error('[Vite] ❌ Backend WebSocket server is not running or not accepting connections on port 8001');
              console.error('[Vite] 💡 Solution: Make sure your backend server is started with: python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload');
            } else if (err.code === 'ECONNRESET') {
              console.error('[Vite] ❌ Backend WebSocket connection was reset - WebSocket route may not exist');
              console.error('[Vite] 💡 Check if your backend has WebSocket routes configured for:', req?.url);
            } else if (err.code === 'ETIMEDOUT') {
              console.error('[Vite] ❌ Backend WebSocket connection timed out');
            } else if (err.code === 'ENOTFOUND') {
              console.error('[Vite] ❌ Backend WebSocket server hostname could not be resolved');
            } else if (err.code === 'EHOSTUNREACH') {
              console.error('[Vite] ❌ Backend WebSocket server host is unreachable');
            }
          });

          proxy.on('proxyReqWs', (proxyReq, req, socket, options, head) => {
            console.log('[Vite] 🔄 WebSocket proxy request:', {
              url: req.url,
              method: req.method,
              origin: req.headers.origin,
              userAgent: req.headers['user-agent']?.substring(0, 50) + '...',
              target: `http://localhost:8001${req.url}`, // Fixed: proper string interpolation
              timestamp: new Date().toISOString()
            });

            // Enhanced socket error handling
            socket.on('error', (err) => {
              console.error('[Vite] 💥 WebSocket client socket error:', {
                message: err.message,
                code: err.code,
                errno: err.errno,
                url: req.url,
                timestamp: new Date().toISOString()
              });
              
              // Provide context-specific error messages
              if (err.code === 'ECONNRESET') {
                console.error('[Vite] 💡 Client disconnected or backend rejected the WebSocket handshake');
              } else if (err.code === 'EPIPE') {
                console.error('[Vite] 💡 Broken pipe - connection was closed unexpectedly');
              }
            });

            socket.on('timeout', () => {
              console.error('[Vite] ⏰ WebSocket client socket timed out for:', req.url);
            });

            socket.on('close', (hadError) => {
              if (hadError) {
                console.error('[Vite] 🔌 WebSocket client socket closed with error for:', req.url);
              } else {
                console.log('[Vite] 🔌 WebSocket client socket closed normally for:', req.url);
              }
            });
          });

          proxy.on('open', (proxySocket) => {
            console.log('[Vite] ✅ WebSocket proxy connection opened successfully');
            
            proxySocket.on('error', (err) => {
              console.error('[Vite] 💥 WebSocket proxy socket error (backend side):', {
                message: err.message,
                code: err.code,
                errno: err.errno,
                timestamp: new Date().toISOString()
              });
              
              if (err.code === 'ECONNRESET') {
                console.error('[Vite] 💡 Backend closed the WebSocket connection unexpectedly');
              } else if (err.code === 'ETIMEDOUT') {
                console.error('[Vite] 💡 Backend WebSocket connection timed out');
              }
            });

            proxySocket.on('close', (hadError) => {
              console.log('[Vite] 🔌 WebSocket proxy socket closed:', {
                hadError,
                timestamp: new Date().toISOString()
              });
              
              if (hadError) {
                console.error('[Vite] ❌ WebSocket proxy socket closed due to error');
              }
            });

            proxySocket.on('timeout', () => {
              console.error('[Vite] ⏰ WebSocket proxy socket timed out');
            });

            // Log data flow for debugging
            proxySocket.on('data', (chunk) => {
              console.log('[Vite] 📨 WebSocket data from backend:', {
                size: chunk.length,
                timestamp: new Date().toISOString()
              });
            });
          });

          proxy.on('close', (res, socket, head) => {
            console.log('[Vite] 🔌 WebSocket proxy connection closed');
          });

          // Handle upgrade errors specifically with detailed logging
          proxy.on('upgrade', (req, socket, head) => {
            console.log('[Vite] ⬆️ WebSocket upgrade attempt:', {
              url: req.url,
              method: req.method,
              headers: {
                upgrade: req.headers.upgrade,
                connection: req.headers.connection,
                'sec-websocket-version': req.headers['sec-websocket-version'],
                'sec-websocket-key': req.headers['sec-websocket-key']
              },
              timestamp: new Date().toISOString()
            });
          });

          // Additional proxy events for comprehensive monitoring
          proxy.on('proxyReq', (proxyReq, req, res, options) => {
            if (req.url?.startsWith('/ws')) {
              console.log('[Vite] 🌐 HTTP request to WebSocket endpoint (before upgrade):', {
                url: req.url,
                method: req.method,
                headers: Object.keys(req.headers),
                timestamp: new Date().toISOString()
              });
            }
          });

          proxy.on('proxyRes', (proxyRes, req, res) => {
            if (req.url?.startsWith('/ws')) {
              console.log('[Vite] 📬 HTTP response from WebSocket endpoint:', {
                url: req.url,
                status: proxyRes.statusCode,
                statusMessage: proxyRes.statusMessage,
                headers: Object.keys(proxyRes.headers),
                timestamp: new Date().toISOString()
              });
              
              if (proxyRes.statusCode === 404) {
                console.error('[Vite] ❌ WebSocket route not found on backend:', req.url);
                console.error('[Vite] 💡 Check if your backend has this WebSocket route configured');
              } else if (proxyRes.statusCode >= 500) {
                console.error('[Vite] ❌ Backend WebSocket server error:', proxyRes.statusCode, proxyRes.statusMessage);
              }
            }
          });
        }
      }
    }
  },
 
  // Resolve aliases for cleaner imports
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@components': resolve(__dirname, './src/components'),
      '@utils': resolve(__dirname, './src/utils'),
      '@hooks': resolve(__dirname, './src/hooks'),
      '@services': resolve(__dirname, './src/services')
    }
  },
 
  // Build optimizations
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          bootstrap: ['react-bootstrap', 'bootstrap'],
          wallet: ['wagmi', 'viem', '@walletconnect/web3-provider']
        }
      }
    }
  },
 
  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'react-bootstrap',
      'bootstrap'
    ]
  }
});