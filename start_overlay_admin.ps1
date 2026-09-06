# PC status overlay をAdministrator権限で起動する
# 初回はUACダイアログが表示されます。「はい」を選択してください

$dir = $PSScriptRoot
$py = Join-Path $dir "testenv\Scripts\python.exe"
Start-Process $py -ArgumentList "overray_status.py" -WorkingDirectory $dir -Verb RunAs -WindowStyle Hidden