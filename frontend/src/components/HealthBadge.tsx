import { Badge, Space, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { request } from '../api/client'

interface HealthPayload {
  status: string
  version: string
}

/**
 * 首页右上角的后端健康状态徽章。
 *
 * 用于 T1 验收：docker compose up --build 后浏览器打开 http://localhost:8080
 * 即可看到 "后端状态：ok" 的标识。
 */
export default function HealthBadge() {
  const [payload, setPayload] = useState<HealthPayload | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    request<HealthPayload>('/health')
      .then((data) => {
        if (!cancelled) setPayload(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : '未知错误')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <Space>
        <Badge status="error" />
        <Typography.Text type="danger">后端不可达：{error}</Typography.Text>
      </Space>
    )
  }
  if (!payload) {
    return (
      <Space>
        <Badge status="processing" />
        <Typography.Text type="secondary">后端状态：检测中…</Typography.Text>
      </Space>
    )
  }
  return (
    <Space>
      <Badge status="success" />
      <Typography.Text>后端状态：{payload.status}（v{payload.version}）</Typography.Text>
    </Space>
  )
}