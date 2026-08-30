# PC status overlay をバックグラウンドで起動する

$pidFile = Join-Path $PSScriptRoot "overray.pid"

if (Test-Path $pidFile) {
    $oldId = Get-Content $pidFile
    try {
        Stop-Process -Id $oldId -Force -ErrorAction Stop
    }
    catch {
        # not running
    }
}

Start-Sleep -Milliseconds 500

$py = Join-Path $PSScriptRoot "testenv\Scripts\python.exe"
$proc = Start-Process $py -ArgumentList "overray_status.py" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$proc.Id | Set-Content $pidFile

Start-Sleep -Seconds 8
Get-Process python -ErrorAction SilentlyContinue |
    Select-Object Id, StartTime |
    Format-Table -AutoSize
