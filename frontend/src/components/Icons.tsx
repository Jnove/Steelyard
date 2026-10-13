import React from 'react'

interface IconProps extends React.SVGProps<SVGSVGElement> {
  size?: number
}

const baseProps = (size = 18, className?: string): React.SVGProps<SVGSVGElement> => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  className,
  'aria-hidden': 'true',
})

/** 好房子 · 居住品质 */
export function IconHome({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  )
}

/** 施工友好 · 工友安全 */
export function IconHardHat({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M2 18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v2z" />
      <path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" />
      <path d="M4 15v-3a8 8 0 0 1 16 0v3" />
    </svg>
  )
}

/** 结构安全 */
export function IconStructure({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M2 20h20" />
      <path d="M5 20V5l7-3 7 3v15" />
      <path d="M9 20v-6h6v6" />
      <line x1="9" y1="9" x2="15" y2="9" />
    </svg>
  )
}

/** 绿色低碳 */
export function IconLeaf({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
    </svg>
  )
}

/** 规则合规 · 防幻觉底座 */
export function IconShieldCheck({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  )
}

/** 权衡 · 筑衡标尺 */
export function IconScale({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M16 16l3-8 3 8a3 3 0 0 1-6 0z" />
      <path d="M2 16l3-8 3 8a3 3 0 0 1-6 0z" />
      <path d="M7 21h10" />
      <path d="M12 3v18" />
      <path d="M3 7h18" />
    </svg>
  )
}

/** 推荐方案 · 标杆 */
export function IconAward({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <circle cx="12" cy="8" r="6" />
      <path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11" />
    </svg>
  )
}

/** 多准则滑杆 · 权重设置 */
export function IconSliders({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  )
}

/** 智能体 · AI 编排 */
export function IconBot({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  )
}

/** 对话 · 追问 */
export function IconMessage({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

/** 报告 · 文档 */
export function IconFileText({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )
}

/** 箭头前进 */
export function IconArrowRight({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  )
}

/** 术语解释 · 帮助说明 */
export function IconHelpCircle({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

/** 警告 · 取舍关注 */
export function IconAlertTriangle({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

/** 成功勾选 */
export function IconCheck({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

/** 红线禁止 / 拦截 */
export function IconBan({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </svg>
  )
}

/** 角色 · 用户群 */
export function IconUser({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

/** 计算引擎 · 齿轮 */
export function IconCpu({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  )
}

/** 方案图层 */
export function IconLayers({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  )
}

/** 新增 / 加号 */
export function IconPlus({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

/** 导入 / 上传 */
export function IconUpload({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

/** 运行 / 评估 */
export function IconPlay({ size = 18, className, ...props }: IconProps) {
  return (
    <svg {...baseProps(size, className)} {...props}>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

