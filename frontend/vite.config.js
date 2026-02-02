import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-oxc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',  // Ensures assets are loaded from root, not port 8000
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
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
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
              return 'vendor-react';
            }

            // UI libraries (Bootstrap, react-select, etc.)
            if (id.includes('react-select') || id.includes('react-bootstrap') || id.includes('bootstrap')) {
              return 'vendor-ui';
            }

            // Toast/notification libraries
            if (id.includes('react-toastify')) {
              return 'vendor-toast';
            }

            // Date/time libraries
            if (id.includes('date-fns') || id.includes('moment')) {
              return 'vendor-date';
            }

            // All other node_modules
            return 'vendor-other';
          }

          // Application code chunks
          // Reports module - heavy pages
          if (id.includes('/pages/reports/')) {
            return 'app-reports';
          }

          // Ledger module - financial pages
          if (id.includes('/pages/ledger/')) {
            return 'app-ledger';
          }

          // Master data pages
          if (id.includes('/pages/masters/')) {
            return 'app-masters';
          }

          // Components chunk
          if (id.includes('/components/')) {
            return 'app-components';
          }
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

  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'axios',
    ],
  },
})
