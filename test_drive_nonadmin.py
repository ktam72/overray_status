import os, sys

os.chdir(r"E:\apps\overray-status")
sys.path.insert(0, r"E:\apps\overray-status")
from overray_status import DriveReader

print("=== non-admin DriveReader.read() ===")
rows = DriveReader().read(refresh=True)
for r in rows:
    print(
        "DRIVE:",
        r.get("letter"),
        r.get("name"),
        "| temp",
        r.get("temp"),
        "| used",
        r.get("used"),
        "total",
        r.get("total"),
    )
