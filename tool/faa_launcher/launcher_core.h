#pragma once
#ifndef UNICODE
#define UNICODE
#define _UNICODE
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <string>
#include <vector>
#include <map>
#include <functional>

namespace faa {

std::wstring Join(const std::wstring& parent, const std::wstring& name);
std::wstring Parent(const std::wstring& path);
std::wstring ExePath();
std::wstring SystemExe(const wchar_t* name);
bool Exists(const std::wstring& path);
bool IsDirectory(const std::wstring& path);
bool MakeDirectories(const std::wstring& path);
std::string Utf8(const std::wstring& text);
std::wstring Wide(const std::string& text);
std::string ReadFileBytes(const std::wstring& path);
bool WriteFileBytes(const std::wstring& path, const std::string& text);
std::wstring SystemError(DWORD code);
std::wstring QuoteArgument(const std::wstring& argument);
std::wstring ReadTomlString(const std::string& content, const std::wstring& section, const std::wstring& key);
std::wstring FindProjectRoot(const std::wstring& start);
std::wstring Timestamp();
std::wstring Sha256(const std::wstring& path);

struct ProcessResult {
    DWORD exitCode;
    DWORD systemError;
    bool cancelled;
    std::string output;
    ProcessResult() : exitCode(1), systemError(0), cancelled(false) {}
};

// 只把安装器本次创建的子进程放入 Job，取消时不会按进程名终止其他 Python 或 uv。
ProcessResult RunProcess(const std::wstring& executable,
    const std::vector<std::wstring>& arguments, const std::wstring& cwd,
    const std::map<std::wstring, std::wstring>& environment, HANDLE cancel,
    const std::function<void(const std::wstring&)>& onLog);

enum class Problem { Files, Network, Permission, Disk, LockMismatch, Dependency, Compatibility, Startup, Other };
Problem ClassifyProblem(const std::string& output, int stage);
std::wstring ProblemAdvice(Problem problem);
bool ValidNetworkUrl(const std::wstring& value, bool allowEmpty);
int RunCoreSelfTests(const std::wstring& reportPath);
int RunFixtureChild(const std::vector<std::wstring>& args);

}  // namespace faa
