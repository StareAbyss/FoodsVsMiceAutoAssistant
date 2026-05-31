# AI 运行环境配置

本文只处理 JetBrains / PyCharm / Codex / ACP 这类 AI 智能体环境问题。项目如何运行见 `运行环境和调试环境.md`；发布包流程见 `打包 & 部署.md`。

## 快速判断

接手后先运行：

```powershell
Get-Command node,npm,npx,uv,python,pip,java,git,cmd | Select-Object Name,Source
node --version
npm --version
npx --version
uv --version
python --version
python -c "import sys; print(sys.executable)"
pip --version
java -version
git --version
cmd /c ver
```

关键路径应优先指向：

```text
node.exe   ...\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin\node.exe
npm.cmd    ...\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin\npm.cmd
npx.cmd    ...\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin\npx.cmd
uv.exe     D:\Dev\Tools\uv\uv.exe
python.exe D:\Dev\Runtimes\Python\Python-3.12.5\python.exe
pip.exe    D:\Dev\Runtimes\Python\Python-3.12.5\Scripts\pip.exe
java.exe   D:\Dev\Runtimes\Java\jdk-1.8.0.261\bin\java.exe
git.exe    D:\Program Files\Git\cmd\git.exe
cmd.exe    C:\Windows\System32\cmd.exe
```

注意：项目 `.venv` 当前是 uv-managed Python 3.12.9；上面的 `D:\Dev\Runtimes\Python\Python-3.12.5` 是 AI/系统命令环境的兜底 Python，不要求和 `.venv` 完全一致。

如果 `java` 指向下面这个路径，通常是错的：

```text
C:\Program Files (x86)\Common Files\Oracle\Java\javapath\java.exe
```

该 Oracle `javapath` 当前可能损坏，曾出现 `could not open ...\jvm.cfg`。应让 `D:\Dev\Runtimes\Java\jdk-1.8.0.261\bin` 排在 PATH 前面。

## Codex 自身配置

优先检查：

```text
C:\Users\Administrator\AppData\Local\JetBrains\PyCharm2026.1\aia\codex\config.toml
```

推荐内容：

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[shell_environment_policy]
inherit = "all"

[shell_environment_policy.set]
PATH = 'C:\Users\Administrator\AppData\Local\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin;D:\Program Files\nodejs;C:\Users\Administrator\AppData\Roaming\npm;C:\Windows\System32;C:\Windows;D:\Dev\Tools\uv;D:\Dev\Runtimes\Python\Python-3.12.5\Scripts;D:\Dev\Runtimes\Python\Python-3.12.5;D:\Dev\Runtimes\Java\jdk-1.8.0.261\bin;D:\Program Files\Git\cmd'
DEV_HOME = 'D:\Dev'
PYTHON312_HOME = 'D:\Dev\Runtimes\Python\Python-3.12.5'
JAVA_HOME = 'D:\Dev\Runtimes\Java\jdk-1.8.0.261'
JAVA8_HOME = 'D:\Dev\Runtimes\Java\jdk-1.8.0.261'
UV_PYTHON_INSTALL_DIR = 'D:\Dev\Runtimes\Python\uv-managed'
UV_CACHE_DIR = 'D:\Dev\Cache\uv'
UV_TOOL_DIR = 'D:\Dev\GlobalEnv\uv-tools'
UV_LINK_MODE = "copy"
PIP_CACHE_DIR = 'D:\Dev\Cache\pip'
```

作用：

- 让 Codex 执行 shell 命令时继承启动器环境。
- 显式把 Node、uv、Python、Java、Git 放到 PATH 前面。
- 避免 `java` 落到损坏的 Oracle `javapath`。

坑点：

- Windows 路径在 TOML 里用单引号，避免 `\U`、`\P` 被当作转义。
- 该文件可能被 PyCharm 重启流程重写。如果重启后又只剩 `approval_policy` 和 `sandbox_mode` 两行，需要重新写入上述配置。
- 该配置只在 Codex 进程启动后生效；如果 ACP 进程还没启动就报 `node` 找不到，看下一节。

## ACP 启动配置

如果 PyCharm 报：

```text
Failed to initialize ACP process
'"node"' 不是内部或外部命令
```

说明问题发生在 Codex 启动前，`config.toml` 帮不上忙。需要检查：

```text
C:\Users\Administrator\.jetbrains\acp.json
```

关键点是 `env.PATH` 必须包含 JetBrains Node、系统 Node、npm 全局目录和开发工具目录：

```json
{
  "agent_servers": {
    "Codex Dev PATH": {
      "command": "C:\\Users\\Administrator\\AppData\\Local\\JetBrains\\PyCharm2026.1\\acp-agents\\.runtimes\\node\\24.13.0\\bin\\npx.cmd",
      "args": [
        "@agentclientprotocol/codex-acp@0.0.44",
        "-acp"
      ],
      "env": {
        "PATH": "C:\\Users\\Administrator\\AppData\\Local\\JetBrains\\PyCharm2026.1\\acp-agents\\.runtimes\\node\\24.13.0\\bin;D:\\Program Files\\nodejs;C:\\Users\\Administrator\\AppData\\Roaming\\npm;C:\\Windows\\System32;C:\\Windows;D:\\Dev\\Tools\\uv;D:\\Dev\\Runtimes\\Python\\Python-3.12.5\\Scripts;D:\\Dev\\Runtimes\\Python\\Python-3.12.5;D:\\Dev\\Runtimes\\Java\\jdk-1.8.0.261\\bin;D:\\Program Files\\Git\\cmd",
        "DEV_HOME": "D:\\Dev",
        "PYTHON312_HOME": "D:\\Dev\\Runtimes\\Python\\Python-3.12.5",
        "JAVA_HOME": "D:\\Dev\\Runtimes\\Java\\jdk-1.8.0.261",
        "JAVA8_HOME": "D:\\Dev\\Runtimes\\Java\\jdk-1.8.0.261",
        "UV_PYTHON_INSTALL_DIR": "D:\\Dev\\Runtimes\\Python\\uv-managed",
        "UV_CACHE_DIR": "D:\\Dev\\Cache\\uv",
        "UV_TOOL_DIR": "D:\\Dev\\GlobalEnv\\uv-tools",
        "UV_LINK_MODE": "copy",
        "PIP_CACHE_DIR": "D:\\Dev\\Cache\\pip"
      }
    }
  }
}
```

坑点：

- `npx.cmd` 可以被绝对路径启动，但 `@agentclientprotocol/codex-acp` 内部还会执行 `node`；所以 PATH 里必须能找到 `node.exe`。
- 不建议直接改 `AppData\Roaming\JetBrains\acp-agents\installed.json`，该文件可能被 JetBrains 更新覆盖。
- 如果使用自定义 agent，需要在 PyCharm AI Chat 里确认已选择 `Codex Dev PATH`。
- 修改后通常需要重启 PyCharm 或重新打开 AI Chat。

## 临时救急

如果当前会话 PATH 不对，但需要先继续工作，可以临时注入：

```powershell
$env:Path = 'C:\Users\Administrator\AppData\Local\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin;D:\Program Files\nodejs;C:\Users\Administrator\AppData\Roaming\npm;C:\Windows\System32;C:\Windows;D:\Dev\Tools\uv;D:\Dev\Runtimes\Python\Python-3.12.5\Scripts;D:\Dev\Runtimes\Python\Python-3.12.5;D:\Dev\Runtimes\Java\jdk-1.8.0.261\bin;D:\Program Files\Git\cmd'
```

或直接用绝对路径：

```powershell
& 'C:\Users\Administrator\AppData\Local\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin\node.exe' --version
& 'C:\Users\Administrator\AppData\Local\JetBrains\PyCharm2026.1\acp-agents\.runtimes\node\24.13.0\bin\npx.cmd' --version
& 'D:\Dev\Tools\uv\uv.exe' --version
& 'D:\Dev\Runtimes\Python\Python-3.12.5\python.exe' --version
& 'D:\Dev\Runtimes\Python\Python-3.12.5\Scripts\pip.exe' --version
& 'D:\Dev\Runtimes\Java\jdk-1.8.0.261\bin\java.exe' -version
& 'D:\Program Files\Git\cmd\git.exe' --version
```

## 不要误判

- 不要看到 `uv`、`python`、`java` 找不到就先重装，先查 PATH。
- 不要看到 `node` 报错就只检查 `npx.cmd`；ACP 包内部也需要 `node.exe`。
- 不要把 `config.toml` 当成 ACP 启动前的万能修复，它只影响 Codex 启动后的命令执行环境。
- 不要直接删除旧运行环境目录，先确认没有脚本依赖。
