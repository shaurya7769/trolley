#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rail Track Geometry Inspection System
Target  : BeagleBone Black Industrial | Ubuntu | 1024x600 HDMI/Touch
Stack   : PyQt5 | Python 3.5+
Version : 5.0.0 - ISO light-theme UI + full BBB hardware backend

Sensor map:
  Rotary Encoder   -> GPIO sysfs CLK/DT/SW (P8.11/P8.12/P8.14)
  Gauge Pot(TRS100)-> ADC  -> /sys/bus/iio/devices/iio:device0/in_voltage0_raw
  Inclinometer     -> ADC  -> /sys/bus/iio/devices/iio:device0/in_voltage1_raw
  GNSS             -> UART -> /dev/ttyS4      (u-blox NEO-M8P-2)
  LTE              -> ETH  -> eth1            (cdc_ether)
  Display          -> HDMI -> omapdrm / xrandr
"""

import sys, os, json, csv, time, random, subprocess
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QScrollArea,
    QFileDialog, QTextEdit, QSizePolicy, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess, QPoint, QRect, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush, QLinearGradient, QPainterPath,
)

# =============================================================================
#  PALETTE  (ISO light theme from railgui25)
# =============================================================================
BG    = "#ECEFF4"
CARD  = "#FFFFFF"
NEON  = "#1B8A4C"    # Track Gauge green
CYAN  = "#1565C0"    # Cross Level blue
AMBER = "#C06000"    # Twist amber
RED   = "#C62828"    # Alarm red
MAGI  = "#5E35B1"    # Distance violet
HEADER_BG     = "#1E2430"
HEADER_ACCENT = "#1B8A4C"

# light tints
NEON_LT  = "#E6F4EE"
CYAN_LT  = "#E3EEFA"
AMBER_LT = "#FFF3E0"
MAGI_LT  = "#EDE7F6"
RED_LT   = "#FFEBEE"
WARN     = "#E65100"
WARN_LT  = "#FFF3E0"

W, H = 1024, 600

# =============================================================================
#  GLOBAL STYLESHEET
# =============================================================================
SS = """
QWidget {
    background: #ECEFF4;
    color: #1A2332;
    font-family: 'Inter', 'DM Sans', 'Liberation Sans', sans-serif;
}
QDialog { background: #FFFFFF; }
QFrame#Card {
    background: #FFFFFF;
    border: 1px solid #DDE3EA;
    border-left: 4px solid #1B8A4C;
    border-radius: 10px;
}
QFrame#Panel {
    background: #FFFFFF;
    border: 1px solid #DDE3EA;
    border-radius: 8px;
}
QTextEdit {
    background: #FFFFFF;
    border: 1px solid #DDE3EA;
    color: #1A2332;
    font-size: 8pt;
    font-family: 'Roboto Mono', 'Courier New';
}
QScrollBar:vertical          { background: #ECEFF4; width: 8px; }
QScrollBar::handle:vertical  { background: #C8D0DA; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

QPushButton#BG {
    background: #E6F4EE; border: 1.5px solid #1B8A4C;
    border-radius: 6px; color: #1B8A4C;
    font-size: 10pt; font-weight: bold;
}
QPushButton#BG:pressed   { background: #D2EDE0; }
QPushButton#BG:disabled  { background: #F0F0F0; border-color: #C8D0DA; color: #A0AAB8; }

QPushButton#BC {
    background: #FFFFFF; border: 2px solid #1565C0;
    border-radius: 12px; color: #1565C0;
    font-size: 10pt; font-weight: 700;
    padding: 4px 18px; min-height: 34px;
}
QPushButton#BC:hover     { background: #F5FAFF; border-color: #0D4A8A; color: #0D4A8A; }
QPushButton#BC:pressed   { background: #E3EEFA; border-color: #0D4A8A; color: #0D4A8A; }
QPushButton#BC:disabled  { background: #F8FAFB; border-color: #C8D0DA; color: #A0AAB8; }

QPushButton#BA {
    background: #FFF3E0; border: 1.5px solid #C06000;
    border-radius: 6px; color: #C06000;
    font-size: 10pt; font-weight: bold;
}
QPushButton#BA:pressed { background: #FFE4C0; }

QPushButton#BR {
    background: #FFEBEE; border: 1.5px solid #C62828;
    border-radius: 6px; color: #C62828;
    font-size: 10pt; font-weight: bold;
}
QPushButton#BR:pressed { background: #FFD6D6; }

QPushButton#BM {
    background: #EDE7F6; border: 1.5px solid #5E35B1;
    border-radius: 6px; color: #5E35B1;
    font-size: 10pt; font-weight: bold;
}
QPushButton#BM:pressed { background: #DDD5F0; }

QPushButton#BX {
    background: #F8FAFB; border: 1px solid #C8D0DA;
    border-radius: 6px; color: #4A5568;
    font-size: 10pt; font-weight: bold;
}
QPushButton#BX:pressed { background: #ECEFF4; }

QPushButton#NK {
    background: #111; border: 1px solid #2a2a2a;
    border-radius: 8px; color: #DDD;
    font-size: 18pt; font-weight: bold;
}
QPushButton#NK:pressed   { background: #222; border-color: #1565C0; }

QPushButton#NO {
    background: #001520; border: 1px solid #1565C0;
    border-radius: 8px; color: #1565C0;
    font-size: 14pt; font-weight: bold;
}
QPushButton#NO:pressed { background: #002030; }

QPushButton#NOK {
    background: #002800; border: 2px solid #1B8A4C;
    border-radius: 8px; color: #1B8A4C;
    font-size: 14pt; font-weight: bold;
}
QPushButton#NOK:pressed { background: #003d00; }

QPushButton#ND {
    background: #1a0a00; border: 1px solid #C06000;
    border-radius: 8px; color: #C06000;
    font-size: 14pt; font-weight: bold;
}
QPushButton#ND:pressed { background: #260e00; }

QPushButton#CK {
    background: #111; border: 1px solid #2a2a2a;
    border-radius: 5px; color: #aaa;
    font-size: 11pt; font-weight: bold;
}
QPushButton#CK:pressed { background: #222; border-color: #C06000; }

QPushButton#EF {
    background: #F8FAFB; border: 1px solid #C8D0DA;
    border-radius: 6px; color: #1565C0;
    font-size: 12pt; font-family: 'Roboto Mono', 'Courier New';
    text-align: left; padding-left: 12px;
}
QPushButton#EF:pressed { background: #E3EEFA; border-color: #1565C0; }

QPushButton#SB {
    background: #F8FAFB; border: 1px solid #DDE3EA;
    border-radius: 8px; color: #8A94A6;
    font-size: 8pt; font-weight: bold;
    padding: 6px 8px; text-align: left;
}
QPushButton#SB:checked { border-color: #1B8A4C88; color: #1B8A4C; }
"""

# =============================================================================
#  CONFIG
# =============================================================================
CFG_PATH = Path(__file__).parent / "rail_config.json"
_DEF = {
    "csv_dir":   str(Path.home() / "surveys"),
    "hl_sec":    30,
    "server":    "8.8.8.8",
    "lte_iface": "eth1",
    "encoder":   {"scale": 1.0, "ppr": 20, "diam": 62.0, "calibrated": False},
    "adc":       {"zero": 2048, "mpc": 0.0684, "calibrated": False},
    "incl":      {"offset": 0.0, "calibrated": False},
    "gnss":      {"ref_ch": 0.0, "calibrated": False},
}


def load_cfg():
    if CFG_PATH.exists():
        try:
            d = json.loads(CFG_PATH.read_text())
            for k, v in _DEF.items():
                d.setdefault(k, v)
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        d[k].setdefault(kk, vv)
            return d
        except Exception:
            pass
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _DEF.items()}


def save_cfg(cfg):
    try:
        CFG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        print("[CFG] {}".format(e))


# =============================================================================
#  HARDWARE  -- BeagleBone Black, full sensor stack from test.py
# =============================================================================
ADC_PATH   = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"  # AIN0 P9.39
ADC_PATH_1 = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"  # AIN1 P9.40

ENC_CLK_GPIO = 45   # P8.11  GPIO1_13
ENC_DT_GPIO  = 44   # P8.12  GPIO1_12
ENC_SW_GPIO  = 26   # P8.14  GPIO0_26
_GPIO_BASE   = "/sys/class/gpio"

SPI_DEV  = "/dev/spidev1.0"
EQEP_PATH = ("/sys/devices/platform/ocp/48304000.epwmss"
             "/48304180.eqep/counter/count0/count")


def _load_kernel_modules():
    modules = ["ti_am335x_adc", "omap_hsmmc"]
    for mod in modules:
        try:
            subprocess.call(["sudo", "modprobe", mod],
                            stdout=open(os.devnull, "w"),
                            stderr=open(os.devnull, "w"))
        except Exception:
            pass
    uart4_pins = [("P9.11", "uart"), ("P9.13", "uart")]
    for pin, mode in uart4_pins:
        try:
            subprocess.call(["config-pin", pin, mode],
                            stdout=open(os.devnull, "w"),
                            stderr=open(os.devnull, "w"))
        except Exception:
            pass


_load_kernel_modules()
time.sleep(1)

HW_SIM = not os.path.exists(ADC_PATH)


def _gpio_export(num):
    val_path = "{}/gpio{}/value".format(_GPIO_BASE, num)
    if not os.path.exists(val_path):
        try:
            with open("{}/export".format(_GPIO_BASE), "w") as f:
                f.write(str(num))
            with open("{}/gpio{}/direction".format(_GPIO_BASE, num), "w") as f:
                f.write("in")
        except Exception:
            pass


def _gpio_read(num):
    try:
        with open("{}/gpio{}/value".format(_GPIO_BASE, num)) as f:
            return int(f.read().strip())
    except Exception:
        return 1


def _sysfs(path, default="0"):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


# =============================================================================
#  HELPERS
# =============================================================================
def _lbl(text, color="#888", pt=9, bold=False):
    l = QLabel(text)
    w = "bold" if bold else "normal"
    l.setStyleSheet("color:{}; font-size:{}pt; font-weight:{};".format(color, pt, w))
    l.setWordWrap(True)
    return l


def _logbox(h=90):
    t = QTextEdit()
    t.setReadOnly(True)
    t.setFixedHeight(h)
    return t


def _vline():
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setStyleSheet("color:#DDE3EA; max-width:1px;")
    return f


def _btn(label, name, h=48, w=None):
    b = QPushButton(label)
    b.setObjectName(name)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    return b


def _shorten(path, n=34):
    return ("..." + path[-(n - 1):]) if len(path) > n else path


def _run_cmd(cmd, callback, parent):
    proc = QProcess(parent)
    proc.setProcessChannelMode(QProcess.MergedChannels)

    def _done():
        out = proc.readAllStandardOutput().data().decode(errors="replace")
        callback(out)

    proc.finished.connect(_done)
    proc.start("sh", ["-c", cmd])
    return proc


# =============================================================================
#  NUMPAD DIALOG
# =============================================================================
class NumpadDialog(QDialog):
    def __init__(self, title, current_val="0", decimals=1,
                 min_val=None, max_val=None, unit="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setStyleSheet(SS + "QDialog{background:#0e0e0e;}")
        self.setFixedSize(380, 480)

        self._dec  = decimals
        self._min  = min_val
        self._max  = max_val
        self._unit = unit
        self._buf  = str(current_val).strip()
        self._result = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        t = QLabel(title.upper())
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:{}; font-size:11pt; font-weight:bold; letter-spacing:2px;".format(CYAN))
        root.addWidget(t)

        self._disp = QLabel()
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(58)
        self._disp.setStyleSheet(
            "background:#060606; border:1px solid {}55; border-radius:6px;"
            " color:{}; font-size:24pt; font-family:'Courier New';"
            " padding-right:10px; font-weight:bold;".format(CYAN, CYAN))
        root.addWidget(self._disp)

        g = QGridLayout()
        g.setSpacing(6)
        rows = [("7","8","9"), ("4","5","6"), ("1","2","3"), (".","0","BS")]
        for r, trio in enumerate(rows):
            for c, lbl in enumerate(trio):
                if lbl == "BS":
                    b = _btn(lbl, "ND", 64, 86)
                    b.clicked.connect(self._del)
                elif lbl == ".":
                    b = _btn(lbl, "NO", 64, 86)
                    b.clicked.connect(lambda _, ch=lbl: self._press(ch))
                    b.setEnabled(decimals > 0)
                else:
                    b = _btn(lbl, "NK", 64, 86)
                    b.clicked.connect(lambda _, ch=lbl: self._press(ch))
                g.addWidget(b, r, c)

        pm  = _btn("+/-", "NO",  64, 86); pm.clicked.connect(self._sign);   g.addWidget(pm,  4, 0)
        clr = _btn("CLR","NO",   64, 86); clr.clicked.connect(self._clear); g.addWidget(clr, 4, 1)
        ok  = _btn("[OK]","NOK", 64, 86); ok.clicked.connect(self._confirm); g.addWidget(ok,  4, 2)
        root.addLayout(g)

        cnc = _btn("X  CANCEL", "BR", 46)
        cnc.clicked.connect(self.reject)
        root.addWidget(cnc)
        self._refresh()

        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width()  - self.width())  // 2,
                      pg.y() + (pg.height() - self.height()) // 2)

    def _press(self, ch):
        if ch == "." and "." in self._buf:
            return
        if "." in self._buf and ch != ".":
            after_dot = self._buf.split(".")[1]
            if len(after_dot) >= self._dec:
                return
        stripped = self._buf.lstrip("-")
        if stripped in ("0", "") and ch != ".":
            self._buf = ("-" if self._buf.startswith("-") else "") + ch
        else:
            self._buf += ch
        self._refresh()

    def _del(self):
        self._buf = self._buf[:-1] if len(self._buf) > 1 else "0"
        if self._buf == "-":
            self._buf = "0"
        self._refresh()

    def _clear(self):
        self._buf = "0"
        self._refresh()

    def _sign(self):
        if self._buf.startswith("-"):
            self._buf = self._buf[1:]
        elif self._buf not in ("0", ""):
            self._buf = "-" + self._buf
        self._refresh()

    def _refresh(self):
        suf = "  {}".format(self._unit) if self._unit else ""
        self._disp.setText((self._buf or "0") + suf)

    def _confirm(self):
        try:
            v = float(self._buf)
        except ValueError:
            v = 0.0
        if self._min is not None:
            v = max(float(self._min), v)
        if self._max is not None:
            v = min(float(self._max), v)
        self._result = v
        self.accept()

    def get_value(self):
        return self._result


# =============================================================================
#  TEXT PICKER DIALOG
# =============================================================================
class TextPickerDialog(QDialog):
    def __init__(self, title, presets=None, current="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setStyleSheet(SS + "QDialog{background:#0e0e0e;}")
        self.setFixedSize(680, 560)

        self._buf    = current or ""
        self._result = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        hdr = QHBoxLayout()
        t = QLabel(title.upper())
        t.setStyleSheet("color:{}; font-size:11pt; font-weight:bold; letter-spacing:2px;".format(AMBER))
        self._disp = QLabel(self._buf or "--")
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(44)
        self._disp.setMinimumWidth(260)
        self._disp.setStyleSheet(
            "background:#060606; border:1px solid {}55; border-radius:5px;"
            " color:{}; font-size:16pt; font-family:'Courier New';"
            " padding-right:8px; font-weight:bold;".format(AMBER, AMBER))
        hdr.addWidget(t, 0)
        hdr.addStretch()
        hdr.addWidget(self._disp, 1)
        root.addLayout(hdr)

        if presets:
            pg = QGridLayout()
            pg.setSpacing(5)
            per_row = 4
            for i, p in enumerate(presets):
                b = QPushButton(p)
                b.setObjectName("BA")
                b.setFixedHeight(44)
                b.clicked.connect(lambda _, v=p: self._pick(v))
                pg.addWidget(b, i // per_row, i % per_row)
            root.addLayout(pg)

        kb_rows = ["ABCDEFGHIJ", "KLMNOPQRST", "UVWXYZ0123", "456789/-. "]
        for row_str in kb_rows:
            rl = QHBoxLayout()
            rl.setSpacing(3)
            for ch in row_str:
                label = "SPC" if ch == " " else ch
                b = QPushButton(label)
                b.setObjectName("CK")
                b.setFixedSize(58, 42)
                b.clicked.connect(lambda _, c=ch: self._char(c))
                rl.addWidget(b)
            root.addLayout(rl)

        br = QHBoxLayout()
        br.setSpacing(6)
        bs  = _btn("BS  BACK", "ND", 42); bs.clicked.connect(self._bksp)
        clr = _btn("CLR",      "BX", 42); clr.clicked.connect(self._clr)
        br.addWidget(bs, 1)
        br.addWidget(clr, 1)
        root.addLayout(br)

        bot = QHBoxLayout()
        bot.setSpacing(8)
        ok  = _btn("[OK]  CONFIRM", "BG", 46); ok.clicked.connect(self._confirm)
        cnc = _btn("X  CANCEL",    "BR", 46); cnc.clicked.connect(self.reject)
        bot.addWidget(cnc, 1)
        bot.addWidget(ok,  1)
        root.addLayout(bot)

        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width()  - self.width())  // 2,
                      pg.y() + (pg.height() - self.height()) // 2)

    def _pick(self, v):
        self._buf = v
        self._disp.setText(v or "--")

    def _char(self, ch):
        self._buf += ch
        self._disp.setText(self._buf or "--")

    def _bksp(self):
        self._buf = self._buf[:-1]
        self._disp.setText(self._buf or "--")

    def _clr(self):
        self._buf = ""
        self._disp.setText("--")

    def _confirm(self):
        self._result = self._buf
        self.accept()

    def get_value(self):
        return self._result


# =============================================================================
#  TOUCH TEXT FIELD  (from railgui25)
# =============================================================================
class TouchTextField(QPushButton):
    activated = pyqtSignal(object)

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._value = ""
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.activated.emit(self))
        self._refresh()

    def _refresh(self):
        if self._value:
            self.setText(self._value)
            self.setStyleSheet(
                "QPushButton { background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
                " padding:0 12px; color:#1A2332; font-size:10pt; text-align:left; }"
                "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }"
                "QPushButton:pressed { background:#EAF3FF; }")
        else:
            self.setText(self._placeholder)
            self.setStyleSheet(
                "QPushButton { background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
                " padding:0 12px; color:#94A3B8; font-size:10pt; text-align:left; }"
                "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }"
                "QPushButton:pressed { background:#EAF3FF; }")

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self._refresh()


# =============================================================================
#  INLINE TEXT PAD  (from railgui25)
# =============================================================================
class InlineTextPad(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = None
        self._buf = ""
        self.setObjectName("Panel")
        self.setStyleSheet(
            "QFrame#Panel { background:#FFFFFF; border:1px solid #D8E1EB; border-radius:14px; }")
        self.hide()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        key_area = QHBoxLayout()
        key_area.setContentsMargins(0, 0, 0, 0)
        key_area.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(6)
        for row_idx, row_str in enumerate(["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]):
            rl = QHBoxLayout()
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(6)
            if row_idx == 1:
                rl.addSpacing(20)
            elif row_idx == 2:
                rl.addSpacing(44)
            for ch in row_str:
                b = QPushButton(ch)
                b.setFixedSize(42, 42)
                b.setStyleSheet(
                    "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px;"
                    " color:#334155; font-size:10pt; font-weight:700; }"
                    "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }"
                    "QPushButton:pressed { background:#EAF3FF; }")
                b.clicked.connect(lambda _, v=ch: self._char(v))
                rl.addWidget(b)
            left.addLayout(rl)

        right = QGridLayout()
        right.setHorizontalSpacing(5)
        right.setVerticalSpacing(5)
        right_keys = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("/", 3, 0), ("0", 3, 1), ("-", 3, 2),
            (".", 4, 0),
        ]
        for ch, r, c in right_keys:
            b = QPushButton(ch)
            b.setFixedSize(42, 42)
            b.setStyleSheet(
                "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px;"
                " color:#334155; font-size:10pt; font-weight:700; }"
                "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }"
                "QPushButton:pressed { background:#EAF3FF; }")
            b.clicked.connect(lambda _, v=ch: self._char(v))
            right.addWidget(b, r, c)

        key_area.addLayout(left, 5)
        key_area.addLayout(right, 1)
        lay.addLayout(key_area)

        bot = QHBoxLayout()
        bot.setSpacing(6)
        for txt, fn, style, flex in [
            ("BACK",  self._backspace,
             "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px; color:#5B6575; font-size:9.5pt; font-weight:700; }"
             "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }", 1),
            ("CLEAR", self._clear,
             "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px; color:#5B6575; font-size:9.5pt; font-weight:700; }"
             "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }", 1),
            ("DONE",  self._done,
             "QPushButton { background:#E3EEFA; border:1px solid #1565C0; border-radius:11px; color:#1565C0; font-size:9.5pt; font-weight:700; }"
             "QPushButton:hover { background:#D9EAFD; }", 2),
        ]:
            b = QPushButton(txt)
            b.setFixedHeight(42)
            b.setStyleSheet(style)
            b.clicked.connect(fn)
            bot.addWidget(b, flex)
        lay.addLayout(bot)

    def bind(self, field):
        self._target = field
        self._buf = field.value()
        self._push_live()
        self.show()

    def _char(self, ch):
        self._buf += ch
        self._push_live()

    def _backspace(self):
        self._buf = self._buf[:-1]
        self._push_live()

    def _clear(self):
        self._buf = ""
        self._push_live()

    def _push_live(self):
        if self._target:
            self._target.set_value(self._buf)

    def _done(self):
        self.hide()


# =============================================================================
#  STEPPER  (from test.py — touch-friendly with numpad dialog)
# =============================================================================
class Stepper(QWidget):
    changed = pyqtSignal(float)

    def __init__(self, val=0, step=1, dec=0,
                 lo=0, hi=9999, unit="", title="VALUE", parent=None):
        super().__init__(parent)
        self._step  = step
        self._dec   = dec
        self._lo    = lo
        self._hi    = hi
        self._unit  = unit
        self._title = title
        self._val   = float(val)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._minus = QPushButton("-")
        self._minus.setObjectName("BX")
        self._minus.setFixedSize(46, 46)
        self._minus.clicked.connect(self._dec_v)

        self._btn = QPushButton()
        self._btn.setObjectName("BC")
        self._btn.setFixedHeight(46)
        self._btn.clicked.connect(self._open_pad)

        self._plus = QPushButton("+")
        self._plus.setObjectName("BC")
        self._plus.setFixedSize(46, 46)
        self._plus.clicked.connect(self._inc_v)

        lay.addWidget(self._minus)
        lay.addWidget(self._btn, 1)
        lay.addWidget(self._plus)
        self._refresh()

    def _refresh(self):
        suf = "  {}".format(self._unit) if self._unit else ""
        fmt = "{{:.{}f}}{{}}".format(self._dec)
        self._btn.setText(fmt.format(self._val, suf))

    def _dec_v(self):
        self._val = max(self._lo, round(self._val - self._step, self._dec))
        self._refresh()
        self.changed.emit(self._val)

    def _inc_v(self):
        self._val = min(self._hi, round(self._val + self._step, self._dec))
        self._refresh()
        self.changed.emit(self._val)

    def _open_pad(self):
        fmt = "{{:.{}f}}".format(self._dec)
        dlg = NumpadDialog(
            self._title, fmt.format(self._val),
            decimals=self._dec, min_val=self._lo, max_val=self._hi,
            unit=self._unit, parent=self.window())
        if dlg.exec_() == QDialog.Accepted and dlg.get_value() is not None:
            self._val = dlg.get_value()
            self._refresh()
            self.changed.emit(self._val)

    def value(self):
        return self._val

    def set_value(self, v):
        self._val = float(v)
        self._refresh()


# =============================================================================
#  PRESET TILES
# =============================================================================
class PresetTiles(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, options, selected="", color=CYAN, parent=None):
        super().__init__(parent)
        self._color = color
        self._btns  = {}
        self._sel   = ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        for opt in options:
            b = QPushButton(opt)
            b.setFixedHeight(44)
            b.setMinimumWidth(60)
            self._style(b, False)
            b.clicked.connect(lambda _, v=opt: self._pick(v))
            lay.addWidget(b)
            self._btns[opt] = b

        lay.addStretch()
        target = selected if selected in self._btns else (options[0] if options else "")
        if target:
            self._pick(target)

    def _style(self, btn, active):
        c = self._color
        if active:
            btn.setStyleSheet(
                "QPushButton{{background:{}22; border:2px solid {};"
                " border-radius:5px; color:{}; font-size:9pt;"
                " font-weight:bold; padding:0 10px;}}"
                "QPushButton:pressed{{background:{}33;}}".format(c, c, c, c))
        else:
            btn.setStyleSheet(
                "QPushButton{background:#111; border:1px solid #2a2a2a;"
                " border-radius:5px; color:#444; font-size:9pt;"
                " font-weight:bold; padding:0 10px;}"
                "QPushButton:pressed{background:#1a1a1a;}")

    def _pick(self, v):
        for opt, btn in self._btns.items():
            self._style(btn, opt == v)
        self._sel = v
        self.changed.emit(v)

    def value(self):
        return self._sel


# =============================================================================
#  ENCODER THREAD  (from test.py — full GPIO sysfs polling)
# =============================================================================
import threading as _threading


class EncoderThread(QThread):
    sw_pressed = pyqtSignal()

    _DEFAULT_PPR   = 20
    _WHEEL_DIAM_MM = 62.0
    _DEBOUNCE_MS   = 50

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg      = cfg
        self._lock    = _threading.Lock()
        self._count   = 0
        self._moving  = False
        self._running = True
        self._last_sw = 1
        self._sw_time = 0.0

    def distance_m(self):
        ppr  = self.cfg["encoder"].get("ppr",  self._DEFAULT_PPR)
        diam = self.cfg["encoder"].get("diam", self._WHEEL_DIAM_MM)
        circ = 3.14159265 * diam
        with self._lock:
            c = abs(self._count)
        return round(c / max(1, ppr) * circ / 1000.0, 3)

    def is_moving(self):
        with self._lock:
            return self._moving

    def reset(self):
        with self._lock:
            self._count  = 0
            self._moving = False

    def stop_thread(self):
        self._running = False

    def run(self):
        if HW_SIM:
            self._run_sim()
        else:
            self._run_hw()

    def _run_hw(self):
        for gpio in (ENC_CLK_GPIO, ENC_DT_GPIO, ENC_SW_GPIO):
            _gpio_export(gpio)
        last_clk = _gpio_read(ENC_CLK_GPIO)
        while self._running:
            clk = _gpio_read(ENC_CLK_GPIO)
            dt  = _gpio_read(ENC_DT_GPIO)
            sw  = _gpio_read(ENC_SW_GPIO)
            if clk != last_clk:
                with self._lock:
                    if dt != clk:
                        self._count += 1
                    else:
                        self._count -= 1
                    self._moving = True
            else:
                with self._lock:
                    self._moving = False
            last_clk = clk
            now = time.time()
            if sw == 0 and self._last_sw == 1:
                if (now - self._sw_time) * 1000 > self._DEBOUNCE_MS:
                    self._sw_time = now
                    self.sw_pressed.emit()
            self._last_sw = sw
            self.msleep(1)

    def _run_sim(self):
        while self._running:
            with self._lock:
                self._moving = False
            self.msleep(100)


# =============================================================================
#  SENSOR THREAD  (from test.py — full BBB ADC/SPI/UART/GPS stack)
# =============================================================================
class SensorThread(QThread):
    data_ready = pyqtSignal(dict)
    fault      = pyqtSignal(str)
    motion     = pyqtSignal(bool)

    _ADC_BITS    = 4096
    _ADC_MID     = 2048
    _GAUGE_STD   = 1676.0
    _GAUGE_MPC   = 0.036621
    _GAUGE_MIN   = 1601.0
    _GAUGE_MAX   = 1751.0
    _CROSS_MAX   = 75.0
    _INCL_FS     = 30.0
    _DEG_TO_MM   = 17.453
    _TWIST_CHORD = 3.5
    _DEADBAND    = 2
    _READ_TWICE  = True
    _GPS_BEARING_DEG = 0.0

    def __init__(self, cfg, encoder):
        super().__init__()
        self.cfg          = cfg
        self._encoder     = encoder
        self.active       = False

        self._has_adc0 = os.path.exists(ADC_PATH)
        self._has_adc1 = os.path.exists(ADC_PATH_1)
        self._has_gps  = os.path.exists("/dev/ttyS4")

        self._raw0       = -1
        self._raw1       = -1
        self._gauge_mm   = self._GAUGE_STD
        self._cross_mm   = 0.0
        self._prev_cross = 0.0

        self._last_dist  = 0.0
        self._last_time  = time.time()
        self._speed_ms   = 0.0

        self._cross_history = []
        self._last_twist    = 0.0

        self._lat        = 0.0
        self._lon        = 0.0
        self._speed_kmh  = 0.0
        self._gps_ser    = None
        self._gps_buf    = ""
        self._gps_active = False

        self._origin_lat = cfg.get("gnss", {}).get("origin_lat", 28.6139)
        self._origin_lon = cfg.get("gnss", {}).get("origin_lon", 77.2090)
        import math as _math
        self._m_per_deg_lat = 111320.0
        self._m_per_deg_lon = 111320.0 * _math.cos(_math.radians(self._origin_lat))

    def run(self):
        self._has_adc0 = os.path.exists(ADC_PATH)
        self._has_adc1 = os.path.exists(ADC_PATH_1)
        self._has_gps  = os.path.exists("/dev/ttyS4")
        self._open_gps()

        while True:
            try:
                d = self._sample()
                self.data_ready.emit(d)
            except Exception as exc:
                self.fault.emit(str(exc))
            self.msleep(500)

    def _sample(self):
        now    = time.time()
        moving = self._encoder.is_moving()
        self.motion.emit(moving)
        dist_m = self._encoder.distance_m()

        dt = now - self._last_time
        if dt > 0.1:
            dd = dist_m - self._last_dist
            raw_speed = dd / dt if dt > 0 else 0.0
            self._speed_ms = 0.3 * raw_speed + 0.7 * self._speed_ms
            self._last_dist = dist_m
            self._last_time = now
        speed_kmh = round(max(0.0, self._speed_ms * 3.6), 1)

        self._update_gauge()
        self._update_cross()

        self._cross_history.append((dist_m, self._cross_mm))
        trim = self._TWIST_CHORD * 2.0
        self._cross_history = [
            (d, c) for d, c in self._cross_history if dist_m - d <= trim
        ]

        if len(self._cross_history) >= 2:
            oldest_dist, oldest_cross = self._cross_history[0]
            span = dist_m - oldest_dist
            if span >= self._TWIST_CHORD:
                target = dist_m - self._TWIST_CHORD
                best   = min(self._cross_history, key=lambda x: abs(x[0] - target))
                chord_used = dist_m - best[0]
                if chord_used > 0.01:
                    self._last_twist = round(abs(self._cross_mm - best[1]) / chord_used, 3)
            elif span > 0.01:
                self._last_twist = round(abs(self._cross_mm - oldest_cross) / span, 3)

        twist = self._last_twist
        self._prev_cross = self._cross_mm

        self._update_gps(dist_m, speed_kmh)

        return {
            "gauge": self._gauge_mm,
            "cross": self._cross_mm,
            "twist": twist,
            "dist" : round(dist_m, 3),
            "lat"  : self._lat,
            "lon"  : self._lon,
            "speed": speed_kmh,
        }

    def _update_gauge(self):
        if not self._has_adc0:
            return
        raw = self._adc_read(ADC_PATH)
        if raw < 0:
            return
        if self._raw0 >= 0 and abs(raw - self._raw0) < self._DEADBAND:
            return
        self._raw0 = raw
        zero  = self.cfg["adc"].get("zero", self._ADC_MID)
        mpc   = self.cfg["adc"].get("mpc",  self._GAUGE_MPC)
        gauge = self._GAUGE_STD + (raw - zero) * mpc
        self._gauge_mm = round(max(self._GAUGE_MIN, min(self._GAUGE_MAX, gauge)), 1)

    def _update_cross(self):
        if not self._has_adc1:
            return
        raw = self._adc_read(ADC_PATH_1)
        if raw < 0:
            return
        if self._raw1 >= 0 and abs(raw - self._raw1) < self._DEADBAND:
            return
        self._raw1 = raw
        offset = self.cfg["incl"].get("offset", 0.0)
        if raw <= self._ADC_MID:
            cross_mm = (raw / float(self._ADC_MID)) * 5.0 - 5.0
        else:
            cross_mm = ((raw - self._ADC_MID) / 2047.0) * 10.0
        cross_mm -= offset
        cross_mm = round(cross_mm, 2)
        self._cross_mm = max(-self._CROSS_MAX, min(self._CROSS_MAX, cross_mm))

    def _adc_read(self, path):
        try:
            if self._READ_TWICE:
                with open(path) as fh:
                    fh.read()
            with open(path) as fh:
                return int(fh.read().strip())
        except Exception:
            return -1

    def _open_gps(self):
        if not self._has_gps:
            return
        try:
            import serial as _ser
            self._gps_ser = _ser.Serial(
                "/dev/ttyS4", baudrate=9600,
                bytesize=8, parity="N", stopbits=1, timeout=0.1)
        except Exception:
            self._gps_ser = None

    def _update_gps(self, dist_m, speed_kmh):
        if self._gps_ser is not None:
            self._read_gps_serial()
            self._speed_kmh = speed_kmh
        else:
            self._mock_gps(dist_m, speed_kmh)

    def _read_gps_serial(self):
        try:
            n = self._gps_ser.in_waiting
            if n > 0:
                self._gps_buf += self._gps_ser.read(n).decode("ascii", errors="replace")
                while "\n" in self._gps_buf:
                    line, self._gps_buf = self._gps_buf.split("\n", 1)
                    self._parse_nmea(line.strip())
        except Exception:
            pass

    def _mock_gps(self, dist_m, speed_kmh):
        import math as _math
        bearing_rad     = _math.radians(self._GPS_BEARING_DEG)
        d_lat           = dist_m * _math.cos(bearing_rad) / self._m_per_deg_lat
        d_lon           = dist_m * _math.sin(bearing_rad) / self._m_per_deg_lon
        self._lat       = round(self._origin_lat + d_lat, 7)
        self._lon       = round(self._origin_lon + d_lon, 7)
        self._speed_kmh = speed_kmh
        self._gps_active = True

    def _parse_nmea(self, sentence):
        try:
            if "*" in sentence:
                sentence = sentence[:sentence.rindex("*")]
            if not sentence.startswith("$"):
                return
            p   = sentence.split(",")
            tag = p[0].upper()
            if "GGA" in tag and len(p) >= 10:
                fix_q = int(p[6]) if p[6].strip().isdigit() else 0
                if fix_q >= 1 and p[2] and p[4]:
                    la = self._nmea_to_dec(p[2], p[3])
                    lo = self._nmea_to_dec(p[4], p[5])
                    if la or lo:
                        self._lat        = la
                        self._lon        = lo
                        self._gps_active = True
            elif "RMC" in tag and len(p) >= 8 and p[2].upper() == "A":
                if len(p) > 5 and p[3] and p[5]:
                    la = self._nmea_to_dec(p[3], p[4])
                    lo = self._nmea_to_dec(p[5], p[6])
                    if la or lo:
                        self._lat = la
                        self._lon = lo
                if len(p) > 7 and p[7].strip():
                    self._speed_kmh = round(float(p[7]) * 1.852, 1)
        except Exception:
            pass

    @staticmethod
    def _nmea_to_dec(raw, direction):
        try:
            raw = raw.strip()
            if not raw or "." not in raw:
                return 0.0
            i   = raw.index(".")
            d   = float(raw[:i - 2])
            m   = float(raw[i - 2:])
            dec = d + m / 60.0
            return round(-dec if direction.upper() in ("S", "W") else dec, 7)
        except Exception:
            return 0.0

    def reset(self):
        self._prev_cross    = 0.0
        self._last_dist     = 0.0
        self._last_time     = time.time()
        self._speed_ms      = 0.0
        self._cross_history = []
        self._last_twist    = 0.0
        if not self._gps_active:
            self._lat = 0.0
            self._lon = 0.0


# =============================================================================
#  NETWORK THREAD  (from test.py)
# =============================================================================
class NetThread(QThread):
    status = pyqtSignal(int, bool)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

    def run(self):
        while True:
            self.status.emit(self._lte(), self._ping())
            self.sleep(15)

    def _lte(self):
        iface = self.cfg.get("lte_iface", "eth1")
        if _sysfs("/sys/class/net/{}/operstate".format(iface), "down") == "up": return 3
        if _sysfs("/sys/class/net/eth0/operstate", "down") == "up": return 2
        return 0 if not HW_SIM else 3

    def _ping(self):
        if HW_SIM: return True
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", self.cfg.get("server", "8.8.8.8")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            return r.returncode == 0
        except Exception:
            return False


# =============================================================================
#  CSV LOGGER  (from test.py — with gauge field)
# =============================================================================
STATION_NAME = "BLR"

_FIELDS = [
    "epoch_time", "reference_type", "reference_value",
    "gauge", "latitude", "longitude",
    "cross_level", "chainage", "twist", "tilt", "tilt_cord_length",
]


class CSVLogger:
    def __init__(self):
        self._f         = self._w = None
        self._rows      = []
        self.path       = ""
        self.count      = 0
        self._ref_type  = ""
        self._ref_value = ""
        self._station   = "BLE"

    def set_reference(self, ref_type, ref_value):
        self._ref_type  = ref_type
        self._ref_value = ref_value

    def set_station(self, station_name):
        self._station = station_name.strip() if station_name else "UNKNOWN"

    def start(self, directory, hl_sec=30):
        os.makedirs(directory, exist_ok=True)
        safe_ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = "{}_{}.csv".format(self._station, safe_ts)
        self.path = os.path.join(directory, filename)
        self._f   = open(self.path, "w", newline="")
        self._w   = csv.DictWriter(self._f, fieldnames=_FIELDS)
        self._w.writeheader()
        self._rows  = []
        self._hl_s  = hl_sec
        self.count  = 0

    def write(self, d):
        if not self._w: return
        cross = d.get("cross", 0)
        row = {
            "epoch_time":       int(time.time()),
            "reference_type":   self._ref_type,
            "reference_value":  self._ref_value,
            "gauge":            d.get("gauge", 0),
            "latitude":         d.get("lat",   0),
            "longitude":        d.get("lon",   0),
            "cross_level":      cross,
            "chainage":         d.get("dist",  0),
            "twist":            d.get("twist", 0),
            "tilt":             cross,
            "tilt_cord_length": d.get("dist",  0),
        }
        self._rows.append((time.time(), row))
        self._w.writerow(row)
        self._f.flush()
        self.count += 1

    def mark(self, hl_sec=30):
        if not self._w or not self._rows: return
        self._hl_s = hl_sec
        self._f.seek(0); self._f.truncate()
        self._w.writeheader()
        for ts, row in self._rows:
            self._w.writerow(row)
        self._f.flush()

    def stop(self):
        if self._f: self._f.close()
        self._f = self._w = None


# =============================================================================
#  CSV WRITER THREAD  (from test.py — non-blocking queue)
# =============================================================================
import queue as _queue


class CSVWriterThread(QThread):
    wrote = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._q         = _queue.Queue(maxsize=2000)
        self._f         = None
        self._writer    = None
        self.path       = ""
        self.count      = 0
        self._ref_type  = ""
        self._ref_value = ""
        self._station   = "BLE"

    def set_reference(self, ref_type, ref_value):
        self._ref_type  = ref_type
        self._ref_value = ref_value

    def set_station(self, name):
        self._station = name.strip() if name else "UNKNOWN"

    def start_session(self, directory, hl_sec=30):
        os.makedirs(directory, exist_ok=True)
        ts        = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = "{}_{}.csv".format(self._station, ts)
        self.path = os.path.join(directory, filename)
        self.count = 0
        self._q.put({"_cmd": "open", "_path": self.path})

    def stop_session(self):
        self._q.put({"_cmd": "close"})

    def enqueue(self, d):
        try:
            self._q.put_nowait(d)
        except _queue.Full:
            pass

    def run(self):
        _EXT = list(_FIELDS) + ["gauge"]
        while True:
            try:
                item = self._q.get(timeout=1.0)
            except _queue.Empty:
                continue
            if isinstance(item, dict) and "_cmd" in item:
                cmd = item["_cmd"]
                if cmd == "open":
                    if self._f: self._f.flush(); self._f.close()
                    self._f = open(item["_path"], "w", newline="")
                    self._writer = csv.DictWriter(
                        self._f, fieldnames=_EXT, extrasaction="ignore")
                    self._writer.writeheader()
                    self._f.flush(); self.count = 0
                elif cmd in ("close", "stop"):
                    if self._f: self._f.flush(); self._f.close()
                    self._f = self._writer = None
                    if cmd == "stop": break
                continue
            if self._writer is None: continue
            cross = item.get("cross", 0)
            row = {
                "epoch_time":       int(time.time()),
                "reference_type":   self._ref_type,
                "reference_value":  self._ref_value,
                "latitude":         item.get("lat",   0),
                "longitude":        item.get("lon",   0),
                "cross_level":      cross,
                "chainage":         item.get("dist",  0),
                "twist":            item.get("twist", 0),
                "tilt":             cross,
                "tilt_cord_length": item.get("dist",  0),
                "gauge":            item.get("gauge", 0),
            }
            try:
                self._writer.writerow(row)
                self._f.flush()
                self.count += 1
                self.wrote.emit(self.count)
            except Exception as e:
                print("[CSVWriterThread] {}".format(e))


# =============================================================================
#  SPARKLINE
# =============================================================================
class SparkLine(QWidget):
    def __init__(self, color=NEON, parent=None):
        super().__init__(parent)
        self._d   = []
        self._col = QColor(color)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push(self, v):
        self._d.append(float(v))
        if len(self._d) > 200: self._d.pop(0)
        self.update()

    def paintEvent(self, _):
        if len(self._d) < 2: return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        mn, mx = min(self._d), max(self._d)
        rng = mx - mn or 1
        pts = [QPoint(int(W * i / (len(self._d) - 1)),
                      int(H * (mx - v) / rng))
               for i, v in enumerate(self._d)]
        p.setPen(QPen(self._col, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])


# =============================================================================
#  GRAPH CANVAS
# =============================================================================
class GraphCanvas(QWidget):
    def __init__(self, color=NEON, parent=None):
        super().__init__(parent)
        self._d   = []
        self._col = QColor(color)
        self.title = ""
        self.unit  = ""
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def load(self, data, title="", unit=""):
        self._d = list(data); self.title = title; self.unit = unit
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(BG))
        if len(self._d) < 2:
            p.setPen(QColor("#8A94A6"))
            p.setFont(QFont("Courier New", 10))
            p.drawText(QRect(0, 0, W, H), Qt.AlignCenter, "NO DATA -- START SESSION FIRST")
            p.end(); return

        PAD = 52; gW = W - PAD - 10; gH = H - 46
        mn, mx = min(self._d), max(self._d); rng = mx - mn or 1

        for i in range(5):
            y   = 26 + gH * i // 4
            val = mx - rng * i / 4
            p.setPen(QPen(QColor("#DDE3EA"), 1, Qt.DashLine))
            p.drawLine(PAD, y, PAD + gW, y)
            p.setPen(QColor("#8A94A6"))
            p.setFont(QFont("Courier New", 7))
            p.drawText(QRect(0, y - 8, PAD - 4, 16),
                       Qt.AlignRight | Qt.AlignVCenter, "{:.2f}".format(val))

        n    = len(self._d)
        path = QPainterPath()
        path.moveTo(PAD, 26 + gH)
        for i, v in enumerate(self._d):
            x = PAD + int(gW * i / (n - 1))
            y = 26  + int(gH * (mx - v) / rng)
            path.lineTo(x, y)
        path.lineTo(PAD + gW, 26 + gH)
        path.closeSubpath()
        grad = QLinearGradient(0, 26, 0, 26 + gH)
        c1 = QColor(self._col); c1.setAlpha(55)
        c2 = QColor(self._col); c2.setAlpha(0)
        grad.setColorAt(0, c1); grad.setColorAt(1, c2)
        p.fillPath(path, QBrush(grad))

        p.setPen(QPen(self._col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        prev = None
        for i, v in enumerate(self._d):
            pt = QPoint(PAD + int(gW * i / (n - 1)), 26 + int(gH * (mx - v) / rng))
            if prev: p.drawLine(prev, pt)
            prev = pt

        p.setPen(self._col)
        p.setFont(QFont("Courier New", 9, QFont.Bold))
        p.drawText(PAD, 18, "{}  [{}]  .  {} pts".format(self.title.upper(), self.unit, n))
        p.setPen(QColor("#8A94A6"))
        p.setFont(QFont("Courier New", 7))
        p.drawText(PAD, H - 4, "SESSION START")
        p.drawText(PAD + gW - 30, H - 4, "NOW")
        p.end()


# =============================================================================
#  TOP BAR  (from railgui25 — fully painted ISO style)
# =============================================================================
class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)

        self._bar_count  = 4
        self._bar_color  = QColor("#4CAF50")
        self._net_txt    = "LTE"
        self._net_col    = QColor("#4CAF50")
        self._sensor_txt = "SENSOR OK"
        self._sensor_ok  = True
        self._bat_txt    = "HW" if not HW_SIM else "SIM"
        self._time_txt   = "--:--:--"
        self._title_txt  = "LWTMT"

        tmr = QTimer(self)
        tmr.timeout.connect(self._tick)
        tmr.start(1000)
        self._tick()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        p.fillRect(0, 0, W, H, QColor("#1C2333"))
        p.fillRect(0, H - 2, W, 2, QColor("#2A3A50"))

        cy = H // 2
        f_mono_sm = QFont("Courier New", 9, QFont.Normal)
        f_mono_md = QFont("Courier New", 10, QFont.Bold)
        f_clock   = QFont("Courier New", 13, QFont.Bold)
        f_title   = QFont("Liberation Sans", 12, QFont.Bold)

        # Signal bars
        bw, bg_gap = 4, 3
        bar_hs = (5, 9, 13, 17)
        x = 14
        for i, bh in enumerate(bar_hs):
            by  = cy + 9 - bh
            col = self._bar_color if i < self._bar_count else QColor("#3A4555")
            path = QPainterPath()
            path.addRoundedRect(x, by, bw, bh, 1, 1)
            p.fillPath(path, col)
            x += bw + bg_gap

        x += 4
        p.setFont(f_mono_md)
        p.setPen(self._net_col)
        p.drawText(x, 0, 40, H, Qt.AlignVCenter | Qt.AlignLeft, self._net_txt)
        x += 40

        x += 6
        p.fillRect(x, cy - 8, 1, 16, QColor("#3A4555"))
        x += 10

        dot_col = QColor("#4CAF50") if self._sensor_ok else QColor("#EF5350")
        p.setBrush(dot_col); p.setPen(Qt.NoPen)
        p.drawEllipse(x, cy - 4, 8, 8)
        x += 14

        p.setFont(f_mono_sm)
        p.setPen(QColor("#A8C8A8") if self._sensor_ok else QColor("#FFAA44"))
        p.drawText(x, 0, 140, H, Qt.AlignVCenter | Qt.AlignLeft, self._sensor_txt)

        p.setFont(f_title)
        p.setPen(QColor("#F3F6FB"))
        p.drawText(QRect(0, 0, W, H), Qt.AlignCenter, self._title_txt)

        p.setFont(f_clock)
        p.setPen(QColor("#FFFFFF"))
        clk_w = 110
        p.drawText(W - clk_w - 14, 0, clk_w, H, Qt.AlignVCenter | Qt.AlignRight, self._time_txt)

        sep_x = W - clk_w - 14 - 10
        p.fillRect(sep_x, cy - 8, 1, 16, QColor("#3A4555"))

        bat_w = 60
        p.setFont(f_mono_sm)
        # colour: green=HW, amber=SIM
        p.setPen(QColor("#4CAF50") if not HW_SIM else QColor("#FF9800"))
        bix = sep_x - bat_w - 8
        p.drawText(bix, 0, bat_w, H, Qt.AlignVCenter | Qt.AlignRight, "[" + self._bat_txt + "]")

        p.end()

    def _tick(self):
        self._time_txt = datetime.now().strftime("%H:%M:%S")
        self.update()

    def update_net(self, bars, cloud):
        self._bar_count = max(0, min(4, bars))
        if bars >= 3:
            self._bar_color = QColor("#4CAF50"); self._net_col = QColor("#4CAF50")
        elif bars >= 1:
            self._bar_color = QColor("#FF9800"); self._net_col = QColor("#FF9800")
        else:
            self._bar_color = QColor("#EF5350"); self._net_col = QColor("#EF5350")
        self._net_txt = "LTE" if cloud else "NO SYNC"
        self.update()

    def push_error(self, msg):
        if msg:
            self._sensor_txt = (msg[:22] + "...") if len(msg) > 22 else msg
            self._sensor_ok  = False
        else:
            self._sensor_txt = "SENSOR OK"
            self._sensor_ok  = True
        self.update()


# =============================================================================
#  CONTROL BAR  (from test.py — mark / calibrate / CSV path)
# =============================================================================
class ControlBar(QWidget):
    sig_cal  = pyqtSignal()
    sig_mark = pyqtSignal(int)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setFixedHeight(44)
        self.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        self._csv_lbl = QLabel("[DIR]  " + _shorten(cfg["csv_dir"]))
        self._csv_lbl.setStyleSheet(
            "background:#F8FAFB; border:1px solid #DDE3EA; border-radius:5px;"
            " color:#1565C0; font-size:8pt; padding:3px 10px; font-family:'Courier New';")
        self._csv_lbl.setFixedHeight(32)

        cal = QPushButton("[COG]  CALIBRATE")
        cal.setStyleSheet(
            "QPushButton{{background:{lt}; border:1.5px solid {c};"
            " border-radius:5px; color:{c}; font-size:9pt;"
            " font-weight:bold; padding:3px 14px; min-height:32px;}}"
            "QPushButton:pressed{{background:#FFE4C0;}}".format(c=AMBER, lt=AMBER_LT))
        cal.clicked.connect(self.sig_cal)

        hl_lbl = QLabel("MARK LAST")
        hl_lbl.setStyleSheet("color:#8A94A6; font-size:8pt;")

        self._stepper = Stepper(cfg.get("hl_sec", 30), step=5, dec=0,
                                lo=5, hi=600, unit="s", title="HIGHLIGHT SECONDS")
        self._stepper.setFixedWidth(200)

        mark = QPushButton("MARK")
        mark.setStyleSheet(
            "QPushButton{{background:{lt}; border:1.5px solid {c};"
            " border-radius:5px; color:{c}; font-size:9pt;"
            " font-weight:bold; padding:3px 12px; min-height:32px;}}"
            "QPushButton:pressed{{background:#D0E4F7;}}".format(c=CYAN, lt=CYAN_LT))
        mark.clicked.connect(lambda: self.sig_mark.emit(int(self._stepper.value())))

        lay.addWidget(self._csv_lbl)
        lay.addWidget(cal)
        lay.addStretch()
        lay.addWidget(hl_lbl)
        lay.addWidget(self._stepper)
        lay.addWidget(mark)

    def set_csv_path(self, path):
        self._csv_lbl.setText("[DIR]  " + _shorten(path))


# =============================================================================
#  METRIC CARD  (from railgui25 — ISO light theme, drop shadow, badge)
# =============================================================================
# RDSO Indian BG thresholds
_THRESH = {
    "gauge": (6.0,  13.0),
    "cross": (50.0, 75.0),
    "twist": (8.0,  13.0),
    "dist":  (None, None),
}
_GAUGE_BASE = 1676.0


class MetricCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, key, title, unit, color, parent=None):
        super().__init__(parent)
        self.key   = key
        self.color = color
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        fx = QGraphicsDropShadowEffect(self)
        fx.setBlurRadius(16)
        fx.setOffset(0, 4)
        fx.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(fx)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(0)

        hdr = QWidget()
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(18, 10, 14, 8)
        hdr_l.setSpacing(8)

        self._title = QLabel(title.upper())
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setStyleSheet(
            "background: transparent; border: none; color: #4A5568;"
            " font-family: 'Liberation Sans',sans-serif;"
            " font-size: 11pt; font-weight: 600; letter-spacing: 1.2px;")

        self._badge = QLabel("NOMINAL")
        self._badge.setAlignment(Qt.AlignCenter)

        hdr_l.addWidget(self._title, 1)
        hdr_l.addWidget(self._badge)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background:#DDE3EA; border:none;")

        val_row_w = QWidget()
        val_row_w.setStyleSheet("background:transparent; border:none;")
        val_row_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer_l = QHBoxLayout(val_row_w)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(0)
        outer_l.addStretch(1)

        pair_w = QWidget()
        pair_w.setStyleSheet("background:transparent; border:none;")
        pair_l = QHBoxLayout(pair_w)
        pair_l.setContentsMargins(0, 0, 0, 0)
        pair_l.setSpacing(6)

        self._val = QLabel("---")
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._val.setMinimumWidth(320)
        self._val.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self._unit = QLabel(unit)
        self._unit.setObjectName("UnitLbl")
        self._unit.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self._unit.setFixedWidth(68)
        self._unit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._apply_unit_style()

        pair_l.addWidget(self._val)
        pair_l.addWidget(self._unit)
        outer_l.addWidget(pair_w)
        outer_l.addStretch(1)

        self._alert = QLabel("")
        self._alert.setAlignment(Qt.AlignCenter)
        self._alert.setFixedHeight(22)
        self._alert.setStyleSheet(
            "color: #C62828; background: transparent; border: none;"
            " font-family: 'Liberation Sans',sans-serif;"
            " font-size: 9pt; font-weight: 600; letter-spacing: 0.5px;")

        lay.addWidget(hdr)
        lay.addWidget(rule)
        lay.addWidget(val_row_w, 1)
        lay.addWidget(self._alert)

        self._apply_badge("NOMINAL", color)
        self._apply_val_style(color)
        self._apply_unit_style()
        self.setStyleSheet(
            "QFrame#Card{{ background:#FFFFFF; border:1px solid #DDE3EA;"
            " border-left:4px solid {}; border-radius:10px;}}".format(color))

    def _apply_badge(self, text, color):
        _BG_MAP = {
            "#1B8A4C": ("#D4EDDA", "#1B8A4C"),
            "#1565C0": ("#D0E4F7", "#1565C0"),
            "#C06000": ("#FFE8C0", "#944800"),
            "#5E35B1": ("#E0D4F5", "#5E35B1"),
            "#C62828": ("#FDDEDE", "#C62828"),
            "#E65100": ("#FFE0CC", "#C04000"),
        }
        bg, fg = _BG_MAP.get(color, ("#E8E8E8", "#333333"))
        self._badge.setText(text)
        self._badge.setStyleSheet(
            "color:{fg}; background:{bg}; border:1.5px solid {fg};"
            " border-radius:4px; padding:3px 10px;"
            " font-family:'Courier New',monospace;"
            " font-size:9pt; font-weight:bold; letter-spacing:1px;".format(fg=fg, bg=bg))

    def _apply_unit_style(self):
        self._unit.setStyleSheet(
            "QLabel#UnitLbl { color: #8A94A6; background: transparent; border: none;"
            " font-family: 'Courier New', monospace; font-size: 13pt; font-weight: 500;"
            " letter-spacing: 1px; padding-bottom: 14px; }")

    def _apply_val_style(self, color):
        self._val.setStyleSheet(
            "color:{}; background:transparent; border:none;"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:84pt; font-weight:700; letter-spacing:-3px;".format(color))

    def refresh(self, val):
        self._val.setText(str(val))
        warn, alarm = _THRESH.get(self.key, (None, None))
        if self.key == "gauge":
            dev = abs(float(val) - _GAUGE_BASE)
        else:
            dev = abs(float(val))
        if alarm is not None and dev >= alarm:
            vc  = RED
            txt = "[!]  ALARM"
            bg  = ("QFrame#Card{{background:#FFEBEE; border:1px solid #DDE3EA;"
                   " border-left:4px solid {}; border-radius:10px;}}").format(RED)
            self._apply_badge("ALARM", RED)
        elif warn is not None and dev >= warn:
            vc  = WARN
            txt = "^  WARN"
            bg  = ("QFrame#Card{{background:#FFF3E0; border:1px solid #DDE3EA;"
                   " border-left:4px solid {}; border-radius:10px;}}").format(WARN)
            self._apply_badge("MONITOR", WARN)
        else:
            vc  = self.color
            txt = ""
            bg  = ("QFrame#Card{{background:#FFFFFF; border:1px solid #DDE3EA;"
                   " border-left:4px solid {}; border-radius:10px;}}").format(self.color)
            self._apply_badge("NOMINAL", self.color)
        self._apply_val_style(vc)
        self._apply_unit_style()
        self._alert.setText(txt)
        self.setStyleSheet(bg)

    def mousePressEvent(self, _):
        self.clicked.emit(self.key)


# =============================================================================
#  GRAPH PAGE
# =============================================================================
class GraphPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        back = _btn("<- BACK", "BC", 46, 140)
        back.clicked.connect(self.sig_back)
        self._lbl = QLabel("--")
        self._lbl.setStyleSheet(
            "color:{}; font-size:11pt; font-weight:bold; letter-spacing:2px;".format(CYAN))
        hdr.addWidget(back)
        hdr.addSpacing(12)
        hdr.addWidget(self._lbl)
        hdr.addStretch()
        lay.addLayout(hdr)

        self._canvas = GraphCanvas()
        lay.addWidget(self._canvas, 1)

    def load(self, title, unit, data, color):
        self._lbl.setText(">  {} -- SESSION HISTORY".format(title.upper()))
        self._canvas._col = QColor(color)
        self._canvas.load(data, title, unit)


# =============================================================================
#  LIVE TERMINAL WIDGET  (from test.py, styled for light theme)
# =============================================================================
class TerminalWidget(QWidget):
    finished = pyqtSignal(int, str)

    def __init__(self, height=200, parent=None):
        super().__init__(parent)
        self._full_out = ""
        self._procs    = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        hdr = QHBoxLayout()
        self._cmd_lbl = QLabel("$  --")
        self._cmd_lbl.setStyleSheet(
            "color:#516074; font-size:8pt; font-family:'Courier New';"
            " background:#F8FAFB; border:1px solid #DDE3EA;"
            " padding:4px 8px; border-radius:8px 8px 0 0;")
        self._stat = QLabel("IDLE")
        self._stat.setStyleSheet(
            "color:#8A94A6; font-size:8pt; font-weight:bold;"
            " font-family:'Courier New'; padding:3px 8px;")
        hdr.addWidget(self._cmd_lbl, 1)
        hdr.addWidget(self._stat)
        lay.addLayout(hdr)

        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._out.setFixedHeight(height)
        self._out.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #DDE3EA;"
            " border-top:none; border-radius:0 0 8px 8px; color:#334155;"
            " font-size:8pt; font-family:'Courier New'; }")
        lay.addWidget(self._out)

    def run(self, cmd):
        self._full_out = ""
        self._out.clear()
        self._cmd_lbl.setText("$  " + cmd[:140])
        self._set_status("RUNNING", AMBER)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda p=proc: self._read(p))
        proc.finished.connect(lambda code, status, p=proc: self._done(code, p))
        proc.start("sh", ["-c", cmd])
        self._procs.append(proc)
        return proc

    def append(self, text):
        self._out.append(text)
        self._scroll()

    def clear_output(self):
        self._out.clear()
        self._full_out = ""
        self._cmd_lbl.setText("$  --")
        self._set_status("IDLE", "#8A94A6")

    def _read(self, proc):
        raw = proc.readAllStandardOutput().data().decode(errors="replace")
        self._full_out += raw
        for line in raw.splitlines():
            if line.strip():
                self._out.append(line)
        self._scroll()

    def _done(self, code, proc):
        raw = proc.readAllStandardOutput().data().decode(errors="replace")
        if raw.strip():
            self._full_out += raw
            for line in raw.splitlines():
                if line.strip():
                    self._out.append(line)
        ok = (code == 0)
        self._set_status("EXIT {}".format(code), NEON if ok else RED)
        self._out.append("\n{}\n{}  exit={}".format('-'*40, 'OK' if ok else 'FAIL', code))
        self._scroll()
        self.finished.emit(code, self._full_out)

    def _scroll(self):
        sb = self._out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_status(self, txt, color):
        self._stat.setText(txt)
        self._stat.setStyleSheet(
            "color:{}; font-size:8pt; font-weight:bold;"
            " font-family:'Courier New'; padding:3px 8px;".format(color))


# =============================================================================
#  ENCODER CAL  (from test.py — full GPIO-based calibration)
# =============================================================================
class EncoderCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg    = cfg
        self._scale = None
        self._phase = "idle"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("ROTARY ENCODER (eQEP) -- ODOMETER CALIBRATION", NEON, 10, True))
        lay.addWidget(_lbl(
            "(1) Set known distance below   "
            "(2) Tap RESET COUNTER   "
            "(3) Roll trolley exact that distance   "
            "(4) Tap CAPTURE & COMPUTE", "#8A94A6", 8))

        dr = QHBoxLayout()
        dr.addWidget(_lbl("Known distance:", "#4A5568"))
        self._dist_s = Stepper(1000, step=100, dec=0, lo=100, hi=50000,
                               unit="mm", title="KNOWN DISTANCE")
        dr.addWidget(self._dist_s, 1)
        lay.addLayout(dr)

        br = QHBoxLayout(); br.setSpacing(8)
        self._rst_btn = _btn("(1) RESET COUNTER",     "BG", 50)
        self._cap_btn = _btn("(2) CAPTURE & COMPUTE", "BC", 50)
        self._cap_btn.setEnabled(False)
        self._rst_btn.clicked.connect(self._do_reset)
        self._cap_btn.clicked.connect(self._do_capture)
        br.addWidget(self._rst_btn, 1)
        br.addWidget(self._cap_btn, 1)
        lay.addLayout(br)

        self._term = TerminalWidget(height=150)
        self._term.finished.connect(self._on_done)
        lay.addWidget(self._term)

        self._res = _lbl("", NEON)
        lay.addWidget(self._res)

        sv = _btn("SAVE CALIBRATION [OK]", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)

        ok = cfg["encoder"].get("calibrated", False)
        sc = cfg["encoder"].get("scale", 1.0)
        self._info = _lbl(
            ("[OK] CALIBRATED" if ok else "[X] NOT CALIBRATED")
            + "  |  scale={:.5f} mm/count".format(sc),
            NEON if ok else RED)
        lay.addWidget(self._info)
        lay.addStretch()

    def _cmd_reset(self):
        if os.path.exists(EQEP_PATH):
            return (
                "echo '# Resetting eQEP counter...' && "
                "echo '# Path: {p}' && "
                "echo 0 > {p} && "
                "echo '# Verify reset:' && cat {p}"
            ).format(p=EQEP_PATH)
        return ("echo '# [SIM] eQEP not present - simulation mode' && "
                "sleep 0.3 && echo 'Counter reset to: 0'")

    def _cmd_read(self):
        if os.path.exists(EQEP_PATH):
            return ("echo '# Reading eQEP counter after trolley roll...' && "
                    "cat {}".format(EQEP_PATH))
        cnt = random.randint(1800, 2400)
        return ("echo '# [SIM] Reading simulated eQEP counter...' && "
                "sleep 0.4 && echo 'Counter value: {}'".format(cnt))

    def _do_reset(self):
        self._phase = "reset"
        self._cap_btn.setEnabled(False)
        self._term.append("# EQEP path: {}".format(EQEP_PATH))
        self._term.run(self._cmd_reset())

    def _do_capture(self):
        self._phase = "capture"
        self._term.run(self._cmd_read())

    def _on_done(self, code, out):
        if code != 0:
            return
        if self._phase == "reset":
            self._term.append("[OK] Counter zeroed.\n  Roll trolley the exact known distance, then tap CAPTURE.")
            self._cap_btn.setEnabled(True)
        elif self._phase == "capture":
            nums = [w.strip(":,") for w in out.split() if w.strip(":,").lstrip("-").isdigit()]
            if not nums:
                self._term.append("[!]  Could not parse count from output"); return
            count = int(nums[-1])
            if count == 0:
                self._term.append("[!]  Count is still zero -- did you roll the trolley?"); return
            self._scale = self._dist_s.value() / count
            self._res.setText("Count: {}   ->   Scale: {:.5f} mm/count   ({:.1f} cts/mm)".format(
                count, self._scale, 1/self._scale))
            self._term.append("# Result: {} mm / {} counts = {:.5f} mm/count".format(
                self._dist_s.value(), count, self._scale))

    def _do_save(self):
        if self._scale is None:
            self._term.append("[!]  Complete steps (1) and (2) first"); return
        self.cfg["encoder"].update({"scale": self._scale, "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText("[OK] CALIBRATED  |  scale={:.5f} mm/count".format(self._scale))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("encoder", self.cfg["encoder"])


# =============================================================================
#  ADC / GAUGE CAL  (from test.py — full two-point calibration)
# =============================================================================
class ADCCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg       = cfg
        self._zero_raw = None
        self._mpc      = None
        self._phase    = "zero"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("GAUGE POTENTIOMETER (TRS100) -- ADC CALIBRATION", CYAN, 10, True))
        lay.addWidget(_lbl(
            "(1) Set gauge to exactly 1676 mm -> tap READ ZERO\n"
            "(2) Shift gauge by known offset -> tap READ OFFSET", "#8A94A6", 8))

        self._z_btn = _btn("(1) READ ZERO  (gauge @ 1676 mm)", "BC", 50)
        self._z_btn.clicked.connect(self._read_zero)
        lay.addWidget(self._z_btn)

        dr = QHBoxLayout()
        dr.addWidget(_lbl("Known offset:", "#4A5568"))
        self._off_s = Stepper(5.0, step=0.5, dec=2, lo=-30, hi=30,
                              unit="mm", title="GAUGE OFFSET")
        dr.addWidget(self._off_s, 1)
        lay.addLayout(dr)

        self._o_btn = _btn("(2) READ OFFSET (after shift)", "BC", 50)
        self._o_btn.setEnabled(False)
        self._o_btn.clicked.connect(self._read_offset)
        lay.addWidget(self._o_btn)

        self._term = TerminalWidget(height=150)
        self._term.finished.connect(self._on_done)
        lay.addWidget(self._term)

        self._res = _lbl("", CYAN)
        lay.addWidget(self._res)

        sv = _btn("SAVE CALIBRATION [OK]", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)

        ok  = cfg["adc"].get("calibrated", False)
        z   = cfg["adc"].get("zero", 2048)
        mpc = cfg["adc"].get("mpc", 0.0684)
        self._info = _lbl(
            ("[OK] CALIBRATED" if ok else "[X] NOT CALIBRATED")
            + "  |  zero={}  mpc={:.5f}".format(z, mpc),
            NEON if ok else RED)
        lay.addWidget(self._info)
        lay.addStretch()

    def _adc_cmd(self):
        if os.path.exists(ADC_PATH):
            return ("echo '# Reading IIO ADC device...' && "
                    "echo '# Path: {p}' && "
                    "echo -n 'Raw ADC value: ' && cat {p}").format(p=ADC_PATH)
        val = random.randint(1950, 2150)
        return ("echo '# [SIM] IIO ADC not present - simulation mode' && "
                "sleep 0.3 && echo 'Raw ADC value: {}'".format(val))

    def _read_zero(self):
        self._phase = "zero"
        self._term.run(self._adc_cmd())

    def _read_offset(self):
        self._phase = "offset"
        self._term.append("# Reading ADC after {:.2f} mm shift...".format(self._off_s.value()))
        self._term.run(self._adc_cmd())

    def _on_done(self, code, out):
        if code != 0:
            return
        nums = [w.strip(":,") for w in out.split()
                if w.strip(":,").lstrip("-").isdigit()]
        if not nums:
            self._term.append("[!]  Could not parse ADC raw value"); return
        val = int(nums[-1])
        if self._phase == "zero":
            self._zero_raw = val
            self._term.append(
                "[OK] Zero raw = {}  (gauge at 1676 mm)\n"
                "  Shift gauge by {:.2f} mm, then tap READ OFFSET.".format(val, self._off_s.value()))
            self._o_btn.setEnabled(True)
        elif self._phase == "offset":
            if self._zero_raw is None:
                return
            delta = val - self._zero_raw
            if delta == 0:
                self._term.append("[!]  D is zero -- did you shift the gauge?"); return
            self._mpc = self._off_s.value() / delta
            self._res.setText("ADC: {}  D={}  mpc={:.5f} mm/count".format(val, delta, self._mpc))

    def _do_save(self):
        if self._zero_raw is None or self._mpc is None:
            self._term.append("[!]  Complete both steps first"); return
        self.cfg["adc"].update({"zero": self._zero_raw, "mpc": self._mpc, "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText("[OK] CALIBRATED  |  zero={}  mpc={:.5f}".format(self._zero_raw, self._mpc))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("adc", self.cfg["adc"])


# =============================================================================
#  INCLINOMETER CAL  (from test.py — AIN1 pot zero calibration)
# =============================================================================
class InclinCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg     = cfg
        self._offset = None
        self._phase  = "idle"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("INCLINOMETER (AIN1 P9.40) -- CROSS-LEVEL ZERO", AMBER, 10, True))
        lay.addWidget(_lbl(
            "(1) Place trolley on certified flat track surface\n"
            "(2) Tap READ ZERO to capture zero-reference\n"
            "(3) Tap VERIFY -- corrected reading must be < +/-0.1 mm", "#8A94A6", 8))

        br = QHBoxLayout(); br.setSpacing(8)
        self._z_btn = _btn("(1) READ ZERO", "BA", 50)
        self._v_btn = _btn("(2) VERIFY",    "BA", 50)
        self._v_btn.setEnabled(False)
        self._z_btn.clicked.connect(self._read_zero)
        self._v_btn.clicked.connect(self._verify)
        br.addWidget(self._z_btn, 1)
        br.addWidget(self._v_btn, 1)
        lay.addLayout(br)

        self._term = TerminalWidget(height=160)
        self._term.finished.connect(self._on_done)
        lay.addWidget(self._term)

        self._res = _lbl("", AMBER)
        lay.addWidget(self._res)

        sv = _btn("SAVE CALIBRATION [OK]", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)

        ok  = cfg["incl"].get("calibrated", False)
        off = cfg["incl"].get("offset", 0.0)
        self._info = _lbl(
            ("[OK] CALIBRATED" if ok else "[X] NOT CALIBRATED")
            + "  |  offset={:.3f} mm".format(off),
            NEON if ok else RED)
        lay.addWidget(self._info)
        lay.addStretch()

    def _adc1_cmd(self):
        adc1 = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
        if os.path.exists(adc1):
            return ("echo '# Reading inclinometer pot (AIN1 P9.40)...' && "
                    "cat {p} && echo '' && cat {p}".format(p=adc1))
        val = random.randint(1900, 2200)
        return ("echo '# [SIM] AIN1 not present -- simulation' && "
                "sleep 0.2 && echo '{}'".format(val))

    def _read_zero(self):
        self._phase = "zero"
        self._term.run(self._adc1_cmd())

    def _verify(self):
        self._phase = "verify"
        self._term.append("# Re-reading to verify zero correction...")
        self._term.run(self._adc1_cmd())

    def _on_done(self, code, out):
        if code != 0:
            return
        nums = [w.strip() for w in out.split() if w.strip().lstrip("-").isdigit()]
        if not nums:
            self._term.append("[!]  Could not parse ADC value"); return
        raw = int(nums[-1])
        ADC_MID = 2048
        if raw <= ADC_MID:
            val_mm = (raw / float(ADC_MID)) * 5.0 - 5.0
        else:
            val_mm = ((raw - ADC_MID) / 2047.0) * 10.0

        if self._phase == "zero":
            self._offset = val_mm
            self._res.setText("Zero offset: raw={} -> {:.3f} mm".format(raw, val_mm))
            self._term.append(
                "[OK] Zero captured: raw={} = {:.3f} mm\n"
                "  Tap VERIFY to confirm correction.".format(raw, val_mm))
            self._v_btn.setEnabled(True)
        elif self._phase == "verify":
            corr = val_mm - (self._offset or 0.0)
            ok   = abs(corr) < 0.1
            self._res.setText("Corrected: {:.3f} mm  {}".format(
                corr, "[OK] PASS" if ok else "[!] Re-zero needed"))
            self._res.setStyleSheet("color:{}; font-size:9pt;".format(NEON if ok else AMBER))

    def _do_save(self):
        if self._offset is None:
            self._term.append("[!]  Read zero first"); return
        self.cfg["incl"].update({"offset": self._offset, "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText("[OK] CALIBRATED  |  offset={:.3f} mm".format(self._offset))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("incl", self.cfg["incl"])


# =============================================================================
#  GNSS CAL  (from test.py)
# =============================================================================
class GNSSCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg     = cfg
        self._action = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("GNSS  u-blox NEO-M8P-2  (/dev/ttyS4) -- FIX & CHAINAGE", MAGI, 10, True))
        lay.addWidget(_lbl(
            "Start gpsd -> check fix (>=4 sats for survey) -> "
            "optionally enable RTK -> set reference chainage -> SAVE", "#8A94A6", 8))

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("> START gpsd",  self._start_gpsd, "BM"),
            ("[S] STOP gpsd", self._stop_gpsd,  "BM"),
            ("[*] CHECK FIX", self._check_fix,  "BM"),
            ("[RTK] RTK MODE",self._rtk,        "BM"),
        ]):
            b = _btn(lbl, nm, 50)
            b.clicked.connect(fn)
            g.addWidget(b, i // 2, i % 2)
        lay.addLayout(g)

        self._term = TerminalWidget(height=170)
        self._term.finished.connect(self._on_done)
        lay.addWidget(self._term)

        rc = QHBoxLayout()
        rc.addWidget(_lbl("Reference chainage:", "#4A5568"))
        self._ch_s = Stepper(cfg["gnss"]["ref_ch"], step=100, dec=1,
                             lo=0, hi=9999999, unit="m", title="REF CHAINAGE")
        rc.addWidget(self._ch_s, 1)
        lay.addLayout(rc)

        sv = _btn("SAVE CONFIGURATION [OK]", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)

        ok = cfg["gnss"].get("calibrated", False)
        self._info = _lbl(
            ("[OK] CONFIGURED" if ok else "[X] NOT CONFIGURED")
            + "  |  ref={:.1f} m".format(cfg['gnss']['ref_ch']),
            NEON if ok else RED)
        lay.addWidget(self._info)
        lay.addStretch()

    def _start_gpsd(self):
        self._action = "start"
        cmd = (
            "echo '# Starting gpsd service on Ubuntu...' && "
            "sudo systemctl start gpsd 2>&1 && "
            "sleep 1 && echo '# Service status:' && systemctl is-active gpsd"
        ) if not HW_SIM else (
            "echo '# [SIM] sudo systemctl start gpsd' && "
            "sleep 0.5 && echo 'gpsd.service: active (running)'"
        )
        self._term.run(cmd)

    def _stop_gpsd(self):
        self._action = "stop"
        cmd = (
            "echo '# Stopping gpsd...' && sudo systemctl stop gpsd 2>&1 && echo 'gpsd stopped.'"
        ) if not HW_SIM else (
            "echo '# [SIM] sudo systemctl stop gpsd' && sleep 0.3 && echo 'gpsd stopped.'"
        )
        self._term.run(cmd)

    def _check_fix(self):
        self._action = "fix"
        cmd = (
            "echo '# Polling GNSS (10 s timeout)...' && "
            "timeout 10 gpspipe -r -n 25 2>&1 | grep -m1 'GGA' || "
            "echo 'No GGA sentence -- is gpsd running and antenna connected?'"
        ) if not HW_SIM else (
            "echo '# [SIM] gpspipe -r -n 25 | grep GGA' && "
            "sleep 0.8 && "
            "echo '$GPGGA,123519,1259.04,N,07730.18,E,1,08,0.9,920.4,M,46.9,M,,*47'"
        )
        self._term.append("# Checking GNSS fix quality (wait up to 10 s)...")
        self._term.run(cmd)

    def _rtk(self):
        self._action = "rtk"
        cmd = (
            "echo '# Enabling RTK via ubxtool...' && ubxtool -p RTCM 2>&1 | head -30"
        ) if not HW_SIM else (
            "echo '# [SIM] ubxtool -p RTCM' && "
            "sleep 0.5 && echo 'RTK RTCM3 output enabled on NEO-M8P-2'"
        )
        self._term.run(cmd)

    def _on_done(self, code, out):
        if self._action == "fix":
            for line in out.splitlines():
                if "GGA" in line:
                    p = line.split(",")
                    try:
                        q    = int(p[6]) if len(p) > 6 else 0
                        sats = int(p[7]) if len(p) > 7 else 0
                        alt  = p[9]      if len(p) > 9 else "?"
                        qual = {0:"No fix", 1:"GPS fix", 2:"DGPS",
                                4:"RTK Fixed", 5:"RTK Float"}.get(q, str(q))
                        col  = NEON if q >= 1 else RED
                        self._term.append(
                            "-> Quality: {}  Satellites: {}  Alt: {} m".format(qual, sats, alt))
                        self._info.setStyleSheet("color:{}; font-size:9pt;".format(col))
                    except Exception:
                        pass
                    return

    def _do_save(self):
        self.cfg["gnss"].update({"ref_ch": self._ch_s.value(), "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText("[OK] CONFIGURED  |  ref={:.1f} m".format(self._ch_s.value()))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("gnss", self.cfg["gnss"])


# =============================================================================
#  LTE STATUS  (from test.py)
# =============================================================================
class LTECal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LTE MODEM  (cdc_ether) -- NETWORK DIAGNOSTICS", CYAN, 10, True))
        lay.addWidget(_lbl(
            "Modem appears as Ethernet via cdc_ether kernel driver.\n"
            "Select interface then run diagnostics to verify connectivity.", "#8A94A6", 8))

        ir = QHBoxLayout()
        ir.addWidget(_lbl("Interface:", "#4A5568"))
        self._iface = PresetTiles(
            ["eth0", "eth1", "usb0", "wwan0"],
            selected=cfg.get("lte_iface", "eth1"), color=CYAN)
        ir.addWidget(self._iface, 1)
        lay.addLayout(ir)

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("IP ADDRESSES", self._ip,     "BC"),
            ("PING TEST",    self._ping,   "BC"),
            ("SHOW ROUTES",  self._routes, "BC"),
            ("nmcli STATUS", self._nmcli,  "BC"),
        ]):
            b = _btn(lbl, nm, 50)
            b.clicked.connect(fn)
            g.addWidget(b, i // 2, i % 2)
        lay.addLayout(g)

        self._term = TerminalWidget(height=210)
        lay.addWidget(self._term)

        sv = _btn("SAVE INTERFACE SELECTION [OK]", "BA", 48)
        sv.clicked.connect(self._save)
        lay.addWidget(sv)
        lay.addStretch()

    def _ip(self):
        i = self._iface.value()
        self._term.run(
            "echo '# ip addr show {i}' && ip addr show {i} 2>&1 && "
            "echo && echo '# ip link show {i}' && ip link show {i} 2>&1".format(i=i))

    def _ping(self):
        srv = self.cfg.get("server", "8.8.8.8")
        self._term.run("echo '# ping -c 4 -W 2 {s}' && ping -c 4 -W 2 {s} 2>&1".format(s=srv))

    def _routes(self):
        self._term.run("echo '# ip route show' && ip route show 2>&1")

    def _nmcli(self):
        cmd = (
            "echo '# nmcli device status' && nmcli device status 2>&1"
        ) if not HW_SIM else (
            "echo '# [SIM] nmcli device status' && "
            "printf 'DEVICE  TYPE      STATE      CONNECTION\\n"
            "eth1    ethernet  connected  LTE-modem\\n"
            "eth0    ethernet  connected  local-net\\n'"
        )
        self._term.run(cmd)

    def _save(self):
        self.cfg["lte_iface"] = self._iface.value()
        save_cfg(self.cfg)
        self._term.append("[OK] Interface saved: {}".format(self._iface.value()))


# =============================================================================
#  DISPLAY CAL  (from test.py)
# =============================================================================
class DisplayCal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LCD DISPLAY  (HDMI / omapdrm) -- XRANDR CONFIGURATION", AMBER, 10, True))

        for label, options, color, attr in [
            ("Output:",     ["HDMI-0","HDMI-1","HDMI-A-1","DVI-0"],        AMBER, "_out"),
            ("Resolution:", ["1024x600","1280x720","800x480","1920x1080"],  AMBER, "_res"),
            ("Rotation:",   ["normal","left","right","inverted"],           AMBER, "_rot"),
        ]:
            row = QHBoxLayout()
            row.addWidget(_lbl(label, "#4A5568"))
            w = PresetTiles(options, options[0], color)
            setattr(self, attr, w)
            row.addWidget(w, 1)
            lay.addLayout(row)

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("APPLY MODE",   self._apply,  "BA"),
            ("AUTO DETECT",  self._auto,   "BA"),
            ("SET ROTATION", self._rotate, "BA"),
            ("LIST MODES",   self._modes,  "BA"),
        ]):
            b = _btn(lbl, nm, 50)
            b.clicked.connect(fn)
            g.addWidget(b, i // 2, i % 2)
        lay.addLayout(g)

        self._term = TerminalWidget(height=190)
        lay.addWidget(self._term)
        lay.addStretch()

    def _apply(self):
        cmd = ("echo '# xrandr --output {out} --mode {res}' && "
               "xrandr --output {out} --mode {res} 2>&1 && "
               "echo 'Mode applied.' || echo 'xrandr error -- check output name with LIST MODES'"
               ).format(out=self._out.value(), res=self._res.value())
        self._term.run(cmd)

    def _auto(self):
        self._term.run("echo '# xrandr --output {out} --auto' && "
                       "xrandr --output {out} --auto 2>&1 && echo 'Done.'".format(out=self._out.value()))

    def _rotate(self):
        cmd = ("echo '# xrandr --output {out} --rotate {rot}' && "
               "xrandr --output {out} --rotate {rot} 2>&1 && "
               "echo 'Rotation set.'").format(out=self._out.value(), rot=self._rot.value())
        self._term.run(cmd)

    def _modes(self):
        self._term.run("echo '# xrandr --query' && xrandr 2>&1")


# =============================================================================
#  CALIBRATION PAGE  (from railgui25 layout + all sensors from test.py)
# =============================================================================
_SENSORS = [
    ("encoder", "Rotary Encoder",        NEON,  EncoderCal),
    ("adc",     "Gauge  (ADC/TRS100)",   CYAN,  ADCCal),
    ("incl",    "Inclinometer  (AIN1)",  AMBER, InclinCal),
    ("gnss",    "GNSS  (NEO-M8P)",       MAGI,  GNSSCal),
    ("lte",     "LTE  Network",          CYAN,  LTECal),
    ("display", "Display  (xrandr)",     AMBER, DisplayCal),
]


class CalibrationPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg   = cfg
        self._btns = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header bar (railgui25 style)
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(12, 0, 12, 0)
        title = QLabel("SENSOR CALIBRATION")
        title.setStyleSheet("color:{}; font-size:13pt; font-weight:bold; letter-spacing:3px;".format(AMBER))
        hdr.addStretch()
        hdr.addWidget(title)
        hdr.addStretch()
        root.addWidget(hdr_w)

        body_w = QWidget()
        body   = QVBoxLayout(body_w)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)

        # horizontal tab navigation (railgui25 style)
        nav = QWidget()
        nav_l = QHBoxLayout(nav)
        nav_l.setContentsMargins(0, 0, 0, 0)
        nav_l.setSpacing(8)

        self._stack = QStackedWidget()

        for i, (key, label, color, Cls) in enumerate(_SENSORS):
            sub = cfg.get(key, {})
            ok  = sub.get("calibrated", False) if isinstance(sub, dict) else False

            btn = QPushButton(("[OK]  " if ok else "o  ") + label)
            btn.setFixedHeight(48)
            btn.setStyleSheet(
                "QPushButton{ background:#FFFFFF; border:1px solid #D7E0EA;"
                " border-radius:12px; color:#5B6575; font-size:9pt;"
                " font-weight:700; padding:6px 12px; text-align:center;}"
                "QPushButton:hover{ background:#F8FAFB; border-color:#BAC8D8; }"
                "QPushButton:pressed{ background:#EEF3F8; }")
            btn.clicked.connect(lambda _, idx=i: self._sel(idx))
            nav_l.addWidget(btn, 1)
            self._btns.append((btn, label, color))

            w = Cls(cfg)
            if hasattr(w, "saved"):
                w.saved.connect(self._on_saved)

            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setStyleSheet("QScrollArea{ border:none; background:#FFFFFF; }")
            sc.setWidget(w)
            self._stack.addWidget(sc)

        body.addWidget(nav)

        rf = QFrame()
        rf.setObjectName("Panel")
        rl = QVBoxLayout(rf)
        rl.setContentsMargins(10, 10, 10, 10)
        rl.addWidget(self._stack)
        body.addWidget(rf, 1)

        root.addWidget(body_w, 1)

        # bottom back button (railgui25 style)
        bottom_w = QWidget()
        bottom_w.setStyleSheet("background:#FFFFFF; border-top:1px solid #DDE3EA;")
        bottom_l = QHBoxLayout(bottom_w)
        bottom_l.setContentsMargins(16, 10, 16, 10)
        back = _btn("<- BACK", "BC", 42, 150)
        back.clicked.connect(self.sig_back.emit)
        bottom_l.addStretch()
        bottom_l.addWidget(back)
        bottom_l.addStretch()
        root.addWidget(bottom_w)

        self._sel(0)

    def _sel(self, idx):
        for i, (btn, _, color) in enumerate(self._btns):
            if i == idx:
                btn.setStyleSheet(
                    "QPushButton{{ background:{c}14; border:2px solid {c};"
                    " border-radius:12px; color:{c}; font-size:9pt;"
                    " font-weight:700; padding:6px 12px; text-align:center;}}"
                    "QPushButton:hover{{ background:{c}18; }}"
                    "QPushButton:pressed{{ background:{c}24; }}".format(c=color))
            else:
                btn.setStyleSheet(
                    "QPushButton{ background:#FFFFFF; border:1px solid #D7E0EA;"
                    " border-radius:12px; color:#5B6575; font-size:9pt;"
                    " font-weight:700; padding:6px 12px; text-align:center;}"
                    "QPushButton:hover{ background:#F8FAFB; border-color:#BAC8D8; }"
                    "QPushButton:pressed{ background:#EEF3F8; }")
        self._stack.setCurrentIndex(idx)

    def _on_saved(self, key, _):
        for i, (k, label, color, *_) in enumerate(_SENSORS):
            if k == key:
                self._btns[i][0].setText("[OK]  " + label)
                break


# =============================================================================
#  STATION PARAMS WIDGET  (from railgui25 — combo + inline text pad)
# =============================================================================
class StationParamsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded   = False
        self._field_names = [
            "Station Code", "Chainage",
            "Nomenclature of Loop/Line Siding",
            "Turn-out No", "Curve No",
            "Level Crossing No", "Hectometer Post",
        ]
        self._field_rows = {}
        self._fields     = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QPushButton(">   STATION PARAMETERS")
        self._hdr.setFixedHeight(50)
        self._hdr.setStyleSheet(
            "QPushButton{{background:#FFFFFF; border:1px solid {c}55;"
            " border-radius:10px; color:{c}; font-size:10pt;"
            " font-weight:bold; font-family:'Courier New'; text-align:left;"
            " padding:0 14px; letter-spacing:1px;}}"
            "QPushButton:pressed{{background:#F4F7FB;}}".format(c=HEADER_ACCENT))
        self._hdr.clicked.connect(self._toggle)
        root.addWidget(self._hdr)

        self._body = QWidget()
        self._body.hide()
        self._body.setStyleSheet(
            "background:#FFFFFF; border-left:1px solid #DDE3EA;"
            " border-right:1px solid #DDE3EA; border-bottom:1px solid #DDE3EA;"
            " border-bottom-left-radius:10px; border-bottom-right-radius:10px;")
        body_l = QVBoxLayout(self._body)
        body_l.setContentsMargins(12, 12, 12, 12)
        body_l.setSpacing(8)

        lbl = QLabel("Select station parameter")
        lbl.setStyleSheet("color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
        body_l.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.addItem("Select station parameter", None)
        for name in self._field_names:
            self.combo.addItem(name, name)
        self.combo.setFixedHeight(42)
        self.combo.setStyleSheet(
            "QComboBox { background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
            " padding:0 12px; color:#1A2332; font-size:10pt; }"
            "QComboBox::drop-down { border:none; width:32px; }"
            "QComboBox QAbstractItemView {"
            " background:#FFFFFF; border:1px solid #C8D0DA; color:#1A2332;"
            " selection-background-color:#E3EEFA; selection-color:#1A2332; }")
        self.combo.currentIndexChanged.connect(self._focus_selected_field)
        body_l.addWidget(self.combo)

        for name in self._field_names:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(12)
            field_lbl = QLabel(name)
            field_lbl.setStyleSheet(
                "color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
            field_lbl.setFixedWidth(250)
            field_edit = TouchTextField("Enter {}".format(name.lower()))
            field_edit.activated.connect(self._activate_text_field)
            row_l.addWidget(field_lbl)
            row_l.addWidget(field_edit, 1)
            row_w.hide()
            self._field_rows[name] = row_w
            self._fields[name] = field_edit
            body_l.addWidget(row_w)

        insp_hdr = QLabel("Inspecting Official")
        insp_hdr.setStyleSheet(
            "color:{}; font-size:9pt; font-weight:bold; background:transparent;".format(HEADER_ACCENT))
        body_l.addWidget(insp_hdr)

        for fname, attr in [("Name", "_official_name"), ("Designation", "_official_designation")]:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(12)
            f = TouchTextField("Enter {}".format(fname.lower()))
            f.activated.connect(self._activate_text_field)
            setattr(self, attr, f)
            lw = QLabel(fname)
            lw.setStyleSheet("color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
            lw.setFixedWidth(250)
            row_l.addWidget(lw)
            row_l.addWidget(f, 1)
            body_l.addWidget(row_w)

        self._text_pad = InlineTextPad()
        body_l.addWidget(self._text_pad)

        root.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        arrow = "v" if self._expanded else ">"
        tick = "   [OK]" if self._expanded else ""
        self._hdr.setText("{}   STATION PARAMETERS{}".format(arrow, tick))
        self._body.setVisible(self._expanded)

    def _focus_selected_field(self, _):
        selected = self.combo.currentData()
        for name, row_w in self._field_rows.items():
            row_w.setVisible(name == selected)
        field = self._fields.get(selected)
        if field:
            self._activate_text_field(field)

    def _activate_text_field(self, field):
        self._text_pad.bind(field)


# =============================================================================
#  DATA ENTRY PAGE  (from railgui25 layout + test.py sensor log)
# =============================================================================
_PARAM_TABLES = [
    ("gauge", "GAUGE",       "gauge", 0.25,  "mm",   NEON),
    ("cross", "CROSS-LEVEL", "cross", 0.25,  "mm",   CYAN),
    ("twist", "TWIST",       "twist", 2.0,   "mm/m", AMBER),
    ("chainage", "CHAINAGE", "dist",  100.0, "m",    MAGI),
]


class DataEntryPage(QWidget):
    sig_back = pyqtSignal()
    CHORD_OPTIONS = ["3.5", "4.5", "7.0", "9.0", "14.0"]

    def __init__(self):
        super().__init__()
        self._sensor_rows = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)
        title = QLabel("SURVEY DATA ENTRY  (RDSO Para 3.2)")
        title.setStyleSheet("color:{}; font-size:11pt; font-weight:bold; letter-spacing:2px;".format(CYAN))
        hdr.addStretch()
        hdr.addWidget(title)
        hdr.addStretch()
        root.addWidget(hdr_w)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(14, 10, 14, 14)
        cl.setSpacing(10)

        # Station Params (railgui25 style)
        self._station_params = StationParamsWidget()
        cl.addWidget(self._station_params)

        # Chord length row
        chord_row = QHBoxLayout()
        chord_row.addWidget(_lbl("Twist Chord (m):", "#4A5568", 9))
        self._chord_tiles = PresetTiles(self.CHORD_OPTIONS, selected="3.5", color=AMBER)
        chord_row.addWidget(self._chord_tiles, 1)
        cl.addLayout(chord_row)

        # Measurement log (test.py style — RDSO Table 3.3)
        cl.addWidget(_lbl("LIVE MEASUREMENT LOG  (RDSO Table 3.3 — auto-captured during session)",
                          CYAN, 9, True))

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(2)
        cols = [
            ("CH (m)",   75, MAGI),
            ("GAUGE mm", 78, NEON),
            ("X-LVL mm", 78, CYAN),
            ("TWIST",    72, AMBER),
            ("LAT",     100, "#8A94A6"),
            ("LON",     100, "#8A94A6"),
        ]
        for txt, fw, col in cols:
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedWidth(fw)
            lbl.setStyleSheet(
                "color:{}; font-size:7pt; font-weight:bold;"
                " background:#ECEFF4; border:1px solid #DDE3EA; padding:3px;".format(col))
            hdr_row.addWidget(lbl)
        cl.addLayout(hdr_row)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_scroll.setStyleSheet("QScrollArea{border:1px solid #DDE3EA;}")
        self._log_scroll.setFixedHeight(180)
        self._log_widget = QWidget()
        self._log_lay = QVBoxLayout(self._log_widget)
        self._log_lay.setContentsMargins(0, 0, 0, 0)
        self._log_lay.setSpacing(1)
        self._log_lay.addStretch()
        self._log_scroll.setWidget(self._log_widget)
        cl.addWidget(self._log_scroll)

        clr_btn = _btn("[DEL]  CLEAR LOG", "BR", 34)
        clr_btn.clicked.connect(self._clear_log)
        cl.addWidget(clr_btn)
        cl.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        bottom_w = QWidget()
        bottom_w.setStyleSheet("background:#FFFFFF; border-top:1px solid #DDE3EA;")
        bottom_l = QHBoxLayout(bottom_w)
        bottom_l.setContentsMargins(16, 10, 16, 10)
        back_btn = _btn("<- BACK", "BC", 42, 150)
        back_btn.clicked.connect(self.sig_back.emit)
        bottom_l.addStretch()
        bottom_l.addWidget(back_btn)
        bottom_l.addStretch()
        root.addWidget(bottom_w)

    def push_sensor_data(self, d):
        ch    = d.get("dist",  0.0)
        gauge = d.get("gauge", 0.0)
        cross = d.get("cross", 0.0)
        twist = d.get("twist", 0.0)
        lat   = d.get("lat",   0.0)
        lon   = d.get("lon",   0.0)
        self._sensor_rows.append((ch, gauge, cross, twist, lat, lon))

        row_w = QWidget()
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        cells = [
            ("{:.2f}".format(ch),    75,  MAGI),
            ("{:.1f}".format(gauge), 78,  NEON),
            ("{:.2f}".format(cross), 78,  CYAN),
            ("{:.3f}".format(twist), 72,  AMBER),
            ("{:.6f}".format(lat),   100, "#8A94A6"),
            ("{:.6f}".format(lon),   100, "#8A94A6"),
        ]
        for txt, fw, col in cells:
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedWidth(fw)
            lbl.setStyleSheet(
                "color:{}; font-size:7pt; font-family:'Courier New';"
                " background:#FAFBFC; border:1px solid #E8EDF2; padding:2px;".format(col))
            rl.addWidget(lbl)
        self._log_lay.insertWidget(self._log_lay.count() - 1, row_w)
        self._log_scroll.verticalScrollBar().setValue(
            self._log_scroll.verticalScrollBar().maximum())

    def _clear_log(self):
        self._sensor_rows = []
        while self._log_lay.count() > 1:
            item = self._log_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_chord_m(self):
        try:
            return float(self._chord_tiles.value())
        except Exception:
            return 3.5

    def get_data(self):
        return {"sensor_rows": list(self._sensor_rows)}


# =============================================================================
#  CSV VIEWER PAGE  (from railgui25)
# =============================================================================
class CSVViewerPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_dir = str(Path.home() / "surveys")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)
        hdr.setSpacing(8)

        back = _btn("<- DASHBOARD", "BC", 40, 170)
        back.clicked.connect(self.sig_back)

        title = QLabel("[CLIP]   CSV FILE VIEWER")
        title.setStyleSheet("color:{}; font-size:13pt; font-weight:bold; letter-spacing:3px;".format(MAGI))

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet("color:#8A94A6; font-size:8pt; font-family:'Courier New';")
        self._file_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        browse_btn = _btn("[OPEN]  BROWSE", "BM", 40, 130)
        browse_btn.clicked.connect(self._browse)

        hdr.addWidget(back)
        hdr.addSpacing(10)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._file_lbl, 1)
        hdr.addSpacing(8)
        hdr.addWidget(browse_btn)
        root.addWidget(hdr_w)

        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        left = QFrame(); left.setObjectName("Panel"); left.setFixedWidth(220)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(5)

        lbl = QLabel("SAVED FILES")
        lbl.setStyleSheet("color:{}; font-size:8pt; font-weight:bold; letter-spacing:2px;".format(MAGI))
        ll.addWidget(lbl)

        self._file_scroll = QScrollArea()
        self._file_scroll.setWidgetResizable(True)
        self._file_scroll.setStyleSheet("QScrollArea{border:none; background:#FAFBFC;}")
        self._file_list_widget = QWidget()
        self._file_list_layout = QVBoxLayout(self._file_list_widget)
        self._file_list_layout.setContentsMargins(2, 2, 2, 2)
        self._file_list_layout.setSpacing(4)
        self._file_list_layout.addStretch()
        self._file_scroll.setWidget(self._file_list_widget)
        ll.addWidget(self._file_scroll, 1)

        refresh_btn = _btn("R  REFRESH", "BX", 36)
        refresh_btn.clicked.connect(self._refresh_list)
        ll.addWidget(refresh_btn)

        body.addWidget(left)

        right = QFrame(); right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)
        rl.setSpacing(4)

        self._row_lbl = QLabel("")
        self._row_lbl.setStyleSheet("color:#8A94A6; font-size:8pt; font-family:'Courier New';")
        rl.addWidget(self._row_lbl)

        self._table = QTableWidget()
        self._table.setStyleSheet(
            "QTableWidget {{ background:#FFFFFF; color:#1A2332;"
            " font-size:8pt; font-family:'Courier New';"
            " gridline-color:#DDE3EA; border:none; }}"
            "QHeaderView::section {{ background:#ECEFF4; color:{c};"
            " font-size:8pt; font-weight:bold; border:1px solid #DDE3EA;"
            " padding:4px; }}"
            "QTableWidget::item:selected {{ background:{c}22; color:#1A2332; }}"
            "QScrollBar:vertical {{ background:#ECEFF4; width:8px; }}"
            "QScrollBar::handle:vertical {{ background:#C8D0DA; border-radius:4px; }}"
            "QScrollBar:horizontal {{ background:#ECEFF4; height:8px; }}"
            "QScrollBar::handle:horizontal {{ background:#C8D0DA; border-radius:4px; }}"
            .format(c=MAGI))
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background:#ECEFF4; color:#8A94A6;"
            " font-size:7pt; border:1px solid #DDE3EA; }")
        rl.addWidget(self._table, 1)

        body.addWidget(right, 1)

        root_body = QWidget()
        root_body.setLayout(body)
        root.addWidget(root_body, 1)

    def set_csv_dir(self, path):
        self._csv_dir = path
        self._refresh_list()

    def load_latest(self):
        self._refresh_list()
        files = sorted(Path(self._csv_dir).glob("*.csv"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            self._load_file(str(files[0]))

    def _refresh_list(self):
        while self._file_list_layout.count() > 1:
            item = self._file_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        files = sorted(Path(self._csv_dir).glob("*.csv"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            btn = QPushButton(f.name)
            btn.setObjectName("EF")
            btn.setFixedHeight(44)
            btn.setStyleSheet(
                "QPushButton{{background:#FAFBFC; border:1px solid #DDE3EA;"
                " border-radius:5px; color:{c}; font-size:7pt;"
                " font-family:'Courier New'; text-align:left; padding-left:8px;}}"
                "QPushButton:pressed{{background:#EDE7F6; border-color:{c};}}".format(c=MAGI))
            btn.clicked.connect(lambda _, p=str(f): self._load_file(p))
            self._file_list_layout.insertWidget(self._file_list_layout.count() - 1, btn)

        if not files:
            empty = QLabel("No CSV files found")
            empty.setStyleSheet("color:#8A94A6; font-size:8pt; padding:8px;")
            self._file_list_layout.insertWidget(0, empty)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", self._csv_dir, "CSV Files (*.csv)")
        if path:
            self._load_file(path)

    def _load_file(self, path):
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                headers = reader.fieldnames or []

            self._table.clear()
            self._table.setRowCount(len(rows))
            self._table.setColumnCount(len(headers))
            self._table.setHorizontalHeaderLabels(headers)

            for r, row in enumerate(rows):
                for c, h in enumerate(headers):
                    item = QTableWidgetItem(str(row.get(h, "")))
                    item.setTextAlignment(Qt.AlignCenter)
                    self._table.setItem(r, c, item)

            name = Path(path).name
            self._file_lbl.setText(name)
            self._row_lbl.setText(
                "{} rows  .  {} columns  .  {}".format(len(rows), len(headers), name))
        except Exception as e:
            self._row_lbl.setText("Error loading file: {}".format(e))


# =============================================================================
#  DASHBOARD PAGE  (from railgui25 ISO style + test.py signal routing)
# =============================================================================
_METRICS = [
    ("gauge", "Track Gauge",  "mm",   NEON),
    ("cross", "Cross Level",  "mm",   CYAN),
    ("twist", "Twist",        "mm/m", AMBER),
    ("dist",  "Distance",     "m",    MAGI),
]


class DashboardPage(QWidget):
    sig_toggle = pyqtSignal(bool)
    sig_pause  = pyqtSignal(bool)
    sig_entry  = pyqtSignal()
    sig_csv    = pyqtSignal()
    sig_graph  = pyqtSignal(str)
    sig_view   = pyqtSignal()
    sig_cal    = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = False
        self._paused  = False

        self.setStyleSheet("background:#ECEFF4;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 6)
        lay.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._cards = {}
        for i, (key, title, unit, color) in enumerate(_METRICS):
            card = MetricCard(key, title, unit, color)
            card.clicked.connect(self.sig_graph)
            grid.addWidget(card, i // 2, i % 2)
            self._cards[key] = card
        lay.addLayout(grid, 1)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#DDE3EA; border:none;")
        lay.addWidget(sep)

        bot = QHBoxLayout()
        bot.setContentsMargins(0, 6, 0, 6)
        bot.setSpacing(10)

        # CSV folder button
        self._csv_btn = QPushButton("[DIR]  SELECT CSV FOLDER")
        self._csv_btn.setFixedHeight(52)
        self._csv_btn.setMinimumWidth(200)
        self._csv_btn.setStyleSheet(self._ss_action(CYAN))
        self._csv_btn.clicked.connect(self.sig_csv)

        # View CSV button
        self._view_btn = QPushButton("[CLIP]  VIEW CSV")
        self._view_btn.setFixedHeight(52)
        self._view_btn.setMinimumWidth(130)
        self._view_btn.setStyleSheet(self._ss_action(MAGI))
        self._view_btn.clicked.connect(self.sig_view)

        vsep = QFrame(); vsep.setFixedSize(1, 40)
        vsep.setStyleSheet("background:#DDE3EA; border:none;")

        self._toggle = QPushButton("> START")
        self._toggle.setFixedHeight(58)
        self._toggle.setMinimumWidth(120)
        self._toggle.setStyleSheet(self._ss_start())
        self._toggle.clicked.connect(self._do_toggle)

        self._pause_btn = QPushButton("|| PAUSE")
        self._pause_btn.setFixedHeight(58)
        self._pause_btn.setMinimumWidth(120)
        self._pause_btn.setStyleSheet(self._ss_pause())
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._do_pause)

        vsep2 = QFrame(); vsep2.setFixedSize(1, 40)
        vsep2.setStyleSheet("background:#DDE3EA; border:none;")

        self._entry_btn = QPushButton("DATA ENTRY")
        self._entry_btn.setFixedHeight(52)
        self._entry_btn.setMinimumWidth(130)
        self._entry_btn.setStyleSheet(self._ss_action(CYAN))
        self._entry_btn.clicked.connect(self.sig_entry)

        self._cal_btn = QPushButton("CALIBRATE")
        self._cal_btn.setFixedHeight(52)
        self._cal_btn.setMinimumWidth(120)
        self._cal_btn.setStyleSheet(self._ss_action(AMBER))
        self._cal_btn.clicked.connect(self.sig_cal)

        self._stat = QLabel("o  IDLE  0 pts")
        self._stat.setStyleSheet(
            "color:#8A94A6; font-family:'Courier New',monospace;"
            " font-size:10pt; font-weight:500;")

        bot.addWidget(self._csv_btn)
        bot.addWidget(self._view_btn)
        bot.addWidget(vsep)
        bot.addStretch()
        bot.addWidget(self._toggle)
        bot.addWidget(self._pause_btn)
        bot.addWidget(vsep2)
        bot.addWidget(self._entry_btn)
        bot.addWidget(self._cal_btn)
        bot.addSpacing(10)
        bot.addWidget(self._stat)
        bot.addStretch()
        lay.addLayout(bot)

    def _ss_action(self, color):
        bg_map = {CYAN: CYAN_LT, AMBER: AMBER_LT, MAGI: MAGI_LT}
        bg = bg_map.get(color, "#F0F0F0")
        return (
            "QPushButton{{ background:{bg}; border:2px solid {c};"
            " border-radius:8px; color:{c};"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:11pt; font-weight:bold; padding:0px 14px;}}"
            "QPushButton:pressed{{ background:{c}; color:#FFFFFF; border:2px solid {c};}}"
            "QPushButton:disabled{{ background:#EEF0F3; border-color:#C8D0DA; color:#B0BAC8;}}"
        ).format(c=color, bg=bg)

    def _ss_start(self):
        return (
            "QPushButton{{ background:{c}; border:2px solid {c};"
            " border-radius:8px; color:#FFFFFF;"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            "QPushButton:pressed{{ background:#145E35; border-color:#145E35; }}"
        ).format(c=NEON)

    def _ss_stop(self):
        return (
            "QPushButton{{ background:{c}; border:2px solid {c};"
            " border-radius:8px; color:#FFFFFF;"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            "QPushButton:pressed{{ background:#8B1A1A; border-color:#8B1A1A; }}"
        ).format(c=RED)

    def _ss_pause(self):
        return (
            "QPushButton{{ background:{lt}; border:2px solid {c};"
            " border-radius:8px; color:{c};"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            "QPushButton:pressed{{ background:{c}; color:#FFFFFF; border:2px solid {c};}}"
            "QPushButton:disabled{{ background:#EEF0F3; border-color:#C8D0DA; color:#B0BAC8;}}"
        ).format(c=AMBER, lt=AMBER_LT)

    def _ss_resume(self):
        return (
            "QPushButton{{ background:{c}; border:2px solid {c};"
            " border-radius:8px; color:#FFFFFF;"
            " font-family:'Liberation Sans',sans-serif;"
            " font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            "QPushButton:pressed{{ background:#0D4A8A; border-color:#0D4A8A; }}"
        ).format(c=CYAN)

    def _do_toggle(self):
        self._running = not self._running
        if self._running:
            self._toggle.setText("[S] STOP")
            self._toggle.setStyleSheet(self._ss_stop())
            self._entry_btn.setEnabled(False)
            self._cal_btn.setEnabled(False)
            self._csv_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            self._paused = False
            self._pause_btn.setText("|| PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        else:
            self._toggle.setText("> START")
            self._toggle.setStyleSheet(self._ss_start())
            self._entry_btn.setEnabled(True)
            self._cal_btn.setEnabled(True)
            self._csv_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._paused = False
            self._pause_btn.setText("|| PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_toggle.emit(self._running)

    def _do_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("> RESUME")
            self._pause_btn.setStyleSheet(self._ss_resume())
        else:
            self._pause_btn.setText("|| PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_pause.emit(self._paused)

    def update_data(self, d):
        for key, card in self._cards.items():
            if key in d:
                card.refresh(d[key])

    def set_session(self, n, running, path=""):
        col  = NEON if running else "#8A94A6"
        icon = "* REC" if running else "o IDLE"
        fname = Path(path).name[-28:] if path else "-"
        self._stat.setText("{}  {} pts  {}".format(icon, n, fname))
        self._stat.setStyleSheet(
            "color:{}; font-family:'Courier New',monospace;"
            " font-size:10pt; font-weight:500;".format(col))

    def set_csv_label(self, path):
        self._csv_btn.setText("[DIR]  " + _shorten(path, 20))


# =============================================================================
#  MAIN APPLICATION  (test.py architecture + railgui25 structure)
# =============================================================================
SCREEN_W, SCREEN_H = 1024, 600


class TrackApp(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg        = load_cfg()
        self.logger     = CSVLogger()
        self.csv_writer = CSVWriterThread(self)
        self.csv_writer.start()

        # EncoderThread: GPIO sysfs polling (from test.py)
        self.encoder = EncoderThread(self.cfg, self)
        self.encoder.sw_pressed.connect(self._on_enc_sw)
        self.encoder.start()

        self.history = {k: [] for k, *_ in _METRICS}

        self.setWindowTitle("Rail Inspection Unit v5.0")
        self.setStyleSheet(SS)

        # SensorThread: full BBB ADC/SPI/UART/GPS (from test.py)
        self.sensor = SensorThread(self.cfg, self.encoder)
        self.sensor.data_ready.connect(self._on_data)
        self.sensor.fault.connect(self._on_fault)
        self.sensor.motion.connect(self._on_motion)
        self.sensor.start()

        # Screen blanking (from test.py)
        self._SCREEN_TIMEOUT_MS = 5 * 60 * 1000
        self._last_motion_time  = time.time()
        self._screen_off        = False

        self._screen_timer = QTimer(self)
        self._screen_timer.setInterval(10000)
        self._screen_timer.timeout.connect(self._check_screen_timeout)
        self._screen_timer.start()

        self._blank = QWidget(self)
        self._blank.setStyleSheet("background:#000000;")
        self._blank.hide()
        self._blank.mousePressEvent = self._wake_screen

        # Network thread (from test.py)
        self.net = NetThread(self.cfg)
        self.net.status.connect(self._on_net)
        self.net.start()

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # TopBar: ISO painted status bar (railgui25)
        self.topbar  = TopBar(self)

        # ControlBar: mark / calibrate / CSV path (test.py)
        self.ctrlbar = ControlBar(self.cfg, self)
        self.ctrlbar.sig_cal.connect(lambda: self._goto(1))
        self.ctrlbar.sig_mark.connect(self._on_mark)

        self.stack = QStackedWidget()

        # Dashboard (railgui25 ISO style + test.py signal routing)
        self.dash = DashboardPage()
        self.dash.sig_toggle.connect(self._on_toggle)
        self.dash.sig_pause.connect(self._on_pause)
        self.dash.sig_entry.connect(lambda: self._goto(2))
        self.dash.sig_csv.connect(self._pick_csv)
        self.dash.sig_graph.connect(self._show_graph)
        self.dash.sig_view.connect(self._show_csv_viewer)
        self.dash.sig_cal.connect(lambda: self._goto(1))
        self.stack.addWidget(self.dash)       # 0

        # CalibrationPage (railgui25 layout + all test.py sensors)
        self.cal = CalibrationPage(self.cfg)
        self.cal.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.cal)        # 1

        # DataEntryPage (railgui25 station params + test.py sensor log)
        self.entry = DataEntryPage()
        self.entry.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.entry)      # 2

        # GraphPage
        self.graph_pg = GraphPage()
        self.graph_pg.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.graph_pg)   # 3

        # CSVViewerPage
        self.csv_viewer = CSVViewerPage()
        self.csv_viewer.sig_back.connect(lambda: self._goto(0))
        self.csv_viewer.set_csv_dir(self.cfg["csv_dir"])
        self.stack.addWidget(self.csv_viewer) # 4

        root.addWidget(self.topbar)
        root.addWidget(self.ctrlbar)
        root.addWidget(self.stack, 1)

        self.dash.set_csv_label(self.cfg["csv_dir"])

        # Window mode
        if not os.environ.get("DISPLAY", ""):
            os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb")
        self.showMaximized()

    def _goto(self, idx):
        self.stack.setCurrentIndex(idx)

    def _on_data(self, d):
        for key in self.history:
            if key in d:
                self.history[key].append(d[key])
                if len(self.history[key]) > 10000:
                    self.history[key].pop(0)
        self.dash.update_data(d)

        if self.sensor.active:
            self.entry.push_sensor_data(d)
            self.csv_writer.enqueue(d)
            self.logger.write(d)

        self.dash.set_session(
            self.csv_writer.count, self.sensor.active,
            self.csv_writer.path or self.logger.path or "")

    def _on_fault(self, msg):
        self.topbar.push_error("Sensor: {}".format(msg))

    def _on_net(self, bars, cloud):
        self.topbar.update_net(bars, cloud)

    def _on_toggle(self, running):
        self.sensor.active = running
        if running:
            self.logger.set_reference("", "")
            self.logger.set_station("BLE")
            self.csv_writer.set_reference("", "")
            self.csv_writer.set_station("BLE")
            self.encoder.reset()
            self.sensor.reset()
            self.history = {k: [] for k in self.history}
            self.logger.start(self.cfg["csv_dir"], self.cfg.get("hl_sec", 30))
            self.csv_writer.start_session(self.cfg["csv_dir"], self.cfg.get("hl_sec", 30))
        else:
            self.logger.stop()
            self.csv_writer.stop_session()

    def _on_pause(self, paused):
        self.sensor.active = not paused

    def _on_motion(self, moving):
        if moving:
            self._last_motion_time = time.time()
            if self._screen_off:
                self._wake_screen()

    def _on_enc_sw(self):
        if self.sensor.active:
            self.encoder.reset()
            self.topbar.push_error("Encoder zeroed by SW press")

    def _check_screen_timeout(self):
        if self._screen_off:
            return
        idle_ms = (time.time() - self._last_motion_time) * 1000
        if idle_ms >= self._SCREEN_TIMEOUT_MS:
            self._blank_screen()

    def _blank_screen(self):
        self._screen_off = True
        self._blank.setGeometry(self.rect())
        self._blank.raise_()
        self._blank.show()

    def _wake_screen(self, _event=None):
        self._screen_off       = False
        self._last_motion_time = time.time()
        self._blank.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._screen_off:
            self._blank.setGeometry(self.rect())

    def _on_mark(self, sec):
        self.cfg["hl_sec"] = sec
        save_cfg(self.cfg)
        self.logger.mark(sec)

    def _show_csv_viewer(self):
        self.csv_viewer.set_csv_dir(self.cfg["csv_dir"])
        self.csv_viewer.load_latest()
        self._goto(4)

    def _pick_csv(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select CSV Output Directory",
            self.cfg["csv_dir"], QFileDialog.ShowDirsOnly)
        if d:
            self.cfg["csv_dir"] = d
            save_cfg(self.cfg)
            self.dash.set_csv_label(d)
            self.ctrlbar.set_csv_path(d)
            self.csv_viewer.set_csv_dir(d)

    def _show_graph(self, key):
        meta = {k: (t, u, c) for k, t, u, c in _METRICS}
        if key not in meta:
            return
        title, unit, color = meta[key]
        self.graph_pg.load(title, unit, list(self.history.get(key, [])), color)
        self._goto(3)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.resize(SCREEN_W, SCREEN_H)
        super().keyPressEvent(e)


# =============================================================================
def main():
    if not os.environ.get("DISPLAY", ""):
        os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb")

    app = QApplication(sys.argv)
    app.setApplicationName("Rail Inspection Unit")

    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    except AttributeError:
        pass

    try:
        app.restoreOverrideCursor()
    except Exception:
        pass

    w = TrackApp()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
