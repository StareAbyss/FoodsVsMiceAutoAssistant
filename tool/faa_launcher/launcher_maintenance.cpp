#include "launcher_maintenance.h"
#include <tlhelp32.h>
#include <algorithm>
#include <stdexcept>
#include <cwctype>

namespace faa {
namespace {
bool Inside(const std::wstring& parent, const std::wstring& child) {
    return child.size()>parent.size() && _wcsnicmp(parent.c_str(),child.c_str(),parent.size())==0 && child[parent.size()]==L'\\';
}
bool JsonString(const std::wstring& text,size_t& position,std::wstring& value) {
    if(position>=text.size()||text[position++]!=L'"')return false;
    while(position<text.size()) {
        wchar_t character=text[position++];if(character==L'"')return true;
        if(character<L' ')return false;
        if(character==L'\\') {
            if(position>=text.size())return false;character=text[position++];
            switch(character) {
            case L'"':case L'\\':case L'/':break;
            case L'n':character=L'\n';break;case L'r':character=L'\r';break;case L't':character=L'\t';break;
            case L'b':character=L'\b';break;case L'f':character=L'\f';break;
            case L'u': {
                if(position+4>text.size())return false;unsigned code=0;
                for(int i=0;i<4;++i){wchar_t digit=text[position++];code*=16;if(digit>=L'0'&&digit<=L'9')code+=digit-L'0';else if(digit>=L'a'&&digit<=L'f')code+=digit-L'a'+10;else if(digit>=L'A'&&digit<=L'F')code+=digit-L'A'+10;else return false;}
                character=static_cast<wchar_t>(code);break;
            }
            default:return false;
            }
        }
        value+=character;
    }
    return false;
}
std::wstring JsonScalar(const std::wstring& text,const std::wstring& key) {
    // 版本记录只读取顶层标量，嵌套对象中的同名字段不能冒充当前备份版本。
    int depth=0;size_t position=0;
    while(position<text.size()) {
        wchar_t character=text[position];
        if(character==L'"') {
            std::wstring name;if(!JsonString(text,position,name))return L"";
            if(depth!=1)continue;
            size_t value=position;while(value<text.size()&&iswspace(text[value]))++value;
            if(value>=text.size()||text[value++]!=L':'||name!=key)continue;
            while(value<text.size()&&iswspace(text[value]))++value;
            if(value<text.size()&&text[value]==L'"'){std::wstring result;return JsonString(text,value,result)?result:L"";}
            size_t end=value;while(end<text.size()&&(iswdigit(text[end])||text[end]==L'-'))++end;
            return text.substr(value,end-value);
        }
        if(character==L'{'||character==L'[')++depth;else if(character==L'}'||character==L']')--depth;
        ++position;
    }
    return L"";
}
bool DirectoryBytes(const std::wstring& path,ULONGLONG& bytes) {
    WIN32_FIND_DATAW entry={};HANDLE search=FindFirstFileW(Join(path,L"*").c_str(),&entry);
    if(search==INVALID_HANDLE_VALUE)return GetLastError()==ERROR_FILE_NOT_FOUND;
    bool complete=true;
    do {
        if(!wcscmp(entry.cFileName,L".")||!wcscmp(entry.cFileName,L".."))continue;
        if(entry.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)continue;
        if(entry.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)complete=DirectoryBytes(Join(path,entry.cFileName),bytes)&&complete;
        else bytes+=(static_cast<ULONGLONG>(entry.nFileSizeHigh)<<32)|entry.nFileSizeLow;
    } while(FindNextFileW(search,&entry));
    DWORD error=GetLastError();FindClose(search);return complete&&error==ERROR_NO_MORE_FILES;
}
std::wstring FinalDirectory(const std::wstring& path) {
    HANDLE file=CreateFileW(path.c_str(),0,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,NULL);
    if(file==INVALID_HANDLE_VALUE) return L"";
    std::vector<wchar_t> buffer(32768);
    DWORD size=GetFinalPathNameByHandleW(file,buffer.data(),static_cast<DWORD>(buffer.size()),FILE_NAME_NORMALIZED);
    CloseHandle(file);
    if(!size||size>=buffer.size()) return L"";
    std::wstring result(buffer.data(),size);
    while(!result.empty()&&result.back()==L'\\') result.pop_back();
    return result;
}
bool ManagedPath(const std::wstring& root,const std::wstring& path) {
    return Inside(Join(root,L".venv"),path)||Inside(Join(root,L"plugins\\launcher_scripts\\bin"),path);
}
bool BackupPath(const std::wstring& root,const std::wstring& backup,std::wstring& resolved,std::wstring& error) {
    const std::wstring directory=Join(root,L"backups"),name=BaseName(backup);
    if(_wcsicmp(Parent(backup).c_str(),directory.c_str())||(name.find(L"FAA.backup.")!=0&&name.find(L"FAA.before-restore.")!=0)||!IsDirectory(backup)) {
        error=L"请选择当前 FAA 的 backups 文件夹内的有效备份。";return false;
    }
    const DWORD parentAttributes=GetFileAttributesW(directory.c_str()),attributes=GetFileAttributesW(backup.c_str());
    const std::wstring resolvedRoot=FinalDirectory(root),resolvedParent=FinalDirectory(directory);resolved=FinalDirectory(backup);
    if(parentAttributes==INVALID_FILE_ATTRIBUTES||attributes==INVALID_FILE_ATTRIBUTES||
        (parentAttributes&FILE_ATTRIBUTE_REPARSE_POINT)||(attributes&FILE_ATTRIBUTE_REPARSE_POINT)||
        resolvedRoot.empty()||resolvedParent.empty()||resolved.empty()||!Inside(resolvedRoot,resolvedParent)||!Inside(resolvedParent,resolved)) {
        error=L"备份及 backups 目录不能使用目录链接，操作范围必须在当前 FAA 内。";return false;
    }
    return true;
}
bool RemoveTree(const std::wstring& path,HANDLE cancel,std::wstring& error) {
    if(cancel&&WaitForSingleObject(cancel,0)==WAIT_OBJECT_0) { SetLastError(ERROR_CANCELLED); error=L"卸除已停止。"; return false; }
    DWORD attributes=GetFileAttributesW(path.c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES) {
        if(GetLastError()==ERROR_FILE_NOT_FOUND||GetLastError()==ERROR_PATH_NOT_FOUND) return true;
        error=path+L"："+SystemError(GetLastError()); return false;
    }
    const bool directory=(attributes&FILE_ATTRIBUTE_DIRECTORY)!=0;
    // 子目录中的链接只移除链接本身，不能遍历到外部数据。
    if(directory&&!(attributes&FILE_ATTRIBUTE_REPARSE_POINT)) {
        WIN32_FIND_DATAW found={}; HANDLE search=FindFirstFileW(Join(path,L"*").c_str(),&found);
        if(search==INVALID_HANDLE_VALUE&&GetLastError()!=ERROR_FILE_NOT_FOUND) { error=path+L"："+SystemError(GetLastError()); return false; }
        if(search!=INVALID_HANDLE_VALUE) {
            do {
                if(wcscmp(found.cFileName,L".")&&wcscmp(found.cFileName,L"..")&&!RemoveTree(Join(path,found.cFileName),cancel,error)) { FindClose(search); return false; }
            } while(FindNextFileW(search,&found));
            DWORD enumerationError=GetLastError(); FindClose(search);
            if(enumerationError!=ERROR_NO_MORE_FILES) { error=path+L"："+SystemError(enumerationError); return false; }
        }
    }
    if((attributes&FILE_ATTRIBUTE_READONLY)&&!(attributes&FILE_ATTRIBUTE_REPARSE_POINT)) SetFileAttributesW(path.c_str(),attributes&~FILE_ATTRIBUTE_READONLY);
    const BOOL removed=directory?RemoveDirectoryW(path.c_str()):DeleteFileW(path.c_str());
    if(!removed) error=path+L"："+SystemError(GetLastError());
    return removed!=FALSE;
}
}
std::wstring BaseName(const std::wstring& path) {
    size_t separator=path.find_last_of(L"\\/"); return separator==std::wstring::npos?path:path.substr(separator+1);
}
std::vector<ManagedProcess> FindManagedProcesses(const std::wstring& root) {
    std::vector<ManagedProcess> result;
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
    if(snapshot==INVALID_HANDLE_VALUE) throw std::runtime_error("无法读取系统进程列表");
    PROCESSENTRY32W entry={}; entry.dwSize=sizeof(entry);
    if(Process32FirstW(snapshot,&entry)) do {
        if(entry.th32ProcessID==GetCurrentProcessId()) continue;
        HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,entry.th32ProcessID);
        if(!process) continue;
        wchar_t path[32768]={}; DWORD size=32768;
        if(QueryFullProcessImageNameW(process,0,path,&size)&&ManagedPath(root,path)) result.push_back({entry.th32ProcessID,entry.szExeFile,path});
        CloseHandle(process);
    } while(Process32NextW(snapshot,&entry));
    CloseHandle(snapshot); return result;
}
bool StopManagedProcess(const std::wstring& root,const ManagedProcess& entry,std::wstring& error) {
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_TERMINATE|SYNCHRONIZE,FALSE,entry.pid);
    if(!process) { if(GetLastError()==ERROR_INVALID_PARAMETER) return true; error=SystemError(GetLastError()); return false; }
    wchar_t path[32768]={}; DWORD size=32768;
    // 再核对进程路径，避免旧 PID 被其他程序复用时结束错误的进程。
    bool valid=QueryFullProcessImageNameW(process,0,path,&size)&&ManagedPath(root,path)&&_wcsicmp(path,entry.path.c_str())==0;
    bool stopped=valid&&TerminateProcess(process,ERROR_CANCELLED);
    DWORD code=GetLastError();
    if(stopped) WaitForSingleObject(process,5000);
    CloseHandle(process);
    if(!stopped) error=valid?SystemError(code):L"进程已变化，请重新检测后再试。";
    return stopped;
}
bool RemoveManagedDirectory(const std::wstring& root,const std::wstring& relative,HANDLE cancel,std::wstring& error) {
    if(relative!=L".venv"&&relative!=L"plugins\\launcher_scripts\\bin") { error=L"拒绝删除非 FAA 管理的目录。"; return false; }
    const std::wstring target=Join(root,relative);
    const DWORD attributes=GetFileAttributesW(target.c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES&&(GetLastError()==ERROR_FILE_NOT_FOUND||GetLastError()==ERROR_PATH_NOT_FOUND)) return true;
    std::wstring current=root;
    size_t begin=0;
    while(begin<relative.size()) {
        const size_t end=relative.find(L'\\',begin);
        current=Join(current,relative.substr(begin,end==std::wstring::npos?end:end-begin));
        DWORD flags=GetFileAttributesW(current.c_str());
        if(flags==INVALID_FILE_ATTRIBUTES||flags&FILE_ATTRIBUTE_REPARSE_POINT) { error=L"卸除目标包含无法读取的目录或目录链接："+current; return false; }
        if(end==std::wstring::npos) break;
        begin=end+1;
    }
    const std::wstring resolvedRoot=FinalDirectory(root),resolvedTarget=FinalDirectory(target);
    if(resolvedRoot.empty()||resolvedTarget.empty()||!Inside(resolvedRoot,resolvedTarget)) { error=L"卸除目标不在当前 FAA 根目录内："+target; return false; }
    return RemoveTree(resolvedTarget,cancel,error);
}
bool IsSafeBackup(const std::wstring& root,const std::wstring& backup,std::wstring& error) {
    std::wstring resolved;if(!BackupPath(root,backup,resolved,error))return false;
    const wchar_t* required[]={L"LICENSE",L"uv.lock",L"pyproject.toml",L"function\\faa_main.py"};
    for(const auto* file:required) if(!Exists(Join(backup,file))) { error=L"备份不完整，缺少："+std::wstring(file); return false; }
    return true;
}
bool RemoveBackupDirectory(const std::wstring& root,const std::wstring& backup,HANDLE cancel,std::wstring& error) {
    std::wstring resolved;if(!BackupPath(root,backup,resolved,error))return false;
    return RemoveTree(resolved,cancel,error);
}
BackupMetadata ReadBackupMetadata(const std::wstring& path) {
    BackupMetadata metadata;
    const std::wstring state=Join(path,L".update_state.json");
    DWORD attributes=GetFileAttributesW(state.c_str());
    if(attributes!=INVALID_FILE_ATTRIBUTES&&!(attributes&FILE_ATTRIBUTE_REPARSE_POINT)) {
        const std::wstring text=Wide(ReadFileBytes(state));
        metadata.version=JsonScalar(text,L"version");metadata.tag=JsonScalar(text,L"tag");
        metadata.commit=JsonScalar(text,L"commit");metadata.pr=JsonScalar(text,L"pr");
    }
    metadata.sizeKnown=DirectoryBytes(path,metadata.bytes);return metadata;
}
std::vector<std::wstring> FindBackups(const std::wstring& root) {
    std::vector<std::wstring> result;
    DWORD attributes=GetFileAttributesW(Join(root,L"backups").c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))return result;
    WIN32_FIND_DATAW entry={}; HANDLE search=FindFirstFileW(Join(root,L"backups\\FAA.*").c_str(),&entry);
    if(search==INVALID_HANDLE_VALUE) return result;
    do {
        std::wstring name=entry.cFileName;
        if((entry.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(entry.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)&&
            (name.find(L"FAA.backup.")==0||name.find(L"FAA.before-restore.")==0)) result.push_back(Join(root,L"backups\\"+name));
    } while(FindNextFileW(search,&entry));
    FindClose(search);
    std::sort(result.begin(),result.end(),[](const std::wstring& left,const std::wstring& right) {
        WIN32_FILE_ATTRIBUTE_DATA first={},second={};GetFileAttributesExW(left.c_str(),GetFileExInfoStandard,&first);GetFileAttributesExW(right.c_str(),GetFileExInfoStandard,&second);
        int order=CompareFileTime(&first.ftLastWriteTime,&second.ftLastWriteTime);return order?order>0:left>right;
    });
    return result;
}
}
