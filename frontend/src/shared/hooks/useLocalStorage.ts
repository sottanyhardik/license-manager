import { useCallback, useRef, useState } from 'react'

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  // Capture the initial value in a ref so removeValue's dep array stays
  // stable even when the caller passes a new object reference each render.
  const initialValueRef = useRef<T>(initialValue)

  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      return item ? (JSON.parse(item) as T) : initialValueRef.current
    } catch {
      return initialValueRef.current
    }
  })

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const valueToStore =
          typeof value === 'function' ? (value as (prev: T) => T)(storedValue) : value
        setStoredValue(valueToStore)
        localStorage.setItem(key, JSON.stringify(valueToStore))
      } catch {
        // Ignore write errors (e.g. storage quota exceeded)
      }
    },
    [key, storedValue],
  )

  const removeValue = useCallback(() => {
    try {
      localStorage.removeItem(key)
      setStoredValue(initialValueRef.current)
    } catch {
      // Ignore
    }
  }, [key]) // initialValueRef is stable — no need to list it

  return [storedValue, setValue, removeValue]
}
