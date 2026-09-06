$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$py = Join-Path $root "testenv\Scripts\python.exe"
$outLog = Join-Path $root "admin_smart_out.log"
$errLog = Join-Path $root "admin_smart_err.log"

$script = @'
import os, sys
os.chdir(r"E:\apps\overray-status")
sys.path.insert(0, r"E:\apps\overray-status")
from overray_status import DriveReader, _find_smartctl
print("smartctl:", _find_smartctl())
print("cwd:", os.getcwd())
print("=== admin DriveReader.read() ===")
rows = DriveReader().read(refresh=True)
for r in rows:
    print("DRIVE:", r.get("letter"), r.get("name"), "| used", r.get("used"), "total", r.get("total"), "| temp", r.get("temp"), "| model", r.get("model"))
print("=== raw smartctl -a on /dev/sda (ata) ===")
import shutil, subprocess
sc = shutil.which("smartctl")
out = subprocess.run([sc, "-a", "-d", "ata", "/dev/sda"], capture_output=True, text=True)
print(out.stdout)
print("STDERR:", out.stderr)
print("=== raw smartctl -a on /dev/sdc (nvme) ===")
out2 = subprocess.run([sc, "-a", "/dev/sdc"], capture_output=True, text=True)
print(out2.stdout)
'@

$argList = @("-c", $script)
$proc = Start-Process -Verb RunAs -FilePath $py -ArgumentList $argList -PassThru `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$proc.WaitForExit()
Write-Output "exit=$($proc.ExitCode)"
