"""微调方案编辑器独立 Demo 使用的亮色与暗色预览 Palette。"""

from PyQt6.QtGui import QColor, QPalette


def create_theme_palette(theme: str) -> QPalette:
    """创建不依赖系统强调色的 Demo 亮色或暗色调色板。

    高饱和的系统主题色（例如红色）不适合作为大量控件的选中底色，因此
    两套固定主题仅使用中性灰作为 Highlight；导入、保存等状态提示仍使用
    FAA 的用户文字色表。
    """
    if theme not in {"light", "dark"}:
        raise ValueError(f"不支持的 FAA 主题: {theme}")

    palette = QPalette()
    if theme == "dark":
        colors = {
            QPalette.ColorRole.Window: "#202124",
            QPalette.ColorRole.WindowText: "#F1F3F4",
            QPalette.ColorRole.Base: "#292A2D",
            QPalette.ColorRole.AlternateBase: "#303134",
            QPalette.ColorRole.ToolTipBase: "#303134",
            QPalette.ColorRole.ToolTipText: "#F1F3F4",
            QPalette.ColorRole.Text: "#F1F3F4",
            QPalette.ColorRole.Button: "#303134",
            QPalette.ColorRole.ButtonText: "#F1F3F4",
            QPalette.ColorRole.BrightText: "#FFFFFF",
            QPalette.ColorRole.Link: "#8AB4F8",
            QPalette.ColorRole.Highlight: "#747A84",
            QPalette.ColorRole.HighlightedText: "#FFFFFF",
            QPalette.ColorRole.PlaceholderText: "#9AA0A6",
            QPalette.ColorRole.Mid: "#5F6368",
            QPalette.ColorRole.Dark: "#171717",
            QPalette.ColorRole.Light: "#3C4043",
        }
        disabled_text = QColor("#777B80")
    else:
        colors = {
            QPalette.ColorRole.Window: "#F3F3F3",
            QPalette.ColorRole.WindowText: "#202124",
            QPalette.ColorRole.Base: "#FFFFFF",
            QPalette.ColorRole.AlternateBase: "#F6F7F9",
            QPalette.ColorRole.ToolTipBase: "#FFFFFF",
            QPalette.ColorRole.ToolTipText: "#202124",
            QPalette.ColorRole.Text: "#202124",
            QPalette.ColorRole.Button: "#F7F7F7",
            QPalette.ColorRole.ButtonText: "#202124",
            QPalette.ColorRole.BrightText: "#FFFFFF",
            QPalette.ColorRole.Link: "#2457C5",
            QPalette.ColorRole.Highlight: "#6B7280",
            QPalette.ColorRole.HighlightedText: "#FFFFFF",
            QPalette.ColorRole.PlaceholderText: "#6C768A",
            QPalette.ColorRole.Mid: "#C9CED8",
            QPalette.ColorRole.Dark: "#9CA3AF",
            QPalette.ColorRole.Light: "#FFFFFF",
        }
        disabled_text = QColor("#9AA1AC")

    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    return palette
