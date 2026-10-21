import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 同时加载项目根的 .env（与后端共享 LLM / DATABASE 配置）
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')
  const base = process.env.VITE_BASE_PATH ?? env.VITE_BASE_PATH ?? '/'
  const apiPrefix = `${base.replace(/\/$/, '')}/api`

  return {
    base,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      // 开发代理：前端 /api 请求转发到本地后端
      proxy: {
        [apiPrefix]: {
          target: env.VITE_BACKEND_URL ?? 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (requestPath: string) => `/api${requestPath.slice(apiPrefix.length)}`,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  }
})
