# monitor_nvda_log.ps1
# Monitors the NVDA log in real-time, highlighting ERRORs and WARNINGs.
# Usage: .\monitor_nvda_log.ps1 [-Filter <regex>]
param(
    [string]$LogPath = "$env:TEMP\nvda.log",
    [string]$Filter  = ""
)

if (-not (Test-Path $LogPath)) {
    Write-Host "Log not found: $LogPath" -ForegroundColor Red
    Write-Host "Make sure NVDA is running." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== NVDA Log Monitor ===" -ForegroundColor Cyan
Write-Host "File : $LogPath" -ForegroundColor Cyan
Write-Host "Filter: $(if ($Filter) { $Filter } else { '(all lines)' })" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Cyan

$stats = @{ ERROR = 0; WARNING = 0; INFO = 0; DEBUG = 0; Other = 0 }
$lastSize = (Get-Item $LogPath).Length

while ($true) {
    Start-Sleep -Milliseconds 500

    if (-not (Test-Path $LogPath)) { continue }

    $currentSize = (Get-Item $LogPath).Length

    if ($currentSize -lt $lastSize) {
        # Log was rotated / truncated (NVDA restarted)
        Write-Host "`n[Log reset detected — NVDA restarted]`n" -ForegroundColor Magenta
        $lastSize = 0
    }

    if ($currentSize -le $lastSize) { continue }

    $stream = [System.IO.File]::Open($LogPath, 'Open', 'Read', 'ReadWrite')
    $stream.Seek($lastSize, 'Begin') | Out-Null
    $reader = New-Object System.IO.StreamReader($stream)
    $newContent = $reader.ReadToEnd()
    $reader.Close()
    $stream.Close()
    $lastSize = $currentSize

    $lines = $newContent -split "`r?`n"
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($Filter -and $line -notmatch $Filter) { continue }

        if ($line -match '^ERROR') {
            Write-Host $line -ForegroundColor Red
            $stats.ERROR++
        } elseif ($line -match '^WARNING') {
            Write-Host $line -ForegroundColor Yellow
            $stats.WARNING++
        } elseif ($line -match '^INFO') {
            Write-Host $line -ForegroundColor Green
            $stats.INFO++
        } elseif ($line -match '^DEBUG') {
            Write-Host $line -ForegroundColor Gray
            $stats.DEBUG++
        } elseif ($line -match '^\s+' -or $line -match '^Traceback|^\s+File |^\s+in ') {
            # Continuation / traceback lines — inherit last level color (print plain)
            Write-Host $line -ForegroundColor DarkRed
        } else {
            Write-Host $line
            $stats.Other++
        }
    }
}
