# 对比展示的参考资源与设计取舍

## 已采用的方向

1. 二维散点图先展示整体取舍，再由选择操作进入双方案差值图；矩阵作为完整查询视图。
2. 给每个点标出方案名称；使用双环表达四维非劣结果，避免单靠颜色区分。
3. 双方案比较使用一致刻度、两个端点及带符号的分差，并配一段只复述已计算结果的短解释。
4. 放大正文与关键数字，减少装饰眉题；完整公式放入可展开区域，保留查看证据的入口。
5. 按 Hallmark 的交互参考重做查询组件：在当前区域查看依据、保持选择和滚动位置、提供键盘及触摸等效操作；改变状态时给出就地反馈。
6. 按用户提供的 UI 素材手册统一玻璃材质：蓝紫 / 淡粉柔光背景、半透明面板与白色高光；图表以固定坐标和深色文字表达数据。

## 来源与适用范围

| 官方或作者资料 | 具体借鉴 | 当前取舍 |
| --- | --- | --- |
| [Apache ECharts 示例](https://github.com/apache/echarts-examples) | scatter、heatmap 的轴、标签、提示和强调；以现有 5.x 能力为集成边界 | 正式前端继续使用已安装的 ECharts；当前展示原型使用原生 SVG，支持离线和矢量导出 |
| [AntV Infographic](https://github.com/antvis/Infographic)及其 [compare 模板](https://github.com/antvis/Infographic/blob/main/skills/infographic-creator/SKILL.md) | 两侧方案身份、同构内容、关键数字与短结论组织在同一张信息图 | 采用图与短结论的构图方法；四象限分类模板不直接充当连续数值散点图 |
| [Frontend Design Skill](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md) | 让主图承担视觉重点，排版服务实际内容，减少无意义标签和装饰 | 图表放在主画面；按钮明确说明后续动作；删除英文装饰眉题 |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 可读字号、清楚的交互状态、颜色之外的标签与键盘操作 | 明确方案名称、非劣双环、违规文字；提供键盘焦点及折叠说明 |
| [AntV Chart Visualization Skills](https://github.com/antvis/chart-visualization-skills) | 按数据关系选择图表 | 使用它的图表选择思路；不调用该集合中 `chart-visualization` 的外部图片 API |
| [AntV S2](https://github.com/antvis/S2) | 交叉表的信息结构与交互 | 当前仅五套方案、四个维度，保留轻量矩阵即可；指标扩充后再评估 |
| [React Compare Slider](https://github.com/nerdyman/react-compare-slider) | 双图拖动比较 | 适合以后已有图纸或效果图时使用，当前指标数据展示不引入 |
| [Hallmark](https://github.com/Nutlope/hallmark/blob/main/skills/hallmark/SKILL.md)、[交互与状态](https://github.com/Nutlope/hallmark/blob/main/skills/hallmark/references/interaction-and-states.md)、[微交互](https://github.com/Nutlope/hallmark/blob/main/skills/hallmark/references/microinteractions.md) | 清楚的触发与反馈、稳定几何、键盘焦点、44px 触摸目标、减少动态效果 | 参考交互章节优化现有工作台，不安装外部包或运行其脚本。查询反馈直接更新表内结果；导出发生在浏览器下载记录中，提供就地状态提示 |

## 数值和视觉语义

- 图表只使用 `frontend/src/mocks/fixtures/data.json` 的已提交示例快照；不因为希望产生视觉变化而改专业数据。
- 0 分是有效值，缺数据是无值状态。ECharts 官方热力图示例中的 `item[2] || '-'` 不适用于筑衡；应单独判断 null/undefined。
- 四维非劣状态从完整排序响应读取，不用二维投影重新推算或连成所谓“四维边界”。
- 散点坐标统一 0–100，不随角色变化；角色切换改变权重、名次和贴近度。原始样例中四个角色第一名相同。
- 不设没有专业依据的“50 分好坏分界线”，不把图表坐标网格线说成合规阈值。
- 违规状态通过文字、斜纹、空心点和排名排除表达；缺值不绘制散点，矩阵显示“缺数据”，不填为 0。

本目录实现为原创页面代码，以上链接作为布局、交互和图形类型参考。Hallmark 按用户指定读取并参考其交互部分；未安装外部 Skill 包或引入新的图表运行依赖。

## 用户提供的玻璃素材手册（2026-10-12）

原始文件保存在 [resources/liquid-glass](resources/liquid-glass/Steelyard_UI_Resource_Guide.md)，附带图片是手册中的概念配色图。手册内的安装步骤、任务说明和第三方资源介绍均作为参考资料；本轮没有运行这些安装命令、复制第三方组件源码或安装 Skill。

采用其近白背景、两层 radial-gradient、20px blur、柔和边线与圆角建议。对图表做了原创 SVG 材质设计，未加载 React Bits / GlassKit / liquid-glass-react。原型的光学效果属于绘制高光及毛玻璃，不能称为真实折射。浏览器验收范围为本机 Edge；Safari / Firefox 的正式组件兼容性由前端接入时验证。
