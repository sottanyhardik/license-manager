import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

// Standalone Vitest config. Kept separate from vite.config.ts so the dev-server
// proxy / build chunking don't affect the test run. JSX/TSX is transformed by
// Vitest's default esbuild pipeline (automatic React 19 runtime).
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // exclude the built output and deps
    exclude: ['node_modules', 'dist'],
  },
})
