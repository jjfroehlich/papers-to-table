import { useEffect, useCallback } from 'react'

interface Props {
  onNext: () => void
  onPrev: () => void
  onNextEvidence: () => void
  onPrevEvidence: () => void
  onAccept: () => void
  onReject: () => void
  onFocusEdit: () => void
  onShowHelp: () => void
  enabled: boolean
}

export function useReviewKeyboardShortcuts({
  onNext,
  onPrev,
  onNextEvidence,
  onPrevEvidence,
  onAccept,
  onReject,
  onFocusEdit,
  onShowHelp,
  enabled,
}: Props) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled) return
      // Skip if focus is inside an input/textarea/select
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (target?.isContentEditable || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowRight') {
        e.preventDefault()
        onNextEvidence()
        return
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowLeft') {
        e.preventDefault()
        onPrevEvidence()
        return
      }

      if (e.ctrlKey || e.metaKey || e.altKey) return

      switch (e.key.toLowerCase()) {
        case 'd':
        case 'arrowright':
          e.preventDefault()
          onNext()
          break
        case 'a':
        case 'arrowleft':
          e.preventDefault()
          onPrev()
          break
        case 'w':
        case 'arrowup':
          e.preventDefault()
          onAccept()
          break
        case 's':
        case 'arrowdown':
          e.preventDefault()
          onReject()
          break
        case 'e':
          e.preventDefault()
          onFocusEdit()
          break
        case '?':
          e.preventDefault()
          onShowHelp()
          break
      }
    },
    [enabled, onNext, onPrev, onNextEvidence, onPrevEvidence, onAccept, onReject, onFocusEdit, onShowHelp]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [handleKey])
}
