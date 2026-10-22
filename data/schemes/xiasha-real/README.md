# 钱塘区下沙公租房一期 · 对比案例

**2026-10-22 路演主案例**。本轮口径、关键参数的来源/计算方法与待签认人见 [参数核对表](parameter-review.md)。A/B/C 的参数与规则调整后已重新生成检查证据；不要使用旧截图或旧排名。

默认和严格版均保留规划三项上限及设防烈度缺失。当前浙江册实算每套有 **5 条数据不足**，三套均保留 69 m 落地式脚手架的 K-05 专家论证提示；这些是教学施工基准，不是已批准施工方案。补设防后 B 仍可能缺 `mic_precast_wall_shear_ratio`。

重复施工指标 G-02/G-03 合并至 K-01/K-02；本项目暂不计分 G-05/Q-05/Q-06，其余项目保留现有代理指标口径。户型三等分已清空，逐栋楼层和住宅/配套、单元及电梯服务户数仍待补证。只能展示“已知条件下的评分与取舍”，不能认定全部合规或确定最优。

真实项目公开资料与待复核记录分开标注；方案数值为演示自拟，不是该项目的批准或建成方案。

同区规模对照与缺规划条件的诚实提示。户数1114、23层、8栋参考2024年项目报道，仍按演示方案处理。

## 来源与边界

公开规模来源：[浙江专项债券披露](https://www.governbond.org.cn/uploadFiles/33/attachFiles/202505/388fa8b9-b364-4828-b9aa-0fdb2644e484.pdf)，PDF 第 43 页；本次读取日期 2026-10-14。公开规模见 `project.json` 的 `_public_facts`，逐字段状态见 `_field_status`。

地上/地下建筑面积分开记录，评分输入 `gfa` 使用演示地上面积。公开规模不是规划条件上限，未取得的条件不补造。
总基底仍按等高体量假设 `gfa / floors` 计算；该假设使 G-05 恒约为 1，因此本项目已暂不计分该项，不能将其作为更绿色的证据。
严格版是本次已核验字段的子集，数据不足不等于合规通过，也不保证可以给出有效推荐。

## 文件与运行

项目参数在 `project.json`；A/B/C 是三个结构路线的演示方案。D/E/F 和 `whatif.json` 属于其他虚构边界案例，不属于下沙主案例。
检查证据是 `_check.txt`、`_check-gb.txt`，真实地块另有 `_check-verified.txt`；都由当前引擎生成。

```powershell
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real --packs GB
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real --params project_verified.json
uv run --project backend python scripts/check_case_library.py --write-evidence
```

本目录自带 `tools/check_case.py`，可整体携带；外部仍需同层级可查找的 `backend/` 和 `rules/`。
只读检查不写数据库。导入前先检查：

```powershell
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/xiasha-real --dry-run
```

实际导入去掉 `--dry-run`，会替换同名项目；不要对已有工程项目盲目运行。

网站追加脚本 `scripts/publish_demo_cases.py` 会保留 `project_notes`、`scheme_notes` 和评分排除项；已有旧案例参数不一致时仍拒绝覆盖。代码合并不会自动迁移服务器案例数据；应按发布流程选择新的教学项目或经人工核对后更新已有数据，再重新评估并生成报告。

## 验证说明

执行版本与程序行为断言见上级 `CASE_BRANCH.md`。排名由实算产生，不能承诺切换角色必然改变名次。
