"""评估结果的数据模型。

字段对应 AGENTS.md "数据模型"一节给出的结果 JSON 示例，每项都带出处。
派生量（如 closeness）由引擎计算，不在此模型中重新声明。

T3 扩展：规则引擎需要表达"这条规则不适用"和"数据不够判不了"两种状态，
因此在 T2 的基础上加了 ``not_applicable`` 状态、可空的 ``score``、
``missing_fields``（缺哪些字段）与维度 ``coverage``（有数据的权重占比）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DimensionKey = Literal["quality", "structure", "construction", "green"]
"""评估维度（居住品质 / 结构 / 施工 / 绿色）。"""


ComplianceStatus = Literal["passed", "failed", "insufficient_data", "not_applicable"]
"""合规判定状态。

- ``passed`` 通过；
- ``failed`` 不通过；
- ``insufficient_data`` 规则用到的字段没填，无法判定；
- ``not_applicable`` 规则的 ``when`` 条件不成立，本方案不适用该规则。
"""


MetricStatus = Literal["scored", "insufficient_data", "not_applicable"]
"""评分指标状态。只有 ``scored`` 才有分数，其余两种 ``score`` 为 null。"""


Severity = Literal["error", "warning"]
"""硬约束的严重程度：``error`` 标红并踢出排名，``warning`` 仅提示。"""


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
    severity: Severity = Field("error", description="严重程度，来自规则的 severity 字段")
    value: float | None = Field(None, description="实际取值；只有能从 check 里认出被比较字段时才有")
    limit: str | None = Field(None, description="规则要求的限值，例如 '>= 3.0'")
    formula: str = Field("", description="判定所用的 check 表达式，供报告溯源")
    source: str | None = Field(None, description="规范条文出处")
    missing_fields: list[str] = Field(
        default_factory=list,
        description="status 为 insufficient_data 时，缺少的原始字段名",
    )
    message: str = Field(description="人类可读的判定说明")


class MetricResult(BaseModel):
    """单个评分指标的输出值与得分。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "评分指标",
            "description": "单条 metric 规则的计算值、得分、所在维度与公式出处",
        }
    )

    rule_id: str = Field(description="规则 ID，例如 K-01")
    name: str = Field(description="指标中文名")
    status: MetricStatus = Field("scored", description="指标状态")
    value: float | None = Field(None, description="计算得到的指标值")
    score: float | None = Field(
        None, ge=0, le=100, description="该指标 0-100 的得分；数据不足或不适用时为 null"
    )
    dimension: DimensionKey = Field(description="所属评估维度")
    weight_in_dimension: float = Field(1.0, gt=0, description="同维度内的相对权重")
    formula: str = Field(description="评分公式或说明")
    source: str = Field(description="规则来源（专业组 / 规范）")
    missing_fields: list[str] = Field(
        default_factory=list,
        description="status 为 insufficient_data 时，缺少的原始字段名",
    )


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


class DimensionCoverage(BaseModel):
    """四维度的数据覆盖率：有分数的指标权重占适用指标总权重的比例，0–1 小数。

    覆盖率低说明这个维度的得分只建立在少数指标上，报告里要提示"结论证据不足"。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "title": "维度覆盖率",
            "description": "各维度内有数据的指标权重占比，0–1 小数",
        }
    )

    quality: float = Field(0.0, ge=0, le=1, description="居住品质")
    structure: float = Field(0.0, ge=0, le=1, description="结构安全")
    construction: float = Field(0.0, ge=0, le=1, description="施工友好")
    green: float = Field(0.0, ge=0, le=1, description="绿色低碳")


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

    scheme_id: str = Field(description="方案标识，对应 schemes 表里的 id")
    scheme_name: str = Field("", description="方案名称，报告与看板展示用")
    compliance: list[ComplianceItem] = Field(
        default_factory=list, description="合规判定清单"
    )
    metrics: dict[str, MetricResult] = Field(
        default_factory=dict, description="键为指标 ID，values 为指标结果"
    )
    dimension_scores: DimensionScores = Field(
        default_factory=DimensionScores, description="四维度加权得分"
    )
    dimension_coverage: DimensionCoverage = Field(
        default_factory=DimensionCoverage, description="四维度数据覆盖率，0–1 小数"
    )
    topsis: RankResult | None = Field(
        None, description="TOPSIS 排序结果；尚未参与排序时为 null"
    )

    @property
    def has_blocking_failure(self) -> bool:
        """是否存在 severity=error 的不通过项（默认不参与排名）。"""
        return any(
            item.status == "failed" and item.severity == "error" for item in self.compliance
        )
