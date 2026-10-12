# 对比展示的参考资源与设计取舍

## 已采用的方向

1. 二维散点图先展示整体取舍，再由选择操作进入双方案差值图；矩阵作为完整查询视图。
2. 给每个点标出方案名称；使用双环表达四维非劣结果，避免单靠颜色区分。
3. 双方案比较使用一致刻度、两个端点及带符号的分差，并配一段只复述已计算结果的短解释。
4. 放大正文与关键数字，减少装饰眉题；完整公式放入可展开区域，保留查看证据的入口。

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

## 数值和视觉语义

- 图表只使用 `frontend/src/mocks/fixtures/data.json` 的已提交示例快照；不因为希望产生视觉变化而改专业数据。
- 0 分是有效值，缺数据是无值状态。ECharts 官方热力图示例中的 `item[2] || '-'` 不适用于筑衡；应单独判断 null/undefined。
- 四维非劣状态从完整排序响应读取，不用二维投影重新推算或连成所谓“四维边界”。
- 散点坐标统一 0–100，不随角色变化；角色切换改变权重、名次和贴近度。原始样例中四个角色第一名相同。
- 不设没有专业依据的“50 分好坏分界线”，不把图表坐标网格线说成合规阈值。
- 违规状态通过文字、斜纹、空心点和排名排除表达；缺值不绘制散点，矩阵显示“缺数据”，不填为 0。

本目录实现为原创页面代码，以上链接作为布局、交互和图形类型参考。未安装或调用外部 Skill，也未引入新的图表运行依赖。
