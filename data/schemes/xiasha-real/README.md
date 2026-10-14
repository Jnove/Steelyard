# 钱塘区下沙公租房一期 · 对比案例

真实项目公开资料与待复核记录分开标注；方案数值为演示自拟，不是该项目的批准或建成方案。

同区规模对照与缺规划条件的诚实提示。户数1114、23层、8栋参考2024年项目报道，仍按演示方案处理。

## 来源与边界

公开规模来源：[浙江专项债券披露](https://www.governbond.org.cn/uploadFiles/33/attachFiles/202505/388fa8b9-b364-4828-b9aa-0fdb2644e484.pdf)，PDF 第 43 页；本次读取日期 2026-10-14。公开规模见 `project.json` 的 `_public_facts`，逐字段状态见 `_field_status`。

地上/地下建筑面积分开记录，评分输入 `gfa` 使用演示地上面积。公开规模不是规划条件上限，未取得的条件不补造。
新增方案的总基底按等高体量假设 `gfa / floors` 计算，不复制旧案例的基底异常值；没有修改 G-05 或任何专业规则。
严格版是本次已核验字段的子集，数据不足不等于合规通过，也不保证可以给出有效推荐。

## 文件与运行

项目参数在 `project.json`；A/B/C 是三个结构路线的演示方案。边界案例另有 D/E/F 和 `whatif.json`。
检查证据是 `_check.txt`、`_check-gb.txt`，真实地块另有 `_check-verified.txt`；都由当前引擎生成。

```powershell
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real --packs GB
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real --params project_verified.json
```

本目录自带 `tools/check_case.py`，可整体携带；外部仍需同层级可查找的 `backend/` 和 `rules/`。
只读检查不写数据库。导入前先检查：

```powershell
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/xiasha-real --dry-run
```

实际导入去掉 `--dry-run`，会替换同名项目；不要对已有工程项目盲目运行。

## 验证说明

执行版本与程序行为断言见上级 `CASE_BRANCH.md`。排名由实算产生，不能承诺切换角色必然改变名次。
