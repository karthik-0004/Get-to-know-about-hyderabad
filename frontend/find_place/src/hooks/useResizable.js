import { useCallback, useRef, useState } from 'react'

/**
 * Hook that provides mouse-drag resizing for a panel.
 *
 * @param {object}  opts
 * @param {number}  opts.defaultWidth  – initial width in px
 * @param {number}  opts.minWidth      – smallest allowed width
 * @param {number}  opts.maxWidth      – largest allowed width
 *
 * @returns {{ width, isDragging, handleMouseDown }}
 */
export default function useResizable({
  defaultWidth = 420,
  minWidth = 350,
  maxWidth = 700,
} = {}) {
  const [width, setWidth] = useState(defaultWidth)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(defaultWidth)

  const onMouseMove = useCallback(
    (e) => {
      if (!dragging.current) return
      // Panel is on the RIGHT → dragging left = wider panel
      const delta = startX.current - e.clientX
      const next = Math.min(maxWidth, Math.max(minWidth, startW.current + delta))
      setWidth(next)
    },
    [minWidth, maxWidth],
  )

  const onMouseUp = useCallback(() => {
    dragging.current = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [onMouseMove])

  const handleMouseDown = useCallback(
    (e) => {
      e.preventDefault()
      dragging.current = true
      startX.current = e.clientX
      startW.current = width
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    },
    [width, onMouseMove, onMouseUp],
  )

  return { width, isDragging: dragging.current, handleMouseDown }
}
