# PC status overlay を終了する

$pidFile = Join-Path $PSScriptRoot "overray.pid"

if (Test-Path $pidFile) {
    $id = Get-Content $pidFile
    try {
        $p = Get-Process -Id $id -ErrorAction Stop
        $p | Stop-Process -Force -ErrorAction Stop
        "Stopped PID: $id"
    }
    catch {
        "PID $id not running"
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
} else {
    "No PID file"
}
