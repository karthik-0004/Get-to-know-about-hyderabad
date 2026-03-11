import { useEffect, useRef, useState } from 'react'
import './UsageBadge.css'

function getDotColor(count, limit) {
  const ratio = count / limit
  if (ratio >= 14 / 15) return '#ef4444' // red
  if (ratio >= 10 / 15) return '#f59e0b' // amber/yellow
  return '#22c55e' // green
}

export default function UsageBadge({ usageInfo }) {
  const [flash, setFlash] = useState(false)
  const prevCount = useRef(usageInfo?.count ?? 0)

  // Animate on count change
  useEffect(() => {
    if (!usageInfo) return
    if (usageInfo.count !== prevCount.current) {
      prevCount.current = usageInfo.count
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 600)
      return () => clearTimeout(t)
    }
  }, [usageInfo?.count])

  if (!usageInfo) return null

  const { count, limit } = usageInfo
  const dotColor = getDotColor(count, limit)

  return (
    <div className={`usage-badge${flash ? ' usage-badge--flash' : ''}`}>
      <span className="usage-badge__dot" style={{ background: dotColor }} />
      <span className="usage-badge__text">
        API Calls: <strong>{count}</strong>/{limit}
      </span>
    </div>
  )
}
