import { useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { loadDashboardPage, loadSchemesPage } from '../routes/page-loaders'
import { prefetchProjectData, type ProjectPage } from './page-prefetch'

export function usePagePrefetch() {
  const client = useQueryClient()
  const { pathname } = useLocation()
  return (to: string) => {
    const preload = () => {
      if (to === pathname) return
      const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
      if (connection?.saveData) return
      const match = to.match(/^\/projects\/([1-9]\d*)\/(schemes|dashboard)$/)
      if (!match) return
      const page = match[2] as ProjectPage
      // Speculative downloads must not produce unhandled promise rejections.
      void (page === 'schemes' ? loadSchemesPage() : loadDashboardPage()).catch(() => {})
      void prefetchProjectData(client, Number(match[1]), page)
    }
    return { onPointerEnter: preload, onFocus: preload, onPointerDown: preload }
  }
}
