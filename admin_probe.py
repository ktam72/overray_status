import os, sys, shutil, subprocess
import traceback


def find_smartctl():
    for c in [
        r"C:\Program Files\smartmontools\bin\smartctl.exe",
        r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe",
        shutil.which("smartctl"),
    ]:
        if c and os.path.exists(c):
            return c
    return None


def main():
    os.chdir(r"E:\apps\overray-status")
    sys.path.insert(0, r"E:\apps\overray-status")
    from overray_status import DriveReader, _find_smartctl

    out = []
    out.append("smartctl: " + str(_find_smartctl()))
    out.append("sc_abs: " + str(find_smartctl()))
    out.append("cwd: " + os.getcwd())
    out.append("=== admin DriveReader.read() ===")
    rows = DriveReader().read(refresh=True)
    for r in rows:
        out.append(
            "DRIVE: "
            + str(r.get("letter"))
            + " "
            + str(r.get("name"))
            + " | used "
            + str(r.get("used"))
            + " total "
            + str(r.get("total"))
            + " | temp "
            + str(r.get("temp"))
            + " | model "
            + str(r.get("model"))
        )
    sc = find_smartctl()
    out.append("=== raw smartctl -a on /dev/sda (ata, HDD) ===")
    r1 = subprocess.run(
        [sc, "-a", "-d", "ata", "/dev/sda"], capture_output=True, text=True
    )
    out.append(r1.stdout)
    out.append("STDERR: " + r1.stderr)
    out.append("=== raw smartctl -a on /dev/sdc (nvme) ===")
    r2 = subprocess.run([sc, "-a", "/dev/sdc"], capture_output=True, text=True)
    out.append(r2.stdout)
    with open("admin_smart_probe.log", "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open("admin_smart_probe_ERR.log", "w", encoding="utf-8") as f:
            f.write("ERROR: " + str(e) + "\n" + traceback.format_exc())
        raise
