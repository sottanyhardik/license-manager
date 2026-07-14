import { useCallback, useState } from 'react'

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      return item ? (JSON.parse(item) as T) : initialValue
    } catch {
      return initialValue
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
      setStoredValue(initialValue)
    } catch {
      // Ignore
    }
  }, [key, initialValue])

  return [storedValue, setValue, removeValue]
}
