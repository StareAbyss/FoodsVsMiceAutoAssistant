import os
import sys

from function.globals.get_paths import PATHS


def is_frozen():
    return hasattr(sys, 'frozen')


def core_exist():
    c_path = PATHS["model"] + "\\faa_ethical_core.onnx"
    return os.path.exists(c_path)


def ethical_core():
    """
    FAA伦理核心, 返回值为是否启用
    """

    if not is_frozen():
        # 为编译运行 不启用伦理核心
        return False

    if not core_exist():
        # 没有伦理核心
        return False

    return True
