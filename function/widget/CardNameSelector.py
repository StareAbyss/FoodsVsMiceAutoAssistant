"""战斗方案编辑器使用的卡片名称解析与可视化选择组件。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

from PyQt6.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from function.globals.get_paths import PATHS


CARD_TYPE_PATH = os.path.join(PATHS["config"], "card_type.json")
CARD_IMAGE_DIR = os.path.join(PATHS["image"]["card"], "准备房间")
CARD_CATEGORY_PATH = os.path.join(PATHS["config"], "card_stage_categories.json")

CARD_FILE_PATTERN = re.compile(r"^(?P<base>.+)-(?P<stage>\d+)\.png$")
CHINESE_NAME_PATTERN = re.compile(r"^(.*[\u4e00-\u9fff])")
COMPACT_CARD_GRID_WIDTH = 72
PRIMARY_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 20
SECONDARY_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 21
SHRINK_LINE_ROLE = int(Qt.ItemDataRole.UserRole) + 22


def apply_faa_application_style(app: QApplication) -> None:
    """
    应用 FAA 主程序的公共 Qt 初始化，同时保留平台原生样式。

    FAA 主程序没有强制指定 ``Fusion`` 或 ``Windows``，而是只设置全局字体，
    因此这里同样不调用 ``setStyle()``，让 Qt 继续跟随系统样式与 Palette。
    """
    from function.globals import EXTRA

    app.setFont(EXTRA.Q_FONT)
    icon_path = os.path.join(PATHS["logo"], "圆角-FetDeathWing-256x-AllSize.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))


@dataclass
class CardEntry:
    """一张基础卡及当前资源中存在的各阶段图片。"""

    base_name: str
    stage_paths: dict[int, str] = field(default_factory=dict)
    chain_kind: str = "normal"

    def search_text(self) -> str:
        """返回用于具体卡片检索的基础名称。"""
        return self.base_name.casefold()

    def stage_label(self, stage: int) -> str:
        """根据普通卡、金卡或融合卡返回用户可读的阶段名称。"""
        if self.chain_kind == "fusion":
            return {0: "初融", 1: "深融", 2: "灵融"}.get(stage, f"阶段 {stage}")
        if self.chain_kind == "gold":
            return {0: "不转", 1: "三转", 2: "四转", 3: "终转"}.get(stage, f"阶段 {stage}")
        return {
            0: "不转",
            1: "一转",
            2: "二转",
            3: "三转",
            4: "终转",
        }.get(stage, f"阶段 {stage}")


@dataclass(frozen=True)
class CardTypeEntry:
    """``card_type.json`` 中的一组类型别名和候选卡片。"""

    keys: tuple[str, ...]
    values: tuple[str, ...]

    @property
    def canonical_name(self) -> str:
        """返回点击类型时写入方案的首个标准名称。"""
        return self.keys[0]


@dataclass(frozen=True)
class ParseResult:
    """卡片标识名称的解析结果。"""

    kind: str
    title: str
    detail: str
    normalized_name: str
    targets: tuple[str, ...]


class CompactCardItemDelegate(QStyledItemDelegate):
    """分别绘制卡片项的两行文字，只缩小被标记的长文本行。"""

    MINIMUM_POINT_SIZE = 6

    @classmethod
    def fit_font(cls, text: str, base_font: QFont, max_width: int) -> QFont:
        """返回能够放入指定宽度的字体，最小不低于 6pt。"""
        font = QFont(base_font)
        while (
            font.pointSize() > cls.MINIMUM_POINT_SIZE
            and QFontMetrics(font).horizontalAdvance(text) > max_width
        ):
            font.setPointSize(font.pointSize() - 1)
        return font

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """使用系统选中背景，居中绘制图标和两行独立字体的文字。"""
        panel_option = QStyleOptionViewItem(option)
        self.initStyleOption(panel_option, index)
        icon_data = index.data(Qt.ItemDataRole.DecorationRole)
        icon = QIcon(icon_data) if isinstance(icon_data, QIcon) else QIcon()
        icon_size = option.widget.iconSize() if option.widget is not None else panel_option.decorationSize
        panel_option.icon = QIcon()
        panel_option.text = ""
        style = option.widget.style() if option.widget else QApplication.style()

        painter.save()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, panel_option, painter, option.widget)

        content_rect = option.rect.adjusted(2, 2, -2, -2)
        pixmap = icon.pixmap(icon_size)
        if not pixmap.isNull() and pixmap.size() != icon_size:
            pixmap = pixmap.scaled(
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        icon_x = content_rect.center().x() - pixmap.width() // 2
        painter.drawPixmap(icon_x, content_rect.top(), pixmap)

        primary_text = index.data(PRIMARY_TEXT_ROLE) or ""
        secondary_text = index.data(SECONDARY_TEXT_ROLE) or ""
        shrink_line = index.data(SHRINK_LINE_ROLE) or 1
        base_font = QFont(option.font)
        available_width = max(1, content_rect.width())
        primary_font = self.fit_font(primary_text, base_font, available_width) if shrink_line == 1 else base_font
        secondary_font = self.fit_font(secondary_text, base_font, available_width) if shrink_line == 2 else base_font

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        color_role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        painter.setPen(option.palette.color(color_role))

        # 两行文字按真实字体行高紧邻排列，额外高度只留在底部，不夹在两行之间。
        text_top = content_rect.top() + icon_size.height()
        primary_height = QFontMetrics(primary_font).height()
        secondary_height = QFontMetrics(secondary_font).height()
        primary_rect = QRect(content_rect.left(), text_top, content_rect.width(), primary_height)
        secondary_rect = QRect(
            content_rect.left(),
            text_top + primary_height,
            content_rect.width(),
            secondary_height,
        )
        alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
        painter.setFont(primary_font)
        painter.drawText(primary_rect, alignment, primary_text)
        painter.setFont(secondary_font)
        painter.drawText(secondary_rect, alignment, secondary_text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """让实际绘制矩形占满列表设置的网格，避免图标挤压文字区域。"""
        if option.widget is not None:
            grid_size = option.widget.gridSize()
            if grid_size.isValid():
                return grid_size
        return super().sizeHint(option, index)


class CardCatalog:
    """从项目配置和准备房间图片构建可视化卡片目录。"""

    def __init__(
            self,
            card_type_path: str = CARD_TYPE_PATH,
            image_dir: str = CARD_IMAGE_DIR,
            category_path: str = CARD_CATEGORY_PATH,
    ):
        self.card_type_path = card_type_path
        self.image_dir = image_dir
        self.category_path = category_path
        self.cards = self._load_cards()
        self._load_categories()
        self.card_types = self._load_card_types()

    def _load_cards(self) -> dict[str, CardEntry]:
        """只将真实存在的准备房间 PNG 纳入可选卡片。"""
        cards: dict[str, CardEntry] = {}
        if not os.path.isdir(self.image_dir):
            return cards

        for file_name in sorted(os.listdir(self.image_dir)):
            match = CARD_FILE_PATTERN.match(file_name)
            if match is None:
                continue
            base_name = match.group("base")
            stage = int(match.group("stage"))
            entry = cards.setdefault(base_name, CardEntry(base_name=base_name))
            entry.stage_paths[stage] = os.path.join(self.image_dir, file_name)
        return cards

    def _load_categories(self) -> None:
        """读取只包含金卡和融合卡例外项的最小类别表。"""
        if not os.path.isfile(self.category_path):
            return

        with open(self.category_path, encoding="utf-8") as file:
            categories = json.load(file)

        for base_name in categories.get("gold", []):
            if base_name in self.cards:
                self.cards[base_name].chain_kind = "gold"
        for base_name in categories.get("fusion", []):
            if base_name in self.cards:
                self.cards[base_name].chain_kind = "fusion"

    def _load_card_types(self) -> list[CardTypeEntry]:
        """读取 FAA 当前使用的卡片类型配置。"""
        with open(self.card_type_path, encoding="utf-8") as file:
            raw_types = json.load(file)
        return [
            CardTypeEntry(keys=tuple(item["key"]), values=tuple(item["value"]))
            for item in raw_types
            if item.get("key") and item.get("value")
        ]

    def card_path(self, precise_name: str) -> str | None:
        """将 ``基础名-阶段`` 转换为图片路径。"""
        if "-" not in precise_name:
            return None
        base_name, stage_text = precise_name.rsplit("-", 1)
        if not stage_text.isdigit():
            return None
        entry = self.cards.get(base_name)
        return entry.stage_paths.get(int(stage_text)) if entry else None

    def expand_identifier(self, card_name: str) -> tuple[str, tuple[str, ...], CardTypeEntry | None]:
        """
        按 ``FAA._card_name_to_tar_list`` 的规则展开名称。

        Returns:
            tuple: ``(纯中文名称, 实际存在的精准名称列表, 命中的卡片类型)``。
        """
        if card_name == "有效承载":
            return card_name, (), None

        match = CHINESE_NAME_PATTERN.match(card_name)
        chinese_name = match.group(1) if match else ""
        matched_type = next(
            (card_type for card_type in self.card_types if chinese_name in card_type.keys),
            None,
        )
        first_targets = list(matched_type.values) if matched_type else [chinese_name]

        if "-" in card_name:
            second_targets = [card_name]
        else:
            second_targets = []
            for target in first_targets:
                if "-" in target:
                    second_targets.append(target)
                else:
                    entry = self.cards.get(target)
                    if entry is not None:
                        second_targets.extend(
                            f"{target}-{stage}"
                            for stage in sorted(entry.stage_paths, reverse=True)
                        )

        existing_targets = tuple(target for target in second_targets if self.card_path(target) is not None)
        return chinese_name, existing_targets, matched_type

    def parse(self, card_name: str) -> ParseResult:
        """解析输入名称并生成界面所需的分类与说明。"""
        card_name = card_name.strip()
        if not card_name:
            return ParseResult("unresolved", "尚未输入名称", "请输入或从下方选择一张卡片。", "", ())

        if card_name == "有效承载":
            return ParseResult(
                "reserved",
                "关卡动态类型：有效承载",
                "实际候选由当前关卡的承载卡配置决定，独立 Demo 中不展开。",
                card_name,
                (),
            )

        chinese_name, targets, matched_type = self.expand_identifier(card_name)
        if matched_type is not None:
            aliases = " / ".join(matched_type.keys)
            detail = f"命中类型别名：{aliases}；按配置顺序选择当前账号拥有的最高优先级卡片。"
            return ParseResult("type", "解析为卡片类型", detail, chinese_name, targets)

        if targets and "-" in card_name:
            return ParseResult(
                "precise",
                "解析为固定转职卡",
                "自动带卡只会查找这一张精准名称对应的图片。",
                card_name,
                targets,
            )

        if targets:
            return ParseResult(
                "fuzzy",
                "解析为卡片及其所有可用转职",
                "自动带卡会按高阶段到低阶段查找，优先选择可识别的最高阶段。",
                chinese_name,
                targets,
            )

        return ParseResult(
            "unresolved",
            "无法解析到可识别卡片",
            "名称未命中卡片类型，且准备房间图片资源中没有对应卡片。",
            chinese_name,
            (),
        )

    def filter_card_types(self, query: str) -> list[CardTypeEntry]:
        """按类型别名或其子卡片名称筛选卡片类型。"""
        query = query.strip().casefold()
        if not query:
            return self.card_types
        return [
            card_type
            for card_type in self.card_types
            if query in " ".join([*card_type.keys, *card_type.values]).casefold()
        ]

    def filter_cards(self, query: str) -> list[CardEntry]:
        """按准备房间图片文件中的基础名称筛选具体卡片。"""
        query = query.strip().casefold()
        cards = [self.cards[name] for name in sorted(self.cards)]
        if not query:
            return cards
        return [card for card in cards if query in card.search_text()]

    def targets_for_type(self, card_type: CardTypeEntry) -> tuple[str, ...]:
        """返回类型配置经真实图片过滤后的候选列表。"""
        return self.expand_identifier(card_type.canonical_name)[1]


class CardNameSelectorWidget(QWidget):
    """卡片名称解析与可视化选择器，可嵌入编辑器弹窗。"""

    def __init__(self, initial_name: str = "海星", parent: QWidget | None = None):
        super().__init__(parent)
        apply_faa_application_style(QApplication.instance())
        self.catalog = CardCatalog()
        self._icon_cache: dict[str, QIcon] = {}
        self._muted_labels: list[QLabel] = []
        self._build_ui()
        self.name_input.setText(initial_name)
        self._change_mode()

    def _build_ui(self) -> None:
        """创建独立 Demo 的全部控件。"""
        self.setWindowTitle("FAA 卡片名称解析与可视化选择 Demo")
        self.resize(860, 820)
        self.setMinimumSize(820, 680)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(14, 12, 14, 12)
        self.root_layout.setSpacing(9)

        input_row = QHBoxLayout()
        input_label = QLabel("当前名称")
        input_label.setFixedWidth(72)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：海星、炭烧海星、炭烧海星-2")
        self.name_input.setClearButtonEnabled(True)
        subtitle = QLabel("输入名称或从下方选择，解析结果会实时更新。")
        self._muted_labels.append(subtitle)
        input_row.addWidget(input_label)
        input_row.addWidget(self.name_input, 1)
        input_row.addWidget(subtitle)
        self.root_layout.addLayout(input_row)

        self.result_panel = QFrame()
        self.result_panel.setFrameShape(QFrame.Shape.StyledPanel)
        result_layout = QVBoxLayout(self.result_panel)
        result_layout.setContentsMargins(8, 6, 8, 6)
        result_layout.setSpacing(4)
        result_header = QHBoxLayout()
        self.status_badge = QLabel("解析结果")
        self._set_heading_font(self.status_badge, point_size=13)
        result_header.addWidget(self.status_badge)
        self.status_detail = QLabel()
        self.status_detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_detail.setWordWrap(False)
        self._muted_labels.append(self.status_detail)
        result_header.addWidget(self.status_detail, 1)
        self.result_count_label = QLabel()
        self._muted_labels.append(self.result_count_label)
        result_header.addWidget(self.result_count_label)
        result_layout.addLayout(result_header)
        self.parsed_list = QListWidget()
        self._setup_icon_list(
            self.parsed_list,
            icon_size=QSize(58, 72),
            grid_size=QSize(COMPACT_CARD_GRID_WIDTH, 116),
        )
        self.parsed_list.setItemDelegate(CompactCardItemDelegate(self.parsed_list))
        self.parsed_list.setFixedHeight(242)
        result_layout.addWidget(self.parsed_list)
        self.root_layout.addWidget(self.result_panel)

        self.selector_panel = QFrame()
        self.selector_panel.setFrameShape(QFrame.Shape.StyledPanel)
        selector_layout = QVBoxLayout(self.selector_panel)
        selector_layout.setContentsMargins(8, 6, 8, 6)
        selector_layout.setSpacing(5)
        selector_top = QHBoxLayout()
        selector_title = QLabel("卡片选择")
        self._set_heading_font(selector_title, point_size=13)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("按卡片类型", "type")
        self.mode_combo.addItem("按具体卡片", "card")
        self.mode_combo.setFixedWidth(128)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索类型名或类型中的卡片…")
        self.search_input.setClearButtonEnabled(True)
        selector_top.addWidget(selector_title)
        selector_top.addSpacing(14)
        selector_top.addWidget(self.mode_combo)
        selector_top.addWidget(self.search_input, 1)
        self.catalog_count_label = QLabel()
        self._muted_labels.append(self.catalog_count_label)
        selector_top.addWidget(self.catalog_count_label)
        selector_layout.addLayout(selector_top)

        self.selector_content_row = QHBoxLayout()
        self.catalog_list = QListWidget()
        self._setup_icon_list(
            self.catalog_list,
            icon_size=QSize(58, 72),
            grid_size=QSize(COMPACT_CARD_GRID_WIDTH, 116),
        )
        self.catalog_list.setItemDelegate(CompactCardItemDelegate(self.catalog_list))
        self.selector_content_row.addWidget(self.catalog_list, 1)

        self.stage_panel = QFrame()
        self.stage_panel.setFrameShape(QFrame.Shape.StyledPanel)
        stage_layout = QVBoxLayout(self.stage_panel)
        stage_layout.setContentsMargins(7, 6, 7, 6)
        stage_layout.setSpacing(4)
        self.stage_title = QLabel("选择具体卡片后显示阶段")
        self._set_heading_font(self.stage_title, point_size=13)
        self.stage_subtitle = QLabel("点击左侧卡片，默认写入“智能选最高”。")
        self._muted_labels.append(self.stage_subtitle)
        self.stage_subtitle.setWordWrap(True)
        self.stage_list = QListWidget()
        self._setup_icon_list(
            self.stage_list,
            icon_size=QSize(58, 72),
            grid_size=QSize(COMPACT_CARD_GRID_WIDTH, 116),
        )
        self.stage_list.setItemDelegate(CompactCardItemDelegate(self.stage_list))
        # 转职区严格容纳两列：融合卡为 2×2，普通卡和金卡最多为 2×3。
        self.stage_panel.setFixedWidth(self._grid_view_width(self.stage_list, 2) + 16)
        stage_layout.addWidget(self.stage_title)
        stage_layout.addWidget(self.stage_subtitle)
        stage_layout.addWidget(self.stage_list, 1)
        self.selector_content_row.addWidget(self.stage_panel)
        selector_layout.addLayout(self.selector_content_row, 1)
        self.root_layout.addWidget(self.selector_panel, 1)

        self.name_input.textChanged.connect(self._refresh_parse_result)
        self.mode_combo.currentIndexChanged.connect(self._change_mode)
        self.search_input.textChanged.connect(self._refresh_catalog)
        self.catalog_list.itemClicked.connect(self._choose_catalog_item)
        self.stage_list.itemClicked.connect(self._choose_stage)
        self._apply_system_palette()

    @staticmethod
    def _grid_view_width(widget: QListWidget, column_count: int) -> int:
        """按 Qt 当前样式的真实尺寸，计算容纳指定列数所需的列表宽度。"""
        grid_width = widget.gridSize().width()
        scrollbar_extent = widget.style().pixelMetric(
            QStyle.PixelMetric.PM_ScrollBarExtent,
            None,
            widget,
        )
        viewport_margins = widget.viewportMargins()
        chrome_width = (
            widget.frameWidth() * 2
            + viewport_margins.left()
            + viewport_margins.right()
        )
        layout_reserve = scrollbar_extent + max(0, widget.spacing())
        return max(
            grid_width + layout_reserve + chrome_width,
            column_count * grid_width + layout_reserve + chrome_width,
        )

    @staticmethod
    def _set_heading_font(widget: QLabel, point_size: int) -> None:
        """仅调整标题字号和字重，不覆盖系统颜色。"""
        font = QFont(widget.font())
        font.setPointSize(point_size)
        font.setBold(True)
        widget.setFont(font)

    def _apply_system_palette(self) -> None:
        """让辅助文字和状态提示使用当前系统 Palette。"""
        app_palette = QApplication.palette()
        muted_color = app_palette.color(QPalette.ColorRole.PlaceholderText)
        for label in self._muted_labels:
            palette = QPalette(label.palette())
            palette.setColor(QPalette.ColorRole.WindowText, muted_color)
            label.setPalette(palette)

    def event(self, event: QEvent) -> bool:
        """系统运行中切换主题或 Qt 样式时重新应用 Palette 角色。"""
        result = super().event(event)
        if event.type() in {
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        } and hasattr(self, "_muted_labels"):
            QTimer.singleShot(0, self._apply_system_palette)
        return result

    @staticmethod
    def _setup_icon_list(widget: QListWidget, icon_size: QSize, grid_size: QSize) -> None:
        """设置用于卡片缩略图的统一列表样式。"""
        widget.setViewMode(QListWidget.ViewMode.IconMode)
        widget.setFlow(QListWidget.Flow.LeftToRight)
        widget.setWrapping(True)
        widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        widget.setMovement(QListWidget.Movement.Static)
        widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        widget.setIconSize(icon_size)
        widget.setGridSize(grid_size)
        widget.setWordWrap(True)
        widget.setSpacing(1)
        # 避免首行图片紧贴列表框线，同时为底部保留轻微呼吸空间。
        widget.setViewportMargins(2, 6, 2, 4)

    def _card_icon(self, path: str | None) -> QIcon:
        """加载并缓存卡片图片；缺图时显示明确的占位图。"""
        cache_key = path or "__missing__"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        if path and os.path.isfile(path):
            pixmap = QPixmap(path)
        else:
            pixmap = QPixmap(64, 80)
            pixmap.fill(QColor("#e7ebf0"))
            painter = QPainter(pixmap)
            painter.setPen(QColor("#8a96a5"))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "无图片")
            painter.end()
        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    def _refresh_parse_result(self) -> None:
        """根据输入实时刷新解析类型和候选图片。"""
        result = self.catalog.parse(self.name_input.text())
        self.status_detail.setText(result.detail)
        self.result_count_label.setText(f"{len(result.targets)} 个可识别候选")

        self.parsed_list.clear()
        for target in result.targets:
            base_name, stage_text = target.rsplit("-", 1)
            entry = self.catalog.cards.get(base_name)
            stage = int(stage_text)
            stage_label = entry.stage_label(stage) if entry else f"阶段 {stage}"
            item = QListWidgetItem(self._card_icon(self.catalog.card_path(target)), f"{target}\n{stage_label}")
            item.setData(PRIMARY_TEXT_ROLE, target)
            item.setData(SECONDARY_TEXT_ROLE, stage_label)
            item.setData(SHRINK_LINE_ROLE, 1)
            item.setToolTip(target)
            self.parsed_list.addItem(item)

    def _change_mode(self) -> None:
        """切换类型选择与具体卡片选择界面。"""
        card_mode = self.mode_combo.currentData() == "card"
        self.stage_panel.setVisible(card_mode)
        self.search_input.setPlaceholderText(
            "搜索基础卡名或任意进化名称…" if card_mode else "搜索类型名或类型中的卡片…"
        )
        self._refresh_catalog()

    def _refresh_catalog(self) -> None:
        """按当前选择模式和搜索词刷新资源目录。"""
        self.catalog_list.clear()
        query = self.search_input.text()
        if self.mode_combo.currentData() == "type":
            entries = self.catalog.filter_card_types(query)
            for card_type in entries:
                targets = self.catalog.targets_for_type(card_type)
                icon_path = self.catalog.card_path(targets[0]) if targets else None
                item = QListWidgetItem(
                    self._card_icon(icon_path),
                    f"{card_type.canonical_name}\n{len(targets)} 个候选",
                )
                item.setData(Qt.ItemDataRole.UserRole, card_type.canonical_name)
                item.setData(PRIMARY_TEXT_ROLE, card_type.canonical_name)
                item.setData(SECONDARY_TEXT_ROLE, f"{len(targets)} 个候选")
                item.setData(SHRINK_LINE_ROLE, 1)
                other_aliases = card_type.keys[1:]
                item.setToolTip(f"其他别名：{' / '.join(other_aliases) if other_aliases else '无'}")
                self.catalog_list.addItem(item)
        else:
            entries = self.catalog.filter_cards(query)
            for card in entries:
                preview_stage = 0 if 0 in card.stage_paths else min(card.stage_paths)
                item = QListWidgetItem(
                    self._card_icon(card.stage_paths.get(preview_stage)),
                    f"{card.base_name}\n{len(card.stage_paths)} 个阶段",
                )
                item.setData(Qt.ItemDataRole.UserRole, card.base_name)
                item.setData(PRIMARY_TEXT_ROLE, card.base_name)
                item.setData(SECONDARY_TEXT_ROLE, f"{len(card.stage_paths)} 个阶段")
                item.setData(SHRINK_LINE_ROLE, 1)
                precise_names = [f"{card.base_name}-{stage}" for stage in sorted(card.stage_paths)]
                item.setToolTip("可用阶段：" + "、".join(precise_names))
                self.catalog_list.addItem(item)
        self.catalog_count_label.setText(f"显示 {self.catalog_list.count()} 项")

    def _choose_catalog_item(self, item: QListWidgetItem) -> None:
        """选择一个类型，或选择具体卡并默认启用智能选最高。"""
        selected_name = item.data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentData() == "type":
            self.name_input.setText(selected_name)
            return

        card = self.catalog.cards[selected_name]
        self.name_input.setText(card.base_name)
        self._show_card_stages(card)

    def _show_card_stages(self, card: CardEntry) -> None:
        """显示智能选择项和该卡所有可用的固定阶段。"""
        self.stage_title.setText(card.base_name)
        kind_names = {"normal": "普通转职卡", "gold": "金卡", "fusion": "融合卡"}
        self.stage_subtitle.setText(
            f"{kind_names.get(card.chain_kind, '卡片')} · 点击“智能选最高”写入基础名称，"
            "点击具体阶段写入“名称-数字”。"
        )
        self.stage_list.clear()

        preview_stage = 0 if 0 in card.stage_paths else min(card.stage_paths)
        smart_item = QListWidgetItem(
            self._card_icon(card.stage_paths.get(preview_stage)),
            "智能选最高\n自动降级",
        )
        smart_item.setData(Qt.ItemDataRole.UserRole, card.base_name)
        smart_item.setData(PRIMARY_TEXT_ROLE, "智能选最高")
        smart_item.setData(SECONDARY_TEXT_ROLE, "自动降级")
        smart_item.setData(SHRINK_LINE_ROLE, 1)
        smart_item.setToolTip(f"写入 {card.base_name}，FAA 按高阶段到低阶段查找")
        self.stage_list.addItem(smart_item)

        for stage in sorted(card.stage_paths):
            precise_name = f"{card.base_name}-{stage}"
            item = QListWidgetItem(
                self._card_icon(card.stage_paths[stage]),
                f"{card.stage_label(stage)}\n{precise_name}",
            )
            item.setData(Qt.ItemDataRole.UserRole, precise_name)
            item.setData(PRIMARY_TEXT_ROLE, card.stage_label(stage))
            item.setData(SECONDARY_TEXT_ROLE, precise_name)
            item.setData(SHRINK_LINE_ROLE, 2)
            item.setToolTip(f"写入 {precise_name}")
            self.stage_list.addItem(item)

    def _choose_stage(self, item: QListWidgetItem) -> None:
        """把智能名称或精准阶段名称写回顶部输入框。"""
        self.name_input.setText(item.data(Qt.ItemDataRole.UserRole))


def parse_args() -> argparse.Namespace:
    """解析 Demo 启动参数。"""
    parser = argparse.ArgumentParser(description="FAA 卡片名称解析与可视化选择 Demo")
    parser.add_argument("--input", default="海星", help="启动时填入的卡片名称")
    parser.add_argument("--screenshot", help="显示后截图到指定路径并自动退出")
    return parser.parse_args()


def main() -> int:
    """启动 Demo；可用 ``--screenshot`` 做无交互视觉验证。"""
    args = parse_args()
    app = QApplication(sys.argv)
    apply_faa_application_style(app)
    window = CardNameSelectorWidget(initial_name=args.input)
    window.show()

    if args.screenshot:
        screenshot_path = os.path.abspath(args.screenshot)

        def save_screenshot() -> None:
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            window.grab().save(screenshot_path)
            app.quit()

        QTimer.singleShot(500, save_screenshot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
