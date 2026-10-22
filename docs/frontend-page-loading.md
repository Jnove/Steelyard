# 方案页与看板加载

工作台页面先挂载并请求数据，图表在局部 Suspense 中异步加载。ECharts 通过 `echarts/core` 仅注册雷达图、折线图、画布渲染器及实际使用的组件；新增图表类型时需同步更新 `ChartRenderer.tsx`。

评分溯源保留常驻 Drawer 外壳，以保留关闭动画和焦点恢复；内容模块首次打开时下载。方案编辑表单同样在打开弹窗时下载。局部模块下载失败时显示可读提示，不阻断页面其他部分。

侧栏、项目列表及项目详情中的方案页和看板链接在指针进入、键盘聚焦或按下时预加载对应模块及已有数据。开启浏览器节省流量模式时跳过预加载。预加载只发送 GET，不重新评估、排序或调用模型；实际进入看板后仍按当前项目保存的角色或自定义权重请求排序。

页面与预加载共享 `project-queries.ts` 的查询键。字段配置缓存 5 分钟，其余查询沿用全局 30 秒设置。方案保存、重新评估或对话推演后，先取消在途方案/评估/排名查询，再标记结果失效，防止旧预加载响应恢复旧结果。

## 验证

`npm test` 检查预加载去重、字段配置缓存、失败恢复及保存期间的在途响应竞态；`npm run build` 检查类型和生产包。

浏览器回归使用隔离 FakeLLM 后端的预览库（需有项目 1、4、5），不连接生产库：

```powershell
# frontend/，后端示例地址为 8018；预览沿用 Vite 的 API 代理。
$env:VITE_BACKEND_URL='http://127.0.0.1:8018'
$env:VITE_BASE_PATH='/'
$env:VITE_USE_MOCK='false'
npm run build
npm run preview -- --host 127.0.0.1 --port 5185 --strictPort

# 另一个终端，生产包预览已启动后执行：
$env:WORKBENCH_URL='http://127.0.0.1:5185'
node scripts/verify-page-loading.mjs
node scripts/verify-dashboard-controls.mjs
node scripts/verify-rank-distribution.mjs
npm run test:workbench
```

`verify-page-loading.mjs` 刻意挂起图表或路由模块下载，验证排名先显示、切换时导航保留、预加载缓存复用、表单与溯源按需下载、关闭焦点恢复及图表失败隔离。它只读取业务数据；报告和截图写入忽略目录 `backend/data/homepage-ui/performance/`。

可设置 `LOADING_AFTER_URL`（默认 `http://127.0.0.1:5185`）测试 `/steelyard` 等公开子路径；若使用独立构建目录，同步设置 `LOADING_AFTER_DIST`。对照旧版本时另设 `LOADING_BEFORE_URL`，并将旧生产包保存在上述报告目录的 `before-dist/`；体积统计取浏览器实际请求的文件，避免把残留文件算入结果。

这些检查验证本地生产包行为；公网秒数仍需发布后复测。
