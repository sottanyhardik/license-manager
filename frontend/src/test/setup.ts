// Vitest global setup — runs once before the test suite.
// Adds jest-dom matchers (toBeInTheDocument, toHaveClass, ...) to expect().
import '@testing-library/jest-dom/vitest'

const createStorage = (): Storage => {
  const store = new Map<string, string>()

  return {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key)
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
  }
}

if (!globalThis.localStorage) {
  Object.defineProperty(globalThis, 'localStorage', {
    value: createStorage(),
    configurable: true,
  })
}

if (!globalThis.sessionStorage) {
  Object.defineProperty(globalThis, 'sessionStorage', {
    value: createStorage(),
    configurable: true,
  })
}

// jsdom does not implement ResizeObserver. `cmdk` (the CommandPalette) observes
// its list on mount, so without this any component rendering it throws
// "ResizeObserver is not defined" before a single assertion runs. Stub it
// globally rather than per-test so every consumer gets it.
if (!globalThis.ResizeObserver) {
  class ResizeObserverStub implements ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }

  Object.defineProperty(globalThis, 'ResizeObserver', {
    value: ResizeObserverStub,
    configurable: true,
    writable: true,
  })
}

// jsdom also has no layout engine, so Element.scrollIntoView is missing. cmdk
// calls it when it moves the selected item into view.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView(): void {}
}
