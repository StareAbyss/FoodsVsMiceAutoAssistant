import ctypes
import re
import sys
from functools import cmp_to_key
from typing import Iterable


def _natural_sort_key(value: str) -> tuple[tuple[int, object], ...]:
    """
    为非 Windows 环境生成数字感知的文件名排序键。

    Args:
        value: 需要参与排序的文件名。

    Returns:
        由文本段和整数段组成的可比较元组。
    """
    sort_key = []
    for part in re.split(r"(\d+)", value):
        if not part:
            continue
        if part.isdecimal():
            sort_key.append((0, int(part)))
        else:
            sort_key.append((1, part.casefold()))
    return tuple(sort_key)


def sort_file_names_like_windows(file_names: Iterable[str]) -> list[str]:
    """
    按 Windows 资源管理器的自然排序规则排列文件名。

    Windows 下直接调用 Shell 的 `StrCmpLogicalW`，确保数字片段和资源管理器
    一样按数值比较。非 Windows 环境使用等价的数字感知规则，方便开发测试。

    Args:
        file_names: 需要排序的文件名序列。

    Returns:
        排序后的新列表，不修改传入序列。
    """
    names = list(file_names)
    if sys.platform != "win32":
        return sorted(names, key=_natural_sort_key)

    compare = ctypes.windll.shlwapi.StrCmpLogicalW
    compare.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
    compare.restype = ctypes.c_int
    return sorted(names, key=cmp_to_key(compare))
