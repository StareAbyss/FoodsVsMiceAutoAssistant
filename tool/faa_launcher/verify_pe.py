"""只读取 PE 文件，验证启动器没有引入系统之外的运行库。"""

import argparse
import json
import struct
from pathlib import Path


SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "comctl32.dll", "comdlg32.dll", "gdi32.dll",
    "gdiplus.dll", "kernel32.dll", "msvcrt.dll", "ntdll.dll", "ole32.dll",
    "oleaut32.dll", "shell32.dll", "shlwapi.dll", "user32.dll", "uuid.dll",
    "ucrtbase.dll", "version.dll", "winmm.dll", "ws2_32.dll",
}


def inspect_pe(path: Path) -> dict:
    """读取普通、延迟导入表及 CLR 目录，返回 DLL 依赖和违规项。"""
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("文件不是 Windows PE")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    directory = optional + (96 if magic == 0x10B else 112)
    image_base = struct.unpack_from("<I" if magic == 0x10B else "<Q", data, optional + (28 if magic == 0x10B else 24))[0]
    sections = []
    for index in range(section_count):
        size, address, raw_size, raw = struct.unpack_from("<IIII", data, optional + optional_size + index * 40 + 8)
        sections.append((address, max(size, raw_size), raw))

    def offset(address: int) -> int:
        """把映像地址映射到磁盘内容，不加载或执行待检查程序。"""
        for start, size, raw in sections:
            if start <= address < start + size:
                return raw + address - start
        return address

    def string(address: int) -> str:
        """读取导入描述符里的 DLL 名称。"""
        start = offset(address)
        return data[start:data.index(b"\0", start)].decode("ascii")

    imports, delayed = [], []
    address = struct.unpack_from("<I", data, directory + 8)[0]
    if address:
        cursor = offset(address)
        while any(fields := struct.unpack_from("<IIIII", data, cursor)):
            imports.append(string(fields[3]))
            cursor += 20
    address = struct.unpack_from("<I", data, directory + 13 * 8)[0]
    if address:
        cursor = offset(address)
        while any(fields := struct.unpack_from("<IIIIIIII", data, cursor)):
            delayed.append(string(fields[1] if fields[0] & 1 else fields[1] - image_base))
            cursor += 32
    clr = struct.unpack_from("<I", data, directory + 14 * 8)[0]
    violations = [name for name in imports + delayed if name.lower() not in SYSTEM_DLLS and not name.lower().startswith(("api-ms-win-", "ext-ms-win-"))]
    if clr:
        violations.append("CLR/.NET")
    return {"path": str(path.resolve()), "architecture": "x86" if magic == 0x10B else "x64",
            "imports": imports, "delay_imports": delayed, "clr": bool(clr), "violations": violations}


def main() -> None:
    """打印可归档的检查结果；存在外部 DLL 或 CLR 时返回失败。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    report = inspect_pe(args.executable)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report["violations"]))


if __name__ == "__main__":
    main()
