# Git Python Plus Documentation

## 📖 Introduction

`Git Python Plus`, also known as `gpp`, is a standalone Git auto-update tool that integrates standard Git update and mirror-accelerated update functionality. This module is fully configurable and can be easily migrated to any Python project.

## ✨ Key Features
- **Fully Configurable**: All parameters can be customized via code or command line
- **Zero Dependency Burden**: No third-party library dependencies
- **Cross-Platform**: Supports Windows, Linux, macOS (requires corresponding platform git tools)
- **Log Callback**: Supports custom log handler functions
- **CLI Tool**: Can be used directly as a command-line tool

## 🚀 Quick Start

### Install UV Package Manager (Windows) (Optional)

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Basic Usage Example

```python
from GitSDK import GitSDK, GitConfig

# 1. Create configuration
config = GitConfig(
    repository='https://github.com/name/project',
    branch='master',
    update=True,
)

# 2. Create updater
updater = GitSDK(config)

# 3. Execute update
if updater.update():
    print("Update successful!")
else:
    print("Update failed")
```

## 📋 Configuration Parameters

### GitConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repository` | str | GitHub URL | Git repository URL |
| `branch` | str | `'master'` | Branch name |
| `git_path` | str | `'git'` | Git executable file path |
| `proxy` | Optional[str] | `None` | HTTP/HTTPS proxy address |
| `ssl` | bool | `True` | Whether to verify SSL certificate |
| `update` | bool | `True` | Enable automatic update |
| `keep_changes` | bool | `False` | Keep local modifications |
| `mirror` | bool | `False` | Use mirror acceleration |
| `mirror_url` | str | `''` | Mirror server address |
| `depth` | Optional[int] | `None` | Shallow clone depth, fetch only last N commits |
| `log_callback` | Callable | `None` | Log callback function |


## 💻 Usage Methods

### Method 1: Python Code Integration
#### Integrate into Your Project
##### Step 1: Copy Files
##### Step 2: Install Dependencies
```bash
uv sync
```
##### Step 3: Modify Configuration
##### Directly modify `config.ini`
##### Note: project_folder path is relative to GitSDK.py file location
##### Step 4: Integration Usage
```python
# In your project entry file
from GitSDK import git_by_ini


def main():
   # Update at startup
   git_by_ini()
   # Run your program
   # ...


if __name__ == '__main__':
   main()
```
##### Step 5: Enjoy!!!
### Method 2: Command Line Tool

#### Basic Usage
```bash
python GitSDK.py --repo https://github.com/name/project
```

#### Check Updates Only
```bash
python GitSDK.py \
    --repo https://github.com/name/project \
    --check-only
# Return value: 0 means updates available, 1 means no updates
```

#### Keep Local Modifications
```bash
python GitSDK.py \
    --repo https://github.com/name/project \
    --keep-changes
```

#### Deepen Shallow Clone or Convert to Full Repository
```bash
# Add 5 more layers of history (from depth=1 to depth=6)
python GitSDK.py \
    --repo https://github.com/name/project \
    --deepen=5

# Reduce history by 2 layers
python GitSDK.py \
    --repo https://github.com/name/project \
    --deepen=-2

# Convert to full repository (fetch all history)
python GitSDK.py \
    --repo https://github.com/name/project \
    --unshallow
```

### Command Line Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--repo` | Git repository URL (required) | - |
| `--branch` | Branch name | `master` |
| `--git` | Git executable file path | `git` |
| `--proxy` | HTTP proxy address | `None` |
| `--no-ssl-verify` | Do not verify SSL certificate | `False` |
| `--no-auto-update` | Disable automatic update | `False` |
| `--keep-changes` | Keep local modifications | `False` |
| `--use-mirror` | Use mirror acceleration | `False` |
| `--mirror-url` | Mirror URL | `''` |
| `--depth` | Shallow clone depth (set during initialization) | `None` |
| `--unshallow` | Convert to full repository (fetch all history) | `False` |
| `--folder` | Project root directory | Current directory |
| `--check-only` | Check updates only | `False` |


## 🎯 Related Git Commands

```
1. Repository Management
git init - Initialize Git repository
2. Remote Repository Configuration
git remote add <name> <url> - Add remote repository
git remote set-url <name> <url> - Set remote repository URL
3. Branch Operations
git fetch <remote> <branch> - Fetch remote branch
git fetch --depth=<N> <remote> <branch> - Fetch with shallow clone depth
git fetch --unshallow - Convert shallow clone to full repository
git fetch --deepen=<N> - Deepen shallow clone by N layers
git checkout <branch> - Switch branch
git pull --ff-only <remote> <branch> - Pull code in fast-forward mode
git pull --ff-only --depth=<N> <remote> <branch> - Pull with shallow clone depth
4. Reset and Revert
git reset --hard <commit> - Hard reset to specified commit
git stash - Stash modifications
git stash pop - Restore stashed modifications
5. Configuration Management
git config --local http.proxy <proxy> - Set HTTP proxy
git config --local https.proxy <proxy> - Set HTTPS proxy
git config --local http.sslVerify true|false - Set SSL verification
git config --local --unset http.proxy - Remove HTTP proxy
git config --local --unset https.proxy - Remove HTTPS proxy
6. Log Viewing
git log --not --remotes=<remote>/* -1 --oneline - Check local-only commits
git log ..<remote>/<branch> --pretty=format:"%H---%an---%ad---%s" --date=iso -1 - Get latest remote commit info
git log ..<remote>/<branch> --pretty=format:"%an|||%ad|||%s|||%H" --date=iso -1 - Get formatted remote commit info
git --no-pager log --no-merges -1 - Display latest version (without merge commits)
```


## 🤝 Contributing

Issues and PRs are welcome to improve this tool!

**Last Updated**: 2026-03-04  
**Version**: 1.0.0
**MinGit Version**: 2.53.0
