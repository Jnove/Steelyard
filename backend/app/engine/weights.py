"""角色权重模板的加载与校验（``rules/weights.yaml``）。

为什么单独一个模块：:mod:`app.engine.mcdm` 按 T4 规格必须是纯函数（无 I/O、无副作用），
而读 YAML 是 I/O。所以"算"留在 mcdm，"读"放在这里，和 :mod:`app.engine.rules`
读规则文件是同一层的职责。

``weights.yaml`` 里每个角色给一个 4×4 两两比较矩阵（或直接给权重），
加载时用 :func:`app.engine.mcdm.ahp_weights` 解出权重并做一致性检验；
**CR ≥ 0.1 只警告不报错**——模板由专业组填，一致性差是需要他们回头改判断，
不该让整个服务起不来。``scripts/check_rules.py`` 会把同样的检查跑成 CI 的闸门。

分数写法：矩阵元素支持 ``1/3`` 这样的字符串。这不只是方便——写 ``0.33`` 会让
``a_ij × a_ji`` 差出 1e-2，直接顶穿 :data:`app.engine.mcdm.RECIPROCAL_TOLERANCE`
的互反检查，而分数是精确的。
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from fractions import Fraction
from math import isclose, isfinite
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.engine.mcdm import (
    CRITERION_ORDER,
    AhpResult,
    McdmInputError,
    ahp_weights,
    normalize_weights,
)

__all__ = [
    "ROLE_KEYS",
    "WEIGHTS_FILENAME",
    "RoleWeightTemplate",
    "WeightsLoadError",
    "WeightsProblem",
    "default_weights_path",
    "get_role_templates",
    "load_role_templates",
    "parse_matrix_entry",
    "reload_role_templates",
    "set_role_templates_for_testing",
]

#: ``rules/`` 下的角色权重模板文件名。
WEIGHTS_FILENAME = "weights.yaml"

#: 旧版本必须提供的四个角色；设计单位是可选的第五个角色。
ROLE_KEYS: tuple[str, ...] = ("government", "developer", "contractor", "resident")
OPTIONAL_ROLE_KEYS: tuple[str, ...] = ("design",)
ROLE_ALIASES = {"residents": "resident", "construction": "contractor"}


@dataclass(frozen=True)
class WeightsProblem:
    """加载 ``weights.yaml`` 时发现的一个问题。

    ``severity`` 为 ``"error"`` 时模板不可用；``"warning"`` 时模板仍可用
    （目前只有一致性 CR ≥ 0.1 属于警告）。``message`` 与 ``fix`` 都是中文，
    会原样出现在 ``check_rules`` 的输出里。
    """

    severity: str
    code: str
    role: str | None
    message: str
    fix: str


class WeightsLoadError(Exception):
    """``weights.yaml`` 里有 error 级问题，模板不可用。"""

    def __init__(self, problems: list[WeightsProblem]) -> None:
        self.problems = problems
        super().__init__(
            "角色权重模板加载失败：\n" + "\n".join(f"  - {p.message}（{p.fix}）" for p in problems)
        )


class RoleWeightTemplate(BaseModel):
    """一个角色的权重模板（已解出权重）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "角色权重模板",
            "description": "某个角色立场下四个维度的相对权重，以及它的一致性检验结果",
        }
    )

    key: str = Field(description="角色键，如 government")
    name: str = Field(description="角色中文名，如 政府 / 保障房平台")
    note: str = Field("", description="这个角色为什么这么排的说明，报告里可以直接引用")
    source: str = Field("", description="矩阵数值的出处；含 TODO 表示尚未核定")
    weights: list[float] = Field(description="四个维度的权重，和为 1，顺序同 CRITERION_ORDER")
    matrix: list[list[float]] | None = Field(
        None, description="两两比较矩阵；直接给 weights 的模板为 null"
    )
    ahp: AhpResult | None = Field(None, description="一致性检验结果；直接给 weights 的模板为 null")

    @property
    def needs_review(self) -> bool:
        """出处还挂着 TODO，或一致性没通过——两种都该提醒使用者。"""
        return "TODO" in self.source or (self.ahp is not None and not self.ahp.consistent)


def parse_matrix_entry(value: Any) -> float:
    """把矩阵元素解析成 float，支持 ``3``、``0.5`` 与 ``"1/3"`` 三种写法。

    Raises:
        ValueError: 解析不出数字，或分母为 0。

    示例：
        >>> parse_matrix_entry("1/3") == 1 / 3
        True
        >>> parse_matrix_entry(5)
        5.0
    """
    if isinstance(value, bool):
        raise ValueError(f"矩阵元素不能是 true / false，当前是 {value!r}")
    if isinstance(value, (int, float)):
        number = float(value)
        if not isfinite(number):
            raise ValueError("权重或矩阵元素必须是有限数，不能填 NaN 或无穷大")
        return number
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(Fraction(text))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"看不懂矩阵元素 {value!r}（可以写 3、0.5 或 1/3）") from exc
    raise ValueError(f"矩阵元素必须是数字或 1/3 这样的分数，当前是 {type(value).__name__}")


def default_weights_path() -> Path:
    """默认路径：仓库根下的 ``rules/weights.yaml``。

    ``app/engine/weights.py`` → parents: engine → app → backend → 仓库根。
    """
    return Path(__file__).resolve().parents[3] / "rules" / WEIGHTS_FILENAME


def _check_one_role(key: str, raw: Any) -> tuple[RoleWeightTemplate | None, list[WeightsProblem]]:
    """校验并解析一个角色。返回 ``(模板 或 None, 问题列表)``。"""
    problems: list[WeightsProblem] = []
    n = len(CRITERION_ORDER)

    if key not in (*ROLE_KEYS, *OPTIONAL_ROLE_KEYS):
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_UNKNOWN",
                role=key,
                message=f"未知角色 {key}",
                fix=f"角色名只能是 {' / '.join((*ROLE_KEYS, *OPTIONAL_ROLE_KEYS))}",
            )
        )

    if not isinstance(raw, dict):
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_NOT_OBJECT",
                role=key,
                message=f"角色 {key} 必须是一个对象",
                fix="在角色名下面缩进 2 空格写 name、matrix 等字段",
            )
        )
        return None, problems

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_MISSING_NAME",
                role=key,
                message=f"角色 {key} 缺少中文名 name",
                fix="补一行 `name: 政府 / 保障房平台` 这样的中文名，前端下拉框要显示它",
            )
        )

    unknown = set(raw) - {"name", "note", "source", "matrix", "weights"}
    if unknown:
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_UNKNOWN_FIELD",
                role=key,
                message=f"角色 {key} 里出现了无法识别的字段 {sorted(unknown)}",
                fix="每个角色只支持 name、note、source、matrix、weights 五个字段",
            )
        )

    has_matrix = raw.get("matrix") is not None
    has_weights = raw.get("weights") is not None
    if has_matrix and has_weights:
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_BOTH_SOURCES",
                role=key,
                message=f"角色 {key} 同时给了 matrix 和 weights",
                fix="二选一：用两两比较矩阵就写 matrix，权重是上级直接规定的就写 weights",
            )
        )
        return None, problems
    if not has_matrix and not has_weights:
        problems.append(
            WeightsProblem(
                severity="error",
                code="ROLE_NO_SOURCE",
                role=key,
                message=f"角色 {key} 既没有 matrix 也没有 weights",
                fix=f"补一个 {n}×{n} 的 matrix，或直接写 weights: [0.4, 0.2, 0.3, 0.1]",
            )
        )
        return None, problems

    if has_weights:
        template, weight_problems = _parse_direct_weights(key, name, raw, n)
        return template, problems + weight_problems

    template, matrix_problems = _parse_matrix(key, name, raw, n)
    return template, problems + matrix_problems


def _parse_direct_weights(
    key: str, name: Any, raw: dict[str, Any], n: int
) -> tuple[RoleWeightTemplate | None, list[WeightsProblem]]:
    """解析直接给出的 weights。"""
    problems: list[WeightsProblem] = []
    values = raw["weights"]
    if not isinstance(values, list) or len(values) != n:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_BAD_LENGTH",
                role=key,
                message=f"角色 {key} 的 weights 必须是 {n} 个数字",
                fix=f"按 {' / '.join(CRITERION_ORDER)} 的顺序写 {n} 个正数，引擎会自动归一化",
            )
        )
        return None, problems
    try:
        numbers = [parse_matrix_entry(v) for v in values]
    except ValueError as exc:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_NOT_NUMBER",
                role=key,
                message=f"角色 {key} 的 weights：{exc}",
                fix="只写数字，不要加引号或单位",
            )
        )
        return None, problems
    if any(v < 0 for v in numbers) or sum(numbers) <= 0:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_NOT_POSITIVE",
                role=key,
                message=f"角色 {key} 的 weights 必须是非负数且不能全为 0，当前是 {numbers}",
                fix="每个维度给一个正数；不关心某个维度可以给一个很小的数，但不要给 0 以下",
            )
        )
        return None, problems

    normalized = normalize_weights(numbers)
    return (
        RoleWeightTemplate(
            key=key,
            name=name if isinstance(name, str) else key,
            note=str(raw.get("note", "")),
            source=str(raw.get("source", "")),
            weights=normalized.tolist(),
            matrix=None,
            ahp=None,
        ),
        problems,
    )


def _parse_matrix(
    key: str, name: Any, raw: dict[str, Any], n: int
) -> tuple[RoleWeightTemplate | None, list[WeightsProblem]]:
    """解析两两比较矩阵并做一致性检验。"""
    problems: list[WeightsProblem] = []
    rows = raw["matrix"]

    if not isinstance(rows, list) or len(rows) != n:
        problems.append(
            WeightsProblem(
                severity="error",
                code="MATRIX_BAD_SHAPE",
                role=key,
                message=f"角色 {key} 的 matrix 必须是 {n} 行",
                fix=f"写成 {n} 行、每行 {n} 个数，顺序是 {' / '.join(CRITERION_ORDER)}",
            )
        )
        return None, problems

    parsed: list[list[float]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != n:
            problems.append(
                WeightsProblem(
                    severity="error",
                    code="MATRIX_BAD_SHAPE",
                    role=key,
                    message=f"角色 {key} 的 matrix 第 {i + 1} 行必须有 {n} 个数",
                    fix=f"每行写成 `- [1, 2, 4, 1]` 这样的 {n} 个数",
                )
            )
            return None, problems
        try:
            parsed.append([parse_matrix_entry(v) for v in row])
        except ValueError as exc:
            problems.append(
                WeightsProblem(
                    severity="error",
                    code="MATRIX_NOT_NUMBER",
                    role=key,
                    message=f"角色 {key} 的 matrix 第 {i + 1} 行：{exc}",
                    fix="分数写成 1/3（带引号也行），不要写 0.33——四舍五入会破坏互反检查",
                )
            )
            return None, problems

    try:
        result = ahp_weights(parsed)
    except McdmInputError as exc:
        problems.append(
            WeightsProblem(
                severity="error",
                code="MATRIX_INVALID",
                role=key,
                message=f"角色 {key} 的 matrix 不合法：{exc}",
                fix="对角线必须全是 1；如果 a[i][j] 写了 3，a[j][i] 必须写 1/3",
            )
        )
        return None, problems

    if not result.consistent:
        problems.append(
            WeightsProblem(
                severity="warning",
                code="MATRIX_INCONSISTENT",
                role=key,
                message=(
                    f"角色 {key} 的判断自相矛盾：一致性比率 CR = {result.cr:.3f}，"
                    f"超过了 {0.1:.1f} 的上限"
                ),
                fix=(
                    "回头检查有没有「A 比 B 重要 3 倍、B 比 C 重要 3 倍，但 A 比 C 只写了 2 倍」"
                    "这类矛盾。三者的倍数应当能大致相乘对上"
                ),
            )
        )

    return (
        RoleWeightTemplate(
            key=key,
            name=name if isinstance(name, str) else key,
            note=str(raw.get("note", "")),
            source=str(raw.get("source", "")),
            weights=result.weights,
            matrix=parsed,
            ahp=result,
        ),
        problems,
    )


def _role_configs(raw: dict[str, Any]) -> tuple[dict[str, Any], list[WeightsProblem]]:
    """兼容旧的角色顶层写法与专业组的 dimensions / roles / validation 写法。

    按字段名取四个评分权重，compliance 只保留为硬门槛；不依赖 YAML 键顺序。
    新格式的原始数值与出处保留在 YAML 内，不删除设计单位或伪造 AHP 矩阵。
    """
    problems: list[WeightsProblem] = []

    def error(code: str, message: str, fix: str) -> None:
        problems.append(WeightsProblem("error", code, None, message, fix))

    nested = "roles" in raw
    entries = raw
    source = ""
    expected_sum: float | None = None
    if nested:
        if set(raw) - {"dimensions", "roles", "validation"}:
            error(
                "WEIGHTS_UNKNOWN_SECTION",
                "权重文件含未知顶层字段",
                "只保留 dimensions、roles、validation",
            )
        dimensions = raw.get("dimensions")
        expected_dims = {"compliance", *CRITERION_ORDER}
        if not isinstance(dimensions, dict) or set(dimensions) != expected_dims:
            error(
                "WEIGHTS_DIMENSIONS",
                "维度必须包含 compliance 和四个评分维度",
                "按 rules/weights.yaml 的维度名填写",
            )
        entries = raw["roles"]
        if not isinstance(entries, dict):
            error("WEIGHTS_ROLES", "roles 必须是角色配置对象", "在 roles 下面按角色名缩进填写")
            return {}, problems
        validation = raw.get("validation", {})
        if not isinstance(validation, dict):
            error(
                "WEIGHTS_VALIDATION",
                "validation 必须是对象",
                "填写 weight_sum、compliance_behavior 和 source",
            )
            validation = {}
        if set(validation) - {"weight_sum", "compliance_behavior", "source"}:
            error(
                "WEIGHTS_VALIDATION",
                "validation 含未知字段",
                "只支持 weight_sum、compliance_behavior 和 source",
            )
        source = str(validation.get("source", ""))
        if "weight_sum" in validation:
            try:
                expected_sum = parse_matrix_entry(validation["weight_sum"])
                if expected_sum <= 0:
                    raise ValueError("合计须为正数")
            except ValueError as exc:
                error("WEIGHTS_SUM", f"weight_sum 无效：{exc}", "填写有限的正数，例如 1.0")
        behavior = validation.get("compliance_behavior")
        if behavior is not None and not isinstance(behavior, str):
            error(
                "WEIGHTS_VALIDATION",
                "compliance_behavior 必须是文字说明",
                "合规门槛与评分权重分别填写",
            )

    configs: dict[str, Any] = {}
    for supplied_key, config in entries.items():
        key = ROLE_ALIASES.get(str(supplied_key), str(supplied_key))
        if key in configs:
            error(
                "WEIGHTS_DUPLICATE_ROLE",
                f"角色 {key} 与其别名重复",
                "resident / residents 和 contractor / construction 各只保留一个",
            )
            continue
        if not nested or not isinstance(config, dict):
            configs[key] = config
            continue
        if set(config) - {"label", "rationale", "source", "weights"}:
            error(
                "ROLE_UNKNOWN_FIELD",
                f"角色 {key} 含未知字段",
                "新格式每个角色只支持 label、rationale、source、weights",
            )
        weights = config.get("weights")
        if not isinstance(weights, dict) or set(weights) != {"compliance", *CRITERION_ORDER}:
            error(
                "WEIGHTS_DIMENSIONS",
                f"角色 {key} 必须按名称提供五个维度权重",
                "填写 compliance、quality、structure、construction、green",
            )
            continue
        try:
            numbers = {dimension: parse_matrix_entry(value) for dimension, value in weights.items()}
        except ValueError as exc:
            error("WEIGHTS_NOT_NUMBER", f"角色 {key}：{exc}", "权重须为有限的非负数字")
            continue
        if any(value < 0 for value in numbers.values()):
            error("WEIGHTS_NOT_POSITIVE", f"角色 {key} 含负权重", "每个维度权重须为非负数")
        if expected_sum is not None and not isclose(
            sum(numbers.values()), expected_sum, abs_tol=1e-6
        ):
            error(
                "WEIGHTS_SUM",
                f"角色 {key} 的五项权重合计与 weight_sum 不符",
                "核对原始权重，合计须与 validation.weight_sum 一致",
            )
        configs[key] = {
            "name": config.get("label"),
            "note": config.get("rationale", ""),
            "source": f"{config.get('source', source)}；compliance 原始权重 {numbers['compliance']:g}，作为独立硬门槛，不计入评分",
            "weights": [numbers[dimension] for dimension in CRITERION_ORDER],
        }
    return configs, problems


def check_weights_file(path: Path) -> tuple[dict[str, RoleWeightTemplate], list[WeightsProblem]]:
    """校验 ``weights.yaml``，返回 ``(可用的模板, 问题列表)``。

    **不抛异常**——这是给 ``check_rules`` 用的入口，它要把所有问题一次列全。
    需要"失败就抛"的语义请用 :func:`load_role_templates`。
    """
    problems: list[WeightsProblem] = []

    if not path.is_file():
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_FILE_MISSING",
                role=None,
                message=f"找不到角色权重模板 {path.name}",
                fix=f"在 rules/ 下创建 {WEIGHTS_FILENAME}，格式见文件顶部注释",
            )
        )
        return {}, problems

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_YAML_PARSE",
                role=None,
                message=f"{path.name} YAML 解析失败：{str(exc).splitlines()[0]}",
                fix="检查缩进用的是不是 2 个空格、冒号是不是英文半角",
            )
        )
        return {}, problems

    if raw is None:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_EMPTY",
                role=None,
                message=f"{path.name} 是空的",
                fix=f"至少要有 {' / '.join(ROLE_KEYS)} 四个角色",
            )
        )
        return {}, problems

    if not isinstance(raw, dict):
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_NOT_MAPPING",
                role=None,
                message=f"{path.name} 顶层必须是「角色名: 配置」的形式，不是列表",
                fix="顶层不要用 `- ` 开头；每个角色顶头写 `government:` 这样的键",
            )
        )
        return {}, problems

    configs, config_problems = _role_configs(raw)
    problems.extend(config_problems)
    templates: dict[str, RoleWeightTemplate] = {}
    for key in (
        *ROLE_KEYS,
        *OPTIONAL_ROLE_KEYS,
        *(key for key in configs if key not in (*ROLE_KEYS, *OPTIONAL_ROLE_KEYS)),
    ):
        if key not in configs:
            continue
        value = configs[key]
        template, role_problems = _check_one_role(str(key), value)
        problems.extend(role_problems)
        if template is not None:
            templates[str(key)] = template

    missing = [key for key in ROLE_KEYS if key not in configs]
    if missing:
        problems.append(
            WeightsProblem(
                severity="error",
                code="WEIGHTS_MISSING_ROLE",
                role=None,
                message=f"{path.name} 缺少角色 {missing}",
                fix=f"四个角色都要有：{' / '.join(ROLE_KEYS)}（前端下拉框按这个顺序展示）",
            )
        )

    return templates, problems


def load_role_templates(path: Path | None = None) -> dict[str, RoleWeightTemplate]:
    """加载角色权重模板。

    Raises:
        WeightsLoadError: 存在 error 级问题。一致性不合格（CR ≥ 0.1）只是警告，
            不会抛异常——模板仍然可用，由 ``check_rules`` 在 CI 里提醒专业组改。
    """
    templates, problems = check_weights_file(path or default_weights_path())
    errors = [p for p in problems if p.severity == "error"]
    if errors:
        raise WeightsLoadError(errors)
    for problem in problems:
        if problem.severity == "warning":
            warnings.warn(problem.message, UserWarning, stacklevel=2)
    return templates


# —— 全局模板（启动时加载一次，开发环境可热重载） —— #

_TEMPLATES: dict[str, RoleWeightTemplate] | None = None


def get_role_templates() -> dict[str, RoleWeightTemplate]:
    """取全局角色模板；首次调用时从默认路径加载。"""
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load_role_templates()
    return _TEMPLATES


def reload_role_templates(path: Path | None = None) -> dict[str, RoleWeightTemplate]:
    """重新加载角色模板。失败时保留原有模板；当前由代码调用，不接入规则重载接口。"""
    global _TEMPLATES
    fresh = load_role_templates(path)
    _TEMPLATES = fresh
    return fresh


def set_role_templates_for_testing(templates: dict[str, RoleWeightTemplate] | None) -> None:
    """测试用：注入（或用 ``None`` 清空）全局角色模板。"""
    global _TEMPLATES
    _TEMPLATES = templates
