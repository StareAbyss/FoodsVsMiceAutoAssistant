$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$source = Join-Path $repoRoot "tool\packaging\faa_launcher\FAA.cs"
$output = Join-Path $repoRoot "plugins\root_entries\FAA.exe"
$iconSource = Get-ChildItem -LiteralPath (Join-Path $repoRoot "resource\logo") -Filter "*-FetDeathWing-450x.png" |
    Select-Object -First 1
$iconFile = Join-Path $repoRoot "tool\packaging\faa_launcher\FAA.generated.ico"

function New-IconFromPng {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePng,
        [Parameter(Mandatory = $true)]
        [string]$DestinationIco
    )

    Add-Type -AssemblyName System.Drawing

    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $frames = New-Object System.Collections.Generic.List[byte[]]
    $sourceImage = [System.Drawing.Image]::FromFile($SourcePng)

    try {
        foreach ($size in $sizes) {
            $bitmap = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

                $scale = [Math]::Min($size / $sourceImage.Width, $size / $sourceImage.Height)
                $width = [int][Math]::Round($sourceImage.Width * $scale)
                $height = [int][Math]::Round($sourceImage.Height * $scale)
                $x = [int][Math]::Floor(($size - $width) / 2)
                $y = [int][Math]::Floor(($size - $height) / 2)
                $graphics.DrawImage($sourceImage, $x, $y, $width, $height)
            }
            finally {
                $graphics.Dispose()
            }

            $memory = New-Object System.IO.MemoryStream
            try {
                $bitmap.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
                $frames.Add($memory.ToArray())
            }
            finally {
                $memory.Dispose()
                $bitmap.Dispose()
            }
        }
    }
    finally {
        $sourceImage.Dispose()
    }

    $stream = [System.IO.File]::Open($DestinationIco, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $writer = New-Object System.IO.BinaryWriter $stream
    try {
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$frames.Count)

        $offset = 6 + (16 * $frames.Count)
        for ($i = 0; $i -lt $frames.Count; $i++) {
            $size = $sizes[$i]
            $writer.Write([byte]$(if ($size -eq 256) { 0 } else { $size }))
            $writer.Write([byte]$(if ($size -eq 256) { 0 } else { $size }))
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$frames[$i].Length)
            $writer.Write([UInt32]$offset)
            $offset += $frames[$i].Length
        }

        foreach ($frame in $frames) {
            $writer.Write($frame)
        }
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}

$candidateCompilers = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)

$compiler = $candidateCompilers | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "csc.exe was not found. Install .NET Framework build tools or build FAA.exe with an equivalent C# compiler."
}

if (-not $iconSource) {
    throw "FAA launcher icon source was not found under resource\logo."
}

try {
    New-IconFromPng -SourcePng $iconSource.FullName -DestinationIco $iconFile

    & $compiler `
        /nologo `
        /target:winexe `
        /platform:anycpu `
        /optimize+ `
        /reference:System.Windows.Forms.dll `
        /win32icon:$iconFile `
        /out:$output `
        $source

    if ($LASTEXITCODE -ne 0) {
        throw "FAA launcher build failed with exit code $LASTEXITCODE."
    }
}
finally {
    if (Test-Path -LiteralPath $iconFile) {
        Remove-Item -LiteralPath $iconFile -Force
    }
}

Write-Host "Built FAA launcher: $output"
Write-Host "Embedded icon: $($iconSource.FullName)"
