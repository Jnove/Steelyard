# 虚构地块 · 合规边界与施工提示 · 对比案例

虚构数据，仅用于程序行为演示，不能作为工程结论。

基准、限高超限、容积率超限、施工专家论证提示及单参数What-if恢复。

## 来源与边界

全部字段为虚构数据，无真实工程来源。

地上/地下建筑面积分开记录，评分输入 `gfa` 使用演示地上面积。公开规模不是规划条件上限，未取得的条件不补造。
新增方案的总基底按等高体量假设 `gfa / floors` 计算，不复制旧案例的基底异常值；没有修改 G-05 或任何专业规则。
严格版是本次已核验字段的子集，数据不足不等于合规通过，也不保证可以给出有效推荐。

## 文件与运行

项目参数在 `project.json`；A/B/C 是三个结构路线的演示方案。边界案例另有 D/E/F 和 `whatif.json`。
检查证据是 `_check.txt`、`_check-gb.txt`，真实地块另有 `_check-verified.txt`；都由当前引擎生成。

```powershell
uv run --project backend python scripts/check_demo_case.py --case data/schemes/demo-boundaries-fictional
uv run --project backend python scripts/check_demo_case.py --case data/schemes/demo-boundaries-fictional --packs GB
```

本目录自带 `tools/check_case.py`，可整体携带；外部仍需同层级可查找的 `backend/` 和 `rules/`。
只读检查不写数据库。导入前先检查：

```powershell
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/demo-boundaries-fictional --dry-run
```

实际导入去掉 `--dry-run`，会替换同名项目；不要对已有工程项目盲目运行。

## 验证说明

执行版本与程序行为断言见上级 `CASE_BRANCH.md`。排名由实算产生，不能承诺切换角色必然改变名次。
