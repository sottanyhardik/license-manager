import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

const sharedRules = {
  // Mark identifiers used in JSX (incl. members like <motion.div>) as used
  'react/jsx-uses-vars': 'error',
  'react/jsx-uses-react': 'off',
  'react-refresh/only-export-components': 'warn',
  'react-hooks/static-components': 'off',
  'react-hooks/use-memo': 'off',
  'react-hooks/component-hook-factories': 'off',
  'react-hooks/preserve-manual-memoization': 'off',
  'react-hooks/immutability': 'off',
  'react-hooks/globals': 'off',
  'react-hooks/refs': 'off',
  'react-hooks/set-state-in-effect': 'off',
  'react-hooks/error-boundaries': 'off',
  'react-hooks/purity': 'off',
  'react-hooks/set-state-in-render': 'off',
  'react-hooks/config': 'off',
  'react-hooks/gating': 'off',
}

const unusedVarsConfig = {
  varsIgnorePattern: '^[A-Z_]',
  argsIgnorePattern: '^_',
  caughtErrorsIgnorePattern: '^(err|error|e)$',
}

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['jest.config.js'],
    languageOptions: {
      globals: globals.node,
      sourceType: 'commonjs',
    },
  },
  // JavaScript / JSX (espree)
  {
    files: ['**/*.{js,jsx}'],
    plugins: { react },
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      ...sharedRules,
      'no-unused-vars': ['warn', unusedVarsConfig],
    },
  },
  // TypeScript / TSX (typescript-eslint parser)
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { react, '@typescript-eslint': tseslint.plugin },
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      parser: tseslint.parser,
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      ...sharedRules,
      // Base rule off, TS-aware version on (understands type-only usage)
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', unusedVarsConfig],
      // TypeScript's own checker handles undefined identifiers/globals
      // (incl. the `React` type namespace); the lint rule false-positives.
      'no-undef': 'off',
    },
  },
  // shadcn/ui primitives intentionally co-export cva variant helpers
  // (buttonVariants, badgeVariants) alongside their components.
  {
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
