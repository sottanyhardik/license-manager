import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-oxc'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), '')
  return {
  plugins: [react(), tailwindcss()],
  base: '/',  // Ensures assets are loaded from root, not port 8000
  server: {
    proxy: {
      '/api': {
        target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            // Suppress ECONNREFUSED noise during Django auto-reload restarts
            if (err.code === 'ECONNREFUSED') {
              if (!res.headersSent) {
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ detail: 'Backend restarting, please retry.' }));
              }
            }
          });
        },
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    manifest: false,
    // Optimize chunk size
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching and performance
        manualChunks: (id) => {
          // Vendor chunks - separate large dependencies
          if (id.includes('node_modules')) {
            // React core libraries
            if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
              return 'vendor-react';
            }
          }

          // Application shell code used on first paint.
          if (
            id.includes('/layout/') ||
            id.includes('/components/Icon') ||
            id.includes('/components/TopNav') ||
            id.includes('/components/LoadingFallback') ||
            id.includes('/components/ErrorScreen') ||
            id.includes('/components/GlobalErrorBoundary')
          ) {
            return 'app-shell';
          }

          // Avoid broad route-level chunks: they can become entry preloads
          // when shared symbols are hoisted by the bundler.

        },

        // Naming pattern for chunks
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      }
    },

    // Enable source maps in production for debugging (optional - remove for smaller builds)
    sourcemap: false,

    // Minification
    minify: 'esbuild',

    // Target modern browsers for smaller bundles
    target: 'es2015',
  },

  resolve: {
    alias: {
      // shadcn/ui convention — `@/components/ui/button` → src/components/ui/button
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // Use the pre-built browser bundle to avoid Node.js fs/stream polyfill issues
      'exceljs': 'exceljs/dist/exceljs.min.js',
    },
  },

  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'axios',
    ],
  },
  }
})
