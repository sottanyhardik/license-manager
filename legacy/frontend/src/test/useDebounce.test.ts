/**
 * Tests for useDebounce (frontend/src/hooks/useDebounce.js)
 *
 * Uses fake timers to control setTimeout without real wall-clock waits.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '@/hooks/useDebounce'

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the initial value immediately without waiting', () => {
    const { result } = renderHook(() => useDebounce('hello', 300))
    expect(result.current).toBe('hello')
  })

  it('does NOT update the debounced value before the delay has elapsed', () => {
    let value = 'initial'
    const { result, rerender } = renderHook(() => useDebounce(value, 300))

    value = 'updated'
    rerender()

    // Advance time by less than the delay — should still be stale
    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(result.current).toBe('initial')
  })

  it('updates the debounced value after the full delay elapses', () => {
    let value = 'initial'
    const { result, rerender } = renderHook(() => useDebounce(value, 300))

    value = 'updated'
    rerender()

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current).toBe('updated')
  })

  it('resets the timer when value changes before delay — only the last value emerges', () => {
    let value = 'first'
    const { result, rerender } = renderHook(() => useDebounce(value, 300))

    // First change at t=0
    value = 'second'
    rerender()
    act(() => { vi.advanceTimersByTime(200) }) // 200ms in — timer still pending

    // Second change at t=200 — should restart the 300ms countdown
    value = 'third'
    rerender()
    act(() => { vi.advanceTimersByTime(200) }) // total 400ms from first change, but only 200ms since last

    // Still not resolved — last timer needs 100ms more
    expect(result.current).toBe('first')

    act(() => { vi.advanceTimersByTime(100) }) // now 300ms have passed since 'third' was set

    expect(result.current).toBe('third')
  })

  it('uses the default delay of 300ms when no delay argument is given', () => {
    let value = 'a'
    const { result, rerender } = renderHook(() => useDebounce(value))

    value = 'b'
    rerender()

    act(() => { vi.advanceTimersByTime(299) })
    expect(result.current).toBe('a')

    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current).toBe('b')
  })

  it('works with non-string values (numbers, objects)', () => {
    let value = 42
    const { result, rerender } = renderHook(() => useDebounce(value, 100))

    value = 99
    rerender()

    act(() => { vi.advanceTimersByTime(100) })
    expect(result.current).toBe(99)
  })
})
