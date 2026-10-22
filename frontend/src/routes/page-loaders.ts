// Navigation and React.lazy share these imports, so intent preloads the same chunks.
export const loadSchemesPage = () => import('../pages/SchemesPage')
export const loadDashboardPage = () => import('../pages/DashboardPage')
