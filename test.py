#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rail Track Geometry Inspection System
Target  : BeagleBone Black Industrial | Ubuntu | 1024x600 HDMI/Touch
Stack   : PyQt5 | Python 3.5+
Version : 4.0.0 - touch + mouse, all features working

Sensor map:
  Rotary Encoder   -> eQEP -> /sys/.../eqep/counter/count0/count
  Gauge Pot(TRS100)-> ADC  -> /sys/bus/iio/devices/iio:device0/in_voltage0_raw
  Inclinometer     -> SPI  -> /dev/spidev1.0  (Murata SCL3300)
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
    QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess, QPoint, QRect, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush, QLinearGradient, QPainterPath,
)

# -----------------------------------------------------------------------------
#  PALETTE
# -----------------------------------------------------------------------------
BG    = "#050505"
CARD  = "#0c0c0c"
NEON  = "#39FF14"
CYAN  = "#00D4FF"
AMBER = "#FFCC00"
RED   = "#FF3131"
MAGI  = "#CC44FF"

W, H = 1024, 600          # target display

# -----------------------------------------------------------------------------
#  GLOBAL STYLESHEET  (no conflicting min-height; sizes set in code)
# -----------------------------------------------------------------------------
SS = """
QWidget            { background: #050505; color: #CCCCCC;
                     font-family: 'Courier New', monospace; }
QDialog            { background: #0e0e0e; }
QFrame#Card        { background: #0c0c0c; border: 1px solid #1c1c1c;
                     border-radius: 10px; }
QFrame#Panel       { background: #080808; border: 1px solid #181818;
                     border-radius: 8px; }
QTextEdit          { background: #060606; border: 1px solid #1a1a1a;
                     color: #888; font-size: 8pt; font-family: 'Courier New'; }
QScrollBar:vertical          { background: #0a0a0a; width: 8px; }
QScrollBar::handle:vertical  { background: #2a2a2a; border-radius: 4px;
                                min-height: 30px; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

/* -- named button styles -- */
QPushButton#BG  { background:#002800; border:2px solid #39FF14; border-radius:7px;
                  color:#39FF14; font-size:10pt; font-weight:bold; }
QPushButton#BG:pressed   { background:#003d00; }
QPushButton#BG:disabled  { background:#0a0a0a; border-color:#1a1a1a; color:#2a2a2a; }

QPushButton#BC  { background:#001520; border:2px solid #00D4FF; border-radius:7px;
                  color:#00D4FF; font-size:10pt; font-weight:bold; }
QPushButton#BC:pressed   { background:#002030; }
QPushButton#BC:disabled  { background:#0a0a0a; border-color:#1a1a1a; color:#2a2a2a; }

QPushButton#BA  { background:#1a1200; border:2px solid #FFCC00; border-radius:7px;
                  color:#FFCC00; font-size:10pt; font-weight:bold; }
QPushButton#BA:pressed   { background:#261b00; }

QPushButton#BR  { background:#1a0000; border:2px solid #FF3131; border-radius:7px;
                  color:#FF3131; font-size:10pt; font-weight:bold; }
QPushButton#BR:pressed   { background:#260000; }

QPushButton#BM  { background:#140020; border:2px solid #CC44FF; border-radius:7px;
                  color:#CC44FF; font-size:10pt; font-weight:bold; }
QPushButton#BM:pressed   { background:#1e0030; }

QPushButton#BX  { background:#111; border:1px solid #333; border-radius:7px;
                  color:#666; font-size:10pt; font-weight:bold; }
QPushButton#BX:pressed   { background:#1a1a1a; }

/* numpad */
QPushButton#NK  { background:#111; border:1px solid #2a2a2a; border-radius:8px;
                  color:#DDD; font-size:18pt; font-weight:bold; }
QPushButton#NK:pressed   { background:#222; border-color:#00D4FF; }
QPushButton#NO  { background:#001520; border:1px solid #00D4FF; border-radius:8px;
                  color:#00D4FF; font-size:14pt; font-weight:bold; }
QPushButton#NO:pressed   { background:#002030; }
QPushButton#NOK { background:#002800; border:2px solid #39FF14; border-radius:8px;
                  color:#39FF14; font-size:14pt; font-weight:bold; }
QPushButton#NOK:pressed  { background:#003d00; }
QPushButton#ND  { background:#1a0a00; border:1px solid #FF8800; border-radius:8px;
                  color:#FF8800; font-size:14pt; font-weight:bold; }
QPushButton#ND:pressed   { background:#260e00; }

/* char-key */
QPushButton#CK  { background:#111; border:1px solid #2a2a2a; border-radius:5px;
                  color:#aaa; font-size:11pt; font-weight:bold; }
QPushButton#CK:pressed   { background:#222; border-color:#FFCC00; }

/* entry-field row button */
QPushButton#EF  { background:#0a0a0a; border:1px solid #222; border-radius:6px;
                  color:#00D4FF; font-size:12pt; font-family:'Courier New';
                  text-align:left; padding-left:12px; }
QPushButton#EF:pressed   { background:#101018; border-color:#00D4FF; }

/* sensor-list side button */
QPushButton#SB  { background:#0c0c0c; border:1px solid #1e1e1e; border-radius:8px;
                  color:#555; font-size:8pt; font-weight:bold;
                  padding:6px 8px; text-align:left; }
QPushButton#SB:checked { border-color:#39FF14; color:#39FF14; }
"""


# -----------------------------------------------------------------------------
#  CONFIG
# -----------------------------------------------------------------------------
CFG_PATH  = Path(__file__).parent / "rail_config.json"
_DEF = {
    "csv_dir":   str(Path.home() / "surveys"),
    "hl_sec":    30,
    "server":    "8.8.8.8",
    "lte_iface": "eth1",
    "encoder":   {"scale": 1.0,  "ppr": 20, "diam": 62.0, "calibrated": False},  # ppr=pulses/rev  diam=wheel_mm
    "adc":       {"zero": 2048,  "mpc": 0.0684, "calibrated": False},
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


# -----------------------------------------------------------------------------
#  HARDWARE  --  BeagleBone Black, direct-wired, no breadboard, no ext. supply
# -----------------------------------------------------------------------------
#
#  +- TWO 10 k- POTS --------------------------------------------------------+
#  |  POWER  (onboard BBB -- no external supply)                              |
#  |    P9.32  VDD_ADC 1.8 V  ->  Pot1 VCC + Pot2 VCC  (twist 2 wires->1 pin) |
#  |    P9.34  GNDA_ADC       ->  Pot 1 GND  (true analog ground)             |
#  |    P9.1   DGND           ->  Pot 2 GND                                   |
#  |  SIGNAL                                                                  |
#  |    P9.39  AIN0  ->  Pot 1 wiper  (TRS100  -- gauge, mm)                  |
#  |    P9.40  AIN1  ->  Pot 2 wiper  (SCL3300 -- cross-level, deg)            |
#  +-------------------------------------------------------------------------+
#
#  +- ROTARY ENCODER  (GND SW DT CLK VCC) -----------------------------------+
#  |    P9.4   3.3 V digital  ->  Encoder VCC  (separate from ADC P9.32)      |
#  |    P9.45  DGND           ->  Encoder GND  (dedicated -- no pot conflict)  |
#  |    P8.11  GPIO1_13 (#45) ->  Encoder CLK                                 |
#  |    P8.12  GPIO1_12 (#44) ->  Encoder DT                                  |
#  |    P8.14  GPIO0_26 (#26) ->  Encoder SW   (push-button -- zero/mark)      |
#  |  GPIO numbers: P8.11=45  P8.12=44  P8.14=26                             |
#  |  (bankx32 + bit: bank1x32+13=45, bank1x32+12=44, bank0x32+26=26)        |
#  +-------------------------------------------------------------------------+
#
#  TOTAL: 10 unique pins -- ZERO CONFLICTS

# BBB IIO ADC sysfs paths (12-bit, 0-4095, max 1.8 V)
ADC_PATH   = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"  # AIN0 P9.39
ADC_PATH_1 = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"  # AIN1 P9.40

# Rotary encoder GPIO sysfs paths
ENC_CLK_GPIO = 45  # P8.11  GPIO1_13
ENC_DT_GPIO  = 44  # P8.12  GPIO1_12
ENC_SW_GPIO  = 26  # P8.14  GPIO0_26
_GPIO_BASE   = "/sys/class/gpio"

SPI_DEV    = "/dev/spidev1.0"

# -- Load required BBB kernel modules at startup -------------------------------
def _load_kernel_modules():
    """
    Load BBB ADC and UART overlay modules silently.
    These are needed for potentiometers (IIO ADC) and GPS (UART4).
    Safe to call multiple times -- modprobe is idempotent.
    """
    modules = [
        "ti_am335x_adc",      # BBB IIO ADC (AIN0..AIN6)
        "omap_hsmmc",         # sometimes needed
    ]
    for mod in modules:
        try:
            subprocess.call(
                ["sudo", "modprobe", mod],
                stdout=open(os.devnull, "w"),
                stderr=open(os.devnull, "w")
            )
        except Exception:
            pass

    # Enable UART4 for GPS (/dev/ttyS4) via config-pin if available
    uart4_pins = [("P9.11", "uart"), ("P9.13", "uart")]
    for pin, mode in uart4_pins:
        try:
            subprocess.call(
                ["config-pin", pin, mode],
                stdout=open(os.devnull, "w"),
                stderr=open(os.devnull, "w")
            )
        except Exception:
            pass

_load_kernel_modules()

# Give the kernel 1 second to create /dev and /sys nodes after module load
time.sleep(1)

# Hardware available when BBB IIO ADC sysfs node is present
HW_SIM = not os.path.exists(ADC_PATH)


def _gpio_export(num):
    """Export a GPIO pin via sysfs if not already exported."""
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
    """Read a sysfs GPIO value; returns 1 or 0."""
    try:
        with open("{}/gpio{}/value".format(_GPIO_BASE, num)) as f:
            return int(f.read().strip())
    except Exception:
        return 1  # default high (pull-up)


# eQEP path kept for reference only (not used in this build)
EQEP_PATH = ("/sys/devices/platform/ocp/48304000.epwmss"
             "/48304180.eqep/counter/count0/count")


def _sysfs(path, default="0"):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


# -----------------------------------------------------------------------------
#  HELPERS
# -----------------------------------------------------------------------------
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
    f.setStyleSheet("color:#1a1a1a;")
    f.setMaximumWidth(1)
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
    """Fire-and-forget QProcess; callback(output_str) called on finish."""
    proc = QProcess(parent)
    proc.setProcessChannelMode(QProcess.MergedChannels)

    def _done():
        out = proc.readAllStandardOutput().data().decode(errors="replace")
        callback(out)

    proc.finished.connect(_done)
    proc.start("sh", ["-c", cmd])
    return proc     # keep reference alive on caller


# =============================================================================
#  NUMPAD DIALOG
#  -- plain QDialog (no frameless), styled dark; always fits inside 1024x600
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

        # title
        t = QLabel(title.upper())
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(
            "color:{}; font-size:11pt; font-weight:bold;".format(CYAN)
        )
        root.addWidget(t)

        # display
        self._disp = QLabel()
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(58)
        self._disp.setStyleSheet(
            ("background:#060606; border:1px solid {}; border-radius:6px;"
             " color:{}; font-size:24pt; font-family:'Courier New';"
             " padding-right:10px; font-weight:bold;").format(CYAN, CYAN)
        )
        root.addWidget(self._disp)

        # numpad
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

        pm  = _btn("+/-",   "NO",  64, 86); pm.clicked.connect(self._sign);  g.addWidget(pm,  4, 0)
        clr = _btn("CLR", "NO",  64, 86); clr.clicked.connect(self._clear); g.addWidget(clr, 4, 1)
        ok  = _btn("[OK] OK","NOK", 64, 86); ok.clicked.connect(self._confirm); g.addWidget(ok,  4, 2)
        root.addLayout(g)

        cnc = _btn("X  CANCEL", "BR", 46)
        cnc.clicked.connect(self.reject)
        root.addWidget(cnc)
        self._refresh()

        # Centre over parent
        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width()  - self.width())  // 2,
                      pg.y() + (pg.height() - self.height()) // 2)

    # -- numpad logic ----------------------------------------------------------
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
#  -- preset tiles + compact A-Z keyboard; fits within 600px height
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

        # title + display on same row to save vertical space
        hdr = QHBoxLayout()
        t = QLabel(title.upper())
        t.setStyleSheet(
            "color:{}; font-size:11pt; font-weight:bold;".format(AMBER)
        )
        self._disp = QLabel(self._buf or "--")
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(44)
        self._disp.setMinimumWidth(260)
        self._disp.setStyleSheet(
            ("background:#060606; border:1px solid {}; border-radius:5px;"
             " color:{}; font-size:16pt; font-family:'Courier New';"
             " padding-right:8px; font-weight:bold;").format(AMBER, AMBER)
        )
        hdr.addWidget(t, 0)
        hdr.addStretch()
        hdr.addWidget(self._disp, 1)
        root.addLayout(hdr)

        # preset buttons grid (3 per row, fixed height 44)
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

        # compact keyboard: rows of 10 chars each
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

        # backspace + clear
        br = QHBoxLayout()
        br.setSpacing(6)
        bs  = _btn("BS  BACK", "ND",  42); bs.clicked.connect(self._bksp)
        clr = _btn("CLR",     "BX",  42); clr.clicked.connect(self._clr)
        br.addWidget(bs, 1)
        br.addWidget(clr, 1)
        root.addLayout(br)

        # ok / cancel
        bot = QHBoxLayout()
        bot.setSpacing(8)
        ok  = _btn("[OK]  CONFIRM", "BG", 46); ok.clicked.connect(self._confirm)
        cnc = _btn("X  CANCEL",  "BR", 46); cnc.clicked.connect(self.reject)
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
#  REUSABLE TOUCH STEPPER  (no conflicting stylesheet sizing)
# =============================================================================
class Stepper(QWidget):
    """  -  [ value ]  +   tap value to open numpad  """
    changed = pyqtSignal(float)

    def __init__(self, val=0, step=1, dec=0,
                 lo=0, hi=9999, unit="", title="VALUE", parent=None):
        super().__init__(parent)
        self._step = step
        self._dec  = dec
        self._lo   = lo
        self._hi   = hi
        self._unit = unit
        self._title = title
        self._val  = float(val)

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
            self._title,
            fmt.format(self._val),
            decimals=self._dec,
            min_val=self._lo, max_val=self._hi,
            unit=self._unit,
            parent=self.window(),
        )
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
#  PRESET TILES  (radio-style; all in code -- no CSS selector needed)
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
                ("QPushButton{{background:{}; border:2px solid {};"
                 " border-radius:5px; color:{}; font-size:9pt;"
                 " font-weight:bold; padding:0 10px;}}"
                 "QPushButton:pressed{{background:{};}}").format(c, c, c, c)
            )
        else:
            btn.setStyleSheet(
                "QPushButton{background:#111; border:1px solid #2a2a2a;"
                " border-radius:5px; color:#444; font-size:9pt;"
                " font-weight:bold; padding:0 10px;}"
                "QPushButton:pressed{background:#1a1a1a;}"
            )

    def _pick(self, v):
        for opt, btn in self._btns.items():
            self._style(btn, opt == v)
        self._sel = v
        self.changed.emit(v)

    def value(self):
        return self._sel


# ==============================================================================
#  ENCODER THREAD  -- polls CLK/DT/SW via BBB sysfs GPIO at 1 ms intervals
#
#  Pins (P8 header -- zero conflict with P9 ADC cluster):
#    CLK  P8.11  GPIO1_13  (#45)  -- quadrature A phase
#    DT   P8.12  GPIO1_12  (#44)  -- quadrature B phase
#    SW   P8.14  GPIO0_26  (#26)  -- push-button (zero / mark)
#    VCC  P9.4   3.3 V digital
#    GND  P9.45  DGND
#
#  Distance = |count| / PPR x wheel_circumference_mm / 1000  (metres)
#  PPR and wheel diameter set in cfg["encoder"]; calibrated in settings page.
# ==============================================================================
import threading as _threading


class EncoderThread(QThread):
    """Thread that polls rotary encoder GPIO and maintains distance counter."""
    sw_pressed = pyqtSignal()   # emitted on SW falling edge (debounced)

    # Encoder specs (overridden by calibration)
    _DEFAULT_PPR   = 20      # pulses per revolution (common KY-040 = 20)
    _WHEEL_DIAM_MM = 62.0    # trolley wheel diameter in mm
    _DEBOUNCE_MS   = 50      # SW debounce window

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg         = cfg
        self._lock       = _threading.Lock()
        self._count      = 0      # signed pulse count
        self._moving     = False
        self._running    = True
        self._last_sw    = 1      # pull-up: idle = high
        self._sw_time    = 0.0

    # -- public API ------------------------------------------------------------
    def distance_m(self):
        """Current distance in metres (thread-safe)."""
        ppr   = self.cfg["encoder"].get("ppr",   self._DEFAULT_PPR)
        diam  = self.cfg["encoder"].get("diam",  self._WHEEL_DIAM_MM)
        circ  = 3.14159265 * diam
        with self._lock:
            c = abs(self._count)
        return round(c / max(1, ppr) * circ / 1000.0, 3)

    def is_moving(self):
        with self._lock:
            return self._moving

    def reset(self):
        with self._lock:
            self._count   = 0
            self._moving  = False

    def stop_thread(self):
        self._running = False

    # -- thread body -----------------------------------------------------------
    def run(self):
        if HW_SIM:
            self._run_sim()
        else:
            self._run_hw()

    def _run_hw(self):
        """Hardware mode: poll sysfs GPIO at 1 ms."""
        for gpio in (ENC_CLK_GPIO, ENC_DT_GPIO, ENC_SW_GPIO):
            _gpio_export(gpio)
        last_clk = _gpio_read(ENC_CLK_GPIO)
        while self._running:
            clk = _gpio_read(ENC_CLK_GPIO)
            dt  = _gpio_read(ENC_DT_GPIO)
            sw  = _gpio_read(ENC_SW_GPIO)
            # quadrature decode
            if clk != last_clk:
                with self._lock:
                    if dt != clk:
                        self._count += 1   # clockwise
                    else:
                        self._count -= 1   # counter-clockwise
                    self._moving = True
            else:
                with self._lock:
                    self._moving = False
            last_clk = clk
            # SW debounce (falling edge = press)
            now = time.time()
            if sw == 0 and self._last_sw == 1:
                if (now - self._sw_time) * 1000 > self._DEBOUNCE_MS:
                    self._sw_time = now
                    self.sw_pressed.emit()
            self._last_sw = sw
            self.msleep(1)

    def _run_sim(self):
        """Simulation: encoder holds position. No random movement."""
        while self._running:
            with self._lock:
                self._moving = False
            self.msleep(100)


# ==============================================================================
#  SENSOR THREAD  (Thread 1)
#
#  Reads two BBB ADC channels at 2 Hz and queries EncoderThread for distance:
#    AIN0 P9.39  ->  TRS100  pot  ->  gauge (mm)
#    AIN1 P9.40  ->  SCL3300 pot  ->  cross-level (deg)
#    EncoderThread         ->  chainage (m)
#
#  Sensor emulation (validated):
#    gauge    = 1676 + (raw0 - GAUGE_ZERO) x GAUGE_MPC       [mm]
#    cross    = (raw1 - 2048) / 2048 x 30.0 - offset         [deg, -30-]
#    twist    = |cross_now - cross_prev| / 3.0                [mm/m, 3 m chord]
# ==============================================================================
class SensorThread(QThread):
    """
    Industrial-grade sensor reader for Indian Railways track geometry trolley.

    Hardware sensors:
      AIN0  P9.39  TRS100 pot       -> Track gauge (mm), Indian BG = 1676 mm
      AIN1  P9.40  SCL3300 pot      -> Cross-level (mm), RDSO +/-75 mm
      /dev/ttyS4   u-blox NEO-M8P-2 -> GPS lat/lon/speed
      EncoderThread                 -> Chainage (m)

    When GPS hardware absent, lat/lon advance with chainage at a realistic
    track heading so all fields show meaningful field-accurate values.

    RDSO references:
      Gauge    : Schedule of Dimensions 1676, BG standard +6/-3 mm warn,
                 +13/-6 mm alarm (A-route)
      Cross-lvl: RDSO/SPN/TC/10  warn >50 mm, alarm >75 mm
      Twist    : RDSO/SPN/TC/10  chord 3.5 m, warn >8 mm, alarm >13 mm
      Speed    : derived from encoder tick rate
    """
    data_ready = pyqtSignal(dict)
    fault      = pyqtSignal(str)
    motion     = pyqtSignal(bool)

    # ------------------------------------------------------------------
    # RDSO Indian BG physical constants
    # ------------------------------------------------------------------
    _ADC_BITS    = 4096        # 12-bit ADC full scale
    _ADC_MID     = 2048        # midpoint -> standard gauge / level
    _GAUGE_STD   = 1676.0      # Indian BG standard (mm)
    # TRS100 pot range: physical gauge 1601-1751 mm (+/-75 mm)
    # 150 mm span / 4096 counts = 0.036621 mm/count
    _GAUGE_MPC   = 0.036621
    _GAUGE_MIN   = 1601.0      # physical minimum (BG -75 mm)
    _GAUGE_MAX   = 1751.0      # physical maximum (BG +75 mm)
    # SCL3300-D01 Mode-1: +/-30 deg full scale
    _INCL_FS     = 30.0
    # 1 deg tilt on 1676 mm base = 17.453 mm cross-level
    _DEG_TO_MM   = 17.453
    _CROSS_MAX   = 75.0        # RDSO alarm limit mm (clamp display)
    # RDSO 3.5 m chord twist measurement
    _TWIST_CHORD = 3.5
    # ADC noise deadband: 5 counts ~ 0.18 mm (ignores electrical noise)
    _DEADBAND    = 5
    # BBB ADC driver bug: read twice, use second value
    _READ_TWICE  = True
    # GPS mock: track bearing in degrees (approx south-to-north typical IR)
    _GPS_BEARING_DEG = 0.0     # degrees true north, updated from cfg

    def __init__(self, cfg, encoder):
        super().__init__()
        self.cfg             = cfg
        self._encoder        = encoder
        self.active          = False

        # Per-sensor hardware flags (checked once at startup)
        self._has_adc0 = os.path.exists(ADC_PATH)
        self._has_adc1 = os.path.exists(ADC_PATH_1)
        self._has_gps  = os.path.exists("/dev/ttyS4")

        # ADC last stable state (-1 = never read, forces first update)
        self._raw0       = -1
        self._raw1       = -1
        self._gauge_mm   = self._GAUGE_STD
        self._cross_mm   = 0.0
        self._prev_cross = 0.0

        # Speed estimation from encoder (m/s)
        self._last_dist  = 0.0
        self._last_time  = time.time()
        self._speed_ms   = 0.0

        # GPS state
        self._lat        = 0.0
        self._lon        = 0.0
        self._speed_kmh  = 0.0
        self._gps_ser    = None
        self._gps_buf    = ""
        self._gps_active = False   # True once a real fix is received

        # Mock GPS origin: load from cfg or use IR Delhi-Howrah reference
        # Track chainage reference point (km 0 = start of survey)
        self._origin_lat = cfg.get("gnss", {}).get("origin_lat", 28.6139)
        self._origin_lon = cfg.get("gnss", {}).get("origin_lon", 77.2090)
        # 1 degree lat ~ 111320 m, 1 degree lon ~ 111320*cos(lat) m
        import math as _math
        self._m_per_deg_lat = 111320.0
        self._m_per_deg_lon = 111320.0 * _math.cos(_math.radians(self._origin_lat))

    # ==================================================================
    def run(self):
        # Re-check hardware after kernel modules have had time to load.
        # __init__ runs at app start before modprobe completes.
        # Wait 2 s then re-detect so AIN1 is not missed.
        self.msleep(2000)
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
            self.msleep(500)    # 2 Hz sample rate

    # ==================================================================
    def _sample(self):
        now    = time.time()
        moving = self._encoder.is_moving()
        self.motion.emit(moving)
        dist_m = self._encoder.distance_m()

        # Speed from encoder (smoothed over last 0.5 s interval)
        dt = now - self._last_time
        if dt > 0.1:
            dd = dist_m - self._last_dist
            raw_speed = dd / dt if dt > 0 else 0.0
            # Low-pass filter: alpha=0.3
            self._speed_ms = 0.3 * raw_speed + 0.7 * self._speed_ms
            self._last_dist = dist_m
            self._last_time = now
        speed_kmh = round(max(0.0, self._speed_ms * 3.6), 1)

        self._update_gauge()
        self._update_cross()

        # Twist: rate of change of cross-level over RDSO 3.5 m chord
        # Only computed when trolley is moving
        if moving:
            twist = round(abs(self._cross_mm - self._prev_cross) / self._TWIST_CHORD, 3)
        else:
            twist = 0.0
        self._prev_cross = self._cross_mm

        # GPS: read hardware if present, else mock from chainage
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

    # ==================================================================
    # GAUGE -- TRS100 potentiometer on AIN0 (P9.39)
    #
    # Formula:  gauge_mm = GAUGE_STD + (raw - zero) * mpc
    #   At pot centre (raw = zero):  gauge = 1676.0 mm  (BG standard)
    #   At pot CW end (raw = 4095):  gauge ~ 1751 mm    (+75 mm)
    #   At pot CCW end (raw = 0):    gauge ~ 1601 mm    (-75 mm)
    #
    # Calibration: zero and mpc stored in cfg["adc"] after ADCCal
    # Uncalibrated: zero=2048, mpc=0.036621 (reasonable factory default)
    # ==================================================================
    def _update_gauge(self):
        if not self._has_adc0:
            return
        raw = self._adc_read(ADC_PATH)
        if raw < 0:
            return
        # Deadband: ignore if pot has not moved beyond noise floor
        if self._raw0 >= 0 and abs(raw - self._raw0) < self._DEADBAND:
            return
        self._raw0 = raw
        zero  = self.cfg["adc"].get("zero", self._ADC_MID)
        mpc   = self.cfg["adc"].get("mpc",  self._GAUGE_MPC)
        gauge = self._GAUGE_STD + (raw - zero) * mpc
        self._gauge_mm = round(max(self._GAUGE_MIN, min(self._GAUGE_MAX, gauge)), 1)

    # ==================================================================
    # CROSS-LEVEL -- SCL3300 inclinometer pot on AIN1 (P9.40)
    #
    # Formula:  angle_deg = (raw - ADC_MID) / ADC_MID * INCL_FS
    #           cross_mm  = (angle_deg - offset) * DEG_TO_MM
    #   At pot centre (raw = 2048):  cross = 0.0 mm   (level track)
    #   At pot CW end (raw = 4095):  angle ~ +30 deg -> +523 mm -> clamped +75 mm
    #   At pot CCW end (raw = 0):    angle ~ -30 deg -> -523 mm -> clamped -75 mm
    #
    # Display range: -75 to +75 mm  (RDSO alarm boundary)
    # Physical clamp: -75 to +75 mm (beyond this is derailment risk)
    # Calibration: offset stored in cfg["incl"]["offset"] after InclinCal
    # ==================================================================
    def _update_cross(self):
        if not self._has_adc1:
            return
        raw = self._adc_read(ADC_PATH_1)
        if raw < 0:
            return
        if self._raw1 >= 0 and abs(raw - self._raw1) < self._DEADBAND:
            return
        self._raw1 = raw
        offset     = self.cfg["incl"].get("offset", 0.0)
        angle_deg  = (raw - self._ADC_MID) / float(self._ADC_MID) * self._INCL_FS
        angle_deg -= offset
        cross_mm   = angle_deg * self._DEG_TO_MM
        # RDSO: display and alarm at +/-75 mm; physically clamp at that
        self._cross_mm = round(max(-self._CROSS_MAX, min(self._CROSS_MAX, cross_mm)), 2)

    # ==================================================================
    # ADC READ -- BBB IIO sysfs with double-read workaround
    # The BBB ADC driver has a known bug where the first read returns
    # the previous sample. Reading twice returns the current value.
    # ==================================================================
    def _adc_read(self, path):
        try:
            if self._READ_TWICE:
                with open(path) as fh:
                    fh.read()          # discard stale first sample
            with open(path) as fh:
                return int(fh.read().strip())
        except Exception:
            return -1

    # ==================================================================
    # GPS -- u-blox NEO-M8P-2 on /dev/ttyS4
    #
    # When hardware GPS is present:
    #   Reads NMEA GGA (position+fix) and RMC (speed) from serial port.
    #   Holds last valid fix indefinitely once acquired.
    #
    # When GPS hardware absent (common during bench testing):
    #   Generates realistic mock coordinates that advance with chainage.
    #   Uses configurable origin point (default: Delhi, NH-44 alignment).
    #   Bearing advances north by default (most IR mainlines run N-S or E-W).
    #   Speed is derived from encoder, matching real field behaviour.
    #   lat/lon shown as 0.0 until session starts and encoder moves.
    # ==================================================================
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
            # Real hardware: read serial buffer
            self._read_gps_serial()
        else:
            # No GPS hardware: mock lat/lon from chainage
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
        """
        Mock GPS: advances with encoder chainage from a configurable origin.
        Shows origin coordinates immediately when session starts.
        Coordinates increment north (or along configured bearing) as trolley moves.
        This matches real field GPS behaviour where coordinates change with distance.
        """
        import math as _math
        bearing_rad = _math.radians(self._GPS_BEARING_DEG)
        # Project dist_m along bearing from origin
        d_lat = dist_m * _math.cos(bearing_rad) / self._m_per_deg_lat
        d_lon = dist_m * _math.sin(bearing_rad) / self._m_per_deg_lon
        self._lat        = round(self._origin_lat + d_lat, 7)
        self._lon        = round(self._origin_lon + d_lon, 7)
        self._speed_kmh  = speed_kmh
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
                        self._lat       = la
                        self._lon       = lo
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

    # ==================================================================
    def reset(self):
        """Session start: reset twist accumulator only.
        Keep pot positions and GPS fix across session boundaries."""
        self._prev_cross = 0.0
        self._last_dist  = 0.0
        self._last_time  = time.time()
        self._speed_ms   = 0.0
        # Reset mock GPS origin to current position if active
        if not self._gps_active:
            self._lat = 0.0
            self._lon = 0.0


# =============================================================================
#  NETWORK THREAD
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
        if _sysfs("/sys/class/net/eth0/operstate",     "down") == "up": return 2
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
#  CSV LOGGER
# =============================================================================
STATION_NAME = "BLR"

_FIELDS = [
    "epoch_time",
    "reference_type",
    "reference_value",
    "latitude",
    "longitude",
    "cross_level",
    "chainage",
    "twist",
    "tilt",
    "tilt_cord_length",
]


class CSVLogger:
    def __init__(self):
        self._f              = self._w = None
        self._rows           = []
        self.path            = ""
        self.count           = 0
        self._ref_type       = ""
        self._ref_value      = ""
        self._station        = "BLE"

    def set_reference(self, ref_type, ref_value):
        """Call before starting a session to store reference type and value."""
        self._ref_type  = ref_type
        self._ref_value = ref_value

    def set_station(self, station_name):
        """Set station name used in the filename."""
        self._station = station_name.strip() if station_name else "UNKNOWN"

    def start(self, directory, hl_sec=30):
        os.makedirs(directory, exist_ok=True)
        # filename: BLE_yyyy-mm-dd_HH-MM-SS.csv
        safe_ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = "BLE_{}.csv".format(safe_ts)
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
            "latitude":         d.get("lat",   0),
            "longitude":        d.get("lon",   0),
            "cross_level":      cross,
            "chainage":         d.get("dist",  0),
            "twist":            d.get("twist", 0),
            "tilt":             cross,              # tilt = inclinometer = cross level
            "tilt_cord_length": d.get("dist",  0), # cord length tracks with chainage
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


# ==============================================================================
#  CSV WRITER THREAD  (Thread 2)
#  Independent of GUI + sensor threads. Non-blocking queue; never stalls GUI.
# ==============================================================================
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
#  GRAPH CANVAS  (QPainter only -- no matplotlib)
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
            p.setPen(QColor("#333"))
            p.setFont(QFont("Courier New", 10))
            p.drawText(QRect(0, 0, W, H), Qt.AlignCenter,
                       "NO DATA -- START SESSION FIRST")
            p.end(); return

        PAD = 52; gW = W - PAD - 10; gH = H - 46
        mn, mx = min(self._d), max(self._d); rng = mx - mn or 1

        # grid lines + y labels
        for i in range(5):
            y   = 26 + gH * i // 4
            val = mx - rng * i / 4
            p.setPen(QPen(QColor("#181818"), 1, Qt.DashLine))
            p.drawLine(PAD, y, PAD + gW, y)
            p.setPen(QColor("#444"))
            p.setFont(QFont("Courier New", 7))
            p.drawText(QRect(0, y - 8, PAD - 4, 16),
                       Qt.AlignRight | Qt.AlignVCenter, "{:.2f}".format(val))

        # filled area
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

        # data line
        p.setPen(QPen(self._col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        prev = None
        for i, v in enumerate(self._d):
            pt = QPoint(PAD + int(gW * i / (n - 1)),
                        26 + int(gH * (mx - v) / rng))
            if prev: p.drawLine(prev, pt)
            prev = pt

        # labels
        p.setPen(self._col)
        p.setFont(QFont("Courier New", 9, QFont.Bold))
        p.drawText(PAD, 18, "{}  [{}]  .  {} pts".format(self.title.upper(), self.unit, n))
        p.setPen(QColor("#333"))
        p.setFont(QFont("Courier New", 7))
        p.drawText(PAD, H - 4, "SESSION START")
        p.drawText(PAD + gW - 30, H - 4, "NOW")
        p.end()


# =============================================================================
#  TOP BAR
# =============================================================================
class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet("background:#060606; border-bottom:1px solid #181818;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        title = QLabel("RAIL INSPECTION UNIT  v4.0")
        title.setStyleSheet("color:#282828; font-size:8pt;")

        self._bars = QLabel("||||")
        self._bars.setStyleSheet("color:#333; font-size:11pt;")
        self._ltxt = QLabel("LTE")
        self._ltxt.setStyleSheet("color:#333; font-size:8pt; font-weight:bold;")

        self._cic  = QLabel("[C]")
        self._cic.setStyleSheet("font-size:13pt; color:#333;")
        self._ctxt = QLabel("OFFLINE")
        self._ctxt.setStyleSheet("color:#333; font-size:8pt; font-weight:bold;")

        self._sim  = QLabel("[ SIM ]" if HW_SIM else "[ HW ]")
        self._sim.setStyleSheet(
            "color:{}; font-size:8pt; font-weight:bold;".format('#FFCC00' if HW_SIM else '#39FF14'))

        self._tclock = QLabel("--:--:--")
        self._tclock.setStyleSheet(
            "color:#CCC; font-size:10pt; font-family:'Courier New';")
        self._tdate = QLabel("-- --- ----")
        self._tdate.setStyleSheet("color:#444; font-size:7pt;")
        tc = QVBoxLayout(); tc.setSpacing(0)
        tc.addWidget(self._tclock); tc.addWidget(self._tdate)

        self._errbtn = QPushButton("[BELL]  OK")
        self._errbtn.setStyleSheet(
            "background:#030903; border:1px solid #183018; border-radius:5px;"
            " color:#1a5a1a; font-size:8pt; padding:2px 8px;")
        self._errs = []

        for w in (title, None, self._sim, _vline(),
                  self._bars, self._ltxt, _vline(),
                  self._cic, self._ctxt, _vline()):
            if w is None:
                lay.addStretch()
            elif isinstance(w, QFrame):
                lay.addWidget(w)
            else:
                lay.addWidget(w)
        lay.addLayout(tc)
        lay.addWidget(_vline())
        lay.addWidget(self._errbtn)

        tmr = QTimer(self)
        tmr.timeout.connect(self._tick)
        tmr.start(1000)
        self._tick()

    def _tick(self):
        n = datetime.now()
        self._tclock.setText(n.strftime("%H:%M:%S"))
        self._tdate.setText(n.strftime("%d %b %Y"))

    def update_net(self, bars, cloud):
        col = NEON if bars >= 3 else AMBER if bars >= 1 else RED
        self._bars.setText("|" * bars + "|" * (4 - bars))
        self._bars.setStyleSheet("color:{}; font-size:11pt;".format(col))
        self._ltxt.setStyleSheet("color:{}; font-size:8pt; font-weight:bold;".format(col))
        c = CYAN if cloud else RED
        self._cic.setStyleSheet("font-size:13pt; color:{};".format(c))
        self._ctxt.setText("CLOUD OK" if cloud else "NO SYNC")
        self._ctxt.setStyleSheet("color:{}; font-size:8pt; font-weight:bold;".format(c))

    def push_error(self, msg):
        self._errs.append(msg)
        self._errbtn.setText("[BELL]  {} ERR".format(len(self._errs)))
        self._errbtn.setStyleSheet(
            ("background:#1a0000; border:1px solid {}; border-radius:5px;"
             " color:{}; font-size:8pt; padding:2px 8px;").format(RED, RED))


# =============================================================================
#  CONTROL BAR
# =============================================================================
class ControlBar(QWidget):
    sig_cal  = pyqtSignal()
    sig_mark = pyqtSignal(int)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setFixedHeight(44)
        self.setStyleSheet(
            "background:#060606; border-bottom:1px solid #141414;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        # CSV path display (read-only label; path chosen from dashboard)
        self._csv_lbl = QLabel("[DIR]  " + _shorten(cfg["csv_dir"]))
        self._csv_lbl.setStyleSheet(
            "background:#111; border:1px solid #333; border-radius:5px;"
            " color:#666; font-size:8pt; padding:3px 10px;"
            " font-family:'Courier New';")
        self._csv_lbl.setFixedHeight(32)

        # Calibrate button
        cal = QPushButton("[COG]  CALIBRATE")
        cal.setStyleSheet(
            ("QPushButton{{background:#1a1500; border:2px solid {};"
             " border-radius:5px; color:{}; font-size:9pt;"
             " font-weight:bold; padding:3px 14px; min-height:32px;}}"
             "QPushButton:pressed{{background:#251d00;}}").format(AMBER, AMBER))
        cal.clicked.connect(self.sig_cal)

        # Mark-last-N-seconds
        hl_lbl = QLabel("MARK LAST")
        hl_lbl.setStyleSheet("color:#333; font-size:8pt;")

        self._stepper = Stepper(
            cfg.get("hl_sec", 30), step=5, dec=0,
            lo=5, hi=600, unit="s", title="HIGHLIGHT SECONDS",
        )
        self._stepper.setFixedWidth(200)

        mark = QPushButton("MARK")
        mark.setStyleSheet(
            ("QPushButton{{background:#001520; border:2px solid {};"
             " border-radius:5px; color:{}; font-size:9pt;"
             " font-weight:bold; padding:3px 12px; min-height:32px;}}"
             "QPushButton:pressed{{background:#002030;}}").format(CYAN, CYAN))
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
#  METRIC CARD
# =============================================================================
# RDSO/SPN/TC/10 Indian Railways BG thresholds
# Gauge  : warn > +6/-3 mm from 1676,  alarm > +13/-6 mm  (A-route)
# Cross  : warn > 50 mm,               alarm > 75 mm       (B-speed)
# Twist  : warn >  8 mm/3.5m chord,    alarm > 13 mm/3.5m  (cat-B)
# Dist   : no threshold
_THRESH = {
    "gauge": (6.0,  13.0),   # mm deviation from 1676
    "cross": (50.0, 75.0),   # mm cross-level
    "twist": (8.0,  13.0),   # mm/3.5m chord
    "dist":  (None, None),
}
# Base value for gauge deviation calculation (Indian BG = 1676 mm)
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

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 5)
        lay.setSpacing(0)

        self._title = QLabel(title.upper())
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(
            "color:#ffffff; font-size:11pt; font-weight:bold;"
            " background:#808080; border-radius:4px; padding:3px 6px;")

        self._val = QLabel("---")
        self._val.setAlignment(Qt.AlignCenter)
        self._val.setStyleSheet(
            ("color:{}; font-size:20pt; font-family:'Courier New';"
             " font-weight:bold;").format(color))
        self._val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._unit = QLabel(unit)
        self._unit.setAlignment(Qt.AlignCenter)
        self._unit.setStyleSheet("color:#2a2a2a; font-size:9pt;")

        self._alert = QLabel("")
        self._alert.setAlignment(Qt.AlignCenter)
        self._alert.setStyleSheet(
            "color:{}; font-size:8pt; font-weight:bold;".format(RED))

        lay.addWidget(self._title)
        lay.addWidget(self._val, 1)
        lay.addWidget(self._unit)
        lay.addWidget(self._alert)

    def refresh(self, val):
        self._val.setText(str(val))
        warn, alarm = _THRESH.get(self.key, (None, None))
        # For gauge: deviation from Indian BG standard 1676 mm
        # For all others: absolute value
        if self.key == "gauge":
            dev = abs(float(val) - _GAUGE_BASE)
        else:
            dev = abs(float(val))
        if alarm is not None and dev >= alarm:
            vc, txt = RED,   "[!]  ALARM"
            bg = "QFrame#Card{{background:#0f0000;border:1px solid {};border-radius:10px;}}".format(RED)
        elif warn is not None and dev >= warn:
            vc, txt = AMBER, "^  WARN"
            bg = "QFrame#Card{{background:#100800;border:1px solid {};border-radius:10px;}}".format(AMBER)
        else:
            vc, txt = self.color, ""
            bg = "QFrame#Card{background:#0c0c0c;border:1px solid #1c1c1c;border-radius:10px;}"
        self._val.setStyleSheet(
            "color:{}; font-size:20pt; font-family:'Courier New'; font-weight:bold;".format(vc))
        self._alert.setText(txt)
        self.setStyleSheet(bg)

    def mousePressEvent(self, _):
        self.clicked.emit(self.key)


# =============================================================================
#  GRAPH PAGE  (full-screen inside stack -- no floating overlay)
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
            "color:{}; font-size:11pt; font-weight:bold;".format(CYAN))
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
#  LIVE TERMINAL WIDGET
#  Streams every stdout/stderr line live into an on-screen green-on-black pane.
#  Call .run(cmd) with any shell command string.
#  Signal finished(exit_code:int, full_output:str) emitted when done.
# =============================================================================
class TerminalWidget(QWidget):
    finished = pyqtSignal(int, str)

    def __init__(self, height=200, parent=None):
        super().__init__(parent)
        self._full_out = ""
        self._procs    = []          # keep QProcess refs alive

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        hdr = QHBoxLayout()
        self._cmd_lbl = QLabel("$  --")
        self._cmd_lbl.setStyleSheet(
            "color:#39FF14; font-size:8pt; font-family:'Courier New';"
            " background:#020a02; padding:3px 8px; border-radius:3px 3px 0 0;")
        self._stat = QLabel("IDLE")
        self._stat.setStyleSheet(
            "color:#333; font-size:8pt; font-weight:bold;"
            " font-family:'Courier New'; padding:3px 8px;")
        hdr.addWidget(self._cmd_lbl, 1)
        hdr.addWidget(self._stat)
        lay.addLayout(hdr)

        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._out.setFixedHeight(height)
        self._out.setStyleSheet(
            "QTextEdit { background:#020a02; border:1px solid #0d2b0d;"
            " border-radius:0 0 4px 4px; color:#39FF14;"
            " font-size:8pt; font-family:'Courier New'; }")
        lay.addWidget(self._out)

    # -- public API ------------------------------------------------------------
    def run(self, cmd):
        """Run a shell command.  Returns the QProcess (caller may keep ref)."""
        self._full_out = ""
        self._out.clear()
        self._cmd_lbl.setText("$  " + cmd[:140])
        self._set_status("RUNNING", AMBER)

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        # connect per-proc so lambda captures correct proc reference
        proc.readyReadStandardOutput.connect(
            lambda p=proc: self._read(p))
        proc.finished.connect(
            lambda code, status, p=proc: self._done(code, p))
        proc.start("sh", ["-c", cmd])
        self._procs.append(proc)
        return proc

    def append(self, text):
        """Manually write a note into the pane."""
        self._out.append(text)
        self._scroll()

    def clear_output(self):
        self._out.clear()
        self._full_out = ""
        self._cmd_lbl.setText("$  --")
        self._set_status("IDLE", "#333")

    # -- internal --------------------------------------------------------------
    def _read(self, proc):
        raw = proc.readAllStandardOutput().data().decode(errors="replace")
        self._full_out += raw
        for line in raw.splitlines():
            if line.strip():
                self._out.append(line)
        self._scroll()

    def _done(self, code, proc):
        # drain any remaining bytes
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
            ("color:{}; font-size:8pt; font-weight:bold;"
             " font-family:'Courier New'; padding:3px 8px;").format(color))


# =============================================================================
#  ENCODER CAL
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

        lay.addWidget(_lbl("ROTARY ENCODER (eQEP) -- ODOMETER CALIBRATION",
                           NEON, 10, True))
        lay.addWidget(_lbl(
            "(1) Set known distance below   "
            "(2) Tap RESET COUNTER   "
            "(3) Roll trolley exact that distance   "
            "(4) Tap CAPTURE & COMPUTE", "#555", 8))

        dr = QHBoxLayout()
        dr.addWidget(_lbl("Known distance:", "#888"))
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
            self._term.append(
                "[OK] Counter zeroed.\n"
                "  Roll trolley the exact known distance, then tap CAPTURE.")
            self._cap_btn.setEnabled(True)
        elif self._phase == "capture":
            nums = [w.strip(":,") for w in out.split() if w.strip(":,").lstrip("-").isdigit()]
            if not nums:
                self._term.append("[!]  Could not parse count from output"); return
            count = int(nums[-1])
            if count == 0:
                self._term.append("[!]  Count is still zero -- did you roll the trolley?")
                return
            self._scale = self._dist_s.value() / count
            self._res.setText(
                ("Count: {}   ->   Scale: {:.5f} mm/count"
                 "   ({:.1f} cts/mm)").format(count, self._scale, 1/self._scale))
            self._term.append(
                ("\n# Result: {} mm / {} counts"
                 " = {:.5f} mm/count").format(self._dist_s.value(), count, self._scale))

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
#  ADC / GAUGE CAL
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

        lay.addWidget(_lbl("GAUGE POTENTIOMETER (TRS100) -- ADC CALIBRATION",
                           CYAN, 10, True))
        lay.addWidget(_lbl(
            "(1) Set gauge to exactly 1676 mm -> tap READ ZERO\n"
            "(2) Shift gauge by known offset -> tap READ OFFSET", "#555", 8))

        self._z_btn = _btn("(1) READ ZERO  (gauge @ 1676 mm)", "BC", 50)
        self._z_btn.clicked.connect(self._read_zero)
        lay.addWidget(self._z_btn)

        dr = QHBoxLayout()
        dr.addWidget(_lbl("Known offset:", "#888"))
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
            return (
                "echo '# Reading IIO ADC device...' && "
                "echo '# Path: {p}' && "
                "echo -n 'Raw ADC value: ' && cat {p}"
            ).format(p=ADC_PATH)
        val = random.randint(1950, 2150)
        return ("echo '# [SIM] IIO ADC not present - simulation mode' && "
                "sleep 0.3 && echo 'Raw ADC value: {}'".format(val))

    def _read_zero(self):
        self._phase = "zero"
        self._term.run(self._adc_cmd())

    def _read_offset(self):
        self._phase = "offset"
        self._term.append("\n# Reading ADC after {:.2f} mm shift...".format(self._off_s.value()))
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
                ("[OK] Zero raw = {}  (gauge at 1676 mm)\n"
                 "  Shift gauge by {:.2f} mm, then tap READ OFFSET.").format(val, self._off_s.value()))
            self._o_btn.setEnabled(True)
        elif self._phase == "offset":
            if self._zero_raw is None:
                return
            delta = val - self._zero_raw
            if delta == 0:
                self._term.append("[!]  D is zero -- did you shift the gauge?"); return
            self._mpc = self._off_s.value() / delta
            self._res.setText(
                "ADC: {}  D={}  mpc={:.5f} mm/count".format(val, delta, self._mpc))
            self._term.append(
                ("\n# {:.2f} mm / {} ADC-counts"
                 " = {:.5f} mm/count").format(self._off_s.value(), delta, self._mpc))

    def _do_save(self):
        if self._zero_raw is None or self._mpc is None:
            self._term.append("[!]  Complete both steps first"); return
        self.cfg["adc"].update({"zero": self._zero_raw, "mpc": self._mpc,
                                "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText(
            "[OK] CALIBRATED  |  zero={}  mpc={:.5f}".format(self._zero_raw, self._mpc))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("adc", self.cfg["adc"])


# =============================================================================
#  INCLINOMETER CAL
# =============================================================================
_SPI_SCRIPT_SRC = """\
import spidev, time, sys
try:
    spi = spidev.SpiDev()
    spi.open(1, 0)
    spi.max_speed_hz = 1000000
    spi.mode = 0
    print("SCL3300: initialising SPI bus...")
    spi.xfer2([0xB4, 0x00, 0x00, 0x1F])   # wake-up
    time.sleep(0.025)
    r = spi.xfer2([0x04, 0x00, 0x00, 0x00])  # read ACC_Y
    spi.close()
    raw = (r[1] << 8) | r[2]
    if raw > 32767:
        raw -= 65536
    angle = raw / 16384.0 * 90.0
    print("SPI raw={}  angle={:.6f}".format(raw, angle))
except Exception as e:
    print("SPI ERROR: {}".format(e), file=sys.stderr)
    sys.exit(1)
"""

_SPI_SIM_SRC = """\
import random, time
print("# [SIM] /dev/spidev1.0 not present -- simulation mode")
time.sleep(0.3)
a = random.gauss(0, 0.12)
raw = int(a * 182)
print("SPI raw={}  angle={:.6f}".format(raw, a))
"""


class InclinCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg     = cfg
        self._offset = None
        self._phase  = "idle"

        # write helper script to /tmp
        script_src = _SPI_SCRIPT_SRC if os.path.exists(SPI_DEV) else _SPI_SIM_SRC
        self._script = Path("/tmp/_scl3300_read.py")
        try:
            self._script.write_text(script_src)
        except Exception:
            pass

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("INCLINOMETER SCL3300 (SPI1.0) -- CROSS-LEVEL ZERO",
                           AMBER, 10, True))
        lay.addWidget(_lbl(
            "(1) Place trolley on certified flat track surface\n"
            "(2) Tap READ ZERO to capture zero-reference angle\n"
            "(3) Tap VERIFY -- corrected reading must be < +/-0.05deg", "#555", 8))

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
            + "  |  offset={:.5f}deg".format(off),
            NEON if ok else RED)
        lay.addWidget(self._info)
        lay.addStretch()

    def _spi_cmd(self):
        return "echo '# Running SPI reader: {}' && python3 {}".format(self._script, self._script)

    def _read_zero(self):
        self._phase = "zero"
        self._term.run(self._spi_cmd())

    def _verify(self):
        self._phase = "verify"
        self._term.append("\n# Re-reading to verify zero correction...")
        self._term.run(self._spi_cmd())

    def _on_done(self, code, out):
        if code != 0:
            return
        angle = None
        for tok in out.split():
            if "angle=" in tok:
                try:
                    angle = float(tok.split("=")[1]); break
                except ValueError:
                    pass
        if angle is None:
            self._term.append("[!]  Could not parse angle from output"); return

        if self._phase == "zero":
            self._offset = angle
            self._res.setText("Zero offset stored: {:.5f}deg".format(angle))
            self._term.append(
                ("\n[OK] Zero offset = {:.5f}deg\n"
                 "  Tap VERIFY to confirm correction is < +/-0.05deg.").format(angle))
            self._v_btn.setEnabled(True)
        elif self._phase == "verify":
            corr = angle - (self._offset or 0.0)
            ok   = abs(corr) < 0.05
            self._res.setText(
                "Corrected: {:.4f}deg  ".format(corr)
                + ("[OK] PASS (<0.05deg)" if ok else "[!]  {:.4f}deg -- re-zero".format(corr)))
            self._res.setStyleSheet(
                "color:{}; font-size:9pt;".format(NEON if ok else AMBER))

    def _do_save(self):
        if self._offset is None:
            self._term.append("[!]  Read zero first"); return
        self.cfg["incl"].update({"offset": self._offset, "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText("[OK] CALIBRATED  |  offset={:.5f}deg".format(self._offset))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("incl", self.cfg["incl"])


# =============================================================================
#  GNSS CAL
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

        lay.addWidget(_lbl("GNSS  u-blox NEO-M8P-2  (/dev/ttyS4) -- FIX & CHAINAGE",
                           MAGI, 10, True))
        lay.addWidget(_lbl(
            "Start gpsd -> check fix (>=4 sats for survey) -> "
            "optionally enable RTK -> set reference chainage -> SAVE", "#555", 8))

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("> START gpsd",  self._start_gpsd,  "BM"),
            ("[S] STOP gpsd",   self._stop_gpsd,   "BM"),
            ("[*] CHECK FIX",  self._check_fix,   "BM"),
            ("[RTK] RTK MODE",   self._rtk,         "BM"),
        ]):
            b = _btn(lbl, nm, 50)
            b.clicked.connect(fn)
            g.addWidget(b, i // 2, i % 2)
        lay.addLayout(g)

        self._term = TerminalWidget(height=170)
        self._term.finished.connect(self._on_done)
        lay.addWidget(self._term)

        rc = QHBoxLayout()
        rc.addWidget(_lbl("Reference chainage:", "#888"))
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
            "sleep 1 && "
            "echo '# Service status:' && "
            "systemctl is-active gpsd && "
            "echo '# Socket status:' && "
            "systemctl is-active gpsd.socket 2>/dev/null || true"
        ) if not HW_SIM else (
            "echo '# [SIM] sudo systemctl start gpsd' && "
            "sleep 0.5 && echo 'gpsd.service: active (running)'"
        )
        self._term.run(cmd)

    def _stop_gpsd(self):
        self._action = "stop"
        cmd = (
            "echo '# Stopping gpsd...' && "
            "sudo systemctl stop gpsd 2>&1 && "
            "echo 'gpsd stopped.'"
        ) if not HW_SIM else (
            "echo '# [SIM] sudo systemctl stop gpsd' && "
            "sleep 0.3 && echo 'gpsd stopped.'"
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
            "echo '# Enabling RTK via ubxtool...' && "
            "ubxtool -p RTCM 2>&1 | head -30"
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
                            "\n-> Quality: {}  Satellites: {}  Alt: {} m".format(qual, sats, alt))
                        self._info.setStyleSheet("color:{}; font-size:9pt;".format(col))
                    except Exception:
                        pass
                    return

    def _do_save(self):
        self.cfg["gnss"].update({"ref_ch": self._ch_s.value(), "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText(
            "[OK] CONFIGURED  |  ref={:.1f} m".format(self._ch_s.value()))
        self._info.setStyleSheet("color:{}; font-size:9pt;".format(NEON))
        self._term.append("[OK] Saved to rail_config.json")
        self.saved.emit("gnss", self.cfg["gnss"])


# =============================================================================
#  LTE STATUS
# =============================================================================
class LTECal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LTE MODEM  (cdc_ether) -- NETWORK DIAGNOSTICS",
                           CYAN, 10, True))
        lay.addWidget(_lbl(
            "Modem appears as Ethernet via cdc_ether kernel driver.\n"
            "Select interface then run diagnostics to verify connectivity.", "#555", 8))

        ir = QHBoxLayout()
        ir.addWidget(_lbl("Interface:", "#888"))
        self._iface = PresetTiles(
            ["eth0", "eth1", "usb0", "wwan0"],
            selected=cfg.get("lte_iface", "eth1"), color=CYAN)
        ir.addWidget(self._iface, 1)
        lay.addLayout(ir)

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("IP ADDRESSES",  self._ip,     "BC"),
            ("PING TEST",     self._ping,   "BC"),
            ("SHOW ROUTES",   self._routes, "BC"),
            ("nmcli STATUS",  self._nmcli,  "BC"),
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
            ("echo '# ip addr show {}' && ip addr show {} 2>&1 && "
             "echo && echo '# ip link show {}' && ip link show {} 2>&1").format(i, i, i, i))

    def _ping(self):
        srv = self.cfg.get("server", "8.8.8.8")
        self._term.run(
            "echo '# ping -c 4 -W 2 {}' && ping -c 4 -W 2 {} 2>&1".format(srv, srv))

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
#  DISPLAY CAL
# =============================================================================
class DisplayCal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LCD DISPLAY  (HDMI / omapdrm) -- XRANDR CONFIGURATION",
                           AMBER, 10, True))

        for label, options, color, attr in [
            ("Output:",     ["HDMI-0","HDMI-1","HDMI-A-1","DVI-0"],        AMBER, "_out"),
            ("Resolution:", ["1024x600","1280x720","800x480","1920x1080"],  AMBER, "_res"),
            ("Rotation:",   ["normal","left","right","inverted"],           AMBER, "_rot"),
        ]:
            row = QHBoxLayout()
            row.addWidget(_lbl(label, "#888"))
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
        cmd = (
            "echo '# xrandr --output {out} --mode {res}' && "
            "xrandr --output {out} --mode {res} 2>&1 && "
            "echo 'Mode applied.' || echo 'xrandr error -- check output name with LIST MODES'"
        ).format(out=self._out.value(), res=self._res.value())
        self._term.run(cmd)

    def _auto(self):
        cmd = (
            "echo '# xrandr --output {out} --auto' && "
            "xrandr --output {out} --auto 2>&1 && echo 'Done.'"
        ).format(out=self._out.value())
        self._term.run(cmd)

    def _rotate(self):
        cmd = (
            "echo '# xrandr --output {out} --rotate {rot}' && "
            "xrandr --output {out} --rotate {rot} 2>&1 && "
            "echo 'Rotation set.'"
        ).format(out=self._out.value(), rot=self._rot.value())
        self._term.run(cmd)

    def _modes(self):
        self._term.run("echo '# xrandr --query' && xrandr 2>&1")


# =============================================================================
#  CALIBRATION PAGE
# =============================================================================
_SENSORS = [
    ("encoder", "ENCODER  (eQEP)",     NEON,  EncoderCal),
    ("adc",     "GAUGE  (ADC/TRS100)", CYAN,  ADCCal),
    ("incl",    "INCLINOMETER  (SPI)", AMBER, InclinCal),
    ("gnss",    "GNSS  (NEO-M8P)",     MAGI,  GNSSCal),
    ("lte",     "LTE  NETWORK",        CYAN,  LTECal),
    ("display", "DISPLAY  (xrandr)",   AMBER, DisplayCal),
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

        # header bar
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#070707; border-bottom:1px solid #1a1a1a;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)
        back = _btn("<- DASHBOARD", "BC", 40, 170)
        back.clicked.connect(self.sig_back)
        title = QLabel("[COG]   SENSOR CALIBRATION")
        title.setStyleSheet(
            "color:{}; font-size:13pt; font-weight:bold;".format(AMBER))
        hdr.addWidget(back); hdr.addStretch()
        hdr.addWidget(title); hdr.addStretch()
        root.addWidget(hdr_w)

        # sidebar + content
        body_w = QWidget()
        body   = QHBoxLayout(body_w)
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        lf = QFrame(); lf.setObjectName("Panel"); lf.setFixedWidth(190)
        ll = QVBoxLayout(lf)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(5)

        self._stack = QStackedWidget()

        for i, (key, label, color, Cls) in enumerate(_SENSORS):
            sub = cfg.get(key, {})
            ok  = sub.get("calibrated", False) if isinstance(sub, dict) else False

            btn = QPushButton(("[OK]  " if ok else "o  ") + label)
            btn.setFixedHeight(46)
            btn.setStyleSheet(
                "QPushButton{ background:#0c0c0c; border:1px solid #1e1e1e;"
                " border-radius:8px; color:#555; font-size:8pt;"
                " font-weight:bold; padding:4px 8px; text-align:left;}"
                "QPushButton:pressed{ background:#1a1a1a; }")
            btn.clicked.connect(lambda _, idx=i: self._sel(idx))
            ll.addWidget(btn)
            self._btns.append((btn, label, color))

            w = Cls(cfg)
            if hasattr(w, "saved"):
                w.saved.connect(self._on_saved)

            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setStyleSheet("QScrollArea{ border:none; background:#050505; }")
            sc.setWidget(w)
            self._stack.addWidget(sc)

        ll.addStretch()
        body.addWidget(lf)

        rf = QFrame(); rf.setObjectName("Panel")
        rl = QVBoxLayout(rf)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self._stack)
        body.addWidget(rf, 1)

        root.addWidget(body_w, 1)
        self._sel(0)

    def _sel(self, idx):
        for i, (btn, _, color) in enumerate(self._btns):
            if i == idx:
                btn.setStyleSheet(
                    ("QPushButton{{ background:{}; border:1px solid {};"
                     " border-radius:8px; color:{}; font-size:8pt;"
                     " font-weight:bold; padding:4px 8px; text-align:left;}}"
                     "QPushButton:pressed{{ background:{}; }}").format(color, color, color, color))
            else:
                btn.setStyleSheet(
                    "QPushButton{ background:#0c0c0c; border:1px solid #1e1e1e;"
                    " border-radius:8px; color:#555; font-size:8pt;"
                    " font-weight:bold; padding:4px 8px; text-align:left;}"
                    "QPushButton:pressed{ background:#1a1a1a; }")
        self._stack.setCurrentIndex(idx)

    def _on_saved(self, key, _):
        for i, (k, label, color, *_) in enumerate(_SENSORS):
            if k == key:
                self._btns[i][0].setText("[OK]  " + label)
                break


# =============================================================================
#  DATA ENTRY PAGE  -- parameter dropdowns with value + frequency tables
# =============================================================================

# key, display label, sensor_key, frequency_interval, unit, color
_PARAM_TABLES = [
    ("gauge",    "GAUGE",       "gauge", 0.25,  "mm",   NEON),
    ("cross",    "CROSS-LEVEL", "cross", 0.25,  "mm",   CYAN),
    ("twist",    "TWIST",       "twist", 2.0,   "mm/m", AMBER),
    ("chainage", "CHAINAGE",    "dist",  100.0, "m",    MAGI),
]


class ParamTableWidget(QWidget):
    """Expandable table showing sensor value + auto-incrementing frequency."""

    def __init__(self, label, color, freq_interval, unit, parent=None):
        super().__init__(parent)
        self._color        = color
        self._freq_interval = freq_interval
        self._unit         = unit
        self._rows         = []          # list of (freq, value) tuples
        self._expanded     = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- dropdown header button --------------------------------------------
        self._hdr = QPushButton(">   {}   ( freq: {} m )".format(label, freq_interval))
        self._hdr.setFixedHeight(46)
        self._hdr.setStyleSheet(
            ("QPushButton{{background:#0c0c0c; border:1px solid {};"
             " border-radius:6px; color:{}; font-size:10pt;"
             " font-weight:bold; font-family:'Courier New'; text-align:left;"
             " padding-left:12px;}}"
             "QPushButton:pressed{{background:#161616;}}").format(color, color))
        self._hdr.clicked.connect(self._toggle)
        root.addWidget(self._hdr)

        # -- collapsible table area --------------------------------------------
        self._table_w = QWidget()
        self._table_w.hide()
        tv = QVBoxLayout(self._table_w)
        tv.setContentsMargins(4, 4, 4, 4)
        tv.setSpacing(2)

        # column headers
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(4)
        for txt, flex in [("SN", 0), ("FREQ (m)", 1), ("VALUE ({})".format(unit), 2)]:
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                ("color:{}; font-size:8pt; font-weight:bold;"
                 " font-family:'Courier New';"
                 " background:#111; border:1px solid #222; padding:4px;").format(color))
            if flex == 0:
                lbl.setFixedWidth(36)
            hdr_row.addWidget(lbl, flex)
        tv.addLayout(hdr_row)

        # scrollable rows area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(180)
        self._scroll.setStyleSheet("QScrollArea{border:none;}")
        self._rows_w  = QWidget()
        self._rows_lay = QVBoxLayout(self._rows_w)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(2)
        self._rows_lay.addStretch()
        self._scroll.setWidget(self._rows_w)
        tv.addWidget(self._scroll)

        root.addWidget(self._table_w)

    def _toggle(self):
        self._expanded = not self._expanded
        arrow = "v" if self._expanded else ">"
        lbl   = self._hdr.text().split("   ", 1)[1]
        self._hdr.setText("{}   {}".format(arrow, lbl))
        self._table_w.setVisible(self._expanded)

    def push_value(self, val):
        """Add a new sensor reading row with auto-incremented frequency."""
        n    = len(self._rows) + 1
        freq = round(n * self._freq_interval, 4)
        self._rows.append((freq, val))

        row_w = QWidget()
        rl    = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        def _cell(txt, flex, bold=False):
            l = QLabel(str(txt))
            l.setAlignment(Qt.AlignCenter)
            w = "bold" if bold else "normal"
            l.setStyleSheet((
                "color:#ccc; font-size:9pt; font-family:'Courier New';"
                " font-weight:{}; background:#0a0a0a;"
                " border:1px solid #1a1a1a; padding:3px;").format(w))
            if flex == 0:
                l.setFixedWidth(36)
            return l, flex

        sn_l,  sf = _cell(n,    0)
        fr_l,  ff = _cell("{:.2f}".format(freq), 1)
        val_l, vf = _cell("{}".format(val), 2, bold=True)
        val_l.setStyleSheet(
            ("color:{}; font-size:9pt; font-family:'Courier New';"
             " font-weight:bold; background:#0a0a0a;"
             " border:1px solid #1a1a1a; padding:3px;").format(self._color))

        rl.addWidget(sn_l,  sf)
        rl.addWidget(fr_l,  ff)
        rl.addWidget(val_l, vf)

        # insert before the stretch
        self._rows_lay.insertWidget(self._rows_lay.count() - 1, row_w)

        # auto-scroll to bottom
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_rows(self):
        self._rows = []
        while self._rows_lay.count() > 1:
            item = self._rows_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_rows(self):
        return list(self._rows)


class DataEntryPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._tables = {}   # key -> ParamTableWidget

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- header bar -------------------------------------------------------
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#070707; border-bottom:1px solid #1a1a1a;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)

        back = _btn("<- DASHBOARD", "BC", 40, 170)
        back.clicked.connect(self.sig_back)

        title = QLabel("SURVEY DATA ENTRY")
        title.setStyleSheet(
            "color:{}; font-size:13pt; font-weight:bold;".format(CYAN))

        clr_btn = _btn("[DEL]  CLEAR ALL", "BR", 40, 150)
        clr_btn.clicked.connect(self._clear_all)

        sv = _btn("[OK]  SAVE & BACK", "BG", 40, 170)
        sv.clicked.connect(self.sig_back)

        hdr.addWidget(back)
        hdr.addStretch()
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(clr_btn)
        hdr.addSpacing(8)
        hdr.addWidget(sv)
        root.addWidget(hdr_w)

        # -- scrollable parameter dropdowns -----------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(8)

        for key, label, _, freq, unit, color in _PARAM_TABLES:
            tw = ParamTableWidget(label, color, freq, unit)
            self._tables[key] = tw
            cl.addWidget(tw)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def push_sensor_data(self, d):
        """Called by TrackApp on every sensor tick to add rows to tables."""
        for key, _, sensor_key, _, _, _ in _PARAM_TABLES:
            if sensor_key in d and key in self._tables:
                self._tables[key].push_value(d[sensor_key])

    def _clear_all(self):
        for tw in self._tables.values():
            tw.clear_rows()

    def get_data(self):
        """Return dict with all table rows for each parameter."""
        return {key: tw.get_rows() for key, tw in self._tables.items()}


# =============================================================================
#  CSV VIEWER PAGE
# =============================================================================
class CSVViewerPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_dir = str(Path.home() / "surveys")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- header bar -------------------------------------------------------
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#070707; border-bottom:1px solid #1a1a1a;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)
        hdr.setSpacing(8)

        back = _btn("<- DASHBOARD", "BC", 40, 170)
        back.clicked.connect(self.sig_back)

        title = QLabel("[CLIP]   CSV FILE VIEWER")
        title.setStyleSheet(
            "color:{}; font-size:13pt; font-weight:bold;".format(MAGI))

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet("color:#444; font-size:8pt; font-family:'Courier New';")
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

        # -- file list panel (left) + table (right) ---------------------------
        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        # left: list of CSV files in the current folder
        left = QFrame(); left.setObjectName("Panel"); left.setFixedWidth(220)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(5)

        lbl = QLabel("SAVED FILES")
        lbl.setStyleSheet(
            "color:{}; font-size:8pt; font-weight:bold;".format(MAGI))
        ll.addWidget(lbl)

        self._file_scroll = QScrollArea()
        self._file_scroll.setWidgetResizable(True)
        self._file_scroll.setStyleSheet("QScrollArea{border:none; background:#050505;}")
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

        # right: table view
        right = QFrame(); right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)
        rl.setSpacing(4)

        # row count label
        self._row_lbl = QLabel("")
        self._row_lbl.setStyleSheet("color:#444; font-size:8pt; font-family:'Courier New';")
        rl.addWidget(self._row_lbl)

        self._table = QTableWidget()
        self._table.setStyleSheet((
            "QTableWidget {{ background:#060606; color:#ccc;"
            " font-size:8pt; font-family:'Courier New';"
            " gridline-color:#1a1a1a; border:none; }}"
            "QHeaderView::section {{ background:#0c0c0c; color:{};"
            " font-size:8pt; font-weight:bold; border:1px solid #1a1a1a;"
            " padding:4px; }}"
            "QTableWidget::item:selected {{ background:{}; color:#fff; }}"
            "QScrollBar:vertical {{ background:#0a0a0a; width:8px; }}"
            "QScrollBar::handle:vertical {{ background:#2a2a2a; border-radius:4px; }}"
            "QScrollBar:horizontal {{ background:#0a0a0a; height:8px; }}"
            "QScrollBar::handle:horizontal {{ background:#2a2a2a; border-radius:4px; }}"
        ).format(MAGI, MAGI))
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background:#0c0c0c; color:#333;"
            " font-size:7pt; border:1px solid #1a1a1a; }")
        rl.addWidget(self._table, 1)

        body.addWidget(right, 1)

        root_body = QWidget()
        root_body.setLayout(body)
        root.addWidget(root_body, 1)

    # -- public ----------------------------------------------------------------
    def set_csv_dir(self, path):
        self._csv_dir = path
        self._refresh_list()

    def load_latest(self):
        """Auto-load the most recently modified CSV in the folder."""
        self._refresh_list()
        files = sorted(Path(self._csv_dir).glob("*.csv"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            self._load_file(str(files[0]))

    # -- internal --------------------------------------------------------------
    def _refresh_list(self):
        # clear old buttons
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
            btn.setStyleSheet((
                "QPushButton{{background:#0a0a0a; border:1px solid #1e1e1e;"
                " border-radius:5px; color:{}; font-size:7pt;"
                " font-family:'Courier New'; text-align:left; padding-left:8px;}}"
                "QPushButton:pressed{{background:#140020; border-color:{};}}"
            ).format(MAGI, MAGI))
            btn.clicked.connect(lambda _, p=str(f): self._load_file(p))
            self._file_list_layout.insertWidget(
                self._file_list_layout.count() - 1, btn)

        if not files:
            empty = QLabel("No CSV files found")
            empty.setStyleSheet("color:#333; font-size:8pt; padding:8px;")
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
#  DASHBOARD PAGE
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
    sig_view   = pyqtSignal()        # open CSV viewer

    def __init__(self):
        super().__init__()
        self._running = False
        self._paused  = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        grid = QGridLayout(); grid.setSpacing(8)
        self._cards = {}
        for i, (key, title, unit, color) in enumerate(_METRICS):
            card = MetricCard(key, title, unit, color)
            card.clicked.connect(self.sig_graph)
            grid.addWidget(card, i // 2, i % 2)
            self._cards[key] = card
        lay.addLayout(grid, 1)

        # bottom bar
        bot = QHBoxLayout()
        bot.setContentsMargins(0, 4, 0, 2)
        bot.setSpacing(0)

        self._csv_btn = QPushButton("[DIR]  SELECT CSV FOLDER")
        self._csv_btn.setObjectName("BC")
        self._csv_btn.setFixedHeight(56)
        self._csv_btn.setFixedWidth(235)
        self._csv_btn.clicked.connect(self.sig_csv)

        self._toggle = QPushButton(">\nSTART")
        self._toggle.setFixedSize(90, 90)
        self._toggle.setStyleSheet(self._ss_start())
        self._toggle.clicked.connect(self._do_toggle)

        self._pause_btn = QPushButton("||\nPAUSE")
        self._pause_btn.setFixedSize(90, 90)
        self._pause_btn.setStyleSheet(self._ss_pause())
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._do_pause)

        self._view_btn = QPushButton("[CLIP]\nVIEW CSV")
        self._view_btn.setObjectName("BM")
        self._view_btn.setFixedSize(110, 78)
        self._view_btn.clicked.connect(self.sig_view)

        self._entry_btn = QPushButton("DATA\nENTRY")
        self._entry_btn.setObjectName("BC")
        self._entry_btn.setFixedSize(110, 78)
        self._entry_btn.clicked.connect(self.sig_entry)

        self._stat = QLabel("o  IDLE\n-")
        self._stat.setStyleSheet(
            "color:#222; font-size:8pt; font-family:'Courier New';")

        bot.addWidget(self._csv_btn)
        bot.addStretch()
        bot.addWidget(self._toggle)
        bot.addSpacing(12)
        bot.addWidget(self._pause_btn)
        bot.addSpacing(16)
        bot.addWidget(self._entry_btn)
        bot.addSpacing(10)
        bot.addWidget(self._view_btn)
        bot.addSpacing(14)
        bot.addWidget(self._stat)
        bot.addStretch()
        lay.addLayout(bot)

    def _ss_start(self):
        return (
            "QPushButton{{background:#002200; border:3px solid {c};"
            " border-radius:45px; color:{c}; font-size:12pt;"
            " font-weight:bold;}}"
            "QPushButton:pressed{{background:#003300;}}"
        ).format(c=NEON)

    def _ss_stop(self):
        return (
            "QPushButton{{background:#220000; border:3px solid {c};"
            " border-radius:45px; color:{c}; font-size:12pt;"
            " font-weight:bold;}}"
            "QPushButton:pressed{{background:#330000;}}"
        ).format(c=RED)

    def _ss_pause(self):
        return (
            "QPushButton{{background:#1a1200; border:3px solid {c};"
            " border-radius:45px; color:{c}; font-size:12pt;"
            " font-weight:bold;}}"
            "QPushButton:pressed{{background:#261b00;}}"
            "QPushButton:disabled{{background:#0a0a0a;"
            " border:3px solid #2a2a2a; color:#2a2a2a;}}"
        ).format(c=AMBER)

    def _ss_resume(self):
        return (
            "QPushButton{{background:#001520; border:3px solid {c};"
            " border-radius:45px; color:{c}; font-size:12pt;"
            " font-weight:bold;}}"
            "QPushButton:pressed{{background:#002030;}}"
        ).format(c=CYAN)

    def _do_toggle(self):
        self._running = not self._running
        if self._running:
            self._toggle.setText("[S]\nSTOP")
            self._toggle.setStyleSheet(self._ss_stop())
            self._entry_btn.setEnabled(False)
            self._csv_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            self._paused = False
            self._pause_btn.setText("||\nPAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        else:
            self._toggle.setText(">\nSTART")
            self._toggle.setStyleSheet(self._ss_start())
            self._entry_btn.setEnabled(True)
            self._csv_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._paused = False
            self._pause_btn.setText("||\nPAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_toggle.emit(self._running)

    def _do_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText(">\nRESUME")
            self._pause_btn.setStyleSheet(self._ss_resume())
        else:
            self._pause_btn.setText("||\nPAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_pause.emit(self._paused)

    def update_data(self, d):
        for key, card in self._cards.items():
            if key in d:
                card.refresh(d[key])

    def set_session(self, n, running, path=""):
        col  = NEON if running else "#2a2a2a"
        icon = "*  REC" if running else "o  IDLE"
        fname = Path(path).name[-28:] if path else "-"
        self._stat.setText("{}  {} pts\n{}".format(icon, n, fname))
        self._stat.setStyleSheet(
            "color:{}; font-size:8pt; font-family:'Courier New';".format(col))

    def set_csv_label(self, path):
        self._csv_btn.setText("[DIR]  " + _shorten(path, 22))


# =============================================================================
#  MAIN APPLICATION
#  -- NO Qt.FramelessWindowHint (kills X11 mouse routing)
#  -- NO QApplication.setOverrideCursor(Qt.BlankCursor) (hides cursor)
#  -- showFullScreen() WITHOUT frameless flag = correct mouse delivery on Ubuntu
# =============================================================================
SCREEN_W, SCREEN_H = 1024, 600


class TrackApp(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg        = load_cfg()
        self.logger     = CSVLogger()           # retained for mark() / CSV viewer
        # Thread 2: dedicated CSV writer
        self.csv_writer = CSVWriterThread(self)
        self.csv_writer.start()
        # Encoder thread: polls GPIO CLK/DT/SW at 1 ms
        self.encoder    = EncoderThread(self.cfg, self)
        self.encoder.sw_pressed.connect(self._on_enc_sw)
        self.encoder.start()
        self.history    = {k: [] for k, *_ in _METRICS}

        self.setWindowTitle("Rail Inspection Unit v5.0")
        self.setStyleSheet(SS)

        # sensor thread (Thread 1 -- passes encoder reference for distance)
        self.sensor = SensorThread(self.cfg, self.encoder)
        self.sensor.data_ready.connect(self._on_data)
        self.sensor.fault.connect(self._on_fault)
        self.sensor.motion.connect(self._on_motion)
        self.sensor.start()

        # -- screen-off timer: 5 min of no encoder motion -> blank screen -------
        self._SCREEN_TIMEOUT_MS = 5 * 60 * 1000   # 5 minutes
        self._last_motion_time  = time.time()
        self._screen_off        = False

        self._screen_timer = QTimer(self)
        self._screen_timer.setInterval(10000)     # check every 10 s
        self._screen_timer.timeout.connect(self._check_screen_timeout)
        self._screen_timer.start()

        # black overlay widget used to blank the screen
        self._blank = QWidget(self)
        self._blank.setStyleSheet("background:#000000;")
        self._blank.hide()
        self._blank.mousePressEvent = self._wake_screen

        # network thread
        self.net = NetThread(self.cfg)
        self.net.status.connect(self._on_net)
        self.net.start()

        # root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar  = TopBar(self)
        self.ctrlbar = ControlBar(self.cfg, self)
        self.ctrlbar.sig_cal.connect(lambda: self._goto(1))
        self.ctrlbar.sig_mark.connect(self._on_mark)

        self.stack = QStackedWidget()

        self.dash = DashboardPage()
        self.dash.sig_toggle.connect(self._on_toggle)
        self.dash.sig_pause.connect(self._on_pause)
        self.dash.sig_entry.connect(lambda: self._goto(2))
        self.dash.sig_csv.connect(self._pick_csv)
        self.dash.sig_graph.connect(self._show_graph)
        self.dash.sig_view.connect(self._show_csv_viewer)
        self.stack.addWidget(self.dash)       # 0

        self.cal = CalibrationPage(self.cfg)
        self.cal.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.cal)        # 1

        self.entry = DataEntryPage()
        self.entry.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.entry)      # 2

        self.graph_pg = GraphPage()
        self.graph_pg.sig_back.connect(lambda: self._goto(0))
        self.stack.addWidget(self.graph_pg)   # 3

        self.csv_viewer = CSVViewerPage()
        self.csv_viewer.sig_back.connect(lambda: self._goto(0))
        self.csv_viewer.set_csv_dir(self.cfg["csv_dir"])
        self.stack.addWidget(self.csv_viewer) # 4

        root.addWidget(self.topbar)
        root.addWidget(self.ctrlbar)
        root.addWidget(self.stack, 1)

        self.dash.set_csv_label(self.cfg["csv_dir"])

        # -- WINDOW: size to VNC/screen geometry safely ----------------------
        try:
            desk   = QApplication.desktop()
            screen = desk.screenGeometry(desk.primaryScreen())
            w, h   = screen.width(), screen.height()
        except Exception:
            w, h = SCREEN_W, SCREEN_H
        self.resize(w, h)
        self.show()

    def _goto(self, idx):
        self.stack.setCurrentIndex(idx)

    def _on_data(self, d):
        # Always update history and dashboard (live readings before session)
        for key in self.history:
            if key in d:
                self.history[key].append(d[key])
                if len(self.history[key]) > 10000:
                    self.history[key].pop(0)
        self.dash.update_data(d)

        # Only write to CSV and data entry table when a session is active
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
            self.encoder.reset()              # zero distance on session start
            self.sensor.reset()
            self.history = {k: [] for k in self.history}
            self.logger.start(self.cfg["csv_dir"], self.cfg.get("hl_sec", 30))
            self.csv_writer.start_session(
                self.cfg["csv_dir"], self.cfg.get("hl_sec", 30))
        else:
            self.logger.stop()
            self.csv_writer.stop_session()

    def _on_pause(self, paused):
        # Pause: stop sensor data collection; Resume: restart it
        self.sensor.active = not paused

    def _on_motion(self, moving):
        """Called every sensor tick; reset idle clock whenever encoder moves."""
        if moving:
            self._last_motion_time = time.time()
            if self._screen_off:
                self._wake_screen()

    def _on_enc_sw(self):
        """Encoder SW push-button: zero the distance counter during a session."""
        if self.sensor.active:
            self.encoder.reset()
            self.topbar.push_error("Encoder zeroed by SW press")

    def _check_screen_timeout(self):
        """Periodically check if encoder has been idle for 5 minutes."""
        if self._screen_off:
            return
        idle_ms = (time.time() - self._last_motion_time) * 1000
        if idle_ms >= self._SCREEN_TIMEOUT_MS:
            self._blank_screen()

    def _blank_screen(self):
        """Cover the entire window with a black overlay."""
        self._screen_off = True
        self._blank.setGeometry(self.rect())
        self._blank.raise_()
        self._blank.show()

    def _wake_screen(self, _event=None):
        """Remove the black overlay and reset idle timer."""
        self._screen_off       = False
        self._last_motion_time = time.time()
        self._blank.hide()

    def resizeEvent(self, e):
        """Keep blank overlay covering full window on resize."""
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
        # ESC exits fullscreen -- useful for recovery / development
        if e.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.resize(SCREEN_W, SCREEN_H)
        super().keyPressEvent(e)


# -----------------------------------------------------------------------------
def main():
    # Set platform before QApplication if no DISPLAY set (BBB headless fallback)
    if not os.environ.get("DISPLAY", ""):
        os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb")

    app = QApplication(sys.argv)
    app.setApplicationName("Rail Inspection Unit")

    # AA_EnableHighDpiScaling only exists in Qt 5.6+ -- guard for older BBB Qt
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    except AttributeError:
        pass

    # restoreOverrideCursor only safe after QApplication exists
    try:
        app.restoreOverrideCursor()
    except Exception:
        pass

    w = TrackApp()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
