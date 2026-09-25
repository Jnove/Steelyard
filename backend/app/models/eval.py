"""评估结果的数据模型。

字段对应 AGENTS.md "数据模型"一节给出的结果 JSON 示例，每项都带出处。
派生量（如 closeness）由引擎计算，不在此模型中重新声明。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DimensionKey = Literal["quality", "structure", "construction", "green"]
"""评估维度（居住品质 / 结构 / 施工 / 绿色）。"""


ComplianceStatus = Literal["passed", "failed", "insufficient_data"]
"""合规判定状态：passed 通过 / failed 不通过 / insufficient_data 数据不足无法判定。"""


class ComplianceItem(BaseModel):
    """单条合规检查结果。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "合规检查项",
            "description": "对应 rules/*.yaml 中一条规则的判定结果",
        }
    )

    rule_id: str = Field(description="规则 ID，例如 C-03")
    name: str = Field(description="规则中文名")
    status: ComplianceStatus = Field(description="判定结果")
    value: float | None = Field(None, description="实际取值")
    limit: str | None = Field(None, description="规则要求的限值，例如 '>= 3.0'")
    source: str | None = Field(None, description="规范条文出处")
    message: str = Field(description="人类可读的判定说明")


class MetricResult(BaseModel):
    """单个评分指标的输出值与得分。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "评分指标",
            "description": "单条 metric 规则的计算值、得分、所在维度与公式出处",
        }
    )

    value: float | None = Field(None, description="计算得到的指标值")
    score: float = Field(description="该指标 0-100 的得分")
    dimension: DimensionKey = Field(description="所属评估维度")
    formula: str = Field(description="评分公式或说明")
    source: str = Field(description="规则来源（专业组 / 规范）")


class DimensionScores(BaseModel):
    """四维度加权得分。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "维度得分",
            "description": "quality / structure / construction / green 四个维度 0-100 的加权得分",
        }
    )

    quality: float = Field(0.0, ge=0, le=100, description="居住品质")
    structure: float = Field(0.0, ge=0, le=100, description="结构安全")
    construction: float = Field(0.0, ge=0, le=100, description="施工友好")
    green: float = Field(0.0, ge=0, le=100, description="绿色低碳")


class RankResult(BaseModel):
    """TOPSIS / AHP 排序结果。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "排序结果",
            "description": "TOPSIS 贴近度与排名",
        }
    )

    closeness: float = Field(description="TOPSIS 贴近度，0-1")
    rank: int = Field(description="在所有参与排序方案中的排名，从 1 开始")


class EvalResult(BaseModel):
    """单个方案的完整评估结果。

    字段顺序与 AGENTS.md 的结果 JSON 示例保持一致，便于前端按既有约定渲染。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "title": "方案评估结果",
            "description": "合规清单 + 指标值 + 维度得分 + 排名，一并交给报告生成器",
        }
    )

    scheme_id: str = Field(description="方案标识，对应 schemes 表里的 id 或 Name")
    compliance: list[ComplianceItem] = Field(
        default_factory=list, description="合规判定清单"
    )
    metrics: dict[str, MetricResult] = Field(
        default_factory=dict, description="键为指标 ID，values 为指标结果"
    )
    dimension_scores: DimensionScores = Field(
        default_factory=DimensionScores, description="四维度加权得分"
    )
    topsis: RankResult | None = Field(
        None, description="TOPSIS 排序结果；尚未参与排序时为 null"
    )