"""在隔离目录验证战利品人工名单、资源更新和精确清理，不联网。"""

import ast
import contextlib
import csv
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from function.common.loot_policy import read_drop_list
from tool.image_resource_pipeline.loot.classification import ItemResource
from tool.image_resource_pipeline.common.files import write_csv
from tool.image_resource_pipeline.loot.sync import sort_loot_list
from tool.image_resource_pipeline.loot.workflow import run_pipeline, whitelist_suggestions


ROOT = Path(__file__).resolve().parents[1]


def png(path, seed=1, size=(44, 44)):
    """构造具有足够独立特征的稳定 PNG 测试夹具。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.random.default_rng(seed).integers(0, 256, (size[1], size[0], 4), dtype=np.uint8)
    data[:, :, 3] = 255
    Image.fromarray(data).save(str(path))


class LootResourceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.args = SimpleNamespace(
            whitelist=self.root / "white.csv", blacklist=self.root / "black.csv",
            unclassified=self.root / "unknown.csv", output=self.root / "candidates",
            loot_root=self.root / "formal", failed_root=self.root / "failed",
            loot_mask=self.root / "mask.png", report_dir=self.root / "reports",
            dry_run=False, offline=False, force=False, timeout=1, downloader="auto", sleep=0, manifest=None,
        )
        self.items = []
        self.set_lists({("道具", "白")}, {("道具", "黑")})

    def set_lists(self, white, black):
        for path, entries in ((self.args.whitelist, white), (self.args.blacklist, black)):
            write_csv(path, [{"类型": category, "名称": name} for category, name in entries], ["类型", "名称"])

    def run_sync(self, fetch=None):
        def local_fetch(item, directory, *_args):
            png(directory / item.item_type / item.filename, seed=11)
            return "已下载", "fixture"

        with patch("tool.image_resource_pipeline.loot.workflow.parse_target_items", return_value=self.items), \
                contextlib.redirect_stdout(io.StringIO()):
            return run_pipeline(self.args, Path("fixture.xlsx"), fetch or local_fetch)

    def test_update_white_keep_history_and_unknown_remove_black(self):
        for name in ("白", "黑", "未知", "新白"):
            self.items.append(ItemResource("0x1", name, "道具", ("fixture",), 2))
        self.set_lists({("道具", "白"), ("道具", "历史白"), ("道具", "新白")}, {("道具", "黑")})
        white = self.args.loot_root / "道具/白.png"
        history = self.args.loot_root / "道具/历史白.png"
        png(white, seed=1)
        png(history, seed=2)
        original_white, original_history = white.read_bytes(), history.read_bytes()
        png(self.args.loot_root / "道具/退回未分类.png", seed=3)
        png(self.args.loot_root / "道具/黑.png", seed=4)
        list_entries = read_drop_list(self.args.whitelist), read_drop_list(self.args.blacklist)
        self.assertEqual(self.run_sync(), 0)
        self.assertNotEqual(white.read_bytes(), original_white)
        self.assertEqual(history.read_bytes(), original_history)
        self.assertTrue((self.args.loot_root / "道具/新白.png").is_file())
        self.assertFalse((self.args.loot_root / "道具/黑.png").exists())
        self.assertFalse((self.args.loot_root / "道具/未知.png").exists())
        self.assertEqual(read_drop_list(self.args.unclassified), {("道具", "未知"), ("道具", "退回未分类")})
        self.assertEqual({p.stem for p in self.args.output.rglob("*.png")}, {"未知", "退回未分类"})
        self.assertEqual((read_drop_list(self.args.whitelist), read_drop_list(self.args.blacklist)), list_entries)
        self.assertFalse((self.args.loot_root / "道具/退回未分类.png").exists())

    def test_conflicting_item_is_untouched(self):
        self.set_lists({("道具", "白")}, {("道具", "白")})
        path = self.args.loot_root / "道具/白.png"
        cached = self.args.output / "道具/白.png"
        png(path)
        png(cached, seed=2)
        before = path.read_bytes(), cached.read_bytes()
        self.items = [ItemResource("0x1", "白", "道具", ("fixture",), 2)]
        self.assertEqual(self.run_sync(fetch=lambda *_args: self.fail("冲突物品不能下载")), 1)
        self.assertEqual((path.read_bytes(), cached.read_bytes()), before)

    def test_failed_download_does_not_replace_formal_with_stale_cache(self):
        path = self.args.loot_root / "道具/白.png"
        png(path)
        png(self.args.output / "道具/白.png", seed=2)
        before = path.read_bytes()
        self.items = [ItemResource("0x1", "白", "道具", ("fixture",), 2)]
        self.assertEqual(self.run_sync(fetch=lambda *_: ("失败", "offline")), 1)
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_white_image_preserves_existing_template(self):
        path = self.args.loot_root / "道具/白.png"
        png(path)
        before = path.read_bytes()
        self.items = [ItemResource("0x1", "白", "道具", ("fixture",), 2)]

        def invalid(item, directory, *_):
            png(directory / item.item_type / item.filename, size=(50, 50))
            return "已下载", "fixture"

        self.assertEqual(self.run_sync(invalid), 1)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_list_stops_before_any_image_changes(self):
        path = self.args.loot_root / "道具/白.png"
        png(path)
        self.args.whitelist.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_sync()
        self.assertTrue(path.is_file())

    def test_unknown_items_are_listed_even_without_downloadable_images(self):
        self.items = [ItemResource("0x1", "未知", "道具", (), 2)]
        self.assertEqual(self.run_sync(fetch=lambda *_args: ("无路径", "")), 0)
        self.assertEqual(read_drop_list(self.args.unclassified), {("道具", "未知")})
        self.assertEqual(list(self.args.loot_root.rglob("*.png")), [])

    def test_transparent_palette_png_is_accepted_without_changing_cdn_bytes(self):
        self.items = [ItemResource("0x1", "白", "道具", ("fixture",), 2)]
        downloaded = []

        def palette_fetch(item, root, *_args):
            path = root / item.item_type / item.filename
            path.parent.mkdir(parents=True)
            image = Image.new("P", (44, 44), color=1)
            image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
            image.save(str(path), transparency=0)
            downloaded.append(path.read_bytes())
            return "已下载", "fixture"

        self.assertEqual(self.run_sync(palette_fetch), 0)
        target = self.args.loot_root / "道具/白.png"
        self.assertEqual(target.read_bytes(), downloaded[0])
        from tool.image_resource_pipeline.loot.matching import read_image
        self.assertEqual(read_image(target).shape, (44, 44, 4))

    def test_white_is_fetched_even_if_cached_and_downloads_are_not_forced(self):
        png(self.args.output / "道具/白.png", seed=1)
        self.items = [ItemResource("0x1", "白", "道具", ("fixture",), 2)]
        calls = []

        def fetch(item, root, timeout, force, downloader):
            calls.append(force)
            png(root / item.item_type / item.filename, seed=3)
            return "已下载", "fixture"

        self.assertEqual(self.run_sync(fetch), 0)
        self.assertEqual(calls, [True])

    def test_offline_verification_uses_formal_white_and_does_not_warn_for_black(self):
        self.args.offline = True
        png(self.args.loot_root / "道具/白.png")
        self.items = [ItemResource("0x1", name, "道具", (), 2) for name in ("白", "黑", "未知")]
        self.assertEqual(self.run_sync(fetch=lambda *_args: self.fail("离线不能下载")), 0)
        summary = (self.args.report_dir / "运行摘要.md").read_text(encoding="utf-8")
        self.assertIn("缺图待核验 1", summary)
        self.assertIn("离线核验", summary)
        self.assertNotIn("道具/黑：无路径", summary)
        self.assertTrue((self.args.loot_root / "道具/白.png").is_file())

    def test_unclassified_cannot_overwrite_manual_list(self):
        self.args.unclassified = self.args.whitelist
        before = self.args.whitelist.read_bytes()
        with self.assertRaises(ValueError):
            self.run_sync()
        self.assertEqual(self.args.whitelist.read_bytes(), before)

    def test_dry_run_does_not_mutate(self):
        self.args.dry_run = True
        self.items = [ItemResource("0x1", "未知", "道具", ("fixture",), 2)]
        self.assertEqual(self.run_sync(fetch=lambda *_args: self.fail("预览不能下载")), 0)
        self.assertFalse(self.args.unclassified.exists())
        self.assertFalse(self.args.output.exists())

    def test_only_repeated_perfect_matches_suggest_whitelist(self):
        unknown, allowed = self.root / "unknown.png", self.root / "white.png"
        png(unknown, seed=20)
        png(allowed, seed=30)
        Image.fromarray(np.zeros((44, 44, 4), dtype=np.uint8)).save(str(self.args.loot_mask))
        self.args.failed_root.mkdir()
        sample = self.args.failed_root / "unknown_1_1.png"
        shutil.copyfile(unknown, sample)
        images = {("道具", "未知"): unknown, ("道具", "白"): allowed}
        args = images, {("道具", "未知")}, self.args.failed_root, self.args.loot_mask
        self.assertEqual(whitelist_suggestions(*args), [])
        repeated = sample.with_name("unknown_1_2.png")
        sample.rename(repeated)
        rows = whitelist_suggestions(*args)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["完美样本累计次数"], 2)
        block = np.array(Image.open(unknown))
        block[:7, :, :3] = 0  # 部分遮挡不计入完美样本次数，即使日志累计很多次。
        repeated.unlink()
        Image.fromarray(block).save(str(repeated.with_name("unknown_2_999.png")))
        self.assertEqual(whitelist_suggestions(*args), [])

    def test_read_drop_list_rejects_incomplete_or_traversal_fields(self):
        for row in ({"类型": "道具", "名称": ""}, {"类型": "..", "名称": "白"}):
            write_csv(self.args.whitelist, [row], ["类型", "名称"])
            with self.assertRaises(ValueError):
                read_drop_list(self.args.whitelist)


class RuntimeLootPolicyTests(unittest.TestCase):
    def test_runtime_filters_and_invalidates_cache_when_lists_change(self):
        # 加载真实纯函数，隔离全局模块的 Qt、游戏资源及启动副作用。
        path = ROOT / "function/globals/g_resources.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {"get_item_loot_policy_signature", "get_item_loot_policy", "flatten_item_loot_images", "get_item_loot_images"}
        module = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
        with tempfile.TemporaryDirectory() as directory:
            white, black = Path(directory) / "white.csv", Path(directory) / "black.csv"
            write_csv(white, [{"类型": "道具", "名称": "白"}], ["类型", "名称"])
            write_csv(black, [], ["类型", "名称"])
            env = {"os": os, "read_drop_list": read_drop_list, "ITEM_LOOT_WHITELIST_CSV": white,
                   "ITEM_LOOT_BLACKLIST_CSV": black, "_ITEM_LOOT_POLICY_CACHE": None,
                   "_ITEM_LOOT_POLICY_SIGNATURE": None,
                   "RESOURCE_P": {"item": {"战利品": {"道具": {"白.png": 1, "未知.png": 2}}}}}
            exec(compile(module, str(path), "exec"), env)
            self.assertEqual(env["get_item_loot_images"](), {"白.png": 1})
            first_signature = env["get_item_loot_policy_signature"]()
            write_csv(white, [{"类型": "道具", "名称": "未知"}], ["类型", "名称"])
            self.assertNotEqual(first_signature, env["get_item_loot_policy_signature"]())
            self.assertEqual(env["get_item_loot_images"](), {"未知.png": 2})
            write_csv(black, [{"类型": "道具", "名称": "未知"}], ["类型", "名称"])
            self.assertEqual(env["get_item_loot_images"](), {})


if __name__ == "__main__":
    unittest.main()
