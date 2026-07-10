$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = $scriptDir

if (-not (Test-Path -LiteralPath (Join-Path $appDir "pyproject.toml"))) {
    $sourceTreeRoot = Join-Path $scriptDir "..\.."
    if (Test-Path -LiteralPath (Join-Path $sourceTreeRoot "pyproject.toml")) {
        $appDir = (Resolve-Path -LiteralPath $sourceTreeRoot).Path
    }
}

$uvBinDir = Join-Path $scriptDir "bin"
$localVenvDir = Join-Path $appDir ".venv"

function Test-IsChildOrSelf {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Parent,
        [Parameter(Mandatory = $true)]
        [string]$Child
    )

    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    return $childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase) -or
        $childFull.StartsWith($parentFull + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Remove-ManagedDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$AllowedParent
    )

    if (-not (Test-IsChildOrSelf -Parent $AllowedParent -Child $Path)) {
        throw "[安全中断] $Label 不在允许删除范围内：$Path"
    }

    if (Test-Path -LiteralPath $Path) {
        Write-Host "正在删除 $Label："
        Write-Host "`"$Path`""
        Remove-Item -LiteralPath $Path -Recurse -Force
    } else {
        Write-Host "$Label 不存在，跳过："
        Write-Host "`"$Path`""
    }
}

function Get-BlockingProcesses {
    $targets = @($uvBinDir, $localVenvDir)
    $currentPid = $PID
    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $process = $_
            $_.ProcessId -ne $currentPid -and
            $_.ExecutablePath -and
            ($targets | Where-Object { Test-IsChildOrSelf -Parent $_ -Child $process.ExecutablePath })
        } |
        Sort-Object ProcessId

    return @($processes)
}

function Show-BlockingProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [array]$Processes
    )

    Write-Host ""
    Write-Host "[提示] 检测到以下进程正在使用 FAA 本地运行环境："
    foreach ($process in $Processes) {
        Write-Host "  PID $($process.ProcessId)  $($process.Name)"
        Write-Host "    $($process.ExecutablePath)"
    }
}

function Resolve-BlockingProcesses {
    while ($true) {
        $blockingProcesses = Get-BlockingProcesses
        if ($blockingProcesses.Count -eq 0) {
            return
        }

        Show-BlockingProcesses -Processes $blockingProcesses
        Write-Host ""
        Write-Host "请先关闭正在运行的 FAA，再继续卸载。"
        Write-Host "直接按 Enter：重新检测"
        Write-Host "输入 K：强制结束上述进程后继续卸载"
        Write-Host "输入 C：取消卸载"
        $choice = (Read-Host "请选择").Trim()

        if ($choice -in @("C", "c")) {
            Write-Host ""
            Write-Host "已取消卸载。"
            Read-Host "按 Enter 关闭此窗口"
            exit 1
        }

        if ($choice -in @("K", "k")) {
            foreach ($process in $blockingProcesses) {
                Write-Host "正在结束进程 PID $($process.ProcessId)：$($process.Name)"
                Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            }
            Start-Sleep -Seconds 1
        }
    }
}

Write-Host "========================================"
Write-Host "FAA 本地运行环境卸载工具"
Write-Host "========================================"
Write-Host ""
Write-Host "本工具只会删除 FAA 管理的本地运行环境："
Write-Host "  1. 项目内 uv："
Write-Host "     `"$uvBinDir`""
Write-Host "  2. 项目虚拟环境："
Write-Host "     `"$localVenvDir`""
Write-Host ""
Write-Host "本工具不会删除："
Write-Host "  - 用户全局 uv"
Write-Host "  - uv cache"
Write-Host "  - uv-managed Python 全局安装"
Write-Host "  - FAA 配置、资源、日志或用户数据"
Write-Host ""

$confirm = (Read-Host "确认卸载本地运行环境？请输入 Y 后按 Enter").Trim()
if ($confirm -notin @("Y", "y")) {
    Write-Host ""
    Write-Host "已取消卸载。"
    Read-Host "按 Enter 关闭此窗口"
    exit 1
}

try {
    Write-Host ""
    Resolve-BlockingProcesses
    Remove-ManagedDirectory -Path $uvBinDir -Label "项目内 uv" -AllowedParent $scriptDir
    Remove-ManagedDirectory -Path $localVenvDir -Label "项目虚拟环境 .venv" -AllowedParent $appDir
    Write-Host ""
    Write-Host "卸载完成。下次启动 FAA 时会自动重新准备运行环境。"
    Read-Host "按 Enter 关闭此窗口"
    exit 0
} catch {
    Write-Host ""
    Write-Host "[错误] 卸载失败："
    Write-Host $_.Exception.Message
    Read-Host "按 Enter 关闭此窗口"
    exit 1
}
