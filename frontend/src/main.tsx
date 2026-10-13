import React from 'react'
import ReactDOM from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { theme, installTheme } from './theme'
import './index.css'
import './workbench.css'
import './liquid-glass.css'

installTheme()
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false } } })
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ConfigProvider theme={theme} locale={zhCN}><AntApp>
    <QueryClientProvider client={client}><BrowserRouter basename={import.meta.env.BASE_URL}><App /></BrowserRouter></QueryClientProvider>
  </AntApp></ConfigProvider></React.StrictMode>,
)
