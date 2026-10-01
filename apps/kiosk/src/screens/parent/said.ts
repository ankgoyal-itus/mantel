/** "4m ago", "3h ago", "2d ago": how long since a feed last answered. */
export function ageSaid(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) {
    return ''
  }
  const minutes = Math.max(0, Math.round((now.getTime() - then.getTime()) / 60000))
  if (minutes < 1) {
    return 'just now'
  }
  if (minutes < 60) {
    return `${minutes}m ago`
  }
  const hours = Math.floor(minutes / 60)
  return hours < 48 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`
}

/** "840 KB", "12.4 MB": the album's size, said the way the Finder says it. */
export function bytesSaid(bytes: number): string {
  if (bytes < 1000 * 1000) {
    return `${Math.max(0, Math.round(bytes / 1000))} KB`
  }
  if (bytes < 1000 * 1000 * 1000) {
    return `${(bytes / 1000 / 1000).toFixed(1)} MB`
  }
  return `${(bytes / 1000 / 1000 / 1000).toFixed(1)} GB`
}
