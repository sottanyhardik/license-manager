import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

// Smoke test — proves the test harness works end to end:
// a pure utility and a real React component render in jsdom.
describe('frontend test harness', () => {
  it('cn() merges tailwind classes (later wins)', () => {
    const hidden = false
    expect(cn('p-2', 'p-4')).toBe('p-4')
    expect(cn('text-red-500', hidden && 'hidden', 'font-bold')).toContain('font-bold')
  })

  it('renders a shadcn Button with its label', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })
})
