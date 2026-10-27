"""验证统一环境检测的失败隔离、可选能力降级和原生界面接收结果。"""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tool/faa_launcher/runtime_probe.py"
SPEC = importlib.util.spec_from_file_location("faa_runtime_probe", SOURCE)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class RuntimeProbeTests(unittest.TestCase):
    """使用子进程结果夹具验证崩溃、超时与提示对启动资格的影响。"""

    def run_probe(self, overrides=None):
        """返回检测退出码和协议输出，指定子项可替换为异常或组件结果。"""
        overrides = overrides or {}
        lines = []

        def runner(arguments, **kwargs):
            """模拟原生扩展子进程，保留真实协议与完整汇总路径。"""
            value = overrides.get(arguments[-1], {"ok": True, "detail": "正常"})
            if isinstance(value, Exception):
                raise value
            if isinstance(value, subprocess.CompletedProcess):
                return value
            return subprocess.CompletedProcess(arguments, 0, "FAA_PROBE_RESULT:" + json.dumps(value), "")

        code = PROBE.run_checks(ROOT, runner=runner, emit=lambda value, **_: lines.append(value))
        return code, lines

    def test_required_component_failure_blocks_launch_but_other_checks_finish(self):
        code, lines = self.run_probe({"qt": {"ok": False, "detail": "DLL 缺失"}})
        self.assertEqual(code, 1)
        self.assertTrue(any("\tqt\tfail\t" in line for line in lines))
        self.assertTrue(any("\tocr\tpass\t" in line for line in lines))
        self.assertEqual(lines[-1], "FAA_RUNTIME_DONE\t1\t0\t12")

    def test_optional_failures_allow_startup(self):
        code, lines = self.run_probe({key: {"ok": False, "detail": "不可用"} for key in ("gpu", "wmi", "solver", "ocr")})
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], "FAA_RUNTIME_DONE\t0\t4\t12")

    def test_native_crash_is_assigned_to_the_failing_component(self):
        crash = subprocess.CompletedProcess([], 0xC0000135, "", "DLL missing")
        code, lines = self.run_probe({"onnx": crash})
        self.assertEqual(code, 1)
        self.assertTrue(any("\tonnx\tfail\t" in line and "0xc0000135" in line for line in lines))

    def test_timeout_remains_optional_for_gpu(self):
        code, lines = self.run_probe({"gpu": subprocess.TimeoutExpired("probe", 40)})
        self.assertEqual(code, 0)
        self.assertTrue(any("\tgpu\twarning\t" in line and "超过 40 秒" in line for line in lines))

    def test_invalid_child_protocol_cannot_pass(self):
        code, lines = self.run_probe({"images": subprocess.CompletedProcess([], 0, "not a probe result", "")})
        self.assertEqual(code, 1)
        self.assertTrue(any("\timages\tfail\t" in line for line in lines))

    def test_locked_package_mismatch_is_reported(self):
        with patch.object(PROBE.importlib.metadata, "version", return_value="0.0.0"):
            with self.assertRaisesRegex(RuntimeError, "uv.lock 不一致"):
                PROBE.check_component("versions", ROOT)

@unittest.skipUnless(sys.platform == "win32" and (ROOT / "FAA - 环境安装器.exe").exists(), "需要构建 Windows 原生安装器")
class EmbeddedRuntimeProbeTests(unittest.TestCase):
    """实际执行 EXE 内嵌检测，不安装软件，也不启动 FAA 主窗口。"""

    def test_embedded_probe_reports_optional_warning_and_required_failure(self):
        with tempfile.TemporaryDirectory(prefix="FAA 统一环境检测 ") as temporary:
            root = Path(temporary)
            (root / ".faa-launcher-runtime-test").touch()
            venv.EnvBuilder(with_pip=False).create(root / ".venv")
            # 仅隔离测试环境通过 pth 复用现有依赖，安装器自身仍只使用所属 .venv。
            site = root / ".venv/Lib/site-packages"
            source_site = Path(sys.prefix) / "Lib/site-packages"
            (site / "faa_probe_fixture.pth").write_text(f"import site; site.addsitedir({str(source_site)!r})\n", encoding="utf-8")
            for name in (".python-version", "pyproject.toml", "uv.lock"):
                shutil.copy2(ROOT / name, root / name)
            files = ("function/faa_main.py", "function/qrc/theme_rc.py", "function/qrc/GTRONICK_rc.py",
                     "resource/ui/FAA_3.0.ui", "resource/ui/StagePlanEditor.ui", "resource/ui/draglabel.py",
                     "function/widget/MultiLevelMenu.py", "resource/template/settings.json")
            for relative in files:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            for relative in ("resource/image/common", "resource/image/card"):
                source = next((ROOT / relative).rglob("*.png"))
                destination = root / relative / source.name
                destination.parent.mkdir(parents=True)
                shutil.copy2(source, destination)

            def run():
                """接收原生界面汇总状态与逐项日志。"""
                report = root / "检测报告.txt"
                process = subprocess.run([str(ROOT / "FAA - 环境安装器.exe"), "--runtime-self-test", str(root), str(report)], timeout=100)
                self.assertEqual(process.returncode, 0)
                return report.read_text(encoding="utf-8")

            report = run()
            self.assertIn("review=1\nfailed=0\nchecks=12\n", report)
            self.assertIn("[warning] 高级识图模型", report)
            self.assertIn("[pass] Qt 图形界面", report)
            self.assertIn("selected=gpu\n", report)
            (root / "resource/ui/FAA_3.0.ui").write_text("broken UI", encoding="utf-8")
            report = run()
            self.assertIn("review=0\nfailed=1\nchecks=12\n", report)
            self.assertIn("[fail] 启动资源与目录写入", report)
            self.assertIn("selected=files\n", report)
            self.assertFalse(list((root / "update_cache/launcher_demo").glob("runtime-*.py")))


if __name__ == "__main__":
    unittest.main()
