/**
 * Tests for useFileUpload (frontend/src/hooks/useFileUpload.js)
 *
 * api (src/api/axios) is vi.mock'd — no real HTTP.
 * sonner is vi.mock'd — toast side effects don't pollute assertions.
 *
 * Hook public interface under test:
 *   files, uploading, results, error, dragActive, fileProgress,
 *   handleFileChange, handleDrop, handleUpload, clearFiles, removeFile, setFiles
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFileUpload } from '@/hooks/useFileUpload'

// ── Module mocks ──────────────────────────────────────────────────────────────
vi.mock('@/api/axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import api from '@/api/axios'

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Build a synthetic File object with a given name, size, and type. */
function makeFile(name: string, sizeBytes: number, type = 'text/csv'): File {
  const content = new Uint8Array(sizeBytes)
  return new File([content], name, { type })
}

/** Build a synthetic input change event containing the given files. */
function makeChangeEvent(files: File[]) {
  return {
    target: {
      files,
      value: '',
    },
    // Prevent the hook's `e.target.value = ''` from throwing in jsdom
    preventDefault: vi.fn(),
  } as unknown as React.ChangeEvent<HTMLInputElement>
}

/** Build a synthetic drop event. */
function makeDropEvent(files: File[]) {
  return {
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    dataTransfer: { files },
  } as unknown as React.DragEvent<HTMLDivElement>
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('useFileUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Initial state ───────────────────────────────────────────────────────────

  it('starts with no files, no error, no results, not uploading, and zero progress', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    expect(result.current.files).toEqual([])
    expect(result.current.uploading).toBe(false)
    expect(result.current.results).toEqual([])
    expect(result.current.error).toBeNull()
    expect(result.current.dragActive).toBe(false)
    expect(result.current.fileProgress).toEqual({})
  })

  // ── File selection via handleFileChange ─────────────────────────────────────

  it('handleFileChange updates files state when a valid .csv file is selected', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    const file = makeFile('data.csv', 1024)
    act(() => {
      result.current.handleFileChange(makeChangeEvent([file]))
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0].name).toBe('data.csv')
    expect(result.current.error).toBeNull()
  })

  it('handleFileChange accepts multiple files when multiple=true (default)', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv', multiple: true })
    )

    const files = [makeFile('a.csv', 512), makeFile('b.csv', 512)]
    act(() => {
      result.current.handleFileChange(makeChangeEvent(files))
    })

    expect(result.current.files).toHaveLength(2)
  })

  it('handleFileChange keeps only the first file when multiple=false', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv', multiple: false })
    )

    const files = [makeFile('a.csv', 512), makeFile('b.csv', 512)]
    act(() => {
      result.current.handleFileChange(makeChangeEvent(files))
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0].name).toBe('a.csv')
  })

  // ── File size validation ────────────────────────────────────────────────────

  it('rejects a file that exceeds maxFileSize and sets error state', () => {
    const maxFileSize = 1 * 1024 * 1024 // 1 MB
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv', maxFileSize })
    )

    const oversizedFile = makeFile('huge.csv', maxFileSize + 1)
    act(() => {
      result.current.handleFileChange(makeChangeEvent([oversizedFile]))
    })

    // No files added
    expect(result.current.files).toHaveLength(0)
    // Error is set and contains the file name
    expect(result.current.error).toContain('huge.csv')
    expect(result.current.error).toContain('1MB')
  })

  it('accepts files below maxFileSize and clears any prior error', () => {
    const maxFileSize = 1 * 1024 * 1024
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv', maxFileSize })
    )

    // First: trigger an error
    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('huge.csv', maxFileSize + 1)]))
    })
    expect(result.current.error).not.toBeNull()

    // Then: select a valid file
    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('ok.csv', 1024)]))
    })
    expect(result.current.files).toHaveLength(1)
    expect(result.current.error).toBeNull()
  })

  // ── File type validation ────────────────────────────────────────────────────

  it('rejects a file with an extension not in accept list', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    const badFile = makeFile('report.xlsx', 1024, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    act(() => {
      result.current.handleFileChange(makeChangeEvent([badFile]))
    })

    expect(result.current.files).toHaveLength(0)
    expect(result.current.error).toContain('report.xlsx')
  })

  it('accepts MIME types case-insensitively', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: 'text/csv' })
    )

    const file = { name: 'ledger', size: 1024, type: 'TEXT/CSV' } as unknown as File
    act(() => {
      result.current.handleFileChange(makeChangeEvent([file]))
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.error).toBeNull()
  })

  it('rejects malformed file-like objects without throwing', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    act(() => {
      result.current.handleFileChange(makeChangeEvent([{} as File]))
    })

    expect(result.current.files).toHaveLength(0)
    expect(result.current.error).toBe('Invalid file selected')
  })

  // ── File selection via handleDrop ───────────────────────────────────────────

  it('handleDrop adds valid files and sets dragActive=false', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    const file = makeFile('dropped.csv', 2048)
    act(() => {
      result.current.handleDrop(makeDropEvent([file]))
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0].name).toBe('dropped.csv')
    expect(result.current.dragActive).toBe(false)
  })

  // ── removeFile ──────────────────────────────────────────────────────────────

  it('removeFile removes the file at the given index', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv', multiple: true })
    )

    act(() => {
      result.current.handleFileChange(
        makeChangeEvent([makeFile('a.csv', 512), makeFile('b.csv', 512)])
      )
    })
    expect(result.current.files).toHaveLength(2)

    act(() => {
      result.current.removeFile(0)
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0].name).toBe('b.csv')
  })

  // ── clearFiles / reset ──────────────────────────────────────────────────────

  it('clearFiles resets files, results, error, and fileProgress to initial state', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    // Put some state in first
    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('x.csv', 512)]))
      // Manually set an error via setError to verify clearFiles wipes it
      result.current.setError('some previous error')
    })

    act(() => {
      result.current.clearFiles()
    })

    expect(result.current.files).toEqual([])
    expect(result.current.results).toEqual([])
    expect(result.current.error).toBeNull()
    expect(result.current.fileProgress).toEqual({})
  })

  // ── handleUpload — no files guard ──────────────────────────────────────────

  it('handleUpload returns early with an error when no files are selected', async () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    let uploadResult: Awaited<ReturnType<typeof result.current.handleUpload>>
    await act(async () => {
      uploadResult = await result.current.handleUpload()
    })

    expect(uploadResult!.success).toBe(false)
    expect(uploadResult!.error).toMatch(/select at least one file/i)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('handleUpload rejects unsafe absolute endpoints before posting', async () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: 'https://example.test/upload/', accept: '.csv' })
    )

    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('valid.csv', 512)]))
    })

    let uploadResult: Awaited<ReturnType<typeof result.current.handleUpload>>
    await act(async () => {
      uploadResult = await result.current.handleUpload()
    })

    expect(uploadResult!.success).toBe(false)
    expect(uploadResult!.error).toMatch(/relative to the API origin/i)
    expect(api.post).not.toHaveBeenCalled()
  })

  // ── handleUpload — successful sequential upload ─────────────────────────────

  it('handleUpload calls api.post and returns success when server responds OK', async () => {
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { message: 'Processed', licenses: [], stats: {} },
    })

    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('valid.csv', 512)]))
    })

    let uploadResult: Awaited<ReturnType<typeof result.current.handleUpload>>
    await act(async () => {
      uploadResult = await result.current.handleUpload()
    })

    expect(api.post).toHaveBeenCalledOnce()
    expect(uploadResult!.success).toBe(true)
    expect(uploadResult!.successCount).toBe(1)
    expect(uploadResult!.failureCount).toBe(0)
    // On success the hook clears the files list
    expect(result.current.files).toHaveLength(0)
    expect(result.current.uploading).toBe(false)
  })

  it('handleUpload tolerates malformed success responses and missing progress totals', async () => {
    ;(api.post as ReturnType<typeof vi.fn>).mockImplementationOnce(async (_path, _formData, config) => {
      config.onUploadProgress?.({ loaded: 10, total: 0 })
      return { data: null }
    })

    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('valid.csv', 512)]))
    })

    let uploadResult: Awaited<ReturnType<typeof result.current.handleUpload>>
    await act(async () => {
      uploadResult = await result.current.handleUpload()
    })

    expect(uploadResult!.success).toBe(true)
    expect(uploadResult!.results[0]).toMatchObject({
      message: 'File processed successfully',
      licenses: [],
      stats: {},
      data: {},
    })
  })

  it('formatFileSize handles invalid and very large values safely', () => {
    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    expect(result.current.formatFileSize(Number.POSITIVE_INFINITY)).toBe('0 Bytes')
    expect(result.current.formatFileSize(-1)).toBe('0 Bytes')
    expect(result.current.formatFileSize(1024 ** 5)).toBe('1048576 GB')
  })

  // ── handleUpload — server error ─────────────────────────────────────────────

  it('handleUpload captures the error message when api.post rejects', async () => {
    const serverError = Object.assign(new Error('Server error'), {
      response: { data: { error: 'Parse failed' } },
    })
    ;(api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(serverError)

    const { result } = renderHook(() =>
      useFileUpload({ endpoint: '/api/upload/', accept: '.csv' })
    )

    act(() => {
      result.current.handleFileChange(makeChangeEvent([makeFile('bad.csv', 512)]))
    })

    let uploadResult: Awaited<ReturnType<typeof result.current.handleUpload>>
    await act(async () => {
      uploadResult = await result.current.handleUpload()
    })

    expect(uploadResult!.success).toBe(false)
    expect(uploadResult!.failureCount).toBe(1)
    const failedEntry = uploadResult!.results[0]
    expect(failedEntry.success).toBe(false)
    expect(failedEntry.error).toBe('Parse failed')
    expect(result.current.uploading).toBe(false)
  })
})
