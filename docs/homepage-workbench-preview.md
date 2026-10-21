# 首页工作台预览

分支：`jnove/homepage-workbench`。本轮只重构 `/projects` 首页及其外框；方案录入、对比看板和对话路由保留既有界面。该分支未发布到生产。

## 页面与组件

- 首页采用项目列表与当前项目详情分栏，提供搜索、教学/虚构案例筛选、时间排序和分页。窄屏将详情放到列表下方，表格在容器内横向滚动。
- 项目新建、编辑和删除继续调用现有 API，保留校验反馈、删除确认与缓存清理；新建后进入该项目的方案页。
- 主色 `#9DD5D4` 小面积用于品牌与选中状态；`#327473` 用于操作与重要文字，`#56B6B5` 用于交互强调，`#DBF0EF` 用于浅色背景。页面以中性色和细边框为主。
- 基础组件由 shadcn/ui `radix-nova` 源码适配，补充 React 18 的 ref 兼容；配置见 `frontend/components.json`，来源与许可见组件目录的 `NOTICE.md`。
- 使用 Lucide、TanStack Table 和 React Hook Form。纯字段初始化、序列化和校验函数抽到 `utils/schema-form.ts`，原 `SchemaForm.tsx` 保持兼容导出，其他页面继续复用同一套业务规则。
- Tailwind 使用 `tw` 前缀且不加载 preflight；首页变量限制在 `.home-theme` 内。参数体量展示保留为可展开区域。

## 独立预览

不要指向生产数据库。以下命令在仓库根目录执行，两个服务分别使用终端。

```powershell
New-Item -ItemType Directory -Force backend/data/homepage-ui | Out-Null
$env:DATABASE_URL="sqlite:///$((Join-Path $PWD 'backend/data/homepage-ui/preview.db').Replace('\','/'))"
$env:LLM_PROVIDER='fake'
uv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8018
```

将仓库已有的五个案例导入该独立实例：

```powershell
uv run --project backend python scripts/publish_demo_cases.py --url http://127.0.0.1:8018 --apply --receipt backend/data/homepage-ui/preview-receipt.json
```

启动前端：

```powershell
$env:VITE_BASE_PATH='/'
$env:VITE_USE_MOCK='false'
$env:VITE_BACKEND_URL='http://127.0.0.1:8018'
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5182 --strictPort
```

打开 `http://127.0.0.1:5182/projects`。此预览使用本地案例和 FakeLLM，不能作为线上模型或工程结论的验收证据。

## 检查

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:homepage
```

浏览器检查需要本机 Chrome，只允许 localhost 地址，默认连接上面的预览服务。它仅创建和清理自己命名的验收项目，覆盖搜索、案例分类、排序、选择、320/375/414/768px 布局、表单与对话框、项目创建/编辑/删除、焦点恢复、失败重试及页面样式隔离。

截图与结果位于忽略目录 `backend/data/homepage-ui/browser/`。生产构建仍有部分大于 500kB 的产物，未在本轮扩展全站打包优化。

本轮验证：91 项前端测试、类型检查与生产构建通过；浏览器 7 组流程通过，未捕获页面脚本异常。桌面、375px 和 768px 截图已检查。
