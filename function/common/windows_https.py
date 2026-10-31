"""更新请求的 Windows HTTPS 重试，使用系统 WinHTTP、Schannel 和证书链策略。"""

import ctypes
from email.parser import Parser
from functools import lru_cache
import io
import ssl
import urllib.error
import urllib.parse
import urllib.request


@lru_cache(maxsize=1)
def _winhttp():
    """按指针宽度声明系统接口；仅在 Windows 证书重试实际发生时加载 DLL。"""
    api = ctypes.WinDLL("winhttp.dll", use_last_error=True)
    pointer, dword, string = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p
    signatures = {
        "WinHttpOpen": ([string, dword, string, string, dword], pointer),
        "WinHttpSetTimeouts": ([pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_int),
        "WinHttpConnect": ([pointer, string, ctypes.c_uint16, dword], pointer),
        "WinHttpOpenRequest": ([pointer, string, string, string, string, pointer, dword], pointer),
        "WinHttpSetOption": ([pointer, dword, pointer, dword], ctypes.c_int),
        "WinHttpSendRequest": ([pointer, string, dword, pointer, dword, dword, ctypes.c_size_t], ctypes.c_int),
        "WinHttpReceiveResponse": ([pointer, pointer], ctypes.c_int),
        "WinHttpQueryHeaders": ([pointer, dword, string, pointer, ctypes.POINTER(dword), pointer], ctypes.c_int),
        "WinHttpReadData": ([pointer, pointer, dword, ctypes.POINTER(dword)], ctypes.c_int),
        "WinHttpCloseHandle": ([pointer], ctypes.c_int),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


def _failure():
    """保留系统错误码，让上层仍能区分证书失败、超时及其他网络错误。"""
    code = ctypes.get_last_error()
    if code in {12037, 12038, 12045, 12057, 12169, 12170, 12175, 12179}:
        reason = ssl.SSLCertVerificationError(1, f"Windows certificate validation failed (WinHTTP {code})")
    elif code == 12002:
        reason = TimeoutError("Windows HTTPS 连接超时 (WinHTTP 12002)")
    else:
        reason = OSError(code, f"Windows HTTPS 网络请求失败 (WinHTTP {code})")
    return urllib.error.URLError(reason)


def _proxy(host: str) -> tuple[int, str | None]:
    """沿用现有代理或系统自动代理；不能因重试而静默绕过显式代理。"""
    if urllib.request.proxy_bypass(host):
        return 1, None  # WINHTTP_ACCESS_TYPE_NO_PROXY
    configured = urllib.request.getproxies().get("https")
    if not configured:
        return 4, None  # WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY，Win10/11 支持
    parsed = urllib.parse.urlsplit(configured if "://" in configured else "http://" + configured)
    if parsed.scheme != "http" or parsed.username is not None or parsed.password is not None or not parsed.hostname:
        raise urllib.error.URLError(
            "Windows 证书重试无法沿用当前代理的协议或嵌入式认证信息；未绕过代理，请检查代理与可信证书设置。"
        )
    host_name = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return 3, f"{host_name}:{parsed.port or 80}"  # WINHTTP_ACCESS_TYPE_NAMED_PROXY


class _Response:
    """持有一次系统 HTTPS 请求，提供更新器需要的流式读取与头信息。"""

    def __init__(self, url: str, method: str, headers: dict[str, str], timeout: float):
        self.url, self._handles = url, []
        self._api = _winhttp()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise urllib.error.URLError("Windows 更新请求只接受不含登录信息的 HTTPS 地址。")
        try:
            access, proxy = _proxy(parsed.hostname)
            session = self._keep(self._api.WinHttpOpen("FAA-Updater", access, proxy, None, 0))
            milliseconds = min(max(int(timeout * 1000), 1), 2147483647)
            if not self._api.WinHttpSetTimeouts(session, milliseconds, milliseconds, milliseconds, milliseconds):
                raise _failure()
            connection = self._keep(self._api.WinHttpConnect(session, parsed.hostname, parsed.port or 443, 0))
            path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            self._request = self._keep(self._api.WinHttpOpenRequest(
                connection, method, path, None, None, None, 0x00800000,  # WINHTTP_FLAG_SECURE
            ))
            # 自己处理跳转，防止 HTTPS 降级，以及把 GitHub Token 带到另一个站点。
            policy = ctypes.c_uint32(0)  # WINHTTP_OPTION_REDIRECT_POLICY_NEVER
            if not self._api.WinHttpSetOption(self._request, 88, ctypes.byref(policy), ctypes.sizeof(policy)):
                raise _failure()
            # 更新接口不使用客户端证书，不自动向服务器提供用户证书库中的身份。
            if not self._api.WinHttpSetOption(self._request, 47, None, 0):  # WINHTTP_OPTION_CLIENT_CERT_CONTEXT
                raise _failure()
            lines = []
            for name, value in headers.items():
                if name.lower() in {"host", "connection", "proxy-authorization", "content-length"}:
                    continue
                if any(character in name + value for character in "\r\n"):
                    raise ValueError("更新请求头不能包含换行。")
                lines.append(f"{name}: {value}\r\n")
            header_text = "".join(lines)
            # 保持系统证书、域名和链验证默认开启；不设置任何忽略证书错误的标志。
            if not self._api.WinHttpSendRequest(self._request, header_text, len(header_text), None, 0, 0, 0):
                raise _failure()
            if not self._api.WinHttpReceiveResponse(self._request, None):
                raise _failure()
            length = ctypes.c_uint32()
            if self._api.WinHttpQueryHeaders(self._request, 22, None, None, ctypes.byref(length), None):
                raise urllib.error.URLError("Windows HTTPS 响应缺少请求头。")
            if ctypes.get_last_error() != 122:  # ERROR_INSUFFICIENT_BUFFER
                raise _failure()
            buffer = ctypes.create_unicode_buffer(length.value // ctypes.sizeof(ctypes.c_wchar))
            if not self._api.WinHttpQueryHeaders(self._request, 22, None, buffer, ctypes.byref(length), None):
                raise _failure()
            status, _, fields = buffer.value.partition("\r\n")
            self.status = int(status.split(" ", 2)[1])
            self.headers = Parser().parsestr(fields)
        except Exception:
            self.close()
            raise

    def _keep(self, handle):
        """记录已取得的资源，后续任何阶段失败都能按逆序关闭。"""
        if not handle:
            raise _failure()
        self._handles.append(handle)
        return handle

    def read(self, size: int = -1) -> bytes:
        """按需读取下载块；不指定大小时用于读取完整 API 响应。"""
        if not self._handles:
            raise ValueError("HTTPS 响应已关闭。")
        if size == 0:
            return b""
        if size is None or size < 0:
            parts = []
            while chunk := self.read(64 * 1024):
                parts.append(chunk)
            return b"".join(parts)
        buffer = ctypes.create_string_buffer(min(size, 64 * 1024))
        received = ctypes.c_uint32()
        if not self._api.WinHttpReadData(self._request, buffer, len(buffer), ctypes.byref(received)):
            raise _failure()
        return buffer.raw[:received.value]

    def close(self):
        """关闭本次请求的全部句柄，允许下载重试和文件清理。"""
        while self._handles:
            self._api.WinHttpCloseHandle(self._handles.pop())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def open_windows_https(request: urllib.request.Request, timeout: float):
    """使用系统证书验证重试更新器的 GET/HEAD，保留 HTTP 错误和流式下载语义。

    Schannel 按 Windows 策略验证证书，链引擎可使用缓存及允许的 AIA 网络补链。
    不导入根证书、不修改系统策略；系统不信任的证书仍中断连接。

    Args:
        request: 原更新请求；只支持当前更新链路使用的 GET、HEAD。
        timeout: 每个网络阶段的超时秒数。

    Returns:
        可用于 with 和 read 的系统 HTTPS 响应。

    Raises:
        urllib.error.URLError: 系统验证、代理、传输或跳转失败。
        urllib.error.HTTPError: 服务器返回非成功状态，保留错误体供限流等判断。
    """
    method = request.get_method()
    if method not in {"GET", "HEAD"} or request.data is not None:
        raise urllib.error.URLError("Windows 更新请求只支持 GET 和 HEAD。")
    url, headers = request.full_url, dict(request.header_items())
    for _ in range(6):
        response = _Response(url, method, headers, timeout)
        if response.status in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise urllib.error.URLError("更新下载跳转缺少目标地址。")
            following = urllib.parse.urljoin(url, location)
            old, new = urllib.parse.urlsplit(url), urllib.parse.urlsplit(following)
            if new.scheme != "https":
                raise urllib.error.URLError("更新下载拒绝跳转到未加密地址。")
            if (old.hostname, old.port or 443) != (new.hostname, new.port or 443):
                headers = {name: value for name, value in headers.items() if name.lower() not in {"authorization", "cookie"}}
            url = following
            continue
        if not 200 <= response.status < 300:
            try:
                body = response.read(64 * 1024)
            finally:
                response.close()
            raise urllib.error.HTTPError(url, response.status, "Windows HTTPS 返回错误状态", response.headers, io.BytesIO(body))
        return response
    raise urllib.error.URLError("更新下载跳转次数过多。")
