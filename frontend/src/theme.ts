import type { ThemeConfig } from 'antd'

/**
 * Ant Design 主题配置。
 *
 * ⚠️ 工业设计同学在此调整视觉：颜色 / 字体 / 圆角 / 间距等 token。
 * 后续页面尽量只引用此处的 token，避免散落硬编码色值。
 */
export const theme: ThemeConfig = {
  token: {
    // 主色：沉稳的工业蓝，避免金融/互联网常用的亮蓝
    colorPrimary: '#2f5bb7',
    colorInfo: '#2f5bb7',
    borderRadius: 6,
    fontSize: 14,
  },
  components: {
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#fafafa',
    },
    Menu: {
      itemSelectedBg: '#e6efff',
      itemSelectedColor: '#2f5bb7',
    },
  },
}