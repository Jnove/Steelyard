import { Layout, Menu } from 'antd'
import { Link, Navigate, Route, Routes } from 'react-router-dom'

import HealthBadge from './components/HealthBadge'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import SchemesPage from './pages/SchemesPage'

const { Header, Content, Sider } = Layout

export default function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ color: '#2f5bb7', fontWeight: 600, fontSize: 18 }}>筑衡</div>
        <div style={{ color: '#666' }}>建筑方案智能比选智能体</div>
        <div style={{ marginLeft: 'auto' }}>
          <HealthBadge />
        </div>
      </Header>
      <Layout>
        <Sider width={220} theme="light">
          <Menu
            mode="inline"
            defaultSelectedKeys={['projects']}
            items={[
              { key: 'projects', label: <Link to="/projects">项目列表</Link> },
            ]}
          />
        </Sider>
        <Content style={{ padding: 24, background: '#fff' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:id/schemes" element={<SchemesPage />} />
            <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
            <Route path="/projects/:id/chat" element={<ChatPage />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}