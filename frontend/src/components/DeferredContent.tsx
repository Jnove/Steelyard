import { Component, Suspense, type ReactNode } from 'react'
import { Alert } from 'antd'

class ContentBoundary extends Component<{ children: ReactNode; errorTitle: string }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed
      ? <Alert type="error" message={this.props.errorTitle} description="请刷新页面重试，其他功能仍可继续使用。" />
      : this.props.children
  }
}

export default function DeferredContent({ children, fallback, errorTitle }: {
  children: ReactNode; fallback: ReactNode; errorTitle: string
}) {
  return <ContentBoundary errorTitle={errorTitle}><Suspense fallback={fallback}>{children}</Suspense></ContentBoundary>
}
