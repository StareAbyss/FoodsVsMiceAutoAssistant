param(
    [string]$Cxx = $env:FAA_CXX,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$builder = Join-Path $PSScriptRoot 'build.ps1'
& $builder -Cxx $Cxx -OutputDirectory $OutputDirectory -Variant Launcher
