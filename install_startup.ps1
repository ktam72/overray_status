# PC status overlay をログオン時に自動起動するためのショートカットを配置する

$scriptDir = $PSScriptRoot
$startOverlay = Join-Path $scriptDir "start_overlay.ps1"

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "overray-status.lnk"

$existing = Get-Item -LiteralPath $shortcutPath -ErrorAction SilentlyContinue
if ($existing) {
    Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction Stop
}

$shell = New-Object -ComObject WScript.Shell
try {
    $lnk = $shell.CreateShortcut($shortcutPath)
    $lnk.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk.Arguments = "-NonInteractive -ExecutionPolicy Bypass -File ""$startOverlay"""
    $lnk.WorkingDirectory = $scriptDir
    $lnk.WindowStyle = 3
    $lnk.Description = "PC status overlay (overray-status) auto start at logon"
    $lnk.Save()
}
finally {
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
}

"Installed: $shortcutPath"
"Target:   $($lnk.TargetPath)"
"Args:     $($lnk.Arguments)"
"Folder:   $startupFolder"
