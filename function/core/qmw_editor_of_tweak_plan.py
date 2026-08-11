"""FAA 微调方案编辑器正式窗口。"""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QEvent, QFile, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from function.common.theme import create_theme_palette as create_theme_preview_palette
from function.core.tweak_plan_editor_model import (
    AUTO_CARD_KEYS,
    BUILT_IN_TWEAK_PLAN_UUIDS,
    TweakPlanDraft,
    generate_plan_uuid,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TWEAK_PLAN_DIR = REPOSITORY_ROOT / "tweak_plan"

AUTO_CARD_LABELS = {
    "icecream": ("极寒冰沙", "自动携带、识别并按最低优先级使用"),
    "god": ("创造神", "仅复制目标允许位置中完整 3×3 的中心格，不推进队列"),
    "ikun": ("幻幻鸡", "存在正数复制目标时自动携带并参与连携"),
    "timer": ("美味计时器", "放在最高复制目标首格；仅二转会按 3×1 范围向内偏移"),
}
DEFAULT_META_DATA_FALLBACK = {
    "recording": {
        "active": False,
        "timestamp": False,
        "player": 1,
    },
    "cd_after_use_random": {
        "active": False,
        "range": [0.05, 0.25],
    },
    "senior_setting": False,
    "auto_mat_card": {
        "enabled": True,
        "use_first": True,
    },
    "enable_auto_card": {
        "icecream": True,
        "god": True,
        "ikun": True,
        "timer": False,
    },
}


def load_default_meta_data(tweak_plan_dir: Path) -> dict:
    """
    读取只读默认方案，供各个“继承默认”选项展示当前结果。

    默认文件缺失或损坏时使用与运行时一致的保守默认值，避免编辑器无法启动。

    Args:
        tweak_plan_dir: 微调方案目录。

    Returns:
        合并兜底值后的默认方案 ``meta_data``。
    """
    defaults = copy.deepcopy(DEFAULT_META_DATA_FALLBACK)
    try:
        with (tweak_plan_dir / "!默认.json").open("r", encoding="utf-8") as file:
            meta_data = json.load(file).get("meta_data", {})
        if not isinstance(meta_data, dict):
            return defaults
    except (OSError, json.JSONDecodeError, AttributeError):
        return defaults

    for key in ("senior_setting",):
        if key in meta_data:
            defaults[key] = copy.deepcopy(meta_data[key])

    raw_recording = meta_data.get("recording")
    if isinstance(raw_recording, dict):
        defaults["recording"].update(raw_recording)

    random_settings = meta_data.get("cd_after_use_random")
    if isinstance(random_settings, dict):
        defaults["cd_after_use_random"].update(random_settings)
    if isinstance(meta_data.get("enable_auto_card"), dict):
        for key in AUTO_CARD_KEYS:
            value = meta_data["enable_auto_card"].get(key)
            if isinstance(value, bool):
                defaults["enable_auto_card"][key] = value
    if isinstance(meta_data.get("auto_mat_card"), dict):
        for key in ("enabled", "use_first"):
            value = meta_data["auto_mat_card"].get(key)
            if isinstance(value, bool):
                defaults["auto_mat_card"][key] = value
    return defaults


def create_neutralized_palette(source: QPalette) -> QPalette:
    """
    保留系统亮暗层级，但把系统强调色替换为中性选中颜色。

    Windows 强调色可能是高饱和红色。它适合小面积系统反馈，不适合作为编辑器
    大量控件的边框和底色，因此 Demo 只继承系统明暗关系，不传播强调色。

    Args:
        source: 当前系统或 FAA 应用调色板。

    Returns:
        窗口、文本等角色保持不变，仅高亮角色改为中性灰的副本。
    """
    palette = QPalette(source)
    is_dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    highlight = QColor("#747A84") if is_dark else QColor("#6B7280")
    highlighted_text = QColor("#FFFFFF")
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.Highlight, highlight)
        palette.setColor(group, QPalette.ColorRole.HighlightedText, highlighted_text)
    return palette


def _mix_colors(first: QColor, second: QColor, first_weight: float) -> QColor:
    """按权重混合两个不透明颜色，供主题感知 QSS 使用。"""
    second_weight = 1.0 - first_weight
    return QColor(
        round(first.red() * first_weight + second.red() * second_weight),
        round(first.green() * first_weight + second.green() * second_weight),
        round(first.blue() * first_weight + second.blue() * second_weight),
    )


class OptionalBoolSelector(QWidget):
    """用明确下拉项编辑可缺省的 JSON 布尔字段。"""

    def __init__(self, title: str, description: str, default_value: bool) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        title_label = QLabel(title)
        description_label = QLabel(description)
        description_label.setObjectName("helperText")
        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        layout.addLayout(text_layout, stretch=1)

        self.combo = QComboBox()
        default_text = "是" if default_value else "否"
        self.combo.addItem(f"缺省 (默认:{default_text})", None)
        self.combo.addItem("是", True)
        self.combo.addItem("否", False)
        self.combo.setMinimumWidth(132)
        self.combo.setToolTip("缺省表示不写入该字段，由运行时使用默认值")
        layout.addWidget(self.combo)

    def value(self) -> bool | None:
        """返回当前选择的 JSON 布尔值或缺省状态。"""
        return self.combo.currentData()

    def set_value(self, value: bool | None) -> None:
        """按对象身份匹配 ``None``、``True`` 或 ``False`` 并更新下拉项。"""
        for index in range(self.combo.count()):
            if self.combo.itemData(index) is value:
                self.combo.setCurrentIndex(index)
                return
        self.combo.setCurrentIndex(0)


class QMWEditorOfTweakPlan(QMainWindow):
    """FAA 微调方案编辑器正式窗口。

    ``demo_mode`` 只供 ``test/tweak_plan_editor_demo`` 的独立评审入口使用；
    正式窗口始终继承 FAA 主程序已经选定的字体、亮暗主题和原生 Qt 控件外观。
    """

    def __init__(
        self,
        tweak_plan_dir: Path = DEFAULT_TWEAK_PLAN_DIR,
        show_default_notice: bool = True,
        demo_mode: bool = False,
        parent: QWidget | None = None,
        on_plan_library_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.tweak_plan_dir = tweak_plan_dir
        self.demo_mode = demo_mode
        self.on_plan_library_changed = on_plan_library_changed
        # 保留参数以兼容既有 Demo 启动与测试调用；加载默认方案已不再弹窗。
        _ = show_default_notice
        # EXTRA 初始化时会通过 QFontDatabase 加载 FAA 字体，必须等 QApplication
        # 已创建后再导入；放到模块顶层会让独立 Demo 卡在启动阶段。
        from function.globals import EXTRA

        self.current_tweak_plan_version = EXTRA.TWEAK_PLAN_VERSION
        self.current_faa_version = EXTRA.VERSION
        self.get_user_text_color = EXTRA.get_user_text_color
        self.default_meta_data = load_default_meta_data(tweak_plan_dir)
        self.system_palette = create_neutralized_palette(QApplication.palette())
        self.current_path: Path | None = None
        self.saved_plan_name = ""
        self.unknown_meta_data: dict = {}
        self.plan_editable = True
        self._loading = False
        self._build_ui()
        self._connect_signals()
        startup_conflicts = self._repair_uuid_conflicts()
        self._load_plan_list()
        self._load_initial_plan()
        if startup_conflicts:
            QTimer.singleShot(
                0,
                lambda: self._show_uuid_conflict_messages(startup_conflicts),
            )

    def _build_ui(self) -> None:
        """构建编辑表单与实时 JSON 方案浏览区。"""
        self.setWindowTitle(
            "微调方案编辑器 · Demo" if self.demo_mode else "微调方案编辑器"
        )
        self.resize(1080, 840)
        self.setMinimumSize(960, 680)

        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)
        self.setCentralWidget(root)

        header = QHBoxLayout()
        title_column = QVBoxLayout()
        title = QLabel("微调方案编辑器")
        title.setObjectName("pageTitle")
        subtitle = QLabel("战斗方案编辑器扩展 · 快速覆盖单场战斗行为")
        subtitle.setObjectName("subtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header.addLayout(title_column)
        header.addStretch()
        self.demo_badge = QLabel("TEST DEMO")
        self.demo_badge.setObjectName("demoBadge")
        self.demo_badge.setVisible(self.demo_mode)
        header.addWidget(self.demo_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root_layout.addLayout(header)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        toolbar_layout.addWidget(QLabel("浏览方案"))
        self.plan_selector = QComboBox()
        self.plan_selector.setMinimumWidth(230)
        self.plan_selector.setToolTip("选择后立即切换到对应的微调方案")
        toolbar_layout.addWidget(self.plan_selector)
        self.new_button = QPushButton("新建")
        self.new_button.setToolTip("复制默认方案，生成新 UUID，并立即保存到微调方案文件夹")
        self.save_button = QPushButton("保存")
        self.save_button.setToolTip("保存当前方案；全零 UUID 默认方案不可保存")
        self.delete_button = QPushButton("删除")
        self.delete_button.setToolTip("确认后将当前方案移入系统回收站")
        self.import_button = QPushButton("从外部导入 JSON…")
        self.import_button.setToolTip("从外部选择 JSON，复制到微调方案文件夹并切换到该方案")
        toolbar_layout.addWidget(self.new_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.delete_button)
        toolbar_layout.addWidget(self.import_button)
        self.operation_status_label = QLabel()
        self.operation_status_label.setObjectName("operationStatus")
        self.operation_status_label.hide()
        self.operation_status_effect = QGraphicsOpacityEffect(
            self.operation_status_label
        )
        self.operation_status_label.setGraphicsEffect(
            self.operation_status_effect
        )
        self.operation_status_animation = QPropertyAnimation(
            self.operation_status_effect,
            b"opacity",
            self,
        )
        self.operation_status_animation.setDuration(800)
        self.operation_status_animation.setStartValue(1.0)
        self.operation_status_animation.setEndValue(0.0)
        self.operation_status_animation.finished.connect(
            self.operation_status_label.hide
        )
        self.operation_status_timer = QTimer(self)
        self.operation_status_timer.setSingleShot(True)
        self.operation_status_timer.setInterval(2600)
        self.operation_status_timer.timeout.connect(
            self._fade_operation_status
        )
        toolbar_layout.addWidget(self.operation_status_label)
        toolbar_layout.addStretch()
        self.theme_label = QLabel("外观")
        self.theme_label.setVisible(self.demo_mode)
        toolbar_layout.addWidget(self.theme_label)
        self.theme_selector = QComboBox()
        self.theme_selector.addItem("跟随 FAA（系统）", "system")
        self.theme_selector.addItem("亮色预览", "light")
        self.theme_selector.addItem("暗色预览", "dark")
        self.theme_selector.setVisible(self.demo_mode)
        toolbar_layout.addWidget(self.theme_selector)
        root_layout.addWidget(toolbar)

        self.read_only_notice = QLabel(
            "当前为全零 UUID 的默认内置方案，仅供查阅。其他方案中设为“缺省”或"
            "“继承”的选项，将继承此方案的对应项。请点击“新建”后编辑自己的方案。"
        )
        self.read_only_notice.setObjectName("readOnlyNotice")
        self.read_only_notice.setWordWrap(True)
        self.read_only_notice.hide()
        root_layout.addWidget(self.read_only_notice)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self._build_editor_panel())
        self.main_splitter.addWidget(self._build_preview_panel())
        # JSON 方案浏览只用于核对当前结果，不需要占据与编辑区接近的宽度。
        # 将主要横向空间留给左侧选项，长说明和原生下拉框会更舒展。
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([720, 300])
        root_layout.addWidget(self.main_splitter, stretch=1)

        self._apply_style()

    def _build_editor_panel(self) -> QWidget:
        """构建可滚动的选项编辑区。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(12)

        basic_group = QGroupBox("方案信息")
        basic_form = QFormLayout(basic_group)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.file_name_input = QLineEdit("未命名微调方案")
        self.file_name_input.setPlaceholderText("对应微调方案文件夹中的 JSON 文件名")
        self.file_name_input.setToolTip("方案名称对应 JSON 文件名；名称必须合法且不能与现有方案重复")
        self.uuid_input = QLineEdit()
        self.uuid_input.setReadOnly(True)
        self.uuid_input.setEnabled(False)
        self.uuid_input.setToolTip("UUID 由 FAA 自动生成；内置方案使用固定 UUID")
        self.version_input = QLineEdit(self.current_tweak_plan_version)
        self.version_input.setReadOnly(True)
        self.version_input.setEnabled(False)
        self.version_input.setToolTip("由当前 FAA 微调方案编辑器自动维护")
        self.faa_version_input = QLineEdit()
        self.faa_version_input.setReadOnly(True)
        self.faa_version_input.setEnabled(False)
        self.faa_version_input.setToolTip("最近一次创建或修改此方案时的 FAA 版本")
        self.tips_input = QPlainTextEdit()
        self.tips_input.setPlaceholderText("说明这份方案适用的关卡、用途或注意事项…")
        self.tips_input.setMaximumHeight(72)
        basic_form.addRow("方案名称", self.file_name_input)
        basic_form.addRow("UUID（自动）", self.uuid_input)
        basic_form.addRow("格式版本（自动）", self.version_input)
        basic_form.addRow("上次编辑时FAA的版本号：", self.faa_version_input)
        basic_form.addRow("方案说明", self.tips_input)
        layout.addWidget(basic_group)

        battle_group = QGroupBox("战斗节奏")
        battle_layout = QVBoxLayout(battle_group)
        interval_row = QHBoxLayout()
        interval_text = QVBoxLayout()
        interval_text.addWidget(QLabel("放卡后的随机间隔"))
        interval_hint = QLabel("界面使用整数毫秒；JSON 仍以秒记录，并同步调整检测轮次")
        interval_hint.setObjectName("helperText")
        interval_text.addWidget(interval_hint)
        interval_row.addLayout(interval_text, stretch=1)
        self.random_mode_combo = QComboBox()
        default_random_settings = self.default_meta_data["cd_after_use_random"]
        default_interval = default_random_settings.get("range")
        if default_random_settings.get("active") is not True:
            default_interval_text = "关闭"
        else:
            default_interval_text = str(default_interval)
        self.random_mode_combo.addItem(
            f"继承 (默认:{default_interval_text})",
            "inherit",
        )
        self.random_mode_combo.addItem("明确关闭", "off")
        self.random_mode_combo.addItem("使用随机范围", "range")
        interval_row.addWidget(self.random_mode_combo)
        self.random_min_spin = self._create_milliseconds_spinbox(50)
        self.random_max_spin = self._create_milliseconds_spinbox(250)
        interval_row.addWidget(self.random_min_spin)
        interval_row.addWidget(QLabel("至"))
        interval_row.addWidget(self.random_max_spin)
        battle_layout.addLayout(interval_row)
        layout.addWidget(battle_group)

        auto_mat_group = QGroupBox("自动承载")
        auto_mat_layout = QVBoxLayout(auto_mat_group)
        self.auto_mat_card_enabled_selector = OptionalBoolSelector(
            "启用承载卡",
            "根据关卡地形需求自动携带、识别并铺设承载卡",
            self.default_meta_data["auto_mat_card"]["enabled"] is True,
        )
        self.auto_mat_card_first_selector = OptionalBoolSelector(
            "优先使用承载卡（0费承载专用）",
            "关闭后先执行战斗方案首卡，避免 25 火承载阻塞产火循环",
            self.default_meta_data["auto_mat_card"]["use_first"] is True,
        )
        auto_mat_layout.addWidget(self.auto_mat_card_enabled_selector)
        auto_mat_layout.addWidget(self.auto_mat_card_first_selector)
        layout.addWidget(auto_mat_group)

        auto_card_group = QGroupBox("自动辅助卡片")
        auto_card_layout = QVBoxLayout(auto_card_group)
        self.auto_card_selectors: dict[str, OptionalBoolSelector] = {}
        for key in AUTO_CARD_KEYS:
            title, description = AUTO_CARD_LABELS[key]
            selector = OptionalBoolSelector(
                f"启用{title}",
                description,
                self.default_meta_data["enable_auto_card"].get(key) is True,
            )
            self.auto_card_selectors[key] = selector
            auto_card_layout.addWidget(selector)
        layout.addWidget(auto_card_group)

        # 高级战斗是可选能力，不属于普通战斗节奏；单独放在所有常用项之后，
        # 避免用户误以为调整随机间隔时必须同时理解或启用高级战斗。
        senior_group = QGroupBox("高级战斗")
        senior_layout = QVBoxLayout(senior_group)
        self.senior_selector = OptionalBoolSelector(
            "启用高级战斗",
            "仅在 FAA 全局“自动高级战斗”总开关同时开启时生效",
            self.default_meta_data["senior_setting"] is True,
        )
        senior_layout.addWidget(self.senior_selector)
        layout.addWidget(senior_group)

        # 录制属于对战斗过程的附加观察能力，不影响带卡、放卡或高级战斗
        # 的核心决策，因此放在编辑区最底部，降低常用战斗选项之间的割裂感。
        recording_group = QGroupBox("战斗录制")
        recording_layout = QVBoxLayout(recording_group)
        self.recording_selector = OptionalBoolSelector(
            "开启战斗录制",
            "进入战斗后开始，战斗执行器退出后停止",
            self.default_meta_data["recording"]["active"] is True,
        )
        self.timestamp_selector = OptionalBoolSelector(
            "添加日期与时间遮挡",
            "在视频左上角绘制白底日期与时间",
            self.default_meta_data["recording"]["timestamp"] is True,
        )
        recording_layout.addWidget(self.recording_selector)
        recording_layout.addWidget(self.timestamp_selector)

        self.recording_player_row = QWidget()
        player_row_layout = QHBoxLayout(self.recording_player_row)
        player_row_layout.setContentsMargins(4, 3, 4, 3)
        player_row_layout.setSpacing(10)
        player_text_layout = QVBoxLayout()
        player_text_layout.setSpacing(1)
        player_text_layout.addWidget(QLabel("录制窗口"))
        player_hint = QLabel("组队时可选择录制 1P 或 2P 游戏窗口")
        player_hint.setObjectName("helperText")
        player_text_layout.addWidget(player_hint)
        player_row_layout.addLayout(player_text_layout, stretch=1)
        self.recording_player_combo = QComboBox()
        self.recording_player_combo.setMinimumWidth(132)
        default_player = self.default_meta_data["recording"]["player"]
        self.recording_player_combo.addItem(
            f"继承 (默认:{default_player}P)",
            None,
        )
        self.recording_player_combo.addItem("1P 窗口", 1)
        self.recording_player_combo.addItem("2P 窗口（仅组队）", 2)
        player_row_layout.addWidget(self.recording_player_combo)
        recording_layout.addWidget(self.recording_player_row)
        layout.addWidget(recording_group)
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_preview_panel(self) -> QWidget:
        """构建供用户核对和导出的实时 JSON 方案浏览区。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(12)

        preview_group = QGroupBox("实时 JSON 预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        preview_font = QFont(QApplication.font())
        preview_font.setPointSize(10)
        preview_font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(preview_font)
        preview_layout.addWidget(self.preview)
        self.validation_label = QLabel("格式校验通过")
        self.validation_label.setObjectName("validationOk")
        preview_layout.addWidget(self.validation_label)
        layout.addWidget(preview_group, stretch=1)
        return panel

    @staticmethod
    def _create_milliseconds_spinbox(value: int) -> QSpinBox:
        """创建以毫秒为单位、仅允许整数的间隔输入框。"""
        spinbox = QSpinBox()
        spinbox.setRange(0, 10_000)
        spinbox.setSingleStep(10)
        spinbox.setSuffix(" ms")
        spinbox.setValue(value)
        spinbox.setMinimumWidth(105)
        return spinbox

    def _connect_signals(self) -> None:
        """连接文件操作与实时预览信号。"""
        self.new_button.clicked.connect(self._new_plan)
        self.save_button.clicked.connect(self._save_plan)
        self.delete_button.clicked.connect(self._delete_plan)
        self.import_button.clicked.connect(self._import_plan)
        self.plan_selector.activated.connect(self._load_selected_plan)
        self.theme_selector.currentIndexChanged.connect(self._on_theme_changed)
        self.random_mode_combo.currentIndexChanged.connect(self._on_random_mode_changed)
        self.file_name_input.editingFinished.connect(
            self._validate_current_plan_name
        )

        controls = [
            self.file_name_input,
            self.tips_input,
            self.senior_selector,
            self.random_mode_combo,
            self.random_min_spin,
            self.random_max_spin,
            self.recording_selector,
            self.timestamp_selector,
            self.recording_player_combo,
            *self.auto_card_selectors.values(),
            self.auto_mat_card_enabled_selector,
            self.auto_mat_card_first_selector,
        ]
        for control in controls:
            if isinstance(control, QLineEdit):
                control.textChanged.connect(self._on_plan_content_changed)
            elif isinstance(control, QPlainTextEdit):
                control.textChanged.connect(self._on_plan_content_changed)
            elif isinstance(control, OptionalBoolSelector):
                control.combo.currentIndexChanged.connect(self._on_plan_content_changed)
            elif isinstance(control, QComboBox):
                control.currentIndexChanged.connect(self._on_plan_content_changed)
            elif isinstance(control, QSpinBox):
                control.valueChanged.connect(self._on_plan_content_changed)

    def _apply_operation_status_color(self, color_level: int = 3) -> None:
        """按当前亮暗主题应用 MidSignalPrint 使用者色表中的状态颜色。"""
        is_dark = (
            self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        )
        theme = "dark" if is_dark else "light"
        color = QColor(
            f"#{self.get_user_text_color(color_level, theme)}"
        )
        palette = QPalette(self.operation_status_label.palette())
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.operation_status_label.setPalette(palette)

    def _show_operation_status(self, text: str, color_level: int = 3) -> None:
        """在工具栏短暂显示成功操作，停留数秒后平滑渐隐。"""
        self.operation_status_animation.stop()
        self.operation_status_timer.stop()
        self.operation_status_effect.setOpacity(1.0)
        self.operation_status_label.setText(text)
        self.operation_status_label.setProperty("colorLevel", color_level)
        self._apply_operation_status_color(color_level)
        self.operation_status_label.show()
        self.operation_status_timer.start()

    def _fade_operation_status(self) -> None:
        """启动工具栏操作提示的渐隐动画。"""
        self.operation_status_animation.stop()
        self.operation_status_animation.setStartValue(
            self.operation_status_effect.opacity()
        )
        self.operation_status_animation.setEndValue(0.0)
        self.operation_status_animation.start()

    def _notify_plan_library_changed(self) -> None:
        """通知 FAA 主窗口刷新内存中的微调方案资源。"""
        if self.on_plan_library_changed is not None:
            self.on_plan_library_changed()

    def _load_plan_list(self) -> None:
        """扫描仓库现有微调方案并填充选择器。"""
        self.plan_selector.clear()
        if not self.tweak_plan_dir.is_dir():
            return
        paths = sorted(self.tweak_plan_dir.glob("*.json"), key=lambda path: path.name)
        for path in paths:
            self.plan_selector.addItem(path.stem, path)

    def _load_initial_plan(self) -> None:
        """优先展示默认方案，目录为空时创建新草稿。"""
        default_path = self.tweak_plan_dir / "!默认.json"
        if default_path.is_file():
            self._load_path(default_path)
        else:
            self._new_plan()

    def refresh_plan_library(self) -> None:
        """重新扫描方案目录，并尽量保持当前方案。

        主界面每次打开编辑器前调用一次，确保用户在窗口关闭期间通过文件管理器
        增删的方案能够立即出现，同时再次执行 UUID 唯一性校验。
        """
        preferred_path = self.current_path
        conflicts = self._repair_uuid_conflicts()
        self._load_plan_list()
        if preferred_path is not None and preferred_path.is_file():
            self._load_path(preferred_path)
        else:
            self._load_initial_plan()
        if conflicts:
            self._show_uuid_conflict_messages(conflicts)

    def _load_selected_plan(self, _index: int | bool = 0) -> None:
        """加载下拉框当前选中的方案。"""
        path = self.plan_selector.currentData()
        if isinstance(path, Path):
            self._load_path(path)

    @staticmethod
    def _uuid_conflict_message(
            plan_name: str,
            old_uuid: str,
            owner_name: str,
            new_uuid: str,
            imported: bool = False,
    ) -> str:
        """生成统一的 UUID 冲突说明；导入提示采用用户指定的完整措辞。"""
        if imported:
            return (
                f"微调方案【{plan_name}】(UUID:{old_uuid})与另一方案 "
                f"【{owner_name}】(UUID:{old_uuid}) 发生冲突，你导入的方案已修改UUID为：{new_uuid}"
            )
        return (
            f"微调方案【{plan_name}】(UUID:{old_uuid})与另一方案 "
            f"【{owner_name}】(UUID:{old_uuid}) 发生冲突，已自动修改UUID为：{new_uuid}"
        )

    def _iter_plan_paths(self) -> list[Path]:
        """按固定内置方案优先、普通方案随后返回方案路径。"""
        if not self.tweak_plan_dir.is_dir():
            return []
        built_in_order = {
            name: index
            for index, name in enumerate(BUILT_IN_TWEAK_PLAN_UUIDS)
        }
        return sorted(
            self.tweak_plan_dir.glob("*.json"),
            key=lambda path: (
                0 if path.stem in built_in_order else 1,
                built_in_order.get(path.stem, 0),
                path.name,
            ),
        )

    @staticmethod
    def _read_plan_mapping(path: Path) -> dict:
        """读取并校验 UUID 管理所需的最小 JSON 结构。"""
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("meta_data"), dict):
            raise ValueError("微调方案缺少 meta_data 对象")
        return data

    @staticmethod
    def _write_plan_mapping(path: Path, data: dict) -> None:
        """以 FAA 微调方案统一格式写回 JSON。"""
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

    def _find_uuid_owner(
            self,
            plan_uuid: str,
            excluded_paths: set[Path] | None = None,
    ) -> Path | None:
        """查找方案文件夹中占用指定 UUID 的另一份方案。"""
        excluded = {
            path.resolve()
            for path in (excluded_paths or set())
        }
        for path in self._iter_plan_paths():
            if path.resolve() in excluded:
                continue
            try:
                data = self._read_plan_mapping(path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if str(data["meta_data"].get("uuid", "")) == plan_uuid:
                return path
        return None

    def _generate_unique_uuid(self, excluded_paths: set[Path] | None = None) -> str:
        """生成当前微调方案文件夹中尚未使用的 UUID1。"""
        while True:
            candidate = generate_plan_uuid()
            if self._find_uuid_owner(candidate, excluded_paths) is None:
                return candidate

    def _repair_uuid_conflicts(
            self,
            excluded_paths: set[Path] | None = None,
    ) -> list[str]:
        """
        扫描方案文件夹并修复重复或无效 UUID。

        初始化时扫描全部文件；保存当前方案时暂时排除当前文件，先修复其他
        方案之间的冲突，再单独拿尚未保存的当前 UUID 与它们比较，避免覆盖
        用户正在界面中编辑的内容。固定内置方案始终恢复为约定 UUID。
        """
        excluded = {
            path.resolve()
            for path in (excluded_paths or set())
        }
        seen: dict[str, Path] = {}
        messages = []
        for path in self._iter_plan_paths():
            if path.resolve() in excluded:
                continue
            try:
                data = self._read_plan_mapping(path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue

            meta_data = data["meta_data"]
            current_uuid = str(meta_data.get("uuid", ""))
            changed = False
            expected_uuid = BUILT_IN_TWEAK_PLAN_UUIDS.get(path.stem)
            if expected_uuid is not None:
                changed = current_uuid != expected_uuid
                current_uuid = expected_uuid
                meta_data["uuid"] = expected_uuid

            try:
                uuid.UUID(current_uuid)
                valid_uuid = True
            except (ValueError, AttributeError):
                valid_uuid = False

            owner = seen.get(current_uuid) if valid_uuid else None
            if not valid_uuid or owner is not None:
                old_uuid = current_uuid or "无效或缺失"
                new_uuid = self._generate_unique_uuid(excluded_paths)
                meta_data["uuid"] = new_uuid
                if owner is None:
                    messages.append(
                        f"微调方案【{path.stem}】的 UUID 无效，已自动修改为：{new_uuid}"
                    )
                else:
                    messages.append(self._uuid_conflict_message(
                        path.stem,
                        old_uuid,
                        owner.stem,
                        new_uuid,
                    ))
                current_uuid = new_uuid
                changed = True

            seen[current_uuid] = path
            if changed:
                try:
                    self._write_plan_mapping(path, data)
                except OSError:
                    continue
        return messages

    def _show_uuid_conflict_messages(self, messages: list[str]) -> None:
        """集中提示自动完成的 UUID 修复。"""
        if messages:
            QMessageBox.warning(
                self,
                "UUID 冲突已修复",
                "\n\n".join(messages),
            )

    def _unique_plan_path(self, preferred_name: str) -> Path:
        """为新建或导入方案生成不与现有文件重名的目标路径。"""
        candidate = self.tweak_plan_dir / f"{preferred_name}.json"
        sequence = 2
        while candidate.exists():
            candidate = self.tweak_plan_dir / f"{preferred_name} ({sequence}).json"
            sequence += 1
        return candidate

    def _import_plan(self) -> None:
        """从外部复制 JSON 到方案文件夹，必要时只修改冲突 UUID。"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "从外部导入微调方案",
            str(self.tweak_plan_dir),
            "JSON 文件 (*.json)",
        )
        if not file_name:
            return

        source_path = Path(file_name)
        try:
            data = self._read_plan_mapping(source_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QMessageBox.critical(self, "无法导入微调方案", str(error))
            return

        target_path = self._unique_plan_path(source_path.stem)
        imported_uuid = str(data["meta_data"].get("uuid", ""))
        try:
            uuid.UUID(imported_uuid)
        except (ValueError, AttributeError):
            new_uuid = self._generate_unique_uuid()
            data["meta_data"]["uuid"] = new_uuid
            QMessageBox.warning(
                self,
                "导入方案 UUID 无效",
                f"微调方案【{target_path.stem}】的 UUID 无效，已生成新 UUID：{new_uuid}",
            )
        else:
            owner = self._find_uuid_owner(imported_uuid)
            if owner is not None:
                new_uuid = self._generate_unique_uuid()
                data["meta_data"]["uuid"] = new_uuid
                QMessageBox.warning(
                    self,
                    "导入方案 UUID 冲突",
                    self._uuid_conflict_message(
                        target_path.stem,
                        imported_uuid,
                        owner.stem,
                        new_uuid,
                        imported=True,
                    ),
                )

        try:
            self.tweak_plan_dir.mkdir(parents=True, exist_ok=True)
            self._write_plan_mapping(target_path, data)
        except OSError as error:
            QMessageBox.critical(self, "导入失败", str(error))
            return

        self._load_plan_list()
        self._load_path(target_path)
        self._notify_plan_library_changed()
        self._show_operation_status(f"已导入：{target_path.name}")

    def _load_path(self, path: Path) -> None:
        """读取方案并将其完整映射到编辑控件。"""
        try:
            draft = TweakPlanDraft.load(path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QMessageBox.critical(self, "无法加载微调方案", str(error))
            return

        if self._is_built_in_path(path):
            draft.plan_uuid = BUILT_IN_TWEAK_PLAN_UUIDS[path.stem]

        self.plan_editable = draft.plan_uuid != BUILT_IN_TWEAK_PLAN_UUIDS["!默认"]
        self.current_path = path
        for index in range(self.plan_selector.count()):
            listed_path = self.plan_selector.itemData(index)
            if isinstance(listed_path, Path) and listed_path.resolve() == path.resolve():
                self.plan_selector.setCurrentIndex(index)
                break
        self._apply_draft(draft, path.stem)
        self._set_plan_editable(self.plan_editable)
        if self.plan_editable:
            self._show_operation_status(f"已切换：{path.name}")
        else:
            self._show_operation_status("正在查阅：!默认.json")

    def _new_plan(self, _checked: bool = False) -> None:
        """复制默认方案，生成新 UUID、清空说明并立即保存切换。"""
        default_path = self.tweak_plan_dir / "!默认.json"
        try:
            draft = TweakPlanDraft.load(default_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QMessageBox.critical(self, "无法新建微调方案", str(error))
            return

        target_path = self._unique_plan_path("新的方案")
        draft.plan_uuid = self._generate_unique_uuid()
        draft.version = self.current_tweak_plan_version
        draft.faa_version = self.current_faa_version
        draft.tips = ""
        try:
            self._write_plan_mapping(target_path, draft.to_mapping())
        except OSError as error:
            QMessageBox.critical(self, "新建失败", str(error))
            return

        self._load_plan_list()
        self._load_path(target_path)
        self._notify_plan_library_changed()
        self._show_operation_status(f"已新建：{target_path.name}")

    def _show_default_read_only_notice(self) -> None:
        """提醒用户全零 UUID 默认方案不可编辑或替换。"""
        QMessageBox.information(
            self,
            "默认方案仅供查阅",
            "UUID 为全零的 【!默认】 方案是 FAA 内置基准，不能编辑、保存或删除。\n\n"
            "如需创建微调方案，请点击“新建”，FAA 会自动生成 UUID。",
        )

    def _set_plan_editable(self, editable: bool) -> None:
        """统一切换默认方案只读态与普通方案编辑态。"""
        self.plan_editable = editable
        self.read_only_notice.setVisible(not editable)
        self.file_name_input.setReadOnly(not editable)
        self.file_name_input.setEnabled(editable)
        self.version_input.setReadOnly(True)
        self.faa_version_input.setReadOnly(True)
        self.uuid_input.setEnabled(False)
        self.version_input.setEnabled(False)
        self.faa_version_input.setEnabled(False)
        self.tips_input.setReadOnly(not editable)
        self.tips_input.setEnabled(editable)
        self.senior_selector.combo.setEnabled(editable)
        self.recording_selector.combo.setEnabled(editable)
        self.timestamp_selector.combo.setEnabled(editable)
        for selector in self.auto_card_selectors.values():
            selector.combo.setEnabled(editable)
        self.auto_mat_card_enabled_selector.combo.setEnabled(editable)
        self.auto_mat_card_first_selector.combo.setEnabled(editable)
        self.random_mode_combo.setEnabled(editable)
        self.recording_player_combo.setEnabled(editable)
        self.save_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        self._on_random_mode_changed()
        self._refresh_preview()

    def _is_built_in_path(self, path: Path) -> bool:
        """判断目标是否为仓库微调目录中的固定内置方案。"""
        try:
            same_parent = path.resolve().parent == self.tweak_plan_dir.resolve()
        except OSError:
            return False
        return same_parent and path.stem in BUILT_IN_TWEAK_PLAN_UUIDS

    def _apply_draft(self, draft: TweakPlanDraft, file_name: str) -> None:
        """在阻止中间刷新时批量设置界面值。"""
        self._loading = True
        self.saved_plan_name = file_name
        self.unknown_meta_data = draft.unknown_meta_data
        self.file_name_input.setText(file_name)
        self.uuid_input.setText(draft.plan_uuid)
        self.version_input.setText(draft.version)
        self.faa_version_input.setText(draft.faa_version or "未记录")
        self.tips_input.setPlainText(draft.tips)
        self.recording_selector.set_value(draft.recording)
        self.timestamp_selector.set_value(draft.timestamp)
        self.senior_selector.set_value(draft.senior_setting)
        player_index = self.recording_player_combo.findData(draft.recording_player)
        self.recording_player_combo.setCurrentIndex(max(0, player_index))
        random_index = self.random_mode_combo.findData(draft.random_interval_mode)
        self.random_mode_combo.setCurrentIndex(max(0, random_index))
        self.random_min_spin.setValue(round(draft.random_interval_min * 1000))
        self.random_max_spin.setValue(round(draft.random_interval_max * 1000))
        for key, value in draft.enable_auto_card.items():
            self.auto_card_selectors[key].set_value(value)
        self.auto_mat_card_enabled_selector.set_value(
            draft.auto_mat_card_enabled
        )
        self.auto_mat_card_first_selector.set_value(
            draft.auto_mat_card_first
        )
        self._loading = False
        self._on_random_mode_changed()
        self._refresh_preview()

    def _collect_draft(self) -> TweakPlanDraft:
        """把当前控件状态整理为可验证、可序列化的草稿。"""
        return TweakPlanDraft(
            plan_uuid=self.uuid_input.text().strip(),
            version=self.version_input.text().strip(),
            faa_version=(
                None
                if self.faa_version_input.text() == "未记录"
                else self.faa_version_input.text()
            ),
            tips=self.tips_input.toPlainText().strip(),
            recording=self.recording_selector.value(),
            timestamp=self.timestamp_selector.value(),
            recording_player=self.recording_player_combo.currentData(),
            random_interval_mode=self.random_mode_combo.currentData(),
            random_interval_min=self.random_min_spin.value() / 1000,
            random_interval_max=self.random_max_spin.value() / 1000,
            senior_setting=self.senior_selector.value(),
            auto_mat_card_enabled=self.auto_mat_card_enabled_selector.value(),
            auto_mat_card_first=self.auto_mat_card_first_selector.value(),
            enable_auto_card={
                key: selector.value()
                for key, selector in self.auto_card_selectors.items()
            },
            unknown_meta_data=self.unknown_meta_data,
        )

    def _on_plan_content_changed(self, *_args) -> None:
        """用户修改方案内容后自动记录当前格式版本与 FAA 版本。"""
        if self._loading or not self.plan_editable:
            return
        self.version_input.setText(self.current_tweak_plan_version)
        self.faa_version_input.setText(self.current_faa_version)
        self._refresh_preview()

    def _on_random_mode_changed(self, _index: int = 0) -> None:
        """仅在使用随机范围时开放上下限输入。"""
        enabled = self.plan_editable and self.random_mode_combo.currentData() == "range"
        self.random_min_spin.setEnabled(enabled)
        self.random_max_spin.setEnabled(enabled)

    def set_theme_mode(self, mode: str) -> None:
        """切换跟随 FAA、亮色预览或暗色预览模式。"""
        index = self.theme_selector.findData(mode)
        if index < 0:
            raise ValueError(f"不支持的主题模式: {mode}")
        if index == self.theme_selector.currentIndex():
            self._on_theme_changed()
        else:
            self.theme_selector.setCurrentIndex(index)

    def _on_theme_changed(self, _index: int = 0) -> None:
        """切换应用 Palette，让全部原生控件同步更新亮暗外观。"""
        app = QApplication.instance()
        if app is None:
            return
        mode = self.theme_selector.currentData()
        palette = self.system_palette if mode == "system" else create_theme_preview_palette(mode)
        app.setPalette(palette)
        self._apply_style()

    def _refresh_preview(self, *_args) -> None:
        """同步 JSON 预览、校验提示和保存/删除按钮状态。"""
        if self._loading:
            return
        draft = self._collect_draft()
        self.preview.setPlainText(draft.to_json())
        messages = draft.validation_messages()
        if not self.plan_editable:
            self.validation_label.setText("默认内置方案 · 仅供查阅")
            self.validation_label.setObjectName("validationOk")
            self.save_button.setEnabled(False)
            self.delete_button.setEnabled(False)
        elif messages:
            self.validation_label.setText("；".join(messages))
            self.validation_label.setObjectName("validationError")
            self.save_button.setEnabled(False)
            self.delete_button.setEnabled(True)
        else:
            self.validation_label.setText("格式校验通过 · 可保存")
            self.validation_label.setObjectName("validationOk")
            self.save_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        self.validation_label.style().unpolish(self.validation_label)
        self.validation_label.style().polish(self.validation_label)

    @staticmethod
    def _plan_name_error(plan_name: str) -> str | None:
        """返回 Windows 文件名规则下的方案名称错误。"""
        if not plan_name:
            return "方案名称不能为空"
        if any(character in plan_name for character in '<>:"/\\|?*'):
            return "方案名称不能包含 < > : \" / \\ | ? *"
        if plan_name.endswith((" ", ".")):
            return "方案名称不能以空格或句点结尾"
        return None

    def _validate_current_plan_name(self) -> bool:
        """
        在名称编辑结束时阻止非法或重复名称，并恢复最近一次已保存名称。

        保存时仍会再次检查，以覆盖“名称检查完成后，外部程序又创建了同名
        文件”的竞态情况。
        """
        if self._loading or not self.plan_editable:
            return True

        plan_name = self.file_name_input.text().strip()
        error = self._plan_name_error(plan_name)
        target_path = self.tweak_plan_dir / f"{plan_name}.json"
        if (
                error is None
                and target_path.exists()
                and (
                    self.current_path is None
                    or target_path.resolve() != self.current_path.resolve()
                )
        ):
            error = f"微调方案【{plan_name}】已经存在，不能使用重复名称。"

        if error is None:
            return True

        self._loading = True
        self.file_name_input.setText(self.saved_plan_name)
        self._loading = False
        self._refresh_preview()
        QMessageBox.warning(
            self,
            "方案名称不可用",
            f"{error}\n\n名称已恢复为【{self.saved_plan_name}】。",
        )
        return False

    def _save_plan(self) -> None:
        """
        将当前方案保存回微调方案文件夹，并再次查验全部 UUID。

        若用户修改方案名称，保存会同步重命名 JSON 文件；若 UUID 与另一方案
        冲突，只修改当前方案 UUID，不覆盖或删除冲突方案。
        """
        if not self.plan_editable:
            self._show_default_read_only_notice()
            return
        if not self._validate_current_plan_name():
            return

        draft = self._collect_draft()
        messages = draft.validation_messages()
        if messages:
            QMessageBox.warning(self, "无法保存", "\n".join(messages))
            return

        plan_name = self.file_name_input.text().strip()
        name_error = self._plan_name_error(plan_name)
        if name_error:
            QMessageBox.warning(self, "无法保存", name_error)
            return

        target_path = self.tweak_plan_dir / f"{plan_name}.json"
        if (
                target_path.exists()
                and (
                    self.current_path is None
                    or target_path.resolve() != self.current_path.resolve()
                )
        ):
            QMessageBox.warning(
                self,
                "方案名称冲突",
                f"微调方案【{plan_name}】已经存在，请修改方案名称后再保存。",
            )
            return

        excluded_paths = {self.current_path} if self.current_path else set()
        repaired_messages = self._repair_uuid_conflicts(excluded_paths)
        owner = self._find_uuid_owner(draft.plan_uuid, excluded_paths)
        if owner is not None:
            old_uuid = draft.plan_uuid
            draft.plan_uuid = self._generate_unique_uuid(excluded_paths)
            repaired_messages.append(self._uuid_conflict_message(
                plan_name,
                old_uuid,
                owner.stem,
                draft.plan_uuid,
            ))

        draft.version = self.current_tweak_plan_version
        draft.faa_version = self.current_faa_version
        try:
            self.tweak_plan_dir.mkdir(parents=True, exist_ok=True)
            if (
                    self.current_path is not None
                    and self.current_path.exists()
                    and self.current_path.resolve().parent == self.tweak_plan_dir.resolve()
                    and self.current_path.resolve() != target_path.resolve()
            ):
                self.current_path.rename(target_path)
            self._write_plan_mapping(target_path, draft.to_mapping())
        except OSError as error:
            QMessageBox.critical(self, "保存失败", str(error))
            return

        self._load_plan_list()
        self._load_path(target_path)
        self._notify_plan_library_changed()
        self._show_operation_status(f"已保存：{target_path.name}")
        self._show_uuid_conflict_messages(repaired_messages)

    def _delete_plan(self) -> None:
        """确认后把当前方案移入系统回收站；永不永久删除作为失败回退。"""
        if not self.plan_editable or self.current_path is None:
            self._show_default_read_only_notice()
            return
        if self.uuid_input.text() == BUILT_IN_TWEAK_PLAN_UUIDS["!默认"]:
            self._show_default_read_only_notice()
            return

        reply = QMessageBox.question(
            self,
            "确认删除微调方案",
            f"确定将微调方案【{self.current_path.stem}】移入系统回收站吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted_path = self.current_path
        if not QFile.moveToTrash(str(deleted_path)):
            QMessageBox.critical(
                self,
                "删除失败",
                "无法将方案移入系统回收站。为避免永久丢失，文件没有被删除。",
            )
            return

        self._load_plan_list()
        default_path = self.tweak_plan_dir / "!默认.json"
        if default_path.is_file():
            self._load_path(default_path)
        elif self.plan_selector.count() > 0:
            self._load_selected_plan()
        self._notify_plan_library_changed()
        self._show_operation_status(f"已移入回收站：{deleted_path.name}")

    def save_screenshot(self, path: Path) -> None:
        """把当前 Demo 窗口保存为评审截图。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.grab().save(str(path))

    def _apply_style(self) -> None:
        """从当前 QApplication Palette 生成仅负责布局修饰的轻量样式。"""
        palette = self.palette()
        window = palette.color(QPalette.ColorRole.Window)
        text = palette.color(QPalette.ColorRole.WindowText)
        panel = palette.color(QPalette.ColorRole.Base)
        border = palette.color(QPalette.ColorRole.Mid)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        is_dark = window.lightness() < 128
        # 说明小字复用 MidSignalPrint 的使用者色表第 9 级，而不是另造灰色。
        # 该色表的亮色 #999999 / 暗色 #CCCCCC 会与 FAA 主题同步切换。
        helper = QColor(
            f"#{self.get_user_text_color(9, 'dark' if is_dark else 'light')}"
        )
        # 说明文字比主要选项小 1pt，配合使用者色表第 9 级灰色形成轻微层级；
        # 不使用粗体或另外指定字体族，继续继承 FAA 的统一字体。
        base_point_size = self.font().pointSize()
        helper_point_size = max(8, base_point_size - 1) if base_point_size > 0 else 9
        badge_background = _mix_colors(panel, text, 0.94 if is_dark else 0.97)

        def name(color: QColor) -> str:
            """返回供 QSS 使用的 RGB 十六进制颜色。"""
            return color.name(QColor.NameFormat.HexRgb)

        self.setStyleSheet(
            f"""
            QWidget#root {{ background: {name(window)}; color: {name(text)}; }}
            QLabel#pageTitle {{ font-size: 26px; color: {name(text)}; }}
            QLabel#subtitle {{ color: {name(muted)}; }}
            QLabel#helperText {{ color: {name(helper)}; font-size: {helper_point_size}pt; }}
            QLabel#demoBadge {{
                color: {name(muted)}; background: {name(badge_background)}; border: 1px solid {name(border)};
                border-radius: 10px; padding: 5px 10px;
            }}
            QLabel#readOnlyNotice {{
                color: {name(text)}; background: {name(badge_background)};
                border: 1px solid {name(border)}; border-radius: 8px; padding: 8px 12px;
            }}
            QFrame#toolbar {{
                background: {name(panel)}; border: 1px solid {name(border)}; border-radius: 10px;
            }}
            QLabel#validationOk {{ color: {name(muted)}; }}
            QLabel#validationError {{ color: {name(text)}; }}
            QSplitter::handle {{ background: transparent; width: 4px; }}
            QScrollArea {{ background: transparent; }}
            """
        )
        if self.operation_status_label.isVisible():
            self._apply_operation_status_color(
                int(self.operation_status_label.property("colorLevel") or 3)
            )

    def event(self, event: QEvent) -> bool:
        """系统 Palette 改变时重新生成主题感知样式。"""
        result = super().event(event)
        if event.type() in {
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.PaletteChange,
        } and hasattr(self, "theme_selector"):
            QTimer.singleShot(0, self._apply_style)
        return result
