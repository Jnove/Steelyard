/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端基础地址，默认 /api（Vite dev server 会代理到后端） */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}