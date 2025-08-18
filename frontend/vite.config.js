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
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true
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