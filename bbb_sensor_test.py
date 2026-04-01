#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bbb_sensor_test.py
==================
BeagleBone Black (Debian Trixie 2026)  --  Terminal Live Sensor Test

Sensors tested:
  ADC0  (Gauge Pot)    P9.39  AIN0  /sys/bus/iio/devices/iio:device0/in_voltage0_raw
  ADC1  (Cross Pot)    P9.40  AIN1  /sys/bus/iio/devices/iio:device0/in_voltage1_raw
  GPIO  (Encoder CLK)  P8.11  GPIO45
  GPIO  (Encoder DT)   P8.12  GPIO44
  GPIO  (Encoder SW)   P8.14  GPIO26
  GPS   (u-blox UART)  P9.11  /dev/ttyS4

NOTES for Debian Trixie (2026-03-17 image):
  - config-pin is GONE. Overlays are loaded in /boot/uEnv.txt at boot time.
  - ADC overlay (BB-ADC) is loaded by DEFAULT on BBB Trixie images.
  - UART4: if /dev/ttyS4 is missing, edit /boot/uEnv.txt and add:
      uboot_overlay_addr4=/lib/firmware/BB-UART4-00A0.dtbo
    OR for newer kernels that ship the built-in UART4 enabled, it may be
    available as /dev/ttyS4 already -- this script will tell you.

WIRING (exact -- no deviations):
  P9.32  VDD_ADC 1.8V  -> Pot(Gauge) Pin1  +  Pot(Cross) Pin1
  P9.34  GNDA_ADC      -> Pot(Gauge) Pin3  +  Pot(Cross) Pin3
  P9.39  AIN0          -> Pot(Gauge) wiper (Pin2)
  P9.40  AIN1          -> Pot(Cross) wiper (Pin2)
  P9.3   3.3V          -> GPS VCC,  Encoder VCC
  P9.1   DGND          -> GPS GND,  Encoder GND
  P9.11  UART4_RX      -> GPS TX pin
  P8.11  GPIO45        -> Encoder CLK
  P8.12  GPIO44        -> Encoder DT
  P8.14  GPIO26        -> Encoder SW (push button)

Run:
  python3 bbb_sensor_test.py

Press Ctrl+C to stop and view per-sensor diagnostic status.
"""

import os
import sys
import time
import subprocess

# ─── Hardware paths ───────────────────────────────────────────────────────────
ADC0      = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
ADC1      = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
GPIO_BASE = "/sys/class/gpio"
CLK_GPIO  = 45   # P8.11
DT_GPIO   = 44   # P8.12
SW_GPIO   = 26   # P8.14
GPS_PORT  = "/dev/ttyS4"
GPS_BAUD  = 9600

# ─── Physics constants ────────────────────────────────────────────────────────
GAUGE_STD = 1676.0          # Indian BG standard gauge mm
ADC_BITS  = 4096
ADC_MID   = 2048
INCL_FS   = 30.0            # Inclinometer full-scale ±deg
DEG_TO_MM = 17.453          # mm/deg for cross-level (1000mm chord)
PPR       = 20              # Encoder pulses/revolution
WHEEL_MM  = 195.0           # Measuring wheel circumference mm (≈62mm dia × π)
DEADBAND  = 5               # ADC counts to ignore (noise suppressor)


# ─── Boot-time overlay check (Trixie: no config-pin) ─────────────────────────
def _run_silent(cmd):
    try:
        subprocess.call(cmd,
                        stdout=open(os.devnull, "w"),
                        stderr=open(os.devnull, "w"))
    except Exception:
        pass


def ensure_adc():
    """Try to modprobe the ADC kernel module (safe to call multiple times)."""
    _run_silent(["sudo", "modprobe", "ti_am335x_adc"])
    time.sleep(0.5)


# ─── ADC ──────────────────────────────────────────────────────────────────────
def adc_read(path):
    """
    BBB IIO ADC driver workaround:
    First file-read returns the PREVIOUS (stale) sample.
    Open and read twice; return only the second value.
    """
    if not os.path.exists(path):
        return -1
    try:
        with open(path) as f:
            f.read()          # discard stale first read
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return -1


# ─── GPIO sysfs ───────────────────────────────────────────────────────────────
def gpio_export(num):
    val_path = "{}/gpio{}/value".format(GPIO_BASE, num)
    if not os.path.exists(val_path):
        try:
            with open("{}/export".format(GPIO_BASE), "w") as f:
                f.write(str(num))
            time.sleep(0.1)
            with open("{}/gpio{}/direction".format(GPIO_BASE, num), "w") as f:
                f.write("in")
        except Exception as e:
            print("[GPIO] Cannot export GPIO{}: {}".format(num, e))


def gpio_read(num):
    try:
        with open("{}/gpio{}/value".format(GPIO_BASE, num)) as f:
            return int(f.read().strip())
    except Exception:
        return 1   # pull-up default = HIGH = not pressed


# ─── Rotary Encoder ───────────────────────────────────────────────────────────
_enc_count   = 0
_enc_last_clk = None


def encoder_tick():
    global _enc_count, _enc_last_clk
    clk = gpio_read(CLK_GPIO)
    dt  = gpio_read(DT_GPIO)
    if _enc_last_clk is None:
        _enc_last_clk = clk
        return
    if clk != _enc_last_clk:
        _enc_count += 1 if (dt != clk) else -1
    _enc_last_clk = clk


def encoder_distance_m():
    return round(abs(_enc_count) / max(1, PPR) * WHEEL_MM / 1000.0, 4)


# ─── GPS ──────────────────────────────────────────────────────────────────────
_gps_ser  = None
_gps_buf  = ""
_gps_lat  = 0.0
_gps_lon  = 0.0
_gps_spd  = 0.0
_gps_fix  = 0
_gps_sats = 0


def gps_open():
    global _gps_ser
    if not os.path.exists(GPS_PORT):
        return
    try:
        import serial
        _gps_ser = serial.Serial(GPS_PORT, GPS_BAUD,
                                 bytesize=8, parity="N",
                                 stopbits=1, timeout=0.05)
    except ImportError:
        print("\n[GPS] pyserial not installed -- run:  pip3 install pyserial")
    except Exception as e:
        print("\n[GPS] Cannot open {}: {}".format(GPS_PORT, e))


def _nmea_to_dec(raw, direction):
    try:
        raw = raw.strip()
        if not raw or "." not in raw:
            return 0.0
        i   = raw.index(".")
        deg = float(raw[:i - 2])
        mn  = float(raw[i - 2:])
        dec = deg + mn / 60.0
        return round(-dec if direction.upper() in ("S", "W") else dec, 7)
    except Exception:
        return 0.0


def _parse_nmea(line):
    global _gps_lat, _gps_lon, _gps_spd, _gps_fix, _gps_sats
    try:
        if "*" in line:
            line = line[:line.rindex("*")]
        if not line.startswith("$"):
            return
        p   = line.split(",")
        tag = p[0].upper()
        if "GGA" in tag and len(p) >= 10:
            q = int(p[6]) if p[6].strip().isdigit() else 0
            _gps_fix = q
            if q >= 1 and p[2] and p[4]:
                la = _nmea_to_dec(p[2], p[3])
                lo = _nmea_to_dec(p[4], p[5])
                if la or lo:
                    _gps_lat = la
                    _gps_lon = lo
            try:
                _gps_sats = int(p[7]) if p[7].strip().isdigit() else _gps_sats
            except Exception:
                pass
        elif "RMC" in tag and len(p) >= 8 and p[2].upper() == "A":
            if len(p) > 5 and p[3] and p[5]:
                la = _nmea_to_dec(p[3], p[4])
                lo = _nmea_to_dec(p[5], p[6])
                if la or lo:
                    _gps_lat = la
                    _gps_lon = lo
            if len(p) > 7 and p[7].strip():
                _gps_spd = round(float(p[7]) * 1.852, 1)
    except Exception:
        pass


def gps_poll():
    global _gps_buf
    if _gps_ser is None:
        return
    try:
        n = _gps_ser.in_waiting
        if n > 0:
            _gps_buf += _gps_ser.read(n).decode("ascii", errors="replace")
            while "\n" in _gps_buf:
                line, _gps_buf = _gps_buf.split("\n", 1)
                _parse_nmea(line.strip())
    except Exception:
        pass


# ─── Wiring Diagnostics ───────────────────────────────────────────────────────
def _adc_status(raw, name, pin):
    """Return (status_letter, description) for display."""
    if raw < 0:
        return "ERR", "{} | {} | NOT FOUND -- check modprobe ti_am335x_adc".format(name, pin)
    if raw < 20:
        return "FAULT", "{} | {} | raw={} -- Disconnected or Pin1 NOT on P9.32 (1.8V)".format(name, pin, raw)
    if raw > 4075:
        return "FAULT", "{} | {} | raw={} -- Saturated: Pin1 is on P9.3 (3.3V), move to P9.32".format(name, pin, raw)
    pct = int(raw / 40.96)
    return "OK", "{} | {} | raw={:>4}  {:>3}%  [{:<20}]".format(
        name, pin, raw, pct, "=" * (pct // 5))


def _gpio_status(pin_num, name, pin_label, last_val):
    try:
        v = gpio_read(pin_num)
        return "OK", "{} | {} | gpio{}  val={}".format(name, pin_label, pin_num, v)
    except Exception as e:
        return "FAULT", "{} | {} | gpio{}  ERROR: {}".format(name, pin_label, pin_num, e)


def _gps_status():
    if not os.path.exists(GPS_PORT):
        return "MISS", "GPS  | /dev/ttyS4 | PORT NOT FOUND -- UART4 overlay not loaded"
    if _gps_ser is None:
        return "ERR", "GPS  | /dev/ttyS4 | Port found but failed to open (pyserial?)"
    if _gps_fix == 0:
        return "WAIT", "GPS  | /dev/ttyS4 | Port open, NO FIX yet -- take outdoors & wait 60s"
    return "OK", "GPS  | /dev/ttyS4 | FIX={} | sats={} | {:.7f},{:.7f} | {:.1f}km/h".format(
        _gps_fix, _gps_sats, _gps_lat, _gps_lon, _gps_spd)


STATUS_COLOR = {
    "OK":    "\033[92m",  # green
    "WAIT":  "\033[93m",  # yellow
    "FAULT": "\033[91m",  # red
    "ERR":   "\033[91m",  # red
    "MISS":  "\033[91m",  # red
}
RESET = "\033[0m"
BOLD  = "\033[1m"


def print_status_block(final=False):
    r0  = adc_read(ADC0)
    r1  = adc_read(ADC1)
    enc_ok = os.path.exists("{}/gpio{}/value".format(GPIO_BASE, CLK_GPIO))

    rows = []
    for raw, name, pin in [(r0, "ADC0-GAUGE", "P9.39"),
                            (r1, "ADC1-CROSS", "P9.40")]:
        st, msg = _adc_status(raw, name, pin)
        rows.append((st, msg))

    for gnum, name, plbl in [(CLK_GPIO, "ENC-CLK", "P8.11"),
                              (DT_GPIO,  "ENC-DT ", "P8.12"),
                              (SW_GPIO,  "ENC-SW ", "P8.14")]:
        st = "OK" if os.path.exists("{}/gpio{}/value".format(GPIO_BASE, gnum)) else "ERR"
        val = gpio_read(gnum) if st == "OK" else "?"
        msg = "{} | {} | gpio{}  val={}".format(name, plbl, gnum, val)
        rows.append((st, msg))

    gst, gmsg = _gps_status()
    rows.append((gst, gmsg))

    title = "FINAL STATUS AFTER Ctrl+C" if final else "HARDWARE STATUS CHECK"
    print("\n" + BOLD + "=" * 74 + RESET)
    print(BOLD + " " + title + RESET)
    print(BOLD + "=" * 74 + RESET)
    for st, msg in rows:
        col = STATUS_COLOR.get(st, "")
        print("  {}[{:<5}]{} {}".format(col, st, RESET, msg))
    print(BOLD + "=" * 74 + RESET + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(BOLD + "\n===  BBB SENSOR LIVE TEST  (Debian Trixie)  ===" + RESET)
    print("Loading ADC kernel module (modprobe ti_am335x_adc)...")
    ensure_adc()

    # GPIO export
    for g in (CLK_GPIO, DT_GPIO, SW_GPIO):
        gpio_export(g)

    # Check ADC presence
    has_adc0 = os.path.exists(ADC0)
    has_adc1 = os.path.exists(ADC1)

    print()
    print(" ADC0 (Gauge, P9.39) : " +
          ("\033[92mFOUND\033[0m" if has_adc0 else "\033[91mMISSING\033[0m -- sudo modprobe ti_am335x_adc"))
    print(" ADC1 (Cross, P9.40) : " +
          ("\033[92mFOUND\033[0m" if has_adc1 else "\033[91mMISSING\033[0m -- same module needed"))
    print(" GPS  (/dev/ttyS4)   : " +
          ("\033[92mFOUND\033[0m" if os.path.exists(GPS_PORT)
           else "\033[91mMISSING\033[0m -- UART4 overlay not loaded (see /boot/uEnv.txt)"))
    print()

    # Open GPS
    gps_open()

    # Initial wiring check
    print_status_block(final=False)

    if not has_adc0:
        print("\033[91m" + "CRITICAL: ADC not found. Cannot read potentiometers." + "\033[0m")
        print("On Debian Trixie with built-in overlays the ADC should auto-load.")
        print("Try:  sudo modprobe ti_am335x_adc")
        print("If still missing, add to /boot/uEnv.txt:")
        print("  uboot_overlay_addr4=/lib/firmware/BB-ADC-00A0.dtbo")
        print("Then reboot and retry.\n")
        sys.exit(1)

    # ── Column header ────────────────────────────────────────────────────────
    HDR = (
        " {:<8} | {:<4} {:<4} {:<10} | "
        "{:<4} {:<4} {:<10} | "
        "{:<5} {:<9} {:<3} | "
        "{:<3} {:<5} | {}"
    ).format(
        "TIME",
        "RAW0", "RAW1", "  (ADC vals)",
        "CLK", "DT", "ENCPULSES",
        "DIST", "GAUGE(mm)", "CROSS",
        "FIX", "SPD",
        "STATUS"
    )
    print(BOLD + HDR + RESET)
    print("-" * len(HDR))

    _prev_r0 = -1
    _prev_r1 = -1
    _gauge_mm  = 1676.0
    _cross_mm  = 0.0

    try:
        while True:
            # Poll encoder rapidly (20 times × 10ms = 200ms effective polling)
            for _ in range(20):
                encoder_tick()
                time.sleep(0.010)

            # ADC reads
            r0 = adc_read(ADC0) if has_adc0 else -1
            r1 = adc_read(ADC1) if has_adc1 else -1

            # Gauge mm (only update if past deadband)
            if r0 >= 0 and (_prev_r0 < 0 or abs(r0 - _prev_r0) >= DEADBAND):
                _prev_r0  = r0
                raw_gauge = 1676.0 + (r0 - ADC_MID) * (150.0 / ADC_BITS)
                _gauge_mm = round(max(1601.0, min(1751.0, raw_gauge)), 1)

            # Cross-level mm (piecewise, matching integrated_rail.py)
            if r1 >= 0 and (_prev_r1 < 0 or abs(r1 - _prev_r1) >= DEADBAND):
                _prev_r1 = r1
                if r1 <= ADC_MID:
                    _cross_mm = round((r1 / float(ADC_MID)) * 5.0 - 5.0, 2)
                else:
                    _cross_mm = round(((r1 - ADC_MID) / 2047.0) * 10.0, 2)
                _cross_mm = max(-75.0, min(75.0, _cross_mm))

            gps_poll()
            dist = encoder_distance_m()

            # Format time
            now_t = time.strftime("%H:%M:%S")

            # Fault flags
            g_disp = "DISCONN" if (r0 < 20) else "{:.1f}".format(_gauge_mm)
            c_disp = "3.3V-ERR" if (r1 > 4075) else "{:.2f}".format(_cross_mm)

            # GPS status
            if not os.path.exists(GPS_PORT):
                gps_disp = "NO PORT"
            elif _gps_fix > 0:
                gps_disp = "FIX{} {}s".format(_gps_fix, _gps_sats)
            else:
                gps_disp = "NO FIX"

            clk_v = gpio_read(CLK_GPIO)
            dt_v  = gpio_read(DT_GPIO)

            line = (
                " {:<8} | {:<4} {:<4}              | "
                "{:<4} {:<4} {:<10} | "
                "{:<5.3f} {:<9} {:<8} | "
                "{:<3} {:.1f}km/h| {}"
            ).format(
                now_t,
                r0 if r0 >= 0 else "ERR",
                r1 if r1 >= 0 else "ERR",
                clk_v, dt_v, _enc_count,
                dist, g_disp, c_disp,
                _gps_fix, _gps_spd,
                gps_disp,
            )

            # Overwrite the same line in terminal
            sys.stdout.write("\r" + line)
            sys.stdout.flush()

    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        print_status_block(final=True)

        # GPS detail
        if _gps_ser is None and not os.path.exists(GPS_PORT):
            print("\033[91m[UART4 FIX]\033[0m /dev/ttyS4 not found.")
            print("  The Debian Trixie image may need an overlay in /boot/uEnv.txt.")
            print("  Check what overlays are available:")
            print("    ls /lib/firmware/ | grep UART")
            print("  Then add to /boot/uEnv.txt:")
            print("    uboot_overlay_addr4=/lib/firmware/<UART4-OVERLAY>.dtbo")
            print("  Reboot and re-run this script.\n")
        elif _gps_fix == 0:
            print("\033[93m[GPS WAIT]\033[0m Port open but no fix.")
            print("  - Move the unit outdoors with clear sky view.")
            print("  - Wait up to 90 seconds for cold-start acquisition.")
            print("  - Verify wiring: GPS TX -> P9.11, VCC->P9.3, GND->P9.1\n")
        else:
            print("\033[92m[GPS OK]\033[0m fix={} sats={} lat={} lon={}".format(
                _gps_fix, _gps_sats, _gps_lat, _gps_lon))

        print("Encoder final count: {}  distance: {:.4f} m\n".format(
            _enc_count, encoder_distance_m()))


if __name__ == "__main__":
    main()
