# -*- coding: utf-8 -*-
"""PC status overlay for Windows (top-center frameless translucent bar)."""

import os
import sys
import shutil
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import psutil
import pynvml
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPen, QPainter, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

BAR_W = 240
BAR_H = 52
BAR_MARGIN = 8
FONT_SIZE = 12
SPACING = 6
UPD_INTERVAL_MS = 1000
SMART_REFRESH_TICKS = 3
SMARTCTL_PATHS = [
    r"C:\Program Files\smartmontools\bin\smartctl.exe",
    r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe",
]
HOTKEY_MOD = Qt.AltModifier
HOTKEY_KEY = Qt.Key_Q

CATEGORY_COLORS = {
    "temp": QColor(180, 255, 90),
    "load": QColor(120, 255, 150),
    "power": QColor(255, 170, 60),
    "fan": QColor(90, 220, 255),
    "vram": QColor(190, 120, 255),
    "cpu": QColor(140, 255, 160),
    "mem": QColor(255, 170, 70),
    "net_down": QColor(180, 255, 90),
    "net_up": QColor(110, 190, 255),
    "board": QColor(150, 255, 150),
}
DEFAULT_COLOR = QColor(200, 200, 205)


class GPUReader:
    def __init__(self):
        pynvml.nvmlInit()
        self.count = pynvml.nvmlDeviceGetCount()
        members = [m for m in dir(pynvml) if m.startswith("nvmlDeviceGet")]

    def read(self):
        rows = []
        for i in range(self.count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            r = dict(name=None, temp=None, load=None, power=None, rpm=None, fanspd=None)
            try:
                r["name"] = pynvml.nvmlDeviceGetName(h)
            except Exception:
                pass
            try:
                temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                if temp is not None and temp > 0:
                    r["temp"] = temp
            except Exception:
                pass
            try:
                r["load"] = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            except Exception:
                pass
            try:
                r["power"] = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
            except Exception:
                pass
            try:
                fanspd = pynvml.nvmlDeviceGetFanSpeed(h)
                if fanspd is not None:
                    r["fanspd"] = fanspd
            except Exception:
                pass
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                r["vram_used"] = mem.used
            except Exception:
                pass
            rows.append(r)
        return rows


class CpuReader:
    def __init__(self):
        self._hw = None
        self._board = None
        self._init()

    def _init(self):
        import HardwareMonitor
        import clr

        try:
            clr.AddReference("LibreHardwareMonitorLib")
        except Exception:
            pass
        try:
            import importlib

            lhW = importlib.import_module("LibreHardwareMonitor.Hardware")
            c = lhW.Computer()
        except Exception:
            self._hw = None
            return
        try:
            c.IsCpuEnabled = True
            c.IsMotherboardEnabled = True
            c.IsStorageEnabled = True
            c.Open()
        except Exception:
            self._hw = None
            return
        self._hw = c
        try:
            for h in list(self._hw.Hardware):
                try:
                    if str(h.HardwareType) == "Motherboard" and self._board is None:
                        self._board = str(h.Name)
                except Exception:
                    pass
        except Exception:
            pass

    def _read_drive(self, h):
        name = str(getattr(h, "Name", "?"))
        temp = total = free = used = None
        try:
            sensors = list(h.Sensors)
        except Exception:
            sensors = []
        for s in sensors:
            try:
                st = str(s.SensorType)
                v = s.Value
                nm = str(getattr(s, "Name", ""))
            except Exception:
                continue
            if st == "Temperature" and v is not None:
                if "Warning" in nm or "Critical" in nm:
                    continue
                if temp is None:
                    temp = v
            elif "Total Space" in nm:
                total = v
            elif "Free Space" in nm:
                free = v
            elif "Used Space" in nm:
                used = v
        return {
            "name": name,
            "temp": temp,
            "total": total,
            "free": free,
            "used": used,
            "mounted": True,
        }

    def read(self):
        cpu_name = None
        board = self._board
        temp = load = power = fan = None
        drives = []
        if self._hw is None:
            self._init()
            if self._hw is None:
                return (None, None, None, None, None, None, [])
        try:
            for h in list(self._hw.Hardware):
                try:
                    h.Update()
                except Exception:
                    continue
                ht = str(h.HardwareType)
                if ht == "Motherboard" and board is None:
                    try:
                        board = str(h.Name)
                    except Exception:
                        pass
                if ht == "Cpu" and cpu_name is None:
                    try:
                        cpu_name = str(h.Name)
                    except Exception:
                        pass
                if ht == "Storage":
                    drives.append(self._read_drive(h))
                    continue
                try:
                    sensors = list(h.Sensors)
                except Exception:
                    sensors = []
                for s in sensors:
                    try:
                        st = str(s.SensorType)
                        v = s.Value
                        nm = str(getattr(s, "Name", ""))
                    except Exception:
                        continue
                    if v is None:
                        continue
                    if ht == "Cpu" and st == "Temperature":
                        if "Package" in nm:
                            temp = v
                        elif temp is None or v > temp:
                            temp = v
                    elif ht == "Cpu" and st == "Load" and load is None:
                        load = v
                    elif ht == "Cpu" and st == "Power":
                        if power is None or "Package" in nm:
                            power = v
                    elif ht == "Cpu" and st == "Control" and fan is None:
                        fan = v
        except Exception:
            pass
        return (cpu_name, board, temp, load, power, fan, drives)


def _find_smartctl():
    for p in SMARTCTL_PATHS:
        if os.path.exists(p):
            return p
    exe = shutil.which("smartctl")
    return exe or SMARTCTL_PATHS[0]


class DriveReader:
    def __init__(self):
        from pySMART import device as devmod
        from pySMART.smartctl import Smartctl

        self._devmod = devmod
        self._Smartctl = Smartctl
        self.smartctl_path = _find_smartctl()
        self._rows = []
        self.refresh()

    def _discover_devices(self):
        import subprocess

        try:
            out = subprocess.run(
                [self.smartctl_path, "--scan"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except Exception:
            out = ""
        devs = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("/dev/") and " -d " in line:
                parts = line.split()
                if len(parts) >= 3:
                    devs.append((parts[0], parts[2].strip()))
                elif len(parts) >= 2:
                    devs.append((parts[0], parts[1][2:].strip()))
        if not devs:
            for i in range(26):
                letter = chr(ord("a") + i)
                devs.append((f"/dev/sd{letter}", "auto"))
        return devs

    def _match(self, disks, vols):
        matched = set()
        rows = []
        disks_by_total = sorted(
            [d for d in disks if d["total"] > 0],
            key=lambda d: d["total"],
        )
        for d in disks_by_total:
            best = None
            best_diff = None
            for v in vols:
                if v["vol"] in matched:
                    continue
                diff = abs(d["total"] - v["total"])
                if best is None or diff < best_diff:
                    best = v
                    best_diff = diff
            if best is not None:
                matched.add(best["vol"])
                rows.append(self._row(d, best))
        remaining = [v for v in vols if v["vol"] not in matched]
        remaining.sort(key=lambda v: v["total"], reverse=True)
        ai = 0
        for d in disks:
            if d["total"] > 0 or ai >= len(remaining):
                continue
            v = remaining[ai]
            ai += 1
            if v["vol"] not in matched:
                matched.add(v["vol"])
                rows.append(self._row(d, v))
        for d in disks:
            if any(r["name"] == d["model"] for r in rows):
                continue
            rows.append(self._row(d, None))
        return rows

    def _row(self, d, v):
        return {
            "name": d["model"],
            "temp": d.get("temp"),
            "total": v["total"] if v else d["total"],
            "used": v["used"] if v else None,
        }

    def read(self, refresh=True):
        if not refresh and self._rows:
            return self._rows
        smartctl = self._Smartctl(smartctl_path=self.smartctl_path)
        disks = []
        for path, iface in self._discover_devices():
            try:
                dev = self._devmod.Device(path, interface=iface, smartctl=smartctl)
                disks.append(
                    {
                        "model": dev.model,
                        "temp": dev.temperature,
                        "total": dev.size,
                    }
                )
            except Exception:
                continue
        vols = []
        for part in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(part.mountpoint)
                vols.append(
                    {
                        "vol": part.mountpoint.rstrip("\\\\"),
                        "used": u.used,
                        "total": u.total,
                    }
                )
            except Exception:
                continue
        self._rows = self._match(disks, vols)
        return self._rows

    def refresh(self):
        self.read(refresh=True)


class Bar(QWidget):
    def __init__(self):
        super().__init__()
        self.gpu = GPUReader()
        self.cpu = CpuReader()
        self.drives = DriveReader()
        self.net_last_recv = psutil.net_io_counters().bytes_recv
        self.net_last_sent = psutil.net_io_counters().bytes_sent
        self.cpu_last = psutil.cpu_percent(interval=None)

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(BAR_W, BAR_H)

        self._tmp = dict(last=None)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(UPD_INTERVAL_MS)

    def _move_to_top_right(self):
        screen = QGuiApplication.primaryScreen() or QApplication.primaryScreen()
        if screen is None:
            return
        g = screen.geometry()
        cw = self.width()
        x = g.right() - cw - BAR_MARGIN
        if x < g.left():
            x = g.left()
        if x + cw > g.right():
            x = g.right() - cw
        y = g.y() + BAR_MARGIN
        self.move(x, y)

    def _read(self):
        rows = self.gpu.read()
        net = psutil.net_io_counters()
        recv_bps = (net.bytes_recv - self.net_last_recv) * 8
        sent_bps = (net.bytes_sent - self.net_last_sent) * 8
        self.net_last_recv = net.bytes_recv
        self.net_last_sent = net.bytes_sent
        cpu = psutil.cpu_percent(interval=None)
        self.cpu_last = cpu
        mem = psutil.virtual_memory()
        mem_total = mem.total

        cpu_name, board, c_temp, c_load, c_power, c_fan, _ = self.cpu.read()

        self._drive_tick = getattr(self, "_drive_tick", 0)
        refresh = self._drive_tick % SMART_REFRESH_TICKS == 0
        self._drive_tick += 1
        drives = self.drives.read(refresh=refresh)

        lines = []
        for i, r in enumerate(rows):
            label = r["name"] or ("GPU" + str(i))
            lines.append(
                [
                    (f"GPU{i}: ", None),
                    (f"{label} ", None),
                ]
            )
            toks = []
            if r["load"] is not None:
                toks.append((f"LOAD{r['load']:.1f}% ", "load"))
            if r["power"] is not None:
                toks.append((f"PWR{r['power']:.1f}W ", "power"))
            if r["fanspd"] is not None:
                toks.append((f"FAN{r['fanspd']}% ", "fan"))
            if r["temp"] is not None:
                toks.append((f"TEMP{r['temp']}\u00b0C ", "temp"))
            if r.get("vram_used") is not None:
                toks.append((f"VRAM{r['vram_used'] / 1024 / 1024:.0f}MB ", "vram"))
            lines.append(toks)

        lines.append(
            [
                ("CPU: ", None),
                (f"{cpu_name} ", None),
            ]
        )
        cpu_toks = []
        if c_load is not None:
            cpu_toks.append((f"LOAD{c_load:.1f}% ", "load"))
        if c_power is not None and c_power > 0:
            cpu_toks.append((f"PWR{c_power:.1f}W ", "power"))
        lines.append(cpu_toks)

        if drives:
            for d in drives:
                lines.append(
                    [
                        (f"DRIVE: ", None),
                        (f"{d['name']} ", None),
                    ]
                )
                toks = []
                used = d.get("used")
                total = d.get("total")
                if used is not None and total is not None:
                    toks.append(
                        (f"Used{used / 1024**3:.0f}G/{total / 1024**3:.0f}G ", "mem")
                    )
                elif total is not None:
                    toks.append((f"{total / 1024**3:.0f}G ", "mem"))
                temp = d.get("temp")
                if temp is not None:
                    toks.append((f"{temp:.0f}\u00b0C ", "temp"))
                lines.append(toks)

        lines.append([("MEMORY: ", None)])
        lines.append(
            [
                (f"{mem.used / 1024**3:.0f}GB／{mem_total / 1024**3:.0f}GB ", "mem"),
            ]
        )

        lines.append([("Network Speed: ", None)])
        lines.append(
            [
                (f"UP {sent_bps / 1e6:.1f}Mbps↑ ", "net_up"),
                (f"DOWN {recv_bps / 1e6:.1f}Mbps↓ ", "net_down"),
            ]
        )

        if board:
            pass

        return lines

    def _tick(self):
        try:
            self._items = self._read()
        except Exception:
            self._items = []
        self._layout_size()
        self.update()

    def _layout_size(self):
        font = self.font()
        font.setPixelSize(FONT_SIZE)
        font.setBold(True)
        fm = QFontMetrics(font)
        lines = getattr(self, "_items", [])
        line_height = FONT_SIZE + 6

        def line_w(line):
            return sum(fm.horizontalAdvance(t) for t, c in line)

        max_w = max((line_w(line) for line in lines), default=100)
        w = max_w + BAR_MARGIN * 2
        h = len(lines) * line_height + BAR_MARGIN * 2
        if w < 80:
            w = 80
        self._content_width = w
        self._content_height = h
        self.resize(w, h)
        self.adjustSize()
        self._content_width = self.width()
        self._move_to_top_right()

    def paintEvent(self, _e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(self.rect(), QColor(0, 0, 0, 0))
            lines = getattr(self, "_items", [])
            line_height = FONT_SIZE + 6
            total_text_height = len(lines) * line_height
            ch = getattr(self, "_content_height", total_text_height + BAR_MARGIN * 2)
            bar = QRect(0, 0, self.width(), ch)
            bar = bar.adjusted(BAR_MARGIN, 0, -BAR_MARGIN, -BAR_MARGIN)
            p.setPen(Qt.NoPen)
            p.fillRect(bar, QColor(20, 20, 24, 80))

            font = self.font()
            font.setPixelSize(FONT_SIZE)
            p.setFont(font)
            fm = QFontMetrics(font)

            y0 = bar.top() + line_height
            bold_font = QFont(font)
            bold_font.setBold(True)
            bfm = QFontMetrics(bold_font)
            cached_category = None
            cached_category_pen = None
            for line in lines:
                total_label_w = 0
                for text, category in line:
                    if category is None:
                        total_label_w += bfm.horizontalAdvance(text)
                x_l = bar.right() - total_label_w
                for text, category in line:
                    if category is None:
                        p.setPen(QColor(255, 255, 255))
                        p.setFont(bold_font)
                        w = bfm.horizontalAdvance(text)
                        p.drawText(x_l, y0, text)
                        x_l += w
                x_r = bar.right()
                for text, category in line:
                    if category is not None:
                        if category != cached_category:
                            cached_category = category
                            cached_category_pen = CATEGORY_COLORS.get(
                                category, DEFAULT_COLOR
                            )
                        p.setPen(cached_category_pen)
                        w = fm.horizontalAdvance(text)
                        x_r -= w
                        p.setFont(font)
                        p.drawText(x_r, y0, text)
                y0 += line_height
        finally:
            p.end()

    def keyPressEvent(self, e):
        if e.modifiers() == HOTKEY_MOD and e.key() == HOTKEY_KEY:
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


def main(argv):
    pynvml.nvmlInit()
    app = QApplication(argv)
    w = Bar()
    w.show()
    QApplication.processEvents()
    w._layout_size()
    QApplication.processEvents()
    try:
        (
            _cpu_name,
            _board,
            c_temp,
            c_load,
            c_power,
            c_fan,
            _drives,
        ) = w.cpu.read()
    except Exception:
        c_temp = c_load = c_power = c_fan = None
    drives = []
    try:
        drives = w.drives.read(refresh=True)
    except Exception:
        drives = []
    drives_out = [
        (d["name"], d["temp"], round(d["total"] / 1024**3), round(d["used"] / 1024**3))
        for d in drives
    ]
    sys.stderr.write(
        f"DEBUG geo={w.geometry()} visible={w.isVisible()}\n"
        f"DEBUG cpu_temp={c_temp} cpu_load={c_load} cpu_power={c_power} c_fan={c_fan}\n"
        f"DEBUG drives={drives_out}\n"
    )
    sys.stderr.flush()
    sys.exit(app.exec())


if __name__ == "__main__":
    import sys

    main(sys.argv)
