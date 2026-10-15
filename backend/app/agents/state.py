"""智能体请求、图状态与调试事件；所有专业数值来自工具。"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.rank import RankRequest

Intent = Literal["new_eval", "whatif", "explain", "reweight"]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=30000)


class SchemeChange(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scheme_id: int = Field(gt=0)
    field: str
    value: Any


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    message: str = Field("生成方案比选报告", max_length=30000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=50)
    intent: Intent | None = None
    role: str | None = None
    weights: list[float] | None = None
    include_whatif: bool = False
    change: SchemeChange | None = None
    rule_id: str | None = None
    scheme_id: int | None = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_weights(self) -> AgentRequest:
        if self.role is not None or self.weights is not None:
            RankRequest(role=self.role, weights=self.weights)
        return self

    def rank_request(self, include_whatif: bool | None = None) -> RankRequest:
        # 未指定立场时明确使用等权演示，并在报告数据里保留来源。
        return RankRequest(
            role=self.role,
            weights=self.weights if self.role else (self.weights or [0.25] * 4),
            include_whatif=self.include_whatif if include_whatif is None else include_whatif,
        )


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    change: SchemeChange | None = None
    role: str | None = None
    weights: list[float] | None = None
    rule_id: str | None = None


class NodeTrace(BaseModel):
    node: str
    elapsed_ms: float
    tool_calls: list[str] = Field(default_factory=list)


class NumberIssue(BaseModel):
    text: str
    start: int
    end: int


class GraphState(BaseModel):
    project_id: int
    request: AgentRequest
    plan: Plan | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    baseline: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    comments: Annotated[list[dict[str, str]], operator.add] = Field(default_factory=list)
    traces: Annotated[list[NodeTrace], operator.add] = Field(default_factory=list)
    report: str = ""
    attempt: int = 0
    unverified_numbers: list[NumberIssue] = Field(default_factory=list)


class AgentOutput(BaseModel):
    report: str
    intent: Intent
    unverified_numbers: list[NumberIssue] = Field(default_factory=list)
    traces: list[NodeTrace] = Field(default_factory=list)
    cached: bool = False
