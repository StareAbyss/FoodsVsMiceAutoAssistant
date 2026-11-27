"""验证原生启动器的实际子进程调用、取消、中文路径与系统 DLL 边界。"""

import importlib.util
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = Path(os.environ.get("FAA_NATIVE_LAUNCHER_EXE", str(ROOT / "FAA - 环境安装器.exe")))


@unittest.skipUnless(EXECUTABLE.is_file(), "请先构建 FAA - 环境安装器.exe")
class NativeLauncherTests(unittest.TestCase):
    """在隔离临时目录中运行核心验证，不安装真实 FAA 环境。"""

    def test_core_with_unicode_path(self):
        """通过真实子进程验证参数转义、环境继承、错误码和 Job 取消。"""
        with tempfile.TemporaryDirectory(prefix="FAA 启动器 验证 ") as directory:
            report = Path(directory) / "核心检查.txt"
            result = subprocess.run([str(EXECUTABLE), "--self-test", str(report)], timeout=30, check=False)
            self.assertEqual(result.returncode, 0, report.read_text(encoding="utf-8") if report.exists() else "没有生成检查报告")
            self.assertIn("failures=0", report.read_text(encoding="utf-8"))

    def test_native_uninstall_is_limited_to_local_environment(self):
        """实际检测隔离环境内的占用进程，并只删除两个受管目录。"""
        with tempfile.TemporaryDirectory(prefix="FAA 原生卸除 ") as directory:
            report = Path(directory) / "卸除检查.txt"
            result = subprocess.run([str(EXECUTABLE), "--maintenance-self-test", str(report)], timeout=20, check=False)
            self.assertEqual(result.returncode, 0, report.read_text(encoding="utf-8") if report.exists() else "没有生成卸除检查报告")

    def test_imports_only_windows_components(self):
        """检查最终 EXE 的普通、延迟 DLL 导入和 CLR 头。"""
        source = ROOT / "tool" / "faa_launcher" / "verify_pe.py"
        spec = importlib.util.spec_from_file_location("native_launcher_verify_pe", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.inspect_pe(EXECUTABLE)
        self.assertFalse(report["violations"], report)
        self.assertEqual(report["architecture"], "x64")

    @unittest.skipUnless(sys.version_info[:2] == (3, 12), "隔离安装验证需要 Python 3.12")
    def test_selected_package_source_preserves_versions_and_hashes(self):
        """用本机 HTTP 源验证实际换源、版本固定、hash 拒绝及锁文件不一致拒绝。"""
        def wheel(version, altered=False):
            output = io.BytesIO()
            prefix = f"faa_source_fixture-{version}.dist-info"
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(f"{prefix}/METADATA", f"Metadata-Version: 2.1\nName: faa-source-fixture\nVersion: {version}\nSummary: {'altered' if altered else 'fixture'}\n")
                archive.writestr(f"{prefix}/WHEEL", "Wheel-Version: 1.0\nGenerator: FAA-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                archive.writestr(f"{prefix}/RECORD", "")
            return output.getvalue()

        files, requests = {}, []
        filename = "faa_source_fixture-1.0.0-py3-none-any.whl"
        newer_filename = "faa_source_fixture-2.0.0-py3-none-any.whl"
        original = wheel("1.0.0")
        for source in ("origin", "chosen", "altered"):
            content = wheel("1.0.0", True) if source == "altered" else original
            files[f"/{source}/files/{filename}"] = content
            links = f'<a href="/{source}/files/{filename}#sha256={hashlib.sha256(content).hexdigest()}">{filename}</a>'
            if source == "chosen":
                files[f"/{source}/files/{newer_filename}"] = wheel("2.0.0")
                links += f'<a href="/{source}/files/{newer_filename}#sha256={hashlib.sha256(files[f"/{source}/files/{newer_filename}"]).hexdigest()}">{newer_filename}</a>'
            files[f"/{source}/simple/faa-source-fixture/"] = links.encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond(True)

            def do_HEAD(self):
                self.respond(False)

            def respond(self, include_body):
                requests.append(self.path)
                body = files.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Type", "text/html" if "/simple/" in self.path else "application/octet-stream")
                self.send_header("Content-Length", str(len(body) if body is not None else 0))
                self.end_headers()
                if body is not None and include_body:
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory(prefix="FAA 下载源 隔离验证 ") as directory:
                base = Path(directory)
                url = f"http://127.0.0.1:{server.server_port}"
                for scenario in ("chosen", "altered", "lock-mismatch"):
                    with self.subTest(scenario=scenario):
                        project = base / scenario
                        uv = project / "plugins" / "launcher_scripts" / "bin" / "uv.exe"
                        uv.parent.mkdir(parents=True)
                        with zipfile.ZipFile(ROOT / "plugins" / "launcher_scripts" / "uv" / "uv-x86_64-pc-windows-msvc.zip") as archive:
                            uv.write_bytes(archive.read("uv.exe"))
                        config = project / "pyproject.toml"
                        config.write_text(
                            '[project]\nname="faa-source-test"\nversion="0.1.0"\nrequires-python=">=3.12"\n'
                            'dependencies=["faa-source-fixture>=1"]\n[[tool.uv.index]]\n'
                            f'url="{url}/origin/simple"\ndefault=true\n', encoding="utf-8")
                        env = {key: value for key, value in os.environ.items() if not key.startswith("UV_")}
                        env.update(UV_CACHE_DIR=str(project / "cache"), UV_NO_CACHE="1", UV_NO_PROGRESS="1", UV_PYTHON_DOWNLOADS="never", UV_PYTHON=sys.executable, NO_PROXY="127.0.0.1,localhost")
                        def run(arguments):
                            return subprocess.run(arguments, cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False, creationflags=subprocess.CREATE_NO_WINDOW)

                        for arguments in ([str(uv), "lock", "--python", sys.executable], [str(uv), "venv", "--python", sys.executable, str(project / ".venv")]):
                            result = run(arguments)
                            self.assertEqual(result.returncode, 0, result.stdout.decode("utf-8", errors="replace"))
                        lock = project / "uv.lock"
                        locked_bytes = lock.read_bytes()
                        if scenario == "lock-mismatch":
                            config.write_text(config.read_text(encoding="utf-8").replace("fixture>=1", "fixture>=2"), encoding="utf-8")
                        config_bytes = config.read_bytes()
                        requests.clear()
                        report = project / "同步日志.txt"
                        source = "chosen" if scenario == "lock-mismatch" else scenario
                        result = run([str(EXECUTABLE), "--sync-dependencies-test", str(project), f"{url}/{source}/simple", str(report)])
                        log = report.read_text(encoding="utf-8") if report.exists() else "没有同步日志"
                        self.assertEqual(result.returncode, 0 if scenario == "chosen" else 1, log)
                        self.assertEqual(lock.read_bytes(), locked_bytes)
                        self.assertEqual(config.read_bytes(), config_bytes)
                        self.assertFalse(any(path.startswith("/origin/") for path in requests), requests)
                        if scenario == "chosen":
                            self.assertIn(f"/chosen/files/{filename}", requests)
                            installed = run([str(project / ".venv" / "Scripts" / "python.exe"), "-c", "import importlib.metadata; print(importlib.metadata.version('faa-source-fixture'))"])
                            self.assertEqual(installed.stdout.strip(), b"1.0.0", log)
                        elif scenario == "altered":
                            self.assertIn("hash", log.lower())
                        else:
                            self.assertFalse(any(path.startswith("/chosen/") for path in requests), requests)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
