import { render, fireEvent } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useReviewKeyboardShortcuts } from './useReviewKeyboardShortcuts'

const actions = {
  onNext: vi.fn(),
  onPrev: vi.fn(),
  onNextEvidence: vi.fn(),
  onPrevEvidence: vi.fn(),
  onAccept: vi.fn(),
  onReject: vi.fn(),
  onFocusEdit: vi.fn(),
  onShowHelp: vi.fn(),
}

function ShortcutHarness() {
  useReviewKeyboardShortcuts({ ...actions, enabled: true })
  return <input aria-label="Editable value" />
}

describe('useReviewKeyboardShortcuts', () => {
  beforeEach(() => {
    Object.values(actions).forEach((action) => action.mockClear())
  })

  it('uses horizontal movement for proposal navigation', () => {
    render(<ShortcutHarness />)

    fireEvent.keyDown(document, { key: 'a' })
    fireEvent.keyDown(document, { key: 'ArrowLeft' })
    fireEvent.keyDown(document, { key: 'd' })
    fireEvent.keyDown(document, { key: 'ArrowRight' })

    expect(actions.onPrev).toHaveBeenCalledTimes(2)
    expect(actions.onNext).toHaveBeenCalledTimes(2)
  })

  it('uses vertical movement for accept and reject', () => {
    render(<ShortcutHarness />)

    fireEvent.keyDown(document, { key: 'w' })
    fireEvent.keyDown(document, { key: 'ArrowUp' })
    fireEvent.keyDown(document, { key: 's' })
    fireEvent.keyDown(document, { key: 'ArrowDown' })

    expect(actions.onAccept).toHaveBeenCalledTimes(2)
    expect(actions.onReject).toHaveBeenCalledTimes(2)
  })

  it('uses Ctrl or Command plus horizontal arrows for evidence', () => {
    render(<ShortcutHarness />)

    fireEvent.keyDown(document, { key: 'ArrowLeft', ctrlKey: true })
    fireEvent.keyDown(document, { key: 'ArrowRight', ctrlKey: true })
    fireEvent.keyDown(document, { key: 'ArrowRight', metaKey: true })

    expect(actions.onPrevEvidence).toHaveBeenCalledOnce()
    expect(actions.onNextEvidence).toHaveBeenCalledTimes(2)
    expect(actions.onPrev).not.toHaveBeenCalled()
    expect(actions.onNext).not.toHaveBeenCalled()
  })

  it('focuses editing with E, reserves Shift for selection, and ignores typing inside form controls', () => {
    const { getByLabelText } = render(<ShortcutHarness />)

    fireEvent.keyDown(document, { key: 'e' })
    fireEvent.keyDown(document, { key: 'Shift' })
    fireEvent.keyDown(getByLabelText('Editable value'), { key: 'w' })

    expect(actions.onFocusEdit).toHaveBeenCalledOnce()
    expect(actions.onAccept).not.toHaveBeenCalled()
  })
})
