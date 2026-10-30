# FAA_LEGACY_UPDATE_BRIDGE - source archive compatibility only.
$entryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Start-Process -FilePath (Join-Path $entryRoot 'FAA - 环境安装器.exe')
