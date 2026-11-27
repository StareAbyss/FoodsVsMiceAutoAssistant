#pragma once
#include "launcher_core.h"

namespace faa {
struct ManagedProcess { DWORD pid; std::wstring name, path; };
struct BackupMetadata { std::wstring version,tag,commit,pr; ULONGLONG bytes=0; bool sizeKnown=true; };
std::vector<ManagedProcess> FindManagedProcesses(const std::wstring& root);
bool StopManagedProcess(const std::wstring& root, const ManagedProcess& process, std::wstring& error);
// 只接受两个固定的相对目录，并拒绝通过目录链接离开当前 FAA 根目录。
bool RemoveManagedDirectory(const std::wstring& root, const std::wstring& relative, HANDLE cancel, std::wstring& error);
bool IsSafeBackup(const std::wstring& root, const std::wstring& backup, std::wstring& error);
// 删除允许不完整的备份，但仍限制为当前 backups 下的受管目录，不跟随目录链接。
bool RemoveBackupDirectory(const std::wstring& root, const std::wstring& backup, HANDLE cancel, std::wstring& error);
BackupMetadata ReadBackupMetadata(const std::wstring& path);
std::vector<std::wstring> FindBackups(const std::wstring& root);
std::wstring BaseName(const std::wstring& path);
}
