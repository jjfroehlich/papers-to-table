/**
 * T091 — Keyboard shortcuts hook for the review workspace.
 *
 * Shortcuts:
 * - ArrowLeft / p: previous proposal
 * - ArrowRight / n: next proposal
 * - a: accept current proposal
 * - r: reject current proposal
 * - e: focus edit input (accept-with-edit)
 * - v: focus/open evidence viewer
 */
import { useEffect } from 'react'

export interface ReviewShortcutHandlers {
  onPrev: () => void
  onNext: () => void
  onAccept: () => void
  onReject: () => void
  onFocusEdit: () => void
  onFocusEvidence: () => void
  /** Set to false to temporarily disable shortcuts (e.g. when typing in an input) */
  enabled?: boolean
}

export function useReviewKeyboardShortcuts({
  onPrev,
  onNext,
  onAccept,
  onReject,
  onFocusEdit,
  onFocusEvidence,
  enabled = true,
}: ReviewShortcutHandlers) {
  useEffect(() => {
    if (!enabled) return

    function handleKeyDown(event: KeyboardEvent) {
      // Do not capture when typing in an input/textarea/select
      const target = event.target as HTMLElement
      const tagName = target.tagName
      if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT') return
      if (target.isContentEditable) return

      switch (event.key) {
        case 'ArrowLeft':
        case 'p':
          event.preventDefault()
          onPrev()
          break
        case 'ArrowRight':
        case 'n':
          event.preventDefault()
          onNext()
          break
        case 'a':
          event.preventDefault()
          onAccept()
          break
        case 'r':
          event.preventDefault()
          onReject()
          break
        case 'e':
          event.preventDefault()
          onFocusEdit()
          break
        case 'v':
          event.preventDefault()
          onFocusEvidence()
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [enabled, onPrev, onNext, onAccept, onReject, onFocusEdit, onFocusEvidence])
}
