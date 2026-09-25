"""确定性引擎：规则加载、指标计算、评分、决策算法。

子模块按 AGENTS.md 约定：
- rules.py    YAML 规则加载、校验、判定
- metrics.py  指标计算
- scoring.py  评分（分段线性等）
- mcdm.py     AHP / TOPSIS / 敏感性 / 帕累托
"""