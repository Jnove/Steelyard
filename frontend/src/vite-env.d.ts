/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端基础地址，默认 BASE_URL + api（Vite dev server 会代理到后端） */
  readonly VITE_API_BASE?: string
  /** true 启用离线示例；其余值都使用真实后端。 */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
