"""卡片名称选择组件的独立启动入口。"""

from function.widget.CardNameSelector import (
    PRIMARY_TEXT_ROLE,
    SECONDARY_TEXT_ROLE,
    SHRINK_LINE_ROLE,
    CardCatalog,
    CardNameSelectorWidget,
    CompactCardItemDelegate,
    apply_faa_application_style,
    main,
)


# 保留原 Demo 类名，已有启动命令和测试无需改变。
CardNameSelectorDemo = CardNameSelectorWidget


if __name__ == "__main__":
    raise SystemExit(main())
