# 钱塘区下沙公租房一期 · 对比案例

**2026-10-22 路演主案例**。本轮口径、关键参数的来源/计算方法与待签认人见 [参数核对表](parameter-review.md)。A/B/C 的参数与规则调整后已重新生成检查证据；不要使用旧截图或旧排名。

补证后默认和严格版均填入政府公示明确的**密度上限0.22**；容积率上限、规划限高和设防烈度仍缺。当前浙江册实算每套有 **4 条数据不足**，C-03按密度要求检查；三套均保留69m落地式脚手架的K-05提示，这些是教学施工基准。补设防后B仍缺`mic_precast_wall_shear_ratio`的结构计算依据。

重复施工指标G-02/G-03合并至K-01/K-02；本项目暂不计分G-05/Q-05/Q-06。已补政府公示的逐栋层数及住宅/配套总量，候选仍为自拟，户型三等分保持清空，单元与电梯服务户数仍缺。只能展示“已知条件下的评分与取舍”，不能认定全部合规或确定最优。

真实项目公开资料与待复核记录分开标注；方案数值为演示自拟，不是该项目的批准或建成方案。

公示背景为1114户、8栋（4号楼22层，其余7栋23层）；候选统一23层仍属教学简化，不能作为真实逐栋方案。

## 来源与边界

采用[钱塘区政府2022-09-02原始公示](https://www.qiantang.gov.cn/art/2022/9/2/art_1657687_58944568.html)的同阶段背景。公示图已于2026-10-22下载核读，图表摘录、哈希与补证边界见[sources](sources/README.md)。债券披露、2025调整转载和竣工报道转为历史版本记录，不与当前采用阶段混拼。

地上计容71615.60m²、住宅65081.71m²、配套6533.89m²、地下41247.51m²、基底5626.94m²均来自同一公示表。公示总面积112863.11m²不含另列架空677.20m²，不能重复相加。候选gfa与基底采用该背景，体积仍为教学推算。
G-05因多栋、裙房、架空与最大层数的面积口径未核定而继续暂不计分；不能将其作为更绿色的证据。图中容积率2.80、H=73.30m/h=70.20m只记设计值，不填规划上限。
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
