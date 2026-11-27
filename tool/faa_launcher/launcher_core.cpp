#include "launcher_core.h"
#include <bcrypt.h>
#include <algorithm>
#include <cwctype>
#include <sstream>
#include <memory>

namespace faa {
namespace {
struct Handle {
    HANDLE value;
    explicit Handle(HANDLE handle = NULL) : value(handle) {}
    ~Handle() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
};
std::wstring Trim(const std::wstring& value) {
    const size_t first = value.find_first_not_of(L" \t\r\n\ufeff");
    if (first == std::wstring::npos) return L"";
    return value.substr(first, value.find_last_not_of(L" \t\r\n") - first + 1);
}
struct EnvironmentLess {
    bool operator()(const std::wstring& a, const std::wstring& b) const { return _wcsicmp(a.c_str(), b.c_str()) < 0; }
};
std::vector<wchar_t> EnvironmentBlock(const std::map<std::wstring, std::wstring>& changes) {
    std::map<std::wstring, std::wstring, EnvironmentLess> values;
    LPWCH inherited = GetEnvironmentStringsW();
    if (inherited) {
        for (const wchar_t* entry = inherited; *entry; entry += wcslen(entry) + 1) {
            std::wstring item(entry);
            const size_t separator = item.find(L'=', item[0] == L'=' ? 1 : 0);
            if (separator != std::wstring::npos) values[item.substr(0, separator)] = item.substr(separator + 1);
        }
        FreeEnvironmentStringsW(inherited);
    }
    for (const auto& change : changes) values[change.first] = change.second;
    std::vector<wchar_t> block;
    for (const auto& item : values) {
        const std::wstring entry = item.first + L"=" + item.second;
        block.insert(block.end(), entry.begin(), entry.end());
        block.push_back(0);
    }
    block.push_back(0);
    if (block.size() == 1) block.push_back(0);
    return block;
}
}

std::wstring Join(const std::wstring& parent, const std::wstring& name) {
    if (parent.empty()) return name;
    return parent + (parent.back() == L'\\' || parent.back() == L'/' ? L"" : L"\\") + name;
}
std::wstring Parent(const std::wstring& path) {
    const size_t last = path.find_last_of(L"\\/");
    return last == std::wstring::npos ? L"" : path.substr(0, last);
}
std::wstring ExePath() {
    std::vector<wchar_t> path(32768);
    DWORD size = GetModuleFileNameW(NULL, path.data(), static_cast<DWORD>(path.size()));
    return std::wstring(path.data(), size);
}
std::wstring SystemExe(const wchar_t* name) {
    wchar_t directory[MAX_PATH] = {};
    GetSystemDirectoryW(directory, MAX_PATH);
    return Join(directory, name);
}
bool Exists(const std::wstring& path) { return GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES; }
bool IsDirectory(const std::wstring& path) {
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY);
}
bool MakeDirectories(const std::wstring& path) {
    if (IsDirectory(path)) return true;
    const std::wstring parent = Parent(path);
    if (!parent.empty() && parent != path && !IsDirectory(parent) && !MakeDirectories(parent)) return false;
    return CreateDirectoryW(path.c_str(), NULL) || GetLastError() == ERROR_ALREADY_EXISTS;
}
std::string Utf8(const std::wstring& text) {
    if (text.empty()) return "";
    int size = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), NULL, 0, NULL, NULL);
    std::string output(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), &output[0], size, NULL, NULL);
    return output;
}
std::wstring Wide(const std::string& text) {
    if (text.empty()) return L"";
    int size = MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), NULL, 0);
    std::wstring output(size, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), &output[0], size);
    return output;
}
std::string ReadFileBytes(const std::wstring& path) {
    Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL));
    if (file.value == INVALID_HANDLE_VALUE) return "";
    std::string output;
    char buffer[16384];
    DWORD read = 0;
    while (ReadFile(file.value, buffer, sizeof(buffer), &read, NULL) && read) output.append(buffer, read);
    return output;
}
bool WriteFileBytes(const std::wstring& path, const std::string& text) {
    Handle file(CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL));
    if (file.value == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    return WriteFile(file.value, text.data(), static_cast<DWORD>(text.size()), &written, NULL) && written == text.size();
}
std::wstring SystemError(DWORD code) {
    wchar_t* message = NULL;
    FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL, code, 0, reinterpret_cast<wchar_t*>(&message), 0, NULL);
    std::wstring result = message ? Trim(message) : L"未知系统错误";
    if (message) LocalFree(message);
    return result + L"（系统错误 " + std::to_wstring(code) + L"）";
}
std::wstring QuoteArgument(const std::wstring& argument) {
    if (!argument.empty() && argument.find_first_of(L" \t\n\r\"") == std::wstring::npos) return argument;
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t character : argument) {
        if (character == L'\\') { ++slashes; continue; }
        if (character == L'"') {
            result.append(slashes * 2 + 1, L'\\');
        } else result.append(slashes, L'\\');
        result.push_back(character);
        slashes = 0;
    }
    result.append(slashes * 2, L'\\');
    return result + L"\"";
}
std::wstring ReadTomlString(const std::string& content, const std::wstring& section, const std::wstring& key) {
    // Python 尚未准备好时仅需读取发行包内的双引号字符串；不把这个读取器当作通用 TOML 解析器。
    std::wistringstream input(Wide(content));
    std::wstring line, current;
    while (std::getline(input, line)) {
        line = Trim(line);
        if (line.empty() || line[0] == L'#') continue;
        if (line[0] == L'[') {
            const size_t start = line.find_first_not_of(L'[');
            const size_t end = line.find(L']', start);
            current = end == std::wstring::npos ? L"" : Trim(line.substr(start, end - start));
            continue;
        }
        if (current != section) continue;
        const size_t equals = line.find(L'=');
        if (equals == std::wstring::npos || Trim(line.substr(0, equals)) != key) continue;
        const std::wstring value = Trim(line.substr(equals + 1));
        if (!value.empty() && value[0] == L'"') {
            const size_t end = value.find(L'"', 1);
            if (end != std::wstring::npos) return value.substr(1, end - 1);
        }
    }
    return L"";
}
std::wstring FindProjectRoot(const std::wstring& start) {
    std::wstring directory = start;
    for (int depth = 0; depth < 10 && !directory.empty(); ++depth) {
        if (Exists(Join(directory, L"pyproject.toml")) && Exists(Join(directory, L"function\\faa_main.py"))) return directory;
        directory = Parent(directory);
    }
    return L"";
}
std::wstring Timestamp() {
    SYSTEMTIME time;
    GetLocalTime(&time);
    wchar_t output[64];
    swprintf(output, 64, L"%04u%02u%02u-%02u%02u%02u-%03u", time.wYear, time.wMonth, time.wDay,
        time.wHour, time.wMinute, time.wSecond, time.wMilliseconds);
    return output;
}
std::wstring Sha256(const std::wstring& path) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0) < 0) return L"";
    DWORD objectSize = 0, returned = 0;
    BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&objectSize), sizeof(objectSize), &returned, 0);
    std::vector<unsigned char> object(objectSize), digest(32);
    bool success = BCryptCreateHash(algorithm, &hash, object.data(), objectSize, NULL, 0, 0) >= 0;
    Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL));
    success = success && file.value != INVALID_HANDLE_VALUE;
    unsigned char buffer[65536];
    DWORD read = 0;
    while (success) {
        if (!ReadFile(file.value, buffer, sizeof(buffer), &read, NULL)) { success = false; break; }
        if (!read) break;
        success = BCryptHashData(hash, buffer, read, 0) >= 0;
    }
    if (success) success = BCryptFinishHash(hash, digest.data(), 32, 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    if (!success) return L"";
    static const wchar_t* digits = L"0123456789ABCDEF";
    std::wstring output;
    for (unsigned char value : digest) { output.push_back(digits[value >> 4]); output.push_back(digits[value & 15]); }
    return output;
}

ProcessResult RunProcess(const std::wstring& executable, const std::vector<std::wstring>& arguments,
    const std::wstring& cwd, const std::map<std::wstring, std::wstring>& environment, HANDLE cancel,
    const std::function<void(const std::wstring&)>& onLog) {
    ProcessResult result;
    SECURITY_ATTRIBUTES security = { sizeof(security), NULL, TRUE };
    HANDLE read = NULL, write = NULL;
    if (!CreatePipe(&read, &write, &security, 0)) { result.systemError = GetLastError(); return result; }
    Handle reader(read), writer(write);
    SetHandleInformation(reader.value, HANDLE_FLAG_INHERIT, 0);
    Handle input(CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &security, OPEN_EXISTING, 0, NULL));
    Handle job(CreateJobObjectW(NULL, NULL));
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job.value || !SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        result.systemError = GetLastError(); return result;
    }
    std::wstring command = QuoteArgument(executable);
    for (const auto& argument : arguments) command += L" " + QuoteArgument(argument);
    std::vector<wchar_t> commandBuffer(command.begin(), command.end());
    commandBuffer.push_back(0);
    std::vector<wchar_t> block = EnvironmentBlock(environment);
    STARTUPINFOW startup = {};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input.value;
    startup.hStdOutput = startup.hStdError = writer.value;
    PROCESS_INFORMATION process = {};
    if (!CreateProcessW(executable.c_str(), commandBuffer.data(), NULL, NULL, TRUE,
        CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT | CREATE_SUSPENDED, block.data(), cwd.c_str(), &startup, &process)) {
        result.systemError = GetLastError(); return result;
    }
    Handle processHandle(process.hProcess), threadHandle(process.hThread);
    // 先分配 Job 再恢复进程，避免取消时漏掉已经派生的下载或安装子进程。
    if (!AssignProcessToJobObject(job.value, process.hProcess)) {
        result.systemError = GetLastError(); TerminateProcess(process.hProcess, 1); return result;
    }
    CloseHandle(writer.value);
    writer.value = NULL;
    if (ResumeThread(process.hThread) == static_cast<DWORD>(-1)) { result.systemError=GetLastError(); return result; }
    std::string pending;
    auto emitLines = [&](bool flush) {
        size_t end;
        while ((end = pending.find_first_of("\r\n")) != std::string::npos) {
            std::string line = pending.substr(0, end);
            pending.erase(0, end + 1);
            if (!line.empty() && onLog) onLog(Wide(line));
        }
        if (flush && !pending.empty()) { if (onLog) onLog(Wide(pending)); pending.clear(); }
    };
    for (;;) {
        if (cancel && WaitForSingleObject(cancel, 0) == WAIT_OBJECT_0) {
            result.cancelled = true;
            TerminateJobObject(job.value, ERROR_CANCELLED);
            WaitForSingleObject(process.hProcess, 5000);
        }
        DWORD available = 0;
        while (PeekNamedPipe(reader.value, NULL, 0, NULL, &available, NULL) && available) {
            char buffer[8192]; DWORD count = 0;
            if (!ReadFile(reader.value, buffer, std::min<DWORD>(available, sizeof(buffer)), &count, NULL) || !count) break;
            // 分块读到半个 UTF-8 字符时先保留字节，直到完整的一行再转换，避免中文被截坏。
            pending.append(buffer, count);
            result.output.append(buffer, count);
            if (result.output.size() > 256 * 1024) result.output.erase(0, result.output.size() - 256 * 1024);
            if (pending.size() > 64 * 1024) emitLines(true);
            emitLines(false);
        }
        if (WaitForSingleObject(process.hProcess, 30) == WAIT_OBJECT_0 || result.cancelled) {
            // 根进程已结束后只排空现有输出，不等待可能被后代继承的管道关闭。
            if (!PeekNamedPipe(reader.value, NULL, 0, NULL, &available, NULL) || !available) break;
        }
    }
    emitLines(true);
    GetExitCodeProcess(process.hProcess, &result.exitCode);
    return result;
}

Problem ClassifyProblem(const std::string& output, int stage) {
    std::string text(output);
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) { return static_cast<char>(tolower(c)); });
    if (text.find("lockfile") != std::string::npos || text.find("lock file") != std::string::npos || text.find("--locked") != std::string::npos) return Problem::LockMismatch;
    if (text.find("no space") != std::string::npos || text.find("disk full") != std::string::npos || text.find("os error 112") != std::string::npos) return Problem::Disk;
    if (text.find("permission denied") != std::string::npos || text.find("access is denied") != std::string::npos || text.find("os error 5") != std::string::npos) return Problem::Permission;
    if (text.find("timed out") != std::string::npos || text.find("timeout") != std::string::npos || text.find("connect") != std::string::npos || text.find("dns") != std::string::npos || text.find("certificate") != std::string::npos || text.find("download") != std::string::npos) return Problem::Network;
    if (stage == 0 || stage == 1) return Problem::Files;
    if (stage == 3) return Problem::Dependency;
    if (stage == 4) return Problem::Startup;
    return Problem::Other;
}
std::wstring ProblemAdvice(Problem problem) {
    switch (problem) {
    case Problem::Files: return L"确认安装器位于 FAA 根目录；如果安装文件损坏，请重新解压完整安装包后再试。";
    case Problem::Network: return L"打开网络设置，更换当前步骤使用的 Python 下载源或依赖包下载源，然后重试这一步。";
    case Problem::Permission: return L"请关闭占用 FAA 文件的程序，并确认当前 FAA 根目录可写后重试。";
    case Problem::Disk: return L"请释放 FAA 所在磁盘和系统缓存磁盘的空间，再重试这一步。";
    case Problem::LockMismatch: return L"安装包的依赖清单不一致。请重新解压完整安装包；本程序不会重新生成锁文件。";
    case Problem::Dependency: return L"先重试；仍失败时可修复依赖。修复按安装包指定版本重新安装，不会删除您的配置。";
    case Problem::Compatibility: return L"选择检测项查看处理建议。系统或驱动问题处理后重试；组件缺失时可修复依赖。";
    case Problem::Startup: return L"请查看启动日志中的具体错误。若提示模块缺失，可先修复依赖再启动。";
    default: return L"请查看下方运行详情；可以保存日志用于排查，也可以重试这一步。";
    }
}
bool ValidNetworkUrl(const std::wstring& value, bool allowEmpty) {
    if (value.empty()) return allowEmpty;
    if (value.find_first_of(L"\r\n\t ") != std::wstring::npos) return false;
    const size_t start=value.find(L"https://")==0?8:value.find(L"http://")==0?7:std::wstring::npos;
    if(start==std::wstring::npos||value.size()<=start) return false;
    const size_t end=value.find_first_of(L"/?#",start);
    return (end==std::wstring::npos?value.size():end)>start;
}

int RunFixtureChild(const std::vector<std::wstring>& args) {
    if (args.size() > 2 && args[2] == L"wait") { Sleep(10000); return 0; }
    std::string text;
    for (size_t index = 2; index < args.size(); ++index) text += Utf8(args[index]) + "\n";
    wchar_t marker[128] = {};
    GetEnvironmentVariableW(L"FAA_NATIVE_TEST", marker, 128);
    text += "ENV=" + Utf8(marker) + "\n";
    DWORD written;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), text.data(), static_cast<DWORD>(text.size()), &written, NULL);
    return 17;
}

int RunCoreSelfTests(const std::wstring& reportPath) {
    std::ostringstream report;
    int failures = 0;
    auto check = [&](bool passed, const char* name) { report << (passed ? "PASS " : "FAIL ") << name << "\n"; if (!passed) ++failures; };
    check(ReadTomlString("[tool.uv]\npython-install-mirror = \"https://test.example/python\" # note\n[[tool.uv.index]]\nurl=\"https://test.example/simple\"\n", L"tool.uv", L"python-install-mirror") == L"https://test.example/python", "read-project-mirror");
    check(ReadTomlString("[[tool.uv.index]]\nurl=\"https://test.example/simple\"\n", L"tool.uv.index", L"url") == L"https://test.example/simple", "read-array-table-index");
    check(ClassifyProblem("the lockfile needs to be updated", 3) == Problem::LockMismatch, "lock-mismatch-is-not-network");
    check(ClassifyProblem("Failed to download: connection timed out", 2) == Problem::Network, "network-failure-advice");
    check(ClassifyProblem("permission denied (os error 5)", 3) == Problem::Permission, "permission-failure-advice");
    check(!ValidNetworkUrl(L"https://safe.example\n--bad", false), "reject-multiline-network-address");
    check(!ValidNetworkUrl(L"http://", false), "reject-network-address-without-host");
    const std::wstring fixture = reportPath + L".hash-input";
    WriteFileBytes(fixture, "abc");
    check(Sha256(fixture) == L"BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD", "system-sha256-known-vector");
    DeleteFileW(fixture.c_str());
    const std::vector<std::wstring> arguments = { L"--fixture-child", L"中文 空格", L"trailing slash \\", L"quote\"inside", L"" };
    ProcessResult child = RunProcess(ExePath(), arguments, Parent(ExePath()), {{ L"FAA_NATIVE_TEST", L"环境变量" }}, NULL, nullptr);
    check(child.exitCode == 17 && !child.systemError, "capture-nonzero-child-exit");
    check(child.output == Utf8(L"中文 空格\ntrailing slash \\\nquote\"inside\n\nENV=环境变量\n"), "unicode-arguments-environment-and-pipe");
    HANDLE cancel = CreateEventW(NULL, TRUE, TRUE, NULL);
    ProcessResult stopped = RunProcess(ExePath(), {L"--fixture-child", L"wait"}, Parent(ExePath()), {}, cancel, nullptr);
    CloseHandle(cancel);
    check(stopped.cancelled, "cancel-only-owned-job");
    ProcessResult absent = RunProcess(Join(Parent(ExePath()), L"__absent_launcher_fixture__.exe"), {}, Parent(ExePath()), {}, NULL, nullptr);
    check(absent.systemError == ERROR_FILE_NOT_FOUND, "report-missing-child-executable");
    report << "failures=" << failures << "\n";
    return WriteFileBytes(reportPath, report.str()) ? (failures ? 1 : 0) : 2;
}
}  // namespace faa
