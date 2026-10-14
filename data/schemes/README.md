# 演示数据一览（三条数据线）

本目录下有三套案例数据，**用途不同、来源性质不同，不要混用**：

| 目录 | 地块来源 | 方案来源 | 用途 | 能否对外当「真实项目」 |
| --- | --- | --- | --- | --- |
| [`mock/`](mock/README.md) | 虚构 | 虚构 | T6 回归测试、前端离线快照、`make seed` 默认样例 | 否 |
| [`demo-qiantang-fictional/`](demo-qiantang-fictional/README.md) | 虚构 | 虚构 | 需要 6 套方案 + 支配关系 + What-if 的完整演示 | 否 |
| [`qiantang-real/`](qiantang-real/README.md) | **真实**（钱塘区前进公租房一期，有公开出处） | 演示自拟 | 需要「真实项目」时用它；项目层来自政府公开信息 | 部分（项目层可，方案层不可） |

**选型一句话**：对外材料要「真实项目」就用 `qiantang-real/`（真实公租房地块，
项目层有公开出处）；要更完整的故事线和支配关系演示就用 `demo-qiantang-fictional/`。
两套可以一起用——主案例用真实地块，录视频时用虚构案例展示更多方案。`mock/` 被测试与
前端快照依赖，**不要改动**。

需要**多个真实项目横向对比**（同一个规则集换项目重跑）时，按
[演示案例候选清单](../../docs/demo-candidates.md) 再复制同结构的案例目录即可；
候选里全部是杭州的公租房项目。

## 通用命令

```bash
# 只读检查任意一个案例：硬约束 + 四维得分 + 帕累托 + 角色排名
uv run --project backend python scripts/check_demo_case.py --case data/schemes/qiantang-real
make case-check CASE=data/schemes/demo-qiantang-fictional

# 导入本地 Demo 库（会先删掉同名项目再写入）
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/qiantang-real
```

`check_demo_case.py` 不写数据库、不调模型；案例目录里的 `_check*.txt` 是它生成的
**证据文件**，不要手改。
