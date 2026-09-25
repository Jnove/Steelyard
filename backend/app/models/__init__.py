"""数据模型层：输入参数、评估结果、SQLModel 表。

子模块：
- params  ProjectParams / SchemeParams（Pydantic v2）
- eval    评估结果 Pydantic 模型（ComplianceItem / MetricResult / ...）
- orm     SQLModel 持久化表（Project / Scheme / EvalResultRow）
"""

from app.models.eval import (
    ComplianceItem,
    ComplianceStatus,
    DimensionKey,
    DimensionScores,
    EvalResult,
    MetricResult,
    RankResult,
)
from app.models.orm import EvalResultRow, Project, Scheme
from app.models.params import (
    CLIMATE_ZONES,
    GROUP_ORDER,
    RISK_FEATURE_OPTIONS,
    STRUCTURE_TYPES,
    ClimateZone,
    ProjectParams,
    SchemeParams,
    StructureType,
)

__all__ = [
    # 输入参数
    "CLIMATE_ZONES",
    "GROUP_ORDER",
    "RISK_FEATURE_OPTIONS",
    "STRUCTURE_TYPES",
    "ClimateZone",
    "ProjectParams",
    "SchemeParams",
    "StructureType",
    # 评估结果
    "ComplianceItem",
    "ComplianceStatus",
    "DimensionKey",
    "DimensionScores",
    "EvalResult",
    "MetricResult",
    "RankResult",
    # SQLModel 表
    "EvalResultRow",
    "Project",
    "Scheme",
]