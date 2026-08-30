# -*- coding: utf-8 -*-
"""PC status overlay for Windows (top-center frameless translucent bar)."""

import sys
import time
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
HOTKEY_MOD = Qt.AltModifier
HOTKEY_KEY = Qt.Key_Q

CATEGORY_COLORS = {
    "temp": QColor(180, 255, 90),
    "load": QColor(120, 255, 150),
    "power": QColor(255, 170, 60),
    "fan": QColor(90, 220, 255),
    "bandwidth": QColor(120, 200, 255),
    "pcie": QColor(200, 220, 90),
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

        def find(suffix):
            matches = [m for m in members if m.endswith(suffix)]
            if not matches:
                raise AttributeError("pynvml: no function ending with " + suffix)
            for m in sorted(matches, reverse=True):
                if not m.startswith("nvmlDeviceGetGpu"):
                    return getattr(pynvml, m)
            return getattr(pynvml, matches[0])

        self._throughput = find("Throughput")
        self._link_max_speed = find("LinkMaxSpeed")
        self._max_gen = find("LinkGeneration")
        self._max_width = find("LinkWidth")
        self._last_total = {}
        self._last_ts = {}
        self._gt_by_maxspeed = {0: 2.5, 1: 5, 2: 8, 3: 16, 4: 16, 5: 32, 6: 64, 7: 128}

    def _bandwidth_pcie(self, i, h):
        try:
            total = self._throughput(h, pynvml.NVML_PCIE_UTIL_TX_BYTES) + self._throughput(h, pynvml.NVML_PCIE_UTIL_RX_BYTES)
        except Exception:
            return (None, None)
        now = time.time()
        last = self._last_total.get(i)
        last_ts = self._last_ts.get(i)
        self._last_total[i] = total
        self._last_ts[i] = now
        if last is None or last_ts is None or now - last_ts <= 0:
            return (None, None)
        dt = now - last_ts
        delta_mb = total - last
        if delta_mb < 0:
            delta_mb = 0
        gbs = delta_mb / dt / 1000.0
        try:
            maxspeed = self._link_max_speed(h)
            gen = self._max_gen(h)
            width = self._max_width(h)
        except Exception:
            return (gbs, None)
        gt = self._gt_by_maxspeed.get(maxspeed, 16)
        theory = 2.0 * gen * gt * width / 8.0
        if theory <= 0:
            return (gbs, None)
        pcie_pct = gbs / theory * 100.0
        return (gbs, pcie_pct)

    def read(self):
        rows = []
        for i in range(self.count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            r = dict(name=None, temp=None, load=None, power=None, rpm=None, fanspd=None, bandwidth=None, pcie=None)
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
            try:
                bw, pcie = self._bandwidth_pcie(i, h)
                r["bandwidth"] = bw
                r["pcie"] = pcie
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
            clr.AddReference('LibreHardwareMonitorLib')
        except Exception:
            pass
        try:
            import importlib
            lhW = importlib.import_module('LibreHardwareMonitor.Hardware')
            c = lhW.Computer()
        except Exception:
            self._hw = None
            return
        try:
            c.IsCpuEnabled = True
            c.IsMotherboardEnabled = True
            c.Open()
        except Exception:
            self._hw = None
            return
        self._hw = c
        try:
            for h in list(self._hw.Hardware):
                try:
                    if str(h.HardwareType) == 'Motherboard' and self._board is None:
                        self._board = str(h.Name)
                except Exception:
                    pass
        except Exception:
            pass

    def read(self):
        cpu_name = None
        board = self._board
        temp = load = power = fan = None
        if self._hw is None:
            self._init()
            if self._hw is None:
                return (None, None, None, None, None, None)
        try:
            for h in list(self._hw.Hardware):
                try:
                    h.Update()
                except Exception:
                    continue
                ht = str(h.HardwareType)
                if ht == 'Motherboard' and board is None:
                    try:
                        board = str(h.Name)
                    except Exception:
                        pass
                if ht == 'Cpu' and cpu_name is None:
                    try:
                        cpu_name = str(h.Name)
                    except Exception:
                        pass
                try:
                    sensors = list(h.Sensors)
                except Exception:
                    sensors = []
                for s in sensors:
                    try:
                        st = str(s.SensorType)
                        v = s.Value
                    except Exception:
                        continue
                    if v is None:
                        continue
                    if ht == 'Cpu' and st == 'Temperature':
                        if temp is None or v > temp:
                            temp = v
                    elif ht == 'Cpu' and st == 'Load' and load is None:
                        load = v
                    elif ht == 'Cpu' and st == 'Power' and power is None:
                        power = v
                    elif ht == 'Cpu' and st == 'Control' and fan is None:
                        fan = v
        except Exception:
            pass
        return (cpu_name, board, temp, load, power, fan)


class Bar(QWidget):
    def __init__(self):
        super().__init__()
        self.gpu = GPUReader()
        self.cpu = CpuReader()
        self.net_last_recv = psutil.net_io_counters().bytes_recv
        self.net_last_sent = psutil.net_io_counters().bytes_sent
        self.cpu_last = psutil.cpu_percent(interval=None)

        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
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

        cpu_name, board, c_temp, c_load, c_power, c_fan = self.cpu.read()

        lines = []
        for i, r in enumerate(rows):
            label = r["name"] or ("GPU" + str(i))
            lines.append([
                (f"GPU{i}: ", None),
                (f"{label} ", None),
            ])
            toks = []
            if r["load"] is not None:
                toks.append((f"LOAD{r['load']}% ", "load"))
            if r["power"] is not None:
                toks.append((f"PWR{r['power']:.1f}W ", "power"))
            if r["fanspd"] is not None:
                toks.append((f"FAN{r['fanspd']}% ", "fan"))
            if r["temp"] is not None:
                toks.append((f"TEMP{r['temp']}\u00b0C ", "temp"))
            if r.get("vram_used") is not None:
                toks.append((f"VRAM{r['vram_used'] / 1024 / 1024:.0f}MB ", "vram"))
            if r.get("bandwidth") is not None:
                toks.append((f"BW{r['bandwidth']:.1f}GB/s ", "bandwidth"))
            if r.get("pcie") is not None:
                toks.append((f"PCIE{r['pcie']:.0f}% ", "pcie"))
            lines.append(toks)

        lines.append([
            ("CPU: ", None),
            (f"{cpu_name} ", None),
        ])
        cpu_toks = []
        if c_load is not None:
            cpu_toks.append((f"LOAD{c_load:.0f}% ", "load"))
        if c_power is not None:
            cpu_toks.append((f"PWR{c_power:.1f}W ", "power"))
        lines.append(cpu_toks)

        lines.append([("MEMORY: ", None)])
        lines.append([
            (f"{mem.used / 1024 ** 3:.0f}GB／{mem_total / 1024 ** 3:.0f}GB ", "mem"),
        ])

        lines.append([("Network Speed: ", None)])
        lines.append([
            (f"UP {sent_bps/1e6:.1f}Mbps↑ ", "net_up"),
            (f"DOWN {recv_bps/1e6:.1f}Mbps↓ ", "net_down"),
        ])

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
                            cached_category_pen = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
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
    sys.stderr.write(f"DEBUG geo={w.geometry()} visible={w.isVisible()}\n")
    sys.stderr.flush()
    sys.exit(app.exec())


if __name__ == "__main__":
    import sys

    main(sys.argv)
