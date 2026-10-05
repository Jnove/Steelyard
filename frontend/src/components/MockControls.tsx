import { useEffect, useState } from 'react'
import { Button, Space, Typography } from 'antd'
import { USE_MOCK } from '../api/client'

type MockTools = Pick<typeof import('../mocks'),
  'mockImportExampleUrl' | 'mockImportInvalidExampleUrl' | 'resetMockData'>

/** 离线模式工具栏；恢复后刷新页面，同时清除当前页面的查询缓存。 */
export default function MockControls() {
  const [tools, setTools] = useState<MockTools>()
  const [error, setError] = useState<string>()
  useEffect(() => {
    if (!USE_MOCK) return
    let active = true
    void import('../mocks').then(module => {
      if (active) setTools(module)
    }).catch(() => {
      if (active) setError('离线工具加载失败，请刷新重试。')
    })
    return () => { active = false }
  }, [])
  if (!USE_MOCK) return null
  const reset = () => {
    try {
      tools?.resetMockData()
      window.location.reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '恢复样例失败，请检查本地存储。')
    }
  }
  return <aside aria-label="离线样例工具">
    <Space wrap>
      <Typography.Text type="secondary">【示例】离线数据操作</Typography.Text>
      <Button size="small" disabled={!tools} href={tools?.mockImportExampleUrl} download="demo-import.xlsx">下载正确 Excel</Button>
      <Button size="small" disabled={!tools} href={tools?.mockImportInvalidExampleUrl} download="demo-invalid.xlsx">下载错误 Excel</Button>
      <Button size="small" disabled={!tools} onClick={reset}>恢复样例并刷新</Button>
      <Typography.Text type="secondary">恢复将清除本机演示编辑及评估结果。</Typography.Text>
    </Space>
    {error && <p role="alert">{error}</p>}
  </aside>
}
