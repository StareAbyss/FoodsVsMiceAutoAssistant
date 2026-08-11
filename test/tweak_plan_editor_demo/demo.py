"""微调方案编辑器的独立评审入口。

正式实现位于 ``function.core.qmw_editor_of_tweak_plan``；这里仅保留 Demo 标识、
主题预览开关和离屏截图命令，避免生产代码反向依赖 test 目录。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from function.core.qmw_editor_of_tweak_plan import (
    DEFAULT_TWEAK_PLAN_DIR,
    QMWEditorOfTweakPlan,
    create_neutralized_palette,
    create_theme_preview_palette,
)
from function.widget.CardNameSelector import apply_faa_application_style


class TweakPlanEditorDemo(QMWEditorOfTweakPlan):
    """启用评审标识与独立主题预览的编辑器。"""

    def __init__(
        self,
        tweak_plan_dir: Path = DEFAULT_TWEAK_PLAN_DIR,
        show_default_notice: bool = True,
    ) -> None:
        super().__init__(
            tweak_plan_dir=tweak_plan_dir,
            show_default_notice=show_default_notice,
            demo_mode=True,
        )


def parse_args() -> argparse.Namespace:
    """解析独立 Demo 的启动参数。"""
    parser = argparse.ArgumentParser(description="微调方案编辑器界面 Demo")
    parser.add_argument("--plan", type=Path, help="启动后加载指定微调方案")
    parser.add_argument("--screenshot", type=Path, help="离屏保存截图后退出")
    parser.add_argument(
        "--theme",
        choices=("system", "light", "dark"),
        default="system",
        help="跟随 FAA 系统外观，或强制亮色/暗色预览",
    )
    return parser.parse_args()


def main() -> int:
    """启动界面，或在截图模式下渲染后退出。"""
    args = parse_args()
    if args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv)
    apply_faa_application_style(app)
    app.setApplicationName("微调方案编辑器 Demo")
    window = TweakPlanEditorDemo(show_default_notice=not bool(args.screenshot))
    window.set_theme_mode(args.theme)
    if args.plan:
        window._load_path(args.plan)
    window.show()
    if args.screenshot:
        QTimer.singleShot(
            250,
            lambda: (window.save_screenshot(args.screenshot), app.quit()),
        )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
