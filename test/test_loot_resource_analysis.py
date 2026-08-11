import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ITEM_RESOURCE_TOOL = ROOT / "tool" / "item_resource"
sys.path.insert(0, str(ITEM_RESOURCE_TOOL))

from analyze_failed_loot_images import (  # noqa: E402
    Candidate,
    MatchScore,
    confidence_for,
    drop_status_for,
    parse_failed_count,
)
from compare_loot_resources import build_missing_rows, build_same_rows  # noqa: E402
from item_resource_common import read_loot_blacklist  # noqa: E402


def make_candidate(*, in_formal_resources=False, blacklisted=False):
    return Candidate(
        name="龙渊钥匙",
        category="关卡门票",
        path=Path("龙渊钥匙.png"),
        feature_indices=np.array([0], dtype=np.int64),
        feature_colors=np.zeros((1, 3), dtype=np.uint8),
        in_formal_resources=in_formal_resources,
        blacklisted=blacklisted,
    )


def make_score(*, exact_ratio, exact_pixels, candidate=None):
    return MatchScore(
        candidate=candidate or make_candidate(),
        exact_ratio=exact_ratio,
        near_ratio=exact_ratio,
        mean_color_error=0.0,
        exact_pixels=exact_pixels,
        feature_pixels=100,
        mismatch_locality=0.0,
    )


class LootResourceAnalysisTests(unittest.TestCase):
    def test_read_loot_blacklist_accepts_utf8_bom_and_skips_incomplete_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blacklist.csv"
            path.write_text(
                "类型,名称\n关卡门票,龙渊钥匙\n关卡门票,\n,空名称\n",
                encoding="utf-8-sig",
            )

            self.assertEqual(read_loot_blacklist(path), {("关卡门票", "龙渊钥匙")})
            self.assertEqual(read_loot_blacklist(path.with_name("missing.csv")), set())

    def test_compare_rows_mark_blacklisted_items(self):
        latest_root = Path("latest")
        loot_root = Path("formal")
        latest_files = {"龙渊钥匙": latest_root / "关卡门票" / "龙渊钥匙.png"}
        loot_files = {"龙渊钥匙": loot_root / "关卡门票" / "龙渊钥匙.png"}
        blacklist = {("关卡门票", "龙渊钥匙")}

        same_rows = build_same_rows(latest_root, loot_root, latest_files, loot_files, blacklist)
        self.assertEqual(same_rows[0]["该物品是否被黑名单忽略"], "是")

        missing_rows = build_missing_rows(latest_root, latest_files, {}, blacklist)
        self.assertEqual(missing_rows[0]["该物品是否被黑名单忽略"], "是")

    def test_parse_failed_count_supports_faa_and_manual_names(self):
        self.assertEqual(parse_failed_count(Path("unknown_12_34.png")), 34)
        self.assertEqual(parse_failed_count(Path("人工保存.png")), 1)

    def test_confidence_uses_best_score_and_runner_up_gap(self):
        self.assertEqual(
            confidence_for(make_score(exact_ratio=0.99, exact_pixels=90), make_score(exact_ratio=0.90, exact_pixels=90)),
            "完美符合",
        )
        self.assertEqual(
            confidence_for(make_score(exact_ratio=0.85, exact_pixels=80), make_score(exact_ratio=0.70, exact_pixels=80)),
            "基本符合",
        )
        self.assertEqual(
            confidence_for(make_score(exact_ratio=0.50, exact_pixels=30), make_score(exact_ratio=0.48, exact_pixels=30)),
            "完全不置信",
        )

    def test_drop_status_distinguishes_blacklist_conflict_and_new_template(self):
        blacklisted = make_candidate(blacklisted=True)
        self.assertIn("黑名单冲突", drop_status_for(blacklisted, "完美符合"))

        new_template = make_candidate()
        self.assertIn("建议补入正式识别库", drop_status_for(new_template, "完美符合"))


if __name__ == "__main__":
    unittest.main()
