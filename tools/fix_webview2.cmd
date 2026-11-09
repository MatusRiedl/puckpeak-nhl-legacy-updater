<# : batch part (PowerShell reads this line as the start of a comment)
@echo off
set "FIX_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([IO.File]::ReadAllText($env:FIX_SELF))"
exit /b
#>
# Puck Peak Legacy Updater: check and repair Microsoft's WebView2 Runtime (the part of Windows that draws the window).
# Double-click it. It asks for administrator rights, checks WebView2, asks before changing anything, reinstalls it,
# and writes webview2-report.txt on the Desktop. FIX_DRYRUN=1: check and report only, change nothing.

$ErrorActionPreference = 'Continue'
$dry = $env:FIX_DRYRUN -eq '1'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin -and -not $dry) {
    Write-Host "Asking for administrator rights..."
    Start-Process -FilePath $env:FIX_SELF -Verb RunAs
    exit
}

$desktop = [Environment]::GetFolderPath('Desktop')
$report = if ($env:FIX_REPORT) { $env:FIX_REPORT } else { Join-Path $desktop 'webview2-report.txt' }
$lines = New-Object System.Collections.Generic.List[string]
function Say($text) { Write-Host $text; $lines.Add($text) }

$client = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$keys = @("HKLM:\SOFTWARE\WOW6432Node\$client", "HKLM:\SOFTWARE\$client", "HKCU:\SOFTWARE\$client")
$roots = @("${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application", "$env:ProgramFiles\Microsoft\EdgeWebView\Application",
           "$env:LOCALAPPDATA\Microsoft\EdgeWebView\Application")

function Look {
    $found = @()
    foreach ($key in $keys) {
        $pv = (Get-ItemProperty -Path $key -Name pv -ErrorAction SilentlyContinue).pv
        if ($pv) { Say "  registry $key = $pv"; $found += [pscustomobject]@{Key = $key; Version = $pv} }
    }
    if (-not $found) { Say "  registry: no WebView2 entry" }
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $names = (Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', '
            Say "  folder $root : $names"
        }
    }
    $broken = $false
    foreach ($entry in $found) {
        $exe = $roots | ForEach-Object { Join-Path $_ "$($entry.Version)\msedgewebview2.exe" } | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($exe) { Say "  $($entry.Version): msedgewebview2.exe is there ($exe)" }
        else { Say "  $($entry.Version): msedgewebview2.exe is MISSING"; $broken = $true }
    }
    return [pscustomobject]@{Entries = $found; Broken = $broken}
}

Say "WebView2 check, $(Get-Date -Format 'yyyy-MM-dd HH:mm'), Windows $([Environment]::OSVersion.Version)$(if ($dry) {', dry run'})"
Say "Before:"
$state = Look
try {
    $threats = Get-MpThreatDetection -ErrorAction Stop | Where-Object { ($_.Resources -join ' ') -match 'EdgeWebView|msedgewebview2' }
    if ($threats) { Say "  Windows Security quarantined WebView2 files: $(($threats.Resources | Select-Object -First 3) -join '; ')" }
    else { Say "  Windows Security: nothing about WebView2 in quarantine" }
} catch { Say "  Windows Security: could not be asked (another antivirus?)" }

if ($dry) { Say "Dry run: nothing changed." }
else {
    if ($state.Broken -or -not $state.Entries) { $q = "WebView2 is damaged. Repair it now? (Y/N)" }
    else { $q = "WebView2 looks complete. Reinstall it anyway? (Y/N)" }
    $answer = Read-Host $q
    if ($answer -notmatch '^[YySs]') { Say "Not repaired (answer: $answer)." }
    else {
        $setup = Join-Path $env:TEMP 'MicrosoftEdgeWebview2Setup.exe'
        Say "Downloading Microsoft's installer..."
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $setup -UseBasicParsing
        } catch { Say "  Download failed: $($_.Exception.Message)" }
        if (-not (Test-Path $setup)) { Say "Stopped before changing anything: no installer." }
        else {
            $n = 0
            foreach ($entry in $state.Entries) {
                $system = $entry.Key -like 'HKLM*'
                $old = $roots | ForEach-Object { Join-Path $_ "$($entry.Version)\Installer\setup.exe" } | Where-Object { Test-Path $_ } | Select-Object -First 1
                if ($old) {
                    Say "Removing the damaged copy with its own uninstaller..."
                    $how = '--uninstall --msedgewebview --verbose-logging --force-uninstall' + $(if ($system) { ' --system-level' })
                    Start-Process -FilePath $old -ArgumentList $how -Wait
                }
                if (Test-Path $entry.Key) {
                    $n += 1
                    $backup = Join-Path $desktop "webview2-registry-backup-$n.reg"
                    $regPath = $entry.Key -replace '^HKLM:', 'HKLM' -replace '^HKCU:', 'HKCU'
                    & reg.exe export $regPath $backup /y | Out-Null
                    Remove-Item -Path $entry.Key -Recurse -ErrorAction SilentlyContinue
                    Say "  Removed the left-over registry entry $($entry.Key) (backup: $backup)"
                }
            }
            Say "Installing WebView2 (this can take a few minutes)..."
            $p = Start-Process -FilePath $setup -ArgumentList '/silent /install' -Wait -PassThru
            Say "  Installer finished with code $($p.ExitCode)"
            $waited = 0
            while ($waited -lt 120 -and -not ($roots | ForEach-Object { Get-ChildItem $_ -Recurse -Filter msedgewebview2.exe -ErrorAction SilentlyContinue })) {
                Start-Sleep -Seconds 5; $waited += 5
            }
            Say "  Waited $waited s for the files"
        }
    }
    Say "After:"
    $after = Look
    if ($after.Entries -and -not $after.Broken) { Say "RESULT: WebView2 is complete. Restart the PC, then start the updater." }
    else { Say "RESULT: WebView2 is still not complete. Send this report." }
}

$log = Join-Path $env:LOCALAPPDATA 'NHLLegacyRosterUpdater\logs\start.log'
if (Test-Path $log) { $lines.Add(''); $lines.Add('Last lines of start.log:'); Get-Content $log -Tail 15 | ForEach-Object { $lines.Add($_) } }
$lines | Set-Content -Path $report -Encoding UTF8
Write-Host ""
Write-Host "Report saved: $report  (send it to us)"
if (-not $dry) { Read-Host "Press Enter to close" | Out-Null }
