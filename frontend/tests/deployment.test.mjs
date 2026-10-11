import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'
import { fileURLToPath } from 'node:url'

async function apiFor(base, override) {
  const result = await build({
    stdin: { contents: `export { request } from '../src/api/client'; export { streamAgent } from '../src/api/agents'`,
      resolveDir: fileURLToPath(new URL('.', import.meta.url)), loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent',
    define: { 'import.meta.env': JSON.stringify({ BASE_URL: base, VITE_API_BASE: override }) },
  })
  const module = { exports: {} }
  new Function('module', 'exports', result.outputFiles[0].text)(module, module.exports)
  return module.exports
}

for (const [base, override, expected] of [
  ['/', undefined, '/api'],
  ['/steelyard/', undefined, '/steelyard/api'],
  ['/steelyard/', '/custom/api/', '/custom/api'],
]) {
  test(`公开 base ${base} 与覆盖 ${override ?? '默认'} 同时作用于 REST 和 POST SSE`, async () => {
    const api = await apiFor(base, override)
    const originalFetch = globalThis.fetch
    const calls = []
    globalThis.fetch = async (url, options) => {
      calls.push([url, options.method])
      return url.endsWith('/chat')
        ? new Response('event: done\ndata: {"report":"ok"}\n\n', { headers: { 'content-type': 'text/event-stream' } })
        : Response.json({ status: 'ok' })
    }
    try {
      assert.deepEqual(await api.request('health'), { status: 'ok' })
      await api.streamAgent('7', 'chat', {}, () => {}, new AbortController().signal)
      assert.deepEqual(calls, [[`${expected}/health`, 'GET'], [`${expected}/projects/7/chat`, 'POST']])
    } finally {
      globalThis.fetch = originalFetch
    }
  })
}
