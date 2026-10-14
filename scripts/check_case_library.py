"""只读检查案例库；可选保存证据，不写数据库或修改规则。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "schemes"
CHECKER = ROOT / "scripts" / "check_demo_case.py"
SLUGS = (
    "qiantang-real",
    "demo-qiantang-fictional",
    "xiasha-real",
    "linping-donghu-real",
    "demo-boundaries-fictional",
)


def verify(slug: str, mode: str, result: dict) -> None:
    """验证展示场景的关键行为，不指定任何方案的排名。"""
    rows = result["schemes"]
    assert len(rows) >= 3, f"{slug}: 至少需要三个方案"
    if slug == "xiasha-real" or (slug == "qiantang-real" and mode == "verified"):
        for row in rows:
            assert {"C-01", "C-02", "C-03"} <= set(row["insufficient_rules"]), row
    if slug == "linping-donghu-real" and mode == "verified":
        for row in rows:
            assert {"C-01", "C-02", "C-03"} <= set(row["insufficient_rules"]), row
    if slug == "demo-boundaries-fictional":
        by_name = {row["name"].split(" ")[0]: row for row in rows}
        assert "C-01" in by_name["D"]["blocking_rules"], by_name["D"]
        assert "C-02" in by_name["E"]["blocking_rules"], by_name["E"]
        assert {"K-03", "K-04"} <= set(by_name["F"]["warning_rules"]), by_name["F"]
        assert not by_name["F"]["blocking_rules"], by_name["F"]
        assert not by_name["D改"]["blocking_rules"], by_name["D改"]
        assert len(rows) == 7, len(rows)
    # 新案例采用等高体量假设，G-05 不能再出现大于1的异常值。
    if slug in SLUGS[2:]:
        for row in rows:
            metric = row["metrics"].get("G-05")
            assert metric and metric["status"] == "scored", (slug, row)
            assert abs(metric["value"] - 1.0) < 1e-5, (slug, row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-evidence", action="store_true", help="保存引擎生成的文本证据")
    args = parser.parse_args()
    count = 0
    with tempfile.TemporaryDirectory(prefix="zhuheng-cases-") as temp:
        for slug in SLUGS:
            case = CASES / slug
            modes = [("default", [], "_check.txt"), ("gb", ["--packs", "GB"], "_check-gb.txt")]
            if (case / "project_verified.json").exists():
                modes.append(("verified", ["--params", "project_verified.json"], "_check-verified.txt"))
            for mode, extra, evidence_name in modes:
                output = Path(temp) / f"{slug}-{mode}.json"
                cmd = [sys.executable, "-X", "utf8", str(CHECKER), "--case", str(case), "--json", str(output), *extra]
                run = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding="utf-8", check=True)
                result = json.loads(output.read_text(encoding="utf-8"))
                verify(slug, mode, result)
                if args.write_evidence:
                    # 统一显示相对目录，避免将机器私有路径写进证据。
                    text = run.stdout.replace(str(case), case.relative_to(ROOT).as_posix())
                    text = "\n".join(line for line in text.splitlines() if not line.startswith("完整结果已写入 ")).rstrip() + "\n"
                    (case / evidence_name).write_text(text, encoding="utf-8")
                count += 1
                print(f"PASS {slug} / {mode}: {len(result['schemes'])} schemes")
    print(f"All {count} case runs passed; database unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
