# Build the Windows program into dist\ :
#   PuckPeakLegacyUpdater.exe           the window (double-click; with arguments it is the command line, as
#                                       `python -m legacy_roster`); its pictures (photos, logos, this season's jerseys and
#                                       centre ice) are not inside: it downloads them (legacy_roster\packs.py)
#   SHA256SUMS.txt                      its checksum
# Since 0.85.0 only this one exe (owner): the copy named NHLLegacyRosterUpdater.exe that 0.80.1 / 0.81.0 carried for the
# update check of 0.80.0 and older is gone; those copies get "Open the download page" (app\selfupdate.OLD_EXE_ASSET).
# No command-line exe and no Mac program since 0.80.1 (owner); the Linux program: packaging/build.sh.
#
# Uses its own virtual environment (.venv) so nothing is installed into your Python.
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Sign      # also sign the exe with a certificate of your own:
#       $env:SIGN_PFX = path to the .pfx, $env:SIGN_PFX_PASSWORD, or $env:SIGN_THUMBPRINT of one in the certificate store;
#       skipped with a line when none is set. The signed releases come from GitHub (.github\workflows\windows-release.yml
#       through SignPath; docs\MAINTAINING.md "Signing"), not from here.
param([switch]$Sign)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$running = Get-Process -Name PuckPeakLegacyUpdater, NHLLegacyRosterUpdater, NHLLegacyRosterUpdater-Photos, NHLLegacyRosterUpdater-cli -ErrorAction SilentlyContinue
if ($running) { throw "Close PuckPeakLegacyUpdater first: Windows does not let a running program be replaced." }

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    python -m venv .venv
}
# pywebview shows the window (the page in legacy_roster\web, drawn by Windows' Edge WebView2); customtkinter draws the
# classic window (kept for 0.10.x as the fallback); Pillow makes the photos and logos (and the brand assets, make_assets.py);
# certifi brings Mozilla's list of trusted certificates (Windows' own list can lack the one a site uses)
& $py -m pip install --quiet --upgrade pip pyinstaller "pywebview==6.2.1" "customtkinter>=6.0,<7" "pillow>=11.2" certifi
if ($LASTEXITCODE -ne 0) { throw "could not install PyInstaller, pywebview, customtkinter, Pillow and certifi" }

$version = (& $py -c "import legacy_roster; print(legacy_roster.__version__)").Trim()
$cacert = (& $py -c "import certifi; print(certifi.where())").Trim()
$data = Join-Path $root 'legacy_roster\data'
$web = Join-Path $root 'legacy_roster\web'
$common = @(
    '--noconfirm', '--clean', '--onefile',
    '--add-data', "$data;legacy_roster\data",
    '--add-data', "$cacert;legacy_roster\data",           # datasource.CA_BUNDLE
    '--icon', (Join-Path $data 'app.ico'),
    # photos and logos: Pillow finds its file readers by name at run time, so name the ones used
    '--hidden-import', 'PIL.PngImagePlugin', '--hidden-import', 'PIL.JpegImagePlugin',
    '--hidden-import', 'PIL.WebPImagePlugin', '--hidden-import', 'PIL.GifImagePlugin',
    '--hidden-import', 'PIL.DdsImagePlugin', '--hidden-import', 'legacy_roster.art.images', '--hidden-import', 'legacy_roster.art.looks', '--hidden-import', 'legacy_roster.art.lookpack',
    '--distpath', 'dist', '--workpath', 'build', '--specpath', 'build'
)

# no pack goes inside (0.32.0): the program downloads its pictures, and nothing names where the game's content came
# from (tools\clean_check.py)
New-Item -ItemType Directory -Force (Join-Path $root 'build') | Out-Null
$zips = Get-ChildItem $data -Filter '*.zip*' -ErrorAction SilentlyContinue
if ($zips) { throw "legacy_roster\data holds $($zips.Name -join ', '): packs never go inside the program (private\packs)." }
& $py tools\clean_check.py
if ($LASTEXITCODE -ne 0) { throw "tools\clean_check.py found words that must not ship (see above)" }
& $py packaging\make_manifest.py      # the page's file list: the window checks it at start (window\main.missing_files)
if ($LASTEXITCODE -ne 0) { throw "could not list the page's files" }
foreach ($old in 'NHLLegacyRosterUpdater-Photos.exe', 'NHLLegacyRosterUpdater-cli.exe', 'NHLLegacyRosterUpdater.exe') {
    $path = Join-Path $root "dist\$old"         # programs of earlier builds
    if (Test-Path $path) { Remove-Item -Force $path }
}
& $py -m PyInstaller @common --windowed --add-data "$web;legacy_roster\web" `
    --collect-all webview --collect-all pythonnet --collect-all clr_loader --collect-all customtkinter `
    --name PuckPeakLegacyUpdater packaging\launcher.py
if ($LASTEXITCODE -ne 0) { throw "building the window program failed" }

if ($Sign) {
    $tool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
    $how = if ($env:SIGN_PFX) { @('/f', $env:SIGN_PFX, '/p', $env:SIGN_PFX_PASSWORD) }
           elseif ($env:SIGN_THUMBPRINT) { @('/sha1', $env:SIGN_THUMBPRINT) } else { $null }
    if (-not $tool -or -not $how) {
        Write-Host "Not signed: signtool.exe (Windows SDK) or a certificate (SIGN_PFX / SIGN_THUMBPRINT) is missing."
    } else {
        & $tool.FullName sign @how /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /d "Puck Peak Legacy Updater" dist\PuckPeakLegacyUpdater.exe
        if ($LASTEXITCODE -ne 0) { throw "signing the program failed" }
    }
}

# checksums of the programs, to attach to the release (the update check compares the download with them)
Get-ChildItem dist\*.exe | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } |
    Set-Content -Encoding ascii dist\SHA256SUMS.txt

Get-ChildItem dist\*.exe | ForEach-Object { "{0}  {1:N1} MB  (version {2})" -f $_.Name, ($_.Length / 1MB), $version }
