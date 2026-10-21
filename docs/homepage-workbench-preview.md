# 筑衡工作台界面预览

分支：`jnove/homepage-workbench`。覆盖项目总览、方案录入、方案对比看板、对话与报告四个页面，以及共享导航、参数弹窗、依据抽屉与比较图导出。该分支未发布到生产。

## 页面与组件

- 首页采用项目列表与当前项目详情分栏，提供搜索、教学/虚构案例筛选、时间排序和分页。窄屏将详情放到列表下方，表格在容器内横向滚动。
- 原 Three.js 建筑展台放在首页标题下、项目列表上方，默认展开。保留参数驱动体量、项目与方案切换、鼠标/方向键观察和复位，仍有 WebGL 不可用时的静态回退。
- 共享侧栏提供项目切换与三个业务页入口；切换项目保留当前工作页，切换页面回到顶部。窄屏改用带焦点恢复的导航对话框。
- 方案页优先呈现候选表与横向参数对照，结构摘要可以展开查看；数值右对齐，缺值仍显示未填写。看板先确定角色与讨论方案，再呈现建议和比较视图；对话页保留流式结果、参数预览、确认执行、报告下载与依据追溯。
- 项目新建、编辑和删除继续调用现有 API，保留校验反馈、删除确认与缓存清理；新建后进入该项目的方案页。
- 主色 `#9DD5D4` 小面积用于品牌与选中状态；`#327473` 用于操作与重要文字，`#56B6B5` 用于交互强调，`#DBF0EF` 用于浅色背景。页面以中性色和细边框为主。
- 基础组件由 shadcn/ui `radix-nova` 源码适配，补充 React 18 的 ref 兼容；配置见 `frontend/components.json`，来源与许可见组件目录的 `NOTICE.md`。
- 使用 Lucide、TanStack Table 和 React Hook Form。纯字段初始化、序列化和校验函数抽到 `utils/schema-form.ts`，原 `SchemaForm.tsx` 保持兼容导出，其他页面继续复用同一套业务规则。
- 复杂表单、数据表、滑杆与抽屉继续使用现有 Ant Design，统一主题、边框和密度；通用图标改为 Lucide。Tailwind 使用 `tw` 前缀且不加载 preflight，共享外框仍限制在 `.home-theme` 内。
- 图表与参数表共用稳定的方案颜色。同一方案换角色、换排序或换页面不会换色；概率图的颜色表示名次，维度标签的颜色表示维度，二者有独立语义。

## 设计依据

参考 Design Taste Frontend 的应用界面流程，选择 `accent-ladder`，seed `1431066042`，保留已确认的品牌色与系统中文字体。布局围绕实际任务展开：

| 页面 | 首要问题 | 主要内容 |
| --- | --- | --- |
| 项目总览 | 当前有哪些地块与候选方案？ | 建筑体量、项目列表、当前项目详情 |
| 方案录入 | 输入是否完整、方案差异在哪里？ | 候选表、参数对照、按 schema 分组的表单 |
| 比选看板 | 当前偏好下如何取舍、依据是什么？ | 角色与权重、推荐摘要、取舍/差值/指标规则三种视图 |
| 对话与报告 | 如何解释结果并验证调整假设？ | 当前上下文、建议问题、流式解释、推演确认、报告 |

保留筑衡自身内容：真实地块背景与教学方案的区分、四个固定维度、角色权重、TOPSIS 排名、硬约束排除、数据不足状态、公式和规则来源、参数体量示意，以及先预览再确认的推演流程。界面不补造指标、地块条件或规则依据。

浏览器检查修正了小于 11px 的文字、厚重面板阴影、低对比文字、数值对齐及手机表格过度折行。保留的取舍：异质内容面板按自身高度排列，避免拉出空白；密集参数的单位和辅助说明使用 11–12px；完整比较与分析可滚动查阅，不把所有图表压进一个首屏。长表与固定刻度图在自身容器内横向滚动。

减少动画使用极短时长保留组件的完成事件，修复 Ant Design 弹窗因旧的 `animation: none` 停在透明状态的问题。长参数表单校验失败时自动滚动到首个错误。

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
npm --prefix frontend run test:workbench
$env:ROADSHOW_URL='http://127.0.0.1:5182'
$env:ROADSHOW_ALLOW_WRITE='1'
node frontend/scripts/verify-roadshow.mjs
```

浏览器检查需要本机 Chrome，只允许 localhost 地址，默认连接上面的预览服务。写入测试只创建和清理自己命名的验收项目，覆盖项目 CRUD、筛选与故障恢复、320/375/414/768px 首页布局，以及四个页面在 1440/768/390px 的布局、导航、方案表单校验、依据抽屉、三种比较视图、搜索、方向键和 SVG 导出。路演回归还覆盖角色与方案上下文、解释、推演取消/确认、过期预览与流式冲突恢复、报告下载、跨项目隔离。

截图与结果位于忽略目录 `backend/data/homepage-ui/browser/`。生产构建仍有部分大于 500kB 的产物，未在本轮扩展全站打包优化。

验证结果与截图由上述脚本写入本地忽略目录；不能将 FakeLLM 的本地流程验收等同于生产模型验收。

2026-10-21 本地验证：91 项前端测试、类型检查、生产构建通过；首页 7 组、工作台 5 组、路演链路 10 组浏览器检查通过，未捕获页面脚本异常。四页的桌面、平板和手机截图已检查；Design Taste 检查无 FAIL，保留的密度和布局 WARN 见上面的取舍说明。
