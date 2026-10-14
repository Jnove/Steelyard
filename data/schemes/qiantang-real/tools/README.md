# 前进公租房一期 · 本地对比案例（自带工具，与仓库其它内容相互独立）

本目录是**自包含**的：案例数据（项目 + 3 套方案 + 证据）与检查工具都在目录内，
拷走整个 `qiantang-real/` 目录即可独立使用，不需要仓库里的其它脚本。

```
qiantang-real/
├── README.md                案例说明：公开出处、真值/暂定值、设计取舍、待办
├── project.json             项目层参数（默认版：暂定值补齐，可直接跑）
├── project_verified.json    严格缺失版（三规划上限与项目设防烈度留空；面积来源记录待复核）
├── A_现浇剪力墙.json         方案 A（演示自拟）
├── B_MiC模块化.json          方案 B（演示自拟）
├── C_现浇基准.json           方案 C（演示自拟）
├── _check.txt               证据：默认参数下的实算结果
├── _check-verified.txt      证据：仅公开数据下的实算结果
├── _check-gb.txt            证据：只按国标（去掉浙江省册）的实算结果
└── tools/
    └── check_case.py        只读检查工具（硬约束 + 四维得分 + 帕累托 + 角色排名）
```

## 怎么用

**唯一的外部依赖是筑衡仓库的 `backend/` 与 `rules/`**（规则引擎与 YAML 规则），
本目录自身不修改它们。

```powershell
# 在本目录内（工具会自动向上找到 backend/）
uv run --project ..\..\..\backend python tools\check_case.py
uv run --project ..\..\..\backend python tools\check_case.py --params project_verified.json
uv run --project ..\..\..\backend python tools\check_case.py --packs GB

# 或者不指定 --case，工具默认就检查自己所在的案例目录
```

**把案例搬到别处**也能跑：只要保持「案例目录」与「仓库的 `backend/`」之间是
可向上查找的层级关系（例如 `<某处>/cases/qiantang-real/tools/` 与 `<某处>/backend/`），
`tools/check_case.py` 会自动定位后端，无需改代码或传路径。

## 独立性约定

1. **数据只在本目录**：项目层、方案层、证据文件都不依赖仓库里的 `data/schemes/mock/`
   或任何前端快照，改这里不会影响 T6 回归测试与前端离线演示。
2. **工具自带**：`tools/check_case.py` 是仓库 `scripts/check_demo_case.py` 的同一份
   脚本，复制进来是为了让案例可整包带走；两边保持同步（改一处要同步另一处）。
3. **只读**：本目录下的工具不写数据库、不调大模型、不改规则；所有 `_check*.txt` 都是
   它生成的产物。
4. **来源标注**：项目层字段逐条注明【公开】/【公开·推定】/【暂定】，方案层统一标注
   「演示自拟」。对外材料必须保留这个区分。

## 与仓库其它部分的关系

- **读**：`backend/app/engine/`（规则引擎、评分）、`rules/*.yaml`（规则与角色权重）。
- **不写**：不改 `rules/`、不改 `backend/`、不改 `data/schemes/mock/`、不改前端快照。
- **不影响**：`make test`、`make docs-check`、前端离线演示都不依赖本目录。

详细背景、公开出处与待核实项见案例 [README.md](../README.md)。
