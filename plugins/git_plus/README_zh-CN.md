# Git Python Plus使用说明

## 📖 简介

`Git Python Plus`又称`gpp`, 是一个独立的 Git 自动更新工具，整合了标准 Git 更新和 镜像加速更新功能。该模块完全可配置化，可以轻松迁移到任意 Python 项目中使用。

## ✨ 主要特性
- **完全可配置**：所有参数均可通过代码或命令行自定义
- **零依赖负担**：不依赖任何第三方库
- **跨平台**：支持 Windows、Linux、macOS(需配置对应平台git工具)
- **日志回调**：支持自定义日志处理函数
- **命令行工具**：可直接作为 CLI 工具使用

## 🚀 快速开始

### 安装UV包管理(Windows)(可选)

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 基础使用示例

```python
from GitSDK import GitSDK, GitConfig

# 1. 创建配置
config = GitConfig(
    repository='https://github.com/name/project',
    branch='master',
    update=True,
)

# 2. 创建更新器
updater = GitSDK(config)

# 3. 执行更新
if updater.update():
    print("更新成功！")
else:
    print("更新失败")
```

## 📋 配置参数详解

### GitConfig 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `repository` | str | GitHub 地址 | Git 仓库 URL |
| `branch` | str | `'master'` | 分支名称 |
| `git_path` | str | `'git'` | Git 可执行文件路径 |
| `proxy` | Optional[str] | `None` | HTTP/HTTPS 代理地址 |
| `ssl` | bool | `True` | 是否验证 SSL 证书 |
| `update` | bool | `True` | 是否启用自动更新 |
| `keep_changes` | bool | `False` | 是否保留本地修改 |
| `mirror` | bool | `False` | 是否使用镜像加速 |
| `mirror_url` | str | `''` | 镜像服务器地址 |
| `depth` | Optional[int] | `None` | 浅克隆深度，仅拉取最近 N 层提交 |
| `log_callback` | Callable | `None` | 日志回调函数 |


## 💻 使用方式
### 方式一：Python 代码调用
#### 集成到项目中
### 步骤一：复制文件
### 步骤二：安装依赖
```bash
uv sync
```
### 步骤三：修改配置
#### 直接修改 `config.ini`
#### 注意project_folder的路径相对于GitSDK.py文件所在目录
### 步骤四：集成使用
```python
# 在你的项目入口文件中
from GitSDK import git_by_ini


def main():
   # 启动时更新
   git_by_ini()
   # 运行你的程序
   # ...


if __name__ == '__main__':
   main()
```
### 步骤五：享受！！！
### 方式二：命令行工具

#### 基本用法
```bash
python GitSDK.py --repo https://github.com/name/project
```
#### 仅检查更新
```bash
python GitSDK.py \
    --repo https://github.com/name/project \
    --check-only
# 返回值：0 表示有更新，1 表示无更新
```
#### 保留本地修改
```bash
python GitSDK.py \
    --repo https://github.com/name/project \
    --keep-changes
```

#### 深化浅克隆或转换为完整仓库
```bash
# 在当前基础上再增加 5 层历史（从 depth=1 到 depth=6）
python GitSDK.py \
    --repo https://github.com/name/project \
    --deepen=5

# 在当前基础上减少 2 层历史
python GitSDK.py \
    --repo https://github.com/name/project \
    --deepen=-2

# 转换为完整仓库（获取所有历史）
python GitSDK.py \
    --repo https://github.com/name/project \
    --unshallow
```

### 命令行参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--repo` | Git 仓库地址（必需） | - |
| `--branch` | 分支名称 | `master` |
| `--git` | git 可执行文件路径 | `git` |
| `--proxy` | HTTP 代理地址 | `None` |
| `--no-ssl-verify` | 不验证 SSL 证书 | `False` |
| `--no-auto-update` | 禁用自动更新 | `False` |
| `--keep-changes` | 保留本地修改 | `False` |
| `--use-mirror` | 使用镜像加速 | `False` |
| `--mirror-url` | 镜像地址 | `''` |
| `--depth` | 浅克隆深度（初始化时设置） | `None` |
| `--unshallow` | 转换为完整仓库（获取所有历史） | `False` |
| `--folder` | 项目根目录 | 当前目录 |
| `--check-only` | 仅检查更新 | `False` |


## 🎯 相关 git代码

```
1. 仓库管理
git init - 初始化 Git 仓库
2. 远程仓库配置
git remote add <name> <url> - 添加远程仓库
git remote set-url <name> <url> - 设置远程仓库 URL
3. 分支操作
git fetch <remote> <branch> - 获取远程分支
git fetch --depth=<N> <remote> <branch> - 以浅克隆深度获取分支
git fetch --unshallow - 将浅克隆转换为完整仓库
git fetch --deepen=<N> - 深化浅克隆深度 N 层
git checkout <branch> - 切换分支
git pull --ff-only <remote> <branch> - 快进模式拉取代码
git pull --ff-only --depth=<N> <remote> <branch> - 以浅克隆深度拉取代码
4. 重置与回退
git reset --hard <commit> - 硬重置到指定提交
git stash - 暂存修改
git stash pop - 恢复暂存的修改
5. 配置管理
git config --local http.proxy <proxy> - 设置 HTTP 代理
git config --local https.proxy <proxy> - 设置 HTTPS 代理
git config --local http.sslVerify true|false - 设置 SSL 验证
git config --local --unset http.proxy - 删除 HTTP 代理配置
git config --local --unset https.proxy - 删除 HTTPS 代理配置
6. 日志查看
git log --not --remotes=<remote>/* -1 --oneline - 检查本地独有提交
git log ..<remote>/<branch> --pretty=format:"%H---%an---%ad---%s" --date=iso -1 - 获取远程最新提交信息
git log ..<remote>/<branch> --pretty=format:"%an|||%ad|||%s|||%H" --date=iso -1 - 获取格式化远程提交信息
git --no-pager log --no-merges -1 - 显示最新版本（不含合并提交）
```


## 🤝 贡献

欢迎提交 Issue 和 PR 来改进这个工具！

**最后更新**: 2026-03-04  
**版本**: 1.0.0
**Mingit版本**: 2.53.0
