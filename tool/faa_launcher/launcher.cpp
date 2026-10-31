#include "launcher_core.h"
#include "launcher_maintenance.h"
#include <windowsx.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shellapi.h>
#include <gdiplus.h>
#include <algorithm>
#include <memory>
#include <sstream>
#include <cwctype>
#include <cstring>
#include <winioctl.h>

using namespace Gdiplus;
using namespace faa;

#ifndef FAA_ENTRY_BUILD
#define FAA_ENTRY_BUILD 0
#endif

namespace {
const UINT WM_LAUNCHER_EVENT = WM_APP + 31;
const int ID_START = 101, ID_CANCEL = 102, ID_NETWORK = 103, ID_EXPORT = 105,
    ID_ACTION = 106, ID_REPAIR = 108, ID_LOG = 109,
    ID_SETTINGS = 110, ID_EXPAND = 111, ID_BACKUPS = 112, ID_REFRESH = 113,
    ID_CONFIRM = 114, ID_FORCE = 115, ID_CHECKS = 116, ID_DELETE_BACKUP = 117, ID_BACKUP_DETAILS = 118;
const wchar_t* StageNames[] = { L"检查安装文件", L"准备安装工具", L"安装 Python", L"同步运行依赖", L"检测运行环境", L"启动 FAA" };
const wchar_t* StageDescriptions[] = { L"确认文件与安装位置", L"校验工具的完整性", L"准备 Python 3.12", L"按发行包恢复依赖", L"统一核对实际运行能力", L"等待主窗口就绪" };
const wchar_t* ActiveTitles[] = { L"确认 FAA 已准备完整", L"准备可靠的安装工具", L"正在准备 Python", L"正在同步运行依赖", L"正在检测 FAA 运行环境", L"正在打开 FAA" };
enum class Operation { Install, Uninstall, Restore, LegacyUpdate };
const wchar_t* UninstallNames[]={L"确认卸除范围",L"检查运行进程",L"卸除本地环境",L"完成卸除"};
const wchar_t* UninstallDescriptions[]={L"保留配置与用户数据",L"处理环境占用",L"移除本地 uv 和 .venv",L"核对卸除结果"};
const wchar_t* RestoreNames[]={L"选择备份版本",L"检查恢复条件",L"备份当前版本",L"恢复版本文件",L"准备并检测环境",L"启动 FAA"};
const wchar_t* RestoreDescriptions[]={L"查看备份与版本信息",L"检查备份和运行进程",L"保存恢复前的版本",L"失败时自动回滚",L"同步依赖后统一检测",L"等待主窗口就绪"};
const wchar_t* LegacyNames[]={L"核对旧版交接",L"获取纯净源码",L"读取新版规则",L"迁移原始用户数据",L"备份并替换",L"更新完成"};
const wchar_t* LegacyDescriptions[]={L"固定原始备份与版本",L"兼容旧版需要再次下载",L"由目标版本生成发行目录",L"使用首次备份而非中间结果",L"失败时保留原始备份",L"请手动运行环境安装器"};
int StepCount(Operation operation) { return operation==Operation::Uninstall?4:6; }
const wchar_t* StepName(Operation operation,int index) { return operation==Operation::Install?StageNames[index]:operation==Operation::Uninstall?UninstallNames[index]:operation==Operation::LegacyUpdate?LegacyNames[index]:RestoreNames[index]; }
const wchar_t* StepDescription(Operation operation,int index) { return operation==Operation::Install?StageDescriptions[index]:operation==Operation::Uninstall?UninstallDescriptions[index]:operation==Operation::LegacyUpdate?LegacyDescriptions[index]:RestoreDescriptions[index]; }
enum class State { Idle, Running, Blocked, Failed, Cancelled, Success, Monitoring, Review };
enum class Step { Pending, Active, Complete, Failed };
enum class EventKind { Start, Finish, Log, Failure, Cancel, Success, Blocked, MonitorStart, ProcessExit, Check, Review, BackupDeleted };
struct RuntimeCheck { std::wstring key,status,label,detail; };
struct Event {
    EventKind kind;
    int stage;
    std::wstring title, detail;
    Problem problem;
    DWORD pid=0;
    unsigned monitorId=0;
    HANDLE process=NULL;
    std::vector<ManagedProcess> processes;
    RuntimeCheck check;
    Event(EventKind value, int index, const std::wstring& heading = L"", const std::wstring& message = L"", Problem issue = Problem::Other)
        : kind(value), stage(index), title(heading), detail(message), problem(issue) {}
    ~Event(){if(process)CloseHandle(process);}
};
struct Options {
    HWND window;
    HANDLE cancel;
    bool reinstall, debug, force=false, removeBackup=false, quickEntry=false;
    unsigned monitorId=0;
    std::vector<ManagedProcess> blockers;
    Operation operation;
    int start;
    std::wstring root, pythonMirror, packageIndex, backup;
    Options() : window(NULL), cancel(NULL), reinstall(false), debug(false), operation(Operation::Install), start(0) {}
};
struct BackupInfo { std::wstring path,label,version,summary,details; };
struct Application {
    HWND window, start, cancel, network, exportLog, action, repair, log, settings, expand, backupList, refresh, confirm, force, checkList, deleteBackup, backupDetails;
    HFONT bodyFont, monoFont;
    HANDLE cancelEvent, worker, monitor=NULL, monitorStop=NULL;
    Operation operation=Operation::Install;
    State state;
    Step steps[6];
    Problem problem;
    int stage, animation;
    bool closeAfterCancel, rootValid, debug=false, logExpanded=false, faaExited=false, restoreFilesReady=false;
    bool quickEntry=FAA_ENTRY_BUILD!=0;
    bool startupFailure=false;
    unsigned monitorId=0;
    DWORD faaExitCode=0;
    std::vector<BackupInfo> backups;
    std::vector<ManagedProcess> blockers;
    std::vector<RuntimeCheck> checks;
    float scale;
    std::wstring root, rootProblem, title, detail, pythonMirror, packageIndex, defaultPythonMirror, index, logFile, selectedBackup;
    std::string logBytes;
    Application() : window(NULL), worker(NULL), state(State::Idle), problem(Problem::Other), stage(0),
        animation(0), closeAfterCancel(false), rootValid(false), scale(1.0f) {
        for (auto& step : steps) step = Step::Pending;
    }
} app;

Color Background(246, 248, 250), Ink(29, 42, 52), Muted(110, 125, 137), Line(229, 235, 239),
    Accent(10, 132, 119), PaleAccent(232, 246, 241), Error(173, 65, 41), PaleError(255, 243, 237);

void Post(const Options& options, Event* event) {
    event->monitorId=options.monitorId;
    if (!PostMessageW(options.window, WM_LAUNCHER_EVENT, 0, reinterpret_cast<LPARAM>(event))) delete event;
}
void WorkerLog(const Options& options, const std::wstring& text) { Post(options, new Event(EventKind::Log, options.start, L"", text)); }
bool Cancelled(const Options& options) { return WaitForSingleObject(options.cancel, 0) == WAIT_OBJECT_0; }
void Failure(const Options& options, int stage, const std::wstring& title, const std::wstring& detail, Problem problem) {
    Post(options, new Event(EventKind::Failure, stage, title, detail, problem));
}
void PostCheck(const Options& options,const RuntimeCheck& check) {
    Event* event=new Event(EventKind::Check,4);event->check=check;Post(options,event);
}
std::map<std::wstring, std::wstring> InstallationEnvironment(const Options& options) {
    std::map<std::wstring, std::wstring> values = {
        {L"UV_NO_MODIFY_PATH", L"1"}, {L"UV_DISABLE_UPDATE", L"1"}, {L"UV_NO_PROGRESS", L"1"},
        {L"NO_COLOR", L"1"}, {L"PYTHONIOENCODING", L"utf-8"}
    };
    if (!options.pythonMirror.empty()) values[L"UV_PYTHON_INSTALL_MIRROR"] = options.pythonMirror;
    return values;
}
bool RunInstallCommand(const Options& options, int stage, const std::wstring& executable, const std::vector<std::wstring>& arguments,
    const std::map<std::wstring,std::wstring>& overrides = {}) {
    auto environment = InstallationEnvironment(options);
    for (const auto& entry : overrides) environment[entry.first] = entry.second;
    ProcessResult result = RunProcess(executable, arguments, options.root, environment, options.cancel,
        [&](const std::wstring& line) { WorkerLog(options, line); });
    if (result.cancelled) { Post(options, new Event(EventKind::Cancel, stage)); return false; }
    if (result.systemError || result.exitCode) {
        const Problem problem = result.systemError == ERROR_ACCESS_DENIED ? Problem::Permission : ClassifyProblem(result.output, stage);
        std::wstring detail = result.systemError ? SystemError(result.systemError) : L"安装工具返回退出码 " + std::to_wstring(result.exitCode) + L"。具体错误已记录在运行详情中。";
        Failure(options, stage, std::wstring(StageNames[stage]) + L"未能完成", detail, problem);
        return false;
    }
    return true;
}
bool SyncDependencies(const Options& options, const std::wstring& uv,int stage=3) {
    const std::wstring configured = ReadTomlString(ReadFileBytes(Join(options.root,L"pyproject.toml")),L"tool.uv.index",L"url");
    if (options.packageIndex.empty() || options.packageIndex == configured) {
        std::vector<std::wstring> arguments = {L"sync", L"--locked", L"--no-dev", L"--python", L"3.12"};
        if (options.reinstall) arguments.push_back(L"--reinstall");
        return RunInstallCommand(options, stage, uv, arguments);
    }
    // uv.lock 固定了下载地址。换源时先验证并导出锁定版本和 hash，避免重新解析或改写发行包的锁文件。
    const std::wstring requirements = Join(options.root,L"update_cache\\launcher\\requirements-" + Timestamp() + L".txt");
    if (!MakeDirectories(Parent(requirements))) {
        Failure(options,stage,L"无法准备依赖清单",SystemError(GetLastError()),Problem::Permission); return false;
    }
    struct ExportGuard { std::wstring path; ~ExportGuard() { DeleteFileW(path.c_str()); } } cleanup = {requirements};
    WorkerLog(options,L"[启动器] 正在核对锁文件并准备指定下载源的依赖清单。");
    if (!RunInstallCommand(options,stage,uv,{L"export",L"--locked",L"--offline",L"--no-dev",L"--no-emit-project",L"--no-header",L"--quiet",L"--output-file",requirements})) return false;
    const std::wstring python = Join(options.root,L".venv\\Scripts\\python.exe");
    if (!Exists(python) && !RunInstallCommand(options,stage,uv,{L"venv",L"--python",L"3.12",Join(options.root,L".venv")})) return false;
    if (!RunInstallCommand(options,stage,python,{L"-c",L"import sys; assert sys.version_info[:2] == (3, 12), 'FAA requires Python 3.12; select a clean release directory'"})) return false;
    std::vector<std::wstring> arguments = {L"--no-config",L"pip",L"sync",requirements,L"--require-hashes",L"--strict",L"--python",python,
        L"--default-index",options.packageIndex};
    if (options.reinstall) arguments.push_back(L"--reinstall");
    // 本次明确选择的源优先于外部 uv 配置；保留系统已有的联网方式，不增加代理设置。
    return RunInstallCommand(options,stage,uv,arguments,{{L"UV_INDEX",L""},{L"UV_EXTRA_INDEX_URL",L""},{L"UV_FIND_LINKS",L""}});
}
bool PrepareUv(const Options& options, const std::wstring& launcherDirectory, const std::wstring& uv,int stage=1) {
    const std::wstring archive = Join(launcherDirectory, L"uv\\uv-x86_64-pc-windows-msvc.zip");
    const std::wstring expected = L"30FDF26C209F0CB7C97D3B08A26AB4E78CE5AE0E031B88798CBACCC0F24F452B";
    if (Exists(uv)) {
        WorkerLog(options, L"[启动器] 使用 FAA 文件夹中的本地 uv。");
        return RunInstallCommand(options, stage, uv, {L"--version"});
    }
    WorkerLog(options, L"[启动器] 正在校验内置 uv 压缩包的 SHA256。");
    if (Sha256(archive) != expected) {
        Failure(options, stage, L"安装工具校验失败", L"内置 uv 压缩包缺失或内容与发行包不一致，请重新解压完整安装包。", Problem::Files);
        return false;
    }
    const std::wstring scratch = Join(options.root, L"update_cache\\launcher\\uv-" + Timestamp());
    if (!MakeDirectories(scratch) || !MakeDirectories(Parent(uv))) {
        Failure(options, stage, L"无法写入安装工具", SystemError(GetLastError()), Problem::Permission); return false;
    }
    const std::wstring tar = SystemExe(L"tar.exe");
    if (!Exists(tar)) {
        Failure(options, stage, L"系统解压组件不可用", L"没有找到 Windows 自带的 tar.exe。安装器需要完整的 Windows 10 2004 或 Windows 11。", Problem::Files);
        return false;
    }
    // 已固定校验 ZIP 的 hash，再交给 Windows 自带 tar 解压；安装器不携带第三方解压 DLL。
    if (!RunInstallCommand(options, stage, tar, {L"-xf", archive, L"-C", scratch})) return false;
    if (!MoveFileExW(Join(scratch, L"uv.exe").c_str(), uv.c_str(), MOVEFILE_WRITE_THROUGH)) {
        Failure(options, stage, L"无法放置安装工具", SystemError(GetLastError()), Problem::Permission); return false;
    }
    // 只清理本次新建暂存目录中的已知文件，不递归删除任何已有用户目录。
    DeleteFileW(Join(scratch, L"uvx.exe").c_str());
    RemoveDirectoryW(scratch.c_str());
    return RunInstallCommand(options, stage, uv, {L"--version"});
}

struct WindowSearch { DWORD pid; HANDLE job; HWND found; HWND error; };
BOOL CALLBACK FindFaaWindow(HWND window, LPARAM parameter) {
    WindowSearch* search = reinterpret_cast<WindowSearch*>(parameter);
    DWORD pid = 0; GetWindowThreadProcessId(window, &pid);
    if (!IsWindowVisible(window)) return TRUE;
    if (pid != search->pid) {
        // Windows 虚拟环境的 python.exe 可能只是启动跳板，主窗口属于同一 Job 内的子进程。
        HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);BOOL owned=FALSE;
        if(process){IsProcessInJob(process,search->job,&owned);CloseHandle(process);}
        if(!owned)return TRUE;
    }
    wchar_t title[512] = {}; GetWindowTextW(window, title, 512);
    if (wcsstr(title, L"FAA 启动失败")) search->error = window;
    // 加载窗口和异常对话框不等于主程序就绪；当前主窗口有独立且固定的标题前缀。
    if (wcsncmp(title, L"FAA - ", 6) == 0) search->found = window;
    return TRUE;
}
std::string EmbeddedResource(int id) {
    HMODULE module=GetModuleHandleW(NULL);HRSRC resource=FindResourceW(module,MAKEINTRESOURCEW(id),RT_RCDATA);
    if(!resource)return "";HGLOBAL loaded=LoadResource(module,resource);const char* bytes=static_cast<const char*>(LockResource(loaded));
    return bytes?std::string(bytes,SizeofResource(module,resource)):"";
}
bool RunRuntimeChecks(const Options& options) {
    const std::wstring helper=Join(options.root,L"update_cache\\launcher\\runtime-"+Timestamp()+L".py");
    const std::string source=EmbeddedResource(3);
    if(source.empty()){Failure(options,4,L"安装器中的检测资源缺失",L"请重新下载完整安装器后重试。",Problem::Files);return false;}
    if(!MakeDirectories(Parent(helper))||!WriteFileBytes(helper,source)) {Failure(options,4,L"无法准备运行环境检测",SystemError(GetLastError()),Problem::Permission);return false;}
    struct HelperGuard {std::wstring path;~HelperGuard(){DeleteFileW(path.c_str());}} cleanup={helper};
    std::map<std::wstring,RuntimeCheck> checks;int reportedFailures=-1,reportedWarnings=-1,reportedCount=-1;
    bool invalid=false,done=false;
    auto result=RunProcess(Join(options.root,L".venv\\Scripts\\python.exe"),{L"-I",L"-u",L"-X",L"utf8",helper,L"--root",options.root},options.root,
        InstallationEnvironment(options),options.cancel,[&](const std::wstring& line) {
        const std::wstring prefix=L"FAA_RUNTIME_CHECK\t",end=L"FAA_RUNTIME_DONE\t";
        if(line.find(prefix)==0) {
            std::vector<std::wstring> fields;size_t position=prefix.size();
            for(int i=0;i<3;++i){size_t tab=line.find(L'\t',position);if(tab==std::wstring::npos){invalid=true;return;}fields.push_back(line.substr(position,tab-position));position=tab+1;}
            fields.push_back(line.substr(position));
            RuntimeCheck check={fields[0],fields[1],fields[2],fields[3]};
            if(done||check.key.empty()||check.label.empty()||(check.status!=L"pending"&&check.status!=L"pass"&&check.status!=L"warning"&&check.status!=L"fail")){invalid=true;return;}
            checks[check.key]=check;PostCheck(options,check);
            if(check.status!=L"pending")WorkerLog(options,L"[环境检测] ["+check.status+L"] "+check.label+L"："+check.detail);
        } else if(line.find(end)==0) {
            std::wistringstream counts(line.substr(end.size()));std::wstring extra;
            if(done||!(counts>>reportedFailures>>reportedWarnings>>reportedCount)||(counts>>extra))invalid=true;
            done=true;
        } else WorkerLog(options,line);
    });
    if(result.cancelled){Post(options,new Event(EventKind::Cancel,4));return false;}
    int failures=0,warnings=0;for(const auto& entry:checks){failures+=entry.second.status==L"fail";warnings+=entry.second.status==L"warning";invalid=invalid||entry.second.status==L"pending";}
    if(result.systemError||invalid||!done||reportedCount!=static_cast<int>(checks.size())||checks.empty()||reportedFailures!=failures||reportedWarnings!=warnings||result.exitCode!=static_cast<DWORD>(failures?1:0)) {
        const std::wstring detail=result.systemError?SystemError(result.systemError):L"检测进程异常退出或结果不完整。请查看运行详情，处理组件或安全软件限制后重新检测。";
        PostCheck(options,{L"probe",L"fail",L"检测工具执行结果",detail});
        Failure(options,4,L"运行环境检测没有完成",detail,Problem::Compatibility);return false;
    }
    if(failures){Failure(options,4,L"运行环境检测未通过",L"有 "+std::to_wstring(failures)+L" 项必需条件未通过。选择失败项查看原因，处理后重试检测或修复依赖。",Problem::Compatibility);return false;}
    if(warnings){Post(options,new Event(EventKind::Review,4));return false;}
    return true;
}
bool LaunchFaa(const Options& options) {
    const std::wstring python = Join(options.root, options.debug?L".venv\\Scripts\\python.exe":L".venv\\Scripts\\pythonw.exe");
    if (!Exists(python)) {
        Failure(options, 5, L"没有找到 Python 启动程序", L"运行环境不完整，请使用“修复依赖”后重新启动。", Problem::Dependency);
        return false;
    }
    const std::wstring startupLog = Join(options.root, L"logs\\launcher\\python-" + Timestamp() + L".log");
    MakeDirectories(Parent(startupLog));
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    HANDLE log = CreateFileW(startupLog.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &security, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (log == INVALID_HANDLE_VALUE) { Failure(options, 5, L"无法创建启动日志", SystemError(GetLastError()), Problem::Permission); return false; }
    HANDLE input = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &security, OPEN_EXISTING, 0, NULL);
    HANDLE job = CreateJobObjectW(NULL, NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        DWORD error = GetLastError(); if (job) CloseHandle(job); CloseHandle(input); CloseHandle(log);
        Failure(options, 5, L"无法管理启动进程", SystemError(error), Problem::Startup); return false;
    }
    std::wstring command = QuoteArgument(python) + L" -u -X utf8 -m function.faa_main";
    std::vector<wchar_t> buffer(command.begin(), command.end()); buffer.push_back(0);
    STARTUPINFOW startup = {}; startup.cb = sizeof(startup); startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input; startup.hStdOutput = startup.hStdError = log;
    PROCESS_INFORMATION process = {};
    BOOL created = CreateProcessW(python.c_str(), buffer.data(), NULL, NULL, TRUE, CREATE_NO_WINDOW | CREATE_SUSPENDED,
        NULL, options.root.c_str(), &startup, &process);
    DWORD error = GetLastError();
    CloseHandle(input); CloseHandle(log);
    if (!created) { CloseHandle(job); Failure(options, 5, L"无法启动 FAA", SystemError(error), Problem::Startup); return false; }
    if (!AssignProcessToJobObject(job, process.hProcess)) {
        error = GetLastError(); TerminateProcess(process.hProcess, 1);
        CloseHandle(process.hThread); CloseHandle(process.hProcess); CloseHandle(job);
        Failure(options, 5, L"无法管理 FAA 进程", SystemError(error), Problem::Startup); return false;
    }
    if(ResumeThread(process.hThread)==static_cast<DWORD>(-1)) {
        error=GetLastError(); CloseHandle(process.hThread); CloseHandle(job); CloseHandle(process.hProcess);
        Failure(options,5,L"无法开始运行 FAA",SystemError(error),Problem::Startup); return false;
    }
    CloseHandle(process.hThread);
    if(options.debug) {
        Event* monitor=new Event(EventKind::MonitorStart,5,L"",startupLog); monitor->pid=process.dwProcessId;
        DuplicateHandle(GetCurrentProcess(),process.hProcess,GetCurrentProcess(),&monitor->process,0,FALSE,DUPLICATE_SAME_ACCESS);Post(options,monitor);
    }
    WorkerLog(options, L"[启动器] 等待 FAA 主窗口，最长 90 秒。启动日志：" + startupLog);
    WindowSearch search = {process.dwProcessId, job, NULL, NULL};
    bool success = false, cancelled = false;
    for (int tick = 0; tick < 360; ++tick) {
        EnumWindows(FindFaaWindow, reinterpret_cast<LPARAM>(&search));
        if (search.error) break;
        if (search.found) { success = true; break; }
        if (WaitForSingleObject(options.cancel,250)==WAIT_OBJECT_0) { cancelled = true; break; }
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting={};
        if(!QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&accounting,sizeof(accounting),NULL)||!accounting.ActiveProcesses)break;
    }
    if (success || search.error) {
        // 主窗口已就绪，或出现需要用户阅读的错误对话框时，让进程独立保留。
        // 清除 kill 标志后再关 Job，避免关闭启动助手把 FAA 或它的错误提示一起关掉。
        limits.BasicLimitInformation.LimitFlags = 0;
        if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) success = false;
    }
    CloseHandle(job); CloseHandle(process.hProcess);
    if (success) {
        DWORD windowPid=0;GetWindowThreadProcessId(search.found,&windowPid);
        WorkerLog(options,L"[启动器] 已识别 FAA 主窗口，PID "+std::to_wstring(windowPid)+L"。");
        return true;
    }
    if (cancelled) { Post(options, new Event(EventKind::Cancel, 5)); return false; }
    const std::wstring output = Wide(ReadFileBytes(startupLog));
    if (!output.empty()&&!options.debug) WorkerLog(options, output);
    Failure(options, 5, L"FAA 尚未成功打开", search.error ? L"请先阅读并关闭 FAA 的启动失败提示，再重试或修复依赖。详细日志可在下方保存。" : L"主程序提前退出或等待主窗口超时，请查看运行详情和启动日志。", Problem::Startup);
    return false;
}

bool IsFaaRoot(const std::wstring& root, std::wstring& problem) {
    if (root.empty() || !IsDirectory(root)) {
        problem = L"EXE 所在目录无法读取。";
        return false;
    }
    const wchar_t* markers[] = {L"LICENSE", L"uv.lock", L"pyproject.toml", L"function\\faa_main.py"};
    std::vector<std::wstring> missing;
    for (const wchar_t* marker : markers) if (!Exists(Join(root, marker))) missing.push_back(marker);
    if (missing.empty()) { problem.clear(); return true; }
    problem = L"未找到：";
    for (size_t index = 0; index < missing.size(); ++index) {
        if (index) problem += L"、";
        problem += missing[index];
    }
    return false;
}

void RunInstall(const Options& options) {
    if(options.root.empty()||!IsDirectory(options.root)) {
        Failure(options,0,L"没有找到 FAA 根目录",L"请将安装器放在同时包含 LICENSE、uv.lock、pyproject.toml 和 function\\faa_main.py 的 FAA 根目录中。",Problem::Files); return;
    }
    const std::wstring launcherDirectory = Join(options.root, L"plugins\\launcher_scripts");
    const std::wstring uv = Join(launcherDirectory, L"bin\\uv.exe");
    for (int stage = options.start; stage < StepCount(options.operation); ++stage) {
        if (Cancelled(options)) { Post(options, new Event(EventKind::Cancel, stage)); return; }
        Post(options, new Event(EventKind::Start, stage, ActiveTitles[stage], StageDescriptions[stage]));
        WorkerLog(options, L"[启动器] 开始：" + std::wstring(StageNames[stage]));
        bool success = true;
        if (stage == 0) {
            const wchar_t* required[] = {L"pyproject.toml", L"uv.lock", L"function\\faa_main.py"};
            for (const wchar_t* path : required) if (!Exists(Join(options.root, path))) {
                Failure(options, 0, L"没有找到完整的 FAA 文件", L"缺少文件：" + Join(options.root, path), Problem::Files); return;
            }
            if (!MakeDirectories(Join(options.root, L"logs\\launcher"))) {
                Failure(options, 0, L"FAA 文件夹不可写", SystemError(GetLastError()), Problem::Permission); return;
            }
            const std::wstring probe = Join(options.root, L"logs\\launcher\\write-check-" + Timestamp());
            if (!WriteFileBytes(probe, "FAA write check")) { Failure(options, 0, L"无法写入 FAA 文件夹", SystemError(GetLastError()), Problem::Permission); return; }
            DeleteFileW(probe.c_str());
            WorkerLog(options, L"[启动器] 文件检查通过：" + options.root);
        } else if (stage == 1) success = PrepareUv(options, launcherDirectory, uv);
        else if (stage == 2) success = RunInstallCommand(options, stage, uv, {L"python", L"install", L"3.12"});
        else if (stage == 3) success = SyncDependencies(options, uv);
        else if (stage == 4) success = RunRuntimeChecks(options);
        else success = LaunchFaa(options);
        if (!success) return;
        Post(options, new Event(EventKind::Finish, stage));
    }
    Post(options, new Event(EventKind::Success, 5));
}
void RunQuickEntry(const Options& options) {
    std::wstring issue;
    if(!IsFaaRoot(options.root,issue)){Failure(options,0,L"FAA 安装文件不完整",issue,Problem::Files);return;}
    // 快速入口只启动现有 Python，不下载、安装、同步依赖或自动修复。
    Post(options,new Event(EventKind::Start,5,L"正在打开 FAA",L"等待本次启动任务的主窗口就绪。"));
    if(LaunchFaa(options))Post(options,new Event(EventKind::Success,5));
}
bool CheckManagedProcesses(const Options& options,int stage) {
    if(options.force) for(const auto& process:options.blockers) {
        std::wstring error;
        WorkerLog(options,L"[进程] 正在结束 "+process.name+L"，PID "+std::to_wstring(process.pid));
        if(!StopManagedProcess(options.root,process,error)) { Failure(options,stage,L"无法结束占用进程",error,Problem::Permission); return false; }
    }
    const auto processes=FindManagedProcesses(options.root);
    if(processes.empty()) return true;
    for(const auto& process:processes) WorkerLog(options,L"[进程] PID "+std::to_wstring(process.pid)+L"："+process.path);
    Event* blocked=new Event(EventKind::Blocked,stage,L"运行环境仍被占用",L"请先关闭所列程序，或在界面中结束这些进程后继续。");blocked->processes=processes;Post(options,blocked);
    return false;
}
void RunUninstall(const Options& options) {
    Post(options,new Event(EventKind::Start,0,L"正在确认卸除范围",L"仅处理当前 FAA 的本地 uv 和 .venv。"));
    std::wstring error;
    if(!IsFaaRoot(options.root,error)) { Failure(options,0,L"FAA 根目录检查失败",error,Problem::Files); return; }
    Post(options,new Event(EventKind::Finish,0));
    Post(options,new Event(EventKind::Start,1,L"正在检查环境占用",L"确认没有程序正在使用此 FAA 的运行环境。"));
    if(!CheckManagedProcesses(options,1)) return;
    Post(options,new Event(EventKind::Finish,1));
    Post(options,new Event(EventKind::Start,2,L"正在卸除本地运行环境",L"用户配置、资源、日志和全局 Python 都会保留。"));
    const wchar_t* targets[]={L"plugins\\launcher_scripts\\bin",L".venv"};
    for(const auto* target:targets) {
        WorkerLog(options,L"[卸除] "+Join(options.root,target));
        if(!RemoveManagedDirectory(options.root,target,options.cancel,error)) {
            if(Cancelled(options)) Post(options,new Event(EventKind::Cancel,2));
            else Failure(options,2,L"运行环境未能完全卸除",error,Problem::Permission);
            return;
        }
    }
    Post(options,new Event(EventKind::Finish,2));
    Post(options,new Event(EventKind::Start,3,L"正在核对卸除结果",L"确认本地环境已经移除。"));
    for(const auto* target:targets)if(Exists(Join(options.root,target))){Failure(options,3,L"环境目录仍然存在",L"请关闭重新创建该环境的程序，然后重试。",Problem::Other);return;}
    Post(options,new Event(EventKind::Finish,3)); Post(options,new Event(EventKind::Success,3));
}
std::string EmbeddedUpdater(){
    return EmbeddedResource(2);
}
void RunRestore(const Options& options) {
    if(options.start<4) {
        std::wstring error;
        Post(options,new Event(EventKind::Start,1,L"正在检查恢复条件",L"核对所选备份、恢复工具与环境占用。"));
        if(!IsSafeBackup(options.root,options.backup,error)) { Failure(options,1,L"所选备份无法恢复",error,Problem::Files); return; }
        if(!CheckManagedProcesses(options,1)) return;
        std::wstring python=Join(options.root,L".venv\\Scripts\\python.exe");
        if(!Exists(python)) {
            wchar_t found[32768]={}; DWORD size=SearchPathW(NULL,L"python.exe",NULL,32768,found,NULL);
            python=size&&size<32768?found:L"";
            if(python.find(L"WindowsApps")!=std::wstring::npos) python.clear();
        }
        if(python.empty()) { Failure(options,1,L"没有可用的 Python",L"请先使用“安装并启动”准备运行环境，然后再恢复备份。",Problem::Dependency); return; }
        const std::wstring helper=Join(options.root,L"update_cache\\launcher\\restore-"+Timestamp()+L".py");
        // 恢复会替换 plugins 目录，内嵌执行脚本可避免它在执行过程中被覆盖。
        const std::string source=EmbeddedUpdater();
        if(source.empty()){Failure(options,1,L"安装器中的恢复资源缺失",L"请重新下载完整的安装器后重试。",Problem::Files);return;}
        if(!MakeDirectories(Parent(helper))||!WriteFileBytes(helper,source)) { Failure(options,1,L"无法准备恢复工具",SystemError(GetLastError()),Problem::Permission); return; }
        struct HelperGuard { std::wstring path; ~HelperGuard(){DeleteFileW(path.c_str());} } cleanup={helper};
        Post(options,new Event(EventKind::Finish,1));
        std::vector<std::wstring> arguments={L"-u",L"-X",L"utf8",helper,L"restore",L"--root",options.root,L"--backup",options.backup,
            L"--launch",L"",L"--gui",L"--preserve-entry",BaseName(ExePath()),L"--preserve-entry",L"FAA - 环境安装器.exe",
            L"--preserve-entry",L"logs"};
        // 版本文件开始移动后不能杀死恢复进程；由更新器完成恢复或回滚，界面只接收阶段和日志。
        ProcessResult result=RunProcess(python,arguments,options.root,InstallationEnvironment(options),NULL,[&](const std::wstring& line) {
            if(line==L"FAA_LAUNCHER_PHASE:backup_current_version") Post(options,new Event(EventKind::Start,2,L"正在备份当前版本",L"当前版本将保存到 backups，便于之后再次恢复。"));
            else if(line==L"FAA_LAUNCHER_PHASE:restoring_backup") {
                Post(options,new Event(EventKind::Finish,2)); Post(options,new Event(EventKind::Start,3,L"正在恢复所选版本",L"将备份中的文件复制回 FAA 根目录。"));
            } else if(line==L"FAA_LAUNCHER_PHASE:restore_completed") Post(options,new Event(EventKind::Finish,3));
            else if(line==L"FAA_LAUNCHER_PHASE:restore_rollback_started") Post(options,new Event(EventKind::Start,3,L"恢复失败，正在回滚",L"正在恢复到操作前的版本，请保持此窗口打开。"));
            else WorkerLog(options,line);
        });
        if(result.systemError||result.exitCode) { Failure(options,3,L"备份恢复未完成",result.systemError?SystemError(result.systemError):L"恢复工具报告错误。回滚结果与具体文件已记录在运行详情中。",Problem::Other); return; }
    }
    if(options.start<5) {
        Post(options,new Event(EventKind::Start,4,L"正在准备并检测恢复后的环境",L"按恢复版本的锁文件同步依赖，然后统一检测运行能力。"));
        const std::wstring launcherDirectory=Join(options.root,L"plugins\\launcher_scripts"),uv=Join(launcherDirectory,L"bin\\uv.exe");
        if(!PrepareUv(options,launcherDirectory,uv,4)||!RunInstallCommand(options,4,uv,{L"python",L"install",L"3.12"})||!SyncDependencies(options,uv,4)||!RunRuntimeChecks(options))return;
        Post(options,new Event(EventKind::Finish,4));
    }
    Post(options,new Event(EventKind::Start,5,L"正在打开恢复后的 FAA",L"等待 FAA 主窗口就绪。"));
    if(!LaunchFaa(options)) return;
    Post(options,new Event(EventKind::Finish,5)); Post(options,new Event(EventKind::Success,5));
}
bool NeedsLegacyUpdate(const std::wstring& root) {
    if(Exists(Join(root,L".git"))||!Exists(Join(root,L"plugins\\updater\\legacy_bridge.py")))return false;
    auto compact=[](std::string value) {
        value.erase(std::remove_if(value.begin(),value.end(),[](char ch){return ch==' '||ch=='\r'||ch=='\n'||ch=='\t';}),value.end());return value;
    };
    const std::string state=compact(ReadFileBytes(Join(root,L"update_cache\\update_state.json")));
    if(state.find("\"update_protocol\":1")!=std::string::npos)return false;
    if(Exists(Join(root,L"update_cache\\legacy_bridge\\state.json")))return true;
    const std::string operation=compact(ReadFileBytes(Join(root,L"update_cache\\updater_state.json")));
    return operation.find("\"phase\":\"update_completed\"")!=std::string::npos;
}
bool StartLegacyCacheEntry(const std::wstring& root) {
    // 正式入口和旧名别名均先退出，由保留区内的同一程序展示进度，避免更新时占用根目录 EXE。
    const std::wstring directory=Join(root,L"update_cache\\legacy_bridge");
    const std::wstring executable=Join(directory,L"entry-"+std::to_wstring(GetCurrentProcessId())+L".exe");
    if(!MakeDirectories(directory)||!CopyFileW(ExePath().c_str(),executable.c_str(),FALSE))return false;
    std::wstring command=QuoteArgument(executable)+L" --legacy-bridge-root "+QuoteArgument(root);
    std::vector<wchar_t> buffer(command.begin(),command.end());buffer.push_back(0);
    STARTUPINFOW startup={};startup.cb=sizeof(startup);PROCESS_INFORMATION process={};
    if(!CreateProcessW(executable.c_str(),buffer.data(),NULL,NULL,FALSE,0,NULL,directory.c_str(),&startup,&process))return false;
    CloseHandle(process.hThread);CloseHandle(process.hProcess);return true;
}
void RunLegacyUpdate(const Options& options) {
    Post(options,new Event(EventKind::Start,0,L"正在完成旧版更新过渡",L"将按目标版本的规则重新准备并迁移，完成后请手动运行环境安装器。"));
    const std::wstring python=Join(options.root,L".venv\\Scripts\\python.exe");
    const std::wstring script=Join(options.root,L"plugins\\updater\\legacy_bridge.py");
    int lastStage=0;
    std::wstring networkError;
    ProcessResult result=RunProcess(python,{L"-I",L"-X",L"utf8",script,L"--root",options.root},options.root,
        InstallationEnvironment(options),NULL,[&](const std::wstring& line) {
            const std::wstring prefix=L"FAA_LEGACY_PHASE:";
            if(line.find(prefix)==0&&line.size()>prefix.size()+1) {
                const int stage=line[prefix.size()]-L'0';
                if(stage>=0&&stage<6) {
                    lastStage=stage;
                    for(int previous=0;previous<stage;++previous)Post(options,new Event(EventKind::Finish,previous));
                    Post(options,new Event(EventKind::Start,stage,LegacyNames[stage],line.substr(prefix.size()+2)));
                }
            }
            const std::wstring networkPrefix=L"FAA_LEGACY_NETWORK_ERROR:";
            if(line.find(networkPrefix)==0)networkError=line.substr(networkPrefix.size());
            WorkerLog(options,line);
        });
    if(result.systemError||result.exitCode) {
        Failure(options,lastStage,networkError.empty()?L"旧版更新过渡未完成":L"GitHub 网络连接失败",
            !networkError.empty()?networkError:result.systemError?SystemError(result.systemError):L"原始备份和过渡记录已保留。请查看运行详情，处理后点击重试，或下次运行快速启动入口继续。",
            networkError.empty()?Problem::Other:Problem::Network);return;
    }
    Post(options,new Event(EventKind::Finish,5));Post(options,new Event(EventKind::Success,5));
}
DWORD WINAPI Worker(void* parameter) {
    std::unique_ptr<Options> options(reinterpret_cast<Options*>(parameter));
    HANDLE mutex=NULL;
    try {
        unsigned long long key=1469598103934665603ULL;
        for(wchar_t ch:options->root) { key^=towlower(ch); key*=1099511628211ULL; }
        mutex=CreateMutexW(NULL,FALSE,(L"Local\\FAA.NativeLauncher."+std::to_wstring(key)).c_str());
        DWORD acquired=mutex?WaitForSingleObject(mutex,0):WAIT_FAILED;
        if(acquired!=WAIT_OBJECT_0&&acquired!=WAIT_ABANDONED) {
            if(mutex) CloseHandle(mutex);
            Failure(*options,options->start,L"另一个环境操作正在运行",L"请等待同一 FAA 目录中的其他安装、卸除或恢复操作结束。",Problem::Other); return 0;
        }
        if(options->operation==Operation::LegacyUpdate)RunLegacyUpdate(*options);
        else if(options->quickEntry)RunQuickEntry(*options);
        else if(options->removeBackup) {
            Post(*options,new Event(EventKind::Start,0,L"正在删除所选备份",L"只处理已确认的备份目录，请等待删除完成。"));
            std::wstring error;
            if(RemoveBackupDirectory(options->root,options->backup,options->cancel,error))Post(*options,new Event(EventKind::BackupDeleted,0,L"",options->backup));
            else Failure(*options,0,L"备份删除未完成",error+L" 部分文件可能已移除。可点击“删除备份”重试；恢复其他备份前请重新选择或刷新列表。",Problem::Permission);
        }
        else if(options->operation==Operation::Install) RunInstall(*options);
        else if(options->operation==Operation::Uninstall) RunUninstall(*options);
        else RunRestore(*options);
    } catch(const std::exception& error) { Failure(*options,options->start,L"操作遇到异常",Wide(error.what()),Problem::Other); }
    catch(...) { Failure(*options,options->start,L"操作遇到异常",L"请查看运行详情后重试。",Problem::Other); }
    if(mutex) {ReleaseMutex(mutex);CloseHandle(mutex);}
    return 0;
}

float W(HWND window) { RECT rect; GetClientRect(window, &rect); return (rect.right - rect.left) / app.scale; }
float H(HWND window) { RECT rect; GetClientRect(window, &rect); return (rect.bottom - rect.top) / app.scale; }
int Px(float value) { return static_cast<int>(value * app.scale + 0.5f); }
void Move(HWND window, float x, float y, float width, float height) { MoveWindow(window, Px(x), Px(y), Px(width), Px(height), TRUE); }
void Round(Graphics& graphics, const RectF& rect, float radius, Color fill, Color stroke = Color(0,0,0,0)) {
    GraphicsPath path;
    float d = radius * 2;
    path.AddArc(rect.X, rect.Y, d, d, 180, 90);
    path.AddArc(rect.GetRight()-d, rect.Y, d, d, 270, 90);
    path.AddArc(rect.GetRight()-d, rect.GetBottom()-d, d, d, 0, 90);
    path.AddArc(rect.X, rect.GetBottom()-d, d, d, 90, 90);
    path.CloseFigure();
    SolidBrush brush(fill); graphics.FillPath(&brush, &path);
    if (stroke.GetA()) { Pen pen(stroke, 1); graphics.DrawPath(&pen, &path); }
}
const wchar_t* UiFontFamily() {
    static std::wstring family;
    if(family.empty()) {
        FontFamily preferred(L"Microsoft YaHei UI");
        family=preferred.GetLastStatus()==Ok?L"Microsoft YaHei UI":L"Segoe UI";
    }
    return family.c_str();
}
void Text(Graphics& graphics, const std::wstring& text, float x, float y, float width, float height,
    float size = 13, Color color = Ink, bool bold = false, StringAlignment alignment = StringAlignmentNear) {
    Font font(UiFontFamily(), size, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
    StringFormat format;
    format.SetAlignment(alignment); format.SetLineAlignment(StringAlignmentNear);
    format.SetTrimming(StringTrimmingEllipsisCharacter);
    SolidBrush brush(color);
    graphics.DrawString(text.c_str(), -1, &font, RectF(x,y,width,height), &format, &brush);
}
void Layout();
void UpdateControls();
void RefreshBackups();
void StopMonitor();
bool RestorePickerVisible() { return app.operation==Operation::Restore&&!app.restoreFilesReady&&app.state!=State::Running&&app.state!=State::Success&&app.state!=State::Monitoring&&app.state!=State::Blocked; }
bool ConfirmationVisible() { return RestorePickerVisible()||(app.operation==Operation::Uninstall&&(app.state==State::Idle||app.state==State::Cancelled)); }
bool ChecksVisible() {return app.operation!=Operation::Uninstall&&app.stage==4&&!app.checks.empty()&&(app.state==State::Running||app.state==State::Failed||app.state==State::Review);}
void UpdateCheckList(const RuntimeCheck& check) {
    auto found=std::find_if(app.checks.begin(),app.checks.end(),[&](const RuntimeCheck& value){return value.key==check.key;});
    size_t index=found==app.checks.end()?app.checks.size():static_cast<size_t>(found-app.checks.begin());
    if(found==app.checks.end())app.checks.push_back(check);else *found=check;
    int selected=static_cast<int>(SendMessageW(app.checkList,LB_GETCURSEL,0,0));
    SendMessageW(app.checkList,LB_RESETCONTENT,0,0);
    for(const auto& item:app.checks){std::wstring row=(item.status==L"pass"?L"[通过]  ":item.status==L"fail"?L"[失败]  ":item.status==L"warning"?L"[提示]  ":L"[检测中]  ")+item.label;SendMessageW(app.checkList,LB_ADDSTRING,0,reinterpret_cast<LPARAM>(row.c_str()));}
    if(selected<0||check.status==L"fail"||check.status==L"warning")selected=static_cast<int>(index);
    SendMessageW(app.checkList,LB_SETCURSEL,selected,0);
}
void PaintMain(HDC dc) {
    const float width=W(app.window),height=H(app.window),mainX=282,mainWidth=width-314;
    Graphics graphics(dc); graphics.ScaleTransform(app.scale,app.scale);
    graphics.SetSmoothingMode(SmoothingModeAntiAlias); graphics.SetTextRenderingHint(TextRenderingHintClearTypeGridFit); graphics.Clear(Background);
    SolidBrush white(Color::White); graphics.FillRectangle(&white,RectF(0,0,248,height));
    Pen line(Line,1); graphics.DrawLine(&line,248.0f,0.0f,248.0f,height);
    Round(graphics,RectF(26,30,43,43),12,Accent); Text(graphics,L"F",34,29,26,43,30,Color::White,true);
    Text(graphics,L"FAA",83,30,125,26,21,Ink,true); Text(graphics,app.operation==Operation::LegacyUpdate?L"旧版更新过渡":L"安装与启动",84,57,120,22,12,Muted);
    const wchar_t* flow=app.operation==Operation::Install?L"安装与启动流程":app.operation==Operation::Uninstall?L"卸除流程":app.operation==Operation::LegacyUpdate?L"旧版更新过渡流程":L"备份恢复流程";
    Text(graphics,flow,28,110,190,24,12,Muted);
    const int count=StepCount(app.operation);
    for(int index=0;index<count;++index) {
        float y=151.0f+index*82; Step step=app.steps[index];
        if(step==Step::Active||step==Step::Failed) Round(graphics,RectF(16,y-10,216,68),10,step==Step::Failed?PaleError:PaleAccent);
        Color tint=step==Step::Complete||step==Step::Active?Accent:step==Step::Failed?Error:Muted;
        SolidBrush circle(step==Step::Complete?Accent:step==Step::Failed?Color(255,228,216):Color(239,243,246));
        graphics.FillEllipse(&circle,28.0f,y+3,28.0f,28.0f);
        if(step==Step::Complete) { Pen tick(Color::White,2);graphics.DrawLine(&tick,36.0f,y+17,41.0f,y+22);graphics.DrawLine(&tick,41.0f,y+22,49.0f,y+12); }
        else Text(graphics,step==Step::Failed?L"!":std::to_wstring(index+1),28,y+6,28,23,13,tint,true,StringAlignmentCenter);
        Text(graphics,StepName(app.operation,index),68,y,157,25,14,step==Step::Pending?Muted:Ink,step==Step::Active||step==Step::Failed);
        Text(graphics,StepDescription(app.operation,index),68,y+27,160,22,11,Muted);
        if(index<count-1) {Pen connector(Line,1);graphics.DrawLine(&connector,42.0f,y+39,42.0f,y+64);}
    }
    Text(graphics,L"FAA / 食物大战老鼠自动助手",28,height-34,208,20,10,Muted);
    Text(graphics,L"环境与版本管理",mainX,27,350,22,12,Muted);
    const wchar_t* heading=app.operation==Operation::Install?L"让 FAA 顺利启动":app.operation==Operation::Uninstall?L"卸除本地运行环境":app.operation==Operation::LegacyUpdate?L"完成旧版更新过渡":L"恢复到备份版本";
    Text(graphics,heading,mainX,52,mainWidth-90,40,27,Ink,true);
    if(!app.logExpanded||!app.rootValid) {
        Round(graphics,RectF(mainX,151,mainWidth,292),15,Color::White,Line);
        if(!app.rootValid) {
            SolidBrush errorCircle(Error);graphics.FillEllipse(&errorCircle,mainX+29,209.0f,54.0f,54.0f);
            Pen cross(Color::White,4);graphics.DrawLine(&cross,mainX+44,224.0f,mainX+68,248.0f);graphics.DrawLine(&cross,mainX+68,224.0f,mainX+44,248.0f);
            Text(graphics,L"启动器不在 FAA 根目录",mainX+98,210,mainWidth-130,40,24,Error,true);
            Text(graphics,L"请将此 EXE 放在 FAA 根目录中再启动。",mainX+98,256,mainWidth-130,30,14,Ink,true);
            Text(graphics,L"根目录应包含 LICENSE、uv.lock、pyproject.toml 和 function\\faa_main.py。",mainX+29,297,mainWidth-58,47,13,Muted);
            Text(graphics,app.rootProblem,mainX+29,354,mainWidth-58,46,12,Error);
        } else if(ChecksVisible()) {
            Text(graphics,app.state==State::Review?L"基础环境已就绪，有可选能力提示":app.title,mainX+24,171,mainWidth-48,31,20,app.state==State::Failed?Error:Ink,true);
            int passed=0,failed=0,warnings=0;for(const auto& item:app.checks){passed+=item.status==L"pass";failed+=item.status==L"fail";warnings+=item.status==L"warning";}
            Text(graphics,L"通过 "+std::to_wstring(passed)+L" · 失败 "+std::to_wstring(failed)+L" · 提示 "+std::to_wstring(warnings)+L"    选择项目查看处理建议",mainX+24,208,mainWidth-48,23,12,Muted);
            int selected=static_cast<int>(SendMessageW(app.checkList,LB_GETCURSEL,0,0));
            if(selected>=0&&static_cast<size_t>(selected)<app.checks.size()) {
                const auto& item=app.checks[selected];
                Text(graphics,item.detail,mainX+24,344,mainWidth-48,83,12,item.status==L"fail"?Error:item.status==L"warning"?Color(148,104,23):Muted);
            }
        } else if(RestorePickerVisible()) {
            Text(graphics,app.state==State::Failed?app.title:L"选择要恢复的备份",mainX+24,171,mainWidth-350,31,20,app.state==State::Failed?Error:Ink,true);
            if(app.backups.empty()) Text(graphics,L"暂未找到备份。请检查 FAA 根目录的 backups 文件夹。",mainX+24,223,mainWidth-48,55,13,Muted);
            int selected=static_cast<int>(SendMessageW(app.backupList,LB_GETCURSEL,0,0));
            if(selected>=0&&static_cast<size_t>(selected)<app.backups.size()) Text(graphics,app.backups[selected].summary,mainX+24,326,mainWidth-48,22,12,Ink);
            Text(graphics,app.state==State::Failed?app.detail:L"将恢复所选版本的文件和配置。当前文件会先备份；运行环境、日志和所选备份会保留。",mainX+24,355,mainWidth-48,43,12,app.state==State::Failed?Error:Muted);
        } else if(app.state==State::Blocked) {
            Text(graphics,app.title,mainX+24,172,mainWidth-48,31,22,Error,true);
            Text(graphics,L"以下程序正在使用此 FAA 的运行环境：",mainX+24,210,mainWidth-48,24,12,Muted);
            Text(graphics,L"关闭程序后点击“重新检测”。需要时可结束所列进程再继续。",mainX+24,353,mainWidth-48,39,12,Muted);
        } else if(app.operation==Operation::Uninstall&&(app.state==State::Idle||app.state==State::Cancelled)) {
            Text(graphics,L"只卸除当前 FAA 的本地环境",mainX+24,174,mainWidth-48,32,22,Ink,true);
            Text(graphics,L"本地安装工具 uv",mainX+24,224,mainWidth-48,22,13,Ink,true);
            Text(graphics,Join(app.root,L"plugins\\launcher_scripts\\bin"),mainX+24,250,mainWidth-48,24,12,Muted);
            Text(graphics,L"Python 虚拟环境 .venv",mainX+24,285,mainWidth-48,22,13,Ink,true);
            Text(graphics,Join(app.root,L".venv"),mainX+24,311,mainWidth-48,24,12,Muted);
            Text(graphics,app.state==State::Cancelled?L"已停止卸除，部分环境可能已移除；可以继续卸除，或返回安装重新准备。":L"配置、资源、日志、全局 uv 和全局 Python 都会保留。",mainX+24,354,mainWidth-48,40,12,Muted);
        } else {
            const bool failed=app.state==State::Failed||app.startupFailure;
            Text(graphics,app.state==State::Running?L"正在进行 · 第 "+std::to_wstring(app.stage+1)+L" 步":failed?L"需要处理":app.state==State::Monitoring?L"FAA 运行中":app.state==State::Success?L"操作完成":app.state==State::Cancelled?L"已暂停":L"准备就绪",mainX+25,173,mainWidth-50,25,12,failed?Error:Accent,true);
            Text(graphics,app.title.empty()?L"准备好开始了吗？":app.title,mainX+25,209,mainWidth-50,41,25,Ink,true);
            Text(graphics,app.detail.empty()?L"检查安装文件，准备 Python 和运行依赖，再为您打开 FAA。\n首次准备可能需要几分钟，每一步都会显示在这里。":app.detail,mainX+25,260,mainWidth-50,55,13,Muted);
            if(failed) {
                const std::wstring advice=app.operation==Operation::LegacyUpdate&&app.problem==Problem::Network?
                    L"检查 GitHub 连接、系统时间和代理可信证书后重试。Python 和依赖包镜像设置不影响源码下载。":
                    app.operation==Operation::Install?ProblemAdvice(app.problem):L"具体文件与处理结果已保留在运行详情中。处理后可以重试或重新选择操作。";
                Round(graphics,RectF(mainX+24,328,mainWidth-48,61),8,PaleError);Text(graphics,advice,mainX+37,339,mainWidth-74,47,12,Error);
            }
            else Text(graphics,app.operation==Operation::Uninstall?L"下次启动时会重新准备运行环境。":app.operation==Operation::Restore?L"恢复过程中请保持窗口打开；复制失败时会自动回滚。":app.debug?L"调试启动已开启：FAA 打开后保留此窗口并持续显示日志。":L"按安装包锁定的版本准备依赖，保留您的用户配置。",mainX+25,333,mainWidth-50,45,12,Muted);
            int completed=0;for(int i=0;i<count;++i) if(app.steps[i]==Step::Complete) ++completed;
            float railWidth=mainWidth-50;
            Round(graphics,RectF(mainX+25,418,railWidth,5),2.5f,Color(235,240,243));
            if(completed) Round(graphics,RectF(mainX+25,418,railWidth*completed/count,5),2.5f,Accent);
            if(app.state==State::Running&&completed<count) {float segment=railWidth/count,offset=(app.animation%100)/100.0f*(segment-25);Round(graphics,RectF(mainX+25+railWidth*completed/count+offset,418,25,5),2.5f,Color(111,195,173));}
            Text(graphics,L"已完成 "+std::to_wstring(completed)+L" / "+std::to_wstring(count)+L" 步",mainX+25,392,200,21,11,Muted);
        }
    }
    const float logY=app.logExpanded&&app.rootValid?151.0f:460.0f;
    Round(graphics,RectF(mainX,logY,mainWidth,height-logY-108),13,Color::White,Line);
    Text(graphics,app.state==State::Monitoring?L"运行详情 · 持续接收 FAA 日志":L"运行详情",mainX+18,logY+14,mainWidth-235,24,12,Ink,true);
    graphics.DrawLine(&line,mainX,height-91,width-32,height-91);
    Text(graphics,!app.rootValid?L"当前目录："+app.root:app.operation==Operation::Restore?L"恢复前会备份当前版本，所选备份不会被删除。":app.operation==Operation::Uninstall?L"仅移除当前目录中的本地 uv 与 .venv。":app.debug?L"调试启动：日志持续显示在此窗口中。":L"环境和日志位于当前 FAA 目录。",mainX,height-82,mainWidth,22,11,Muted);
}
void AppendLog(const std::wstring& message) {
    SYSTEMTIME time;GetLocalTime(&time);wchar_t prefix[32];swprintf(prefix,32,L"%02u:%02u:%02u  ",time.wHour,time.wMinute,time.wSecond);
    const std::wstring line=std::wstring(prefix)+message+L"\r\n";app.logBytes+=Utf8(line);
    if(app.logBytes.size()>1024*1024) app.logBytes.erase(0,app.logBytes.size()-1024*1024);
    if(GetWindowTextLengthW(app.log)>100000) {SendMessageW(app.log,EM_SETSEL,0,30000);SendMessageW(app.log,EM_REPLACESEL,FALSE,reinterpret_cast<LPARAM>(L""));}
    SendMessageW(app.log,EM_SETSEL,GetWindowTextLengthW(app.log),GetWindowTextLengthW(app.log));SendMessageW(app.log,EM_REPLACESEL,FALSE,reinterpret_cast<LPARAM>(line.c_str()));SendMessageW(app.log,EM_SCROLLCARET,0,0);
    if(!app.logFile.empty()) {HANDLE file=CreateFileW(app.logFile.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);if(file!=INVALID_HANDLE_VALUE){std::string bytes=Utf8(line);DWORD written=0;WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&written,NULL);CloseHandle(file);}}
}
bool OpenEnvironmentInstaller(const Event& failure) {
    const std::wstring installer=Join(app.root,L"FAA - 环境安装器.exe");
    std::wstring report;
    if(app.rootValid) {
        report=Join(app.root,L"logs\\launcher\\startup-failure-"+Timestamp()+L".txt");
        auto single=[](std::wstring value){for(auto& character:value)if(character==L'\r'||character==L'\n')character=L' ';return value;};
        std::string body="FAA_STARTUP_FAILURE_V1\n"+std::to_string(failure.stage)+"\n"+std::to_string(static_cast<int>(failure.problem))+"\n"+
            Utf8(single(failure.title))+"\n"+Utf8(single(failure.detail))+"\n"+app.logBytes;
        if(!MakeDirectories(Parent(report))||!WriteFileBytes(report,body))report.clear();
    }
    std::wstring command=QuoteArgument(installer);if(!report.empty())command+=L" --startup-error "+QuoteArgument(report);
    std::vector<wchar_t> buffer(command.begin(),command.end());buffer.push_back(0);STARTUPINFOW startup={};startup.cb=sizeof(startup);PROCESS_INFORMATION process={};
    if(Exists(installer)&&CreateProcessW(installer.c_str(),buffer.data(),NULL,NULL,FALSE,0,NULL,app.root.c_str(),&startup,&process)){
        CloseHandle(process.hThread);CloseHandle(process.hProcess);return true;
    }
    const DWORD launchError=GetLastError();
    std::wstring reason=Exists(installer)?L"无法打开环境安装器：\n"+SystemError(launchError):L"未找到环境安装器：\n"+installer;
    MessageBoxW(app.window,(failure.title+L"\n"+failure.detail+L"\n\n"+reason+L"\n请将环境安装器放在快速启动程序所在的 FAA 根目录，或重新解压完整发行包。\n\n启动日志："+app.logFile).c_str(),L"FAA 启动失败",MB_OK|MB_ICONERROR);
    return false;
}
bool ImportStartupFailure(const std::wstring& path) {
    WIN32_FILE_ATTRIBUTE_DATA attributes={};
    if(_wcsicmp(Parent(path).c_str(),Join(app.root,L"logs\\launcher").c_str())||BaseName(path).find(L"startup-failure-")!=0||
        !GetFileAttributesExW(path.c_str(),GetFileExInfoStandard,&attributes)||attributes.nFileSizeHigh||attributes.nFileSizeLow>2*1024*1024)return false;
    std::istringstream input(ReadFileBytes(path));std::string magic,stageText,problemText,title,detail;
    if(!std::getline(input,magic)||magic!="FAA_STARTUP_FAILURE_V1"||!std::getline(input,stageText)||!std::getline(input,problemText)||!std::getline(input,title)||!std::getline(input,detail))return false;
    int stage=-1,problem=-1;try{stage=std::stoi(stageText);problem=std::stoi(problemText);}catch(...){return false;}
    if(stage<0||stage>5||problem<0||problem>static_cast<int>(Problem::Other))return false;
    // 快速入口没有执行安装步骤；展示原始错误后等待用户从头选择环境操作。
    app.stage=0;app.state=State::Idle;app.startupFailure=true;app.problem=static_cast<Problem>(problem);app.title=Wide(title);app.detail=Wide(detail);
    for(auto& step:app.steps)step=Step::Pending;
    std::string line;while(std::getline(input,line))AppendLog(Wide(line));
    AppendLog(L"[启动失败] "+app.title+L"："+app.detail);return true;
}
void ReadSources() {
    const std::string config=ReadFileBytes(Join(app.root,L"pyproject.toml"));
    app.index=ReadTomlString(config,L"tool.uv.index",L"url");if(app.index.empty())app.index=L"https://pypi.org/simple";
    app.defaultPythonMirror=ReadTomlString(config,L"tool.uv",L"python-install-mirror");if(app.defaultPythonMirror.empty())app.defaultPythonMirror=L"https://github.com/astral-sh/python-build-standalone/releases/download";
}
std::wstring VersionAt(const std::wstring& root) {
    std::wistringstream input(Wide(ReadFileBytes(Join(root,L"function\\globals\\Extra.py"))));std::wstring line;
    while(std::getline(input,line)) {size_t begin=line.find_first_not_of(L" \t");if(begin==std::wstring::npos)continue;line=line.substr(begin);if(line.find(L"VERSION")!=0)continue;size_t equals=line.find(L'=');if(equals==std::wstring::npos||line.substr(7,equals-7).find_first_not_of(L" \t")!=std::wstring::npos)continue;size_t quote=line.find_first_of(L"\"'",equals+1);if(quote!=std::wstring::npos){size_t end=line.find(line[quote],quote+1);if(end!=std::wstring::npos)return line.substr(quote+1,end-quote-1);}}
    return L"未知版本";
}
std::wstring BackupSize(const BackupMetadata& metadata) {
    double value=static_cast<double>(metadata.bytes);const wchar_t* units[]={L"B",L"KB",L"MB",L"GB",L"TB"};int unit=0;
    while(value>=1024&&unit<4){value/=1024;++unit;}wchar_t text[64]={};swprintf(text,64,L"%.1f %ls",value,units[unit]);
    return metadata.sizeKnown?text:L"至少 "+std::wstring(text)+L"（部分内容不可读）";
}
void RefreshBackups() {
    const std::wstring previous=app.selectedBackup;app.backups.clear();SendMessageW(app.backupList,LB_RESETCONTENT,0,0);
    for(const auto& path:FindBackups(app.root)) {
        BackupMetadata metadata=ReadBackupMetadata(path);
        std::wstring name=BaseName(path),version=metadata.version.empty()?VersionAt(path):metadata.version,stamp=name.substr(name.find_last_of(L'.')+1),kind=name.find(L"FAA.before-restore.")==0?L"恢复前备份":L"更新前备份";
        if(stamp.size()==15&&stamp[8]==L'-')stamp=stamp.substr(0,4)+L"-"+stamp.substr(4,2)+L"-"+stamp.substr(6,2)+L" "+stamp.substr(9,2)+L":"+stamp.substr(11,2);
        auto shown=[](const std::wstring& value){return value.empty()?L"未记录":value;};
        std::wstring details=L"备份目录："+name+L"\n版本："+version+L"\nTag："+shown(metadata.tag)+L"\nPR："+shown(metadata.pr)+L"\n提交："+shown(metadata.commit)+L"\n大小："+BackupSize(metadata)+L"\n路径："+path;
        std::wstring error;if(!IsSafeBackup(app.root,path,error))details+=L"\n\n此备份不能恢复："+error;
        app.backups.push_back({path,version+L"  ·  "+stamp+L"  ·  "+kind+L"  ·  "+BackupSize(metadata),version,L"所选版本 "+version+L"  ·  当前版本 "+VersionAt(app.root),details});
    }
    for(const auto& backup:app.backups)SendMessageW(app.backupList,LB_ADDSTRING,0,reinterpret_cast<LPARAM>(backup.label.c_str()));
    app.selectedBackup.clear();
    if(!app.backups.empty()){int selected=0;for(size_t i=0;i<app.backups.size();++i)if(app.backups[i].path==previous)selected=static_cast<int>(i);SendMessageW(app.backupList,LB_SETCURSEL,selected,0);app.selectedBackup=app.backups[selected].path;app.steps[0]=Step::Complete;}else app.steps[0]=Step::Pending;
    SendMessageW(app.confirm,BM_SETCHECK,BST_UNCHECKED,0);
}
void Layout() {
    float width=W(app.window),height=H(app.window),mainWidth=width-314;
    Move(app.action,282,106,mainWidth,240);
    const float logY=app.logExpanded&&app.rootValid?151:460;
    Move(app.log,300,logY+40,mainWidth-36,height-logY-156);
    Move(app.expand,width-126,logY+8,78,28);Move(app.exportLog,width-218,logY+8,82,28);
    Move(app.backupList,306,app.state==State::Blocked?240:213,mainWidth-48,app.state==State::Blocked?102:104);
    Move(app.checkList,306,236,mainWidth-48,98);
    Move(app.refresh,width-138,171,90,28);Move(app.confirm,306,402,mainWidth-48,25);Move(app.force,width-226,398,170,29);
    Move(app.backupDetails,width-338,171,90,28);Move(app.deleteBackup,width-238,171,90,28);
    Move(app.network,282,height-55,108,34);Move(app.settings,app.operation!=Operation::Uninstall?402:282,height-55,108,34);Move(app.repair,522,height-55,100,34);
    Move(app.cancel,width-314,height-55,112,34);Move(app.start,width-188,height-55,156,34);
    InvalidateRect(app.window,NULL,FALSE);
}
void UpdateControls() {
    const bool running=app.state==State::Running,valid=app.rootValid;
    auto visible=[&](HWND control,bool show){if(control)ShowWindow(control,show?SW_SHOW:SW_HIDE);};
    const bool legacy=app.operation==Operation::LegacyUpdate;
    visible(app.action,valid&&!legacy);EnableWindow(app.action,valid&&!running&&!legacy);
    visible(app.network,valid&&!legacy&&app.operation!=Operation::Uninstall);EnableWindow(app.network,valid&&!running);
    visible(app.settings,valid&&!legacy);EnableWindow(app.settings,valid&&!running);
    visible(app.exportLog,valid);EnableWindow(app.exportLog,valid);visible(app.expand,valid);EnableWindow(app.expand,valid);SetWindowTextW(app.expand,app.logExpanded?L"收起":L"放大");
    const bool picker=valid&&!app.logExpanded&&RestorePickerVisible(),blocked=valid&&!app.logExpanded&&app.state==State::Blocked;
    visible(app.backupList,(picker&&!app.backups.empty())||blocked);visible(app.refresh,picker);visible(app.confirm,valid&&!app.logExpanded&&ConfirmationVisible());visible(app.force,blocked&&!app.blockers.empty());
    visible(app.backupDetails,picker);visible(app.deleteBackup,picker);EnableWindow(app.backupDetails,!app.backups.empty());EnableWindow(app.deleteBackup,!app.backups.empty());
    visible(app.checkList,valid&&!app.logExpanded&&ChecksVisible());
    SetWindowTextW(app.confirm,app.operation==Operation::Restore?L"确认恢复所选备份，并先保存当前版本":L"确认卸除上述本地运行环境");
    const bool confirmed=SendMessageW(app.confirm,BM_GETCHECK,0,0)==BST_CHECKED;
    bool canStart=valid&&!running&&app.state!=State::Monitoring;
    const bool deleteFailed=app.operation==Operation::Restore&&app.state==State::Failed&&app.stage==0;
    if(deleteFailed)canStart=false;
    if(ConfirmationVisible())canStart=canStart&&confirmed&&(app.operation!=Operation::Restore||!app.backups.empty());
    visible(app.start,valid);EnableWindow(app.start,canStart);
    const bool cancellable=running&&app.operation!=Operation::Restore&&!legacy;visible(app.cancel,cancellable);EnableWindow(app.cancel,cancellable);
    const bool repair=valid&&app.operation!=Operation::Uninstall&&(app.operation==Operation::Install||app.restoreFilesReady)&&app.state==State::Failed&&(app.problem==Problem::Dependency||app.problem==Problem::Compatibility||app.problem==Problem::Startup);visible(app.repair,repair);
    const wchar_t* label=app.operation==Operation::Install?L"准备并启动 FAA":app.operation==Operation::Uninstall?L"卸除运行环境":L"恢复所选备份";
    if(app.state==State::Review)label=L"继续启动 FAA";
    else if(app.state==State::Blocked)label=L"重新检测";
    else if(app.state==State::Monitoring)label=L"FAA 正在运行";
    else if(app.state==State::Success)label=app.operation==Operation::Uninstall?L"返回安装":L"关闭";
    else if(app.state==State::Failed)label=legacy?L"重试更新过渡":deleteFailed?L"请重试删除备份":app.operation==Operation::Restore?(app.restoreFilesReady?L"重试启动":L"重试恢复"):L"重试这一步";
    else if(app.state==State::Cancelled)label=L"继续";
    SetWindowTextW(app.start,label);Layout();
}
void Reset() {
    app.startupFailure=false;
    StopMonitor();for(auto& step:app.steps)step=Step::Pending;
    app.checks.clear();SendMessageW(app.checkList,LB_RESETCONTENT,0,0);
    app.state=State::Idle;app.stage=0;app.restoreFilesReady=false;app.logExpanded=false;app.faaExited=false;app.title.clear();app.detail.clear();app.logFile.clear();app.logBytes.clear();app.blockers.clear();SetWindowTextW(app.log,L"");
    SendMessageW(app.confirm,BM_SETCHECK,BST_UNCHECKED,0);
    if(app.operation==Operation::Restore)RefreshBackups();
    AppendLog(app.rootValid?L"[启动器] 已就绪："+std::wstring(app.operation==Operation::Install?L"安装与启动":app.operation==Operation::Uninstall?L"卸除运行环境":app.operation==Operation::LegacyUpdate?L"旧版更新过渡":L"恢复备份"):L"[启动器] 已锁定："+app.rootProblem);
    UpdateControls();
}
void ChangeOperation() {
    app.operation=static_cast<Operation>(SendMessageW(app.action,CB_GETCURSEL,0,0));
    Reset();
}
void Begin(bool repair=false,bool force=false,bool removeBackup=false) {
    if(app.state==State::Running||app.state==State::Monitoring||!app.rootValid)return;
    if(app.state==State::Success) {
        if(app.operation!=Operation::Uninstall){DestroyWindow(app.window);return;}
        SendMessageW(app.action,CB_SETCURSEL,0,0);ChangeOperation();return;
    }
    if(!removeBackup&&ConfirmationVisible()&&SendMessageW(app.confirm,BM_GETCHECK,0,0)!=BST_CHECKED)return;
    if(app.operation==Operation::Install&&app.state==State::Idle&&Exists(Join(app.root,L".git"))&&MessageBoxW(app.window,L"当前是源码开发目录。同步运行环境可能移除开发依赖。\n\n是否继续准备此目录的运行环境？",L"确认当前目录",MB_OKCANCEL|MB_ICONINFORMATION)!=IDOK)return;
    std::unique_ptr<Options> options(new Options);options->window=app.window;options->cancel=app.cancelEvent;options->debug=app.debug;options->operation=app.operation;options->force=force;options->blockers=app.blockers;
    options->removeBackup=removeBackup;
    options->root=app.root;options->pythonMirror=app.pythonMirror;options->packageIndex=app.packageIndex;
    bool retry=app.state==State::Failed||app.state==State::Cancelled||app.state==State::Blocked;
    options->start=app.state==State::Review?5:app.operation==Operation::Install?(retry?std::min(app.stage,4):0):app.operation==Operation::Restore?(app.restoreFilesReady?4:1):0;
    if(repair)options->start=app.operation==Operation::Install?3:4;
    if(removeBackup)options->start=0;
    if(options->start<=4){app.checks.clear();SendMessageW(app.checkList,LB_RESETCONTENT,0,0);}
    options->reinstall=repair;
    if(app.operation==Operation::Restore) {if(app.selectedBackup.empty())return;options->backup=app.selectedBackup;}
    for(int index=options->start;index<StepCount(app.operation);++index)app.steps[index]=Step::Pending;
    if(app.operation==Operation::Restore)app.steps[0]=Step::Complete;
    ResetEvent(app.cancelEvent);if(app.worker){CloseHandle(app.worker);app.worker=NULL;}
    const std::wstring directory=Join(app.root,app.operation==Operation::LegacyUpdate?L"update_cache\\legacy_bridge":L"logs\\launcher");if(MakeDirectories(directory))app.logFile=Join(directory,L"launcher-"+Timestamp()+L".log");
    app.state=State::Running;app.startupFailure=false;app.faaExited=false;app.closeAfterCancel=false;
    AppendLog(L"[启动器] 开始操作："+std::wstring(app.operation==Operation::Install?L"安装与启动":app.operation==Operation::Uninstall?L"卸除运行环境":L"恢复备份"));
    UpdateControls();app.worker=CreateThread(NULL,0,Worker,options.get(),0,NULL);
    if(app.worker)options.release();else {app.state=State::Failed;app.title=L"无法开始操作";app.detail=SystemError(GetLastError());UpdateControls();}
}
std::wstring ControlText(HWND window) {std::vector<wchar_t> buffer(GetWindowTextLengthW(window)+1);GetWindowTextW(window,buffer.data(),static_cast<int>(buffer.size()));return buffer.data();}
struct MonitorData {Options options;std::wstring path;DWORD pid;HANDLE process=NULL;~MonitorData(){if(process)CloseHandle(process);}};
DWORD WINAPI MonitorLog(void* value) {
    std::unique_ptr<MonitorData> data(reinterpret_cast<MonitorData*>(value));
    HANDLE process=data->process;
    HANDLE file=CreateFileW(data->path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    std::string pending;
    auto drain=[&](bool flush){
        if(file!=INVALID_HANDLE_VALUE){char bytes[8192];DWORD read=0;while(ReadFile(file,bytes,sizeof(bytes),&read,NULL)&&read)pending.append(bytes,read);}
        size_t end;while((end=pending.find_first_of("\r\n"))!=std::string::npos){std::string line=pending.substr(0,end);pending.erase(0,end+1);if(!line.empty())WorkerLog(data->options,Wide(line));}
        if(flush&&!pending.empty()){WorkerLog(data->options,Wide(pending));pending.clear();}
    };
    bool exited=false;
    while(WaitForSingleObject(data->options.cancel,100)==WAIT_TIMEOUT){drain(false);if(!process||WaitForSingleObject(process,0)==WAIT_OBJECT_0){exited=true;break;}}
    drain(true);if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);
    if(exited){DWORD code=0;if(process)GetExitCodeProcess(process,&code);Event* event=new Event(EventKind::ProcessExit,4);event->pid=code;Post(data->options,event);}
    return 0;
}
void StopMonitor() {++app.monitorId;if(app.monitor){SetEvent(app.monitorStop);WaitForSingleObject(app.monitor,3000);CloseHandle(app.monitor);app.monitor=NULL;}if(app.monitorStop){CloseHandle(app.monitorStop);app.monitorStop=NULL;}}
void StartMonitor(Event& event) {
    StopMonitor();app.monitorStop=CreateEventW(NULL,TRUE,FALSE,NULL);
    std::unique_ptr<MonitorData> data(new MonitorData);data->options.window=app.window;data->options.cancel=app.monitorStop;data->options.monitorId=app.monitorId;data->path=event.detail;data->pid=event.pid;data->process=event.process;event.process=NULL;
    app.monitor=CreateThread(NULL,0,MonitorLog,data.get(),0,NULL);if(app.monitor)data.release();else AppendLog(L"[日志] 无法启动实时读取，原始日志："+event.detail);
}
void DrawButton(DRAWITEMSTRUCT* item);
void DrawCombo(DRAWITEMSTRUCT* item) {
    int selected=static_cast<int>(item->itemID);
    if(selected<0) selected=static_cast<int>(SendMessageW(item->hwndItem,CB_GETCURSEL,0,0));
    const int length=static_cast<int>(SendMessageW(item->hwndItem,CB_GETLBTEXTLEN,selected,0));
    if(selected<0||length<0) return;
    std::vector<wchar_t> caption(length+1);
    SendMessageW(item->hwndItem,CB_GETLBTEXT,selected,reinterpret_cast<LPARAM>(caption.data()));
    Graphics graphics(item->hDC); graphics.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    const RECT& rect=item->rcItem;
    const bool highlighted=(item->itemState&ODS_SELECTED)&&!(item->itemState&ODS_COMBOBOXEDIT);
    SolidBrush background(highlighted?PaleAccent:Color::White);
    graphics.FillRectangle(&background,RectF(static_cast<float>(rect.left),static_cast<float>(rect.top),
        static_cast<float>(rect.right-rect.left),static_cast<float>(rect.bottom-rect.top)));
    Font font(UiFontFamily(),12*app.scale,FontStyleRegular,UnitPixel);
    StringFormat format; format.SetLineAlignment(StringAlignmentCenter); format.SetTrimming(StringTrimmingEllipsisCharacter);
    SolidBrush text((item->itemState&ODS_DISABLED)?Muted:Ink);
    graphics.DrawString(caption.data(),-1,&font,RectF(static_cast<float>(rect.left+Px(8)),static_cast<float>(rect.top),
        static_cast<float>(rect.right-rect.left-Px(12)),static_cast<float>(rect.bottom-rect.top)),&format,&text);
}
void DrawButton(DRAWITEMSTRUCT* item);
struct DownloadSource { const wchar_t* name; const wchar_t* url; };
const DownloadSource PythonSources[] = {
    {L"npmmirror 镜像 -国内用户使用",L"https://registry.npmmirror.com/-/binary/python-build-standalone"},
    {L"中国科学技术大学镜像 -国内用户使用",L"https://mirrors.ustc.edu.cn/github-release/astral-sh/python-build-standalone"},
    {L"官方源（GitHub） -国外用户使用",L"https://github.com/astral-sh/python-build-standalone/releases/download"},
    {L"自定义",L""}
};
const DownloadSource PackageSources[] = {
    {L"清华大学镜像 -国内用户使用",L"https://pypi.tuna.tsinghua.edu.cn/simple"},
    {L"中国科学技术大学镜像 -国内用户使用",L"https://mirrors.ustc.edu.cn/pypi/simple"},
    {L"阿里云镜像 -国内用户使用",L"https://mirrors.aliyun.com/pypi/simple"},
    {L"腾讯云镜像 -国内用户使用",L"https://mirrors.cloud.tencent.com/pypi/simple"},
    {L"华为云镜像 -国内用户使用",L"https://repo.huaweicloud.com/repository/pypi/simple"},
    {L"官方源（PyPI） -国外用户使用",L"https://pypi.org/simple"},
    {L"自定义",L""}
};
const int PythonSourceCount=sizeof(PythonSources)/sizeof(PythonSources[0]);
const int PackageSourceCount=sizeof(PackageSources)/sizeof(PackageSources[0]);
struct NetworkDialog {
    HWND window,labels[2],sources[2],urls[2],apply,cancel;
    bool accepted;
    int customY[2],footerY;
    std::wstring mirror,packageIndex,error;
};
bool CustomSource(HWND source,int count) { return SendMessageW(source,CB_GETCURSEL,0,0)==count-1; }
std::wstring CleanSourceUrl(const std::wstring& value) {
    const size_t first=value.find_first_not_of(L" \t\r\n");
    if(first==std::wstring::npos) return L"";
    std::wstring result=value.substr(first,value.find_last_not_of(L" \t\r\n")-first+1);
    while(!result.empty()&&result.back()==L'/') result.pop_back();
    return result;
}
void FillSources(HWND combo,HWND input,const DownloadSource* choices,int count,const std::wstring& value) {
    int selected=count-1;
    for(int index=0;index<count;++index) {
        SendMessageW(combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(choices[index].name));
        if(index<count-1&&CleanSourceUrl(value)==choices[index].url) selected=index;
    }
    SendMessageW(combo,CB_SETCURSEL,selected,0);
    SetWindowTextW(input,selected==count-1?value.c_str():L"");
}
void LayoutNetwork(NetworkDialog& dialog) {
    int y=84;
    for(int group=0;group<2;++group) {
        const bool custom=CustomSource(dialog.sources[group],group==0?PythonSourceCount:PackageSourceCount);
        Move(dialog.labels[group],28,static_cast<float>(y),568,22);
        Move(dialog.sources[group],28,static_cast<float>(y+28),568,240);
        dialog.customY[group]=y+68;
        Move(dialog.urls[group],28,static_cast<float>(dialog.customY[group]),568,29);
        ShowWindow(dialog.urls[group],custom?SW_SHOW:SW_HIDE);
        EnableWindow(dialog.urls[group],custom);
        y+=custom?130:86;
    }
    dialog.footerY=y+2;
    Move(dialog.cancel,378,static_cast<float>(y+44),98,34);
    Move(dialog.apply,488,static_cast<float>(y+44),108,34);
    RECT rect={0,0,Px(610),Px(static_cast<float>(y+102))};
    AdjustWindowRectEx(&rect,static_cast<DWORD>(GetWindowLongPtrW(dialog.window,GWL_STYLE)),FALSE,WS_EX_DLGMODALFRAME);
    SetWindowPos(dialog.window,NULL,0,0,rect.right-rect.left,rect.bottom-rect.top,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
    InvalidateRect(dialog.window,NULL,TRUE);
}
std::wstring SelectedSource(HWND combo,HWND input,const DownloadSource* choices,int count) {
    const int selected=static_cast<int>(SendMessageW(combo,CB_GETCURSEL,0,0));
    return selected>=0&&selected<count-1?choices[selected].url:CleanSourceUrl(ControlText(input));
}
LRESULT CALLBACK NetworkProc(HWND window,UINT message,WPARAM wParam,LPARAM lParam) {
    NetworkDialog* dialog=reinterpret_cast<NetworkDialog*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(message==WM_CREATE) {
        dialog=reinterpret_cast<NetworkDialog*>(reinterpret_cast<CREATESTRUCTW*>(lParam)->lpCreateParams);
        SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(dialog)); dialog->window=window;
        auto control=[&](const wchar_t* type,const wchar_t* text,DWORD style,int id,float x,float y,float width,float height) {
            HWND child=CreateWindowExW(0,type,text,WS_CHILD|WS_VISIBLE|style,
                Px(x),Px(y),Px(width),Px(height),window,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(NULL),NULL);
            SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(app.bodyFont),TRUE); return child;
        };
        for(int group=0;group<2;++group) {
            dialog->labels[group]=control(L"STATIC",group==0?L"Python 下载源":L"Python 依赖包下载源",0,0,0,0,0,0);
            dialog->sources[group]=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS|WS_TABSTOP,201+group*2,0,0,0,0);
            dialog->urls[group]=control(L"EDIT",L"",ES_AUTOHSCROLL|WS_TABSTOP,202+group*2,0,0,0,0);
            SendMessageW(dialog->urls[group],EM_SETCUEBANNER,FALSE,reinterpret_cast<LPARAM>(group==0?
                L"输入 Python 下载镜像的根网址（https://…）":L"输入依赖包下载源网址（https://…/simple）"));
        }
        FillSources(dialog->sources[0],dialog->urls[0],PythonSources,PythonSourceCount,app.pythonMirror.empty()?app.defaultPythonMirror:app.pythonMirror);
        FillSources(dialog->sources[1],dialog->urls[1],PackageSources,PackageSourceCount,app.packageIndex.empty()?app.index:app.packageIndex);
        dialog->cancel=control(L"BUTTON",L"取消",BS_OWNERDRAW|WS_TABSTOP,IDCANCEL,0,0,0,0);
        dialog->apply=control(L"BUTTON",L"应用设置",BS_OWNERDRAW|WS_TABSTOP,IDOK,0,0,0,0);
        LayoutNetwork(*dialog);
        SetFocus(dialog->sources[0]); return 0;
    }
    if(message==WM_PAINT||message==WM_PRINTCLIENT) {
        PAINTSTRUCT paint={}; HDC dc=message==WM_PAINT?BeginPaint(window,&paint):reinterpret_cast<HDC>(wParam);
        Graphics graphics(dc); graphics.ScaleTransform(app.scale,app.scale);
        graphics.Clear(Color::White); graphics.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
        graphics.SetSmoothingMode(SmoothingModeAntiAlias);
        Text(graphics,L"网络设置",28,23,560,38,23,Ink,true);
        Text(graphics,L"分别选择 Python 和依赖包的下载位置。",28,57,568,22,12,Muted);
        if(dialog) {
            for(int group=0;group<2;++group) if(CustomSource(dialog->sources[group],group==0?PythonSourceCount:PackageSourceCount))
                Round(graphics,RectF(27,static_cast<float>(dialog->customY[group]-1),570,31),5,Color::White,Color(196,206,213));
            Text(graphics,dialog->error.empty()?L"设置仅对本次启动器运行有效。":dialog->error,28,static_cast<float>(dialog->footerY),568,37,12,dialog->error.empty()?Muted:Error);
        }
        if(message==WM_PAINT) EndPaint(window,&paint); return 0;
    }
    if(message==WM_MEASUREITEM) { reinterpret_cast<MEASUREITEMSTRUCT*>(lParam)->itemHeight=Px(24); return TRUE; }
    if(message==WM_DRAWITEM) {
        DRAWITEMSTRUCT* item=reinterpret_cast<DRAWITEMSTRUCT*>(lParam);
        if(item->CtlType==ODT_COMBOBOX) DrawCombo(item); else DrawButton(item);
        return TRUE;
    }
    if(message==WM_CTLCOLORSTATIC||message==WM_CTLCOLOREDIT) {
        SetTextColor(reinterpret_cast<HDC>(wParam),RGB(69,86,99)); SetBkColor(reinterpret_cast<HDC>(wParam),RGB(255,255,255));
        return reinterpret_cast<LRESULT>(GetStockObject(WHITE_BRUSH));
    }
    if(message==WM_COMMAND&&dialog) {
        const int id=LOWORD(wParam);
        if((id==201||id==203)&&HIWORD(wParam)==CBN_SELCHANGE) {
            dialog->error.clear(); LayoutNetwork(*dialog); return 0;
        }
        if(id==IDCANCEL) { DestroyWindow(window); return 0; }
        if(id==IDOK) {
            dialog->mirror=SelectedSource(dialog->sources[0],dialog->urls[0],PythonSources,PythonSourceCount);
            dialog->packageIndex=SelectedSource(dialog->sources[1],dialog->urls[1],PackageSources,PackageSourceCount);
            for(int group=0;group<2;++group) if(!ValidNetworkUrl(group==0?dialog->mirror:dialog->packageIndex,false)) {
                dialog->error=(group==0?L"Python 下载源：":L"依赖包下载源：")+std::wstring(L"请填写完整的 http:// 或 https:// 网址，不能包含空格。");
                SetFocus(dialog->urls[group]); InvalidateRect(window,NULL,TRUE); return 0;
            }
            dialog->accepted=true; DestroyWindow(window); return 0;
        }
    }
    if(message==WM_CLOSE) { DestroyWindow(window); return 0; }
    return DefWindowProcW(window,message,wParam,lParam);
}
void OpenNetwork() {
    NetworkDialog dialog={};
    RECT owner; GetWindowRect(app.window,&owner);
    HWND window=CreateWindowExW(WS_EX_DLGMODALFRAME,L"FAA.Network.Native",L"网络设置 · FAA 启动助手",WS_CAPTION|WS_SYSMENU,
        owner.left+(owner.right-owner.left-Px(626))/2,owner.top+(owner.bottom-owner.top-Px(430))/2,Px(626),Px(430),app.window,NULL,GetModuleHandleW(NULL),&dialog);
    if(!window) return;
    EnableWindow(app.window,FALSE); ShowWindow(window,SW_SHOW);
    MSG message;
    while(IsWindow(window)&&GetMessageW(&message,NULL,0,0)>0) if(!IsDialogMessageW(window,&message)) { TranslateMessage(&message); DispatchMessageW(&message); }
    EnableWindow(app.window,TRUE); SetForegroundWindow(app.window);
    if(dialog.accepted) {
        app.pythonMirror=dialog.mirror; app.packageIndex=dialog.packageIndex;
        // 自定义网址可能携带凭据，因此不把用户填写的地址主动写入日志。
        AppendLog(L"[启动器] 本次网络设置已更新，可以重试当前步骤。");
        UpdateControls();
    }
}
struct SettingsDialog {HWND check;bool accepted=false,debug=false;};
LRESULT CALLBACK SettingsProc(HWND window,UINT message,WPARAM wParam,LPARAM lParam) {
    SettingsDialog* dialog=reinterpret_cast<SettingsDialog*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(message==WM_CREATE){
        dialog=reinterpret_cast<SettingsDialog*>(reinterpret_cast<CREATESTRUCTW*>(lParam)->lpCreateParams);SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(dialog));
        auto control=[&](const wchar_t* type,const wchar_t* title,DWORD style,int id,int x,int y,int width,int height){HWND child=CreateWindowExW(0,type,title,WS_CHILD|WS_VISIBLE|style,Px(x),Px(y),Px(width),Px(height),window,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(NULL),NULL);SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(app.bodyFont),TRUE);return child;};
        control(L"STATIC",L"启动方式",0,0,24,20,480,30);
        dialog->check=control(L"BUTTON",L"调试启动：保留日志窗口",BS_AUTOCHECKBOX|WS_TABSTOP,601,24,63,480,28);
        SendMessageW(dialog->check,BM_SETCHECK,dialog->debug?BST_CHECKED:BST_UNCHECKED,0);
        control(L"STATIC",L"FAA 打开后保留此安装器，持续显示运行输出和异常。\n日志可在右侧放大查看，关闭安装器后 FAA 继续运行。",0,0,44,102,450,54);
        control(L"BUTTON",L"取消",BS_OWNERDRAW|WS_TABSTOP,IDCANCEL,300,178,90,34);
        control(L"BUTTON",L"应用设置",BS_OWNERDRAW|WS_TABSTOP,IDOK,402,178,110,34);return 0;
    }
    if(message==WM_PAINT||message==WM_PRINTCLIENT){PAINTSTRUCT paint={};HDC dc=message==WM_PAINT?BeginPaint(window,&paint):reinterpret_cast<HDC>(wParam);RECT area={};GetClientRect(window,&area);FillRect(dc,&area,reinterpret_cast<HBRUSH>(GetStockObject(WHITE_BRUSH)));if(message==WM_PAINT)EndPaint(window,&paint);return 0;}
    if(message==WM_DRAWITEM){DrawButton(reinterpret_cast<DRAWITEMSTRUCT*>(lParam));return TRUE;}
    if(message==WM_CTLCOLORSTATIC||message==WM_CTLCOLORBTN){SetBkColor(reinterpret_cast<HDC>(wParam),RGB(255,255,255));return reinterpret_cast<LRESULT>(GetStockObject(WHITE_BRUSH));}
    if(message==WM_COMMAND&&dialog){if(LOWORD(wParam)==IDOK){dialog->debug=SendMessageW(dialog->check,BM_GETCHECK,0,0)==BST_CHECKED;dialog->accepted=true;DestroyWindow(window);return 0;}if(LOWORD(wParam)==IDCANCEL){DestroyWindow(window);return 0;}}
    if(message==WM_CLOSE){DestroyWindow(window);return 0;}
    return DefWindowProcW(window,message,wParam,lParam);
}
void OpenSettings(){
    SettingsDialog dialog;dialog.debug=app.debug;RECT owner={};GetWindowRect(app.window,&owner);
    HWND window=CreateWindowExW(WS_EX_DLGMODALFRAME,L"FAA.Settings.Native",L"额外设置",WS_CAPTION|WS_SYSMENU,owner.left+(owner.right-owner.left-Px(550))/2,owner.top+(owner.bottom-owner.top-Px(265))/2,Px(550),Px(265),app.window,NULL,GetModuleHandleW(NULL),&dialog);
    if(!window)return;EnableWindow(app.window,FALSE);ShowWindow(window,SW_SHOW);MSG message;
    while(IsWindow(window)&&GetMessageW(&message,NULL,0,0)>0)if(!IsDialogMessageW(window,&message)){TranslateMessage(&message);DispatchMessageW(&message);}
    EnableWindow(app.window,TRUE);SetForegroundWindow(app.window);
    if(dialog.accepted){app.debug=dialog.debug;AppendLog(app.debug?L"[设置] 已开启调试启动，FAA 打开后保留日志窗口。":L"[设置] 已使用普通启动方式。");UpdateControls();}
}
void ExportLog() {
    wchar_t path[32768]=L"FAA-启动日志.log";
    OPENFILENAMEW save={}; save.lStructSize=sizeof(save); save.hwndOwner=app.window;
    save.lpstrFilter=L"日志文件 (*.log)\0*.log\0文本文件 (*.txt)\0*.txt\0\0"; save.lpstrFile=path; save.nMaxFile=32768;
    save.lpstrTitle=L"保存 FAA 启动日志"; save.Flags=OFN_OVERWRITEPROMPT|OFN_PATHMUSTEXIST; save.lpstrDefExt=L"log";
    if(GetSaveFileNameW(&save)&&!WriteFileBytes(path,"\xEF\xBB\xBF"+app.logBytes)) MessageBoxW(app.window,SystemError(GetLastError()).c_str(),L"日志未能保存",MB_OK|MB_ICONERROR);
}
void DrawButton(DRAWITEMSTRUCT* item) {
    RECT rect=item->rcItem; int width=rect.right,height=rect.bottom;
    Graphics graphics(item->hDC); graphics.SetSmoothingMode(SmoothingModeAntiAlias); graphics.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    const bool primary=item->CtlID==ID_START||item->CtlID==IDOK, disabled=(item->itemState&ODS_DISABLED)!=0, pressed=(item->itemState&ODS_SELECTED)!=0;
    const Color fill=disabled?Color(227,233,236):primary?(pressed?Color(6,107,97):Accent):Color::White;
    Round(graphics,RectF(1,1,static_cast<float>(width-2),static_cast<float>(height-2)),7*app.scale,fill,primary?fill:Line);
    Font font(UiFontFamily(),12*app.scale,primary?FontStyleBold:FontStyleRegular,UnitPixel);
    StringFormat format; format.SetAlignment(StringAlignmentCenter); format.SetLineAlignment(StringAlignmentCenter);
    SolidBrush brush(disabled?Muted:primary?Color::White:Ink);
    const std::wstring caption=ControlText(item->hwndItem);
    graphics.DrawString(caption.c_str(),-1,&font,RectF(0,0,static_cast<float>(width),static_cast<float>(height)),&format,&brush);
    if(item->itemState&ODS_FOCUS) { RECT focus={4,4,width-4,height-4}; DrawFocusRect(item->hDC,&focus); }
}
LRESULT CALLBACK MainProc(HWND window,UINT message,WPARAM wParam,LPARAM lParam) {
    if(message==WM_CREATE) {
        app.window=window;
        app.bodyFont=CreateFontW(-Px(13),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,UiFontFamily());
        app.monoFont=CreateFontW(-Px(12),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Consolas");
        auto control=[&](const wchar_t* type,const wchar_t* text,DWORD style,int id) {
            HWND child=CreateWindowExW(0,type,text,WS_CHILD|WS_VISIBLE|style,0,0,0,0,window,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(NULL),NULL);
            SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(app.bodyFont),TRUE); return child;
        };
        app.action=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS|WS_TABSTOP,ID_ACTION);
        const wchar_t* actions[]={L"安装并启动",L"卸除运行环境",L"恢复到备份"};
        for(const auto* action:actions)SendMessageW(app.action,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(action));
        SendMessageW(app.action,CB_SETCURSEL,0,0);
        app.start=control(L"BUTTON",L"准备并启动 FAA",BS_OWNERDRAW|WS_TABSTOP,ID_START);
        app.cancel=control(L"BUTTON",L"停止准备",BS_OWNERDRAW|WS_TABSTOP,ID_CANCEL);
        app.network=control(L"BUTTON",L"网络设置",BS_OWNERDRAW|WS_TABSTOP,ID_NETWORK);
        app.exportLog=control(L"BUTTON",L"保存日志",BS_OWNERDRAW|WS_TABSTOP,ID_EXPORT);
        app.repair=control(L"BUTTON",L"修复依赖",BS_OWNERDRAW|WS_TABSTOP,ID_REPAIR);
        app.settings=control(L"BUTTON",L"额外设置",BS_OWNERDRAW|WS_TABSTOP,ID_SETTINGS);
        app.expand=control(L"BUTTON",L"放大",BS_OWNERDRAW|WS_TABSTOP,ID_EXPAND);
        app.refresh=control(L"BUTTON",L"刷新备份",BS_OWNERDRAW|WS_TABSTOP,ID_REFRESH);
        app.backupDetails=control(L"BUTTON",L"备份详情",BS_OWNERDRAW|WS_TABSTOP,ID_BACKUP_DETAILS);
        app.deleteBackup=control(L"BUTTON",L"删除备份",BS_OWNERDRAW|WS_TABSTOP,ID_DELETE_BACKUP);
        app.force=control(L"BUTTON",L"结束所列进程并继续",BS_OWNERDRAW|WS_TABSTOP,ID_FORCE);
        app.confirm=control(L"BUTTON",L"",BS_AUTOCHECKBOX|WS_TABSTOP,ID_CONFIRM);
        app.backupList=control(L"LISTBOX",L"",LBS_NOTIFY|LBS_NOINTEGRALHEIGHT|WS_VSCROLL|WS_BORDER|WS_TABSTOP,ID_BACKUPS);
        app.checkList=control(L"LISTBOX",L"",LBS_NOTIFY|LBS_NOINTEGRALHEIGHT|WS_VSCROLL|WS_BORDER|WS_TABSTOP,ID_CHECKS);
        app.log=control(L"EDIT",L"",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL|WS_TABSTOP,ID_LOG);
        SendMessageW(app.log,WM_SETFONT,reinterpret_cast<WPARAM>(app.monoFont),TRUE); SendMessageW(app.log,EM_SETLIMITTEXT,128000,0);
        app.cancelEvent=CreateEventW(NULL,TRUE,FALSE,NULL);
        // 过渡流程不属于用户可选的安装操作，不能被组合框默认项重置成安装流程。
        if(app.operation==Operation::LegacyUpdate)Reset();else ChangeOperation();
        if(!app.rootValid) {
            app.title=L"启动器不在 FAA 根目录";
            app.detail=L"请将安装器放在 FAA 根目录中再启动。";
            AppendLog(L"[启动器] 根目录校验失败："+app.rootProblem);
        }
        SetTimer(window,1,40,NULL); return 0;
    }
    if(message==WM_SIZE) { if(app.log) Layout(); return 0; }
    if(message==WM_GETMINMAXINFO) {
        MINMAXINFO* limits=reinterpret_cast<MINMAXINFO*>(lParam); limits->ptMinTrackSize.x=Px(1000); limits->ptMinTrackSize.y=Px(730); return 0;
    }
    if(message==WM_ERASEBKGND) return 1;
    if(message==WM_PRINTCLIENT) { PaintMain(reinterpret_cast<HDC>(wParam)); return 0; }
    if(message==WM_PAINT) {
        PAINTSTRUCT paint; HDC dc=BeginPaint(window,&paint);
        RECT rect; GetClientRect(window,&rect); HDC buffer=CreateCompatibleDC(dc); HBITMAP bitmap=CreateCompatibleBitmap(dc,rect.right,rect.bottom);
        HGDIOBJ previous=SelectObject(buffer,bitmap); PaintMain(buffer); BitBlt(dc,0,0,rect.right,rect.bottom,buffer,0,0,SRCCOPY);
        SelectObject(buffer,previous); DeleteObject(bitmap); DeleteDC(buffer); EndPaint(window,&paint); return 0;
    }
    if(message==WM_MEASUREITEM) { reinterpret_cast<MEASUREITEMSTRUCT*>(lParam)->itemHeight=Px(24); return TRUE; }
    if(message==WM_DRAWITEM) {
        DRAWITEMSTRUCT* item=reinterpret_cast<DRAWITEMSTRUCT*>(lParam);
        if(item->CtlType==ODT_COMBOBOX) DrawCombo(item); else DrawButton(item);
        return TRUE;
    }
    if(message==WM_CTLCOLOREDIT||message==WM_CTLCOLORSTATIC||message==WM_CTLCOLORBTN) {
        SetTextColor(reinterpret_cast<HDC>(wParam),RGB(69,86,99)); SetBkColor(reinterpret_cast<HDC>(wParam),RGB(255,255,255));
        return reinterpret_cast<LRESULT>(GetStockObject(WHITE_BRUSH));
    }
    if(message==WM_TIMER) { if(app.state==State::Running) { ++app.animation; RECT rect={Px(282),Px(151),Px(W(window)-32),Px(443)}; InvalidateRect(window,&rect,FALSE); } return 0; }
    if(message==WM_LAUNCHER_EVENT) {
        std::unique_ptr<Event> event(reinterpret_cast<Event*>(lParam));
        if(event->monitorId&&event->monitorId!=app.monitorId)return 0;
        if(event->kind==EventKind::Log){AppendLog(event->detail);return 0;}
        if(event->kind==EventKind::BackupDeleted){
            AppendLog(L"[备份] 已删除所选备份："+event->detail);app.state=State::Idle;app.stage=0;app.restoreFilesReady=false;app.title.clear();app.detail.clear();
            for(auto& step:app.steps)step=Step::Pending;RefreshBackups();UpdateControls();return 0;
        }
        if(event->kind==EventKind::Check){UpdateCheckList(event->check);UpdateControls();return 0;}
        if(event->kind==EventKind::MonitorStart){StartMonitor(*event);return 0;}
        if(event->kind==EventKind::ProcessExit){
            app.faaExited=true;app.faaExitCode=event->pid;AppendLog(L"[FAA] 程序已退出，退出码 "+std::to_wstring(event->pid));
            if(app.state==State::Monitoring){app.state=event->pid?State::Failed:State::Success;app.title=event->pid?L"FAA 异常退出":L"FAA 已正常退出";app.detail=L"运行输出已保留在下方日志中。";app.problem=Problem::Startup;}
            UpdateControls();return 0;
        }
        if(event->kind==EventKind::Review){
            app.state=State::Review;app.stage=4;app.steps[4]=Step::Complete;app.logExpanded=false;
            app.title=L"运行环境检测完成";app.detail=L"必需条件已通过。请阅读可选能力提示，确认后继续启动 FAA。";
            for(size_t i=0;i<app.checks.size();++i)if(app.checks[i].status==L"warning"){SendMessageW(app.checkList,LB_SETCURSEL,i,0);break;}
            AppendLog(L"[环境检测] "+app.detail);
        }
        else if(event->kind==EventKind::Start){app.stage=event->stage;app.steps[app.stage]=Step::Active;app.title=event->title;app.detail=event->detail;}
        else if(event->kind==EventKind::Finish){app.steps[event->stage]=Step::Complete;if(app.operation==Operation::Restore&&event->stage==3)app.restoreFilesReady=true;}
        else if(event->kind==EventKind::Failure){
            app.state=State::Failed;app.stage=event->stage;app.steps[app.stage]=Step::Failed;app.title=event->title;app.detail=event->detail;app.problem=event->problem;app.logExpanded=false;
            // 后续可选能力提示不能盖住阻止启动的原因；汇总失败时优先选中必需失败项。
            if(event->stage==4)for(size_t i=0;i<app.checks.size();++i)if(app.checks[i].status==L"fail"){SendMessageW(app.checkList,LB_SETCURSEL,i,0);break;}
            AppendLog(L"[错误] "+event->title+L"："+event->detail);if(app.operation==Operation::Restore&&!app.restoreFilesReady){RefreshBackups();app.steps[app.stage]=Step::Failed;}
            if(app.quickEntry){OpenEnvironmentInstaller(*event);DestroyWindow(window);return 0;}
            if(app.closeAfterCancel){DestroyWindow(window);return 0;}
        }else if(event->kind==EventKind::Blocked){
            app.state=State::Blocked;app.stage=event->stage;app.steps[app.stage]=Step::Failed;app.title=event->title;app.detail=event->detail;app.logExpanded=false;
            app.blockers=event->processes;
            SendMessageW(app.backupList,LB_RESETCONTENT,0,0);
            for(const auto& process:app.blockers){std::wstring row=process.name+L"    PID "+std::to_wstring(process.pid);SendMessageW(app.backupList,LB_ADDSTRING,0,reinterpret_cast<LPARAM>(row.c_str()));AppendLog(L"[占用] "+row+L"："+process.path);}
        }else if(event->kind==EventKind::Cancel){
            app.state=State::Cancelled;app.steps[app.stage]=Step::Pending;app.title=L"操作已停止";app.detail=app.operation==Operation::Uninstall?L"部分运行环境可能已移除，可以继续卸除或重新安装。":L"已完成的步骤会保留，可以调整设置后继续。";
            AppendLog(L"[启动器] 已停止当前操作。");if(app.closeAfterCancel){DestroyWindow(window);return 0;}
        }else if(event->kind==EventKind::Success){
            if(app.operation==Operation::LegacyUpdate) {
                app.state=State::Success;app.title=L"更新完成";app.detail=L"请自行运行 FAA - 环境安装器.exe，准备新版运行环境后启动 FAA。原始版本备份已保留。";
                AppendLog(L"[更新] "+app.detail);UpdateControls();return 0;
            }
            app.state=app.debug&&app.operation!=Operation::Uninstall&&!app.faaExited?State::Monitoring:State::Success;
            app.title=app.operation==Operation::Uninstall?L"本地运行环境已卸除":app.operation==Operation::Restore?L"备份恢复完成，FAA 已就绪":L"FAA 已准备就绪";
            app.detail=app.operation==Operation::Uninstall?L"配置和用户数据已保留。下次启动时会重新准备环境。":app.debug?L"此窗口将持续显示 FAA 运行日志。关闭此窗口会停止显示日志，FAA 继续运行。":L"FAA 主窗口已打开，可以开始使用。";
            if(app.debug&&app.faaExited&&app.operation!=Operation::Uninstall){app.state=app.faaExitCode?State::Failed:State::Success;app.title=app.faaExitCode?L"FAA 异常退出":L"FAA 已正常退出";app.detail=L"运行输出已保留在下方日志中。";app.problem=Problem::Startup;}
            if(app.debug&&app.operation!=Operation::Uninstall)app.logExpanded=true;
            AppendLog(L"[启动器] "+app.title);if(app.closeAfterCancel){DestroyWindow(window);return 0;}
            if(!app.debug&&app.operation!=Operation::Uninstall){
                // 成功通知只在主窗口已出现、FAA 已脱离启动 Job 后发送，此处关闭不会结束 FAA。
                DestroyWindow(window);return 0;
            }
        }
        UpdateControls();return 0;
    }
    if(message==WM_COMMAND){
        const int id=LOWORD(wParam);
        if(id==ID_START)Begin();
        else if(id==ID_CANCEL){SetEvent(app.cancelEvent);EnableWindow(app.cancel,FALSE);app.detail=L"正在停止当前操作…";InvalidateRect(window,NULL,FALSE);}
        else if(id==ID_NETWORK)OpenNetwork();
        else if(id==ID_SETTINGS)OpenSettings();
        else if(id==ID_EXPAND){app.logExpanded=!app.logExpanded;UpdateControls();}
        else if(id==ID_CHECKS&&HIWORD(wParam)==LBN_SELCHANGE)InvalidateRect(window,NULL,FALSE);
        else if(id==ID_EXPORT)ExportLog();
        else if(id==ID_CONFIRM)UpdateControls();
        else if(id==ID_REFRESH){app.state=State::Idle;app.title.clear();app.detail.clear();RefreshBackups();UpdateControls();}
        else if((id==ID_BACKUP_DETAILS||id==ID_DELETE_BACKUP)&&RestorePickerVisible()) {
            int selected=static_cast<int>(SendMessageW(app.backupList,LB_GETCURSEL,0,0));
            if(selected>=0&&static_cast<size_t>(selected)<app.backups.size()) {
                const auto& backup=app.backups[selected];
                if(id==ID_BACKUP_DETAILS)MessageBoxW(window,backup.details.c_str(),L"备份详情",MB_OK|MB_ICONINFORMATION);
                else if(MessageBoxW(window,(L"将永久删除以下备份，无法撤销：\n\n"+backup.label+L"\n"+backup.path+L"\n\n确认删除？").c_str(),L"删除选中备份",MB_YESNO|MB_ICONWARNING|MB_DEFBUTTON2)==IDYES)Begin(false,false,true);
            }
        }
        else if(id==ID_BACKUPS&&HIWORD(wParam)==LBN_SELCHANGE&&RestorePickerVisible()){
            int selected=static_cast<int>(SendMessageW(app.backupList,LB_GETCURSEL,0,0));
            if(selected>=0&&static_cast<size_t>(selected)<app.backups.size()){app.selectedBackup=app.backups[selected].path;app.steps[0]=Step::Complete;SendMessageW(app.confirm,BM_SETCHECK,BST_UNCHECKED,0);app.state=State::Idle;app.title.clear();app.detail.clear();UpdateControls();}
        }else if(id==ID_FORCE&&app.state==State::Blocked){
            if(MessageBoxW(window,L"将结束上方列出的 FAA 环境进程，再继续当前操作。未完成的任务也会终止。\n\n是否继续？",L"结束占用进程",MB_YESNO|MB_ICONWARNING)==IDYES)Begin(false,true);
        }else if(id==ID_REPAIR){
            if(MessageBoxW(window,L"将按安装包锁定的版本重新安装运行依赖，保留用户配置。\n\n是否继续？",L"修复运行依赖",MB_OKCANCEL|MB_ICONINFORMATION)==IDOK)Begin(true);
        }else if(id==ID_ACTION&&HIWORD(wParam)==CBN_SELCHANGE)ChangeOperation();
        return 0;
    }
    if(message==WM_CLOSE){
        if(app.state==State::Running){
            if(app.operation==Operation::Restore||app.operation==Operation::LegacyUpdate){AppendLog(L"[版本操作] 文件准备、替换或回滚完成后才能关闭窗口。");app.detail=L"正在处理版本文件，请等待完成后关闭，避免中断替换或回滚。";UpdateControls();return 0;}
            app.closeAfterCancel=true;SetEvent(app.cancelEvent);app.detail=L"正在安全停止当前操作…";UpdateControls();return 0;
        }
        DestroyWindow(window);return 0;
    }
    if(message==WM_DESTROY){
        KillTimer(window,1);StopMonitor();
        if(app.worker){WaitForSingleObject(app.worker,5000);CloseHandle(app.worker);}
        CloseHandle(app.cancelEvent);DeleteObject(app.bodyFont);DeleteObject(app.monoFont);PostQuitMessage(app.quickEntry&&app.state==State::Failed?1:0);return 0;
    }
    return DefWindowProcW(window,message,wParam,lParam);
}

int RunMaintenanceSelfTests(const std::wstring& reportPath) {
    int failures=0;std::ostringstream report;
    auto check=[&](bool passed,const char* name){report<<(passed?"PASS ":"FAIL ")<<name<<"\n";if(!passed)++failures;};
    const std::wstring root=reportPath+L".fixture",venv=Join(root,L".venv"),bin=Join(root,L"plugins\\launcher_scripts\\bin");
    MakeDirectories(Join(venv,L"Scripts"));MakeDirectories(bin);
    WriteFileBytes(Join(root,L"config.keep"),"user settings");WriteFileBytes(Join(venv,L"readonly.txt"),"fixture");SetFileAttributesW(Join(venv,L"readonly.txt").c_str(),FILE_ATTRIBUTE_READONLY);
    WriteFileBytes(Join(bin,L"uv.fixture"),"fixture");
    std::wstring error;
    check(!RemoveManagedDirectory(root,L".",NULL,error)&&Exists(Join(root,L"config.keep")),"refuse-deleting-root-or-unmanaged-directory");
    const std::wstring child=Join(venv,L"Scripts\\held.exe");
    bool copied=CopyFileW(ExePath().c_str(),child.c_str(),FALSE)!=FALSE;
    std::wstring command=QuoteArgument(child)+L" --fixture-child wait";std::vector<wchar_t> buffer(command.begin(),command.end());buffer.push_back(0);
    STARTUPINFOW startup={};startup.cb=sizeof(startup);PROCESS_INFORMATION process={};
    bool created=copied&&CreateProcessW(child.c_str(),buffer.data(),NULL,NULL,FALSE,CREATE_NO_WINDOW|CREATE_SUSPENDED,NULL,root.c_str(),&startup,&process);
    bool detected=false,stopped=false;
    if(created){for(const auto& item:FindManagedProcesses(root))if(item.pid==process.dwProcessId){detected=true;stopped=StopManagedProcess(root,item,error);}if(!stopped)TerminateProcess(process.hProcess,1);WaitForSingleObject(process.hProcess,5000);CloseHandle(process.hThread);CloseHandle(process.hProcess);}
    check(created&&detected&&stopped,"detect-and-stop-only-process-in-isolated-environment");
    check(!StopManagedProcess(root,{GetCurrentProcessId(),L"test",ExePath()},error),"refuse-stopping-process-outside-managed-environment");
    const std::wstring outside=reportPath+L".outside";MakeDirectories(outside);WriteFileBytes(Join(outside,L"keep.txt"),"outside data");
    auto junction=[&](const std::wstring& link){
        if(!CreateDirectoryW(link.c_str(),NULL))return false;
        const std::wstring substitute=L"\\??\\"+outside;
        struct Junction {DWORD tag;WORD length,reserved,subOffset,subLength,printOffset,printLength;wchar_t names[2048];} data={};
        if(substitute.size()+outside.size()+2>=2048)return false;
        data.tag=IO_REPARSE_TAG_MOUNT_POINT;data.subLength=static_cast<WORD>(substitute.size()*sizeof(wchar_t));data.printOffset=data.subLength+sizeof(wchar_t);data.printLength=static_cast<WORD>(outside.size()*sizeof(wchar_t));
        memcpy(data.names,substitute.c_str(),data.subLength);memcpy(reinterpret_cast<BYTE*>(data.names)+data.printOffset,outside.c_str(),data.printLength);data.length=static_cast<WORD>(8+data.printOffset+data.printLength+sizeof(wchar_t));
        HANDLE handle=CreateFileW(link.c_str(),GENERIC_WRITE,0,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS,NULL);DWORD returned=0;
        bool success=handle!=INVALID_HANDLE_VALUE&&DeviceIoControl(handle,FSCTL_SET_REPARSE_POINT,&data,data.length+8,NULL,0,&returned,NULL);if(handle!=INVALID_HANDLE_VALUE)CloseHandle(handle);return success;
    };
    const bool nestedJunction=junction(Join(venv,L"linked"));
    check(nestedJunction,"create-isolated-directory-junction-fixture");
    check(RemoveManagedDirectory(root,L".venv",NULL,error)&&!Exists(venv),"remove-local-environment-including-readonly-files");
    check(ReadFileBytes(Join(outside,L"keep.txt"))=="outside data","uninstall-does-not-follow-nested-directory-junction");
    const bool rootJunction=junction(venv);
    check(rootJunction&&!RemoveManagedDirectory(root,L".venv",NULL,error)&&ReadFileBytes(Join(outside,L"keep.txt"))=="outside data","refuse-uninstalling-linked-environment-root");
    if(rootJunction)RemoveDirectoryW(venv.c_str());
    check(RemoveManagedDirectory(root,L"plugins\\launcher_scripts\\bin",NULL,error)&&!Exists(bin)&&ReadFileBytes(Join(root,L"config.keep"))=="user settings","remove-local-uv-and-preserve-user-data");
    check(RemoveManagedDirectory(root,L".venv",NULL,error),"missing-environment-is-already-uninstalled");
    const std::wstring recovery=Join(root,L"restore-fixture"),backup=Join(recovery,L"backups\\FAA.backup.20261020-123000");
    MakeDirectories(Join(backup,L"function"));
    WriteFileBytes(Join(backup,L"LICENSE"),"license");WriteFileBytes(Join(backup,L"uv.lock"),"lock");WriteFileBytes(Join(backup,L"pyproject.toml"),"fixture");WriteFileBytes(Join(backup,L"function\\faa_main.py"),"fixture");
    check(IsSafeBackup(recovery,backup,error)&&!IsSafeBackup(recovery,root,error),"backup-preflight-rejects-paths-outside-local-backups");
    const std::wstring disposable=Join(recovery,L"backups\\FAA.backup.20250101-000000");MakeDirectories(disposable);
    const std::string metadataSource="{\"nested\":{\"version\":\"wrong\"},\"version\":\"v3.2.0\",\"tag\":\"v3.2.0-\\u6d4b\\u8bd5\",\"pr\":1055,\"commit\":\"abc123\"}";
    WriteFileBytes(Join(disposable,L".update_state.json"),metadataSource);WriteFileBytes(Join(disposable,L"data.bin"),"abc");
    const bool backupLink=junction(Join(disposable,L"linked"));BackupMetadata metadata=ReadBackupMetadata(disposable);
    check(metadata.version==L"v3.2.0"&&metadata.tag==L"v3.2.0-测试"&&metadata.pr==L"1055"&&metadata.commit==L"abc123", "backup-details-use-top-level-state-and-decode-json-escapes");
    check(backupLink&&metadata.sizeKnown&&metadata.bytes==metadataSource.size()+3,"backup-size-does-not-count-external-junction-data");
    HANDLE dated=CreateFileW(disposable.c_str(),FILE_WRITE_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,NULL);
    FILETIME newer={0xffffffff,0x02000000};bool datedSet=dated!=INVALID_HANDLE_VALUE&&SetFileTime(dated,NULL,NULL,&newer);if(dated!=INVALID_HANDLE_VALUE)CloseHandle(dated);
    auto ordered=FindBackups(recovery);check(datedSet&&!ordered.empty()&&ordered.front()==disposable,"backup-order-matches-modification-time-rather-than-name");
    check(!RemoveBackupDirectory(recovery,root,NULL,error)&&!RemoveBackupDirectory(recovery,Join(recovery,L"backups"),NULL,error),"backup-deletion-rejects-root-and-backups-container");
    check(!IsSafeBackup(recovery,disposable,error)&&RemoveBackupDirectory(recovery,disposable,NULL,error)&&!Exists(disposable)&&Exists(backup)&&ReadFileBytes(Join(outside,L"keep.txt"))=="outside data","delete-incomplete-backup-without-following-junction-or-touching-other-backups");
    const std::wstring linkedBackup=Join(recovery,L"backups\\FAA.backup.linked");bool linkedCreated=junction(linkedBackup);
    check(linkedCreated&&!RemoveBackupDirectory(recovery,linkedBackup,NULL,error),"refuse-deleting-linked-backup-root");if(linkedCreated)RemoveDirectoryW(linkedBackup.c_str());
    const std::wstring linkedContainer=Join(root,L"linked-backups-fixture");MakeDirectories(linkedContainer);bool containerLinked=junction(Join(linkedContainer,L"backups"));
    check(containerLinked&&FindBackups(linkedContainer).empty()&&!RemoveBackupDirectory(linkedContainer,Join(linkedContainer,L"backups\\FAA.backup.external"),NULL,error),"refuse-linked-backups-container");if(containerLinked)RemoveDirectoryW(Join(linkedContainer,L"backups").c_str());
    WriteFileBytes(Join(recovery,L"app.txt"),"current");WriteFileBytes(Join(backup,L"app.txt"),"backup");
    WriteFileBytes(Join(recovery,L"installer.keep"),"running launcher");WriteFileBytes(Join(backup,L"installer.keep"),"old launcher");
    const std::wstring helper=Join(root,L"embedded-restore.py");bool extracted=WriteFileBytes(helper,EmbeddedUpdater());
    const std::wstring python=Join(Parent(ExePath()),L".venv\\Scripts\\python.exe");
    ProcessResult restored;
    if(extracted)restored=RunProcess(python,{L"-u",L"-X",L"utf8",helper,L"restore",L"--root",recovery,L"--backup",backup,L"--launch",L"",L"--gui",L"--preserve-entry",L"installer.keep"},root,{},NULL,nullptr);
    check(extracted&&!restored.systemError&&!restored.exitCode&&ReadFileBytes(Join(recovery,L"app.txt"))=="backup"&&ReadFileBytes(Join(recovery,L"installer.keep"))=="running launcher"&&restored.output.find("FAA_LAUNCHER_PHASE:restore_completed")!=std::string::npos,"embedded-recovery-tool-restores-isolated-files-through-hidden-process");
    report<<"failures="<<failures<<"\n";return WriteFileBytes(reportPath,report.str())?(failures?1:0):2;
}
int RunStartupSelfTest(const std::wstring& root,const std::wstring& reportPath,const std::wstring& mode,const std::wstring& operation) {
    // 此入口只启动带专用标记的隔离夹具，不同步或修复维护者的 FAA 环境。
    if(!Exists(Join(root,L".faa-launcher-startup-test"))||Exists(Join(root,L".git"))||Parent(reportPath)!=root)return 2;
    app.quickEntry=false;app.root=root;app.rootValid=true;app.debug=mode==L"debug";
    const bool legacy=operation==L"legacy";
    app.operation=legacy?Operation::LegacyUpdate:operation==L"restore"?Operation::Restore:Operation::Install;
    app.state=State::Running;app.stage=5;app.faaExited=false;app.closeAfterCancel=false;
    for(int index=0;index<5;++index)app.steps[index]=Step::Complete;
    app.steps[5]=Step::Active;ResetEvent(app.cancelEvent);
    Options options;options.window=app.window;options.cancel=app.cancelEvent;options.root=root;options.debug=app.debug;options.operation=app.operation;
    UpdateControls();
    bool launched=false;
    if(legacy)RunLegacyUpdate(options);else launched=LaunchFaa(options);
    if(launched){Post(options,new Event(EventKind::Finish,5));Post(options,new Event(EventKind::Success,5));}
    DWORD start=GetTickCount();MSG message;
    while(app.state==State::Running&&IsWindow(app.window)&&GetTickCount()-start<2000){
        while(PeekMessageW(&message,NULL,0,0,PM_REMOVE)){if(message.message!=WM_QUIT){TranslateMessage(&message);DispatchMessageW(&message);}}
        if(app.state==State::Running)MsgWaitForMultipleObjects(0,NULL,FALSE,10,QS_ALLINPUT);
    }
    std::ostringstream report;
    report<<"launch_success="<<(launched?1:0)<<"\nwindow_open="<<(IsWindow(app.window)?1:0)<<"\n";
    report<<"monitoring="<<(app.state==State::Monitoring?1:0)<<"\nfailed="<<(app.state==State::Failed?1:0)<<"\n";
    if(legacy)report<<"stage="<<app.stage<<"\nnetwork="<<(app.problem==Problem::Network?1:0)<<"\nnetwork_visible="<<((GetWindowLongW(app.network,GWL_STYLE)&WS_VISIBLE)?1:0)
        <<"\ntitle="<<Utf8(app.title)<<"\ndetail="<<Utf8(app.detail)<<"\n";
    return WriteFileBytes(reportPath,report.str())?0:3;
}

}

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int show) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    int count=0; LPWSTR* raw=CommandLineToArgvW(GetCommandLineW(),&count);
    std::vector<std::wstring> arguments;
    for(int index=0;index<count;++index) arguments.push_back(raw[index]);
    LocalFree(raw);
    if(count>1&&arguments[1]==L"--fixture-child") return RunFixtureChild(arguments);
    if(count>2&&arguments[1]==L"--self-test") return RunCoreSelfTests(arguments[2]);
    if(count>2&&arguments[1]==L"--maintenance-self-test") return RunMaintenanceSelfTests(arguments[2]);
    const bool cachedBridge=count>2&&arguments[1]==L"--legacy-bridge-root";
    app.root=cachedBridge?arguments[2]:Parent(ExePath());
    app.rootValid=IsFaaRoot(app.root,app.rootProblem);
    if(cachedBridge) {
        if(_wcsicmp(Parent(ExePath()).c_str(),Join(app.root,L"update_cache\\legacy_bridge").c_str())||!app.rootValid||!NeedsLegacyUpdate(app.root))return 2;
        app.operation=Operation::LegacyUpdate;app.quickEntry=false;
    } else if(app.quickEntry&&app.rootValid&&NeedsLegacyUpdate(app.root)) {
        if(StartLegacyCacheEntry(app.root))return 0;
        MessageBoxW(NULL,(L"无法打开旧版更新过渡界面：\n"+SystemError(GetLastError())+L"\n请保留更新缓存后重新运行快速启动入口。").c_str(),L"FAA 更新过渡",MB_OK|MB_ICONERROR);return 1;
    }
    // DPI 感知由内嵌 manifest 在创建窗口前启用，兼容较早的 Windows SDK 头文件。
    HDC screen=GetDC(NULL); app.scale=GetDeviceCaps(screen,LOGPIXELSX)/96.0f; ReleaseDC(NULL,screen);
    RECT work={}; SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);
    // 初始窗口必须放得下整个工作区；缩小物理尺寸时，文字和控件按同一比例缩放。
    app.scale=std::min(app.scale,std::min((work.right-work.left-24)/1040.0f,(work.bottom-work.top-48)/740.0f));
    if(app.rootValid) ReadSources();
    ULONG_PTR token=0; GdiplusStartupInput input; GdiplusStartup(&token,&input,NULL);
    INITCOMMONCONTROLSEX common={sizeof(common),ICC_STANDARD_CLASSES|ICC_PROGRESS_CLASS}; InitCommonControlsEx(&common);
    WNDCLASSW cls={}; cls.hInstance=instance; cls.lpfnWndProc=MainProc; cls.lpszClassName=L"FAA.Launcher.Native";
    cls.hCursor=LoadCursorW(NULL,IDC_ARROW); cls.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(4)); RegisterClassW(&cls);
    cls.lpfnWndProc=NetworkProc; cls.lpszClassName=L"FAA.Network.Native"; cls.hbrBackground=reinterpret_cast<HBRUSH>(GetStockObject(WHITE_BRUSH)); RegisterClassW(&cls);
    cls.lpfnWndProc=SettingsProc; cls.lpszClassName=L"FAA.Settings.Native"; RegisterClassW(&cls);
    RECT size={0,0,Px(1040),Px(740)}; AdjustWindowRectEx(&size,WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,FALSE,0);
    int width=size.right-size.left,height=size.bottom-size.top;
    const wchar_t* windowTitle=cachedBridge?L"FAA 旧版更新过渡":app.quickEntry?L"FAA 启动中":L"FAA 环境安装器";
    HWND window=CreateWindowExW(0,L"FAA.Launcher.Native",windowTitle,WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,
        work.left+(work.right-work.left-width)/2,work.top+(work.bottom-work.top-height)/2,width,height,NULL,NULL,instance,NULL);
    if(!window) return 1;
    if(count>5&&arguments[1]==L"--startup-self-test") {
        int result=RunStartupSelfTest(arguments[2],arguments[3],arguments[4],arguments[5]);
        if(IsWindow(window))DestroyWindow(window);
        GdiplusShutdown(token);return result;
    }
    if(count>3&&arguments[1]==L"--runtime-self-test") {
        const std::wstring root=arguments[2],report=arguments[3];
        if(!Exists(Join(root,L".faa-launcher-runtime-test"))||Exists(Join(root,L".git"))||Parent(report)!=root){DestroyWindow(window);GdiplusShutdown(token);return 2;}
        app.root=root;app.rootValid=true;app.operation=Operation::Install;app.stage=4;app.state=State::Running;
        Options options;options.root=root;options.window=window;options.cancel=app.cancelEvent;
        bool passed=RunRuntimeChecks(options);
        MSG message;while(PeekMessageW(&message,NULL,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}
        int selected=static_cast<int>(SendMessageW(app.checkList,LB_GETCURSEL,0,0));
        std::string selectedKey=selected>=0&&static_cast<size_t>(selected)<app.checks.size()?Utf8(app.checks[selected].key):"";
        WriteFileBytes(report,"passed="+std::to_string(passed)+"\nreview="+std::to_string(app.state==State::Review)+"\nfailed="+std::to_string(app.state==State::Failed)+"\nchecks="+std::to_string(app.checks.size())+"\nselected="+selectedKey+"\n"+app.logBytes);
        DestroyWindow(window);GdiplusShutdown(token);return 0;
    }
    if(count>4&&arguments[1]==L"--sync-dependencies-test") {
        Options isolated; isolated.root=arguments[2]; isolated.packageIndex=arguments[3];
        isolated.window=window; isolated.cancel=app.cancelEvent;
        const bool success=SyncDependencies(isolated,Join(isolated.root,L"plugins\\launcher_scripts\\bin\\uv.exe"));
        MSG message;
        while(PeekMessageW(&message,NULL,0,0,PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
        WriteFileBytes(arguments[4],app.logBytes);
        DestroyWindow(window); GdiplusShutdown(token); return success?0:1;
    }
    if(cachedBridge) {
        app.state=State::Running;ResetEvent(app.cancelEvent);
        app.logFile=Join(Join(app.root,L"update_cache\\legacy_bridge"),L"launcher-"+Timestamp()+L".log");
        Options* options=new Options;options->root=app.root;options->window=window;options->cancel=app.cancelEvent;options->operation=Operation::LegacyUpdate;
        app.worker=CreateThread(NULL,0,Worker,options,0,NULL);
        if(!app.worker){delete options;app.state=State::Failed;app.title=L"无法开始旧版更新过渡";app.detail=SystemError(GetLastError());}
        UpdateControls();ShowWindow(window,show);UpdateWindow(window);
    } else if(app.quickEntry) {
        app.state=State::Running;ResetEvent(app.cancelEvent);
        const std::wstring directory=Join(app.root,L"logs\\launcher");
        if(app.rootValid&&MakeDirectories(directory))app.logFile=Join(directory,L"entry-"+Timestamp()+L".log");
        Options* options=new Options;options->root=app.root;options->window=window;options->cancel=app.cancelEvent;options->quickEntry=true;
        app.worker=CreateThread(NULL,0,Worker,options,0,NULL);
        if(!app.worker){delete options;app.state=State::Failed;OpenEnvironmentInstaller(Event(EventKind::Failure,0,L"无法开始启动 FAA",SystemError(GetLastError())));DestroyWindow(window);}
    } else {
        if(count>2&&arguments[1]==L"--startup-error")ImportStartupFailure(arguments[2]);
        UpdateControls();ShowWindow(window,show);UpdateWindow(window);
    }
    MSG message;
    while(GetMessageW(&message,NULL,0,0)>0) {
        if(!IsDialogMessageW(window,&message)) { TranslateMessage(&message); DispatchMessageW(&message); }
    }
    GdiplusShutdown(token); return static_cast<int>(message.wParam);
}
