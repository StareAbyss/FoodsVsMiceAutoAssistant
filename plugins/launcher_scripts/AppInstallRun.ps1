param(
    [switch]$RunInConsole
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$uvDir = Join-Path $scriptDir "uv"
$uvBinDir = Join-Path $scriptDir "bin"
$uvExe = Join-Path $uvBinDir "uv.exe"
$uvZip = Join-Path $uvDir "uv-x86_64-pc-windows-msvc.zip"
$uvZipSha256 = "30FDF26C209F0CB7C97D3B08A26AB4E78CE5AE0E031B88798CBACCC0F24F452B"
$appDir = $scriptDir

function Write-Header {
    Write-Host "============================================================"
    if ($RunInConsole) {
        Write-Host "FAA 自动安装与启动（保留运行框）"
    } else {
        Write-Host "FAA 自动安装与启动"
    }
    Write-Host "============================================================"
    Write-Host "当前目录："
    Write-Host "`"$appDir\`""
    Write-Host ""
    Write-Host "本程序会自动准备 FAA 所需的运行环境。"
    Write-Host "普通用户不需要提前安装 uv 或 Python。"
    Write-Host "首次启动可能需要数分钟，请耐心等待。"
    if ($RunInConsole) {
        Write-Host "本入口会在当前黑框中运行 FAA，方便排查启动日志和异常。"
    }
    Write-Host "============================================================"
}

function Stop-WithMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host ""
    Write-Host $Message
    Write-Host "FAA 安装或启动失败。"
    Write-Host "请根据上方的错误提示处理后重试。"
    Read-Host "按 Enter 关闭此窗口"
    exit 1
}

function Find-AppDir {
    if (Test-Path -LiteralPath (Join-Path $appDir "pyproject.toml")) {
        return
    }

    $sourceTreeRoot = Join-Path $scriptDir "..\.."
    if (Test-Path -LiteralPath (Join-Path $sourceTreeRoot "pyproject.toml")) {
        $script:appDir = (Resolve-Path -LiteralPath $sourceTreeRoot).Path
        return
    }

    Stop-WithMessage "[错误] 未找到 pyproject.toml。请确认你正在从完整的 FAA 发布包中启动，或者没有把 FAA.exe 单独拿出来运行。"
}

function Prepare-Uv {
    Write-Host ""
    Write-Host "[1/4] 正在准备 FAA 自带的 uv 环境管理器..."
    if (Test-Path -LiteralPath $uvExe) {
        Write-Host "已找到本地 uv："
        Write-Host "`"$uvExe`""
        return
    }

    Write-Host "首次启动未找到本地 uv，正在从发布包内置文件安装。"
    $installer = Join-Path $uvDir "uv-installer.ps1"
    if (-not (Test-Path -LiteralPath $installer)) {
        Stop-WithMessage "[错误] 缺少 uv 安装脚本：`n`"$installer`"`n请重新解压完整发布包后再启动。"
    }
    if (-not (Test-Path -LiteralPath $uvZip)) {
        Stop-WithMessage "[错误] 缺少内置 uv 压缩包：`n`"$uvZip`"`n请重新解压完整发布包后再启动。"
    }

    Write-Host "正在校验内置 uv 文件完整性..."
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $uvZip).Hash
    if ($actualHash -ne $uvZipSha256) {
        Stop-WithMessage "[错误] 内置 uv 文件校验失败，文件可能损坏或被替换。请重新下载或重新解压发布包。"
    }

    $env:UV_INSTALL_DIR = $uvBinDir
    $env:UV_NO_MODIFY_PATH = "1"
    $env:UV_DISABLE_UPDATE = "1"
    $env:INSTALLER_DOWNLOAD_URL = $uvDir

    & powershell -NoProfile -ExecutionPolicy Bypass -File $installer
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "[错误] uv 安装失败。请检查系统是否允许运行 PowerShell 脚本，或尝试以管理员身份重新启动。"
    }
    if (-not (Test-Path -LiteralPath $uvExe)) {
        Stop-WithMessage "[错误] uv.exe 未能安装到目标位置：`n`"$uvExe`"`n请确认当前目录有写入权限。"
    }

    Write-Host "uv 准备完成。"
}

function Install-Python {
    Set-Location -LiteralPath $appDir
    Write-Host ""
    Write-Host "[2/4] 正在准备 Python 3.12 运行环境..."
    Write-Host "首次启动可能需要下载 Python，请保持网络连接。"
    Write-Host "Python 下载源：uv 默认 Python 安装源。"
    Write-Host "如需修改 Python 下载镜像，开发者可在 AppInstallRun.ps1 的 uv python install 命令中添加 --mirror 参数。"
    Write-Host "也可以设置环境变量 UV_PYTHON_INSTALL_MIRROR。"

    & $uvExe python install 3.12
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "[错误] Python 运行环境准备失败。请检查网络连接，或稍后重试。"
    }

    Write-Host "Python 运行环境准备完成。"
}

function Sync-Locked {
    Set-Location -LiteralPath $appDir
    Write-Host ""
    Write-Host "[3/4] 正在安装或校验 FAA 运行依赖..."
    Write-Host "首次启动会比较慢，后续启动会复用本地环境。"
    Write-Host "Python 依赖下载源：pyproject.toml 中的 [[tool.uv.index]]。"
    Write-Host "当前默认镜像源：https://pypi.tuna.tsinghua.edu.cn/simple"
    Write-Host "如需修改依赖镜像，开发者可编辑 pyproject.toml 的 [[tool.uv.index]].url。"

    & $uvExe sync --locked --no-dev
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "[错误] FAA 运行依赖安装失败。请检查网络连接，或确认发布包中的 uv.lock 没有被修改。"
    }

    Write-Host "FAA 运行依赖准备完成。"
}

function Run-App {
    Set-Location -LiteralPath $appDir
    Write-Host ""
    Write-Host "[4/4] 正在启动 FAA 主程序..."

    if ($RunInConsole) {
        $pythonExe = Join-Path $appDir ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $pythonExe)) {
            Stop-WithMessage "[错误] 未找到带运行框启动所需的 Python：`n`"$pythonExe`"`n请重新运行本脚本，或确认第 3 步依赖安装已经成功完成。"
        }

        Write-Host "将使用当前黑框前台启动 FAA。"
        Write-Host "此模式用于排查问题：FAA 运行期间请不要关闭此窗口。"
        & $pythonExe -m function.faa_main
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) {
            $exitCode = 0
        }

        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "FAA 已正常退出，退出码：0"
        } else {
            Write-Host "[错误] FAA 异常退出，退出码：$exitCode"
            Write-Host "请查看上方控制台输出，也可以查看 logs 文件夹中的日志。"
        }
        Read-Host "按 Enter 关闭此窗口"
        exit $exitCode
    }

    $pythonwExe = Join-Path $appDir ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path -LiteralPath $pythonwExe)) {
        Stop-WithMessage "[错误] 未找到 GUI 启动器：`n`"$pythonwExe`"`n请重新运行本脚本，或确认第 3 步依赖安装已经成功完成。"
    }

    Write-Host "将使用独立窗口启动 FAA，启动后本黑框会自动关闭。"
    Start-Process -FilePath $pythonwExe -ArgumentList @("-m", "function.faa_main") -WorkingDirectory $appDir
    Write-Host "FAA 主程序已启动，本窗口将在 3 秒后自动关闭。"
    Start-Sleep -Seconds 3
}

Find-AppDir
Write-Header
Prepare-Uv
Install-Python
Sync-Locked
Run-App
exit 0
