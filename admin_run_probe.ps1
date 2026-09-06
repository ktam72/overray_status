$root = "E:\apps\overray-status"
$py = Join-Path $root "testenv\Scripts\python.exe"
$proc = Start-Process -Verb RunAs -FilePath $py -ArgumentList @("admin_probe.py") -WorkingDirectory $root -PassThru
$proc.WaitForExit()
Write-Output "exit=$($proc.ExitCode)"
