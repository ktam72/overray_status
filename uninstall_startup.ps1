# PC status overlay のログオン自動起動ショートカットを削除する

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "overray-status.lnk"

if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction Stop
    "Removed: $shortcutPath"
} else {
    "Startup shortcut not found: $shortcutPath"
}
