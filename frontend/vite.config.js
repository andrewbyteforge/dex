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
   
    // Explicit proxy configuration for backend - FIXED to consistently use port 8001
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
            
            // Send meaningful error response with CORRECT port number
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

            // Check for specific error types with detailed explanations - FIXED port reference
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
              headers: Object.keys(req.headers),
              timestamp: new Date().toISOString()
            });
            
            // Log the WebSocket upgrade request (before upgrade)
            if (req.url?.startsWith('/ws')) {
              console.log('[Vite] 📤 WebSocket upgrade request to endpoint (before upgrade):', {
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