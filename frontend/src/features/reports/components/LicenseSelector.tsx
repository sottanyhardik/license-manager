import { useState } from 'react'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

interface Props {
  value: number[]
  onChange: (ids: number[]) => void
}

export function LicenseSelector({ value, onChange }: Props) {
  const [raw, setRaw] = useState(value.join(', '))

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const text = e.target.value
    setRaw(text)
    const ids = text
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0)
    onChange(ids)
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor="license-ids">License IDs</Label>
      <Input
        id="license-ids"
        placeholder="e.g. 1, 2, 3"
        value={raw}
        onChange={handleChange}
      />
      <p className="text-xs text-muted-foreground">Comma-separated license IDs</p>
    </div>
  )
}
