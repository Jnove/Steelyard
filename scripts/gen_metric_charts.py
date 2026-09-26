"""为 ``docs/rules-guide.md`` 第 4 节生成 3 张分段线性折线示意图。

输出位置：``docs/img/`` 下三张 PNG。

设计要点
--------
- 中文标题与轴标签（用 matplotlib 内置中文字体或在缺字体时退到 ``Arial Unicode MS``）；
- 配色避开红绿色盲（用蓝 / 橙 / 灰）；
- 图例标记每个控制点（横轴值、纵轴分数）；
- 数据点来自指南里的 6 个 ``metric_*`` 示例，保持一致。

用法::

    uv run --project backend python scripts/gen_metric_charts.py
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 不弹窗，纯写文件
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "img"


@dataclass(frozen=True)
class ChartSpec:
    """一张图的所有要素：标题、坐标轴、points、控制点说明。"""

    filename: str
    title: str
    xlabel: str
    ylabel: str
    points: tuple[tuple[float, float], ...]
    caption: str  # 在 docs/rules-guide.md 里直接复用的图说


#: 与指南 6.4 节的三个 metric 示例一一对应。
CHARTS: tuple[ChartSpec, ...] = (
    ChartSpec(
        filename="metric_bigger_is_better.png",
        title="越大越好：标准层重复率",
        xlabel="标准层重复率（0–1）",
        ylabel="分数（0–100）",
        points=((0.50, 0), (0.80, 70), (0.95, 100)),
        caption="横轴=指标值，纵轴=分数。值越大分越高，分段点之间按线性插值。",
    ),
    ChartSpec(
        filename="metric_smaller_is_better.png",
        title="越小越好：单栋户数",
        xlabel="单栋户数（户/栋）",
        ylabel="分数（0–100）",
        points=((60, 100), (120, 70), (200, 0)),
        caption="横轴=指标值，纵轴=分数。值越小分越高，横轴按 x 升序、纵轴随之递减。",
    ),
    ChartSpec(
        filename="metric_optimal_in_middle.png",
        title="适中最好：主要房间南向比例",
        xlabel="南向比例（0–1）",
        ylabel="分数（0–100）",
        points=((0.20, 0), (0.55, 100), (0.90, 0)),
        caption="横轴=指标值，纵轴=分数。点先升后降就表达「适中最好」，峰值点是理想区间。",
    ),
)


def _setup_chinese_font() -> str | None:
    """尽量让 matplotlib 用上中文字体；找不到也不报错（fallback 到英文 / 拼音也接受）。"""
    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans CN",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "PingFang SC",
        "Hiragino Sans GB",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name
    return None


def _render_one(spec: ChartSpec) -> Path:
    xs = [p[0] for p in spec.points]
    ys = [p[1] for p in spec.points]

    fig, ax = plt.subplots(figsize=(6.5, 4.0), dpi=110)
    ax.plot(
        xs,
        ys,
        marker="o",
        markersize=9,
        linewidth=2.2,
        color="#1f77b4",
        markerfacecolor="#ff7f0e",
        markeredgecolor="#1f77b4",
        label="分段线性",
    )
    # 在每个控制点旁边标注坐标
    for x, y in spec.points:
        ax.annotate(
            f"({x:g}, {y:g})",
            xy=(x, y),
            xytext=(8, -14),
            textcoords="offset points",
            fontsize=9,
            color="#444444",
        )

    ax.set_title(spec.title, fontsize=14, pad=12)
    ax.set_xlabel(spec.xlabel, fontsize=11)
    ax.set_ylabel(spec.ylabel, fontsize=11)
    ax.set_xlim(min(xs) - 0.05 * (max(xs) - min(xs) + 1), max(xs) + 0.05 * (max(xs) - min(xs) + 1))
    ax.set_ylim(-5, 105)
    ax.grid(True, linestyle="--", linewidth=0.5, color="#cccccc")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="lower right", frameon=False)

    fig.tight_layout()
    out = OUT_DIR / spec.filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 docs/rules-guide 用折线示意图")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help=f"输出目录（默认 {OUT_DIR.relative_to(ROOT)}）",
    )
    args = parser.parse_args(argv)

    # Windows 控制台 GBK 兜底
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    args.out_dir.mkdir(parents=True, exist_ok=True)
    font = _setup_chinese_font()
    if font is None:
        sys.stderr.write(
            "WARN · 没找到中文字体（已尝试 Noto Sans CJK / 微软雅黑 / SimHei 等），"
            "图里的中文可能显示成方块。\n"
        )
    else:
        print(f"使用字体：{font}")

    for spec in CHARTS:
        path = args.out_dir / spec.filename
        _render_one(spec)
        print(f"  wrote {path}")

    print(f"OK · {len(CHARTS)} 张图已写到 {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
