#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rail Track Geometry Inspection System
Target  : BeagleBone Black Industrial | Ubuntu | 1024×600 HDMI/Touch
Stack   : PyQt5 | Python 3.8+
Version : 4.0.0 — touch + mouse, all features working

Sensor map:
  Rotary Encoder   → eQEP → /sys/…/eqep/counter/count0/count
  Gauge Pot(TRS100)→ ADC  → /sys/bus/iio/devices/iio:device0/in_voltage0_raw
  Inclinometer     → SPI  → /dev/spidev1.0  (Murata SCL3300)
  GNSS             → UART → /dev/ttyS4      (u-blox NEO-M8P-2)
  LTE              → ETH  → eth1            (cdc_ether)
  Display          → HDMI → omapdrm / xrandr
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
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess, QPoint, QRect, QSize, QEvent
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush, QLinearGradient, QPainterPath,
)

# ─────────────────────────────────────────────────────────────────────────────
#  PALETTE
# ─────────────────────────────────────────────────────────────────────────────
# ── ISO RESTYLE ──
BG    = "#ECEFF4"
CARD  = "#FFFFFF"
NEON  = "#1B8A4C"    # Track Gauge green
CYAN  = "#1565C0"    # Cross Level blue
AMBER = "#C06000"    # Twist amber
RED   = "#C62828"    # Alarm red
MAGI  = "#5E35B1"    # Distance violet
HEADER_BG     = "#1E2430"   # status bar bg
HEADER_ACCENT = "#1B8A4C"   # accent green

# light tints
NEON_LT  = "#E6F4EE"
CYAN_LT  = "#E3EEFA"
AMBER_LT = "#FFF3E0"
MAGI_LT  = "#EDE7F6"
RED_LT   = "#FFEBEE"
WARN     = "#E65100"
WARN_LT  = "#FFF3E0"

W, H = 1024, 600          # target display

# ─────────────────────────────────────────────────────────────────────────────
#  GLOBAL STYLESHEET
# ─────────────────────────────────────────────────────────────────────────────
# ── ISO RESTYLE ──
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
    padding: 4px 18px;
    min-height: 34px;
}
QPushButton#BC:hover     { background: #F5FAFF; border-color: #0D4A8A; color: #0D4A8A; }
QPushButton#BC:pressed   { background: #E3EEFA; border-color: #0D4A8A; color: #0D4A8A; }
QPushButton#BC:disabled  { background: #F8FAFB; border-color: #C8D0DA; color: #A0AAB8; }
QPushButton#BC:focus     { border: 2px solid #1565C0; }

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


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────
CFG_PATH  = Path(__file__).parent / "rail_config.json"
_DEF = {
    "csv_dir":   str(Path.home() / "surveys"),
    "hl_sec":    30,
    "server":    "8.8.8.8",
    "lte_iface": "eth1",
    "encoder":   {"scale": 1.0,  "factor": 1.0, "calibrated": False},
    "adc":       {"zero": 2048,  "mpc": 0.0684, "factor": 1.0, "calibrated": False},
    "incl":      {"offset": 0.0, "factor": 1.0, "calibrated": False},
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
        print(f"[CFG] {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  HARDWARE
# ─────────────────────────────────────────────────────────────────────────────
EQEP_PATH = ("/sys/devices/platform/ocp/48304000.epwmss"
             "/48304180.eqep/counter/count0/count")
ADC_PATH  = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
SPI_DEV   = "/dev/spidev1.0"
HW_SIM    = not os.path.exists(EQEP_PATH)


def _sysfs(path, default="0"):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _lbl(text, color="#888", pt=9, bold=False):
    l = QLabel(text)
    w = "bold" if bold else "normal"
    l.setStyleSheet(f"color:{color}; font-size:{pt}pt; font-weight:{w};")
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
    f.setStyleSheet("color:#1a1a1a; max-width:1px;")
    return f


def _btn(label, name, h=48, w=None):
    b = QPushButton(label)
    b.setObjectName(name)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    return b


def _shorten(path, n=34):
    return ("…" + path[-(n - 1):]) if len(path) > n else path


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


# ═════════════════════════════════════════════════════════════════════════════
#  NUMPAD DIALOG
#  — plain QDialog (no frameless), styled dark; always fits inside 1024×600
# ═════════════════════════════════════════════════════════════════════════════
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
            f"color:{CYAN}; font-size:11pt; font-weight:bold; letter-spacing:2px;"
        )
        root.addWidget(t)

        # display
        self._disp = QLabel()
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(58)
        self._disp.setStyleSheet(
            f"background:#060606; border:1px solid {CYAN}55; border-radius:6px;"
            f" color:{CYAN}; font-size:24pt; font-family:'Courier New';"
            f" padding-right:10px; font-weight:bold;"
        )
        root.addWidget(self._disp)

        # numpad
        g = QGridLayout()
        g.setSpacing(6)
        rows = [("7","8","9"), ("4","5","6"), ("1","2","3"), (".","0","⌫")]
        for r, trio in enumerate(rows):
            for c, lbl in enumerate(trio):
                if lbl == "⌫":
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

        pm  = _btn("±",   "NO",  64, 86); pm.clicked.connect(self._sign);  g.addWidget(pm,  4, 0)
        clr = _btn("CLR", "NO",  64, 86); clr.clicked.connect(self._clear); g.addWidget(clr, 4, 1)
        ok  = _btn("✓ OK","NOK", 64, 86); ok.clicked.connect(self._confirm); g.addWidget(ok,  4, 2)
        root.addLayout(g)

        cnc = _btn("✕  CANCEL", "BR", 46)
        cnc.clicked.connect(self.reject)
        root.addWidget(cnc)
        self._refresh()

        # Centre over parent
        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width()  - self.width())  // 2,
                      pg.y() + (pg.height() - self.height()) // 2)

    # ── numpad logic ──────────────────────────────────────────────────────────
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
        suf = f"  {self._unit}" if self._unit else ""
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


# ═════════════════════════════════════════════════════════════════════════════
#  TEXT PICKER DIALOG
#  — preset tiles + compact A-Z keyboard; fits within 600px height
# ═════════════════════════════════════════════════════════════════════════════
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
            f"color:{AMBER}; font-size:11pt; font-weight:bold; letter-spacing:2px;"
        )
        self._disp = QLabel(self._buf or "—")
        self._disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp.setFixedHeight(44)
        self._disp.setMinimumWidth(260)
        self._disp.setStyleSheet(
            f"background:#060606; border:1px solid {AMBER}55; border-radius:5px;"
            f" color:{AMBER}; font-size:16pt; font-family:'Courier New';"
            f" padding-right:8px; font-weight:bold;"
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
        bs  = _btn("⌫  BACK", "ND",  42); bs.clicked.connect(self._bksp)
        clr = _btn("CLR",     "BX",  42); clr.clicked.connect(self._clr)
        br.addWidget(bs, 1)
        br.addWidget(clr, 1)
        root.addLayout(br)

        # ok / cancel
        bot = QHBoxLayout()
        bot.setSpacing(8)
        ok  = _btn("✓  CONFIRM", "BG", 46); ok.clicked.connect(self._confirm)
        cnc = _btn("✕  CANCEL",  "BR", 46); cnc.clicked.connect(self.reject)
        bot.addWidget(cnc, 1)
        bot.addWidget(ok,  1)
        root.addLayout(bot)

        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width()  - self.width())  // 2,
                      pg.y() + (pg.height() - self.height()) // 2)

    def _pick(self, v):
        self._buf = v
        self._disp.setText(v or "—")

    def _char(self, ch):
        self._buf += ch
        self._disp.setText(self._buf or "—")

    def _bksp(self):
        self._buf = self._buf[:-1]
        self._disp.setText(self._buf or "—")

    def _clr(self):
        self._buf = ""
        self._disp.setText("—")

    def _confirm(self):
        self._result = self._buf
        self.accept()

    def get_value(self):
        return self._result


# ═════════════════════════════════════════════════════════════════════════════
#  REUSABLE TOUCH STEPPER  (no conflicting stylesheet sizing)
# ═════════════════════════════════════════════════════════════════════════════
class Stepper(QWidget):
    """Tap-to-edit numeric field with inline light keypad."""
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

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._btn = QPushButton()
        self._btn.setFixedHeight(50)
        self._btn.setStyleSheet(
            "QPushButton {"
            " background:#FFFFFF; border:1px solid #C8D0DA; border-radius:12px;"
            " color:#1565C0; font-size:12pt; font-weight:700;"
            " padding:0 16px; text-align:center; }"
            "QPushButton:hover { background:#F8FAFB; border-color:#1565C0; }"
            "QPushButton:pressed { background:#EAF3FF; }")
        self._btn.clicked.connect(self._open_pad)
        lay.addWidget(self._btn)

        self._pad = QFrame()
        self._pad.setObjectName("Panel")
        self._pad.hide()
        pad_l = QVBoxLayout(self._pad)
        pad_l.setContentsMargins(12, 12, 12, 12)
        pad_l.setSpacing(8)

        self._pad_disp = QLabel()
        self._pad_disp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._pad_disp.setFixedHeight(46)
        self._pad_disp.setStyleSheet(
            "background:#F8FAFB; border:1px solid #DDE3EA; border-radius:10px;"
            " color:#1565C0; font-size:16pt; font-weight:700; padding:0 14px;")
        pad_l.addWidget(self._pad_disp)

        g = QGridLayout()
        g.setSpacing(8)
        rows = [("7", "8", "9"), ("4", "5", "6"), ("1", "2", "3"), (".", "0", "⌫")]
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                b = QPushButton(ch)
                b.setFixedSize(64, 52)
                b.setStyleSheet(
                    "QPushButton { background:#FFFFFF; border:1px solid #DDE3EA;"
                    " border-radius:10px; color:#334155; font-size:14pt; font-weight:700; }"
                    "QPushButton:hover { background:#F8FAFB; border-color:#1565C0; }"
                    "QPushButton:pressed { background:#EAF3FF; }")
                if ch == "⌫":
                    b.clicked.connect(self._pad_backspace)
                else:
                    b.clicked.connect(lambda _, v=ch: self._pad_char(v))
                    if ch == "." and self._dec == 0:
                        b.setEnabled(False)
                g.addWidget(b, r, c)
        pad_l.addLayout(g)

        action_l = QHBoxLayout()
        action_l.setSpacing(8)
        clr = QPushButton("CLEAR")
        clr.setFixedHeight(44)
        clr.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:1px solid #DDE3EA; border-radius:10px;"
            " color:#5B6575; font-size:10pt; font-weight:700; }"
            "QPushButton:hover { background:#F8FAFB; border-color:#BAC8D8; }")
        clr.clicked.connect(self._pad_clear)
        done = QPushButton("DONE")
        done.setFixedHeight(44)
        done.setStyleSheet(
            "QPushButton { background:#E3EEFA; border:1px solid #1565C0; border-radius:10px;"
            " color:#1565C0; font-size:10pt; font-weight:700; }"
            "QPushButton:hover { background:#D8E9FD; }")
        done.clicked.connect(self._pad_commit)
        action_l.addWidget(clr)
        action_l.addWidget(done)
        pad_l.addLayout(action_l)
        lay.addWidget(self._pad)

        self._buf = ""
        self._refresh()

    def _refresh(self):
        suf = f"  {self._unit}" if self._unit else ""
        self._btn.setText(f"{self._val:.{self._dec}f}{suf}")

    def _open_pad(self):
        self._buf = f"{self._val:.{self._dec}f}"
        self._pad_disp.setText(self._btn.text())
        self._pad.setVisible(not self._pad.isVisible())

    def _pad_char(self, ch):
        if ch == "." and "." in self._buf:
            return
        if "." in self._buf and ch != ".":
            after_dot = self._buf.split(".")[1]
            if len(after_dot) >= self._dec:
                return
        if self._buf in ("0", "0" * max(1, self._dec + 2)) and ch != ".":
            self._buf = ch
        else:
            self._buf += ch
        self._pad_refresh()

    def _pad_backspace(self):
        self._buf = self._buf[:-1] if self._buf else ""
        self._pad_refresh()

    def _pad_clear(self):
        self._buf = ""
        self._pad_refresh()

    def _pad_refresh(self):
        txt = self._buf or "0"
        suf = f" {self._unit}" if self._unit else ""
        self._pad_disp.setText(txt + suf)

    def _pad_commit(self):
        try:
            v = float(self._buf or 0)
        except ValueError:
            v = self._val
        v = max(self._lo, min(self._hi, v))
        self._val = round(v, self._dec)
        self._refresh()
        self._pad.hide()
        self.changed.emit(self._val)

    def value(self):
        return self._val

    def set_value(self, v):
        self._val = float(v)
        self._refresh()


class TouchTextField(QPushButton):
    activated = pyqtSignal(object)

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._value = ""
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
            " padding:0 12px; color:#94A3B8; font-size:10pt; text-align:left; }"
            "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }"
            "QPushButton:pressed { background:#EAF3FF; }")
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
            ("BACK", self._backspace, "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px; color:#5B6575; font-size:9.5pt; font-weight:700; }"
                                      "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }", 1),
            ("CLEAR", self._clear, "QPushButton { background:#F8FAFB; border:1px solid #D8E1EB; border-radius:11px; color:#5B6575; font-size:9.5pt; font-weight:700; }"
                                       "QPushButton:hover { background:#FFFFFF; border-color:#1565C0; }", 1),
            ("DONE", self._done, "QPushButton { background:#E3EEFA; border:1px solid #1565C0; border-radius:11px; color:#1565C0; font-size:9.5pt; font-weight:700; }"
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


# ═════════════════════════════════════════════════════════════════════════════
#  PRESET TILES  (radio-style; all in code — no CSS selector needed)
# ═════════════════════════════════════════════════════════════════════════════
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
                f"QPushButton{{background:{c}22; border:2px solid {c};"
                f" border-radius:5px; color:{c}; font-size:9pt;"
                f" font-weight:bold; padding:0 10px;}}"
                f"QPushButton:pressed{{background:{c}33;}}"
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


# ═════════════════════════════════════════════════════════════════════════════
#  SENSOR THREAD
# ═════════════════════════════════════════════════════════════════════════════
class SensorThread(QThread):
    data_ready = pyqtSignal(dict)
    fault      = pyqtSignal(str)
    motion     = pyqtSignal(bool)   # True = encoder moving, False = stationary

    def __init__(self, cfg):
        super().__init__()
        self.cfg    = cfg
        self.active = False
        self._dist  = 0.0
        self._lastc = 0

    def run(self):
        while True:
            if self.active:
                try:
                    d = self._sim() if HW_SIM else self._hw()
                    self.data_ready.emit(d)
                except Exception as e:
                    self.fault.emit(str(e))
            self.msleep(500)

    def _hw(self):
        cnt         = int(_sysfs(EQEP_PATH, "0"))
        delta       = cnt - self._lastc
        self._lastc = cnt
        enc_factor = self.cfg["encoder"].get("factor", 1.0)
        adc_factor = self.cfg["adc"].get("factor", 1.0)
        self._dist += delta * self.cfg["encoder"]["scale"] * enc_factor / 1000.0
        self.motion.emit(delta != 0)
        raw   = int(_sysfs(ADC_PATH, str(self.cfg["adc"]["zero"])))
        gauge = 1435.0 + (raw - self.cfg["adc"]["zero"]) * self.cfg["adc"]["mpc"] * adc_factor
        cross = self._spi()
        twist = round(abs(cross) * 0.65 + random.gauss(0, 0.015), 2)
        return {"gauge": round(gauge, 1), "cross": round(cross, 2),
                "twist": twist, "dist": round(self._dist, 1),
                "lat": 0.0, "lon": 0.0, "speed": 0.0}

    def _spi(self):
        try:
            import spidev
            spi = spidev.SpiDev()
            spi.open(1, 0); spi.max_speed_hz = 1_000_000; spi.mode = 0
            spi.xfer2([0xB4, 0x00, 0x00, 0x1F])
            self.msleep(5)
            r = spi.xfer2([0x04, 0x00, 0x00, 0x00]); spi.close()
            raw = (r[1] << 8) | r[2]
            if raw > 32767: raw -= 65536
            factor = self.cfg["incl"].get("factor", 1.0)
            return round((raw / 16384.0 * 90.0 - self.cfg["incl"]["offset"]) * factor, 2)
        except Exception:
            return round(random.gauss(0, 0.15) * self.cfg["incl"].get("factor", 1.0), 2)

    def _sim(self):
        enc_factor = self.cfg["encoder"].get("factor", 1.0)
        adc_factor = self.cfg["adc"].get("factor", 1.0)
        incl_factor = self.cfg["incl"].get("factor", 1.0)
        self._dist += 0.2 * enc_factor
        self.motion.emit(True)
        cross = round(random.gauss(0, 0.25) * incl_factor, 2)
        return {"gauge": round(1435.0 + random.gauss(0, 0.12) * adc_factor, 1),
                "cross": cross,
                "twist": round(abs(cross) * 0.65 + random.gauss(0, 0.015), 2),
                "dist":  round(self._dist, 1),
                "lat":   12.9716 + self._dist * 1e-6,
                "lon":   77.5946 + self._dist * 1e-6,
                "speed": round(random.uniform(2.0, 8.0), 1)}

    def reset(self):
        self._dist = 0.0; self._lastc = 0


# ═════════════════════════════════════════════════════════════════════════════
#  NETWORK THREAD
# ═════════════════════════════════════════════════════════════════════════════
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
        if _sysfs(f"/sys/class/net/{iface}/operstate", "down") == "up": return 3
        if _sysfs("/sys/class/net/eth0/operstate",     "down") == "up": return 2
        return 0 if not HW_SIM else 3

    def _ping(self):
        if HW_SIM: return True
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", self.cfg.get("server", "8.8.8.8")],
                capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False


# ═════════════════════════════════════════════════════════════════════════════
#  CSV LOGGER
# ═════════════════════════════════════════════════════════════════════════════
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
        filename = f"BLE_{safe_ts}.csv"
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


# ═════════════════════════════════════════════════════════════════════════════
#  SPARKLINE
# ═════════════════════════════════════════════════════════════════════════════
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


# ═════════════════════════════════════════════════════════════════════════════
#  GRAPH CANVAS  (QPainter only — no matplotlib)
# ═════════════════════════════════════════════════════════════════════════════
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
                       "NO DATA — START SESSION FIRST")
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
                       Qt.AlignRight | Qt.AlignVCenter, f"{val:.2f}")

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
        p.drawText(PAD, 18, f"{self.title.upper()}  [{self.unit}]  ·  {n} pts")
        p.setPen(QColor("#333"))
        p.setFont(QFont("Courier New", 7))
        p.drawText(PAD, H - 4, "SESSION START")
        p.drawText(PAD + gW - 30, H - 4, "NOW")
        p.end()


# ═════════════════════════════════════════════════════════════════════════════
#  TOP BAR  — Android-style status bar  (fully painted — no font fallback)
# ═════════════════════════════════════════════════════════════════════════════
class TopBar(QWidget):
    # ── ISO RESTYLE ──
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)

        # State drawn in paintEvent
        self._bar_count   = 4
        self._bar_color   = QColor("#4CAF50")
        self._net_txt     = "LTE"
        self._net_col     = QColor("#4CAF50")
        self._sensor_txt  = "SENSOR OK"
        self._sensor_ok   = True
        self._bat_txt     = "87%"
        self._time_txt    = "--:--:--"
        self._title_txt   = "LWTMT"

        # No child widgets — everything painted
        tmr = QTimer(self)
        tmr.timeout.connect(self._tick)
        tmr.start(1000)
        self._tick()

    def paintEvent(self, event):
        # ── ISO RESTYLE — entire status bar drawn with QPainter ──
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        # ── Background ───────────────────────────────────────────────────────
        p.fillRect(0, 0, W, H, QColor("#1C2333"))

        # ── Thin accent line at very bottom ──────────────────────────────────
        p.fillRect(0, H - 2, W, 2, QColor("#2A3A50"))

        cy = H // 2   # vertical center

        # ── Font helpers ─────────────────────────────────────────────────────
        f_mono_sm = QFont("Courier New", 9, QFont.Normal)
        f_mono_md = QFont("Courier New", 10, QFont.Bold)
        f_clock   = QFont("Courier New", 13, QFont.Bold)
        f_title   = QFont("Segoe UI", 12, QFont.Bold)

        # ── LEFT: Signal bars ─────────────────────────────────────────────────
        bw, bg_gap = 4, 3
        bar_hs = (5, 9, 13, 17)
        x = 14
        for i, bh in enumerate(bar_hs):
            by = cy + 9 - bh
            col = self._bar_color if i < self._bar_count else QColor("#3A4555")
            # rounded rect look
            path = QPainterPath()
            path.addRoundedRect(x, by, bw, bh, 1, 1)
            p.fillPath(path, col)
            x += bw + bg_gap

        # ── LEFT: LTE label ───────────────────────────────────────────────────
        x += 4
        p.setFont(f_mono_md)
        p.setPen(self._net_col)
        p.drawText(x, 0, 40, H, Qt.AlignVCenter | Qt.AlignLeft, self._net_txt)
        x += 40

        # ── Separator ─────────────────────────────────────────────────────────
        x += 6
        p.fillRect(x, cy - 8, 1, 16, QColor("#3A4555"))
        x += 10

        # ── LEFT: Sensor dot + label ──────────────────────────────────────────
        dot_col = QColor("#4CAF50") if self._sensor_ok else QColor("#EF5350")
        p.setBrush(dot_col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(x, cy - 4, 8, 8)
        x += 14

        p.setFont(f_mono_sm)
        p.setPen(QColor("#A8C8A8") if self._sensor_ok else QColor("#FFAA44"))
        p.drawText(x, 0, 140, H, Qt.AlignVCenter | Qt.AlignLeft, self._sensor_txt)

        # ── CENTER: Trolley name ──────────────────────────────────────────────
        p.setFont(f_title)
        p.setPen(QColor("#F3F6FB"))
        p.drawText(QRect(0, 0, W, H), Qt.AlignCenter, self._title_txt)

        # ── RIGHT: Clock ──────────────────────────────────────────────────────
        p.setFont(f_clock)
        p.setPen(QColor("#FFFFFF"))
        clk_w = 110
        p.drawText(W - clk_w - 14, 0, clk_w, H,
                   Qt.AlignVCenter | Qt.AlignRight, self._time_txt)

        # ── RIGHT: Separator ──────────────────────────────────────────────────
        sep_x = W - clk_w - 14 - 10
        p.fillRect(sep_x, cy - 8, 1, 16, QColor("#3A4555"))

        # ── RIGHT: Battery ────────────────────────────────────────────────────
        bat_w = 60
        p.setFont(f_mono_sm)
        p.setPen(QColor("#A8C8A8"))
        # battery icon drawn as small rect
        bix = sep_x - bat_w - 8
        p.drawText(bix, 0, bat_w, H,
                   Qt.AlignVCenter | Qt.AlignRight, "▮ " + self._bat_txt)

        p.end()

    def _tick(self):
        self._time_txt = datetime.now().strftime("%H:%M:%S")
        self.update()

    def update_net(self, bars, cloud):
        # ── ISO RESTYLE ──
        self._bar_count = max(0, min(4, bars))
        if bars >= 3:
            self._bar_color = QColor("#4CAF50");  self._net_col = QColor("#4CAF50")
        elif bars >= 1:
            self._bar_color = QColor("#FF9800");  self._net_col = QColor("#FF9800")
        else:
            self._bar_color = QColor("#EF5350");  self._net_col = QColor("#EF5350")
        self._net_txt = "LTE" if cloud else "NO SYNC"
        self.update()

    def push_error(self, msg):
        # ── ISO RESTYLE ──
        if msg:
            self._sensor_txt = (msg[:22] + "…") if len(msg) > 22 else msg
            self._sensor_ok  = False
        else:
            self._sensor_txt = "SENSOR OK"
            self._sensor_ok  = True
        self.update()


# ═════════════════════════════════════════════════════════════════════════════
#  CONTROL BAR
# ═════════════════════════════════════════════════════════════════════════════
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
        self._csv_lbl = QLabel("📁  " + _shorten(cfg["csv_dir"]))
        self._csv_lbl.setStyleSheet(
            "background:#111; border:1px solid #333; border-radius:5px;"
            " color:#666; font-size:8pt; padding:3px 10px;"
            " font-family:'Courier New';")
        self._csv_lbl.setFixedHeight(32)

        # Calibrate button
        cal = QPushButton("⚙  CALIBRATE")
        cal.setStyleSheet(
            f"QPushButton{{background:#1a1500; border:2px solid {AMBER};"
            f" border-radius:5px; color:{AMBER}; font-size:9pt;"
            f" font-weight:bold; padding:3px 14px; min-height:32px;}}"
            f"QPushButton:pressed{{background:#251d00;}}")
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
            f"QPushButton{{background:#001520; border:2px solid {CYAN};"
            f" border-radius:5px; color:{CYAN}; font-size:9pt;"
            f" font-weight:bold; padding:3px 12px; min-height:32px;}}"
            f"QPushButton:pressed{{background:#002030;}}")
        mark.clicked.connect(lambda: self.sig_mark.emit(int(self._stepper.value())))

        lay.addWidget(self._csv_lbl)
        lay.addWidget(cal)
        lay.addStretch()
        lay.addWidget(hl_lbl)
        lay.addWidget(self._stepper)
        lay.addWidget(mark)

    def set_csv_path(self, path):
        self._csv_lbl.setText("📁  " + _shorten(path))


# ═════════════════════════════════════════════════════════════════════════════
#  METRIC CARD
# ═════════════════════════════════════════════════════════════════════════════
_THRESH = {
    "gauge": (0.5, 1.5),
    "cross": (0.8, 1.5),
    "twist": (0.40, 0.80),
    "dist":  (None, None),
}


class MetricCard(QFrame):
    # ── ISO RESTYLE ──
    def __init__(self, key, title, unit, color, parent=None):
        super().__init__(parent)
        self.key   = key
        self.color = color
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # drop shadow
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        fx = QGraphicsDropShadowEffect(self)
        fx.setBlurRadius(16)
        fx.setOffset(0, 4)
        fx.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(fx)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(0)

        # ── Card header ───────────────────────────────────────────────────────
        hdr = QWidget()
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(18, 10, 14, 8)
        hdr_l.setSpacing(8)

        self._title = QLabel(title.upper())
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setStyleSheet(
            "background: transparent; border: none;"
            " color: #4A5568;"
            " font-family: 'Inter','DM Sans','Liberation Sans',sans-serif;"
            " font-size: 11pt; font-weight: 600; letter-spacing: 1.2px;")

        self._badge = QLabel("NOMINAL")
        self._badge.setAlignment(Qt.AlignCenter)

        hdr_l.addWidget(self._title, 1)
        hdr_l.addWidget(self._badge)

        # thin line under header
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background:#DDE3EA; border:none;")

        # ── Value + unit — centred inline pair ───────────────────────────────
        # Outer widget fills the card body and centres the inner pair
        val_row_w = QWidget()
        val_row_w.setStyleSheet("background:transparent; border:none;")
        val_row_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Outer layout centres the inner pair horizontally and vertically
        outer_l = QHBoxLayout(val_row_w)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(0)
        outer_l.addStretch(1)

        # Inner pair: [number_fixed_container] [unit_fixed]
        pair_w = QWidget()
        pair_w.setStyleSheet("background:transparent; border:none;")
        pair_l = QHBoxLayout(pair_w)
        pair_l.setContentsMargins(0, 0, 0, 0)
        pair_l.setSpacing(6)

        # Number — fixed width so unit never shifts; right-aligned inside it
        self._val = QLabel("---")
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._val.setMinimumWidth(320)   # wide enough for "1435.0", "-0.44" etc
        self._val.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # Unit — fixed width, baseline-aligned, named for CSS lock
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
            " font-family: 'Inter','DM Sans',sans-serif;"
            " font-size: 9pt; font-weight: 600; letter-spacing: 0.5px;")

        lay.addWidget(hdr)
        lay.addWidget(rule)
        lay.addWidget(val_row_w, 1)
        lay.addWidget(self._alert)

        self._apply_badge("NOMINAL", color)
        self._apply_val_style(color)
        self._apply_unit_style()
        self.setStyleSheet(
            f"QFrame#Card{{"
            f" background:#FFFFFF; border:1px solid #DDE3EA;"
            f" border-left:4px solid {color}; border-radius:10px;}}")

    # ── ISO RESTYLE ──
    def _apply_badge(self, text, color):
        # Map each metric colour to a solid light background
        _BG_MAP = {
            "#1B8A4C": ("#D4EDDA", "#1B8A4C"),   # green
            "#1565C0": ("#D0E4F7", "#1565C0"),   # blue
            "#C06000": ("#FFE8C0", "#944800"),   # amber  — dark text for contrast
            "#5E35B1": ("#E0D4F5", "#5E35B1"),   # violet
            "#C62828": ("#FDDEDE", "#C62828"),   # red alarm
            "#E65100": ("#FFE0CC", "#C04000"),   # orange warn
        }
        bg, fg = _BG_MAP.get(color, ("#E8E8E8", "#333333"))
        self._badge.setText(text)
        self._badge.setStyleSheet(
            f"color:{fg}; background:{bg};"
            f" border:1.5px solid {fg};"
            f" border-radius:4px;"
            f" padding:3px 10px;"
            f" font-family:'Courier New',monospace;"
            f" font-size:9pt; font-weight:bold; letter-spacing:1px;")

    # ── ISO RESTYLE ──
    def _apply_unit_style(self):
        """Lock the unit label to a fixed, non-inheriting style always."""
        self._unit.setStyleSheet(
            "QLabel#UnitLbl {"
            " color: #8A94A6;"
            " background: transparent;"
            " border: none;"
            " font-family: 'Courier New', monospace;"
            " font-size: 13pt;"
            " font-weight: 500;"
            " letter-spacing: 1px;"
            " padding-bottom: 14px;"
            "}")

    # ── ISO RESTYLE ──
    def _apply_val_style(self, color):
        self._val.setStyleSheet(
            f"color:{color}; background:transparent; border:none;"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:84pt; font-weight:700; letter-spacing:-3px;")

    # ── ISO RESTYLE ──
    def refresh(self, val):
        self._val.setText(str(val))
        warn, alarm = _THRESH.get(self.key, (None, None))
        dev = (abs(float(val) - 1435.0) if self.key == "gauge"
               else abs(float(val)))
        if alarm is not None and dev >= alarm:
            vc  = RED
            txt = "⚠  ALARM"
            bg  = (f"QFrame#Card{{background:#FFEBEE; border:1px solid #DDE3EA;"
                   f" border-left:4px solid {RED}; border-radius:10px;}}")
            self._apply_badge("ALARM", RED)
        elif warn is not None and dev >= warn:
            vc  = WARN
            txt = "△  WARN"
            bg  = (f"QFrame#Card{{background:#FFF3E0; border:1px solid #DDE3EA;"
                   f" border-left:4px solid {WARN}; border-radius:10px;}}")
            self._apply_badge("MONITOR", WARN)
        else:
            vc  = self.color
            txt = ""
            bg  = (f"QFrame#Card{{background:#FFFFFF; border:1px solid #DDE3EA;"
                   f" border-left:4px solid {self.color}; border-radius:10px;}}")
            self._apply_badge("NOMINAL", self.color)
        self._apply_val_style(vc)
        self._apply_unit_style()
        self._alert.setText(txt)
        self.setStyleSheet(bg)

# ═════════════════════════════════════════════════════════════════════════════
#  GRAPH PAGE  (full-screen inside stack — no floating overlay)
# ═════════════════════════════════════════════════════════════════════════════
class GraphPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        back = _btn("← BACK", "BC", 46, 140)
        back.clicked.connect(self.sig_back)
        self._lbl = QLabel("—")
        self._lbl.setStyleSheet(
            f"color:{CYAN}; font-size:11pt; font-weight:bold; letter-spacing:2px;")
        hdr.addWidget(back)
        hdr.addSpacing(12)
        hdr.addWidget(self._lbl)
        hdr.addStretch()
        lay.addLayout(hdr)

        self._canvas = GraphCanvas()
        lay.addWidget(self._canvas, 1)

    def load(self, title, unit, data, color):
        self._lbl.setText(f"▸  {title.upper()} — SESSION HISTORY")
        self._canvas._col = QColor(color)
        self._canvas.load(data, title, unit)



# ═════════════════════════════════════════════════════════════════════════════
#  LIVE TERMINAL WIDGET
#  Streams every stdout/stderr line live into an on-screen green-on-black pane.
#  Call .run(cmd) with any shell command string.
#  Signal finished(exit_code:int, full_output:str) emitted when done.
# ═════════════════════════════════════════════════════════════════════════════
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
        self._cmd_lbl = QLabel("$  —")
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

    # ── public API ────────────────────────────────────────────────────────────
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
        self._cmd_lbl.setText("$  —")
        self._set_status("IDLE", "#8A94A6")

    # ── internal ──────────────────────────────────────────────────────────────
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
        self._set_status(f"EXIT {code}", NEON if ok else RED)
        self._out.append(f"\n{'─'*40}\n{'OK' if ok else 'FAIL'}  exit={code}")
        self._scroll()
        self.finished.emit(code, self._full_out)

    def _scroll(self):
        sb = self._out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_status(self, txt, color):
        self._stat.setText(txt)
        self._stat.setStyleSheet(
            f"color:{color}; font-size:8pt; font-weight:bold;"
            f" font-family:'Courier New'; padding:3px 8px;")


# ═════════════════════════════════════════════════════════════════════════════
#  ENCODER CAL
# ═════════════════════════════════════════════════════════════════════════════
class EncoderCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        fr = QHBoxLayout()
        fr.addWidget(_lbl("Calibration factor:", "#4A5568", 10, True))
        self._factor_s = Stepper(cfg["encoder"].get("factor", 1.0), step=0.01, dec=3,
                                 lo=0.001, hi=100.0, unit="x",
                                 title="ENCODER CALIBRATION FACTOR")
        fr.addWidget(self._factor_s, 1)
        lay.addLayout(fr)

        sv = _btn("SAVE CHANGES", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)
        lay.addStretch()

    def _cmd_reset(self):
        if os.path.exists(EQEP_PATH):
            return (f"echo '# Resetting eQEP counter...' && "
                    f"echo '# Path: {EQEP_PATH}' && "
                    f"echo 0 > {EQEP_PATH} && "
                    f"echo '# Verify reset:' && cat {EQEP_PATH}")
        cnt = random.randint(1800, 2400)
        return (f"echo '# [SIM] eQEP not present — simulation mode' && "
                f"sleep 0.3 && echo 'Counter reset to: 0'")

    def _cmd_read(self):
        if os.path.exists(EQEP_PATH):
            return (f"echo '# Reading eQEP counter after trolley roll...' && "
                    f"cat {EQEP_PATH}")
        cnt = random.randint(1800, 2400)
        return (f"echo '# [SIM] Reading simulated eQEP counter...' && "
                f"sleep 0.4 && echo 'Counter value: {cnt}'")

    def _do_reset(self):
        self._phase = "reset"
        self._cap_btn.setEnabled(False)
        self._term.append(f"# EQEP path: {EQEP_PATH}")
        self._term.run(self._cmd_reset())

    def _do_capture(self):
        self._phase = "capture"
        self._term.run(self._cmd_read())

    def _on_done(self, code, out):
        if code != 0:
            return
        if self._phase == "reset":
            self._term.append(
                "✓ Counter zeroed.\n"
                "  Roll trolley the exact known distance, then tap CAPTURE.")
            self._cap_btn.setEnabled(True)
        elif self._phase == "capture":
            nums = [w.strip(":,") for w in out.split() if w.strip(":,").lstrip("-").isdigit()]
            if not nums:
                self._term.append("⚠  Could not parse count from output"); return
            count = int(nums[-1])
            if count == 0:
                self._term.append("⚠  Count is still zero — did you roll the trolley?")
                return
            self._scale = self._dist_s.value() / count
            self._res.setText(
                f"Count: {count}   →   Scale: {self._scale:.5f} mm/count"
                f"   ({1/self._scale:.1f} cts/mm)")
            self._term.append(
                f"\n# Result: {self._dist_s.value()} mm / {count} counts"
                f" = {self._scale:.5f} mm/count")

    def _do_save(self):
        factor = self._factor_s.value()
        self.cfg["encoder"].update({"factor": factor, "calibrated": True})
        save_cfg(self.cfg)
        self.saved.emit("encoder", self.cfg["encoder"])


# ═════════════════════════════════════════════════════════════════════════════
#  ADC / GAUGE CAL
# ═════════════════════════════════════════════════════════════════════════════
class ADCCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        fr = QHBoxLayout()
        fr.addWidget(_lbl("Calibration factor:", "#4A5568", 10, True))
        self._factor_s = Stepper(cfg["adc"].get("factor", 1.0), step=0.01, dec=3,
                                 lo=0.001, hi=100.0, unit="x",
                                 title="POTENTIOMETER CALIBRATION FACTOR")
        fr.addWidget(self._factor_s, 1)
        lay.addLayout(fr)

        sv = _btn("SAVE CHANGES", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)
        lay.addStretch()

    def _adc_cmd(self):
        if os.path.exists(ADC_PATH):
            return (f"echo '# Reading IIO ADC device...' && "
                    f"echo '# Path: {ADC_PATH}' && "
                    f"echo -n 'Raw ADC value: ' && cat {ADC_PATH}")
        val = random.randint(1950, 2150)
        return (f"echo '# [SIM] IIO ADC not present — simulation mode' && "
                f"sleep 0.3 && echo 'Raw ADC value: {val}'")

    def _read_zero(self):
        self._phase = "zero"
        self._term.run(self._adc_cmd())

    def _read_offset(self):
        self._phase = "offset"
        self._term.append(f"\n# Reading ADC after {self._off_s.value():.2f} mm shift...")
        self._term.run(self._adc_cmd())

    def _on_done(self, code, out):
        if code != 0:
            return
        nums = [w.strip(":,") for w in out.split()
                if w.strip(":,").lstrip("-").isdigit()]
        if not nums:
            self._term.append("⚠  Could not parse ADC raw value"); return
        val = int(nums[-1])

        if self._phase == "zero":
            self._zero_raw = val
            self._term.append(
                f"✓ Zero raw = {val}  (gauge at 1435 mm)\n"
                f"  Shift gauge by {self._off_s.value():.2f} mm, then tap READ OFFSET.")
            self._o_btn.setEnabled(True)
        elif self._phase == "offset":
            if self._zero_raw is None:
                return
            delta = val - self._zero_raw
            if delta == 0:
                self._term.append("⚠  Δ is zero — did you shift the gauge?"); return
            self._mpc = self._off_s.value() / delta
            self._res.setText(
                f"ADC: {val}  Δ={delta}  mpc={self._mpc:.5f} mm/count")
            self._term.append(
                f"\n# {self._off_s.value():.2f} mm / {delta} ADC-counts"
                f" = {self._mpc:.5f} mm/count")

    def _do_save(self):
        factor = self._factor_s.value()
        self.cfg["adc"].update({"factor": factor, "calibrated": True})
        save_cfg(self.cfg)
        self.saved.emit("adc", self.cfg["adc"])


# ═════════════════════════════════════════════════════════════════════════════
#  INCLINOMETER CAL
# ═════════════════════════════════════════════════════════════════════════════
_SPI_SCRIPT_SRC = """\
import spidev, time, sys
try:
    spi = spidev.SpiDev()
    spi.open(1, 0)
    spi.max_speed_hz = 1_000_000
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
    print(f"SPI raw={raw}  angle={angle:.6f}")
except Exception as e:
    print(f"SPI ERROR: {e}", file=sys.stderr)
    sys.exit(1)
"""

_SPI_SIM_SRC = """\
import random, time
print("# [SIM] /dev/spidev1.0 not present — simulation mode")
time.sleep(0.3)
a = random.gauss(0, 0.12)
raw = int(a * 182)
print(f"SPI raw={raw}  angle={a:.6f}")
"""


class InclinCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        fr = QHBoxLayout()
        fr.addWidget(_lbl("Calibration factor:", "#4A5568", 10, True))
        self._factor_s = Stepper(cfg["incl"].get("factor", 1.0), step=0.01, dec=3,
                                 lo=0.001, hi=100.0, unit="x",
                                 title="INCLINOMETER CALIBRATION FACTOR")
        fr.addWidget(self._factor_s, 1)
        lay.addLayout(fr)

        sv = _btn("SAVE CHANGES", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)
        lay.addStretch()

    def _spi_cmd(self):
        return f"echo '# Running SPI reader: {self._script}' && python3 {self._script}"

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
            self._term.append("⚠  Could not parse angle from output"); return

        if self._phase == "zero":
            self._offset = angle
            self._res.setText(f"Zero offset stored: {angle:.5f}°")
            self._term.append(
                f"\n✓ Zero offset = {angle:.5f}°\n"
                "  Tap VERIFY to confirm correction is < ±0.05°.")
            self._v_btn.setEnabled(True)
        elif self._phase == "verify":
            corr = angle - (self._offset or 0.0)
            ok   = abs(corr) < 0.05
            self._res.setText(
                f"Corrected: {corr:.4f}°  "
                + ("✓ PASS (<0.05°)" if ok else f"⚠  {corr:.4f}° — re-zero"))
            self._res.setStyleSheet(
                f"color:{NEON if ok else AMBER}; font-size:9pt;")

    def _do_save(self):
        factor = self._factor_s.value()
        self.cfg["incl"].update({"factor": factor, "calibrated": True})
        save_cfg(self.cfg)
        self.saved.emit("incl", self.cfg["incl"])


# ═════════════════════════════════════════════════════════════════════════════
#  GNSS CAL
# ═════════════════════════════════════════════════════════════════════════════
class GNSSCal(QWidget):
    saved = pyqtSignal(str, dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg     = cfg
        self._action = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("GNSS  u-blox NEO-M8P-2  (/dev/ttyS4) — FIX & CHAINAGE",
                           MAGI, 10, True))
        lay.addWidget(_lbl(
            "Start gpsd → check fix (≥4 sats for survey) → "
            "optionally enable RTK → set reference chainage → SAVE", "#555", 8))

        g = QGridLayout(); g.setSpacing(8)
        for i, (lbl, fn, nm) in enumerate([
            ("▶ START gpsd",  self._start_gpsd,  "BM"),
            ("■ STOP gpsd",   self._stop_gpsd,   "BM"),
            ("⊛ CHECK FIX",  self._check_fix,   "BM"),
            ("⚡ RTK MODE",   self._rtk,         "BM"),
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
                             lo=0, hi=9_999_999, unit="m", title="REF CHAINAGE")
        rc.addWidget(self._ch_s, 1)
        lay.addLayout(rc)

        sv = _btn("SAVE CONFIGURATION ✓", "BA", 48)
        sv.clicked.connect(self._do_save)
        lay.addWidget(sv)

        ok = cfg["gnss"].get("calibrated", False)
        self._info = _lbl(
            ("✓ CONFIGURED" if ok else "✗ NOT CONFIGURED")
            + f"  |  ref={cfg['gnss']['ref_ch']:.1f} m",
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
            "echo 'No GGA sentence — is gpsd running and antenna connected?'"
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
                            f"\n→ Quality: {qual}  Satellites: {sats}  Alt: {alt} m")
                        self._info.setStyleSheet(f"color:{col}; font-size:9pt;")
                    except Exception:
                        pass
                    return

    def _do_save(self):
        self.cfg["gnss"].update({"ref_ch": self._ch_s.value(), "calibrated": True})
        save_cfg(self.cfg)
        self._info.setText(
            f"✓ CONFIGURED  |  ref={self._ch_s.value():.1f} m")
        self._info.setStyleSheet(f"color:{NEON}; font-size:9pt;")
        self._term.append("✓ Saved to rail_config.json")
        self.saved.emit("gnss", self.cfg["gnss"])


# ═════════════════════════════════════════════════════════════════════════════
#  LTE STATUS
# ═════════════════════════════════════════════════════════════════════════════
class LTECal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LTE MODEM  (cdc_ether) — NETWORK DIAGNOSTICS",
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

        sv = _btn("SAVE INTERFACE SELECTION ✓", "BA", 48)
        sv.clicked.connect(self._save)
        lay.addWidget(sv)
        lay.addStretch()

    def _ip(self):
        i = self._iface.value()
        self._term.run(
            f"echo '# ip addr show {i}' && ip addr show {i} 2>&1 && "
            f"echo && echo '# ip link show {i}' && ip link show {i} 2>&1")

    def _ping(self):
        srv = self.cfg.get("server", "8.8.8.8")
        self._term.run(
            f"echo '# ping -c 4 -W 2 {srv}' && ping -c 4 -W 2 {srv} 2>&1")

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
        self._term.append(f"✓ Interface saved: {self._iface.value()}")


# ═════════════════════════════════════════════════════════════════════════════
#  DISPLAY CAL
# ═════════════════════════════════════════════════════════════════════════════
class DisplayCal(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        lay.addWidget(_lbl("LCD DISPLAY  (HDMI / omapdrm) — XRANDR CONFIGURATION",
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
        cmd = (f"echo '# xrandr --output {self._out.value()} --mode {self._res.value()}' && "
               f"xrandr --output {self._out.value()} --mode {self._res.value()} 2>&1 && "
               f"echo 'Mode applied.' || echo 'xrandr error — check output name with LIST MODES'")
        self._term.run(cmd)

    def _auto(self):
        cmd = (f"echo '# xrandr --output {self._out.value()} --auto' && "
               f"xrandr --output {self._out.value()} --auto 2>&1 && echo 'Done.'")
        self._term.run(cmd)

    def _rotate(self):
        cmd = (f"echo '# xrandr --output {self._out.value()} --rotate {self._rot.value()}' && "
               f"xrandr --output {self._out.value()} --rotate {self._rot.value()} 2>&1 && "
               f"echo 'Rotation set.'")
        self._term.run(cmd)

    def _modes(self):
        self._term.run("echo '# xrandr --query' && xrandr 2>&1")


# ═════════════════════════════════════════════════════════════════════════════
#  CALIBRATION PAGE
# ═════════════════════════════════════════════════════════════════════════════
_SENSORS = [
    ("adc", "Potentiometer", CYAN, ADCCal),
    ("incl", "Inclinometer", AMBER, InclinCal),
    ("encoder", "Rotary Encoder", NEON, EncoderCal),
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
        hdr_w.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(12, 0, 12, 0)
        title = QLabel("SENSOR CALIBRATION")
        title.setStyleSheet(
            f"color:{AMBER}; font-size:13pt; font-weight:bold; letter-spacing:3px;")
        hdr.addStretch()
        hdr.addWidget(title)
        hdr.addStretch()
        root.addWidget(hdr_w)

        body_w = QWidget()
        body = QVBoxLayout(body_w)
        body.setContentsMargins(18, 18, 18, 18)
        body.setSpacing(14)

        nav = QWidget()
        nav_l = QHBoxLayout(nav)
        nav_l.setContentsMargins(0, 0, 0, 0)
        nav_l.setSpacing(10)

        self._stack = QStackedWidget()

        for i, (key, label, color, Cls) in enumerate(_SENSORS):
            sub = cfg.get(key, {})
            ok  = sub.get("calibrated", False) if isinstance(sub, dict) else False

            btn = QPushButton(("✓  " if ok else "○  ") + label)
            btn.setFixedHeight(52)
            btn.setStyleSheet(
                "QPushButton{ background:#FFFFFF; border:1px solid #D7E0EA;"
                " border-radius:14px; color:#5B6575; font-size:10pt;"
                " font-weight:700; padding:8px 16px; text-align:center;}"
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
        rl.setContentsMargins(12, 12, 12, 12)
        rl.addWidget(self._stack)
        body.addWidget(rf, 1)

        root.addWidget(body_w, 1)

        bottom_w = QWidget()
        bottom_w.setStyleSheet("background:#FFFFFF; border-top:1px solid #DDE3EA;")
        bottom_l = QHBoxLayout(bottom_w)
        bottom_l.setContentsMargins(16, 10, 16, 10)
        back = _btn("← BACK", "BC", 42, 150)
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
                    f"QPushButton{{ background:{color}14; border:2px solid {color};"
                    f" border-radius:14px; color:{color}; font-size:10pt;"
                    f" font-weight:700; padding:8px 16px; text-align:center;}}"
                    f"QPushButton:hover{{ background:{color}18; }}"
                    f"QPushButton:pressed{{ background:{color}24; }}")
            else:
                btn.setStyleSheet(
                    "QPushButton{ background:#FFFFFF; border:1px solid #D7E0EA;"
                    " border-radius:14px; color:#5B6575; font-size:10pt;"
                    " font-weight:700; padding:8px 16px; text-align:center;}"
                    "QPushButton:hover{ background:#F8FAFB; border-color:#BAC8D8; }"
                    "QPushButton:pressed{ background:#EEF3F8; }")
        self._stack.setCurrentIndex(idx)

    def _on_saved(self, key, _):
        for i, (k, label, color, *_) in enumerate(_SENSORS):
            if k == key:
                self._btns[i][0].setText("✓  " + label)
                break


# ═════════════════════════════════════════════════════════════════════════════
#  DATA ENTRY PAGE  — parameter dropdowns with value + frequency tables
# ═════════════════════════════════════════════════════════════════════════════

# key, display label, sensor_key, frequency_interval, unit, color
_PARAM_TABLES = [
    ("gauge", "GAUGE", "gauge", "mm", NEON, [0.25, 0.5, 0.75, 1.0]),
    ("twist", "TWIST", "twist", "mm/m", AMBER, [2.0, 3.0, 4.0]),
]


class ParamTableWidget(QWidget):
    """Expandable frequency selector for a survey parameter."""

    def __init__(self, label, color, unit, freq_options=None, parent=None):
        super().__init__(parent)
        self._color = color
        self._unit = unit
        self._expanded = False
        self._label = label
        self._freq_options = freq_options or []
        self._freq_interval = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── dropdown header button ────────────────────────────────────────────
        self._hdr = QPushButton()
        self._hdr.setFixedHeight(50)
        self._hdr.setStyleSheet(
            f"QPushButton{{background:#FFFFFF; border:1px solid {color}55;"
            f" border-radius:10px; color:{color}; font-size:10pt;"
            f" font-weight:bold; font-family:'Courier New'; text-align:left;"
            f" padding:0 14px; letter-spacing:1px;}}"
            f"QPushButton:pressed{{background:#F4F7FB;}}")
        self._hdr.clicked.connect(self._toggle)
        root.addWidget(self._hdr)
        self._update_header()

        # ── collapsible table area ────────────────────────────────────────────
        self._table_w = QWidget()
        self._table_w.setStyleSheet(
            "background:#FFFFFF; border-left:1px solid #DDE3EA;"
            " border-right:1px solid #DDE3EA; border-bottom:1px solid #DDE3EA;"
            " border-bottom-left-radius:10px; border-bottom-right-radius:10px;")
        self._table_w.hide()
        tv = QVBoxLayout(self._table_w)
        tv.setContentsMargins(8, 8, 8, 8)
        tv.setSpacing(4)

        if self._freq_options:
            freq_lbl = QLabel("Select recording frequency")
            freq_lbl.setStyleSheet(
                "color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
            tv.addWidget(freq_lbl)

            self._freq_combo = QComboBox()
            self._freq_combo.addItem("Select frequency", None)
            for val in self._freq_options:
                self._freq_combo.addItem(self._format_freq_option(val), val)
            self._freq_combo.setFixedHeight(40)
            self._freq_combo.setStyleSheet(
                "QComboBox {"
                " background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
                " padding:0 12px; color:#1A2332; font-size:10pt; }"
                "QComboBox::drop-down { border:none; width:32px; }"
                "QComboBox QAbstractItemView {"
                " background:#FFFFFF; border:1px solid #C8D0DA; color:#1A2332;"
                " selection-background-color:#E3EEFA; selection-color:#1A2332; }")
            self._freq_combo.currentIndexChanged.connect(self._on_freq_changed)
            tv.addWidget(self._freq_combo)

        root.addWidget(self._table_w)

    def _toggle(self):
        self._expanded = not self._expanded
        self._table_w.setVisible(self._expanded)
        self._update_header()

    def _format_freq_option(self, value):
        return f"{value:g}m"

    def _update_header(self):
        arrow = "▼" if self._expanded else "▶"
        tick = "   ✔" if self._expanded else ""
        if self._freq_interval is None:
            text = self._label
        else:
            text = f"{self._label} (selected frequency: {self._format_freq_option(self._freq_interval)})"
        self._hdr.setText(f"{arrow}   {text}{tick}")

    def _on_freq_changed(self, _):
        self._freq_interval = self._freq_combo.currentData()
        self._update_header()

    def push_value(self, val):
        return

    def clear_rows(self):
        return

    def get_rows(self):
        return []


class StationParamsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._field_names = [
            "Station Code",
            "Chainage",
            "Nomenclature of Loop/Line Siding",
            "Turn-out No",
            "Curve No",
            "Level Crossing No",
            "Hectometer Post",
        ]
        self._field_rows = {}
        self._fields = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QPushButton("▶   STATION PARAMETERS")
        self._hdr.setFixedHeight(50)
        self._hdr.setStyleSheet(
            f"QPushButton{{background:#FFFFFF; border:1px solid {HEADER_ACCENT}55;"
            f" border-radius:10px; color:{HEADER_ACCENT}; font-size:10pt;"
            f" font-weight:bold; font-family:'Courier New'; text-align:left;"
            f" padding:0 14px; letter-spacing:1px;}}"
            f"QPushButton:pressed{{background:#F4F7FB;}}")
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
        lbl.setStyleSheet(
            "color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
        body_l.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.addItem("Select station parameter", None)
        for name in self._field_names:
            self.combo.addItem(name, name)
        self.combo.setFixedHeight(42)
        self.combo.setStyleSheet(
            "QComboBox {"
            " background:#F8FAFB; border:1px solid #C8D0DA; border-radius:8px;"
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
            field_edit = TouchTextField(f"Enter {name.lower()}")
            field_edit.activated.connect(self._activate_text_field)
            row_l.addWidget(field_lbl)
            row_l.addWidget(field_edit, 1)
            row_w.hide()
            self._field_rows[name] = row_w
            self._fields[name] = field_edit
            body_l.addWidget(row_w)

        insp_hdr = QLabel("Inspecting Official")
        insp_hdr.setStyleSheet(
            f"color:{HEADER_ACCENT}; font-size:9pt; font-weight:bold; background:transparent;")
        body_l.addWidget(insp_hdr)

        name_row = QWidget()
        name_row_l = QHBoxLayout(name_row)
        name_row_l.setContentsMargins(0, 0, 0, 0)
        name_row_l.setSpacing(12)
        self._official_name = TouchTextField("Enter name of inspecting official")
        self._official_name.activated.connect(self._activate_text_field)
        name_lbl = QLabel("Name")
        name_lbl.setStyleSheet(
            "color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
        name_lbl.setFixedWidth(250)
        name_row_l.addWidget(name_lbl)
        name_row_l.addWidget(self._official_name, 1)
        body_l.addWidget(name_row)

        desig_row = QWidget()
        desig_row_l = QHBoxLayout(desig_row)
        desig_row_l.setContentsMargins(0, 0, 0, 0)
        desig_row_l.setSpacing(12)
        self._official_designation = TouchTextField("Enter designation")
        self._official_designation.activated.connect(self._activate_text_field)
        desig_lbl = QLabel("Designation")
        desig_lbl.setStyleSheet(
            "color:#4A5568; font-size:9pt; font-weight:600; background:transparent;")
        desig_lbl.setFixedWidth(250)
        desig_row_l.addWidget(desig_lbl)
        desig_row_l.addWidget(self._official_designation, 1)
        body_l.addWidget(desig_row)

        self._text_pad = InlineTextPad()
        body_l.addWidget(self._text_pad)

        root.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        arrow = "▼" if self._expanded else "▶"
        tick = "   ✔" if self._expanded else ""
        self._hdr.setText(f"{arrow}   STATION PARAMETERS{tick}")
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


class DataEntryPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._tables = {}   # key → ParamTableWidget

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ───────────────────────────────────────────────────────
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #DDE3EA;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)

        title = QLabel("SURVEY DATA ENTRY")
        title.setStyleSheet(
            f"color:{CYAN}; font-size:13pt; font-weight:bold; letter-spacing:3px;")
        hdr.addStretch()
        hdr.addWidget(title)
        hdr.addStretch()
        root.addWidget(hdr_w)

        # ── scrollable parameter dropdowns ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(8)

        self._station_params = StationParamsWidget()
        cl.addWidget(self._station_params)

        for key, label, _, unit, color, freq_options in _PARAM_TABLES:
            tw = ParamTableWidget(label, color, unit, freq_options)
            self._tables[key] = tw
            cl.addWidget(tw)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        bottom_w = QWidget()
        bottom_w.setStyleSheet("background:#FFFFFF; border-top:1px solid #DDE3EA;")
        bottom_l = QHBoxLayout(bottom_w)
        bottom_l.setContentsMargins(16, 10, 16, 10)

        back_btn = _btn("← BACK", "BC", 42, 150)
        back_btn.clicked.connect(self.sig_back.emit)
        bottom_l.addStretch()
        bottom_l.addWidget(back_btn)
        bottom_l.addStretch()
        root.addWidget(bottom_w)

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


# ═════════════════════════════════════════════════════════════════════════════
#  CSV VIEWER PAGE
# ═════════════════════════════════════════════════════════════════════════════
class CSVViewerPage(QWidget):
    sig_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_dir = str(Path.home() / "surveys")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ───────────────────────────────────────────────────────
        hdr_w = QWidget()
        hdr_w.setFixedHeight(50)
        hdr_w.setStyleSheet("background:#070707; border-bottom:1px solid #1a1a1a;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(10, 0, 10, 0)
        hdr.setSpacing(8)

        back = _btn("← DASHBOARD", "BC", 40, 170)
        back.clicked.connect(self.sig_back)

        title = QLabel("📋   CSV FILE VIEWER")
        title.setStyleSheet(
            f"color:{MAGI}; font-size:13pt; font-weight:bold; letter-spacing:3px;")

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet("color:#444; font-size:8pt; font-family:'Courier New';")
        self._file_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        browse_btn = _btn("📂  BROWSE", "BM", 40, 130)
        browse_btn.clicked.connect(self._browse)

        hdr.addWidget(back)
        hdr.addSpacing(10)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._file_lbl, 1)
        hdr.addSpacing(8)
        hdr.addWidget(browse_btn)
        root.addWidget(hdr_w)

        # ── file list panel (left) + table (right) ───────────────────────────
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
            f"color:{MAGI}; font-size:8pt; font-weight:bold; letter-spacing:2px;")
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

        refresh_btn = _btn("↺  REFRESH", "BX", 36)
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
        self._table.setStyleSheet(
            f"QTableWidget {{ background:#060606; color:#ccc;"
            f" font-size:8pt; font-family:'Courier New';"
            f" gridline-color:#1a1a1a; border:none; }}"
            f"QHeaderView::section {{ background:#0c0c0c; color:{MAGI};"
            f" font-size:8pt; font-weight:bold; border:1px solid #1a1a1a;"
            f" padding:4px; }}"
            f"QTableWidget::item:selected {{ background:{MAGI}33; color:#fff; }}"
            f"QScrollBar:vertical {{ background:#0a0a0a; width:8px; }}"
            f"QScrollBar::handle:vertical {{ background:#2a2a2a; border-radius:4px; }}"
            f"QScrollBar:horizontal {{ background:#0a0a0a; height:8px; }}"
            f"QScrollBar::handle:horizontal {{ background:#2a2a2a; border-radius:4px; }}"
        )
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

    # ── public ────────────────────────────────────────────────────────────────
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

    # ── internal ──────────────────────────────────────────────────────────────
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
            btn.setStyleSheet(
                f"QPushButton{{background:#0a0a0a; border:1px solid #1e1e1e;"
                f" border-radius:5px; color:{MAGI}; font-size:7pt;"
                f" font-family:'Courier New'; text-align:left; padding-left:8px;}}"
                f"QPushButton:pressed{{background:#140020; border-color:{MAGI};}}")
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
                f"{len(rows)} rows  ·  {len(headers)} columns  ·  {name}")
        except Exception as e:
            self._row_lbl.setText(f"Error loading file: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ═════════════════════════════════════════════════════════════════════════════
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
    sig_cal    = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = False
        self._paused  = False

        # ── ISO RESTYLE ──
        self.setStyleSheet("background:#ECEFF4;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 6)
        lay.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._cards = {}
        for i, (key, title, unit, color) in enumerate(_METRICS):
            card = MetricCard(key, title, unit, color)
            grid.addWidget(card, i // 2, i % 2)
            self._cards[key] = card
        lay.addLayout(grid, 1)

        # ── ISO RESTYLE — separator ──
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#DDE3EA; border:none;")
        lay.addWidget(sep)

        # ── ISO RESTYLE — bottom control bar ──
        bot = QHBoxLayout()
        bot.setContentsMargins(0, 6, 0, 6)
        bot.setSpacing(12)

        self._toggle = QPushButton("▶  START")
        self._toggle.setFixedHeight(58)
        self._toggle.setMinimumWidth(130)
        self._toggle.setStyleSheet(self._ss_start())
        self._toggle.clicked.connect(self._do_toggle)

        self._pause_btn = QPushButton("⏸  PAUSE")
        self._pause_btn.setFixedHeight(58)
        self._pause_btn.setMinimumWidth(130)
        self._pause_btn.setStyleSheet(self._ss_pause())
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._do_pause)

        # vertical separator between pairs
        vsep = QFrame()
        vsep.setFixedSize(1, 40)
        vsep.setStyleSheet("background:#DDE3EA; border:none;")

        self._entry_btn = QPushButton("DATA ENTRY")
        self._entry_btn.setFixedHeight(58)
        self._entry_btn.setMinimumWidth(140)
        self._entry_btn.setStyleSheet(self._ss_action(CYAN))
        self._entry_btn.clicked.connect(self.sig_entry)

        self._cal_btn = QPushButton("CALIBRATE")
        self._cal_btn.setFixedHeight(58)
        self._cal_btn.setMinimumWidth(130)
        self._cal_btn.setStyleSheet(self._ss_action(AMBER))
        self._cal_btn.clicked.connect(self.sig_cal)

        self._stat = QLabel("○  IDLE  0 pts")
        self._stat.setStyleSheet(
            "color:#8A94A6; font-family:'Roboto Mono','Courier New',monospace;"
            " font-size:11pt; font-weight:500; letter-spacing:0.5px;")

        bot.addStretch()
        bot.addWidget(self._toggle)
        bot.addWidget(self._pause_btn)
        bot.addWidget(vsep)
        bot.addWidget(self._entry_btn)
        bot.addWidget(self._cal_btn)
        bot.addSpacing(10)
        bot.addWidget(self._stat)
        bot.addStretch()
        lay.addLayout(bot)

    # ── ISO RESTYLE ──
    def _ss_action(self, color):
        bg = CYAN_LT if color == CYAN else AMBER_LT
        return (
            f"QPushButton{{"
            f" background:{bg}; border:2px solid {color};"
            f" border-radius:8px; color:{color};"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            f"QPushButton:pressed{{"
            f" background:{color}; color:#FFFFFF; border:2px solid {color};}}"
            f"QPushButton:disabled{{"
            f" background:#EEF0F3; border-color:#C8D0DA; color:#B0BAC8;}}")

    # ── ISO RESTYLE ──
    def _ss_start(self):
        return (
            f"QPushButton{{"
            f" background:{NEON}; border:2px solid {NEON};"
            f" border-radius:8px; color:#FFFFFF;"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            f"QPushButton:pressed{{"
            f" background:#145E35; border-color:#145E35; color:#FFFFFF;}}")

    # ── ISO RESTYLE ──
    def _ss_stop(self):
        return (
            f"QPushButton{{"
            f" background:{RED}; border:2px solid {RED};"
            f" border-radius:8px; color:#FFFFFF;"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            f"QPushButton:pressed{{"
            f" background:#8B1A1A; border-color:#8B1A1A; color:#FFFFFF;}}")

    # ── ISO RESTYLE ──
    def _ss_pause(self):
        return (
            f"QPushButton{{"
            f" background:{AMBER_LT}; border:2px solid {AMBER};"
            f" border-radius:8px; color:{AMBER};"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            f"QPushButton:pressed{{"
            f" background:{AMBER}; color:#FFFFFF; border:2px solid {AMBER};}}"
            f"QPushButton:disabled{{"
            f" background:#EEF0F3; border-color:#C8D0DA; color:#B0BAC8;}}")

    # ── ISO RESTYLE ──
    def _ss_resume(self):
        return (
            f"QPushButton{{"
            f" background:{CYAN}; border:2px solid {CYAN};"
            f" border-radius:8px; color:#FFFFFF;"
            f" font-family:'Inter','DM Sans','Liberation Sans',sans-serif;"
            f" font-size:13pt; font-weight:bold; padding:0px 18px;}}"
            f"QPushButton:pressed{{"
            f" background:#0D4A8A; border-color:#0D4A8A; color:#FFFFFF;}}")

    def _do_toggle(self):
        self._running = not self._running
        if self._running:
            self._toggle.setText("■  STOP")
            self._toggle.setStyleSheet(self._ss_stop())
            self._entry_btn.setEnabled(False)
            self._cal_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            self._paused = False
            self._pause_btn.setText("⏸  PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        else:
            self._toggle.setText("▶  START")
            self._toggle.setStyleSheet(self._ss_start())
            self._entry_btn.setEnabled(True)
            self._cal_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._paused = False
            self._pause_btn.setText("⏸  PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_toggle.emit(self._running)

    def _do_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("▶  RESUME")
            self._pause_btn.setStyleSheet(self._ss_resume())
        else:
            self._pause_btn.setText("⏸  PAUSE")
            self._pause_btn.setStyleSheet(self._ss_pause())
        self.sig_pause.emit(self._paused)

    def update_data(self, d):
        for key, card in self._cards.items():
            if key in d:
                card.refresh(d[key])

    def set_session(self, n, running, path=""):
        # ── ISO RESTYLE ──
        col  = NEON if running else "#8A94A6"
        icon = "●  REC" if running else "○  IDLE"
        self._stat.setText(f"{icon}  {n} pts")
        self._stat.setStyleSheet(
            f"color:{col}; font-family:'Roboto Mono','Courier New',monospace;"
            f" font-size:11pt; font-weight:500; letter-spacing:0.5px;")


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
#  — NO Qt.FramelessWindowHint (kills X11 mouse routing)
#  — NO QApplication.setOverrideCursor(Qt.BlankCursor) (hides cursor)
#  — showFullScreen() WITHOUT frameless flag = correct mouse delivery on Ubuntu
# ═════════════════════════════════════════════════════════════════════════════
SCREEN_W, SCREEN_H = 1024, 600


class TrackApp(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg     = load_cfg()
        self.logger  = CSVLogger()
        self.history = {k: [] for k, *_ in _METRICS}

        self.setWindowTitle("Rail Inspection Unit v5.0")
        self.setStyleSheet(SS + "QWidget#TrackApp{background:#ECEFF4;}")  # ── ISO RESTYLE ──

        # sensor thread
        self.sensor = SensorThread(self.cfg)
        self.sensor.data_ready.connect(self._on_data)
        self.sensor.fault.connect(self._on_fault)
        self.sensor.motion.connect(self._on_motion)
        self.sensor.start()

        # ── screen-off timer: 5 min of no encoder motion → blank screen ───────
        self._SCREEN_TIMEOUT_MS = 5 * 60 * 1000   # 5 minutes
        self._last_motion_time  = time.time()
        self._screen_off        = False

        self._screen_timer = QTimer(self)
        self._screen_timer.setInterval(10_000)     # check every 10 s
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

        self.stack = QStackedWidget()

        self.dash = DashboardPage()
        self.dash.sig_toggle.connect(self._on_toggle)
        self.dash.sig_pause.connect(self._on_pause)
        self.dash.sig_entry.connect(lambda: self._goto(2))
        self.dash.sig_cal.connect(lambda: self._goto(1))
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
        # ── ISO RESTYLE ── no status_strip; topbar IS the status bar
        root.addWidget(self.stack, 1)

        # ── WINDOW: fullscreen, WM-managed, mouse cursor VISIBLE ─────────────
        if sys.platform.startswith("linux"):
            self.showFullScreen()    # no FramelessWindowHint → cursor works
        else:
            self.resize(SCREEN_W, SCREEN_H)
            self.show()

    def _goto(self, idx):
        self.stack.setCurrentIndex(idx)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def _on_data(self, d):
        for key in self.history:
            if key in d:
                self.history[key].append(d[key])
                if len(self.history[key]) > 10_000:
                    self.history[key].pop(0)
        self.dash.update_data(d)
        if self.sensor.active:
            self.entry.push_sensor_data(d)
        self.logger.write(d)
        self.dash.set_session(
            self.logger.count, self.sensor.active, self.logger.path or "")

    def _on_fault(self, msg):
        self.topbar.push_error(f"Sensor: {msg}")

    def _on_net(self, bars, cloud):
        self.topbar.update_net(bars, cloud)

    def _on_toggle(self, running):
        self.sensor.active = running
        if running:
            self.logger.set_reference("", "")
            self.logger.set_station("BLE")
            self.sensor.reset()
            self.history = {k: [] for k in self.history}
            self.logger.start(self.cfg["csv_dir"], self.cfg.get("hl_sec", 30))
        else:
            self.logger.stop()

    def _on_pause(self, paused):
        # Pause: stop sensor data collection; Resume: restart it
        self.sensor.active = not paused

    def _on_motion(self, moving):
        """Called every sensor tick; reset idle clock whenever encoder moves."""
        if moving:
            self._last_motion_time = time.time()
            if self._screen_off:
                self._wake_screen()

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
            self.csv_viewer.set_csv_dir(d)

    def _show_graph(self, key):
        meta = {k: (t, u, c) for k, t, u, c in _METRICS}
        if key not in meta:
            return
        title, unit, color = meta[key]
        self.graph_pg.load(title, unit, list(self.history.get(key, [])), color)
        self._goto(3)

    def keyPressEvent(self, e):
        # ESC exits fullscreen — useful for recovery / development
        if e.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.resize(SCREEN_W, SCREEN_H)
        super().keyPressEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Rail Inspection Unit")
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.restoreOverrideCursor()      # guarantee cursor is never hidden
    w = TrackApp()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
