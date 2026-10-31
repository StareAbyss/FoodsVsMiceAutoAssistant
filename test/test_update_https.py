"""通过本机 HTTPS 服务验证更新连接的 CA 追加、域名校验和信任失败。"""

from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

from function.common import update_manifest, update_staging, windows_https


class LocalHttpsFixture:
    """仅生成隔离测试 CA；不修改 Windows 证书库，也不依赖新的 Python 包。"""

    def __init__(self):
        executable = shutil.which("openssl")
        if not executable:
            git = shutil.which("git")
            candidate = Path(git).resolve().parents[1] / "usr/bin/openssl.exe" if git else None
            if candidate and candidate.is_file():
                executable = str(candidate)
        if not executable:
            raise unittest.SkipTest("需要开发环境的 OpenSSL 工具生成本机 HTTPS 夹具")
        self.directory = tempfile.TemporaryDirectory(prefix="faa_https_tls_")
        self.root = Path(self.directory.name)
        self.servers = []
        self.real_context = ssl.create_default_context
        self.real_request = urllib.request.Request

        def openssl(*arguments):
            subprocess.run([executable, *map(str, arguments)], check=True, timeout=30,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", self.root / "leaf.key",
                    "-out", self.root / "leaf.csr", "-subj", "/CN=localhost")
            extensions = self.root / "leaf.ext"
            extensions.write_text(
                "subjectAltName=DNS:localhost\nbasicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n",
                encoding="ascii",
            )
            for serial, name in enumerate(("system", "additional", "unknown"), start=1):
                openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                        "-keyout", self.root / f"{name}.key", "-out", self.ca(name),
                        "-subj", f"/CN=FAA Test {name}", "-addext", "basicConstraints=critical,CA:TRUE",
                        "-addext", "keyUsage=critical,keyCertSign,cRLSign")
                openssl("x509", "-req", "-in", self.root / "leaf.csr", "-CA", self.ca(name),
                        "-CAkey", self.root / f"{name}.key", "-set_serial", str(serial), "-days", "2",
                        "-out", self.root / f"{name}.leaf.pem", "-extfile", extensions)
        except Exception:
            self.close()
            raise

    def ca(self, name):
        return self.root / f"{name}.ca.pem"

    def system_context(self):
        """用一张隔离 CA 代表已有系统信任，真实执行 OpenSSL 的证书验证。"""
        return self.real_context(cafile=str(self.ca("system")))

    def start(self, name, payload=b"fixture", redirect=None):
        """建立仅监听回环地址的 TLS 服务，可真实跨端口重定向。"""
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302 if redirect else 200)
                if redirect:
                    self.send_header("Location", redirect)
                self.send_header("Content-Length", str(0 if redirect else len(payload)))
                self.end_headers()
                if not redirect:
                    self.wfile.write(payload)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.root / f"{name}.leaf.pem", self.root / "leaf.key")
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return f"https://localhost:{server.server_port}/fixture"

    def route_request(self, destination):
        """只把 GitHub URL 路由到本机，urlopen、重定向和 TLS 握手不被替换。"""
        def request(url, *args, **kwargs):
            if str(url).startswith(("https://github.com/", "https://api.github.com/")):
                url = destination
            return self.real_request(url, *args, **kwargs)
        return request

    def augmented_environment(self):
        """替换本次进程的 CA 来源，不写全局信任或关闭证书校验。"""
        stack = ExitStack()
        stack.enter_context(patch.object(ssl, "create_default_context", side_effect=self.system_context))
        stack.enter_context(patch("certifi.where", return_value=str(self.ca("additional"))))
        return stack

    def close(self):
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.directory.cleanup()


class UpdateHttpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tls = LocalHttpsFixture()

    @classmethod
    def tearDownClass(cls):
        cls.tls.close()

    def test_additional_ca_allows_verified_redirect_without_replacing_system_roots(self):
        """原有 CA 与补充 CA 各保护一跳，下载和 API 都使用真实校验后的连接。"""
        payload = b"PK\x03\x04verified source archive"
        additional = self.tls.start("additional", payload)
        original = self.tls.start("system", redirect=additional)
        with self.assertRaises(urllib.error.URLError) as rejected:
            urllib.request.urlopen(additional, context=self.tls.system_context(), timeout=3)
        self.assertIsInstance(rejected.exception.reason, ssl.SSLCertVerificationError)
        with self.tls.augmented_environment():
            context = update_manifest.create_https_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            with patch.object(urllib.request, "Request", side_effect=self.tls.route_request(original)):
                destination = self.tls.root / "source.zip"
                update_staging.download_github_archive("a" * 40, destination, retries=0)
            self.assertEqual(destination.read_bytes(), payload)
            api = self.tls.start("additional", b'{"verified": true}')
            with patch.object(urllib.request, "Request", side_effect=self.tls.route_request(api)):
                self.assertEqual(update_manifest.GitHubClient(token="fixture-token").request_json("/fixture", retries=0), {"verified": True})

    def test_wrong_hostname_and_unknown_issuer_remain_rejected(self):
        additional = self.tls.start("additional").replace("localhost", "127.0.0.1")
        unknown = self.tls.start("unknown")
        for name, endpoint in (("hostname", additional), ("issuer", unknown)):
            with self.subTest(failure=name), self.tls.augmented_environment(), \
                    patch.object(urllib.request, "Request", side_effect=self.tls.route_request(endpoint)):
                destination = self.tls.root / f"rejected-{name}.zip"
                destination.write_bytes(b"partial download")
                with self.assertRaises(urllib.error.URLError) as rejected:
                    update_staging.download_github_archive("a" * 40, destination, retries=0)
                self.assertIsInstance(rejected.exception.reason, ssl.SSLCertVerificationError)
                self.assertFalse(destination.exists())

    def test_missing_certifi_keeps_system_validation_and_invalid_bundle_is_explicit(self):
        trusted = self.tls.start("system")
        unknown = self.tls.start("unknown")
        with patch.object(ssl, "create_default_context", side_effect=self.tls.system_context), \
                patch.dict(sys.modules, {"certifi": None}):
            context = update_manifest.create_https_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            with urllib.request.urlopen(trusted, context=context, timeout=3) as response:
                self.assertEqual(response.read(), b"fixture")
            with self.assertRaises(urllib.error.URLError) as rejected:
                urllib.request.urlopen(unknown, context=context, timeout=3)
            self.assertIsInstance(rejected.exception.reason, ssl.SSLCertVerificationError)
        invalid = self.tls.root / "invalid.pem"
        invalid.write_text("not a certificate bundle", encoding="ascii")
        with patch.object(ssl, "create_default_context", side_effect=self.tls.system_context), \
                patch("certifi.where", return_value=str(invalid)):
            with self.assertRaisesRegex(urllib.error.URLError, "HTTPS.*证书") as rejected:
                update_manifest.create_https_context()
            self.assertIsNotNone(rejected.exception.__cause__)


@unittest.skipUnless(sys.platform == "win32", "需要 Windows 系统验证重试分支")
class WindowsHttpsRetryTests(unittest.TestCase):
    def test_only_certificate_failures_trigger_system_retry(self):
        """只对信任问题换验证栈，普通网络或 HTTP 失败继续保留原有语义。"""
        request = urllib.request.Request("https://api.github.com/fixture")
        original = urllib.error.URLError(ssl.SSLCertVerificationError(1, "test issuer missing"))
        response, progress = object(), Mock()
        with patch.object(urllib.request, "urlopen", side_effect=original), \
                patch.object(windows_https, "open_windows_https", return_value=response) as native:
            self.assertIs(update_manifest.open_update_url(request, 4, progress), response)
        native.assert_called_once_with(request, 4)
        progress.assert_called_once_with()
        # Python 本地证书包损坏也不能阻止系统使用自己的信任库验证。
        with patch.object(update_manifest, "create_https_context", side_effect=update_manifest._CertificateStoreError("bad CA bundle")), \
                patch.object(windows_https, "open_windows_https", return_value=response) as native:
            self.assertIs(update_manifest.open_update_url(request, 4), response)
        native.assert_called_once_with(request, 4)
        for failure in (urllib.error.URLError(TimeoutError("timeout")),
                        urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)):
            with self.subTest(error=type(failure).__name__), \
                    patch.object(urllib.request, "urlopen", side_effect=failure), \
                    patch.object(windows_https, "open_windows_https") as native:
                with self.assertRaises(urllib.error.URLError) as error:
                    update_manifest.open_update_url(request, 4)
                self.assertIs(error.exception, failure)
                native.assert_not_called()

    def test_system_failure_preserves_python_error_and_rate_limit_response(self):
        """失败日志包含两次验证原因；系统 HTTP 403 仍能被 API 识别为限流。"""
        request = urllib.request.Request("https://api.github.com/fixture")
        original = urllib.error.URLError(ssl.SSLCertVerificationError(1, "test issuer missing"))
        system = urllib.error.URLError(ssl.SSLCertVerificationError(1, "system issuer missing"))
        with patch.object(urllib.request, "urlopen", side_effect=original), \
                patch.object(windows_https, "open_windows_https", side_effect=system):
            with self.assertRaises(urllib.error.URLError) as error:
                update_manifest.open_update_url(request, 4)
            self.assertIs(error.exception.__cause__, original)
        response = Mock(status=403, headers={})
        response.read.return_value = b'{"message":"API rate limit exceeded"}'
        client = update_manifest.GitHubClient()
        client.token = None
        with patch.object(urllib.request, "urlopen", side_effect=original), \
                patch.object(windows_https, "_Response", return_value=response):
            with self.assertRaises(update_manifest.GitHubRateLimitError):
                client.request_json("/fixture", retries=0)
        response.close.assert_called_once()

    def test_system_redirect_protects_credentials_and_rejects_plain_http(self):
        """系统连接跨域时剥离 Token 和 Cookie，并禁止降级到 HTTP。"""
        request = urllib.request.Request("https://github.com/source", headers={
            "Authorization": "Bearer fixture-only", "Cookie": "fixture-only", "User-Agent": "FAA-test",
        })
        redirect = Mock(status=302, headers={"Location": "https://codeload.github.com/archive.zip"})
        success = Mock(status=200)
        with patch.object(windows_https, "_Response", side_effect=[redirect, success]) as opened:
            self.assertIs(windows_https.open_windows_https(request, 4), success)
        sent = {name.lower(): value for name, value in opened.call_args_list[1].args[2].items()}
        self.assertNotIn("authorization", sent)
        self.assertNotIn("cookie", sent)
        self.assertEqual(sent["user-agent"], "FAA-test")
        redirect.close.assert_called_once()
        insecure = Mock(status=302, headers={"Location": "http://codeload.github.com/archive.zip"})
        with patch.object(windows_https, "_Response", return_value=insecure):
            with self.assertRaisesRegex(urllib.error.URLError, "未加密"):
                windows_https.open_windows_https(request, 4)
        insecure.close.assert_called_once()

    def test_system_retry_preserves_proxy_selection(self):
        """不能因系统重试改为直连，也不能向服务器误发代理密码。"""
        with patch.object(urllib.request, "proxy_bypass", return_value=False), \
                patch.object(urllib.request, "getproxies", return_value={"https": "http://127.0.0.1:7890"}):
            self.assertEqual(windows_https._proxy("github.com"), (3, "127.0.0.1:7890"))
        with patch.object(urllib.request, "proxy_bypass", return_value=True):
            self.assertEqual(windows_https._proxy("github.com"), (1, None))
        for proxy in ("socks5://127.0.0.1:7890", "http://user:password@127.0.0.1:7890"):
            with self.subTest(proxy=proxy.split(":", 1)[0]), \
                    patch.object(urllib.request, "proxy_bypass", return_value=False), \
                    patch.object(urllib.request, "getproxies", return_value={"https": proxy}):
                with self.assertRaisesRegex(urllib.error.URLError, "未绕过代理") as error:
                    windows_https._proxy("github.com")
                self.assertNotIn("password", str(error.exception))


if __name__ == "__main__":
    unittest.main()
