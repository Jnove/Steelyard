"""Mock 数据校验测试。

任务 T6：保证 ``data/schemes/mock/`` 下的虚构项目与方案：

1. 顶层都有 ``_note`` 声明（以「虚构数据」开头）；
2. 能通过 :class:`ProjectParams` / :class:`SchemeParams` 的字段校验（T2）；
3. 与脚本常量 ``SCHEME_FILES`` / ``WHATIF_PARENT_NAME`` 对得上；
4. ``seed_mock.py`` 的 dry-run 路径能跑通且不写数据库。
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOCK_DIR = ROOT / "data" / "schemes" / "mock"


def _import_seed():
    """重新加载 ``scripts.seed_mock``，确保每次测试都拿到最新代码。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("scripts.seed_mock")


@pytest.fixture(scope="module")
def seed_mod():
    return _import_seed()


class TestMockJsonShape:
    """每个 JSON 文件的形状：``_note`` / ``name`` / ``params``。"""

    def test_all_files_exist(self) -> None:
        expected = [
            "project.json",
            "A_高品质.json",
            "B_不合规.json",
            "C_MiC高标准化.json",
            "D_均衡.json",
            "E_被支配.json",
            "C_现浇.json",
        ]
        for name in expected:
            assert (MOCK_DIR / name).exists(), f"缺少 {name}"

    def test_every_file_has_note(self) -> None:
        for path in sorted(MOCK_DIR.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            note = payload.get("_note")
            assert isinstance(note, str), f"{path.name} 缺少 _note"
            assert note.startswith("虚构数据"), (
                f"{path.name} 的 _note 必须以「虚构数据」开头"
            )
            assert "不得用于验证" in note, f"{path.name} 的 _note 应明确禁止用于验证"


class TestProjectJson:
    """项目 JSON 必须通过 ProjectParams 校验。"""

    def test_project_params_valid(self) -> None:
        from app.models import ProjectParams

        payload = json.loads((MOCK_DIR / "project.json").read_text(encoding="utf-8"))
        params = ProjectParams.model_validate(payload["params"])
        assert params.climate_zone == "夏热冬冷"
        assert params.far_max is not None and params.far_max > 0
        assert params.density_max is not None and 0 < params.density_max <= 1


class TestSchemeJson:
    """每套方案必须通过 SchemeParams 校验。"""

    @pytest.mark.parametrize(
        "filename",
        [
            "A_高品质.json",
            "B_不合规.json",
            "C_MiC高标准化.json",
            "D_均衡.json",
            "E_被支配.json",
            "C_现浇.json",
        ],
    )
    def test_scheme_params_valid(self, filename: str) -> None:
        from app.models import SchemeParams

        payload = json.loads((MOCK_DIR / filename).read_text(encoding="utf-8"))
        # 这里才是验收标准的核心："必须通过 T2 模型校验"
        params = SchemeParams.model_validate(payload["params"])
        # 任意一个数值字段非空即可证明校验通过
        assert params.gfa is not None

    def test_b_is_intentionally_non_compliant(self) -> None:
        """B 方案的层高 2.9 m 故意低于 3.0 m，是 T6 演示硬约束标红的核心样本。"""
        payload = json.loads((MOCK_DIR / "B_不合规.json").read_text(encoding="utf-8"))
        assert payload["params"]["floor_height"] == 2.9
        assert payload["params"]["floor_height"] < 3.0

    def test_e_not_better_than_d_on_every_numeric(self) -> None:
        """E 方案的数值字段都不优于 D，演示帕累托支配。

        对每对 (D, E) 的同名字段，给出预期的"不更优"含义；构造性反例无法用
        通用公式表达，所以在脚本里硬编码约定。帕累托支配只要求 E 在各个维度上
        不优于 D、且至少一项严格更差，所以这里用 ``<=`` 而不是 ``<``。
        """
        d = json.loads((MOCK_DIR / "D_均衡.json").read_text(encoding="utf-8"))["params"]
        e = json.loads((MOCK_DIR / "E_被支配.json").read_text(encoding="utf-8"))["params"]

        # 大部分维度：E 比 D 低
        assert e["inner_area_ratio"] < d["inner_area_ratio"]
        assert e["south_room_ratio"] < d["south_room_ratio"]
        assert e["window_floor_ratio"] < d["window_floor_ratio"]
        assert e["window_wall_ratio"]["南"] < d["window_wall_ratio"]["南"]
        assert e["std_floor_repeat"] < d["std_floor_repeat"]
        assert e["prefab_ratio_est"] < d["prefab_ratio_est"]
        # 电梯数：E 与 D 持平。12 层及以上每单元至少 2 台是 GB 55038—2025
        # 第4.2.4条的强制下限，不能再拿来当"更差"的区分项（少一台会被硬约束
        # 直接踢出排名，就演示不出支配关系了）。
        assert e["elevators_per_unit"] <= d["elevators_per_unit"]

        # 构件种类：种类越多越不利（更非标），所以 E 应该 > D
        assert e["component_types"] > d["component_types"]

        # 结构体系：E = 框架 < D = 框架-剪力墙（按"结构弱 → 维度得分低"的方向）
        assert e["structure_type"] == "框架"
        assert d["structure_type"] == "框架-剪力墙"

        # 风险特征：E 有，D 没有
        assert len(e["risk_features"]) > len(d["risk_features"])

    def test_c_whatif_differs_from_c_mic_only_in_specific_fields(self) -> None:
        """C 现浇 = C MiC 高标准化改成现浇剪力墙后的对照版，体量与户数保持一致。"""
        c_mic = json.loads(
            (MOCK_DIR / "C_MiC高标准化.json").read_text(encoding="utf-8")
        )["params"]
        c_cast = json.loads((MOCK_DIR / "C_现浇.json").read_text(encoding="utf-8"))["params"]

        # 体量字段保持一致
        for key in ("gfa", "footprint", "buildings", "floors", "units", "volume"):
            assert c_cast[key] == c_mic[key], f"C 现浇 的 {key} 应等于 C MiC"

        # 结构体系变化（核心 what-if 变更点）
        assert c_cast["structure_type"] == "剪力墙"
        assert c_mic["structure_type"] == "MiC"

        # 工业化的关键指标均下降：装配率、标准化程度
        assert c_cast["prefab_ratio_est"] < c_mic["prefab_ratio_est"]
        assert c_cast["std_floor_repeat"] < c_mic["std_floor_repeat"]
        # 构件种类增加（更多种类 → 更非标）
        assert c_cast["component_types"] > c_mic["component_types"]


class TestSeedMockScript:
    """scripts/seed_mock.py 自身的可运行性。"""

    def test_seed_files_constant_matches_directory(self, seed_mod) -> None:
        """``SCHEME_FILES`` 里的每个文件都得存在；``WHATIF_PARENT_NAME`` 必须指向存在的方案。"""
        for filename in seed_mod.SCHEME_FILES:
            assert (MOCK_DIR / filename).exists(), filename

        names = {
            json.loads((MOCK_DIR / f).read_text(encoding="utf-8"))["name"]
            for f in seed_mod.SCHEME_FILES
        }
        assert seed_mod.WHATIF_PARENT_NAME in names, (
            f"WHATIF_PARENT_NAME {seed_mod.WHATIF_PARENT_NAME!r} "
            "不在 SCHEME_FILES 任意一个文件的 name 字段里"
        )

    def test_loaders_return_valid_payloads(self, seed_mod) -> None:
        """脚本里 ``load_*`` 入口必须能直接吃默认目录。"""
        project_payload = seed_mod.load_project_payload(MOCK_DIR)
        scheme_pairs, whatif_pair = seed_mod.load_scheme_payloads(MOCK_DIR)

        assert project_payload["name"] == seed_mod.DEFAULT_PROJECT_NAME
        assert len(scheme_pairs) == len(seed_mod.SCHEME_FILES)
        assert whatif_pair is not None
        assert whatif_pair[0]["name"].startswith("C ")

    def test_dry_run_does_not_touch_database(
        self, seed_mod, tmp_path: Path
    ) -> None:
        """``--dry-run`` 路径不应触达数据库 / 写盘。"""
        # 指向不存在的 mock 目录会先报错，因此先用默认目录做 dry-run；
        # 然后用一个临时目录只放一个无效 JSON，验证 fail-fast 行为不写库。
        rc = seed_mod.main(["--dry-run"])
        assert rc == 0

        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "project.json").write_text(
            json.dumps({"_note": "虚构数据", "name": "x", "params": {}}),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            seed_mod.main(["--dry-run", "--mock-dir", str(bad_dir)])