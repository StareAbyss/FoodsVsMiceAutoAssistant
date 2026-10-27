"""安装完成后，在独立隐藏进程中验证 FAA 的实际运行依赖，不启动游戏或读取凭据。"""

import argparse
import ctypes
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import tomllib
import traceback
import xml.etree.ElementTree as ET


# 原生扩展可能直接崩溃；每组使用独立进程，便于指出具体组件并继续收集其余结果。
CHECKS = (
    ("system", "Windows 与 Python", False, 15),
    ("files", "启动资源与目录写入", False, 15),
    ("versions", "锁定依赖版本", False, 15),
    ("qt", "Qt 图形界面", False, 30),
    ("images", "图像读取与识别", False, 25),
    ("windows_api", "后台操作与本地加密", False, 20),
    ("business", "方案、表格与网络组件", False, 20),
    ("onnx", "ONNX 基础推理组件", False, 25),
    ("gpu", "高级识图模型与 GPU（可选）", True, 40),
    ("wmi", "WMI 凭据绑定能力（可选）", True, 15),
    ("solver", "特殊卡片求解器（可选）", True, 15),
    ("ocr", "截图 OCR 扩展（可选）", True, 10),
)


def check_component(key: str, root: Path) -> str:
    """执行一组检测，返回简短结果；异常由外层转换为失败或可选能力提示。"""
    if key == "system":
        version = sys.getwindowsversion()
        if version.build < 19041:
            raise RuntimeError(f"Windows build {version.build} 过旧，请升级到 Windows 10 2004 或更新版本。")
        expected = (root / ".python-version").read_text(encoding="utf-8").strip()
        if f"{sys.version_info.major}.{sys.version_info.minor}" != expected or struct.calcsize("P") != 8:
            raise RuntimeError(f"需要 {expected} 64 位 Python，请使用安装器重新准备运行环境。")
        # ORT DirectML 的 DLL 加载条件与 GPU 能否加速分开判断；这里不要求存在独立显卡。
        directory = ctypes.create_unicode_buffer(32768)
        ctypes.windll.kernel32.GetSystemDirectoryW(directory, len(directory))
        for name in ("dxcore.dll", "d3d12.dll"):
            ctypes.WinDLL(str(Path(directory.value) / name), winmode=0x800)
        return f"Windows build {version.build}，Python {expected} 64 位，系统 DirectX 组件可加载。"

    if key == "files":
        for relative in ("function/faa_main.py", "function/qrc/theme_rc.py", "function/qrc/GTRONICK_rc.py"):
            if not (root / relative).is_file():
                raise FileNotFoundError(f"缺少 {relative}，请重新解压完整安装包。")
        for relative in ("resource/ui/FAA_3.0.ui", "resource/ui/StagePlanEditor.ui"):
            ET.parse(root / relative)
        with (root / "resource/template/settings.json").open(encoding="utf-8-sig") as stream:
            json.load(stream)
        for relative in ("resource/image/common", "resource/image/card"):
            if next((root / relative).rglob("*.png"), None) is None:
                raise FileNotFoundError(f"{relative} 没有图像资源，请重新解压完整安装包。")
        # 新用户尚无个人配置；仅探测 FAA 会写入的目录，不解析或修改现有设置。
        for relative in (".", "config", "logs", "update_cache"):
            directory = root / relative
            directory.mkdir(exist_ok=True)
            with tempfile.TemporaryFile(dir=directory) as stream:
                stream.write(b"FAA runtime check")
                stream.flush()
        return "启动 UI、默认配置与图像目录完整；根目录、配置、日志和缓存可写。"

    if key == "versions":
        with (root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)
        with (root / "uv.lock").open("rb") as stream:
            lock = tomllib.load(stream)

        def normalize(name):
            """按 Python 包名规则匹配锁文件和安装元数据。"""
            return re.sub(r"[-_.]+", "-", name).lower()

        locked = {}
        for package in lock["package"]:
            locked.setdefault(normalize(package["name"]), set()).add(package["version"])
        errors = []
        for requirement in project["project"]["dependencies"]:
            name = re.match(r"[A-Za-z0-9_.-]+", requirement).group()
            try:
                installed = importlib.metadata.version(name)
                if installed not in locked.get(normalize(name), set()):
                    errors.append(f"{name}={installed} 与 uv.lock 不一致")
            except importlib.metadata.PackageNotFoundError:
                errors.append(f"缺少 {name}")
        if errors:
            raise RuntimeError("；".join(errors) + "。请点击修复依赖。")
        return "项目直接运行依赖已安装，版本与 uv.lock 一致；不要求开发依赖。"

    if key == "qt":
        # UI 中声明了项目自定义控件；仅在此隔离组加入项目路径，避免影响其他依赖的加载来源。
        sys.path.insert(0, str(root))
        from PyQt6.QtWidgets import QApplication, QWidget
        from PyQt6 import uic
        from function.qrc import theme_rc, GTRONICK_rc
        application = QApplication([])
        if application.platformName() != "windows":
            raise RuntimeError("Qt 没有使用 Windows 图形平台，请检查 QT_QPA_PLATFORM 等外部环境设置。")
        widget = QWidget()
        widget.winId()
        widget.close()
        # 编译 UI 可校验控件依赖和 XML，不实例化 FAA 主窗口及其后台线程。
        for relative in ("resource/ui/FAA_3.0.ui", "resource/ui/StagePlanEditor.ui"):
            uic.loadUiType(str(root / relative))
        return "Qt Windows 平台与隐藏窗口初始化正常，FAA UI 可以解析。"

    if key == "images":
        import cv2
        import numpy as np
        from PIL import Image
        sample = next((root / "resource/image/common").rglob("*.png"))
        pixels = cv2.imdecode(np.fromfile(sample, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if pixels is None or not pixels.size:
            raise RuntimeError(f"图像无法解码：{sample.relative_to(root)}，请重新解压资源。")
        with Image.open(sample) as picture:
            picture.load()
        cv2.matchTemplate(np.zeros((8, 8), np.uint8), np.ones((2, 2), np.uint8), cv2.TM_SQDIFF)
        return "NumPy、OpenCV、Pillow 与包内 PNG 读取正常，基础识图运算正常。"

    if key == "windows_api":
        import win32api
        import win32gui
        import win32con
        import pythoncom
        from Crypto.Cipher import AES
        win32api.GetVersionEx()
        win32gui.GetDesktopWindow()
        pythoncom.CoInitialize()
        pythoncom.CoUninitialize()
        data = b"FAA runtime test"
        cipher = AES.new(b"FAA probe key123", AES.MODE_ECB)
        if cipher.decrypt(cipher.encrypt(data)) != data:
            raise RuntimeError("本地 AES 加解密自检失败，请修复依赖。")
        return "pywin32、COM 和 AES 可用；未执行截图、点击或读取账号密码。"

    if key == "business":
        for name in ("colorlog", "dacite", "networkx", "openpyxl", "psutil", "pulp", "pyclipper", "pytz", "requests", "shapely", "wmi"):
            importlib.import_module(name)
        return "方案处理、表格、进程、几何、网络与 WMI 模块均可导入。"

    if key == "onnx":
        import onnxruntime as ort
        if "CPUExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("ONNX Runtime 缺少 CPU 推理后端，请修复依赖。")
        return f"ONNX Runtime {ort.__version__} 可加载，CPU 推理后端可用。"

    if key == "gpu":
        import onnxruntime as ort
        model = root / "resource/model/mouseV2.onnx"
        if not model.is_file():
            raise RuntimeError("缺少 mouseV2.onnx，高级战斗识图不可用；基础功能可继续。")
        providers = ort.get_available_providers()
        if "DmlExecutionProvider" not in providers:
            ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
            raise RuntimeError("模型可由 CPU 加载，GPU 加速不可用；可在高级设置中使用 CPU。")
        session = ort.InferenceSession(str(model), providers=["DmlExecutionProvider", "CPUExecutionProvider"])
        if "DmlExecutionProvider" not in session.get_providers():
            raise RuntimeError("DirectML 已回退到 CPU；可更新显卡驱动，或在高级设置中选择 CPU。")
        return "高级识图模型可以加载，DirectML GPU 后端初始化成功。"

    if key == "wmi":
        import wmi
        # 只查询系统服务是否响应，不采集用于凭据绑定的硬盘或主板标识。
        try:
            responding = bool(wmi.WMI().Win32_OperatingSystem())
        except Exception as error:
            raise RuntimeError("当前检测进程无法查询 WMI，设备凭据绑定可能受限；请检查 Windows Management Instrumentation 服务和系统权限。") from error
        if not responding:
            raise RuntimeError("WMI 服务未返回系统信息；依赖设备信息的凭据绑定可能不可用。")
        return "WMI 服务响应正常；未读取机器标识或现有凭据。"

    if key == "solver":
        import pulp
        if not pulp.PULP_CBC_CMD(msg=0).available():
            raise RuntimeError("CBC 求解器文件不可用，部分特殊卡片方案无法计算；请修复依赖。")
        return "PuLP 的 CBC 求解器文件可访问；未执行战斗方案。"

    if key == "ocr":
        directory = root / "plugins/pak"
        if not ((directory / "model.py").is_file() or (directory / "model/__init__.py").is_file()):
            raise RuntimeError("未安装截图 OCR 的 model 扩展，截图识别方案功能不可用；其他功能可继续。")
        return "截图 OCR 扩展入口存在；模型实际识别由对应功能初始化时检查。"
    raise ValueError(f"未知检测项：{key}")


def run_checks(root: Path, runner=subprocess.run, emit=print) -> int:
    """汇总隔离检测并发送原生界面协议；返回 0 表示可启动，1 表示必需项失败。"""
    failures = warnings = 0

    def report(key, status, label, detail):
        """规范化为单行协议，防止异常内容破坏界面字段边界。"""
        fields = (key, status, label, detail)
        emit("FAA_RUNTIME_CHECK\t" + "\t".join(str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in fields), flush=True)

    for key, label, optional, timeout in CHECKS:
        report(key, "pending", label, "正在检测…")
        try:
            environment = dict(os.environ, PYTHONIOENCODING="utf-8")
            # 不继承 PYTHONPATH，避免从全局或开发目录误导入其他版本的依赖。
            environment.pop("PYTHONPATH", None)
            result = runner([sys.executable, "-I", "-u", "-X", "utf8", str(Path(__file__).resolve()), "--root", str(root), "--child", key],
                            cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            payloads = [line.removeprefix("FAA_PROBE_RESULT:") for line in result.stdout.splitlines() if line.startswith("FAA_PROBE_RESULT:")]
            if result.returncode or not payloads:
                raise RuntimeError(f"组件检测进程异常退出（{result.returncode:#x}），可能存在 DLL 或驱动问题；请查看日志并修复依赖。\n{result.stdout}\n{result.stderr}")
            payload = json.loads(payloads[-1])
            status = "pass" if payload["ok"] else "warning" if optional else "fail"
            detail = payload["detail"]
            if result.stderr.strip():
                emit(f"[环境检测] [{key}] {result.stderr.strip()}", flush=True)
        except Exception as error:
            status = "warning" if optional else "fail"
            detail = (f"检测超过 {timeout} 秒，请检查组件或服务是否被阻止。" if isinstance(error, subprocess.TimeoutExpired) else str(error))
            if optional:
                detail += " 此项为可选能力，可继续启动 FAA。"
        failures += status == "fail"
        warnings += status == "warning"
        report(key, status, label, detail)
    emit(f"FAA_RUNTIME_DONE\t{failures}\t{warnings}\t{len(CHECKS)}", flush=True)
    return int(bool(failures))


def main() -> int:
    """运行完整检测或某个隔离子项，不初始化 FAA 主程序。"""
    if sys.platform == "win32":
        # DLL 崩溃交给父进程显示检测失败，避免 Windows 再弹出独立的故障对话框。
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--child", choices=[item[0] for item in CHECKS])
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    if arguments.child:
        try:
            detail = check_component(arguments.child, root)
            result = {"ok": True, "detail": detail}
        except Exception as error:
            advice = {
                "system": "请更新 Windows；Python 或系统组件缺失时重新准备环境。",
                "files": "请确认 FAA 目录可写，并重新解压完整发行包资源。",
                "versions": "请使用修复依赖，按发行包锁定版本重新安装。",
                "qt": "请修复依赖；仍失败时检查系统组件与外部 Qt 环境设置。",
                "images": "请修复依赖；包内图片损坏时重新解压资源。",
                "windows_api": "请修复依赖，并检查系统是否限制组件加载。",
                "business": "请点击修复依赖后重试。",
                "onnx": "请修复依赖，并检查 Windows 和显卡驱动是否完整。",
            }.get(arguments.child, "此项为可选能力，可继续启动 FAA。")
            result = {"ok": False, "detail": f"{error} {advice}"}
            traceback.print_exc()
        print("FAA_PROBE_RESULT:" + json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    return run_checks(root)


if __name__ == "__main__":
    raise SystemExit(main())
