$py = "C:\Users\ktam7\OneDrive\ドキュメント\apps\overray-status\testenv\Scripts\python.exe"
Test-Path $py
$proc = Start-Process $py -ArgumentList "overray_status.py" -WorkingDirectory "C:\Users\ktam7\OneDrive\ドキュメント\apps\overray-status" -WindowStyle Hidden -PassThru
"PID: $($proc.Id)"
Stop-Process -Id $proc.Id -Force
