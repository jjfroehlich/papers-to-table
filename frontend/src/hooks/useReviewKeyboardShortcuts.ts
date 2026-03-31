import { useEffect, useCallback } from 'react'

interface Props {
  onNext: () => void
  onPrev: () => void
  onAccept: () => void
  onReject: () => void
  onFocusEdit: () => void
  onShowHelp: () => void
  enabled: boolean
}

export function useReviewKeyboardShortcuts({
  onNext,
  onPrev,
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
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      switch (e.key) {
        case ']':
        case 'n':
          e.preventDefault()
          onNext()
          break
        case '[':
        case 'p':
          e.preventDefault()
          onPrev()
          break
        case 'a':
          e.preventDefault()
          onAccept()
          break
        case 'r':
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
    [enabled, onNext, onPrev, onAccept, onReject, onFocusEdit, onShowHelp]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [handleKey])
}
