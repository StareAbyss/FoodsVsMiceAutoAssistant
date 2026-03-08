"""
Git 自动更新模块
整合了 Git 仓库管理和 mirror 加速更新功能
支持完全配置化，可迁移到任意项目使用
"""

import configparser
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, Literal

# 添加当前目录到 sys.path，确保能找到 logger 模块
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from logger import SimpleLogger

@dataclass
class GitLogInfo:
    """Git 日志信息数据结构"""
    author: str = ""
    date: str = ""
    message: str = ""
    commit_hash: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            'author': self.author,
            'date': self.date,
            'message': self.message,
            'commit_hash': self.commit_hash
        }


@dataclass
class GitConfig:
    """Git 更新配置"""
    repository: str = "https://github.com/name/test.git"
    branch: str = "master"
    git_path: str = "git"
    proxy: Optional[str] = None
    ssl: bool = True
    update: bool = True
    keep_changes: bool = False
    mirror: bool = False
    mirror_url: str = ""
    depth: Optional[int] = None  # 浅克隆深度，None 表示完整克隆
    
    # 日志回调 (可选）（其它自行实现日志系统调用方法）
    log_callback: Optional[Callable[[str], None]] = None
    
    def __post_init__(self):
        if self.git_path:
            self.git_path = self.git_path.replace('\\', '/')
        if self.mirror_url:
            self.mirror_url = self.mirror_url.strip('/')


class GitSDK:
    """Git 仓库 py 接口"""
    
    # 类级别的线程池，所有实例共享
    _executor: Optional[ThreadPoolExecutor] = None
    
    @classmethod
    def _get_executor(cls, max_workers: int = 5) -> ThreadPoolExecutor:
        """获取或创建线程池"""
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="GitSDK")
        return cls._executor
    
    @classmethod
    def shutdown_executor(cls):
        """关闭线程池（在程序退出时调用）"""
        if cls._executor is not None:
            cls._executor.shutdown(wait=True)
            cls._executor = None
    
    def __init__(self, config: GitConfig, folder: Optional[str] = None):
        """
        Args:
            config: Git 配置对象
            folder: 项目根目录，默认为当前目录
        """
        self.config = config
        self.folder = folder or os.getcwd()
        self.logger = SimpleLogger(config.log_callback)
        # 切换到项目目录以便执行 git 命令
        os.chdir(self.folder)
        self.git_config = configparser.ConfigParser()
        self.git_config.read('./.git/config')
    @property
    def git(self) -> str:
        """获取 git 可执行文件路径"""
        exe = self.config.git_path
        if exe and os.path.exists(exe):
            return exe
        return 'git'
    @staticmethod
    def delete(file: str):
        """删除文件"""
        try:
            os.remove(file)
            print(f'Remove {file}')
        except FileNotFoundError:
            print(f'File not found: {file}')
    
    def config_eq(self, section: str, option: str, value: Optional[str]) -> bool:
        """
        检查本地 git 配置项是否匹配
        
        Args:
            section: 配置节
            option: 配置项
            value: 期望值
            
        Returns:
            bool: 是否匹配
        """
        result = self.git_config.get(section, option, fallback=None)
        if result == value:
            self.logger.info(f'Git config {section}.{option} = {value}')
            return True
        else:
            self.logger.warning(f'Git config {section}.{option} != {value}')
            return False
    
    def run_async(self, operation: Literal['update', 'check_update', 'deepen', 'get_git_log'], 
                  callback: Optional[Callable[[Any], None]] = None,
                  **kwargs) -> Future:
        """
        统一的异步操作接口
        
        Args:
            operation: 操作类型，可选：'update', 'check_update', 'deepen', 'get_git_log'
            callback: 操作完成后的回调函数，接收操作的返回值
            **kwargs: 传递给具体操作的参数
            
        Returns:
            Future: 代表异步操作结果的 Future 对象
            
        Examples:
            # 异步更新
            future = sdk.run_async('update', callback=lambda success: print(f'更新{'成功' if success else '失败'}'))
            
            # 异步检查更新
            future = sdk.run_async('check_update', callback=lambda has: print(f'有更新：{has}'))
            
            # 异步深化，传递额外参数
            future = sdk.run_async('deepen', depth=5, callback=lambda r: print('完成'))
            
            # 异步获取 git log
            future = sdk.run_async('get_git_log', callback=lambda log: print(f'最新提交：{log.commit_hash[:8] if log else "无"}'))
        """
        executor = self._get_executor()
        
        # 映射操作名称到方法
        operation_map = {
            'update': self.update,
            'check_update': self.check_update,
            'deepen': self.deepen,
            'get_git_log': self.get_git_log
        }
        
        if operation not in operation_map:
            raise ValueError(f"未知操作：{operation}，必须是 'update', 'check_update', 'deepen', 'get_git_log' 之一")
        
        method = operation_map[operation]
        
        def worker():
            """工作函数"""
            try:
                result = method(**kwargs)
                if callback:
                    callback(result)
                return result
            except Exception as e:
                self.logger.error(f"Async {operation} failed: {e}")
                if callback:
                    callback(None)
                raise
        
        # 提交到线程池
        self.logger.info(f"Async operation '{operation}' started")
        return executor.submit(worker)
    
    def get_git_log(self, source: str = "origin", branch: Optional[str] = None, count: Optional[int] = None) -> list[GitLogInfo]:
        """
        获取 git log 信息列表（支持获取多条历史记录）
        
        Args:
            source: remote 名称
            branch: 分支名称，默认为配置中的分支
            count: 获取的日志数量，None 表示获取所有历史
            
        Returns:
            list[GitLogInfo]: GitLogInfo 对象列表，按时间倒序（最新的在前）
        """
        if branch is None:
            branch = self.config.branch
            
        # 先 fetch 确保获取最新信息
        git = self.git
        if not self.run_cmd(f'"{git}" fetch {source} {branch}', allow_failure=True):
            self.logger.warning("Failed to fetch from remote")
            return []
        
        # 构建 git log 命令，获取所有远程分支上但本地没有的提交
        count_param = f"-{count}" if count else ""
        output = self.run_cmd(
            f'"{git}" log ..{source}/{branch} --pretty=format:"%an|||%ad|||%s|||%H" --date=iso {count_param}',
            return_output=True
        )
        
        logs = []
        if output:
            # 按行分割，每行是一个提交
            lines = output.strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split("|||")
                if len(parts) >= 4:
                    author, date, message, commit_hash = parts[0], parts[1], parts[2], parts[3]
                    log_info = GitLogInfo(
                        author=author,
                        date=date,
                        message=message,
                        commit_hash=commit_hash
                    )
                    logs.append(log_info)
                    self.logger.info(f"Get git log: {commit_hash[:8]} - {message}")
        
        # 如果没有远程更新，获取本地提交历史
        if not logs:
            local_output = self.run_cmd(
                f'"{git}" log --pretty=format:"%an|||%ad|||%s|||%H" --date=iso {count_param}',
                return_output=True
            )
            
            if local_output:
                lines = local_output.strip().split('\n')
                for line in lines:
                    if not line.strip():
                        continue
                    parts = line.split("|||")
                    if len(parts) >= 4:
                        author, date, message, commit_hash = parts[0], parts[1], parts[2], parts[3]
                        log_info = GitLogInfo(
                            author=author,
                            date=date,
                            message=message,
                            commit_hash=commit_hash
                        )
                        logs.append(log_info)
                        self.logger.info(f"Get local git log: {commit_hash[:8]} - {message}")
        
        if not logs:
            self.logger.warning("No git log information available")
        
        return logs
    

    
    def run_cmd(self, command: str, allow_failure: bool = False, output: bool = True, return_output: bool = False, auto_input_n: bool = False) -> bool | str:
        """
        执行命令
        
        Args:
            command: 命令字符串
            allow_failure: 是否允许失败
            output: 是否输出日志（仅在 return_output=False 时生效）
            return_output: 是否返回命令输出（True 时返回 stdout）
            auto_input_n: 是否自动输入 'n' 响应交互式提示（用于 git unlink failed 等情况）
            
        Returns:
            bool | str: 返回布尔值表示成功与否，或当 return_output=True 时返回命令输出
        """
        command = command.replace(r"\\", "/").replace("\\", "/")
        self.logger.info(f'Run command: {command}')
        
        # 如果需要自动输入 n，使用管道方式
        if auto_input_n:
            # Windows 下使用 echo n | command 的方式
            # 同时设置 GIT_TERMINAL_PROMPT=0 禁用交互提示
            # 使用 Popen 和 communicate 来确保输入能正确传递
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,  # 捕获输出用于调试
                stderr=subprocess.PIPE,  # 捕获错误用于调试
                text=True,
                encoding="utf8",
                shell=True,
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
            )
            stdout, stderr = process.communicate()  # 获取输出
            error_code = process.returncode
            
            # 输出错误信息用于调试
            if error_code and stderr:
                self.logger.error(f'Command stderr: {stderr}')
            
            if error_code:
                if allow_failure:
                    self.logger.warning(f'[ Command Error ], error_code: {error_code}')
                    return False
                else:
                    self.logger.info(f'[ Command Error ], error_code: {error_code}')
                    raise Exception(f"Command failed: {command}")
            else:
                self.logger.info(f'[ Command Success ]{command}')
                return True
        
        if return_output:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf8", shell=True
            )
            if output:
                if result.stdout:
                    self.logger.info(result.stdout)
                if result.stderr:
                    self.logger.info(result.stderr)
            
            if result.returncode and not allow_failure:
                self.logger.info(f'[ Command Error ], error_code: {result.returncode}')
                raise Exception(f"Command failed: {command}")
            return result.stdout
        else:
            error_code = os.system(command)
            if error_code:
                if allow_failure:
                    self.logger.warning(f'[ Command Error ], error_code: {error_code}')
                    return False
                else:
                    self.logger.info(f'[ Command Error ], error_code: {error_code}')
                    raise Exception(f"Command failed: {command}")
            else:
                self.logger.info(f'[ Command Success ]{command}')
                return True
    
    def mirror_repo(self, repo_url: str) -> str:
        """
        将仓库 URL 转换为 mirror 加速 URL
        
        Args:
            repo_url: 原始仓库 URL
            
        Returns:
            str: mirror 加速后的 URL
        """
        if not self.config.mirror or not self.config.mirror_url:
            return repo_url
        
        mirror_base = self.config.mirror_url.rstrip('/')
        # 处理 github.com 的 URL
        if 'github.com' in repo_url:
            # https://github.com/user/repo.git -> https://mirror.com/github.com/user/repo.git
            repo_path = repo_url.replace('https://', '').replace('http://', '')
            return f'{mirror_base}/{repo_path}'
        
        return repo_url
    
    def git_repo_init(self, repo: str, source: str = 'origin',
                      branch: str = 'master', proxy: Optional[str] = '',
                      ssl: bool = True, keep_changes: bool = False,
                      depth: Optional[int] = None):
        """
        初始化 git 仓库并拉取代码
        
        Args:
            repo: 仓库地址
            source: remote 名称
            branch: 分支名称
            proxy: 代理地址
            ssl: 是否验证 SSL
            keep_changes: 是否保留本地修改
            depth: 浅克隆深度，None 表示完整克隆
        """
        # 应用 mirror 加速
        repo = self.mirror_repo(repo)
        
        # 修复仓库
        if not self.run_cmd(f'"{self.git}" init', allow_failure=True):
            for file in ['./.git/HEAD','./.git/ORIG_HEAD','./.git/config','./.git/index', ]:
                self.delete(file)
            self.run_cmd(f'"{self.git}" init')
        
        # 设置代理
        if proxy:
            self.logger.info('Set Git Proxy')
            if not self.config_eq('http', 'proxy', value=f"http://127.0.0.1:{proxy}"):
                self.run_cmd(f'"{self.git}" config --local http.proxy http://127.0.0.1:{proxy}')
            if not self.config_eq('https', 'proxy', value=f"http://127.0.0.1:{proxy}"):
                self.run_cmd(f'"{self.git}" config --local https.proxy http://127.0.0.1:{proxy}')
        else:
            self.logger.info('No Proxy')
            if not self.config_eq('http', 'proxy', value=None):
                self.run_cmd(f'"{self.git}" config --local --unset http.proxy', allow_failure=True)
            if not self.config_eq('https', 'proxy', value=None):
                self.run_cmd(f'"{self.git}" config --local --unset https.proxy', allow_failure=True)
        
        # 设置 SSL 验证
        if ssl:
            if not self.config_eq('http', 'sslVerify', value='true'):
                self.run_cmd(f'"{self.git}" config --local http.sslVerify true', allow_failure=True)
        else:
            self.logger.warning('SSL verify is closed')
            if not self.config_eq('http', 'sslVerify', value='false'):
                self.run_cmd(f'"{self.git}" config --local http.sslVerify false', allow_failure=True)
        
        # 设置远程仓库
        if not self.config_eq(f'remote "{source}"', 'url', value=repo):
            if not self.run_cmd(f'"{self.git}" remote set-url {source} {repo}', allow_failure=True):
                self.run_cmd(f'"{self.git}" remote add {source} {repo}')
        
        # Fetch 分支，可能因网络原因失败
        fetch_cmd = f'"{self.git}" fetch {source} {branch}'
        if depth is not None:
            fetch_cmd += f' --depth={depth}'
        if not self.run_cmd(fetch_cmd, allow_failure= True):
            self.logger.info('Fetch failed, retry')
            self.run_cmd(fetch_cmd)
        
        # Pull 分支
        # 移除 git lock 文件
        for file in ['./.git/HEAD.lock','./.git/index.lock','./.git/refs/heads/master.lock',]:
            if os.path.exists(file):
                self.logger.info(f'Remove Lock file {file}')
                self.delete(file)
        
        # 构建 pull 命令，支持 depth 参数
        pull_cmd = f'"{self.git}" pull --ff-only {source} {branch}'
        if depth is not None:
            pull_cmd += f' --depth={depth}'
        
        if keep_changes:
            init=False
            stash_success = self.run_cmd(f'"{self.git}" stash', allow_failure=True)
            if not stash_success:
                self.logger.warning('Stash failed, maybe first init')
                self.run_cmd(f'{self.git} commit --allow-empty -m initial-commit')
                stash_success = self.run_cmd(f'"{self.git}" stash', allow_failure=True)
                init=stash_success
            if stash_success:
                if not self.run_cmd(pull_cmd, auto_input_n=True, allow_failure=True):
                    self.run_cmd(f'{self.git} merge --no-ff')
                else:
                    self.run_cmd(pull_cmd, auto_input_n=True)
                if not self.run_cmd(f'"{self.git}" stash pop', allow_failure=True):
                    self.logger.info('Stash pop failed, no local modifications')
            else:
                # 重试后仍然失败，强制硬更新
                self.logger.info('Stash failed, force reset')
                self.run_cmd(f'"{self.git}" reset --hard {source}/{branch}', auto_input_n=True)
                self.run_cmd(pull_cmd, auto_input_n=True)
        else:
            self.run_cmd(f'"{self.git}" reset --hard {source}/{branch}', auto_input_n=True)
            # Since `git fetch` is already called, checkout is faster
            if not self.run_cmd(f'"{self.git}" checkout {branch}', allow_failure=True):
                self.run_cmd(pull_cmd, auto_input_n=True)
        
        # 显示当前分支版本
        self.run_cmd(f'"{self.git}" --no-pager log --no-merges -1')
    
    def update(self):
        """
        执行更新
        
        Returns:
            bool: 是否更新成功
        """
        self.logger.info('Start Git')
        
        if not self.config.update:
            self.logger.info('Disable update, skip')
            return True
        try:
            self.git_repo_init(
                repo=self.config.repository,
                source='origin',
                branch=self.config.branch,
                proxy=self.config.proxy,
                ssl=self.config.ssl,
                keep_changes=self.config.keep_changes,
                depth=self.config.depth,
            )
        except Exception as e:
            self.logger.error(f'Git update failed{e}')
            return False
        return True
    
    def check_update(self) -> bool:
        """
        检查是否有更新
        
        Returns:
            bool: 是否有可用更新
        """
        # 使用 git fetch 检查
        source = "origin"
        branch = self.config.branch
        git = self.git

        if not self.run_cmd(f'"{git}" fetch {source} {branch}', allow_failure=True):
            self.logger.warning("Failed git fetch")
            return False
        
        # 检查是否有新提交
        log = self.run_cmd(
            f'"{git}" log --not --remotes={source}/* -1 --oneline'
        ,return_output= True)
        if log:
            self.logger.info(
                f"You can't update because Local commit {log.split()[0]} is not update to upstream repository"
            )
            return False
        
        # 获取当前分支落后于远程分支的那些提交
        output = self.run_cmd(
            f'"{git}" log ..{source}/{branch} --pretty=format:"%an|||%ad|||%s|||%H" --date=iso -1'
        ,return_output= True)
        if output:
            output = output.split("|||")
            if len(output) >= 4:
                author, date, message, hash1 = output[0], output[1], output[2], output[3]
                self.logger.info(f"Updates detected")
                self.logger.info(f"{hash1[:8]} - {message}")
                return True
        
        self.logger.info("Repo is current commit")
        return False
    
    def deepen(self, depth: int = 1, unshallow: bool = False):
        """
        深化浅克隆深度或转换为完整仓库,本地日志缺失可以调用本函数还原
        """
        source = "origin"
        branch = self.config.branch
        git = self.git
        
        if unshallow:
            # 转换为完整仓库
            self.logger.info("Converting to full repository")
            cmd = f'"{git}" fetch --unshallow'
            if not self.run_cmd(cmd, allow_failure=True):
                self.logger.warning("Failed to unshallow, because it is a complete repository now")
                return False
        elif depth is not None:
            # 在现有基础上增加深度
            if depth > 0:
                self.logger.info(f"Deepening by {depth} layers from current shallow boundary")
                cmd = f'"{git}" fetch --deepen={depth}'
            else:
                self.logger.info("No depth change needed")
                return False
            self.run_cmd(cmd)
        
        # 重置到最新提交
        self.run_cmd(f'"{git}" reset --hard {source}/{branch}')
        
        # 显示当前版本
        self.run_cmd(f'"{git}" --no-pager log --no-merges -1')
        return True


def git_by_ini(use_dev = None, async_mode: bool = False, operation: str = 'check_update', log_callback = None, keep_changes_override: bool = None):
    """
    从 INI 配置文件读取参数并执行 Git 操作
    
    Args:
        use_dev: 是否使用 dev_config.ini，None 表示根据 settings.ini 中的 use_dev_config 决定
        async_mode: 是否使用异步模式（非阻塞）
        operation: 操作类型，可选：'update', 'check_update', 'get_git_log', 'deepen'
        log_callback: 日志回调函数
        keep_changes_override: 是否保留本地修改的覆盖值（None 表示使用配置文件中的值）
        
    Returns:
        bool|GitLogInfo: 操作结果，get_git_log 返回 GitLogInfo，其他返回 bool
    """
    # 如果 use_dev 未指定，从 settings.ini 中读取
    if use_dev is None:
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.ini')
        if os.path.exists(settings_file):
            parser = configparser.ConfigParser()
            parser.read(settings_file, encoding='utf-8')
            use_dev = parser.getboolean('settings', 'use_dev_config', fallback=False)
    
    # 根据 use_dev 参数决定使用哪个配置文件
    config_file = os.path.join(os.path.dirname(__file__), 'dev_config.ini')
    if (not os.path.exists(config_file)) or (not use_dev):
        config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if not os.path.exists(config_file):
        print(f"错误：配置文件不存在 - {config_file}")
        return False

    parser = configparser.ConfigParser()
    parser.read(config_file, encoding='utf-8')

    # 从 INI 文件读取参数
    repo = parser.get('git', 'repository')
    branch = parser.get('git', 'branch')
    git_path = parser.get('git', 'git_path')

    # 如果 git_path 是相对路径，转换为绝对路径
    if not os.path.isabs(git_path):
        git_path = os.path.join(os.path.dirname(__file__), git_path).replace('\\', '/')

    update = parser.getboolean('update', 'update')
    # 如果提供了覆盖值则使用覆盖值，否则使用配置文件中的值
    if keep_changes_override is not None:
        keep_changes = keep_changes_override
    else:
        keep_changes = parser.getboolean('update', 'keep_changes')
    use_mirror = parser.getboolean('update', 'mirror')
    mirror_url = parser.get('update', 'mirror_url', fallback='')
    depth_str = parser.get('update', 'depth', fallback='')
    depth = int(depth_str) if depth_str.strip() else None

    proxy = parser.get('network', 'proxy', fallback=None)
    ssl = parser.getboolean('network', 'ssl')

    project_folder = parser.get('paths', 'project_folder', fallback=None)
    if project_folder and not os.path.isabs(project_folder):
        # 如果是相对路径，相对于 GitSDK.py 所在目录转换
        project_folder = os.path.join(os.path.dirname(__file__), project_folder)
    elif not project_folder or project_folder.strip() == '':
        project_folder = os.getcwd()

    # 创建配置并执行更新
    updater = create(
        repo,
        branch,
        git_path,
        proxy,
        ssl,
        update,
        keep_changes,
        use_mirror,
        mirror_url,
        depth,
        project_folder,
        log_callback,  # 传递日志回调
    )
    
    try:
        if async_mode:
            future = updater.run_async(operation, callback=None)
            result = future.result()
            return result if result is not None else True  # update() 默认返回 True
        else:
            if operation == 'get_git_log':
                return updater.get_git_log()
            elif operation == 'check_update':
                return updater.check_update()
            elif operation == 'update':
                return updater.update()
            elif operation == 'deepen':
                return updater.deepen(unshallow=True)
            else:
                raise ValueError(f"未知操作：{operation}")
    finally:
        updater.shutdown_executor()
def create(
    repository: str,
    branch: str = 'master',
    git_path: str = 'git',
    proxy_port: Optional[str] = None,
    ssl_verify: bool = True,
    need_update: bool = True,
    keep_changes: bool = False,
    use_mirror: bool = False,
    mirror_url: str = '',
    depth: Optional[int] = None,
    folder: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> GitSDK:
    """
    创建 Git 更新器的便捷函数
    
    Args:
        repository: Git 仓库地址
        branch: 分支名称
        git_path: git 可执行文件路径
        proxy_port: 代理地址
        ssl_verify: 是否验证 SSL
        need_update: 是否自动更新
        keep_changes: 是否保留本地修改
        use_mirror: 是否使用 mirror
        mirror_url: mirror 地址
        folder: 项目根目录
        log_callback: 日志回调函数
        depth: 浅克隆深度，None 表示完整克隆
        
    Returns:
        GitSDK 实例
    """
    config = GitConfig(
        repository=repository,
        branch=branch,
        git_path=git_path,
        proxy=proxy_port,
        ssl=ssl_verify,
        update=need_update,
        keep_changes=keep_changes,
        mirror=use_mirror,
        mirror_url=mirror_url,
        depth=depth,
        log_callback=log_callback,
    )
    return GitSDK(config, folder)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Git 自动更新工具')
    parser.add_argument('--repo', type=str, required=True, help='Git 仓库地址')
    parser.add_argument('--branch', type=str, default='master', help='分支名称')
    parser.add_argument('--git', type=str, default='git', help='git 可执行文件路径')
    parser.add_argument('--proxy', type=str, default=None, help='HTTP 代理')
    parser.add_argument('--no-ssl-verify', action='store_true', help='不验证 SSL')
    parser.add_argument('--no-auto-update', action='store_true', help='禁用自动更新')
    parser.add_argument('--keep-changes', action='store_true', help='保留本地修改')
    parser.add_argument('--use-mirror', action='store_true', help='使用 mirror 加速')
    parser.add_argument('--mirror-url', type=str, default='', help='mirror 地址')
    parser.add_argument('--folder', type=str, default=None, help='项目根目录')
    parser.add_argument('--check-only', action='store_true', help='仅检查更新，不执行更新')
    parser.add_argument('--depth', type=int, default=None, help='浅克隆深度')
    parser.add_argument('--unshallow', action='store_true', help='转换为完整仓库（获取所有历史）')
    parser.add_argument('--async-mode', action='store_true', help='使用异步模式（非阻塞）')
    parser.add_argument('--get-log', action='store_true', help='获取 git log 信息并输出')
    
    args = parser.parse_args()
    config = GitConfig(
        repository=args.repo,
        branch=args.branch,
        git_path=args.git,
        proxy=args.proxy,
        ssl=not args.no_ssl_verify,
        update=not args.no_auto_update,
        keep_changes=args.keep_changes,
        mirror=args.use_mirror,
        mirror_url=args.mirror_url,
        depth=args.depth,
    )
    SDK = GitSDK(config, folder=args.folder)
    
    try:
        if args.get_log:
            if args.async_mode:
                future = SDK.run_async('get_git_log', callback=None)
                log_info = future.result()
            else:
                log_info = SDK.get_git_log()
            
            if log_info:
                print(f"Author: {log_info.author}")
                print(f"Date:   {log_info.date}")
                print(f"Message: {log_info.message}")
                print(f"Commit: {log_info.commit_hash}")
                sys.exit(0)
            else:
                print("Failed to get git log information")
                sys.exit(1)
        elif args.check_only:
            if args.async_mode:
                future = SDK.run_async('check_update', callback=None)
                result = future.result()
                state = True
            else:
                state = SDK.check_update()
        elif args.unshallow:
            if args.async_mode:
                future = SDK.run_async('deepen', unshallow=True, callback=None)
                result = future.result()
                state = True
            else:
                state = SDK.deepen(unshallow=True)
        else:
            if args.async_mode:
                future = SDK.run_async('update', callback=None)
                result = future.result()
                state = True
            else:
                state = SDK.update()
    finally:
        SDK.shutdown_executor()
    
    sys.exit(0 if state else 1)
