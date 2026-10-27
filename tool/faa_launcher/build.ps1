param(
    [string]$Cxx = $env:FAA_CXX,
    [string]$OutputDirectory,
    [ValidateSet('Both', 'Installer', 'Launcher')]
    [string]$Variant = 'Both'
)

$ErrorActionPreference = 'Stop'
$sourceDirectory = $PSScriptRoot
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $sourceDirectory '..\..')).Path
if (-not $OutputDirectory) { $OutputDirectory = $projectRoot }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

if (-not $Cxx) {
    foreach ($candidate in @('g++.exe', 'cl.exe')) {
        $compilerCommand = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($compilerCommand) { $Cxx = $compilerCommand.Source; break }
    }
}
if (-not $Cxx -or -not (Test-Path -LiteralPath $Cxx)) {
    throw '未找到 C++ 编译器。请用 -Cxx 指定 MinGW-w64 g++.exe，或在 Visual Studio 开发者命令行中运行。'
}

$compilerDirectory = Split-Path -Parent $Cxx
$savedPath = $env:PATH
$artifacts = [Collections.Generic.List[string]]::new()
$buildRoot = Join-Path $projectRoot 'dist\faa_launcher'
foreach ($directory in @((Join-Path $projectRoot 'dist'), $buildRoot)) {
    if ((Test-Path -LiteralPath $directory) -and
        ((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "构建目录不能为目录链接：$directory"
    }
}
$buildWorkspace = Join-Path $buildRoot ('build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $buildWorkspace | Out-Null
$generatedIcon = Join-Path $sourceDirectory 'launcher.generated.ico'
$locationPushed = $false
try {
    Copy-Item -LiteralPath (Join-Path $projectRoot 'resource\logo\圆角-FetDeathWing-256x-AllSize.ico') -Destination $generatedIcon -Force
    $env:PATH = "$compilerDirectory;$savedPath"
    Push-Location -LiteralPath $sourceDirectory
    $locationPushed = $true
    $variants = if ($Variant -eq 'Both') { @('Installer', 'Launcher') } else { @($Variant) }
    foreach ($kind in $variants) {
        $isLauncher = $kind -eq 'Launcher'
        $buildDirectory = Join-Path $buildWorkspace $kind.ToLowerInvariant()
        New-Item -ItemType Directory -Force -Path $buildDirectory | Out-Null
        $name = if ($isLauncher) { 'FAA - 快速启动.exe' } else { 'FAA - 环境安装器.exe' }
        $output = Join-Path $buildDirectory $name
        $define = if ($isLauncher) { @('/D', 'FAA_ENTRY_BUILD=1') } else { @() }

        if ([IO.Path]::GetFileName($Cxx) -ieq 'cl.exe') {
            $resource = Join-Path $buildDirectory 'launcher.res'
            $resourceDefine = if ($isLauncher) { @('/d', 'FAA_ENTRY_BUILD=1') } else { @() }
            & rc.exe /nologo /c65001 @resourceDefine "/fo$resource" launcher.rc
            if ($LASTEXITCODE -ne 0) { throw 'Windows 资源编译失败。' }
            & $Cxx /nologo /std:c++17 /utf-8 /EHsc /O2 /MT /W4 /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0601 @define `
                launcher.cpp launcher_core.cpp launcher_maintenance.cpp $resource "/Fe:$output" "/Fo:$buildDirectory\" `
                /link /SUBSYSTEM:WINDOWS user32.lib gdi32.lib gdiplus.lib shell32.lib comctl32.lib comdlg32.lib uuid.lib bcrypt.lib
        } else {
            $resourceCompiler = Join-Path $compilerDirectory 'windres.exe'
            if (-not (Test-Path -LiteralPath $resourceCompiler)) { throw 'MinGW-w64 编译器旁没有找到 windres.exe。' }
            $resource = Join-Path $buildDirectory 'launcher-resource.o'
            $windresDefine = if ($isLauncher) { @('--define', 'FAA_ENTRY_BUILD=1') } else { @() }
            & $resourceCompiler --codepage=65001 @windresDefine -i launcher.rc -O coff -o $resource
            if ($LASTEXITCODE -ne 0) { throw 'Windows 资源编译失败。' }
            $compilerDefine = if ($isLauncher) { @('-D', 'FAA_ENTRY_BUILD=1') } else { @() }
            & $Cxx -std=c++11 -O2 -Wall -Wextra -Wno-missing-field-initializers -Wno-unknown-pragmas -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0601 @compilerDefine `
                -municode -mwindows -static -static-libgcc -static-libstdc++ `
                launcher.cpp launcher_core.cpp launcher_maintenance.cpp $resource -o $output `
                -luser32 -lgdi32 -lgdiplus -lshell32 -lcomctl32 -lcomdlg32 -luuid -lbcrypt `
                '-Wl,--nxcompat,--dynamicbase' -s
        }
        if ($LASTEXITCODE -ne 0) { throw "FAA 启动器编译失败：$kind" }

        $artifact = Join-Path $OutputDirectory $name
        Copy-Item -LiteralPath $output -Destination $artifact -Force
        $artifacts.Add($artifact)
        $packagedEntry = Join-Path (Join-Path $projectRoot 'plugins\root_entries') $name
        Copy-Item -LiteralPath $output -Destination $packagedEntry -Force
    }
} catch {
    Write-Warning "构建未完成，中间文件保留在：$buildWorkspace"
    throw
} finally {
    if ($locationPushed) { Pop-Location }
    $env:PATH = $savedPath
    Remove-Item -LiteralPath $generatedIcon -Force -ErrorAction SilentlyContinue
}

try {
    # 只删除本次独立工作目录；自定义输出和失败构建可能也位于 dist，不能整体清空。
    $resolvedWorkspace = (Resolve-Path -LiteralPath $buildWorkspace).Path
    if ((Split-Path -Parent $resolvedWorkspace) -ne [IO.Path]::GetFullPath($buildRoot) -or
        (Split-Path -Leaf $resolvedWorkspace) -notmatch '^build-[0-9a-f]{32}$') {
        throw "拒绝清理范围外的目录：$resolvedWorkspace"
    }
    foreach ($directory in @((Join-Path $projectRoot 'dist'), $buildRoot, $resolvedWorkspace)) {
        if ((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "清理目录不能为目录链接：$directory"
        }
    }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($resolvedWorkspace)
    while ($pending.Count -gt 0) {
        foreach ($item in Get-ChildItem -LiteralPath $pending.Pop() -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "中间文件中存在链接：$($item.FullName)" }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
    Remove-Item -LiteralPath $resolvedWorkspace -Recurse -Force
    if (@(Get-ChildItem -LiteralPath $buildRoot -Force).Count -eq 0) { Remove-Item -LiteralPath $buildRoot }
    Write-Output '已清理本次构建中间文件。'
} catch {
    Write-Warning "正式程序已生成，但中间文件未能完全清理：$($_.Exception.Message)"
}

foreach ($artifact in $artifacts) { Write-Output "已生成：$artifact" }
Write-Output '仅构建快速启动和环境安装器。'
