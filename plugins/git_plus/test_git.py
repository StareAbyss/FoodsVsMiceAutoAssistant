"""
GitUpdater 测试用例
包含基础使用、mirror 更新、自定义日志等场景
"""
import os
import configparser

# 导入模块
from GitSDK import  GitSDK,GitConfig, create


# 项目内 Git 可执行文件路径
GIT_PATH = os.path.join(
    os.path.dirname(__file__), 
    'depend/MinGit-2.53.0-64-bit/mingw64/bin/git.exe'
).replace('\\', '/')


def test_basic_update():
    """测试 1: 基础 Git 更新"""
    print(" 测试 1: 基础 Git 更新")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        update=True,
    )
    
    updater = GitSDK(config)
    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success


def test_with_proxy():
    """测试 2: 使用代理更新"""
    print(" 测试 2: 使用代理更新")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        proxy='http://127.0.0.1:7890',  # 替换为实际代理地址
        update=True,
    )
    
    updater = GitSDK(config)
    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success


def test_check_only():
    """测试 3: 仅检查更新（不执行）"""
    print(" 测试 3: 仅检查更新")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        update=False,  # 禁用自动更新
    )
    
    updater = GitSDK(config)
    has_update = updater.check_update()
    print(f"是否有更新：{'是' if has_update else '否'}\n")
    return has_update


def test_custom_logger():
    """测试 4: 自定义日志回调"""
    print(" 测试 4: 自定义日志回调")
    
    log_messages = []
    
    def custom_log_handler(message: str):
        """自定义日志处理函数"""
        log_messages.append(message)
        print(f"[自定义日志] {message}")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        log_callback=custom_log_handler,
    )
    
    updater = GitSDK(config)
    success = updater.update()
    
    print(f"\n共记录 {len(log_messages)} 条日志")
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success


def test_mirror_update():
    """测试 5: mirror 加速更新"""
    print(" 测试 5: mirror 加速更新")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        mirror=True,
        mirror_url='https://your-mirror-server.com/',  # 替换为实际 mirror 地址
    )
    
    updater = GitSDK(config)
    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success




def test_keep_changes():
    """测试 6: 保留本地修改"""
    print(" 测试 6: 保留本地修改")
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
        keep_changes=True,  # 保留本地修改
    )
    
    updater = GitSDK(config)
    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success


def test_git_by_ini(use_dev=False):
    # 读取 INI 配置文件，优先读取 dev_config.ini
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
    )

    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success


def test_specific_folder():
    """测试 8: 指定项目目录"""
    print("=" * 66)
    print(" 测试 8: 指定项目目录")
    print("=" * 66)
    
    target_folder = r'E:\TAEGET\git'  # 替换为目标目录
    
    config = GitConfig(
        repository='https://github.com/syfoud/Git-Python-Plus.git',
        branch='main',
        git_path=GIT_PATH,
    )
    
    updater = GitSDK(config, folder=target_folder)
    success = updater.update()
    print(f"更新结果：{'成功' if success else '失败'}\n")
    return success




if __name__ == '__main__':
    # 可以选择运行单个测试或全部测试
    # test_basic_update()
    # test_with_proxy()
    # test_check_only()
    # test_custom_logger()
    # test_mirror_update()
    # test_create_updater_function()
    # test_keep_changes()
    # test_specific_folder()
    test_git_by_ini()

